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

파일 꼴(표 없이 맨 위 칸만):
    docs = "manual"
    skip = ["docs/README.md"]
    title = "h1"
"""

from __future__ import annotations

import logging
import subprocess
import time
import tomllib
from typing import Any

log = logging.getLogger("foreman.notioncfg")

REPO_FILE = ".foreman/notion.toml"
REPO_REF = "origin/main"

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

    def __init__(self, base: dict[str, dict[str, Any]], notifier: Any = None, ref: str = REPO_REF) -> None:
        self.base, self.notifier, self.ref = base, notifier, ref
        self.state: dict[str, dict[str, Any]] = {}
        self._args: dict[str, dict[str, Any]] = {}      # 마지막으로 적용한 인자(깨진 파일이면 이것을 그대로 쓴다)
        self._sent: set[str] = set()

    def args_for(self, name: str, repo: str) -> dict[str, Any]:
        """지금 쓸 Publisher.configure 인자를 정하고 state를 남긴다."""
        ncfg = self.base.get(name) or {}
        text, blob, err = read_repo_file(repo, self.ref)
        prev = self.state.get(name) or {}
        if not err and text is not None and blob == prev.get("blob") and not prev.get("error") and name in self._args:
            prev["checked_at"] = time.time()
            return self._args[name]                    # 그대로 — 다시 풀지 않는다
        st: dict[str, Any] = {"file": REPO_FILE, "ref": self.ref, "blob": blob, "source": "foreman", "warnings": [],
                              "error": None, "checked_at": time.time()}
        fields: dict[str, Any] | None = None
        if not err and text is not None:
            try:
                fields, st["warnings"] = parse_repo_file(text)
            except ValueError as e:
                err = str(e)
        if err:
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
        self.state[name] = st
        self._args[name] = args
        return args

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
        return changed

    def _alert(self, name: str, msg: str, key: str) -> None:
        k = f"{name}:{key}:{msg[:60]}"
        if k in self._sent:
            return
        self._sent.add(k)
        log.warning("Notion 게시 설정(%s): %s", name, msg)
        if not self.notifier:
            return
        try:
            rule = self.notifier.rules.for_project(name)
            prefix = rule.prefix if rule else f"[{name}]"
            self.notifier.send_direct(name, "docsync", None, f"{prefix} ⚠ Notion 게시 설정 — {msg}")
        except Exception as e:  # noqa: BLE001 — 알림 실패가 설정을 막지 않는다(로그에는 남았다)
            log.warning("설정 알림 실패: %s", type(e).__name__)
