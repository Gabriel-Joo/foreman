"""승인 요약 — 걸린 명령이 "무엇을 대상으로" 하는지 한 줄로(11-03 사용자 요청).

승인 창에 명령이 통째로 나와 읽기 힘들었다. 판단에 필요한 것은 대상이다:
  rm -rf → /tmp/claude-1000/…/tmp.x (이 명령에서 mktemp로 만든 것)
  rm -rf → /home/kopo17/volumes (기존 디렉토리, 파일 1,234개)
  kubectl delete → pod/jenkins-0 (jenkins 네임스페이스)
  DROP DATABASE runshoes_v3dry (컨테이너 runshoes-mysql-dev)
  읽기 → /home/kopo17/AI_programming/foreman/.env.bridge (비밀 파일)

규칙 이름이 아니라 명령을 본다 — CC 자체가 묻는 것(rule "cc")에도 같은 요약이 붙는다. 못 알아보면 명령 앞부분.
요약은 텔레그램 · 대시보드 · CC 승인 창(permissionDecisionReason) · 승인 이력(approval.summary)에 쓴다. 비밀값은 마스킹한 뒤에 쓴다.
"""

import os
import re
import shlex
from typing import Any

MAX = 300
SEG = re.compile(r"&&|\|\||[;|\n]")


def _words(s: str) -> list[str]:
    try:
        return shlex.split(s, comments=False)
    except ValueError:
        return s.split()


def _assigns(cmd: str) -> dict[str, str]:
    """같은 명령 안의 V=값. mktemp는 표시로."""
    out: dict[str, str] = {}
    for m in re.finditer(r"(?:^|[\s;&|(])([A-Za-z_]\w*)=(\"?)(\$\(\s*mktemp\b[^)]*\)|[^\s;&|\"]+)\2", cmd):
        out[m.group(1)] = "@mktemp" if "mktemp" in m.group(3) else m.group(3)
    return out


def _resolve(tok: str, cwd: str | None, env: dict[str, str]) -> tuple[str, str | None]:
    """rm 대상 하나 → (보여 줄 경로, 덧붙일 설명)."""
    m = re.fullmatch(r"\$\{?([A-Za-z_]\w*)(?::\?)?\}?(/.*)?", tok)
    if m:
        v = env.get(m.group(1))
        if v == "@mktemp":
            return f"${m.group(1)}{m.group(2) or ''}", "이 명령에서 mktemp로 만든 것"
        if v is None:
            return tok, "변수 — 이 명령 안에서 값을 모른다"
        tok = v + (m.group(2) or "")
    if "$" in tok or "`" in tok:
        return tok, "변수 · 치환 — 이 명령 안에서 값을 모른다"
    p = os.path.expanduser(tok)
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(cwd or "/", p))
    if any(ch in p for ch in "*?["):
        return p, "글롭"
    if os.path.islink(p):
        return p, "심볼릭 링크"
    if os.path.isdir(p):
        try:
            n, cut = _count_files(p)
            return p, f"기존 디렉토리, 파일 {n:,}{'+' if cut else ''}개"
        except OSError:
            return p, "기존 디렉토리"
    if os.path.exists(p):
        return p, "기존 파일"
    return p, "지금은 없음"


def _count_files(p: str, cap: int = 5000, dirs_cap: int = 2000, budget_s: float = 0.3) -> tuple[int, bool]:
    """파일 수 — PreToolUse는 4초 안에 답해야 하므로 0.3초 · 파일 5,000 · 디렉토리 2,000에서 멈춘다(그러면 '+')."""
    import time
    t0, n, d = time.monotonic(), 0, 0
    for _root, _dirs, files in os.walk(p):
        n += len(files)
        d += 1
        if n >= cap or d >= dirs_cap or time.monotonic() - t0 > budget_s:
            return n, True
    return n, False


def _rm(cmd: str, cwd: str | None) -> str | None:
    env = _assigns(cmd)
    targets, flags = [], ""
    for seg in SEG.split(cmd):
        w = _words(seg.strip())
        while w and (re.fullmatch(r"[A-Za-z_]\w*=.*", w[0]) or w[0] in ("sudo", "nice", "nohup", "command")):
            w = w[1:]
        if not w or os.path.basename(w[0]) not in ("rm", "rmdir"):
            continue
        opts = [x for x in w[1:] if x.startswith("-") and x != "--"]
        flags = flags or " ".join(opts)
        targets += [x for x in w[1:] if not x.startswith("-")]
    if not targets:
        return None
    shown = []
    for t in targets[:3]:
        path, why = _resolve(t, cwd, env)
        shown.append(f"{path} ({why})" if why else path)
    more = f" 외 {len(targets) - 3}개" if len(targets) > 3 else ""
    return f"rm {flags} → ".replace("  ", " ") + ", ".join(shown) + more


def _kubectl(cmd: str) -> str | None:
    m = re.search(r"\bkubectl\b([^;&|\n]*?)\s(delete|drain|cordon|scale)\s+([^;&|\n'\"]*)", cmd)
    if not m:
        return None
    allw = _words(m.group(1) + " " + m.group(3))
    ns = None
    for i, x in enumerate(allw):
        if x in ("-n", "--namespace") and i + 1 < len(allw):
            ns = allw[i + 1]
        elif x.startswith("--namespace="):
            ns = x.split("=", 1)[1]
    w = _words(m.group(3))
    res, i, files, extra = [], 0, [], []
    while i < len(w):
        x = w[i]
        if x in ("-n", "--namespace", "-l", "--selector", "--context", "--grace-period", "--timeout"):
            if x in ("-l", "--selector") and i + 1 < len(w):
                extra.append(f"라벨 {w[i + 1]}")
            i += 2
            continue
        if x in ("-f", "--filename") and i + 1 < len(w):
            files.append(w[i + 1])
            i += 2
            continue
        if x in ("--all", "-A", "--all-namespaces"):
            extra.append("전부" if x == "--all" else "모든 네임스페이스")
        elif not x.startswith("-"):
            res.append(x)
        i += 1
    if len(res) >= 2 and "/" not in res[0]:
        res = [f"{res[0]}/{r}" for r in res[1:]]
    what = ", ".join(res[:4]) or (f"{', '.join(files)}에 적힌 것" if files else "?")
    notes = [f"{ns} 네임스페이스" if ns else "기본 네임스페이스"] + extra
    return f"kubectl {m.group(2)} → {what} ({', '.join(notes)})"


def _docker(cmd: str) -> str | None:
    m = re.search(r"\bdocker(\s+compose)?\b([^;&|\n]*?)\s(rm|rmi|prune|volume\s+rm|volume\s+prune|network\s+rm|"
                  r"system\s+prune|image\s+prune|down)\b([^;&|\n]*)", cmd)
    if not m:
        return None
    verb = re.sub(r"\s+", " ", m.group(3))
    args = [x for x in _words(m.group(4)) if not x.startswith("-")]
    opts = [x for x in _words(m.group(4)) if x.startswith("-")]
    if verb == "down":
        vol = any(o in ("-v", "--volumes") for o in opts)
        return f"docker compose down → {'볼륨까지 지운다' if vol else '컨테이너'}" + (f" ({' '.join(opts)})" if opts else "")
    return f"docker {verb} → {', '.join(args[:4]) or '조건에 맞는 것 전부'}" + (f" ({' '.join(opts)})" if opts else "")


def _db(cmd: str) -> str | None:
    m = re.search(r"(?i)\b(drop\s+(?:database|table|schema)(?:\s+if\s+exists)?\s+[\w`.\"]+|truncate\s+table\s+[\w`.\"]+|"
                  r"delete\s+from\s+[\w`.\"]+(?:\s+where\s+[^;\"']{0,40})?|flushall|flushdb|dropdb\s+\S+)", cmd)
    if not m:
        return None
    s = re.sub(r"\s+", " ", m.group(1))
    if re.match(r"(?i)delete", s) and not re.search(r"(?i)\bwhere\b", s):
        s += " (WHERE 없음 — 전부)"
    c = re.search(r"\bdocker\s+exec\b(?:\s+-\w+)*\s+([\w.-]+)", cmd) or re.search(r"\bkubectl\b[^;&|\n]*\bexec\b[^;&|\n]*?\s([\w.-]+)\s+(?:-c\s+\S+\s+)?--", cmd)
    where = f" (컨테이너 {c.group(1)})" if c else ""
    return s + where


def _git(cmd: str) -> str | None:
    m = re.search(r"\bgit\b(?:\s+-C\s+(\S+))?[^;&|\n]*?\s(push|reset|clean|checkout|restore|branch|stash|filter-branch|"
                  r"filter-repo|reflog|gc)\b([^;&|\n]*)", cmd)
    if not m:
        return None
    where = f" ({m.group(1)})" if m.group(1) else ""
    return f"git {m.group(2)}{re.sub(r'\s+', ' ', m.group(3)).rstrip()[:120]}{where}"


def summarize(tool: str, inp: dict[str, Any], rule: str, reason: str, cwd: str | None) -> str:
    """한 줄 — 무엇을 대상으로. 못 알아보면 명령 앞부분."""
    if tool == "AskUserQuestion":
        qs = [q for q in (inp.get("questions") or []) if isinstance(q, dict)]
        first = qs[0].get("question") or qs[0].get("header") or "" if qs else ""
        return (f"질문 {len(qs)}개 — " if len(qs) > 1 else "질문 — ") + str(first)[:MAX - 12]
    if tool != "Bash":
        path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
        verb = {"Write": "쓰기", "Edit": "고치기", "MultiEdit": "고치기", "NotebookEdit": "고치기",
                "Read": "읽기"}.get(tool, tool)
        if isinstance(path, str) and path:
            p = path if os.path.isabs(path) else os.path.join(cwd or "/", path)
            kind = "비밀 파일" if rule == "민감한-경로" else ("안전 규칙 · 설정 파일" if rule == "보호-설정파일" else
                                                         ("기존 파일" if os.path.exists(p) else "새 파일"))
            return f"{verb} → {p} ({kind})"[:MAX]
        return f"{tool} — {reason}"[:MAX]
    full = str(inp.get("command") or "")
    # heredoc 본문은 대상을 뽑지 않는다(11-03 — 파이썬 f"rm … {SP}/shots"를 셸 명령으로 읽어 "frm (변수…)"가 나왔다).
    # 검사(approval.py)는 본문까지 하지만, 요약은 셸 명령 줄만 본다. 걸린 게 본문 안이면 "해석기 스크립트 안"이라고만 적는다
    from bridge.approval import HEREDOC
    bodies = [(m.group("line").strip(), m.group("body")) for m in HEREDOC.finditer(full)]
    cmd = HEREDOC.sub(lambda m: m.group("line") + " <<HEREDOC", full)
    if rule in ("민감한-경로", "보호-설정파일"):
        m = re.search(r"\(([^()]*)\)\s*$", reason)
        if m:
            head, _, tok = m.group(1).partition(" ")
            verb = "쓰기" if rule == "보호-설정파일" or head in ("cp", "mv", "tee") else ("내보내기" if head in ("curl", "wget", "scp", "rsync") else "읽기")
            what = tok or head
            if what and not os.path.isabs(what) and not what.startswith("~"):
                what = os.path.normpath(os.path.join(cwd or "/", what))
            return f"{verb}({head}) → {what} ({'비밀 파일' if rule == '민감한-경로' else '안전 규칙 · 설정 파일'})"[:MAX]
    for fn in (_db, lambda c: _rm(c, cwd), _kubectl, _docker, _git):
        try:
            s = fn(cmd)
        except Exception:  # noqa: BLE001 — 요약 실패가 승인을 막으면 안 된다
            s = None
        if s:
            return s[:MAX]
    if bodies:
        head = bodies[0][0] or "heredoc"
        interp = re.search(r"\b(python3?|bash|sh|node|perl|ruby|mysql|psql|kubectl|vagrant)\b", head)
        return (f"{rule} → {interp.group(1) if interp else 'heredoc'} 스크립트 안에서 걸림 "
                f"(본문 {len(bodies[0][1].splitlines())}줄 — 대상은 본문을 직접 본다)")[:MAX]
    m = re.search(r"\(([^()]{3,})\)\s*$", reason)
    if m:
        return f"{rule} → {m.group(1)}"[:MAX]
    first = next((x.strip() for x in SEG.split(cmd) if x.strip() and not x.strip().startswith("cd ")), cmd.strip())
    return f"{rule} → {first}"[:MAX]
