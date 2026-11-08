from datetime import UTC, datetime, timedelta
from pathlib import Path

from bridge.overlap import (Corpus, OverlapRules, OverlapWatch, cross_message, is_ident, load_rules, match, message, same_text, score,
                            skip, words)

REPO = Path(__file__).resolve().parent.parent

# 11-06 실제 사례(log/infra_20261106_jenkins-harbor-after-outage.md) — 198이 먼저 받고, 197에 같은 조사가 함께 들어갔다
A = "jenkins-0 Unknown · harbor-jobservice CrashLoopBackOff 원인 조사해줘. 정전 뒤 노드는 Ready"
B = "tmux 이름 충돌 고쳐줘. 그리고 jenkins-0 Unknown이랑 harbor-jobservice CrashLoopBackOff도 원인 봐줘"


def test_words_keep_identifiers_and_strip_josa():
    w = words("<pasted_content id=\"x\">bridge.db.migrate로 0020을 돌리고 jenkins-0를 본다. the 세션에서</pasted_content>")
    assert {"bridge.db.migrate", "jenkins-0", "세션"} <= w
    assert "the" not in w and "0020" not in w and "pasted_content" not in w   # 흔한 낱말 · 숫자만 · 꼬리표


def test_ident_and_score():
    assert is_ident("jenkins-0") and is_ident("harbor-jobservice") and is_ident("edcd41a") and is_ident("12_scribe.md")
    assert not is_ident("crashloopbackoff") and not is_ident("정전")
    assert score(["jenkins-0", "crashloopbackoff", "정전"]) == 3                  # 식별자 2 · 영문 1 · 한글 0


def test_real_case_matches_and_unrelated_does_not():
    c = Corpus.build([A, B, "README 고쳐줘", "Notion 게시 기능 만들자", *[f"다른 일 {i}" for i in range(20)]])
    r = OverlapRules()
    sc, shared = match(words(B), words(A), c, r)
    assert sc >= r.min_score and shared[:2] == ["harbor-jobservice", "jenkins-0"]
    assert match(words("Notion 게시 기능 만들자"), words(A), c, r)[0] == 0


def test_common_words_are_not_rare():
    docs = [f"jenkins-0 확인 {i}" for i in range(50)] + [A]
    c = Corpus.build(docs)
    r = OverlapRules(rare_ratio=0.01, rare_min_df=3)
    assert not c.rare("jenkins-0", r) and c.rare("harbor-jobservice", r)


def test_korean_only_overlap_scores_zero():
    c = Corpus.build(["글마다 주제를 한눈에", "글마다 주제가 한눈에 보이게"])
    assert match(words("글마다 주제를 한눈에"), words("글마다 주제가 한눈에 보이게"), c, OverlapRules())[0] == 0


def test_shown_words_are_only_scored_ones():
    # 11-08 세션 214 알림 — 「쉬어서」「중이라」「하한」이 세지 않으면서 겹친 낱말로 찍혔다
    a = "맥락 300k · 500k 알림, 쉬어서 식은 세션은 하한이 낮다. 일하는 중이라"
    b = "300k 500k 넘으면 쉬어서 끝내기, 하한 다시 보기, 지금 중이라"
    c = Corpus.build([a, b, *[f"다른 일 {i}" for i in range(20)]])
    sc, shared = match(words(b), words(a), c, OverlapRules())
    assert shared == ["300k", "500k"] and sc == 4


SHOE = """<pasted_content id="2878">
# 요약·설명 다시 쓰기 — 수정 지시
샘플 톤은 좋다. 넷만 고치고 전체 진행해라.
## 1. "~라는 평이 있습니다"를 줄여라
한 설명문에 한 번 이하로. 지금은 네 번씩 나온다.
## 2. 발볼·와이드·가격은 조심해서 써라
## 5. 리뷰 없는 67켤레 리뷰를 새로 받아라. 사이트맵에 있는 것만.
전체 310켤레 진행해라.
</pasted_content>"""


def test_same_text_catches_repasted_instruction():
    # 11-08 — 런슈즈 217에 넣은 지시가 FOREMAN 214에도 들어왔다(꼬리표 id만 다르다)
    assert same_text(SHOE.replace("2878", "1dbe"), SHOE)
    assert same_text(SHOE + "\n그리고 오늘 안에", SHOE)                       # 한 줄 덧붙여도
    assert not same_text("리셋 확인해줘", "리셋 확인해줘")                         # 짧은 글은 보지 않는다
    assert not same_text(A + " " + B, SHOE)
    m = cross_message("[포먼]", 214, "사용량", 217, "클러스터 이주", "런슈즈", datetime(2026, 11, 8, 5, 14))
    assert "런슈즈 세션 217「클러스터 이주」에 14:14에 들어간 글과 거의 같습니다" in m and "[이 세션 작업 중단]" in m


def test_cross_project_alert_with_fake_db(tmp_path):
    import asyncio

    class Res:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows

    class C:
        async def execute(self, *_a, **_k):
            return Res([(217, SHOE, datetime(2026, 11, 8, 5, 14), "cc-217", "클러스터 이주", "runshoes")])

    class N:
        def __init__(self): self.sent = []
        def send_direct(self, *a): self.sent.append(a)

    class R:
        prefix = "[포먼]"

    class Rules:
        def for_project(self, _p): return R()

    n = N()
    w = OverlapWatch(None, n, Rules(), tmp_path / "없음.toml", tmp_path)
    me = (1, "foreman", "사용량", None)
    now = datetime(2026, 11, 8, 5, 18)
    info = asyncio.run(w._cross(C(), 214, me, SHOE.replace("2878", "1dbe"), now, {"cc-217"}))
    assert info["cross"] and info["with"] == 217 and info["with_label"] == "런슈즈"
    assert len(n.sent) == 1 and n.sent[0][1] == "overlap" and "📋 다른 프로젝트" in n.sent[0][3]
    assert asyncio.run(w._cross(C(), 214, me, SHOE, now, set())) is None                  # 그 세션이 끝났으면 안 본다
    assert asyncio.run(w._cross(C(), 215, me, "짧은 글 확인", now, {"cc-217"})) is None


def test_scribe_jobs_are_skipped():
    assert skip('\n\n<pasted_content id="d36c">\n[FOREMAN 서기 일감 — 회고] foreman')
    assert not skip("[FOREMAN 인계 r=690cec] 직전 세션의 인계다") and not skip(B)


def test_message_wording():
    m = message("[포먼]", 197, "브리지 복구", 198, "jenkins 조사", datetime(2026, 11, 6, 3, 37), ["jenkins-0", "harbor-jobservice"])
    assert m.startswith("[포먼] 겹침 — 세션 197「브리지 복구」") and "세션 198「jenkins 조사」이 12:37부터" in m
    assert "막지 않았습니다" in m and "jenkins-0, harbor-jobservice" in m


def test_repo_config_and_missing_file(tmp_path):
    r = load_rules(REPO / "config" / "notify.toml")
    assert r.enabled and r.min_score == 3 and r.window_min == 180
    assert load_rules(tmp_path / "없음.toml") == OverlapRules()


def test_panel_band_expires(tmp_path):
    w = OverlapWatch(None, None, None, tmp_path / "없음.toml", tmp_path)
    now = datetime.now(UTC).replace(tzinfo=None)
    w.recent[1] = {"with": 2, "at": "x", "at_dt": now}
    w.recent[3] = {"with": 4, "at": "y", "at_dt": now - timedelta(minutes=w.rules.show_min + 1)}
    assert w.for_session(1) == {"with": 2, "at": "x"} and w.for_session(3) is None and w.for_session(9) is None
