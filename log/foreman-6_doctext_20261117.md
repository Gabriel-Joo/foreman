# 문서 도구 합치기 1단계: 문법 묶음과 머리 주석 읽기 (foreman-6, 2026-11-17)

관리자 410 코더 일감. 사용자 결정(11-17): 문서 도구를 FOREMAN 한 곳으로 합친다. 차례는 1) 근거 표시와 머리 주석 읽기, 2) 거꾸로 찾기, 3) 문서 점검, 4) 원고 쓰는 기준 문서. 이번은 1단계만.

## 1. 한 일

- 문법 묶음 `bridge/doctext/`를 만들었다. 표준 라이브러리만 쓴다(다른 저장소가 FOREMAN 명령으로 부를 수 있게)
  - `lines.py` 코드 울타리와 HTML 주석 가르기(`walk`, `text_lines`, `comments`)
  - `marks.py` 근거 표시 종류, 정규식(`MARK`, `CODE_MARK`, `mark_re`), 노션 판에서 떼기(`STRIP`, `STRIP_TURN`), 값 나누기(`target`, `split_range`, `mark_file`)
  - `head.py` 머리 주석(`COVERS`, `READ`, `parse_head`, `strip_comments`, `head_text`, `bad_covers`)
  - `titles.py` 첫 `#` 줄(`first_h1`), 번호 뗀 제목(`bare_title`), 편 사이 참조(`XREF`, `xref_pattern`, `xref_index`, `xref_lookup`)
  - `config.py` `.foreman/docs.toml` 뼈대(읽기와 기본값만)
- FOREMAN 쪽 쓰는 곳을 모두 이 묶음으로 바꿨다(아래 표). 옛 이름(`manuscript.parse_head`, `notion.first_h1`, `notion.xref_index`, `evidence.MARK`)은 묶음 것을 다시 내보내 그대로 된다
- 명령 `tools/docs.py`(`head`, `marks`, `config`, `--repo`, `--rev`, `--json`)
- 시험 `tests/test_doctext.py`(20), `tests/test_docs_config.py`(14), `tests/test_docs_tool.py`(10)
- 고친 코드를 가리키는 문서: `docs/12_scribe.md` 「5.」(머리 주석 자리, 편 사이 참조 자리, 새 항목 「문서 문법 묶음」), `docs/11_worktree.md` 「8.」 표 줄과 「9.」 가리킴 줄, `docs/style_guide.md` 「1.」 노션 원고 줄, 원고 `notion/10_scribe/03_evidence.md`(다루는 곳에 `bridge/doctext/`, `tools/docs.py` 더함, 「게시기는 아직 자기 정규식에 종류를 따로 적어 둔다」 문단은 틀린 말이 되어 고침), `notion/10_scribe/04_notion.md`(다루는 곳에 `bridge/doctext/`), `notion/10_scribe/01_room.md`, `notion/01_structure.md` 모듈 표, `notion/14_screen/05_check.md`(화면 말 시험이 MARK를 가져오는 자리). 읽은 커밋은 바꾸지 않았다
  - `docs/style_guide.md`를 고쳐 합치기 카드가 사람에게 간다
  - 거꾸로 찾기 `--range main...HEAD --unfixed`에 남는 「안 고침」 17편은 걸린 파일(`scribe_room.py`, `docrefs.py`, `notion.py`, `docsync.py`, `tests/`)의 다른 기능(서기 일감, 코더 규칙 붙이기, 게시 흐름 등)을 다루는 문단이라 지금 코드와 맞아 그대로 두었다. `notion/16_tests.md` 87줄의 「근거 확인기의 정규식 한 곳에서 가져오게 했다」는 그때 한 일을 적은 과거 이야기라 그대로 두었다

## 2. 모은 문법과 옮긴 쓰는 곳

| 문법 | 전(따로 정한 곳) | 후 |
|---|---|---|
| 근거 표시 정규식 `[c\|t\|log\|docs\|code:값]` | `bridge/evidence.py` `MARK`, `bridge/notion.py` `EVIDENCE_STRIP`과 `_INLINE`의 ev 묶음(종류를 따로 적음), `bridge/docrefs.py` `MARK`(code만) | `doctext.marks` `MARK`, `STRIP`, `KINDS_RE`, `CODE_MARK`. 게시기 `_INLINE`은 `KINDS_RE`로 짠다 |
| 턴 표지 떼기 `[t:…]` | `notion.inline`, `notion.first_h1` 각자 글 | `doctext.marks.STRIP_TURN` |
| 값 나누기 `파일:줄-줄#절` | `evidence._file_problem` 정규식, `notion._runs`의 `re.split(r"[:#]")` 두 번, `docrefs.RANGE`와 `_split_range` | `doctext.marks.target`, `mark_file`, `split_range`, `RANGE` |
| 머리 주석 | `bridge/manuscript.py` `_comments`, `parse_head`, `strip_comments`, `head_text`, `bad_covers` | `doctext.head`(manuscript.py는 셈과 나무 차례만) |
| 울타리와 주석 가르기 | `manuscript._comments`, `notion.first_h1`, `evidence.check_text`(``` 뒤집기만), `docrefs.refs_in`, `docrefs._headings` 다섯 벌 | `doctext.lines.walk` 하나 |
| 첫 `#` 줄 | `bridge/notion.py` `first_h1`(manuscript, docsync는 notion에서 가져옴) | `doctext.titles.first_h1` |
| 번호 뗀 제목, 참조 색인과 찾기 | `notion.XREF_BARE`, `xref_index`, `Ctx.xref_url` 안 찾기 | `doctext.titles` `bare_title`, `xref_index`, `xref_lookup`. `Ctx.xref_url`은 경고와 pending만 |
| 참조 `→ 「제목」` 정규식 | `notion._INLINE` xref 묶음, `evidence.XREF`(느슨한 다른 꼴) | `doctext.titles.xref_pattern`, `XREF` |
| 머리 주석 꼴 가져오기 | `scribe_room._head_rule`, `docsync.status`, `notion.Publisher`, `docrefs`, `evidence`가 `bridge.manuscript`에서 | 모두 `bridge.doctext.head`에서. `scribe_room.py`는 가져오는 한 줄과 그 함수 설명 한 줄만 고쳤다 |
| 화면 말 시험의 근거 표시 이름 | `tests/screen_words.py`가 `bridge.evidence.MARK` | `bridge.doctext.marks.MARK` |

`bridge/notion.py` `md_to_blocks`의 코드 블록 규칙(`^(```|~~~)\s*언어\s*$`)은 Notion 블록 변환(언어 이름까지 읽는다)이라 묶음에 넣지 않았다. 원고 문법이 아니다.

`tests/test_doctext.py` `test_no_grammar_copies_left`가 `bridge/` 아래(묶음 밖)에 근거 표시, 머리 주석 칸, 번호 떼기, 참조 정규식 글이 다시 나오면 실패한다.

## 3. 동작이 바뀌었나

네 저장소(FOREMAN, 인프라, 런슈즈, 펫퍼민트)의 추적 `.md` 622개 모두에 대해 옮기기 전과 뒤의 출력을 떠서 견줬다: `parse_head`, `strip_comments`, `first_h1`, `docrefs.refs_in`, `docrefs._headings`, `evidence.check_text`(DB 없이), `notion.md_to_blocks`(원고 판과 아닌 판, 참조 색인 포함, 경고와 pending까지). **차이 0**. 스크립트는 scratchpad에만 두었다(저장소에 넣지 않음).

글을 다섯 벌이 서로 다르게 가르던 것을 하나로 모으면서, 위 622개에는 없는 모양에서만 판정이 바뀐다:

- 근거 확인기: 전에는 ``` 줄마다 뒤집기만 해서 `~~~` 울타리 안을 읽었고 닫는 울타리 길이를 보지 않았다. 이제 게시기, 머리 주석과 같은 규칙(``` 또는 ~~~, 같은 글자로 같은 길이 이상이 닫는다). HTML 주석 안의 ``` 줄이 울타리를 열지 않는다
- 근거 확인기의 「다른 글 안내는 주장이 아니다」: 전에는 `→\s*「[^」]*」`로 빈 제목, 백틱 든 제목까지 지웠다. 이제 게시기가 링크로 읽는 참조 꼴과 같다(한 줄, 비지 않음, 백틱 없음). 백틱 든 제목의 참조 줄에 숫자가 있으면 이제 의심으로 뜰 수 있다
- 거꾸로 찾기 `refs_in`: HTML 주석 안 ``` 줄이 울타리를 열지 않는다(전에는 열었다)
- 거꾸로 찾기 `_headings`(걸린 줄의 제목): HTML 주석 안 `#` 줄을 제목으로 세지 않고, 닫는 울타리는 같은 길이 이상이어야 한다

## 4. 인프라 스크립트와 다른 점(읽기만 했다)

`scripts/docs-check.py`
- 머리 주석: 파일 맨 앞 주석만(`re.match(r"\s*<!--…-->")`), 값 둘레 백틱을 떼지 않는다, 칸마다 목록. FOREMAN은 울타리 밖 첫 머리 주석(맨 앞이 아니어도), 백틱 뗌. 인프라 원고 41편은 모두 맨 앞이라 지금은 같은 값이 나온다(`tools/docs.py --repo <인프라> head`: 원고 29편, 포트폴리오 12편 모두 머리 주석 있음, 읽은 커밋 묶음마다 하나)
- 울타리와 주석(`body_lines`): ``` 뒤집기만(`~~~`, 길이 없음), 주석을 울타리보다 먼저 본다(울타리 안 `<!--`가 주석을 연다). 그리고 **울타리 안 근거 표시, 참조, 금지어도 검사한다**(울타리 표시는 CLAIM에만 쓴다). FOREMAN은 울타리 안을 읽지 않는다(원고의 꼴 예시를 코드 블록에 두는 까닭)
- 근거 표시: 정규식은 같다. `t`, `log`는 「이 저장소에서 쓰지 않는 종류」로 틀림. 값 끝 `#절`을 받지 않는다. 파일 있는지를 작업 트리가 아니라 읽은 커밋 트리로 본다. `code:폴더`를 끝 / 없이 써도 그 아래 파일이 있으면 받는다
- 다루는 곳: 읽은 커밋의 추적 파일과 맞댄다(폴더, fnmatchcase 글롭, 같은 경로). FOREMAN 근거 확인기는 작업 트리 경로가 있는지 본다
- 제목: `# `로 시작하는 첫 줄(울타리, 주석, YAML 안도), 백틱 `*` `[t:]`를 떼지 않는다. 원고는 번호 뗀 제목만 색인(번호째 쓴 참조는 못 찾는다), 포트폴리오는 그대로 제목만. `docs/NN_*.md`의 참조도 원고 제목 색인으로 찾는다(묶음을 건너간다. FOREMAN 게시기는 같은 묶음만). 그래서 `tools/docs.py --repo <인프라> marks`는 docs 쪽 참조 6개를 「편 없음」으로 보이고 docs-check는 0이다
- 참조 정규식 `→\s*「(?P<t>[^」]*)」`: 빈 제목, 백틱 든 제목도 받는다
- CLAIM `\d|“|”`(인용 「」와 "…" 없음), 참조를 지우지 않고, 20자 넘음 조건이 없다
- 읽은 커밋: 원고와 docs/NN은 모두 하나, 포트폴리오끼리 하나(`read_commit = "set"`)
- 금지어(IP, 도메인, 홈 경로, 토큰 꼴, 포트), 포트폴리오만 한 도메인 예외, 그림 파일 있는지

`scripts/docs_for_code.py`
- `_comments`, `parse_head`, `refs_in`, `_pathlike`가 FOREMAN 11-17 아침 판을 그대로 옮긴 것이다. 울타리 걷기는 FOREMAN의 옛 docrefs 꼴이라 위 3절의 「주석 안 ``` 줄」에서만 이제 갈린다
- `MARK`가 `code`와 `docs` 둘(FOREMAN docrefs는 code만). docs/ 아래 문서와 묶음 밖 `*.md`가 「문서 트리거」로 근거 표시와 다루는 곳으로만 걸린다
- `docs/history/`는 문서도 코드도 아니다. 원고 폴더 기본 `notion/`(FOREMAN은 설정이 없으면 원고 묶음 없음). 번호 짝(`docs/NN` → `notion/NN_*`)

## 5. `.foreman/docs.toml` 칸과 기본값

파일이 없으면 FOREMAN 지금 동작. 1단계에서는 읽기만 하고 어느 도구도 아직 이 값으로 판정하지 않는다. 인프라 저장소에 파일을 만들지 않았다(인프라 세션 몫).

| 칸 | 기본값(FOREMAN) | 인프라에 맞을 값 | 쓰는 단계 |
|---|---|---|---|
| `records` | `["log/"]`(docrefs `SKIP_CODE_DIRS`와 같다, 시험이 맞댄다) | `["docs/history/"]` | 2, 3 |
| `pair_numbers` | `false` | `true` | 2 |
| `read_commit` | `"piece"`(기준, 사용자 11-17) | 3단계 전환 동안만 `"set"`, 끝나면 지운다 | 3 |
| `allowed_domains` | `[]` | 포트폴리오의 그 도메인 | 3 |
| `not_code` | `[".md"]` | 같음 | 2 |
| `[sets] docs`, `notion`, `portfolio` | `"docs/"`, 없음(notion.toml `src`를 따른다), `"portfolio/"` | `notion = "notion/"` | 1(명령), 2 |

- 모르는 칸, 모르는 묶음은 경고(명령은 stderr). 깨진 TOML, 틀린 꼴은 기본값으로 떨어지지 않고 `DocsConfigError`(명령 종료 코드 2). 기록 폴더가 조용히 FOREMAN 기본값으로 돌면 그 저장소 기록이 코드로 세어진다
- TOML 함정: `[sets]` 표 뒤에 쓴 맨 위 칸은 표 안으로 들어간다. 견본(모듈 설명)은 표를 맨 뒤에 두고, 그렇게 들어간 칸은 「모르는 묶음 sets.records」 경고로 보인다(시험 있음)

## 6. 명령

```
.venv/bin/python tools/docs.py [--repo <저장소>] [--rev <커밋>] [--json] head [--set docs|notion|portfolio]
.venv/bin/python tools/docs.py [...] marks [문서 ...] [--set ...]
.venv/bin/python tools/docs.py [...] config
```

- 읽기만(git은 ls-files, ls-tree, cat-file, show, rev-parse). 작업 트리 또는 `--rev`
- 실패는 종료 코드 2와 까닭: 폴더 없음, git 저장소 아님, 없는 커밋, 깨진 docs.toml. 명령 파일만 FOREMAN 밖으로 옮겨 부르거나(파이썬 3.11 아래 포함) 묶음을 못 불러오면 2. 부르는 쪽 껍데기도 `|| true`로 덮지 말 것(2단계 인프라 껍데기에 적는다)
- 인프라에 돌려 본 것: 근거 표시와 참조 2,535개, `[docs:history/…:193-197]` 꼴 줄 범위가 나뉜다. 원고 참조는 번호 없이 써도 풀린다

## 7. 다음 단계(1단계를 하며 보인 것)

2단계(거꾸로 찾기)
- `docrefs`가 `docs.toml`을 쓰게: `records`(지금 `SKIP_CODE_DIRS` 고정), `not_code`, `[sets]`(지금 `DOCS_DIR`, `PORTFOLIO_DIR` 고정과 `manuscript_src`), `pair_numbers`
- 인프라처럼 `[docs:]` 근거 표시와 묶음 밖 `*.md`를 「문서 트리거」로(지금 FOREMAN은 code 표시만 본다)
- 저장소 읽기(`docrefs._tree`, `_read_many`)를 묶음으로 옮기고 `tools/docs.py refs`를 붙인다. 명령은 지금 이 둘을 docrefs에서 빌려 쓴다
- 인프라 `scripts/docs_for_code.py`를 FOREMAN 명령을 부르는 껍데기로(인프라 세션 몫, 들어내기는 그 세션 지시서가 끝난 뒤)

3단계(문서 점검)
- 정할 것: 머리 주석을 맨 앞만 볼지(인프라) 어디든 첫 것(FOREMAN), 울타리 안 근거 표시를 검사할지(인프라는 함, FOREMAN은 안 함. 원고 예시를 코드 블록에 두는 약속과 부딪친다), 근거 표시 종류를 저장소마다 막을지(인프라 `t`, `log`. 칸이 하나 더 필요하다), 참조를 묶음 건너 찾을지(인프라 docs → 원고. 칸이 하나 더 필요하다), 파일 있는지를 작업 트리로 볼지 읽은 커밋으로 볼지, CLAIM 꼴
- 금지어와 `allowed_domains`, 그림 파일 있는지, 다루는 곳이 읽은 커밋에 있는지, 범위(추적 파일이 어느 편 다루는 곳에 드는지)
- FOREMAN 원고에서 지금 못 푸는 참조 넷: `notion/10_scribe/04_notion.md`의 「제목」 둘(꼴 설명), 「승인 카드」, `notion/14_screen/05_check.md` 「Claude Code 창」. 게시기가 이미 경고로 알리는 것이고 서기 몫이다

사용자 답(11-17, 관리자 410을 거쳐 이 세션에 붙여 넣어짐). 3단계 지시문에 이 순서와 까닭을 옮긴다
- 근거 줄 번호: FOREMAN은 파일 단위 근거 그대로 두고 밀림은 서기실 셈으로 본다. 줄 단위 밀림 검사는 인프라에만 쓴다(지시 22 「줄 번호 붙이지 마라」 유지). 까닭은 줄 번호 유지비다. 인프라는 CLAUDE.md 한 줄에 근거 45곳이 밀렸고, FOREMAN은 근거 2,454개에 코드가 더 자주 바뀐다
- 「시험 파일만 바뀌어도 걸리는」 넓은 셈은 다루는 곳이 넓게 적힌 문제다. 3단계에서 시험 폴더를 통째로 다루는 곳에 넣은 편을 찾아 범위를 좁힌다. 시험 파일 자체를 셈에서 빼지 않는다(시험을 다루는 편은 걸리는 것이 맞다)
- 읽은 커밋은 편마다가 기준이다. `read_commit` 기본값은 `"piece"`(이 브랜치에서 그렇게 만들었다). 까닭: 묶음마다 하나 규칙 때문에 인프라가 한 편만 확인하고 44편의 읽은 커밋을 통째로 올려 「실제로 열어 본 커밋」이라는 뜻을 잃었다. 런슈즈, 펫퍼민트도 처음부터 편마다로 시작한다
- 인프라 전환은 지금 하지 않는다. 지금 `scripts/docs-check.py` 14줄이 묶음 하나를 요구하고 그 스크립트는 고장만 고치기로 묶여 있다. 3단계에서 점검을 FOREMAN으로 옮길 때 인프라 56편 머리를 편마다로 바꾸고 「묶음 하나」 요구를 설정으로 받는다. 전환하는 동안만 인프라 설정에 `read_commit = "set"`을 두고, 끝나면 기본값과 같게 지운다
- 주석의 줄표와 가운뎃점: 지금 규칙은 커밋 메시지와 화면 글에만 있다. 4단계 기준 문서에서 원고, docs, 주석까지 넓히고 새 줄을 보는 시험으로 건다. 그때까지는 기록만 한다

## 8. 시험

- 기준(바꾸기 전) `.venv/bin/python -m pytest -q`: 1241 통과
- 바꾼 뒤 `.venv/bin/python -m pytest -q`: 아래 「시험 결과」, `node --test tests/js/`: 아래
- 새 시험: `tests/test_doctext.py` 20(울타리와 주석, 근거 표시 다섯 종류와 인프라 줄 범위 꼴, 머리 주석 FOREMAN 꼴과 인프라 꼴, 첫 # 줄, 번호째 참조와 번호 없는 참조, 쓰는 곳이 모두 같은 정의를 쓰는지, 묶음 밖에 문법 글이 다시 나오지 않는지), `tests/test_docs_config.py` 14(기본값이 FOREMAN 동작과 같은지, 인프라 꼴, 표 뒤 칸 함정, 틀린 값 9가지, 커밋에서 읽기), `tests/test_docs_tool.py` 10(tmp 가짜 저장소 FOREMAN 꼴, 인프라 꼴, `--rev`, 읽기만 하는지, 실패 넷, FOREMAN 밖에서 부르기)

시험 결과: `.venv/bin/python -m pytest -q` 1285 통과(경고 1, 전부터 있던 것), `node --test tests/js/` 222 통과. 설정 시험을 따로 파일로 옮긴 뒤 새 시험 셋 44 통과, 원고를 한 편 더 고친 뒤 화면 말 시험과 원고 변환 시험 27 통과

## 9. 겹침

같은 시각 다른 코더가 `bridge/scribe_room.py` 포트폴리오 지시문 절을, 서기가 `notion/00_foreman.md`, `notion/15_db.md`, `portfolio/15_telegram.md`를 고친다. 이 브랜치는 `scribe_room.py`의 `_head_rule` 안 가져오기 한 줄과 설명 한 줄만 고쳤고(지시문 글은 그대로), 서기의 세 파일은 건드리지 않았다. 합칠 때 `_head_rule` 근처에서 겹치면 이 두 줄만 살리면 된다.

## 10. 규칙

규칙 위반 없음. 파일은 Edit, Write로만 고쳤다. 읽기만 하는 확인 하나(고친 원고의 근거 표시 확인)를 Bash에서 heredoc으로 넘긴 파이썬으로 돌렸다. 파일을 쓰지 않았다.
