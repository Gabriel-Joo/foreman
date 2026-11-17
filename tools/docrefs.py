"""거꾸로 찾기 명령(11-17). 코드 파일이나 커밋 범위를 주면 그 코드를 가리키는 docs, 노션 원고, 포트폴리오와 줄을 보인다.

읽기만 한다. 아무것도 고치지 않는다. 판정은 `bridge/docrefs.py` 한 곳(합치기 카드와 같다).

    .venv/bin/python tools/docrefs.py bridge/mergeprep.py                 # 이 파일을 가리키는 문서
    .venv/bin/python tools/docrefs.py bridge/transcript/ bridge/x.py:10-40 # 폴더, 줄 범위
    .venv/bin/python tools/docrefs.py --range main...HEAD                 # 이 브랜치가 바꾼 코드로, 고침 / 안 고침까지
    .venv/bin/python tools/docrefs.py --range a1b2c3d..HEAD --unfixed     # 안 고친 문서만
    .venv/bin/python tools/docrefs.py --repo <다른 저장소> --range origin/main~20..origin/main --brief
    .venv/bin/python tools/docrefs.py --range main...HEAD --json          # 기계가 읽을 때

종료 코드: 0(찾음, 없어도 0), 2(인자나 git 문제).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.docrefs import DocrefsError, scan  # noqa: E402

KIND_KO = {"docs": "docs", "notion": "노션 원고", "portfolio": "포트폴리오"}
HOW_KO = {"mark": "근거 표시", "path": "경로", "name": "파일 이름", "covers": "다루는 곳"}


def fixed_ko(v: bool | None) -> str:
    return "고침" if v is True else "안 고침" if v is False else "모름"


def render(res: dict, brief: bool = False, unfixed: bool = False) -> str:
    out = []
    head = f"걸리는 문서 {res['total']}"
    if res["range"]:
        head += f", 안 고침 {res['unfixed']} (범위 {res['range']}, 바뀐 코드 파일 {len(res['code'])}개)"
    else:
        head += f" (코드 파일 {len(res['code'])}개, 고쳤는지는 범위를 주어야 압니다)"
    out.append(head)
    for w in res.get("warnings") or []:
        out.append(f"⚠ {w}")
    for d in res["docs"]:
        if unfixed and d["fixed"] is not False:
            continue
        lines = sorted({h["line"] for h in d["hits"]})
        out.append(f"\n[{fixed_ko(d['fixed'])}] {d['doc']} ({KIND_KO.get(d['kind'], d['kind'])}) 줄 {', '.join(map(str, lines[:12]))}"
                   + (" …" if len(lines) > 12 else "") + f" ← {', '.join(d['files'])}")
        if brief:
            continue
        last = None
        for h in d["hits"]:
            key = (h["para_from"], h["code"])
            if key == last:
                continue
            last = key
            rng = f" 줄 {h['range'][0]}-{h['range'][1]}" + (" (바뀐 줄과 겹침)" if h["overlap"] else " (바뀐 줄과 안 겹침)"
                                                            if h["overlap"] is False else "") if h["range"] else ""
            out.append(f"  {h['line']}: 「{h['heading'] or '(제목 없음)'}」 {HOW_KO.get(h['how'], h['how'])} {h['ref']} → {h['code']}{rng}")
            if h["how"] != "covers":
                span = f"{h['para_from']}-{h['para_to']}" if h["para_to"] != h["para_from"] else str(h["para_from"])
                out.append(f"     ({span}) {h['para']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="코드를 가리키는 문서를 거꾸로 찾는다(읽기만)")
    ap.add_argument("files", nargs="*", help="코드 파일(경로, 끝이 /인 폴더, 경로:시작-끝)")
    ap.add_argument("--range", dest="rng", help="커밋 범위 A..B 또는 A...B(갈라진 곳부터). 바뀐 코드 파일로 찾고 고침 / 안 고침을 보인다")
    ap.add_argument("--repo", default=".", help="저장소 경로(기본 지금 폴더). 다른 저장소도 읽기만 한다")
    ap.add_argument("--rev", help="범위 없이 찾을 때 문서를 읽을 커밋(기본 작업 트리)")
    ap.add_argument("--src", help="원고 폴더(기본: 그 저장소 .foreman/notion.toml 또는 FOREMAN config/notion.toml의 src)")
    ap.add_argument("--unfixed", action="store_true", help="안 고친 문서만")
    ap.add_argument("--brief", action="store_true", help="문서와 줄 번호만")
    ap.add_argument("--json", action="store_true", help="JSON으로")
    a = ap.parse_args(argv)
    if not a.files and not a.rng:
        ap.error("코드 파일이나 --range 중 하나는 주어야 합니다")
    try:
        res = scan(a.repo, files=a.files or None, rng=a.rng, rev=a.rev, src=a.src)
    except DocrefsError as e:
        print(f"거꾸로 찾기 실패: {e}", file=sys.stderr)
        return 2
    if a.json:
        if a.unfixed:
            res = {**res, "docs": [d for d in res["docs"] if d["fixed"] is False]}
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(render(res, a.brief, a.unfixed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
