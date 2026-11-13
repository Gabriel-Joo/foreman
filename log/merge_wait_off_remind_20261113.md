# 사람 승인 합치기 물음 — 끈 것은 막대에서도 빼기 · 5일째 한 번 알리기 — 2026-11-13 (코더 cc/foreman-3, 관리자 318 일감 D)

바탕: `log/merge_wait_to_manager_20261113.md`(`b70018b`) 「사람이 정할 것」 1 · 2.

## 한 일

### 1. [답 안 해도 됨]으로 끈 합치기 물음 — 다시 안 올리고 승인 막대 숫자에서도 뺀다 (`bridge/mergeprep.py` · `bridge/api/dashboard.py` · `handoff.js`)
- 카드에 `esc_off_at` 칸(사람이 끈 시각). 카드 JSON이라 DB `merge_card`에 같이 남는다 — **스키마 안 바꿈**
- **사람이 끈 것과 브리지가 내린 것을 가르는 법**: 브리지는 물음을 내릴 때(`_esc_close` — 합쳐짐 · 미뤄짐 · 없어짐 · 관리자 바뀜) 카드의 `esc_id`를 함께 비운다. 그러니 `_esc_sync`에서 **카드가 아직 쥔 물음이 떠 있지 않고 그 id에 esc-off가 있으면 사람이 끈 것**이다(`_esc_offs`). esc-off가 없으면 7일(ESC_KEEP)이 지나 사라진 것 — 지금처럼 둔다(막대에 남음)
- 끈 카드는: 다시 올리지 않는다(관리자가 바뀌어도 · 브리지를 다시 띄워도) · `merge_waits`에서 뺀다 → 승인 막대 「🔀 합치기 대기 N」 숫자 · 작업 세션 머리 위 「합치기 기다림」 · 말풍선이 함께 빠진다(모두 `merge_waits` 하나를 읽는다 — JS 갈래는 안 고침). 관리자 머리 위는 esc-off로 이미 빠진다
- 카드는 그대로: `GET /api/merge-prep?project=`(관리자 쪽 목록 — `esc_off_at` 칸이 실린다) · 세션 패널 「세션」 탭 카드에 「사람이 답 안 해도 됨으로 둠 — 시각. 관리자 머리 위 · 승인 막대에서 뺐습니다(합치려면 [합치기])」(`handoff.js mp-off`, 툴팁 「답 안 해도 됨 — …」). [합치기] · [나중에]는 그대로
- **새 커밋으로 카드가 다시 만들어지면 다시 올린다**(새 일). `prep`이 새 `Card`를 만들면 `esc_off_at`이 빈다. 같은 커밋(main만 앞섬 · live만 바뀜)으로 다시 만들 때는 `esc_*`와 함께 `esc_off_at`도 잇는다(같은 일)

### 2. 5일째에 한 번 알림 (`bridge/mergeprep.py`)
- `MergePrepCfg.remind_days = 5`(`[merge_prep] remind_days`, 0이면 끔, ESC_KEEP 7일 미만이어야 — 아니면 `load`가 ValueError). **설정 파일은 고치지 않았다** — 코드 기본값만
- `_esc_sync`가 같은 관리자에게 떠 있는 합치기 물음의 올린 시각(`_esc_open`이 `created_at`도 싣는다)을 보고, `remind_days`가 지났으면 텔레그램 **바로**(`send_direct(..., later=False)` — 묶음을 켠 프로젝트여도) 한 번:
  「⏳ 합치기 카드가 5일째 사람 승인을 기다립니다 — 이틀 뒤 관리자 머리 위에서 사라집니다(카드는 남음) · 세션 N 「제목」」(남은 날은 7 − remind_days로 하루 · 이틀 · 사흘 …)
- **한 번만**: 열쇠 `mergeprep:remind:<escalate id>` — `_notify`가 `notification.rule`을 보고 이미 있으면 안 보낸다(브리지를 다시 띄워도). 매 맞추기(1분)마다 DB를 보지 않게 메모리 표(`_reminded`)도 둔다
- 사람이 끈 물음은 `_esc_open`에 없으니 알리지 않는다
- `_notify`에 `later` 인자(주면 `send_direct`에 넘기고, 안 주면 지금처럼 notifier가 정함 — 가짜 notifier가 `later`를 안 받는 다른 시험을 깨지 않게)

## 확인
- `pytest` 전체 **821 통과 · 1 건너뜀**. 새 `tests/test_merge_wait_off_remind.py` 6개: 사람이 끔 → 막대(merge_waits)에서 빠지고 · 목록에 남고 · 다시 안 올림(다시 맞춤 · 관리자 인계 · 다시 띄움) · 새 커밋이면 다시 올림 / 브리지가 내린 것 · 7일 지난 것은 사람이 끈 것 아님 / 4일 23시간엔 안 알림 · 5일 넘으면 한 번(later=False, 글) · 다시 띄워도 한 번 / 끈 카드 · remind_days=0은 안 알림 / `load` 기본 5 · 0 · 7이면 거부 / 남은 날 글. 시각은 시험 안에서 잰다. 실제 `config/*.toml`은 읽지 않는다(tmp_path에 쓴 파일)
- `node --test tests/js/` **133 통과** — `mergeprep.test.mjs`에 끈 카드 표시(mp-off · [합치기] 남음 · 합친 카드엔 안 보임)
- 화면: 이 worktree 코드로 미리보기(`python -m bridge.preview --port 8232`)를 직접 띄워 `tools/screen.py --demo overhead_marks --views foreman,ronanlab-infra,map --no-term` 세 테마 × 1920 · 1366 · 1024 × 좁게/넓게 **18조합 문제 0**, 화면마다 `window.office.bubbleAudit()` 빈 목록. 점검 뒤 껐다
  - 시연 자료는 안 고쳤다 — 끈 카드는 `merge_wait`에 아예 안 실리므로 시연에 더할 모양이 없다. 패널 카드 한 줄은 시연 화면에 안 나와 JS 시험으로만 봤다

## 설계와 달랐던 점 · 판단 근거
- **사람이 끈 것을 어떻게 아나** — esc-off 행에는 누가 썼는지 칸이 없다. detail 모양을 바꾸면 `human_needs`의 `done` 맞대기가 깨진다. 대신 「브리지는 내릴 때 카드의 esc_id를 비운다」는 불변식을 썼다 — 카드가 쥔 채 꺼진 물음은 사람만 끌 수 있다. 맞추기는 `_sync_lock` 안에서 한 줄로 돌아 사이에 끼는 경우가 없다
- **알림 기준 시각은 카드가 아니라 escalate 시각** — 사라지는 7일이 escalate `created_at`에서 재지므로 「이틀 뒤 사라집니다」가 맞으려면 같은 시각을 봐야 한다. 관리자 인계로 다시 올리면 7일도 새로 시작하니 새 물음 id로 다시 한 번 알릴 수 있다(열쇠가 물음 id)
- **7일이 지나 사라질 때 한 줄 더 보내지 않았다** — 5일 알림이 이미 「이틀 뒤 사라짐 · 카드는 남음」을 말했고, 카드는 막대 숫자에 계속 남는다(사람이 끈 것이 아니면). 같은 일을 두 번 알리지 않는다
- **알림이 못 나가는 경우**: 브리지가 5일째 전부터 7일째 뒤까지 내려가 있었으면 그 물음은 `_esc_open`(7일 안)에서 빠져 알림 없이 사라진다. 막대 숫자는 남는다. 드물어 두었다
- **사람이 끈 뒤 다시 올리지 않는 것은 시간이 지나도 그대로** — 사용자 말 「답을 안 하겠다는 뜻이다」를 따랐다. 다시 올리는 것은 새 커밋(새 카드)뿐

## 규칙 지킴(11-13 관리자 318이 더한 줄)
- **heredoc 덧붙이기 꼴을 한 번 썼다** — JS 시험(`tests/js/mergeprep.test.mjs`)을 더하려다 `cat >> /dev/null <<'X'`(빈 본문)를 Bash로 한 번 쳤다. 손이 먼저 나간 것으로, 대상이 `/dev/null`이라 **저장소 파일은 하나도 바뀌지 않았다**. 바로 멈추고 시험은 Edit로 넣었다. 그 밖의 파일 고치기는 모두 Edit · Write
- 그 밖에 어긴 것 없음: sed -i · cp · python으로 파일 쓰기 안 함, push 안 함, 브리지 다시 띄우기 안 함, 설정 파일 · 스키마 · README · CLAUDE.md · docs · `bridge/preview*.py` 안 고침. 점검용 미리보기(`python -m bridge.preview --port 8232`, 이 worktree 코드)는 직접 띄웠다가 PID로 껐다(pkill -f 안 씀). 시험 안의 `tmp_path` 파일 쓰기는 시험 코드다

## 되돌리는 법
- 이 커밋을 `git revert`. 카드 JSON의 `esc_off_at`은 옛 코드가 `from_saved`에서 버린다 — 되돌린 뒤 끈 카드는 옛 동작대로 막대에 다시 세지만 머리 위로 다시 올라가지는 않는다(esc_id는 그대로 쥐고 있다)
- 알림만 끄려면 `config/handoff.toml [merge_prep] remind_days = 0` + 브리지 다시 띄우기
- 합친 뒤 브리지를 다시 띄워야 서버 쪽이 돈다(원본 세션이). 패널 글(JS)은 새로 고침

## 사람이 정할 것
1. 브리지가 5~7일째 사이 내내 내려가 있던 드문 경우의 알림 누락 — 지금은 막대 숫자만 남는다. 7일이 지난 물음도 한 번 알리게 할지
2. `config/handoff.toml`에 `remind_days = 5` 줄(설명 포함)을 적어 둘지 — 지금은 코드 기본값만이라 설정 파일에서 안 보인다

## README에서 뺄 줄
- README 「나중에 할 일」에 「사람이 끈 합치기 물음이 막대에 남음」 · 「7일 지나면 조용히 사라짐」 류의 줄이 있으면 뺀다(관리자가 확인)
