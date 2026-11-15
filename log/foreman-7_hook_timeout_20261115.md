# hooks 견본 승인 한도를 실제 설정에 맞춤 (foreman-7, 11-15)

## 한 일

- `deploy/hooks/foreman-hooks.json` PermissionRequest `timeout` 900 → 3660
- `tests/test_hook_timeouts.py` 새로 씀: 브리지 `wait_s` < 스크립트 curl `max` < 견본 hook `timeout`을 저장소 안 값끼리 맞댐. 견본을 900으로 되돌려 보니 시험이 깨졌고(`wait_s=3600, curl max=3630, 견본 hook timeout=900`), 3660으로 돌리자 통과

## 3660이 어디서 오는가

세 값이 겹쳐 있고 각 단계가 30초씩 여유를 둔다(기록 `log/stage13_demo_capture_result.md` 43줄: 승인 대기 10분 → 60분).

| 값 | 자리 |
|---|---|
| 3600 | `config/approval.toml` `[defaults] wait_s`(브리지가 브라우저 결정을 기다리는 시간) |
| 3630 | `scripts/foreman-decide.sh` permission `max`(curl 한도, wait_s보다 30초 길다) |
| 3660 | CC hook `timeout`(max보다 30초 길다) |

견본이 900이면 다시 깔았을 때 CC가 15분에 훅을 끊고 브리지만 계속 기다린다.

## 지금 값(시험 밖, 읽기만)

- `~/.claude/settings.json` PermissionRequest `timeout` = 3660(지금 이 기계). 홈 설정은 기계마다 달라 시험에 넣지 않았다
- 견본 3660, `wait_s` 3600, `max` 3630

## 확인 체크리스트

- [x] 견본과 실제 설정 값이 같은가: 같다(3660 = 3660)
- [x] 어긋나면 깨지는 시험이 추가되었는가: `tests/test_hook_timeouts.py`. 단, 견본 ↔ 홈 설정은 맞대지 않고 견본 ↔ 브리지 설정 ↔ 스크립트 순서만 본다
- [x] 다른 곳에 같은 숫자가 박혀 있지 않은가: 아래 표

## 같은 숫자 grep 결과

| 곳 | 값 | 뜻 | 처리 |
|---|---|---|---|
| `config/approval.toml` 28~30줄 주석 | 3600 | 승인 한도 | 이미 맞음. 바꾸면 스크립트와 견본도 함께라는 주석이 있음 |
| `scripts/foreman-decide.sh` 13줄 | 3630 · 3660 | 승인 한도 | 이미 맞음 |
| `bridge/config.py` `turn_abandon_s` 3600 | | 턴 포기 한도 | 다른 뜻, 그대로 |
| `bridge/config.py` 12 * 3600 | | 쿠키 12시간 | 다른 뜻, 그대로 |
| `bridge/notify.py` `[:900]` | | 알림 글자 수 | 다른 뜻, 그대로 |
| `docs/11_foreman_dispatch.md` · `docs/operations.md` · `bridge/handover.py` 15분 | | 계획 넘김 대기 · 백그라운드 조용함 | 다른 뜻, 그대로 |
| `log/bg_long`, `log/foreman-3_*` 등의 `timeout 900` | | pytest 감시 한도 | 다른 뜻, 기록이라 그대로 |
| `README.md` 239줄 | 2초 | foreman-hook.sh 한도 | 승인 한도 아님, 그대로 |
| `notion/04_approval/02_flow.md` 207줄, `notion/02_ingest/02_hooks.md` 136줄 | 900초 | 견본이 어긋나 있다는 글 | 이제 사실이 아님 → 서기 몫 |

## 서기 몫

- `notion/04_approval/02_flow.md` 207줄 근처, `notion/02_ingest/02_hooks.md` 136줄 근처: 「견본이 아직 900초」 문단을 지우거나 「맞췄고 시험이 지킨다」로 고친다. `notion/04_approval.md` 109줄 근처 서술도 함께 본다
- `docs/operations.md` · `docs/style_guide.md`는 이 일감에서 건드리지 않았다. 견본 값을 말하는 곳은 없었다

## 확인

- `.venv/bin/python -m pytest -q`: 1062 통과 · 1 경고
- `node --test tests/js/`: 209 통과 · 0 실패
- 브리지를 다시 띄우지 않았고 `~/.claude/settings.json`은 읽기만 했다. push 안 함

## 규칙 위반

1건. 시험을 만든 직후 `/dev/null`에 `sed -i.bak ...`를 잘못 쳤다(Bash로 파일을 고치지 않는다는 규칙). 대상이 `/dev/null`이라 `sed: couldn't edit /dev/null: not a regular file`로 실패했고 아무 파일도 바뀌지 않았다. 불필요한 명령을 붙여 넣은 실수다. 그 뒤 값을 바꿀 때는 모두 Edit로 했다.
