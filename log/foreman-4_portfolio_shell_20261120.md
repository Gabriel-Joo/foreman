# 포트폴리오 「셸 패널」 맞추기 (2026-11-20, foreman-4 서기)

맞대 본 main 커밋: `b43e598`

## 축과 근거

화면 축. 이 편이 다루는 화면이 `bridge/static/js/terminal.js`(화면 맨 아래 셸 막대, 부탁 띠, 결과 띠)로 있고, `tools/screen.py`로 찍을 수 있다.

## 바뀐 코드

머리 주석의 읽은 커밋 `5e0f7c5` 뒤 다루는 곳을 바꾼 커밋은 둘이다.

- `b6aebf9`: `bridge/terminal.py` docstring 한 줄의 「README 2.4」를 「docs/00_design.md 2.4」로 바꿨다
- `2203c57`: `bridge/terminal.py`, `bridge/api/terminal.py`, `deploy/shell/foreman-cc-view`의 주석, docstring, 로그 글에서 「CC 화면」을 「세션 화면」으로 바꿨다

둘 다 동작과 셸 화면 글은 그대로다. 원고는 「CC 화면」을 쓰지 않는다.

## 맞대 본 것

- 사람이 쳐야 하는 명령 목록 `HUMAN_CMD`, 부탁하는 말 `CUE`, 따옴표 인용 빼기 `_QUOTED`(terminal.py)
- 친 명령 맞대기: 비운 자리 앞까지 같거나 앞 세 낱말(`cmd_matches`)
- 결과 마지막 60줄(`terminal_output_lines`), 부탁 기다림 30분(`terminal_request_ttl_s` 1800초)
- 결과 머리 「[터미널 패널] 부탁한 명령을 사람이 터미널 패널에서 실행했다」, 결과 띠 「세션에 전달했다」(terminal.py)
- 화면 글: [셸 비우기], [▲ 위로], [▼ 아래로], [입력으로], 「부탁 N」, 미리 채움 안내 두 가지, 「미리 채우지 못했습니다」, [다시 채우기] [복사] [닫기](terminal.js)
- 편 사이 참조 「알려진 한계」(3절에 셸 패널 줄이 있다), 「세션 패널: 대화와 활동」, 편 끝 링크 `notion/03_session.md`
- 본문은 고칠 곳이 없었다

## 고친 것

- 읽은 커밋을 `b43e598`로
- 사진(`portfolio/img/13_shell_bar.png`, 11-19 찍음)은 그대로 쓴다. 그 뒤 화면 파일(css, index.html, terminal.js) 변경이 없고, 열어 보니 접힌 [▲ 셸] 막대와 패널 자리가 설명과 같다

`tools/docs.py check`: 틀린 것 0.

## 규칙

규칙 위반 없음.
