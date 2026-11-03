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
