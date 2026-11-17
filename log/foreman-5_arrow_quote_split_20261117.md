# 화살표 뒤 「」 가르기 (서기, 관리자 410 일감, 11-17)

점검기와 게시기는 화살표 뒤 「제목」을 편 사이 참조로 읽는다. 화면 글이나 메뉴 길을 화살표 뒤 「」로 옮긴 줄이 "그 제목을 가진 편이 없습니다" 틀림으로 걸릴 수 있어 도구를 바꾸지 않고 문법을 갈랐다.

## 한 일

1. `docs/manuscript_rules.md` 1절에 두 줄을 더했다(1절은 서기 둘과 코더가 모두 지시문으로 받는다).
   - 화살표(`→`) 뒤의 「」는 편 사이 참조다. 같은 묶음 편의 제목이어야 하고 없으면 점검이 틀림으로 센다
   - 화살표 뒤에 화면 글이나 사람 말을 그대로 옮길 때는 " "를 쓴다
2. `bridge/manuscript_rules.py`는 1절 맨 위 글머리 줄을 그대로 지시문에 넣으므로 코드는 고치지 않았다. 시험 `tests/test_manuscript_rules.py`에 `test_arrow_quote_rule_reaches_every_prompt`를 더해 기술문서 서기, 포트폴리오 서기, 코더 지시문이 두 줄을 받는지 본다.
3. 저장소의 `docs/`, `notion/`, `portfolio/`, `README.md`를 찾았다. 방법: 추적하는 `*.md`에서 코드 울타리와 백틱 안을 빼고, 도구와 같은 꼴(`bridge/doctext/titles.py` `XREF`)로 화살표 뒤 「」를 모두 뽑아 `xref_lookup`으로 같은 묶음 편 제목과 맞댔다. 제목을 못 찾은 것만 화면 글 후보로 봤다. 화살표와 「」 사이에 백틱이 낀 꼴(`→ \`docs/operations.md\` 「5. …」`)은 도구가 참조로 읽지 않아 대상이 아니다. 제목을 찾은 참조는 모두 진짜 편 사이 참조로 두었다.

## 바꾼 줄 (6곳, 5줄)

| 파일 | 줄 | 전 | 후 |
|---|---|---|---|
| `docs/10_office_design.md` | 171 | `claude-opus-5-5` → 「Opus 5.5」 | → "Opus 5.5" |
| `docs/10_office_design.md` | 172 | `claude-sonnet-5-5` → 「Sonnet 5.5」 | → "Sonnet 5.5" |
| `docs/10_office_design.md` | 172 | 옛 별칭 `opus` → 「Opus」 | → "Opus" |
| `docs/10_office_design.md` | 190 | 막대 → 「세션 정리」 탭 | → "세션 정리" 탭 |
| `docs/11_worktree.md` | 161 | [끝내기 ▾] → 「합치고 끝내기」 | → "합치고 끝내기" |
| `docs/12_scribe.md` | 181 | `docs/02_pipeline/` → 「02. 파이프라인 설계」 | → "02. 파이프라인 설계" |

`notion/`과 `portfolio/`에는 제목 없는 화살표 참조가 0건이었다(화면 글 후보 없음).

## 판단이 갈려 고치지 않은 줄

없음. 후보 6곳 모두 화면 글, 메뉴 길, 노션 페이지 이름, 모델 이름 표시였다.

## 시험

- `.venv/bin/python -m pytest -q`: 1391 passed
- `tools/docs.py check`: 틀린 것 0(의심 229는 전부터 있던 숫자와 인용 줄), 줄표와 가운뎃점 새 줄 0건

## 겹침

코더 546이 같은 시각 `docs/11_worktree.md`, `docs/12_scribe.md`를 고친다. 이 세션은 위 두 줄(161, 181)만 한 줄씩 고쳤다. 합칠 때 같은 줄이 겹치면 rebase로 풀면 된다(이 세션 쪽은 그 줄 안의 「」 두 개를 " "로 바꾼 것뿐이다).

## 하지 않은 것

- `bridge/doctext/`, `bridge/notion.py`, style_guide 4-1, CLAUDE.md, 화면 말 시험, 화살표 뒤가 아닌 「」 인용은 그대로 두었다.
- 런슈즈 1줄, 펫퍼민트 1줄은 그 저장소 관리자가 고친다(이 세션은 고치지 않았다).

규칙 위반 없음
