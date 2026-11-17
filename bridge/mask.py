"""DB에 넣기 전에 비밀값을 가린다 — 프롬프트, 명령, assistant 글, 큐 내용 전부.

1. 정확한 값: 비밀값 파일(`secret_env_files`, 저장소 맨 위 .env*에서 .example 같은 예시 파일을 뺀 전부와
   config가 가리키는 토큰 파일)에서 이름이 비밀인 키(PASSWORD, TOKEN, SECRET, KEY)의
   값(8자 이상)을 «masked:KEY»로. MYSQL_USER 같은 비밀 아닌 값은 가리지 않는다(실측: foreman_app이 가려졌다)
   11-17 전에는 db, bridge, telegram 셋을 손으로 적어 .env.notion, .env.project_tokens가 빠져 있었다.
   손 목록은 새 파일이 생길 때마다 또 빠지므로 고르는 방식으로 바꿨다(tests/test_secret_files.py가 지킨다)
2. 형식: 알려진 토큰 모양(텔레그램 봇, Anthropic, GitHub, AWS, Notion 통합, Bearer, 개인키 블록)
3. 키=값: 이름에 PASSWORD · SECRET · TOKEN · API_KEY · PWD가 들어간 대입의 값(6자 이상)

남는 위험: 형식을 모르는 비밀(예: ~/.claude/sessions/*.key 내용 — 킥오프 때 한 번 출력에 찍혔다)은
1·2·3 어디에도 안 걸릴 수 있다. 그래서 tool_result 본문은 처음부터 저장하지 않는다(assembler.py).
"""

import re
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from bridge.config import REPO

# 예시 파일(값 없음, 저장소에 추적됨). config/approval.toml의 secret 규칙과 같은 꼬리
EXAMPLE_SUFFIX = re.compile(r"\.(example|sample|template|dist)$")
# config가 비밀값 파일 경로를 바꿀 수 있는 자리: (파일, 표, 칸)
CONFIGURED_SECRET_FILES = (
    ("config/notify.toml", "telegram", "env_file"),        # bridge/notify.py
    ("config/tokens.toml", "project_tokens", "file"),      # bridge/scopetoken.py
)
MIN_EXACT = 8
SECRET_KEY = re.compile(r"(?i)PASSWORD|PASSWD|TOKEN|SECRET|KEY")

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "«masked:private-key»"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), "«masked:telegram-bot-token»"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "«masked:anthropic-key»"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "«masked:github-token»"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "«masked:aws-key»"),
    # Notion 내부 통합 토큰: 지금 꼴 ntn_, 옛 꼴 secret_ (뒤가 40자 넘는 영숫자라서 secret_key 같은 낱말에는 안 걸린다)
    (re.compile(r"\b(?:ntn|secret)_[A-Za-z0-9]{40,}\b"), "«masked:notion-token»"),
    (re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=-]{16,}"), r"\1 «masked»"),
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|_PWD)[A-Z0-9_]*)(\s*[=:]\s*)(['\"]?)([^\s'\"`$]{6,})\3"
        ),
        r"\1\2\3«masked»\3",
    ),
]


def configured_secret_files(repo: Path = REPO) -> list[Path]:
    """config가 가리키는 비밀값 파일(기본값이 아닌 경로로 바꿔도 따라간다). config를 못 읽으면 건너뛴다."""
    out: list[Path] = []
    for rel, table, key in CONFIGURED_SECRET_FILES:
        try:
            v = (tomllib.loads((repo / rel).read_text(encoding="utf-8")).get(table) or {}).get(key)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if v:
            p = Path(str(v))
            out.append(p if p.is_absolute() else repo / p)
    return out


def secret_env_files(repo: Path = REPO) -> list[Path]:
    """가릴 비밀값 파일: 저장소 맨 위 .env*에서 예시 파일을 뺀 전부와 config가 가리키는 토큰 파일. 이름만 고른다."""
    found = {p for p in repo.glob(".env*") if p.is_file() and not EXAMPLE_SUFFIX.search(p.name)}
    found.update(configured_secret_files(repo))
    return sorted(found)


def _load_exact(paths: Iterable[Path]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for p in paths:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.strip().strip("'\"")
            if not SECRET_KEY.search(key):
                continue
            if len(val) >= MIN_EXACT and not val.isdigit() and val.lower() not in ("true", "false"):
                out.append((val, f"«masked:{key.strip()}»"))
    out.sort(key=lambda kv: -len(kv[0]))  # 긴 것부터(한 값이 다른 값을 포함할 때)
    return out


class Masker:
    def __init__(self, env_paths: Iterable[Path] | None = None) -> None:
        self.exact = _load_exact(env_paths if env_paths is not None else secret_env_files())

    def text(self, s: str | None) -> str | None:
        if not s:
            return s
        for val, rep in self.exact:
            if val in s:
                s = s.replace(val, rep)
        for pat, rep in _PATTERNS:
            s = pat.sub(rep, s)
        return s

    def deep(self, obj: Any, clip: int | None = None) -> Any:
        """dict · list 안의 문자열을 모두 가린다. clip이 있으면 문자열마다 그 길이로 자르고 '…(N자)'를 붙인다."""
        if isinstance(obj, str):
            s = self.text(obj) or ""
            if clip is not None and len(s) > clip:
                return s[:clip] + f"…({len(s)}자)"
            return s
        if isinstance(obj, dict):
            return {k: self.deep(v, clip) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.deep(v, clip) for v in obj]
        return obj
