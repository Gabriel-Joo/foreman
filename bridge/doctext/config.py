"""저장소마다 다른 문서 규칙: `<저장소>/.foreman/docs.toml`(11-17 문서 도구 합치기 1단계, 뼈대).

파일이 없으면 FOREMAN 지금 동작이 기본값이다. 1단계는 읽기와 기본값만 있고, 거꾸로 찾기(2단계)와 문서 점검(3단계)이 이 값을 쓰기 시작한다.

    records = ["log/"]          # 기록 폴더. 문서 묶음에도 코드에도 넣지 않는다(인프라는 ["docs/history/"])
    pair_numbers = false        # docs/NN_*.md가 바뀌면 같은 번호 원고 notion/NN_*도 걸기(인프라만 true)
    read_commit = "piece"       # 읽은 커밋을 편마다 따로("piece", FOREMAN) 또는 묶음마다 하나("set", 인프라)
    allowed_domains = []        # 원고 금지어(도메인)에서 빼는 도메인
    not_code = [".md"]          # 바뀌어도 코드로 세지 않는 확장자(문서 묶음 폴더 아래 파일은 확장자와 상관없이 코드가 아니다)

    [sets]                      # 문서 묶음 폴더(끝이 /). 표는 맨 위 칸들 뒤에 둔다(뒤에 쓴 칸은 TOML에서 이 표 안으로 들어간다)
    docs = "docs/"
    notion = "notion/"          # 원고 폴더. 없으면 .foreman/notion.toml 또는 FOREMAN config/notion.toml의 src를 따른다
    portfolio = "portfolio/"

모르는 칸은 경고로 알리고 쓰지 않는다. 깨진 파일이나 틀린 값은 기본값으로 떨어지지 않고 DocsConfigError로 멈춘다
(조용히 FOREMAN 기본값으로 돌면 다른 저장소의 기록 폴더가 코드로 세어지는 것처럼 틀린 결과가 알림 없이 나온다).
"""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

PATH = ".foreman/docs.toml"
SET_NAMES = ("docs", "notion", "portfolio")
READ_COMMIT = ("piece", "set")


class DocsConfigError(ValueError):
    pass


@dataclass
class DocsConfig:
    sets: dict[str, str | None] = field(default_factory=lambda: {"docs": "docs/", "notion": None, "portfolio": "portfolio/"})
    records: list[str] = field(default_factory=lambda: ["log/"])
    pair_numbers: bool = False
    read_commit: str = "piece"
    allowed_domains: list[str] = field(default_factory=list)
    not_code: list[str] = field(default_factory=lambda: [".md"])
    source: str = "default"                 # "default" 또는 읽은 파일(`.foreman/docs.toml`, rev가 있으면 `rev:.foreman/docs.toml`)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"sets": dict(self.sets), "records": list(self.records), "pair_numbers": self.pair_numbers,
                "read_commit": self.read_commit, "allowed_domains": list(self.allowed_domains),
                "not_code": list(self.not_code), "source": self.source, "warnings": list(self.warnings)}


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
    known = {"sets", "records", "pair_numbers", "read_commit", "allowed_domains", "not_code"}
    for k in raw:
        if k not in known:
            cfg.warnings.append(f"{source}: 모르는 칸 {k}는 쓰지 않습니다")
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
        exts = _strs(raw["not_code"], "not_code")
        bad = [e for e in exts if not e.startswith(".") or "/" in e]
        if bad:
            raise DocsConfigError(f"{source}: not_code는 .으로 시작하는 확장자여야 합니다: {bad}")
        cfg.not_code = exts
    return cfg


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
