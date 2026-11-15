"""세션 인계 · 세션 조작(11단계 앞당김, 11-05 — docs/11_handoff.md).

인계 요약은 그 세션 자신이 쓴다. 브리지는 기존 입력 경로(방법 C)로 요청 프롬프트를 넣고, 트랜스크립트의 assistant 줄에서
`<<<FOREMAN-HANDOFF r=X>>> … <<<END r=X>>>`를 꺼낸다. 요청 줄의 머리 `[FOREMAN 인계 요청 r=X]`로 조립기가 그 턴을
origin=handoff로 달아 보통 응답 · 알림과 가른다.

세션 조작(끝내기 · 멈춤 · 되살리기 · 작업 중단)은 사람이 그 pane에서 치는 키와 같은 것을 보낸다(/exit · Ctrl+Z · fg · Esc).
되살리기는 FOREMAN이 멈춘 것만(session_action) — 사용자가 남겨 둔 정지 CC는 건드리지 않는다(CLAUDE.md).
"""

import asyncio
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge import handoff_state as hs
from bridge import pointers as ptr
from bridge import worktree as wt
from bridge.inject import Refused, _status, _tmux_env, deliver, resolve, tmux
from bridge.liveness import _proc_stat, live_sessions
from bridge.model_choice import Models

log = logging.getLogger("foreman.handoff")

REQ_HEAD = "[FOREMAN 인계 요청 r={r}]"
IN_HEAD = "[FOREMAN 인계 r={r}]"
REQ_RE = re.compile(r"\[FOREMAN 인계 요청 r=([0-9a-f]{6})\]")
IN_RE = re.compile(r"\[FOREMAN 인계 r=([0-9a-f]{6})\]")
MAX_BODY = 4000          # 요약을 시킬 때의 분량(1판)
MAX_BODY_V2 = 2500       # 2판 — 문서에 없는 것만
MAX_INJECT = 8000        # 새 세션에 넣는 글 상한
WAIT_S = 600.0           # 요약이 돌아오기를 기다리는 시간
HANDOFF_DIR = Path.home() / ".foreman" / "handoff"
KEEP_FULL = ("진행", "미완", "다음", "주의")      # 분량을 줄일 때도 통째로 넣는 절
# 역할 캐릭터 이름(0017 재배치와 같다, 서기는 12a, 관리자는 11-09 — 합치기 · 시험 · push · 브리지 다시 띄우기 · 기록, 상주 아님).
# 디자이너는 11-10 — 화면(office.js · panel.css · 테마 · 캐릭터 · 이름표 · 카드), 상주 아님.
# 세션이 가질 수 있는 역할이 이것뿐이다 — foreman은 감독실 캐릭터(세션 없음) 몫이라 넣지 않는다
ROLE_KO = {"coder": "코더", "inspector": "조사", "scribe": "서기", "manager": "관리자", "designer": "디자이너"}   # inspector 화면 이름 11-15 점검 → 조사
ROLE_OLD_KO = {"inspector": "점검"}   # 바꾸기 전 화면 이름 — 그 이름의 캐릭터(DB)를 쓸 때 새 이름으로 바꾼다(_character_for)
ROLE_ACT = "role"               # session_action — 역할 바꾸기(11-09). detail "옛 → 새"
SCRIBE_TASK_ACT = "scribe-task"   # session_action — 서기 세션이 무슨 일인지(detail "일 [토픽]", 11-15부터 spawn_new 한 곳에서). scribe_room.TASK_ACT
REST_ACT = "rest"                 # session_action — [쉬게 하기](11-09). 합치기 · 버리기 전까지 그 worktree는 "합치기 기다림"
REST_RESUME_ACT = "rest-resume"   # session_action — [이어서]. 'resume'(일시정지 되살리기)과 섞이지 않게 따로

REQUEST_PROMPT = """{head}
이 세션을 새 세션으로 넘기려고 한다. 새 세션은 이 대화를 전혀 모르고, 아래 인계 문서만 받는다.
지금까지의 대화 전체를 바탕으로 인계 문서를 써라.

- 파일을 고치거나 커밋 · 배포하지 마라. 정확히 쓰려고 git status · git log 같은 읽기는 해도 된다
- 승인을 기다리는 것 · 돌고 있는 서브에이전트 · 걸어 둔 타이머가 있으면 반드시 적어라
- 사용자가 정한 것(결정 · 하지 말라고 한 것)은 빠짐없이 "주의"에 적어라
- 직전 인계 요약을 받고 시작한 세션이면 그 내용도 지금 기준으로 고쳐 넣어라(이어 쓰기가 아니라 갱신)
- {max_body}자 안. 아래 형식 그대로, 마지막 응답에 한 번만 써라(표지 줄 두 개를 글자 그대로):

<<<FOREMAN-HANDOFF r={r}>>>
## 목표 · 맥락
(이 작업이 왜 · 무엇을 향하는지 3~5줄)
## 한 일
(결과 위주 — 커밋 해시 · 파일 경로)
## 진행 중 · 미완
(어디서 멈췄는지, 다음에 건드릴 파일 · 명령)
## 다음 할 일
(순서대로)
## 주의
(사용자가 정한 것, 하지 말 것, 막힌 것 · 확인 필요)
## 참고
(문서 · 로그 · 메모리 경로)
<<<END r={r}>>>"""

# 인계 2판(11-05, docs/11_handoff_v2.md) — 요약은 짧게 · 문서에 없는 것만, 나머지는 「읽을 곳」으로 넘긴다.
# 근거: 압축 손실 점검 두 번 — 잃은 지시의 대부분은 대화에서만 정한 것이었고, 문서에 적힌 것은 읽으면 되살아났다
REQUEST_PROMPT_V2 = """{head}
이 세션을 새 세션으로 넘기려고 한다. 새 세션은 이 대화를 모른다. 인계 문서는 **짧게, 문서에 없는 것만** 쓰고,
나머지는 새 세션이 직접 읽을 「읽을 곳」으로 넘긴다(요약은 기억에서 나와 빠지지만 문서는 남아 있다).

- 파일을 고치거나 커밋 · 배포하지 마라. 정확히 쓰려고 git status · git log · 문서 읽기는 해도 된다
- 이 대화에서 정했는데 아직 어느 문서에도 없는 결정 · 금지 · 기준이 있으면 "문서와 다른 지금"에 적고, 끝에 "문서로 옮길 것"으로 따로 알려라
- 「읽을 곳」은 이 일을 이어 가는 데 꼭 읽어야 할 곳만(보통 3~8개). 한 줄에 하나, 이 모양 그대로:
  - `경로` 「절 이름」 — 왜              예: - `CLAUDE.md` 「작업 규칙」 — 금지 항목
  - `경로` — 왜(무엇에 필요한지)        예: - `docs/11_handoff.md` — 인계 흐름 전체
  문서의 일부는 줄 번호가 아니라 절 제목(「…」, 문서의 # 제목 글 그대로)으로 가리켜라. 줄 번호는 문서가 조금만 바뀌어도 어긋난다.
  경로는 저장소 맨 위 기준. 실제로 있는 파일 · 절만(브리지가 확인하고, 틀리면 넣지 않는다)
- {max_body}자 안. 아래 형식 그대로, 마지막 응답에 한 번만 써라(표지 줄 두 개를 글자 그대로):

<<<FOREMAN-HANDOFF r={r}>>>
## 지금 상태
(어디까지 왔나 — 브랜치 · 마지막 커밋 해시 · 돌고 있는 것. 5~8줄)
## 다음 할 일
(순서대로 3~5개)
## 걸려 있는 것
(승인 대기 · 서브에이전트 · 타이머 · 커밋 안 한 변경 · 사람이 하기로 한 것. 없으면 "없음")
## 문서와 다른 지금
(문서에는 X인데 지금은 Y — 문서를 아직 못 고친 것만. 없으면 "없음")
## 읽을 곳
- `경로` — 왜
<<<END r={r}>>>"""

INJECT_PROMPT_V2 = """{head} 직전 세션 {src}의 인계다. 너는 이 일을 이어받는 새 세션이다.
**먼저 아래 「읽을 곳」을 모두 Read로 읽어라**(줄 범위가 있으면 그 범위, 절 이름이 있으면 그 절). 다 읽은 뒤
(1) 각 문서에서 이 일에 걸리는 규칙 · 결정을 2줄씩 (2) 「문서와 다른 지금」을 어떻게 다룰지를 말하고
(3) 「다음 할 일」을 시작하기 전에 사용자의 확인을 기다려라. 읽었는지는 브리지가 확인한다.

{body}"""

INJECT_PROMPT = """{head} 직전 세션 {src}의 인계 요약이다. 너는 이 일을 이어받는 새 세션이다.
읽고 나서 (1) 이해한 것을 5줄 안으로 말하고 (2) "다음 할 일"을 시작하기 전에 사용자의 확인을 기다려라.

{body}"""


_MOVE_CFG: dict[str, Any] = {"mtime": None, "on": False}


def move_flow_on(path: Path | None = None) -> bool:
    """config/handoff.toml [move] one_flow — 옮기기 한 흐름(11-11). 파일이 바뀌면 다시 읽는다. 못 읽으면 꺼짐(옛 흐름)."""
    import tomllib
    p = path or Path(__file__).resolve().parent.parent / "config" / "handoff.toml"
    try:
        m = p.stat().st_mtime
        if path is None and m == _MOVE_CFG["mtime"]:
            return _MOVE_CFG["on"]
        on = bool((tomllib.loads(p.read_text()).get("move") or {}).get("one_flow", False))
    except (OSError, ValueError) as e:
        log.warning("옮기기 한 흐름 설정을 못 읽어 끔: %s", e)
        return False
    if path is None:
        _MOVE_CFG.update(mtime=m, on=on)
    return on


def new_req() -> str:
    return secrets.token_hex(3)


def request_prompt(req: str, fmt: str = "v2") -> str:
    if fmt == "v2":
        return REQUEST_PROMPT_V2.format(head=REQ_HEAD.format(r=req), r=req, max_body=MAX_BODY_V2)
    return REQUEST_PROMPT.format(head=REQ_HEAD.format(r=req), r=req, max_body=MAX_BODY)


def block_re(req: str) -> re.Pattern[str]:
    return re.compile(rf"<<<FOREMAN-HANDOFF r={req}>>>[ \t]*\n(.*?)\n[ \t]*<<<END r={req}>>>", re.S)


def extract_block(texts: str, req: str) -> str | None:
    """assistant 글에서 마지막 표지 짝 사이. 없으면 None."""
    found = block_re(req).findall(texts)
    body = found[-1].strip() if found else ""
    return body or None


def assistant_text(path: str | Path, offset: int) -> str:
    """offset 뒤 메인 세션 assistant 줄의 text 블록만 — user 줄(요청 프롬프트에도 표지가 있다)은 보지 않는다."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return ""
    out = []
    for raw in data.split(b"\n"):
        if b'"assistant"' not in raw:            # 빠른 거르기(정확한 판정은 아래 json)
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        for b in (d.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                out.append(b["text"])
    return "\n".join(out)


def _sections(body: str) -> list[tuple[str, str]]:
    parts, cur, buf = [], "", []
    for line in body.splitlines():
        if line.startswith("## "):
            if cur or buf:
                parts.append((cur, "\n".join(buf).strip()))
            cur, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if cur or buf:
        parts.append((cur, "\n".join(buf).strip()))
    return parts


def fit_body(body: str, limit: int = MAX_INJECT, full_path: str | None = None) -> tuple[str, bool]:
    """넣을 분량으로 — 넘으면 진행 중 · 미완 · 다음 할 일 · 주의는 통째로, 나머지 절은 앞부분만. (글, 줄였나)"""
    if len(body) <= limit:
        return body, False
    secs = _sections(body)
    keep = sum(len(t) + len(h) + 4 for h, t in secs if any(k in h for k in KEEP_FULL))
    others = [h for h, _ in secs if not any(k in h for k in KEEP_FULL)]
    room = max(200, (limit - keep - 300) // max(1, len(others)))
    out = []
    for h, t in secs:
        if not any(k in h for k in KEEP_FULL) and len(t) > room:
            t = t[:room].rsplit("\n", 1)[0] + "\n…(줄임)"
        out.append(f"## {h}\n{t}" if h else t)
    s = "\n".join(out)
    if full_path:
        s += f"\n\n(분량 때문에 일부 절을 줄였다 — 전체는 {full_path} 을 Read하라)"
    return s[: limit + 400], True


# 11-11 — pgrep -f 함정(bridge/pgrep_guard.py가 PreToolUse에서 거부하지만, 거부당하기 전에 알게). 서기 COMMON도 같은 줄
PGREP_LINE = ("`pgrep -f` · `pkill -f`를 쓰지 않는다 — CC는 Bash 명령 전체를 `bash -c`로 돌려 패턴이 자기 셸에 걸린다"
              "(브리지가 거부한다). 기다릴 때는 그 작업의 PID나 결과 파일을 보고, 꼭 찾아야 하면 `[p]ython`처럼 대괄호로 감싸 "
              "확인과 실행을 따로 친다")


def wt_block(cwd: str | None) -> str:
    """받는 세션이 따로 작업(worktree)에서 떴으면 넣는 글 맨 앞에 붙일 절(11-09). 인계를 쓴 세션은 받을 세션이 어디서 뜰지
    모른다 — 「지금 상태」에 "브랜치 main"이라고 적어도 실제는 worktree였다(11-05 · 11-09 두 번). 띄운 브리지가 안다.
    11-10 — 모든 저장소에 들어가므로 공통 사실만(런슈즈 세션이 "README 로드맵 표" · log/ 같은 FOREMAN 규칙을 자기 규칙으로 읽었다).
    저장소별 분기는 만들지 않고 나머지는 그 저장소 CLAUDE.md로(사용자 결정, 런슈즈 세션 요청)."""
    if not cwd:
        return ""
    _, name = wt.split(cwd)
    if not name:
        return ""
    return ("## 이 세션이 뜬 자리 (브리지가 띄울 때 정함)\n"
            f"- 이 세션은 원본 폴더가 아니라 **따로 작업(worktree) `.worktrees/{name}` · 브랜치 `{wt.BRANCH_PREFIX}{name}`**에서 떴다. "
            "아래 인계에 \"브랜치 main\"이라고 적혀 있어도 이것이 맞다(인계를 쓴 세션은 어디서 뜰지 몰랐다)\n"
            "- 커밋은 이 브랜치에 한다. push · 합치기는 기본으로 하지 않는다(사용자가 시키면 따른다) — "
            "합치기는 사람(패널 [합치기]) 또는 관리 세션이 한다. 끝내기 전에 커밋을 마친다\n"
            "- 브리지를 다시 띄우지 않는다 — 도는 브리지는 FOREMAN 원본 폴더의 코드다\n"
            f"- {PGREP_LINE}\n"
            "- 그 밖에 원본 폴더에서만 할 일 · 결과를 남길 자리는 그 저장소의 CLAUDE.md가 정한 것을 따른다"
            "(정한 것이 없으면 이 브랜치의 커밋과 최종 보고로 충분하다)\n\n")


# 교장 계획으로 띄울 때(11-10) — 사람이 계획 카드에서 이미 봤으니 확인을 다시 기다리지 않는다. 인계 단독(새 세션으로 옮기기)은 위 글 그대로
INJECT_PROMPT_V2_GO = """{head} 직전 세션 {src}의 인계다. 너는 이 일을 이어받는 새 세션이다.
**먼저 아래 「읽을 곳」을 모두 Read로 읽어라**(줄 범위가 있으면 그 범위, 절 이름이 있으면 그 절). 다 읽은 뒤
(1) 각 문서에서 이 일에 걸리는 규칙 · 결정을 2줄씩 (2) 「문서와 다른 지금」을 어떻게 다룰지를 말하고
(3) 「다음 할 일」을 바로 시작하라(사람이 계획 카드에서 이미 봤다). 읽었는지는 브리지가 확인한다.

{body}"""

INJECT_PROMPT_GO = """{head} 직전 세션 {src}의 인계 요약이다. 너는 이 일을 이어받는 새 세션이다.
읽고 나서 "다음 할 일"을 바로 시작하라(사람이 계획 카드에서 이미 봤다).

{body}"""


def inject_prompt(req: str, src: str, body: str, confirm: bool = True) -> str:
    """confirm=False — 교장 계획으로 띄울 때. 「확인을 기다려라」 없이 바로 시작하게 한다."""
    v2 = ptr.is_v2(body)
    tpl = (INJECT_PROMPT_V2 if v2 else INJECT_PROMPT) if confirm else (INJECT_PROMPT_V2_GO if v2 else INJECT_PROMPT_GO)
    return tpl.format(head=IN_HEAD.format(r=req), src=src, body=body)


NOTE_MAX = 2000


def note_block(note: str | None) -> str:
    """새 세션으로 옮기기 [덧붙여서 보내기](11-09) — 사람이 넣기 직전에 쓴 말. 인계 글 맨 끝에 붙인다(마지막에 읽는 말).
    요약 본문은 바꾸지 않는다(요약 이력 · 읽을 곳 확인이 그대로)."""
    n = (note or "").strip()[:NOTE_MAX]
    return f"\n\n## 사람이 덧붙인 말 (넣기 직전)\n{n}" if n else ""


def transcript_path(cwd: str, cc_session_id: str) -> str:
    """CC가 쓰는 자리 — ~/.claude/projects/<cwd의 영숫자 밖 글자를 -로>/<id>.jsonl(실측: '/' '_' → '-')."""
    return str(Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", cwd) / f"{cc_session_id}.jsonl")


async def repo_root(cwd: str | None) -> str | None:
    """그 폴더가 속한 git 저장소 맨 위(worktree면 그 worktree). 저장소가 아니면 cwd 그대로."""
    if not cwd or not Path(cwd).is_dir():
        return None
    top = await ptr._git(cwd, "rev-parse", "--show-toplevel")
    return top or cwd


def compact_body(path: str | Path) -> str | None:
    """마지막 auto-compact 요약(CC가 쓴 것) + 그 뒤 사람 프롬프트 · 마지막 응답 — 죽은 세션의 보조 수단."""
    last_compact, after_prompts, last_reply = None, [], ""
    try:
        f = open(path, "rb")
    except OSError:
        return None
    with f:
        for raw in f:
            if b'"isCompactSummary":true' in raw:
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue
                c = (d.get("message") or {}).get("content")
                last_compact = c if isinstance(c, str) else "".join(
                    b.get("text", "") for b in c or [] if isinstance(b, dict))
                after_prompts, last_reply = [], ""
            elif last_compact is not None and (b'"type":"user"' in raw or b'"type":"assistant"' in raw):
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue
                if d.get("isSidechain") or d.get("isMeta"):
                    continue
                c = (d.get("message") or {}).get("content")
                if d.get("type") == "user" and isinstance(c, str) and c.strip():
                    after_prompts.append(c.strip()[:300])
                elif d.get("type") == "assistant":
                    t = "".join(b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")
                    if t.strip():
                        last_reply = t.strip()
    if last_compact is None:
        return None
    out = ["## 마지막 자동 압축 요약(CC가 쓴 것)", last_compact.strip()[:6000]]
    if after_prompts:
        out += ["## 압축 뒤 사람 프롬프트", *[f"- {p}" for p in after_prompts[-15:]]]
    if last_reply:
        out += ["## 마지막 응답", last_reply[:2000]]
    return "\n".join(out)


@dataclass
class SessionRow:
    id: int
    cc: str | None
    character_id: int | None
    cwd: str | None
    transcript: str | None
    project: str | None
    title: str | None


class HandoffManager:
    def __init__(self, engine: AsyncEngine, sessions_dir: str | Path, notifier: Any = None, on_change: Any = None,
                 tmux_socket: str | None = None, claude_bin: str = "claude", project_of: Any = None) -> None:
        self.engine, self.sessions_dir, self.notifier, self.on_change = engine, sessions_dir, notifier, on_change
        self.socket = tmux_socket or f"{os.environ.get('TMUX_TMPDIR', '/tmp')}/tmux-{os.getuid()}/default"
        self.claude_bin = claude_bin
        self.project_of = project_of        # cwd → (프로젝트 이름|None, 캐릭터 id) — 조립기와 같은 규칙(새 세션 행을 미리 만들 때)
        self.wait_s = WAIT_S
        self._tasks: set[asyncio.Task[Any]] = set()
        self.schema: Any = None             # 스키마 잠금 — 합치기 · 버리기에서 푼다(main.py가 넣는다)
        self.previews: Any = None           # 미리보기(bridge/previews.py) — 끝내기 · 합치기 · 버리기에서 끈다
        self.models = Models()              # 고를 수 있는 모델 · 역할 기본값(config/models.toml, 11-05)
        self.promote: Any = None            # 문서로 옮기기(bridge/promote.py) — main.py가 넣는다
        self.mergeprep: Any = None          # 합치기 준비(bridge/mergeprep.py, 11-11) — config/handoff.toml이 켜면 main.py가 넣는다

    # ── 조회 ────────────────────────────────────────────
    async def session(self, sid: int) -> SessionRow | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, cs.character_id, cs.cwd, tf.path, p.name, COALESCE(cs.custom_title, cs.title) "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "LEFT JOIN project p ON p.id = ch.project_id LEFT JOIN transcript_file tf ON tf.id = cs.transcript_file_id "
                "WHERE cs.id = :id"), {"id": sid})).first()
        return SessionRow(*r) if r else None

    async def summaries(self, sid: int, limit: int = 20) -> list[dict[str, Any]]:
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT id, req, kind, source, status, turn_id, body, chars, raw, error, parent_id, injected_cc_session, "
                "injected_at, created_at FROM summary WHERE session_id = :s ORDER BY id DESC LIMIT :n"),
                {"s": sid, "n": limit})).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("injected_at", "created_at"):
                d[k] = d[k].isoformat() + "Z" if d[k] else None
            if d["raw"]:
                d["raw"] = d["raw"][-4000:]
            out.append(d)
        return out

    async def summary(self, summary_id: int) -> dict[str, Any] | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT * FROM summary WHERE id = :i"), {"i": summary_id})).mappings().first()
        return dict(r) if r else None

    async def latest_ok(self, sid: int) -> dict[str, Any] | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT * FROM summary WHERE session_id = :s AND status = 'ok' ORDER BY id DESC LIMIT 1"),
                {"s": sid})).mappings().first()
        return dict(r) if r else None

    async def controls(self, row: SessionRow) -> dict[str, Any]:
        """패널이 버튼을 켜고 끄는 근거 — 실제 조작 때 다시 확인한다."""
        live = live_sessions(self.sessions_dir).get(row.cc or "")
        te = _tmux_env(live.pid) if live else None
        busy = bool(live and _status(self.sessions_dir, live.pid) == "busy")
        stopped_pid = await self._foreman_stopped(row.id)
        pending = await self._pending(row.id) or await self._promote_busy(row.id)
        out: dict[str, Any] = {"live": bool(live), "pid": live.pid if live else None, "state": live.state if live else None,
                               "tmux": bool(te), "busy": busy, "pending_req": pending,
                               "foreman_stopped": stopped_pid is not None}
        why = None
        if not live:
            why = "끝난 세션입니다"
        elif live.state == "T":
            why = "일시정지된 세션입니다" + (" (FOREMAN이 멈춤)" if stopped_pid else " (사람이 멈춤, 건드리지 않습니다)")
        elif not te:
            why = "FOREMAN 터미널(tmux) 밖에서 띄운 세션이라 화면에서 보내거나 끌 수 없습니다"
        elif busy:
            why = "작업 중입니다"
        out["why"] = why
        ok_live = bool(live and te and live.state != "T")
        out["can"] = {
            "summary": ok_live and not busy and not pending,
            "promote": ok_live and not busy and not pending and self.promote is not None,
            "headless": not live and bool(row.cc and row.cwd) and not pending,
            "compact": bool(row.transcript),
            "exit": ok_live and not busy,
            "rest": ok_live and not busy and bool(row.cwd and wt.split(row.cwd)[1]),   # 쉬게 하기(11-09) — worktree 세션만
            "stop": ok_live and not busy,
            "resume": bool(live and live.state == "T" and stopped_pid == live.pid),
            "interrupt": ok_live and busy,
            "spawn": bool(row.cwd and Path(row.cwd).is_dir()),
        }
        try:
            out["worktree"] = await self.worktree(row)
        except Refused as e:
            out["worktree"] = {"error": str(e)}
        # 2판 인계를 받고 시작한 세션 — 「읽을 곳」을 실제로 읽었나(11-05)
        out["reads"] = await self.handoff_reads(row)
        # 11-11 C 2물결 「일곱」 — 옮기기 한 흐름(config/handoff.toml [move] one_flow) · 이 세션이 넘겨받은 글(새 세션 패널에 보인다)
        out["move_flow"] = move_flow_on()
        try:
            out["received"] = await self.received(row)
        except Exception as e:  # noqa: BLE001 — 못 읽어도 패널은 뜬다
            out["received"] = {"error": f"넘겨받은 글을 읽지 못했습니다({type(e).__name__})"}
        return out

    async def received(self, row: SessionRow) -> dict[str, Any] | None:
        """이 세션이 옮기기로 넘겨받은 요약 — 옮기기 전 확인 창을 없앤 대신 받은 쪽 패널에서 무엇이 넘어왔는지 본다."""
        if not row.cc:
            return None
        async with self.engine.connect() as c:
            s = (await c.execute(text(
                "SELECT s.id, s.session_id, s.body, s.injected_at, COALESCE(cs.custom_title, cs.title) FROM summary s "
                "LEFT JOIN character_session cs ON cs.id = s.session_id WHERE s.injected_cc_session = :c "
                "ORDER BY s.injected_at DESC LIMIT 1"), {"c": row.cc})).first()
        if not s:
            return None
        return {"summary_id": s[0], "from_session": s[1], "from_title": s[4], "body": s[2] or "",
                "at": s[3].isoformat() + "Z" if s[3] else None}

    async def _pending(self, sid: int) -> str | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT req FROM summary WHERE session_id = :s AND status = 'requested' "
                "AND created_at > NOW(3) - INTERVAL 15 MINUTE ORDER BY id DESC LIMIT 1"), {"s": sid})).first()
        return r[0] if r else None

    async def _promote_busy(self, sid: int) -> str | None:
        """문서로 옮기기 요청(목록 · 쓰기)을 기다리는 중이면 "promote" — 인계 요청과 겹쳐 보내지 않는다.
        표가 아직 없으면(0020 전) 없는 것으로 본다."""
        if self.promote is None:
            return None
        try:
            return "promote" if await self.promote._busy(sid) else None
        except Exception as e:  # noqa: BLE001
            log.warning("문서로 옮기기 상태를 읽지 못함(0020 적용 전?): %s", type(e).__name__)
            return None

    async def _foreman_stopped(self, sid: int) -> int | None:
        """마지막 멈춤 · 되살리기 기록이 FOREMAN의 성공한 멈춤이면 그 pid."""
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT action, pid FROM session_action WHERE session_id = :s AND ok AND action IN ('stop', 'resume') "
                "ORDER BY id DESC LIMIT 1"), {"s": sid})).first()
        return int(r[1]) if r and r[0] == "stop" and r[1] else None

    # ── 기록 ────────────────────────────────────────────
    async def _act(self, sid: int | None, action: str, pid: int | None, ok: bool, detail: str | None) -> None:
        async with self.engine.begin() as c:
            await c.execute(text(
                "INSERT INTO session_action (session_id, action, pid, ok, detail) VALUES (:s, :a, :p, :o, :d)"),
                {"s": sid, "a": action, "p": pid, "o": ok, "d": (detail or "")[:512] or None})
        log.info("세션 조작 %s session=%s pid=%s %s %s", action, sid, pid, "ok" if ok else "실패", detail or "")

    async def _scribe_task_of(self, sid: int | None) -> str | None:
        """옮기기 — 옛 서기 세션의 일 종류를 물려준다(새 세션이 같은 일을 잇는다)."""
        if not sid:
            return None
        async with self.engine.connect() as c:
            return (await c.execute(text("SELECT detail FROM session_action WHERE session_id = :s AND action = :a AND ok "
                                         "ORDER BY id DESC LIMIT 1"), {"s": sid, "a": SCRIBE_TASK_ACT})).scalar()

    async def _new_summary(self, row: SessionRow, kind: str, source: str, status: str, **kw: Any) -> tuple[int, str]:
        req = new_req()
        # 인계 검증(11-06) — 만들 때의 git · 잠금 상태. 고친 요약은 원본의 상태를 물려받는다(내용이 그때 기준이다)
        state = kw["state"] if "state" in kw else await self._snapshot(row)
        async with self.engine.begin() as c:
            res = await c.execute(text(
                "INSERT INTO summary (character_id, session_id, req, kind, source, status, body, state, chars, raw, error, parent_id) "
                "VALUES (:ch, :s, :r, :k, :src, :st, :b, :state, :n, :raw, :e, :par)"),
                {"ch": row.character_id, "s": row.id, "r": req, "k": kind, "src": source, "st": status,
                 "b": kw.get("body"), "state": json.dumps(state, ensure_ascii=False) if state else None,
                 "n": len(kw["body"]) if kw.get("body") else None, "raw": kw.get("raw"),
                 "e": kw.get("error"), "par": kw.get("parent_id")})
        return res.lastrowid, req

    async def _snapshot(self, row: SessionRow) -> dict[str, Any] | None:
        try:
            return await hs.snapshot(row.cwd, row.project, self.schema)
        except Exception as e:  # noqa: BLE001 — 상태를 못 적어도 요약은 만든다(넣을 때 "확인 못 함"으로 보인다)
            log.warning("인계 상태 기록 실패 session=%s: %s", row.id, type(e).__name__)
            return None

    @staticmethod
    def _json(v: Any) -> Any:
        if v is None or isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except ValueError:
            return None

    async def _finish(self, summary_id: int, status: str, body: str | None, raw: str | None, error: str | None,
                      turn_id: int | None = None) -> None:
        async with self.engine.begin() as c:
            await c.execute(text(
                "UPDATE summary SET status = :st, body = :b, chars = :n, raw = :raw, error = :e, "
                "turn_id = COALESCE(:t, turn_id) WHERE id = :i"),
                {"st": status, "b": body, "n": len(body) if body else None, "raw": (raw or "")[-200000:] or None,
                 "e": (error or "")[:512] or None, "t": turn_id, "i": summary_id})
        if self.on_change:
            self.on_change()

    def _notify(self, row: SessionRow, msg: str) -> None:
        if self.notifier:
            try:
                rule = self.notifier.rules.for_project(row.project) if hasattr(self.notifier, "rules") else None
                prefix = (rule.prefix if rule and rule.prefix else "[미분류]") + " "     # 승인 알림과 같은 접두어
                self.notifier.send_direct(row.project, "handoff", row.id, prefix + msg)
            except Exception as e:  # noqa: BLE001 — 알림 실패가 요약을 막지 않는다
                log.warning("인계 알림 실패: %s", type(e).__name__)

    def _spawn_task(self, coro: Any) -> None:
        t = asyncio.create_task(coro)
        self._tasks.add(t)

        def done(t: asyncio.Task[Any]) -> None:
            self._tasks.discard(t)
            if not t.cancelled() and t.exception():
                log.error("인계 작업 실패: %r", t.exception(), exc_info=t.exception())
        t.add_done_callback(done)

    # ── 요약 받기 ────────────────────────────────────────
    async def request_live(self, row: SessionRow, kind: str = "snapshot", fmt: str = "v2") -> dict[str, Any]:
        """살아 있는 tmux 세션에 요약을 시킨다. 보내고 바로 돌아오고, 응답은 뒤에서 기다린다."""
        if not row.cc:
            raise Refused("CC 세션 ID가 없습니다")
        if await self._pending(row.id) or await self._promote_busy(row.id):
            raise Refused("이미 요약 · 대화 결정 문서에 적기를 기다리는 중입니다")
        _t, ls, busy = await resolve(row.cc, self.sessions_dir)
        if busy:
            raise Refused("작업 중입니다. 작업이 끝난 뒤에 요약해 주세요(중간에 끼면 작업과 섞입니다)")
        sid, req = await self._new_summary(row, kind, "self", "requested")
        path = row.transcript or transcript_path(row.cwd or "", row.cc)
        offset = os.path.getsize(path) if os.path.exists(path) else 0
        try:
            res = await deliver(row.cc, request_prompt(req, fmt), sessions_dir=self.sessions_dir, transcript=path)
        except Refused as e:
            await self._finish(sid, "failed", None, None, f"보내지 못함: {e}")
            raise
        if not res.get("delivered"):
            await self._finish(sid, "failed", None, None, "제출이 확인되지 않았다. 입력 칸에 남았을 수 있다")
            return {"summary_id": sid, "req": req, "status": "failed"}
        self._spawn_task(self._wait_live(row, sid, req, path, offset, (res["delivered"] or {}).get("prompt_id")))
        return {"summary_id": sid, "req": req, "status": "requested", "pid": ls.pid}

    async def _wait_live(self, row: SessionRow, sid: int, req: str, path: str, offset: int, prompt_id: str | None) -> None:
        loop = asyncio.get_running_loop()
        end = loop.time() + self.wait_s
        ended_seen: float | None = None
        turn_id = None
        while loop.time() < end:
            await asyncio.sleep(2.0)
            texts = assistant_text(path, offset)
            body = extract_block(texts, req)
            if body:
                await self._finish(sid, "ok", body, texts, None, turn_id or await self._turn_of(prompt_id))
                self._notify(row, f"인계 요약 저장 ({len(body):,}자) — 세션 {row.cc[:8] if row.cc else row.id}")
                return
            if prompt_id and ended_seen is None:
                turn_id = await self._turn_of(prompt_id)
                if turn_id and await self._turn_ended(turn_id):
                    ended_seen = loop.time()
            if ended_seen and loop.time() - ended_seen > 6:     # 턴이 닫혔는데 표지가 없다(마지막 줄이 늦게 쓰일 여유 6초)
                await self._finish(sid, "failed", None, texts, "턴이 끝났는데 인계 표지가 없다", turn_id)
                self._notify(row, "인계 요약 실패 — 표지 없음(원문은 패널에)")
                return
            if row.cc and row.cc not in live_sessions(self.sessions_dir):
                await self._finish(sid, "failed", None, texts, "기다리는 중에 세션이 끝났다", turn_id)
                return
        await self._finish(sid, "timeout", None, assistant_text(path, offset), f"{self.wait_s:.0f}초 안에 돌아오지 않았다", turn_id)
        self._notify(row, "인계 요약 시간 초과")

    async def _turn_of(self, prompt_id: str | None) -> int | None:
        if not prompt_id:
            return None
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT id FROM turn WHERE prompt_id = :p"), {"p": prompt_id})).first()
        return r[0] if r else None

    async def _turn_ended(self, turn_id: int) -> bool:
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT ended_at FROM turn WHERE id = :i"), {"i": turn_id})).first()
        return bool(r and r[0])

    async def request_headless(self, row: SessionRow, kind: str = "handoff", fmt: str = "v2") -> dict[str, Any]:
        """죽은 세션 — claude -p --resume <id>로 같은 컨텍스트를 불러 그 세션이 쓴다(fork 아님). 버튼을 누를 때만."""
        if not row.cc or not row.cwd:
            raise Refused("CC 세션 ID나 작업 폴더 정보가 없습니다")
        if row.cc in live_sessions(self.sessions_dir):
            raise Refused("이 세션은 아직 살아 있습니다. 같은 세션을 두 곳에서 이어 쓰지 않도록 막았습니다")
        if await self._pending(row.id):
            raise Refused("이미 요약을 기다리는 중입니다")
        if not Path(row.cwd).is_dir():
            raise Refused(f"작업 폴더가 없습니다: {row.cwd}")
        sid, req = await self._new_summary(row, kind, "self_headless", "requested")
        self._spawn_task(self._run_headless(row, sid, req, fmt))
        return {"summary_id": sid, "req": req, "status": "requested"}

    async def _run_headless(self, row: SessionRow, sid: int, req: str, fmt: str = "v2") -> None:
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        try:
            p = await asyncio.create_subprocess_exec(
                self.claude_bin, "-p", "--resume", row.cc or "", "--output-format", "text", request_prompt(req, fmt),
                cwd=row.cwd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, env=env)
            try:
                out, err = await asyncio.wait_for(p.communicate(), self.wait_s)
            except TimeoutError:
                p.kill()
                await p.wait()
                await self._finish(sid, "timeout", None, None, f"claude -p가 {self.wait_s:.0f}초 안에 끝나지 않았다")
                return
        except OSError as e:
            await self._finish(sid, "failed", None, None, f"claude를 띄우지 못함: {e}")
            return
        texts = out.decode(errors="replace")
        body = extract_block(texts, req)
        if body:
            await self._finish(sid, "ok", body, texts, None)
            self._notify(row, f"죽은 세션 인계 요약 저장 ({len(body):,}자) — claude -p --resume")
        else:
            await self._finish(sid, "failed", None, texts or err.decode(errors="replace")[-4000:],
                               f"표지 없음 (종료 코드 {p.returncode})")

    async def from_compact(self, row: SessionRow, kind: str = "handoff") -> dict[str, Any]:
        if not row.transcript:
            raise Refused("이 세션의 기록 파일이 없습니다")
        body = await asyncio.to_thread(compact_body, row.transcript)
        if not body:
            raise Refused("자동 압축 요약이 없습니다(압축된 적이 없는 세션입니다)")
        sid, req = await self._new_summary(row, kind, "compact", "ok", body=body)
        if self.on_change:
            self.on_change()
        return {"summary_id": sid, "req": req, "status": "ok"}

    async def edit(self, summary_id: int, body: str) -> dict[str, Any]:
        src = await self.summary(summary_id)
        if not src:
            raise Refused("요약이 없습니다")
        row = await self.session(src["session_id"])
        if not row:
            raise Refused("세션이 없습니다")
        sid, req = await self._new_summary(row, src["kind"], "edited", "ok", body=body.strip(), parent_id=summary_id,
                                           state=self._json(src.get("state")))
        if self.on_change:
            self.on_change()
        return {"summary_id": sid, "req": req, "status": "ok"}

    # ── 넣을 글 ──────────────────────────────────────────
    async def injection(self, summary_id: int, target_cwd: str | None = None, replace: bool = False,
                        confirm: bool = True) -> dict[str, Any]:
        """넣을 글. target_cwd — 받는 세션이 뜬 폴더(넣을 때). worktree면 그 사실을 맨 앞에 붙인다. 미리보기(띄우기 전)에는
        없으므로 worktree_next로 "따로 작업에서 뜰 것"만 알린다. replace — 새 세션으로 옮기기의 미리보기: 옛 세션(요약을 쓴
        세션)을 빼고 판단한다(spawn(replace=True)와 같은 판단)."""
        s = await self.summary(summary_id)
        if not s or s["status"] != "ok" or not s["body"]:
            raise Refused("넣을 수 있는 요약이 아닙니다(저장이 끝난 요약만 넣습니다)")
        row = await self.session(s["session_id"])
        src = f"{(row.cc or '')[:8]}" + (f"({row.title})" if row and row.title else "")
        full = HANDOFF_DIR / f"{s['req']}.md"
        body, cut = fit_body(s["body"], MAX_INJECT, str(full))
        # 인계 검증(11-06) — 만들 때 상태와 지금을 비교해 "인계 뒤 바뀐 것"을 본문 앞에 붙인다(미리보기 · 넣기 같은 글)
        state = self._json(s.get("state"))
        try:
            dr = await hs.drift(state, row.project if row else None, self.schema,
                                [p.path for p in ptr.parse(s["body"]) if p.path] if ptr.is_v2(s["body"]) else None)
        except Exception as e:  # noqa: BLE001 — 비교 실패를 숨기지 않는다: 그 사실을 줄로 붙인다
            log.warning("인계 비교 실패 summary=%s: %s", summary_id, type(e).__name__)
            dr = [f"인계 뒤 바뀐 것을 확인하지 못했습니다({type(e).__name__}) — 지금 상태를 직접 확인하라."]
        if state is None:
            dr = ["이 인계에는 만들 때의 상태 기록이 없습니다(11-06 이전 인계) — 「지금 상태」가 맞는지 git · 잠금으로 직접 확인하라."]
        # 11-11 아홉 — 새로 띄우기 · 옮기기는 요약을 쓴 세션의 역할로 뜬다(spawn). 관리자면 원본 폴더 · 이미 있으면 거절을 미리 알린다
        role = await self._role(row.id) if (target_cwd is None and row and self.engine is not None) else None
        ex = row.cc if (replace and row) else None
        out = {"summary_id": summary_id, "text": inject_prompt(s["req"], src, wt_block(target_cwd) + hs.block(dr) + body, confirm), "cut": cut,
               "full_path": str(full) if cut else None, "chars": len(s["body"]), "v2": ptr.is_v2(s["body"]),
               "pointers": [], "blocked": None, "state": state, "drift": dr, "role": role,
               "worktree_next": target_cwd is None and bool(row and row.cwd) and self.will_worktree(
                   wt.split(row.cwd)[0], ex, role),
               # 띄울 때 거절될 까닭(넣기 자체는 막지 않는다 — 넣을 때는 새 관리자가 이미 살아 있다)
               "manager_block": (await self.manager_conflict(wt.split(row.cwd)[0], ex)
                                 if role == "manager" and row and row.cwd else None)}
        if out["v2"]:
            # 2판 — 읽을 곳을 기계로 확인한다. 틀린 곳(없는 파일 · 줄 · 절)이 있으면 넣지 않는다(요약을 고치면 된다)
            # 11-09 기준은 새 세션이 시작할 원본 폴더(새 worktree도 base 브랜치에서 갈라진다). 전에는 요약을 쓴 세션의 폴더였다 —
            # 그 worktree가 main보다 뒤처지면 main에는 있는 절을 "찾지 못했다"고 막았다(런슈즈). 쓴 worktree에만 있으면 그 까닭을 붙인다
            src = await repo_root(row.cwd if row else None)
            base = wt.split(src)[0] if src else None
            ps = await ptr.check(ptr.parse(s["body"]), base or "", other=src,
                                 other_note="원본 폴더에는 아직 없고 요약을 쓴 작업방에만 있습니다(합친 뒤 넣습니다)")
            out["pointers"] = ptr.as_dicts(ps)
            bad = [p for p in ps if not p.ok]
            if not ps:
                out["blocked"] = "「읽을 곳」이 비었습니다. 요약을 고쳐 읽을 곳을 넣어 주세요"
            elif bad:
                out["blocked"] = "읽을 곳이 틀렸습니다. " +"; ".join(f"{p.path or p.raw}: {p.problem}" for p in bad)
        return out

    async def ensure_injectable(self, summary_id: int, target_cwd: str | None = None, confirm: bool = True) -> dict[str, Any]:
        inj = await self.injection(summary_id, target_cwd, confirm=confirm)
        if inj["blocked"]:
            raise Refused(inj["blocked"])
        return inj

    async def handoff_reads(self, row: SessionRow) -> dict[str, Any] | None:
        """이 세션이 2판 인계를 받고 시작했으면 — 「읽을 곳」을 실제로 Read했나(도구 이벤트로 맞댄다)."""
        if not row.cc:
            return None
        async with self.engine.connect() as c:
            s = (await c.execute(text(
                "SELECT id, body, drift FROM summary WHERE injected_cc_session = :c ORDER BY injected_at DESC LIMIT 1"),
                {"c": row.cc})).first()
            if not s or not ptr.is_v2(s[1]):
                return None
            targets = [r[0] for r in (await c.execute(text(
                "SELECT target FROM event WHERE session_id = :i AND type = 'tool_use' AND tool = 'Read'"),
                {"i": row.id})).all()]
        repo = await repo_root(row.cwd)
        # 11-09 받은 세션이 실제로 보는 폴더 기준으로 읽을 곳을 확인한다 — 틀린 곳은 읽음에서 뺀다. 그 세션이 worktree인데
        # 거기 없고 원본(main)에는 있으면 "뒤처졌다"고 알린다(런슈즈: worktree가 main보다 뒤처져 절이 없었다)
        base = wt.split(repo)[0] if repo else None
        note = None
        if repo and base and os.path.realpath(base) != os.path.realpath(repo):
            bb = await wt.base_branch(base)
            n = await ptr._git(repo, "rev-list", "--count", f"HEAD..{bb}")
            note = (f"이 작업방이 {bb}보다 커밋 {n}개 뒤처졌습니다({bb}에는 있습니다). fast-forward하면 읽을 수 있습니다"
                    if n.isdigit() and int(n) else f"{bb}에는 있습니다")
        ps = await ptr.check(ptr.parse(s[1]), repo or "", other=base, other_note=note)
        # drift — 넣을 때 붙인 "인계 뒤 바뀐 것"(11-06). 받은 세션 패널에 보인다
        return {"summary_id": s[0], "drift": self._json(s[2]) or []} | ptr.reads(ps, repo or "", targets)

    async def resend_reads(self, row: SessionRow) -> dict[str, Any]:
        """안 읽은 곳만 다시 — 그 세션에 "아직 읽지 않은 곳"을 보낸다."""
        r = await self.handoff_reads(row)
        if not r or not r["missing"]:
            raise Refused("다시 보낼 곳이 없습니다(읽을 곳이 있는 요약을 받은 세션이 아니거나 모두 읽었습니다)")
        msg = ("[FOREMAN 인계] 「읽을 곳」 중 아직 읽지 않은 곳이 있다. 지금 Read로 읽고, 각각 이 일에 걸리는 규칙 · 결정을 "
               "2줄씩 말해라:\n" + "\n".join(f"- `{p}`" for p in r["missing"]))
        res = await deliver(row.cc or "", msg, sessions_dir=self.sessions_dir,
                            transcript=row.transcript or transcript_path(row.cwd or "", row.cc or ""))
        return {"delivered": bool(res.get("delivered")), "queued": res.get("queued"), "missing": r["missing"]}

    def _write_full(self, req: str, body: str) -> None:
        HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
        p = HANDOFF_DIR / f"{req}.md"
        p.write_text(body + "\n", encoding="utf-8")
        p.chmod(0o600)

    async def inject(self, summary_id: int, cc_session_id: str, cwd: str, note: str | None = None) -> dict[str, Any]:
        inj = await self.ensure_injectable(summary_id, cwd)
        s = await self.summary(summary_id)
        if inj["cut"]:
            self._write_full(s["req"], s["body"])
        res = await deliver(cc_session_id, inj["text"] + note_block(note), sessions_dir=self.sessions_dir,
                            transcript=transcript_path(cwd, cc_session_id), verify_s=15.0)
        if res.get("delivered"):
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE summary SET injected_cc_session = :c, injected_at = NOW(3), drift = :d WHERE id = :i"),
                                {"c": cc_session_id, "i": summary_id, "d": json.dumps(inj["drift"], ensure_ascii=False)})
        return {"delivered": bool(res.get("delivered")), "queued": res.get("queued"), "cut": inj["cut"], "drift": inj["drift"]}

    # ── 새로 띄우기 ──────────────────────────────────────
    async def spawn(self, row: SessionRow, summary_id: int | None, replace: bool = False, note: str | None = None) -> dict[str, Any]:
        """세션 패널의 [새로 띄우기] — 그 세션과 같은 폴더 · 역할 · 모델로(모델은 띄울 때 고른 것, 없으면 역할 기본값).
        replace — 새 세션으로 옮기기(옛 세션을 곧 끝낸다). worktree를 판단할 때 옛 세션을 세지 않는다(11-09).
        note — [덧붙여서 보내기]로 사람이 쓴 말. 인계 글 끝에 붙는다(요약이 있을 때만)."""
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT role, model FROM character_session WHERE id = :i"), {"i": row.id})).first()
        role, model = (r[0], r[1]) if r else (None, None)
        # worktree 세션이면 원본 저장소 기준으로(같은 worktree에 둘이 붙지 않게 — 살아 있는 세션이 있으니 새 worktree가 된다)
        return await self.spawn_new(wt.split(row.cwd or "")[0] if row.cwd else "", summary_id, None, src_session=row.id,
                                    role=role if role in ROLE_KO else None, model=model,
                                    exclude_cc=row.cc if replace else None, note=note)

    async def spawn_new(self, cwd: str, summary_id: int | None, title: str | None,
                        src_session: int | None = None, first_prompt: str | None = None,
                        read_only: bool = False, role: str | None = None, worktree: bool | None = None,
                        model: str | None = None, exclude_cc: str | None = None, note: str | None = None,
                        scribe_task: str | None = None) -> dict[str, Any]:
        """+ 버튼 · [새로 띄우기] — tmux 세션을 만들고 그 안에서 claude(resume 아님). 세션 행을 바로 만들어(이름도) 첫 입력 전에도
        화면에 캐릭터가 선다. 인계 요약을 고르면 입력 칸이 뜬 뒤 넣는다. 폴더 신뢰 창이 뜨면 사람이 터미널에서 답할 때까지
        뒤에서 기다렸다가(5분) 이어 한다.
        worktree — None이면 그 프로젝트에 살아 있는 세션이 있을 때만 따로 작업 자리(git worktree)에서 띄운다(11-05). True · False는 강제.
        model — config/models.toml의 id. 없으면 역할 기본값, 그것도 없으면 CC 설정(--model 없이).
        exclude_cc — worktree=None 판단에서 세지 않을 세션(옮기기의 옛 세션).
        scribe_task — 역할 scribe면 무슨 서기 일인지(session_action scribe-task의 detail, 「일 토픽」). 띄우는 길이 셋(서기실 [시키기],
        계획 [시작], 직접 띄우기)이어도 여기 한 곳에서 남겨 서기실 열린 일 · 겹침 막기가 모두를 본다(11-15). 없으면 옮기기는 옛 세션의 것,
        아니면 plan."""
        cwd = os.path.realpath(os.path.expanduser(cwd or ""))
        if not cwd or not Path(cwd).is_dir():
            raise Refused(f"폴더가 없습니다: {cwd}")
        if model and not self.models.valid(model):
            raise Refused(f"고를 수 없는 모델입니다: {model}")
        model = self.models.pick(model, role)
        if role == "manager":
            # 11-11 아홉 — 관리자는 늘 원본 폴더. 전에는 살아 있는 세션만 보고 worktree로 보냈다(관리자가 .worktrees/에 떴다).
            # 아무것도 만들기 전(tmux · worktree)에 거절한다
            if worktree or wt.split(cwd)[1] is not None:
                raise Refused("관리자는 원본 폴더에서만 띄웁니다. 작업방을 끄고 저장소 맨 위 폴더에서 띄워 주세요")
            if why := await self.manager_conflict(cwd, exclude_cc):
                raise Refused(why)
            worktree = False
        if summary_id is not None:
            await self.ensure_injectable(summary_id)      # 넣을 수 있는 요약인지 먼저(안 되면 띄우지도 않는다 — 2판은 읽을 곳 확인까지)
        project = self.project_of(cwd)[0] if self.project_of else None
        base = "cc-" + (re.sub(r"[^a-z0-9]+", "-", (project or Path(cwd).name or "session").lower()).strip("-") or "session")
        existing = set((await tmux(self.socket, "list-sessions", "-F", "#{session_name}")).split())
        name, n = base, 2
        while name in existing:
            name, n = f"{base}-{n}", n + 1
        wt_info = None
        if worktree is None:
            worktree = self.will_worktree(cwd, exclude_cc, role)
        if worktree:
            if wt.split(cwd)[1] is not None or not await wt.is_repo(cwd):
                raise Refused("작업방은 저장소 맨 위 폴더에서만 띄울 수 있습니다")
            wt_info = await wt.create(cwd, name.removeprefix("cc-"))
            cwd = wt_info["path"]
        await tmux(self.socket, "new-session", "-d", "-s", name, "-c", cwd)
        pane = (await tmux(self.socket, "display-message", "-p", "-t", name, "#{pane_id}")).strip()
        # 읽기 전용(포먼이 "살펴보기만"으로 정한 일 · 자동 기상) — CC plan 모드: 읽기 · 조사만, 고치기 전에 사람 승인
        await tmux(self.socket, "send-keys", "-t", pane, "-l", self.claude_bin + (f" --model {model}" if model else "")
                   + (" --permission-mode plan" if read_only else ""))
        await tmux(self.socket, "send-keys", "-t", pane, "Enter")
        out: dict[str, Any] = {"tmux": name, "pane": pane, "cwd": cwd, "project": project, "cc_session_id": None,
                               "pid": None, "session_id": None, "note": None, "injected": False, "worktree": wt_info,
                               "model": model}
        extra = {"first_prompt": first_prompt, "role": role, "worktree_path": wt_info["path"] if wt_info else None,
                 "model": model, "note": note, "scribe_task": scribe_task}
        cc, pid, trust = await self._wait_ready(pane, 45)
        if trust:
            out["note"] = "처음 쓰는 폴더라 신뢰 확인 창이 떴습니다. 터미널(tmux " + name + ")에서 답하면 이어서 " + ("첫 글을 넣습니다." if (summary_id or first_prompt) else "화면에 뜹니다.")
            self._spawn_task(self._finish_spawn(name, pane, cwd, summary_id, title, src_session, wait=300, **extra))
            await self._act(src_session, "spawn", None, True, f"{name} {pane} 신뢰 창 대기")
            return out
        if cc is None:
            await self._act(src_session, "spawn", None, False, f"{name} {pane} CC를 못 찾음")
            out["note"] = "45초 안에 새 세션을 찾지 못했습니다. 대화창에서 확인해 주세요."
            return out
        return out | await self._finish_spawn(name, pane, cwd, summary_id, title, src_session, cc=cc, pid=pid, **extra)

    def will_worktree(self, cwd: str, exclude_cc: str | None = None, role: str | None = None) -> bool:
        """spawn_new(worktree=None)이 따로 작업 자리로 보낼까 — 그 프로젝트에 살아 있는 세션이 있으면.
        exclude_cc — 세지 않을 세션(새 세션으로 옮기기의 옛 세션: 곧 끝나니 하나 더 생기는 게 아니다, 11-09).
        role — 관리자(manager)는 늘 원본 폴더라 False(11-11 아홉). 코더 · 서기 · 디자이너 등은 위 규칙."""
        if role == "manager" or not self.project_of or not cwd:
            return False
        project = self.project_of(cwd)[0]
        return bool(project) and wt.split(cwd)[1] is None and any(
            self.project_of(ls.cwd)[0] == project
            for cc, ls in live_sessions(self.sessions_dir).items() if not (exclude_cc and cc == exclude_cc))

    def _live_in_base(self, cwd: str, exclude_cc: str | None = None) -> list[str]:
        """이 저장소의 원본 폴더(.worktrees/ 밖)에서 살아 있는 CC 세션 id들. exclude_cc는 뺀다(옮기기의 옛 세션)."""
        repo = os.path.realpath(wt.split(cwd)[0]) if cwd else ""
        if not repo:
            return []
        out = []
        for cc, ls in live_sessions(self.sessions_dir).items():
            if (exclude_cc and cc == exclude_cc) or not ls.cwd:
                continue
            p = os.path.realpath(ls.cwd)
            if wt.split(p)[1] is None and (p == repo or p.startswith(repo + os.sep)):
                out.append(cc)
        return out

    async def manager_conflict(self, cwd: str, exclude_cc: str | None = None) -> str | None:
        """관리자를 띄우면 안 되는 까닭(11-11 아홉) — 원본 폴더에 역할 관리자인 세션이 이미 살아 있으면 그 사유, 없으면 None.
        관리자는 원본 폴더에 하나다(코드를 합치고 push하는 자리). 옮기기의 옛 세션(exclude_cc)은 곧 끝나니 세지 않는다."""
        ccs = self._live_in_base(cwd, exclude_cc)
        if not ccs or self.engine is None:
            return None
        from sqlalchemy import bindparam
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cc_session_id, id, role FROM character_session WHERE cc_session_id IN :c ORDER BY id")
                .bindparams(bindparam("c", expanding=True)), {"c": ccs})).all()
        latest = {cc: (sid, role) for cc, sid, role in rows}          # 같은 cc의 마지막 행(ORDER BY id)
        for cc, (sid, role) in latest.items():
            if role == "manager":
                return (f"원본 폴더에 관리자(세션 {sid})가 이미 살아 있습니다. 관리자는 원본 폴더에 하나입니다. "
                        "그 세션을 끝내거나, 그 세션 패널에서 [새 세션으로 옮기기]로 바꿔 주세요")
        return None

    async def _wait_ready(self, pane: str, secs: float) -> tuple[str | None, int | None, bool]:
        """(cc 세션 id, pid, 신뢰 창이 떴나). 입력 칸(❯)이 뜨고 일하지 않을 때까지."""
        cc, pid = None, None
        loop = asyncio.get_running_loop()
        end = loop.time() + secs
        while loop.time() < end:
            await asyncio.sleep(1.0)
            try:
                screen = await tmux(self.socket, "capture-pane", "-p", "-t", pane)
            except Refused:
                return None, None, False                  # pane이 사라졌다
            if re.search(r"trust (the files in )?this folder|Do you trust", screen, re.I):
                return None, None, True
            if cc is None:
                for ls in live_sessions(self.sessions_dir).values():
                    te = _tmux_env(ls.pid)
                    if te and te[1] == pane:
                        cc, pid = ls.session_id, ls.pid
                        break
            if cc and "❯" in screen and _status(self.sessions_dir, pid) != "busy":
                return cc, pid, False
        return cc, pid, False

    async def _finish_spawn(self, name: str, pane: str, cwd: str, summary_id: int | None, title: str | None,
                            src_session: int | None, cc: str | None = None, pid: int | None = None,
                            wait: float = 0, first_prompt: str | None = None, role: str | None = None,
                            worktree_path: str | None = None, model: str | None = None, note: str | None = None,
                            scribe_task: str | None = None) -> dict[str, Any]:
        if cc is None:                                    # 신뢰 창 — 사람이 답하기를 기다린다
            loop = asyncio.get_running_loop()
            end = loop.time() + wait
            while loop.time() < end and cc is None:
                cc, pid, trust = await self._wait_ready(pane, 20)
            if cc is None:
                await self._act(src_session, "spawn", None, False, f"{name} 신뢰 창에 답이 없어 그만둠")
                return {"note": "신뢰 확인 창에 답이 없어 그만뒀습니다."}
        if not (title or "").strip() and summary_id is not None:
            title = await self._inherited_title(summary_id)
        sid = await self._ensure_row(cc, cwd, title)
        ch = await self._character_for(cwd, role or "coder")
        if role or worktree_path or ch or model:
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE character_session SET role = COALESCE(:r, role), worktree_path = COALESCE(:w, worktree_path), "
                                     "character_id = COALESCE(:ch, character_id), model = COALESCE(:m, model) WHERE id = :i"),
                                {"r": role[:16] if role else None, "w": worktree_path, "ch": ch, "m": model, "i": sid})
        await self._act(src_session or sid, "spawn", pid, True, f"{name} {pane} cc={cc} 새 세션 행 {sid}")
        if role == "scribe":
            await self._act(sid, SCRIBE_TASK_ACT, pid, True, scribe_task or await self._scribe_task_of(src_session) or "plan")
        if self.on_change:
            self.on_change()
        out: dict[str, Any] = {"cc_session_id": cc, "pid": pid, "session_id": sid}
        if first_prompt:
            # 포먼이 쓴 첫 글(+ 고른 인계 요약) — 사람이 계획 카드에서 확인 · 고친 글 그대로
            body = first_prompt
            if summary_id is not None:
                inj = await self.ensure_injectable(summary_id, cwd, confirm=False)   # 계획 카드에서 이미 봤다(11-10)
                s = await self.summary(summary_id)
                if inj["cut"]:
                    self._write_full(s["req"], s["body"])
                body += "\n\n" + inj["text"]
                async with self.engine.begin() as c:
                    await c.execute(text("UPDATE summary SET injected_cc_session = :c, injected_at = NOW(3) WHERE id = :i"),
                                    {"c": cc, "i": summary_id})
            await asyncio.sleep(1.0)
            r = await deliver(cc, body, sessions_dir=self.sessions_dir, transcript=transcript_path(cwd, cc), verify_s=15.0)
            out["injected"] = bool(r.get("delivered"))
            if not out["injected"]:
                out["note"] = "첫 글을 보냈지만 제출을 확인하지 못했습니다. 입력 칸을 확인해 주세요."
            return out
        if summary_id is not None:
            await asyncio.sleep(1.0)
            r = await self.inject(summary_id, cc, cwd, note)
            out["injected"] = r["delivered"]
            if not r["delivered"]:
                out["note"] = "인계 글을 보냈지만 제출을 확인하지 못했습니다. 입력 칸을 확인해 주세요."
            else:
                row = await self.session(sid)
                if row:
                    self._notify(row, f"새 세션에 인계 넣음 — {name} (세션 {cc[:8]})")
        return out

    async def _character_for(self, cwd: str, role: str) -> int | None:
        """이 세션을 붙일 캐릭터(11-05 재배치, README 2.3 · 2.4 · 3.4) — 포먼이 채용한다(부모 = 그 프로젝트의 포먼).
        원본 폴더면 역할 캐릭터("코더" · "조사" · "서기"), worktree면 그 자리의 일꾼("코더 foreman-2" — 합치기 · 버리기 때 퇴장).
        같은 이름이 퇴장해 있으면 되살린다(이름은 프로젝트 안에서 고유). 프로젝트 밖(떠돌이)은 그대로 둔다."""
        name0 = ROLE_KO.get(role)
        if not name0 or not self.project_of:
            return None
        project = self.project_of(cwd)[0]
        if not project:
            return None
        wt_name = wt.split(cwd)[1]
        name = f"{name0} {wt_name}" if wt_name else name0
        async with self.engine.begin() as c:
            f = (await c.execute(text("SELECT ch.id, ch.project_id FROM `character` ch JOIN project p ON p.id = ch.project_id "
                                      "WHERE p.name = :p AND ch.current_role = 'foreman' LIMIT 1"), {"p": project})).first()
            if not f:
                return None
            r = (await c.execute(text("SELECT id FROM `character` WHERE project_id = :pid AND name = :n"),
                                 {"pid": f[1], "n": name})).first()
            if not r and role in ROLE_OLD_KO:
                # 화면 이름을 바꾼 역할(11-15 점검 → 조사) — 옛 이름 캐릭터가 있으면 새 이름으로 바꿔 이어 쓴다(마이그레이션 없이, 쓸 때)
                old = f"{ROLE_OLD_KO[role]} {wt_name}" if wt_name else ROLE_OLD_KO[role]
                r = (await c.execute(text("SELECT id FROM `character` WHERE project_id = :pid AND name = :n"),
                                     {"pid": f[1], "n": old})).first()
                if r:
                    await c.execute(text("UPDATE `character` SET name = :n WHERE id = :i"), {"n": name, "i": r[0]})
            if r:
                await c.execute(text("UPDATE `character` SET retired_at = NULL, current_role = :r WHERE id = :i"), {"r": role, "i": r[0]})
                return r[0]
            res = await c.execute(text("INSERT INTO `character` (project_id, parent_id, name, current_role, status, kind, spawned_by) "
                                       "VALUES (:pid, :f, :n, :r, 'DORMANT', 'agent', 'foreman')"),
                                  {"pid": f[1], "f": f[0], "n": name, "r": role})
            return res.lastrowid

    async def _retire_wt_characters(self, row: SessionRow, wt_name: str) -> None:
        """worktree를 합치거나 버리면 그 자리의 일꾼은 퇴장(세션 이력은 남는다)."""
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE `character` ch JOIN project p ON p.id = ch.project_id SET ch.retired_at = NOW(3) "
                                 "WHERE p.name = :p AND ch.name LIKE :n AND ch.retired_at IS NULL"),
                            {"p": row.project, "n": f"% {wt_name}"})

    async def _inherited_title(self, summary_id: int) -> str | None:
        """인계로 띄운 새 세션은 원 세션에 사람이 붙인 이름을 물려받는다(11-06 — 인계 · 새 세션마다 행이 새로 생겨
        이름이 자동 제목으로 "돌아간" 것처럼 보였다). 이름을 따로 주면 그것이 이긴다."""
        async with self.engine.connect() as c:
            return (await c.execute(text(
                "SELECT cs.custom_title FROM summary s JOIN character_session cs ON cs.id = s.session_id WHERE s.id = :i"),
                {"i": summary_id})).scalar()

    async def _ensure_row(self, cc: str, cwd: str, title: str | None) -> int:
        """새 CC 세션의 행 — 첫 줄이 기록되기 전에 만들어 둔다(조립기는 같은 cc_session_id 행을 이어 쓴다)."""
        char = self.project_of(cwd)[1] if self.project_of else None
        async with self.engine.begin() as c:
            r = (await c.execute(text("SELECT id FROM character_session WHERE cc_session_id = :c ORDER BY id DESC LIMIT 1"),
                                 {"c": cc})).first()
            if r:
                if title:
                    await c.execute(text("UPDATE character_session SET custom_title = :t WHERE id = :i"), {"t": title, "i": r[0]})
                return r[0]
            if char is None:
                char = (await c.execute(text("SELECT id FROM `character` WHERE project_id IS NULL ORDER BY id LIMIT 1"))).scalar()
            res = await c.execute(text(
                "INSERT INTO character_session (character_id, type, role, cc_session_id, cwd, wake_reason, attached_at, custom_title) "
                "VALUES (:ch, 'agent', 'coder', :c, :cwd, 'user', NOW(3), :t)"),
                {"ch": char, "c": cc, "cwd": cwd, "t": (title or "").strip() or None})
            return res.lastrowid

    # ── 세션 조작 ────────────────────────────────────────
    async def action(self, row: SessionRow, act: str) -> dict[str, Any]:
        if not row.cc:
            raise Refused("CC 세션 ID가 없습니다")
        if act == "resume":
            return await self._resume(row)
        t, ls, busy = await resolve(row.cc, self.sessions_dir)
        if act == "interrupt":
            if not busy:
                raise Refused("작업 중이 아니라 중단할 작업이 없습니다")
            await tmux(t.socket, "send-keys", "-t", t.pane, "Escape")
            await self._act(row.id, "interrupt", ls.pid, True, t.pane)
            return {"ok": True, "pane": t.pane}
        if busy:
            raise Refused("작업 중입니다. 작업이 끝난 뒤에 하거나 먼저 [작업 중단]을 눌러 주세요")
        if act == "exit":
            tname = (await tmux(t.socket, "display-message", "-p", "-t", t.pane, "#{session_name}")).strip()
            # 11-08 — /usage · 설정 같은 화면이 떠 있으면 입력 줄(❯)이 없어 /exit를 못 받는다(세션 210, 끝내기가 안 됐다).
            # 11-09부터 deliver가 Esc(최대 3번)로 닫고 보낸다(inject.clear_screen — 모든 보내기에 같게). 작업 중이 아닐 때만 여기 온다.
            # 11-13부터 Esc가 결정이 되는 창(신뢰 · 권한 · 끝내기 확인)이나 모르는 창이면 Esc 없이 거부한다
            res = await deliver(row.cc, "/exit", sessions_dir=self.sessions_dir, transcript=None, command=True)
            # 11-08 15 → 45초 — 맥락 520k 세션(200)이 /exit 뒤 15초 안에 내려가지 않아 "실패"로 보였고, 다시 누르자 끝났다
            gone = await self._wait(lambda: row.cc not in live_sessions(self.sessions_dir), 45)
            cleaned = await self._cleanup_tmux(row.id, t, tname) if gone else False
            if gone:
                await self._stop_preview(row)             # 세션을 끝내면 미리보기도(다시 보려면 [미리보기 열기])
            await self._act(row.id, "exit", ls.pid, gone, f"{t.pane} {tname} steps={','.join(res['steps'])}{' tmux 정리' if cleaned else ''}")
            return {"ok": gone, "pane": t.pane, "tmux_closed": cleaned,
                    "note": None if gone else "45초 안에 끝나지 않았습니다. 대화창을 확인해 주세요."}
        if act == "stop":
            await tmux(t.socket, "send-keys", "-t", t.pane, "C-z")
            stopped = await self._wait(lambda: (_proc_stat(ls.pid) or ("?",))[0] == "T", 5)
            await self._act(row.id, "stop", ls.pid, stopped, t.pane)
            return {"ok": stopped, "pane": t.pane, "note": None if stopped else "5초 안에 멈추지 않았습니다."}
        raise Refused(f"모르는 조작입니다: {act}")

    async def _cleanup_tmux(self, sid: int, t: Any, tname: str) -> bool:
        """끝낸 세션의 tmux 세션도 닫는다(11-05) — FOREMAN이 띄운 것만(session_action spawn 기록에 그 이름), 그리고 pane에
        claude가 아니라 셸만 남았을 때. 사람이 만든 tmux(cc-runshoes 등)는 건드리지 않는다."""
        if not tname:
            return False
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT 1 FROM session_action WHERE action = 'spawn' AND ok AND detail LIKE :d LIMIT 1"),
                {"d": tname + " %"})).first()
        if not r:
            return False
        try:
            # 세션 파일이 사라진 직후엔 claude 프로세스가 아직 내려가는 중일 수 있다(11-05 worktree 시험) — 5초까지 기다린다
            for _ in range(10):
                panes = (await tmux(t.socket, "list-panes", "-t", tname, "-F", "#{pane_current_command}")).split()
                if not any(p == "claude" for p in panes):
                    await tmux(t.socket, "kill-session", "-t", tname)
                    return True
                await asyncio.sleep(0.5)
            return False
        except Refused:
            return False

    # ── 따로 작업(worktree) 합치기 · 버리기(11-05) ──────────────
    def _wt_of(self, row: SessionRow) -> tuple[str, str]:
        repo, name = wt.split(row.cwd or "")
        if not name:
            raise Refused("작업방에서 띄운 세션이 아닙니다")
        return repo, name

    async def worktree(self, row: SessionRow) -> dict[str, Any] | None:
        if not row.cwd or not wt.split(row.cwd)[1]:
            return None
        repo, name = self._wt_of(row)
        out = await wt.status(repo, name)
        out["live"] = bool(row.cc and row.cc in live_sessions(self.sessions_dir))
        lock = (self.schema.state.get(row.project or "") if self.schema else None) or {}
        out["schema_lock"] = lock.get("wt") == name
        out["preview"] = await self.previews.get(out["path"]) if self.previews else None
        out["preview_dead"] = (self.previews.dead.get(out["path"]) if self.previews and not out["preview"] else None)   # 죽어서 기록을 치운 까닭
        out["preview_ok"] = bool(self.previews and row.project in self.previews.cmds)
        if out.get("exists") and await self._role(row.id) == "scribe":
            out["review"] = await self._scribe_review(row, repo, out)
        # 쉬게 하기(11-09) — 마지막 쉬게 하기 시각(살아 있지 않을 때만 "쉬는 중"), [이어서]를 켤지
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT created_at FROM session_action WHERE session_id = :s AND action = :a AND ok ORDER BY id DESC LIMIT 1"),
                {"s": row.id, "a": REST_ACT})).first()
        out["rested_at"] = r[0].isoformat() + "Z" if r and not out["live"] else None
        # 11-11(받은 할 일 #17) — 실제와 다른 「합치기 기다림」: 이름이 뒤 세션에 다시 쓰였거나 밖에서 이미 합침
        from bridge.coder_room import rest_stale, reused_by
        async with self.engine.connect() as c:
            out["reused_by"] = await reused_by(c, row.id, out["path"])
        out["stale"] = await rest_stale(self.engine, row.id, row.cwd) if not out["live"] else None
        out["in_base"] = bool(out.get("exists") and out.get("ahead") == 0 and not out.get("dirty"))
        if out["stale"]:
            out["rested_at"] = None
        out["resume_ok"] = bool(out.get("exists") and not out["live"] and row.cc and not out["reused_by"])
        return out

    async def _guard_reused(self, row: SessionRow, repo: str, name: str) -> None:
        """이 세션의 worktree 이름을 뒤 세션이 다시 쓰고 있으면 거부 — 지금 폴더는 뒤 세션 것이다(합치면 그 세션 일을 합친다)."""
        from bridge.coder_room import reused_by
        if self.engine is None:
            return
        async with self.engine.connect() as c:
            later = await reused_by(c, row.id, os.path.join(repo, wt.WT_DIR, name))
        if later:
            raise Refused(f"이 작업방 이름({name})은 지금 세션 {later}이 쓰고 있습니다. 이 세션의 작업방은 이미 지워졌습니다. "
                          f"세션 {later}의 패널에서 합치거나 버립니다")

    async def _role(self, sid: int) -> str | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT role FROM character_session WHERE id = :s"), {"s": sid})).first()
        return r[0] if r else None

    async def set_role(self, row: SessionRow, role: str) -> dict[str, Any]:
        """세션 역할 바꾸기(11-09) — character_session.role을 바꾸고 그 역할 캐릭터("관리자" · worktree면 "관리자 foreman-3")로
        옮긴다(새 세션 역할 캐릭터와 같은 규칙, _character_for). 프로젝트 밖 세션은 캐릭터를 그대로 둔다. session_action 'role'에 남긴다."""
        if role not in ROLE_KO:
            raise Refused(f"바꿀 수 없는 역할입니다({role}). {' · '.join(ROLE_KO.values())} 중에서 고릅니다")
        old = await self._role(row.id)
        if old == role:
            return {"id": row.id, "role": role, "changed": False}
        ch = await self._character_for(row.cwd or "", role)
        async with self.engine.begin() as c:
            await c.execute(text("UPDATE character_session SET role = :r, character_id = COALESCE(:ch, character_id) WHERE id = :i"),
                            {"r": role, "ch": ch, "i": row.id})
        await self._act(row.id, ROLE_ACT, None, True, f"{old} → {role}" + (f" 캐릭터 {ch}" if ch else ""))
        if self.on_change:
            self.on_change()
        return {"id": row.id, "role": role, "old": old, "character_id": ch, "changed": True}

    async def _scribe_review(self, row: SessionRow, repo: str, st: dict[str, Any]) -> dict[str, Any] | None:
        """서기 브랜치 검토(12b) — 근거 확인 · 고친 양. 실패해도 따로 작업 칸은 뜬다."""
        from bridge import evidence as ev
        try:
            return await ev.review(self.engine, repo, st["path"], st["base"], st["branch"], row.id)
        except Exception as e:  # noqa: BLE001
            log.warning("서기 검토 실패: %s", type(e).__name__)
            return {"error": f"검토하지 못했습니다({type(e).__name__})"}

    async def _save_review(self, row: SessionRow, branch: str, rv: dict[str, Any]) -> None:
        import json as _json
        async with self.engine.begin() as c:
            task = (await c.execute(text(
                "SELECT detail FROM session_action WHERE session_id = :s AND action = 'scribe-task' ORDER BY id DESC LIMIT 1"),
                {"s": row.id})).first()
            r = rv.get("revision") or {}
            await c.execute(text(
                "INSERT INTO scribe_review (session_id, task, branch, marks, bad, unsupported, draft_lines, revision_lines, detail) "
                "VALUES (:s, :t, :b, :m, :bad, :u, :d, :r, :x)"),
                {"s": row.id, "t": ((task[0] or "").split() or [None])[0] if task else None, "b": branch,
                 "m": rv.get("marks", 0), "bad": rv.get("bad", 0), "u": rv.get("unsupported", 0),
                 "d": r.get("draft_lines", 0), "r": r.get("revision_lines", 0),
                 "x": _json.dumps([{k: f[k] for k in ("path", "total", "bad", "unsupported")} for f in rv.get("files", [])],
                                  ensure_ascii=False)})

    async def preview(self, row: SessionRow, on: bool) -> dict[str, Any]:
        """[미리보기 열기] · [닫기] — 끝난 세션이어도 worktree가 남아 있으면 연다(합치기 전에 보려고)."""
        if not self.previews:
            raise Refused("미리보기가 꺼져 있습니다")
        repo, name = self._wt_of(row)
        path = os.path.join(repo, wt.WT_DIR, name)
        if not on:
            return {"stopped": await self.previews.stop(path)}
        return await self.previews.start(row.project, path)

    async def _stop_preview(self, row: SessionRow) -> bool:
        if not (self.previews and row.cwd):
            return False
        repo, name = wt.split(row.cwd)
        return bool(name) and await self.previews.stop(os.path.join(repo, wt.WT_DIR, name))

    async def worktree_act(self, row: SessionRow, act: str, end: bool = False, title: str | None = None) -> dict[str, Any]:
        """merge(사람 승인 — 화면의 확인 창) · discard(커밋까지 버림). 세션이 끝난 뒤에만 — 도는 세션의 바닥을 옮기지 않는다.
        end=True면 살아 있는 세션을 먼저 끝내고 이어서 한다(11-06 — 끝내기 누르고 합치기를 또 찾아 눌러야 했다).
        합치기는 끝내기 **전에** 커밋 안 된 변경을 본다 — 끝낸 뒤에 알면 그 세션에게 커밋을 시킬 수 없다.
        title(11-13) — squash 커밋 제목을 사람 · 관리자가 정할 때. 그 저장소 꼴이 아니면 끝내기 전에 거부. 안 넘기면 세션 제목으로 기계가 만든다."""
        repo, name = self._wt_of(row)
        await self._guard_reused(row, repo, name)
        if act == "merge" and title is not None:
            st_t = await wt.status(repo, name)
            if st_t.get("exists"):
                title = await wt.check_title_for(repo, st_t["base"], title)
        ended = None
        if row.cc and row.cc in live_sessions(self.sessions_dir):
            if not end:
                raise Refused("세션이 아직 살아 있습니다. [끝내기 ▾]의 [합치고 끝내기]로 끝내면서 합칠 수 있습니다. 버리려면 세션을 끝낸 뒤 「브랜치 이름」 칸의 [버리기]를 누릅니다")
            if act == "merge":
                st = await wt.status(repo, name)
                if st.get("dirty"):
                    files = ", ".join(st["dirty"][:8]) + (" …" if len(st["dirty"]) > 8 else "")
                    raise Refused(f"커밋 안 된 변경이 {len(st['dirty'])}개 있습니다({files}). 세션에게 커밋을 시킨 뒤 다시 눌러 주세요."
                                  " 세션은 끝내지 않았습니다")
            r = await self.action(row, "exit")
            if not r.get("ok"):
                raise Refused("세션이 끝나지 않아 멈췄습니다. " +(r.get("note") or "대화창을 확인해 주세요"))
            ended = {"tmux_closed": r.get("tmux_closed")}
        rv = None
        if act == "merge" and await self._role(row.id) == "scribe":   # 합치면 브랜치가 지워진다 — 검토는 먼저(12b)
            st0 = await wt.status(repo, name)
            if st0.get("exists"):
                rv = await self._scribe_review(row, repo, st0)
        if act == "merge":
            res = await wt.merge(repo, name, title=title, topic=row.title, sid=row.id)
        elif act == "discard":
            await wt.remove(repo, name, force=True)
            res = {"ok": True, "note": "작업방과 브랜치를 지웠습니다(커밋 안 된 변경 · 합치지 않은 커밋도 함께)."}
        else:
            raise Refused(f"모르는 조작입니다: {act}")
        if ended is not None:
            res["ended"] = ended
        if rv and res.get("ok") and not rv.get("error"):
            try:
                await self._save_review(row, f"cc/{name}", rv)
                res["review"] = {k: rv[k] for k in ("marks", "bad", "unsupported", "revision")}
            except Exception as e:  # noqa: BLE001 — 기록 실패가 합치기를 되돌리지 않는다
                log.warning("서기 검토 기록 실패: %s", type(e).__name__)
        if res.get("ok") and self.schema and row.project:
            res["schema_unlocked"] = self.schema.release(row.project, name)
        if res.get("ok"):
            res["preview_stopped"] = await self._stop_preview(row)
            if row.project:
                await self._retire_wt_characters(row, name)
            if self.mergeprep is not None:                # 합치기 막대 · 말풍선이 1분 훑기를 기다리지 않게(11-11)
                self.mergeprep.worktree_gone(row.id)
        await self._act(row.id, f"wt-{act}", None, bool(res.get("ok")),
                        f"{name} {res.get('note') or ''} {','.join(res.get('conflict') or [])}"[:500])
        if self.on_change:
            self.on_change()
        return res

    # ── 쉬게 하기 · 이어서(11-09, log/coder_resident_20261109.md) ──────────────
    # 쉬게 하기 = 지금까지를 이 브랜치에 커밋 → 세션만 /exit, worktree는 남긴다. 캐릭터는 자리로 돌아가 "합치기 기다림".
    # 이어서 = 같은 worktree에서 그 CC 세션을 --resume으로 다시 붙인다(같은 일의 맥락을 잇는다). 새 일은 새 세션이다.
    # 실패(커밋 · 뒤에서 도는 일 · 끝내기 확인 창 · resume)는 모두 화면에 까닭으로 돌려준다 — 조용히 넘어가지 않는다
    async def _running_work(self, row: SessionRow, pid: int | None) -> list[str]:
        """뒤에서 도는 일 — 백그라운드 Bash · Monitor(끝 알림 없음, 이 CC 프로세스가 뜬 뒤 시작) · 도는 서브에이전트.
        대시보드 「뒤에서 도는 일」과 같은 기준(bridge/api/dashboard.py background_running). 이것이 있으면 /exit가 CC 확인 창에 걸린다
        (log/old_session_exit_bg_20261109.md)."""
        from datetime import UTC, datetime, timedelta
        started = None
        if pid:
            try:
                ms = json.loads(Path(self.sessions_dir, f"{pid}.json").read_text(encoding="utf-8")).get("startedAt")
                if isinstance(ms, (int, float)):
                    started = datetime.fromtimestamp(ms / 1000, UTC).replace(tzinfo=None)
            except (OSError, ValueError):
                pass
        async with self.engine.connect() as c:
            bg = (await c.execute(text(
                "SELECT s.tool, JSON_UNQUOTE(JSON_EXTRACT(s.payload, '$.description')), s.ts FROM event s "
                "WHERE s.session_id = :s AND s.type = 'bg_start' AND s.ts > :cut AND NOT EXISTS (SELECT 1 FROM event e "
                "WHERE e.session_id = s.session_id AND e.type = 'bg_end' AND e.target = s.target) ORDER BY s.ts"),
                {"s": row.id, "cut": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)})).all()
            subs = (await c.execute(text("SELECT description FROM subagent_run WHERE session_id = :s AND status = 'running'"),
                                    {"s": row.id})).all()
        out = [f"{tool or '셸'}{f': {desc}' if desc and desc != 'null' else ''}"
               for tool, desc, ts in bg if not (started and ts and ts < started)]
        out += [f"서브에이전트{f': {d}' if d else ''}" for (d,) in subs]
        return out

    async def _exit_blocker(self, pane: str) -> str | None:
        """/exit 뒤 안 내려갔을 때 그 까닭 — CC 끝내기 확인 창이 떠 있으면 그렇다고."""
        try:
            screen = await tmux(self.socket, "capture-pane", "-p", "-t", pane)
        except Refused:
            return None
        if re.search(r"Background work is running|will stop when you exit|Exit and stop tasks", screen):
            return "CC 끝내기 확인 창에 걸렸습니다(뒤에서 도는 일이 있어 CC가 묻고 기다립니다)"
        return None

    async def rest(self, row: SessionRow) -> dict[str, Any]:
        """[쉬게 하기] — 커밋(커밋 안 한 변경이 있으면) → 세션만 끝냄 → worktree는 남김. session_action 'rest'에 남긴다."""
        repo, name = self._wt_of(row)
        if not row.cc or row.cc not in live_sessions(self.sessions_dir):
            raise Refused("이미 끝난 세션입니다. 「브랜치 이름」 칸에서 [이어서], [합치기], [버리기]를 고릅니다")
        t, ls, busy = await resolve(row.cc, self.sessions_dir)
        if busy:
            raise Refused("작업 중입니다. 작업이 끝난 뒤에 쉬게 해 주세요. 세션은 그대로입니다")
        bg = await self._running_work(row, ls.pid)
        if bg:
            raise Refused(f"뒤에서 도는 일이 {len(bg)}개 있습니다({'; '.join(bg[:3])}{' …' if len(bg) > 3 else ''}). 지금 끝내면 CC가 "
                          "끝내기 확인 창에서 멈춥니다. 그 일이 끝난 뒤에 쉬게 해 주세요. 커밋도 하지 않았습니다")
        title = (row.title or "").strip() or f"세션 {row.id}"
        path = os.path.join(repo, wt.WT_DIR, name)
        try:
            saved = await wt.save_progress(path, f"쉬게 하기: 진행 중 저장 — {title}"[:200])
        except Refused as e:
            await self._act(row.id, REST_ACT, ls.pid, False, f"{name} 커밋 실패: {e}")
            raise
        saved_txt = (f"커밋 {saved['commit']}(파일 {saved['files']}개)" if saved["commit"] else "커밋할 변경 없음") + (
            f" · 넣지 않은 것 {len(saved['skipped'])}개({', '.join(saved['skipped'][:4])})" if saved["skipped"] else "")
        r = await self.action(row, "exit")
        if not r.get("ok"):
            why = await self._exit_blocker(t.pane) or r.get("note") or "45초 안에 끝나지 않았습니다"
            await self._act(row.id, REST_ACT, ls.pid, False, f"{name} {saved_txt} 끝내기 실패: {why}")
            if self.on_change:
                self.on_change()
            return {"ok": False, "commit": saved["commit"], "skipped": saved["skipped"],
                    "note": f"{saved_txt}까지 했지만 세션이 끝나지 않았습니다({why}). 터미널(tmux)에서 확인해 주세요."}
        await self._act(row.id, REST_ACT, ls.pid, True, f"{name} {saved_txt}")
        if self.on_change:
            self.on_change()
        return {"ok": True, "commit": saved["commit"], "files": saved["files"], "skipped": saved["skipped"],
                "tmux_closed": r.get("tmux_closed"),
                "note": f"쉬게 했습니다({saved_txt}). 작업방 {wt.BRANCH_PREFIX}{name}는 남아 있습니다. [이어서] · [합치기] · [버리기]로 이어 갑니다."}

    async def rest_resume(self, row: SessionRow) -> dict[str, Any]:
        """[이어서] — 같은 worktree에서 그 CC 세션을 `claude --resume`으로 다시 붙인다. 새 tmux 창에서."""
        repo, name = self._wt_of(row)
        await self._guard_reused(row, repo, name)
        path = os.path.join(repo, wt.WT_DIR, name)
        if not Path(path).is_dir():
            raise Refused("작업방이 없습니다. 이미 합쳤거나 버렸습니다")
        if not row.cc:
            raise Refused("CC 세션 ID가 없어 이어 붙일 수 없습니다")
        if row.cc in live_sessions(self.sessions_dir):
            raise Refused("이미 살아 있는 세션입니다. 패널에서 그대로 이어 쓰면 됩니다")
        cwd = row.cwd if row.cwd and Path(row.cwd).is_dir() else path
        if not Path(transcript_path(cwd, row.cc)).is_file():
            raise Refused("이 세션의 대화 기록 파일을 찾지 못해 이어 붙일 수 없습니다. 새 세션으로 띄워 주세요")
        async with self.engine.connect() as c:
            model = (await c.execute(text("SELECT model FROM character_session WHERE id = :i"), {"i": row.id})).scalar()
        model = self.models.resolve(model)          # 11-14 전 값(opus 등 별칭)은 목록의 id로, 모르는 값은 None(CC 설정)
        base = "cc-" + (re.sub(r"[^a-z0-9]+", "-", (row.project or "session").lower()).strip("-") or "session")
        existing = set((await tmux(self.socket, "list-sessions", "-F", "#{session_name}")).split())
        tname, n = base, 2
        while tname in existing:
            tname, n = f"{base}-{n}", n + 1
        await tmux(self.socket, "new-session", "-d", "-s", tname, "-c", cwd)
        pane = (await tmux(self.socket, "display-message", "-p", "-t", tname, "#{pane_id}")).strip()
        await tmux(self.socket, "send-keys", "-t", pane, "-l", f"{self.claude_bin} --resume {row.cc}" + (f" --model {model}" if model else ""))
        await tmux(self.socket, "send-keys", "-t", pane, "Enter")
        cc, pid, trust = await self._wait_ready(pane, 45)
        if cc is None:
            why = "폴더 신뢰 확인 창이 떴습니다" if trust else "45초 안에 이어 붙은 세션을 찾지 못했습니다"
            await self._act(row.id, REST_RESUME_ACT, None, False, f"{tname} {pane} {why}")
            return {"ok": False, "tmux": tname, "note": f"{why}. 터미널(tmux {tname})에서 확인해 주세요."}
        sid = row.id
        if cc != row.cc:
            # CC가 다른 id로 이었으면 새 행에 이름 · 역할 · 자리를 물려준다(같은 캐릭터)
            sid = await self._ensure_row(cc, cwd, row.title)
            async with self.engine.begin() as c:
                await c.execute(text(
                    "UPDATE character_session n JOIN character_session o ON o.id = :o SET n.role = o.role, "
                    "n.worktree_path = o.worktree_path, n.character_id = o.character_id, n.model = o.model, "
                    "n.custom_title = COALESCE(n.custom_title, o.custom_title) WHERE n.id = :n"), {"o": row.id, "n": sid})
        # tmux 정리(_cleanup_tmux)는 'spawn' 기록으로 FOREMAN이 띄운 창을 알아본다
        await self._act(sid, "spawn", pid, True, f"{tname} {pane} cc={cc} 이어서(--resume {row.cc[:8]})")
        await self._act(row.id, REST_RESUME_ACT, pid, True, f"{tname} {pane} cc={cc}" + (f" 새 행 {sid}" if sid != row.id else ""))
        if self.on_change:
            self.on_change()
        return {"ok": True, "tmux": tname, "session_id": sid, "cc_session_id": cc,
                "note": f"이어서 붙였습니다(tmux {tname}). 같은 대화를 그대로 이어 갑니다."}

    async def _resume(self, row: SessionRow) -> dict[str, Any]:
        live = live_sessions(self.sessions_dir).get(row.cc or "")
        if not live or live.state != "T":
            raise Refused("일시정지된 세션이 아닙니다")
        if await self._foreman_stopped(row.id) != live.pid:
            raise Refused("FOREMAN이 멈춘 세션이 아닙니다. 사람이 멈춘 세션은 건드리지 않습니다")
        te = _tmux_env(live.pid)
        if not te:
            raise Refused("tmux 밖에서 도는 세션입니다")
        socket, pane = te
        cmd = (await tmux(socket, "display-message", "-p", "-t", pane, "#{pane_current_command}")).strip()
        if cmd == "claude":
            raise Refused("이미 돌고 있습니다")
        # fg는 가장 최근에 멈춘 작업을 되살린다 — 그 셸에 멈춘 작업이 이 claude 하나인지 본다
        await tmux(socket, "send-keys", "-t", pane, "-l", "fg")
        await tmux(socket, "send-keys", "-t", pane, "Enter")
        ok = await self._wait(lambda: (_proc_stat(live.pid) or ("?",))[0] != "T", 5)
        await self._act(row.id, "resume", live.pid, ok, pane)
        return {"ok": ok, "pane": pane, "note": None if ok else "5초 안에 다시 시작하지 않았습니다. 대화창을 확인해 주세요."}

    @staticmethod
    async def _wait(cond: Any, secs: float) -> bool:
        loop = asyncio.get_running_loop()
        end = loop.time() + secs
        while loop.time() < end:
            if cond():
                return True
            await asyncio.sleep(0.3)
        return bool(cond())
