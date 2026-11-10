# 한국어 훅이 모델 글을 따옴표로 되돌리지 않게 (11-10, 코더, 관리자 244)

## 바꾼 것
- `scripts/korean-check.py`: 알림에서 인용(`snippet`)을 뺐다. "직전 진행 글이 영어였습니다"만 알린다. 판정 · 한 번만 · 실패해도 조용히는 그대로. 모듈 docstring에 11-10 까닭 한 줄
- 상태 폴더는 환경 변수 `FOREMAN_KOCHECK_STATE`로 바꿀 수 있다(없으면 기본 `~/.cache/foreman-kocheck`)
- 새 시험 `tests/test_korean_check.py` 3개: 영어 글 → 알림이 나오고 글의 낱말이 출력에 없음 · 한글 글 → 출력 없음 · 같은 uuid는 두 번째에 출력 없음

## 시험
- `tests/test_korean_check.py` 3 passed (전체 시험은 관리자가 합친 뒤)

## 남은 것
- README 「나중에 할 일」 줄은 그대로 둠 — 합친 뒤 sonnet이 더는 막히지 않는지 관리자가 확인
