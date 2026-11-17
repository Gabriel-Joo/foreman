"""디스패처(11-05, docs/11_foreman_dispatch.md · 11-08 docs/14_dispatcher_note_wake.md) — 사람이 "뭘 하려는지" 말하면 계획을 낸다.

화면의 감독실 캐릭터(오피스 팀장 · 마법학교 교장 · 현장 소장 · 기본 디스패처)가 이 디스패처의 얼굴이다. 세션은 없다.
디스패처는 상주하지 않는다. 요청마다 브리지가 "상황 묶음"(프로젝트 · CLAUDE.md · 메모리 색인 · docs 색인 · 진행 중인 일(노트) · 지난 디스패치 ·
세션 · 인계 요약 · 파이프라인)을 LLM 없이 모아 `claude -p` 한 번에 넣고, 정해진 모양의 계획(JSON)을 받는다.
계획은 사람이 화면에서 보고 고친 뒤 승인해야 시작한다. 진행 중인 일 고치기 제안도 같은 [시작]으로 반영한다(bridge/foreman_note.py).

- 디스패처는 읽기만: Read · Grep · Glob(docs를 찾아보게). 셸 · 쓰기 없음, 훅 끔, 세션 기록 안 남김(--no-session-persistence)
- 파일(CLAUDE.md · MEMORY.md · docs)은 mtime이 바뀐 것만 다시 읽는다
- 계획의 출처: human(사람이 말함) · wake(실패 이벤트 — bridge/wake.py, 계획만 만들고 사람에게 [시작]?을 묻는다)
"""

import asyncio
import fnmatch
import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge import foreman_note as notes
from bridge.handoff import HandoffManager
from bridge.inject import Refused, _tmux_env, deliver
from bridge.liveness import live_sessions
from bridge.mask import Masker
from bridge.roles import ROLE_KO, SESSION_ROLES, role_line
from bridge.scribe_room import TASKS as SCRIBE_TASKS
from bridge.usage import record_cli

log = logging.getLogger("foreman.dispatch")

MODES = ("new", "handoff", "attach", "ask")
ROLES = SESSION_ROLES   # 교장 계획이 쓸 수 있는 역할 — bridge/roles.py 한 곳(11-15)
PLAN_TIMEOUT_S = 180.0
_cache: dict[str, tuple[float, str]] = {}


def read_cached(path: Path, limit: int) -> str | None:
    """mtime이 같으면 전에 읽은 것. 없으면 None."""
    try:
        m = path.stat().st_mtime
    except OSError:
        return None
    k = str(path)
    if k in _cache and _cache[k][0] == m:
        return _cache[k][1]
    try:
        s = path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return None
    _cache[k] = (m, s)
    return s


def memory_dir(repo: str) -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", repo) / "memory"


OPS_DOC = Path(__file__).resolve().parent.parent / "docs" / "operations.md"


def server_paths() -> str:
    """서버 공통 경로(클러스터 VM · 매니페스트 · 저장소 · 접속) — 어느 프로젝트 일이든 상황 묶음에 늘 넣는다.
    11-06: 포먼 CLAUDE.md 정리로 이 표가 docs/operations.md 「1.」로 갔다. 전후 비교에서 계획은 같았지만, "펫퍼민트 파드 보기"처럼
    포먼 이름이 없는 요청은 정리 전에도 이 표를 못 봐 kubectl 들어가는 법(vagrant ssh m-k8s)이 첫 글에 빠졌다."""
    body = read_cached(OPS_DOC, 8000) or ""
    m = re.search(r"^## 1\..*?$(.*?)(?=^## )", body, re.S | re.M)
    return m.group(1).strip() if m else ""


def docs_index(repo: str, cap: int = 60) -> list[str]:
    out = []
    for p in sorted(Path(repo, "docs").glob("*.md"))[:cap]:
        head = read_cached(p, 4000) or ""
        title = next((ln.lstrip("# ").strip() for ln in head.splitlines() if ln.startswith("#")), "")
        out.append(f"docs/{p.name} — {title[:100]}")
    return out


async def _git(repo: str, *args: str) -> str:
    p = await asyncio.create_subprocess_exec("git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), 5)
    except TimeoutError:
        p.kill()
        return ""
    return out.decode(errors="replace").strip()


async def _git_checked(repo: str, *args: str) -> str:
    """실패하면 예외 — 노트의 옛 HEAD가 없어진 것(리베이스 등)을 "아무 일 없음"과 가르려고."""
    p = await asyncio.create_subprocess_exec("git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), 5)
    except TimeoutError:
        p.kill()
        raise RuntimeError("git 시간 초과") from None
    if p.returncode:
        raise RuntimeError(f"git {args[0]} 실패")
    return out.decode(errors="replace").strip()


ALIASES ={"foreman": ("포먼", "FOREMAN", "Foreman")}   # 11-08 화면 이름표가 FOREMAN으로 — 사람은 여전히 "포먼"이라고 쓴다

# 서기 일 이름은 bridge/scribe_room.py TASKS 한 곳에서 가져온다(11-17, 지시문에 손으로 적은 목록이 옛 sync, loss를 말하고
# techdoc을 빠뜨렸다). publish는 세션이 아니라 버튼이라 뺀다(scribe_room.start가 거절한다)
SCRIBE_SESSION_TASKS = tuple(k for k in SCRIBE_TASKS if k != "publish")
SCRIBE_TASK_LINE = ", ".join(f"{SCRIBE_TASKS[k]['title']}({k})" for k in SCRIBE_SESSION_TASKS)

INSTRUCTIONS = """너는 FOREMAN의 디스패처(감독)다. 사람이 하려는 일을 듣고, 어느 프로젝트에서 어떤 Claude Code 세션으로 할지 계획을 낸다.
너는 계획만 낸다 — 세션을 띄우는 것은 사람이 계획을 승인한 뒤 브리지가 한다. 파일을 고치거나 명령을 실행하지 마라.
필요하면 Read · Grep · Glob으로 아래 경로의 문서(CLAUDE.md · 메모리 · docs)를 더 읽어도 된다. 읽기는 꼭 필요한 만큼만.

판단할 것:
1. project — 아래 목록의 이름 하나. 모호하면 mode "ask"로 되묻는다(추측해서 고르지 마라)
2. mode
   - "attach": 같은 일을 이미 하고 있는 살아 있는 tmux 세션이 있으면 새로 띄우지 말고 그 세션에 보낼 글만 쓴다(attach_session)
   - "handoff": 끝났거나 오래된 세션의 일을 이어 가야 하면 그 세션의 인계 요약(summary_id)을 쓴다. 요약이 없으면 "new"로 하고 이유에 적는다
   - "new": 새 일
   - "ask": 모호하거나 위험해서 사람이 정해야 할 것이 있을 때(questions에 물을 것)
3. role — {ROLE_LINE}
   - scribe 일감(docs/12_scribe.md): {SCRIBE_TASKS}
   - "coder"(코더): 고친 코드를 가리키는 문서(docs, 노션 원고, 포트폴리오)도 그 코더 세션이 같은 브랜치에서 함께 고친다(11-17 사용자 지시 21,
     코드 고침 뒤 서기가 따라잡는 사슬을 끊는다). 브리지가 코더 첫 글 끝에 이 규칙과 거꾸로 찾는 도구(tools/docrefs.py)를 붙이니
     first_prompt에 옮기지 마라. 코드 고침 뒤에 그 문서만 맞추는 서기 세션을 따로 내지 마라. 디자이너, 조사에는 이 규칙이 없다
   - 문서 정리 요청이면 scribe. 서기는 따로 작업(worktree)으로 띄우고, 합치기가 사람의 검토다
   - "manager"(관리자): 코드를 고치지 않고 다른 세션의 일을 거두는 일 — worktree 합친 뒤 시험 · push · 브리지 다시 띄우기 · 화면 점검 · log 기록.
     상주 세션이 아니다. 사람이 그런 일을 콕 집어 맡길 때만 고른다(코드를 고치는 일이면 coder)
   - "designer"(디자이너): 화면 일 — js · css · 테마(theme.json 자리 · 가구 · 색) · 캐릭터 · 이름표 · 카드 · 툴팁 글.
     파이썬 · 브리지 · API · DB(마이그레이션)는 coder. 둘이 걸치면(새 API + 그 화면) 화면이 API에 기대니 coder를 먼저 낸다 —
     first_prompt에 "화면은 다음 디자이너 세션 몫 — API 응답 모양을 log에 적고 끝낸다"를, reasons에 나눈 까닭을 쓴다.
     화면 쪽이 몇 줄뿐이면 나누지 않고 coder 하나로 끝낸다
   - "inspector"(조사): 원인 찾기, 살펴보기, 비교, 제안처럼 고치지 않는 일. 결과 log 하나는 쓰고 커밋한다(브리지가 log 밖 쓰기를 막는다).
     고칠 것이 나오면 그 log에 적고 끝낸다. 고치기는 사람이 결과를 보고 코더로. 모델이 더 필요하다고 코더로 고르지 마라(모델은 사람이 카드에서 고른다)
4. read_only — 보통 false. 조사는 브리지가 정한다(log만 쓰게 막는 프로젝트면 보통 모드, 아니면 CC 읽기 전용 모드). 고치는 일이면 false
5. title — 세션 이름(한국어, 짧게)
6. first_prompt — 새 세션(또는 attach 세션)에 넣을 첫 글. 한국어로:
   - 무엇을 하려는지(사람의 요청을 구체적으로)
   - 먼저 읽을 문서 경로(docs/… — 새 세션은 CLAUDE.md와 메모리 색인은 스스로 읽으니 다시 옮기지 마라)
   - 지켜야 할 것: 상황 묶음에 보이는 사용자 결정 · 금지(특히 압축 손실 점검 목록에서 이 일과 겹치는 것)
   - 받으면 바로 시작하게 쓴다. first_prompt 끝에 "이해한 것 N줄 말하고 확인 기다려라" · "이해한 것을 요약하고 확인을 기다려라" 같은 말은
     붙이지 마라 — 사람이 [계획 받기]에서 이미 보고 고쳤다(같은 확인을 두 번 하게 된다, 11-10). 세션은 받으면 바로 시작한다.
     일 중에 사람이 정해야 할 것(운영 적재 · push 등)에서 멈추라는 말은 '지켜야 할 것'에 그대로 둔다
   - 인계 요약 본문은 넣지 마라 — summary_id를 고르면 브리지가 뒤에 붙인다
7. reasons — 왜 이렇게 판단했는지(짧게, 근거가 된 세션 · 요약 · 문서를 짚어서)
8. confidence — 0~1. 0.6 아래면 mode "ask"를 생각하라
9. note_updates — 그 프로젝트 「진행 중인 일」을 고칠 제안(없으면 []). 진행 중인 일은 다음에 너를 부를 때 다시 들어간다. 사람이 [시작]을 누를 때만 반영된다
   - 쌓는 것은 하나뿐: 지금 도는 일 줄기 — 무엇을 · 어느 세션들에서 · 어디까지 · 남은 것. 일이 끝나면 내려간다
   - 쌓지 마라: 규칙 · 금지 · 설계 결정 · 사람이 정한 판단(「~는 ~로 한다」 「~하지 않는다」), 저장소 구조 · 자주 쓰는 명령 · 파일 경로 목록.
     요청 글에 「사용자 지시」 「사용자 결정」이 있어도 그것은 이번 세션의 first_prompt '지켜야 할 것'에 넣는다 — 진행 중인 일이 아니다.
     오래 지킬 규칙이면 그 일의 세션이 CLAUDE.md · docs에 적게 first_prompt에 쓴다(새 세션은 CLAUDE.md · docs를 스스로 읽는다)
   - {"op": "add", "body": "300자 안", "source": "세션 N | log/….md | docs/….md | dispatch #N | 커밋 <sha>"}
     · {"op": "update", "id": 줄번호, "body": ..., "source": ...} · {"op": "retire", "id": 줄번호, "why": "..."}
     · {"op": "touch", "id": 줄번호} (다시 확인했는데 아직 진행 중이다 — 확인 시각만 새로)
   - 이번 요청이 진행 중인 일을 잇는다면 그 줄을 update해 지금 상태로. 끝난 일은 retire
   - 관리자 띄우기는 진행 중인 일에 쓰지 않는다(관리자 자리는 /api/managers에 있다).
     관리자를 띄우면서 다른 일(「띄워서 X를 정리하게」)도 함께 맡기면 그 일만 thread로 쓴다
   - ⚠ 표시(확인 뒤 바뀜)가 붙은 줄은 그대로 믿지 말고, 필요하면 Read로 확인한 뒤 update · retire · touch를 제안하라
   - 사람의 요청 글 자체가 근거면 source를 비워 둔다(브리지가 이번 dispatch 번호를 넣는다)
   - 상한은 프로젝트마다 약 2000토큰이다. 짧게 쓰고, 넘치면 오래된 것을 retire하라
10. sessions — 띄울 세션 목록. 위 3 ~ 6(role · read_only · title · first_prompt)은 세션마다 이 안에 쓴다. 기본은 하나
   - 여럿은 사람이 개수를 말했거나("둘 띄워"), 큰 일을 맡을 파일이 겹치지 않게 나눠 동시에 하는 것이 분명히 나을 때만
   - files — 그 세션이 맡을 파일(저장소 기준 경로, 폴더는 끝에 /, 글롭 * 가능). 고칠 파일을 알면 하나여도 적는다 —
     띄울 때 브리지가 살아 있는 세션 · 다른 계획과 겹치는지 본다. 모르면 []
   - task — role "scribe"일 때만, 서기실 일 이름({SCRIBE_TASK_KEYS}) 중 맞는 것. 브리지가 서기실과 같은 일이
     열려 있는지 함께 센다. 맞는 것이 없으면 쓰지 않는다(plan으로 적힌다)
   - 여럿이면 세션끼리 files가 겹치지 않게 나눈다. 겹칠 수밖에 없으면 merge_order(1부터, 먼저 합칠 것이 작다)로 순서를 정하고 reasons에 까닭을
   - 여럿이면 각 first_prompt에 맡을 파일과 "맡은 파일 밖은 고치기 전에 멈추고 묻는다"를 적는다
   - mode "attach"는 세션 하나만(보낼 곳이 하나다)

답은 아래 JSON 하나만, ```json 블록으로. 다른 말은 쓰지 마라.
```json
{"project": "...", "mode": "new|handoff|attach|ask", "base_session": null, "summary_id": null, "attach_session": null,
 "sessions": [{"role": "coder", "read_only": false, "title": "...", "first_prompt": "...", "files": ["bridge/x.py"], "merge_order": 1}],
 "reasons": ["..."], "confidence": 0.8, "questions": [], "note_updates": []}
```""".replace("{ROLE_LINE}", role_line()).replace(   # 역할 한 줄 설명은 bridge/roles.py 한 곳(11-15). 화면 역할 고르기 칸과 같은 글
    "{SCRIBE_TASKS}", SCRIBE_TASK_LINE).replace("{SCRIBE_TASK_KEYS}", ", ".join(SCRIBE_SESSION_TASKS))

# ── 한 계획에 여러 세션(11-11 교장 ①) ─────────────────────────
# 계획 JSON의 sessions[]가 세션마다 역할 · 모델 · 이름 · 첫 글 · 읽기 전용 · worktree · 맡을 파일 · 합칠 순서 · 켬을 갖는다.
# 위쪽 칸(role · title · first_prompt …)은 sessions[0]과 같게 둔다(check가 맞춘다) — 옛 계획(세션 하나 모양) · 옛 계획 카드가 그대로 돈다:
# 옛 카드는 위쪽 칸만 고쳐 보내므로, sessions_edit가 없으면 위쪽 칸이 sessions[0]을 이긴다. 세션별로 고치는 카드는 sessions_edit: true를 보낸다
MAX_SESSIONS = 6
S_FIELDS = ("role", "model", "title", "first_prompt", "read_only", "worktree", "files", "merge_order", "task")
TASK_RE = re.compile(r"[a-z][a-z0-9_-]{0,19}")   # 서기 일 종류(11-15) — scribe_room.TASKS의 키 꼴. 띄울 때 session_action scribe-task로 남는다


def norm_files(v: Any) -> list[str]:
    """맡을 파일 — 저장소 기준 상대 경로만(절대 경로 · .. 은 뺀다), 겹친 것 하나로, 40개까지."""
    if isinstance(v, str):
        v = re.split(r"[,\n]", v)
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        s = str(x or "").strip().strip("`").strip()
        s = s[2:] if s.startswith("./") else s
        if not s or s.startswith("/") or s.startswith("~") or ".." in s.split("/"):
            continue
        s = s[:200]
        if s not in out:
            out.append(s)
    return out[:40]


def _int(v: Any) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 0 < n < 1000 else None


def sessions_of(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """계획의 세션 목록(정리한 것). sessions가 없으면 위쪽 칸으로 하나를 만든다(옛 계획)."""
    raw = plan.get("sessions")
    raw = [dict(s) for s in raw if isinstance(s, dict)] if isinstance(raw, list) else []
    if not raw:
        raw = [{}]
    if not plan.get("sessions_edit"):      # 옛 카드 · 옛 계획 — 위쪽 칸이 첫 세션을 이긴다
        for k in (*S_FIELDS, "read_only_set"):
            if plan.get(k) is not None:
                raw[0][k] = plan[k]
    out = []
    for i, s in enumerate(raw[:MAX_SESSIONS]):
        out.append({"role": s.get("role") if s.get("role") in ROLES else "coder",
                    "model": s.get("model") or None,
                    "title": str(s.get("title") or "")[:120],
                    "first_prompt": str(s.get("first_prompt") or "")[:12000],
                    "read_only": bool(s.get("read_only")),
                    "read_only_set": bool(s.get("read_only_set")),
                    "worktree": s["worktree"] if isinstance(s.get("worktree"), bool) else None,
                    "files": norm_files(s.get("files")),
                    "merge_order": _int(s.get("merge_order")) or i + 1,
                    "task": t if isinstance(t := s.get("task"), str) and TASK_RE.fullmatch(t) else None,
                    "on": s.get("on") is not False})
    return out


def adopt_sessions(plan: dict[str, Any]) -> dict[str, Any]:
    """교장의 답 — sessions가 있으면 그것이 맞다. 위쪽 칸을 sessions[0]으로 덮어 옛 카드가 첫 세션을 보이게."""
    ss = plan.get("sessions")
    if isinstance(ss, list) and ss and isinstance(ss[0], dict):
        for k in S_FIELDS:
            plan.pop(k, None)
        plan["sessions_edit"] = True
    return plan


def _mirror(plan: dict[str, Any]) -> dict[str, Any]:
    first = plan["sessions"][0]
    for k in S_FIELDS:
        plan[k] = first[k]
    plan["log_only"] = bool(first.get("log_only"))     # 조사 세션을 브리지가 log만 쓰게 막는다(11-15) — 계획 카드 글
    plan.pop("sessions_edit", None)
    return plan


def _hit(p: str, q: str) -> bool:
    if p == q:
        return True
    for x, y in ((p, q), (q, p)):
        d = x.rstrip("/")
        if (x.endswith("/") or "." not in d.rsplit("/", 1)[-1]) and y.startswith(d + "/"):
            return True
        if any(ch in x for ch in "*?[") and fnmatch.fnmatchcase(y.rstrip("/"), x):
            return True
    return False


def files_overlap(a: list[str], b: list[str]) -> list[str]:
    """맡을 파일 두 벌이 겹치는 것 — 같은 경로 · 폴더 안 · 글롭. 보일 글은 더 구체적인 쪽."""
    out: list[str] = []
    for p in a:
        for q in b:
            if _hit(p, q):
                glob_p, glob_q = (any(ch in x for ch in "*?[") for x in (p, q))
                w = q if glob_p and not glob_q else p if glob_q and not glob_p else max(p, q, key=len)
                if w not in out:
                    out.append(w)
    return sorted(out)


# 「열려 있다」(11-15 사용자) — 합치거나 버리기 전. 서기실 열린 일 · 겹침 막기와 계획 겹침(file_conflicts)이 같은 판단을 쓴다.
# UNMERGED_SQL은 character_session 별칭 cs에 붙인다. worktree 세션은 그 폴더가 남아 있는 동안만(합치기 기록 없이 지운 worktree가
# 영영 열린 채로 남았다 — 11-15 지금 DB에서 296 · 311 · 펫퍼민트 260), 원본 폴더 세션은 끝나기(detached) 전까지
UNMERGED_SQL = ("NOT EXISTS (SELECT 1 FROM session_action m WHERE m.session_id = cs.id "
                "AND m.action IN ('wt-merge', 'wt-discard') AND m.ok)")


def still_open(worktree_path: str | None, detached: bool) -> bool:
    return Path(worktree_path).is_dir() if worktree_path else not detached


WAKE_HINT = """
# 이번 요청은 사람이 아니라 실패 이벤트가 불렀다(자동 기상 2단계)
- 계획은 사람이 텔레그램 · 화면에서 보고 [시작]을 눌러야 시작한다. 사람은 지금 자리에 없을 수 있다 — first_prompt만 읽어도 무엇을 할지 알 수 있게
- 원인을 살펴보는 일이다: role "inspector"(조사). 고치기는 사람이 결과를 보고 정한다
- 같은 실패를 이미 살펴보는 살아 있는 세션이 있으면 "attach"
- 실패 알림 글에 프로젝트가 없으면(인프라 전체) 서버 공통 경로를 보고 가장 가까운 프로젝트를 고르고 이유에 적는다"""


class ForemanDispatcher:
    def __init__(self, engine: AsyncEngine, sessions_dir: str | Path, handoff: HandoffManager, projects: Any,
                 pipeline_snapshot: Any = None, claude_bin: str = "claude", model: str = "sonnet",
                 workdir: str | Path | None = None) -> None:
        self.engine, self.sessions_dir, self.handoff = engine, sessions_dir, handoff
        self.projects = projects                     # () -> [(repo, project_id, name, char_id)]
        self.pipeline_snapshot = pipeline_snapshot   # async () -> {"projects": [...]}
        self.claude_bin, self.model = claude_bin, model
        self.workdir = Path(workdir or Path.home() / ".foreman" / "dispatch")
        self.running: dict[int, str | None] = {}    # 지금 claude -p가 도는 디스패치 → 프로젝트(캐릭터가 일하는 모습)
        self._origin: dict[int, str] = {}           # 도는 디스패치 → human · wake (다시 받기는 사람 것만 끊는다)
        self._procs: dict[int, Any] = {}            # 도는 디스패치 → claude -p 프로세스(PID로 끊기 위해)
        self._cut: set[int] = set()                 # 다시 받기로 끊긴 디스패치 — 늦게 온 결과를 버린다
        self.on_change: Any = None               # 상태가 바뀌면(계획 시작 · 끝 · 시작 · 버림) 화면에 알린다
        # 조사 세션을 브리지가 log만 쓰게 막는가(프로젝트 → bool, 11-15). main.py가 역할 권한(roleguard)을 켠 뒤 넣는다.
        # 막으면 조사는 보통 모드로, 아니면(다른 프로젝트 · 역할 권한이 꺼짐) 예전처럼 읽기 전용(plan 모드)으로 띄운다
        self.inspector_log_only: Any = lambda project: False
        # 11-13 끝난 「진행 중인 일」 줄 내리기 · 낡음 문턱(bridge/foreman_note.py NoteRules). 설정 파일([note])은 main이 읽어 넣는다
        self.note_rules = notes.NoteRules()
        self._note_task: asyncio.Task[Any] | None = None
        self.note_sweep_at: datetime | None = None

    # ── 끝난 줄 내리기(11-13) ──────────────────────────────
    async def sweep_notes(self, why: str = "") -> list[dict[str, Any]]:
        """모든 프로젝트의 진행 중인 일 줄을 훑어 끝난 줄을 내린다. 프로젝트 하나가 실패해도 나머지는 한다."""
        live = set(live_sessions(self.sessions_dir))
        done: list[dict[str, Any]] = []
        for _repo, _pid, name, _ch in self.projects() or []:
            try:
                async with self.engine.begin() as c:
                    rs = await notes.sweep(c, name, live, self.note_rules)
                done += [dict(r, project=name) for r in rs if r["retired"]]
            except Exception as e:  # noqa: BLE001 — 훑기 실패가 계획 · 브리지를 멈추지 않는다(로그로는 남긴다)
                log.warning("노트 훑기 실패(%s, %s): %s: %s", why, name, type(e).__name__, str(e)[:200])
        self.note_sweep_at = datetime.now(UTC).replace(tzinfo=None)
        if done:
            log.info("노트 훑기(%s): 끝난 줄 %d 내림 — %s", why, len(done),
                     ", ".join(f"{r['project']} #{r['id']} {r['why']}" for r in done)[:600])
            self._changed()
        return done

    def poke_notes(self, why: str = "", delay: float = 5.0) -> None:
        """세션 끝 · 합치기 · 버리기 · 브리지 뜸 — 조금 뒤 한 번 훑는다(그 사이 또 오면 한 번으로)."""
        if self._note_task and not self._note_task.done():
            return

        async def later() -> None:
            await asyncio.sleep(delay)
            await self.sweep_notes(why)
        try:
            self._note_task = asyncio.create_task(later(), name="foreman-note-sweep")
        except RuntimeError:            # 이벤트 루프 밖(시험 등)
            self._note_task = None

    async def note_loop(self, every_s: float = 1800.0) -> None:
        """주기 훑기 — 세션 끝 · 합치기 신호를 놓쳐도(브리지 밖에서 합침 등) 30분 안에 맞춘다."""
        while True:
            await asyncio.sleep(every_s)
            await self.sweep_notes("주기")

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass

    # ── 상황 묶음 ────────────────────────────────────────
    async def context(self, request: str, project: str | None = None, wake: bool = False) -> str:
        from bridge.api.dashboard import LABEL
        projs = self.projects() or []
        # 요청에 프로젝트 이름(영문 · 한국어 이름표 · 별명)이 있으면 그 프로젝트만 자세히 — 없으면 전부(토큰을 아낀다).
        # 화면의 그 방 팀장실에서 말하면 project가 정해져 온다
        def named(p: Any) -> bool:
            if project:
                return p[2] == project
            keys = (p[2], p[2].split("-")[0], LABEL.get(p[2]) or "\0", *ALIASES.get(p[2], ()))
            return any(k in request for k in keys)
        wanted = [p for p in projs if named(p)] or projs
        live = live_sessions(self.sessions_dir)
        parts = [f"# 지금 시각 {time.strftime('%Y-%m-%d %H:%M')} (KST)",
                 f"# {'실패 이벤트(자동)' if wake else '사람의 요청'}\n{request}"]
        if project:
            parts.append(f"# 사람이 {LABEL.get(project, project)}({project}) 방에서 말했다 — 다른 프로젝트라는 근거가 없으면 이 프로젝트")
        sp = server_paths()
        if sp:
            parts.append(f"# 서버 공통 경로({OPS_DOC} 「1.」 — 클러스터 · VM · 인프라 일이면 first_prompt에 그대로 옮긴다)\n{sp}")
        async with self.engine.connect() as c:
            for repo, _pid, name, _ch in projs:
                full = any(p[2] == name for p in wanted)
                branch = await _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
                commits = await _git(repo, "log", "--oneline", "-5", "--no-decorate")
                dirty = len([x for x in (await _git(repo, "status", "--porcelain")).splitlines() if x.strip()])
                sec = [f"\n## 프로젝트 {name} (화면 이름 {LABEL.get(name, name)}){'' if full else ' — 요약만'}\n- 저장소: {repo} (브랜치 {branch}, 고친 채 커밋 안 한 파일 {dirty}개)",
                       "- 최근 커밋:\n" + "\n".join("  " + x[:140] for x in commits.splitlines())]
                if full:
                    cm = read_cached(Path(repo, "CLAUDE.md"), 6000)
                    sec.append(f"- CLAUDE.md({repo}/CLAUDE.md):\n" + ("\n".join("  " + x for x in cm.splitlines()) if cm else "  (없음)"))
                    mi = read_cached(memory_dir(repo) / "MEMORY.md", 4000)
                    sec.append(f"- 메모리 색인({memory_dir(repo)}/MEMORY.md — 새 세션이 스스로 읽는다):\n" +
                               ("\n".join("  " + x for x in mi.splitlines()) if mi else "  (없음)"))
                    di = docs_index(repo)
                    if di:
                        sec.append("- docs 목록(본문은 Read로):\n" + "\n".join("  " + x for x in di))
                    loss = sorted(Path(__file__).resolve().parent.parent.joinpath("log").glob(f"{name}_compaction_loss_*.md"))
                    if loss:
                        sec.append(f"- 압축 손실 점검(이 프로젝트 세션이 잊은 사용자 지시 · 결정 목록): {loss[-1]} — 이 일과 겹치는 항목은 first_prompt의 '지켜야 할 것'에")
                    # 진행 중인 일(11-08 노트, 11-13 이 칸 하나만). 확인 뒤 바뀐 것은 ⚠로. 상한을 넘친 줄은 접혀 안 들어간다
                    head = await _git(repo, "rev-parse", "HEAD")
                    nt = await notes.render(c, name, head or None, _git_checked, repo, rules=self.note_rules)
                    fold = f", 접힌 줄 {nt['folded']}개" if nt["folded"] else ""
                    sec.append(f"- 진행 중인 일(note_updates로 고친다, 약 {nt['tokens']}/{nt['cap']}토큰{fold}):\n"
                               + (nt["text"] or "  (없음 — 이번 일이 여러 세션 · 여러 번에 걸쳐 이어질 일이면 한 줄 제안하라)"))
                    rd = await notes.recent_dispatches(c, name)
                    if rd:
                        sec.append("- 지난 디스패치(사람이 고친 칸 — 같은 실수를 되풀이하지 마라):\n" + "\n".join(rd))
                # 세션 — 살아 있는 것 + 최근 48시간
                rows = (await c.execute(text(
                    "SELECT cs.id, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), cs.role, cs.cwd, "
                    "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id), "
                    "(SELECT LEFT(t.prompt_text, 240) FROM turn t WHERE t.session_id = cs.id AND t.origin = 'human' ORDER BY t.seq DESC LIMIT 1) "
                    "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id JOIN project p ON p.id = ch.project_id "
                    "WHERE p.name = :n AND cs.type = 'agent' AND cs.hidden_at IS NULL ORDER BY cs.id DESC LIMIT 25"), {"n": name})).all()
                ss = []
                for sid, cc, title, role, cwd, last, prompt in rows:
                    ls = live.get(cc or "")
                    if not ls and not (last and (datetime.now(UTC).replace(tzinfo=None) - last).total_seconds() < 48 * 3600):   # DB 시각은 UTC
                        continue
                    state = ("멈춤" if ls.state == "T" else "살아 있음") if ls else "끝남"
                    tm = "tmux 안(입력 가능)" if ls and _tmux_env(ls.pid) else ("tmux 밖(입력 불가)" if ls else "")
                    ss.append(f"  - 세션 {sid} \"{title or cc[:8]}\" [{state}{', ' + tm if tm else ''}] 역할 {role}, 마지막 활동 {last}(UTC)")
                    # 이 세션이 지금 무슨 일을 하는지 — 최근 사람 요청 3개 · 마지막 답 앞부분(같은 일을 하는 세션이면 attach)
                    hum = (await c.execute(text(
                        "SELECT t.started_at, LEFT(t.prompt_text, 400), "
                        "(SELECT LEFT(JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.text')), 300) FROM event e WHERE e.turn_id = t.id "
                        " AND e.type = 'assistant_msg' AND e.subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.block')) = 'text' "
                        " ORDER BY e.id DESC LIMIT 1) "
                        "FROM turn t WHERE t.session_id = :s AND t.origin = 'human' ORDER BY t.seq DESC LIMIT 3"), {"s": sid})).all()
                    for at, pr, rep in hum:
                        p_ = re.sub(r"\s+", " ", re.sub(r"</?pasted_content[^>]*>", "", pr or ""))[:220]
                        ss.append(f"    · {at:%m-%d %H:%M} 사람 요청: {p_}" + (f"\n      → 답: {re.sub(chr(10), ' ', rep or '')[:220]}" if rep else ""))
                    srow = (await c.execute(text(
                        "SELECT id, created_at, LEFT(body, 700) FROM summary WHERE session_id = :s AND status = 'ok' ORDER BY id DESC LIMIT 1"),
                        {"s": sid})).first()
                    if srow:
                        ss.append(f"    · 인계 요약 summary_id={srow[0]} ({srow[1]}) 앞부분: " + re.sub(r"\s+", " ", srow[2] or "")[:600])
                sec.append("- 세션:\n" + ("\n".join(ss) if ss else "  (최근 세션 없음)"))
                parts.append("\n".join(sec))
        if self.pipeline_snapshot:
            try:
                snap = await self.pipeline_snapshot()
                pl = []
                for p in snap.get("projects", []):
                    ch = (p.get("chains") or [None])[0]
                    if ch:
                        st = ", ".join(f"{k} {v.get('status')}" for k, v in (ch.get("stages") or {}).items())
                        pl.append(f"- {p['project']}: 마지막 빌드 {ch.get('short')} — {st}" + (f" (깨짐: {ch['broke']})" if ch.get("broke") else ""))
                if pl:
                    parts.append("\n## 파이프라인\n" + "\n".join(pl))
            except Exception as e:  # noqa: BLE001
                log.warning("파이프라인 상태를 못 읽음: %s", type(e).__name__)
        return "\n".join(parts)

    # ── 계획 ─────────────────────────────────────────────
    async def plan(self, request: str, project: str | None = None, origin: str = "human",
                   wake_key: str | None = None, wake_text: str | None = None) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise Refused("무엇을 하려는지 적어 주세요")
        if project and project not in {p[2] for p in (self.projects() or [])}:
            project = None
        t0 = time.monotonic()
        wake = origin == "wake"
        await self.sweep_notes("계획 전")        # 11-13 끝난 일을 진행 중인 일로 넣지 않게 — 부르기 전에 한 번 더 맞춘다
        ctx = await self.context(request, project, wake)
        prompt = INSTRUCTIONS + (WAKE_HINT if wake else "") + "\n\n# 상황 묶음\n" + ctx
        did = await self._record(request, len(ctx), origin, project, wake_key, wake_text)
        if origin == "human":                    # 11-14 다시 받기 — 같은 방에서 아직 도는 앞 계획은 끊고 이것만 남긴다
            self._cut_earlier(did, project)
        self.running[did] = project
        self._origin[did] = origin
        self._changed()
        try:
            return await self._plan(did, prompt, len(ctx), t0)
        finally:
            self.running.pop(did, None)
            self._origin.pop(did, None)
            self._procs.pop(did, None)
            self._cut.discard(did)
            self._changed()

    def _cut_earlier(self, new_did: int, project: str | None) -> list[int]:
        """같은 프로젝트(방)에서 도는 앞 사람 계획을 끊는다. 그 `claude -p` 프로세스만 PID로 죽이고(패턴 찾기 아님),
        디스패치 번호를 _cut에 적어 늦게 온 결과를 _plan이 버리게 한다."""
        cut = [d for d, pj in self.running.items() if d < new_did and pj == project and self._origin.get(d) == "human"]
        for d in cut:
            self._cut.add(d)
            p = self._procs.get(d)
            if p is not None and p.returncode is None:
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
            log.info("다시 받기: 앞 계획 dispatch=%s을 끊음(새 dispatch=%s)", d, new_did)
        return cut

    async def _drop_cut(self, did: int, t0: float) -> None:
        await self._finish(did, None, "replaced", "다시 받기로 끊었습니다", t0)
        raise Refused("다시 받기로 이 계획을 끊었습니다")

    async def _plan(self, did: int, prompt: str, ctx_chars: int, t0: float) -> dict[str, Any]:
        self.workdir.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        dirs = [x for p in (self.projects() or []) for x in ("--add-dir", p[0])]
        try:
            p = await asyncio.create_subprocess_exec(
                self.claude_bin, "-p", "--model", self.model, "--output-format", "json", "--no-session-persistence",
                "--settings", json.dumps({"disableAllHooks": True}),
                "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Agent",
                *dirs,                                   # --add-dir는 값을 여러 개 받아 뒤의 인자를 삼킨다 — 프롬프트는 stdin으로
                cwd=str(self.workdir), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=env)
            self._procs[did] = p
            if did in self._cut:                 # 띄우는 사이에 끊겼다
                p.kill()
            out, err = await asyncio.wait_for(p.communicate(prompt.encode()), PLAN_TIMEOUT_S)
        except TimeoutError:
            p.kill()
            # 화면 · 알림에 나가는 글 — "디스패처"라고 쓰지 않는다(11-09)
            await self._finish(did, None, "failed", f"{PLAN_TIMEOUT_S:.0f}초 안에 계획을 받지 못했습니다", t0)
            raise Refused(f"{PLAN_TIMEOUT_S:.0f}초 안에 계획을 받지 못했습니다") from None
        except OSError as e:
            why = f"claude를 띄우지 못했습니다: {e}" + (f". PATH에 {self.claude_bin}가 없습니다(브리지 서비스의 PATH 확인)"
                                                       if isinstance(e, FileNotFoundError) else "")
            await self._finish(did, None, "failed", why, t0)
            raise Refused(why) from None
        if did in self._cut:                     # 앞 계획의 결과는 화면 · 기록에 섞지 않는다
            await self._drop_cut(did, t0)
        raw = out.decode(errors="replace")
        try:
            j = json.loads(raw)
            result = j.get("result", "")
        except ValueError:
            j, result = None, raw
        # 11-08 — --no-session-persistence라 트랜스크립트가 없다. 사용량은 여기서만 남는다(docs/15_usage.md)
        await record_cli(self.engine, "dispatch", did, self.running.get(did), j)
        plan = parse_plan(result)
        if plan is None:
            # 11-10 원인을 가려 화면에 한 줄로, 답 앞부분 · JSON이 깨진 자리는 dispatch.error와 로그에(비밀값은 가린다)
            kind, detail = diagnose(p.returncode, result, err.decode(errors="replace"), j)
            why = FAIL_WHY[kind]
            m = Masker()
            rec = m.text(f"{why} [{kind}]" + (f": {detail}" if detail else "") + "\n답 앞부분: " + (result or "")[:400]) or why
            log.warning("계획 받기 실패 dispatch=%s [%s] %s", did, kind, (m.text(detail) or "")[:300])
            await self._finish(did, None, "failed", rec, t0)
            raise Refused(f"{why}. 다시 물어보거나 직접 골라 주세요")
        if self._origin.get(did) == "wake":
            plan["wake"] = True      # 자동 기상 계획 — 조사도 읽기 전용 그대로(README 「자는 사이에 커밋이 쌓이면 안 된다」, check)
        plan = await self.check(adopt_sessions(plan), did)
        await self._finish(did, plan, "planned", None, t0)
        return {"dispatch_id": did, "plan": plan, "ms": round((time.monotonic() - t0) * 1000), "context_chars": ctx_chars}

    async def check(self, plan: dict[str, Any], dispatch_id: int | None = None) -> dict[str, Any]:
        """디스패처의 계획을 사실과 맞춘다 — 없는 프로젝트 · 남의 요약 · 죽은 세션을 고르면 경고를 붙이고 비운다.
        세션마다(11-11) 역할 · 모델 · 읽기 전용 · worktree를 맞추고, 맡을 파일이 다른 세션 · 계획과 겹치면 경고를 붙인다."""
        warn = []
        names = {p[2]: p[0] for p in (self.projects() or [])}
        # warn은 화면 계획 창 맨 위에 뜬다 — 사람이 알아야 할 것(계획이 바뀌었다 · 골라 달라)만. 다듬기는 로그로(11-09 사용자:
        # "노트 제안의 출처 ''를 … '이번 요청'으로 바꿨습니다"가 두 번 떴는데 무슨 소린지 모르겠다, 내부 처리면 빼라)
        if plan.get("mode") not in MODES:
            log.info("계획 다듬기: 모르는 방식 %r → new", plan.get("mode")); plan["mode"] = "new"
        ss = sessions_of(plan)
        many = len(ss) > 1
        try:
            log_only = bool(self.inspector_log_only(plan.get("project")))
        except Exception:  # noqa: BLE001 — 모르면 예전처럼 읽기 전용
            log_only = False
        for i, s in enumerate(ss):
            who = f"세션 {i + 1}: " if many else ""
            s["log_only"] = s["role"] == "inspector" and log_only
            if s["role"] == "inspector" and not s["read_only_set"]:
                # 조사는 읽고 알아보는 일(11-15). 브리지가 log만 쓰게 막는 프로젝트면 보통 모드로 — 결과 log를 승인 없이 쓰고 커밋한다.
                # 막지 못하는 프로젝트면 예전처럼 읽기 전용(plan 모드, 고치기 전에 승인). 카드에서 바꾸면 read_only_set.
                # 자동 기상 계획(plan["wake"])은 막는 프로젝트여도 읽기 전용 — 사람이 없는 사이에 log 커밋도 쌓이지 않게(README 「자동 기상」)
                if log_only and not plan.get("wake") and s["read_only"]:
                    s["read_only"] = False
                elif (not log_only or plan.get("wake")) and not s["read_only"]:
                    s["read_only"] = True
                    warn.append(f"{who}역할이 조사라 읽기 전용으로 시작합니다")
            s.pop("read_only_set", None)
            # 모델(11-05) — 포먼(LLM)은 고르지 않는다. 사람이 카드에서 고른 값이 목록에 있으면 그것, 아니면 역할 기본값
            s["model"] = self.handoff.models.pick(s.get("model"), s["role"])
        plan.pop("read_only_set", None)
        plan["sessions"] = ss
        if plan.get("project") not in names and plan["mode"] != "ask":
            warn.append(f"모르는 프로젝트 {plan.get('project')!r}입니다. 사람이 골라 주세요"); plan["mode"] = "ask"
        plan["repo"] = names.get(plan.get("project"))
        async with self.engine.connect() as c:
            if plan.get("summary_id"):
                r = (await c.execute(text("SELECT s.status, p.name FROM summary s JOIN character_session cs ON cs.id = s.session_id "
                                          "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                                          "WHERE s.id = :i"), {"i": plan["summary_id"]})).first()
                if not r or r[0] != "ok" or r[1] != plan.get("project"):
                    warn.append(f"인계 요약 {plan['summary_id']}을(를) 쓸 수 없습니다(없거나 다른 프로젝트). 비웠습니다"); plan["summary_id"] = None
            if plan.get("attach_session"):
                r = (await c.execute(text("SELECT cc_session_id FROM character_session WHERE id = :i"), {"i": plan["attach_session"]})).first()
                ls = live_sessions(self.sessions_dir).get(r[0]) if r else None
                if not ls or ls.state == "T" or not _tmux_env(ls.pid):
                    warn.append(f"세션 {plan['attach_session']}에 보낼 수 없습니다(끝났거나 tmux 밖). 새로 띄우기로 바꿨습니다")
                    plan["attach_session"] = None
                    plan["mode"] = "handoff" if plan.get("summary_id") else "new"
            # 노트 고치기 제안(11-08) — 그 프로젝트의 지금 노트와 맞춘다. 프로젝트를 바꾸면 다른 프로젝트 줄 제안은 빠진다
            plan["note_updates"], nw = await notes.check_ops(c, plan.get("project") if plan.get("project") in names else None,
                                                             plan.get("note_updates") or [])
            for w in nw:                  # 노트 제안 다듬기(출처를 '이번 요청'으로 · 자름 · 모양이 틀려 뺌) — 로그로만
                log.info("계획 다듬기(노트 제안): %s", w)
                if w.startswith(notes.DROPPED_WARN):   # 11-13 없앤 칸(규칙 · 판단)을 쌓자고 했다 — 사람이 보게 카드에
                    warn.append(w)
        if plan["mode"] == "attach" and not plan.get("attach_session"):
            plan["mode"] = "new"
        if plan["mode"] == "handoff" and not plan.get("summary_id"):
            plan["mode"] = "new"
        if plan["mode"] == "attach" and sum(s["on"] for s in ss) > 1:
            for s in ss[1:]:
                s["on"] = False
            warn.append("보내기(attach)는 세션 하나에만 합니다. 둘째 세션부터는 껐습니다")
        # 따로 작업(worktree, 11-05) — 그 프로젝트에 살아 있는 세션이 있으면 기본으로 켠다. 사람이 카드에서 끌 수 있다.
        # 둘째 세션부터는 첫 세션이 살아 있게 되니 기본으로 켠다(11-11)
        repo = plan.get("repo")
        others = [ls for ls in live_sessions(self.sessions_dir).values()
                  if repo and (ls.cwd == repo or ls.cwd.startswith(repo.rstrip("/") + "/"))]
        plan["live_here"] = len(others)
        for i, s in enumerate(ss):
            if s["worktree"] is None:      # 관리자는 늘 원본 폴더(11-11 아홉 — spawn_new가 worktree면 거절한다)
                s["worktree"] = s["role"] != "manager" and (bool(others) or i > 0)
        # [시작]이 무엇을 띄우는지 경고 줄 맨 위에 한 줄로 — 세션 칸이 접혀 있어도 · 옛 카드(첫 세션만 보임)여도 보이게
        if many and plan["mode"] != "attach":
            on_ = [f"{i + 1}「{s['title'] or s['role']}」({ROLE_KO.get(s['role'], s['role'])} · {s['model'] or '기본'}"
                   f"{' · 작업방' if s['worktree'] else ''})" for i, s in enumerate(ss) if s["on"]]
            warn.append(f"이 계획은 세션 {len(on_)}개를 띄웁니다: {', '.join(on_)}")
        # 맡을 파일 겹침(11-11 일곱) — 계획 안 · 살아 있는 세션 · 아직 시작 안 한 다른 계획
        plan["file_overlaps"] = []
        if plan["mode"] != "ask" and plan.get("project") in names:
            plan["file_overlaps"], fw = await self.file_conflicts(plan["project"], ss, dispatch_id)
            warn.extend(fw)
            warn.extend(o["text"] for o in plan["file_overlaps"])
        # 다시 맞출 때(시작 · 다시 열기) 지난번에 붙인 경고는 빼고 새로 — 겹침이 풀렸으면 사라지고, 같은 경고가 쌓이지 않는다
        auto = set(plan.get("auto_warnings") or [])
        plan["warnings"] = warn + [w for w in (plan.get("warnings") or []) if w not in warn and w not in auto]
        plan["auto_warnings"] = warn
        return _mirror(plan)

    # ── 맡을 파일 겹침(11-11 일곱) ───────────────────────────
    async def file_conflicts(self, project: str, sessions: list[dict[str, Any]], dispatch_id: int | None = None,
                             exclude_session: int | None = None) -> tuple[list[dict[str, Any]], list[str]]:
        """세션들의 맡을 파일이 (1) 이 계획의 다른 세션 (2) 살아 있는 세션이 맡은 파일 · 이미 고치고 있는 파일 (3) 아직 시작 안 한
        다른 계획(하루 안)과 겹치는지. 돌려주는 것: (겹침 [{idx, kind, with, files, text}], 못 본 것 경고).
        막지 않는다 — 일부러 나눠 시킬 수 있다. 못 본 것은 경고로 남긴다(겹침 없음과 가른다)."""
        repo = next((p[0] for p in (self.projects() or []) if p[2] == project), None)
        mine = [(i, s) for i, s in enumerate(sessions) if s.get("on", True) and s.get("files")]
        if not mine or not repo:
            return [], []
        many = len(sessions) > 1

        def who(i: int) -> str:
            return f"세션 {i + 1}「{sessions[i].get('title') or sessions[i].get('role')}」의 맡을 파일이" if many else "맡을 파일이"
        out: list[dict[str, Any]] = []
        failed: list[str] = []

        def add(i: int, kind: str, with_: Any, files: list[str], what: str) -> None:
            more = f" 외 {len(files) - 6}개" if len(files) > 6 else ""
            out.append({"idx": i, "kind": kind, "with": with_, "files": files,
                        "text": f"{who(i)} {what}과 겹칩니다: {', '.join(files[:6])}{more}"})
        for n, (i, a) in enumerate(mine):
            for j, b in mine[n + 1:]:
                if hit := files_overlap(a["files"], b["files"]):
                    add(i, "plan", j, hit, f"이 계획의 세션 {j + 1}「{b.get('title') or b.get('role')}」")
        live = {k: v for k, v in live_sessions(self.sessions_dir).items() if v.state != "T"}
        try:
            async with self.engine.connect() as c:
                # 살아 있는 세션(14일 안) + 합치지 않은 worktree(11-15 — 「열려 있다」 = 합치거나 버리기 전, 서기실과 같은 판단)
                rows = (await c.execute(text(
                    "SELECT ds.session_id, ds.files, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), cs.worktree_path, "
                    f"cs.detached_at IS NOT NULL, NOT ({UNMERGED_SQL}) FROM dispatch_session ds "
                    "JOIN dispatch d ON d.id = ds.dispatch_id JOIN character_session cs ON cs.id = ds.session_id "
                    "WHERE d.project = :p AND ds.status = 'started' AND ds.dispatch_id <> :d "
                    f"AND (ds.created_at > NOW(3) - INTERVAL 14 DAY OR (cs.worktree_path IS NOT NULL AND {UNMERGED_SQL})) "
                    "ORDER BY ds.id"),
                    {"p": project, "d": dispatch_id or 0})).all()
                from bridge import scribe_room as sr        # 서기실로 띄운 일(0030 기록이 없던 11-15 전 것도) — 같은 겹침에 넣는다
                scribes = await sr.open_tasks(self.engine, project)
                plans = (await c.execute(text(
                    "SELECT id, COALESCE(edited, plan) FROM dispatch WHERE project = :p AND status = 'planned' AND id <> :d "
                    "AND plan IS NOT NULL AND created_at > NOW(3) - INTERVAL 1 DAY ORDER BY id DESC LIMIT 20"),
                    {"p": project, "d": dispatch_id or 0})).all()
                here = [ls for ls in live.values() if ls.cwd == repo or ls.cwd.startswith(repo.rstrip("/") + "/")]
                ids = {}
                if here:
                    q = text("SELECT cc_session_id, id, COALESCE(custom_title, title) FROM character_session WHERE cc_session_id IN :cc"
                             ).bindparams(bindparam("cc", expanding=True))
                    ids = {r[0]: (int(r[1]), r[2]) for r in (await c.execute(q, {"cc": [ls.session_id for ls in here]})).all()}
        except Exception as e:  # noqa: BLE001 — 0030 전 DB 등. 겹침 없음으로 보이지 않게 경고로
            log.warning("맡을 파일 겹침 확인 실패: %s", type(e).__name__)
            return out, [f"맡을 파일이 살아 있는 세션 · 다른 계획과 겹치는지 보지 못했습니다({type(e).__name__})"]
        claimed: dict[int, tuple[list[str], str, str]] = {}      # 세션 → (맡을 파일, 이름, 어떤 세션)
        for sid, files, cc, title, wpath, detached, merged in rows:
            if sid is None or int(sid) == exclude_session:
                continue
            alive = cc in live
            if not alive and not (wpath and not merged and still_open(wpath, bool(detached))):
                continue
            claimed[int(sid)] = (norm_files(json.loads(files) if isinstance(files, str) else files), title or "",
                                 "살아 있는 세션" if alive else "합치지 않은 세션")
        for o in scribes:
            if o["session_id"] not in claimed and o["session_id"] != exclude_session:
                claimed[o["session_id"]] = (o["files"], o["title"] or "", "열려 있는 서기 세션")
        for sid, (fs, title, kind) in claimed.items():
            for i, a in mine:
                if hit := files_overlap(a["files"], fs):
                    add(i, "claimed", sid, hit, f"{kind} {sid}「{title}」이 맡은 파일")
        for did, pj in plans:
            try:
                other = sessions_of(json.loads(pj) if isinstance(pj, str) else pj)
            except (ValueError, TypeError):
                continue
            theirs = [f for s in other if s["on"] for f in s["files"]]
            for i, a in mine:
                if hit := files_overlap(a["files"], theirs):
                    add(i, "planned", int(did), hit, f"아직 시작하지 않은 계획 #{did}의 맡을 파일")
        # 살아 있는 세션이 실제로 고치고 있는 것(바탕 뒤 변경 — 커밋 안 한 것 포함). 맡을 파일을 적지 않은 세션도 잡는다
        from bridge.overlap import changed_since, git_lines
        top = await git_lines(repo, "rev-parse", "HEAD") if here else None
        for ls in here[:8]:
            sid, title = ids.get(ls.session_id, (None, None))
            if sid is None or sid == exclude_session:
                continue
            base = await git_lines(ls.cwd, "merge-base", "HEAD", top[0]) if top else None
            ch = await changed_since(ls.cwd, base[0]) if base else None
            if ch is None:
                failed.append(f"살아 있는 세션 {sid}이 고치고 있는 파일을 git으로 읽지 못했습니다")
                continue
            for i, a in mine:
                hit = files_overlap(a["files"], sorted(ch))
                if hit and not any(o["kind"] == "claimed" and o["with"] == sid and o["idx"] == i for o in out):
                    add(i, "editing", sid, hit, f"살아 있는 세션 {sid}「{title or ''}」이 이미 고치고 있는 파일")
        return out, failed

    # ── 시작 ─────────────────────────────────────────────
    async def start(self, dispatch_id: int, plan: dict[str, Any], inbox_id: int | list[int] | None = None) -> dict[str, Any]:
        async with self.engine.connect() as c:
            st = (await c.execute(text("SELECT status FROM dispatch WHERE id = :i"), {"i": dispatch_id})).scalar()
        if st != "planned":
            raise Refused({"started": "이미 시작한 계획입니다", "discarded": "버린 계획입니다", "failed": "실패한 계획입니다",
                                                                       "replaced": "다시 받기로 끊긴 계획입니다"}.get(
                st or "", "없는 계획입니다"))
        plan = await self.check(dict(plan), dispatch_id)
        if plan["mode"] == "ask":
            raise Refused("되묻는 계획입니다. 질문에 답해 다시 물어보거나 직접 골라 주세요")
        ss = plan["sessions"]
        on = [i for i, s in enumerate(ss) if s["on"]]
        if not on:
            raise Refused("켠 세션이 없습니다. 하나 이상 켜 주세요")
        for i in on:
            if not ss[i]["first_prompt"].strip():
                raise Refused("넣을 첫 글이 비었습니다" + (f"(세션 {i + 1})" if len(ss) > 1 else ""))
        # 세션마다 결과 — dispatch_session 한 줄씩(off · started · failed)
        done: dict[int, dict[str, Any]] = {}
        errs: dict[int, str] = {}
        if plan["mode"] == "attach":
            async with self.engine.connect() as c:
                r = (await c.execute(text("SELECT cc_session_id, cwd FROM character_session WHERE id = :i"), {"i": plan["attach_session"]})).first()
            from bridge.handoff import transcript_path
            res = await deliver(r[0], ss[on[0]]["first_prompt"], sessions_dir=self.sessions_dir, transcript=transcript_path(r[1] or "", r[0]))
            out = {"mode": "attach", "session_id": plan["attach_session"], "injected": bool(res.get("delivered")), "queued": res.get("queued")}
            done[on[0]] = {"session_id": plan["attach_session"], "cwd": r[1]}
        else:
            # 차례대로 띄운다. 첫 세션이 못 뜨면 아무것도 안 띄운 것이라 그대로 거절(계획은 planned로 남아 다시 누를 수 있다).
            # 둘째부터 못 뜨면 띄운 것은 그대로 두고 결과에 적는다 — 화면 · 텔레그램은 API가 알린다(조용히 하나만 뜨지 않게)
            out = {}
            for i in on:
                s = ss[i]
                try:
                    r = await self.handoff.spawn_new(plan["repo"], plan.get("summary_id") if plan["mode"] == "handoff" and not done else None,
                                                     s["title"] or None, first_prompt=s["first_prompt"], read_only=s["read_only"],
                                                     role=s["role"], worktree=bool(s["worktree"]), model=s["model"],
                                                     scribe_task=s.get("task"))
                except Exception as e:  # noqa: BLE001
                    if not done:
                        raise
                    errs[i] = str(e) if isinstance(e, Refused) else f"{type(e).__name__}: {e}"
                    log.warning("계획 #%s 세션 %d 띄우기 실패: %s", dispatch_id, i + 1, errs[i][:300])
                    continue
                done[i] = r
                if not out:
                    out = dict(r)
            out["mode"] = plan["mode"]
        out["sessions"] = [{"idx": i, "title": ss[i]["title"], "role": ss[i]["role"], "on": ss[i]["on"],
                            "session_id": (done.get(i) or {}).get("session_id"), "tmux": (done.get(i) or {}).get("tmux"),
                            "worktree": (done.get(i) or {}).get("worktree"), "model": (done.get(i) or {}).get("model"),
                            "error": errs.get(i)} for i in range(len(ss))]
        if errs:
            out["failed"] = [{"idx": i, "title": ss[i]["title"], "error": e} for i, e in errs.items()]
            out["note"] = (f"{out.get('note') or ''} " + " ".join(
                f"세션 {i + 1}「{ss[i]['title'] or ss[i]['role']}」은 띄우지 못했습니다({e[:120]})." for i, e in errs.items())
                + " 띄운 세션은 그대로 둡니다. 못 띄운 것은 새 계획으로 다시 띄워 주세요.").strip()
        head = await _git(plan["repo"], "rev-parse", "HEAD") if plan.get("repo") else ""
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET edited = :e, status = 'started', started_at = NOW(3), session_id = :s, project = :p WHERE id = :i"),
                            {"e": json.dumps(plan, ensure_ascii=False), "s": out.get("session_id"), "p": plan.get("project"), "i": dispatch_id})
            try:
                await save_sessions(c, dispatch_id, ss, done, errs)
            except Exception as e:  # noqa: BLE001 — 0030 전 DB. 시작은 되돌리지 않고 알린다
                log.warning("계획 #%s 세션 기록(dispatch_session) 실패: %s", dispatch_id, type(e).__name__)
                out["note"] = f"{out.get('note') or ''} 세션별 기록(맡을 파일)을 남기지 못했습니다({type(e).__name__}).".strip()
            # 노트 — 사람이 켠 제안만, 이 [시작]과 같은 트랜잭션으로
            touched = await notes.apply(c, plan["project"], plan.get("note_updates") or [], dispatch_id,
                                        out.get("session_id") or plan.get("attach_session"), head or None)
        out["notes"] = len(touched)
        # 받은 할 일 — 하나(11-09 코더 「맡길 일」) 또는 여럿(11-11 목록에서 골라 묶은 계획)
        inbox_list = [int(i) for i in (inbox_id if isinstance(inbox_id, list) else [inbox_id] if inbox_id else [])]
        if inbox_list and out.get("session_id"):
            # 이 세션이 가져간다. 합쳐지면 "끝남". 못 가져가도(이미 가져감 · 버림) 시작은 그대로
            from bridge import scribe_room as sr
            taken, whys = [], []
            for iid in dict.fromkeys(inbox_list):
                try:
                    if await sr.inbox_take_pick(self.engine, iid, int(out["session_id"])):
                        taken.append(iid)
                    else:
                        whys.append(f"포스트잇 #{iid}은 이미 다른 세션이 가져갔거나 닫은 것이라 이 세션 몫으로 적지 않았습니다.")
                except Exception as e:  # noqa: BLE001 — 0028 전 DB 등. 시작을 되돌리지 않고 화면에 알린다
                    whys.append(f"포스트잇 #{iid}을 이 세션 몫으로 적지 못했습니다({type(e).__name__}).")
            out["inbox_taken"] = bool(taken) and len(taken) == len(set(inbox_list))
            out["inbox_taken_ids"] = taken
            if whys:
                out["note"] = f"{out.get('note') or ''} {' '.join(whys)}".strip()
            try:
                from bridge.api import coder
                coder.invalidate()
            except Exception:  # noqa: BLE001
                pass
        self._changed()
        return out

    async def saved_plan(self, dispatch_id: int) -> dict[str, Any]:
        """저장된 계획(사람이 고친 것이 있으면 그것) — 관리자에게 넘긴 계획을 관리자가 그대로 시작할 때(11-11 bridge/handover.py)."""
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT COALESCE(edited, plan) FROM dispatch WHERE id = :i"), {"i": dispatch_id})).first()
        if not r or not r[0]:
            raise Refused("저장된 계획이 없습니다")
        return json.loads(r[0]) if isinstance(r[0], str) else dict(r[0])

    async def handed(self, dispatch_id: int) -> dict[str, Any] | None:
        """관리자에게 넘긴 기록(0031). 칸이 없는 DB(0031 전)면 None — 카드는 넘김 표시만 빠진다."""
        try:
            async with self.engine.connect() as c:
                r = (await c.execute(text("SELECT handed_to, handed_at, handed_alert_at FROM dispatch WHERE id = :i"),
                                     {"i": dispatch_id})).first()
        except Exception:  # noqa: BLE001
            return None
        if not r or not r[1]:
            return None
        return {"to_session": r[0], "at": r[1].isoformat() + "Z", "alerted": bool(r[2])}

    async def get(self, dispatch_id: int) -> dict[str, Any]:
        """화면이 계획 하나를 다시 연다(텔레그램 링크 · 말풍선 [제안]) — 계획은 그때 사실과 다시 맞춘다."""
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT id, origin, project, request, status, plan, wake_text, created_at, error FROM dispatch WHERE id = :i"),
                                 {"i": dispatch_id})).first()
        if not r:
            raise Refused("없는 계획입니다")
        plan = json.loads(r[5]) if r[5] else None
        if plan and r[4] == "planned":
            plan = await self.check(plan, dispatch_id)
        elif plan:
            plan["sessions"] = sessions_of(plan)      # 옛 계획(세션 하나 모양)도 같은 모양으로 읽힌다
        return {"dispatch_id": r[0], "origin": r[1], "project": r[2], "request": r[3], "status": r[4], "plan": plan,
                "wake_text": r[6], "created_at": r[7].isoformat() + "Z" if r[7] else None, "error": r[8],
                "handed": await self.handed(dispatch_id)}

    async def merge_order(self, project: str, only: list[str] | None = None) -> dict[str, Any]:
        """합칠 브랜치(그 저장소의 worktree cc/*)가 둘 이상일 때 같은 파일을 건드리는 쌍 · 권하는 순서(11-11 일곱).
        합치기 카드(생명주기 쪽)가 부른다 — GET /api/foreman/merge-order. 판정은 bridge/overlap.py merge_order."""
        from bridge.overlap import git_lines, merge_order
        repo = next((p[0] for p in (self.projects() or []) if p[2] == project), None)
        if not repo:
            raise Refused("모르는 프로젝트입니다")
        lines = await git_lines(repo, "worktree", "list", "--porcelain")
        if lines is None:
            raise Refused("작업방 목록을 git으로 읽지 못했습니다")
        wts, path = [], None
        for ln in lines:
            if ln.startswith("worktree "):
                path = ln[9:]
            elif ln.startswith("branch refs/heads/cc/") and path and path != repo:
                wts.append({"branch": ln[len("branch refs/heads/"):], "cwd": path})
        if only:
            wts = [w for w in wts if w["branch"] in only]
        async with self.engine.connect() as c:
            for w in wts:
                r = (await c.execute(text("SELECT id FROM character_session WHERE cwd = :c ORDER BY id DESC LIMIT 1"), {"c": w["cwd"]})).first()
                w["session_id"] = int(r[0]) if r else None
                w["dispatch_id"] = w["merge_order"] = None
                if r:
                    try:
                        d = (await c.execute(text("SELECT dispatch_id, merge_order FROM dispatch_session WHERE session_id = :s "
                                                  "ORDER BY id DESC LIMIT 1"), {"s": r[0]})).first()
                    except Exception:  # noqa: BLE001 — 0030 전 DB: 계획의 순서 없이 겹침으로만
                        d = None
                    if d:
                        w["dispatch_id"], w["merge_order"] = int(d[0]), d[1]
        main = (await git_lines(repo, "rev-parse", "--abbrev-ref", "HEAD") or ["main"])[0]
        out = await merge_order(repo, wts, main)
        out["project"], out["main"] = project, main
        return out

    async def discard(self, dispatch_id: int) -> None:
        async with self.engine.begin() as c:
            r = await c.execute(text("UPDATE dispatch SET status = 'discarded' WHERE id = :i AND status = 'planned'"), {"i": dispatch_id})
        if not r.rowcount:
            raise Refused("이미 시작했거나 버린 계획입니다")
        self._changed()

    async def state(self) -> dict[str, Any]:
        """화면의 감독실 캐릭터 — 지금 계획을 세우는 중(프로젝트) · [시작]을 기다리는 자동 제안(24시간 안)."""
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT id, project, wake_text, JSON_UNQUOTE(JSON_EXTRACT(plan, '$.title')), created_at FROM dispatch "
                "WHERE origin = 'wake' AND status = 'planned' AND plan IS NOT NULL AND created_at > NOW(3) - INTERVAL 1 DAY ORDER BY id DESC"))).all()
        return {"running": [{"dispatch_id": k, "project": v} for k, v in self.running.items()],
                "pending": [{"dispatch_id": r[0], "project": r[1], "why": r[2], "title": r[3],
                             "created_at": r[4].isoformat() + "Z"} for r in rows]}

    async def notes_of(self, project: str) -> dict[str, Any]:
        """패널 — 그 프로젝트의 노트(접힘 · 확인 뒤 바뀐 것 포함)와 지난 디스패치."""
        repo = next((p[0] for p in (self.projects() or []) if p[2] == project), None)
        if not repo:
            raise Refused("모르는 프로젝트입니다")
        head = await _git(repo, "rev-parse", "HEAD")
        async with self.engine.connect() as c:
            nt = await notes.render(c, project, head or None, _git_checked, repo, rules=self.note_rules)
            rd = await notes.recent_dispatches(c, project, 8)
            auto = await notes.auto_retired(c, project)
        items = [{"id": n["id"], "kind": n["kind"], "body": n["body"], "source": n["source"], "drift": n["drift"],
                  "stale": n["stale"], "folded": n["folded"], "checked_at": n["checked_at"].isoformat() + "Z"} for n in nt["notes"]]
        return {"project": project, "notes": items, "tokens": nt["tokens"], "cap": nt["cap"], "folded": nt["folded"],
                "dispatches": [x.strip()[2:] for x in rd], "auto_retired": auto,
                "stale_rule": {"days": self.note_rules.stale_days, "commits": self.note_rules.stale_commits}}

    async def retire_note(self, note_id: int) -> None:
        async with self.engine.begin() as c:
            if not await notes.retire_by_hand(c, note_id):
                raise Refused("이미 내린 줄입니다")

    async def restore_note(self, note_id: int) -> None:
        async with self.engine.begin() as c:
            if not await notes.restore(c, note_id):
                raise Refused("기계가 끝났다고 본 일이 아니거나 이미 되살렸습니다")
        self._changed()

    async def touch_note(self, note_id: int) -> None:
        async with self.engine.begin() as c:
            if not await notes.touch_by_hand(c, note_id):
                raise Refused("진행 중인 일 줄이 아니거나 이미 내린 줄입니다")

    async def _record(self, request: str, chars: int, origin: str = "human", project: str | None = None,
                      wake_key: str | None = None, wake_text: str | None = None) -> int:
        async with self.engine.begin() as c:
            r = await c.execute(text("INSERT INTO dispatch (origin, project, wake_key, wake_text, request, context_chars, model, status) "
                                     "VALUES (:o, :p, :k, :w, :r, :n, :m, 'planned')"),
                                {"o": origin, "p": project, "k": wake_key, "w": (wake_text or "")[:1000] or None,
                                 "r": request, "n": chars, "m": self.model})
            return r.lastrowid

    async def _finish(self, did: int, plan: dict[str, Any] | None, status: str, error: str | None, t0: float) -> None:
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE dispatch SET plan = :p, status = :s, error = :e, ms = :ms, "
                                 "project = COALESCE(:pj, project) WHERE id = :i"),
                            {"p": json.dumps(plan, ensure_ascii=False) if plan else None, "s": status, "e": (error or "")[:1000] or None,
                             "ms": round((time.monotonic() - t0) * 1000), "pj": (plan or {}).get("project") if (plan or {}).get("repo") else None,
                             "i": did})


async def save_sessions(c: Any, dispatch_id: int, ss: list[dict[str, Any]], done: dict[int, dict[str, Any]],
                        errs: dict[int, str]) -> None:
    """계획의 세션마다 dispatch_session 한 줄(0030) — off(끔) · started(띄움) · failed(못 띄움)."""
    for i, s in enumerate(ss):
        st = "started" if i in done else ("failed" if i in errs else "off")
        d = done.get(i) or {}
        await c.execute(text(
            "INSERT INTO dispatch_session (dispatch_id, idx, role, model, title, files, merge_order, status, session_id, cwd, error) "
            "VALUES (:d, :i, :r, :m, :t, :f, :o, :s, :sid, :cwd, :e)"),
            {"d": dispatch_id, "i": i, "r": s.get("role"), "m": d.get("model") or s.get("model"), "t": (s.get("title") or "")[:255] or None,
             "f": json.dumps(s.get("files") or [], ensure_ascii=False), "o": s.get("merge_order"), "s": st,
             "sid": d.get("session_id"), "cwd": (d.get("cwd") or "")[:1024] or None, "e": (errs.get(i) or "")[:500] or None})


async def record_spawn(engine: AsyncEngine, origin: str, project: str | None, session: dict[str, Any], result: dict[str, Any] | None,
                       error: str | None = None, request: str | None = None, summary_id: int | None = None) -> int:
    """교장 계획을 거치지 않은 띄우기도 dispatch 기록을 남긴다(11-11 교장 ④ — 11-09 232 · 11-10 265가 기록 없음).
    origin: spawn(/api/spawn — + 새 세션 창 · 관리자) · move(새 세션으로 옮기기). 계획 카드와 같은 모양(sessions 한 칸)으로 적어
    지난 디스패치 · 맡을 파일 겹침 · 합칠 순서가 같은 길로 읽는다. 돌려주는 것: dispatch id."""
    if not session.get("role") and (result or {}).get("session_id"):
        async with engine.connect() as c:      # 옮기기는 역할을 옛 세션에서 물려받는다 — 새 세션 행에서 읽는다
            session = {**session, "role": (await c.execute(text("SELECT role FROM character_session WHERE id = :i"),
                                                          {"i": result["session_id"]})).scalar()}
    ss = sessions_of({"sessions": [session], "sessions_edit": True})
    plan = _mirror({"project": project, "mode": "handoff" if summary_id else "new", "summary_id": summary_id,
                    "sessions": ss, "reasons": [f"교장 계획 없이 바로 띄움({origin})"], "note_updates": []})
    req = (request or "").strip() or f"(바로 띄움) {ss[0]['title'] or ss[0]['role']}"
    ok = result is not None and error is None
    async with engine.begin() as c:
        r = await c.execute(text(
            "INSERT INTO dispatch (origin, project, request, plan, status, error, session_id, started_at) "
            "VALUES (:o, :p, :r, :pl, :s, :e, :sid, IF(:ok, NOW(3), NULL))"),
            {"o": origin, "p": project, "r": req[:4000], "pl": json.dumps(plan, ensure_ascii=False), "s": "started" if ok else "failed",
             "e": (error or "")[:1000] or None, "sid": (result or {}).get("session_id"), "ok": ok})
        did = r.lastrowid
        await save_sessions(c, did, ss, {0: result} if ok else {}, {} if ok else {0: error or "실패"})
    return did


# 계획 받기 실패 원인(11-10) — 「답에서 계획을 찾지 못했습니다」 하나로는 한도 · 빈 답 · 깨진 JSON · 호출 실패를 가를 수 없었다
LIMIT_RE = re.compile(r"usage limit|hit your (?:usage )?limit|limit reached|rate[ _-]?limit|out of (?:extra )?usage|사용량 한도", re.I)
FAIL_WHY = {"limit": "사용량 한도에 막혔습니다", "call": "claude 호출이 실패했습니다", "empty": "답이 비어 있습니다",
            "noblock": "답에 계획(JSON)이 없습니다", "broken": "답의 형식이 깨졌습니다"}


def _json_fault(s: str) -> str:
    """계획 후보를 읽을 때 난 JSON 오류와 그 자리 앞뒤 — 나중에 무엇이 깨졌는지 볼 수 있게."""
    m = re.findall(r"```json\s*(\{.*?\})\s*```", s, re.S)
    c = m[-1] if m else s[s.find("{"): s.rfind("}") + 1]
    try:
        d = json.loads(c)
    except ValueError as e:
        pos = getattr(e, "pos", None)
        near = c[max(0, pos - 60): pos + 60].replace("\n", "⏎") if isinstance(pos, int) else ""
        return f"{getattr(e, 'msg', type(e).__name__)} (줄 {getattr(e, 'lineno', '?')} 칸 {getattr(e, 'colno', '?')}) 근처: {near}"
    return "JSON에 mode가 없습니다" if isinstance(d, dict) else "JSON이 객체가 아닙니다"


def diagnose(rc: int | None, result: str, err: str, j: dict[str, Any] | None) -> tuple[str, str]:
    """계획 받기가 실패한 까닭 — (종류, 자세히). 종류는 FAIL_WHY의 키. 자세히는 비밀값을 가리기 전의 짧은 글."""
    result, err = result or "", err or ""
    j = j if isinstance(j, dict) else {}
    if LIMIT_RE.search(result) or LIMIT_RE.search(err) or j.get("api_error_status") == 429:
        return "limit", (result or err)[:200]
    if rc or j.get("is_error"):
        return "call", f"종료 코드 {rc}" + (f" · {j.get('subtype')}" if j.get("subtype") else "") + f": {(err or result)[:200]}"
    if not result.strip():
        return "empty", f"stderr: {err[:200]}" if err.strip() else ""
    if "{" not in result:
        return "noblock", ""
    return "broken", _json_fault(result)


def parse_plan(s: str) -> dict[str, Any] | None:
    """포먼의 답에서 계획 JSON — ```json 블록이 있으면 그것, 없으면 첫 { … 마지막 }."""
    m = re.findall(r"```json\s*(\{.*?\})\s*```", s or "", re.S)
    cands = m[::-1] or ([s[s.find("{"): s.rfind("}") + 1]] if s and "{" in s else [])
    for c in cands:
        try:
            d = json.loads(c)
        except ValueError:
            continue
        if isinstance(d, dict) and "mode" in d:
            return d
    return None
