# 놓친 실패 알림을 바로, docrefs 헛걸림 고침 (foreman-4, 2026-11-17)

관리자 410의 코더 일감(사용자 지시 22의 2, 3, 5번). 앞선 기록: `log/foreman-5_fail_now_unpriced_20261117.md`(514), `log/foreman-4_notion_catchup_20261117.md` 「2.」(다섯을 찾은 곳).

브랜치 `cc/foreman-4`, push 안 함, 브리지 다시 띄우지 않음.

## 1. 실패 알림을 바로

### 1-1. 바로 가게 바꾼 알림

모두 `HandoffManager._notify`(종류 `handoff`)를 빌려 부르는 곳이다. `fail=True`를 넘겨 514가 만든 길(글 앞 ⚠, `later=False`)로 간다.

| 파일 | 글 요지 | 전 |
|---|---|---|
| `bridge/losscheck.py` `_run` | ⚠ 압축으로 잊은 것 찾기 실패(예외 이름) | 묶음 |
| `bridge/losscheck.py` `_run_inner` | ⚠ 압축으로 잊은 것 찾기 실패(모든 판정 묶음 실패) | 묶음 |
| `bridge/promote.py` `_wait_list` | ⚠ 대화 결정 문서에 적기, 목록 실패(표지 없음, 세션 끝남, 시간 초과) | 묶음 |
| `bridge/promote.py` `_wait_list` | ⚠ 대화 결정 문서에 적기, 목록 실패(목록 해석 거부) | 묶음 |
| `bridge/promote.py` `_wait_write` | ⚠ 대화 결정 문서에 적기, 확인 실패 | 묶음 |
| `bridge/losscheck.py` `_run_inner` (더 찾음) | 압축으로 잊은 것 찾기 끝, 글에 「묶음 N개 실패」가 든 일부 실패 | 묶음 → **일부 실패면 바로**(`fail=bool(bad)`). 건너뛴 프롬프트만 있으면 묶음 그대로 |

### 1-2. 514 표 밖에서 다시 훑은 결과

방법: `bridge/` 아래 `_notify(`, `send_direct(` 호출을 모두 grep하고, `[digest] kinds`(turn, batch, merge, handoff, docsync, recon) 종류로 가는 것과 `later=True`를 넘기는 것을 글까지 읽었다.

- handoff: 위 여섯. `bridge/handoff.py` 안 실패는 514가 이미 `fail=True`. 🛡 「안전 규칙 파일이 합치기로 바뀌었습니다」는 종류 `rulefile`(묶음 밖)
- merge(`bridge/mergeprep.py`): 실패, 못 함은 모두 글에 ⚠이거나 `later=False`. 「합치기 준비됨」은 걸린 것이 있으면 ⚠, 🛡 줄과 `later=False`
- docsync: 실패는 ⚠(`bridge/docsync.py`, `bridge/notioncfg.py`). ✋ 덮지 않음은 실패가 아님(514 판정 그대로)
- recon, turn, batch: 514 판정 그대로
- `later=True`를 넘기는 곳은 escalate 보고 하나(`bridge/api/dashboard.py`), 실패 알림이 아님
- 묶음 밖 종류(insp, manager, approval, stall 등)는 늘 바로라 볼 것 없음
- 결론: 더 찾은 것은 losscheck 「끝」의 일부 실패 하나

### 1-3. 514가 왜 놓쳤나

514는 묶음 종류마다 알림을 내는 파일(`bridge/notify.py`, `bridge/handoff.py` 등)을 읽어 표를 만들었다. losscheck와 promote는 자기 파일에서 `self.m._notify`로 HandoffManager의 알림 함수를 빌려 불러, 「handoff 종류 = handoff.py」로 훑으면 보이지 않는다.

### 1-4. 건 시험 (`tests/test_fail_notify_scan.py`)

- 종류가 아니라 부르는 곳에서 출발한다. `bridge/` 모든 .py를 AST로 읽어 `_notify(...)`, `send_direct(...)` 호출을 찾고, 인자 글자(문자열 상수, f-string 글자 부분, `rule=`, `kind=`, mergeprep 키는 뺌)에 「실패」, 「시간 초과」, 「못」이 들면 실패 알림으로 본다
- 실패 알림은 `fail=`(False 상수가 아님), `later=False`, 글에 urgent_marks(⚠ ❌ 🛑 ⏰ ❓) 가운데 하나가 있거나, 종류가 묶음 밖이어야 한다. `self._notify`의 종류는 모듈 표(`NOTIFY_KIND_BY_MODULE`)로 정하고, 표에 없는 모듈은 묶음 종류로 본다(새 모듈이 `_notify`를 만들면 표에 적어야 지난다). `_notify` 정의 몸 안 호출은 부른 쪽에서 보므로 뺀다
- 실패 알림을 20개 넘게 찾는지도 본다(훑기가 고장 나 0개를 찾고 지나가지 않게). 지금 21개
- main 판 `bridge/losscheck.py`, `bridge/promote.py`에 대 보니 다섯이 모두 `fail` 없이 잡혔다(고치기 전이면 깨지는 시험)
- 한계: 글이 모두 변수인 호출(losscheck 「끝」의 `err`)은 낱말로 못 본다. 그래서 losscheck 예외 실패와 promote 목록 실패를 실제로 돌려 `fail=True`인지 보는 시험 셋을 함께 걸었다

## 2. docrefs 헛걸림

- `bridge/docrefs.py` `is_code`: 문서 묶음 판정을 `kind_of`(`.md`만 본다)에 맡겨 `portfolio/img/`의 png, gif, webm이 코드로 세어졌다. 문서 묶음 폴더(`doc_sets`의 docs, 원고 폴더, `portfolio/`) 아래 파일은 확장자와 상관없이 코드가 아니게 했다. 빈 폴더 값은 건너뛴다(모든 파일이 코드가 아니게 되는 것을 막음)
- 시험 `tests/test_docrefs.py` `test_doc_folder_media_is_not_code`: 범위에 portfolio, notion, docs 아래 사진과 코드 하나를 넣어 코드가 그 하나뿐인지, `bridge/static/img/a.png`와 `portfolio.py`는 여전히 코드인지

## 3. 확인만 한 셋

- **다른 저장소 코더에게도 규칙 절**: 붙는다. `bridge/handoff.py` `_finish_spawn`이 프로젝트를 가리지 않고 `docrefs.prompt_block(cwd, role)`을 부르고, `prompt_block`은 역할만 본다(`bridge/roles.py` `DOCS_RULE_ROLES = {"coder"}`). 다른 저장소면 FOREMAN 도구를 `--repo .`로 가리키는 명령과 「이 저장소의 CLAUDE.md와 docs를 따른다」가 간다. 고치지 않음. 첫 글 없이 띄운 빈 코더 세션에는 어느 저장소든 붙지 않는 것은 그대로(`log/foreman-8_docrefs_20261117.md` 3절)
- **원고, 포트폴리오가 늘 사람 승인 경로에 있나**: 없다. `config/handoff.toml` `[merge_prep.human_always] paths`(values yaml, `config/*.toml`, CLAUDE.md, AGENTS.md, `.claude/*`, 마이그레이션)와 프로젝트별 `human_paths`(FOREMAN은 `docs/style_guide.md`, `docs/operations.md`) 어디에도 `notion/`, `portfolio/`가 없고, `bridge/mergeprep.py` `human_reasons`에도 문서 폴더 규칙은 없다. 다만 파일을 지우는 카드는 경로와 상관없이 사람 승인이다(`deletions`). 관리자 메모리 「문서 합치기는 사용자에게」(11-15)는 코드가 아니라 관리자 규칙이라, 원고 카드를 관리자가 승인해도 되는지는 그 메모리 쪽에서 정할 일이다
- **operations, style_guide는 계속 사람 승인**: 그대로. 손대지 않음

## 4. 함께 고친 문서

`tools/docrefs.py`로 고친 코드 셋을 가리키는 문서 20편을 찾았다. 대부분 파일 단위로 걸린 것이고, 바뀐 동작을 말하는 문단만 고쳤다.

| 문서 | 고친 곳 |
|---|---|
| `notion/11_notify.md` | 하루 묶음 표 「옮기기 요약」 두 칸, 「같은 handoff 종류여도 … 21:00 묶음에 실린다」 문단을 「바로 간다, 처음 놓친 까닭, 시험」으로 |
| `notion/08_handoff/03_promote.md` | 목록 실패, 확인 실패 알림이 21:00 묶음에 실린다던 두 문단 |
| `notion/08_handoff/01_loss.md` | 「점검의 실패 알림에는 그 표시가 없다」 문단, 일부 실패 끝남 알림 |
| `docs/11_worktree.md` 9절 | `--range`에서 코드가 아닌 것에 문서 묶음 아래 파일 |
| `notion/07_merge/01_card.md` | 「걸리는 문서」에서 코드만 고르는 줄 |
| `notion/16_tests.md` | 시험 파일 수와 시험 수(96개, 1,227개), 문서 폴더 사진 시험과 실패 알림 훑기 시험 한 줄씩 |

- 남은 「안 고침」 열넷(`--range main...HEAD --unfixed`)은 파일 단위로 걸린 것이고, 알림 묶음이나 코드로 세는 규칙을 말하는 문단이 없어 그대로 두었다

- 원고 머리 「읽은 커밋」은 바꾸지 않았다. 범위 검사 「판단이 필요한 것」 줄은 건드리지 않았다
- 안 고친 것: `docs/operations.md` 「5. 알림(텔레그램) 상세」 표에 인계 요약, 점검, 문서 옮기기 줄이 없다(514 기록 4절의 서기 몫). 같은 시각 서기가 그 파일 한 줄을 고치고 있어 건드리지 않았다. 더할 줄: 「압축으로 잊은 것 찾기, 대화 결정 문서에 적기 실패 | `bridge/losscheck.py`, `bridge/promote.py`, 종류 `handoff` | 묶음을 켠 프로젝트여도 바로(⚠), 끝남은 21:00 묶음(점검 일부 실패는 바로)」
- 포트폴리오 `portfolio/06_handoff.md`는 알림 묶음을 말하지 않아 그대로

## 5. 시험

- `.venv/bin/python -m pytest -q`: 1227 passed
- `node --test tests/js/`: 222 pass, 0 fail

## 6. 알릴 것

- 브리지를 다시 띄워야 반영된다(`bridge/losscheck.py`, `bridge/promote.py`, `bridge/docrefs.py`)

## 규칙 위반

- 11-17 이 세션에서 도구 호출 사이 진행 글 다섯을 영어 낱말로 시작했다(「Now 2번 docrefs입니다」, 「Now 시험 파일을 씁니다」, 「Also 머리 docstring 줄 …」, 「Add 시험 하나를 더합니다」, 「Now 원고 고침입니다」). CLAUDE.md 「항상 한국어로 답한다」와 일감의 「Now …로 쓰지 않는다」 위반이다. 결과 기록을 쓰기 전에 스스로 알아챘고 그 뒤로는 한국어로만 썼다
- 참고(위반 아님으로 봄): main 판 코드에 시험 훑기를 대 보려고 `python - <<'EOF'`로 읽기만 하는 스크립트를 한 번 돌렸다. 파일을 만들거나 고치지 않았다
