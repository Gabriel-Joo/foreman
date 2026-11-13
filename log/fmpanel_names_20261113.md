# 교장 노트 패널 이름 둘 바꾸기 (11-13)

## 한 일
- `bridge/static/js/fmpanel.js`
  - 「자동으로 내린 줄 N」 → 「끝난 일 N」, 호버를 지시한 글로 바꿈
  - [되살리기] 호버와 확인 창을 「끝나지 않았으면 되돌립니다 — 다시 진행 중인 일로 두고, 다시 자동으로 내리지 않습니다」 뜻으로 바꿈
  - 「지난 계획 N」 → 「지난 요청 N」, 호버를 지시한 글로 바꿈
- `bridge/foreman.py` `restore_note`의 서버 거부 사유(화면에 뜨는 글)에 옛 이름이 있어 같이 바꿈: 「기계가 끝났다고 본 일이 아니거나 이미 되살렸습니다」
- `tests/js/fmpanel_notes.test.mjs`: 이름 기대값 갱신
- 상황 묶음 이름(`bridge/foreman_note.py`)과 `docs/14_dispatcher_note_wake.md`, 시험 `tests/test_note_auto_retire.py`의 주석은 범위 밖이라 두었다

## 조사: 화면 「지난 계획 8」 vs 상황 묶음 5건
- 같은 함수 `notes.recent_dispatches(c, project, limit)`를 두 곳이 다른 한도로 부른다
  - 화면(`bridge/foreman.py:861`): 8건
  - 교장 상황 묶음(`bridge/foreman.py:391`): 기본값 5건(`foreman_note.py:163`)
- 그래서 화면이 상황 묶음보다 3건 더 보인다. 버그가 아니라 한도 차이다. 어느 쪽에 맞출지는 정하지 않았다(범위 밖)

## 시험
- `node --test tests/js/`: 148 통과
- `pytest`: 856 통과, 1 건너뜀
- `tools/screen.py --views foreman --no-term --sizes 1366x768`(미리보기 8277): 세 테마 문제 0건, tipAudit 0/185~212
- 한계: 이 점검이 노트 패널의 `<details>`를 열어 둔 채 찍었는지는 확인하지 못했다. 바뀐 호버가 tipAudit에 들어갔는지는 보장하지 못한다. 관리자가 미리보기에서 눈으로 확인해 주십시오

## 규칙 위반 없음
