"""서기실(12a, 11-06) — 할 일 세기(LLM 없음) · 시킬 일 프롬프트."""

import subprocess

import pytest

from bridge import scribe_room as sr


def _repo(tmp_path, result_convention=True):
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    (r / "log").mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    (r / "README.md").write_text("# x\n", encoding="utf-8")
    (r / "docs" / "11_handoff.md").write_text("# 11\n", encoding="utf-8")
    (r / "docs" / "12_scribe.md").write_text("# 12\n", encoding="utf-8")
    (r / "docs" / "style_guide.md").write_text("# 기준\n", encoding="utf-8")
    if result_convention:
        (r / "log" / "stage11_handoff_result.md").write_text("# 결과\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "처음")
    for i in range(3):
        (r / f"f{i}.txt").write_text(str(i))
        g("add", "."), g("commit", "-qm", f"c{i}")
    return r


def test_stages_without_result_only_with_convention(tmp_path):
    r = _repo(tmp_path)
    assert sr.stages_without_result(str(r)) == ["docs/12_scribe.md"]       # 11은 stage11_*가 있다, style_guide는 번호 없음
    r2 = _repo(tmp_path / "b", result_convention=False)
    assert sr.stages_without_result(str(r2)) == []                          # 결과 문서 관례가 없는 저장소는 세지 않는다(펫퍼민트)


@pytest.mark.parametrize("task", ["doccheck", "trim", "later"])
def test_task_prompts(task):
    p = sr.task_prompt(task, "foreman", "/repo", {"stages": "docs/12_x.md", "materials": "/m/later.md"})
    assert p.startswith(f"[FOREMAN 서기 일감 — {sr.TASKS[task]['title']}] foreman")
    assert "push하지 않는다" in p and "CLAUDE.md" in p
    if task == "doccheck":
        assert "고치지 마라" in p and "docs/12_x.md" in p
    if task == "later":
        assert "/m/later.md" in p and "고칠 곳: 재료가 고른 편 파일" in p
    with pytest.raises(ValueError):
        sr.task_prompt("publish", "foreman", "/repo")


def test_blocked_same_task_same_file_no_cap():
    """동시에 시키기(11-06) — 같은 일 · 같은 파일만 막고, 파일이 다른 일은 몇 개든 같이 둔다(11-15 상한 없앰)."""
    trim = {"session_id": 194, "task": "trim", "title": "서기 — CLAUDE.md 정리"}
    later = {"session_id": 193, "task": "later", "title": "서기 — 나중에 할 일 정리"}
    # 11-17 알려진 한계 쓰기는 docs/TODO.md도 맡는다(TODO에서 [한계로] 보낸 항목을 지운다). docs/ 통째로 맡는 trim과 겹쳐 막힌다
    assert "docs/TODO.md" in sr.blocked("later", [trim])
    assert sr.blocked("later", [{"session_id": 5, "task": "portfolio", "topic": "01_a", "title": "서기"}], None, ["notion/09.md"]) is None
    assert "portfolio/01_a" in sr.blocked("later", [{"session_id": 5, "task": "portfolio", "topic": "01_a", "title": "서기"}], None,
                                          ["portfolio/01_a.md"])            # 고른 편이 열린 포트폴리오 편이면 막는다
    assert "이미 열려" in sr.blocked("trim", [trim])
    assert "docs/TODO.md" in sr.blocked("docfix", [later])                    # 문서 고치기(docs/)와 알려진 한계 쓰기(docs/TODO.md)는 겹친다
    assert sr.blocked("doccheck", [trim, later]) is None                      # 둘 열려 있어도 파일이 다르면 셋째를 막지 않는다
    many = [trim, later] + [{"session_id": 300 + i, "task": "portfolio", "topic": f"0{i}_x", "title": "서기"} for i in range(4)]
    assert sr.blocked("doccheck", many) is None and sr.blocked("portfolio", many, "09_y") is None
    assert sr.blocked("doccheck", []) is None
    assert not hasattr(sr, "MAX_OPEN")
    assert "retro" not in sr.TASKS and "retro" not in sr.TOUCHES             # 회고 쓰기는 11-15에 뺐다
    assert "readme" not in sr.TASKS and "readme" not in sr.TOUCHES           # README 갱신도 11-15에 뺐다(로드맵 표를 없앰)
    assert not hasattr(sr, "README_STALE")


def test_blocked_sees_plan_scribe_by_files():
    """계획 길로 띄운 서기(일 종류 plan)는 맡을 파일로 막는다 — 같은 plan끼리는 같은 일로 보지 않는다(11-15 두 길 합치기)."""
    plan = {"session_id": 437, "task": "plan", "title": "CLAUDE.md 정리 서기", "files": ["CLAUDE.md", "docs/operations.md"]}
    assert "CLAUDE.md" in sr.blocked("trim", [plan]) and "CLAUDE.md 정리 서기" in sr.blocked("trim", [plan])
    assert "docs/operations.md" in sr.blocked("docfix", [plan], None)          # docs/ 폴더 ↔ 그 안의 파일
    assert sr.blocked("later", [plan]) is None                                 # README는 안 맡았다
    assert sr.blocked("plan", [plan]) is None                                  # plan끼리는 같은 일이 아니다
    dc = {"session_id": 9, "task": "doccheck", "title": "서기", "files": sr.touches("doccheck")}
    assert "이미 열려" in sr.blocked("doccheck", [dc])
    assert sr.touches("portfolio", "00_a") == ["portfolio/00_a*"]
    assert sr.blocked("portfolio", [{"session_id": 1, "task": "plan", "title": "t", "files": ["portfolio/00_a.md"]}], "00_a")


def test_portfolio_pieces_from_folder_and_blocked_per_piece(tmp_path):
    """포트폴리오(11-15 화면 축) — 정해진 주제 목록 없이 portfolio/ 파일이 편이다. 머리 주석의 읽은 커밋 뒤 다루는 코드를 바꾼
    feat · fix 커밋만 센다(docs 커밋 · 다른 파일 커밋은 세지 않는다). 머리 주석이 없으면 0이 아니라 셀 수 없음."""
    r = tmp_path / "repo"
    (r / "portfolio" / "img").mkdir(parents=True)
    (r / "bridge").mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    (r / "bridge" / "scribe.js").write_text("a\n", encoding="utf-8")
    (r / "bridge" / "other.py").write_text("a\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "feat: 처음")
    base = g("rev-parse", "--short", "HEAD")
    from bridge.manuscript import head_text
    (r / "portfolio" / "01_room.md").write_text(head_text(["bridge/scribe.js"], base) + "\n# 서기실\n본문\n", encoding="utf-8")
    (r / "portfolio" / "00_overview.md").write_text("# 한눈에\n머리 주석 없음\n", encoding="utf-8")
    (r / "portfolio" / "img" / "x.md").write_text("# 그림 설명은 편이 아니다\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "docs: 포트폴리오")
    for i, msg in enumerate(["fix: 서기실 고침", "docs: 서기실 문서 맞춤", "feat(scope): 서기실 더함"]):
        (r / "bridge" / "scribe.js").write_text(f"{i}\n", encoding="utf-8")
        g("add", "."), g("commit", "-qm", msg)
    (r / "bridge" / "other.py").write_text("b\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "feat: 다른 파일")
    tps = sr.topics(str(r))
    assert [t["slug"] for t in tps] == ["00_overview", "01_room"]                 # 번호 차례, img/ 아래는 편이 아니다
    assert tps[1]["title"] == "서기실" and tps[1]["commits"] == 2                  # fix 하나 + feat 하나(docs · 다른 파일 뺌)
    assert tps[0]["commits"] is None and "머리 주석" in tps[0]["why"]
    assert sr.topics(str(tmp_path / "없음")) == [] and sr.has_portfolio(str(r))
    a = {"session_id": 1, "task": "portfolio", "topic": "00_overview", "title": "서기"}
    assert "이미 열려" in sr.blocked("portfolio", [a], "00_overview")
    assert sr.blocked("portfolio", [a], "01_room") is None                        # 다른 편 — 다른 파일
    assert "portfolio/" in sr.blocked("portfolio", [a])                           # 편 없이(폴더 통째로)는 열린 편과 겹친다
    assert sr.touches("portfolio") == ["portfolio/"]
    assert sr.blocked("later", [a]) is None
    one = sr.task_prompt("portfolio", "foreman", "/repo", {"slug": "01_room", "title": "서기실", "covers": "`bridge/scribe.js`",
                                                           "commits": "2개", "siblings": ""})
    whole = sr.task_prompt("portfolio", "foreman", "/repo", {"siblings": "「한눈에」"})
    for p in (one, whole):
        assert "tools/screen.py" in p and "경어체" in p and "화면 축" in p and "다루는 곳:" in p and "읽은 커밋:" in p
        assert "본 판" not in p and "config/portfolio.toml" not in p and "portfolio: " not in p
    assert "portfolio/01_room.md" in one and "정해진 주제 목록은 없다" in whole
    assert "../notion/" in whole and "무엇을 해 주는지" in whole and "덧붙인 요청" not in whole
    assert "16편" in sr.task_prompt("portfolio", "foreman", "/repo", {"note": "포트폴리오 16편, 합치지 않는다"})
    for p in (one, whole):                                                        # 11-17 축 기준: 화면이 있으면 화면 축, 없으면 결정 중심
        assert "보여줄 화면이 있으면 화면 축, 없으면 결정 중심" in p                   # 축 줄은 원고 쓰는 기준(docs/manuscript_rules.md 5절)에서 온다
        assert "화면 축: 한 편이 화면 하나다" in p and "결정 중심: 한 편이 결정 하나다" in p
        assert "상황" in p and "고른 것" in p and "까닭" in p and "치른 값" in p
        assert "log/" in p and "본 근거" in p                                      # 어느 축을 골랐는지 기록하게 한다
        assert p.index("축은 하나로 정한다") < p.index("화면 축: 한 편이")              # 기준이 맨 앞(두 갈래보다 먼저)


def test_writing_prompts_keep_user_rules():
    """11-15 사용자 지시 셋이 두 지시문에 모두 들어 있다(빠지면 실패). 문단으로 쓴다, 비개발자도 읽는다(어려운 말은 그 자리에서 풀기),
    포트폴리오는 편마다 화면 사진과 움직이는 것은 영상."""
    port = sr.task_prompt("portfolio", "foreman", "/repo", {"siblings": "「한눈에」"})
    tech = sr.task_prompt("techdoc", "foreman", "/repo", {})
    for p in (port, tech):                                                        # 11-17부터 원고 쓰는 기준 한 벌(docs/manuscript_rules.md)에서 온다
        assert "대부분 목록 없이 문단으로 쓴다" in p and "용어 풀이" in p
        assert "비개발자도 읽는다" in p and "처음 나오는 자리에서 한 줄로 푼다" in p
    assert "다루는 범위가 좁다는 뜻이지 문장을 짧게 끊으라는 뜻이 아니다" in port
    for want in ("편마다 그 화면 사진을 한 장 이상", "영상", "docs/13_demo_capture.md", "portfolio/img/", "--record", "?demo=", "bridge/static/demo/",
                 "FOREMAN 찍는 법", "비밀값"):   # 11-19 사진 크기 숫자는 지시문에 두지 않고 docs/style_guide.md 「FOREMAN 찍는 법」을 가리킨다
        assert want in port, want


def test_techdoc_task_prompt_and_two_days():
    """기술문서 쓰기(11-15) — 목차는 서기가, 편마다 서브에이전트. 쓰는 법 · 나무 규칙 · 머리 주석이 일감에 든다.
    마지막으로 합친 뒤 이틀이 지났고 다루는 코드가 바뀐 편이 있을 때만 할 일에 올린다."""
    from datetime import datetime, timedelta
    p = sr.task_prompt("techdoc", "foreman", "/repo", {"changed": "`notion/02_x.md`(3개)", "tree": "`notion/02_x.md`", "note": "브리지 편도"})
    for want in ("notion/", "서브에이전트", "평서체", "날짜", "[code:경로]", "NN_이름/", "다루는 곳:", "읽은 커밋:", "docs를 그대로 옮기지 않고",
                 "notion/02_x.md`(3개)", "브리지 편도", "Notion에 올리기",
                 "비개발자도 읽는다. 쉬운 말로 쓰되 기술 설명을 빼지 않는다", "어려운 말은 처음 나오는 자리에서 한 줄로 푼다"):
        assert want in p, want
    assert "본 판" not in p
    assert sr.touches("techdoc") == ["notion/"] and "techdoc" in sr.TASKS
    now = datetime(2026, 11, 15, 12)
    changed = [{"commits": 2}, {"commits": 0}]
    assert sr.techdoc_state(changed, now - timedelta(days=3), now)["due"] is True
    assert sr.techdoc_state(changed, now - timedelta(days=1), now)["due"] is False            # 이틀이 안 지남
    assert sr.techdoc_state([{"commits": 0}], now - timedelta(days=9), now)["due"] is False   # 코드가 그대로면 이틀이 지나도 안 올린다
    unk = sr.techdoc_state([{"commits": None}], now - timedelta(days=3), now)
    assert unk["due"] is True and "머리 주석을 읽지 못한 편 1" in unk["why"]                 # 셀 수 없는 편은 조용히 「그대로」가 되지 않는다
    assert sr.techdoc_state([], None, now)["due"] is False                                     # 첫 목차는 사람이 정한다
    st = sr.techdoc_state(changed, now - timedelta(days=3), now)
    assert st["why"].startswith("글 2편 가운데 코드가 바뀐 편 1")


def test_techdoc_and_portfolio_start_refusals(tmp_path):
    """기술문서 쓰기는 원고 폴더가 notion/인 프로젝트만, 포트폴리오는 portfolio/ 폴더가 있는 저장소만(세션을 띄우기 전에 거절)."""
    import asyncio
    from bridge.inject import Refused
    r = _repo(tmp_path)

    class _Pub:
        def __init__(self, src):
            self.src = src
    eng = _FakeEngine({"foreman": str(r)})
    for pubs in (None, {"foreman": _Pub("docs/")}):
        with pytest.raises(Refused, match="notion/"):
            asyncio.run(sr.start(None, eng, "foreman", "techdoc", publishers=pubs))
    with pytest.raises(Refused, match="portfolio/ 폴더가 없습니다"):
        asyncio.run(sr.start(None, eng, "foreman", "portfolio"))
    (r / "portfolio").mkdir()
    with pytest.raises(Refused, match="편을 찾지 못했습니다"):
        asyncio.run(sr.start(None, eng, "foreman", "portfolio", "09_없음"))


def test_later_prompt_writes_to_picked_piece_and_drops_todo(tmp_path):
    """「알려진 한계 쓰기」(11-17 문서 정리 E). README가 아니라 [한계로]에서 고른 편의 「알려진 한계」 절에 까닭과 함께 쓴다.
    TODO 항목에서 온 줄은 같은 커밋에서 docs/TODO.md 항목을 지우고 메시지에 (todo:번호)를 적는다. 11-17 전의 README 생성물 거부는 없앴다."""
    r = _repo(tmp_path)
    p = sr.task_prompt("later", "foreman", str(r), {"materials": "/m/later.md"})
    assert "고른 편의 「알려진 한계」 절" in p and "안 하는 까닭" in p
    assert "`docs/TODO.md`의 그 항목" in p and "`(todo:번호)`" in p
    assert "README 「6. 로드맵」" not in p                       # 옛 README 절 만들기 지시는 없다
    assert sr.touches("later") == ["docs/TODO.md"]                       # 고른 편 파일은 띄울 때 더한다(blocked의 extra). README는 11-19에 뺐다
    # 11-19: 한계가 무엇인지는 기준 문서 줄이 정한다. 지시문 본문에 옛 두 갈래 말(안 하기로 한 것만, 뺄 줄)이 남지 않는다
    assert "한계, 조건, 설계, 할 일 넷으로 가른다" in p and "한계 편은 결정으로 묶는다" in p
    assert "안 하기로 한 것만 쓰는 절" not in p and "뺄 줄" not in p and "README" not in p.split("원고 쓰는 기준")[0]


class _FakeEngine:
    """start가 저장소 경로만 읽는다."""

    def __init__(self, repos):
        self.repos = repos

    def connect(self):
        eng = self

        class _C:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, q, params=None):
                class _R:
                    def first(self_inner):
                        p = (params or {}).get("p")
                        return (eng.repos[p],) if p in eng.repos else None
                return _R()
        return _C()


class _FakeSpawn:
    """handoff 대신 spawn_new에 넘긴 이름, 지시문, 일 종류를 적어 두고 세션 번호를 준다(실제 세션은 띄우지 않는다)."""

    def __init__(self):
        self.calls, self.acts = [], []

    async def spawn_new(self, repo, char, name, **kw):
        self.calls.append({"repo": repo, "name": name, **kw})
        return {"session_id": 900 + len(self.calls), "tmux": "cc-foreman-9"}

    async def _act(self, sid, action, pid, ok, detail):
        self.acts.append((sid, action, detail))


class _Pub:
    src = "notion/"


def _piece_repo(tmp_path):
    """notion/ 아래 하위 폴더 편까지 있는 원고와 portfolio/ 한 편. 다루는 코드를 읽은 커밋 뒤 feat로 바꿔 둔다."""
    from bridge.manuscript import head_text
    r = tmp_path / "pr"
    for d in ("notion/10_scribe", "portfolio", "bridge"):
        (r / d).mkdir(parents=True)
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    g("init", "-q", "-b", "main"), g("config", "user.email", "t@t"), g("config", "user.name", "t")
    for f in ("a.py", "b.py"):
        (r / "bridge" / f).write_text("0\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "feat: 처음")
    base = g("rev-parse", "--short", "HEAD")
    docs = {"notion/00_intro.md": ("bridge/b.py", "들어가며"), "notion/10_scribe.md": ("bridge/a.py", "서기"),
            "notion/10_scribe/03_evidence.md": ("bridge/a.py", "근거 표시"), "portfolio/01_room.md": ("bridge/a.py", "서기실")}
    for path, (cov, title) in docs.items():
        (r / path).write_text(head_text([cov], base) + f"\n# {title}\n본문\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "docs: 원고")
    (r / "bridge" / "a.py").write_text("1\n", encoding="utf-8")
    g("add", "."), g("commit", "-qm", "fix: 서기 고침")
    return r


def _start(monkeypatch, r, task, topic=None, opened=None, note=None):
    """가짜 세션 띄우기. 열린 일은 opened로 주고, dispatch 기록(맡을 파일)은 record_spawn을 가로채 본다."""
    import asyncio
    from bridge import foreman
    rec = []

    async def _open(engine, project):
        return list(opened or [])

    async def _spawn_rec(engine, origin, project, sess, res, *a):
        rec.append(sess)
    monkeypatch.setattr(sr, "open_tasks", _open)
    monkeypatch.setattr(foreman, "record_spawn", _spawn_rec)
    m = _FakeSpawn()
    out = asyncio.run(sr.start(m, _FakeEngine({"foreman": str(r)}), "foreman", task, topic, note, publishers={"foreman": _Pub()}))
    return out, m.calls[0], rec[0]


def test_techdoc_one_piece_start_like_portfolio(tmp_path, monkeypatch):
    """11-19 foreman-125. 기술문서 쓰기도 편 하나만 고쳐 쓴다. 맡을 파일, 지시문, 일 제목이 그 편 하나이고 다른 편은 안 건드린다.
    포트폴리오와 같은 표(PIECE_TASKS)를 지난다."""
    r = _piece_repo(tmp_path)
    tps = sr.topics(str(r), "techdoc")
    assert [t["slug"] for t in tps] == ["00_intro", "10_scribe", "10_scribe/03_evidence"]      # 하위 폴더 편도 편이다
    assert [t["commits"] for t in tps] == [0, 1, 1]
    out, call, rec = _start(monkeypatch, r, "techdoc", "10_scribe/03_evidence")
    assert out["topic"] == "10_scribe/03_evidence"
    assert call["name"] == "서기 — 기술문서 쓰기: 근거 표시"                                  # 일 제목에 편 이름
    assert call["scribe_task"] == "techdoc 10_scribe/03_evidence"                                # open_tasks가 편을 되읽는다
    assert rec["files"] == ["notion/10_scribe/03_evidence.md"]                                   # 그 편 파일만(같은 이름 부모 편은 아니다)
    p = call["first_prompt"]
    assert "한 편 「근거 표시」(`notion/10_scribe/03_evidence.md`)" in p and "이 편 하나만 고친다" in p
    assert "고칠 곳은 `notion/10_scribe/03_evidence.md`뿐이다" in p and "고칠 곳은 `notion/`뿐이다" not in p
    assert "다른 편은 고치지 않는다" in p and "「서기」(`notion/10_scribe.md`)" in p and "「들어가며」(`notion/00_intro.md`)" in p
    assert "이 편 전체를 지금 코드와 맞대 읽었을 때만" in p and "올리지 않고 그대로 두고" in p      # 11-19 사용자 결정
    assert "`bridge/a.py`" in p and "1개" in p
    for keep in ("원고 쓰는 기준", "[code:경로]", "다루는 곳:", "읽은 커밋:", "Notion에 올리기", "비밀값"):   # 통째 쓰기의 나머지 약속은 그대로
        assert keep in p, keep
    assert "나무 규칙" not in p and "지금 원고(서기실이 센 것)" not in p and "통으로 쓴다" not in p
    # 편 없이 시키면 지금처럼 통째 쓰기(폴더 통째로 맡는다)
    _, whole, rec2 = _start(monkeypatch, r, "techdoc")
    assert rec2["files"] == ["notion/"] and whole["scribe_task"] == "techdoc" and "통으로 쓴다" in whole["first_prompt"]


def test_techdoc_piece_blocked_same_piece_only_and_refusals(tmp_path, monkeypatch):
    """같은 편 두 번은 막고 다른 편은 막지 않는다. 통째 쓰기가 열려 있으면 모든 편과 겹친다. 없는 편, 원고 폴더 밖 경로는 거절."""
    from bridge.inject import Refused
    r = _piece_repo(tmp_path)
    one = {"session_id": 5, "task": "techdoc", "topic": "10_scribe/03_evidence", "title": "서기",
           "files": sr.touches("techdoc", "10_scribe/03_evidence")}
    with pytest.raises(Refused, match="이미 열려"):
        _start(monkeypatch, r, "techdoc", "10_scribe/03_evidence", [one])
    _, call, _ = _start(monkeypatch, r, "techdoc", "10_scribe", [one])                           # 부모 편은 다른 파일
    assert call["scribe_task"] == "techdoc 10_scribe"
    assert "notion/" in sr.blocked("techdoc", [one])                                             # 통째 쓰기는 열린 편과 겹친다
    assert "notion/" in sr.blocked("techdoc", [{"session_id": 6, "task": "techdoc", "topic": None, "title": "서기"}], "00_intro")
    assert sr.blocked("portfolio", [one], "01_room") is None                                     # 다른 일, 다른 폴더
    assert "기술문서 쓰기: 10_scribe/03_evidence" in sr.blocked("techdoc", [one], "10_scribe/03_evidence")
    for bad in ("09_없음", "99_none", "../docs/00_design", "/etc/passwd", "10_scribe/../00_intro", "docs/00_design", "00_intro.md"):
        with pytest.raises(Refused, match="기술문서 편을 찾지 못했습니다"):
            _start(monkeypatch, r, "techdoc", bad)
    assert not sr.topic_ok("techdoc", "../x") and not sr.topic_ok("techdoc", "a//b") and not sr.topic_ok("techdoc", "x" * 121)
    assert sr.topic_ok("techdoc", "10_scribe/03_evidence") and not sr.topic_ok("portfolio", "10_scribe/03_evidence")
    from bridge.api.scribe import StartIn
    assert StartIn(project="foreman", task="techdoc", topic="09_dispatcher/02_note_wake_long_name_over_forty").topic


def test_portfolio_start_unchanged_through_piece_table(tmp_path, monkeypatch):
    """포트폴리오는 표로 모은 뒤에도 그대로다. 편 하나면 portfolio/<slug>*, 일 제목, 지시문이 전과 같다."""
    r = _piece_repo(tmp_path)
    out, call, rec = _start(monkeypatch, r, "portfolio", "01_room")
    assert rec["files"] == ["portfolio/01_room*"] and call["name"] == "서기 — 포트폴리오 쓰기: 서기실"
    assert call["scribe_task"] == "portfolio 01_room" and "`portfolio/01_room.md`" in call["first_prompt"]
    _, whole, rec2 = _start(monkeypatch, r, "portfolio")
    assert rec2["files"] == ["portfolio/"] and whole["scribe_task"] == "portfolio"


def test_later_start_records_without_readme_rows(tmp_path, monkeypatch):
    """「알려진 한계 쓰기」를 띄우면 어디까지 봤나(LATER_ACT)를 남기고 쓸 줄을 가져간다. 11-19 README 뺄 줄을 없앤 뒤
    남은 len(rows)가 세션을 띄운 다음 NameError를 냈다(조용히 기록이 빠짐)."""
    import asyncio
    from bridge import scribe as sc
    r = _piece_repo(tmp_path)
    taken = []

    async def _inbox(engine, project):
        return [{"id": 3, "piece": "notion/00_intro.md", "reason": "까닭", "body": "글", "created_at": None, "todo": None}]

    async def _since(engine, project):
        return None

    async def _take(engine, ids, sid):
        taken.append((ids, sid))
    monkeypatch.setattr(sr, "inbox_new", _inbox)
    monkeypatch.setattr(sr, "later_since", _since)
    monkeypatch.setattr(sr, "_inbox_take", _take)
    monkeypatch.setattr(sc, "OUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(sc, "kst", lambda v: "11-19")
    import bridge.foreman as fm

    async def _rec(*a):
        return None

    async def _open(engine, project):
        return []
    monkeypatch.setattr(fm, "record_spawn", _rec)
    monkeypatch.setattr(sr, "open_tasks", _open)
    m = _FakeSpawn()
    asyncio.run(sr.start(m, _FakeEngine({"foreman": str(r)}), "foreman", "later"))
    assert m.acts and m.acts[0][1] == sr.LATER_ACT and m.acts[0][2].endswith("쓸 줄 1개") and taken == [([3], 901)]


def test_later_task_is_known_limits():
    """11-15 포스트잇 — 미룬 말 그물은 bridge/postit.py(tests/test_postit.py). 서기 later는 「알려진 한계」 쓰기다(11-17부터 고른 편에)."""
    assert not hasattr(sr, "LATER")
    assert sr.TASKS["later"]["title"] == "알려진 한계 쓰기"
    p = sr.task_prompt("later", "foreman", "/repo", {"materials": "/m/later.md"})
    assert "알려진 한계" in p and "[한계로]" in p and "나중에 할 일" not in p


def test_last_change_commits_since_and_unreadable(tmp_path):
    """포트폴리오 마지막 쓴 시각 + 그 뒤 커밋 수(D2). 바꾼 적 없으면 0이고, git을 못 읽으면 0이 아니라 None(「읽지 못했습니다」)."""
    r = _repo(tmp_path)
    when, n = sr.last_change(str(r), "README.md")
    assert when and n == 3
    assert sr.last_change(str(r), "portfolio/없음.md") == (None, 0)
    assert sr.last_change(str(tmp_path / "git아님"), "README.md") == (None, None)


def test_doccheck_report_latest_and_docfix_prompt(tmp_path):
    r = _repo(tmp_path)
    assert sr.doccheck_report(str(r)) is None
    (r / "log" / "doccheck_20261110.md").write_text("a", encoding="utf-8")
    (r / "log" / "doccheck_20261111.md").write_text("b", encoding="utf-8")
    assert sr.doccheck_report(str(r)) == "doccheck_20261111.md"
    p = sr.task_prompt("docfix", "foreman", "/repo", {"report": "log/doccheck_20261111.md"})
    assert "log/doccheck_20261111.md" in p and "고치는 일이다" in p and "push하지 않는다" in p
    q = sr.task_prompt("docfix", "foreman", "/repo", {"note": "docs에 안 들어간 것 둘"})
    assert "docs에 안 들어간 것 둘" in q and "그대로 믿지 말고" in q


def test_docfix_blocked_with_readme_and_start_refuses_without_source():
    import asyncio
    from bridge.inject import Refused
    later = {"session_id": 5, "task": "later", "title": "서기"}
    assert "docs/TODO.md" in sr.blocked("docfix", [later])                     # docs/를 고치는 일과 같이 못 연다(알려진 한계 쓰기는 docs/TODO.md를 고친다)
    for topic, note in ((None, None), ("../etc/passwd", None), ("doccheck_x/../y.md", "a")):
        with pytest.raises(Refused):
            asyncio.run(sr.start(None, None, "foreman", "docfix", topic, note))
