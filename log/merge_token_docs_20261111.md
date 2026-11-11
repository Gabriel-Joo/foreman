# 297 합침 · 290 마무리 · API 토큰 바꿈 · 292 합침 · 낡은 문서 서기 띄움 (2026-11-11 저녁, 원본 폴더, 관리자 276)

앞 기록: [merge_bar_discard_tab_20261111.md](merge_bar_discard_tab_20261111.md). 사용자 지시 「다섯을 순서대로」

## 하나 — 297 합침

- `cc/foreman-2` `b289eeb` 커밋 하나(`tests/test_terminal.py` +5 −3 · `log/test_terminal_bearer_20261111.md`). 차이에 설정 값 0(개수로만), merge-tree exit 0 → 카드 승인 → `3cb1787`
- main에 push 안 한 290이 함께 있어 297만 따로 push할 수 없다 → 둘의 운영 DB 대조를 먼저 하고 한 번에 push

## 둘 — 290 마무리

- 운영 DB 시험 전(표 27 · 마지막 `0031_handover_todo_edit`) = 지금(표 27 · 마지막 0031), 남은 `foreman\_test\_%` 0
- push `3cb1787`(290 `8b05914` · 기록 `a38dcf8` · 297) → 승인 대기 0 → **브리지 19:06:56**(794119 → 1189365), 오류 없음

## 셋 — API 토큰 바꿈(값은 어디에도 적지 않음)

- 미리보기 브리지: 없음(8200 포트는 `model-service` — 미리보기 아님)
- **Edit 도구로 `.env.bridge`를 고치면 새 값이 도구 입력으로 화면에 나온다** → 「값을 화면에 내지 마라」를 앞세워 스크래치 스크립트(파이썬)로: 승인 대기 0 확인 → 새 값(`secrets.token_urlsafe(32)`)으로 그 줄만 바꿈(권한 600 유지, 백업 파일 없음) → 바로 브리지 다시 띄움(1.5초) → **옛 값 401 · 새 값 200** → 해당 줄 1 · 옛 값이 파일에 남은 수 0. 새 값이 200이 아니면 옛 줄로 되돌리는 길을 넣었으나 쓰이지 않음. 「파일은 Edit · Write로만」 규칙과 어긋난 점을 사용자에게 알림
- 브리지 19:07:39(1193342), 「합치기 준비 켬」, 오류 없음, 브리지 로그에 새 값 0(개수)
- 마스킹(`bridge/mask.py`)은 브리지를 띄울 때 `.env.bridge`의 정확한 값을 읽으니 새 값도 가린다. worktree의 `.env.bridge`는 원본 링크라 따로 할 것 없음
- 브라우저 접속 키는 사용자가 다시 넣음

## 넷 — 292 합침

- `cc/foreman-4` 커밋 다섯(문서 넷 · 기록 하나), merge-tree exit 0. 브리지를 다시 띄워 카드가 메모리에서 사라져 있어 `refresh`로 다시 만든 뒤 승인 → `b436e69`(rebase 뒤 fast-forward), push. 문서 · 기록만 바뀌어 브리지는 그대로
- 합침 알림의 「고치지 않은 문서」 후보: `docs/style_guide.md` · `docs/12_scribe.md` · `docs/14_dispatcher_note_wake.md`

## 다섯 — 낡은 문서 서기 298(sonnet, dispatch 372, `.worktrees/foreman-2`)

- `docs/10_office_design.md` 151줄 부근: 막대 → 「대화 탭」이 아니라 「세션 탭」, 「버려도 최대 1분」이 아니라 「버리면 바로」(291)
- `docs/operations.md` 28줄 시험 줄: 세션마다 시험 DB(290 기록대로)
- tmux · systemd: 관리자가 본 것 — tmux `foreman-bridge`에는 11-06부터 빈 bash 하나만(서기 · 브리지 없음), 서기 · 코더는 `cc-<프로젝트>[-N]`에 뜸, 브리지는 systemd `active`. `docs/operations.md` 39줄 「서기 세션은 아직 tmux `foreman-bridge` 안에」가 낡음 — 298이 직접 다시 보고 맞춤
- **CLAUDE.md 48줄 「브리지(tmux `foreman-bridge`)」도 같은 낡음** — 서기 몫이 아니라 사용자에게 알림
- 문서마다 커밋 · 커밋만 · Edit · Write로만, ACTIVE 확인
