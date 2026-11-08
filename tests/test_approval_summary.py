"""승인 요약(11-03) — 승인 창에서 "무엇을 대상으로"가 한눈에 보이게. 그리고 승인 이력의 결과 판정."""

from bridge.api.approvals import outcome
from bridge.approval_summary import summarize

R = "/home/kopo17/AI_programming/foreman"


def s(cmd, rule="rm-재귀", reason=""):
    return summarize("Bash", {"command": cmd}, rule, reason, R)


def test_rm_targets(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "a").write_text("x")
    out = s(f"rm -rf {d} {tmp_path}/gone")
    assert out.startswith("rm -rf → ") and f"{d} (기존 디렉토리, 파일 1개)" in out and "(지금은 없음)" in out
    assert "(이 명령에서 mktemp로 만든 것)" in s('D=$(mktemp -d) && cp a "$D/" && rm -rf "${D:?}"')
    assert "값을 모른다" in s('rm -rf "$TARGET"', "애매한-삭제")
    assert "/home/kopo17/AI_programming/foreman/build" in s("rm -r build")             # 상대 경로는 cwd로


def test_kubectl_docker_db_git():
    assert s('vagrant ssh m-k8s -c "kubectl -n jenkins delete pod jenkins-0"', "kubectl-삭제") == \
        "kubectl delete → pod/jenkins-0 (jenkins 네임스페이스)"
    assert "deploy.yaml에 적힌 것" in s("kubectl delete -f deploy.yaml", "kubectl-삭제")
    assert s("docker compose down -v", "docker-삭제").startswith("docker compose down → 볼륨까지")
    assert s("echo 'DROP DATABASE x;' | docker exec -i runshoes-mysql-dev mysql", "DB-파괴") == \
        "DROP DATABASE x (컨테이너 runshoes-mysql-dev)"
    assert "WHERE 없음" in s('mysql -e "DELETE FROM users;"', "DB-파괴")
    assert s("git -C ~/r push --force origin main", "git-강제push") == "git push --force origin main (~/r)"


def test_sensitive_and_write():
    out = s("cat .env.bridge", "민감한-경로", "Bash: 비밀 …(cat .env.bridge)")
    assert out == f"읽기(cat) → {R}/.env.bridge (비밀 파일)"
    w = summarize("Write", {"file_path": "config/approval.toml"}, "보호-설정파일", "", R)
    assert w == f"쓰기 → {R}/config/approval.toml (안전 규칙 · 설정 파일)"


def test_fallback_and_never_raises():
    assert s("sudo reboot", "재부팅-종료") == "재부팅-종료 → sudo reboot"
    assert s('rm -rf "unterminated', "rm-재귀")                                      # 따옴표가 깨져도 무언가 낸다


def test_outcome():
    assert outcome("terminal", "terminal", "accept", None) == "approved"
    assert outcome("allowed", "browser", None, None) == "approved"
    assert outcome("denied", "browser", None, None) == "denied"
    assert outcome("timeout", "timeout", None, 1) == "approved"     # 시간 초과 뒤 터미널에서 허락 — 도구가 돌았다
    assert outcome("timeout", "timeout", None, 0) == "denied"
    assert outcome("abandoned", "bridge", None, None) == "unknown"


def test_heredoc_body_is_not_parsed_as_shell():
    """11-03 — 파이썬 heredoc 안 f"rm -f {SP}/shots"를 셸로 읽어 "frm (변수…)"가 나왔다."""
    cmd = ".venv/bin/python - <<'EOF'\nimport subprocess\nSP='/x'\nsubprocess.run(f\"rm -rf {SP}/shots\", shell=True)\nEOF"
    out = s(cmd)
    assert "frm" not in out and "{SP}" not in out
    assert out.startswith("rm-재귀 → python") and "스크립트 안에서 걸림" in out
    # heredoc 밖의 셸 명령은 그대로 뽑는다
    out2 = s("rm -rf /tmp/zz-none && cat > notes.md <<'EOF'\nrm -rf 설명\nEOF")
    assert out2.startswith("rm -rf → /tmp/zz-none")


def test_ask_user_question_is_readable():
    """11-09 — AskUserQuestion 카드가 JSON 300자에서 잘려 선택지를 못 봤다. 질문 · 선택지를 읽는 글로, 1024자까지."""
    from bridge.approvals import _approval_text, _target
    long = "설명 " * 120
    inp = {"questions": [{"question": "어떻게 키울까요?", "header": "키우는 법", "multiSelect": False,
                          "options": [{"label": "캐릭터만", "description": long}, {"label": "캐릭터+가구", "description": "같이"},
                                      {"label": "여백만", "description": "조금"}]}]}
    t = _target("AskUserQuestion", inp)
    assert t.startswith("1. [키우는 법] 어떻게 키울까요?") and "   3) 여백만 — 조금" in t and "{" not in t
    assert len(t) > 300
    assert summarize("AskUserQuestion", inp, "cc", "", None) == "질문 — 어떻게 키울까요?"
    msg = _approval_text("foreman", "AskUserQuestion", t, "질문", "", 3600, None)
    assert "❓" in msg and "승인" not in msg and msg.endswith("그 세션의 터미널에서 답합니다")


def test_answer_question_from_panel():
    """11-09 — 패널에서 질문에 답한다: 선택지 이름만, 하나만 고름 질문엔 하나, 여러 개는 쉼표로. 결과는 ("answer", None)."""
    import asyncio
    from types import SimpleNamespace

    from bridge.approvals import ApprovalManager

    async def run():
        inp = {"questions": [{"question": "A?", "multiSelect": False, "options": [{"label": "x"}, {"label": "y"}]},
                             {"question": "B?", "multiSelect": True, "options": [{"label": "p"}, {"label": "q"}]}]}
        m = SimpleNamespace(waiting={}, questions={7: inp}, answers={})
        m.questions_of = lambda aid: ApprovalManager.questions_of(m, aid)
        assert ApprovalManager.answer(m, 7, {"A?": ["x"]}) == "gone"            # 기다리는 hook이 없다
        m.waiting[7] = asyncio.get_running_loop().create_future()
        assert ApprovalManager.answer(m, 7, {"A?": ["x"]}) == "bad"             # B? 안 골랐다
        assert ApprovalManager.answer(m, 7, {"A?": ["x", "y"], "B?": ["p"]}) == "bad"   # 하나만 고르는 질문에 둘
        assert ApprovalManager.answer(m, 7, {"A?": ["z"], "B?": ["p"]}) == "bad"        # 없는 선택지
        assert ApprovalManager.answer(m, 7, {"A?": ["y"], "B?": ["p", "q"]}) == "ok"
        assert m.answers[7] == {"A?": "y", "B?": "p, q"} and m.waiting[7].result() == ("answer", None)
        assert ApprovalManager.answer(m, 7, {"A?": ["y"], "B?": ["p"]}) == "gone"       # 이미 답했다
        assert ApprovalManager.questions_of(m, 8) is None

    asyncio.run(run())
