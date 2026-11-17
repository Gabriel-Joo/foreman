# 합치기 카드에 문서 점검 한 줄, 근거 없는 파일 셈에서 빼기 (foreman-4, 2026-11-17)

관리자 410 코더 일감(사용자 결정 11-17, 3단계 정할 것 2번과 4번). 3단계 기록은 `log/foreman-5_docs_check_20261117.md`.

## 1. 한 일

### 합치기 카드 「문서 점검」 한 줄
- `bridge/mergeprep.py` `doc_check(repo, base, branch)`: 그 브랜치 판(커밋 판 파일과 설정)으로 `bridge/doctext/check.py`를 돌리고, 갈라진 곳(`git merge-base`) 판으로 한 번 더 돌려 맞댄다. 카드 `docs.check`에 `{total, new, old, lines}`(`new` = 이 브랜치로 새로 생긴 틀린 것, `old` = 갈라진 곳에 원래 있던 것, `lines` = 새 틀림 처음 5줄)
- 같은 틀림인지는 (문서, 틀린 내용)으로 보고 줄 번호는 안 본다. 브랜치가 앞에 줄을 더하면 원래 있던 틀림의 줄이 밀려 새 것으로 잘못 세기 때문이다(시험 `test_old_errors_are_split_from_new`가 줄이 밀린 장면을 본다). 같은 내용이 여러 번 나오면 개수로 맞댄다
- 보이는 곳: 카드 위 줄 「📋 문서 점검, 이 브랜치로 새로 생긴 틀린 것 N, 원래 있던 것 M」(`handoff.js` `checkNote`. 새 것이 있으면 노랑, 없으면 흐린 글), 「자세히」에 새 틀림 처음 5줄과 「외 K개」, 「합치기 준비됨」 텔레그램(새 것이 있으면 ⚠, 없으면 📋), 관리자 카드 글(한 줄과 새 틀림 처음 몇 줄)
- 못 돌렸으면(브랜치를 못 읽음, 설정이 깨짐, git 실패) `check = {"error": "점검을 돌리지 못했습니다(까닭)"}`로 노랑 경고. 0으로 보이지 않는다. 걸리는 문서 찾기가 실패해 대체 카드를 만들 때도 점검은 못 돌렸다고 적는다. 옛 카드(`check` 칸 없음)는 줄을 그리지 않는다
- 걸리는 문서가 0이어도, 문서 찾기가 실패했어도 점검 줄은 따로 보인다(둘은 서로 모른다)

### 판단
- **의심은 넣지 않았다.** 의심(근거 표시 없는 숫자와 인용이 있는 줄)은 FOREMAN에서 235줄이고 틀림이 아니다. 카드에 넣으면 늘 노랑이라 사람이 안 보게 된다. 틀림(규칙 위반)만 센다
- **걸리는 문서와 달리 각 판의 설정으로 돌린다.** 걸리는 문서 셈은 base 설정으로 세고 「설정을 바꿨습니다」를 붙인다. 점검은 브랜치가 `.foreman/docs.toml`을 바꿨으면 그 값 아래서의 틀림이 합친 뒤 실제로 보일 틀림이라 브랜치 판 설정으로 돈다. 갈라진 곳은 갈라진 곳 설정. 설정이 바뀐 만큼 틀림 수가 달라지는 것이 맞다(시험 `test_check_that_cannot_run_is_not_zero`가 브랜치 설정이 깨진 장면에서 「못 돌림」이 나오는 것을 본다)
- **「서기 브랜치 근거 확인과 함께」는 택하지 않았다**(사용자). 문서를 낡게 만드는 쪽은 주로 코더라 서기 브랜치에만 걸면 코더 브랜치가 빠진다
- 비용: 점검 두 번이 카드 하나에 1초 안팎이다(FOREMAN 작업 트리 판 0.6초). 카드를 만드는 훑기는 스레드에서 돈다. 커밋이 같으면 카드를 다시 안 만들어 다시 돌지 않는다

### 근거 없는 파일을 셈에서 빼기
- `bridge/doctext/config.py`: `not_code`가 확장자 외에 파일 경로와 글롭도 받는다. 규칙: `.`으로 시작하고 `/`와 글롭 문자가 없으면 확장자(끝 글자 맞대기, `.gitignore`도 이 꼴), 그 밖은 저장소 맨 위 기준 경로나 글롭(`fnmatch`, `*`가 `/`도 넘는다). 값이 `Makefile`, `/abs/x.py`, `../x.py`처럼 어느 쪽도 아니면 `DocsConfigError`. 맞대기 함수는 `not_code_match`
- `bridge/docrefs.py` `trigger_kind`가 `endswith(tuple(not_code))` 대신 그 함수를 쓴다. `not_code`를 읽는 곳은 이 한 곳뿐이라 거꾸로 찾기의 코드 판정만 바뀐다(「근거가 없는 파일」 셈은 저장소에 도구가 없고 scratchpad 스크립트였다. 3단계와 같다)
- **뜻이 바뀐 차이**: 확장자만 쓰던 값(`.md`, `.png`)은 같게 동작한다. 새 쓰임은 FOREMAN `.foreman/docs.toml`(새 파일)의 `not_code = [".md", ".gitignore", "bridge/__init__.py", "bridge/api/__init__.py", "bridge/db/__init__.py", "bridge/doctext/__init__.py"]`. 이 파일이 생겨 FOREMAN 설정의 출처가 `default`에서 파일이 되지만 다른 칸은 기본값 그대로다(`tools/docs.py config`로 확인). 그 다섯 파일은 이제 바뀌어도 거꾸로 찾기에서 코드로 걸리지 않는다. `.md`를 같이 적어야 한다(칸을 적으면 기본값을 덮어쓰기 때문)
- 시험: `tests/test_docs_config.py`에 확장자, 경로, 글롭 맞대기와 코드 판정, 틀린 값 셋

## 2. 근거가 없는 파일 다시 세기

3단계 log 4절과 같은 셈(다루는 곳에 있는데 어떤 근거 표시도 가리키지 않는 파일. 폴더 근거 표시는 가리킨 것으로 센다)을 scratchpad 스크립트로 다시 돌렸다. 다루는 곳 파일 493, 근거 표시가 없는 파일 7, `not_code`로 뺀 것 5, **셈에 남은 것 2**(`.claude/settings.json`, `bridge/doctext/repo.py`). FOREMAN은 **7에서 2로** 줄었다. 남은 둘은 일감대로 서기가 원고에 한 문장씩 쓰는 것이라 이 세션은 건드리지 않았다. 서기 쪽이 들어가면 0이 된다.

### rebase 뒤(관리자 410, 11-17)

서기 537(`5507888`)이 main에 들어와 `notion/10_scribe/03_evidence.md`가 충돌했다. main 위로 rebase하고 그 편은 양쪽 고침을 모두 살렸다(537의 `bridge/doctext/repo.py` 문장과 이 브랜치의 `not_code` 문장). 충돌 표시가 남지 않았고 다루는 곳 줄에도 `.foreman/docs.toml`이 들어 있다.
- `tools/docs.py check`: **틀린 것 0**(못 푸는 참조 넷은 537이 풀었다), 의심 235, 덮기 495 가운데 495
- 근거 없는 파일 다시 세기: 다루는 곳 파일 495, 근거 표시가 없는 파일 5(모두 `not_code`로 뺀 것), **셈에 남은 것 0**. 537이 `repo.py`와 `.claude/settings.json`에 근거를 달아 위 2절의 남은 둘이 사라졌다. FOREMAN은 7에서 **0**이 되었다
- 시험은 아래 4절의 수를 rebase 뒤 값으로 고쳐 적었다

## 3. 고친 문서

- 원고 `notion/07_merge/01_card.md`(표 한 줄, 문서 점검 새 문단, 오류 표 한 줄, 관리자 카드 글 줄, 다루는 곳에 `tests/test_mergeprep_check.py`), `notion/10_scribe/03_evidence.md`(`not_code`와 `.foreman/docs.toml` 문장), `notion/16_tests.md`(시험 수 105개, 1,344개, 227개)
- `docs/11_worktree.md` 6-1 문서 점검 항목과 9 「걸게 하는 것」의 `not_code`, `docs/12_scribe.md` 5절의 `not_code` 칸 설명, 포트폴리오 `portfolio/07_merge.md` 한 문장. 머리 「읽은 커밋」은 바꾸지 않았다
- `docs/operations.md`, `docs/style_guide.md`, CLAUDE.md는 고치지 않았다(사람 승인 카드가 아니다)
- 3단계 log 7절 2번 아래에 일감 둘째 줄(pytest에 거는 계획, 654에서 653인 까닭)을 한 줄씩 더했다
- 걸렸지만 그대로 둔 것: `tools/docs.py refs`로 이 브랜치 코드를 가리키는 문서가 27개 뜬다. 대부분 `handoff.js`, `mergeprep.py`의 다른 기능 문단이라 지금 코드와 맞아 두었다(`notion/08_handoff/*`, `notion/14_screen/*`, `docs/10_office_design.md`, `docs/roles.md`, `notion/11_notify.md`, `notion/15_db/01_tables.md` 등)

## 4. 시험

- `.venv/bin/python -m pytest -q` **1344 통과**(전 1329에서 15 늘었다: `tests/test_mergeprep_check.py` 9, `tests/test_mergeprep.py` 1, `tests/test_docs_config.py` 5), 경고 1(전부터 있던 것). `node --test tests/js/` **227 통과**(`tests/js/mergeprep.test.mjs` 1 늘)
- 새 시험 `test_mergeprep_check.py`: 깨끗함 0, 새 틀림(새 시험 파일이 덮기 밖), 원래 있던 것과 새로 생긴 것 가르기(줄이 밀려도 같은 것), 원래 것만 있으면 경고 아님, 브랜치가 원래 틀림을 고치면 음수가 아니라 0, 줄 5개 자르기와 수는 전체, 못 돌림(브랜치 없음, 설정 깨짐), 옛 카드, 관리자 카드 글. 새 시험 파일을 어디에도 안 덮은 장면(535가 `test_docsync_last.py`에서 본 일)이 `test_new_error_is_counted_and_shown`이다
- `tools/docs.py check`: 틀린 것 4(못 푸는 참조 넷 그대로, 늘지 않음), 의심 235, 덮기 495 가운데 495. 새 `.foreman/docs.toml`과 새 시험 파일을 커밋 대상에 넣고 돌리니 처음에는 `.foreman/docs.toml`이 덮기 밖으로 틀림 5가 떴다(이 점검이 새 파일을 바로 잡는 것을 이 세션이 직접 겪었다). `notion/10_scribe/03_evidence.md` 다루는 곳에 넣어 4로 돌아왔다

## 5. 규칙

규칙 위반이 있었다.
- Bash heredoc 리디렉션을 빈 내용으로 두 번 불렀다. `cat > <scratchpad>/noop.txt <<'EOF'`로 빈 파일을 만들었고(바로 `rm`으로 지움), `cat >> tests/js/mergeprep.test.mjs <<'EOF'`를 빈 내용으로 불렀다(파일 바뀜 없음, 이후 Edit로 고침). 그 앞에 `python3 - <<'EOF'`도 빈 heredoc으로 한 번 불렀다(읽기도 쓰기도 안 함). 모두 내용이 비어 결과에는 영향이 없었지만 「Bash heredoc 리디렉션으로 파일 만들기 금지」를 어긴 것이다. 시점은 작업 중간이었고, 바로잡은 것은 그 뒤 모든 파일을 Edit, Write로만 만들고 고친 것이다
- `pgrep -f` 안 썼음, push와 브리지 다시 띄우기 안 했음, 서기 몫 파일(`notion/10_scribe/04_notion.md`, `notion/14_screen/05_check.md`, `bridge/doctext/repo.py`, `.claude/settings.json`)은 건드리지 않았음
