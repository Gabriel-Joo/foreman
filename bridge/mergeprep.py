"""합치기 준비(11-11 1물결 A 「하나」 · 「넷」, log/plan_structure_20261111.md) — 판에 박힌 단계는 브리지가 기계로.

worktree 세션이 「일을 마침」이 되면 merge-tree를 돌려 **합치기 승인 카드**를 만든다. 사람 화면에는 승인만 뜬다.
- 언제 보나(11-11 사용자): 세션이 응답을 마치는 순간(턴 끝 — on_turn_closed) 바로. 1분 훑기는 놓친 것을 줍는 그물
- 일을 마침: 살아 있고 · 일하지 않고(busy 아님, 열린 턴 없음, 뒤에서 도는 일 없음) · 권한 거부로 멈추지 않음 — 또는 세션이 끝남.
  그리고 worktree에 합칠 커밋이 있고(ahead > 0) 커밋 안 한 변경이 0. 마지막 응답이 묻는 말이어도 일을 마친 것으로 보고, 카드에
  「세션이 묻는 말이 있습니다」를 함께 싣는다(답 기다림과 일을 마침은 따로 — D2 281은 보고 끝 확인 부탁 때문에 카드가 안 떴다)
  (「보고 옴」(대시보드 human_needs의 report)은 사람이 패널을 열면 읽음으로 사라진다 — 읽었든 아니든 일을 마친 것은 같아 묻지 않는다)
- 카드: 브랜치 · 커밋 · 바뀐 파일 · 충돌 여부(`git merge-tree --write-tree`) · ff 가능 / main이 앞섬 · 정리 후보(넷)
- [합치기]: 다시 잰다(카드 뒤 커밋이 바뀌었으면 거절하고 카드를 새로). 충돌 없고 깨끗하면 HandoffManager.worktree_act(merge,
  end=살아 있음) — 살아 있는 세션은 끝내고 합친다. main이 앞섰으면 worktree.merge가 rebase한다(살아 있으면 끝내기 전에 임시
  worktree에서 rebase가 되는지 먼저 본다 — 끝낸 뒤 충돌이면 풀 세션이 없다, docs/11_worktree.md 「6.」).
  충돌이면 끝내지 않고 그 세션에 「main을 가져와 풀라」를 보낸다. 세션이 끝났으면 관리자 세션에
- 결과는 관리자 세션(원본 폴더의 역할 관리자)에 deliver로 남긴다 — 「합쳤습니다 — 시험 · push는 관리자」. 관리자가 없으면 텔레그램
- 1단계는 합치기까지. 2단계(시험 → push → 승인 대기 0 → 브리지 → 점검)는 after_merge 자리만

조용한 고장 금지: 준비 실패 · 훑기가 stuck_min 넘게 안 끝남 · 합치기 실패 · 관리자에게 못 알림 → 텔레그램 한 번 + 카드(목록)에 사유.
카드는 브리지 메모리에 둔다(마이그레이션 없음) — 다시 띄우면 다음 훑기에서 다시 만든다. [나중에]는 session_action 'mprep-skip'
(detail = 브랜치 끝 커밋)에 남아 그 커밋이 바뀌기 전까지 다시 띄우지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge import worktree as wt
from bridge.inject import Refused, _status, deliver
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.mergeprep")

ACT_CARD, ACT_SKIP, ACT_MERGE, ACT_CONFLICT = "mprep-card", "mprep-skip", "mprep-merge", "mprep-conf"   # session_action(12자까지)
NOTIFY_KIND = "merge"                                                                                # notification.kind(8자까지)
TURN_END_DELAYS = (3.0, 10.0)        # 턴 끝 뒤 두 번 본다(초) — 시험이 바꾼다


# ── 설정 ────────────────────────────────────────────────
@dataclass
class DocsCfg:
    readme: str = "README.md"
    readme_section: str = "나중에 할 일"
    docs_dir: str = "docs"
    max: int = 12


@dataclass
class MergePrepCfg:
    enabled: bool = False
    every_s: int = 60
    stuck_min: int = 10
    notify_ready: bool = True
    stage: int = 1
    projects: list[str] = field(default_factory=list)     # 비면 모든 프로젝트
    docs: DocsCfg = field(default_factory=DocsCfg)


def load(path: str | Path) -> MergePrepCfg:
    """config/handoff.toml [merge_prep]. 파일이 없으면 꺼진 기본값. 값이 틀리면 ValueError — 조용히 기본값으로 가지 않는다."""
    p = Path(path)
    if not p.exists():
        return MergePrepCfg()
    raw = tomllib.loads(p.read_text(encoding="utf-8")).get("merge_prep") or {}
    d = raw.get("docs") or {}
    cfg = MergePrepCfg(enabled=bool(raw.get("enabled", False)), every_s=int(raw.get("every_s", 60)),
                       stuck_min=int(raw.get("stuck_min", 10)), notify_ready=bool(raw.get("notify_ready", True)),
                       stage=int(raw.get("stage", 1)), projects=[str(x) for x in raw.get("projects") or []],
                       docs=DocsCfg(readme=str(d.get("readme", "README.md")), readme_section=str(d.get("readme_section", "나중에 할 일")),
                                    docs_dir=str(d.get("docs_dir", "docs")), max=int(d.get("max", 12))))
    if cfg.every_s < 10 or cfg.stuck_min < 1 or cfg.stage not in (1, 2):
        raise ValueError("merge_prep 값이 맞지 않습니다(every_s ≥ 10, stuck_min ≥ 1, stage 1 · 2)")
    return cfg


# ── 순수 판정(시험하기 쉽게 git · DB와 떼어 둠) ────────────────────
def parse_merge_tree(rc: int, out: str) -> list[str] | None:
    """`git merge-tree --write-tree --name-only --no-messages` 결과 → None(충돌 없음) · [충돌 파일]. 그 밖의 실패는 Refused."""
    if rc == 0:
        return None
    if rc == 1:
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        return sorted(set(lines[1:])) or ["(파일 이름을 읽지 못함)"]
    raise Refused(f"git merge-tree 실패(종료 코드 {rc}): {out[-300:]}")


_PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|이랑|하고|이|가|은|는|을|를|의|에|로|와|과|도|만)$")
_STOP = {"main", "index", "config", "test", "tests", "api", "init", "readme", "md", "py", "js", "toml", "the", "and", "for",
         "합침", "기록", "고침", "더함", "뺌", "그대로", "있으면", "없으면", "때", "것", "뒤", "전", "수", "줄"}


def _words(s: str) -> set[str]:
    out = set()
    for w in re.findall(r"[0-9A-Za-z_가-힣.-]+", s or ""):
        w = _PARTICLE.sub("", w.strip(".-").lower()) if re.search(r"[가-힣]$", w) else w.strip(".-").lower()
        if len(w) >= 2 and w not in _STOP and not w.isdigit():
            out.add(w)
    return out


def _file_keys(files: list[str]) -> dict[str, str]:
    """바뀐 파일 → 찾을 글자(전체 경로 · 파일 이름 · 이름 줄기). 줄기는 4자 이상만(짧은 줄기는 헛걸림)."""
    keys: dict[str, str] = {}
    for f in files:
        keys[f] = f
        base = os.path.basename(f)
        keys.setdefault(base, f)
        stem = os.path.splitext(base)[0].removeprefix("test_")
        if len(stem) >= 4 and stem.lower() not in _STOP:
            keys.setdefault(stem, f)
    return keys


def _has_key(line: str, key: str) -> bool:
    """낱말 경계로만 — `handoff`가 `stage11_handoff_result`에, 줄기가 다른 확장자(`handoff.js`)에 걸리지 않게(11-11 라이브 점검).
    경로 · 파일 이름 앞의 `/`는 같은 파일이라 허용한다."""
    stem = "." not in key and "/" not in key
    tail = r"(?![\w.-])" if stem else r"(?![\w-])"
    return re.search(r"(?<![\w.-])" + re.escape(key) + tail, line) is not None


def readme_rows(readme: str, section: str) -> list[tuple[int, str]]:
    """README의 `section` 낱말이 든 제목 아래 표 줄들 — [(줄 번호(1부터), 줄)]. 머리 · 구분 줄은 뺀다."""
    out: list[tuple[int, str]] = []
    inside = False
    head_seen = False
    for i, ln in enumerate(readme.splitlines(), 1):
        if ln.startswith("#"):
            if inside:
                break
            inside = section in ln
            head_seen = False
            continue
        if inside and ln.startswith("|"):
            if not head_seen:
                head_seen = True          # 첫 줄 = 머리
                continue
            if re.match(r"^\|[\s:|-]+\|?\s*$", ln):
                continue
            out.append((i, ln))
    return out


def _quoted(s: str) -> list[str]:
    """「…」 바깥 짝만(안에 「」가 겹쳐 있어도 — 「「권한 거부」 표시가 꺼지지 않는다」)."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch == "「":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "」" and depth:
            depth -= 1
            if depth == 0:
                out.append(s[start:i])
    return out


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", s or "")).strip()


def log_drop_lines(logs: dict[str, str]) -> list[tuple[str, str]]:
    """세션 log의 「README에서 뺄 줄」 절에 적은 표 줄 이름들 — [(log 경로, 이름)]. 세션이 직접 「이 줄은 끝났다」고 적은 것(1순위)."""
    out: list[tuple[str, str]] = []
    for path, body in sorted(logs.items()):
        inside = False
        for ln in body.splitlines():
            if ln.startswith("#"):
                inside = "README에서 뺄" in ln
                continue
            if inside and ln.lstrip().startswith(("-", "*", "|")):
                for q in _quoted(ln):
                    q = _plain(q)
                    if len(q) >= 4:
                        out.append((path, q))
    return out


_INBOX_NO = re.compile(r"받은 할 일\s*#\s*(\d+)")
_LOG_LINK = re.compile(r"(?<![\w/.-])(?:log/)?([\w.-]+\.md)\b")


def doc_candidates(readme: str, section: str, docs: dict[str, str], files: list[str], subjects: list[str],
                   limit: int = 12, logs: dict[str, str] | None = None) -> dict[str, Any]:
    """넷 — 이번 작업으로 없어지거나 바뀔 수 있는 줄 **후보**(고르기 · 지우기는 사람 승인 뒤 관리자). 브리지는 맞대기만 한다.
    README 표 줄 — 점수 높은 차례(11-11 2물결 「넷」: 282 카드 후보 15개 중 맞는 것은 2순위 하나뿐이었다):
      100  세션 log(이번에 바뀐 log/*.md)의 「README에서 뺄 줄」에 그 줄 이름을 적음 — 세션이 직접 끝났다고 한 것
       50  표 줄 「근거」 칸이 링크한 log를 이번에 고침
       40  표 줄의 「받은 할 일 #N」이 이번 커밋 글 · 세션 log에도 나옴
       10  바뀐 파일(경로 · 이름 · 줄기, 낱말 경계로)을 적음(파일마다)
        1  커밋 글의 **드문** 낱말 겹침(낱말마다) — 낱말만으로는 셋 넘게 겹쳐야 후보(11-11: 둘로는 헛걸림이 대부분이었다)
    docs: 바뀐 파일 경로 · 이름을 적은 줄을 문서마다 묶는다. 이번에 그 문서를 고치지 않았으면 `stale` — 설계가 바뀌었으면 맞출 후보."""
    logs = logs or {}
    keys = _file_keys(files)
    changed = set(files)
    changed_names = {os.path.basename(f) for f in changed if f.startswith("log/")}
    rows = readme_rows(readme, section)
    sub_words = set().union(*(_words(s) for s in subjects)) if subjects else set()
    row_words = [(_words(ln)) for _, ln in rows]
    common = {w for w in sub_words if rows and sum(w in rw for rw in row_words) > max(2, len(rows) // 10)}
    drops = log_drop_lines(logs)
    inbox_seen = {m for s in [*subjects, *logs.values()] for m in _INBOX_NO.findall(s)}
    cand: list[dict[str, Any]] = []
    for (no, ln), rw in zip(rows, row_words):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        cell, evidence = cells[0], cells[-1] if len(cells) > 1 else ""
        title = _plain(cell)
        why: list[str] = []
        score = 0
        named = [p for p, q in drops if q in title]
        if named:
            score += 100
            why.append(f"세션 기록 「README에서 뺄 줄」({os.path.basename(named[0])})")
        links = {m for m in _LOG_LINK.findall(evidence)} & changed_names
        if links:
            score += 50
            why.append(f"근거 칸의 기록을 이번에 고침({', '.join(sorted(links))})")
        inbox = sorted(set(_INBOX_NO.findall(ln)) & inbox_seen)
        if inbox:
            score += 40
            why.append("받은 할 일 " + " · ".join(f"#{n}" for n in inbox))
        hit_f = sorted({keys[k] for k in keys if _has_key(ln, k)})
        hit_w = sorted((sub_words & rw) - common)
        score += 10 * len(hit_f) + len(hit_w)
        if not why and not hit_f and len(hit_w) < 3:
            continue
        if hit_f:
            why.append("바뀐 파일을 적음")
        elif hit_w and not why:
            why.append("커밋 글 낱말만 겹침")
        cand.append({"where": "README", "line": no, "text": re.sub(r"\s+", " ", cell)[:200],
                     "files": hit_f, "words": hit_w[:6], "score": score, "why": why, "weak": score < 10})
    cand.sort(key=lambda x: -x["score"])
    dgroups: list[dict[str, Any]] = []
    fkeys = {k: v for k, v in keys.items() if "/" in k or "." in k}       # docs는 경로 · 파일 이름만(줄기는 헛걸림이 많다)
    for path, body in sorted(docs.items()):
        lines = []
        hit: set[str] = set()
        for i, ln in enumerate(body.splitlines(), 1):
            h = {fkeys[k] for k in fkeys if _has_key(ln, k)}
            if h:
                lines.append(i)
                hit |= h
        if lines:
            dgroups.append({"where": path, "lines": lines[:8], "count": len(lines), "files": sorted(hit),
                            "stale": path not in changed})
    dgroups.sort(key=lambda x: -x["count"])
    return {"readme": cand[:limit], "docs": dgroups[:limit], "readme_rows": len(rows)}


# ── 카드 ─────────────────────────────────────────────────
@dataclass
class Card:
    sid: int
    title: str | None
    project: str | None
    role: str | None
    repo: str
    name: str
    branch: str
    base: str
    head: str                     # 브랜치 끝 커밋(카드의 열쇠 — 바뀌면 다시 만든다)
    base_head: str
    live: bool
    why: str                      # 「일을 마침」의 근거(사람이 읽는 말)
    ahead: int
    behind: int
    commits: list[str]
    files: list[str]
    conflict: list[str] | None    # None = 충돌 없음
    docs: dict[str, Any] | None
    asks: dict[str, Any] | None = None   # 마지막 응답이 묻는 말이면(human_needs의 asks) — 일을 마친 것과 따로 본다. 카드는 뜬다
    via: str = "sweep"            # turn_end(턴 끝에서 바로) · sweep(1분 훑기가 주움)
    status: str = "ready"         # ready · merging · merged · conflict_sent · conflict_manager · failed
    note: str | None = None
    error: str | None = None
    manager_told: bool | None = None
    made_at: str = ""
    updated_at: str = ""

    @property
    def ff(self) -> bool:
        return self.behind == 0

    def view(self) -> dict[str, Any]:
        return asdict(self) | {"ff": self.ff, "head8": self.head[:8]}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds") + "Z"


class MergePrep:
    def __init__(self, handoff: Any, cfg: MergePrepCfg, notifier: Any = None, on_change: Any = None) -> None:
        self.h, self.cfg, self.notifier, self.on_change = handoff, cfg, notifier, on_change
        self.engine, self.sessions_dir = handoff.engine, handoff.sessions_dir
        self.cards: dict[int, Card] = {}
        self.health: dict[str, Any] = {"ok": True, "last": None, "error": None}
        self._lock = asyncio.Lock()          # 훑기 · 턴 끝 · 합치기가 겹치지 않게
        self._task: asyncio.Task[Any] | None = None
        self._tasks: set[asyncio.Task[Any]] = set()       # 턴 끝 확인
        self._touched = False                # 있던 카드의 표시(묻는 말)만 바뀜 — 화면을 다시 그린다
        self.turn_end: dict[str, Any] = {"ok": 0, "fail": 0, "error": None, "at": None}   # 턴 끝 넘기기 — health로 보인다
        self.health["turn_end"] = self.turn_end

    # ── 보기 ──
    def view(self) -> dict[str, Any]:
        return {"enabled": self.cfg.enabled, "stage": self.cfg.stage, "health": self.health,
                "cards": [c.view() for c in sorted(self.cards.values(), key=lambda c: c.made_at, reverse=True)]}

    def card_for(self, sid: int) -> dict[str, Any] | None:
        c = self.cards.get(sid)
        return c.view() if c else None

    # ── 훑기 ──
    async def _candidates(self) -> list[tuple[Any, ...]]:
        """worktree에서 띄운 세션 — 그 worktree 폴더의 마지막 세션만(이름을 다시 쓴 앞 세션은 뺀다). 숨긴 세션은 보지 않는다."""
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, cs.cwd, COALESCE(cs.custom_title, cs.title), p.name, cs.role "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.type = 'agent' AND cs.hidden_at IS NULL AND cs.cwd LIKE :w AND cs.id IN ("
                "  SELECT MAX(id) FROM character_session WHERE cwd LIKE :w GROUP BY cwd)"), {"w": f"%/{wt.WT_DIR}/%"})).all()
        out = []
        seen: set[str] = set()
        for r in sorted(rows, key=lambda r: -r[0]):
            repo, name = wt.split(r[2] or "")
            key = f"{repo}/{name}"
            if not name or key in seen or not os.path.isdir(os.path.join(repo, wt.WT_DIR, name)):
                continue
            if self.cfg.projects and r[4] not in self.cfg.projects:
                continue
            seen.add(key)
            out.append(r)
        return out

    async def _done_live(self, sid: int, cc: str, pid: int) -> str | None:
        """살아 있는 세션이 일을 마쳤나 — 마쳤으면 근거 글, 아니면 None.
        11-11(사용자): 답을 기다리는 것과 일을 마친 것은 따로 본다 — 보고 끝 확인 부탁(「…한 번씩 확인해 주세요」)이 답 기다림으로
        잡혀 카드가 아예 안 떴다(D2 281). 묻는 말은 _asks로 카드에 함께 싣는다. 권한 거부로 멈춘 것은 일을 마친 것이 아니다."""
        if _status(self.sessions_dir, pid) == "busy":
            return None
        from bridge.api.dashboard import human_needs
        async with self.engine.connect() as c:
            if (await c.execute(text("SELECT 1 FROM turn WHERE session_id = :s AND ended_at IS NULL LIMIT 1"), {"s": sid})).first():
                return None
            if not (await c.execute(text("SELECT 1 FROM event WHERE session_id = :s AND type = 'assistant_msg' LIMIT 1"),
                                    {"s": sid})).first():
                return None
            needs = (await human_needs(c, f"({int(sid)})")).get(sid) or {}
        if needs.get("denied"):
            return None
        row = await self.h.session(sid)
        if row is None or await self.h._running_work(row, pid):
            return None
        return "보고 옴 — 일하지 않고 응답을 마쳤습니다"

    async def _asks(self, sid: int) -> dict[str, Any] | None:
        """마지막 응답이 사람에게 묻는 말이면 {at, tail, event_id}(대시보드 「답 기다림」과 같은 판정). 사람이 [답 안 해도 됨]으로
        끈 것은 없다."""
        from bridge.api.dashboard import human_needs
        async with self.engine.connect() as c:
            return ((await human_needs(c, f"({int(sid)})")).get(sid) or {}).get("asks")

    async def _skipped(self, sid: int, head: str) -> bool:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT detail FROM session_action WHERE session_id = :s AND action = :a ORDER BY id DESC LIMIT 1"),
                {"s": sid, "a": ACT_SKIP})).first()
        return bool(r and r[0] == head)

    async def _git_facts(self, repo: str, name: str) -> dict[str, Any]:
        st = await wt.status(repo, name)
        if not st.get("exists"):
            return st
        _, head = await wt.git(repo, "rev-parse", st["branch"])
        _, bhead = await wt.git(repo, "rev-parse", st["base"])
        st["head"], st["base_head"] = head.strip(), bhead.strip()
        return st

    async def _conflict(self, repo: str, base: str, branch: str) -> list[str] | None:
        rc, out = await wt.git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", base, branch, check=False)
        return parse_merge_tree(rc, out)

    async def _docs(self, repo: str, base: str, branch: str, st: dict[str, Any]) -> dict[str, Any]:
        d = self.cfg.docs
        _, files = await wt.git(repo, "diff", "--name-only", f"{base}...{branch}")
        _, subj = await wt.git(repo, "log", "--format=%s", f"{base}..{branch}")
        rc, readme = await wt.git(repo, "show", f"{base}:{d.readme}", check=False)
        rc2, names = await wt.git(repo, "ls-tree", "-r", "--name-only", base, "--", d.docs_dir, check=False)
        docs: dict[str, str] = {}
        for n in (names.splitlines() if rc2 == 0 else [])[:200]:
            if n.endswith(".md"):
                r3, body = await wt.git(repo, "show", f"{base}:{n}", check=False)
                if r3 == 0:
                    docs[n] = body
        logs: dict[str, str] = {}
        for n in [f for f in files.splitlines() if f.startswith("log/") and f.endswith(".md")][:20]:
            r4, body = await wt.git(repo, "show", f"{branch}:{n}", check=False)
            if r4 == 0:
                logs[n] = body
        return doc_candidates(readme if rc == 0 else "", d.readme_section, docs, files.splitlines(), subj.splitlines(), d.max,
                              logs=logs)

    async def prep(self, r: tuple[Any, ...], live: dict[str, Any], via: str = "sweep") -> Card | None:
        """한 세션 — 일을 마쳤고 합칠 것이 있으면 카드(같은 커밋이면 있던 카드 그대로). 아니면 None(있던 ready 카드는 치운다)."""
        sid, cc, cwd, title, project, role = r
        repo, name = wt.split(cwd)
        ls = live.get(cc or "")
        if ls is not None and ls.state == "T":
            return None                                   # 사람이 멈춰 둔 세션은 건드리지 않는다
        why = await self._done_live(sid, cc, ls.pid) if ls else "세션이 끝났습니다"
        if not why:
            return None
        st = await self._git_facts(repo, name)
        if not st.get("exists") or st["ahead"] == 0 or st["dirty"]:
            return None
        asks = await self._asks(sid) if ls else None       # 끝난 세션은 답할 곳이 없다
        old = self.cards.get(sid)
        if old and (old.status == "merging" or (old.head == st["head"] and old.base_head == st["base_head"] and old.live == bool(ls))):
            if old.status == "ready" and old.asks != asks:  # 같은 커밋에서 묻는 말만 생기거나 풀림 — 카드는 그대로, 표시만
                old.asks, old.updated_at = asks, _iso(_now())
                self._touched = True
            return old
        if await self._skipped(sid, st["head"]):
            return None
        conflict = await self._conflict(repo, st["base"], st["branch"])
        try:
            docs = await self._docs(repo, st["base"], st["branch"], st)
        except Exception as e:  # noqa: BLE001 — 후보를 못 뽑아도 카드는 낸다(사유를 붙여)
            docs = {"error": f"정리 후보를 뽑지 못했습니다({type(e).__name__})", "readme": [], "docs": []}
        _, files = await wt.git(repo, "diff", "--name-only", f"{st['base']}...{st['branch']}")
        now = _iso(_now())
        card = Card(sid=sid, title=title, project=project, role=role, repo=repo, name=name, branch=st["branch"], base=st["base"],
                    head=st["head"], base_head=st["base_head"], live=bool(ls), why=why, ahead=st["ahead"], behind=st["behind"],
                    commits=st["commits"], files=files.splitlines()[:60], conflict=conflict, docs=docs, asks=asks, via=via,
                    made_at=now, updated_at=now)
        if old is None or old.head != card.head:
            await self.h._act(sid, ACT_CARD, None, True, f"{name} {card.head[:8]} " + ("충돌 " + ",".join(conflict)[:300] if conflict else "충돌 없음")
                              + (" · 묻는 말 있음" if asks else "") + (" · 턴 끝" if via == "turn_end" else " · 훑기"))
            if self.cfg.notify_ready:
                self._notify(card, f"mergeprep:ready:{sid}:{card.head[:12]}",
                             f"⑂ 합치기 준비됨 — 「{title or sid}」(세션 {sid}) {card.branch} 커밋 {card.ahead}개, "
                             + (f"충돌 {len(conflict)}개" if conflict else ("충돌 없음 · ff 가능" if card.ff else f"충돌 없음 · {card.base}에 새 커밋 {card.behind}개(rebase)"))
                             + (f"\n❓ 세션이 묻는 말이 있습니다 — 패널에서 답하십시오: {asks.get('tail') or ''}" if asks else "")
                             + "\n▶ 그 세션 패널의 「합치기 승인」에서 승인합니다")
        return card

    async def check(self) -> int:
        """한 번 훑는다 — 카드 수를 돌려준다. 세션마다 실패는 그 카드에 사유로 남기고 다음 세션으로 간다.
        11-11부터 카드는 턴 끝(on_turn_closed)에서 바로 만든다. 훑기는 놓친 것을 줍는 그물이다(브리지를 다시 띄운 사이 끝난 세션,
        턴 끝 확인이 실패한 세션, 끝난 세션 · 다시 일하는 세션의 카드 치우기)."""
        async with self._lock:
            self._touched = False
            rows = await self._candidates()
            live = await asyncio.to_thread(live_sessions, self.sessions_dir)
            keep: set[int] = set()
            changed = False
            for r in rows:
                sid = r[0]
                try:
                    card = await self.prep(r, live)
                except Exception as e:  # noqa: BLE001
                    card = self._failed_card(r, f"합치기 준비 실패: {type(e).__name__}: {str(e)[:200]}")
                if card is None:
                    continue
                keep.add(sid)
                if self.cards.get(sid) is not card:
                    self.cards[sid] = card
                    changed = True
            changed = changed or self._touched
            for sid in [s for s, c in self.cards.items() if s not in keep and c.status == "ready"]:
                del self.cards[sid]                       # 더는 일을 마친 상태가 아니다(다시 일함 · 합침 · 버림)
                changed = True
            # 끝난 카드(merged 등)는 6시간 뒤 치운다
            cut = _iso(_now() - timedelta(hours=6))
            for sid in [s for s, c in self.cards.items() if s not in keep and c.status != "ready" and c.updated_at < cut]:
                del self.cards[sid]
            self.health = {"ok": True, "last": _iso(_now()), "error": None, "turn_end": self.turn_end}
        if changed and self.on_change:
            self.on_change()
        return len(self.cards)

    async def check_one(self, sid: int, via: str = "turn_end") -> Card | None:
        """한 세션만 본다(턴 끝). worktree 세션이 아니거나 그 폴더의 마지막 세션이 아니면 아무것도 하지 않는다."""
        async with self._lock:
            self._touched = False
            rows = [r for r in await self._candidates() if r[0] == sid]
            if not rows:
                return None
            live = await asyncio.to_thread(live_sessions, self.sessions_dir)
            try:
                card = await self.prep(rows[0], live, via=via)
            except Exception as e:  # noqa: BLE001
                card = self._failed_card(rows[0], f"합치기 준비 실패: {type(e).__name__}: {str(e)[:200]}")
            changed = self._touched
            old = self.cards.get(sid)
            if card is None:
                if old is not None and old.status == "ready":
                    del self.cards[sid]                   # 다시 일함 · 커밋 안 한 변경 — 훑기와 같다
                    changed = True
            elif old is not card:
                self.cards[sid] = card
                changed = True
        if changed and self.on_change:
            self.on_change()
        return card

    def on_turn_closed(self, session_id: int, *_: Any, **__: Any) -> None:
        """조립기가 턴을 닫은 직후(트랜잭션 안일 수 있다 — 여기서는 예약만). 11-11(사용자): 세션이 응답을 마치는 순간 관리자 몫
        (합치기 준비)으로 바로 넘긴다 — 1분 훑기에 기대지 않는다. Stop hook이 마지막 응답 줄 · CC 상태 파일보다 먼저 올 수 있어
        TURN_END_DELAYS 뒤 두 번 본다(두 번째는 묻는 말 표시를 바로잡는다). 실패는 health에 남기고 다음 훑기가 줍는다 —
        훑기마저 실패하면 _health_bad가 텔레그램으로 알린다."""
        if not self.cfg.enabled:
            return

        async def go() -> None:
            for d in TURN_END_DELAYS:
                await asyncio.sleep(d)
                try:
                    async with asyncio.timeout(60):
                        await self.check_one(session_id)
                    self.turn_end["ok"] += 1
                except Exception as e:  # noqa: BLE001 — 실패가 적재를 막지 않는다. 그물(훑기)이 줍는다
                    self.turn_end["fail"] += 1
                    self.turn_end["error"] = f"세션 {session_id}: {type(e).__name__}: {str(e)[:160]}"
                    self.turn_end["at"] = _iso(_now())
                    log.warning("턴 끝 합치기 준비 실패 — 다음 훑기가 줍는다: %s", self.turn_end["error"])
                    return
        t = asyncio.get_running_loop().create_task(go())
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def _failed_card(self, r: tuple[Any, ...], err: str) -> Card:
        sid, cc, cwd, title, project, role = r
        repo, name = wt.split(cwd)
        old = self.cards.get(sid)
        if old and old.error == err:
            return old
        now = _iso(_now())
        c = Card(sid=sid, title=title, project=project, role=role, repo=repo, name=name, branch=wt.BRANCH_PREFIX + name, base="",
                 head=(old.head if old else ""), base_head="", live=False, why="", ahead=0, behind=0, commits=[], files=[],
                 conflict=None, docs=None, status="failed", error=err, made_at=now, updated_at=now)
        log.warning("합치기 준비 실패 세션 %s: %s", sid, err)
        self._notify(c, f"mergeprep:fail:{sid}:{now[:13]}", f"⚠ {err} — 「{title or sid}」(세션 {sid}). 패널 「합치기 승인」에 사유가 있습니다")
        return c

    def worktree_gone(self, sid: int) -> bool:
        """worktree가 합쳐지거나 버려졌다(HandoffManager.worktree_act가 부른다) — 그 세션의 대기 카드를 바로 치운다.
        11-11: 승인은 approve가 카드 상태를 바꿔 막대에서 바로 빠졌지만, 버리기 · 카드 밖 합치기는 카드를 몰라 ready로 남았다가
        1분 훑기에서야 사라졌다(그 사이 막대를 누르면 없는 세션으로 갔다). 합치는 중(merging) 카드는 approve가 마저 쓰니 둔다.
        잠금을 잡지 않는다(approve가 잠근 채 worktree_act를 부른다) — 딕셔너리 한 줄이라 이벤트 루프 안에서 안전하다."""
        c = self.cards.get(sid)
        if c is None or c.status == "merging":
            return False
        del self.cards[sid]
        return True

    # ── 승인 ──
    async def skip(self, sid: int) -> dict[str, Any]:
        """[나중에] — 이 브랜치 끝 커밋이 바뀌기 전까지 카드를 다시 띄우지 않는다."""
        c = self.cards.get(sid)
        if not c or c.status not in ("ready", "failed", "conflict_sent", "conflict_manager"):
            raise Refused("치울 합치기 카드가 없습니다")
        await self.h._act(sid, ACT_SKIP, None, True, c.head)
        del self.cards[sid]
        if self.on_change:
            self.on_change()
        return {"ok": True, "note": "카드를 치웠습니다 — 이 세션이 새로 커밋하면 다시 만듭니다."}

    async def approve(self, sid: int) -> dict[str, Any]:
        """사람이 [합치기]를 눌렀다. 다시 재고 → 충돌이면 그 세션(끝났으면 관리자)에 풀라고 보냄 · 깨끗하면 (끝내고) 합침."""
        c = self.cards.get(sid)
        if not c or c.status not in ("ready", "conflict_sent", "conflict_manager", "failed"):
            raise Refused("승인할 합치기 카드가 없습니다 — 카드가 사라졌거나 이미 합치는 중입니다")
        if not c.head:
            raise Refused("준비가 실패한 카드입니다 — 사유를 보고 다음 훑기를 기다리거나 패널 [합치기]로 합칩니다")
        async with self._lock:
            row = await self.h.session(sid)
            if row is None:
                raise Refused("세션이 없습니다")
            st = await self._git_facts(c.repo, c.name)
            if not st.get("exists"):
                del self.cards[sid]
                raise Refused("worktree가 없습니다 — 이미 합쳤거나 버렸습니다")
            if st["dirty"]:
                raise Refused(f"커밋 안 된 변경이 {len(st['dirty'])}개 생겼습니다 — 그 세션이 커밋한 뒤 카드가 다시 뜹니다. 아무것도 하지 않았습니다")
            if st["head"] != c.head:
                del self.cards[sid]
                raise Refused("카드를 만든 뒤 브랜치에 커밋이 더 생겼습니다 — 다음 훑기에서 새 카드를 만듭니다. 아무것도 하지 않았습니다")
            live = bool(row.cc and row.cc in live_sessions(self.sessions_dir))
            conflict = await self._conflict(c.repo, st["base"], st["branch"])
            if not conflict and live and st["behind"]:
                conflict = await self._rebase_check(c.repo, st["base"], st["branch"])
            c.behind, c.base_head, c.live, c.conflict, c.updated_at = st["behind"], st["base_head"], live, conflict, _iso(_now())
            if conflict:
                return await self._send_conflict(c, row, live)
            c.status, c.error = "merging", None
            if self.on_change:
                self.on_change()
            try:
                res = await self.h.worktree_act(row, "merge", end=live)
            except Refused as e:
                c.status, c.error = "failed", str(e)
                await self.h._act(sid, ACT_MERGE, None, False, f"{c.name} 거부: {e}"[:500])
                self._notify(c, f"mergeprep:mfail:{sid}:{c.head[:12]}", f"⚠ 합치기 승인 뒤 멈춤 — 「{c.title or sid}」 {e}")
                if self.on_change:
                    self.on_change()
                raise
            c.updated_at = _iso(_now())
            if res.get("ok"):
                c.status, c.note = "merged", res.get("note")
                await self.h._act(sid, ACT_MERGE, None, True, f"{c.name} {c.head[:8]} 커밋 {res.get('merged')}개")
                c.manager_told = await self._tell_manager(c, self._merged_msg(c, res))
                await self.after_merge(c, res)
            else:
                c.status, c.error = "failed", (res.get("note") or "합치지 못했습니다") + (
                    f" 충돌 파일: {', '.join(res['conflict'])}" if res.get("conflict") else "")
                await self.h._act(sid, ACT_MERGE, None, False, f"{c.name} {c.error}"[:500])
                self._notify(c, f"mergeprep:mfail:{sid}:{c.head[:12]}", f"⚠ 합치기 실패 — 「{c.title or sid}」 {c.error}")
                if res.get("ended") is not None or not live:
                    c.manager_told = await self._tell_manager(c, (
                        f"[FOREMAN 합치기] 세션 {sid} 「{c.title or ''}」의 {c.branch}를 합치지 못했다 — {c.error}. 그 세션은 끝났다. "
                        f"관리자가 원본 폴더에서 풀어 합친다(docs/11_worktree.md 「6.」). 시험 · push도 관리자 몫이다."))
            if self.on_change:
                self.on_change()
            return {"ok": c.status == "merged", "status": c.status, "note": c.note or c.error, "card": c.view(),
                    "manager_told": c.manager_told, "result": res}

    async def _rebase_check(self, repo: str, base: str, branch: str) -> list[str] | None:
        """살아 있는 세션을 끝내기 전에 — main 위로 rebase가 되는지 임시 worktree(분리된 HEAD)에서 본다. merge-tree는 세 갈래
        합치기라 깨끗해도 커밋 하나씩 얹는 rebase는 중간 커밋에서 충돌할 수 있다. 끝낸 뒤 알면 풀 세션이 없다."""
        tmp = tempfile.mkdtemp(prefix="foreman-mprep-")
        path = os.path.join(tmp, "wt")
        try:
            await wt.git(repo, "worktree", "add", "--detach", path, branch)
            rc, out = await wt.git(path, "rebase", base, check=False)
            if rc == 0:
                return None
            _, files = await wt.git(path, "diff", "--name-only", "--diff-filter=U", check=False)
            await wt.git(path, "rebase", "--abort", check=False)
            return sorted(set(files.splitlines())) or ["(rebase 중 충돌 — 파일 이름을 읽지 못함)"]
        finally:
            await wt.git(repo, "worktree", "remove", "--force", path, check=False)
            await wt.git(repo, "worktree", "prune", check=False)
            try:
                os.rmdir(tmp)
            except OSError:
                pass

    async def _send_conflict(self, c: Card, row: Any, live: bool) -> dict[str, Any]:
        files = ", ".join(c.conflict or [])
        if live:
            msg = (f"[FOREMAN 합치기] 사람이 합치기를 승인했는데 {c.branch}가 {c.base}와 충돌한다(파일: {files}). "
                   f"`git rebase {c.base}`로 {c.base}를 가져와 충돌을 풀고 커밋한 뒤 보고해라. push · 브리지 다시 띄우기는 하지 마라. "
                   f"풀고 나면 브리지가 합치기 카드를 다시 만든다.")
            ok = await self._deliver(row.cc, row.cwd, msg)
            c.status = "conflict_sent"
            c.note = ("세션을 끝내지 않고 그 세션에 「main을 가져와 풀라」를 보냈습니다." if ok
                      else "그 세션에 보내지 못했습니다 — 입력 칸을 확인해 주세요.")
            if not ok:
                c.error = c.note
                self._notify(c, f"mergeprep:cfail:{c.sid}:{c.head[:12]}", f"⚠ 충돌 풀기를 보내지 못함 — 「{c.title or c.sid}」(세션 {c.sid})")
        else:
            c.status = "conflict_manager"
            c.manager_told = await self._tell_manager(c, (
                f"[FOREMAN 합치기] 사람이 세션 {c.sid} 「{c.title or ''}」의 {c.branch} 합치기를 승인했는데 {c.base}와 충돌한다(파일: {files}). "
                f"그 세션은 끝났다 — 관리자가 원본 폴더에서 풀어 합친다(docs/11_worktree.md 「6.」). 시험 · push도 관리자 몫이다."))
            c.note = "세션이 끝나 관리자에게 충돌 풀기를 넘겼습니다." if c.manager_told else "세션이 끝났고 관리자 세션도 없어 넘기지 못했습니다 — 텔레그램으로 알렸습니다."
        await self.h._act(c.sid, ACT_CONFLICT, None, c.status == "conflict_sent" and not c.error or bool(c.manager_told),
                          f"{c.name} {c.head[:8]} {files}"[:500])
        if self.on_change:
            self.on_change()
        return {"ok": False, "status": c.status, "note": c.note, "card": c.view(), "manager_told": c.manager_told}

    def _merged_msg(self, c: Card, res: dict[str, Any]) -> str:
        how = "fast-forward" if c.ff else f"{c.base} 위로 rebase 뒤 fast-forward"
        ended = " 세션은 끝냈다." if res.get("ended") is not None else ""
        docs = (c.docs or {})
        dn = len(docs.get("readme") or []) + len(docs.get("docs") or [])
        # 근거가 있는 후보(세션 기록 · 근거 칸 · 받은 할 일 번호 — 점수 40 이상)는 글에 바로 적는다(11-11 2물결 「넷」)
        sure = [x for x in docs.get("readme") or [] if x.get("score", 0) >= 40][:5]
        stale = [x["where"] for x in docs.get("docs") or [] if x.get("stale")][:5]
        extra = ""
        if sure:
            extra += " 근거 있는 README 정리 후보: " + "; ".join(
                f"README:{x['line']} {x['text'][:80]}({' · '.join(x.get('why') or [])})" for x in sure) + "."
        if stale:
            extra += f" 이번에 바뀐 파일을 적었는데 고치지 않은 문서: {', '.join(stale)} — 설계가 바뀌었으면 맞출 후보."
        return (f"[FOREMAN 합치기] 사람이 승인해 세션 {c.sid} 「{c.title or ''}」의 {c.branch}(커밋 {res.get('merged', c.ahead)}개)를 "
                f"{c.base}에 합쳤다({how}).{ended} 1단계라 브리지는 합치기까지만 했다 — 시험 · push · 브리지 다시 띄우기 · 화면 점검은 "
                f"관리자가 한다." + (f" README · docs 정리 후보 {dn}개는 그 세션 패널 카드에 있다 — 고르고 지우는 것은 사람 승인 뒤"
                                     "(판단이 필요하면 사람에게 묻고, 혼자 지우지 않는다)." if dn else "") + extra)

    async def after_merge(self, c: Card, res: dict[str, Any]) -> None:
        """2단계 자리 — 승인 뒤 시험 → push → 승인 대기 0 확인 → 브리지 다시 띄우기 → 화면 점검. 사용자가 1단계를 써 본 뒤 정한다.
        stage = 2로 켜도 지금은 아무것도 하지 않고 그렇다고 남긴다(조용히 넘어가지 않게)."""
        if self.cfg.stage >= 2:
            c.note = (c.note or "") + " (2단계는 아직 만들지 않았습니다 — 시험 · push는 관리자가 합니다.)"
            log.warning("merge_prep stage=2지만 2단계는 아직 없다 — 합치기까지만 했다(세션 %s)", c.sid)

    # ── 알리기 ──
    async def _deliver(self, cc: str | None, cwd: str | None, msg: str) -> bool:
        if not cc:
            return False
        from bridge.handoff import transcript_path
        try:
            r = await deliver(cc, msg, sessions_dir=self.sessions_dir, transcript=transcript_path(cwd or "", cc), verify_s=15.0)
        except Refused as e:
            log.warning("합치기 결과를 보내지 못함 %s: %s", cc[:8], e)
            return False
        return bool(r.get("delivered") or r.get("queued"))

    async def manager_of(self, repo: str) -> tuple[str, str] | None:
        """원본 폴더에 살아 있는 역할 관리자 (cc, cwd). 여럿이면 마지막 행."""
        ccs = self.h._live_in_base(repo)
        if not ccs:
            return None
        from sqlalchemy import bindparam
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cc_session_id, role, cwd FROM character_session WHERE cc_session_id IN :c ORDER BY id")
                .bindparams(bindparam("c", expanding=True)), {"c": ccs})).all()
        latest = {cc: (role, cwd) for cc, role, cwd in rows}
        mgr = [(cc, cwd) for cc, (role, cwd) in latest.items() if role == "manager"]
        return mgr[-1] if mgr else None

    async def _tell_manager(self, c: Card, msg: str) -> bool:
        m = await self.manager_of(c.repo)
        ok = bool(m) and await self._deliver(m[0], m[1], msg)
        if not ok:
            self._notify(c, f"mergeprep:mgr:{c.sid}:{c.head[:12]}:{c.status[:8]}",
                         ("관리자 세션이 없어" if not m else "관리자 세션에 보내지 못해") + f" 텔레그램으로 남깁니다 — {msg}")
        return ok

    def _notify(self, c: Card | None, key: str, msg: str) -> None:
        """텔레그램 한 번(key가 이미 있으면 보내지 않는다 — 브리지를 다시 띄워도). c가 없으면 FOREMAN 전체 알림."""
        if self.notifier is None:
            return
        project, sid = (c.project, c.sid) if c else ("foreman", None)

        async def go() -> None:
            try:
                async with self.engine.connect() as cn:
                    if (await cn.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key[:64]})).first():
                        return
                rule = self.notifier.rules.for_project(project) if project else None
                prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
                self.notifier.send_direct(project, NOTIFY_KIND, sid, f"{prefix} {msg}"[:3500], rule=key[:64])
            except Exception as e:  # noqa: BLE001 — 알림 실패가 합치기를 막지 않는다
                log.warning("합치기 알림 실패: %s", type(e).__name__)
        t = asyncio.get_running_loop().create_task(go())
        self.h._tasks.add(t)
        t.add_done_callback(self.h._tasks.discard)

    # ── 돌기 ──
    async def run(self) -> None:
        stuck_s = self.cfg.stuck_min * 60
        while True:
            await asyncio.sleep(self.cfg.every_s)
            try:
                await asyncio.wait_for(self.check(), stuck_s)
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                why = f"합치기 준비가 {self.cfg.stuck_min}분째 끝나지 않아 끊었습니다(git · DB가 막혔을 수 있습니다)"
                self._health_bad(why, f"mergeprep:stuck:{_now():%Y%m%d%H}")
            except Exception as e:  # noqa: BLE001 — 한 번의 실패가 감시를 멈추지 않는다
                self._health_bad(f"합치기 준비 실패: {type(e).__name__}: {str(e)[:200]}", f"mergeprep:err:{_now():%Y%m%d%H}")

    def _health_bad(self, why: str, key: str) -> None:
        log.warning(why)
        self.health = {"ok": False, "last": self.health.get("last"), "error": why, "at": _iso(_now()), "turn_end": self.turn_end}
        self._notify(None, key, f"⚠ {why}")
        if self.on_change:
            self.on_change()

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.create_task(self.run(), name="foreman-merge-prep")
        return self._task
