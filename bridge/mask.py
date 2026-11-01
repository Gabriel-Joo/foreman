"""DB에 넣기 전에 비밀값을 가린다 — 프롬프트, 명령, assistant 글, 큐 내용 전부.

1. 정확한 값: 저장소의 .env.*(db · bridge · telegram)에 있는 값(8자 이상)을 «masked:KEY»로
2. 형식: 알려진 토큰 모양(텔레그램 봇, Anthropic, GitHub, AWS, Bearer, 개인키 블록)
3. 키=값: 이름에 PASSWORD · SECRET · TOKEN · API_KEY · PWD가 들어간 대입의 값(6자 이상)

남는 위험: 형식을 모르는 비밀(예: ~/.claude/sessions/*.key 내용 — 킥오프 때 한 번 출력에 찍혔다)은
1·2·3 어디에도 안 걸릴 수 있다. 그래서 tool_result 본문은 처음부터 저장하지 않는다(assembler.py).
"""

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from bridge.config import REPO

ENV_FILES = (".env.db", ".env.bridge", ".env.telegram")
MIN_EXACT = 8

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "«masked:private-key»"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), "«masked:telegram-bot-token»"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "«masked:anthropic-key»"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "«masked:github-token»"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "«masked:aws-key»"),
    (re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=-]{16,}"), r"\1 «masked»"),
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|_PWD)[A-Z0-9_]*)(\s*[=:]\s*)(['\"]?)([^\s'\"`$]{6,})\3"
        ),
        r"\1\2\3«masked»\3",
    ),
]


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
            if len(val) >= MIN_EXACT and not val.isdigit() and val.lower() not in ("true", "false"):
                out.append((val, f"«masked:{key.strip()}»"))
    out.sort(key=lambda kv: -len(kv[0]))  # 긴 것부터(한 값이 다른 값을 포함할 때)
    return out


class Masker:
    def __init__(self, env_paths: Iterable[Path] | None = None) -> None:
        self.exact = _load_exact(env_paths if env_paths is not None else (REPO / f for f in ENV_FILES))

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
