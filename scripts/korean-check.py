#!/usr/bin/env python3
"""PostToolUse hook(11-05) — 직전 진행 글이 영어면 모델에게 바로 알린다.

CLAUDE.md의 "항상 한국어로(도구 호출 사이 진행 글까지)" 규칙은 세션 시작 때 한 번 읽히는 지시문이라,
영어 도구 결과를 읽은 직후의 짧은 진행 글이 영어로 흐르는 것을 막지 못했다(11-05에 여러 번).
이 hook은 도구가 끝날 때마다 트랜스크립트의 가장 최근 assistant 글 한 덩어리를 보고, 코드 · 경로 · URL을 뺀
나머지에 한글이 거의 없으면 additionalContext로 경고를 넣는다. 같은 글에는 한 번만. 실패해도 조용히 지나간다.

11-10: 알림에 모델이 쓴 글을 따옴표로 되돌려 넣지 않는다 — 서기 세션 245(sonnet)가 그 알림 직후 안전 분류기
(reasoning_extraction)에 막혔고, 되돌려 보여 주는 것이 원인으로 짐작되어 인용을 뺐다.
"""
import json
import os
import re
import sys

STATE_DIR = os.environ.get("FOREMAN_KOCHECK_STATE") or os.path.expanduser("~/.cache/foreman-kocheck")
TAIL_BYTES = 400_000


def last_text(path: str) -> tuple[str, str] | None:
    """트랜스크립트 끝에서 가장 최근 assistant text 블록 (uuid, 글)."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content") or []
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        text = "\n".join(t for t in texts if t.strip())
        if text:
            return e.get("uuid") or "", text
    return None


def is_english(text: str) -> bool:
    t = re.sub(r"```.*?```", " ", text, flags=re.S)           # 코드 블록
    t = re.sub(r"`[^`]*`", " ", t)                             # 인라인 코드 · 경로
    t = re.sub(r"https?://\S+|[\w./~-]*/[\w./-]+", " ", t)     # URL · 경로
    hangul = len(re.findall(r"[가-힣]", t))
    latin = len(re.findall(r"[A-Za-z]", t))
    return latin >= 25 and hangul < latin * 0.15


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("transcript_path")
    if not path or not os.path.exists(path):
        return
    found = last_text(path)
    if not found:
        return
    uid, text = found
    if not is_english(text):
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    mark = os.path.join(STATE_DIR, re.sub(r"[^\w-]", "_", data.get("session_id") or "x"))
    try:
        if open(mark).read().strip() == uid:
            return                                                # 이 글로는 이미 알렸다
    except OSError:
        pass
    with open(mark, "w") as f:
        f.write(uid)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
        "[한국어 규칙] 직전 진행 글이 영어였습니다. CLAUDE.md 작업 규칙: 도구 호출 사이의 짧은 진행 글까지 "
        "전부 한국어로 씁니다. 다음 글부터 한국어로 쓰세요(도구 결과가 영어여도)."}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
