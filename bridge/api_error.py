"""CC API 오류의 종류 가르기(11-11, README 「"API 오류"만 뜨고 까닭이 안 보인다」).

11-10 서기 245의 응답이 모델 안전 분류기에 두 번 막혔는데(`[reasoning_extraction]`) 패널에는 끝 이유 「API 오류」만 보였고 브리지
로그에도 남지 않았다 — 관리자가 tmux 화면과 대화 기록을 열어 보고서야 알았다(조용한 고장).

CC는 오류를 응답 대신 남긴다(트랜스크립트 assistant 줄 `isApiErrorMessage`, `error` 값 — rate_limit · invalid_request 등,
글 "API Error: …"). 이 글에서 종류 · 할 일 · request id만 뽑는다. 글은 적재기 Masker를 거친 것이고, 여기서 다시 URL을 지운다 —
request id(`req_…`)는 비밀값이 아니다(지원 문의에 쓰는 번호).
"""

from __future__ import annotations

import re
from typing import Any

REQ_RE = re.compile(r"\breq_[A-Za-z0-9]{8,64}\b")
DETAIL_RE = re.compile(r"Details:\s*`?\[([a-z_]{3,40})\]`?")
RESET_RE = re.compile(r"resets\s+([0-9:apm]+(?:\s*\([^)]{1,40}\))?)", re.I)

# (kind, 판정, 화면 이름, 할 일)
KINDS: list[tuple[str, Any, str, str]] = [
    ("safeguard", re.compile(r"safeguards flagged|usage policy|violat\w+ (our|the) (usage|acceptable)", re.I),
     "안전 분류기 거부", "/model로 다른 모델로 바꾸거나 요청 글을 바꿔 다시 보냅니다"),
    ("rate_limit", re.compile(r"rate.?limit|spend limit|usage limit|hit your .*limit|limit resets", re.I),
     "사용량 한도", "한도가 풀리는 시각까지 기다리거나 한도를 올립니다"),
    ("overloaded", re.compile(r"overloaded|\b529\b", re.I),
     "과부하", "잠시 뒤 다시 보냅니다(Anthropic 쪽이 붐빕니다)"),
    ("context", re.compile(r"prompt is too long|context (window|length)|too many tokens", re.I),
     "맥락 초과", "/compact로 줄이거나 새 세션으로 옮깁니다"),
    ("auth", re.compile(r"authenticat|\b401\b|invalid api key|please run /login|oauth", re.I),
     "인증", "/login으로 다시 로그인합니다"),
    ("server", re.compile(r"\b5\d\d\b|internal server error|api_error|timed? ?out|connection", re.I),
     "서버 오류", "잠시 뒤 다시 보냅니다"),
]
ERROR_KIND = {"rate_limit": "rate_limit", "overloaded": "overloaded", "authentication_failed": "auth",
              "server_error": "server"}


def classify(text: str | None, error: str | None = None) -> dict[str, Any]:
    """{kind, label, action, request_id, detail, reset}. 모르면 kind 'unknown'(「API 오류」)."""
    t = text or ""
    kind, label, action = "unknown", "API 오류", "그 세션 터미널에서 오류 글을 보고 다시 보냅니다"
    hit = False
    for k, rx, lab, act in KINDS:
        if rx.search(t):
            kind, label, action, hit = k, lab, act, True
            break
    if not hit and error in ERROR_KIND:
        k = ERROR_KIND[error]
        for k2, _, lab, act in KINDS:
            if k2 == k:
                kind, label, action = k2, lab, act
    m = REQ_RE.search(t)
    d = DETAIL_RE.search(t)
    r = RESET_RE.search(t) if kind == "rate_limit" else None
    return {"kind": kind, "label": label, "action": action, "request_id": m.group(0) if m else None,
            "detail": d.group(1) if d else None, "reset": r.group(1) if r else None, "error": error}


def one_line(c: dict[str, Any]) -> str:
    """패널 · 텔레그램 한 줄 — 「안전 분류기 거부 [reasoning_extraction] · req_… — 할 일」."""
    parts = [c["label"] + (f" [{c['detail']}]" if c.get("detail") else "")]
    if c.get("reset"):
        parts.append(f"{c['reset']}에 풀림")
    if c.get("request_id"):
        parts.append(c["request_id"])
    return " · ".join(parts) + f" — {c['action']}"
