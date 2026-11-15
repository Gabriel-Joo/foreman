# docs 다섯 편을 코드에 맞춤 (2026-11-16, 서기, 관리자 410 일감)

> 대상: `docs/style_guide.md`, `docs/11_foreman_dispatch.md`, `docs/operations.md`, `docs/11_worktree.md`, `docs/11_handoff_v2.md`. 읽은 기준 커밋 `9a7c22d`.
> 나눠 쓴 방법: 서브에이전트 셋(operations와 style_guide, 11_worktree, 11_foreman_dispatch와 11_handoff_v2)이 병렬로 고쳤고, 관리 세션이 문서끼리 모순, 공개 서술 기준, 시험, 커밋을 맡았다. 서브에이전트는 모두 끝났다.

## 1. 고친 곳

| 파일 | 절 | 코드에서 무엇이 어떻게 달랐나 | 근거 커밋 |
|---|---|---|---|
| operations | 「2.」 브리지 줄 | `bridge/hookmiss.py`가 빠져 있었다 | `cd14ed6` |
| operations | 「2.」 새 줄 「훅 스크립트, 견본」 | 훅을 다루는 줄이 없었다. 승인 대기 한도 차례(브리지 `wait_s` 3600, 스크립트 curl 3630, 훅 `timeout` 3660)와 견본이 3660인 것(전 900), 입력 바이트를 바꾸지 않고 넘기는 것(파이프, 소켓 모두) | `883c4c9`, `58f9f03` |
| operations | 「2.」 설정 줄 | `notion.toml`의 `docs`, `src` 칸과 FOREMAN 값(`manual`, `notion/`)이 없었다. 지워진 `portfolio.toml`이 남아 있었다(대신 `portfolio/` 폴더 파일이 편 목록, `scribe_room.topics`) | `16dcb3a` |
| operations | 「2.」 설정 줄 | `[merge_prep] projects`를 더한 근거로 squash 전 커밋 `6194ef7`, `9fa7831`을 들었다. main 이력에는 `ddb9d15`, `eab68a0`이다 | `ddb9d15`, `eab68a0` |
| operations | 「2.」 시험 줄 | 시험이 실제 `.run/hook_miss.log`에 쓰지 않게 한 격리(`tests/conftest.py` autouse 고정물)가 없었다 | `f663fab` |
| operations | 「3.」 systemd | 브리지 밖 알림(`OnFailure`, `foreman-bridge-alert.service`, `failed`일 때만 보냄, 못 잡는 것, 설치 상태 11-16 확인)이 없었다 | `cd14ed6` |
| operations | 「3.」 새 줄 hook_miss | 줄 꼴(시각, 출처, 갈래, 까닭, 세션, 도구), 1MB에서 `.1`, 시험은 자리를 바꿈, 읽어 알리는 쪽은 아직 없음. 갈래 이름은 적지 않고 코드를 가리킨다(아래 「4.」) | `cd14ed6`, `58f9f03` |
| operations | 「3.」 시험 DB | 「운영 DB에 쓰는 시험 둘」이 낡았다. `test_record_cli_writes_rows`는 세션 시험 DB로 옮겨 하나뿐이다 | `424a9bf` |
| operations | 「3.」 세션 화면 | 머리줄 글이 「세션 창」이었으나 코드 `showSize`는 「Claude Code 창」 | `1f08ac5` |
| operations | 「4.」 역할 권한 | `inspector-write`가 없었다. `enforce = ["inspector-write"]`라 observe여도 이 규칙만 막는다 | `8d12fd0` |
| operations | 「5.」 브리지 밖 알림 줄, 표 새 줄 「브리지가 멈춤」 | systemd 알림 길이 없었다 | `cd14ed6` |
| operations | 「5.」 표 Notion 기술문서 줄 | [지금 맞추기], [Notion에 올리기]도 같은 `DocSync.run_one`이라 같은 알림이 간다. 번호 없는 파일을 게시기가 어떻게 다루는지(아래 「3.」 10번) | `16dcb3a` |
| style_guide | 「1.」 포트폴리오 줄 | `config/portfolio.toml`이 없다. 편 목록은 `portfolio/` 폴더 파일, 편 하나가 화면 하나, 사진과 영상 이름 | `16dcb3a` |
| style_guide | 「1.」 새 줄 「노션 원고」 | `notion/` 원고 종류가 표에 없었다 | `16dcb3a` |
| style_guide | 「3.」 포트폴리오 | 옛 1~8 틀이 지금 일감 지시문(`task_prompt`)과 다르다. 옛 틀은 지우지 않고 「바뀜」만 붙였다 | `16dcb3a` |
| style_guide | 「3.」 근거 표시 줄 | 노션 판에서는 근거 표시와 머리 주석을 뗀다(`MANUSCRIPTS`, `Ctx.manuscript`). 문서는 「글자만 남는다」였다 | `16dcb3a` |
| style_guide | 「3.」 사진 줄 | 영상(GIF, WebM)과 캡션 표시가 없었다 | `16dcb3a` |
| 11_worktree | 「6.」 규칙 파일 알림 | 작업방 안의 규칙 파일을 고치는 순간에도 🛡 알림이 간다(`approval.toml [sensitive]` `protect`와 편집 허용 목록에 작업방 경로 꼴). 문서는 합칠 때 알림만 적었다 | `7ccb55f` |
| 11_worktree | 「6-1.」 merge_prep 켜짐 줄 | squash 전 커밋 `6194ef7`, `9fa7831`을 main 커밋 `ddb9d15`, `eab68a0`으로 | `ddb9d15`, `eab68a0` |
| 11_worktree | 「7.」 한계, hook_miss | 기록 줄에 출처와 까닭이 빠져 있었다. 기록하는 두 곳(브리지, 스크립트)을 적었다 | `cd14ed6`, `58f9f03` |
| 11_worktree | 「7.」 한계, 훅 바이트 | 소켓 입력도 그대로 넘긴다. 들어감(`cd14ed6`), 스크립트만 되돌림(`1d303b9`, 브리지 쪽 기록은 남음), 다시 넣음(`58f9f03`) 순서 | `cd14ed6`, `1d303b9`, `58f9f03` |
| 11_worktree | 「8.」 바꾼 이름, operations와 style_guide에서 걸리면 | 시험이 보는 문서에 원고 `notion/**/*.md`, `portfolio/*.md`가 들었고 서기 몫으로 간다(`tests/screen_words.py` `MANUSCRIPT_DIRS`) | `16dcb3a` |
| 11_worktree | 「8.」 문서 [버튼] | 근거 표시는 버튼으로 읽지 않는다(`bridge/evidence.py` `MARK`) | `e5d584b` |
| 11_foreman_dispatch | 「7.」 자동화 | 알림 둘째 줄 글과 자리(`wake.py` `_wake_inner`)가 바뀌었다 | `10e1e5b` |
| 11_foreman_dispatch | 「9-1.」 띄우는 길 | 가리키던 절 「11. 받는 함 [＋ 할 일]」은 지금 「11. 포스트잇」이고 [＋ 할 일] 창은 빠졌다 | `docs/12_scribe.md` 지금 절 제목 |
| 11_foreman_dispatch | 「10-2.」 역할 조사 | 화면 이름을 `ROLE_KO` 세 곳에서 바꿨다고 적혀 있었다. 지금은 `bridge/roles.py` `ROLE_INFO`와 `roles.js` `ROLE_LABEL` 한 곳 | `8d12fd0` 뒤 역할 모으기 |
| 11_foreman_dispatch | 「11.」 서기 일 종류 | 서기실 `TASKS`에 techdoc이 있는데 교장 지시문 목록에는 없다는 사실을 적었다 | `16dcb3a` |
| 11_foreman_dispatch | 「11.」 merge_prep 줄 | 프로젝트가 foreman, 인프라 둘로 적혀 있었다. 지금 네 프로젝트 | `ddb9d15`, `eab68a0` |
| 11_foreman_dispatch | 「11.」 역할 권한은 관찰만 | 「켜지 않는다」(11-12)만 있었다. 11-15부터 `inspector-write` 하나는 막는다 | `8d12fd0` |
| 11_handoff_v2 | 압축 손실 점검을 버튼으로 | 「약 80개씩」이었으나 `losscheck.GROUP_MAX = 20` | `4704490` |
| 11_handoff_v2 | 쌓인 대화 비율, 확인 안 된 것 | Sonnet은 11-14에 `[windows]`에서 빠졌다. 추정으로 남은 것은 Haiku 200k | `config/models.toml` 지금 값 |

## 2. 확인했지만 고치지 않은 것

- 1번(3660초): 11_worktree, 11_foreman_dispatch, 11_handoff_v2, style_guide에는 다루는 절이 없다. operations에만 넣었다
- 3번(통째로 지우기): 다섯 문서에 승인 판정 절이 없어 새 절을 만들지 않았다. 작업방 규칙 파일 알림만 11_worktree에 넣었다. 판정에서 빠지는 꼴과 조건은 쓰지 않았다
- 9번(점검을 조사로): 다섯 문서에 역할 뜻의 「점검」은 남아 있지 않다. 남은 「점검」은 압축 손실 점검, 화면 점검, `tipAudit` 같은 다른 뜻이다
- 10번(번호 없는 파일): 다섯 문서 어디에도 이 규칙이 없다. 코드는 번호 없는 파일을 건너뛰지 않는다. 번호식 제목(`new_title = "numbered"`) 프로젝트에서는 새 페이지를 만들지 않고 실패(⚠)로 남고(`bridge/notion.py`), FOREMAN `notion/`은 번호 있는 글 뒤에 올린다(`manuscript.tree_order`). 이 코드 사실만 operations 「5.」 Notion 줄에 적었다. 「올리지 않는다」는 코드 규칙이 아니라 실패를 그냥 두는 운영 관행이라 규칙으로 쓰지 않았다(아래 「5.」)
- style_guide 「4-1.」 화면 말 시험 줄은 범위를 「코드 문자열이나 문서 인용」이라고만 하지만 `docs/11_worktree.md` 「8.」을 가리키므로 두었다

## 3. 코드가 이상해 보이는 곳 (고치지 않음, 사람이 정함)

- **`tests/test_stage2_db.py::test_digest_send_failure_and_late_are_reported`가 실제 시각에 따라 실패한다.** 기록 시각은 DB의 실제 지금이고 판정 시각은 「UTC 오늘 11:00」이라, 30시간을 빼도 26시간을 넘지 않는 시각대(이번에는 KST 06시대)에 돌리면 `late:foreman`이 나오지 않는다. 이 브랜치는 docs만 바꿨고, 단독으로 두 번 돌려도 같다
- `bridge/foreman.py` 교장 지시문 「10. sessions」의 서기 task 목록에 techdoc이 없다. 교장 계획은 「기술문서 쓰기」를 붙이지 못한다(`TASK_RE`는 받으므로 사람이 카드에서 넣는 것은 된다). 일부러 뺀 것인지 확인이 필요하다
- `bridge/notion.py` `Ctx` 독스트링과 `MANUSCRIPTS` 주석, `config/notion.toml` 주석이 「저장소가 비공개라」라고 한다. 저장소는 이제 Public이다(동작은 같다)
- `deploy/hooks/foreman-hooks.json`에 홈 절대 경로가 그대로 들어 있다. 저장소가 Public이다
- `bridge/hookmiss.py` 독스트링은 스크립트 쪽 갈래를 7이라 하고, `log/foreman-4_hook_bytes_20261115.md`는 12갈래라 한다. 지금 스크립트에서 센 수와 둘 다 다르다(동작 문제는 아니다)
- `scripts/foreman-bridge-alert.sh`는 상태를 못 읽으면 보내는 쪽이다. 의도로 보이지만 문서에는 「`failed`가 아니면 보내지 않는다」만 적었다

## 4. 문서끼리 모순

| 어느 문서 어느 절끼리 | 무엇이 다른가 | 코드는 | 처리 |
|---|---|---|---|
| 11_foreman_dispatch 「11.」 merge_prep 줄 ↔ 11_worktree 「6-1.」, operations 「2.」 설정 | 프로젝트가 둘(foreman, 인프라) ↔ 넷 | 넷(`config/handoff.toml`) | 고침 |
| 11_worktree 「6-1.」, operations 「2.」 ↔ main 이력 | 근거 커밋 `6194ef7`, `9fa7831`(squash 전, main에 없음) | main은 `ddb9d15`, `eab68a0` | 고침 |
| operations 「4.」 역할 권한 「관찰 중, 막지 않고」 ↔ 11_foreman_dispatch 「10-2.」, 「11.」 표 예외 줄 | 하나도 막지 않음 ↔ `inspector-write`는 막음 | `enforce = ["inspector-write"]` | 고침(operations 「4.」, 11_foreman_dispatch 「11.」 「관찰만 하고 켜지 않는다」 줄) |
| 11_foreman_dispatch 「10-2.」 ↔ 같은 문서 「10.」 끝 줄 | 화면 이름 자리가 `ROLE_KO` 세 곳 ↔ `roles.py` 한 곳 | `roles.py`, `roles.js` 한 곳 | 고침 |
| operations hook_miss 줄(서브에이전트가 처음 쓴 판) ↔ 11_worktree 「7.」 | 판정 없이 통과하는 갈래를 이름으로 늘어놓음 ↔ 공개 전(`494dfbf`) 「갈래」로만 일반화 | 갈래는 코드에 있음 | operations를 11_worktree 수준으로 줄임(갈래 이름 목록과 「없거나 늦거나」 조건 서술을 빼고 코드를 가리킴) |
| 번호 없는 파일 운영 관행 ↔ 코드 | 「노션에 올리지 않는다」 ↔ 건드리지 않고 올리거나 실패로 남김 | 건너뛰는 코드 없음 | **코드로 가를 수 없음, 보고만.** 관행을 코드로 만들지(건너뛰기), 지금처럼 실패를 둘지는 사람이 정한다 |

## 5. 남은 것

- 위 「3.」 여섯 줄은 사람이 본다
- 번호 없는 파일 처리(위 「4.」 마지막 줄)는 사람이 정한다
- 11_foreman_dispatch 「11.」 역할 권한 표 줄과 「켜는 법」 아래 줄에는 예전부터 해석기로 쓰는 예시와 지나가는 길 낱말이 있다. 이번에 새로 쓴 것이 아니라 두었고, 공개 서술 정리 때 볼 만하다
- README, CLAUDE.md는 건드리지 않았다(일감대로 맨 마지막에 따로)

## 6. 확인 체크리스트

- [x] 다섯 문서를 모두 봤는가: 봤다(서브에이전트 셋이 나눠 보고, 관리 세션이 겹치는 주제를 다섯 문서에서 다시 찾았다)
- [x] 어긋난 곳마다 무엇이 어떻게 달랐는지 적었는가: 「1.」 표
- [x] 코드가 이상해 보이는 곳을 따로 모았는가: 「3.」, 고치지 않았다
- [x] 문서끼리 모순되는 곳을 찾았는가: 「4.」 여섯 줄, 다섯은 코드대로 고치고 하나는 보고만
- [ ] 시험이 통과하는가: `node --test tests/js/` 210 통과. pytest는 1175 통과, 1 실패(「3.」 첫 줄, 시각에 기대는 시험, 이 변경과 무관). 화면 말 시험은 서기 몫 0줄
- [x] README와 CLAUDE.md를 건드리지 않았는가: 건드리지 않았다(`git diff --name-only`는 docs 다섯과 이 log뿐)

새로 쓴 글에 em dash와 가운뎃점은 없다(낱말 단위 diff로 0개). IP, 도메인, 토큰, 홈 경로를 넣지 않았다.

## 7. 규칙 위반

- **서브에이전트 하나(operations와 style_guide 몫)가 스크래치 폴더에 파일 두 개를 Bash `>` 리디렉션으로 만들었다.** 마무리에 기호 개수를 세려고 diff를 담았다. 저장소 밖 세션 스크래치이지만 일감의 「`>` 리디렉션으로 파일 만들기 금지」에 글자 그대로 어긋난다. 그 뒤로는 파이프로만 셌다. 지우려던 `rm`은 CC 안전 검사에 막혀 실행되지 않았고 다시 시도하지 않았다. 파일은 세션 스크래치에 남아 있다(저장소와 무관)
- **관리 세션이 커밋 직전 진행 글 하나를 「Wait,」라는 영어 낱말로 시작했다**(시험을 다시 돌린 뒤). 「진행 글까지 모두 한국어」에 어긋난다. 보낸 뒤에 알아챘고, 그 뒤 글은 한국어로 썼다
- 나머지 서브에이전트 둘은 규칙 위반 없음
