# 291(버리기 즉시 · 「세션」 탭) 합침 · 라이브 여섯 가지 · 290 결과 · API 토큰 확인 (2026-11-11 저녁, 원본 폴더, 관리자 276)

앞 기록: [merge_merge_wait_20261111.md](merge_merge_wait_20261111.md)

## 합침

- merge-tree main(`48a6f82`) ↔ `cc/foreman-3`(`581bf49`): exit 0, 커밋 셋, 변경 0. 서기 292 카드는 그대로 둠(사용자: 이 고침 먼저)
- 카드 291 승인 → `merged`, 커밋 3개(`0e1298c` 버리기 · 카드 밖 합치기도 바로 빠짐 · `b749468` 막대 → 「세션」 탭 · `ed2d3d7` 기록)
- 다른 pytest 없음 확인 뒤 혼자: **pytest 688 · node 123 통과** → push(`ed2d3d7`)
- 승인 대기 0 → **브리지 18:00:57**(553079 → 794119)
- 합침 알림의 「고치지 않은 문서」 후보 다섯: `docs/11_foreman_dispatch.md` · `operations.md` · `10_office_design.md` · `11_handoff.md` · `style_guide.md`(292가 맡은 넷 + `11_handoff.md` · `style_guide.md`)

## 라이브 여섯 가지 — 실제 카드(292 서기 카드 + 시험 293 · 294), 292는 보기만

| 본 것 | 결과 |
|---|---|
| ① 버리면 막대가 바로 줄어드나 | **바로** — 294 버림(응답 0.9초) → 4초 안에 API 대기에서 빠지고 막대 「3 → 2」 |
| ② 버리면 말풍선도 바로 사라지나 | **바로** — 말풍선은 같은 `merge_wait` 값을 그린다. 버린 뒤 4초 API에서 294 없음 |
| ③ 승인했을 때도 바로 줄어드나 | **API는 바로, 이미 열린 화면은 4초 넘게** — 293 승인 → 4초 뒤 API 대기 `{292}`뿐인데 열린 화면 막대는 「2」 그대로. 1분 30초쯤 뒤 새로 연 화면은 「1」로 맞음. 버리기보다 승인 쪽이 열린 화면에 늦게 닿는다 — 몇 초인지는 재지 못함(셋째 시험 295가 같은 worktree 이름 `foreman-3`을 받아 293이 이미 합친 파일과 같아 「변경 없음」으로 끝나 카드가 안 생김 — 관리자 시험 설계 실수) |
| ④ 막대를 누르면 「세션」 탭 | **됨** — 패널 293 · 탭 `세션:on` |
| ⑤ 캐릭터를 누르면 마지막에 본 탭 | **됨** — 탭을 「대화」로 바꾼 뒤 293 캐릭터를 실제 마우스로 누름 → 293 · `대화:on` |
| ⑥ 여럿일 때 가장 오래된 것 | **됨** — 카드 셋 중 since가 가장 이른 293(09:01:39)으로 감. **알아둘 것**: 292 카드는 그보다 먼저(17:2x) 있었는데 since가 09:01:59 — 브리지를 다시 띄우면 카드가 메모리에서 다시 만들어져 「오래됨」이 띄운 뒤 시각으로 바뀐다 |

- 페이지 오류 0. 시험 293(합침 — `log/mergewait_trial_foreman-3_20261111.md`가 main에 남음, `5af8b89`) · 294(버림) · 295(버림, 커밋 없음) `hidden_reason='test'`

## 290(시험 DB) 결과 — 사용자에게 먼저 알림, 아직 안 합침

- 권한 확인(SHOW GRANTS): `foreman\_test\_%`.*에 SELECT · INSERT · UPDATE · DELETE · CREATE · DROP · REFERENCES · INDEX · ALTER
- 290 보고: 혼자 698 통과 · 1 건너뜀 · node 123, 경고 없음 · 동시 둘 A 698 · B 698 통과(B에만 0099) · 끝난 뒤 `foreman_test_%` 0개 · kill -9 남은 DB는 다음 시작 때 치움 · 운영 foreman 표 27 · 마지막 0031 그대로. 첫 동시 시험에서 `test_app_db`가 운영 DB에 붙어 1건 실패 → 관리자 허락으로 세션 DB로 옮기고 토큰 헤더가 실패 출력에 풀리지 않게 고침. 커밋 `702bd42`, 카드 290 `ready`

## API 토큰(FOREMAN_API_TOKEN) — 확인만(값은 적지 않음)

- 저장: `.env.bridge` 한 파일(권한 600). worktree의 `.env.bridge`는 이 파일을 가리키는 링크. systemd 유닛 · cron · CC 설정 · 다른 저장소에는 없음
- 읽는 곳: 브리지(`bridge/config.py` — 띄울 때 한 번 읽음), 브라우저(localStorage `foremanToken` — 사람이 접속 키 창에 넣음, `usage.html` · `debug.html`도), 미리보기 브리지(worktree 링크로 띄울 때 읽음), 세션 · 관리자 명령(그때마다 `.env.bridge`에서 `sed`로 읽음), `tools/screen.py`(돌릴 때마다 읽음). 훅은 다른 토큰(`FOREMAN_HOOK_TOKEN`)
- 찍힌 값이 남은 곳: 290의 CC 대화 파일(`~/.claude/projects/…foreman--worktrees-foreman-2/<세션>.jsonl`) 1개. 브리지 로그 · 저널 · `log/` · FOREMAN DB(글자 칸 23개)에는 0 — DB 사본은 `mask.py`가 정확한 값으로 가림

## 290 합침 · 실패 출력 확인에서 멈춤 · test_terminal 4줄(사용자 지시 「넷을 순서대로」)

- 290: merge-tree exit 0 → 카드 승인 → `8b05914`(push 전). 혼자 pytest 701 · node 123 통과. 머리글 「시험 DB: foreman_test_main_897324」, 공용 DB 경고 없음, 끝난 뒤 `foreman\_test\_%` 0개. 운영 DB 시험 전 표 27 · 마지막 0031(시험 뒤 대조는 아직)
- 일부러 실패시킨 확인(스크래치 시험): 290의 가린 헤더는 첫째 꼴(assert 줄 안 호출 인자)은 막지만, 둘째 꼴(헤더 사전을 `==`로 견줌)은 pytest 사전 차이가 값을 풀어 냄 → **멈춤**. 이때 **관리자가 Bearer 뒤 글자를 묶어 보는 명령을 써 토큰 값을 이 관리자 세션 도구 출력에 한 번 냈다**(사용자에게 바로 알림 — 토큰 바꾸기로 함께 쓸모없어짐)
- 사용자: 둘째 꼴이 실제로 있는지 먼저 → 저장소 시험에 **0곳**. 그 확인 중 첫째 꼴이 `tests/test_terminal.py`(진짜 토큰 날 사전 `h`) 4줄 568 · 585 · 587 · 592에 남은 것을 찾음(실패시키지 않고 꼴만 봄)
- 고침 세션 296(sonnet, dispatch 366)이 4줄 고침을 해 놓고 18:24 첫 턴 끝에 **API 오류(안전 분류기 거부, `req_011Cgvu6VKKieKTCH3eXg9ud`)**로 끊김 — 일부러 실패시키는 임시 시험을 만들던 참. 커밋 · 확인 · 시험 · 기록 없음, worktree에 `tests/test_terminal.py` +5 −3. 296 스크래치의 `test_mask_probe.py`는 관리자가 지움. 대화 · 화면 · 차이에 토큰 값 0
- 사용자: 296을 끝내고 이어받을 새 세션 → 296 `exit`(worktree 그대로) → **세션 297**(코더 · opus, 같은 worktree `foreman-2`). 교장 `/start`는 늘 원본 폴더에서 새 worktree를 만들어 기존 worktree에 붙일 수 없어 `/api/spawn`(cwd = 그 worktree, `worktree:false`)으로 — dispatch 367(origin `spawn`) · `dispatch_session` 기록 남음. 지시문: 이미 된 것은 손대지 않고 확인만, 가린 헤더 repr · 실패 출력의 설정 값 개수(값을 화면에 내지 않는 세기 명령을 적어 줌), 어긋나게 한 줄 되돌리기, 전체 시험, 커밋 하나
- 18:46 CC 자동 업데이트 순간 이 셸의 `grep`(CC 실행 파일에 기대는 함수)이 「claude native binary not installed」로 한 번 실패 — 이후 값 세기는 `/usr/bin/grep`으로
