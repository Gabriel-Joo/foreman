"""세션이 살아 있는지 · 멈췄는지(11-11, README 「나중에 할 일」 「세션이 살아 있는지 · 멈췄는지 알기」).

CC는 스스로 심장박동을 보내지 않는다 — sessions/<pid>.json의 updatedAt은 상태(busy · idle)가 바뀔 때만 바뀐다(11-11 확인:
작업 중 11분째에도 그대로). 그래서 브리지가 1분마다 직접 잰다(심장박동 = 프로세스 · CC 상태 · 대화 기록의 마지막 줄 · tmux 화면).

멈춤의 종류(kind) — 화면(/api/dashboard `stall`)과 텔레그램이 같은 판정을 쓴다:
- died        작업 중(열린 턴)에 세션 프로세스가 사라졌다 — 일이 끝났다는 신호 없이 끊김
- silent      작업 중(busy)인데 SILENT 동안 대화 기록에 한 줄도 없다 — 한 도구가 끝나지 않는다
              (11-09 `until ! pgrep -f …` 셸이 영원히 돌았던 꼴. 화면의 스피너는 계속 돌아 화면으로는 못 가린다)
- loop        같은 작업(열린 턴)에서 LOOP_WINDOW 안에 같은 도구 · 같은 대상을 LOOP_SAME번 넘게, 또는 실패가 LOOP_ERRORS번 넘게(삽질)
              「같은」은 most_repeated · same_key가 가른다(11-11 디자이너 273 오판 뒤): Bash는 앞머리(S=… · cd … && · export ·
              timeout · env)를 뺀 명령 전체로, 서브에이전트마다 따로, 그 사이에 고친 것(Edit · Write · MCP 쓰기)이 있으면 다시 0부터
- exit_confirm CC 끝내기 확인 창("Background work is running … Exit and stop tasks")이 떠 있다 — 사람 답을 기다리며 멈춤
              (README 「세션이 끝나지 않고 CC 끝내기 확인 창에 걸린 것」)
- dialog      쉬는(busy 아닌) 세션에 결정 창(계획 승인 · 도구 권한 · 폴더 신뢰 …, `inject.screen_state`)이나 모르는 창이 떠 있는데
              브리지가 기다리는 승인(approval `pending`)이 없다 — 패널에는 답할 카드가 없고 대화창에서만 풀린다(11-14 362,
              `log/silent_finish_20261114.md` 1 · 4절). 모르는 창은 CC가 status `waiting`을 적었을 때만. 화면을 못 읽는 세션(tmux 밖)은
              status `waiting`만으로. 승인 대기 시간이 지나 브리지가 이미 알린 창(마지막 승인이 30분 안의 timeout)은 화면에만
- notice      안내 창(자동 압축 권유 · /model · /config …, screen_state `dismiss`)이 떠 있다 — dialog와 같게 2분 넘으면 알림 한 번
              (11-14 사용자 결정, 11-13 서기 339가 자동 압축 권유 창에 걸려 합치기가 멈췄다. 일부러 연 창도 2분이면 걸린다)
- long        한 작업이 LONG 넘게 — 화면에만(알리지 않는다, 긴 일은 정상일 수 있다)
- bg_long     뒤에서 도는 일(백그라운드 Bash)이 BG_LONG 넘게 끝 알림 없이 돈다(11-14, 11-13 330의 pytest가 2시간 10분 멈춘 채 돌았다).
              세션이 턴을 닫고 쉬어도 잰다. 출력이 나온 적 있고 BG_QUIET 안에 바뀌었으면 정상(계속 일하는 중), 나오다 안 바뀌었으면 「멈췄을 수 있음」.
              출력이 한 번도 안 나왔으면(파일 크기 0 — `| tail`처럼 끝에서만 찍는 명령) 멈춤 여부를 모르니 「오래 돕니다」만(11-14 헛경보 고침).
              Monitor는 일부러 오래 도는 것이라 뺀다. 알림 열쇠 `stall:bg_long:<세션>:<task>`

알림: kind마다 ALERT_AFTER를 넘으면 텔레그램 한 번(notification.rule 키 `stall:<kind>:<세션>:<시작 시각>` — 브리지를 다시 띄워도 한 번).
창(exit_confirm · dialog · notice)의 시작 시각은 브리지 메모리(그 창을 처음 본 때)라, 다시 띄우면 한 번 더 갈 수 있다.
멈춤 항목의 `notify`가 False면 알리지 않는 것이다(화면 툴팁이 「텔레그램으로도 알립니다」를 붙일지 가를 때 쓴다).
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import bindparam, text

from bridge.approval import _seg_spans      # 승인 판정과 같은 쪼개기(따옴표 · $( ) 안의 구분자는 무시)
from bridge.inject import Refused, _status, _tmux_env, screen_state, tmux
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.stallwatch")

SILENT = timedelta(minutes=30)
LOOP_WINDOW = timedelta(minutes=30)
LOOP_SAME = 6
LOOP_ERRORS = 8
# 같은 파일을 여러 번 고치고 읽는 것은 보통 코딩이다(11-11 실제로 재 보니 코더 272가 dashboard.py Edit 6번으로 걸렸다)
LOOP_QUIET = {"Edit", "MultiEdit", "Write", "NotebookEdit", "Read", "TodoWrite", "Grep", "Glob"}
# 파일을 고치는 도구 — 그 사이에 고친 것이 있으면 같은 명령을 다시 돌려도 맴돎이 아니다(고치고 다시 시험하기는 정상 진행)
LOOP_PROGRESS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
# MCP의 쓰기 도구도 고치기다(11-10 인프라 265가 Notion 페이지를 고치며 notion-update-page 같은 쪽을 6번 — 문서 고치기였다)
LOOP_PROGRESS_MCP = re.compile(r"^mcp__.*(update|create|edit|write|append|insert|replace|move|delete)", re.I)
LONG = timedelta(hours=2)
EXIT_RE = re.compile(r"Background work is running|will stop when you exit|Exit and stop tasks")
BG_LONG = timedelta(minutes=30)      # 뒤에서 도는 일이 이만큼 지나야 본다(11-14 — pytest 전체는 2~3분, 길어야 10분)
BG_QUIET = timedelta(minutes=15)     # 출력 파일이 이만큼 안 바뀌면 멈췄을 수 있다(점 하나씩 찍는 시험도 15분 비는 일은 드물다)
BG_SKIP_TOOLS = {"Monitor"}          # 일부러 오래 도는 것
ALERT_AFTER = {"died": timedelta(0), "silent": timedelta(0), "loop": timedelta(0), "exit_confirm": timedelta(minutes=2),
               "bg_long": timedelta(0), "dialog": timedelta(minutes=2), "notice": timedelta(minutes=2)}
# 승인 대기 시간이 지나 브리지가 「이제 대화창에서만 답할 수 있습니다」를 이미 보낸 뒤 이만큼은 dialog를 다시 알리지 않는다
TIMEOUT_QUIET = timedelta(minutes=30)

LABEL = {
    "died": "작업 중에 끊김",
    "silent": "응답 없음",
    "loop": "같은 자리에서 맴돎",
    "exit_confirm": "끝내기 확인 창에서 멈춤",
    "dialog": "창에서 답을 기다림",
    "notice": "안내 창이 떠 있음",
    "long": "긴 작업",
    "bg_long": "뒤에서 도는 일이 오래 걸림",
}


@dataclass
class Sample:
    """한 세션의 한 번 잰 값 — judge()의 입력(순수 판정을 시험하려고 DB · tmux와 떼어 둠)."""
    sid: int
    live: bool
    busy: bool = False
    turn_started: datetime | None = None          # 열린 턴(없으면 None)
    last_event: datetime | None = None
    last_tool: tuple[str | None, str | None] | None = None
    same: tuple[str | None, str | None, int] | None = None   # (도구, 대상, 횟수) — LOOP_WINDOW 안 같은 것 가장 많이
    errors: int = 0
    screen: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    # 끝 알림 없는 뒤에서 도는 일 — [{task, tool, description, since, out_mtime, out_size}] (judge_bg가 본다)
    bg: list[dict[str, Any]] = field(default_factory=list)
    # 쉬는 세션에 뜬 창(11-14 362, judge_dialog)
    cc_status: str | None = None                  # CC가 sessions/<pid>.json에 적은 status(busy · idle · waiting)
    pending: int = 0                              # 브리지가 기다리는 승인(approval pending) 수
    last_appr: tuple[str, datetime | None] | None = None   # 마지막 승인의 (status, decided_at)


def bg_output_stat(cc_session_id: str | None, task: str | None) -> tuple[datetime, int] | None:
    """뒤에서 도는 일의 출력 파일(/tmp/claude-<uid>/<폴더>/<CC 세션>/tasks/<task>.output)의 (마지막으로 바뀐 때(UTC), 크기) — 못 찾으면 None.
    task · 세션 id는 DB 값이라 글자를 가려 받고, 찾는 곳은 내 /tmp/claude-<uid> 아래뿐이다.
    크기 0 = 한 번도 출력이 안 나왔다(11-14: `pytest | tail`처럼 끝에서만 찍는 명령은 처음부터 끝까지 비어 있다.
    파일이 만들어질 때 시각이 찍히므로 빈 파일의 마지막 변경 시각은 「출력이 멈춘 때」가 아니다)."""
    if not cc_session_id or not task or not re.fullmatch(r"[\w-]+", cc_session_id) or not re.fullmatch(r"[\w-]+", task):
        return None
    for p in glob.glob(f"/tmp/claude-{os.getuid()}/*/{cc_session_id}/tasks/{task}.output"):
        try:
            st = os.stat(p)
        except OSError:
            continue
        return datetime.fromtimestamp(st.st_mtime, UTC).replace(tzinfo=None), st.st_size
    return None


def bg_output_mtime(cc_session_id: str | None, task: str | None) -> datetime | None:
    """출력 파일이 마지막으로 바뀐 때(UTC, 못 찾으면 None) — bg_output_stat의 앞 값."""
    st = bg_output_stat(cc_session_id, task)
    return st[0] if st else None


def judge_bg(s: Sample, now: datetime) -> list[dict[str, Any]]:
    """뒤에서 도는 일이 오래 걸리는지 — 일마다 [{kind: bg_long, label, since, detail, key, task, stalled}]. 살아 있는 세션만.
    - BG_LONG 안이면 아무것도 없다 · Monitor는 뺀다
    - 출력이 한 번도 안 나왔으면(파일 크기 0) 멈췄는지 알 수 없다 — 오래 돈다는 것만 말한다(끝에서만 찍는 명령일 수 있다)
    - 출력이 나온 적 있고 BG_QUIET 안에 바뀌었으면 계속 일하는 중이라 정상(오래 걸리는 시험도 점은 찍는다)
    - 나온 적 있는데 안 바뀌었으면 「멈췄을 수 있음」(stalled). 출력 파일을 못 찾으면 오래 걸린다는 것만 말한다
    - out_size가 없는 값(옛 꼴)은 출력이 나온 것으로 본다"""
    out: list[dict[str, Any]] = []
    if not s.live:
        return out
    for b in s.bg:
        since = b.get("since")
        if not since or b.get("tool") in BG_SKIP_TOOLS or now - since < BG_LONG:
            continue
        mt = b.get("out_mtime")
        never = mt is not None and b.get("out_size") == 0      # 한 번도 안 나옴 — mtime은 파일이 만들어진 때라 쓰지 않는다
        if never:
            mt = None
        elif mt is not None and now - mt < BG_QUIET:
            continue
        name = (b.get("description") or b.get("task") or "").strip()[:60]
        run = fmt_elapsed(now - since)
        if never:
            detail = f"「{name}」이 {run}째 돌고 있습니다 — 아직 출력이 한 번도 없습니다(끝에서만 출력하는 명령일 수 있습니다)"
        elif mt is None:
            detail = f"「{name}」이 {run}째 끝 알림 없이 돕니다 — 출력 파일을 찾지 못했습니다"
        else:
            detail = f"「{name}」이 {run}째 돌고 출력이 {fmt_elapsed(now - mt)}째 그대로입니다 — 멈췄을 수 있습니다"
        out.append({"kind": "bg_long", "label": LABEL["bg_long"], "since": since, "detail": detail,
                    "key": f"stall:bg_long:{s.sid}:{b.get('task')}", "task": b.get("task"), "stalled": mt is not None})
    return out


def fmt_elapsed(d: timedelta) -> str:
    """경과를 사람 말로 — 45분 · 2시간 10분 · 1일 3시간"""
    m = max(int(d.total_seconds() // 60), 0)
    if m < 60:
        return f"{m}분"
    h, mm = divmod(m, 60)
    if h < 24:
        return f"{h}시간" + (f" {mm}분" if mm else "")
    dd, hh = divmod(h, 24)
    return f"{dd}일" + (f" {hh}시간" if hh else "")


def dialog_key(s: Sample) -> str | None:
    """쉬는 세션에 뜬 창을 가르는 열쇠 — 바뀌면 「처음 본 때」를 다시 잰다. 창이 없으면 None."""
    if not s.live or s.busy:
        return None
    if s.screen:
        kind, name = screen_state(s.screen)
        # 모르는 창은 CC status도 열쇠에 — 늘 「모름」으로 보이던 화면이 waiting으로 바뀌면 그때부터 다시 잰다
        return None if kind == "prompt" else f"{kind}:{name or s.cc_status or ''}"
    return "waiting" if s.cc_status == "waiting" else None


def judge_dialog(s: Sample, now: datetime, since: datetime | None = None) -> list[dict[str, Any]]:
    """쉬는 세션에 뜬 CC 창 — exit_confirm · dialog · notice 중 하나(없으면 []). since = 그 창을 처음 본 때."""
    if not s.live or s.busy:
        return []
    since = since or now

    def item(kind: str, detail: str, notify: bool = True) -> list[dict[str, Any]]:
        return [{"kind": kind, "label": LABEL[kind], "since": since, "detail": detail, "notify": notify}]

    if not s.screen:
        if s.cc_status == "waiting" and not s.pending:
            return item("dialog", "CC가 사람을 기다린다고 적었는데 브리지가 기다리는 승인이 없습니다(화면은 못 읽었습니다) — "
                                  "그 세션의 대화창에 창이 떠 있을 수 있습니다")
        return []
    kind, name = screen_state(s.screen)
    if kind == "prompt":
        return []
    if name == "끝내기 확인" or EXIT_RE.search(s.screen):
        return item("exit_confirm", "CC가 뒤에서 도는 일을 멈출지 묻고 기다립니다(1 멈추고 끝내기 · 2 뒤로 보내고 끝내기 · 3 남기)")
    if kind == "dismiss":
        return item("notice", (f"「{name}」 " if name else "") + "안내 창이 떠 있어 세션이 입력을 못 받습니다 — 대화창을 확인해 주세요")
    if s.pending:
        return []                                  # 패널에 카드가 이미 있다
    if kind == "unknown" and s.cc_status != "waiting":
        return []                                  # 화면을 잘못 가른 것일 수 있다 — CC도 기다린다고 적었을 때만
    what = f"「{name}」 창" if name else "알 수 없는 창"
    st, at = s.last_appr or (None, None)
    quiet = kind == "decision" and st == "timeout" and at is not None and now - at < TIMEOUT_QUIET
    return item("dialog", f"{what}이 떠 있는데 패널에는 기다리는 승인이 없습니다 — 그 세션의 대화창에서 답해야 이어집니다"
                + (" (화면 승인은 대기 시간이 지나 닫혔습니다)" if quiet else ""), notify=not quiet)


def judge(s: Sample, now: datetime, exit_since: datetime | None = None) -> list[dict[str, Any]]:
    """멈춤 목록 — [{kind, label, since, detail[, notify]}]. since는 그 상태가 시작된 때(알림 키에 쓴다).
    exit_since = 지금 떠 있는 창을 처음 본 때(judge_dialog의 since)."""
    out: list[dict[str, Any]] = []

    def add(kind: str, since: datetime | None, detail: str) -> None:
        out.append({"kind": kind, "label": LABEL[kind], "since": since, "detail": detail})

    if not s.live:
        if s.turn_started:
            add("died", s.last_event or s.turn_started, "작업이 끝났다는 신호 없이 세션 프로세스가 사라졌습니다")
        return out
    out.extend(judge_dialog(s, now, exit_since))
    if s.busy and s.last_event and now - s.last_event >= SILENT:
        tool, target = s.last_tool or (None, None)
        mins = int((now - s.last_event).total_seconds() // 60)
        add("silent", s.last_event, f"{mins}분째 대화 기록에 줄이 없습니다 — 마지막 도구 {tool or '?'}"
            + (f" {target[:80]}" if target else "") + "가 끝나지 않았을 수 있습니다")
    if s.turn_started:
        if s.same and s.same[2] >= LOOP_SAME:
            add("loop", s.turn_started, f"30분 안에 {s.same[0]} {(s.same[1] or '')[:80]}를 {s.same[2]}번 했습니다")
        elif s.errors >= LOOP_ERRORS:
            add("loop", s.turn_started, f"30분 안에 도구가 {s.errors}번 실패했습니다")
        if now - s.turn_started >= LONG:
            add("long", s.turn_started, f"한 작업이 {int((now - s.turn_started).total_seconds() // 60)}분째입니다")
    out += judge_bg(s, now)
    return out


# 명령 앞머리 — 무엇을 하는지는 바꾸지 않고 자리만 잡는 것(11-11 디자이너 273: `S=<스크래치 경로>; …`가 앞 160자를 채워
# 뒤가 다른 명령 여덟 개가 하나로 묶였다). 맨 바깥 수준의 ; · && · 줄바꿈으로 이어진 앞 조각만 뺀다(파이프 앞은 빼지 않는다).
_SETUP_SEG = re.compile(
    r"""(?:[A-Za-z_]\w*=\S*(?:\s+[A-Za-z_]\w*=\S*)*      # S=… · T=$(…) · A=1 B=2(값에 공백 없는 꼴 — 공백은 아래 _ASSIGN_ONLY)
        |export\s.*|unset\s.*|cd(?:\s.*)?|pushd\s.*|set\s+[-+]\S*.*|umask\s.*
        |(?:source|\.)\s+\S*activate\S*|\#.*)""", re.X | re.S)
_ASSIGN_ONLY = re.compile(r"""(?:[A-Za-z_]\w*=(?:'[^']*'|"(?:[^"\\]|\\.)*"|\$\((?:[^()]|\([^()]*\))*\)|`[^`]*`|[^\s;&|'"`$]|\$(?!\())*\s*)+""", re.S)
# 한 명령 안의 앞머리 — A=B cmd · env A=B cmd · timeout 60 cmd · nice · time · command
_PREFIX_WORD = re.compile(
    r"""^(?:[A-Za-z_]\w*=(?:'[^']*'|"(?:[^"\\]|\\.)*"|\S)*\s+
        |env(?:\s+-\S+)*\s+(?=\S)|timeout(?:\s+-\S+)*\s+\d+(?:\.\d+)?[smhd]?\s+
        |nice(?:\s+-n)?(?:\s+-?\d+)?\s+|time\s+|command\s+|stdbuf(?:\s+-\S+)+\s+)""", re.X)


def same_key(tool: str | None, target: str | None) -> str:
    """같은 일인지 가를 열쇠 — Bash는 앞머리를 빼고 남은 명령 전체(공백은 하나로). 다른 도구는 대상 그대로."""
    t = (target or "").strip()
    if tool != "Bash" or not t:
        return t
    spans = _seg_spans(t)
    k = 0
    while k < len(spans) - 1:
        a, b, _ = spans[k]
        seg = t[a:b].strip()
        if spans[k + 1][2] not in (";", "&&", "\n"):       # 다음이 파이프(|)나 ||면 앞 조각도 명령의 일부
            break
        if not (_SETUP_SEG.fullmatch(seg) or _ASSIGN_ONLY.fullmatch(seg)):
            break
        k += 1
    rest = t[spans[k][0]:].strip() if spans else t
    while (m := _PREFIX_WORD.match(rest)) and m.end() < len(rest):
        rest = rest[m.end():]
    return " ".join(rest.split()) or " ".join(t.split())


def most_repeated(events: list[tuple[Any, ...]]) -> tuple[str | None, str | None, int] | None:
    """시간 순 (도구, 대상[, 누가])에서 가장 많이 되풀이한 것 — (도구, 열쇠, 횟수). 누가 = 서브에이전트(없으면 본 세션).

    - 조용한 도구(LOOP_QUIET)는 세지 않는다
    - 누가마다 따로 센다 — 병렬 서브에이전트 아홉이 저마다 ToolSearch 한 번씩은 맴돎이 아니다(10-21 런슈즈 156 실제)
    - 고치면(LOOP_PROGRESS · MCP 쓰기) 그 누가의 센 것을 모두 0으로 — 고치고 다시 돌리기는 맴돎이 아니다
    """
    counts: dict[tuple[Any, str | None, str], int] = {}
    best: tuple[str | None, str | None, int] | None = None
    for ev in events:
        tool, target = ev[0], ev[1]
        who = ev[2] if len(ev) > 2 else None
        if tool in LOOP_PROGRESS or (tool and LOOP_PROGRESS_MCP.match(tool)):
            for k in [k for k in counts if k[0] == who]:
                del counts[k]
            continue
        if tool in LOOP_QUIET:
            continue
        key = (who, tool, same_key(tool, target))
        counts[key] = n = counts.get(key, 0) + 1
        if best is None or n > best[2]:
            best = (tool, key[2], n)
    return best


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def _proc_started(sessions_dir: Any, pid: int) -> datetime | None:
    """sessions/<pid>.json의 startedAt(UTC) — 대시보드 background_running의 「지금 프로세스가 뜬 뒤」 거르기와 같다."""
    from bridge.api.dashboard import _started
    return _started(sessions_dir, pid)


class StallWatch:
    def __init__(self, engine: Any, notifier: Any, sessions_dir: Any, every_s: float = 60.0) -> None:
        self.engine, self.notifier, self.dir, self.every = engine, notifier, sessions_dir, every_s
        self.live: Any = live_sessions          # 시험이 바꿔 끼운다
        self.status: Any = _status
        self.screen: Any = self._screen
        self.dialog_seen: dict[int, tuple[str, datetime]] = {}   # 쉬는 세션에 뜬 창(dialog_key)을 처음 본 때(세션별, 메모리)
        self.snapshot: dict[int, list[dict[str, Any]]] = {}   # 대시보드가 읽는다

    async def _screen(self, pid: int) -> str | None:
        te = _tmux_env(pid)
        if not te:
            return None
        try:
            # -J(줄 이음)는 inject._capture와 같게 — screen_state의 표 · 테두리 꼴이 그 옵션으로 잰 것이다(11-13 351)
            return await tmux(te[0], "capture-pane", "-p", "-J", "-t", te[1])
        except Refused:
            return None

    async def samples(self, now: datetime) -> tuple[list[Sample], dict[int, tuple[Any, ...]]]:
        live = await asyncio.to_thread(self.live, self.dir)
        live_ok = {cc: ls for cc, ls in live.items() if ls.state != "T"}     # 멈춰 둔(Ctrl+Z) 것은 보지 않는다
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, COALESCE(cs.custom_title, cs.title), p.name, "
                "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id) "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.type = 'agent' AND cs.hidden_at IS NULL AND (cs.cc_session_id IN :ids OR cs.id IN "
                "(SELECT session_id FROM turn WHERE ended_at IS NULL AND started_at > :cut))"
            ).bindparams(bindparam("ids", expanding=True)),
                {"ids": sorted(live_ok) or ["-"], "cut": now - timedelta(hours=24)})).all()
            if not rows:
                return [], {}
            in_ids = "(" + ",".join(str(int(r[0])) for r in rows) + ")"
            turns = {r[0]: r[1:] for r in (await c.execute(text(
                f"SELECT session_id, id, started_at FROM turn WHERE session_id IN {in_ids} AND ended_at IS NULL"))).all()}
            last_tool = {r[0]: (r[1], r[2]) for r in (await c.execute(text(
                f"SELECT e.session_id, e.tool, e.target FROM event e JOIN (SELECT session_id, MAX(id) mid FROM event "
                f"WHERE session_id IN {in_ids} AND type = 'tool_use' GROUP BY session_id) x ON x.mid = e.id"))).all()}
            same: dict[int, tuple[Any, Any, int]] = {}
            errs: dict[int, int] = {}
            for sid, (tid, _) in turns.items():
                # 앞 몇 글자로 묶지 않는다 — 명령 전체(1,024자 넘으면 payload의 원문)를 가져와 same_key로 가른다
                evs = (await c.execute(text(
                    "SELECT tool, IF(target_truncated, COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.target_full')), target), target), "
                    "subagent_id FROM event WHERE session_id = :s AND turn_id = :t AND type = 'tool_use' AND ts > :w ORDER BY ts, id"),
                    {"s": sid, "t": tid, "w": now - LOOP_WINDOW})).all()
                if (r := most_repeated([tuple(e) for e in evs])):
                    same[sid] = r
                # 실패도 누가(서브에이전트)마다 — 병렬 다섯이 한두 번씩 실패한 것을 합쳐 8번으로 세지 않는다(11-09 런슈즈 221 실제)
                errs[sid] = int((await c.execute(text(
                    "SELECT COUNT(*) n FROM event WHERE session_id = :s AND turn_id = :t AND type = 'tool_result' "
                    "AND status = 'error' AND ts > :w GROUP BY subagent_id ORDER BY n DESC LIMIT 1"),
                    {"s": sid, "t": tid, "w": now - LOOP_WINDOW})).scalar() or 0)
            # 끝 알림 없는 뒤에서 도는 일(bg_start에 bg_end가 없는 것) — 대시보드 「뒤에서 도는 일」과 같은 기준(24시간 안)
            bgs: dict[int, list[tuple[Any, ...]]] = {}
            for bsid, task, tool, desc, bts in (await c.execute(text(
                    f"SELECT s.session_id, s.target, s.tool, JSON_UNQUOTE(JSON_EXTRACT(s.payload, '$.description')), s.ts "
                    f"FROM event s WHERE s.session_id IN {in_ids} AND s.type = 'bg_start' AND s.ts > :cut AND NOT EXISTS "
                    f"(SELECT 1 FROM event e WHERE e.session_id = s.session_id AND e.type = 'bg_end' AND e.target = s.target) "
                    f"ORDER BY s.ts"), {"cut": now - timedelta(hours=24)})).all():
                bgs.setdefault(bsid, []).append((task, tool, None if desc in (None, "null") else desc, bts))
            # 쉬는 세션에 뜬 창(judge_dialog) — 브리지가 기다리는 승인 수 · 마지막 승인
            pending = {r[0]: int(r[1]) for r in (await c.execute(text(
                f"SELECT session_id, COUNT(*) FROM approval WHERE session_id IN {in_ids} AND status = 'pending' "
                f"GROUP BY session_id"))).all()}
            last_appr = {r[0]: (r[1], r[2]) for r in (await c.execute(text(
                f"SELECT a.session_id, a.status, a.decided_at FROM approval a JOIN (SELECT session_id, MAX(id) mid FROM approval "
                f"WHERE session_id IN {in_ids} GROUP BY session_id) x ON x.mid = a.id"))).all()}
        out: list[Sample] = []
        meta: dict[int, tuple[Any, ...]] = {}
        for sid, cc, title, project, last_ts in rows:
            if cc in live and cc not in live_ok:      # 멈춰 둔(T) 세션 — 끊긴 것도 멈춘 것도 아니다(사용자가 남겨 둠)
                continue
            ls = live_ok.get(cc)
            cc_st = self.status(self.dir, ls.pid) if ls else None     # 아래 bg 반복의 st(출력 파일)와 다른 이름으로
            busy = cc_st == "busy"
            screen = await self.screen(ls.pid) if ls and not busy else None    # 창은 일하지 않을 때(idle · waiting) 뜬다
            t = turns.get(sid)
            started = _proc_started(self.dir, ls.pid) if ls and bgs.get(sid) else None
            bg = []
            for task, tool, desc, bts in bgs.get(sid, []) if ls else []:
                if started is not None and bts is not None and bts < started:
                    continue                              # 지금 프로세스가 뜨기 전 것은 죽었다(대시보드와 같은 거르기)
                if tool in BG_SKIP_TOOLS or now - bts < BG_LONG:
                    continue                              # 짧은 것은 출력 파일을 볼 필요가 없다
                st = await asyncio.to_thread(bg_output_stat, cc, task)
                bg.append({"task": task, "tool": tool, "description": desc, "since": bts,
                           "out_mtime": st[0] if st else None, "out_size": st[1] if st else None})
            out.append(Sample(sid=sid, live=bool(ls), busy=busy, turn_started=t[1] if t else None, last_event=last_ts,
                              last_tool=last_tool.get(sid), same=same.get(sid), errors=errs.get(sid, 0), screen=screen, bg=bg,
                              cc_status=cc_st, pending=pending.get(sid, 0), last_appr=last_appr.get(sid)))
            meta[sid] = (title, project)
        return out, meta

    async def check(self, now: datetime | None = None) -> list[str]:
        """한 번 잰다 — snapshot을 고치고, 알릴 것은 보낸다. 돌려주는 값: 이번에 보낸 rule 키들."""
        now = now or datetime.now(UTC).replace(tzinfo=None)
        samples, meta = await self.samples(now)
        snap: dict[int, list[dict[str, Any]]] = {}
        sent: list[str] = []
        seen_dialog: set[int] = set()
        for s in samples:
            if (dk := dialog_key(s)) is not None:
                seen_dialog.add(s.sid)
                if (prev := self.dialog_seen.get(s.sid)) is None or prev[0] != dk:
                    self.dialog_seen[s.sid] = (dk, now)
            found = judge(s, now, self.dialog_seen[s.sid][1] if s.sid in seen_dialog else None)
            if found:
                snap[s.sid] = [{**f, "since": _iso(f["since"])} for f in found]
            for f in found:
                if f["kind"] not in ALERT_AFTER or not f.get("notify", True) or now - (f["since"] or now) < ALERT_AFTER[f["kind"]]:
                    continue
                key = f.get("key") or f"stall:{f['kind']}:{s.sid}:{(f['since'] or now):%Y%m%d%H%M}"
                if await self._send(key, s.sid, meta.get(s.sid, (None, None)), f):
                    sent.append(key)
        for sid in list(self.dialog_seen):
            if sid not in seen_dialog:
                del self.dialog_seen[sid]
        self.snapshot = snap
        return sent

    async def _send(self, key: str, sid: int, meta: tuple[Any, ...], f: dict[str, Any]) -> bool:
        if self.notifier is None:
            return False
        async with self.engine.connect() as c:
            if (await c.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key})).first():
                return False
        title, project = meta
        rule = self.notifier.rules.for_project(project) if project else None
        prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
        what = {"died": "다시 띄우거나 [새로 띄우기]로 이어 갑니다",
                "silent": "대화창에서 무엇이 도는지 보고, 필요하면 [작업 중단]을 누릅니다",
                "loop": "그 세션에 다른 방법을 지시하거나 [작업 중단]을 누릅니다",
                "exit_confirm": "대화창에서 고릅니다 — 뒤에서 도는 일이 끝나도 되면 1, 남기려면 3",
                "bg_long": "대화창에서 그 일을 보고, 멈췄으면 세션에 멈추라고 지시합니다",
                "dialog": "그 세션의 대화창에서 답합니다 — 패널에는 답할 카드가 없습니다"}.get(f["kind"], "")
        msg = "\n".join([f"{prefix} ⏸ {f['label']} — 「{title or sid}」(세션 {sid})", f"▶ {f['detail']}", what])
        log.warning("멈춤 알림: 세션 %s %s — %s", sid, f["kind"], f["detail"][:120])
        self.notifier.send_direct(project, "stall", sid, msg, rule=key)
        return True

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.every)
            try:
                await self.check()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 한 번의 실패가 감시를 멈추지 않는다
                log.warning("멈춤 확인 실패: %s: %s", type(e).__name__, str(e)[:200])
