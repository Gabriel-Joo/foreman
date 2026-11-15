# 화면 말 시험이 `[code:…]`를 단추로 읽던 것 고침 (11-15, foreman-6)

## 한 일
- `tests/screen_words.py` `buttons_in`이 근거 표시를 빼는 줄을 `^(?:log|c|docs|t):` 정규식에서 `bridge.evidence.MARK`로 바꿨다. `code`가 목록에 없어 `[code:경로:줄-줄]`가 단추로 읽혔다
- 손으로 `tests/screen_words.py`를 돌릴 때도 `bridge`를 가져오도록 파일 위에서 저장소 뿌리를 `sys.path`에 넣었다
- 시험 `test_evidence_marks_are_not_buttons` 추가: `[code:…]` `[c:…]` `[t:…]` `[log:…]` `[docs:…]`는 안 나오고 `[Notion에 올리기]`는 나온다

## 같은 목록이 다른 곳에 있는지
- `bridge/evidence.py`의 `MARK`가 근거 표시 이름(c · t · log · docs · code)의 유일한 정의다
- `bridge/manuscript.py`에는 이름 목록이 없다(`evidence`를 쓰거나 따로 두지 않는다)
- `tests/screen_words.py`의 `_REF_DEF`는 `[이름]: 주소` 형태의 링크 정의 줄을 빼는 것이라 근거 표시 목록과 무관하다
- 그래서 시험 쪽 중복은 `MARK`를 가져오는 것으로 한 곳에 모았다. 앞으로 근거 표시 이름이 늘면 `MARK`만 고치면 된다

## 확인
- `.venv/bin/python -m pytest -q`: 1061 통과. `node --test tests/js/`: 209 통과. 브리지는 다시 띄우지 않았다
- 원고(`notion/`, `portfolio/`)는 고치지 않았다

## 규칙 위반 없음
