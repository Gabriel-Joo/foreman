"""저장소마다 다른 문서 규칙: `<저장소>/.foreman/docs.toml`(11-17 문서 도구 합치기 1단계, 뼈대).

파일이 없으면 FOREMAN 지금 동작이 기본값이다. 거꾸로 찾기(2단계, bridge/docrefs.py)와 문서 점검(3단계, bridge/doctext/check.py)이 이 값을 쓴다.

    records = ["log/"]          # 기록 폴더. 문서 묶음에도 코드에도 넣지 않는다(인프라는 ["docs/history/"])
    pair_numbers = false        # docs/NN_*.md가 바뀌면 같은 번호 원고 notion/NN_*도 걸기(인프라만 true)
    read_commit = "piece"       # 읽은 커밋을 편마다 따로("piece", FOREMAN) 또는 묶음마다 하나("set", 인프라)
    allowed_domains = []        # 원고 금지어(도메인)에서 빼는 도메인
    not_code = [".md"]          # 바뀌어도 코드로 세지 않는 확장자, 파일 경로, 글롭(문서 묶음 폴더 아래 파일은 확장자와 상관없이 코드가 아니다)

    [sets]                      # 문서 묶음 폴더(끝이 /). 표는 맨 위 칸들 뒤에 둔다(뒤에 쓴 칸은 TOML에서 이 표 안으로 들어간다)
    docs = "docs/"
    notion = "notion/"          # 원고 폴더. 없으면 .foreman/notion.toml 또는 FOREMAN config/notion.toml의 src를 따른다
    portfolio = "portfolio/"

    [check]                     # 문서 점검(tools/docs.py check, 3단계). 값은 FOREMAN 기본, 괄호는 인프라 값
    sets = ["notion", "portfolio"]        # 머리 주석과 근거를 보는 묶음(["notion", "portfolio", "docs"])
    numbered_only = []                    # 이 묶음은 바로 아래 NN_*.md만 본다(["docs", "portfolio"])
    head_at = "first"                     # 머리 주석: 울타리 밖 첫 주석("first") 또는 파일 맨 앞 주석만("top")
    fenced = false                        # 코드 울타리 안의 근거 표시, 참조, 금지어도 본다(true)
    kinds = ["c", "t", "log", "docs", "code"]   # 쓸 수 있는 근거 종류(["c", "docs", "code"])
    xref = {}                             # 묶음 건너 참조: 그 묶음의 참조를 다른 묶음 제목으로 찾는다({ docs = "notion" })
    files_at = "worktree"                 # 근거와 다루는 곳의 파일이 있는지 보는 판: 작업 트리 또는 읽은 커밋("read")
    claim = '\\d|“|”|"[^"]{4,}"|「[^」]{2,}」'   # 근거가 있어야 할 줄(의심)의 꼴('\\d|“|”')
    claim_min = 21                        # 의심으로 셀 줄의 가장 짧은 글자 수(0)
    banned = []                           # 금지어(IP, 도메인, 홈 경로, 토큰 꼴, 포트)를 보는 묶음(["notion", "portfolio"])
    domains_in = ["portfolio"]            # allowed_domains를 받는 묶음
    cover_by = ["notion"]                 # 덮기 검사: 문서 묶음과 기록 밖 추적 파일은 이 묶음 어느 편의 다루는 곳에 들어야 한다
    dashdot_base = "648ac08…"             # 새 줄 em dash와 가운뎃점 검사의 기준 커밋(4단계). 없으면 검사하지 않고 점검 결과에 알린다

모르는 칸은 경고로 알리고 쓰지 않는다. 깨진 파일이나 틀린 값은 기본값으로 떨어지지 않고 DocsConfigError로 멈춘다
(조용히 FOREMAN 기본값으로 돌면 다른 저장소의 기록 폴더가 코드로 세어지는 것처럼 틀린 결과가 알림 없이 나온다).
"""

from __future__ import annotations

import fnmatch
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

PATH = ".foreman/docs.toml"
SET_NAMES = ("docs", "notion", "portfolio")
READ_COMMIT = ("piece", "set")
HEAD_AT = ("first", "top")
FILES_AT = ("worktree", "read")
FOREMAN_CLAIM = r"\d|“|”|\"[^\"]{4,}\"|「[^」]{2,}」"      # bridge/evidence.py가 11-06부터 쓰던 꼴


class DocsConfigError(ValueError):
    pass


@dataclass
class CheckConfig:
    """문서 점검 칸(`[check]`). 기본값은 FOREMAN 지금 동작(근거 확인기 bridge/evidence.py와 게시기)."""
    sets: list[str] = field(default_factory=lambda: ["notion", "portfolio"])
    numbered_only: list[str] = field(default_factory=list)
    head_at: str = "first"
    fenced: bool = False
    kinds: list[str] = field(default_factory=lambda: ["c", "t", "log", "docs", "code"])
    xref: dict[str, str] = field(default_factory=dict)
    files_at: str = "worktree"
    claim: str = FOREMAN_CLAIM
    claim_min: int = 21
    banned: list[str] = field(default_factory=list)
    domains_in: list[str] = field(default_factory=lambda: ["portfolio"])
    cover_by: list[str] = field(default_factory=lambda: ["notion"])
    dashdot_base: str | None = None       # 기본값 없음: 저장소마다 넣는 때의 main이 다르다(`bridge/doctext/dashdot.py`)

    def as_dict(self) -> dict[str, Any]:
        return {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in self.__dict__.items()}


def _set_list(v: Any, where: str) -> list[str]:
    out = _strs(v, where) if v != [] else []
    bad = [x for x in out if x not in SET_NAMES]
    if bad:
        raise DocsConfigError(f"{where}: 묶음 이름은 {', '.join(SET_NAMES)}만 됩니다: {bad}")
    return out


def _check(raw: Any, source: str, warnings: list[str]) -> CheckConfig:
    import re
    from bridge.doctext.marks import KINDS
    if not isinstance(raw, dict):
        raise DocsConfigError(f"{source}: check는 표([check])여야 합니다")
    c = CheckConfig()
    for k, v in raw.items():
        where = f"{source}: check.{k}"
        if k in ("sets", "numbered_only", "banned", "domains_in", "cover_by"):
            setattr(c, k, _set_list(v, where))
        elif k == "head_at" or k == "files_at":
            allowed = HEAD_AT if k == "head_at" else FILES_AT
            if v not in allowed:
                raise DocsConfigError(f"{where}는 {' 또는 '.join(allowed)}여야 합니다: {v!r}")
            setattr(c, k, v)
        elif k == "fenced":
            if not isinstance(v, bool):
                raise DocsConfigError(f"{where}는 true 또는 false여야 합니다")
            c.fenced = v
        elif k == "kinds":
            ks = _strs(v, where)
            if [x for x in ks if x not in KINDS]:
                raise DocsConfigError(f"{where}: 근거 종류는 {', '.join(KINDS)}만 됩니다: {ks}")
            c.kinds = ks
        elif k == "xref":
            if not isinstance(v, dict) or any(a not in SET_NAMES or b not in SET_NAMES for a, b in v.items()):
                raise DocsConfigError(f"{where}는 {{묶음 = \"찾을 묶음\"}} 표여야 합니다: {v!r}")
            c.xref = dict(v)
        elif k == "claim":
            if not isinstance(v, str) or not v:
                raise DocsConfigError(f"{where}: 정규식 글이어야 합니다: {v!r}")
            try:
                re.compile(v)
            except re.error as e:
                raise DocsConfigError(f"{where}: 정규식이 아닙니다: {v!r} ({e})") from e
            c.claim = v
        elif k == "claim_min":
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise DocsConfigError(f"{where}는 0 이상 정수여야 합니다: {v!r}")
            c.claim_min = v
        elif k == "dashdot_base":
            if not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{7,40}", v):
                raise DocsConfigError(f"{where}는 커밋 해시(소문자 16진수 7~40자)여야 합니다: {v!r}")
            c.dashdot_base = v
        else:
            warnings.append(f"{source}: 모르는 칸 check.{k}는 쓰지 않습니다")
    return c


@dataclass
class DocsConfig:
    sets: dict[str, str | None] = field(default_factory=lambda: {"docs": "docs/", "notion": None, "portfolio": "portfolio/"})
    records: list[str] = field(default_factory=lambda: ["log/"])
    pair_numbers: bool = False
    read_commit: str = "piece"
    allowed_domains: list[str] = field(default_factory=list)
    not_code: list[str] = field(default_factory=lambda: [".md"])
    check: CheckConfig = field(default_factory=CheckConfig)
    source: str = "default"                 # "default" 또는 읽은 파일(`.foreman/docs.toml`, rev가 있으면 `rev:.foreman/docs.toml`)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"sets": dict(self.sets), "records": list(self.records), "pair_numbers": self.pair_numbers,
                "read_commit": self.read_commit, "allowed_domains": list(self.allowed_domains),
                "not_code": list(self.not_code), "check": self.check.as_dict(),
                "source": self.source, "warnings": list(self.warnings)}


def _folder(v: Any, where: str) -> str:
    if not isinstance(v, str) or not v.endswith("/") or v.startswith("/") or ".." in PurePosixPath(v).parts or v == "/":
        raise DocsConfigError(f"{where}: 저장소 안 폴더(끝이 /)여야 합니다: {v!r}")
    return v


def _strs(v: Any, where: str) -> list[str]:
    if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
        raise DocsConfigError(f"{where}: 글자 목록이어야 합니다: {v!r}")
    return list(v)


def parse(text: str, source: str = PATH) -> DocsConfig:
    """docs.toml 글 → DocsConfig. 없는 칸은 기본값."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise DocsConfigError(f"{source}를 읽지 못했습니다: {e}") from e
    cfg = DocsConfig(source=source)
    known = {"sets", "records", "pair_numbers", "read_commit", "allowed_domains", "not_code", "check"}
    for k in raw:
        if k not in known:
            cfg.warnings.append(f"{source}: 모르는 칸 {k}는 쓰지 않습니다")
    if "check" in raw:
        cfg.check = _check(raw["check"], source, cfg.warnings)
    if "sets" in raw:
        sets = raw["sets"]
        if not isinstance(sets, dict):
            raise DocsConfigError(f"{source}: sets는 표([sets])여야 합니다")
        for k, v in sets.items():
            if k not in SET_NAMES:
                cfg.warnings.append(f"{source}: 모르는 묶음 sets.{k}는 쓰지 않습니다({', '.join(SET_NAMES)}만)")
                continue
            cfg.sets[k] = _folder(v, f"sets.{k}")
    if "records" in raw:
        cfg.records = [_folder(v, "records") for v in _strs(raw["records"], "records")]
    if "pair_numbers" in raw:
        if not isinstance(raw["pair_numbers"], bool):
            raise DocsConfigError(f"{source}: pair_numbers는 true 또는 false여야 합니다")
        cfg.pair_numbers = raw["pair_numbers"]
    if "read_commit" in raw:
        if raw["read_commit"] not in READ_COMMIT:
            raise DocsConfigError(f"{source}: read_commit은 {' 또는 '.join(READ_COMMIT)}여야 합니다: {raw['read_commit']!r}")
        cfg.read_commit = raw["read_commit"]
    if "allowed_domains" in raw:
        cfg.allowed_domains = [d.lower() for d in _strs(raw["allowed_domains"], "allowed_domains")]
    if "not_code" in raw:
        pats = _strs(raw["not_code"], "not_code")
        bad = [e for e in pats if not _not_code_ok(e)]
        if bad:
            raise DocsConfigError(f"{source}: not_code는 .으로 시작하는 확장자나 저장소 안 파일 경로, 글롭이어야 합니다: {bad}")
        cfg.not_code = pats
    return cfg


def _is_ext(p: str) -> bool:
    return p.startswith(".") and "/" not in p and not any(ch in p for ch in "*?[")


def _not_code_ok(p: str) -> bool:
    if _is_ext(p):
        return True
    return ("/" in p or any(ch in p for ch in "*?[")) and not p.startswith("/") and ".." not in PurePosixPath(p).parts


def not_code_match(path: str, patterns: list[str]) -> bool:
    """`not_code` 칸에 드는 파일인가. `.`으로 시작하고 `/`가 없는 값은 확장자(끝 글자, 파일 이름 `.gitignore`도 같은 꼴),
    그 밖은 저장소 맨 위 기준 경로나 글롭(`bridge/__init__.py`, `bridge/*/__init__.py`)이다. 글롭의 `*`는 `/`도 넘는다."""
    return any(path.endswith(p) if _is_ext(p) else fnmatch.fnmatchcase(path, p) for p in patterns)


def load(repo: str | Path, rev: str | None = None) -> DocsConfig:
    """그 저장소의 docs.toml. rev가 없으면 작업 트리, 있으면 그 커밋의 파일(읽기만). 없으면 기본값(source "default")."""
    if rev is None:
        p = Path(repo) / PATH
        if not p.is_file():
            return DocsConfig()
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as e:
            raise DocsConfigError(f"{PATH}를 읽지 못했습니다: {e}") from e
        return parse(text, PATH)
    r = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{PATH}"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        exists = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
                                capture_output=True, text=True, timeout=15)
        if exists.returncode != 0:
            raise DocsConfigError(f"커밋 {rev}을 찾지 못했습니다")
        return DocsConfig()
    return parse(r.stdout, f"{rev}:{PATH}")
