"""VARCHAR 칼럼에 들어가는 값의 목록. DB는 ENUM을 쓰지 않고 여기서 검사한다(0001_init.sql 머리말)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CharacterStatus(StrEnum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    DORMANT = "DORMANT"
    SUSPENDED = "SUSPENDED"
    STALE = "STALE"


class Role(StrEnum):
    FOREMAN = "foreman"
    CODER = "coder"
    CICD = "cicd"
    INSPECTOR = "inspector"
    HELPER = "helper"
    INFRA = "infra"


class EventSource(StrEnum):
    HOOK = "hook"
    TRANSCRIPT = "transcript"
    POLL = "poll"
    DEBUG = "debug"  # 1단계 확인용(/api/debug/emit)
    BRIDGE = "bridge"  # 브리지가 한 일(입력 주입 등)
    SHELL = "shell"    # 7단계 터미널 패널에서 사람이 친 명령(PROMPT_COMMAND → /hooks/shell)


class EventType(StrEnum):
    START = "start"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ASSISTANT_MSG = "assistant_msg"
    STOP = "stop"
    ERROR = "error"
    APPROVAL_REQ = "approval_req"
    APPROVAL_RES = "approval_res"
    INTERRUPTED = "interrupted"
    COMPACT = "compact"
    QUEUED = "queued"
    SESSION_END = "session_end"
    SUBAGENT_START = "subagent_start"
    SUBAGENT_STOP = "subagent_stop"
    RESTART_LOOP = "restart_loop"
    INPUT = "input"  # 3단계 입력 주입(거부 포함)
    SHELL_CMD = "shell_cmd"          # 7단계 — 터미널 패널에서 친 명령(마스킹). 승인 정책은 걸리지 않는다
    TERM_REQUEST = "term_request"    # CC가 사람에게 부탁한 명령을 감지해 패널에 미리 채웠다
    TERM_RESULT = "term_result"      # 그 명령의 결과를 부탁한 세션에 전달했다(거부 포함)
    DEBUG = "debug"


class EventStatus(StrEnum):
    WORKING = "working"
    IDLE = "idle"
    WAITING = "waiting"
    DONE = "done"
    ERROR = "error"


TARGET_MAX = 1024  # event.target VARCHAR(1024)


def clip_target(target: str | None) -> tuple[str | None, str | None]:
    """target을 칼럼 길이에 맞춘다. (칼럼에 넣을 값, 잘렸으면 원문 · 아니면 None).

    실측(11-02): Bash 명령 9,979개 중 25.2%가 1,024자 초과, 최대 24,528자. 원문은 payload.target_full로 간다.
    잘린 값 끝에 '…'를 붙여 화면에서도 잘린 것이 보이게 한다. 마스킹은 이 함수 전에 끝나 있어야 한다.
    """
    if target is None or len(target) <= TARGET_MAX:
        return target, None
    return target[: TARGET_MAX - 1] + "…", target


def utcnow() -> datetime:
    return datetime.now(UTC)


class EventIn(BaseModel):
    """생산자(hook · 와처 · 폴링 · 디버그)가 파이프라인에 넣는 이벤트. id는 적재 때 붙는다."""

    source: EventSource
    type: EventType
    ts: datetime = Field(default_factory=utcnow)
    uuid: str | None = Field(default=None, max_length=36)
    parent_uuid: str | None = Field(default=None, max_length=36)
    session_id: int | None = None
    character_id: int | None = None
    turn_id: int | None = None
    message_id: str | None = Field(default=None, max_length=64)
    subagent_id: int | None = None
    tool_use_id: str | None = Field(default=None, max_length=64)
    tool: str | None = Field(default=None, max_length=64)
    target: str | None = None  # 마스킹 후. 길면 clip_target이 자른다
    status: EventStatus | None = None
    commit_sha: str | None = Field(default=None, min_length=40, max_length=40)
    payload: dict[str, Any] | None = None

    @field_validator("ts")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        # 시간대 없는 값은 UTC로 본다(트랜스크립트 timestamp는 Z, 서버 로컬은 KST라 섞이면 9시간 어긋난다)
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v
