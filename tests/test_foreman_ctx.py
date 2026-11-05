"""포먼 디스패처 상황 묶음 — 서버 공통 경로(11-06). CLAUDE.md 정리로 경로 표가 docs/operations.md 「1.」로 갔다.
이 절이 옮겨지거나 이름이 바뀌면 디스패처가 클러스터 · VM 경로를 못 본다 — 여기서 먼저 깨진다."""

from bridge import foreman as fm


def test_server_paths_from_operations_doc():
    s = fm.server_paths()
    assert "vagrant ssh m-k8s" in s and "ronanlab-infra" in s and "petmint-rag-chatbot" in s
    assert "## 2." not in s                       # 「1.」 절만
