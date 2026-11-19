"""원고 쓰는 기준 한 벌(11-17 문서 도구 합치기 4단계). `docs/manuscript_rules.md`의 1~5절 맨 위 글머리 줄을 읽어 지시문 줄을 만든다.

기준을 바꿀 때는 그 문서만 고친다. 서기 지시문 둘(`scribe_room.task_prompt` 기술문서, 포트폴리오)과 코더 규칙 절
(`docrefs.prompt_block`)이 이 모듈의 `block`을 부른다. 다른 저장소 세션도 FOREMAN 브리지가 띄우므로 같은 줄을 받는다.

문서를 읽지 못하거나 받을 절이 비면 조용히 빈 글을 내지 않는다. 지시문에 「원고 쓰는 기준을 읽지 못했습니다」와 문서 경로를
넣고 경고 로그를 남긴다(세션이 문서를 직접 읽게). 시험(`tests/test_manuscript_rules.py`)이 지금 문서가 읽히는지 본다.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bridge.doctext.marks import STRIP

log = logging.getLogger(__name__)

FOREMAN_ROOT = Path(__file__).resolve().parent.parent
REL = "docs/manuscript_rules.md"
PATH = FOREMAN_ROOT / REL

# 지시문 종류마다 받을 절. "3:1"은 3절 첫 줄만
KINDS: dict[str, tuple[str, ...]] = {
    "techdoc": ("1", "2", "4"),
    "portfolio": ("1", "2", "5"),
    "coder": ("1", "2", "3:1", "4:1", "5:1"),
    # 서기 「알려진 한계 쓰기」(later). 한계, 조건, 설계, 할 일을 가르는 줄과 한계 편의 꼴이 1, 2절에 있다
    "limit": ("1", "2"),
}
# 코더 줄 앞에 붙이는 말. 코더는 여러 문서 종류의 기준을 한 번에 받아 어느 문서 기준인지 보여야 한다(서기는 한 종류만 받아 붙이지 않는다)
LABEL = {"2": "기술문서 원고와 포트폴리오: ", "3": "docs: ", "4": "기술문서 원고: ", "5": "포트폴리오: "}
LABELED = ("coder",)

HEAD = re.compile(r"^## (\d+)\. ")
ITEM = re.compile(r"^- (.+)$")


class ManuscriptRulesError(RuntimeError):
    pass


def sections(text: str) -> dict[str, list[str]]:
    """절 번호 → 맨 위 글머리 줄(근거 표시를 뗀 글). 들여 쓴 줄과 글머리 아닌 줄은 넣지 않는다."""
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for line in text.splitlines():
        if (h := HEAD.match(line)):
            cur = h.group(1)
            out.setdefault(cur, [])
        elif line.startswith("## "):
            cur = None
        elif cur and (m := ITEM.match(line)):
            out[cur].append(STRIP.sub("", m.group(1)).rstrip())
    return out


def lines(kind: str, text: str | None = None) -> list[str]:
    """그 지시문 종류가 받을 기준 줄. 문서를 읽지 못하거나 받을 절이 비면 ManuscriptRulesError."""
    if kind not in KINDS:
        raise ValueError(kind)
    if text is None:
        try:
            text = PATH.read_text(encoding="utf-8")
        except OSError as e:
            raise ManuscriptRulesError(f"{REL}를 읽지 못했습니다({e.__class__.__name__})") from e
    secs = sections(text)
    out: list[str] = []
    for want in KINDS[kind]:
        num, _, first = want.partition(":")
        got = secs.get(num) or []
        if not got:
            raise ManuscriptRulesError(f"{REL} 「{num}.」 절에 글머리 줄이 없습니다")
        pre = LABEL.get(num, "") if kind in LABELED else ""
        out += [pre + x for x in (got[:1] if first else got)]
    return out


def doc_path(own: bool) -> str:
    """지시문에 적을 문서 경로. FOREMAN 저장소면 상대 경로, 다른 저장소면 FOREMAN 쪽 절대 경로."""
    return REL if own else str(PATH)


def block(kind: str, own: bool, title: str = "원고 쓰는 기준") -> str:
    """지시문에 넣을 절: 제목 줄, 출처 줄, 기준 줄. 읽지 못하면 그 까닭과 문서를 직접 읽으라는 줄."""
    where = doc_path(own)
    head = (f"{title}\n- 출처: `{where}`. 모든 저장소가 같은 한 벌이다. 이 저장소만 다른 것은 그 저장소 "
            "`docs/style_guide.md`에 있다")
    try:
        got = lines(kind)
    except ManuscriptRulesError as e:
        log.warning("manuscript rules: %s", e)
        return f"{head}\n- 원고 쓰는 기준을 읽지 못했습니다: {e}. `{where}`를 직접 읽고 따르고, 마지막 응답에 이 줄을 알린다"
    return head + "\n" + "\n".join(f"- {x}" for x in got)
