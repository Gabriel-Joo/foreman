"""8단계 CI/CD 인과 체인 — 웹훅 판정(순수 함수), 그리고 foreman_test DB + 임시 git 저장소로
커밋 → 세션 귀속 → Jenkins(여러 커밋이 한 빌드) → Harbor(태그 12자리) → ArgoCD → 실패 위치 · 알림 · 인프라 캐릭터.
"""

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pymysql
import pytest

from bridge.api.webhooks import _allowed
from bridge.config import Settings
from bridge.db.engine import make_engine
from bridge.db.migrate import main as migrate_main
from bridge.mask import Masker
from bridge.pipeline import (PipelineManager, argocd_status, build_cause, harbor_items, image_tag, jenkins_status,
                             load_pipeline, commit_match, other_repo, watch_state, webhook_broken)

REPO = Path(__file__).resolve().parent.parent


# ── 판정 ──────────────────────────────────────────────────
def test_jenkins_status():
    assert jenkins_status({"phase": "started"}) == ("running", None)
    assert jenkins_status({"phase": "completed", "result": "SUCCESS"}) == ("success", None)
    assert jenkins_status({"phase": "completed", "result": "FAILURE", "stage": "빌드·push"}) == ("failed", "빌드·push")
    assert jenkins_status({"phase": "completed", "result": "ABORTED"})[0] == "failed"


def test_build_cause_and_webhook_break():
    assert build_cause({"cause": "webhook"}) == "webhook"
    assert build_cause({"cause": "x"}) is None and build_cause({}) is None
    # 새것부터. 웹훅으로 시작한 적이 있고, 최근 2번이 폴링 → 끊김
    assert webhook_broken(["poll", "poll", "webhook"])
    assert webhook_broken(["poll", "manual", "poll", "webhook"])          # 손으로 누른 것은 건너뛴다
    assert not webhook_broken(["poll", "webhook", "poll"])                 # 연달아 2번이 아니다
    assert not webhook_broken(["poll", "poll", "poll"])                    # 웹훅으로 시작한 적이 없다(아직 안 건 job)
    assert not webhook_broken(["webhook", "poll", "poll", "webhook"])      # 다시 웹훅 — 복구
    assert not webhook_broken([None, None, None])                          # 옛 빌드(원인 모름)


def test_watch_state():
    assert watch_state(30, 180, 1020) == "ok"
    assert watch_state(180, 180, 1020) == "late"
    assert watch_state(1019, 180, 1020) == "late"
    assert watch_state(1020, 180, 1020) == "missing"


def test_harbor_items():
    body = {"type": "PUSH_ARTIFACT", "occur_at": 1793620000, "event_data": {
        "resources": [{"digest": "sha256:ab", "tag": "0f349e101774"}],
        "repository": {"namespace": "runshoes", "repo_full_name": "runshoes/runshoes", "name": "runshoes"}}}
    assert harbor_items(body) == [{"project": "runshoes", "repo": "runshoes/runshoes", "digest": "sha256:ab",
                                   "tag": "0f349e101774", "status": "success", "step": None, "type": "PUSH_ARTIFACT"}]
    assert harbor_items({**body, "type": "PULL_ARTIFACT"}) == []
    assert harbor_items({**body, "type": "SCANNING_FAILED"})[0]["status"] == "failed"


def test_argocd_status_and_tag():
    assert argocd_status({"phase": "Running"}) == ("running", None)
    assert argocd_status({"phase": "Succeeded", "health": "Healthy", "sync": "Synced"}) == ("success", None)
    assert argocd_status({"phase": "Failed"}) == ("failed", "sync")
    assert argocd_status({"phase": "Succeeded", "health": "Degraded"}) == ("failed", "health")
    # 11-03 Sync 대기 — 수동 Sync 앱의 새 리비전 OutOfSync는 실패가 아니다
    base = {"sync": "OutOfSync", "health": "Healthy", "revision": "b" * 40, "op_revision": "a" * 40}
    assert argocd_status({**base, "automated": False, "phase": "Succeeded"}) == ("waiting", None)
    assert argocd_status({**base, "automated": False, "phase": "Failed"}) == ("waiting", None)   # 지난 작업의 실패 — 새 리비전과 무관
    assert argocd_status({**base, "automated": True, "phase": "Succeeded"}) == ("running", None)  # 자동 Sync — 곧 동기화된다
    assert argocd_status({**base, "automated": None}) == ("running", None)                         # 모르면 예전처럼
    same = {**base, "op_revision": "b" * 40}
    assert argocd_status({**same, "automated": False, "phase": "Failed"}) == ("failed", "sync")    # 이 리비전의 Sync가 실패
    assert argocd_status({**same, "automated": False, "phase": "Running"}) == ("running", None)    # 사람이 Sync를 눌렀다
    assert argocd_status({**base, "automated": False, "health": "Degraded"}) == ("failed", "health")
    imgs =["mysql:8.0", "harbor.ronanlab.dev/runshoes/runshoes:0f349e101774",
            "harbor.ronanlab.dev/runshoes/runshoes-chatbot:0f349e101774"]
    assert image_tag(imgs, "runshoes") == "0f349e101774"
    assert image_tag(["harbor.ronanlab.dev/petmint/petmint-app:abcdefabcdef"], "runshoes") is None


def test_other_repo():
    repo = "/home/kopo17/AI_programming/runshoes"
    # 실측: 런슈즈 세션이 인프라 저장소에 한 커밋이 런슈즈 커밋으로 잡혔다
    assert other_repo("cd ~/ronanlab-infra && git add x && git commit -q -F - <<'EOF'", repo, repo)
    assert other_repo("git -C /home/kopo17/ronanlab-infra commit -m x", repo, repo)
    assert not other_repo("git add a && git commit -m 'fix'", repo, repo)
    assert not other_repo("cd backend && git commit -m x", repo, repo)          # 저장소 안 하위 디렉토리
    assert not other_repo(f"cd {repo} && git commit -m x", repo, "/tmp")


def test_commit_match():
    repo = "/home/kopo17/AI_programming/runshoes"
    heredoc = "git add a && git commit -q -F - <<'EOF'\nfix(ui): 와이드 \"없음\"은 출처 면제 — 관리 폼\n\n본문\nEOF"
    assert commit_match(heredoc, 'fix(ui): 와이드 "없음"은 출처 면제 — 관리 폼', repo, repo) == 2
    assert commit_match(heredoc, "fix(catalog): 출처 묶음의 와이드 칸", repo, repo) == 0     # 다른 제목 → 아니다
    # 한 명령에서 런슈즈 커밋 뒤 인프라 저장소로 — 제목이 있으면 이 커밋
    both = "git commit -m 'feat: 다듬기 3차 — 체험 카드' && cd ~/ronanlab-infra && git commit -m 'runbook'"
    assert commit_match(both, "feat: 다듬기 3차 — 체험 카드", repo, repo) == 2
    assert commit_match("cd ~/ronanlab-infra && git commit -m 'runbook'", "feat: x", repo, repo) == 0
    assert commit_match("git revert --no-edit 648548b", "Revert x", repo, repo) == 1          # 메시지를 알 수 없음


def test_allowed_sources():
    nets = "127.0.0.0/8,192.168.121.0/24,192.168.122.0/24"
    assert _allowed("192.168.122.11", nets) and _allowed("192.168.121.179", nets) and _allowed("127.0.0.1", nets)
    assert not _allowed("192.168.0.20", nets)      # LAN에서 경로를 잡아 보내도 거절
    assert not _allowed("8.8.8.8", nets)


def test_config_loads():
    r = load_pipeline(REPO / "config" / "pipeline.toml")
    assert r.by("jenkins_job", "runshoes-app").name == "runshoes"
    assert r.by("harbor_project", "petmint").name == "petmint-rag-chatbot"
    assert set(r.infra) == {"jenkins", "harbor", "argocd"}


# ── DB + 임시 git 저장소 ───────────────────────────────────────
class FakePipeline:
    def __init__(self):
        self.events, self.msgs = [], []

    def submit(self, ev):
        self.events.append(ev)

    def publish(self, m):
        self.msgs.append(m)


class FakeNotifier:
    def __init__(self):
        self.sent = []
        self.rules = SimpleNamespace(for_project=lambda n: SimpleNamespace(prefix="[런슈즈]") if n == "runshoes" else None)

    def send_direct(self, project, kind, session_id, msg):
        self.sent.append((project, kind, msg))


def _git(repo: Path, *args: str, when: datetime | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x"}
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
    return subprocess.run(["git", "-C", str(repo), *args], env=env, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str, when: datetime) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"{name} 고침", when=when)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def env(tmp_path: Path):
    s = Settings(mysql_database="foreman_test", watch_enabled=False)
    conn = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                           password=s.mysql_password.get_secret_value(), database=s.mysql_database, autocommit=True)
    with conn.cursor() as c:
        c.execute("SET FOREIGN_KEY_CHECKS = 0")
        c.execute("SHOW TABLES")
        for (t,) in c.fetchall():
            c.execute(f"DROP TABLE `{t}`")
        c.execute("SET FOREIGN_KEY_CHECKS = 1")
    assert migrate_main([], settings=s) == 0
    repo = tmp_path / "runshoes"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    with conn.cursor() as c:
        c.execute("UPDATE project SET repo_path = %s WHERE name = 'runshoes'", (str(repo),))
    yield s, repo, conn
    conn.close()


def q(conn, sql, *a):
    with conn.cursor() as c:
        c.execute(sql, a)
        return c.fetchall()


@pytest.mark.db
async def test_chain_end_to_end(env):
    s, repo, conn = env
    t0 = datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(minutes=30)
    c1 = _commit(repo, "a.txt", t0)
    c2 = _commit(repo, "b.txt", t0 + timedelta(minutes=5))
    _git(repo, "update-ref", "refs/remotes/origin/main", c1)          # c1만 push됨
    # c2는 런슈즈 세션이 git commit을 부른 직후에 생겼다
    (char,) = q(conn, "SELECT c.id FROM `character` c JOIN project p ON p.id = c.project_id "
                      "WHERE p.name = 'runshoes' AND c.current_role = 'foreman'")[0]
    with conn.cursor() as c:
        c.execute("INSERT INTO character_session (character_id, type, role, cc_session_id, title, wake_reason) "
                  "VALUES (%s, 'agent', 'coder', 'aaaaaaaa-0000-0000-0000-000000000000', '장바구니 고침', 'user')", (char,))
        sid = c.lastrowid
        c.execute("INSERT INTO event (session_id, character_id, source, ts, type, tool, target) VALUES "
                  "(%s, %s, 'transcript', %s, 'tool_use', 'Bash', 'git add b.txt && git commit -m \"b.txt 고침\"')",
                  (sid, char, t0 + timedelta(minutes=5) - timedelta(seconds=3)))
        ev = c.lastrowid
    engine = make_engine(s)
    notifier = FakeNotifier()
    pm = PipelineManager(engine, load_pipeline(REPO / "config" / "pipeline.toml"), FakePipeline(), Masker(env_paths=[]),
                         notifier)
    try:
        await pm.start(loops=False)
        p = pm.rules.projects["runshoes"]
        assert await pm.scan_git(p) == 2
        rows = dict((r[0], r[1:]) for r in q(conn, "SELECT sha, session_id, event_id, pushed_at FROM git_commit"))
        assert rows[c2][0] == sid and rows[c2][1] == ev and rows[c2][2] is None     # 세션 귀속, 아직 push 전
        assert rows[c1][0] is None and rows[c1][2] is not None                      # 사람 커밋, push됨
        assert q(conn, "SELECT commit_sha FROM event WHERE id = %s", ev)[0][0] == c2

        # Jenkins 첫 빌드(c1), 그다음 2분 폴링 사이에 c2 · c3이 push되어 빌드 하나(머리 c3)
        await pm.on_jenkins({"job": "runshoes-app", "number": 1, "phase": "started", "commit": c1})
        await pm.on_jenkins({"job": "runshoes-app", "number": 1, "phase": "completed", "result": "SUCCESS", "commit": c1})
        c3 = _commit(repo, "c.txt", t0 + timedelta(minutes=8))
        _git(repo, "update-ref", "refs/remotes/origin/main", c3)
        await pm.scan_git(p)
        assert q(conn, "SELECT pushed_at IS NOT NULL FROM git_commit WHERE sha = %s", c2)[0][0] == 1
        out = await pm.on_jenkins({"job": "runshoes-app", "number": 2, "phase": "started", "commit": c3,
                                   "url": "https://jenkins.ronanlab.dev/job/runshoes-app/2/"})
        linked = {r[0] for r in q(conn, "SELECT commit_sha FROM build_commit WHERE build_id = %s", out["build"])}
        assert linked == {c2, c3}                               # 여러 커밋이 한 빌드에
        await pm.on_harbor({"type": "PUSH_ARTIFACT", "occur_at": 1793620000, "event_data": {
            "resources": [{"digest": "sha256:01", "tag": c3[:12]}],
            "repository": {"namespace": "runshoes", "repo_full_name": "runshoes/runshoes"}}})
        assert q(conn, "SELECT commit_sha FROM build WHERE stage = 'harbor'")[0][0] == c3   # 태그 12자리 → 전체 SHA
        # 늦게 온 running이 끝난 상태를 덮지 않는다 / 실패로 바뀌면 한 번만 알린다
        await pm.on_argocd({"app": "runshoes", "phase": "Succeeded", "health": "Degraded", "revision": "f" * 40,
                            "images": [f"harbor.ronanlab.dev/runshoes/runshoes:{c3[:12]}"], "message": "CrashLoopBackOff"})
        await pm.on_argocd({"app": "runshoes", "phase": "Running", "revision": "f" * 40,
                            "images": [f"harbor.ronanlab.dev/runshoes/runshoes:{c3[:12]}"]})
        await pm.on_argocd({"app": "runshoes", "phase": "Succeeded", "health": "Degraded", "revision": "f" * 40,
                            "images": [f"harbor.ronanlab.dev/runshoes/runshoes:{c3[:12]}"]})
        assert q(conn, "SELECT status, step FROM build WHERE stage = 'argocd'")[0] == ("failed", "health")
        assert len(notifier.sent) == 1 and "ArgoCD 배포" in notifier.sent[0][2] and c3[:8] in notifier.sent[0][2]

        # 인프라 캐릭터 — 첫 웹훅에 등장, 단계마다 하나
        infra = q(conn, "SELECT name, infra_type, status FROM `character` WHERE kind = 'infra' ORDER BY id")
        assert [r[1] for r in infra] == ["jenkins", "harbor", "argocd"] and all(r[2] == "IDLE" for r in infra)

        snap = await pm.snapshot()
        run = next(x for x in snap["projects"] if x["project"] == "runshoes")
        chain = run["chains"][0]
        assert chain["head"] == c3 and chain["broke"] == "argocd"
        assert {c["sha"] for c in chain["commits"]} == {c2, c3}
        assert next(c for c in chain["commits"] if c["sha"] == c2)["title"] == "장바구니 고침"
        assert set(chain["stages"]) == {"jenkins", "harbor", "argocd"}

        # Jenkins 실패 — 깨진 스테이지까지
        await pm.on_jenkins({"job": "runshoes-app", "number": 3, "phase": "completed", "result": "FAILURE",
                             "stage": "빌드·push", "commit": c3})
        assert q(conn, "SELECT status, step FROM build WHERE external_id = 'runshoes-app#3'")[0] == ("failed", "빌드·push")
        assert "Jenkins 빌드 · 빌드·push" in notifier.sent[-1][2]
        # 모르는 job은 건너뛴다
        assert "ignored" in await pm.on_jenkins({"job": "other", "number": 1})
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_watch_missing_and_webhook_break(env):
    """빠진 알림 찾기(토큰 없는 보정) — push 뒤 시작 알림이 없으면 알리고, 늦게 오면 한 번 더. 웹훅 끊김 · 복구."""
    s, repo, conn = env
    t0 = datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(minutes=30)
    c1 = _commit(repo, "a.txt", t0)
    _git(repo, "update-ref", "refs/remotes/origin/main", c1)
    engine = make_engine(s)
    notifier = FakeNotifier()
    pm = PipelineManager(engine, load_pipeline(REPO / "config" / "pipeline.toml"), FakePipeline(), Masker(env_paths=[]),
                         notifier)
    try:
        await pm.start(loops=False)
        p = pm.rules.projects["runshoes"]
        await pm.track_origin(p)
        assert "runshoes" not in pm._pending                     # 처음 본 머리는 기준만
        c2 = _commit(repo, "b.txt", t0 + timedelta(minutes=1))
        _git(repo, "update-ref", "refs/remotes/origin/main", c2)
        await pm.track_origin(p)
        pend = pm._pending["runshoes"]
        assert pend["head"] == c2
        await pm.check_watch()
        assert pend["state"] == "ok" and not notifier.sent
        pend["at"] -= timedelta(minutes=4)
        await pm.check_watch()
        assert pend["state"] == "late" and not notifier.sent      # 3분: 화면만
        pend["at"] -= timedelta(minutes=14)
        await pm.check_watch()
        await pm.check_watch()
        assert pend["state"] == "missing" and len(notifier.sent) == 1 and "빌드 알림 없음" in notifier.sent[0][2]
        snap = await pm.snapshot()
        assert next(x for x in snap["projects"] if x["project"] == "runshoes")["watch"]["state"] == "missing"
        # 늦게 도착 — 폴링이 잡은 빌드
        await pm.on_jenkins({"job": "runshoes-app", "number": 10, "phase": "started", "commit": c2, "cause": "webhook"})
        await pm.check_watch()
        assert "runshoes" not in pm._pending and "늦게 도착" in notifier.sent[-1][2]

        # 머리의 자손을 빌드해도 채워진 것으로 본다(커밋 여럿이 한 빌드)
        c3 = _commit(repo, "c.txt", t0 + timedelta(minutes=2))
        _git(repo, "update-ref", "refs/remotes/origin/main", c3)
        await pm.track_origin(p)
        c4 = _commit(repo, "d.txt", t0 + timedelta(minutes=3))
        await pm.on_jenkins({"job": "runshoes-app", "number": 11, "phase": "completed", "result": "SUCCESS", "commit": c4,
                             "cause": "poll"})
        await pm.check_watch()
        assert "runshoes" not in pm._pending
        n = len(notifier.sent)
        # 웹훅 끊김: 웹훅으로 시작한 적이 있고 폴링이 연달아 2번 → 한 번 알림, 웹훅으로 돌아오면 복구
        await pm.on_jenkins({"job": "runshoes-app", "number": 12, "phase": "started", "commit": c4, "cause": "poll"})
        assert len(notifier.sent) == n + 1 and "웹훅 끊김" in notifier.sent[-1][2]
        await pm.on_jenkins({"job": "runshoes-app", "number": 12, "phase": "completed", "result": "SUCCESS",
                             "commit": c4, "cause": "poll"})
        await pm.on_jenkins({"job": "runshoes-app", "number": 13, "phase": "started", "commit": c4, "cause": "poll"})
        assert len(notifier.sent) == n + 1                        # 같은 상태는 다시 안 알린다
        await pm.on_jenkins({"job": "runshoes-app", "number": 14, "phase": "started", "commit": c4, "cause": "webhook"})
        assert "웹훅 복구" in notifier.sent[-1][2]
        # 시작은 왔는데 35분 넘게 끝 알림 없음 — 한 번만
        old = int((datetime.now(UTC) - timedelta(minutes=40)).timestamp() * 1000)
        await pm.on_jenkins({"job": "runshoes-app", "number": 15, "phase": "started", "commit": c4, "cause": "webhook",
                             "timestamp": old})
        k = len(notifier.sent)
        await pm.check_watch()
        await pm.check_watch()
        ends = [m for _, _, m in notifier.sent[k:] if "끝 알림 없음" in m]
        assert len(ends) >= 1 and any("runshoes-app#15" in m for m in ends)
        assert len([m for m in ends if "#15" in m]) == 1
    finally:
        await engine.dispose()


@pytest.mark.db
async def test_argocd_sync_waiting_attaches_to_undeployed_build(env):
    """수동 Sync 앱(펫퍼민트 모양): OutOfSync 알림의 이미지는 아직 옛 태그다 — Sync 대기는 배포 안 된 새 빌드에 붙고,
    실패가 아니어서 알림도 없다. 사람이 Sync하면 같은 행이 성공으로."""
    s, repo, conn = env
    t0 = datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(minutes=30)
    old = _commit(repo, "a.txt", t0)
    new = _commit(repo, "b.txt", t0 + timedelta(minutes=1))
    _git(repo, "update-ref", "refs/remotes/origin/main", new)
    engine = make_engine(s)
    notifier = FakeNotifier()
    pm = PipelineManager(engine, load_pipeline(REPO / "config" / "pipeline.toml"), FakePipeline(), Masker(env_paths=[]),
                         notifier)
    try:
        await pm.start(loops=False)
        img = lambda sha: [f"harbor.ronanlab.dev/runshoes/runshoes:{sha[:12]}"]   # noqa: E731
        await pm.on_jenkins({"job": "runshoes-app", "number": 1, "phase": "completed", "result": "SUCCESS", "commit": old})
        await pm.on_argocd({"app": "runshoes", "sync": "Synced", "health": "Healthy", "phase": "Succeeded",
                            "revision": "1" * 40, "op_revision": "1" * 40, "images": img(old), "automated": False})
        await pm.on_jenkins({"job": "runshoes-app", "number": 2, "phase": "completed", "result": "SUCCESS", "commit": new})
        out = await pm.on_argocd({"app": "runshoes", "sync": "OutOfSync", "health": "Healthy", "phase": "Succeeded",
                                  "revision": "2" * 40, "op_revision": "1" * 40, "images": img(old), "automated": False})
        assert out["status"] == "waiting"
        assert q(conn, "SELECT commit_sha, status FROM build WHERE id = %s", out["build"])[0] == (new, "waiting")
        assert q(conn, "SELECT status FROM build WHERE stage = 'argocd' AND commit_sha = %s", old)[0][0] == "success"
        assert not notifier.sent                                           # 실패가 아니다
        snap = await pm.snapshot()
        chain = next(x for x in snap["projects"] if x["project"] == "runshoes")["chains"][0]
        assert chain["head"] == new and chain["stages"]["argocd"]["status"] == "waiting" and chain["broke"] is None
        await pm.on_argocd({"app": "runshoes", "sync": "Synced", "health": "Healthy", "phase": "Succeeded",
                            "revision": "2" * 40, "op_revision": "2" * 40, "images": img(new), "automated": False})
        assert q(conn, "SELECT status FROM build WHERE id = %s", out["build"])[0][0] == "success"
    finally:
        await engine.dispose()
