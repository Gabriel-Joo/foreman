# 맨 위 문서 근거 표시를 한 벌로, 문서를 가리키는 code 표시 잡기 (2026-11-20, foreman-6)

시작한 main 커밋: `a511e6f`(docs: 끝난 할 일 셋을 지우고 합친 결과를 적음). 관리자 410 코더 일감(사용자 결정 11-20).

## 1. 센 수

원고(`notion/`, `portfolio/`)와 docs에서 `code` 종류가 `.md`를 가리키는 곳. FOREMAN은 `git grep`(log 뺌), 다른 저장소는 main 판 `tools/docs.py --repo <저장소> marks`(그 저장소 점검 묶음 안)로 셌다. 다른 저장소는 읽기만 했다.

| 저장소 | code가 .md를 가리킴 | 맨 위 CLAUDE.md, README.md | 많이 가리키는 파일 |
|---|---|---|---|
| FOREMAN | 56곳(23편, 모두 notion/) | CLAUDE.md 49, README.md 0 | CLAUDE.md 49, LICENSES.md 6, .claude/agents/Explore.md 1 |
| 런슈즈 | 16곳(docs) | 0 | contract/README.md 16 |
| 펫퍼민트 | 282곳(docs, notion, portfolio) | 0 | KNOWN_ISSUES.md 112, data/review/*.md 나머지 |
| 인프라 | 329곳(docs, notion, portfolio) | CLAUDE.md 96 | CLAUDE.md 96, apps/*/README.md, apps/runshoes/runbooks/*.md |

- FOREMAN docs와 코드 주석에는 없다. 시험 두 곳(`tests/test_docrefs_config.py`)이 가짜 저장소 글에 `[code:CLAUDE.md]`, `[code:README.md]`를 썼다
- 다른 세 저장소 모두 `docs/README.md`가 있고, 런슈즈(`docs/HISTORY.md` 등), 펫퍼민트(`portfolio/10_docs.md` 등)가 그것을 `[docs:README.md]`로 가리킨다
- 셈의 차이: 점검 결과(아래 3절)의 수는 점검 묶음과 울타리 설정을 따르므로 위 표와 같다(런슈즈 16, 펫퍼민트 282, 인프라 329)

## 2. 고른 길: (나) 새 종류 `[repo:경로]`

맨 위 문서용 꼴을 따로 두었다. `[repo:CLAUDE.md]`, `[repo:LICENSES.md:3]`, `[repo:.claude/agents/Explore.md]`. 값은 저장소 맨 위 기준 경로이고 `.md`만 받는다.

까닭:
- (가) 「`docs/X`가 없으면 맨 위 X」는 다른 세 저장소에서 `[docs:README.md]`가 이미 `docs/README.md`를 뜻한다. 그 저장소에서는 맨 위 README를 docs 종류로 가리킬 길이 없고, FOREMAN(`docs/README.md` 없음)에서는 같은 표시가 맨 위를 뜻하게 되어 같은 표시가 저장소마다 다른 파일이 된다. 파일이 생기거나 지워지면 뜻이 바뀌는 것도 조용한 고장이다
- (가)의 「정해진 맨 위 문서만」도 README.md가 그 목록에 들면 같은 문제다
- 다른 저장소의 code 표시가 가리키는 문서는 맨 위가 아닌 것이 많다(`contract/README.md`, `apps/*/README.md`, `data/review/*.md`). repo를 「저장소 기준 문서 경로」로 두면 이것들도 한 꼴로 옮길 수 있다

한 벌 지키기:
- `[docs:X]`는 언제나 `docs/X`(묶음 폴더)다. 맨 위로 넘어가 풀지 않는다
- `[repo:]`가 `.md`가 아니면 틀림(「코드는 [code:…]로 씁니다」), docs 폴더나 기록 폴더 아래면 틀림(「docs/ 아래 파일은 [docs:…]로 씁니다」). 같은 파일을 두 꼴로 가리키지 않게. 새 종류라 옛 줄이 없어 언제나 틀림이다
- `[code:]`가 `.md`를 가리키면 점검 3번이 바꿀 꼴과 함께 잡는다(docs 폴더 안이면 `[docs:…]`, 밖이면 `[repo:…]`를 알려 준다)

판정 함수 하나: `bridge/doctext/marks.py` `mark_target(kind, v, docs_dir, log_dir)`(경로만은 `mark_path`). 쓰는 곳:
- 문서 점검과 근거 확인기: `check.mark_problem`(근거 확인기 `bridge/evidence.py`는 이것을 가져다 쓴다)
- 거꾸로 찾기: `docrefs.refs_in`. 맨 위 CLAUDE.md가 바뀌면 `[repo:CLAUDE.md]`를 단 편을 찾는다(시험)
- 노션 판 글자와 링크: `bridge/notion.py` `_runs`의 근거 표시 갈래 셋(code, log와 docs)을 `mark_path` 한 줄로 합쳤다. 떼기(`STRIP`)는 원래 `marks.KINDS`에서 만들어 새 종류도 저절로 떼진다
- `tools/docs.py marks`: 결과에 풀린 경로 `path` 칸을 더했다(`file` 칸은 값의 파일 부분 그대로, 시험이 기대하는 꼴이라 두었다). 사람이 읽는 출력은 `path`를 보인다
- 서기실 셈: `bridge/scribe_room.py`와 `bridge/manuscript.py`에는 근거 표시를 경로로 푸는 곳이 없다(`marks`를 가져다 쓰는 곳을 grep으로 찾아 본 결과). 원고 규칙 줄에서 표시를 떼는 `bridge/manuscript_rules.py`는 `STRIP`을 써서 저절로 repo도 뗀다. 따로 고칠 곳이 없었다

## 3. 문서를 가리키는 code 표시 잡기

「」 없는 참조 점검과 같은 길로 했다. 기준 커밋 칸 `[check] code_doc_base`를 새로 두고, 그 뒤 더하거나 고친 줄만 틀림, 옛 줄은 의심(`suspects`의 `code_doc`). 칸이 없으면 모두 의심으로 세고 `notes`에 수를 알린다. 결과 `code_doc`(`base`, `new`, `old`, `ran`), 출력 한 줄. 같은 기준 커밋이면 xref의 새 줄 셈을 다시 쓴다.

- FOREMAN `.foreman/docs.toml`에 `code_doc_base = a511e6f…`(이 검사가 들어오기 바로 전 main). 이 브랜치에서 56곳을 모두 바꿔 옛 줄도 0이다
- 근거 확인기(서기 합치기 카드)는 이 검사를 하지 않는다. 확인기는 기준 커밋 없이 글 전체를 보므로 다른 저장소의 옛 줄이 서기 카드마다 틀림으로 뜬다
- 다른 저장소 설정 `kinds = ["c", "docs", "code"]`는 고치지 않았다. 설정을 읽을 때 code가 있으면 repo를 함께 넣는다(repo는 code에서 문서를 떼어 낸 종류라서)
- 다른 저장소 점검(이 브랜치 도구로, 읽기만): 런슈즈 틀린 것 0(의심 281에서 297, 문서를 가리키는 code 16), 펫퍼민트 0(377에서 659, 282), 인프라 0(2에서 331, 329). 기준 커밋 칸이 없어 모두 의심이고 알림 한 줄이 뜬다

## 4. 원고 표시 바꾸기

notion 23편 56곳: `[code:CLAUDE.md…]` 49, `[code:LICENSES.md…]` 6, `[code:.claude/agents/Explore.md]` 1을 `[repo:…]`로. 글과 「읽은 커밋」은 그대로다. Edit의 모두 바꾸기로 표시 앞머리만 바꿨다.
- 줄표 검사의 옮긴 줄 풀이는 근거 표시를 떼고 맞대므로(`marks.STRIP`에 repo가 들어갔다) 표시만 바꾼 옛 줄은 새 줄로 세지 않는다(시험 `test_converted_line_is_not_new`)
- 다른 서기가 고치는 중인 `notion/09_dispatcher/02_note_wake.md`(2곳), `notion/10_scribe/01_room.md`(1곳), `notion/14_screen/05_check.md`(3곳)도 바꿨다. 같은 줄을 그쪽이 고치면 합칠 때 충돌할 수 있다

## 5. 문서

- `docs/manuscript_rules.md` 2절 「지금 상태를 쓴다… 근거는 문장 끝 근거 표시로만 단다」 줄 끝에 종류 셋의 쓰임을 더했다(코더, 서기 지시문에 들어가는 줄). 처음에 예시를 대괄호 꼴로 썼다가 그 문서의 근거 표시 시험(`tests/test_manuscript_rules.py`)이 진짜 표시로 읽어 깨져, 종류 이름으로 바꿨다. 6절 옮긴 줄 줄의 종류 목록에 repo를 더했다(근거 표시 줄, 동작이 바뀐 것). 다른 절은 건드리지 않았다. 사람 승인 문서라 합치기 카드가 사람에게 간다
- `docs/12_scribe.md` 「4.」에 repo 줄 하나, 「5.」 노션 판 떼는 목록과 `[check]` 칸(`kinds`, `code_doc_base`)
- `docs/style_guide.md` 근거 표시 줄 아래에 맨 위 문서 줄 하나
- `docs/11_worktree.md` 「9.」 가리킴 줄
- `notion/10_scribe/03_evidence.md`: 종류 다섯을 여섯으로, 표에 repo 줄, 맨 위 문서는 repo로 가리킨다는 문단(전에는 「code 종류로 가리켜야 한다」), 머리 주석 다루는 곳에 새 시험 파일, 「code 종류는 가장 늦게 붙었다」를 code와 repo 둘로 고침. 읽은 커밋은 올리지 않았다
- 거꾸로 찾기가 걸어 둔 다른 문서들(`notion/10_scribe/04_notion.md`, `notion/07_merge/01_card.md` 등)은 점검, 노션 게시 일반을 가리키는 문단이라 이번 변경과 어긋나지 않아 그대로 두었다

## 6. 시험

`tests/test_root_mark.py` 새로 11개: 종류마다 풀기, `[docs:CLAUDE.md]`는 `docs/CLAUDE.md`, code가 .md를 가리키는 판정, `STRIP`이 repo를 뗌, 점검에서 repo가 맨 위로 풀림과 줄 범위, repo 한 벌 약속, 옛 줄 의심과 새 줄 틀림(docs 폴더 안 문서는 `[docs:]`를 알려 줌), 표시만 바꾼 옛 줄은 줄표 새 줄이 아님, 기준 커밋 없음, 다른 저장소 kinds에 repo가 저절로 듦, 거꾸로 찾기가 맨 위 CLAUDE.md 변경으로 그 편을 찾음(줄 범위 겹침까지), 노션 판에서 떼짐과 링크 경로. 바꾼 옛 시험: KINDS 튜플, 인프라 kinds, 가짜 원고의 `[code:CLAUDE.md]`, `[code:README.md]`.

결과: `tools/docs.py check` 틀린 것 0(의심 209 그대로), pytest 1533 통과, node 250 통과.

## 7. 규칙 위반

규칙 위반 없음.

## 사람이 정할 것

1. 다른 세 저장소에 `code_doc_base`를 둘지와 옛 줄(런슈즈 16, 펫퍼민트 282, 인프라 329)을 repo로 바꿀지. 그 저장소 일이라 그쪽 관리자 몫이다. 지금은 모두 의심으로만 세고 알림 한 줄이 뜬다
2. 인프라 `apps/*/README.md`, 펫퍼민트 `data/review/*.md`처럼 맨 위가 아닌 문서도 repo로 옮길지(지금 repo는 받는다. 이름은 「맨 위 기준 경로」라는 뜻이다)
3. 합칠 때 main이 `a511e6f`보다 앞서 있고 그 사이 다른 브랜치가 `[code:CLAUDE.md]` 꼴 줄을 더했으면, 그 줄은 새 줄이라 점검 틀림이 된다(의도한 동작). 그때는 그 줄을 repo로 바꾸면 된다
