"""VARCHAR 칼럼에 들어가는 값의 목록. DB는 ENUM을 쓰지 않고 여기서 검사한다(0001_init.sql 머리말)."""

from enum import StrEnum


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
