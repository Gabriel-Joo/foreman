"""조립 — 트랜스크립트 줄과 hook을 turn · message · subagent_run · event 행으로 만든다.

쓰는 작업은 하나다(asyncio.Lock). 파일 한 덩어리(chunk) = DB 트랜잭션 하나이고, transcript_file의 offset도
같은 트랜잭션에서 옮긴다 — 커밋되지 않은 줄은 다음에 다시 읽힌다. 다시 읽어도 행이 늘지 않는다:
  event   uuid UNIQUE (uuid 없는 줄 · 한 줄의 두 번째 블록은 경로·offset으로 만든 uuid5)
  message message.id PK — content 블록마다 줄이 쪼개져도 usage는 한 번만
  turn    prompt_id UNIQUE — CC의 promptId(한 턴의 user 줄이 모두 같은 값을 갖는다, 0003 머리말)

턴 경계(README 3.2) — 먼저 온 신호가 닫는다(closed_by에 출처):
  열기  새 promptId를 가진 user 줄(프롬프트 · task-notification · 다른 세션 메시지). hook UserPromptSubmit
  닫기  system/turn_duration → stop · '[Request interrupted by user…]' → interrupted · API 오류 → stop_failure
        hook Stop/StopFailure/SessionEnd · 프로세스가 사라짐(sweep) → session_end(hook을 한 번도 못 받은 세션) / process_lost
        새 턴이 열렸는데 앞 턴이 안 닫혔으면 → 앞 턴에 모델 활동이 있었으면 no_signal(종료 신호가 기록되지 않았다),
        없었으면 merged(응답 없이 다음 입력과 함께 처리 — 실측 54건 전부 이쪽: task-notification 46 · 다른 세션 메시지 5 · 사람 3)
  순서  파일 기록 순서. timestamp로 정렬하지 않는다(역전 실측)

서브에이전트(README 3.11): 부모의 Agent tool_result(toolUseResult.agentId)에서 행을 만들고 그 턴을 spawn_turn으로.
  자식 파일의 메시지 · 이벤트는 spawn_turn에 귀속. 출력 토큰은 output_tokens_reliable=false.
  <task-notification>의 subagent_tokens 등은 reported_*에 보조 검증용으로만 남긴다
tool_result 본문은 저장하지 않는다(길이 · 오류 여부만, 오류면 앞 300자) — 형식을 모르는 비밀이 섞일 수 있다(mask.py)
"""

import asyncio
import logging
import re
import uuid as uuidlib
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from bridge.api_error import classify as classify_api_error
from bridge.config import Settings
from bridge.inject import _status
from bridge.liveness import live_sessions
from bridge.mask import Masker
from bridge.models import clip_target
from bridge.transcript.reader import Chunk, FileKey, read_meta

log = logging.getLogger("foreman.assembler")

NS = uuidlib.UUID("6f1c2a52-0f6e-4b8e-9b55-1d2f0e6a4f01")
INTERRUPT = "[Request interrupted by user"
AGENT_MSG = "Another Claude session sent a message"
# 관리자끼리 부탁(bridge/managers.py ask_text) — tmux 입력 칸으로 들어와 사람 입력처럼 잡히던 것(11-12).
# 보낸 쪽이 프로젝트 관리자인 것만 — 「사람 관리자」(계획 카드 [관리자에게 보내기], from 없음)는 사람이 누른 것이라 human으로 둔다
MGR_ASK = "[관리자 부탁 — "
MGR_ASK_HUMAN = "[관리자 부탁 — 사람 관리자"
TEXT_CLIP = 2000      # tool_use 입력의 문자열 하나
PREVIEW = 500         # 큐 · 알림 미리보기
QUEUE_TEXT = 20_000   # 작업 중에 보낸 입력(대기열) — 턴이 되지 않고 열린 턴에 끼어든다. 대화 패널이 이것을 내 글로 보여 준다(11-05)
ERR_PREVIEW = 300     # 오류 tool_result 앞부분
FROM_RE = re.compile(r'<agent-message from="([^"]+)"')
TAG_RE = re.compile(r"<(task-id|tool-use-id|status|summary|subagent_tokens|tool_uses|duration_ms)>(.*?)</\1>", re.S)
NOTIF_STATUS = {"completed": "done", "failed": "failed", "killed": "stopped", "stopped": "stopped", "cancelled": "stopped"}


def _uuid5(*parts: Any) -> str:
    return str(uuidlib.uuid5(NS, "|".join(str(p) for p in parts)))


def _ts(s: str | None) -> datetime:
    if not s:
        return datetime.now(UTC).replace(tzinfo=None)
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _target_of(name: str, inp: dict[str, Any]) -> str | None:
    for k in {
        "Bash": ("command",), "Read": ("file_path",), "Edit": ("file_path",), "Write": ("file_path",),
        "NotebookEdit": ("notebook_path", "file_path"), "Grep": ("pattern",), "Glob": ("pattern",),
        "WebFetch": ("url",), "WebSearch": ("query",), "Agent": ("description",), "Task": ("description",),
        "Skill": ("skill",), "Monitor": ("description", "command"),
    }.get(name, ()):
        if isinstance(inp.get(k), str):
            return inp[k]
    for v in inp.values():  # 모르는 도구: 첫 짧은 문자열
        if isinstance(v, str) and v:
            return v
    return None


@dataclass
class TurnRef:
    id: int
    prompt_id: str | None
    started_at: datetime
    by_hook: bool = False
    active: bool = False  # 이 턴에 모델 활동(assistant 줄)이 있었나 — 안 닫힌 채 다음 턴이 오면 merged / no_signal


@dataclass
class SessionState:
    id: int
    character_id: int
    project: str | None
    seq: int
    open_turn: TurnRef | None
    last_turn_id: int | None
    last_ts: datetime | None = None
    hook_seen: bool = False
    detached: bool = False
    transcript_file_id: int | None = None
    title: str | None = None
    copying: bool = False        # fork · resume가 복사해 온 앞 세션 줄을 지나는 중 — 첫 새 프롬프트까지 건너뛴다(11-05)
    copy_floor: datetime | None = None   # 복사 구간 직전 이 세션 줄의 시각 — 이보다 이른 user 줄은 복사 줄
    prompt_turns: "OrderedDict[str, int]" = field(default_factory=OrderedDict)
    tool_names: "OrderedDict[str, str]" = field(default_factory=OrderedDict)
    agent_inputs: "OrderedDict[str, dict[str, Any]]" = field(default_factory=OrderedDict)

    def remember(self, d: "OrderedDict[str, Any]", k: str, v: Any, cap: int = 2048) -> None:
        d[k] = v
        d.move_to_end(k)
        while len(d) > cap:
            d.popitem(last=False)


@dataclass
class SubState:
    id: int
    session_id: int
    spawn_turn_id: int | None


@dataclass
class FileState:
    id: int
    offset: int
    inode: int


@dataclass
class Batch:
    events: list[dict[str, Any]] = field(default_factory=list)
    messages: dict[str, dict[str, Any]] = field(default_factory=dict)
    turn_msgs: list[dict[str, Any]] = field(default_factory=list)  # WS로 낼 턴 열기·닫기
    closed: list[tuple[int, int, str, str, str | None]] = field(default_factory=list)  # 커밋 뒤 알림(세션, 턴, 이유, 출처, 메모)
    subs_done: set[int] = field(default_factory=set)  # 커밋 뒤 묶음 판정할 세션(서브에이전트가 끝났다)
    compacts: set[int] = field(default_factory=set)   # 커밋 뒤 압축 알림을 판정할 세션(11-05)
    tool_results: list[tuple[str, Any]] = field(default_factory=list)  # 커밋 뒤 승인 대기에 알릴 (tool_use_id, permissionDecision)
    skipped: list[tuple[int, str]] = field(default_factory=list)  # 너그러운 모드에서 버린 줄 (offset, 이유)


@dataclass
class Stats:
    files: int = 0
    chunks: int = 0
    lines: int = 0
    skipped_api: int = 0
    bad_lines: int = 0
    events: int = 0
    messages: int = 0
    turns_opened: int = 0
    turns_closed: dict[str, int] = field(default_factory=dict)
    resets: int = 0
    copied_prompts: int = 0      # resume · fork 세션이 복사해 온 앞 세션의 프롬프트(이미 원래 세션에 있다 — 건너뜀)
    skipped_records: int = 0     # 너그러운 모드에서 건너뛴 줄(watcher가 같은 덩어리에서 여러 번 실패한 뒤)


class Assembler:
    def __init__(self, engine: AsyncEngine, settings: Settings, masker: Masker, publish: Any = None) -> None:
        self.engine = engine
        self.s = settings
        self.mask = masker
        self.publish = publish            # 적재 뒤 WS로 내보내는 함수(dict) — 백필 중에는 안 부른다
        self.lock = asyncio.Lock()
        self.live = False
        self.sessions: dict[str, SessionState] = {}
        self.subs: dict[str, SubState] = {}
        self.files: dict[str, FileState] = {}
        self.projects: list[tuple[str, int, str, int]] = []  # (repo_path, project_id, name, 새 세션을 붙일 character_id — 코더, 없으면 포먼)
        self.unassigned_char: int | None = None
        self.stats = Stats()
        # 턴이 닫힌 직후 부르는 함수(session_id, turn_id, reason, by, note) — 4단계 알림. 실시간 모드에서만
        self.on_turn_closed: Any = None
        self.on_subagents_changed: Any = None  # (session_id) — 서브에이전트가 끝났다
        self.on_compact: Any = None            # (session_id) — 압축이 있었다(11-05 압축 알림). 실시간 모드에서만
        # (session_id, cc_session_id, 가린 프롬프트, ts) — 사람 입력이 들어왔다(11-06 겹침 알림, UserPromptSubmit hook만)
        self.on_human_prompt: Any = None
        self.on_tool_result: Any = None        # (tool_use_id, permissionDecision) — 5단계 승인 대기(터미널에서 답했다)

    # ── 시작 ────────────────────────────────────────────────
    async def load(self) -> None:
        async with self.engine.connect() as c:
            # 새로 입양하는 세션의 자리 — 그 프로젝트의 코더(0017 재배치 뒤). 코더가 없으면 예전처럼 포먼
            rows = (await c.execute(text(
                "SELECT p.repo_path, p.id, p.name, COALESCE("
                "(SELECT k.id FROM `character` k WHERE k.project_id = p.id AND k.current_role = 'coder' "
                " AND k.retired_at IS NULL AND k.name = '코더' LIMIT 1), c.id) FROM project p "
                "JOIN `character` c ON c.project_id = p.id AND c.current_role = 'foreman'"))).all()
            self.projects = sorted(((r[0], r[1], r[2], r[3]) for r in rows), key=lambda x: -len(x[0]))
            r = (await c.execute(text(
                "SELECT id FROM `character` WHERE project_id IS NULL AND name = '미분류' LIMIT 1"))).first()
            self.unassigned_char = r[0] if r else None
            for path, fid, off, ino in (await c.execute(text(
                    "SELECT path, id, read_offset, inode FROM transcript_file"))).all():
                self.files[path] = FileState(fid, off, ino)

    def file_state(self, path: str) -> FileState | None:
        return self.files.get(path)

    def _project_for(self, cwd: str | None, project_dir: str) -> tuple[str | None, int]:
        if cwd:
            for repo, _pid, name, char in self.projects:
                if cwd == repo or cwd.startswith(repo.rstrip("/") + "/"):
                    return name, char
        for repo, _pid, name, char in self.projects:  # cwd가 없으면 디렉토리 이름(/ _ → -)으로
            if project_dir == re.sub(r"[/_.]", "-", repo):
                return name, char
        if self.unassigned_char is None:
            raise RuntimeError("미분류 캐릭터가 없다 — 0004 마이그레이션")
        return None, self.unassigned_char

    # ── 세션 · 파일 · 서브에이전트 ─────────────────────────────
    async def _session(self, c: AsyncConnection, sid: str, cwd: str | None, project_dir: str,
                       first_ts: datetime | None, tf_id: int | None) -> SessionState:
        st = self.sessions.get(sid)
        if st is None:
            row = (await c.execute(text(
                "SELECT cs.id, cs.character_id, cs.detached_at, cs.transcript_file_id, p.name, cs.title "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.cc_session_id = :sid ORDER BY cs.id DESC LIMIT 1"), {"sid": sid})).first()
            if row is None:
                project, char = self._project_for(cwd, project_dir)
                res = await c.execute(text(
                    "INSERT INTO character_session (character_id, type, role, cc_session_id, cwd, transcript_file_id, "
                    "wake_reason, attached_at) VALUES (:char, 'agent', 'coder', :sid, :cwd, :tf, 'user', :at)"),
                    {"char": char, "sid": sid, "cwd": cwd, "tf": tf_id, "at": first_ts or _ts(None)})
                sess_id, detached, tf, title = res.lastrowid, False, tf_id, None
            else:
                sess_id, char, detached, tf, project, title = row[0], row[1], row[2] is not None, row[3], row[4], row[5]
            seq = (await c.execute(text("SELECT COALESCE(MAX(seq), 0) FROM turn WHERE session_id = :s"),
                                   {"s": sess_id})).scalar_one()
            o = (await c.execute(text(
                "SELECT id, prompt_id, started_at FROM turn WHERE session_id = :s AND ended_at IS NULL "
                "ORDER BY seq DESC LIMIT 1"), {"s": sess_id})).first()
            last = (await c.execute(text("SELECT MAX(id) FROM turn WHERE session_id = :s"), {"s": sess_id})).scalar()
            hook = (await c.execute(text(
                "SELECT 1 FROM event WHERE session_id = :s AND source = 'hook' LIMIT 1"), {"s": sess_id})).first()
            ref = None
            if o:
                act = (await c.execute(text(
                    "SELECT 1 FROM event WHERE turn_id = :t AND type IN ('assistant_msg', 'tool_use') LIMIT 1"),
                    {"t": o[0]})).first()
                ref = TurnRef(o[0], o[1], o[2], o[1] is None, active=act is not None)
            st = SessionState(sess_id, char, project, seq, ref,
                              last, hook_seen=hook is not None, detached=detached, transcript_file_id=tf, title=title)
            self.sessions[sid] = st
        if tf_id is not None and st.transcript_file_id is None:
            await c.execute(text("UPDATE character_session SET transcript_file_id = :tf WHERE id = :id"),
                            {"tf": tf_id, "id": st.id})
            st.transcript_file_id = tf_id
        if st.detached and tf_id is not None:  # 끝난 줄 알았던 세션에 새 줄(--resume) — 다시 붙었다
            await c.execute(text("UPDATE character_session SET detached_at = NULL WHERE id = :id"), {"id": st.id})
            st.detached = False
        return st

    async def _file(self, c: AsyncConnection, ch: Chunk) -> int:
        fs = self.files.get(ch.key.path)
        if fs is not None:
            return fs.id
        res = await c.execute(text(
            "INSERT INTO transcript_file (path, cc_session_id, agent_id, inode, read_offset) "
            "VALUES (:p, :sid, :aid, :ino, 0) ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)"),
            {"p": ch.key.path, "sid": ch.key.cc_session_id, "aid": ch.key.agent_id, "ino": ch.inode})
        return res.lastrowid

    async def _turn_of_prompt(self, c: AsyncConnection, st: SessionState, pid: str | None) -> int | None:
        if not pid:
            return st.open_turn.id if st.open_turn else None
        if st.open_turn and st.open_turn.prompt_id == pid:
            return st.open_turn.id
        if pid in st.prompt_turns:
            return st.prompt_turns[pid]
        r = (await c.execute(text("SELECT id FROM turn WHERE prompt_id = :p"), {"p": pid})).first()
        if r:
            st.remember(st.prompt_turns, pid, r[0], 256)
            return r[0]
        return None

    async def _sub(self, c: AsyncConnection, agent_id: str, st: SessionState, *, tool_use_id: str | None = None,
                   spawn_turn: int | None = None, info: dict[str, Any] | None = None) -> SubState:
        """agent_id로 subagent_run을 찾거나 만든다. 부모 tool_result에서 오면 spawn_turn을 채운다."""
        sub = self.subs.get(agent_id)
        created = False
        if sub is None:
            r = (await c.execute(text("SELECT id, session_id, spawn_turn_id FROM subagent_run WHERE agent_id = :a"),
                                 {"a": agent_id})).first()
            if r:
                sub = SubState(r[0], r[1], r[2])
            else:
                info = info or {}
                if spawn_turn is None and tool_use_id:
                    e = (await c.execute(text(
                        "SELECT turn_id FROM event WHERE tool_use_id = :t AND type = 'tool_use' AND subagent_id IS NULL "
                        "LIMIT 1"), {"t": tool_use_id})).first()
                    spawn_turn = e[0] if e else None
                res = await c.execute(text(
                    "INSERT INTO subagent_run (session_id, agent_id, tool_use_id, spawn_turn_id, agent_type, mode, "
                    "spawn_depth, description, status, output_tokens_reliable) VALUES "
                    "(:s, :a, :t, :turn, :type, :mode, :depth, :desc, :status, FALSE)"),
                    {"s": st.id, "a": agent_id, "t": tool_use_id or "", "turn": spawn_turn,
                     "type": info.get("agent_type") or "unknown", "mode": info.get("mode") or "background",
                     "depth": info.get("spawn_depth") or 1, "desc": (info.get("description") or "")[:512] or None,
                     "status": info.get("status") or "running"})
                sub = SubState(res.lastrowid, st.id, spawn_turn)
                created = True
            self.subs[agent_id] = sub
        if not created and info and (info.get("description") or info.get("agent_type") or tool_use_id):
            # hook(SubagentStart)이 트랜스크립트보다 먼저 행을 만들면 설명 · 종류가 비어 있다 — 뒤에 온 정보로 채운다(4단계 실측)
            await c.execute(text(
                "UPDATE subagent_run SET description = COALESCE(description, :desc), "
                "agent_type = IF(agent_type = 'unknown' AND :type IS NOT NULL, :type, agent_type), "
                "tool_use_id = IF(tool_use_id = '' AND :tu IS NOT NULL, :tu, tool_use_id) WHERE id = :id"),
                {"desc": (info.get("description") or "")[:512] or None, "type": info.get("agent_type"),
                 "tu": tool_use_id, "id": sub.id})
        if spawn_turn is not None and sub.spawn_turn_id is None:
            await c.execute(text(
                "UPDATE subagent_run SET spawn_turn_id = :t, tool_use_id = IF(tool_use_id = '', :tu, tool_use_id) "
                "WHERE id = :id"), {"t": spawn_turn, "tu": tool_use_id or "", "id": sub.id})
            sub.spawn_turn_id = spawn_turn
        return sub

    # ── 턴 ─────────────────────────────────────────────────
    async def _open_turn(self, c: AsyncConnection, st: SessionState, b: Batch, *, pid: str | None, uuid: str | None,
                         origin: str, prompt: str | None, ts: datetime, by: str) -> int:
        if pid:
            r = (await c.execute(text("SELECT id, ended_at FROM turn WHERE prompt_id = :p"), {"p": pid})).first()
            if r:
                # 다시 읽는 중 — 이미 있는 턴. 닫힌 턴이어도 지금부터의 줄은 이 턴의 것이다.
                # (가장 최근의 열린 턴을 문맥으로 두면 옛 턴의 turn_duration이 그 턴을 닫는다 — 2단계 다시 읽기 시험에서 발견)
                # 닫힌 턴을 다시 닫는 것은 아무것도 바꾸지 않는다(ended_at IS NULL 조건) — duration만 비어 있으면 채운다
                st.remember(st.prompt_turns, pid, r[0], 256)
                st.open_turn = TurnRef(r[0], pid, ts, active=True)
                return r[0]
            o = st.open_turn
            if o and o.prompt_id is None and o.by_hook:  # hook이 먼저 연 턴 — promptId를 채운다
                await c.execute(text(
                    "UPDATE turn SET prompt_id = :p, prompt_uuid = :u, origin = :o, "
                    "prompt_text = COALESCE(prompt_text, :t) WHERE id = :id"),
                    {"p": pid, "u": await self._free_uuid(c, uuid, o.id), "o": origin, "t": prompt, "id": o.id})
                o.prompt_id = pid
                st.remember(st.prompt_turns, pid, o.id, 256)
                return o.id
        if st.open_turn:
            o = st.open_turn
            last = st.last_ts or o.started_at
            if o.active:
                reason = "no_signal"
            elif (ts - last).total_seconds() >= self.s.turn_abandon_s:
                # 응답 없이 1시간 넘게 열려 있던 입력 — 다음 입력에 합쳐진 것이 아니라 버려진 것(Esc가 첫 응답 전에
                # 눌리면 중단 표시 줄도 Stop hook도 남지 않는다 — 6단계 실측). 진짜 merged는 최대 56분(실측)
                reason = "abandoned"
            else:
                reason = "merged"
            await self._close_turn(c, st, b, reason, last if reason == "abandoned" else (st.last_ts or ts), by)
        st.seq += 1
        res = await c.execute(text(
            "INSERT INTO turn (session_id, seq, prompt_id, origin, prompt_uuid, prompt_text, started_at) "
            "VALUES (:s, :seq, :p, :o, :u, :t, :at)"),
            {"s": st.id, "seq": st.seq, "p": pid, "o": origin, "u": await self._free_uuid(c, uuid), "t": prompt, "at": ts})
        tid = res.lastrowid
        st.open_turn = TurnRef(tid, pid, ts, by_hook=(by == "hook"))
        if pid:
            st.remember(st.prompt_turns, pid, tid, 256)
        self.stats.turns_opened += 1
        b.turn_msgs.append({"type": "turn", "op": "open", "turn_id": tid, "session_id": st.id, "seq": st.seq,
                            "origin": origin, "project": st.project, "ts": ts.isoformat() + "Z", "by": by})
        return tid

    @staticmethod
    async def _copied_line(c: AsyncConnection, st: SessionState, uuid: str) -> bool:
        """이 줄이 다른 세션에서 복사해 온 줄인가 — 같은 uuid의 이벤트(프롬프트 줄 = start 이벤트)나 턴이 다른 세션에 있다.
        이벤트도 보는 것은 앞 세션 턴의 prompt_uuid가 비어 있을 수 있어서다(_free_uuid)."""
        r = (await c.execute(text("SELECT session_id FROM event WHERE uuid = :u"), {"u": uuid})).first()
        if r is None:
            r = (await c.execute(text("SELECT session_id FROM turn WHERE prompt_uuid = :u"), {"u": uuid})).first()
        return r is not None and r[0] != st.id

    @staticmethod
    async def _free_uuid(c: AsyncConnection, uuid: str | None, own: int | None = None) -> str | None:
        """turn.prompt_uuid는 UNIQUE다. 다른 턴이 이미 가진 uuid면 비운다(NULL) — 그 값 하나로 덩어리 전체가 막히면 안 된다
        (11-03: resume · fork 세션이 앞 세션 줄을 uuid째 복사해 와서 06:48부터 한 세션 적재가 몇 시간 막혔다)."""
        if not uuid:
            return None
        r = (await c.execute(text("SELECT id FROM turn WHERE prompt_uuid = :u"), {"u": uuid})).first()
        return uuid if r is None or r[0] == own else None

    async def _close_turn(self, c: AsyncConnection, st: SessionState, b: Batch, reason: str, ts: datetime, by: str,
                          *, turn_id: int | None = None, duration: int | None = None, note: str | None = None) -> int | None:
        tid = turn_id or (st.open_turn.id if st.open_turn else None)
        if tid is None:
            return None
        res = await c.execute(text(
            "UPDATE turn SET ended_at = GREATEST(:ts, started_at), end_reason = :r, closed_by = :by, "
            "duration_ms = COALESCE(:d, duration_ms) WHERE id = :id AND ended_at IS NULL"),
            {"ts": ts, "r": reason, "by": by, "d": duration, "id": tid})
        if res.rowcount:
            self.stats.turns_closed[reason] = self.stats.turns_closed.get(reason, 0) + 1
            b.turn_msgs.append({"type": "turn", "op": "close", "turn_id": tid, "session_id": st.id, "reason": reason,
                                "by": by, "project": st.project, "ts": ts.isoformat() + "Z"})
            b.closed.append((st.id, tid, reason, by, note))  # 커밋 뒤에 알린다 — 트랜잭션 안에서 부르면 닫히기 전을 읽는다
        elif duration is not None:  # 이미 다른 신호로 닫힘 — 소요 시간만 채운다
            await c.execute(text("UPDATE turn SET duration_ms = :d WHERE id = :id AND duration_ms IS NULL"),
                            {"d": duration, "id": tid})
        if st.open_turn and st.open_turn.id == tid:
            st.open_turn = None
        st.last_turn_id = tid
        return tid

    # ── 이벤트 · 메시지 버퍼 ───────────────────────────────────
    def _event(self, b: Batch, st: SessionState, *, uuid: str, ts: datetime, type: str, source: str = "transcript",
               turn_id: int | None = None, parent_uuid: str | None = None, message_id: str | None = None,
               subagent_id: int | None = None, tool_use_id: str | None = None, tool: str | None = None,
               target: str | None = None, status: str | None = None, payload: dict[str, Any] | None = None) -> None:
        target = self.mask.text(target)
        clipped, full = clip_target(target)
        payload = dict(payload or {})
        if full is not None:
            payload["target_full"] = full
        b.events.append({
            "uuid": uuid, "parent_uuid": parent_uuid, "session_id": st.id, "character_id": st.character_id,
            "turn_id": turn_id, "message_id": message_id, "subagent_id": subagent_id, "tool_use_id": tool_use_id,
            "source": source, "ts": ts, "type": type, "tool": (tool or None) and tool[:64], "target": clipped,
            "target_truncated": full is not None, "status": status,
            "payload": _json(payload) if payload else None,
        })

    def _message(self, b: Batch, d: dict[str, Any], turn_id: int | None, subagent_id: int | None, ts: datetime) -> None:
        m = d.get("message") or {}
        mid = m.get("id")
        if not mid:
            return
        u = m.get("usage") or {}
        row = {"id": mid, "turn_id": turn_id, "subagent_id": subagent_id, "model": (m.get("model") or "?")[:64],
               "stop_reason": m.get("stop_reason"), "request_id": d.get("requestId"),
               "ti": u.get("input_tokens") or 0, "to": u.get("output_tokens") or 0,
               "tr": u.get("cache_read_input_tokens") or 0, "tc": u.get("cache_creation_input_tokens") or 0,
               "at": ts}
        prev = b.messages.get(mid)
        if prev:  # 같은 응답의 다른 블록 줄 — usage는 같다. 더 큰 output · 있는 stop_reason만 반영
            prev["to"] = max(prev["to"], row["to"])
            prev["stop_reason"] = prev["stop_reason"] or row["stop_reason"]
        else:
            b.messages[mid] = row

    async def _flush(self, c: AsyncConnection, b: Batch) -> None:
        if b.messages:
            await c.execute(text(
                "INSERT INTO message (id, turn_id, subagent_id, model, stop_reason, request_id, token_input, "
                "token_output, token_cache_read, token_cache_creation, created_at) VALUES "
                "(:id, :turn_id, :subagent_id, :model, :stop_reason, :request_id, :ti, :to, :tr, :tc, :at) "
                "ON DUPLICATE KEY UPDATE token_output = GREATEST(token_output, VALUES(token_output)), "
                "stop_reason = COALESCE(stop_reason, VALUES(stop_reason)), turn_id = COALESCE(turn_id, VALUES(turn_id))"),
                list(b.messages.values()))
            self.stats.messages += len(b.messages)
        if b.events:
            await c.execute(text(
                "INSERT INTO event (uuid, parent_uuid, session_id, character_id, turn_id, message_id, subagent_id, "
                "tool_use_id, source, ts, type, tool, target, target_truncated, status, payload) VALUES "
                "(:uuid, :parent_uuid, :session_id, :character_id, :turn_id, :message_id, :subagent_id, :tool_use_id, "
                ":source, :ts, :type, :tool, :target, :target_truncated, :status, :payload) "
                "ON DUPLICATE KEY UPDATE id = id"), b.events)
            self.stats.events += len(b.events)

    # ── 덩어리 적용 ──────────────────────────────────────────
    async def skip_chunk(self, ch: Chunk) -> None:
        """마지막 수단 — 이 덩어리를 적재하지 않고 offset만 넘긴다(같은 실패가 너그러운 모드에서도 되풀이될 때, watcher).
        그 줄들은 DB에 없다. 파일 · 범위는 watcher가 로그와 알림으로 남긴다."""
        async with self.lock:
            async with self.engine.begin() as c:
                tf_id = await self._file(c, ch)
                await c.execute(text("UPDATE transcript_file SET read_offset = :o, inode = :i WHERE id = :id"),
                                {"o": ch.end, "i": ch.inode, "id": tf_id})
            self.sessions.pop(ch.key.cc_session_id, None)   # 메모리 문맥은 DB에서 다시 읽는다
            self.files[ch.key.path] = FileState(tf_id, ch.end, ch.inode)

    async def apply_chunk(self, ch: Chunk, tolerant: bool = False) -> list[tuple[int, str]]:
        """적재한다. 돌려주는 값: 너그러운 모드에서 버린 줄(offset, 이유) — 보통은 빈 목록."""
        async with self.lock:
            b = Batch()
            sid = ch.key.cc_session_id
            try:
                async with asyncio.timeout(self.s.ingest_timeout_s):
                    async with self.engine.begin() as c:
                        tf_id = await self._file(c, ch)
                        cwd = next((d.get("cwd") for _, d in ch.records if d.get("cwd")), None)
                        first_ts = next((_ts(d["timestamp"]) for _, d in ch.records if d.get("timestamp")), None)
                        st = await self._session(c, sid, cwd, ch.key.project_dir, first_ts,
                                                 None if ch.key.is_sub else tf_id)
                        if ch.key.is_sub:
                            await self._apply_sub(c, ch, st, b)
                        else:
                            await self._apply_main(c, ch, st, b, tolerant)
                        await self._flush(c, b)
                        last_uuid = next((d.get("uuid") for _, d in reversed(ch.records) if d.get("uuid")), None)
                        await c.execute(text(
                            "UPDATE transcript_file SET read_offset = :o, inode = :i, last_uuid = COALESCE(:u, last_uuid) "
                            "WHERE id = :id"), {"o": ch.end, "i": ch.inode, "u": last_uuid, "id": tf_id})
            except BaseException:
                # 롤백됐다 — 이 세션의 메모리 상태를 버리고 다음에 DB에서 다시 읽는다
                self.sessions.pop(sid, None)
                self.subs = {k: v for k, v in self.subs.items() if v.session_id != (st.id if "st" in locals() else -1)}
                # 파일 offset은 그대로 둔다 — 롤백이라 DB의 read_offset도 이 덩어리 앞이다. 전에는 지워서 실패할 때마다
                # 파일을 처음부터 다시 읽었다(큰 트랜스크립트면 재시도마다 수십 MB, 11-03)
                raise
            self.files[ch.key.path] = FileState(tf_id, ch.end, ch.inode)
            s = self.stats
            s.chunks += 1
            s.lines += len(ch.records)
            s.skipped_api += ch.skipped_api
            s.bad_lines += ch.bad_lines
            s.resets += int(ch.reset)
            if ch.bad_lines:
                log.warning("JSON 아닌 줄 %d개 건너뜀: %s", ch.bad_lines, ch.key.path)
        self._after_commit(b)
        if self.live and self.publish:
            await self._publish(b, st)
        return b.skipped

    def _after_commit(self, b: Batch) -> None:
        if self.live and self.on_turn_closed:
            for args in b.closed:
                self.on_turn_closed(*args)
        if self.live and self.on_subagents_changed:
            for sid in b.subs_done:
                self.on_subagents_changed(sid)
        if self.live and self.on_compact:
            for sid in b.compacts:
                self.on_compact(sid)
        if self.on_tool_result:
            for tuid, perm in b.tool_results:
                self.on_tool_result(tuid, perm)

    async def _apply_main(self, c: AsyncConnection, ch: Chunk, st: SessionState, b: Batch, tolerant: bool = False) -> None:
        for off, d in ch.records:
            if not tolerant:
                await self._main_record(c, ch.key, st, b, off, d)
                continue
            # 너그러운 모드(watcher가 같은 덩어리에서 여러 번 실패한 뒤) — 줄마다 SAVEPOINT. 실패한 줄만 버리고 나머지는 적재한다
            try:
                async with c.begin_nested():
                    await self._main_record(c, ch.key, st, b, off, d)
            except Exception as e:  # noqa: BLE001
                self.stats.skipped_records += 1
                b.skipped.append((off, f"{type(e).__name__}: {str(e)[:200]}"))
                log.warning("줄 건너뜀 %s @%d: %s: %s", ch.key.path, off, type(e).__name__, str(e)[:200])

    async def _main_record(self, c: AsyncConnection, key: FileKey, st: SessionState, b: Batch, off: int,
                           d: dict[str, Any]) -> None:
        t = d.get("type")
        uid = d.get("uuid") or _uuid5(key.path, off)
        ts = _ts(d.get("timestamp")) if d.get("timestamp") else (st.last_ts or _ts(None))
        par = d.get("parentUuid")
        if st.copying and t in ("user", "assistant", "system", "attachment"):
            # 복사 구간 — 앞 세션에 이미 있는 줄이다. 사람 프롬프트 줄만 _main_user가 보고 복사가 끝났는지 가린다
            # (복사 구간의 turn_duration이 새 세션의 열린 턴을 옛 시각으로 닫거나, 옛 응답이 새 턴에 붙지 않게)
            content = (d.get("message") or {}).get("content")
            if t != "user" or (isinstance(content, list) and any(
                    isinstance(x, dict) and x.get("type") == "tool_result" for x in content)):
                return
        if t == "user":
            await self._main_user(c, st, b, d, uid, ts, par)
        elif t == "assistant":
            # 열린 턴이 없으면 직전 턴 — hook(Stop)이 트랜스크립트보다 먼저 와서 턴을 닫은 뒤 늦게 쓰인 응답 줄
            # (실측: headless CC에서 Stop hook이 마지막 assistant 줄보다 먼저 도착)
            tid = st.open_turn.id if st.open_turn else st.last_turn_id
            if st.open_turn:
                st.open_turn.active = True
            self._message(b, d, tid, None, ts)
            if d.get("isApiErrorMessage"):
                # 11-11 — 종류(분류기 거부 · 한도 · 과부하 …)와 request id를 뽑아 남기고 브리지 로그에 한 줄(bridge/api_error.py)
                full = self.mask.text(_text_of(d["message"].get("content")))
                ce = classify_api_error(full, d.get("error"))
                log.warning("API 오류: 세션 %s · %s%s · %s", st.id, ce["kind"], f" [{ce['detail']}]" if ce["detail"] else "",
                            ce["request_id"] or "request id 없음")
                self._event(b, st, uuid=uid, ts=ts, type="error", turn_id=tid, parent_uuid=par, status="error",
                            payload={"error": d.get("error"), "text": full[:PREVIEW], "api_error": ce})
                await self._close_turn(c, st, b, "stop_failure", ts, "transcript")
            else:
                self._assistant_blocks(b, st, d, uid, ts, par, tid, None)
        elif t == "system":
            sub = d.get("subtype")
            if sub == "turn_duration":
                dur = d.get("durationMs")
                if st.open_turn:
                    tid = await self._close_turn(c, st, b, "stop", ts, "transcript", duration=dur)
                else:
                    tid = st.last_turn_id
                    if tid:
                        await self._close_turn(c, st, b, "stop", ts, "transcript", turn_id=tid, duration=dur)
                self._event(b, st, uuid=uid, ts=ts, type="stop", turn_id=tid, parent_uuid=par, status="idle",
                            payload={"durationMs": dur, "messageCount": d.get("messageCount")})
            elif sub == "compact_boundary":
                tid = st.open_turn.id if st.open_turn else None
                if tid:
                    await c.execute(text("UPDATE turn SET compacted = TRUE WHERE id = :id"), {"id": tid})
                self._event(b, st, uuid=uid, ts=ts, type="compact", turn_id=tid, parent_uuid=par,
                            payload={"compactMetadata": d.get("compactMetadata")})
                b.compacts.add(st.id)
        elif t == "ai-title":
            # CC가 붙이는 세션 제목 — 대화가 흘러가며 바뀐다. 같은 제목이 수천 번 반복되므로 바뀔 때만 쓴다
            title = (self.mask.text(str(d.get("aiTitle") or "")) or "").strip()[:255]
            if title and title != st.title:
                await c.execute(text("UPDATE character_session SET title = :t WHERE id = :id"), {"t": title, "id": st.id})
                st.title = title
        elif t == "queue-operation":
            op = d.get("operation")
            if op == "enqueue":
                self._bg_end(b, st, _text_of(d.get("content")) or str(d.get("content") or ""), ts)
            self._event(b, st, uuid=uid, ts=ts, type="queued", turn_id=st.open_turn.id if st.open_turn else None,
                        status="waiting" if op == "enqueue" else None,
                        payload={"op": op, "content": self.mask.deep(_text_of(d.get("content")) or d.get("content"), QUEUE_TEXT)})
        elif t == "attachment" and (d.get("attachment") or {}).get("type") == "queued_command":
            a = d["attachment"]
            self._bg_end(b, st, _text_of(a.get("prompt")) or str(a.get("prompt") or ""), ts)
            self._event(b, st, uuid=uid, ts=ts, type="queued", turn_id=st.open_turn.id if st.open_turn else None,
                        parent_uuid=par, payload={"op": "delivered", "mode": a.get("commandMode"),
                                                  "prompt": self.mask.deep(_text_of(a.get("prompt")) or a.get("prompt"), QUEUE_TEXT)})
        if d.get("timestamp") and not st.copying:      # 복사 줄의 옛 시각으로 되돌아가지 않게
            st.last_ts = ts

    async def _main_user(self, c: AsyncConnection, st: SessionState, b: Batch, d: dict[str, Any], uid: str,
                         ts: datetime, par: str | None) -> None:
        msg = d.get("message") or {}
        content = msg.get("content")
        pid = d.get("promptId")
        blocks = content if isinstance(content, list) else []
        results = [x for x in blocks if isinstance(x, dict) and x.get("type") == "tool_result"]
        if results:
            tid = await self._turn_of_prompt(c, st, pid)
            tur = d.get("toolUseResult")
            for i, r in enumerate(results):
                body = r.get("content")
                chars = len(body) if isinstance(body, str) else sum(len(x.get("text", "")) for x in body or [] if isinstance(x, dict))
                err = bool(r.get("is_error"))
                pl: dict[str, Any] = {"chars": chars, "is_error": err}
                if err:
                    pl["error_preview"] = (self.mask.text(_text_of(body)) or "")[:ERR_PREVIEW]
                tuid = r.get("tool_use_id")
                if tuid:
                    b.tool_results.append((tuid, d.get("permissionDecision")))
                self._event(b, st, uuid=uid if i == 0 else _uuid5(uid, i), ts=ts, type="tool_result", turn_id=tid,
                            parent_uuid=par, tool_use_id=tuid, tool=st.tool_names.get(tuid or ""),
                            status="error" if err else "done", payload=pl)
                # 백그라운드 Bash(backgroundTaskId) · Monitor(taskId) — 턴이 끝나도 돈다. 끝은 <task-notification>(_bg_end).
                # 화면이 "IDLE인데 일이 돈다"를 보이려고 남긴다(11-06 — Sonnet 판정이 도는데 캐릭터가 자고 있었다)
                bg = isinstance(tur, dict) and len(results) == 1 and (
                    tur.get("backgroundTaskId") or (st.tool_names.get(tuid or "") == "Monitor" and tur.get("taskId")))
                # TaskStop으로 멈춘 백그라운드는 <task-notification>이 오지 않는다 — 결과의 task_id로 끝을 남긴다
                # (11-06: 멈춘 시험 스크립트가 "백그라운드 1"로 남아 답을 마친 뒤에도 캐릭터가 기다림으로 보였다)
                if (isinstance(tur, dict) and len(results) == 1 and tur.get("task_id")
                        and st.tool_names.get(tuid or "") in ("TaskStop", "KillShell") and not err):
                    self._bg_end_task(b, st, str(tur["task_id"]), "stopped", ts, tuid)
                if bg:
                    tool = st.tool_names.get(tuid or "") or "Bash"
                    desc = (st.agent_inputs.get(tuid or "") or {}).get("description")
                    self._event(b, st, uuid=_uuid5(st.id, bg, "bg_start"), ts=ts, type="bg_start", turn_id=tid,
                                tool_use_id=tuid, tool=tool, target=str(bg), status="working",
                                payload={"description": self.mask.text(str(desc))[:200] if desc else None})
                # Agent 결과 — 서브에이전트가 떴다(async_launched). 여기서 행을 만들고 이 턴을 spawn_turn으로
                if isinstance(tur, dict) and tur.get("agentId") and len(results) == 1:
                    inp = st.agent_inputs.get(tuid or "", {})
                    await self._sub(c, tur["agentId"], st, tool_use_id=tuid, spawn_turn=tid, info={
                        "agent_type": inp.get("subagent_type") or tur.get("agentType"),
                        "mode": "background" if inp.get("run_in_background") or tur.get("status") == "async_launched" else "foreground",
                        "description": inp.get("description") or tur.get("description")})
            return
        s = _text_of(content)
        if uid and ((st.copying and st.copy_floor and ts < st.copy_floor) or await self._copied_line(c, st, uid)):
            # resume · fork로 만든 세션이 앞 세션 기록을 uuid째 복사해 시작한다. 그 기록은 원래 세션에 이미 있다 — 건너뛴다.
            # promptId는 빠진 채(백그라운드 fork, 11-03 bb19f9d2)일 수도, 새 프롬프트의 promptId로 바뀐 채
            # (claude --fork-session, 11-05 실측)일 수도 있다 — 그래서 promptId가 아니라 uuid로 가린다.
            # 뒤따르는 복사 줄(응답 · 도구 결과 · turn_duration · 중단 표시)도 첫 새 프롬프트까지 건너뛴다(_main_record).
            # 복사 줄은 원래 시각을 그대로 갖는다 — 복사 구간 앞의 이 세션 줄(queue-operation 등)보다 이르면, DB에 같은
            # uuid가 없어도(이벤트를 남기지 않는 같은 턴의 둘째 user 줄) 복사 줄로 본다
            if not st.copying:
                st.copy_floor = st.last_ts
            self.stats.copied_prompts += 1
            st.copying = True
            return
        st.copying = False
        if d.get("isCompactSummary"):
            tid = await self._turn_of_prompt(c, st, pid)
            if tid:
                await c.execute(text("UPDATE turn SET compacted = TRUE WHERE id = :id"), {"id": tid})
            return
        if s.startswith(INTERRUPT):
            tid = await self._turn_of_prompt(c, st, pid)
            self._event(b, st, uuid=uid, ts=ts, type="interrupted", turn_id=tid, parent_uuid=par, status="idle",
                        payload={"text": s[:80]})
            await self._close_turn(c, st, b, "interrupted", ts, "transcript", turn_id=tid)
            return
        known = await self._turn_of_prompt(c, st, pid) if pid else None
        origin = await self._resolve_origin(c, st, d, s)
        if known is not None and pid:
            # 이미 있는 턴의 줄 — 같은 턴의 다른 user 줄(이미지 설명 등)이거나, 다시 읽는 중에 지나가는 옛 턴의 프롬프트.
            # 어느 쪽이든 지금부터의 줄은 이 턴의 것이다(닫힌 턴이어도). 최근의 열린 턴을 문맥으로 두면
            # 옛 턴의 turn_duration이 그 턴을 닫는다 — 2단계 다시 읽기 시험에서 발견
            if not (st.open_turn and st.open_turn.id == known):
                st.open_turn = TurnRef(known, pid, ts, active=True)
            # 사람의 글이 뒤에 오면 턴의 출처 · 본문을 바꾼다
            if origin == "human":
                await c.execute(text(
                    "UPDATE turn SET origin = 'human', prompt_text = :t, prompt_uuid = COALESCE(:u, prompt_uuid) "
                    "WHERE id = :id AND origin = 'meta'"),
                    {"t": self.mask.text(s), "u": await self._free_uuid(c, uid, known), "id": known})
            return
        if not pid and uid:
            # promptId 없는 사람 줄 — 이 uuid의 턴이 이 세션에 이미 있으면 다시 읽는 중(inode 변경 · 잘림) — 그 턴을 문맥으로
            # (다른 세션의 턴이면 위에서 복사 줄로 걸렀다)
            r = (await c.execute(text("SELECT id, session_id FROM turn WHERE prompt_uuid = :u"), {"u": uid})).first()
            if r is not None and r[1] == st.id:
                st.open_turn = TurnRef(r[0], None, ts, active=True)
                return
        tid = await self._open_turn(c, st, b, pid=pid, uuid=uid, origin=origin, prompt=self.mask.text(s), ts=ts,
                                    by="transcript")
        self._event(b, st, uuid=uid, ts=ts, type="start", turn_id=tid, parent_uuid=par, status="working",
                    target=s[:200], payload={"origin": origin, "source": d.get("promptSource"),
                                             "turnPosition": d.get("turnPosition")})
        if origin == "task_notification":
            await self._notification(c, st, b, s, uid, ts, tid)

    async def _resolve_origin(self, c: AsyncConnection, st: SessionState, d: dict[str, Any], s: str) -> str:
        """_origin + 보낸 쪽 확인. <agent-message from="X">의 X가 이 세션의 서브에이전트면 subagent_message,
        아니면 agent_message(다른 세션). 문장 모양으로는 못 가른다 — 같은 결과 전달이 트랜스크립트에는
        "Another Claude session sent a message: <agent-message …"로, hook에는 "<agent-message …"로 왔다(4단계 실측)."""
        origin = self._origin(d, s)
        m = FROM_RE.search(s[:300])
        if m and origin in ("agent_message", "subagent_message", "meta", "human"):
            aid = m.group(1)
            own = aid in self.subs or (await c.execute(text(
                "SELECT 1 FROM subagent_run WHERE agent_id = :a AND session_id = :s"), {"a": aid, "s": st.id})).first()
            origin = "subagent_message" if own else "agent_message"
        return origin

    @staticmethod
    def _origin(d: dict[str, Any], s: str) -> str:
        kind = (d.get("origin") or {}).get("kind")
        if s.lstrip().startswith("<task-notification") or d.get("turnOrigin") == "task_notification" or kind == "task-notification":
            return "task_notification"
        # 서브에이전트가 돌려준 결과(hand-back) — 내용으로 가른다. isMeta가 붙어 올 때도, 사람 입력(origin human)처럼
        # 올 때도 있었다(4단계 실측). 다른 세션의 메시지는 "Another Claude session sent a message: <agent-message …"
        if s.lstrip().startswith("<agent-message"):
            return "subagent_message"
        # FOREMAN이 넣은 인계 요청 · 인계 글(11-05, bridge/handoff.py) — 여러 줄이라 <pasted_content>로 감싸여 온다
        head = s.lstrip()[:120]
        if "[FOREMAN 인계 요청 r=" in head:
            return "handoff"
        if "[FOREMAN 인계 r=" in head:
            return "handoff_in"
        if MGR_ASK in head and MGR_ASK_HUMAN not in head:
            return "manager_ask"
        if d.get("isMeta"):
            return "agent_message" if AGENT_MSG in s[:120] else "meta"
        return "human"

    def _bg_end(self, b: Batch, st: SessionState, s: str, ts: datetime) -> None:
        """백그라운드 작업이 끝났다 — <task-notification>의 status. 같은 알림이 큐(enqueue) · 첨부(queued_command) ·
        사람 줄 세 곳 중 어디로든 올 수 있어 uuid를 작업 id로 정해 한 번만 남긴다. Monitor의 중간 이벤트는 status가 없다."""
        if "<task-notification" not in (s or "")[:300]:
            return
        tags = {k: v.strip() for k, v in TAG_RE.findall(s)}
        task, status = tags.get("task-id"), tags.get("status")
        if not task or not status or status == "running":
            return
        self._bg_end_task(b, st, task, status, ts, tags.get("tool-use-id"))

    def _bg_end_task(self, b: Batch, st: SessionState, task: str, status: str, ts: datetime, tuid: str | None) -> None:
        u = _uuid5(st.id, task, "bg_end")
        # 같은 묶음에 같은 uuid가 둘이면 여러 행 INSERT … ON DUPLICATE가 MySQL 1869로 묶음째 실패한다(11-06 시험) — 묶음 안에서 한 번만
        if any(e["uuid"] == u for e in b.events):
            return
        self._event(b, st, uuid=u, ts=ts, type="bg_end", target=task,
                    tool_use_id=tuid, status="done", payload={"status": status[:20]})

    async def _notification(self, c: AsyncConnection, st: SessionState, b: Batch, s: str, uid: str, ts: datetime,
                            tid: int) -> None:
        self._bg_end(b, st, s, ts)
        tags = {k: v.strip() for k, v in TAG_RE.findall(s)}
        aid = tags.get("task-id")
        if not aid or "tool-use-id" not in tags:
            return  # Bash 백그라운드 작업 · Monitor 이벤트 — 서브에이전트가 아니다
        sub = self.subs.get(aid)
        if sub is None:
            r = (await c.execute(text("SELECT id, session_id, spawn_turn_id FROM subagent_run WHERE agent_id = :a"),
                                 {"a": aid})).first()
            if not r:
                return
            sub = self.subs[aid] = SubState(r[0], r[1], r[2])

        def num(k: str) -> int | None:
            v = tags.get(k)
            return int(v) if v and v.isdigit() else None

        await c.execute(text(
            "UPDATE subagent_run SET status = COALESCE(:st, status), result_turn_id = :rt, "
            "reported_tokens = COALESCE(:rtk, reported_tokens), reported_tool_uses = COALESCE(:rtu, reported_tool_uses), "
            "reported_duration_ms = COALESCE(:rd, reported_duration_ms) WHERE id = :id"),
            {"st": NOTIF_STATUS.get(tags.get("status", "")), "rt": tid, "rtk": num("subagent_tokens"),
             "rtu": num("tool_uses"), "rd": num("duration_ms"), "id": sub.id})
        b.subs_done.add(st.id)
        self._event(b, st, uuid=_uuid5(uid, "subagent_stop"), ts=ts, type="subagent_stop", turn_id=tid,
                    subagent_id=sub.id, tool_use_id=tags.get("tool-use-id"), status="done",
                    payload={"status": tags.get("status"), "summary": self.mask.text(tags.get("summary", ""))[:PREVIEW],
                             "subagent_tokens": num("subagent_tokens")})

    def _assistant_blocks(self, b: Batch, st: SessionState, d: dict[str, Any], uid: str, ts: datetime,
                          par: str | None, tid: int | None, sub_id: int | None) -> None:
        mid = (d.get("message") or {}).get("id")
        for i, blk in enumerate((d.get("message") or {}).get("content") or []):
            if not isinstance(blk, dict):
                continue
            u = uid if i == 0 else _uuid5(uid, i)
            k = blk.get("type")
            if k == "text":
                self._event(b, st, uuid=u, ts=ts, type="assistant_msg", turn_id=tid, parent_uuid=par, message_id=mid,
                            subagent_id=sub_id, status="working",
                            payload={"block": "text", "text": self.mask.text(blk.get("text", ""))})
            elif k == "thinking":
                self._event(b, st, uuid=u, ts=ts, type="assistant_msg", turn_id=tid, parent_uuid=par, message_id=mid,
                            subagent_id=sub_id, status="working",
                            payload={"block": "thinking", "chars": len(blk.get("thinking") or "")})
            elif k == "tool_use":
                name, inp, tuid = blk.get("name") or "?", blk.get("input") or {}, blk.get("id")
                if tuid:
                    st.remember(st.tool_names, tuid, name)
                    if name == "Agent" or name == "Monitor" or (name == "Bash" and inp.get("run_in_background")):
                        # Agent는 서브에이전트 행에, 백그라운드 Bash · Monitor는 bg_start 이벤트에 설명을 단다
                        st.remember(st.agent_inputs, tuid, {k2: inp.get(k2) for k2 in
                                                            ("subagent_type", "run_in_background", "description")}, 512)
                self._event(b, st, uuid=u, ts=ts, type="tool_use", turn_id=tid, parent_uuid=par, message_id=mid,
                            subagent_id=sub_id, tool_use_id=tuid, tool=name, status="working",
                            target=_target_of(name, inp), payload={"input": self.mask.deep(inp, TEXT_CLIP)})

    async def _apply_sub(self, c: AsyncConnection, ch: Chunk, st: SessionState, b: Batch) -> None:
        key = ch.key
        meta = read_meta(key)
        sub = await self._sub(c, key.agent_id or "", st, tool_use_id=meta.get("toolUseId"), info={
            "agent_type": meta.get("agentType"),
            "mode": "fork" if meta.get("isFork") else (meta.get("requestShape") or "background"),
            "spawn_depth": meta.get("spawnDepth"), "description": meta.get("description"),
            "status": "done" if meta.get("finished") else "running"})
        tid = sub.spawn_turn_id
        first_ts = last_ts = None
        if ch.start == 0 and ch.records:
            d0 = ch.records[0][1]
            first_ts = _ts(d0.get("timestamp"))
            self._event(b, st, uuid=_uuid5(key.path, "start"), ts=first_ts, type="subagent_start", turn_id=tid,
                        subagent_id=sub.id, tool_use_id=meta.get("toolUseId"), status="working",
                        payload={"agentType": meta.get("agentType"), "description": meta.get("description")})
        for off, d in ch.records:
            t = d.get("type")
            uid = d.get("uuid") or _uuid5(key.path, off)
            ts = _ts(d.get("timestamp")) if d.get("timestamp") else (last_ts or _ts(None))
            last_ts = ts
            first_ts = first_ts or ts
            par = d.get("parentUuid")
            if t == "assistant":
                self._message(b, d, tid, sub.id, ts)
                self._assistant_blocks(b, st, d, uid, ts, par, tid, sub.id)
            elif t == "user":
                content = (d.get("message") or {}).get("content")
                for i, r in enumerate(x for x in (content if isinstance(content, list) else [])
                                      if isinstance(x, dict) and x.get("type") == "tool_result"):
                    body = r.get("content")
                    chars = len(body) if isinstance(body, str) else sum(len(x.get("text", "")) for x in body or [] if isinstance(x, dict))
                    err = bool(r.get("is_error"))
                    pl: dict[str, Any] = {"chars": chars, "is_error": err}
                    if err:
                        pl["error_preview"] = (self.mask.text(_text_of(body)) or "")[:ERR_PREVIEW]
                    if r.get("tool_use_id"):
                        b.tool_results.append((r["tool_use_id"], d.get("permissionDecision")))
                    self._event(b, st, uuid=uid if i == 0 else _uuid5(uid, i), ts=ts, type="tool_result", turn_id=tid,
                                parent_uuid=par, subagent_id=sub.id, tool_use_id=r.get("tool_use_id"),
                                tool=st.tool_names.get(r.get("tool_use_id") or ""), status="error" if err else "done",
                                payload=pl)
        await c.execute(text(
            "UPDATE subagent_run SET started_at = COALESCE(started_at, :f), ended_at = GREATEST(COALESCE(ended_at, :l), :l), "
            "status = IF(:fin AND status IN ('running', 'stale'), 'done', IF(status = 'stale', 'running', status)) "
            "WHERE id = :id"),
            {"f": first_ts, "l": last_ts or first_ts, "fin": bool(meta.get("finished")), "id": sub.id})
        if meta.get("finished"):
            b.subs_done.add(st.id)

    async def fill_titles(self) -> int:
        """제목이 빈 세션(0011 이전에 적재)에 트랜스크립트의 마지막 ai-title을 채운다. 재적재가 아니라 빈 칸 채우기."""
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cs.id, tf.path FROM character_session cs JOIN transcript_file tf ON tf.id = cs.transcript_file_id "
                "WHERE cs.title IS NULL"))).all()
        n = 0
        for sess_id, path in rows:
            title = await asyncio.to_thread(_last_ai_title, path)
            if not title:
                continue
            title = (self.mask.text(title) or "").strip()[:255]
            async with self.engine.begin() as c:
                await c.execute(text("UPDATE character_session SET title = :t WHERE id = :id AND title IS NULL"),
                                {"t": title, "id": sess_id})
            for st in self.sessions.values():
                if st.id == sess_id:
                    st.title = title
            n += 1
        return n

    # ── 사후 연결 · 정리 ──────────────────────────────────────
    async def link(self) -> dict[str, int]:
        """띄운 턴을 늦게 안 서브에이전트의 메시지 · 이벤트에 턴을 채우고, 토큰 합계를 다시 낸다."""
        async with self.lock:
            async with asyncio.timeout(self.s.ingest_timeout_s):
                async with self.engine.begin() as c:
                    r1 = await c.execute(text(
                        "UPDATE subagent_run sr JOIN event e ON e.tool_use_id = sr.tool_use_id AND e.type = 'tool_use' "
                        "AND e.subagent_id IS NULL SET sr.spawn_turn_id = e.turn_id "
                        "WHERE sr.spawn_turn_id IS NULL AND e.turn_id IS NOT NULL AND sr.tool_use_id <> ''"))
                    r2 = await c.execute(text(
                        "UPDATE message m JOIN subagent_run sr ON sr.id = m.subagent_id SET m.turn_id = sr.spawn_turn_id "
                        "WHERE m.turn_id IS NULL AND sr.spawn_turn_id IS NOT NULL"))
                    r3 = await c.execute(text(
                        "UPDATE event e JOIN subagent_run sr ON sr.id = e.subagent_id SET e.turn_id = sr.spawn_turn_id "
                        "WHERE e.turn_id IS NULL AND sr.spawn_turn_id IS NOT NULL"))
                    r4 = await c.execute(text(
                        "UPDATE subagent_run sr JOIN (SELECT subagent_id, SUM(token_input) ti, SUM(token_output) tout, "
                        "SUM(token_cache_read) tr, SUM(token_cache_creation) tc FROM message WHERE subagent_id IS NOT NULL "
                        "GROUP BY subagent_id) x ON x.subagent_id = sr.id SET sr.token_input = x.ti, sr.token_output = x.tout, "
                        "sr.token_cache_read = x.tr, sr.token_cache_creation = x.tc"))
            self.subs.clear()  # spawn_turn을 DB에서 다시 읽게
            return {"spawn_turn": r1.rowcount, "message_turn": r2.rowcount, "event_turn": r3.rowcount,
                    "token_sum": r4.rowcount}

    async def sweep(self, now: datetime | None = None) -> int:
        """살아 있는 프로세스가 없는 세션의 열린 턴을 닫고 세션을 떼어 놓는다. 정지(T)된 프로세스는 살아 있는 것이다."""
        live = live_sessions(self.s.sessions_dir)
        now = now or datetime.now(UTC).replace(tzinfo=None)
        idle = self.s.idle_close_s
        closed = 0
        async with self.lock:
            async with asyncio.timeout(self.s.ingest_timeout_s):
                async with self.engine.begin() as c:
                    rows = (await c.execute(text(
                        "SELECT cs.id, cs.cc_session_id, cs.detached_at, cs.pid, "
                        "(SELECT MAX(ts) FROM event e WHERE e.session_id = cs.id) AS last_ts, "
                        "EXISTS(SELECT 1 FROM event e WHERE e.session_id = cs.id AND e.source = 'hook') AS hooked, "
                        "(SELECT t.id FROM turn t WHERE t.session_id = cs.id AND t.ended_at IS NULL ORDER BY t.seq DESC LIMIT 1) AS open_turn "
                        "FROM character_session cs WHERE cs.cc_session_id IS NOT NULL"))).all()
                    # 기록도 끝 신호도 없이 오래된 running 서브에이전트 — 묶음 알림이 영원히 기다리지 않게(실측: 펫퍼민트에
                    # 10-15~10-19의 7개가 running으로 남아 있었다). 새로 알릴 일이 아니므로 알린 것으로 표시한다
                    await c.execute(text(
                        "UPDATE subagent_run SET status = 'stale', notified_at = COALESCE(notified_at, UTC_TIMESTAMP(3)) "
                        "WHERE status = 'running' AND COALESCE(ended_at, started_at) < :cut"),
                        {"cut": now - timedelta(seconds=self.s.subagent_stale_s)})
                    b = Batch()
                    for sess_id, sid, detached_at, pid, last_ts, hooked, open_turn in rows:
                        ls = live.get(sid)
                        if ls is not None:
                            if pid != ls.pid or detached_at is not None:
                                await c.execute(text("UPDATE character_session SET pid = :p, detached_at = NULL WHERE id = :id"),
                                                {"p": ls.pid, "id": sess_id})
                            # 프로세스는 살아 있는데 CC가 일하지 않고(busy 아님 · 정지 아님) 열린 턴이 1시간 넘게 조용하다 —
                            # 끝 신호 없이 버려진 턴(Esc가 첫 응답 전에 눌린 경우 등). 마지막 활동 시각으로 닫는다
                            if open_turn and ls.state != "T" and _status(self.s.sessions_dir, ls.pid) not in (None, "busy"):
                                tlast = (await c.execute(text(
                                    "SELECT COALESCE((SELECT MAX(e.ts) FROM event e WHERE e.turn_id = t.id), t.started_at) "
                                    "FROM turn t WHERE t.id = :t"), {"t": open_turn})).scalar()
                                if tlast and (now - tlast).total_seconds() >= self.s.turn_abandon_s:
                                    res = await c.execute(text(
                                        "UPDATE turn SET ended_at = GREATEST(:ts, started_at), end_reason = 'abandoned', "
                                        "closed_by = 'sweep' WHERE id = :id AND ended_at IS NULL"), {"ts": tlast, "id": open_turn})
                                    if res.rowcount:
                                        closed += 1
                                        self.stats.turns_closed["abandoned"] = self.stats.turns_closed.get("abandoned", 0) + 1
                                        b.closed.append((sess_id, open_turn, "abandoned", "sweep", None))
                                        b.turn_msgs.append({"type": "turn", "op": "close", "turn_id": open_turn,
                                                            "session_id": sess_id, "reason": "abandoned", "by": "sweep",
                                                            "ts": tlast.isoformat() + "Z"})
                                        if (st_ := self.sessions.get(sid)) and st_.open_turn and st_.open_turn.id == open_turn:
                                            st_.open_turn = None
                                            st_.last_turn_id = open_turn
                            continue
                        quiet = last_ts is None or (now - last_ts).total_seconds() > idle
                        if not quiet:
                            continue
                        end = last_ts or now
                        if open_turn:
                            st = self.sessions.get(sid)
                            reason = "process_lost" if hooked else "session_end"
                            res = await c.execute(text(
                                "UPDATE turn SET ended_at = GREATEST(:ts, started_at), end_reason = :r, closed_by = 'sweep' "
                                "WHERE id = :id AND ended_at IS NULL"), {"ts": end, "r": reason, "id": open_turn})
                            if res.rowcount:
                                closed += 1
                                self.stats.turns_closed[reason] = self.stats.turns_closed.get(reason, 0) + 1
                                b.closed.append((sess_id, open_turn, reason, "sweep", None))
                                b.turn_msgs.append({"type": "turn", "op": "close", "turn_id": open_turn,
                                                    "session_id": sess_id, "reason": reason, "by": "sweep",
                                                    "ts": end.isoformat() + "Z"})
                            if st and st.open_turn and st.open_turn.id == open_turn:
                                st.open_turn = None
                                st.last_turn_id = open_turn
                        if detached_at is None:
                            await c.execute(text("UPDATE character_session SET detached_at = :ts WHERE id = :id"),
                                            {"ts": end, "id": sess_id})
                            # 서브에이전트는 부모 프로세스 안에서 돈다 — 부모가 없으면 끝난 것
                            await c.execute(text(
                                "UPDATE subagent_run SET status = 'stopped' WHERE session_id = :id AND status = 'running'"),
                                {"id": sess_id})
                            if (st := self.sessions.get(sid)):
                                st.detached = True
        self._after_commit(b)
        if self.live and self.publish:
            for m in b.turn_msgs:
                self.publish(m)
        return closed

    async def ids_for(self, p: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
        """hook 입력(session_id · cwd · transcript_path · prompt_id)으로 (세션, 캐릭터, 턴) id — 5단계 판정 기록용."""
        sid = p.get("session_id")
        if not sid:
            return None, None, None
        st = self.sessions.get(sid)
        if st is None:
            tp = p.get("transcript_path") or ""
            async with self.lock:
                async with asyncio.timeout(self.s.db_query_timeout_s * 2):
                    async with self.engine.begin() as c:
                        st = await self._session(c, sid, p.get("cwd"), Path(tp).parent.name if tp else "",
                                                 datetime.now(UTC).replace(tzinfo=None), None)
        turn = None
        pid = p.get("prompt_id")
        if pid and pid in st.prompt_turns:
            turn = st.prompt_turns[pid]
        elif st.open_turn:
            turn = st.open_turn.id
        return st.id, st.character_id, turn

    # ── hook ────────────────────────────────────────────────
    HOOK_EVENT = {"UserPromptSubmit": "start", "Stop": "stop", "StopFailure": "error", "SessionEnd": "session_end",
                  "SubagentStart": "subagent_start", "SubagentStop": "subagent_stop"}

    async def apply_hook(self, name: str, p: dict[str, Any]) -> None:
        sid = p.get("session_id")
        if not sid or name not in self.HOOK_EVENT:
            return
        now = datetime.now(UTC).replace(tzinfo=None)
        tp = p.get("transcript_path") or ""
        project_dir = Path(tp).parent.name if tp else ""
        b = Batch()
        human_prompt: str | None = None
        async with self.lock:
            try:
                async with asyncio.timeout(self.s.db_query_timeout_s * 2):
                    async with self.engine.begin() as c:
                        st = await self._session(c, sid, p.get("cwd"), project_dir, now, None)
                        st.hook_seen = True
                        tid = st.open_turn.id if st.open_turn else None
                        sub_id = None
                        hook_type = self.HOOK_EVENT[name]
                        if name == "UserPromptSubmit":
                            # 겹침 알림(11-06) — 사람이 넣은 것(받은 인계 포함)만. 대기열 입력도 hook이 한 번씩 온다
                            if self._origin({}, p.get("prompt") or "") in ("human", "handoff_in"):
                                human_prompt = self.mask.text(p.get("prompt"))
                            o = st.open_turn
                            if o is not None:
                                # 턴이 열려 있다 — 트랜스크립트가 이미 연 이 프롬프트이거나, 바쁠 때 보낸 입력(대기열 →
                                # 같은 턴에 전달). 후자에도 UserPromptSubmit이 불린다(3단계 실측). 새 턴을 열지 않는다.
                                # (시간 창으로 가르던 것은 15초 넘은 턴에 대기열 입력이 오면 진행 중인 턴을 닫았다)
                                tid = o.id
                                if o.prompt_id and (now - o.started_at).total_seconds() >= 15:
                                    hook_type = "queued"
                            else:
                                # 출처는 프롬프트 내용으로 — 서브에이전트 결과 전달은 트랜스크립트에 프롬프트 줄 없이
                                # hook으로만 오는 경우가 있었다(4단계 실측, 턴이 human으로 남아 개별 알림이 나갔다)
                                tid = await self._open_turn(c, st, b, pid=None, uuid=None,
                                                            origin=await self._resolve_origin(c, st, {}, p.get("prompt") or ""),
                                                            prompt=self.mask.text(p.get("prompt")), ts=now, by="hook")
                        elif name == "Stop":
                            tid = await self._close_turn(c, st, b, "stop", now, "hook",
                                                         note=p.get("last_assistant_message"))
                        elif name == "StopFailure":
                            tid = await self._close_turn(c, st, b, "stop_failure", now, "hook")
                        elif name == "SessionEnd":
                            tid = await self._close_turn(c, st, b, "session_end", now, "hook")
                            await c.execute(text("UPDATE character_session SET detached_at = :ts WHERE id = :id"),
                                            {"ts": now, "id": st.id})
                            st.detached = True
                        elif name in ("SubagentStart", "SubagentStop") and p.get("agent_id"):
                            # agent_type이 빈 SubagentStop은 CC 내부 보조 에이전트다 — Start도 트랜스크립트 파일도 없다(4단계 실측).
                            # hook만으로는 행을 만들지 않는다: Stop은 있는 행만 갱신, Start는 종류가 있을 때만 만든다
                            known = p["agent_id"] in self.subs or (await c.execute(text(
                                "SELECT 1 FROM subagent_run WHERE agent_id = :a"), {"a": p["agent_id"]})).first() is not None
                            if known or (name == "SubagentStart" and p.get("agent_type")):
                                sub = await self._sub(c, p["agent_id"], st, info={"agent_type": p.get("agent_type") or None})
                                sub_id = sub.id
                                if name == "SubagentStop":
                                    await c.execute(text(
                                        "UPDATE subagent_run SET status = IF(status = 'running', 'done', status) WHERE id = :id"),
                                        {"id": sub.id})
                                    b.subs_done.add(st.id)
                        keep = {k: p.get(k) for k in ("hook_event_name", "reason", "error", "agent_type",
                                                      "stop_hook_active", "permission_mode") if p.get(k) is not None}
                        self._event(b, st, uuid=str(uuidlib.uuid4()), ts=now, type=hook_type, source="hook",
                                    turn_id=tid, subagent_id=sub_id, payload=keep or None)
                        await self._flush(c, b)
            except BaseException:
                self.sessions.pop(sid, None)
                raise
        self._after_commit(b)
        if self.live and self.on_human_prompt and human_prompt:
            try:
                self.on_human_prompt(st.id, sid, human_prompt, now)
            except Exception as e:  # noqa: BLE001 — 알림이 적재를 막으면 안 된다
                log.warning("겹침 알림 예약 실패: %s", type(e).__name__)
        if self.live and self.publish:
            await self._publish(b, st)

    # ── WS ─────────────────────────────────────────────────
    async def _publish(self, b: Batch, st: SessionState) -> None:
        for m in b.turn_msgs:
            self.publish(m)
        if not b.events:
            return
        uuids = [e["uuid"] for e in b.events][-500:]
        try:
            async with asyncio.timeout(self.s.db_query_timeout_s):
                async with self.engine.connect() as c:
                    ids = dict((await c.execute(text("SELECT uuid, id FROM event WHERE uuid IN :u").bindparams(
                        _expanding("u")), {"u": uuids})).all())
        except Exception:  # noqa: BLE001 — 화면용. 못 가져오면 id 없이 보낸다
            ids = {}
        for e in b.events[-500:]:
            pl = e["payload"]
            self.publish({"type": "event", "event": {
                "id": ids.get(e["uuid"]), "source": e["source"], "type": e["type"], "tool": e["tool"],
                "target": (e["target"] or "")[:200] or None, "status": e["status"], "turn_id": e["turn_id"],
                "session_id": e["session_id"], "subagent_id": e["subagent_id"], "project": st.project,
                "ts": e["ts"].isoformat(timespec="milliseconds") + "Z",
                "summary": _summary(e["type"], pl)}})

    async def stats_snapshot(self) -> dict[str, Any]:
        return self.stats.__dict__ | {"turns_closed": dict(self.stats.turns_closed), "live": self.live}


def _last_ai_title(path: str, tail: int = 4 << 20, whole_max: int = 64 << 20) -> str | None:
    """트랜스크립트의 마지막 ai-title. 끝 4MB를 먼저 보고, 없으면 작은 파일만 처음부터."""
    import json
    import os
    try:
        size = os.path.getsize(path)
    except OSError:
        return None

    def scan(data: bytes) -> str | None:
        last = None
        for raw in data.split(b"\n"):
            if b'"type":"ai-title"' in raw[:200]:
                try:
                    last = json.loads(raw).get("aiTitle") or last
                except ValueError:
                    pass
        return last

    with open(path, "rb") as f:
        f.seek(max(0, size - tail))
        t = scan(f.read())
        if t or size <= tail or size > whole_max:
            return t
        f.seek(0)
        return scan(f.read())


def _summary(type_: str, payload_json: str | None) -> str | None:
    if not payload_json or type_ not in ("assistant_msg", "subagent_stop", "stop", "error"):
        return None
    import json
    p = json.loads(payload_json)
    if type_ == "assistant_msg":
        return (p.get("text") or "")[:200] if p.get("block") == "text" else f"(thinking {p.get('chars')}자)"
    if type_ == "stop":
        return f"{p['durationMs']}ms" if p.get("durationMs") is not None else None
    return (p.get("summary") or p.get("text") or "")[:200] or None


def _json(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)


def _expanding(name: str):  # noqa: ANN202
    from sqlalchemy import bindparam
    return bindparam(name, expanding=True)

