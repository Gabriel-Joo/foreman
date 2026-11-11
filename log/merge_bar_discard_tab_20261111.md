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
