"""시연 대본 만들기(13, docs/13_demo_capture.md) — 실제 기록(DB · /api/pipeline)을 재생 대본으로. 결과는 bridge/static/demo/<이름>.json

    .venv/bin/python tools/demo_from_db.py all

- **실제 기록 재생(source=record):** 도구 순서 · 서브에이전트 수 · 승인 규칙 · 빌드 단계 순서는 실제 기록 그대로. 간격만 화면에 맞게 줄인다
  (걸어가는 시간이 보이게 한 단계 2 ~ 3초). 세션 이름 · 경로 · 명령 · 프롬프트는 대본에 남기지 않는다(시연용 이름, 명령은 종류만)
- **대본(source=script):** 실제 기록으로 안 되는 장면만 — 인계 미리보기(인계 본문은 실제 대화라 넣지 않는다) · 겹침 띠
- 대본 안의 시각은 "@+ms"(재생 시작 기준) — demo.js가 재생할 때 실제 시각으로 바꾼다
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import urllib.request
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bridge.config import get_settings  # noqa: E402
from bridge.db.engine import make_engine  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "bridge" / "static" / "demo"
LABEL = {"runshoes": "런슈즈", "petmint-rag-chatbot": "펫퍼민트", "foreman": "FOREMAN", "ronanlab-infra": "인프라"}
WANDER_TURN, SUB_TURN, APPROVAL_ID = 5762, 5823, 1        # 11-06 고른 실제 기록(아래 각 함수)


def sess(sid: int, project: str, title: str, *, state: str = "ACTIVE", tool: str | None = None, target: str = "",
         role: str = "coder", subs: int = 0, **kw: object) -> dict:
    """화면이 그리는 세션 한 개(/api/dashboard 모양) — 시연용 이름."""
    busy = state == "ACTIVE"
    s = {"id": sid, "cc_session_id": f"demo-{sid:04d}", "short": f"demo{sid:04d}", "character": "코더", "project": project,
         "title": title, "custom_title": None, "cc_name": None, "role": role, "cwd": f"/demo/{project}", "pid": 10000 + sid,
         "proc": "S", "cc_status": "busy" if busy else "idle", "state": state, "stuck_turn": False, "injectable": True,
         "tmux_pane": None, "open_turn": {"id": sid * 10, "origin": "human", "started_at": "@-30000", "prompt": "시연"} if busy else None,
         "activity": {"tool": tool, "target": target, "ts": "@-1000", "subagent": False} if tool else None,
         "subagents_running": subs, "subagent_descs": ["조사"] * subs, "background": [],
         "tokens": {"input": 0, "output": 0, "today_output": 0, "today_input": 0, "subagent_input": 0, "subagent_output": 0, "by_model": []},
         "model": "claude-opus-5-5", "model_label": "Opus 5.5", "model_family": "opus", "model_req": "opus", "compact": None,
         "overlap": None, "last_ts": "@-1000", "attached_at": "@-600000", "detached_at": None}
    s.update(kw)
    return s


def convo(sid: int, *pairs: tuple[str, str | None]) -> dict:
    """패널 [대화] 탭에 보일 시연 대화 — 비면 화면이 "불러오는 중…"으로 남는다. 마지막 턴의 답이 None이면 진행 중."""
    turns = []
    for k, (prompt, reply) in enumerate(pairs):
        done = reply is not None
        turns.append({"id": sid * 100 + k, "seq": k + 1, "origin": "human", "started_at": f"@-{(len(pairs) - k) * 60000}",
                      "ended_at": f"@-{(len(pairs) - k) * 60000 - 30000}" if done else None, "end_reason": "stop" if done else None,
                      "duration_ms": 30000 if done else None, "prompt": prompt, "reply": reply, "mid": [], "queued": [],
                      "tools": 6, "subagents": 0})
    return {f"/api/sessions/{sid}/conversation": {"session_id": sid, "turns": turns}}


def snapshot(*extra: dict) -> dict:
    """세 프로젝트 방이 다 서도록 쉬는 세션 하나씩 + 장면 세션."""
    base = [sess(901, "runshoes", "카탈로그 정리", state="IDLE"), sess(902, "petmint-rag-chatbot", "평가셋 재검수", state="IDLE")]
    ss = base + list(extra)
    projects = [{"name": p, "label": LABEL[p], "sessions": [s for s in ss if s["project"] == p]} for p in LABEL]
    return {"generated_at": "@+0", "projects": projects, "approvals": [], "hidden_dormant": 0,
            "terminal": {"enabled": False}, "ingest": None}


def tool_target(tool: str, tgt: str | None) -> str:
    """명령 · 경로는 남기지 않는다 — 구역을 가르는 종류만(theme.json tools 규칙이 보는 낱말)."""
    t = tgt or ""
    if tool == "Bash":
        if re.search(r"\b(pytest|node --test|bash -n|py_compile|ruff)\b", t):
            return "pytest -q"
        if re.search(r"(^|[;&|(]\s*)git\b", t):
            return "git status"
        return "ls"
    return ""


def ev(sid: int, at: int, typ: str, tool: str | None = None, target: str = "", source: str = "transcript") -> dict:
    return {"at": at, "msg": {"type": "event", "event": {"id": None, "source": source, "type": typ, "tool": tool, "target": target,
                                                          "status": None, "turn_id": sid * 10, "session_id": sid, "subagent_id": None,
                                                          "project": None, "ts": f"@+{at}", "summary": None}}}


async def wander(c) -> dict:
    """V1 — 실제 턴 하나의 도구 순서에서 구역이 바뀌는 곳만, 작업 책상 → 물약실 → 시약대가 처음 이어지는 구간부터 다섯 걸음."""
    rows = (await c.execute(text("SELECT tool, target FROM event WHERE turn_id = :t AND type = 'tool_use' AND source = 'transcript' "
                                 "AND subagent_id IS NULL ORDER BY ts"), {"t": WANDER_TURN})).all()
    zone = lambda tool, tt: ("test" if tt == "pytest -q" else "seal" if tt == "git status" else "potion") if tool == "Bash" else (  # noqa: E731
        "desk" if re.match(r"Edit|Write", tool) else "library" if re.match(r"Read|Grep|Glob", tool) else tool)
    seq = []
    for tool, tgt in rows:
        tt = tool_target(tool, tgt)
        if not seq or zone(*seq[-1]) != zone(tool, tt):
            seq.append((tool, tt))
    zs = [zone(*x) for x in seq]
    i = next(k for k in range(len(zs) - 2) if zs[k:k + 3] == ["desk", "potion", "test"])
    pick = seq[i:i + 5]
    steps = [ev(951, 400 + n * 2600, "tool_use", tool, tt) for n, (tool, tt) in enumerate(pick)]
    steps.append({"at": 400 + len(pick) * 2600, "end": True})
    s = sess(951, "foreman", "코더 — 화면 고침", tool=pick[0][0], target=pick[0][1])
    return {"title": "구역 옮겨 다니기", "source": "record",
            "note": f"실제 턴 {WANDER_TURN}의 도구 순서(구역이 바뀌는 곳만) — 간격은 한 걸음 2.6초로", "snapshot": snapshot(s), "steps": steps}


async def subagents(c) -> dict:
    """V3 — 실제 턴에서 띄운 서브에이전트 수만큼 소환(원탁방) → 일 → 끝(연기). 소환은 실제처럼 거의 동시에."""
    n = (await c.execute(text("SELECT COUNT(*) FROM event WHERE turn_id = :t AND type = 'subagent_start'"), {"t": SUB_TURN})).scalar() or 0
    s = sess(952, "foreman", "코더 — 조사 맡김", tool="Agent")
    steps = [ev(952, 300, "tool_use", "Agent")]
    steps += [ev(952, 900 + k * 120, "subagent_start") for k in range(n)]
    steps += [ev(952, 4200 + k * 500, "subagent_stop") for k in range(n)]
    steps += [ev(952, 4200 + n * 500 + 300, "tool_use", "Edit"), {"at": 4200 + n * 500 + 1600, "end": True}]
    return {"title": "서브에이전트 소환 · 끝", "source": "record", "note": f"실제 턴 {SUB_TURN}의 서브에이전트 {n}개 — 일한 시간은 줄였다",
            "snapshot": snapshot(s), "steps": steps}


async def approval(c) -> dict:
    """V5 — 실제 승인 기록(규칙 · 도구 · 브라우저 허용). 캐릭터가 손을 들고 카드가 뜬다 → [허용] → 다시 일한다."""
    a = (await c.execute(text("SELECT tool, rule, reason, status FROM approval WHERE id = :i"), {"i": APPROVAL_ID})).first()
    s = sess(953, "foreman", "코더 — 정리", tool="Bash", target="ls")
    ap = {"id": 9001, "session_id": 953, "tool": a[0], "target": "rm -r junk-a", "rule": a[1], "reason": a[2], "created_at": "@+1500",
          "summary": "rm -r junk-a — 시험용 폴더 지우기"}
    steps = [{"at": 300, "js": "window.office.openSession(953)"},
             {"at": 1500, "msg": {"type": "approval", "op": "pending", "approval": ap}},
             {"at": 6000, "msg": {"type": "approval", "op": "resolved", "approval": {**ap, "status": a[3], "decided_by": "browser"}}},
             ev(953, 6600, "tool_use", "Bash", "ls"), {"at": 9500, "end": True}]
    return {"title": "승인 요청 → 처리", "source": "record",
            "note": f"실제 승인 {APPROVAL_ID}(11-02 승인 시스템 시험, 규칙 {a[1]}, 브라우저에서 {a[3]}) — 명령은 실제 그대로(시험용)",
            "snapshot": snapshot(s), "steps": steps,
            "api": convo(953, ("시험 폴더 정리해 줘", "남은 시험 폴더를 확인했습니다. junk-a를 지우겠습니다."), ("지워 줘", None))}


def pipeline() -> dict:
    """V2 — 실제 런슈즈 빌드(#68)의 단계 순서: 커밋 → ① 빌드 → ② 이미지 → ③ 배포. 실제 4분 26초 · 4초를 몇 초로."""
    tok = next(ln.split("=", 1)[1].strip().strip('"') for ln in (REPO / ".env.bridge").read_text().splitlines()
               if ln.startswith("FOREMAN_API_TOKEN="))
    req = urllib.request.Request("http://127.0.0.1:8000/api/pipeline", headers={"Authorization": f"Bearer {tok}"})
    pj = next(p for p in json.load(urllib.request.urlopen(req, timeout=20))["projects"] if p["project"] == "runshoes")
    real = next(ch for ch in pj["chains"] if (ch["stages"].get("jenkins") or {}).get("ext") == "runshoes-app#68")
    head = real["head"]
    commit = {"sha": head, "short": head[:8], "subject": "카탈로그 숫자 고침", "session_id": 961, "title": "코더", "character": "코더", "author": "demo"}

    def chain(j: dict, a: dict | None, at: str) -> dict:
        st = {"jenkins": {"status": "none", "step": None, "ext": "runshoes-app#68", "url": None, "message": None, **j}}
        if a:
            st["argocd"] = {"status": "none", "step": None, "ext": "runshoes", "url": None, "message": None, **a}
        return {"head": head, "short": head[:8], "commits": [commit], "stages": st, "broke": None, "at": at}

    old = {"head": "0" * 40, "short": "00000000", "commits": [], "broke": None, "at": "@-7200000",
           "stages": {"jenkins": {"status": "success", "started_at": "@-7300000", "ended_at": "@-7250000"},
                      "argocd": {"status": "success", "started_at": "@-7240000", "ended_at": "@-7200000"}}}
    base = {k: pj[k] for k in ("project", "infra", "waiting", "watch", "webhook_broken")}
    base["waiting"], base["watch"] = [], None

    def state(*chains: dict) -> dict:
        return {"runshoes": {**base, "chains": [*chains, old]}}
    steps = [
        {"at": 1200, "pipeline": state(chain({"status": "running", "started_at": "@+1200", "step": "Test"}, None, "@+1200"))},
        {"at": 9000, "pipeline": state(chain({"status": "running", "started_at": "@+1200", "step": "Push to Harbor"}, None, "@+1200"))},
        {"at": 12500, "pipeline": state(chain({"status": "success", "started_at": "@+1200", "ended_at": "@+12500"},
                                              {"status": "running", "started_at": "@+12600"}, "@+12600"))},
        {"at": 15000, "pipeline": state(chain({"status": "success", "started_at": "@+1200", "ended_at": "@+12500"},
                                              {"status": "success", "started_at": "@+12600", "ended_at": "@+15000",
                                               "message": "successfully synced"}, "@+15000"))},
        {"at": 18000, "end": True}]
    s = sess(961, "runshoes", "코더 — 카탈로그", tool="Bash", target="git status")
    snap = snapshot(s)
    return {"title": "출하 라인", "source": "record",
            "note": "실제 런슈즈 빌드 #68의 단계 순서(빌드 4분 26초 · 배포 4초) — 몇 초로 줄였다. 커밋 제목은 시연용",
            "snapshot": snap, "pipeline": state(), "steps": steps}


def still() -> dict:
    """V4 — 테마 전환용. 같은 순간의 한 방(작업 · 쉼 · 서기)을 테마만 바꿔 찍는다(테마 링크는 실제 조작)."""
    ss = [sess(971, "foreman", "코더 — 화면 고침", tool="Edit"), sess(972, "foreman", "코더 — 시험", tool="Bash", target="pytest -q"),
          sess(973, "foreman", "코더 — 조사", tool="Read"), sess(974, "foreman", "서기 — 정리", role="scribe", tool="Edit")]
    return {"title": "같은 순간, 세 테마", "source": "script", "note": "테마 전환은 실제 조작 — 세션 넷은 시연용 정지 장면",
            "snapshot": snapshot(*ss), "steps": [{"at": 60000, "end": True}]}


def handoff() -> dict:
    """V6(대본) — 압축 2번 띠 → [세션] 탭 → [새로 띄우기] 미리보기의 「인계 뒤 바뀐 것」. 인계 본문은 실제 대화라 시연 글로 쓰고,
    바뀐 것 네 줄은 11-06 실제로 겪은 일(r=690cec — worktree 없어짐 · 합쳐짐 · 새 커밋 · 잠금 주인)을 옮겼다."""
    s = sess(981, "foreman", "코더 — 인계 2판", tool="Edit",
             compact={"count": 2, "last_ts": "@-20000", "level": "due", "short": False, "gaps": []})
    body = ("## 지금 상태\n- worktree foreman-2에서 c를 만들었다. 아직 합치지 않았다\n## 다음 할 일\n1. 합친 뒤 첫 실제 사례로 확인\n"
            "## 문서와 다른 지금\n- 순서는 c → d → 12a\n## 읽을 곳\n- `docs/11_handoff_v2.md:115-138` — d 설계")
    drift = ["인계를 쓴 지 1시간 28분 지났습니다.",
             "worktree `foreman-2`(브랜치 `cc/foreman-2`)는 지금 없습니다 — 인계 때 커밋 edcd41a은 `main`에 합쳐졌습니다.",
             "`main`에 인계 뒤 커밋이 7개 생겼습니다: 겹침 알림 / 사람이 붙인 세션 이름이 항상 이기게 / 글씨 한 번 더 키움 외 4개",
             "스키마 잠금이 세션 65d05e2c(worktree foreman-2)에서 세션 5a3b93e0로 바뀌었습니다."]
    text_ = ("[FOREMAN 인계 r=690cec] 직전 세션의 인계다. 너는 이 일을 이어받는 새 세션이다.\n**먼저 아래 「읽을 곳」을 모두 Read로 읽어라** …\n\n"
             "## 인계 뒤 바뀐 것 (브리지가 git · 잠금으로 확인)\n" + "\n".join(f"- {x}" for x in drift) + "\n\n" + body)
    api = {"/api/sessions/981/handoff": {
        "controls": {"live": True, "pid": 11981, "state": "S", "tmux": True, "busy": False, "pending_req": None, "foreman_stopped": False,
                     "why": "살아 있음", "can": {"summary": True, "promote": True, "headless": False, "compact": False, "exit": True,
                                                 "stop": True, "resume": False, "interrupt": True, "spawn": True},
                     "worktree": None, "reads": None, "losscheck": True},
        "summaries": [{"id": 77, "kind": "handoff", "source": "self", "status": "ok", "created_at": "@-5280000", "chars": len(body),
                       "body": body, "raw": None, "error": None, "injected_at": None, "injected_cc_session": None}],
        "promotions": [], "promotions_error": None, "promote_inputs": [], "losschecks": [], "losschecks_error": None},
        "/api/summaries/77/injection": {"summary_id": 77, "text": text_, "cut": False, "full_path": None, "chars": len(body), "v2": True,
                                        "pointers": [{"path": "docs/11_handoff_v2.md", "start": 115, "end": 138, "section": None,
                                                      "why": "d 설계", "raw": "", "ok": True, "problem": None, "commits_since": 0, "stale": False}],
                                        "blocked": None, "state": {}, "drift": drift},
           **convo(981, ("c 만들어 줘", "c를 만들었습니다. 시험 393개가 통과했습니다."), ("인계 요약 써 줘", "인계 요약을 저장했습니다."))}
    steps = [{"at": 300, "js": "window.office.openSession(981)"},
             {"at": 3000, "js": "document.querySelector('#pTabs [data-tab=sess]').click()"},
             {"at": 5200, "js": "document.querySelector('#pHand button[data-act=spawn]').click()"},
             {"at": 6400, "js": "const b=document.querySelector('#pHand .hand-drift'); if(b) b.scrollIntoView({block:'start'})"},
             {"at": 11000, "end": True}]
    return {"title": "압축 띠 → 인계 뒤 바뀐 것", "source": "script",
            "note": "대본 — 인계 본문은 시연 글, 「인계 뒤 바뀐 것」 네 줄은 11-06 실제 사례(r=690cec)", "snapshot": snapshot(s), "api": api, "steps": steps}


def overlap() -> dict:
    """V7(대본) — 겹침 띠. 11-06 실제 사례(같은 jenkins 조사가 두 세션에)의 낱말 · 시각을 옮겼다."""
    a = sess(982, "foreman", "코더 — 브리지 복구", tool="Bash",
             overlap={"with": 983, "with_title": "코더 — jenkins-0 조사", "since": "@-60000", "since_kst": "12:37",
                      "words": ["harbor-jobservice", "jenkins-0", "crashloopbackoff", "unknown"], "score": 6, "at": "@-3000"})
    b = sess(983, "foreman", "코더 — jenkins-0 조사", tool="Bash", target="ls")
    steps = [{"at": 300, "js": "window.office.openSession(982)"}, {"at": 5500, "end": True}]
    return {"title": "겹침 알림 띠", "source": "script", "note": "대본 — 낱말 · 시각 · 점수는 11-06 실제 사례(세션 197 · 198)",
            "snapshot": snapshot(a, b), "steps": steps,
            "api": convo(982, ("브리지 systemd 유닛 확인해 줘", "유닛은 떠 있습니다."),
                         ("jenkins-0 Unknown · harbor-jobservice CrashLoopBackOff 원인도 봐 줘", None))}


async def stills(c) -> dict:
    """정지 사진용 한 장면(13e) — 상태 넷 · 서기 둘(이름 겹침 · 근거 검토) · 잃은 것 점검 결과 · 포먼 계획 창 · 적재 막힘 띠 · 모델별 토큰.
    실제 기록에서 옮긴 것: 디스패치 계획(dispatch 마지막 행), 잃은 것 판정 항목(11-05 손 점검 정답 사본 all.json 앞의 사라짐 · 약해짐).
    나머지(세션 · 숫자)는 시연용."""
    import os
    plan = json.loads((await c.execute(text("SELECT plan FROM dispatch ORDER BY id DESC LIMIT 1"))).scalar() or "{}")
    base = Path(os.path.expanduser("~/.foreman/compaction_baseline/20261105/foreman/all.json"))
    allj = json.loads(base.read_text(encoding="utf-8")) if base.exists() else []
    lost = [x for x in allj if x.get("status") in ("사라짐", "약해짐")][:5]
    counts = {k: sum(1 for x in allj if x.get("status") == k) for k in ("사라짐", "약해짐", "뒤집힘", "살아 있음", "끝남")}
    counts["살아 있음"] = counts["살아 있음"] or sum(1 for x in allj if x.get("status") == "살아있음")
    tok = {"input": 1_890_000_000, "output": 6_400_000, "today_output": 1_200_000, "today_input": 410_000_000, "subagent_input": 0,
           "subagent_output": 0, "by_model": [
               {"model": "claude-opus-5-5", "label": "Opus 5.5", "family": "opus", "input": 1_880_000_000, "output": 6_350_000,
                "today_input": 409_000_000, "today_output": 1_190_000},
               {"model": "claude-haiku-5-5", "label": "Haiku 5.5", "family": "haiku", "input": 7_000_000, "output": 50_000,
                "today_input": 900_000, "today_output": 9_000}]}
    ss = [sess(991, "foreman", "코더 — 화면 고침", tool="Edit", tokens=tok),
          sess(992, "foreman", "코더 — 쉬는 중", state="IDLE"),
          sess(993, "foreman", "코더 — 기다려 둠", state="SUSPENDED", proc="T", cc_status=None),
          sess(994, "foreman", "코더 — 정리 마침", state="DORMANT", proc=None, cc_status=None, detached_at="@-20000", last_ts="@-20000"),
          sess(995, "foreman", "서기 — 포트폴리오 쓰기: 한눈에", role="scribe", state="IDLE", cwd="/demo/foreman/.worktrees/foreman-3"),
          sess(996, "petmint-rag-chatbot", "코더 — 평가 다시 돌림", tool="Bash", target="ls",
               compact={"count": 2, "last_ts": "@-20000", "level": "due", "short": False, "gaps": []})]
    snap = snapshot(*ss)
    snap["ingest"] = {"ok": False, "stalled": False, "tick_age_s": 1,
                      "stuck": [{"session": "런슈즈 세션", "minutes": 14, "failures": 104, "error": "IntegrityError — 같은 프롬프트 id"}]}
    ctl = {"live": True, "pid": 1, "state": "S", "tmux": True, "busy": False, "pending_req": None, "foreman_stopped": False, "why": "살아 있음",
           "can": {"summary": True, "promote": True, "headless": False, "compact": False, "exit": True, "stop": True, "resume": False,
                   "interrupt": True, "spawn": True}, "worktree": None, "reads": None, "losscheck": True}
    empty = {"summaries": [], "promotions": [], "promotions_error": None, "promote_inputs": [], "losschecks_error": None}
    review = {"marks": 70, "bad": 0, "unsupported": 2, "files": [{"path": "portfolio/00_overview.md", "bad": [],
              "unsupported": [{"line": 7, "text": "![감독실 — 프로젝트 셋과 떠돌이 라운지를 지도 한 장에 …](img/00_overview_hq.png)"}]}],
              "revision": {"draft_lines": 148, "revision_lines": 0, "draft_commits": 1, "revision_commits": 0, "ratio": 0.0}}
    wt = {"exists": True, "branch": "cc/foreman-3", "base": "main", "live": False, "ahead": 1, "behind": 0, "dirty": [], "schema_lock": False,
          "commits": ["098da51 portfolio: 00_overview — 무엇 · 왜 · 구조 · 겪은 문제 · 숫자 · 한계"],
          "diffstat": [" portfolio/00_overview.md | 148 +++++", " 2 files changed, 148 insertions(+)"], "review": review,
          "preview": None, "preview_ok": True}
    api = {
        "/api/sessions/995/handoff": {"controls": {**ctl, "live": False, "why": "끝난 세션입니다", "worktree": wt}, **empty, "losschecks": []},
        "/api/sessions/996/handoff": {"controls": ctl, **empty, "losschecks": [
            {"id": 7, "session_id": 996, "status": "done", "model": "sonnet", "cost_usd": 1.99, "groups_done": 7, "groups_total": 7,
             "created_at": "@-600000", "updated_at": "@-120000", "counts": counts, "lost_total": counts["사라짐"] + counts["약해짐"],
             "lost": lost, "error": None}]},
        "/api/foreman/plan": {"dispatch_id": 1, "ms": 18000, "plan": plan},
        "/api/spawn/options": {"home": "/demo", "projects": [{"name": p, "repo": f"/demo/{p}"} for p in LABEL], "recent_cwds": [],
                               "models": {"choices": [{"id": "opus", "label": "Opus", "note": "가장 잘하지만 비쌉니다"},
                                                      {"id": "sonnet", "label": "Sonnet", "note": "대부분의 일에 충분합니다"},
                                                      {"id": "haiku", "label": "Haiku", "note": "가볍고 빠른 일"}],
                                          "defaults": {"coder": "opus", "inspector": "sonnet", "cicd": "sonnet", "scribe": "opus"}},
                               "summaries": []},
        **convo(991, ("헤더 글씨 키워 줘", "탭 · 버튼 · 라벨을 2px 키웠습니다. 세 테마 × 세 크기 점검 0건입니다."), ("패널 접기도 봐 줘", None))}
    return {"title": "정지 사진용 장면", "source": "script",
            "note": "대본 — 계획 창은 실제 디스패치 계획, 잃은 것 목록은 11-05 손 점검의 실제 항목. 세션 · 숫자는 시연용",
            "snapshot": snap, "api": api, "steps": [{"at": 120000, "end": True}]}


async def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    OUT.mkdir(parents=True, exist_ok=True)
    e = make_engine(get_settings())
    try:
        async with e.connect() as c:
            made = {"wander": await wander(c), "subagents": await subagents(c), "approval": await approval(c), "stills": await stills(c)}
    finally:
        await e.dispose()
    made["pipeline"], made["still"], made["handoff"], made["overlap"] = pipeline(), still(), handoff(), overlap()
    for name, sc in made.items():
        if which in ("all", name):
            (OUT / f"{name}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{name}: {sc['title']} — {sc['source']}, 단계 {len(sc['steps'])}, {sc['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
