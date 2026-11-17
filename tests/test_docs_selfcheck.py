"""FOREMAN 저장소 자체의 문서 점검(11-17 문서 도구 합치기 3단계 뒤, 사용자 결정).

`tools/docs.py check`와 같은 판정(bridge/doctext/check.py)을 이 저장소 작업 트리에 돌린다.
틀린 것이 하나라도 있으면 깨지고, 의심은 실패시키지 않는다. 카드 한 줄은 보이게만 할 뿐이라
아무도 안 보면 문서가 조용히 낡는다. 깨지게 만드는 것은 시험뿐이다.
작업 트리 판(rev 없음)이라 아직 커밋 안 한 새 원고도 본다. 다른 저장소는 점검하지 않는다.
"""

from pathlib import Path

from bridge import docrefs
from bridge.doctext import check as ck
from bridge.doctext import config as dcfg

ROOT = Path(__file__).resolve().parent.parent
SHOW = 8


def test_foreman_docs_check_has_no_errors():
    repo = str(ROOT)
    cfg = dcfg.load(repo)
    sets = docrefs.resolve_sets(repo, cfg)
    res = ck.run(repo, None, cfg, sets)
    assert res["sets"], "점검할 문서 묶음을 하나도 읽지 못했습니다(설정이나 폴더를 확인하세요)"
    errs = res["errors"]
    lines = []
    for e in errs[:SHOW]:
        where = f"{e['doc']}:{e['line']}" if e["doc"] and e["line"] else (e["doc"] or "저장소 전체")
        lines.append(f"  {where}: {e['what']}")
    more = f"\n  ... 외 {len(errs) - SHOW}개" if len(errs) > SHOW else ""
    assert not errs, (f"문서 점검에서 틀린 것 {len(errs)}개(전체는 `.venv/bin/python tools/docs.py check`):\n"
                      + "\n".join(lines) + more)
