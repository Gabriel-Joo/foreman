"""세션마다 따로 작업하는 자리(git worktree, 11-05 · docs/00_design.md 3.4).

한 프로젝트에 세션이 이미 살아 있는데 하나를 더 띄우면, 기본으로 `<repo>/.worktrees/<이름>`(브랜치 `cc/<이름>`)에서 띄운다.
같은 파일을 둘이 덮어쓰거나 커밋이 섞이는 것을 막는다. 끝낼 때는 사람이 승인하면 main 위로 rebase한 뒤 fast-forward로 합친다.
충돌이 나면 rebase를 되돌리고 충돌 파일을 보여 준다(멈춤). 합친 뒤에는 worktree와 브랜치를 지운다.

- 폴더를 저장소 안에 두는 까닭: 조립기가 cwd 접두어로 프로젝트를 정하므로(`_project_for`) 그대로 같은 프로젝트의 캐릭터가 된다.
  CC 폴더 신뢰도 상위 폴더를 따른다
- 커밋 안 하는 것(.venv · .tools · .env*· node_modules)은 원본을 가리키는 링크로 둔다. `.git/info/exclude`(로컬 전용, 저장소 파일 아님)에
  `.worktrees/`와 링크 이름을 넣어 git이 보지 않게 한다
- CC 메모리 폴더는 작업 폴더 경로마다 따로 생긴다 — worktree 쪽 `memory`를 원본 메모리 폴더 링크로 만든다
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from bridge.approval import rule_files
from bridge.inject import Refused

WT_DIR = ".worktrees"
BRANCH_PREFIX = "cc/"
EXCLUDE = [f"/{WT_DIR}/", "/.venv", "/.tools", "/.env*", "node_modules"]   # 링크는 파일이라 `.venv/` 패턴에 안 걸린다
LINK_TOP = re.compile(r"^(\.venv|\.tools|\.env.*)$")                    # 저장소 맨 위에서 링크할 것(추적 안 되는 것만)
LINK_SUB = ("node_modules",)                                     # 한 단계 아래(frontend/node_modules 등)


async def git(cwd: str | Path, *args: str, check: bool = True) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec("git", "-C", str(cwd), *args, stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.STDOUT, env={**os.environ, "GIT_EDITOR": "true",
                                                                                   "GIT_TERMINAL_PROMPT": "0"})
    out, _ = await p.communicate()
    s = out.decode(errors="replace").strip()
    if check and p.returncode:
        raise Refused(f"git {' '.join(args[:2])} 실패: {s[-300:]}")
    return p.returncode or 0, s


def cc_project_dir(cwd: str | Path) -> Path:
    """CC가 그 폴더의 트랜스크립트 · 메모리를 두는 곳(handoff.transcript_path와 같은 규칙)."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(cwd))


def split(path: str | Path) -> tuple[str, str | None]:
    """폴더 → (저장소, worktree 이름 또는 None). `<repo>/.worktrees/<name>/…`이면 그 이름."""
    p = os.path.realpath(str(path))
    m = re.match(rf"^(.*?)/{re.escape(WT_DIR)}/([^/]+)(?:/|$)", p)
    return (m.group(1), m.group(2)) if m else (p, None)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:24] or "wt"


async def is_repo(path: str) -> bool:
    rc, out = await git(path, "rev-parse", "--show-toplevel", check=False)
    return rc == 0 and os.path.realpath(out) == os.path.realpath(path)


async def base_branch(repo: str) -> str:
    _, b = await git(repo, "branch", "--show-current")
    if not b:
        raise Refused("원본 저장소가 브랜치 위에 있지 않습니다(detached HEAD)")
    return b


async def create(repo: str, hint: str) -> dict[str, Any]:
    """새 worktree — 이름은 `<hint>`, 겹치면 -2, -3 …. 원본 브랜치의 지금 커밋에서 갈라진다."""
    repo = os.path.realpath(repo)
    if not await is_repo(repo):
        raise Refused(f"git 저장소의 맨 위 폴더가 아닙니다: {repo}")
    base = await base_branch(repo)
    _, branches = await git(repo, "branch", "--list", f"{BRANCH_PREFIX}*", "--format=%(refname:short)")
    taken = set(branches.split()) | {p.name for p in (Path(repo) / WT_DIR).glob("*")}
    name, n = slug(hint), 2
    while name in taken or BRANCH_PREFIX + name in taken:
        name, n = f"{slug(hint)}-{n}", n + 1
    path = Path(repo) / WT_DIR / name
    _exclude(repo)
    await git(repo, "worktree", "add", "-b", BRANCH_PREFIX + name, str(path), base)
    links = link_local(repo, str(path))
    mem = link_memory(repo, str(path))
    return {"name": name, "path": str(path), "branch": BRANCH_PREFIX + name, "base": base, "links": links, "memory": mem}


def _exclude(repo: str) -> None:
    f = Path(repo) / ".git" / "info" / "exclude"
    f.parent.mkdir(parents=True, exist_ok=True)
    have = f.read_text().splitlines() if f.exists() else []
    add = [x for x in EXCLUDE if x not in have]
    if add:
        with f.open("a") as fh:
            fh.write(("\n" if have and have[-1] else "") + "# FOREMAN worktree(11-05)\n" + "\n".join(add) + "\n")


def link_local(repo: str, wt: str) -> list[str]:
    """커밋 안 하는 것 — 원본을 가리키는 링크. 이미 있으면(추적되는 파일 등) 건드리지 않는다."""
    done = []
    cands = [p for p in Path(repo).iterdir() if LINK_TOP.match(p.name)]
    for sub in Path(repo).iterdir():
        if sub.is_dir() and not sub.name.startswith("."):
            cands += [sub / n for n in LINK_SUB if (sub / n).exists()]
    for src in cands:
        dst = Path(wt) / src.relative_to(repo)
        if dst.exists() or dst.is_symlink() or not dst.parent.is_dir():
            continue
        dst.symlink_to(src)
        done.append(str(src.relative_to(repo)))
    return done


def link_memory(repo: str, wt: str) -> str | None:
    """worktree 쪽 CC 프로젝트 폴더의 memory → 원본 저장소의 memory. 원본에 메모리가 없으면 만들지 않는다."""
    src = cc_project_dir(repo) / "memory"
    if not src.is_dir():
        return None
    d = cc_project_dir(wt)
    d.mkdir(parents=True, exist_ok=True)
    dst = d / "memory"
    if dst.is_symlink() or dst.exists():
        return str(dst)
    dst.symlink_to(src)
    return str(dst)


async def status(repo: str, name: str) -> dict[str, Any]:
    """합치기 전에 보는 것 — 갈라진 뒤 쌓인 커밋, 원본이 앞서간 커밋 수, 커밋 안 된 변경, 바뀐 파일."""
    path = Path(repo) / WT_DIR / name
    branch = BRANCH_PREFIX + name
    out: dict[str, Any] = {"name": name, "path": str(path), "branch": branch, "exists": path.is_dir()}
    if not path.is_dir():
        return out
    base = await base_branch(repo)
    _, ahead = await git(repo, "rev-list", "--count", f"{base}..{branch}")
    _, behind = await git(repo, "rev-list", "--count", f"{branch}..{base}")
    _, log = await git(repo, "log", "--format=%h %s", f"{base}..{branch}")
    _, dirty = await git(path, "status", "--porcelain")
    _, stat = await git(repo, "diff", "--stat", f"{base}...{branch}")
    out.update(base=base, ahead=int(ahead or 0), behind=int(behind or 0), commits=log.splitlines()[:30],
               dirty=[ln for ln in dirty.splitlines() if ln][:30], diffstat=stat.splitlines()[-12:])
    return out


async def in_base(repo: str, name: str) -> bool | None:
    """브랜치가 이미 원본 브랜치에 들어 있는가(11-11, 받은 할 일 #17 — 밖에서 `git merge --ff-only`로 합치면 FOREMAN이 몰랐다).
    갈라진 뒤 커밋이 없거나(`--is-ancestor`), 있어도 같은 변경이 원본에 이미 있으면(`git cherry`가 모두 `-` — rebase 뒤 합침) True.
    브랜치가 없으면 None(지워짐 — 합치거나 버린 뒤). 저장소를 못 읽으면 Refused — 「끝났다」고 말하지 않는다."""
    branch = BRANCH_PREFIX + name
    await git(repo, "rev-parse", "--git-dir")
    rc, _ = await git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    if rc:
        return None
    base = await base_branch(repo)
    rc, _ = await git(repo, "merge-base", "--is-ancestor", branch, base, check=False)
    if rc == 0:
        return True
    rc, out = await git(repo, "cherry", base, branch, check=False)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return rc == 0 and bool(lines) and all(ln.startswith("-") for ln in lines)


def _forbidden(wt_path: str, rel: str) -> bool:
    """쉬게 하기 커밋에 넣으면 안 되는 것 — 원본을 가리키는 링크(.venv · .tools · .env* · node_modules)와 worktree 밖을 가리키는 링크.
    .gitignore가 없는 저장소에서도 막는다(`.venv/` 패턴은 링크(파일)에 안 걸린다 — EXCLUDE 주석). 견본(.env*.example)은 넣는다."""
    top = rel.split("/", 1)[0]
    if "node_modules" in rel.split("/"):
        return True
    if top in (".venv", ".tools") or (top.startswith(".env") and not top.endswith(".example")):
        return True
    p = Path(wt_path) / rel
    if p.is_symlink():
        target = os.path.realpath(p)
        return not (target == os.path.realpath(wt_path) or target.startswith(os.path.realpath(wt_path) + os.sep))
    return False


async def save_progress(wt_path: str, message: str) -> dict[str, Any]:
    """[쉬게 하기](11-09) — 커밋 안 한 변경을 이 브랜치에 커밋한다. `git add -A`(.gitignore를 지킨다) 뒤 넣으면 안 되는 것(_forbidden)은
    빼고, 빠진 것은 결과에 적는다(조용히 넘어가지 않는다). 변경이 없으면 커밋하지 않는다. 실패는 Refused로 — 세션을 끝내기 전에 멈춘다."""
    _, dirty = await git(wt_path, "status", "--porcelain")
    if not dirty.strip():
        return {"commit": None, "files": 0, "skipped": []}
    await git(wt_path, "add", "-A")
    _, staged = await git(wt_path, "diff", "--cached", "--name-only", "-z")
    names = [n for n in staged.split("\0") if n]
    skipped = [n for n in names if _forbidden(wt_path, n)]
    if skipped:
        await git(wt_path, "reset", "-q", "--", *skipped)
    keep = [n for n in names if n not in skipped]
    if not keep:
        return {"commit": None, "files": 0, "skipped": skipped}
    rc, out = await git(wt_path, "commit", "-q", "-m", message, check=False)
    if rc:
        await git(wt_path, "reset", "-q", check=False)       # 올려 둔 것을 내린다 — 작업 트리는 그대로
        raise Refused(f"커밋하지 못했습니다: {out[-300:] or 'git commit 실패'}. 세션은 끝내지 않았습니다")
    _, h = await git(wt_path, "rev-parse", "--short", "HEAD")
    return {"commit": h, "files": len(keep), "skipped": skipped}


# squash로 합칠지 — 프로젝트마다(config/handoff.toml [merge_prep.per_project.<이름>] squash, 11-12). 합치기 준비(bridge/mergeprep.py)가
# 켜져 있으면 저장소 경로 → bool을 돌려주는 async 함수를 넣는다. 없으면(꺼짐 · 시험) 늘 지금 동작(rebase → ff).
# HandoffManager.worktree_act가 `merge(repo, name)`으로 부르므로(패널 [합치기] · 카드 승인 둘 다) 여기서 고른다.
SQUASH_OF: Any = None


# ── squash 커밋 제목(11-13 337) ──
# 첫 커밋 제목만 쓰면 `git log --oneline` · 빌드 알림 · Notion 짝처럼 제목 한 줄만 보는 곳에서 나머지 커밋이 안 보였다(사용자).
# 제목은 묶은 일 전체(사람이 넘긴 제목 > 세션 제목 > 「첫 제목 외 N건」)를, 그 저장소의 커밋 꼴로 말한다.
# 원래 커밋은 본문(날짜 · 해시 · 제목)과 숨은 ref(SQUASH_REF — 브랜치 · 태그 목록에 안 보이고 push되지 않는다)로 찾는다.
CONV_RE = re.compile(r"^([a-z]+)(\([^)]*\))?!?: (.+)$")
CONV_ORDER = ("feat", "fix", "perf", "refactor", "ops", "build", "ci", "test", "docs", "style", "chore", "revert")
CONV_DESC_MAX = 50          # 런슈즈 · 인프라 · 펫퍼민트 CLAUDE.md 「커밋 메시지」 — 설명 한 줄 50자 안, 마침표 없음
FREE_TITLE_MAX = 120
SQUASH_REF = "refs/foreman/squashed/"
_DECLARED_CONV = re.compile(r"`타입(\([^)]*\))?: 설명`")

# ── 커밋 글의 기호(11-13 사용자 결정) ──
# FOREMAN · 런슈즈 CLAUDE.md 「커밋 메시지」: em dash(—)와 가운뎃점(·)을 쓰지 않고, 화살표(→)로 문장을 대신하지 않고, 범위 표시
# `타입(범위):`를 쓰지 않는다. 세션 제목 · 원래 커밋 제목에는 이것들이 흔해서 그대로 두면 관리자가 커밋마다 다시 썼다.
# 바꾸기는 여기 한 곳에서만 한다(squash 제목 · 본문 목록 · 사람이 넘긴 제목 모두).
_SYMBOL_CHARS = "—·・→"                     # em dash, 가운뎃점(라틴 · 가타카나), 화살표. en dash(–)는 범위(1–3)라 두었다
_SYMBOL_RE = re.compile(rf"\s*[{_SYMBOL_CHARS}]\s*")
_COMMAS_RE = re.compile(r",(\s*,)+")
_CONV_PARTS = re.compile(r"^([a-z]+)(\([^)]*\))?(!?): (.*)$")


def plain(s: str | None) -> str:
    """글 한 줄의 em dash · 가운뎃점 · 화살표를 쉼표로 바꾼다. 빈칸을 하나로, 쉼표 앞 빈칸을 빼고, 겹친 쉼표를 하나로,
    앞뒤 쉼표와 끝 마침표를 뺀다. 예: 「A — B · C → D」 → 「A, B, C, D」, 「경험·후기」 → 「경험, 후기」, 「A, — B」 → 「A, B」."""
    s = " ".join((s or "").split())
    s = _SYMBOL_RE.sub(", ", s)
    s = _COMMAS_RE.sub(",", s)
    s = re.sub(r"\s+,", ",", s)
    return s.strip(" ,").rstrip(".").rstrip(" ,")


def plain_title(t: str | None) -> str:
    """커밋 제목 한 줄 — `타입(범위): 설명`이면 범위를 빼고(`!`는 둔다) 설명에 plain을, 아니면 전체에 plain을."""
    t = " ".join((t or "").split())
    m = _CONV_PARTS.match(t)
    return f"{m.group(1)}{m.group(3)}: {plain(m.group(4))}" if m else plain(t)


def _title_changes(t: str) -> str:
    """사람이 넘긴 제목을 plain_title이 어떻게 바꿨는지 — 결과 note에 쓴다(조용히 바꾸지 않게)."""
    said = []
    if any(c in t for c in _SYMBOL_CHARS):
        said.append("제목의 em dash · 가운뎃점 · 화살표를 쉼표로 바꿨습니다.")
    m = _CONV_PARTS.match(t.strip())
    if m and m.group(2):
        said.append(f"제목의 범위 표시 {m.group(2)}를 뺐습니다.")
    return " ".join(said)


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1].rstrip(" ,") + "…"


async def commit_style(repo: str, base: str) -> str:
    """그 저장소의 커밋 제목 꼴 — "conventional"(`타입: 설명`) 또는 "free"(FOREMAN처럼 한글 자유 꼴).
    저장소 맨 위 CLAUDE.md가 `타입: 설명`을 적었으면 conventional(규칙이 앞선다 — 펫퍼민트처럼 최근 커밋이 꼴 밖이어도).
    CLAUDE.md에 없으면 base 최근 제목 40개 중(합침 · Merge 빼고) 60% 넘게 `타입:` 꼴이면 conventional."""
    try:
        text = (Path(repo) / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if _DECLARED_CONV.search(text):
        return "conventional"
    _, out = await git(repo, "log", "-40", "--no-merges", "--format=%s", base, check=False)
    subs = [s for s in out.splitlines() if s and not s.startswith(("합침(", "Merge "))]
    conv = sum(1 for s in subs if CONV_RE.match(s))
    return "conventional" if len(subs) >= 5 and conv / len(subs) > 0.6 else "free"


def check_title(style: str, title: str) -> str:
    """사람 · 관리자가 넘긴 squash 제목을 그 저장소 꼴로 본다. 맞으면 앞뒤 빈칸만 뗀 제목, 아니면 Refused(아무것도 하기 전에).
    em dash · 가운뎃점 · 화살표 · 범위 표시는 거부하지 않는다 — 길이는 plain_title로 바꾼 뒤 모양으로 재고, 실제 바꾸기와
    「바꿨습니다」 note는 merge가 한다(여기서 바꿔 돌려주면 merge가 바뀐 줄 모른다 — handoff · mergeprep가 이 값을 그대로 넘긴다)."""
    t = (title or "").strip()
    if not t:
        raise Refused("제목이 비어 있습니다")
    if "\n" in t or "\r" in t:
        raise Refused("제목은 한 줄이어야 합니다. 원래 커밋 목록은 본문에 저절로 들어갑니다")
    p = plain_title(t)
    if style == "conventional":
        if not CONV_RE.match(t):
            raise Refused("이 저장소의 커밋 꼴은 `타입: 설명`입니다(예: feat: 챗봇 검색 색인). 제목이 그 꼴이 아닙니다")
        if t.endswith("."):
            raise Refused("이 저장소의 커밋 제목은 마침표로 끝내지 않습니다")
        m = CONV_RE.match(p)
        if not m:
            raise Refused("설명이 비어 있습니다. 기호를 쉼표로 바꾸고 나니 남는 글이 없습니다")
        if len(m.group(3)) > CONV_DESC_MAX:
            raise Refused(f"설명이 {len(m.group(3))}자입니다. 이 저장소는 {CONV_DESC_MAX}자 안입니다")
    elif len(p) > FREE_TITLE_MAX:
        raise Refused(f"제목이 {len(p)}자입니다. {FREE_TITLE_MAX}자 안으로 넘겨 주세요")
    return t


async def check_title_for(repo: str, base: str, title: str) -> str:
    return check_title(await commit_style(repo, base), title)


def squash_title(style: str, subjects: list[str], branch: str, topic: str | None = None, sid: int | None = None) -> str:
    """기계가 만드는 squash 제목. subjects = 원래 커밋 제목(오래된 차례), topic = 세션 제목(custom_title 우선 — 묶은 일 전체를 말한다).
    conventional(FOREMAN도 11-13부터): `타입: <세션 제목>`(타입은 원래 커밋 타입 중 가장 무거운 것, 없으면 chore, 설명 50자 안).
    커밋 수는 제목에 넣지 않고 본문 첫 문장에 쓴다(11-13 — 「— 커밋 N개」 꼬리가 em dash였다).
    free(CLAUDE.md에 꼴이 없고 최근 제목도 자유 꼴인 저장소): `합침(<브랜치>, 세션 N, 커밋 N개): <세션 제목>`.
    세션 제목 · 첫 제목의 em dash · 가운뎃점 · 화살표 · 범위 표시는 plain으로 바꾼다."""
    n = len(subjects)
    first = subjects[0] if subjects else branch
    if style == "conventional":
        types = [m.group(1) for s in subjects if (m := CONV_RE.match(s))]
        typ = min(types, key=lambda t: CONV_ORDER.index(t) if t in CONV_ORDER else len(CONV_ORDER)) if types else "chore"
        m = CONV_RE.match(" ".join((topic or "").split()))
        what, tail = plain(m.group(3) if m else topic), ""
        if not what:
            m = CONV_RE.match(first)
            what, tail = plain(m.group(3) if m else first), f" 외 {n - 1}건"
        return f"{typ}: {_cut(what, CONV_DESC_MAX - len(tail))}{tail}"
    who = branch + (f", 세션 {sid}" if sid else "")
    what = plain(topic) or f"{plain(first)} 외 {n - 1}건"
    return _cut(f"합침({who}, 커밋 {n}개): {what}", FREE_TITLE_MAX)


async def squash_message(repo: str, base: str, branch: str, *, topic: str | None = None, title: str | None = None,
                         sid: int | None = None, style: str | None = None) -> str:
    """squash 커밋 글 — 제목(위 squash_title, title을 넘기면 그것) + 원래 커밋들의 날짜 · 해시 · 제목을 오래된 차례로 + 원래 커밋 찾는 법.
    해시는 브랜치를 지우면 사라지므로 merge가 SQUASH_REF<끝 해시>를 남긴다(이 저장소에만). 원래 커밋의 Co-Authored-By 줄은
    겹치지 않게 끝에 모은다."""
    _, rows = await git(repo, "log", "--reverse", "--date=format:%Y-%m-%d %H:%M", "--format=%ad%x09%h%x09%s", f"{base}..{branch}")
    _, bodies = await git(repo, "log", "--format=%B", f"{base}..{branch}")
    _, tip = await git(repo, "rev-parse", branch)
    items = [ln.split("\t", 2) for ln in rows.splitlines() if ln.count("\t") >= 2]
    style = style or await commit_style(repo, base)
    head = title or squash_title(style, [s for _, _, s in items], branch, topic, sid)
    co: list[str] = []
    for ln in bodies.splitlines():
        if ln.strip().lower().startswith("co-authored-by:") and ln.strip() not in co:
            co.append(ln.strip())
    # 본문도 자연어 문장 · 기호 없이(11-13). 원래 커밋 목록은 찾기용으로 남기되(337) 각 제목에도 같은 바꾸기를 한다
    what = plain(topic)
    lead = (f"세션 {sid}의 일" if sid else "이 일" if what else "이 브랜치의 일") + (f"({what})" if what else "")
    about = f"{lead}을 커밋 {len(items)}개에서 하나로 묶었다. 작업한 브랜치는 {branch}이다."
    body = (about + "\n\n원래 커밋(오래된 차례):\n" + "\n".join(f"- {d} {h} {plain_title(s)}" for d, h, s in items)
            + f"\n\n원래 커밋 보기: git log {SQUASH_REF}{tip[:12]} (이 저장소에만 있고 push되지 않는다)")
    return head + "\n\n" + body + ("\n\n" + "\n".join(co) if co else "") + "\n"


async def merge(repo: str, name: str, squash: bool | None = None, *, title: str | None = None, topic: str | None = None,
                sid: int | None = None) -> dict[str, Any]:
    """rebase(worktree에서) → fast-forward(원본에서) → worktree · 브랜치 지우기. 충돌이면 rebase를 되돌리고 멈춘다.
    squash(11-12, 프로젝트마다 켬 — None이면 SQUASH_OF가 정한다): rebase까지 같고, 브랜치 트리로 커밋 하나를 만들어(`commit-tree`,
    부모 = 원본 브랜치 끝) 그것을 fast-forward한다 — 원본 작업 트리에서 `merge --squash`를 돌리지 않으니 실패 꼴(원본의 커밋 안 된
    변경과 겹침 등)이 ff와 같다. squash 뒤 브랜치는 원본의 조상이 아니라 `-D`로 지운다(트리가 같은지 본 뒤에만).
    push는 하지 않는다(런슈즈는 push가 곧 배포 — 사람이 따로).
    squash 제목(11-13): title(사람 · 관리자가 넘긴 것 — 그 저장소 꼴이 아니면 아무것도 하기 전에 거부) > topic(세션 제목) > 기계.
    합친 뒤 SQUASH_REF<브랜치 끝 해시>를 브랜치 끝에 남겨 원래 커밋을 찾을 수 있게 한다. 넘긴 제목을 못 썼으면(squash가 아님) 결과에 적는다."""
    if squash is None:
        squash = bool(SQUASH_OF and await SQUASH_OF(repo))
    st = await status(repo, name)
    if not st["exists"]:
        raise Refused("작업방이 없습니다")
    if st["dirty"]:
        raise Refused(f"커밋 안 된 변경이 {len(st['dirty'])}개 있습니다. 그 세션에서 커밋하거나 버린 뒤 합쳐 주세요")
    path, base, branch = st["path"], st["base"], st["branch"]
    style = await commit_style(repo, base)
    changed = ""
    if title is not None:
        title = check_title(style, title)
        changed, title = _title_changes(title), plain_title(title)     # 기호 · 범위 표시를 바꾸고 그렇다고 알린다
    unused ="" if title is None else " 넘긴 제목은 쓰지 않았습니다(squash로 묶지 않아 원래 커밋이 그대로 들어갔습니다)."
    if st["ahead"] == 0:
        await remove(repo, name, force=False)
        return {"ok": True, "merged": 0, "note": "합칠 커밋이 없어 작업방만 지웠습니다."}
    if st["behind"]:
        rc, out = await git(path, "rebase", base, check=False)
        if rc:
            _, files = await git(path, "diff", "--name-only", "--diff-filter=U", check=False)
            await git(path, "rebase", "--abort", check=False)
            return {"ok": False, "conflict": files.splitlines(), "detail": out[-800:],
                    "note": "rebase 중 충돌이 나서 되돌렸습니다. 충돌 파일을 그 세션에서 풀어 커밋한 뒤 다시 합쳐 주세요."}
    _, dirty_main = await git(repo, "status", "--porcelain", "--untracked-files=no")
    rules, rules_err = await rule_changes(repo, base, branch)
    rnote = _rule_note(rules, rules_err)
    target, sq = branch, None
    if squash and st["ahead"] >= 2:                      # 커밋 하나는 묶을 것이 없다 — 그대로 ff
        _, tree = await git(repo, "rev-parse", f"{branch}^{{tree}}")
        _, parent = await git(repo, "rev-parse", base)
        rc, _ = await git(repo, "merge-base", "--is-ancestor", parent, branch, check=False)
        if rc:
            return {"ok": False, "conflict": [], "detail": "",
                    "note": f"rebase 뒤에도 {base} 끝이 브랜치의 조상이 아닙니다({base}가 그 사이 움직였을 수 있습니다). 다시 합쳐 주세요."}
        msg = await squash_message(repo, base, branch, topic=topic, title=title, sid=sid, style=style)
        _, tip = await git(repo, "rev-parse", branch)
        _, sq = await git(repo, "commit-tree", tree, "-p", parent, "-m", msg)
        target = sq
    rc, out = await git(repo, "merge", "--ff-only", target, check=False)
    if rc:
        return {"ok": False, "conflict": [], "detail": out[-800:],
                "note": "원본 저장소에서 fast-forward가 되지 않았습니다(원본의 커밋 안 된 변경과 겹칠 수 있습니다)."
                        + (f" 원본에 커밋 안 된 파일 {len(dirty_main.splitlines())}개." if dirty_main else "")}
    if sq:
        # 원래 커밋을 남긴다 — 브랜치를 지우면 해시만 남고 커밋은 gc로 사라지므로. 못 남기면 결과에 적는다(조용히 잃지 않게)
        ref = SQUASH_REF + tip[:12]
        rrc, rout = await git(repo, "update-ref", "-m", f"foreman squash {sq[:12]}", ref, tip, check=False)
        kept = (f" 원래 커밋은 `git log {ref}`로 봅니다." if rrc == 0
                else f" 원래 커밋 ref({ref})를 남기지 못했습니다: {rout[-200:]}. 본문의 제목 · 날짜만 남습니다.")
        # 원본 끝 트리 = 브랜치 트리일 때만 브랜치를 -D로 지운다. 아니면 브랜치를 남기고 그렇다고 알린다(조용히 잃지 않게)
        rc, _ = await git(repo, "diff", "--quiet", base, branch, check=False)
        await remove(repo, name, force=False, drop_branch=rc == 0)
        head = msg.split("\n", 1)[0]
        return {"ok": True, "merged": st["ahead"], "commits": st["commits"], "squash": sq[:12], "into": sq[:12], "title": head,
                "orig_ref": ref if rrc == 0 else None, "rule_files": rules,
                "note": f"{base}에 커밋 {st['ahead']}개를 커밋 하나({sq[:8]} 「{head}」)로 묶어 합쳤습니다(squash, 본문에 원래 날짜 · 해시 · 제목)."
                        + kept + ("" if rc == 0 else f" 트리가 달라 브랜치 {branch}는 지우지 않고 남겼습니다.")
                        + (f" {changed}" if changed else "") + " push는 하지 않았습니다." + rnote}
    # 11-14 화면 갈래 — 합친 뒤 원본 끝 커밋(rebase로 해시가 바뀌었을 수 있다)과 그 제목. 카드가 push 여부를 이 해시로 본다
    _, into = await git(repo, "rev-parse", base, check=False)
    _, into_title = await git(repo, "log", "-1", "--format=%s", base, check=False)
    await remove(repo, name, force=False)
    return {"ok": True, "merged": st["ahead"], "commits": st["commits"], "into": (into or "")[:12] or None, "title": into_title or None,
            "rule_files": rules, "note": f"{base}에 커밋 {st['ahead']}개를 합쳤습니다." + unused + " push는 하지 않았습니다." + rnote}


async def rule_changes(repo: str, base: str, branch: str) -> tuple[list[str], str | None]:
    """이 합치기가 바꾸는 안전 규칙 · 게이트 파일(11-15, config/approval.toml [sensitive] protect). 합치기를 막지는 않는다 —
    결과 · 카드 · 🛡 알림에 「규칙 파일이 바뀝니다」로 보인다. 확인을 못 했으면 (빈 목록, 까닭) — 조용히 「없음」으로 두지 않는다."""
    try:
        _, names = await git(repo, "diff", "--name-only", f"{base}...{branch}")
        return rule_files(repo, names.splitlines()), None
    except Exception as e:  # noqa: BLE001
        return [], f"규칙 파일이 바뀌는지 확인하지 못했습니다({type(e).__name__})"


def _rule_note(rules: list[str], err: str | None) -> str:
    if err:
        return f" {err}."
    if not rules:
        return ""
    return f" 🛡 규칙 파일이 바뀝니다({', '.join(rules[:5])}{' …' if len(rules) > 5 else ''}). 브리지를 다시 띄우면 반영됩니다."


async def remove(repo: str, name: str, force: bool, drop_branch: bool | None = None) -> None:
    """worktree와 브랜치를 지운다. drop_branch=True면 worktree는 그대로(--force 없이) 지우고 브랜치만 `-D`(squash 뒤 — 원본의 조상이
    아니라 `-d`가 거부한다). None이면 force를 따른다."""
    path = Path(repo) / WT_DIR / name
    if path.is_dir():
        await git(repo, "worktree", "remove", *(["--force"] if force else []), str(path))
    await git(repo, "worktree", "prune", check=False)
    hard = force if drop_branch is None else drop_branch
    await git(repo, "branch", "-D" if hard else "-d", BRANCH_PREFIX + name, check=False)
