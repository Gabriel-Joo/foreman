# 시험이 실제 hook_miss.log를 더럽히던 것 고침 (foreman-5, 11-15)

## 무엇이 틀렸나
- 브리지 쪽 갈래를 가짜 예외로 부르는 시험(`tests/test_roleguard.py`의 역할 판정 예외 시험 등)은 기록 자리를 바꾸지 않았다. 그래서 pytest를 돌릴 때마다 실제 `.run/hook_miss.log`에 `bridge 역할판정예외 ZeroDivisionError` 줄이 생겼다.
- 이 파일은 갈래별 수를 세어 알림 문턱으로 쓸 재료라, 가짜 줄은 거짓 알림이나 거짓 통계가 된다.
- `tests/test_hookmiss.py`만 `miss_log` 고정물로 자리를 바꿨고 나머지 시험은 환경 변수를 정하지 않았다.

## 한 일
- `tests/conftest.py`에 모든 시험이 기본으로 받는 고정물 `_hook_miss_log_isolated`를 더했다. 환경 변수 `FOREMAN_HOOK_MISS_LOG`를 시험마다 임시 폴더로 정한다. 스크립트(`scripts/foreman-decide.sh`)를 하위 프로세스로 부르는 시험도 환경을 이어받아 같은 임시 폴더로 간다. 기록을 확인하는 시험의 `miss_log`는 이 위에 다시 덮어쓰니 그대로 돈다.
- `tests/test_hookmiss.py`에 시험 하나를 더했다. 기본 기록 자리가 실제 `.run`이 아닌지, 기록을 한 줄 남긴 뒤에도 실제 파일 크기가 그대로인지 본다.

## 확인
- `pytest -q` 1093 통과, `node --test tests/js/` 209 통과.
- 작업방에서 전체 시험을 돌린 뒤 원본 폴더 `.run/hook_miss.log`의 `ZeroDivisionError` 줄 수는 2로 그대로였다. 전체 줄 수는 27에서 48로 늘었는데, 그 사이 도는 다른 세션의 실제 훅이 남긴 줄이다(시험이 만든 것이 아니다).
- 실제 파일의 기존 줄은 지우지 않았다(관리자가 처리).

## 다른 시험이 실제 파일에 쓰는지 점검(grep)
| 대상 | 판단 |
|---|---|
| `.run/hook_miss.log` | 위에서 고침 |
| `.run/notion_repo_config.json` | `bridge/main.py`가 시작할 때 `root_dir/.run/`으로 정하는데, 전체 시험 뒤에도 수정 시각이 11-12로 그대로라 시험이 쓰지 않는다. 손대지 않음 |
| `.run/ttyd*.sock`, `ttyd*.log` | 시험이 쓰지 않음(수정 시각은 브리지 재시작 때). 손대지 않음 |
| 홈의 `~/.claude/...` | 시험의 `~/.claude` 글은 모두 승인 규칙이 막는지 보는 문자열이고 실제로 읽거나 쓰지 않는다. `test_app_db`는 와처를 꺼 둔다 |
| 그 밖의 `write_text` | 모두 `tmp_path` 아래 |

## 규칙 위반
규칙 위반 없음. (진행 글은 모두 한국어로 썼다. 훅이 영어였다는 알림을 한 번 보였으나 내가 쓴 글은 한국어였다.)
