"""프로젝트 토큰 — 그 프로젝트 세션 · 방 API만 여는 토큰(11-11 C 2물결 「하나」, log/coder_c_wave2_20261111.md).

지금까지는 토큰 하나(`FOREMAN_API_TOKEN`)로 모든 API가 열렸다 — 런슈즈 세션에 주면 FOREMAN 방 세션도 띄우고 끝낼 수 있다.
관리 토큰은 그대로 전체용으로 남기고, 프로젝트마다 토큰을 하나 더 둔다.

- 값은 `.env.project_tokens`(권한 600, `.gitignore`의 `.env*`) — 줄마다 `FOREMAN_TOKEN_<프로젝트>=<값>`.
  만들기는 `python -m bridge.scopetoken new <프로젝트>` — 값을 화면에 찍지 않고 파일에만 쓴다(키 이름 · 파일만 알린다)
- 켜기는 `config/tokens.toml [project_tokens] enabled`(처음엔 false — 꺼져 있으면 프로젝트 토큰은 아예 안 받는다)
- 프로젝트 토큰이 닿는 곳(`allowed`) — 나머지는 모두 403 + 무엇이 왜 막혔는지:
    /api/sessions/{sid}[/…]           그 세션이 이 프로젝트 것일 때(방 · 패널 · 입력 · 끝내기 · 합치기 …)
    POST /api/spawn                   띄울 폴더(cwd)가 이 프로젝트 저장소(또는 그 worktree) 안일 때
    GET  /api/spawn/options           (읽기 — 띄우기 창 재료)
    /api/foreman/plan · start         본문 project(start는 plan.project)가 이 프로젝트일 때
    GET  /api/foreman/state · notes · context · merge-order   ?project= 가 이 프로젝트일 때
    GET  /api/merge-prep              (11-12) ?project= 가 이 프로젝트일 때 — 그 프로젝트 합치기 카드만.
                                      승인은 /api/sessions/{sid}/merge-prep(위 세션 줄) — 프로젝트 토큰이면 by=manager로 본다
    /api/managers[/…]                 (관리자 주소 — 「둘」) 읽기는 모두, 부탁 보내기는 보낸 쪽이 이 프로젝트일 때 — 그 라우터가 본다
    POST /api/publish                 (11-12) 본문 project가 이 프로젝트일 때. force · action=docsync는 관리 토큰만
    GET  /api/publish                 ?project= 가 이 프로젝트일 때(없으면 foreman)
    POST /api/publish/pair            (11-12) 본문 project가 이 프로젝트일 때 — 페이지가 그 root 아래인지는 게시기가 본다
  WS(`/ws`)와 터미널은 관리 토큰만 — 화면은 관리용이다
- 같은 유닉스 사용자로 도는 세션은 `.env.bridge`도 읽을 수 있다 — 이것은 막는 벽이 아니라 **잘못 부르는 것을 막는 칸막이**다
"""

from __future__ import annotations

import hmac
import os
import re
import secrets
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "tokens.toml"
MIN_LEN = 32
_KEY = re.compile(r"^FOREMAN_TOKEN_([A-Z0-9_]+)=(.*)$")


def key_of(project: str) -> str:
    """프로젝트 이름 → 환경 키 이름(`petmint-rag-chatbot` → `FOREMAN_TOKEN_PETMINT_RAG_CHATBOT`)."""
    return "FOREMAN_TOKEN_" + re.sub(r"[^A-Z0-9]", "_", project.upper())


@dataclass
class TokenConfig:
    enabled: bool = False
    file: Path = REPO / ".env.project_tokens"
    error: str | None = None            # 설정을 못 읽음 — 프로젝트 토큰은 받지 않고 이유를 남긴다

    @classmethod
    def load(cls, path: Path = CONFIG) -> "TokenConfig":
        if not path.exists():
            return cls()
        try:
            r = tomllib.loads(path.read_text()).get("project_tokens") or {}
        except (OSError, tomllib.TOMLDecodeError) as e:
            return cls(error=f"{path.name}을 읽지 못했습니다: {e}")
        f = Path(str(r.get("file") or ".env.project_tokens"))
        return cls(enabled=bool(r.get("enabled", False)), file=f if f.is_absolute() else REPO / f)


@dataclass
class TokenBook:
    """파일의 토큰들 — 바뀌면(mtime) 다시 읽는다. 값은 메모리에만, repr에 나오지 않게."""
    cfg: TokenConfig
    _mtime: float = -1.0
    _by_key: dict[str, str] = field(default_factory=dict, repr=False)
    error: str | None = None

    def _reload(self) -> None:
        try:
            st = self.cfg.file.stat()
        except FileNotFoundError:
            self._by_key, self._mtime, self.error = {}, -1.0, None
            return
        if st.st_mtime == self._mtime:
            return
        out: dict[str, str] = {}
        bad = []
        for ln in self.cfg.file.read_text().splitlines():
            m = _KEY.match(ln.strip())
            if not m:
                continue
            v = m.group(2).strip().strip("'\"")
            if len(v) < MIN_LEN:
                bad.append(f"FOREMAN_TOKEN_{m.group(1)}")
                continue
            out[f"FOREMAN_TOKEN_{m.group(1)}"] = v
        self._by_key, self._mtime = out, st.st_mtime
        self.error = f"{MIN_LEN}자보다 짧아 버린 토큰: {', '.join(bad)}" if bad else None

    def project_of(self, given: str, projects: list[str]) -> str | None:
        """받은 토큰이 어느 프로젝트 것인가. 모르면 None. 모든 후보와 비교한다(시간 차로 새지 않게)."""
        if not self.cfg.enabled or not given:
            return None
        self._reload()
        hit = None
        for p in projects:
            v = self._by_key.get(key_of(p))
            if v and hmac.compare_digest(given.encode(), v.encode()):
                hit = p
        return hit


# ── 범위 판정 ────────────────────────────────────────────────
_SESS = re.compile(r"^/api/sessions/(\d+)(/|$)")
_FOREMAN_BODY = {"/api/foreman/plan", "/api/foreman/start", "/api/foreman/handover"}
_FOREMAN_QUERY = {"/api/foreman/state", "/api/foreman/notes", "/api/foreman/context", "/api/foreman/merge-order",
                  "/api/merge-prep"}       # 11-12 — 관리자가 자기 프로젝트 합치기 카드를 모아 본다
ADMIN_ONLY_HINT = "관리 토큰(FOREMAN_API_TOKEN)이 필요합니다"


def in_repo(cwd: str, repo: str) -> bool:
    """cwd가 repo(또는 그 .worktrees/ 아래) 안인가. 링크를 풀고 본다."""
    if not cwd or not repo:
        return False
    c, r = os.path.realpath(os.path.expanduser(cwd)), os.path.realpath(repo)
    return c == r or c.startswith(r.rstrip("/") + "/")


PUBLISH_ADMIN_ONLY = "force · 한꺼번에 맞추기는 FOREMAN 관리자에게 부탁합니다"


def _publish_why(scope: str, method: str, query: dict[str, str], body: Any) -> str | None:
    """Notion 게시(11-12 사용자 결정 — 메모리 feedback-notion-publish-auth와 같은 선): 프로젝트 토큰은 자기 프로젝트 문서만
    force 없이 올린다. force 덮기 · [지금 맞추기] 한꺼번에(action = docsync)는 관리 토큰만 — 사람에게 묻는 일이라서.
    project가 없으면 foreman(PublishIn · GET 기본값과 같게)."""
    if method == "GET":
        p = query.get("project") or "foreman"
        if p == scope:
            return None
        return f"프로젝트 토큰({scope})으로는 ?project={scope} 의 게시 상태만 읽을 수 있습니다 — 받은 project: {p}"
    if method != "POST":
        return f"프로젝트 토큰({scope})은 이 API({method} /api/publish)에 닿지 않습니다 — {ADMIN_ONLY_HINT}"
    b = body if isinstance(body, dict) else {}
    p = b.get("project") or "foreman"
    if p != scope:
        return f"프로젝트 토큰({scope})으로는 이 프로젝트 문서만 게시할 수 있습니다 — 받은 project: {p}"
    # force는 거짓이 분명한 값만 통과(pydantic이 "true" · 1도 True로 받는다). 라우터(bridge/api/publish.py)도 한 번 더 본다
    # 11-20 포트폴리오 한꺼번에 올리기(원본 없는 페이지 내리기, 번호순 다시 세우기 포함)도 action = docsync라 관리 토큰만
    if b.get("force") not in (None, False, 0, "", "false", "False", "0") or b.get("action") == "docsync":
        return f"프로젝트 토큰({scope})으로는 할 수 없습니다 — {PUBLISH_ADMIN_ONLY}"
    return None


async def why_out_of_scope(scope: str, method: str, path: str, query: dict[str, str], body: Any,
                           session_project: Any, repo_of: Any, dispatch_project: Any = None) -> str | None:
    """프로젝트 토큰 요청이 범위 밖이면 사유, 안이면 None.
    session_project(sid) → 프로젝트 이름 | None, repo_of(project) → 저장소 경로 | None (둘 다 async)."""
    m = _SESS.match(path)
    if m:
        sid = int(m.group(1))
        p = await session_project(sid)
        if p == scope:
            return None
        return (f"프로젝트 토큰({scope})으로는 다른 프로젝트({p or '모름'})의 세션 {sid}을 다룰 수 없습니다 — "
                f"그 프로젝트 토큰이나 {ADMIN_ONLY_HINT}")
    if path == "/api/spawn" and method == "POST":
        cwd = (body or {}).get("cwd") if isinstance(body, dict) else None
        repo = await repo_of(scope)
        if cwd and repo and in_repo(cwd, repo):
            return None
        return (f"프로젝트 토큰({scope})으로는 그 프로젝트 저장소({repo or '등록 안 됨'}) 안에서만 세션을 띄울 수 있습니다 — "
                f"받은 폴더: {cwd or '없음'}")
    if path == "/api/spawn/options" and method == "GET":
        return None
    if path in _FOREMAN_BODY and method == "POST":
        b = body if isinstance(body, dict) else {}
        p = b.get("project") if path.endswith("/plan") else (b.get("plan") or {}).get("project")
        if p is None and path.endswith("/start") and b.get("use_saved") and dispatch_project and b.get("dispatch_id"):
            p = await dispatch_project(int(b["dispatch_id"]))     # 관리자에게 넘긴 계획(저장된 것) — 그 계획의 프로젝트
        if p == scope:
            return None
        return f"프로젝트 토큰({scope})으로는 이 프로젝트 계획만 세우고 시작할 수 있습니다 — 받은 project: {p or '없음'}"
    if path in _FOREMAN_QUERY and method == "GET":
        if query.get("project") == scope:
            return None
        return f"프로젝트 토큰({scope})으로는 ?project={scope} 로만 읽을 수 있습니다"
    if path == "/api/managers" or path.startswith("/api/managers/"):
        return None              # 관리자 주소 — 보낸 쪽 확인은 그 라우터(bridge/api/managers.py)가 한다
    if path == "/api/publish":
        return _publish_why(scope, method, query, body)
    if path == "/api/publish/pair" and method == "POST":
        p = (body or {}).get("project") if isinstance(body, dict) else None
        if p == scope:
            return None
        return f"프로젝트 토큰({scope})으로는 이 프로젝트 짝만 등록할 수 있습니다 — 받은 project: {p or '없음'}"
    if path == "/api/postit":
        # 11-15 포스트잇 — 그 프로젝트 관리자가 사람 말(「포스트잇에 올려라」)을 그 턴에서 올린다. 읽기도 그 프로젝트만
        p = query.get("project") if method == "GET" else (body or {}).get("project") if isinstance(body, dict) else None
        if p == scope and method in ("GET", "POST"):
            return None
        return f"프로젝트 토큰({scope})으로는 이 프로젝트 포스트잇만 읽고 올릴 수 있습니다. 받은 project: {p or '없음'}"
    return f"프로젝트 토큰({scope})은 이 API({method} {path})에 닿지 않습니다 — {ADMIN_ONLY_HINT}"


# ── 만들기(CLI) ──────────────────────────────────────────────
def write_token(project: str, file: Path) -> str:
    """새 토큰을 만들어 파일에 쓴다(같은 키는 바꿈). 값은 돌려주지 않는다 — 키 이름만."""
    key = key_of(project)
    lines = file.read_text().splitlines() if file.exists() else []
    lines = [ln for ln in lines if not ln.startswith(key + "=")]
    lines.append(f"{key}={secrets.token_urlsafe(32)}")
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(file, 0o600)
    return key


def main(argv: list[str]) -> int:
    cfg = TokenConfig.load()
    if len(argv) == 2 and argv[0] == "new":
        key = write_token(argv[1], cfg.file)
        print(f"{cfg.file}에 {key}를 썼습니다(값은 출력하지 않습니다). 켜져 있지 않으면 config/tokens.toml enabled")
        return 0
    if argv == ["list"]:
        book = TokenBook(cfg)
        book._reload()
        print("켜짐" if cfg.enabled else "꺼짐", "·", cfg.file)
        for k in sorted(book._by_key):
            print(" ", k)
        if book.error:
            print("  ⚠", book.error)
        return 0
    print("쓰는 법: python -m bridge.scopetoken new <프로젝트> | list", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
