"""문서 도구 명령(11-17 문서 도구 합치기). 다른 저장소도 이 명령 하나를 부른다. 읽기만 한다. 아무것도 고치지 않는다.

    .venv/bin/python tools/docs.py head                       # 원고와 포트폴리오 편마다 제목, 다루는 곳, 읽은 커밋
    .venv/bin/python tools/docs.py head --set notion --json
    .venv/bin/python tools/docs.py marks notion/03_x.md       # 근거 표시와 편 사이 참조(줄, 종류, 파일, 줄 범위, 참조가 가리키는 편)
    .venv/bin/python tools/docs.py config                     # 그 저장소 .foreman/docs.toml을 읽은 값(없으면 기본값)
    .venv/bin/python tools/docs.py --repo <다른 저장소> head   # 다른 저장소를 읽기만 한다
    .venv/bin/python tools/docs.py --repo <다른 저장소> --rev origin/main marks

문법은 bridge/doctext 한 곳이다. 2단계에서 refs(거꾸로 찾기), 3단계에서 check(문서 점검)가 붙는다.

종료 코드: 0(읽음), 2(인자, 저장소, git, 설정 문제). FOREMAN 저장소 밖으로 이 파일만 옮겨 부르거나 파이썬이 3.11보다 낮으면
조용히 넘지 않고 2로 끝난다. 부르는 쪽도 이 명령이 없거나 실패한 것을 `|| true`로 덮지 않는다(조용한 고장이 된다).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from bridge.docrefs import DocrefsError, _read_many, _tree, manuscript_src
    from bridge.doctext import config as dcfg
    from bridge.doctext.head import parse_head
    from bridge.doctext.lines import text_lines
    from bridge.doctext.marks import marks, target
    from bridge.doctext.titles import XREF, first_h1, xref_index, xref_lookup
except ImportError as e:      # FOREMAN 밖으로 옮긴 파일, tomllib가 없는 옛 파이썬
    print(f"문서 도구를 불러오지 못했습니다(FOREMAN 저장소의 tools/docs.py를 FOREMAN .venv 파이썬으로 불러야 합니다): {e}",
          file=sys.stderr)
    sys.exit(2)

SET_KO = {"docs": "docs", "notion": "노션 원고", "portfolio": "포트폴리오"}


class Fail(Exception):
    pass


def repo_root(repo: str) -> str:
    p = Path(repo)
    if not p.is_dir():
        raise Fail(f"저장소 폴더가 없습니다: {repo}")
    r = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise Fail(f"git 저장소가 아닙니다: {repo}")
    return r.stdout.strip()


def resolve_sets(repo: str, cfg: dcfg.DocsConfig) -> dict[str, str]:
    """{묶음: 폴더}. 원고 폴더가 docs.toml에 없으면 notion.toml src(거꾸로 찾기와 같은 길). 원고 폴더가 없거나 docs와 같으면 뺀다."""
    sets = {k: v for k, v in cfg.sets.items() if v}
    if cfg.sets.get("notion") is None:
        src = manuscript_src(repo)
        if src:
            sets["notion"] = src
    if sets.get("notion") == sets.get("docs"):
        sets.pop("notion", None)
    return sets


def doc_files(repo: str, rev: str | None, sets: dict[str, str], records: list[str], only: list[str] | None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, d in sets.items():
        if only and k not in only:
            continue
        out[k] = [p for p in _tree(repo, rev, [d]) if p.endswith(".md") and not p.startswith(tuple(records))]
    return out


def cmd_head(repo: str, rev: str | None, cfg: dcfg.DocsConfig, sets: dict[str, str], only: list[str] | None) -> dict:
    res: dict = {"sets": {}}
    for k, paths in doc_files(repo, rev, sets, cfg.records, only).items():
        bodies = _read_many(repo, rev, paths)
        pieces = []
        for p in paths:
            body = bodies.get(p, "")
            h = parse_head(body)
            pieces.append({"path": p, "title": first_h1(body)[1], "head": h is not None,
                           "covers": (h or {}).get("covers", []), "read": (h or {}).get("read")})
        reads = sorted({x["read"] for x in pieces if x["read"]})
        res["sets"][k] = {"folder": sets[k], "pieces": pieces, "reads": reads,
                          "no_head": [x["path"] for x in pieces if not x["head"]]}
    return res


def cmd_marks(repo: str, rev: str | None, cfg: dcfg.DocsConfig, sets: dict[str, str], only: list[str] | None,
              files: list[str]) -> dict:
    by_set = doc_files(repo, rev, sets, cfg.records, only)
    want = set(files)
    out = []
    for k, paths in by_set.items():
        bodies = _read_many(repo, rev, paths)
        index = xref_index({p: first_h1(b)[1] for p, b in bodies.items()})
        for p in paths:
            if want and p not in want:
                continue
            for i, ln in text_lines(bodies.get(p, "").splitlines()):
                for kind, v, _ in marks(ln):
                    t = target(v) if kind != "c" and kind != "t" else None
                    out.append({"doc": p, "set": k, "line": i, "kind": kind, "value": v,
                                "file": t[0] if t else None, "from": t[1] if t else None, "to": (t[2] or t[1]) if t else None,
                                "shape_ok": t is not None or kind in ("c", "t")})
                for x in XREF.finditer(ln):
                    hits = xref_lookup(index, x["t"])
                    out.append({"doc": p, "set": k, "line": i, "kind": "xref", "value": x["t"], "file": None,
                                "from": None, "to": None, "refers": hits})
    missing = sorted(want - {p for ps in by_set.values() for p in ps})
    return {"marks": out, "not_in_sets": missing}


def render_head(res: dict) -> str:
    out = []
    for k, s in res["sets"].items():
        out.append(f"[{SET_KO.get(k, k)}] {s['folder']} 편 {len(s['pieces'])}, 머리 주석 없음 {len(s['no_head'])}, "
                   f"읽은 커밋 {len(s['reads'])}가지" + (f" ({', '.join(s['reads'])})" if s["reads"] else ""))
        for x in s["pieces"]:
            if x["head"]:
                out.append(f"  {x['path']} 「{x['title'] or '(제목 없음)'}」 읽은 커밋 {x['read'] or '(없음)'}, "
                           f"다루는 곳 {', '.join(x['covers']) or '(없음)'}")
            else:
                out.append(f"  {x['path']} 「{x['title'] or '(제목 없음)'}」 머리 주석 없음")
    return "\n".join(out)


def render_marks(res: dict) -> str:
    out = []
    for m in res["marks"]:
        if m["kind"] == "xref":
            r = m["refers"]
            where = r[0] if len(r) == 1 else "(그 제목을 가진 편 없음)" if not r else f"(겹침 {len(r)}: {', '.join(r)})"
            out.append(f"{m['doc']}:{m['line']} 참조 「{m['value']}」 → {where}")
        else:
            rng = f" 줄 {m['from']}" + (f"-{m['to']}" if m["to"] != m["from"] else "") if m.get("from") else ""
            bad = "" if m["shape_ok"] else " (모양을 알아보지 못함)"
            out.append(f"{m['doc']}:{m['line']} [{m['kind']}] {m['file'] or m['value']}{rng}{bad}")
    for p in res["not_in_sets"]:
        out.append(f"⚠ 문서 묶음 밖이라 읽지 않았습니다: {p}")
    out.append(f"근거 표시와 참조 {len(res['marks'])}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="문서 문법을 읽는 명령(읽기만)")
    ap.add_argument("--repo", default=".", help="저장소 경로(기본 지금 폴더). 다른 저장소도 읽기만 한다")
    ap.add_argument("--rev", help="읽을 커밋(기본 작업 트리)")
    ap.add_argument("--json", action="store_true", help="JSON으로")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("head", help="편마다 제목, 다루는 곳, 읽은 커밋")
    h.add_argument("--set", action="append", choices=list(SET_KO), help="이 묶음만(여러 번 줄 수 있다)")
    m = sub.add_parser("marks", help="근거 표시와 편 사이 참조")
    m.add_argument("files", nargs="*", help="이 문서만(저장소 맨 위 기준 경로)")
    m.add_argument("--set", action="append", choices=list(SET_KO), help="이 묶음만")
    sub.add_parser("config", help=".foreman/docs.toml을 읽은 값")
    a = ap.parse_args(argv)
    try:
        repo = repo_root(a.repo)
        cfg = dcfg.load(repo, a.rev)
        sets = resolve_sets(repo, cfg)
        if a.cmd == "config":
            res = {**cfg.as_dict(), "resolved_sets": sets}
            text = "\n".join([f"설정 {cfg.source}", *(f"  {k} = {json.dumps(v, ensure_ascii=False)}"
                                                      for k, v in cfg.as_dict().items() if k not in ("source", "warnings")),
                              f"  읽는 묶음 = {json.dumps(sets, ensure_ascii=False)}"])
        elif a.cmd == "head":
            res = cmd_head(repo, a.rev, cfg, sets, a.set)
            text = render_head(res)
        else:
            res = cmd_marks(repo, a.rev, cfg, sets, a.set, a.files)
            text = render_marks(res)
    except (Fail, DocrefsError, dcfg.DocsConfigError) as e:
        print(f"문서 도구 실패: {e}", file=sys.stderr)
        return 2
    for w in cfg.warnings:
        print(f"⚠ {w}", file=sys.stderr)
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
