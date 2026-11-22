# 포트폴리오 「셸 패널」 고쳐 쓰기 (2026-11-22, foreman-4 서기)

규칙 위반 없음.

## 한 일

- `portfolio/13_shell.md`의 읽은 커밋을 `b43e598`에서 `1a18e48`로 올렸다
- 「결과가 그 세션에 돌아간다」 둘째 문단에 결과 전달 판정을 더했다. 입력 칸이 비면 전달한 것으로 보고(`inject.submitted`), 2분 뒤에도 기록에 없으면 결과 띠를 「세션에 전달 못 함: 늦게 다시 봐도 세션 기록에 없다」로 바꾼다. 입력 칸에 글이 남은 경우의 까닭 글도 적었다. 늦은 확인의 설명은 「세션 패널: 대화와 활동」을 가리켰다
- 사진 `13_shell_bar.png`, 영상 `13_shell_request.gif`는 그대로 쓴다. 읽은 커밋 뒤 바뀐 코드는 `92eae54`의 `bridge/terminal.py`뿐이고 `bridge/static/js/terminal.js`는 바뀌지 않았다. 막대 사진은 열어 보았다

## 축

화면 축. 근거: `bridge/static/js/terminal.js`(셸 막대와 부탁 띠를 그리는 화면 js), `portfolio/img/13_shell_bar.png`(`tools/screen.py`로 찍은 화면)가 있다.

## 확인

- `tools/docs.py check`: 틀린 것 0
- 결과 띠가 「늦게 다시 봐도 세션 기록에 없다」로 바뀌는 실제 화면은 보지 않았다(코드로만 확인)
