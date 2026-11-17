# 실패 알림은 바로, 출처 없는 Fable 가격은 비움 (foreman-5, 2026-11-17)

관리자 410의 코더 일감(사용자 지시 11-17). 앞선 기록: `log/foreman-5_bridge_oddities_fix_20261117.md` 「3.」(511이 찾고 고치지 않은 것).

브랜치 `cc/foreman-5`, 커밋 셋(push 안 함, 브리지 다시 띄우지 않음).

| 커밋 | 제목 |
|---|---|
| `e691c9a` | fix: 인계 요약 실패 알림을 묶지 않고 바로 보냄 |
| `aa59fc0` | fix: 출처 없는 Fable 가격을 지우고 모름으로 표시 |
| (이 기록) | docs: 실패 알림과 Fable 가격 비움을 기록함 |

## 1. 실패 알림은 바로

### 1-1. 한 곳에서 지키는 방법과 판단 근거

- 「실패는 바로」는 이미 한 곳에 있었다. `bridge/notify.py` `digestable`이 글에 `[digest] urgent_marks`(⚠ ❌ 🛑 ⏰ ❓)가 있으면 묶음으로 미루지 않는다. 묶음 종류의 실패 알림 가운데 이 표시가 없던 것은 인계 요약 둘뿐이었다(아래 1-3 표)
- 그래서 새 규칙을 더하지 않고, 실패 알림이 그 중앙 규칙에 걸리게 했다. `HandoffManager._notify(fail=True)`가 글 앞에 ⚠를 달고, 511과 같은 꼴로 `later=False`도 함께 넘긴다. 둘을 함께 쓰는 까닭: ⚠는 사람이 텔레그램에서 실패를 한눈에 알게 하고, `later=False`는 글이 나중에 바뀌어도 바로 가게 한다
- 글 낱말(「실패」, 「시간 초과」)로 중앙에서 가르는 길은 쓰지 않았다. 묶음 종류 `turn`은 세션 응답 글을 그대로 싣는데 성공 보고에도 「실패」가 흔히 나온다. 기계가 만든 글에도 「실패 0」 같은 꼴이 생길 수 있다
- `send_direct`의 판정을 `Notifier.direct_decision`으로 꺼냈다(동작은 같다). 시험이 실제 판정 함수를 부르게 하려는 것이다
- `config/notify.toml`은 바꾸지 않았다(사람 승인 카드 없음)

### 1-2. 바로 가게 바꾼 알림

| 파일 | 글 요지 | 종류 | 전 |
|---|---|---|---|
| `bridge/handoff.py` `_wait_live` | ⚠ 인계 요약 실패, 표지가 없습니다(원문은 패널에) | handoff | 묶음(⚠ 없음) |
| `bridge/handoff.py` `_wait_live` | ⚠ 인계 요약 시간 초과, N초 안에 돌아오지 않았습니다 | handoff | 묶음(⚠ 없음) |
| `bridge/handoff.py` `_wait_live` | ⚠ 인계 요약 실패, 기다리는 중에 세션이 끝났습니다 | handoff | **알림 없음**(조용한 실패) |
| `bridge/handoff.py` `_run_headless` | ⚠ 죽은 세션 인계 요약 시간 초과 | handoff | **알림 없음** |
| `bridge/handoff.py` `_run_headless` | ⚠ 죽은 세션 인계 요약 실패, claude를 띄우지 못했습니다(예외 이름) | handoff | **알림 없음** |
| `bridge/handoff.py` `_run_headless` | ⚠ 죽은 세션 인계 요약 실패, 표지가 없습니다(종료 코드) | handoff | **알림 없음** |

- 알림이 없던 넷은 요약이 뒤에서 돌아 버튼을 누른 사람이 화면을 떠났으면 아무도 몰랐다. 「실패는 바로 안다」에 들어 함께 더했다
- 요청을 입력 칸에 넣지 못한 실패(`request_live`의 「보내지 못함」, 「제출이 확인되지 않았다」)는 API가 부른 쪽에 바로 돌려주므로 알림을 더하지 않았다

### 1-3. 묶음 종류 알림을 모두 읽은 결과

| 종류 | 실패 알림 | 판정 |
|---|---|---|
| turn | API 오류, 중단, 세션 종료, 프로세스 사라짐 | 이미 바로(`URGENT_REASONS`, `bridge/notify.py` `_emit_turn`) |
| batch | 서브에이전트 failed가 하나라도 있으면 | 이미 바로(`_batch` 「failed」 판정) |
| merge | 준비 실패, 합치기 실패, 승인 뒤 멈춤, 충돌 풀기 못 보냄, 스스로 합치지 않음, DB 쓰기 못 함 | 이미 바로(글에 ⚠). 관리자에게 못 알림 둘은 511이 `later=False` |
| handoff | 위 1-2 | **이번에 바로** |
| docsync | ⚠ Notion 기술문서 자동 게시 실패, ⚠ Notion 게시 설정(`bridge/notioncfg.py`) | 이미 바로(글에 ⚠) |
| recon | 없음(아래 1-4) | 묶음 그대로 |

### 1-4. 묶음으로 둔 것과 까닭

- **성공, 진행 알림**: 「인계 요약 저장」, 「죽은 세션 인계 요약 저장」, 「새 세션에 인계 넣음」, 「⑂ 합치기 준비됨」(🛡나 ⚠ 사람 승인 줄이 없을 때), 턴 끝, 서브에이전트 묶음(실패 없음). 지시대로 묶음
- **docsync ✋ 「사람이 고친 곳이 있어 덮지 않았습니다」**: 실패가 아니다. 사람이 Notion에서 고친 것을 지키려고 브리지가 일부러 덮지 않은 것이고, 할 일(git에 옮기거나 [Notion 수정 버리고 덮기])은 서기실 할 일 목록에 남는다. 늦게 봐도 잃는 것이 없다. 사람이 볼 목록이라 묶음 그대로
- **recon 🧹 「끝난 뒤 어긋난 것」**: 실패를 알리는 것이 아니라 끝난 뒤 남은 정리 거리(커밋 안 된 worktree, 남은 폴더나 브랜치)를 훑은 목록이다. `bridge/reconcile.py`는 고치거나 지우지 않으므로 기다리는 동안 사라지는 것이 없고, 코더 패널 「맡길 일」에도 보인다. 세션이 실패한 순간의 알림은 따로 있다(턴 끝 process_lost 등, 바로). 묶음 그대로
  - 다만 `dirty`(끝난 세션의 worktree에 커밋 안 된 변경)는 「세션이 일을 마치지 못하고 끝났다」로도 읽힌다. 사람이 그 뜻으로 보고 바로 받기를 원하면 `reconcile.py`가 `dirty`만 ⚠를 달면 된다(이번에는 하지 않음)

## 2. Fable 가격

### 2-1. 출처 확인 결과

- `git log -S'[prices.fable]'`: 처음 들어온 커밋은 `5958940`(11-08 「feat: 사용량 한도를 읽어 하한을 셈하고 /api/usage로 내보냄」, 옛 이름 `8b73d61`). 본문에 Fable 가격 출처가 없다
- 주석: `config/usage.toml`에 Fable 줄 출처 주석이 없었다
- log, docs: `log/stage15_usage_result.md`는 Fable %만 적었다. `log/foreman-4_docs_four_sync_20261117.md`, `log/foreman-8_doc_drift_20261116.md`, `docs/15_usage.md` 모두 「확인 못 함」. `log/foreman-3_model_menu_20261114.md`는 이 표를 근거로 「가장 비싸고」를 썼다(출처가 아니라 이 표를 쓴 곳)
- 결론: **네 칸(input 10, output 50, cache_read 0.25, cache_write 20) 모두 출처 없음** → `[prices.fable]`을 통째로 지우고 그 자리에 까닭 주석
- 참고(값을 넣지 않음): 이 세션의 claude-api 스킬 표(11-03 캐시)는 Fable 5와 5.1을 입력 $10, 출력 $50, Fable 5.2를 입력 $8, 출력 $40, 캐시 읽기 $0.20으로 적는다. 캐시 쓰기는 없다. `config/usage.toml`의 `fable`은 버전을 가리지 않고 걸리고, `config/models.toml`이 띄우는 Fable은 5.2라 옛 네 칸은 5.2 값과도 맞지 않는다. 어느 값을 넣을지는 사람이 정할 일이라 칸은 비워 두었다

### 2-2. 빠진 칸을 0원으로 세지 않게

- `bridge/usage.py`: `UsageConfig.usd`는 칸이 있는 토큰만 더한다(전에는 `p.get(k, 0.0)`으로 빠진 칸을 0원으로 더했다). 새 `UsageConfig.unpriced(model, t)`가 칸이 없는 토큰을 종류마다 센다. 표에 없는 모델은 토큰 전부가 「모름」이다(전에는 조용히 0)
- `breakdown`: 표 줄마다 `unpriced`(`{종류: 토큰}`), 맨 위 `unpriced`(`[{model, kind, tokens}]`). `limit_status`: 한도마다 그 창의 `unpriced`(새 `window_unpriced`). `bridge/api/usage.py`: `recent.unpriced`도
- `bridge/static/usage.html`: 위 띠 「환산이 일부 빠졌습니다. 가격 출처가 없는 칸은 0원으로 세지 않고 「모름」으로 둡니다: …」, 세션, 프로젝트, 모델 표와 한도 카드 「FOREMAN이 본 것」의 금액 옆 「+ 모름」(호버에 빠진 토큰)
- 영향: 「주간 · Fable」 한도는 FOREMAN이 본 금액이 0이 되어 하한, 추정 %, 「이 속도면 언제 100%」를 셈하지 않는다. 측정 %는 그대로 /usage에서 읽는다. 머리 칩(`/api/usage/brief`)은 % 만 쓰므로 바뀌지 않는다. 지난 관찰(`usage_observation.seen_usd`)에 이미 들어간 옛 Fable 값은 그대로 남는다(지우지 않음)
- 화면 말을 바꾼 것이 아니라 새 글을 더한 것이라 `tests/data/screen_words.toml`에 줄을 넣지 않았다

## 3. 원고가 다시 볼 곳 (`notion/`, `portfolio/`는 건드리지 않음)

- `notion/13_usage.md` 57줄 환산 표 Fable 줄 `10 | 50 | 0.25 | 20` → 「출처 없음」, 그리고 「모름」 표시(`docs/15_usage.md` 2절)
- `notion/13_usage.md` 224줄과 모델 메뉴 글 「가장 비싸고, 주간 한도가 따로 있습니다」(`log/foreman-3_model_menu_20261114.md`)는 지운 가격표를 근거로 썼다. 화면 글은 코드라 이번 범위에서 고치지 않았다. 관리자 판단

## 4. 서기 몫 (`docs/operations.md`, `docs/style_guide.md`)

- `docs/operations.md` 「5. 알림(텔레그램) 상세」 표에 인계 요약 줄이 없다. 「인계 요약 실패, 시간 초과(세션 끝남, 죽은 세션 포함) | `bridge/handoff.py`, 종류 `handoff` | 묶음을 켠 프로젝트여도 바로(⚠, `later=False`), 성공은 21:00 묶음」을 더할 것. 같은 절 `[digest]` 설명에 「묶음 종류여도 실패는 ⚠로 바로」를 한 줄
- `docs/operations.md` 27줄 「설정」의 `usage.toml`에 「Fable 가격 칸 없음(11-17, 출처 없음), 칸 없는 토큰은 /usage에 「모름」」

## 5. 시험

- 새 `tests/test_fail_now_unpriced.py` 여섯: 묶음 종류마다 실패는 바로, 성공은 묶음(handoff, docsync ✋, recon, merge, 묶음 안 켠 프로젝트) / `HandoffManager._notify` 실패는 ⚠와 `later=False` / `_wait_live` 시간 초과와 세션 끝남이 바로 나감 / 빠진 칸이 0이 아니라 unpriced / DB에 Opus와 Fable 행을 넣어 `breakdown` 합이 Opus만이고 Fable이 unpriced, `limit_status` 창의 unpriced
- `.venv/bin/python -m pytest -q`: 1195 passed
- `node --test tests/js/`: 218 pass, 0 fail
- `bridge/static/usage.html` 스크립트 문법: `node -e`로 `new Function` 확인(파일을 만들지 않음)

## 6. 알릴 것

- 브리지를 다시 띄워야 반영된다(`bridge/handoff.py`, `bridge/notify.py`, `bridge/usage.py`, `config/usage.toml`)
- Fable 가격을 넣을지, 넣는다면 어느 출처의 어느 버전 값인지는 사람이 정한다(2-1 참고)

## 규칙 위반

- 11-17 이 세션에서 도구 호출 사이 진행 글 하나를 영어로 썼다(「Now let me check the test helpers …」). 브리지 훅이 바로 알려 주었고 그다음 글부터 한국어로 썼다. CLAUDE.md 「항상 한국어로 답한다」 위반
- 그 밖에는 규칙 위반 없음
