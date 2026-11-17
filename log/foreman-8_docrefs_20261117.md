# 문서가 밀리는 사슬 끊기: 거꾸로 찾기, 코더 지시문, 합치기 카드 (11-17, cc/foreman-8)

관리자 410의 코더 일감(사용자 지시 21). 상세 설계는 `docs/11_worktree.md` 「9.」, 카드는 「6-1.」.

## 1. 한 일

- 거꾸로 찾는 도구 `bridge/docrefs.py`(브리지 함수 `scan`) + 명령 `tools/docrefs.py`, 시험 `tests/test_docrefs.py`(tmp 가짜 저장소 11개)
- 코더 첫 글 끝에 규칙 절을 붙임(코더만), 교장 지시문 코더 줄, 역할 한 줄 설명
- 합치기 카드의 「정리 후보」를 거꾸로 찾기 결과 「걸리는 문서」로 바꿔 하나로 합침. 카드 위 줄, 「자세히」, 알림, 관리자 카드 글, 합친 뒤 글에 「걸리는 문서 N, 안 고침 M」
- 코더가 문서를 못 고치게 하던 약속을 풂(아래 4.)
- 첫 사례로 이 브랜치가 바꾼 코드를 가리키는 문서 가운데 내용이 틀어진 문단을 같은 브랜치에서 고침(아래 6.)

## 2. 도구와 사용법

읽기만 한다. git은 `ls-tree`, `ls-files`, `cat-file --batch`, `diff`, `merge-base`, `rev-parse`만 부른다(시험 `test_read_only`가 status, HEAD, stash가 그대로인지 본다).

```
.venv/bin/python tools/docrefs.py bridge/mergeprep.py                  # 이 파일을 가리키는 문서와 줄, 문단
.venv/bin/python tools/docrefs.py bridge/transcript/ bridge/x.py:10-40  # 폴더, 줄 범위
.venv/bin/python tools/docrefs.py --range main...HEAD                  # 이 브랜치가 바꾼 코드로, 고침 / 안 고침까지
.venv/bin/python tools/docrefs.py --range <A>..<B> --unfixed --brief   # 안 고친 문서만, 문서와 줄 번호만
.venv/bin/python tools/docrefs.py --repo <다른 저장소> --range origin/main~20..origin/main
.venv/bin/python tools/docrefs.py --range main...HEAD --json           # 기계용
```

- 문서 묶음: `docs/`, 원고 폴더(그 저장소 `.foreman/notion.toml` `src`, 없으면 FOREMAN `config/notion.toml`의 그 저장소 칸. worktree면 원본 폴더 이름으로 찾는다. `--src`로 덮음), `portfolio/`. `*.md`만. README.md, CLAUDE.md는 묶음에 넣지 않았다
- 가리킴 넷: `[code:경로]`(폴더면 아래 모두, `:10-20`이면 바뀐 줄과 겹치는지), 머리 주석 「다루는 곳」(파일, 폴더, 글롭), 백틱이나 맨글 경로, 백틱 안 파일 이름(저장소에 하나뿐일 때만)
- 백틱과 맨글의 폴더, 글롭은 두 단계 이상만. 첫 판에서 `docs/roles.md`가 `bridge/`, `tests/*` 때문에 바뀐 파일 20개 모두에 걸렸다
- 범위 모드에서 코드가 아닌 것: 문서 묶음, `log/`, `*.md`
- 속도: FOREMAN 전체(docs, 원고, 포트폴리오 약 90편)에서 0.25초

## 3. 지시문에 넣은 곳

| 곳 | 무엇 |
|---|---|
| `bridge/roles.py` `CODER_DOCS_RULE`, `DOCS_RULE_ROLES = {"coder"}` | 사용자 문장 그대로. 코더만 |
| `bridge/docrefs.py` `prompt_block(cwd, role)` | 규칙 + 도구 명령 + 말투 한 줄(FOREMAN이면 docs, 원고, 포트폴리오 규칙과 그 원천, 다른 저장소면 「그 저장소 CLAUDE.md, docs를 따른다」와 `--repo .` 명령) + 사람 승인 문서 안내 |
| `bridge/handoff.py` `_finish_spawn` | 첫 글이 있으면 끝에, 인계만이면 `inject(rule=…)`로 인계 뒤, 사람이 덧붙인 말 앞에. 계획 [시작], [+ 세션], 새 세션으로 옮기기가 모두 여기를 지난다 |
| `bridge/foreman.py` 교장 지시문 「3. role」 | 코더 줄: 규칙을 first_prompt에 옮기지 말고, 코드 고침 뒤 그 문서만 맞추는 서기 세션을 따로 내지 마라. 디자이너, 조사에는 규칙이 없다 |
| `bridge/roles.py` `ROLE_INFO`, `roles.js` `ROLE_DESC` | 「코드를 고치거나 만듭니다. 그 코드를 가리키는 문서도 함께 고칩니다」(역할 고르기 칸, 교장 지시문 첫 줄) |

붙지 않는 곳: 첫 글 없이 사람이 띄운 빈 코더 세션, attach(살아 있는 세션에 글 보내기). FOREMAN 코더는 CLAUDE.md에서도 안다.

## 4. 푼 규칙(파일, 전, 후)

| 파일 | 전 | 후 |
|---|---|---|
| CLAUDE.md 「따로 작업(worktree)에서 일할 때」 | 다만 operations.md와 style_guide.md는 건드리지 않는다, 사람 승인 카드라 코더가 건드리면 카드가 매번 사람에게 간다, 서기가 따로 맞춘다 | 고친 코드를 가리키는 문서(docs, 원고, 포트폴리오)도 같은 브랜치에서 고친다. 도구로 본다. 못 고치면 보고. 말투는 `docs/12_scribe.md` 「0.」. 그 둘도 고친다(카드가 사람에게 간다) |
| CLAUDE.md 「역할을 가르는 기준」 | 코더: 코드를 고치거나 만든다 | 뒤에 「그 코드를 가리키는 문서도 함께 고친다」 |
| `docs/11_worktree.md` 「8.」 | operations, style_guide, 원고에서 걸리면 코더는 고치지 않고 `[[scribe]]` | 코더가 고친다. 고칠 수 없을 때만 `[[scribe]]`에 적고 까닭을 보고 |
| `tests/screen_words.py` 머리, `SCRIBE_DOCS` 주석, `explain` 안내 | 「코더가 고치지 않습니다」 | 「이름을 바꾼 코더가 같은 브랜치에서 고칩니다 … 고칠 수 없을 때만 서기 몫」. `[[scribe]]` 목록과 요약 줄 「서기 몫 N줄」은 그대로(코더가 못 고친 것을 적는 곳) |
| `tests/data/screen_words.toml` 서기 몫 머리 주석 | 같은 뜻 | 같은 뜻으로 바꿈 |
| `docs/12_scribe.md` 7절 | 원고는 서기가 쓰는 글이라 늘 서기 몫 | 코더가 고치고, 못 고칠 때만 서기 몫. 「코더도 원고와 포트폴리오를 고친다」 한 줄 |

찾아봤지만 막음이 없던 곳: `config/roles.toml`(코더 규칙 없음), `bridge/roleguard.py`(서기, 조사, 관리자만), 교장 지시문과 서기실 지시문(「코더는 notion/, portfolio/를 건드리지 않는다」류 문장 없음, `grep`으로 확인).

## 5. 카드에 더한 것, 정리 후보와의 판단

- 카드 `docs`: `total`, `unfixed`, `code`(바뀐 코드 파일 수), `warnings`, 문서마다 `kind`, `hits`(줄, 제목, 문단 앞 160자, 코드). 옛 칸(`where`, `lines`, `count`, `files`, `stale`, 빈 `readme`)은 이어서 옛 카드와 DB 되살리기가 그대로 그려진다
- 화면(`handoff.js` `docsNote`): 위 줄 「📄 걸리는 문서 N, 안 고침 M」(안 고친 것이 있으면 노랑), 호버에 안 고친 것 먼저 문서 10개. 「자세히」에 문서마다 `원고`, `포트폴리오` 표시, 줄, 코드 파일, 고침(초록) / 안 고침(노랑), 줄 호버에 제목과 문단. 찾지 못하면 위 줄에 경고
- 알림: 「합치기 준비됨」 텔레그램에 `📄 걸리는 문서 N, 안 고침 M`(찾지 못하면 `⚠ 까닭`). 관리자 카드 글, 합친 뒤 관리자 글에 같은 수와 안 고친 문서 이름, `tools/docrefs.py --range`로 확인하라는 한 줄
- **정리 후보와 합쳤다.** 판단: 둘 다 「이 브랜치가 바꾼 파일을 적은 문서를 이 브랜치에서 고쳤나」를 묻는다. 정리 후보는 docs만, 파일 이름 글자로, base 판으로 읽었고 원고, 포트폴리오, `[code:]`, 「다루는 곳」을 보지 못했다. 둘을 따로 두면 같은 문서가 두 수로 보이고 사람이 어느 쪽을 믿을지 정해야 한다. 그래서 `mergeprep.doc_candidates`가 `docrefs.scan`을 부르게 바꿨다(옛 `_file_keys`, `_has_key`, `_STOP`은 지움). API `docs_done`, `keep_docs_h`는 이름 그대로 두었다(화면, 알림 글만 「걸리는 문서」)
- 옛 정리 후보와 다른 점: 바뀐 테스트, 설정 파일(`config/*.toml`, `tests/*`)도 코드로 친다. 파일 이름만 적은 줄은 저장소에 그 이름이 하나일 때만 친다(옛것은 줄기까지 봤다가 docs에서는 경로, 이름만 봤다)

## 6. 첫 사례: 이 브랜치의 걸리는 문서

코드 커밋 셋 뒤 `--range main...HEAD`로 46편이 걸렸다(파일 단위라 문단 대부분은 이번 고침과 상관없다). 내용이 틀어진 문단만 찾아 고쳤다(`정리 후보`, `코드를 고치거나 만듭`, 코더 문서 금지 문장, 첫 글에 붙는 것).

- 고침: `docs/11_worktree.md`(6-1 걸리는 문서, 8, 새 9절), `docs/12_scribe.md`, `docs/operations.md`(서기 몫 한 줄, 거꾸로 찾기 한 줄), `docs/roles.md`, `docs/10_office_design.md`(자세히 목록), `docs/11_foreman_dispatch.md`(교장 코더 줄), CLAUDE.md 두 줄, `notion/07_merge/01_card.md`(「정리 후보」 절을 「걸리는 문서」로 다시 씀, 표, 그림, 머리 주석 다루는 곳에 `bridge/docrefs.py`), `notion/14_screen/05_check.md`(서기 몫 문단), `notion/05_roles.md`, `notion/05_roles/01_roles.md`(표, 코더 절에 까닭 한 문단), `notion/00_foreman.md`(표), `notion/09_dispatcher/01_plan.md`(첫 글 절에 한 문단), `portfolio/09_new_session.md`(표), `portfolio/07_merge.md`(카드 문단에 경어체 두 문장)
- 안 고침(본 뒤 그대로): 나머지 원고와 docs는 `bridge/handoff.py`, `bridge/foreman.py`, `tests/*`를 다른 기능 때문에 가리킨다. `notion/15_db/01_tables.md` 248과 `notion/07_merge/01_card.md` 171의 「정리 후보 6개가 사라졌다」는 그때 이름을 쓴 지난 일이라 두었다
- 원고 머리 주석의 「읽은 커밋」은 고치지 않았다. 고친 것은 문단 몇 개이고 편 전체를 그 커밋으로 다시 읽은 것이 아니라서, 서기실이 이 편들을 「코드가 바뀐 편」으로 계속 세는 것이 맞다
- 말투: docs는 평서체, 원고는 평서체에 문장 끝 근거 표시, 포트폴리오는 경어체 문단

## 7. 같이 도는 세션과 겹친 파일

- `bridge/handoff.py`(514 코더가 알림 쪽을 고침): `_finish_spawn` 첫 글 넣는 자리, `inject` 머리, import 한 줄만. 알림 줄은 건드리지 않았다. 합칠 때 rebase가 필요할 수 있다
- `notion/`, `portfolio/`(515, 516 서기): 위 6.의 문단만. 같은 편을 고치고 있으면 충돌이 날 수 있다
- 513의 파일(`scribe.js`, `publish.py`, `notion.py`, `scribe_room.py`)은 건드리지 않았다

## 8. 사람이 정할 것

1. `docs/operations.md`, `docs/style_guide.md`를 합치기 카드에서 늘 사람 승인(`config/handoff.toml` `[merge_prep.per_project.foreman] human_paths`)으로 둘지. 코더가 이제 이 둘을 고치므로, 그대로면 이 둘을 건드린 코더 카드는 매번 사람에게 간다(이번 브랜치도 CLAUDE.md와 operations.md 때문에 사람 카드다)
2. 원고(`notion/`)와 포트폴리오를 코더가 고친 카드도 관리자가 승인해도 되는지(지금은 관리자 카드). 서기 검토를 거치게 하려면 따로 정해야 한다
3. 밀린 것을 어떻게 셀지(아래 9.)
4. 근거 표시에 코드 줄 번호를 붙일지. 붙이면 이 도구가 바뀐 줄과 겹치는지를 보여 「안 고침」 헛걸림이 크게 준다. 지금 2,643개 모두 파일, 폴더 단위
5. 다른 저장소 코더에게도 이 절이 붙는다(FOREMAN 도구를 `--repo .`로 읽기만, 그 저장소 CLAUDE.md를 따르라고). 런슈즈, 펫퍼민트 CLAUDE.md와 어긋나면 `DOCS_RULE_ROLES`를 프로젝트별로 좁힐지

## 9. 밀린 것 세기 제안(합친 뒤 관리자)

- **앞으로**: 이 브랜치를 합친 커밋을 기준점 `B0`로 두고 `tools/docrefs.py --range B0..main --unfixed --brief`. 이 규칙이 생긴 뒤 코드를 바꾸고도 같은 범위에서 고치지 않은 문서만 나온다
- **지금 밀린 것(원고, 포트폴리오)**: 편마다 머리 「읽은 커밋」이 기준이다. 서기실 머리줄의 「코드가 바뀐 편」(`docsync`, `manuscript.code_commits`)이 이미 「읽은 커밋 뒤 다루는 곳을 바꾼 feat, fix 커밋」을 센다. 이 도구는 거기에 「어느 줄이 걸리는지」를 더한다. 읽은 커밋별로 묶어 돌리면 된다. 11-17 지금 읽은 커밋은 셋(e5d584b 34편, 9a7c22d 21편, b97ff43 11편)이다. 예: `--range 9a7c22d..main --unfixed`는 바뀐 코드 28개, 걸리는 문서 67, 안 고침 13
- **docs/**: 머리 주석이 없어 읽은 커밋이 없다. 기준을 「그 문서의 마지막 커밋」으로 잡고 `git log -1 --format=%h -- docs/x.md` 뒤 범위로 돌리는 것을 제안한다(도구에 `--since-doc` 같은 칸을 더할 수 있다, 아직 안 만듦)
- 발견: `notion/10_scribe/04_notion.md`의 머리 주석 자리에 견본 글 「읽은 커밋: <서기가 읽은 main 커밋>」이 있다. 이 편은 셀 수 없음으로 잡힐 것이다(이번에 고치지 않음, 서기 몫)

## 10. 확인 체크리스트

- [x] 거꾸로 찾는 도구가 도는가: 돈다. FOREMAN에서 파일 모드, 범위 모드 모두 0.25초 안팎. 시험 11개
- [x] 커밋 범위를 주면 걸리는 문서를 모두 찾는가: `--range`로 바뀐 코드 파일 전부를 docs, 원고, 포트폴리오와 맞대고 고침 / 안 고침을 보인다(시험 `test_range_fixed_unfixed_and_line_overlap`). 단 「모두」는 위 네 가리킴 꼴 안에서다. 경로 없이 기능 이름만 적은 문단은 못 찾는다
- [x] 코더 지시문에 규칙이 들어갔는가: 첫 글 끝(브리지), 교장 지시문, 역할 설명. 시험 `tests/test_coder_docs_rule.py`(코더만 붙고 디자이너, 조사에는 안 붙는다)
- [x] 합치기 카드에 걸리는 문서가 보이는가: 위 줄, 자세히, 알림, 관리자 글. 시험 node 1개 더함, pytest 2개 더함. 실제 화면은 보지 못했다(브리지를 다시 띄우지 않음, 미리보기로 보지 않음)
- [x] 기존 시험이 통과하는가: 아래 11.

## 11. 시험

- `.venv/bin/python -m pytest -q`: 코드 커밋 뒤 1209 passed, 문서 고침과 주석 바로잡기 뒤 다시 1209 passed(화면 말 시험 서기 몫 0줄)
- `node --test tests/js/`: 219 passed

## 12. 규칙 위반

- **진행 글 첫머리 영어 낱말**: 「Now 합치기 카드 코드를 바꿉니다」 한 번(일감이 「Now …」로 쓰지 말라고 한 바로 그 꼴), 「Edit 세 곳…」, 「Edit `docs/12_scribe.md`…」, 「Edit 원고와…」 세 번. 진행 글을 쓸 때 한국어인지 보지 않았다. 그 뒤로는 한국어로만 썼다
- **새 주석, docstring에 em dash(—)와 가운뎃점(·)**: `bridge/docrefs.py` 9곳, `tools/docrefs.py`, 시험 파일, `mergeprep.py`, `handoff.py`, `roles.py`, `handoff.js`, `screen_words.toml`, 시험 주석 등 22곳. 코드 커밋 셋(`8150c86`, `f3c5032`, `1dce4a6`)에 들어갔고, 끝내기 전에 찾아 쉼표, 마침표로 바꿔 다음 커밋에서 바로잡았다. 툴팁 첫 줄에서 제목과 설명을 가르는 기호(`tip.js`가 자른다)와 원래 있던 글은 규칙대로 그대로 두었다
- 그 밖(파일은 Edit, Write로만, `pgrep -f` 안 씀, push와 브리지 다시 띄우기 안 함, 다른 저장소 안 고침)은 지켰다

## 이어서(11-17, main `5adb03a` 위로 rebase)

- 충돌은 `notion/07_merge/01_card.md` 머리 주석 한 곳이었다. 515(`e8ba9a5`)가 범위를 고치며 「읽은 커밋」을 `5e0f7c5`로 올렸고, 이 브랜치는 「다루는 곳」에 `bridge/docrefs.py`를 더했다. 둘 다 살렸다(다루는 곳에 docrefs, 읽은 커밋 `5e0f7c5`). 본문은 저절로 합쳐졌고 「걸리는 문서」 절과 515의 고침이 모두 남았다. 근거 확인기 66개 모두 맞음
- rebase 뒤 `--range main...HEAD`: 걸리는 문서 46, 안 고침 32로 rebase 전과 같다. main에 새로 들어온 513 코드(`bridge/notion.py`, `bridge/scribe_room.py`, `bridge/api/publish.py`, `scribe.js`)는 이 브랜치의 코드 파일과 겹치지 않아 카드 결과를 바꾸지 않는다. 새로 들어온 원고에 옛 말(정리 후보, 코더가 문서를 고치지 않는다는 줄)이 다시 생긴 곳도 없어 더 고친 문단은 없다
- 시험: pytest 1216 passed, node 222 passed
- 규칙 위반 없음
