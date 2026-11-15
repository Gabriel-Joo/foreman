"""Notion 게시 설정을 각 프로젝트 저장소로(11-12 사용자 지시) — `<저장소>/.foreman/notion.toml`(그 저장소 origin/main에서 읽는다).

- 그 프로젝트가 **push한 판만** 읽는다(`git show origin/main:.foreman/notion.toml`) — 작업 트리 · 안 올린 커밋은 보지 않는다
- 파일이 있으면 아래 REPO_KEYS는 **모두 그 파일 것**(FOREMAN `config/notion.toml`의 같은 칸은 쓰지 않는다 — 경고만).
  칸마다 섞지 않는 까닭: 두 곳에 같은 칸이 있으면 저장소에서 칸을 지워도 FOREMAN 값이 살아남아 조용히 다르게 돈다
- 파일이 없으면 지금처럼 FOREMAN `config/notion.toml`의 그 칸(런슈즈 · 펫퍼민트 — 아무것도 달라지지 않는다)
- **쓰기 범위를 정하는 칸은 FOREMAN에만**(FOREMAN_ONLY) — 저장소 파일에 있으면 쓰지 않고 경고(남의 프로젝트 페이지를 root로
  적어 고치는 길을 막는다). Notion 토큰(`.env.notion`) · 짝(`doc_publish`)도 FOREMAN 그대로
- 다시 읽기: 맞추기 주기(bridge/docsync.py DocSync, 5분)마다. 파일 blob이 그대로면 다시 풀지 않는다.
  깨진 파일(TOML 오류 · 칸 형식 · origin/main 없음)이면 **옛 설정을 그대로 쓰고 알린다**(텔레그램 · 로그 · GET /api/publish의 config) —
  조용히 꺼지거나 FOREMAN 칸으로 돌아가지 않는다. 브리지가 뜰 때 이미 깨져 있으면 옛 설정이 없으니 FOREMAN 칸 + 알림
  (저장소 파일을 한 번도 쓰지 않은 프로젝트만 — 아래 「게시 멈춤」)
- 읽는 판(ref)은 그 프로젝트 FOREMAN 칸의 `ref`(없으면 origin/main) — 문서 게시와 같은 판(11-12 사용자 지시)
- **게시 멈춤(11-12 사용자 지시)**: 한 번이라도 저장소 파일로 돈 프로젝트는 `.run/notion_repo_config.json`(MEMORY_FILE)에 기억한다
  (브리지를 다시 띄워도 남는다). 그 프로젝트가 저장소 파일을 **잃으면** — 지워짐, 또는 깨졌는데 쓸 마지막 판이 없음(다시 띄운 뒤) —
  FOREMAN 칸으로 떨어지지 않고 게시를 멈춘다: 게시기에 `config_halt`(사유 글)를 달고, POST /api/publish · 짝 등록 · 자동 맞추기가
  그것을 보고 거절한다. 알림 = 텔레그램 한 번 · 로그 · GET /api/publish의 config(halted · source · error) · 서기 할 일 줄.
  파일이 바르게 돌아오면 다시 돌고 한 번 알린다. 일부러 FOREMAN 칸으로 되돌리려면 관리 토큰으로
  DELETE /api/publish/repo-config?project=<이름>(forget) — 기억을 지우고 FOREMAN 칸으로 다시 읽는다

파일 꼴(표 없이 맨 위 칸만):
    docs = "manual"
    skip = ["docs/README.md"]
    title = "h1"
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

log = logging.getLogger("foreman.notioncfg")

REPO_FILE = ".foreman/notion.toml"
REPO_REF = "origin/main"
MEMORY_FILE = "notion_repo_config.json"     # .run/ 아래 — 저장소 파일로 돈 적이 있는 프로젝트(브리지를 다시 띄워도 남게)

# 저장소 파일이 정할 수 있는 칸 — 여기 한 곳에만 둔다(bridge/notion.py Publisher.configure가 읽는 칸과 같다). 값의 형식도 본다
REPO_KEYS: dict[str, tuple[type, ...]] = {
    "docs": (str,),             # off · manual · auto
    "quiet_min": (int, float),  # auto의 기다림(분)
    "skip": (list,),            # 맞추기 대상이 아닌 docs 파일 · "…/" 폴더
    "create": (bool,),          # 짝 없는 문서를 새로 만드나
    "archive": (bool,),         # 원본이 사라지면 휴지통으로 보내나
    "title": (str,),            # keep · h1
    "order": (str,),            # keep
    "header": (str,),           # footer
    "headings": (str,),         # md
    "keep_notion": (list,),     # inline_code · image · heading · shape
    "new_parent": (str,),       # folder
    "new_title": (str,),        # numbered
}
# Publisher opts로 넘기는 칸(docs · quiet_min은 따로 받는다) — 옛 bridge/main.py 목록과 같다
OPT_KEYS = tuple(k for k in REPO_KEYS if k not in ("docs", "quiet_min"))
# FOREMAN config/notion.toml에서만 — 쓰기 범위(root · docs_page · portfolio_page)와 원본 커밋 · 링크(ref · github: push한 판만 읽는다는 약속)
FOREMAN_ONLY = ("root", "docs_page", "portfolio_page", "github", "ref")
DOCS_MODES = ("off", "manual", "auto")


def base_args(ncfg: dict[str, Any]) -> dict[str, Any]:
    """FOREMAN 칸 → Publisher.configure 인자. 옛 bridge/main.py와 같은 식(바꾸지 않은 프로젝트가 그대로 돌게)."""
    return {"docs_mode": ncfg.get("docs") or "off", "quiet_min": float(ncfg.get("quiet_min") or 30),
            "opts": {k: ncfg.get(k) for k in OPT_KEYS if k in ncfg}}


# 멈췄는데 쓸 마지막 판도 없을 때(다시 띄운 뒤) 게시기에 줄 인자 — 게시는 config_halt로 모두 거절되지만, 그 문도 뚫렸을 때를 대비해
# 쓰기를 가장 좁게(새로 만들지 않음 · 휴지통 안 보냄 · 차례 · 제목 그대로). docs는 manual — off면 서기 화면이 기술문서 줄을 숨겨 멈춤이 안 보인다
HALT_ARGS = base_args({"docs": "manual", "create": False, "archive": False, "order": "keep", "title": "keep"})


def halt_message(name: str, why: str) -> str:
    return (f"{name}의 {REPO_FILE}을 읽지 못해 게시를 멈췄습니다({why}). 파일을 되살리거나 FOREMAN 관리자에게 알려 주십시오")


def read_repo_file(repo: str, ref: str = REPO_REF) -> tuple[str | None, str | None, str | None]:
    """(글, blob 해시, 오류). 파일이 없으면 (None, None, None). ref 자체가 없으면 오류(파일 없음과 가른다 — 조용히 FOREMAN 칸으로 가지 않게)."""
    def git(*a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=15)
    try:
        if git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
            return None, None, f"{ref}이 없습니다({repo})"
        b = git("rev-parse", "--verify", "--quiet", f"{ref}:{REPO_FILE}")
        if b.returncode != 0:
            return None, None, None
        blob = b.stdout.strip()
        r = git("cat-file", "blob", blob)
        if r.returncode != 0:
            return None, blob, f"{REPO_FILE}을 읽지 못했습니다: {r.stderr.strip()[:120]}"
        return r.stdout, blob, None
    except (OSError, subprocess.SubprocessError) as e:
        return None, None, f"git을 부르지 못했습니다: {type(e).__name__}"


def parse_repo_file(text: str) -> tuple[dict[str, Any], list[str]]:
    """저장소 파일 → (쓸 칸, 경고). 깨졌으면 ValueError(사유). FOREMAN_ONLY · 모르는 칸은 쓰지 않고 경고."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"TOML을 읽지 못했습니다: {e}") from e
    out: dict[str, Any] = {}
    warns: list[str] = []
    for k, v in raw.items():
        if k in FOREMAN_ONLY:
            warns.append(f"{k}는 FOREMAN config/notion.toml에서만 정합니다 — 저장소 파일의 값은 쓰지 않습니다")
            continue
        if k not in REPO_KEYS:
            warns.append(f"모르는 칸 {k} — 쓰지 않습니다")
            continue
        types = REPO_KEYS[k]
        if isinstance(v, bool) and bool not in types:          # True는 int이기도 하다 — quiet_min = true를 숫자로 받지 않게
            raise ValueError(f"{k}의 형식이 틀렸습니다({type(v).__name__})")
        if not isinstance(v, types):
            raise ValueError(f"{k}의 형식이 틀렸습니다({type(v).__name__})")
        if isinstance(v, list) and not all(isinstance(x, str) for x in v):
            raise ValueError(f"{k}는 글자 목록이어야 합니다")
        if k == "docs" and v not in DOCS_MODES:
            raise ValueError(f"docs = {v!r}을 모릅니다(off · manual · auto)")
        if k == "quiet_min" and v < 0:
            raise ValueError("quiet_min은 0 이상이어야 합니다")
        out[k] = v
    return out, warns


class NotionConfig:
    """프로젝트마다 지금 쓰는 설정의 출처 · 경고 · 오류(GET /api/publish의 config). 다시 읽기는 refresh."""

    def __init__(self, base: dict[str, dict[str, Any]], notifier: Any = None, ref: str = REPO_REF,
                 memory: str | Path | None = None) -> None:
        """ref — FOREMAN 칸에 ref가 없을 때 읽을 판. memory — 저장소 파일로 돈 적이 있는 프로젝트를 남길 파일(없으면 이 프로세스 안에서만)."""
        self.base, self.notifier, self.ref = base, notifier, ref
        self.state: dict[str, dict[str, Any]] = {}
        self._args: dict[str, dict[str, Any]] = {}      # 마지막으로 적용한 인자(깨진 파일이면 이것을 그대로 쓴다)
        self._sent: set[str] = set()
        self.halted: dict[str, str] = {}                # 프로젝트 → 게시를 멈춘 사유(halt_message) — 게시기의 config_halt
        self.memory = Path(memory) if memory else None
        self.seen: dict[str, dict[str, Any]] = self._load()

    def ref_for(self, name: str) -> str:
        """저장소 파일을 읽는 판 — 그 프로젝트 FOREMAN 칸의 ref(문서 게시와 같은 판), 없으면 origin/main."""
        return (self.base.get(name) or {}).get("ref") or self.ref

    # ── 기억(저장소 파일로 돈 적이 있는 프로젝트) ──────────────────
    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.memory or not self.memory.exists():
            return {}
        try:
            raw = json.loads(self.memory.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not all(isinstance(v, dict) for v in raw.values()):
                raise ValueError("꼴이 틀렸습니다")
            return raw
        except (OSError, ValueError) as e:
            # 기억이 깨지면 「저장소 파일을 쓰던 프로젝트」를 잊는다 — 조용히 FOREMAN 칸으로 떨어질 수 있으니 알리고, 깨진 파일은 옆에 남긴다
            try:
                os.replace(self.memory, self.memory.with_name(self.memory.name + ".broken"))
            except OSError:
                pass
            self._say("foreman", f"{self.memory.name}을 읽지 못했습니다({type(e).__name__}) — 저장소 설정을 쓰던 프로젝트를 잊었을 수 "
                                 f"있습니다. 깨진 파일은 {self.memory.name}.broken으로 옮겼습니다")
            return {}

    def _save(self, name: str) -> None:
        if not self.memory:
            return
        try:
            self.memory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tmp = self.memory.with_name(self.memory.name + ".tmp")
            tmp.write_text(json.dumps(self.seen, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.memory)
        except OSError as e:
            self._alert(name, f"{self.memory.name}에 쓰지 못했습니다({type(e).__name__}) — 브리지를 다시 띄우면 이 프로젝트가 "
                              f"저장소 설정을 쓰던 것을 잊습니다", "memory-write")

    def _remember(self, name: str, blob: str | None, ref: str) -> None:
        old = self.seen.get(name)
        if old and old.get("blob") == blob and old.get("ref") == ref and not old.get("halted"):
            return
        now = time.time()
        self.seen[name] = {"blob": blob, "ref": ref, "first_at": (old or {}).get("first_at", now), "last_at": now}
        self._save(name)

    def forget(self, name: str, pub: Any = None) -> bool:
        """저장소 설정 기억 지우기(관리 토큰만 — DELETE /api/publish/repo-config). 일부러 FOREMAN 칸으로 되돌릴 때.
        저장소 파일이 아직 있으면 다음 읽기에서 다시 기억한다(파일을 먼저 지우고 부른다). 기억이 있었나."""
        had = self.seen.pop(name, None) is not None
        if had:
            self._save(name)
        self.halted.pop(name, None)
        self.state.pop(name, None)
        self._args.pop(name, None)
        if pub is not None:
            pub.configure(**self.args_for(name, pub.repo))
            pub.config_halt = self.halted.get(name)
        self._say(name, f"저장소 설정 기억을 지웠습니다 — 이제 {REPO_FILE}이 없으면 FOREMAN config/notion.toml 칸으로 돕니다")
        return had

    def args_for(self, name: str, repo: str) -> dict[str, Any]:
        """지금 쓸 Publisher.configure 인자를 정하고 state를 남긴다. 게시를 멈춰야 하면 halted[name]에 사유."""
        ncfg = self.base.get(name) or {}
        ref = self.ref_for(name)
        text, blob, err = read_repo_file(repo, ref)
        prev = self.state.get(name) or {}
        if (not err and text is not None and blob == prev.get("blob") and prev.get("ref") == ref and not prev.get("error")
                and name in self._args):
            prev["checked_at"] = time.time()
            return self._args[name]                    # 그대로 — 다시 풀지 않는다
        st: dict[str, Any] = {"file": REPO_FILE, "ref": ref, "blob": blob, "source": "foreman", "warnings": [],
                              "error": None, "halted": False, "checked_at": time.time()}
        fields: dict[str, Any] | None = None
        if not err and text is not None:
            try:
                fields, st["warnings"] = parse_repo_file(text)
            except ValueError as e:
                err = str(e)
        seen = name in self.seen
        if err and seen and (name not in self._args or name in self.halted):
            # 저장소 파일을 쓰던 프로젝트인데 깨졌고 쓸 마지막 판이 없다(브리지를 다시 띄운 뒤 · 이미 멈춘 채) — FOREMAN 칸으로 떨어지지 않는다
            args = self._halt(name, st, f"깨짐 — {err}")
        elif fields is None and not err and seen:
            args = self._halt(name, st, f"{ref}에 파일이 없습니다")
        elif err:
            st["error"] = err
            if name in self._args:                     # 옛 설정 그대로(조용히 꺼지지 않게)
                st["source"] = prev.get("source", "foreman")
                st["stale"] = True
                args = self._args[name]
                self._alert(name, f"{REPO_FILE}이 깨져 옛 설정을 그대로 씁니다 — {err}", blob or err)
            else:                                      # 브리지가 뜰 때부터 깨짐 — 옛 설정이 없으니 FOREMAN 칸
                args = base_args(ncfg)
                self._alert(name, f"{REPO_FILE}이 깨져 FOREMAN config/notion.toml 칸으로 돌았습니다 — {err}", blob or err)
        elif fields is None:
            args = base_args(ncfg)
        else:
            st["source"] = "repo"
            unused = [k for k in REPO_KEYS if k in ncfg]
            if unused:
                st["warnings"].append(f"저장소 파일이 앞서 FOREMAN 칸의 {', '.join(unused)}는 쓰지 않습니다")
            args = base_args(fields)
            if st["warnings"]:
                self._alert(name, f"{REPO_FILE} 경고 — " + " · ".join(st["warnings"]), blob or "")
            # 멈춰 있다가 돌아옴 — 한 번 알린다(바뀔 때만 오니 되풀이되지 않는다). 멈춘 채 브리지를 다시 띄웠어도 기억 파일의 halted로 안다
            was = self.halted.pop(name, None) or (self.seen.get(name) or {}).get("halted")
            self._remember(name, blob, ref)
            if was:
                self._say(name, f"{REPO_FILE}을 다시 읽었습니다({ref}) — 게시를 다시 돌립니다")
        self.state[name] = st
        self._args[name] = args
        return args

    def _halt(self, name: str, st: dict[str, Any], why: str) -> dict[str, Any]:
        msg = halt_message(name, why)
        st.update(source="repo", halted=True, error=msg)
        if self.halted.get(name) != msg:                  # 멈추기 시작할 때 · 사유가 바뀔 때만 — 같은 상태면 한 번(다시 띄우면 한 번 더 — 멈춰 있다는 것을 다시 알린다)
            self._say(name, f"🛑 {msg}")
        self.halted[name] = msg
        rec = self.seen.get(name)
        if rec is not None and rec.get("halted") != msg:  # 기억 파일에도 — 다시 띄운 뒤 돌아왔을 때 「다시 돌립니다」를 보내려고
            rec["halted"] = msg
            self._save(name)
        return HALT_ARGS

    def mark(self, pubs: dict[str, Any]) -> None:
        """게시기에 멈춤 표시(config_halt)를 단다 — POST /api/publish · 짝 등록 · 맞추기가 이것을 보고 거절한다."""
        for name, pub in pubs.items():
            pub.config_halt = self.halted.get(name)

    def refresh(self, pubs: dict[str, Any]) -> list[str]:
        """게시기마다 다시 읽어 바뀐 것만 configure. 바뀐 프로젝트 이름들. 한 프로젝트가 막혀도 나머지는 본다."""
        changed = []
        for name, pub in pubs.items():
            try:
                old = self._args.get(name)
                new = self.args_for(name, pub.repo)
                if new != old:
                    pub.configure(**new)
                    changed.append(name)
                    log.warning("Notion 게시 설정을 다시 읽었습니다(%s, 출처 %s)", name, self.state[name]["source"])
            except Exception as e:  # noqa: BLE001 — 다시 읽기 실패는 옛 설정 그대로
                log.warning("Notion 게시 설정 다시 읽기 실패(%s): %s", name, type(e).__name__)
            pub.config_halt = self.halted.get(name)
        return changed

    def _alert(self, name: str, msg: str, key: str) -> None:
        """같은 것은 한 번만(이 프로세스 안)."""
        k = f"{name}:{key}:{msg[:60]}"
        if k in self._sent:
            return
        self._sent.add(k)
        self._say(name, msg)

    def _say(self, name: str, msg: str) -> None:
        """로그 + 텔레그램. 멈춤 · 다시 돎은 바뀔 때만 부르므로 여기서 거르지 않는다."""
        log.warning("Notion 게시 설정(%s): %s", name, msg)
        if not self.notifier:
            return
        try:
            rule = self.notifier.rules.for_project(name)
            prefix = rule.prefix if rule else f"[{name}]"
            self.notifier.send_direct(name, "docsync", None, f"{prefix} ⚠ Notion 게시 설정 — {msg}")
        except Exception as e:  # noqa: BLE001 — 알림 실패가 설정을 막지 않는다(로그에는 남았다)
            log.warning("설정 알림 실패: %s", type(e).__name__)
