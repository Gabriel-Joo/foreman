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

## 313 화면 숨기기 끝 — 사람이 볼 차례(합치지 않음)

- `5311749`: `approver == "manager"`이고 `human_why`가 없는 카드를 승인 막대(`merge_waits` — 말풍선도 같은 값이라 함께 빠짐) · 패널 [합치기](「관리자 세션이 승인합니다 — 사람이 누를 것은 없습니다.」)에서 뺌. 충돌 · 실패 카드는 다시 보임, 관리자 알림 실패면 사람 승인으로. [끝내고 합치기] · 「따로 작업」 [합치기]는 남김. heredoc(`cat >>`)으로 시험을 붙인 것도 스스로 밝힘(sed와 같은 위반, log에)
- 브랜치 `cc/foreman-4` 커밋 2(`b46f246` · `5311749`), merge-tree exit 0. `config/handoff.toml`: FOREMAN · 인프라 `approver = "human"` · `squash = false`(합쳐도 지금 동작), FOREMAN `human_paths` = style_guide · operations, `human_always`(값 · 설정 · 규칙 문서 · 마이그레이션 · 자원 키 · 이력 낱말 · 지우기 · 서브모듈)
- 사용자에게 물음: 합칠지 · 합친 뒤 FOREMAN · 인프라 `approver = "manager"` · `squash = true` · 남긴 두 단추

## 314 check_watch 합침(관리자 승인 — 「늘 사람」 목록에 안 걸림)

- 314 `983f2a1`: 원인 = `MAX(COALESCE(ended_at, :n))`이 운영 DB에서 문자열(`'2026-11-12 09:54:42.000'`) → `max(pend["at"], busy)`. `SELECT MAX(ended_at), SUM(ended_at IS NULL)`로 나눠 안 끝난 빌드가 있으면 지금 · 없으면 마지막 끝(원래 뜻 그대로) + `_as_dt`. 프로젝트별 `_watch_project`를 `_guard_watch`로 감쌈(`check_sync_wait`도), 실패는 「칸 + 예외 종류」마다 한 번 ⚠ 알림(묶음 아닌 바로) · 회복 ✅ 한 번, ArgoCD 확인 실패도 이제 알림. 시험 3. 들여쓰기를 Bash 파이썬으로 고친 것을 스스로 밝힘(규칙 위반 — Edit로 바로잡음)
- 관리자 판단: 고친 줄을 읽어 원래 뜻과 같음 확인 → merge-tree exit 0 → `--no-ff` **`01ff8bb`** → pytest **774** · node **123** → push → 승인 대기 0 → **브리지 19:23:00**(728766 → 871853), 오류 0 · 감시 실패 0
- 314는 살려 둠(끝낼지 사용자에게)

## 313 합침 · 켜다가 시험 하나 깨짐 · 315

- 사용자: 313 합쳐라 · 합친 뒤 FOREMAN · 인프라 `approver = "manager"` · `squash = true` · 실제로 도는지 보라 · 314 끝내라 · 남긴 두 단추 그대로
- 314: 쉼 · worktree 변경 0 · 앞 0 확인 → `exit` ok
- 313: merge-tree exit 0(314 합친 뒤 다시) → `--no-ff` **`ea7fbee`** → pytest **791** · node **124** 통과
- 설정 켬 → **pytest 1 실패**: `tests/test_mergeprep.py:499` `test_live_config_starts_as_today`가 실제 `config/handoff.toml`을 읽고 「사람 · squash 꺼짐」을 기대(README 「실제 설정 파일을 읽는 시험」과 같은 종류). 11-12 302 때 사용자 결정(기대값만 바꾸지 말고 임시 파일)대로 → **설정을 되돌리고**(작업 트리 깨끗) `ea7fbee`만 push → 승인 대기 0 → **브리지 19:31:16**(871853 → 939985), 오류 0
- **315**(sonnet, `/api/spawn` 새 worktree `foreman-2`): 그 시험을 임시 설정 파일로, worktree에서 켠 설정으로도 통과하는지 확인만. 띄울 때 「313과 맡을 파일 겹침(tests/test_mergeprep.py)」 경고 — 313은 합쳐진 뒤 쉬는 중이라 실제 겹침 아님
- 315를 합친 뒤 설정을 다시 켜고, 시험 세션 하나로 카드 → 관리자 알림 → 관리자 승인(`"by":"manager"`) → squash를 실제로 본다

## 「맡길 일 2」

- FOREMAN 「어긋남」 둘: 312(`.worktrees/foreman-3`) · 314(`.worktrees/foreman`)가 합치기 · 쉬게 하기 없이 끝남 — 관리자가 손으로 `--no-ff` 합친 뒤 `exit`해서 worktree · 브랜치가 남았다. 커밋은 모두 main에 있다. (펫퍼민트 `model-service`는 원래 있던 것, 11-12 인계 「지우지 않는다」)

## 역할 권한 observe 기록(11-11 17:39 KST ~, 확인만)

- `event` approval_req의 `role_rule` **15건**: 「Bash로 파일 고침」 8 · 「관리자 코드」 7. `[roles] projects = ["foreman"]`이라 런슈즈 · 인프라 세션은 보지 않는다
- Bash로 파일 고침 8 — 모두 시험 파일에 `cat >> … <<'EOF'`(heredoc): 291 ×1(11-11) · **312 ×3**(test_managers ×2 · test_stage2_db — **312는 보고에서 밝히지 않았다**) · 313 ×3(test_scopetoken은 같은 명령에 `sed -i`도) · 314 ×1(test_pipeline)
- **안 잡힌 것 1**: 314의 `.venv/bin/python - <<'EOF'`로 `bridge/pipeline.py` 들여쓰기 고침(10:17:11) — 해석기에 표준 입력으로 넘긴 코드 안의 `open(f)`라 검사에 안 걸림. 실제 위반 9 중 8 기록
- enforce였다면: heredoc 8은 막힘, 파이썬 1은 통과
- 관리자 코드 7 — 모두 관리자 276: `CLAUDE.md` Edit ×4(11-11 19:11 ~ 19:18) · `docs/12_scribe.md` ×2 · `docs/operations.md` ×1(11-12 15:21 `2395477` 인계 전 결정 기록). `manager_allow`(config · log · README) 밖이라 enforce면 막힘. 사용자 지시로 한 정당한 일로 보인다(CLAUDE.md는 사용자가 시킨 규칙 고침 — 다만 그 지시가 어디 있었는지는 이번에 확인하지 않음)
- 「관리자가 합친 뒤 시험 파일 고치기」는 기록 0(11-12 302 때는 코더에게 맡겼다)

## 315 합침 · 승인자 · squash 켬 · 실제로 돎

- 315 `942e2a5`(`test_live_config_starts_as_today` → `test_config_without_project_rules_is_human_and_ff`, `tmp_path` 설정 — 뜻 그대로) → merge-tree exit 0 → `--no-ff` `8ec776c`
- `config/handoff.toml` FOREMAN · 인프라 `approver = "manager"` · `squash = true` → pytest **791** · node **124** → **`ca8fb8b`** push → 승인 대기 0 → **브리지 19:38:37**(939985 → 1008315)
- 사용자: 맡길 일 2 버려라 → 315 `exit` → 셋 다 변경 0 · 앞 0 확인 뒤 버리기(314 `foreman` · 312 `foreman-3` · 315 `foreman-2`) ok. 남은 worktree는 313 `foreman-4`(합쳐짐 · 쉼)
- 사용자: 310의 rebase는 시킨 것 — 되돌리지 말고 **push하지 마라**(V17 · V18 — 운영 스키마), 300이 다시 일하면 해시 바뀜 알려라 → 310에게 전함. 310은 「다시 시작하면」이 아니라 바로 300 입력 칸에 넣었다(「새 일은 시작하지 말고 확인만」을 붙임)
- **실제 확인 — 시험 세션 316**(`/api/spawn`, sonnet): log 파일 하나를 커밋 2개로 → 카드: `approver: manager` · `human_why: []` · `manager_told: true` · 관리자 309 입력 칸에 「[FOREMAN 합치기 카드] … 승인자는 관리자다 …」 · 사람 화면 316 `merge_wait` 없음(막대 · 말풍선에서 빠짐) → 관리자 `POST /api/sessions/316/merge-prep {"action":"merge","by":"manager"}` → `merged`, **커밋 하나 `697685e`** 「합침(cc/foreman, 커밋 2개): docs: 합치기 실제 확인 1차」 + 본문 「원래 커밋(오래된 차례): - 2026-11-12 19:39 docs: … 1차 / 2차」, 316 끝냄 · worktree 지움 · 관리자에게 결과 알림 → push → 316 `hidden_reason = 'test'`
  - 알아둘 것: squash 커밋 제목이 첫 커밋 제목을 그대로 따른다(위 「1차」) — 묶음 전체를 말하지 않을 수 있다. 원래 커밋의 본문은 실리지 않고 제목 · 날짜만

## 역할 권한 — 검사를 지나가는 길 · 런슈즈 · 인프라로 넓히면(확인만)

- 지나가는 길(`bridge/roleguard.py` 읽음): ① 해석기 안의 쓰기(`python -c` · `python - <<EOF` · `node -e` 등 — 일부러 안 봄, 261행) ② 경로에 `$`나 백틱(`sed -i … "$F"` · `> $OUT`) — 판정 안 함(228행) ③ `cd $X` 뒤 — 어디인지 몰라 안 막음 ④ 따옴표가 안 닫혀 나눌 수 없는 명령 ⑤ `>` · `>>` · `tee` · `sed/perl/gsed -i` 말고 쓰는 명령 — `cp` · `mv` · `install` · `dd of=` · `truncate` · `patch` · `git apply` · `git checkout -- 파일` · `awk -i inplace` · `ed` 등 ⑥ 스크래치에 쓴 뒤 `cp`로 저장소에 넣기(②+⑤) ⑦ 역할이 없는(미분류) 세션은 관리자 · 서기 규칙을 안 받음 ⑧ `[roles] projects = ["foreman"]` 밖은 처음부터 안 봄
- 런슈즈 · 인프라 지난 7일(approval_req Bash · Edit · Write 3,780건)을 같은 검사기로 다시 돌림 → **290건 걸림**:
  - 런슈즈 코더 Bash 파일 고침 137 — git이 무시하는 작업 폴더(`catalog/local/work` 등) 쪽이 적어도 37, 추적 파일(`DESIGN.md` 12 · `src/` 15 · `backend/src` 7 · `scripts/parity` 8 · 문서 · 시험 등)이 적어도 45 — 경로 가르기가 일부 어긋나 정확한 몫은 못 냄
  - 런슈즈 worktree push 21(11-08 그때는 세션이 push하던 규칙)
  - 인프라 관리자 「관리자 코드」 116 · 런슈즈 관리자 11 — 기본 `manager_allow`(config · log · README)가 FOREMAN 모양이라, 인프라 관리자가 원본 폴더에서 한 문서 옮기기 · `apps/monitoring` · CLAUDE.md, 런슈즈 관리자의 CLAUDE.md · HISTORY · TODO가 다 걸림
  - 그 밖 4(서기 2 · 인프라 코더 1 · 인프라 관리자 Bash 1)
- 넓히려면: `roles.toml projects`에 둘 더하기(설정) + **프로젝트마다 `manager_allow` · `scribe_deny`**(지금은 하나 — 코드 `roleguard.py` `RolesConfig`) + 무시되는 작업 폴더 · 생성물 경로를 막지 않을 목록(런슈즈 `catalog/local/` 등 — 코드 · 설정) + 각 저장소 CLAUDE.md에 같은 규칙(런슈즈 · 인프라엔 이미 「Edit · Write로만」 있음) + observe로 며칠 돌려 위 다시 돌리기와 견주기
