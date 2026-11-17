"""문서 문법 묶음(11-17 사용자 결정: 문서 도구를 FOREMAN 한 곳으로 합치기, 1단계).

원고, 포트폴리오, docs를 읽는 문법을 여기 한 곳에서만 정한다. 정규식과 파서를 다른 모듈에 다시 쓰지 않는다.

- `lines`   코드 울타리와 HTML 주석 가르기(walk, text_lines, comments)
- `marks`   근거 표시 `[c:]` `[t:]` `[log:]` `[docs:]` `[code:]`와 경로 뒤 `:줄` `:줄-줄`
- `head`    머리 주석 「다루는 곳」 「읽은 커밋」
- `titles`  편 제목(첫 # 줄), 번호 뗀 제목, 편 사이 참조 `→ 「제목」`
- `config`  저장소마다 다른 것 `.foreman/docs.toml`(뼈대)

쓰는 곳: 근거 확인기(bridge/evidence.py), 게시기(bridge/notion.py), 거꾸로 찾기(bridge/docrefs.py),
원고 셈(bridge/manuscript.py), 명령 tools/docs.py. 표준 라이브러리만 쓴다(다른 저장소에서 FOREMAN 명령으로 부를 수 있게).
"""

from bridge.doctext.head import COVERS, READ, bad_covers, head_text, parse_head, strip_comments
from bridge.doctext.lines import comments, text_lines, walk
from bridge.doctext.marks import CODE_MARK, KINDS, MARK, STRIP, STRIP_TURN, mark_file, mark_re, marks, split_range, target
from bridge.doctext.titles import XREF, bare_title, first_h1, xref_index, xref_lookup

__all__ = ["CODE_MARK", "COVERS", "KINDS", "MARK", "READ", "STRIP", "STRIP_TURN", "XREF", "bad_covers", "bare_title",
           "comments", "first_h1", "head_text", "mark_file", "mark_re", "marks", "parse_head", "split_range",
           "strip_comments", "target", "text_lines", "walk", "xref_index", "xref_lookup"]
