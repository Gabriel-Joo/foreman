"""거꾸로 찾기 명령(11-17). `tools/docs.py refs`와 같은 결과를 내는 껍데기(11-17 문서 도구 합치기 2단계).

코더 첫 글(`bridge/docrefs.py` `prompt_block`)과 합치기 카드 안내가 이 이름을 쓰므로 남겨 둔다. 판정은 `bridge/docrefs.py` 한 곳.
읽기만 한다. 아무것도 고치지 않는다.

    .venv/bin/python tools/docrefs.py bridge/mergeprep.py                 # 이 파일을 가리키는 문서
    .venv/bin/python tools/docrefs.py bridge/transcript/ bridge/x.py:10-40 # 폴더, 줄 범위
    .venv/bin/python tools/docrefs.py --range main...HEAD                 # 이 브랜치가 바꾼 코드로, 고침 / 안 고침까지
    .venv/bin/python tools/docrefs.py --range a1b2c3d..HEAD --unfixed     # 안 고친 문서만
    .venv/bin/python tools/docrefs.py --repo <다른 저장소> --range origin/main~20..origin/main --brief
    .venv/bin/python tools/docrefs.py --range main...HEAD --json          # 기계가 읽을 때

종료 코드: 0(찾음, 없어도 0), 2(인자, git, 설정 문제).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent / "docs.py"


def to_docs_argv(argv: list[str] | None) -> list[str]:
    """이 명령의 인자를 `tools/docs.py [--repo] [--rev] [--json] refs ...`로 옮긴다."""
    ap = argparse.ArgumentParser(description="코드를 가리키는 문서를 거꾸로 찾는다(읽기만, tools/docs.py refs와 같다)")
    ap.add_argument("files", nargs="*", help="코드 파일(경로, 끝이 /인 폴더, 경로:시작-끝). docs 문서도 된다")
    ap.add_argument("--range", dest="rng", help="커밋 범위 A..B 또는 A...B(갈라진 곳부터). 바뀐 파일로 찾고 고침 / 안 고침을 보인다")
    ap.add_argument("--repo", default=".", help="저장소 경로(기본 지금 폴더). 다른 저장소도 읽기만 한다")
    ap.add_argument("--rev", help="범위 없이 찾을 때 문서를 읽을 커밋(기본 작업 트리)")
    ap.add_argument("--src", help="원고 폴더(기본: 그 저장소 .foreman/docs.toml, .foreman/notion.toml, FOREMAN config/notion.toml 차례)")
    ap.add_argument("--unfixed", action="store_true", help="안 고친 문서만")
    ap.add_argument("--brief", action="store_true", help="문서와 줄 번호만")
    ap.add_argument("--json", action="store_true", help="JSON으로")
    a = ap.parse_args(argv)
    if not a.files and not a.rng:
        ap.error("코드 파일이나 --range 중 하나는 주어야 합니다")
    out = ["--repo", a.repo, *(["--rev", a.rev] if a.rev else []), *(["--json"] if a.json else []), "refs"]
    out += [*(["--range", a.rng] if a.rng else []), *(["--src", a.src] if a.src else []),
            *(["--unfixed"] if a.unfixed else []), *(["--brief"] if a.brief else [])]
    return out + ["--", *a.files] if a.files else out


def main(argv: list[str] | None = None) -> int:
    docs_argv = to_docs_argv(argv)
    spec = importlib.util.spec_from_file_location("foreman_docs_tool", DOCS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(docs_argv)


if __name__ == "__main__":
    sys.exit(main())
