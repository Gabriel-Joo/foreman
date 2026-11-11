"""`pgrep -f` · `pkill -f`가 자기 셸에 걸리는 함정 막기(11-11, README 「나중에 할 일」 pgrep 줄 ①).

CC는 Bash 명령 전체를 `bash -c '…'`로 돌린다 → 그 셸의 명령 줄(/proc/<pid>/cmdline)에 명령 글이 통째로 들어 있다.
`pgrep -f <패턴>`은 명령 줄 전체에서 패턴(정규식)을 찾으므로, **패턴이 이 명령 글 어딘가에 걸리면 자기 자신을 찾는다.**
- 11-09 관리자 "다른 pytest 있음"을 세 번 헛봄, 코더 233 `until ! pgrep -f "tools/screen.py"` 셸이 영원히 안 끝남
- 대괄호 트릭(`[p]ython`)은 패턴 글자 자체에는 안 걸리게 하지만, **같은 명령 안에서 그 프로그램을 돌리면** 뒤쪽 글자
  (`.venv/bin/python -m pytest …`)에 또 걸린다(11-10 관리자)
그래서 판정은 "패턴 정규식이 이 명령 글에 걸리는가" 하나다 — 걸리면 거부하고 까닭과 고친 예를 돌려준다.
승인 모드(observe)와 상관없이(스키마 잠금 · 다른 저장소 막음과 같은 자리, bridge/approvals.py). `pkill -f`는 자기 셸을 죽인다.
"""

from __future__ import annotations

import re
import shlex

TOOLS = {"Bash", "Monitor"}                 # 명령 글을 셸로 돌리는 도구
_CALL = re.compile(r"(?<![\w./-])(pgrep|pkill)(?![\w-])")
_STOP = re.compile(r"\|\||&&|[;|\n)`]")      # 이 호출의 인자가 끝나는 곳
# 값을 받는 옵션(그다음 낱말은 패턴이 아니다) — procps pgrep/pkill
_ARG_OPTS = {"-d", "-g", "-G", "-P", "-s", "-t", "-u", "-U", "-F", "--delimiter", "--pgroup", "--group", "--parent",
             "--session", "--terminal", "--euid", "--uid", "--pidfile", "--ns", "--nslist", "--signal", "-r", "--runstates"}


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|$)", re.S)
# 명령 자리 — 이 뒤에 오는 pgrep만 실제로 돈다(echo · 커밋 글 · 따옴표 안의 낱말은 아니다)
_CMD_POS = re.compile(r"(^|[;&|(\n`!]|\$\(|\b(until|while|if|then|do|else|elif|time|sudo|exec|xargs|nohup)|"
                      r"\btimeout\s+\S+|\bwatch(\s+-\S+(\s+\d+)?)*)\s*$")


def _calls(cmd: str) -> list[tuple[str, bool, str | None]]:
    """명령 글 안의 pgrep · pkill 호출 — [(이름, -f 있음, 패턴)]. heredoc 본문과 명령 자리가 아닌 곳은 뺀다."""
    out = []
    body = _HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n", cmd)
    for m in _CALL.finditer(body):
        if not _CMD_POS.search(body[:m.start()]):
            continue
        rest = body[m.end():]
        stop = _STOP.search(rest)
        seg = rest[:stop.start()] if stop else rest
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        full, pat, skip = False, None, False
        for t in toks:
            if skip:
                skip = False
                continue
            if t in _ARG_OPTS:
                skip = True
                continue
            if t == "--full":
                full = True
                continue
            if t.startswith("--"):                       # --x=값 · 값 없는 긴 옵션
                continue
            if t.startswith("-") and len(t) > 1:
                letters = t[1:]
                if letters.isdigit() or (letters.isupper() and len(letters) > 1):   # pkill -9 · -TERM(신호)
                    continue
                if "f" in letters:                       # -f · -af · -fl …
                    full = True
                continue
            pat = t
            break
        out.append((m.group(1), full, pat))
    return out


def _matches(pat: str, cmd: str) -> bool:
    try:
        return re.search(pat, cmd) is not None
    except re.error:
        return pat in cmd


def check(tool: str, inp: dict) -> str | None:
    """거부 까닭(화면 · CC에 보일 글) 또는 None."""
    if tool not in TOOLS:
        return None
    cmd = str(inp.get("command") or "")
    if "pgrep" not in cmd and "pkill" not in cmd:
        return None
    for name, full, pat in _calls(cmd):
        if not full or not pat or "$" in pat:            # 변수 패턴은 글로 가릴 수 없다 — 막지 않는다
            continue
        if _matches(pat, cmd):
            fix = re.sub(r"^(\W*)(\w)", r"\1[\2]", pat, count=1)
            return (f"pgrep-자기걸림: `{name} -f {pat}`가 이 명령 자신에 걸립니다 — CC는 Bash 명령 전체를 `bash -c '…'`로 돌려 "
                    f"그 셸의 명령 줄에 이 글이 그대로 있습니다" + (" · pkill이면 자기 셸을 죽입니다" if name == "pkill" else "")
                    + f". 고친 예: 패턴을 `{fix}`처럼 대괄호로 감싸고, 확인과 실행을 따로 칩니다(같은 명령 안에서 그 프로그램을 "
                    "돌리면 대괄호도 다시 걸립니다). 기다릴 때는 pgrep -f로 찾지 말고 그 작업의 PID나 결과 파일을 봅니다")
    return None
