"""근거 표시(11-06, `docs/12_scribe.md` 「4.」): 원고 문장 끝의 `[종류:값]`.

    [c:1a2b3c4]                 커밋
    [t:123]                     FOREMAN 턴(DB)
    [log:파일.md]               log/ 아래 파일
    [docs:파일.md:10-20]        docs/ 아래 파일, 줄 범위는 줄 하나(:10)나 범위(:10-20). 인프라는 [docs:history/x.md:193-197]
    [code:bridge/x.py]          저장소 맨 위 기준 코드 파일, 끝이 /면 폴더, 뒤에 :줄 :줄-줄
    [repo:CLAUDE.md]            저장소 맨 위 기준 문서(.md) 가운데 docs와 기록 폴더 밖의 것(CLAUDE.md, README.md, LICENSES.md,
                                .claude/agents/Explore.md). 뒤에 :줄 :줄-줄(11-20, log/foreman-6_root_mark_20261120.md)

값에는 공백과 `]`가 없다. 줄 범위 뒤 `#…`(절 이름)는 떼고 읽는다.

표시가 가리키는 저장소 경로는 `mark_target` 한 곳에서 푼다. 문서 점검, 근거 확인기, 거꾸로 찾기, 노션 판 글자가 모두 이것을 쓴다.
`[docs:X]`는 언제나 `docs/X`다. 맨 위 문서를 `[docs:]`로 풀지 않는 까닭: 런슈즈, 펫퍼민트, 인프라 모두 `docs/README.md`가 있어
`[docs:README.md]`가 저장소마다 다른 파일을 뜻하게 된다. `[code:]`가 문서(.md)를 가리키면 점검이 잡는다(`code_doc`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

KINDS = ("c", "t", "log", "docs", "code", "repo")
FILE_KINDS = ("log", "docs", "code", "repo")      # 값이 파일 경로인 종류
DOC_EXT = ".md"                                   # 「문서」의 판정. [code:]가 이것을 가리키면 틀림, [repo:]는 이것만


def mark_re(kinds: Iterable[str] = KINDS) -> re.Pattern[str]:
    """`[종류:값]`. 이름 붙은 묶음 k(종류), v(값)."""
    return re.compile(rf"\[(?P<k>{'|'.join(kinds)}):(?P<v>[^\]\s]+)\]")


MARK = mark_re()
CODE_MARK = mark_re(("code",))
REF_MARK = mark_re(("code", "docs", "repo"))                # 거꾸로 찾기가 따라가는 종류(c, t, log는 걸게 하는 파일을 가리키지 않는다)
KINDS_RE = "|".join(KINDS)                                  # 다른 정규식 안에 끼울 때(bridge/notion.py 줄 안 꾸밈)
STRIP = re.compile(rf"\s*\[(?:{KINDS_RE}):[^\]\s]+\]")      # 노션 판에서 떼는 근거 표시(앞 공백까지)
STRIP_TURN = re.compile(r"\s*\[t:[^\]\s]+\]")               # 턴 표지만(원고가 아닌 글, 제목 줄)

# 값 = 파일(:줄(-줄))(#절). 파일에는 : # 이 없다
TARGET = re.compile(r"^(?P<f>[^:#]+?)(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?(?:#.*)?$")
# 경로:줄(-줄). 백틱 안 경로, 명령 인자, [code:] 값에 쓴다(파일에 :가 있어도 마지막 :줄만 뗀다)
RANGE = re.compile(r"^(?P<p>.+?):(?P<a>\d+)(?:-(?P<b>\d+))?$")


def target(v: str) -> tuple[str, int | None, int | None] | None:
    """근거 표시 값 → (파일, 시작 줄, 끝 줄). 줄이 하나면 끝 줄은 None, 줄이 없으면 둘 다 None. 모양이 틀리면 None."""
    m = TARGET.match(v)
    if not m:
        return None
    return m["f"], int(m["a"]) if m["a"] else None, int(m["b"]) if m["b"] else None


def mark_target(kind: str, v: str, docs_dir: str = "docs/", log_dir: str = "log/") -> tuple[str, int | None, int | None] | None:
    """파일 종류 근거 표시 → (저장소 맨 위 기준 경로, 시작 줄, 끝 줄). code, repo는 값 그대로, docs는 docs_dir, log는 log_dir 아래.
    파일 종류가 아니거나 모양이 틀리면 None. 표시를 경로로 푸는 곳은 모두 이 함수를 쓴다(같은 표시가 곳마다 다르게 풀리지 않게)."""
    if kind not in FILE_KINDS:
        return None
    t = target(v)
    if not t:
        return None
    name, a, b = t
    base = {"docs": docs_dir, "log": log_dir}.get(kind, "")
    return base + name, a, b


def mark_path(kind: str, v: str, docs_dir: str = "docs/", log_dir: str = "log/") -> str | None:
    """`mark_target`의 경로만."""
    t = mark_target(kind, v, docs_dir, log_dir)
    return t[0] if t else None


def code_doc(kind: str, v: str) -> bool:
    """`[code:]`가 문서(.md)를 가리킨다. 문서는 `[repo:]`(docs 폴더 안이면 `[docs:]`)로 쓴다."""
    p = mark_path(kind, v) if kind == "code" else None
    return bool(p and p.endswith(DOC_EXT))


def repo_problem(v: str, docs_dir: str = "docs/", log_dir: str = "log/") -> str | None:
    """`[repo:]` 값이 한 벌 약속을 어긴 까닭. 같은 파일을 두 꼴로 가리키지 않게 코드와 docs, 기록 폴더 파일은 받지 않는다."""
    p = mark_path("repo", v)
    if not p:
        return None
    if not p.endswith(DOC_EXT):
        return f"문서(.md)가 아닙니다. 코드는 [code:{p}]로 씁니다"
    for k, d in (("docs", docs_dir), ("log", log_dir)):
        if d and p.startswith(d):
            return f"{d} 아래 파일은 [{k}:{p[len(d):]}]로 씁니다"
    return None


def split_range(tok: str) -> tuple[str, tuple[int, int] | None]:
    """`경로:10-20` → (경로, (10, 20)), `경로:10` → (경로, (10, 10)), 줄이 없으면 (tok, None)."""
    m = RANGE.match(tok)
    if not m:
        return tok, None
    a = int(m["a"])
    return m["p"], (a, int(m["b"] or a))


def mark_file(v: str) -> str:
    """값의 파일 부분(줄 범위, 절을 뗀 것). 노션 판이 글자로 보일 때."""
    return re.split(r"[:#]", v)[0]


def marks(line: str, kinds: Iterable[str] | None = None) -> Iterator[tuple[str, str, re.Match[str]]]:
    """한 줄의 근거 표시 (종류, 값, 맞은 것)."""
    rx = MARK if kinds is None else mark_re(kinds)
    for m in rx.finditer(line):
        yield m["k"], m["v"], m
