# 교장이 관리자 띄우기를 「사람이 정한 판단」으로 쓰게 (관리자 318 일감, 11-13 사용자 결정)

## 한 일
- `bridge/foreman.py` `INSTRUCTIONS` 9번 `note_updates`에 세 줄 추가: 역할 manager 세션을 띄우는 계획이면 thread를 쓰지 말고 decision 한 줄 「<프로젝트> 관리자가 있다(세션 N, 원본 폴더)」, 관리자가 바뀌면(옮기기 · 새로 띄움) 그 줄을 update, 관리자를 띄우며 다른 일도 맡기면 그 X만 thread
- 시험 `tests/test_instructions_manager_decision.py`(지시문 문자열 2개). 교장(LLM)은 부르지 않는다
- 시험 결과: pytest 전체 841 통과 · 1 건너뜀, `node --test tests/js/` 140 통과 · 0 실패

## 판단 근거
- **바꿀 곳은 지시문 한 곳뿐이다.** `notes.check_ops`(`bridge/foreman_note.py`)는 노트 제안 모양과 출처만 맞추는 함수이고, 계획의 세션 목록(role)을 받지 않는다. 자동으로 내리는 길(`manager_spawn_done`)은 건드리지 않았다(`config/wake.toml`에서 꺼진 채)
- **「manager 띄우기 + thread add」 경고는 더하지 않았다.** ① check_ops 안에서는 계획의 role을 몰라 호출부(`foreman.py` 543줄 근처)까지 고쳐야 한다 ② 관리자를 띄우면서 맡긴 다른 일의 thread는 정당해서 thread 글에 「관리자」가 들었는지로는 맞고 틀림을 못 가른다(오경고) ③ 경고는 막지 않는 표시일 뿐이라 지시문이 지켜지지 않을 때만 쓸모가 있다. 지켜지지 않는 일이 실제로 보이면 그때 계획 카드 `warnings`에 더한다
- 효과가 지시문에 달려 있고 LLM이 어길 수 있다는 점은 남는다. 어기면 thread가 생기고 「낡음」 표시 후 사람이 [내리기]하는 지금 길 그대로다

## 되돌리는 법
- `bridge/foreman.py`의 추가 세 줄과 시험 파일을 지운다(`git revert` 이 커밋). 브리지는 합친 뒤 원본 세션이 다시 띄워야 지시문이 바뀐다

## 규칙 위반
규칙 위반 없음. 파일은 Edit · Write로만 썼고, 진행 글도 한국어였다.
