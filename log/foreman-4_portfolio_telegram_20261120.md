# 포트폴리오 「텔레그램 알림」 고쳐 쓰기 (foreman-4, 2026-11-20)

맞대 본 main 커밋: d6c1e82. 규칙 위반 없음.

## 축

화면 축. 근거: `bridge/static/`에 화면 html, css, js가 있고 `tools/screen.py`로 찍을 수 있다. 이 편이 보이는 화면은 감독실 교장 머리 위 「시작할 일 N」과 [시작] 링크가 여는 새 세션 창이다.

## 한 일

- 읽은 커밋(fb7121b) 뒤 다루는 곳을 바꾼 커밋은 b6aebf9 하나였다. `bridge/notify.py`, `bridge/wake.py` 주석의 「README 3.x」를 `docs/00_design.md`로 바꾼 것뿐이라 동작은 그대로다. 본문의 문턱(묶음 21:00, 26시간, 10분 다시, 12시간, 하루 5번, 펫퍼민트 5분)은 `config/notify.toml`, `config/wake.toml`과 맞았다.
- 「바로 가는 알림」 표에 코드에는 있고 표에 없던 바로 가는 알림 네 줄을 더했다: 권한 거부(`bridge/human_wait.py`), API 오류로 멈춤 N분째(`bridge/human_wait.py`), 세션 멈춤 ⏸(`bridge/stallwatch.py`), 스키마 잠금 🔒(`bridge/approvals.py`).
- 표 아래 문단에 권한 거부와 API 오류로 멈춤의 화면 쪽은 → 「머리 위 표시와 띠」, 압축 직후 알림은 → 「세션 정리: 인계와 옮기기」로 가리키는 말을 더했다.
- 머리 주석 읽은 커밋을 d6c1e82로 바꿨다.
- 사진 두 장(`15_telegram_suggest.png`, `15_telegram_plan.png`)은 찍은 커밋(0ba3538) 뒤 감독실과 새 세션 창 코드가 바뀌지 않았고, 열어 보아 비밀값이 없어 그대로 썼다.

## 확인

- `tools/docs.py check` 틀림 0, `tests/test_manuscript_rules.py`, `tests/test_screen_words.py` 58개 통과.

## 표에 넣지 않은 바로 가는 알림

겹침(`bridge/overlap.py`), 배포 대기(`bridge/pipeline.py`), 웹훅 끊김 의심과 빌드 끝 알림 없음과 감시 실패(`bridge/pipeline.py`), 맥락 크기와 넘어갈 때(`bridge/compactwatch.py`), 「!」 명령이 글로 들어감(`bridge/bang_watch.py`), 서기실 전체 줄 실패(`bridge/scribe_queue.py`), 조사 세션 끝내기 실패(`bridge/inspector_close.py`), Notion 게시 설정(`bridge/notioncfg.py`). 표가 모든 알림을 늘어놓는 자리는 아니라 넣지 않았다. 대신 표 머리 문단에 「표는 자주 받는 것을 모은 것」이라 적고 겹침과 감시 실패를 보기로 들었다(그 문장의 「모두 바로 간다」는 `config/notify.toml` [digest] 주석의 「kinds에 없는 종류 전부」가 근거다).
