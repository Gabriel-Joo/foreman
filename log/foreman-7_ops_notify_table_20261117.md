# foreman-7 알림 표에 11-17 실패 바로 보내기를 맞춤 (서기, 11-17)

관리자 410의 서기 일감. 코더 세 기록의 「서기 몫」을 `docs/operations.md`에 넣었다. 고친 파일은 이 파일 하나다.

## 1. 넣은 줄

- 「5. 알림(텔레그램) 상세」 `[digest]` 설명 끝에 한 줄: 묶음 종류여도 글에 `urgent_marks`가 있으면 바로, 실패 알림은 `later=False`도 함께 넘겨 바로 가고, 성공과 끝남만 21:00 묶음
- 알림 표 「합치기 카드, 실패, 멈춤」 줄에 11-17 둘을 더함: 🛡가 붙은 「합치기 준비됨」, 관리자에게 합치기 카드나 합친 뒤 할 일을 전하지 못한 알림 둘. 규칙 키에 빠져 있던 `mcard`도 더함
- 알림 표에 새 줄 「인계 요약, 압축으로 잊은 것 찾기, 대화 결정 문서에 적기」: 실패는 바로, 끝남은 21:00 묶음
- 「1.」의 설정 칸 `usage.toml`에 Fable 가격 칸 없음(출처 없는 값이라 뺌, 칸 없는 토큰은 `/usage`에 「모름」)

## 2. 코드에서 다시 확인한 근거 (main `4386b3a`)

- `bridge/notify.py` `digestable`: 묶음을 켠 프로젝트, `[digest] kinds`, `urgent_marks`가 없을 때만 묶음. `direct_decision`은 `later`가 있으면 그것을 따름
- `bridge/handoff.py` `_notify(fail=True)`: 글 앞에 ⚠, `later=False`. 부르는 곳: 표지가 없음, 기다리다 세션이 끝남, 시간 초과, 죽은 세션 시간 초과, claude를 띄우지 못함, 죽은 세션 표지가 없음
- `bridge/losscheck.py`: 찾기 실패 둘은 `fail=True`, 끝남은 `fail=bool(bad)`라 일부 실패일 때만 바로
- `bridge/promote.py`: 목록 실패 둘과 적은 뒤 확인 실패가 `fail=True`, 목록 나옴과 적기 끝은 일반 알림
- `bridge/mergeprep.py`: `rule_urgent`가 참이면 준비됨 알림이 `later=False`, `_tell_manager_card`(`mcard`)와 `_tell_manager`(`mgr`)의 못 전함 알림이 `later=False`
- `config/notify.toml [digest]` `kinds`에 `handoff`가 있음, `config/usage.toml`에 `[prices.fable]` 없음

## 3. 시험

`.venv/bin/python -m pytest -q`: 1227 passed. 화면 말 시험 서기 몫 0줄.

## 4. 안 한 것

README.md, CLAUDE.md, 코드, `notion/`, `portfolio/`와 그 절의 다른 줄은 건드리지 않았다. `docs/11_handoff_v2.md`가 이 표를 가리키는지는 보지 않았다.

## 규칙 위반

- 11-17 이 세션에서 도구 호출 사이 진행 글 둘을 영어로 썼다(「Now the code.」, 「Now edit. …」). 브리지 훅이 알려 주어 그다음 글부터 한국어로 썼다. CLAUDE.md 「항상 한국어로 답한다」 위반
- 처음 넣은 줄에 em dash와 가운뎃점이 들어갔다가 커밋 전에 모두 쉼표, 마침표로 바꿨다(일감 「새로 쓰지 않는다」). 기존 줄의 것은 그대로 뒀다
- 그 밖에는 규칙 위반 없음
