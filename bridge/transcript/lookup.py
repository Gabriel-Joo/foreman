"""도구 호출 본문을 트랜스크립트에서 그때그때 읽는다(11-05 패널 — 터미널처럼 "무엇을 읽고 무엇이 나왔나").

DB에는 도구 결과 본문을 넣지 않는다(2단계 원칙 — 용량 · 비밀). 패널에서 활동 줄을 누를 때만 이 파일을 연다.
최근 것이 파일 끝에 있으므로 끝에서부터 조각(8MB)씩 거꾸로 tool_use_id를 찾는다. 730MB 파일 전체를 훑어도 1~2초.
"""

import json
import os
from pathlib import Path
from typing import Any

CHUNK = 8 << 20
MAX_TEXT = 60_000     # 결과 본문 상한(글자) — 화면용
MAX_INPUT = 20_000    # 입력 문자열 하나의 상한


def _iter_lines_backward(path: str | Path, needle: bytes):
    """needle이 든 줄을 파일 끝에서부터 돌려준다(줄 전체 bytes)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        end = size
        carry = b""
        while end > 0:
            start = max(0, end - CHUNK)
            f.seek(start)
            buf = f.read(end - start) + carry
            # 조각 앞쪽의 잘린 줄은 다음(앞) 조각과 이어 붙인다
            if start > 0:
                cut = buf.find(b"\n")
                carry, buf = (buf[:cut], buf[cut + 1:]) if cut >= 0 else (buf, b"")
            else:
                carry = b""
            pos = len(buf)
            while True:
                i = buf.rfind(needle, 0, pos)
                if i < 0:
                    break
                ls = buf.rfind(b"\n", 0, i) + 1
                le = buf.find(b"\n", i)
                le = len(buf) if le < 0 else le
                yield buf[ls:le]
                pos = ls
            end = start


def _text_blocks(content: Any) -> tuple[str, list[str]]:
    """tool_result content → (글, 글이 아닌 블록 종류들)."""
    if isinstance(content, str):
        return content, []
    texts, other = [], []
    for b in content or []:
        if isinstance(b, dict):
            if b.get("type") == "text":
                texts.append(b.get("text", ""))
            else:
                other.append(b.get("type", "?"))
    return "\n".join(texts), other


def find_tool_call(path: str | Path, tool_use_id: str) -> dict[str, Any]:
    """{"input": dict|None, "name": str|None, "result": str|None, "is_error": bool|None, "extra": dict, "found": {...}}"""
    out: dict[str, Any] = {"input": None, "name": None, "result": None, "is_error": None, "extra": {},
                           "other_blocks": [], "found": {"use": False, "result": False}}
    needle = tool_use_id.encode()
    for raw in _iter_lines_backward(path, needle):
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        content = (d.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if not out["found"]["result"] and b.get("type") == "tool_result" and b.get("tool_use_id") == tool_use_id:
                txt, other = _text_blocks(b.get("content"))
                out["result"], out["other_blocks"] = txt, other
                out["is_error"] = bool(b.get("is_error"))
                tur = d.get("toolUseResult")
                if isinstance(tur, dict):        # Bash는 stdout · stderr가 따로, 끊김 · 백그라운드 표시
                    for k in ("stderr", "interrupted", "returnCodeInterpretation", "backgroundTaskId", "durationMs",
                              "numLines", "totalLines"):
                        if tur.get(k) not in (None, "", False):
                            out["extra"][k] = tur[k]
                    if isinstance(tur.get("file"), dict):
                        out["extra"]["file"] = {k: tur["file"].get(k) for k in ("filePath", "numLines", "startLine", "totalLines")}
                out["result_ts"] = d.get("timestamp")
                out["found"]["result"] = True
            elif not out["found"]["use"] and b.get("type") == "tool_use" and b.get("id") == tool_use_id:
                out["input"], out["name"] = b.get("input"), b.get("name")
                out["use_ts"] = d.get("timestamp")
                out["found"]["use"] = True
        if out["found"]["use"] and out["found"]["result"]:
            break
    return out


def clip_input(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj if len(obj) <= MAX_INPUT else obj[:MAX_INPUT] + f"\n…({len(obj) - MAX_INPUT:,}자 줄임)"
    if isinstance(obj, dict):
        return {k: clip_input(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clip_input(v) for v in obj[:200]]
    return obj


def clip_text(s: str | None) -> tuple[str | None, int]:
    if s is None:
        return None, 0
    n = len(s)
    if n <= MAX_TEXT:
        return s, n
    head = MAX_TEXT * 2 // 3
    return s[:head] + f"\n\n…(가운데 {n - MAX_TEXT:,}자 줄임 — 전체는 트랜스크립트에)…\n\n" + s[-(MAX_TEXT - head):], n
