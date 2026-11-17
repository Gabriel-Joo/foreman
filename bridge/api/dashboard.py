"""대시보드 데이터(6단계) — 프로젝트별 세션 스냅샷과 세션의 최근 대화. API 토큰이 필요하다.

화면은 이 스냅샷을 한 번 받고, 그 뒤로는 WS(이벤트 · 턴 · 승인 · 세션 상태)로 고친다. 스냅샷은 몇 초마다 다시 받아
어긋난 것을 맞춘다. 그리는 쪽(static/js/render.js)은 이 모양만 안다 — 테마 렌더러로 바꿔도 여기는 그대로.

상태(docs/00_design.md 2.1):
  SUSPENDED  프로세스가 정지(T)
  DORMANT    살아 있는 프로세스가 없다
  ACTIVE     CC가 일하는 중(sessions json status = busy) 또는 열린 턴이 있다
  IDLE       살아 있고 쉬는 중
"""

import asyncio
import logging
import os
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text

from bridge.api.auth import require_api_token
from bridge.api_error import classify as classify_api_error
from bridge.api_error import one_line as api_error_line
from bridge.inject import _status, _tmux_env
from bridge.liveness import live_sessions
from bridge.compactwatch import context_status, status as compact_status
from bridge.model_choice import family as model_family
from bridge.model_choice import label as model_label
from bridge.roles import WORKER_ROLES
from bridge.uiver import ui_version

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])
log = logging.getLogger(__name__)

PROJECT_ORDER = ["runshoes", "petmint-rag-chatbot", "foreman", "ronanlab-infra"]
LABEL = {"runshoes": "런슈즈", "petmint-rag-chatbot": "펫퍼민트", "foreman": "FOREMAN", "ronanlab-infra": "인프라", None: "미분류"}
DORMANT_SHOW_H = 48          # 프로세스가 없는 세션은 이 시간 안에 활동이 있던 것만
KST = timedelta(hours=9)
_cache: dict[str, Any] = {"at": 0.0, "data": None}


def _cc_name(sessions_dir: Any, pid: int) -> str | None:
    """sessions/<pid>.json의 name(CC가 붙이는 짧은 이름, 예: petmint-rag-chatbot-33). .key는 열지 않는다."""
    import json
    from pathlib import Path
    try:
        return json.loads(Path(sessions_dir, f"{pid}.json").read_text(encoding="utf-8")).get("name")
    except (OSError, ValueError):
        return None


def _started(sessions_dir: Any, pid: int) -> datetime | None:
    """sessions/<pid>.json의 startedAt(ms) — 이 CC 프로세스가 뜬 시각(UTC, tz 없음). 그 전에 띄운 백그라운드는 이미 죽었다."""
    import json
    from pathlib import Path
    try:
        ms = json.loads(Path(sessions_dir, f"{pid}.json").read_text(encoding="utf-8")).get("startedAt")
    except (OSError, ValueError):
        return None
    return datetime.fromtimestamp(ms / 1000, UTC).replace(tzinfo=None) if isinstance(ms, (int, float)) else None


async def latest_tool_acts(c: Any, in_ids: str) -> dict[int, tuple[Any, ...]]:
    """세션마다 마지막 도구 호출 — {세션: (tool, target, ts, subagent_id, description)}.
    description은 Bash 입력에 CC가 붙인 하는 일 한 줄(11-14, payload.input은 수집기가 이미 가렸다). Bash 아니면 None."""
    return {r[0]: r[1:] for r in (await c.execute(text(
        f"SELECT e.session_id, e.tool, e.target, e.ts, e.subagent_id, "
        f"IF(e.tool = 'Bash', JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.input.description')), NULL) FROM event e JOIN ("
        f"  SELECT session_id, MAX(id) mid FROM event WHERE session_id IN {in_ids} AND type = 'tool_use' "
        f"  AND source = 'transcript' GROUP BY session_id) x ON x.mid = e.id"))).all()}


def background_running(rows: list[tuple[Any, ...]], started: datetime | None, cc_session_id: str | None = None) -> list[dict[str, Any]]:
    """bg_start(끝 알림 없는 것) 중 지금 프로세스가 뜬 뒤에 시작한 것만 — [{task, tool, description, since, out_changed, out_size}].
    out_changed = 출력 파일(tasks/<task>.output)이 마지막으로 바뀐 때(11-14 — 오래 도는 일이 멈췄는지 보이려고, 못 찾으면 None).
    out_size = 그 파일 크기(바이트, 못 찾으면 None). 0이면 한 번도 출력이 안 나온 것 — 화면이 「출력 멈춤」을 붙이지 않는다.
    경과는 화면이 since로 계산한다(서버는 매번 다시 안 만들어도 되게)."""
    from bridge.stallwatch import BG_SKIP_TOOLS, bg_output_stat
    out = []
    for task, tool, desc, ts in rows:
        if started is not None and ts is not None and ts < started:
            continue
        st = bg_output_stat(cc_session_id, task) if cc_session_id and tool not in BG_SKIP_TOOLS else None
        out.append({"task": task, "tool": tool, "description": desc, "since": _iso(ts),
                    "out_changed": _iso(st[0]) if st else None, "out_size": st[1] if st else None})
    return out


def invalidate() -> None:
    """세션 상태가 바뀌었다 — 다음 스냅샷은 새로 만든다."""
    _cache["data"] = None


def char_state(proc: str | None, cc_status: str | None, open_turn: bool) -> str:
    """프로세스가 살아 있으면 CC가 직접 적는 status가 기준이다(busy → ACTIVE, 그 밖 → IDLE).
    열린 턴은 status를 모를 때만 본다 — 끝 신호 없이 멈춘 턴 하나가 세션을 몇 시간씩 ACTIVE로 보이게 했다
    (6단계 실측: 펫퍼민트가 프롬프트 · API 요청 뒤 응답도 끝 신호도 없이 10시간, CC status는 idle)."""
    if proc is None:
        return "DORMANT"
    if proc == "T":
        return "SUSPENDED"
    if cc_status is not None:
        return "ACTIVE" if cc_status == "busy" else "IDLE"
    return "ACTIVE" if open_turn else "IDLE"


async def _switch_status(c: Any, ctx: dict[int, dict[str, Any]], min_pct: int) -> dict[int, dict[str, Any]]:
    """작업 전환 권유(11-09) — 쌓인 대화 ≥ min_pct%인 세션만 마지막 사람 턴을 본다(세션마다 질의 셋, 대개 몇 개 안 된다).
    {turn_id, phrase, committed, idle, pct}. 판정은 텔레그램과 같은 함수(bridge/switchwatch.py)."""
    from bridge.switchwatch import latest_signal, should_suggest
    out: dict[int, dict[str, Any]] = {}
    for sid, v in ctx.items():
        if v.get("pct") is None or v["pct"] < min_pct:
            continue
        sig = await latest_signal(c, sid)
        if sig and should_suggest(v["pct"], min_pct, sig.phrase, sig.committed, sig.idle):
            out[sid] = {"turn_id": sig.turn_id, "phrase": sig.phrase, "committed": sig.committed, "idle": sig.idle, "pct": v["pct"]}
    return out


# 11-09 사람이 해야 풀리는 것(사용자: "사람 답을 기다리는 상태는 쉼이 아니다", "CC 자체 권한 거부는 화면에 아예 없다")
DENIED_PREFIX = "Permission for this action was denied"          # CC auto mode 분류기 거부 — FOREMAN 승인 큐를 거치지 않는다
_DENY_REASON = re.compile(r"Reason:\s*\[([^\]]+)\]")
# 글로 묻고 끝난 응답 — 마지막 문단에 묻는 말이 있으면(추정). 질문 카드(AskUserQuestion)는 따로 잡힌다
# 11-11(받은 할 일 #13): 끝 600자 전체를 보던 것을 **마지막 문단**만으로 좁혔다. 11-10 관리자 244의 합치기 보고 등 7건이
# 보고 가운데의 "확인해 주세요" · "UI 불만 (가)" 같은 말에 걸려 묻지 않는 글이 답 기다림이 됐다(log/coder_screen_state_20261111.md)
# 11-11(사용자): 마지막 문단만 보니 너무 좁았다 — 코더 274 보고가 「**사용자가 정할 것:** …」 문단 뒤에 「자세한 내용은 log에
# 적었습니다」를 붙여 못 잡았다. 끝 ASK_PARAS 문단을 보고, 「~주십시오」 · 「정할 것:」 머리말도 잡는다
ASK_PARAS = 3
_ASKS = re.compile(r"\?\s*$|까요[.?]?\s*$|[가-힣]\?(\s|$)|(골라|말씀해|알려|정해|확인해|눌러|결정해|답해) ?(주세요|주십시오|주시겠어요|주시겠습니까)|(정해|골라) ?주(시면|셔야)"
                   r"|중 하나를"
                   # 11-11(사용자): 사람이 움직여야 이어지는 글 — 「1번을 마쳤다고 알려 주시면 그때 하겠습니다」(인프라 265, 567293 —
                   # 끝 「참고할 것」 목록 안의 한 줄). 「~하라고 하시면 · 원하시면」 같은 제안은 _OFFER_IF로 따로 뺀다
                   r"|(알려|말씀해|허락해|승인해|맡겨|보내|넘겨) ?주시면[^.?!\n]{0,60}(겠습니다|겠어요|드릴게요|할게요)"
                   r"|^\W*((사용자|사람|당신)[가이께서 ]*)?(정할|정하실|정해 ?주실|고를|고르실|골라 ?주실|결정할|결정하실|답할|답하실|여쭐|승인받을|아직 답을 기다리는) ?(것|일|점|부분)\W*[:：]"
                   r"|^\W*(결정 필요|질문)\W*[:：]", re.M)
# 「(가)」는 고르라는 말과 같이 있을 때만 — 할 일 이름 「UI 불만 (가)」처럼 가리키기만 한 것은 묻는 말이 아니다
_CHOICE = re.compile(r"\((가|나|다)\)[^\n]*(까요|골라|정해|중 하나)")
# 다른 세션 · 사람에게 넘기는 부탁 — 지금 이 사람의 답을 막고 기다리는 것이 아니다("합친 뒤 관리자가 확인해 주세요")
_THIRD = re.compile(r"(관리자|원본 (폴더 )?세션|교장|서기|코더|디자이너|다음 세션)[이가은는께]?(서)? [^\n]{0,60}주세요")


# 끝 문단을 넓히며 실제 DB에서 본 거짓 꼴(11-11): 인용 안의 말(챗봇 문장 "…알려 주세요" · "한 켤레 더 골라 주세요"를 띄웁니다),
# FAQ 「**Q:** …요?」, 「?」로 끝나는 제목 줄(## Is … ?), 「바꾸고 싶으시면 말씀해 주세요」 같은 조건부 제안(이미 끝난 보고)
_QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”|「[^」\n]*」|『[^』\n]*』|`[^`\n]*`')
_FAQ = re.compile(r"^\W*(Q|A|질문|답)\W*[:：]")
_OFFER = re.compile(r"[^.?!\n]*(원하시면|원하시길|싶으시면|보시면|있으면|있다면|셨다면|뜻이면|필요하시면|거라면|맞는다면)[^.?!\n]{0,40}"
                    r"(말씀해|알려) ?(주세요|주십시오|주시면[^.?!\n]{0,60}(겠습니다|겠어요|드릴게요|할게요))\.?")


def last_paragraph(reply: str, n: int = 1) -> str:
    """빈 줄로 나눈 끝 n문단(빈 문단은 건너뜀) — 문단마다 끝 600자. 긴 문단의 머리 줄이 제목 · 굵은 글(「### 정해 주셔야 할 것」
    · 「**정할 것:**」 뒤에 긴 목록)이면 그 줄도 남긴다."""
    paras = [p for p in re.split(r"\n\s*\n", reply.strip()) if p.strip()]

    def cut(p: str) -> str:
        head = p.strip().splitlines()[0]
        return p if len(p) <= 600 else (head + "\n" if re.match(r"\s*(#|\*\*)", head) else "") + p[-600:]
    return "\n\n".join(cut(p) for p in paras[-n:])


def ask_line(reply: str | None) -> str | None:
    """응답의 끝 ASK_PARAS 문단에서 사람에게 묻는 줄(없으면 None). 다음에 할 일을 말한 것(「~기다리겠습니다」)은
    묻는 말 꼴이 아니라 걸리지 않는다. 관리자 · 코더 등 다른 세션에게 넘기는 부탁도 뺀다."""
    if not reply:
        return None
    for line in reversed(last_paragraph(reply, ASK_PARAS).splitlines()):
        bare = _OFFER.sub("", _QUOTED.sub("…", line))
        if _FAQ.match(bare) or (bare.lstrip().startswith("#") and bare.rstrip().endswith("?")):
            continue
        if _CHOICE.search(bare):
            return line
        m = _ASKS.search(bare)
        if m and not _THIRD.search(bare):
            return line
    return None


def asks_text(reply: str | None) -> bool:
    return ask_line(reply) is not None


async def human_needs(c: Any, in_ids: str, relay: dict[str, tuple[bool, bool]] | None = None) -> dict[int, dict[str, Any]]:
    """세션마다 — 마지막 사람 입력(origin human 턴) 뒤의 CC 권한 거부 마지막 한 건, 마지막 본 대화 응답이 묻는 말인지.
    사람이 다시 입력하면(새 human 턴) 둘 다 풀린다.

    11-13(사용자 — 사람이 봐야 하는 것은 관리자 머리 위에만):
    - 관리자: 출처 relay · manager_ask 턴의 응답으로는 asks · report를 내지 않는다. 사람에게 올릴 것은 escalate(관리자가 API로 부름)
    - 작업 세션(coder · scribe · designer): 그 응답의 턴을 관리자에게 넘긴 기록(relay-out, ok)이 있고 같은 종류면 asks · report 대신
      relayed(「관리자에게 보고함」 · 「관리자 답 기다림」). 넘기지 못했거나 기록이 없으면 지금처럼 사람에게 — 조용히 묻히지 않게.
      relay = {프로젝트: (relay_reports, relay_questions)} — 켜진 프로젝트는 턴 끝 뒤 RELAY_GRACE 동안 넘기기를 기다린다(그 사이 안 띄움)"""
    out: dict[int, dict[str, Any]] = {}
    last_human = {r[0]: r[1] for r in (await c.execute(text(
        f"SELECT session_id, MAX(started_at) FROM turn WHERE session_id IN {in_ids} AND origin = 'human' "
        f"GROUP BY session_id"))).all()}
    # 11-11(사용자, 펫퍼민트 227): 거부 뒤 세션이 다른 방법으로 지나가도 사람이 다시 입력할 때까지 「권한 거부」가 남았다.
    # 거부 뒤에 도구 결과가 하나라도 더 있거나(막힌 명령이 지나감 · 다른 방법으로 넘어감 — 마지막 거부 뒤라 거부가 아니다)
    # 어떤 origin이든 새 턴이 시작됐으면(다음 일로 넘어감) 풀린 것으로 본다. 거부 뒤 글만 쓰고 멈춘 세션은 그대로 남는다
    for sid, tool, ts, sub, prev, moved in (await c.execute(text(
            f"SELECT e.session_id, e.tool, e.ts, e.subagent_id, JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.error_preview')), "
            f"  EXISTS(SELECT 1 FROM event e2 WHERE e2.session_id = e.session_id AND e2.ts >= e.ts AND e2.id > e.id "
            f"         AND e2.type = 'tool_result') "
            f"  OR EXISTS(SELECT 1 FROM turn t WHERE t.session_id = e.session_id AND t.started_at > e.ts) "
            f"FROM event e JOIN (SELECT session_id, MAX(id) mid FROM event WHERE session_id IN {in_ids} AND type = 'tool_result' "
            f"  AND status = 'error' AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.error_preview')) LIKE :p GROUP BY session_id"
            f") x ON x.mid = e.id"), {"p": DENIED_PREFIX + "%"})).all():
        if (last_human.get(sid) and ts < last_human[sid]) or moved:
            continue
        m = _DENY_REASON.search(prev or "")
        out.setdefault(sid, {})["denied"] = {"tool": tool, "reason": m.group(1) if m else None, "at": _iso(ts),
                                            "subagent": sub is not None}
    # 사람이 [답 안 해도 됩니다]로 끈 응답(session_action 'asks-off', detail = 그 응답 이벤트 id) — 다음 응답이 오면 다시 판정
    async def last_detail(act: str) -> dict[int, str]:
        return {r[0]: r[1] for r in (await c.execute(text(
            f"SELECT a.session_id, a.detail FROM session_action a JOIN (SELECT session_id, MAX(id) mid FROM session_action "
            f"WHERE session_id IN {in_ids} AND action = :a AND ok GROUP BY session_id) x ON x.mid = a.id"), {"a": act})).all()}
    off = await last_detail(ASKS_OFF_ACT)
    read = await last_detail(REPORT_READ_ACT)      # 「보고 옴」을 사람이 읽음(그 세션 패널을 엶)
    relayed = {r[0]: (r[1], bool(r[2])) for r in (await c.execute(text(
        f"SELECT a.session_id, a.detail, a.ok FROM session_action a JOIN (SELECT session_id, MAX(id) mid FROM session_action "
        f"WHERE session_id IN {in_ids} AND action = :a GROUP BY session_id) x ON x.mid = a.id"), {"a": RELAY_OUT_ACT})).all()}
    # 같은 턴을 관리자에게 넘긴 종류 모두(ok) — 보고 · 물음이 겹치면 화면은 「관리자에게 보고함」이 이긴다(11-13 사용자, render.js workerMark)
    relayed_kinds: dict[tuple[int, str], set[str]] = {}
    for rsid, rdet in (await c.execute(text(
            f"SELECT session_id, detail FROM session_action WHERE session_id IN {in_ids} AND action = :a AND ok "
            f"AND created_at > :cut"), {"a": RELAY_OUT_ACT, "cut": datetime.now() - REPORT_FRESH})).all():
        k, _, t = (rdet or "").partition(":")
        relayed_kinds.setdefault((rsid, t), set()).add(k)
    now = datetime.now(UTC).replace(tzinfo=None)
    fresh = now - REPORT_FRESH
    for sid, reply, ts, eid, turn_id, origin, role, project in (await c.execute(text(
            f"SELECT e.session_id, JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.text')), e.ts, e.id, e.turn_id, t.origin, cs.role, p.name "
            f"FROM event e JOIN ("
            f"  SELECT session_id, MAX(id) mid FROM event WHERE session_id IN {in_ids} AND type = 'assistant_msg' "
            f"  AND subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' GROUP BY session_id"
            f") x ON x.mid = e.id LEFT JOIN turn t ON t.id = e.turn_id "
            f"LEFT JOIN character_session cs ON cs.id = e.session_id LEFT JOIN `character` ch ON ch.id = cs.character_id "
            f"LEFT JOIN project p ON p.id = ch.project_id"))).all():
        if last_human.get(sid) and ts < last_human[sid]:
            continue
        if off.get(sid) == str(eid):       # [답 안 해도 됨]을 누른 것은 읽은 것이기도 하다
            continue
        if role == "manager" and origin in MGR_QUIET_ORIGINS:
            continue                       # 중계 · 관리자끼리 부탁에 대한 응답 — 사람에게 올릴 것은 escalate로
        line = ask_line(reply)
        kind = "question" if line else ("report" if read.get(sid) != str(eid) and ts >= fresh else None)
        if kind is None:
            continue
        if role in WORKER_ROLES:
            rec = relayed.get(sid)
            if rec and rec[1] and turn_id is not None and rec[0] == f"{kind}:{turn_id}":
                kinds = sorted(relayed_kinds.get((sid, str(turn_id)), set()) | {kind})
                out.setdefault(sid, {})["relayed"] = {"kind": kind, "kinds": kinds, "at": _iso(ts), "event_id": eid}
                continue
            on = (relay or {}).get(project or "")
            waiting = rec is None or rec[0].split(":", 1)[-1] != str(turn_id)
            if on and on[kind == "question"] and waiting and turn_id is not None and now - ts < RELAY_GRACE:
                continue                   # 알림이 아직 관리자에게 넘기는 중 — 끝나면 relayed 또는 사람에게
        if kind == "question":
            out.setdefault(sid, {})["asks"] = {"at": _iso(ts), "tail": line.strip()[-160:], "event_id": eid}
        else:
            out.setdefault(sid, {})["report"] = {"at": _iso(ts), "tail": last_paragraph(reply or "").strip()[-160:], "event_id": eid}
    # 사람에게 올린 것(escalate, 관리자만). 보고는 마지막 하나만, 읽거나(esc-read) 사람이 그 관리자에게 입력하면 사라진다.
    # 물음은 11-17 사용자 결정 (다)로 바뀌었다(인프라 #3058이 다른 얘기를 입력해도 사라질 수 있었다). 사람이 그 관리자에게 입력한 뒤에
    # 입력 글에 물음 번호(#id)가 있으면 끝난 것(띄우지 않는다. 기록은 그 사람 턴의 글과 escalate 행 자체),
    # 번호 없이 넘어갔으면 「아직 안 본 것」(unseen)으로 남기고 사람이 [봤다](esc-seen)로 하나씩 지운다. 입력 전이면 지금처럼 question
    done = {r[0] for r in (await c.execute(text(
        f"SELECT detail FROM session_action WHERE session_id IN {in_ids} AND action IN (:r, :o, :s) AND ok"),
        {"r": ESC_READ_ACT, "o": ESC_OFF_ACT, "s": ESC_SEEN_ACT})).all()}
    merges: dict[int, list[dict[str, Any]]] = {}
    open_qs: list[tuple[int, int, datetime, str]] = []
    for aid, sid, detail, at in (await c.execute(text(
            f"SELECT id, session_id, detail, created_at FROM session_action WHERE session_id IN {in_ids} AND action = :a AND ok "
            f"AND created_at > :cut ORDER BY id"), {"a": ESC_ACT, "cut": now - ESC_KEEP})).all():
        kind, _, body = (detail or "").partition(":")
        if kind not in ESC_KINDS:
            continue
        esc_ = out.setdefault(sid, {}).setdefault("escalate", {})
        if (m := _MERGE_TAG.match(body)) and kind == "question":
            # 11-13 브리지가 올린 합치기 카드 물음 — 카드가 남아 있는 동안 남는다(사람이 그 관리자에게 입력해도). 내리는 것은 브리지
            # (카드가 합쳐짐 · 미뤄짐 · 없어짐 → esc-off)와 사람의 [답 안 해도 됨]. 관리자의 다른 물음과 서로 덮지 않는다
            if str(aid) not in done:
                merges.setdefault(sid, []).append({"id": aid, "at": _iso(at), "text": body[m.end():][:300],
                                                   "merge_sid": int(m.group(1))})
            continue
        if kind == "question":
            if str(aid) not in done:
                open_qs.append((aid, sid, at, body))
            continue
        if str(aid) in done or (last_human.get(sid) and last_human[sid] > at):
            esc_.pop(kind, None)
        else:
            esc_[kind] = {"id": aid, "at": _iso(at), "text": body[:300]}
    for sid, items in (await esc_question_states(c, open_qs)).items():
        esc_ = out.setdefault(sid, {}).setdefault("escalate", {})
        if items["pending"]:
            esc_["question"] = items["pending"][-1]       # 머리 위에는 가장 최근 물음 하나(앞의 물음은 사람이 입력하면 unseen으로)
        if items["unseen"]:
            esc_["unseen"] = items["unseen"]
    for sid, ms in merges.items():
        esc_ = out.setdefault(sid, {}).setdefault("escalate", {})
        q = esc_.get("question")
        if q is None or q["id"] < ms[-1]["id"]:       # 머리 위에는 가장 최근 물음 하나 — 합치기 카드가 여럿이면 merges에 모두
            esc_["question"] = ms[-1]
        esc_["merges"] = [x["merge_sid"] for x in ms]
    for v in out.values():
        if "escalate" in v and not v["escalate"]:
            del v["escalate"]
    return out


async def api_stops(c: Any, in_ids: str) -> dict[int, dict[str, Any]]:
    """API 오류로 멈춘 세션(11-13, log/screen_api_error_bar_20261113.md) — 마지막 턴이 stop_failure로
    끝났고 그 뒤 새 턴이 없다. 다음 턴이 시작되면(사람 입력 · 다른 세션 메시지 등 어떤 출처든) 마지막 턴이 바뀌어 저절로 풀린다.
    빨간 「…」(stuck_turn)은 끝 신호가 안 온 **열린** 턴이고, 이것은 **닫힌** 턴이라 서버 상태는 IDLE이다 — 상태 값은 늘리지 않고
    (docs/00_design.md 3.11) 이 칸으로 가른다. 까닭은 대화 패널과 같은 bridge/api_error.py로(글이 있는 트랜스크립트 쪽을 먼저).
    {세션: {turn_id, at(턴이 끝난 시각), kind, label, action, request_id, detail, reset, line}}"""
    rows = (await c.execute(text(
        f"SELECT t.session_id, t.id, t.ended_at FROM turn t JOIN (SELECT session_id, MAX(seq) ms FROM turn "
        f"WHERE session_id IN {in_ids} GROUP BY session_id) x ON x.session_id = t.session_id AND x.ms = t.seq "
        f"WHERE t.end_reason = 'stop_failure' AND t.ended_at IS NOT NULL"))).all()
    if not rows:
        return {}
    errs: dict[int, tuple[str | None, str | None]] = {}
    for tid, t_, err in (await c.execute(text(
            "SELECT turn_id, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')), JSON_UNQUOTE(JSON_EXTRACT(payload, '$.error')) "
            "FROM event WHERE turn_id IN :ids AND type = 'error' ORDER BY id").bindparams(bindparam("ids", expanding=True)),
            {"ids": [r[1] for r in rows]})).all():
        t_ = t_ if t_ != "null" else None
        if t_ or tid not in errs:          # 글이 있는 것(트랜스크립트)이 hook 것(error 값만)보다 낫다
            errs[tid] = (t_, err if err != "null" else None)
    out: dict[int, dict[str, Any]] = {}
    for sid, tid, ended in rows:
        ce = classify_api_error(*errs.get(tid, (None, None)))
        out[sid] = {"turn_id": tid, "at": _iso(ended), **{k: ce[k] for k in ("kind", "label", "action", "request_id", "detail", "reset")},
                    "line": api_error_line(ce)}
    return out


# 중계 대상 역할 WORKER_ROLES는 bridge/roles.py 한 곳(11-15, notify와 같은 것. 위 import)
MGR_QUIET_ORIGINS = {"relay", "manager_ask", "merge_card"}   # 관리자 턴 중 사람에게 띄우지 않는 출처(merge_card 11-15 — 합치기 카드로 연 턴)
RELAY_OUT_ACT = "relay-out"     # 작업 세션 session_action — 알림이 그 턴을 관리자에게 넘긴 결과. detail = "<kind>:<turn_id>"
# 넘기는 동안(턴 끝 → 관리자 입력 칸) 사람용 표시를 안 띄우는 시간 — 넘기면 relayed, 못 넘기면 사람에게.
# 11-13 관리자가 잰 실제 값(11-12 ~ 11-13 session_action mgr-relay 6건): 2.5초 ×3 · 17.4초 ×3, 실패 0. 17.4초는 settle 2초 +
# deliver(verify_s=15)(관리자가 일하는 중이라 대기열)로 보인다. 30초 = 가장 긴 성공 17.4초 + 여유(전엔 150초 — 넘기기 제한 60초까지 기다렸다).
# 대가: 넘기기 제한(60초)에 걸리는 드문 경우는 30초에 사람용 표시가 먼저 떴다가 넘기기가 성공하면 relayed로 바뀐다(잠깐 떴다 사라짐)
RELAY_GRACE = timedelta(seconds=30)
ESC_ACT, ESC_READ_ACT, ESC_OFF_ACT = "escalate", "esc-read", "esc-off"   # 관리자가 사람에게 올림 · 사람이 읽음 · 사람이 끔
ESC_SEEN_ACT = "esc-seen"       # 11-17 번호 없이 넘어간 물음(아직 안 본 것)을 사람이 [봤다]로 지움. detail = escalate id
ESC_KINDS = ("report", "question")
ESC_KEEP = timedelta(days=7)
# 사람 입력 글의 물음 번호, 예: 「#3058 승인」. 뒤에 숫자가 더 붙은 것(#30581)은 다른 번호다
_ESC_NO = re.compile(r"#(\d+)(?!\d)")


def esc_numbers(prompt: str | None) -> set[int]:
    """사람 입력 글에 든 물음 번호들."""
    return {int(x) for x in _ESC_NO.findall(prompt or "")}


async def esc_question_states(c: Any, qs: list[tuple[int, int, datetime, str]]) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """관리자 escalate 물음(합치기 카드 물음, 사람이 끄거나 [봤다]로 지운 것은 뺀다)을 그 뒤의 사람 입력으로 가른다(11-17 사용자 결정 (다)).
    qs = [(escalate id, 세션, 올린 시각 UTC, 글)]. 돌려줌 {세션: {"pending": [...], "unseen": [...], "answered": [...]}}, 각 항목 {id, at, text}.
    - answered: 그 물음 뒤 사람 턴(origin human) 글 어디에든 #id가 있다. 끝난 것이라 화면에 띄우지 않는다
    - unseen: 그 뒤 사람 턴이 있는데 #id가 없다(번호 없이 넘어감). 여러 물음이 있으면 번호가 든 것만 끝나고 나머지는 여기로
    - pending: 그 뒤 사람 턴이 없다(지금처럼 「사용자 답 기다림」)
    사람 턴 글(turn.prompt_text)은 DB에 들어갈 때 마스킹을 거친 글이다. 물음 번호는 마스킹에 걸리지 않는다"""
    out: dict[int, dict[str, list[dict[str, Any]]]] = {}
    if not qs:
        return out
    turns: dict[int, list[tuple[datetime, set[int]]]] = {}
    for tsid, started, prompt in (await c.execute(text(
            "SELECT session_id, started_at, prompt_text FROM turn WHERE session_id IN :sids AND origin = 'human' "
            "AND started_at > :since").bindparams(bindparam("sids", expanding=True)),
            {"sids": sorted({q[1] for q in qs}), "since": min(q[2] for q in qs)})).all():
        turns.setdefault(tsid, []).append((started, esc_numbers(prompt)))
    for aid, sid, at, body in qs:
        after = [nums for started, nums in turns.get(sid, []) if started > at]
        state = "answered" if any(aid in nums for nums in after) else ("unseen" if after else "pending")
        d = out.setdefault(sid, {"pending": [], "unseen": [], "answered": []})
        d[state].append({"id": aid, "at": _iso(at), "text": body[:300]})
    return out
# 11-13 사람 승인 합치기 카드를 브리지가 관리자 머리 위로 올린 물음 — detail 글 앞에 기계 표시(모델이 쓰는 글이 아니다).
# 사람에게 보이는 글 · 알림에는 붙지 않는다(human_needs가 떼어 낸다)
_MERGE_TAG = re.compile(r"#merge:(\d+)# ")


def merge_tag(card_sid: int) -> str:
    return f"#merge:{int(card_sid)}# "


ASKS_OFF_ACT = "asks-off"        # session_action — 사람이 「이 응답은 답 안 해도 됩니다」(11-11, 받은 할 일 #13)
# 「보고 옴」(11-11 사용자 — 보고를 마친 캐릭터에 아무 표시가 없어 눌러 보고서야 끝난 것을 안다). 묻지 않고 끝난 마지막 응답을
# 사람이 그 세션 패널을 열어 읽기 전까지. 읽음은 session_action 'report-read'(detail = 그 응답 이벤트 id) — 다음 응답이 오면 다시 뜬다.
# REPORT_FRESH보다 오래된 응답은 띄우지 않는다(처음 켤 때 쉬는 세션이 모두 「보고 옴」이 되지 않게)
REPORT_READ_ACT = "report-read"
REPORT_FRESH = timedelta(hours=24)


async def report_read(engine: Any, sid: int, event_id: int | None = None) -> dict[str, Any]:
    """「보고 옴」을 읽음으로. event_id를 주면 그 응답이 지금 보고일 때만(패널을 연 사이 새 응답이 오면 그것은 남긴다)."""
    async with engine.begin() as c:
        needs = await human_needs(c, f"({int(sid)})")
        r = (needs.get(sid) or {}).get("report")
        if not r or (event_id is not None and int(event_id) != int(r["event_id"])):
            return {"ok": False, "note": "읽을 보고가 없습니다"}
        await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                        {"s": sid, "a": REPORT_READ_ACT, "d": str(r["event_id"])})
    _cache["data"] = None
    return {"ok": True, "event_id": r["event_id"]}


@router.post("/sessions/{sid}/report-read")
async def report_read_api(sid: int, request: Request, event_id: int | None = None) -> dict[str, Any]:
    # 점검 도구(tools/screen.py, ?probe=1)가 연 패널은 사람이 읽은 것이 아니다(11-11 227의 보고가 이렇게 사라졌다)
    if request.headers.get("x-foreman-probe"):
        return {"ok": False, "note": "점검 화면은 읽음으로 세지 않습니다"}
    return await report_read(request.app.state.store.engine, sid, event_id)


async def asks_off(engine: Any, sid: int) -> dict[str, Any]:
    """지금 답 기다림으로 잡힌 응답 하나를 끈다. 다음 응답이 오면 다시 판정한다(이벤트 id로 묶음)."""
    async with engine.begin() as c:
        needs = await human_needs(c, f"({int(sid)})")
        a = (needs.get(sid) or {}).get("asks")
        q = ((needs.get(sid) or {}).get("escalate") or {}).get("question")
        if not a and q:        # 관리자가 사람에게 올린 물음(11-13) — 그 물음만 끈다
            await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                            {"s": sid, "a": ESC_OFF_ACT, "d": str(q["id"])})
            _cache["data"] = None
            return {"ok": True, "escalate_id": q["id"], "note": "관리자가 올린 이 물음의 답 기다림을 껐습니다"}
        if not a:
            return {"ok": False, "note": "지금 답 기다림이 아닙니다"}
        await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                        {"s": sid, "a": ASKS_OFF_ACT, "d": str(a["event_id"])})
    _cache["data"] = None
    return {"ok": True, "event_id": a["event_id"], "note": "이 응답의 답 기다림을 껐습니다. 다음 응답이 오면 다시 판정합니다"}


@router.post("/sessions/{sid}/asks-off")
async def asks_off_api(sid: int, request: Request) -> dict[str, Any]:
    return await asks_off(request.app.state.store.engine, sid)


# ── 11-13 사람에게 올리기(escalate) — 관리자만. 사람 화면의 「사용자에게 보고함」 · 「사용자 답 기다림」과 알림이 이 신호 하나를 쓴다 ──
class EscalateIn(BaseModel):
    kind: Literal["report", "question"]
    text: str = Field(min_length=1, max_length=8000)


async def escalate(engine: Any, sid: int, kind: str, body: str, notifier: Any = None, tag: str = "") -> dict[str, Any]:
    """관리자 세션이 사람에게 보고 · 물음을 올린다. session_action 'escalate'(detail = "<kind>:<글 앞부분>")에 남기고 알린다 —
    물음은 바로(❓ 급함), 보고는 그 프로젝트가 하루 묶음을 켰으면 묶음으로. 관리자가 아니면 403.
    tag는 브리지가 기계적으로 올릴 때만(합치기 카드 — merge_tag). detail 글 앞에 붙고 알림 글에는 안 붙는다."""
    async with engine.begin() as c:
        r = (await c.execute(text(
            "SELECT cs.role, p.name, COALESCE(cs.custom_title, cs.title) FROM character_session cs "
            "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
            "WHERE cs.id = :s AND cs.hidden_at IS NULL"), {"s": sid})).first()
        if r is None:
            raise HTTPException(404, "세션이 없습니다")
        role, project, title = r
        if role != "manager":
            raise HTTPException(403, f"사람에게 올리기는 관리자 세션만 합니다 — 세션 {sid}의 역할은 {role or '없음'}입니다. "
                                     "작업 세션은 관리자에게 보고하면 됩니다")
        # created_at은 UTC로 직접 — 사람 입력(turn.started_at, UTC)과 비교해 물음을 내린다
        res = await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail, created_at) "
                                   "VALUES (:s, :a, 1, :d, UTC_TIMESTAMP(3))"),
                              {"s": sid, "a": ESC_ACT, "d": f"{kind}:{tag}{body.strip()}"[:512]})
        aid = res.lastrowid
    _cache["data"] = None
    notified = False
    if notifier is not None:
        try:
            rule = notifier.rules.for_project(project) if getattr(notifier, "rules", None) else None
            prefix = (rule and rule.prefix) or f"[{project or '미분류'}]"
            head = f"❓ 관리자가 사용자 답을 기다립니다 #{aid}" if kind == "question" else "📋 관리자 보고"
            msg = f"{prefix} {head} · 세션 {sid}" + (f" 「{title}」" if title else "") + f"\n{body.strip()}"
            if kind == "question" and not tag:      # 11-17 번호로 답하면 끝난다(합치기 카드 물음은 카드가 남는 동안 남으니 빼고)
                msg += f"\n(답할 때 물음 번호 #{aid}도 함께 넣으면 이 물음이 끝납니다)"
            notifier.send_direct(project, "escalate", sid, msg[:3500], rule=f"escalate:{aid}",
                                 later=bool(kind == "report" and rule and rule.digest))
            notified = True
        except Exception:  # noqa: BLE001 — 알림 실패가 화면 표시를 막지 않는다(화면에는 이미 남았다)
            notified = False
    return {"ok": True, "id": aid, "kind": kind, "notified": notified,
            "note": (f"사람 화면 관리자 머리 위에 「사용자 답 기다림」으로 띄웠습니다. 물음 번호는 #{aid}입니다. "
                     "사람이 그 번호를 넣어 답하면 끝나고, 번호 없이 다른 얘기를 하면 「아직 안 본 물음」으로 남습니다")
            if kind == "question" else "사람 화면 관리자 머리 위에 「사용자에게 보고함」으로 띄웠습니다"}


@router.post("/sessions/{sid}/escalate")
async def escalate_api(sid: int, body: EscalateIn, request: Request) -> dict[str, Any]:
    return await escalate(request.app.state.store.engine, sid, body.kind, body.text,
                          getattr(request.app.state, "notifier", None))


async def escalate_read(engine: Any, sid: int, esc_id: int) -> dict[str, Any]:
    """「사용자에게 보고함」을 읽음으로 — 사람이 그 관리자 패널을 열었다(report-read와 같은 방식)."""
    async with engine.begin() as c:
        needs = await human_needs(c, f"({int(sid)})")
        r = ((needs.get(sid) or {}).get("escalate") or {}).get("report")
        if not r or int(r["id"]) != int(esc_id):
            return {"ok": False, "note": "읽을 보고가 없습니다"}
        await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                        {"s": sid, "a": ESC_READ_ACT, "d": str(r["id"])})
    _cache["data"] = None
    return {"ok": True, "id": r["id"]}


@router.post("/sessions/{sid}/escalate-read")
async def escalate_read_api(sid: int, request: Request, id: int) -> dict[str, Any]:  # noqa: A002
    if request.headers.get("x-foreman-probe"):
        return {"ok": False, "note": "점검 화면은 읽음으로 세지 않습니다"}
    return await escalate_read(request.app.state.store.engine, sid, id)


async def escalate_seen(engine: Any, sid: int, esc_id: int) -> dict[str, Any]:
    """「아직 안 본 물음」 하나를 사람이 [봤다]로 지운다(11-17). 번호 없이 넘어간 물음만 지울 수 있다."""
    async with engine.begin() as c:
        needs = await human_needs(c, f"({int(sid)})")
        unseen = ((needs.get(sid) or {}).get("escalate") or {}).get("unseen") or []
        if int(esc_id) not in {int(u["id"]) for u in unseen}:
            return {"ok": False, "note": "아직 안 본 물음 목록에 그 번호가 없습니다"}
        await c.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                        {"s": sid, "a": ESC_SEEN_ACT, "d": str(int(esc_id))})
    _cache["data"] = None
    log.info("관리자 세션 %s의 물음 #%s를 사람이 봤다로 지웠다", sid, esc_id)
    return {"ok": True, "id": int(esc_id), "note": f"봤다로 지웠습니다(물음 #{int(esc_id)})"}


@router.post("/sessions/{sid}/escalate-seen")
async def escalate_seen_api(sid: int, request: Request, id: int) -> dict[str, Any]:  # noqa: A002
    if request.headers.get("x-foreman-probe"):
        return {"ok": False, "note": "점검 화면은 봤다로 세지 않습니다"}
    return await escalate_seen(request.app.state.store.engine, sid, id)


def visible_rows(rows: list[Any], live: Any, cut: datetime, done: dict[int, tuple[str, datetime]],
                 isdir: Any = os.path.isdir) -> list[Any]:
    """카드 · 목록에 보일 세션 — 살아 있거나, DORMANT_SHOW_H 안에 활동이 있었거나, 합치지 않은 worktree가 남은 것.
    행: (id, cc, cwd, attached, detached, char, project, last_ts, …).

    합치지 않은 worktree가 남은 세션은 오래돼도 남긴다(11-06) — 빠지면 그 세션 패널의 [합치기] · [버리기]에 닿을 길이 없다.
    11-11(UI 불만 (나)): 그 폴더를 쓴 마지막 세션이고 합치기 · 버리기를 하지 않은 것만. 전엔 폴더만 봐서, 이름이 다시 쓰인
    foreman · foreman-3의 끝난 세션 40여 개(11-05부터, 이미 합친 것)가 목록에 남아 옛 보고가 새 것처럼 보였다."""
    wt_last: dict[str, int] = {}
    for r in rows:
        if r[2] and "/.worktrees/" in r[2]:
            wt_last[r[2]] = max(wt_last.get(r[2], 0), r[0])

    def keeps_wt(r: Any) -> bool:
        return bool(r[2] and wt_last.get(r[2]) == r[0] and isdir(r[2])
                    and (done.get(r[0]) or ("",))[0] not in ("wt-merge", "wt-discard"))

    return [r for r in rows if (r[1] in live) or (r[7] and r[7] >= cut) or keeps_wt(r)]


ENDED_LABEL = {"wt-merge": ("merged", "합쳤습니다"), "wt-discard": ("discarded", "버렸습니다"),
               "rest": ("rested", "쉬게 했습니다 — 합치기 기다림"), "exit": ("exited", "끝냈습니다")}


def merge_waits(mp: Any) -> dict[int, dict[str, Any]]:
    """사람 승인을 기다리는 합치기 카드(status=ready)를 세션 id별로. 합치는 중 · 합침 · 충돌을 보낸 카드는 뺀다.
    mergeprep.py는 고치지 않고 이미 있는 view()를 읽는다(GET /api/merge-prep과 같은 값).
    11-12(사용자): 관리자가 승인하는 카드(approver = manager, 늘-사람 까닭 없음)는 뺀다 — 승인 막대 · 머리 위 말풍선이 모두 이 값을
    읽으므로 함께 빠진다. 늘-사람 카드(human_why)는 관리자가 승인할 수 없으니 그대로 보인다(안 보이면 아무도 누르지 않고 멈춘다).
    11-13(사용자 — 사람은 관리자하고만 이야기한다): 브리지가 그 카드를 관리자 머리 위 「사용자 답 기다림」으로 올렸으면 to_manager에
    그 관리자 세션 id — 작업 세션 머리 위 「합치기 기다림」은 이때 안 띄운다(render.js needMark). 승인 막대는 그대로 센다.
    관리자가 없거나 올리지 못했으면 None → 지금처럼 작업 세션 머리 위(조용히 묻히지 않게).
    11-13(사용자 — 「답 안 해도 됨은 답을 안 하겠다는 뜻이다. 숫자로 남아 있으면 그것도 보게 된다」): 사람이 관리자 머리 위 그 물음을
    [답 안 해도 됨]으로 끈 카드(esc_off_at)는 뺀다 — 승인 막대 숫자 · 작업 세션 머리 위 · 말풍선에서 함께 빠진다. 카드 자체는
    GET /api/merge-prep · 세션 패널 「세션 정리」 탭에 남는다(handoff.js가 끈 시각을 보인다)."""
    if mp is None or not getattr(mp.cfg, "enabled", False):
        return {}
    return {c["sid"]: {"since": c["made_at"], "head8": c["head8"], "files": len(c["files"]), "asks": bool(c.get("asks")),
                       "to_manager": c.get("esc_mgr") if c.get("esc_id") else None, "esc_error": c.get("esc_error")}
            for c in mp.view()["cards"] if c["status"] == "ready" and not manager_card(c) and not c.get("esc_off_at")}


def manager_card(c: dict[str, Any]) -> bool:
    """관리자가 승인하는 카드인가 — 사람 화면에서 숨긴다(handoff.js managerCard와 같은 기준).
    11-15 브리지가 스스로 합치는 조사 log 카드(approver auto, bridge/inspector_close.py)도 사람이 누를 것이 없어 같이 뺀다."""
    return c.get("approver") in ("manager", "auto") and not c.get("human_why")


def ended_info(done: tuple[str, datetime] | None, detached: datetime | None) -> dict[str, Any]:
    """끝난 세션의 끝난 꼴 — {kind, label, at}. FOREMAN이 끝낸 기록이 없으면 kind 'gone'(터미널에서 /exit · 프로세스 사라짐)."""
    if done:
        kind, label = ENDED_LABEL.get(done[0], ("exited", "끝냈습니다"))
        return {"kind": kind, "label": label, "at": _iso(done[1])}
    return {"kind": "gone", "label": "끝났습니다", "at": _iso(detached)}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def _today_utc() -> datetime:
    """한국 시간 오늘 0시를 UTC로(토큰 '오늘' 합계)."""
    now_kst = datetime.now(UTC).replace(tzinfo=None) + KST
    return datetime(now_kst.year, now_kst.month, now_kst.day) - KST


@router.get("/dashboard")
async def dashboard(request: Request) -> dict[str, Any]:
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < 2.0:   # 탭 여러 개 · 잦은 새로고침
        return _cache["data"]
    s = request.app.state.settings
    live = live_sessions(s.sessions_dir)
    cut = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=DORMANT_SHOW_H)
    today = _today_utc()
    async with request.app.state.store.engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT cs.id, cs.cc_session_id, cs.cwd, cs.attached_at, cs.detached_at, ch.name, p.name, "
            "(SELECT MAX(e.ts) FROM event e WHERE e.session_id = cs.id) AS last_ts, cs.title, cs.role, cs.custom_title, cs.model "
            "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
            # 셸 세션(7단계 터미널 패널, type='shell')은 캐릭터 카드가 아니다
            # 숨긴 세션(0018, 시험 등)은 카드 · 토큰 집계에서 뺀다 — 지우지는 않았다
            "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.cc_session_id IS NOT NULL AND cs.type = 'agent' "
            "AND cs.hidden_at IS NULL"))).all()
        # 끝난 까닭(11-11, UI 불만 (나)) — 세션마다 마지막으로 성공한 합치기 · 버리기 · 쉬게 하기 · 끝내기
        done = {r[0]: (r[1], r[2]) for r in (await c.execute(text(
            "SELECT a.session_id, a.action, a.created_at FROM session_action a JOIN (SELECT session_id, MAX(id) mid "
            "FROM session_action WHERE action IN ('wt-merge', 'wt-discard', 'rest', 'exit') AND ok GROUP BY session_id"
            ") x ON x.mid = a.id"))).all()}
        visible = visible_rows(rows, live, cut, done)
        ids = [r[0] for r in visible] or [0]
        in_ids = "(" + ",".join(str(int(i)) for i in ids) + ")"
        open_turns = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT session_id, id, origin, started_at, LEFT(prompt_text, 300) FROM turn "
            f"WHERE session_id IN {in_ids} AND ended_at IS NULL"))).all()}
        acts = await latest_tool_acts(c, in_ids)
        subs = {}
        for sid, status, desc in (await c.execute(text(
                f"SELECT session_id, status, description FROM subagent_run WHERE session_id IN {in_ids} "
                f"AND status = 'running'"))).all():
            subs.setdefault(sid, []).append(desc)
        # 백그라운드 Bash · Monitor — 시작(bg_start)에 끝(bg_end)이 아직 없는 것. 살아 있는 세션만(11-06)
        live_ids = [r[0] for r in visible if r[1] in live] or [0]
        bgs: dict[int, list[tuple[Any, ...]]] = {}
        for sid_, task, tool, desc, ts in (await c.execute(text(
                "SELECT s.session_id, s.target, s.tool, JSON_UNQUOTE(JSON_EXTRACT(s.payload, '$.description')), s.ts "
                "FROM event s WHERE s.session_id IN (" + ",".join(str(int(i)) for i in live_ids) + ") "
                "AND s.type = 'bg_start' AND s.ts > :cut AND NOT EXISTS (SELECT 1 FROM event e WHERE "
                "e.session_id = s.session_id AND e.type = 'bg_end' AND e.target = s.target) ORDER BY s.ts"),
                {"cut": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)})).all():
            bgs.setdefault(sid_, []).append((task, tool, None if desc in (None, "null") else desc, ts))
        toks ={r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT t.session_id, SUM(m.token_input), SUM(m.token_output), SUM(m.token_cache_read), "
            f"SUM(m.token_cache_creation), SUM(IF(m.created_at >= :today, m.token_output, 0)), "
            f"SUM(IF(m.created_at >= :today, m.token_input + m.token_cache_read + m.token_cache_creation, 0)) "
            f"FROM message m JOIN turn t ON t.id = m.turn_id WHERE t.session_id IN {in_ids} AND m.subagent_id IS NULL "
            f"GROUP BY t.session_id"), {"today": today})).all()}
        sub_toks = {r[0]: r[1:] for r in (await c.execute(text(
            f"SELECT session_id, SUM(token_input + token_cache_read + token_cache_creation), SUM(token_output) "
            f"FROM subagent_run WHERE session_id IN {in_ids} GROUP BY session_id"))).all()}
        # 모델별 토큰(11-05) — 서브에이전트 메시지도 띄운 턴에 붙어 있으므로 message만 묶으면 겹치지 않는다
        by_model: dict[int, list[dict[str, Any]]] = {}
        for sid_, model, tin, tout, din, dout in (await c.execute(text(
                f"SELECT t.session_id, m.model, SUM(m.token_input + m.token_cache_read + m.token_cache_creation), "
                f"SUM(m.token_output), SUM(IF(m.created_at >= :today, m.token_input + m.token_cache_read + m.token_cache_creation, 0)), "
                f"SUM(IF(m.created_at >= :today, m.token_output, 0)) "
                f"FROM message m JOIN turn t ON t.id = m.turn_id WHERE t.session_id IN {in_ids} AND m.model <> '<synthetic>' "
                f"GROUP BY t.session_id, m.model ORDER BY SUM(m.token_output) DESC"), {"today": today})).all():
            by_model.setdefault(sid_, []).append({
                "model": model, "label": model_label(model), "family": model_family(model),
                "input": int(tin or 0), "output": int(tout or 0), "today_input": int(din or 0), "today_output": int(dout or 0)})
        # 압축 알림(11-05) — 세션별 압축 횟수 · 단계(due 2번 · late 4번, notify.toml [compact])
        cmp = await compact_status(c, [r[0] for r in visible], request.app.state.compact_rules)
        # 맥락 크기(11-08) — 마지막 본 대화 응답의 맥락. 300k "넘어갈 때" · 500k "늦었음"(notify.toml [compact] context_at)
        ctx = await context_status(c, [r[0] for r in visible], request.app.state.compact_rules)
        # 응답 하나가 이 맥락을 다시 읽는 값(캐시 읽기 정가, config/usage.toml) — 패널 띠 "응답당 약 $0.07"(11-09)
        ucfg = getattr(getattr(request.app.state, "usage", None), "cfg", None)
        for v in ctx.values():
            p = ucfg.price(v["model"]) if ucfg else None
            v["usd_reply"] = round(v["tokens"] * p.get("cache_read", 0.0) / 1e6, 3) if p else None
        # 작업 전환 권유(11-09, bridge/switchwatch.py) — 텔레그램과 같은 판정을 패널 띠에도. 쌓인 대화가 문턱 이상인 세션만 본다
        switch = await _switch_status(c, ctx, request.app.state.compact_rules.switch_min_pct)
        # 지금 모델 — 본 대화(서브에이전트 아님)의 마지막 응답. 세션 안에서 /model로 바꾸면 따라간다
        cur_model = {r[0]: r[1] for r in (await c.execute(text(
            f"SELECT t.session_id, m.model FROM message m JOIN turn t ON t.id = m.turn_id JOIN ("
            f"  SELECT t2.session_id, MAX(m2.created_at) mx FROM message m2 JOIN turn t2 ON t2.id = m2.turn_id "
            f"  WHERE t2.session_id IN {in_ids} AND m2.subagent_id IS NULL AND m2.model <> '<synthetic>' GROUP BY t2.session_id"
            f") x ON x.session_id = t.session_id AND x.mx = m.created_at WHERE m.subagent_id IS NULL"))).all()}
        nt = getattr(request.app.state, "notifier", None)
        relay_on = {k: (r.relay_reports, r.relay_questions) for k, r in (getattr(getattr(nt, "rules", None), "projects", None) or {}).items()}
        needs = await human_needs(c, in_ids, relay_on)
        apistop = await api_stops(c, in_ids)
        appr = (await c.execute(text(
            "SELECT id, session_id, tool, target, rule, reason, created_at, summary FROM approval WHERE status = 'pending' "
            "ORDER BY id"))).all()
        appr_rows = appr
    projects: dict[str | None, list[dict[str, Any]]] = {}
    ovl = getattr(request.app.state, "overlap", None)     # 겹침 알림(11-06, bridge/overlap.py) — 패널 띠
    mwait = merge_waits(getattr(getattr(request.app.state, "handoff", None), "mergeprep", None))   # 합치기 카드 대기(11-11)
    for sid, cc, cwd, attached, detached, char, project, last_ts, title, role, custom, model_req in visible:
        ls = live.get(cc)
        cc_status = _status(s.sessions_dir, ls.pid) if ls else None
        te = _tmux_env(ls.pid) if ls else None
        ot = open_turns.get(sid)
        act = acts.get(sid)
        tk = toks.get(sid) or (0, 0, 0, 0, 0, 0)
        st_ = sub_toks.get(sid) or (0, 0)
        projects.setdefault(project, []).append({
            "id": sid, "cc_session_id": cc, "short": (cc or "")[:8], "character": char, "project": project,
            # 세션을 알아보는 이름: CC가 붙인 제목(ai-title) → 살아 있으면 CC 세션 이름(예: runshoes-50) → 짧은 id.
            # 캐릭터(포먼 등) · 역할(coder 등)은 따로 — 한 캐릭터에 세션 여럿이 붙어 있다(2단계 입양)
            "title": title, "custom_title": custom, "cc_name": _cc_name(s.sessions_dir, ls.pid) if ls else None, "role": role,
            "cwd": cwd, "pid": ls.pid if ls else None, "proc": ls.state if ls else None, "cc_status": cc_status,
            "state": char_state(ls.state if ls else None, cc_status, ot is not None),
            # 열린 턴이 있는데 CC는 일하지 않는다 — 끝 신호 없이 멈춘 턴(숨기지 않고 따로 보인다)
            "stuck_turn": bool(ot is not None and ls and ls.state != "T" and cc_status not in (None, "busy")),
            "injectable": bool(ls and te and ls.state != "T"), "tmux_pane": te[1] if te else None,
            "open_turn": {"id": ot[0], "origin": ot[1], "started_at": _iso(ot[2]), "prompt": ot[3]} if ot else None,
            "activity": {"tool": act[0], "target": (act[1] or "")[:200], "ts": _iso(act[2]),
                         "subagent": act[3] is not None,
                         # 11-14 Bash 도구에 CC가 붙인 하는 일 한 줄(수집기가 이미 가린 값). 없으면 화면이 명령 머리로 고른다
                         "description": ((act[4] or "").strip()[:200] or None) if act[4] not in (None, "null") else None,
                         } if act else None,
            # 11-09 사람이 해야 풀리는 것 — CC 자체 권한 거부(auto mode) · 글로 묻고 기다림(일하지 않을 때만)
            "denied": (needs.get(sid) or {}).get("denied"),
            # 11-13 API 오류로 멈춤 — 마지막 턴이 stop_failure로 끝났고 새 턴이 없다(api_stops). 살아 있고 멈춰 두지(T) 않았고
            # 일하지 않을 때만 — 끝난 세션은 「끝남」이, 멈춰 둔 세션은 사람이 일부러 둔 것이다
            "api_stop": apistop.get(sid) if ls and ls.state != "T" and cc_status != "busy" and ot is None else None,
            "asks": (needs.get(sid) or {}).get("asks") if cc_status != "busy" and ot is None else None,
            # 보고 옴(11-11) — 묻지 않고 끝난 응답을 사람이 아직 안 읽음. 일하는 중이면 내지 않는다
            "report": (needs.get(sid) or {}).get("report") if cc_status != "busy" and ot is None else None,
            # 11-13 작업 세션 — 그 보고 · 물음을 관리자에게 넘겼다(사람용 report · asks 대신 작게). 일하는 중이면 내지 않는다
            "relayed": (needs.get(sid) or {}).get("relayed") if cc_status != "busy" and ot is None else None,
            # 11-13 관리자가 사람에게 올린 것 {report?, question?} — 관리자가 일하는 중이어도 남는다(사람이 읽거나 답할 때까지)
            "escalate": (needs.get(sid) or {}).get("escalate"),
            # 합치기 기다림(11-11) — 카드는 세션 탭 안에만 보여 사람이 몰랐다. 캐릭터 머리 위 · 승인 막대가 이걸 읽는다
            "merge_wait": mwait.get(sid),
            "subagents_running": len(subs.get(sid, [])),
            "subagent_descs": [d for d in subs.get(sid, []) if d][:10],
            # 턴이 끝나도 도는 일 — 백그라운드 Bash · Monitor. 상태 값은 늘리지 않고(docs/00_design.md 3.11) 화면이 "기다림"으로 그린다
            "background": background_running(bgs.get(sid, []), _started(s.sessions_dir, ls.pid) if ls else None, cc)[:10],
            "tokens": {"input": int(tk[0] or 0) + int(tk[2] or 0) + int(tk[3] or 0), "output": int(tk[1] or 0),
                       "today_output": int(tk[4] or 0), "today_input": int(tk[5] or 0),
                       "subagent_input": int(st_[0] or 0), "subagent_output": int(st_[1] or 0),
                       "by_model": by_model.get(sid, [])},
            # 모델 — model: 지금 쓰는 것(마지막 응답), model_req: 띄울 때 또는 패널 모델 창에서 고른 것(입양한 세션 · CC 설정이면 null)
            "model": cur_model.get(sid), "model_label": model_label(cur_model.get(sid)),
            "model_family": model_family(cur_model.get(sid)), "model_req": model_req,
            "compact": cmp.get(sid),
            "context": ctx.get(sid),
            "switch": switch.get(sid),
            "overlap": ovl.for_session(sid) if ovl else None,
            "last_ts": _iso(last_ts), "attached_at": _iso(attached), "detached_at": _iso(detached),
            # 끝난 세션(11-11, UI 불만 (나)) — 어떻게 끝났는지. 화면이 「끝남 — 합쳤습니다」로 갈라 옛 보고를 지난 일로 보인다
            "ended": ended_info(done.get(sid), detached) if not ls else None,
            # 멈춤(11-11, bridge/stallwatch.py) — 작업 중 끊김 · 응답 없음 · 맴돎 · 끝내기 확인 창 · 긴 작업. 1분마다 잰 마지막 값
            "stall": (stall.snapshot.get(sid) if (stall := getattr(request.app.state, "stallwatch", None)) else None) or None,
        })
    order = {"ACTIVE": 0, "SUSPENDED": 1, "IDLE": 2, "DORMANT": 3}
    out_projects = []
    for name in [*PROJECT_ORDER, *sorted(k for k in projects if k and k not in PROJECT_ORDER), None]:
        if name not in projects:
            continue
        ss = sorted(projects[name], key=lambda x: (order[x["state"]], -(datetime.fromisoformat(x["last_ts"][:-1]).timestamp() if x["last_ts"] else 0)))
        out_projects.append({"name": name, "label": LABEL.get(name, name), "sessions": ss})
    data = {
        "generated_at": _iso(datetime.now(UTC).replace(tzinfo=None)),
        "ui": ui_version(),                   # 화면 코드 지문 — 열린 페이지가 옛 코드면 [새로 고침] 띠(11-09)
        "projects": out_projects,
        "approvals": [{"id": a[0], "session_id": a[1], "tool": a[2], "target": a[3], "rule": a[4], "reason": a[5],
                       "created_at": _iso(a[6]), "summary": a[7], "status": "pending",
                       # 질문(AskUserQuestion)이면 선택지 — 패널에서 바로 답한다(11-09). 브리지가 다시 뜨면 없다(터미널에서)
                       "questions": am.questions_of(a[0]) if (am := getattr(request.app.state, "approvals", None)) else None}
                      for a in appr_rows],
        "hidden_dormant": len(rows) - len(visible),
        "terminal": term.snapshot() if (term := getattr(request.app.state, "terminal", None)) else {"enabled": False},
        # 적재(수집기) 상태 — 막히면 머리 띠(11-03, bridge/ingest_health.py)
        "ingest": mon.snapshot() if (mon := getattr(request.app.state, "ingest_monitor", None)) else None,
    }
    _cache.update(at=time.monotonic(), data=data)
    return data


@router.get("/sessions/{session_id}/conversation")
async def conversation(session_id: int, request: Request, limit: int = 15) -> dict[str, Any]:
    """최근 턴 — 입력(내 프롬프트 · 완료 알림 등)과 그 턴의 마지막 응답. 도구 결과 본문은 DB에 없다(2단계 원칙)."""
    limit = max(1, min(limit, 50))
    async with request.app.state.store.engine.connect() as c:
        if (await c.execute(text("SELECT 1 FROM character_session WHERE id = :s"), {"s": session_id})).first() is None:
            raise HTTPException(404, "세션 없음")
        turns = (await c.execute(text(
            "SELECT t.id, t.seq, t.origin, t.started_at, t.ended_at, t.end_reason, t.duration_ms, "
            "LEFT(t.prompt_text, 12000), "
            "(SELECT JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.text')) FROM event e WHERE e.turn_id = t.id "
            " AND e.type = 'assistant_msg' AND e.subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.block')) = 'text' "
            " ORDER BY e.id DESC LIMIT 1), "
            "(SELECT COUNT(*) FROM event e WHERE e.turn_id = t.id AND e.type = 'tool_use' AND e.subagent_id IS NULL), "
            "(SELECT COUNT(*) FROM subagent_run sr WHERE sr.spawn_turn_id = t.id) "
            "FROM turn t WHERE t.session_id = :s ORDER BY t.seq DESC LIMIT :n"), {"s": session_id, "n": limit})).all()
        # 마지막 응답 앞의 중간 글(터미널에는 도구 호출 사이사이 보인다 — 11-05 패널 개선). 턴마다 최근 12개, 각 3000자
        mid: dict[int, list[str]] = {}
        queued: dict[int, list[dict[str, Any]]] = {}
        api_err: dict[int, dict[str, Any]] = {}
        ids = [r[0] for r in turns]
        if ids:
            rows = (await c.execute(text(
                "SELECT turn_id, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')) FROM event WHERE turn_id IN :ids "
                "AND type = 'assistant_msg' AND subagent_id IS NULL AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.block')) = 'text' "
                "ORDER BY id").bindparams(bindparam("ids", expanding=True)), {"ids": ids})).all()
            for tid, t_ in rows:
                if t_:
                    mid.setdefault(tid, []).append(t_)
            # 작업 중에 보낸 입력 — 새 턴이 되지 않고 대기열로 열린 턴에 끼어든다(queued_command attachment, op=delivered).
            # 전에는 대화 패널이 턴의 첫 프롬프트만 보여서 이 글들이 아예 안 보였다(11-05 사용자 보고)
            qrows = (await c.execute(text(
                "SELECT turn_id, ts, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.prompt')) FROM event WHERE turn_id IN :ids "
                "AND type = 'queued' AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.op')) = 'delivered' ORDER BY ts, id"
            ).bindparams(bindparam("ids", expanding=True)), {"ids": ids})).all()
            for tid, ts_, p in qrows:
                if p and p != "null":
                    queued.setdefault(tid, []).append({"ts": _iso(ts_), "text": p})
            # API 오류의 까닭(11-11, bridge/api_error.py) — 「API 오류」만이 아니라 종류 · 할 일 · request id. 읽을 때 가르므로 옛 오류도
            for tid, t_, err in (await c.execute(text(
                    "SELECT turn_id, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.text')), JSON_UNQUOTE(JSON_EXTRACT(payload, '$.error')) "
                    "FROM event WHERE turn_id IN :ids AND type = 'error' ORDER BY id").bindparams(bindparam("ids", expanding=True)),
                    {"ids": ids})).all():
                if (t_ and t_ != "null") or tid not in api_err:     # 글이 있는 것(트랜스크립트)이 hook 것(error 값만)보다 낫다
                    ce = classify_api_error(t_ if t_ != "null" else None, err if err != "null" else None)
                    api_err[tid] = {**ce, "line": api_error_line(ce)}
    return {"session_id": session_id, "turns": [
        {"id": r[0], "seq": r[1], "origin": r[2], "started_at": _iso(r[3]), "ended_at": _iso(r[4]),
         "end_reason": r[5], "duration_ms": r[6], "prompt": r[7], "reply": (r[8] or "")[:20000],
         "mid": [x[:3000] for x in mid.get(r[0], [])[:-1][-12:]],
         "queued": queued.get(r[0], [])[-20:],
         "api_error": api_err.get(r[0]) if r[5] == "stop_failure" else None,
         "tools": r[9], "subagents": r[10]} for r in reversed(turns)]}


# ── 11-05 활동 줄 · 도구 본문 — 터미널처럼 "무엇을 읽고 무엇이 나왔나". 본문은 DB에 없다 — 누를 때만 트랜스크립트에서 ──
@router.get("/sessions/{session_id}/activity")
async def activity(session_id: int, request: Request, limit: int = 40) -> dict[str, Any]:
    """최근 도구 호출(메인 + 서브에이전트) — 화면을 연 뒤가 아니라 DB에서. 결과 상태는 같은 tool_use_id의 tool_result."""
    limit = max(1, min(limit, 200))
    async with request.app.state.store.engine.connect() as c:
        rows = (await c.execute(text(
            "SELECT e.id, e.ts, e.tool, e.target, e.subagent_id, e.tool_use_id, "
            "(SELECT r.status FROM event r WHERE r.session_id = e.session_id AND r.type = 'tool_result' "
            " AND r.tool_use_id = e.tool_use_id LIMIT 1) "
            "FROM event e WHERE e.session_id = :s AND e.type = 'tool_use' ORDER BY e.id DESC LIMIT :n"),
            {"s": session_id, "n": limit})).all()
        # 11-09 세션 간 메시지 — 받는 쪽 트랜스크립트(대기열 줄)로 도착 · 읽음
        sends = [r[0] for r in rows if r[2] == "SendMessage"]
        xm: dict[int, dict[str, Any]] = {}
        if sends:
            from bridge import xmsg
            got = (await c.execute(text(
                "SELECT id, ts, JSON_UNQUOTE(JSON_EXTRACT(payload, '$.input.message')), JSON_UNQUOTE(JSON_EXTRACT(payload, '$.input.to')) "
                "FROM event WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": sends})).all()
            xm = await xmsg.statuses(c, [(r[0], r[1], r[2] or "") for r in got if xmsg.is_session_target(r[3])])
    return {"session_id": session_id, "items": [
        {"id": r[0], "ts": _iso(r[1]), "tool": r[2], "target": (r[3] or "")[:200], "subagent": bool(r[4]),
         "has_body": bool(r[5]), "status": r[6],
         **({"xmsg": {k: (_iso(v) if isinstance(v, datetime) else v) for k, v in xm[r[0]].items()}} if r[0] in xm else {})}
        for r in reversed(rows)]}


@router.get("/events/{event_id}/detail")
async def event_detail(event_id: int, request: Request) -> dict[str, Any]:
    """도구 호출 하나의 입력 전체 · 결과 본문. 비밀값은 가린다(Masker + URL 자격증명)."""
    from bridge.mask import Masker
    from bridge.terminal import mask_output
    from bridge.transcript.lookup import clip_input, clip_text, find_tool_call
    async with request.app.state.store.engine.connect() as c:
        r = (await c.execute(text(
            "SELECT e.type, e.tool_use_id, e.tool, e.subagent_id, "
            " (SELECT tf.path FROM character_session cs JOIN transcript_file tf ON tf.id = cs.transcript_file_id "
            "  WHERE cs.id = e.session_id), "
            " (SELECT tf.path FROM subagent_run sr JOIN transcript_file tf ON tf.agent_id = sr.agent_id "
            "  WHERE sr.id = e.subagent_id LIMIT 1) "
            "FROM event e WHERE e.id = :i"), {"i": event_id})).first()
    if r is None:
        raise HTTPException(404, "이벤트 없음")
    etype, tuid, tool, sub_id, main_path, sub_path = r
    if etype not in ("tool_use", "tool_result") or not tuid:
        raise HTTPException(400, "도구 호출이 아니다")
    path = sub_path if sub_id else main_path
    if not path or not os.path.exists(path):
        raise HTTPException(410, "트랜스크립트 파일이 없다(지워졌거나 옮겨졌다)")
    t0 = time.monotonic()
    found = await asyncio.to_thread(find_tool_call, path, tuid)
    m = Masker()
    result, n = clip_text(found["result"])
    return {"event_id": event_id, "tool": found["name"] or tool, "tool_use_id": tuid,
            "input": m.deep(clip_input(found["input"])) if found["input"] is not None else None,
            "result": mask_output(m, result) if result is not None else None, "result_chars": n,
            "is_error": found["is_error"], "extra": m.deep(found["extra"]), "other_blocks": found["other_blocks"],
            "found": found["found"], "file": os.path.basename(path), "ms": round((time.monotonic() - t0) * 1000)}
