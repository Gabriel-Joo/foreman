# 승인 지옥 줄이기 — 확인 · 사용자 결정 · 코더 B · C 띄움 (2026-11-12 저녁, 원본 폴더, FOREMAN 관리자 309)

사용자: 「세션이 일을 끝낼 때마다 보고 · 합치기 카드가 사용자에게 온다 — 오늘 하루 수십 번」. 바꾸려는 그림: 코더 · 서기 · 디자이너가 끝내면 그 프로젝트 관리자가 받고, 모아서 보고 · 다시 뿌리고 · 합치고, 사용자에게는 한 덩어리가 끝났을 때 한 번. 먼저 확인만(그 단계는 기록하지 않음 — 「고치지 마라」), 결정 뒤 이 기록.

## 확인한 것(11-12, DB `notification` · 코드)

- 오늘 보낸 텔레그램: 관리자 턴 끝 86(**그중 41은 관리자끼리 부탁으로 연 턴**) · docsync 47(대부분 펫퍼민트 실패 되풀이) · 코더 턴 끝 28 · 그 밖 40 남짓. 합치기 카드 생성 10 · 합침 4
- 턴 끝 보고: 텔레그램(`config/notify.toml` — 프로젝트별 칸은 종료 이유 · 출처 · 최소 길이 · 실패만) + 화면(「보고 옴 · 답 기다림」). 역할로 가르거나 관리자에게 보내는 칸 없음. 관리자 부탁은 `managers.ask_text`가 tmux에 평범한 글로 넣어 출처 `human` → 설정으로 못 가른다
- 합치기 카드: 생기면 사용자 텔레그램(`notify_ready`) + 패널 · 막대, 관리자는 합친 뒤 결과 · 충돌만(`mergeprep.py` `_tell_manager`). 프로젝트 토큰은 자기 세션 `/api/sessions/{sid}/merge-prep` · `/worktree`에 이미 닿지만 **카드 목록 `GET /api/merge-prep`은 403**(런슈즈 토큰으로 확인)
- 합치기 몸: `bridge/worktree.py` 203 `merge` — worktree rebase → 원본 `merge --ff-only` → 브랜치 지우기. squash 길 없음

## 사용자 결정

- 관리자에게 넘김: ① 합치기 승인 ② 품질 판단 · 다시 뿌리기 ④ README · docs 정리 후보 고르기 ⑤ 언제 묶어 올릴지
- ③ 세션이 묻는 말: **관리자는 답하지 않는다 — 받아서 사람에게 올린다(중계만)**. 관리자 한 곳에서 모아 오고 판단은 사람
- 늘 사람에게 올릴 목록: 설정 · 값 파일(`values*.yaml` · `config/*.toml` · 자원 크기) · CLAUDE.md · 규칙 문서 · 마이그레이션 · 이력 다시 쓰기 · force push · 지우기 · 다른 저장소 · 사람이 직접 쓴 글을 고친 것
- 커밋 뭉치기: 지금부터 합치는 것에 squash, 과거는 손대지 않음. 본문에 원래 커밋들의 제목 · 날짜를 차례로(11-12 런슈즈 메시지 다시 쓰기와 같은 방식)
- 처음 한동안 텔레그램은 끄지 않고 **하루 한 번 묶음**. 먼저 켤 곳 FOREMAN · 인프라, 런슈즈는 300 일이 끝난 뒤, 펫퍼민트는 관리자가 없어 그대로
- **관리자끼리 부탁 턴 텔레그램부터 끈다**(오늘 41번 — 사람이 안 봐도 되는 것)

## 나눔 · 띄움 — 교장 경로 dispatch 408(세션 둘, 경고는 「세션 2개」 안내뿐, 파일 겹침 0)

| 세션 | 일 | 맡을 파일 | 자리 |
|---|---|---|---|
| **312** B 알림 · 중계(opus) | ① 관리자 부탁 턴 텔레그램 끄기(먼저 따로 커밋 → 관리자가 먼저 합침) ② 일꾼 턴 끝 보고를 관리자 입력 칸으로 ③ 묻는 말 관리자 중계(답하지 않음) ④ 하루 한 번 묶음(급한 것은 바로, 묶음 실패도 알림). DB가 필요하면 묻기 | `bridge/notify.py` · `managers.py` · `assembler.py` · `config/notify.toml` · 시험 | `.worktrees/foreman-3` |
| **313** C 합치기(opus) | ① 카드 생김 → 관리자, 프로젝트마다 승인자 ② `GET /api/merge-prep?project=` 프로젝트 토큰 ③ 정리 후보 고르기를 관리자에게 ④ 늘 사람 목록에 걸리면 사람 승인(경로로 못 가르는 것은 log에) ⑤ squash(프로젝트마다, 본문에 원래 제목 · 날짜) | `bridge/mergeprep.py` · `worktree.py` · `scopetoken.py` · `api/handoff.py` · `config/handoff.toml` · 시험 | `.worktrees/foreman-4` |

- 같이 도는 311(check_watch, `pipeline.py`)과 셋 — 동시 한도(11-09 사용자 「셋」)
- 공통: 새 동작은 프로젝트마다 스위치 · 처음엔 꺼짐(B의 ①만 바로 모든 프로젝트), 관리자가 없으면 지금처럼 사람, 커밋만 · 되돌리는 법 · 브리지 안 띄움 · README 표 안 고침
- 합친 뒤 관리자: FOREMAN · 인프라만 켬(인프라는 299에게 알림). 관리자 규칙 줄(FOREMAN · 인프라 CLAUDE.md)은 규칙 문서라 안을 사용자에게 보인 뒤

## 312 ① 먼저 합침 — 관리자끼리 부탁 턴 텔레그램 끄기

- 312 보고: `9707dc5` — 글 머리 「[관리자 부탁 — 」인 턴을 출처 `manager_ask`로(`assembler._origin`), `notify.toml` 기본 origins에 없어 안 보냄, overlap · 답 기다림 · 서기의 사람 입력 셈에서도 빠짐. 오늘 41건(276 12 · 309 11 · runshoes 12 · infra 6) 모두 해당. 계획 카드의 「사람 → 관리자」는 human 그대로
- 312가 살아 있어 손으로: `merge-tree` exit 0(따로) → main이 앞서 `merge --no-ff 9707dc5` → **`e9d5247`** → pytest **762** · node **123** 통과 → push → 승인 대기 0 → **브리지 18:49:07**(3580901 → 633656), 새 프로세스 오류 0
- 312 물음: `render.js` `ORIGIN_LABEL`에 `manager_ask` 이름표가 없어 패널에 글자 그대로 보임(맡은 파일 밖) → 한 줄 허락(화면 글 「~습니다」), 같은 브랜치에 따로 커밋. `POST /api/sessions/312/input`(대기열)
- **알아둘 것**: 이 세션 셸에는 `XDG_RUNTIME_DIR`이 없고 `DBUS_SESSION_BUS_ADDRESS`가 `/tmp/dbus-…`를 가리켜 `systemctl --user`가 「Process org.freedesktop.systemd1 exited with status 1」로 실패했다. `XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`를 앞에 두면 된다(실패한 첫 시도는 브리지를 건드리지 않았다 — 15:13:04 그대로였음을 확인)
- 실제로 `manager_ask`로 잡히는지는 다음 관리자 부탁 턴에서 DB로 본다

## 312 ②~④ 합침 · FOREMAN · 인프라 켬

- 312 보고: `9499739`(이름표 「관리자 부탁」) · `597cb6e`(② 작업 보고 → 관리자 「[작업 보고 — …]」 ③ 묻는 말 → 「[사람에게 올릴 물음 — …]」 + 「관리자가 답하지 않습니다」, 관리자가 그걸로 연 턴은 출처 `relay` ④ `notification.decision = 'digest'`로 모아 21:00 Asia/Seoul 프로젝트마다 한 통, 스키마 안 바꿈). 스위치 `notify.toml [projects.*] relay_reports · relay_questions · digest` 모두 false로
- 관리자 품질 판단(이제 관리자 몫): 312 log의 급한 것 목록 · 되돌리는 법 · 시험 8개 읽음. 알아둘 것 — **보고 넘기기만 켜면 텔레그램이 일꾼 몫에서 관리자 relay 턴 몫으로 옮겨 갈 뿐**이라(312 「설계와 달랐던 점」) 셋을 함께 켬
- merge-tree exit 0(따로) → `--no-ff cc/foreman-3` **`f567676`** → `config/notify.toml` FOREMAN · 인프라 세 칸 true **`7c66c67`**(사용자 결정 「먼저 켤 곳 FOREMAN과 인프라」) → pytest **771** · node **123** → push → 승인 대기 0 → **브리지 19:01:25**(633656 → 728766), 오류 0
- 312: `render.js` `relay` 이름표(「작업 세션 보고」) 허락 — 같은 브랜치에 따로 커밋. 299에게 켠 것 · 「물음은 답하지 말고 모아 사람에게」 알림(delivered)
- 볼 것: 첫 작업 보고가 관리자 입력 칸에 오는지(session_action `mgr-relay`) · 21:00 첫 묶음이 나가는지 · 펫퍼민트 · 런슈즈는 그대로인지
- 312 이름표 `8cbd8a8`(`relay: '작업 세션 보고'`, 화면만) — merge-tree exit 0 → `--no-ff` **`84e9370`** → node 123 → push. 브리지는 다시 띄우지 않음(파이썬 변경 없음)
- **실제로 돎(19:01 뒤 DB)**: 312 턴 끝 → 관리자 309 입력 칸에 「[작업 보고 — 세션 312 …]」(session_action `mgr-relay` ok, 10:02:10 UTC) · 그 턴 알림 `digest`(`relayed:report`) · 312 합치기 카드 알림 `digest` · 299가 받은 309 부탁 턴 출처 `manager_ask` → `skipped`(`origin:manager_ask`). 21:00 첫 묶음은 아직

## 311 → 314 · 312 끝냄 · 313 화면 숨기기 · 「나중에 할 일」 둘

- **311 확인**(사용자 지시, 확인만): 살아 있음 · 첫 턴 18:29:26 시작 17초 만에 `stop_failure` — 안전 분류기 거부 `reasoning_extraction`(req_011CgxoJE99nFPwwmmgXsknS), 도구 6번(읽기) 뒤 멈춤, 커밋 0 · 변경 0, 텔레그램 「⚠ API 오류로 멈춤」 나감. 지도에서는 IDLE → 대강당(설계대로 — 「오류로 멈춤」 상태가 없다). 받은 겹침 경고는 드문 낱말 맞대기(점수 30, 관리자가 받은 글을 지시문에 옮겨서) — 278의 같은 파일 헛경보와 다른 종류
  - 관리자 실수: 확인 명령의 `cd .worktrees/foreman`이 이어져 관리자 셸 위치가 311의 worktree로 바뀌었다(읽기만, 바꾼 것 없음) → 다음 명령부터 원본 절대 경로
- **사용자 답**: 311은 같은 대화에 이어 시키면 또 걸리니 끝내고 새 세션으로, 걸린 표현은 바꿔 · 312 끝냄 · 관리자 승인 카드는 사람 화면에서 셋 다 숨김(승인 막대 · 패널 [합치기] · 머리 위 말풍선), 단 「늘 사람에게」 걸린 카드는 그대로 · 「나중에 할 일」 둘 · 313은 사람이 직접 본다(합치지 않음)
- 311 · 312: 쉬는 중 · worktree 변경 0 · main보다 앞 0을 따로 확인 → `action exit` 둘 다 ok(tmux 닫힘)
- **314**(sonnet) — `/api/spawn` cwd = `.worktrees/foreman`, `worktree:false`(이미 있는 worktree에 붙임, dispatch 기록 남음). 지시문은 같은 일을 일 목록으로만 적고(다른 세션의 추정을 옮겨 「먼저 재현해 확인하라」던 꼴은 뺌), 311이 커밋 0 · 변경 0으로 끝난 것을 적음
- **313 보고(18:52, 중계 켜기 전이라 사용자에게 감)**: 승인자 `approver` · 사람 승인 사유 `human_why` · `note` 칸(새 상태 없이 `ready`), squash는 `wt.SQUASH_OF` 훅이라 `[merge_prep] enabled`일 때만, FOREMAN 관리자는 관리 토큰이라 `"by":"manager"`를 스스로 적어야 함(브리지가 못 가름), 경로로 못 가르는 것(자원 크기는 YAML 키만 · 지우기 · 이력 다시 쓰기는 커밋 글 · 다른 저장소는 서브모듈만 · 사람이 쓴 글은 못 가름 — 작성자가 모두 같다), 판정 실패는 사람 쪽으로. 이 브랜치는 `config/handoff.toml`을 바꿔 사람 승인 카드. **`tests/test_scopetoken.py`를 sed로 한 줄 고침(스스로 밝힘 — Edit · Write 규칙 위반)**
- 313에게: 화면 셋 숨기기(`dashboard.py` `merge_waits` · `handoff.js` · 말풍선), `human_why` 있는 카드는 그대로, 관리자에게는 보이는지 확인, 따로 커밋, sed 한 줄은 log에 적기 — 합치기는 사람이 본다
- README 「나중에 할 일」: 「API 오류로 멈춘 세션이 일하는 것처럼 보인다」 · 「겹침 요청 낱말 헛경보 — 관리자가 코더에게 넘긴 지시문」 둘 더함(정해짐)
