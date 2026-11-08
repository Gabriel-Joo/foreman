"""겹침 알림(11-06) — 사람 입력이 들어오면 같은 프로젝트의 살아 있는 다른 세션이 최근 받은 요청과 맞대 본다.

근거(log/infra_20261106_jenkins-harbor-after-outage.md 「같은 조사를 두 세션이 했다」): 겹침 확인은 디스패처에만 있고
디스패처는 세션을 새로 띄울 때만 돈다. 그래서 "먼저 띄운 세션의 일을 나중에 다른 세션에 다시 시키는 것"은 어디서도
보지 않았다(세션 198 · 197이 jenkins-0 · harbor-jobservice를 같이 조사).

어떻게: 드문 낱말(최근 사람 요청 전체에서 거의 안 나오는 낱말 — `jenkins-0` 같은 식별자는 무겁게)이 겹친 점수로
싸게 거른다. 걸리면 텔레그램(접두어 있는 프로젝트만) + 패널 띠. **막지 않는다** — 일부러 둘에 시킬 수 있다.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tomllib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import bindparam, text

log = logging.getLogger("foreman.overlap")

KST = timedelta(hours=9)
# 영숫자 낱말(안의 - _ . 은 잇는다 — jenkins-0, harbor-jobservice, bridge.db.migrate) · 한글 낱말
_ASCII = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.\-]*[A-Za-z0-9])?")
_HANGUL = re.compile(r"[가-힣]{2,}")
# 한글 낱말 끝의 조사 — 이것만 떼어 같은 낱말로 센다(형태소 분석은 하지 않는다)
_JOSA = ("에서는", "으로는", "에서", "으로", "에게", "까지", "부터", "보다", "처럼", "이랑", "하고",
         "은", "는", "이", "가", "을", "를", "에", "와", "과", "도", "로", "의", "만")
# 어디서나 흔한 것 — 말뭉치가 작을 때도 드문 낱말로 잡히지 않게
_STOP = frozenset("""
the and for with from that this not you are was but can all any has have will into then than when what
http https www com md py js json toml sql html css txt log docs bridge claude foreman runshoes petmint
home kopo17
""".split())
# 포먼이 내는 서기 일감(docs/12_scribe.md)은 일부러 나눠 시키는 틀 글이다 — 맞대지 않는다(11-06 다시 돌리기 헛알림의 대부분)
_SKIP_HEAD = ("[FOREMAN 서기 일감",)
_PROJ_KO = {"runshoes": "런슈즈", "petmint-rag-chatbot": "펫퍼민트", "foreman": "FOREMAN"}


def projLabel(name: str | None) -> str:  # noqa: N802 — 화면(js)의 이름과 맞춘다
    return _PROJ_KO.get(name or "", name or "미분류")


def skip(prompt: str | None) -> bool:
    head = _TAGS.sub("", (prompt or "")[:300]).lstrip()
    return head.startswith(_SKIP_HEAD)
# 시스템이 넣는 꼬리표 — 사람이 쓴 낱말이 아니다
_TAGS = re.compile(r"<(/?)(pasted_content|system-reminder|command-[a-z-]+|local-command-[a-z-]+)[^>]*>")


@dataclass
class OverlapRules:
    enabled: bool = True
    window_min: int = 180       # 다른 세션의 이 시간 안의 사람 요청과 맞댄다
    per_session: int = 5        # 다른 세션마다 최근 요청 몇 개까지
    min_score: int = 3          # 이 점수부터 알린다 — 식별자(-_. 숫자가 섞인 낱말)는 2점, 그 밖은 1점
    rare_ratio: float = 0.01    # 말뭉치(최근 사람 요청)에서 이 비율 이하로 나오면 드문 낱말
    rare_min_df: int = 3        # 말뭉치가 작을 때 — 이 문서 수 이하는 드문 낱말
    corpus_days: int = 30
    corpus_max: int = 3000
    repeat_min: int = 60        # 같은 두 세션은 이 시간 안에 다시 알리지 않는다
    show_min: int = 120         # 패널 띠를 보이는 시간


def load_rules(path: str | Path) -> OverlapRules:
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("overlap") or {}
    except OSError:
        raw = {}
    d = OverlapRules()
    return OverlapRules(**{k: type(getattr(d, k))(raw[k]) for k in d.__dataclass_fields__ if k in raw})


# ── 낱말 ─────────────────────────────────────────────────
def is_ident(w: str) -> bool:
    """식별자 — 글자와 숫자 · -_. 이 섞였다(jenkins-0, harbor-jobservice, 0020_promotion.sql, edcd41a)."""
    return bool(re.search(r"[-_.]", w) or (re.search(r"\d", w) and re.search(r"[a-z]", w)))


def _strip_josa(w: str) -> str:
    for j in _JOSA:
        if w.endswith(j) and len(w) - len(j) >= 2:
            return w[: -len(j)]
    return w


def words(s: str | None) -> set[str]:
    """요청 하나의 낱말 집합. 길이 4 미만 영문(숫자만 · 짧은 낱말)과 흔한 낱말은 뺀다."""
    if not s:
        return set()
    s = _TAGS.sub(" ", s)
    out: set[str] = set()
    for m in _ASCII.finditer(s):
        w = m.group(0).lower().strip(".-_")
        if len(w) < 4 or w.isdigit() or w in _STOP:
            continue
        out.add(w)
    for m in _HANGUL.finditer(s):
        w = _strip_josa(m.group(0))
        if len(w) >= 2:
            out.add(w)
    return out


@dataclass
class Corpus:
    """최근 사람 요청의 낱말 문서 빈도 — 드문 낱말을 가른다."""
    df: dict[str, int] = field(default_factory=dict)
    n: int = 0

    @classmethod
    def build(cls, docs: Iterable[str | None]) -> Corpus:
        df: dict[str, int] = {}
        n = 0
        for d in docs:
            n += 1
            for w in words(d):
                df[w] = df.get(w, 0) + 1
        return cls(df, n)

    def rare(self, w: str, r: OverlapRules) -> bool:
        return self.df.get(w, 0) <= max(r.rare_min_df, int(self.n * r.rare_ratio))


def score(shared: Iterable[str]) -> int:
    """식별자 2점 · 영문 낱말 1점 · 한글 0점. 한글 낱말은 조사를 떼도 「글은」「알린다」처럼 틀 글에서 겹쳐
    헛알림을 냈다(11-06 지난 30일 다시 돌리기) — 보여 주기만 하고 세지 않는다."""
    return sum(2 if is_ident(w) else 1 if w.isascii() else 0 for w in shared)


def match(new: set[str], old: set[str], corpus: Corpus, r: OverlapRules) -> tuple[int, list[str]]:
    """(점수, 겹친 드문 낱말 — 식별자 · 영문 순). 보여 주는 것도 점수에 든 낱말만 — 한글은 세지 않으면서 보여 주니
    「쉬어서」「중이라」가 근거처럼 찍혔다(11-08 세션 214 알림)."""
    shared = sorted((w for w in new & old if w.isascii() and corpus.rare(w, r)), key=lambda w: (not is_ident(w), w))
    return score(shared), shared


def same_text(a: str | None, b: str | None, min_words: int = 12, ratio: float = 0.8) -> bool:
    """거의 같은 글 — 다른 프로젝트 세션에 이미 넣은 글을 또 넣었나(11-08 런슈즈 신발 지시가 FOREMAN 세션에 두 번 들어왔다).
    낱말 집합(한글 포함)의 자카드 ≥ ratio, 양쪽 다 낱말 min_words개 이상(짧은 "확인해줘" 류는 보지 않는다)."""
    wa, wb = words(a), words(b)
    if len(wa) < min_words or len(wb) < min_words:
        return False
    return len(wa & wb) / len(wa | wb) >= ratio


def cross_message(prefix: str, sid: int, title: str, other: int, other_title: str, other_proj: str, at: datetime) -> str:
    return (f"{prefix} 📋 다른 프로젝트 — 세션 {sid}「{title}」에 방금 넣은 글이 {other_proj} 세션 {other}「{other_title}」에 "
            f"{kst_hm(at)}에 들어간 글과 거의 같습니다. 잘못된 창에 붙여 넣었을 수 있습니다.\n"
            f"막지 않았습니다 — 실수면 패널 띠의 [이 세션 작업 중단]을 누르세요.")


def kst_hm(ts: datetime) -> str:
    return (ts + KST).strftime("%H:%M")


def message(prefix: str, sid: int, title: str, other: int, other_title: str, since: datetime, shared: list[str]) -> str:
    return (f"{prefix} 겹침 — 세션 {sid}「{title}」에 방금 넣은 요청이 세션 {other}「{other_title}」이 "
            f"{kst_hm(since)}부터 하는 일과 겹칠 수 있습니다.\n겹친 낱말: {', '.join(shared[:8])}\n"
            f"막지 않았습니다 — 일부러 나눠 시킨 것이면 그대로 두면 됩니다.")


# ── 감시 ─────────────────────────────────────────────────
class OverlapWatch:
    """조립기가 사람 입력(UserPromptSubmit)을 적재한 뒤 부른다. 실패해도 적재를 막지 않는다."""

    def __init__(self, engine: Any, notifier: Any, notify_rules: Any, path: str | Path, sessions_dir: Path,
                 on_change: Any = None) -> None:
        self.engine, self.notifier, self.notify_rules = engine, notifier, notify_rules
        self.rules = load_rules(path)
        self.sessions_dir = sessions_dir
        self.on_change = on_change
        self._corpus: Corpus | None = None
        self._corpus_at = 0.0
        self._sent: dict[tuple[int, int], float] = {}           # (세션, 다른 세션) → 알린 시각(monotonic)
        self.recent: dict[int, dict[str, Any]] = {}             # 세션 → 패널 띠(마지막 겹침)
        self._tasks: set[asyncio.Task[None]] = set()

    def on_prompt(self, session_id: int, cc_session_id: str, prompt: str, ts: datetime) -> None:
        if not self.rules.enabled:
            return
        t = asyncio.get_running_loop().create_task(self.check(session_id, cc_session_id, prompt, ts))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def for_session(self, sid: int) -> dict[str, Any] | None:
        o = self.recent.get(sid)
        if not o or datetime.now(UTC).replace(tzinfo=None) - o["at_dt"] > timedelta(minutes=self.rules.show_min):
            return None
        return {k: v for k, v in o.items() if k != "at_dt"}

    async def _get_corpus(self, c: Any) -> Corpus:
        if self._corpus is None or time.monotonic() - self._corpus_at > 1800:
            rows = (await c.execute(text(
                "SELECT prompt_text FROM turn WHERE origin IN ('human', 'handoff_in') AND started_at >= :cut "
                "ORDER BY id DESC LIMIT :n"),
                {"cut": datetime.now(UTC).replace(tzinfo=None) - timedelta(days=self.rules.corpus_days),
                 "n": self.rules.corpus_max})).all()
            self._corpus = await asyncio.to_thread(Corpus.build, [r[0] for r in rows])
            self._corpus_at = time.monotonic()
        return self._corpus

    @staticmethod
    async def _handoff_linked(c: Any, session_id: int, cc_session_id: str, prompt: str) -> set[int]:
        """인계로 이어진 세션 — 같은 일을 넘겨받은 것이지 겹친 것이 아니다(11-08 세션 214 ~ 211 헛알림).
        인계 글은 넣음 기록(summary.injected_at)보다 먼저 적재된다(0.3초) — 그래서 글의 r=도 본다.
        - 이 요청의 [FOREMAN 인계 r=X] → 넘겨준 세션
        - 나에게 넣은 인계(injected_cc_session = 나) → 넘겨준 세션
        - 내가 넘겨준 인계 → 받은 세션"""
        from bridge.handoff import IN_RE
        reqs = IN_RE.findall((prompt or "")[:500]) or [""]          # 빈 req는 맞는 행이 없다
        q = text("SELECT s.session_id, cs.id FROM summary s "
                 "LEFT JOIN character_session cs ON cs.cc_session_id = s.injected_cc_session "
                 "WHERE s.injected_cc_session = :cc OR s.session_id = :me OR s.req IN :reqs"
                 ).bindparams(bindparam("reqs", expanding=True))
        rows = (await c.execute(q, {"cc": cc_session_id, "me": session_id, "reqs": reqs})).all()
        return {x for a, b in rows for x in (a, b) if x is not None and x != session_id}

    async def _cross(self, c: Any, session_id: int, me: Any, prompt: str, ts: datetime, live: set[str]) -> dict[str, Any] | None:
        """다른 프로젝트의 살아 있는 세션이 최근(window_min) 받은 사람 글과 거의 같으면 알린다(11-08). 같은 프로젝트 겹침은
        드문 낱말 점수로 보지만, 이것은 "같은 글을 다른 창에 또 붙였다"를 잡는다 — 프로젝트를 건너 같은 일이 두 번 돈다."""
        if skip(prompt) or len(words(prompt)) < 12:
            return None
        rows = (await c.execute(text(
            "SELECT t.session_id, t.prompt_text, t.started_at, cs.cc_session_id, "
            "COALESCE(cs.custom_title, cs.title, LEFT(cs.cc_session_id, 8)), p.name "
            "FROM turn t JOIN character_session cs ON cs.id = t.session_id JOIN `character` ch ON ch.id = cs.character_id "
            "LEFT JOIN project p ON p.id = ch.project_id "
            "WHERE (ch.project_id IS NULL OR ch.project_id <> :p) AND cs.hidden_at IS NULL AND cs.detached_at IS NULL "
            "AND t.origin = 'human' AND t.started_at >= :cut ORDER BY t.id DESC LIMIT 200"),
            {"p": me[0], "cut": ts - timedelta(minutes=self.rules.window_min)})).all()
        hit = next((x for x in rows if x[3] in live and same_text(prompt, x[1])), None)
        if not hit:
            return None
        other, _p, at, _cc, title, proj = hit
        now_m = time.monotonic()
        if now_m - self._sent.get((session_id, other), -1e9) < self.rules.repeat_min * 60:
            return None
        self._sent[(session_id, other)] = now_m
        label = projLabel(proj)
        info = {"cross": True, "with": other, "with_title": title, "with_project": proj, "with_label": label,
                "since": at.isoformat(timespec="seconds") + "Z", "since_kst": kst_hm(at), "words": [], "score": 0,
                "at": ts.isoformat(timespec="seconds") + "Z", "at_dt": ts}
        self.recent[session_id] = info
        log.info("다른 프로젝트 같은 글 session=%d ~ %d(%s)", session_id, other, proj)
        rule = self.notify_rules.for_project(me[1]) if self.notify_rules else None
        if rule is not None and self.notifier is not None:
            self.notifier.send_direct(me[1], "overlap", session_id,
                                      cross_message(rule.prefix, session_id, me[2] or str(session_id), other, title or str(other), label, at))
        if self.on_change:
            self.on_change()
        return info

    async def check(self, session_id: int, cc_session_id: str, prompt: str, ts: datetime) -> dict[str, Any] | None:
        try:
            async with asyncio.timeout(20):
                return await self._check(session_id, cc_session_id, prompt, ts)
        except Exception as e:  # noqa: BLE001 — 알림 실패가 적재를 막으면 안 된다
            log.warning("겹침 확인 실패 session=%s: %s", session_id, type(e).__name__)
            return None

    async def _check(self, session_id: int, cc_session_id: str, prompt: str, ts: datetime) -> dict[str, Any] | None:
        from bridge.liveness import live_sessions
        r = self.rules
        new = set() if skip(prompt) else words(prompt)
        if not new:
            return None
        # 살아 있는 세션(멈춘 T는 뺀다 — 지금 일하는 세션이 아니다)
        live = {k for k, v in (await asyncio.to_thread(live_sessions, self.sessions_dir)).items()
                if v.state != "T" and k != cc_session_id}
        if not live:
            return None
        async with self.engine.connect() as c:
            me = (await c.execute(text(
                "SELECT ch.project_id, p.name, COALESCE(cs.custom_title, cs.title, LEFT(cs.cc_session_id, 8)), cs.hidden_at "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id "
                "LEFT JOIN project p ON p.id = ch.project_id WHERE cs.id = :i"), {"i": session_id})).first()
            if not me or me[0] is None or me[3] is not None:
                return None
            linked = await self._handoff_linked(c, session_id, cc_session_id, prompt)
            cross = await self._cross(c, session_id, me, prompt, ts, live)
            if cross:
                return cross
            rows = (await c.execute(text(
                "SELECT t.session_id, t.prompt_text, t.started_at, cs.cc_session_id, "
                "COALESCE(cs.custom_title, cs.title, LEFT(cs.cc_session_id, 8)) "
                "FROM turn t JOIN character_session cs ON cs.id = t.session_id JOIN `character` ch ON ch.id = cs.character_id "
                "WHERE ch.project_id = :p AND t.session_id <> :me AND cs.hidden_at IS NULL AND cs.detached_at IS NULL "
                "AND t.origin IN ('human', 'handoff_in') AND t.started_at >= :cut ORDER BY t.id DESC"),
                {"p": me[0], "me": session_id, "cut": ts - timedelta(minutes=r.window_min)})).all()
            rows = [x for x in rows if x[3] in live and x[0] not in linked and not skip(x[1])]
            if not rows:
                return None
            corpus = await self._get_corpus(c)
        best: dict[int, dict[str, Any]] = {}
        seen: dict[int, int] = {}
        for sid, ptxt, started, _cc, title in rows:
            if seen.get(sid, 0) >= r.per_session:
                continue
            seen[sid] = seen.get(sid, 0) + 1
            sc, shared = match(new, words(ptxt), corpus, r)
            if sc < r.min_score:
                continue
            b = best.setdefault(sid, {"score": 0, "shared": [], "since": started, "title": title})
            b["score"] = max(b["score"], sc)
            b["shared"] = sorted(set(b["shared"]) | set(shared), key=lambda w: (not is_ident(w), w))
            b["since"] = min(b["since"], started)       # 겹친 요청 중 가장 이른 것 — "언제부터"
        if not best:
            return None
        other, b = max(best.items(), key=lambda kv: kv[1]["score"])
        now_m = time.monotonic()
        if now_m - self._sent.get((session_id, other), -1e9) < r.repeat_min * 60:
            return None
        self._sent[(session_id, other)] = now_m
        info = {"with": other, "with_title": b["title"], "since": b["since"].isoformat(timespec="seconds") + "Z",
                "since_kst": kst_hm(b["since"]), "words": b["shared"][:8], "score": b["score"],
                "at": ts.isoformat(timespec="seconds") + "Z", "at_dt": ts}
        self.recent[session_id] = info
        log.info("겹침 session=%d ~ %d score=%d words=%s", session_id, other, b["score"], ",".join(b["shared"][:8]))
        rule = self.notify_rules.for_project(me[1]) if self.notify_rules else None
        if rule is not None and self.notifier is not None:   # 접두어 없는 프로젝트(미분류)는 보내지 않는다 — 알림 규칙과 같다
            self.notifier.send_direct(me[1], "overlap", session_id,
                                      message(rule.prefix, session_id, me[2] or str(session_id), other,
                                              b["title"] or str(other), b["since"], b["shared"]))
        if self.on_change:
            self.on_change()
        return info
