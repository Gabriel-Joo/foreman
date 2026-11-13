# 합치기 카드를 DB에 남기기 (11-13, 일감 B — 관리자 318 → 코더 foreman-3)

계기: 11-13 관리자가 319 카드를 승인해 합친 뒤 브리지를 다시 띄우자 카드가 사라져 정리 후보 6개를 못 봤다(카드는 메모리에만 있었다). 합친 뒤 브리지를 다시 띄우는 것은 정해진 절차라 늘 일어나는 조용한 손실이었다. 같은 뿌리: README 「나중에 할 일」 「오래됨」 시각 줄(11-11 292).

## 한 일

| 무엇 | 어디 |
|---|---|
| 표 `merge_card` — 세션 하나에 한 줄(`session_id` PK). 카드 전부(`Card`의 칸 = `view()`에서 `ff` · `head8`를 뺀 것)는 `card` JSON 한 칸에 넣었다. 고를 때 쓰는 `project` · `head` · `status` · `made_at` · `updated_at`만 칸으로 따로 뺐다 | `migrations/0032_merge_card.sql` |
| 맞춰 쓰기 `MergePrep.sync()` — 메모리 카드의 JSON을 지난번에 쓴 것(`_saved`)과 견줘 바뀐 카드만 upsert하고, 메모리에서 빠진 카드는 DELETE. 부르는 곳: 훑기 · 턴 끝 확인 · 승인(합치는 중 표시도 바로) · 미루기 · 관리자 알림 결과 · 버리기(`worktree_gone`은 예약만) | `bridge/mergeprep.py` |
| 되살리기 `MergePrep.restore()` — `run()` 맨 앞(첫 훑기 전)에 돈다. JSON 그대로 카드를 만든다(`Card.from_saved`, 모르는 칸은 버림). `made_at` · `updated_at` · 정리 후보가 그대로 남는다. 브랜치 끝 커밋이 바뀌었으면 다음 훑기의 `prep`이 지금처럼 다시 만든다(카드 생김 기록 · 알림도 그때) | 〃 |
| 끝난 카드 남김 — `updated_at`(DB에 남은 시각) 기준 `keep_h`(6). **합친 카드에 정리 후보가 남아 있으면 `keep_docs_h`(72)**. 치우면 DB에서도 지운다 | 〃 `_expired` |
| 조용한 고장 금지 — 쓰기 · 읽기가 실패해도 카드는 메모리로 돈다. 처음 실패할 때 텔레그램 한 번(`mergeprep:db:save|load:…`). 목록 `view()["store"]`와 `health.error`에 사유를 싣는다 — 패널 「합치기 승인」은 이미 `health.error`를 띄운다(`handoff.js` 50줄, 고치지 않음). 다시 되면 사유가 사라지고 밀린 카드를 쓴다 | 〃 `_store_bad` · `_apply_store_health` |
| 시험 10개 — 다시 띄운 것처럼 새 `MergePrep`을 만든다. 카드 · 정리 후보 · made_at이 그대로인지, 새 커밋이면 다시 만드는지, main만 앞서면 made_at을 잇는지, 합친 카드 남김(정리 후보 있음 7h 남음 · 73h 치움 / 없음 7h 치움), 합치는 중 → failed, 쓰기 실패(표 이름 바꿈) 알림 한 번 + 사유 + 회복, 읽기 실패, 설정 값 | `tests/test_mergeprep_db.py`(세션 시험 DB) |

시험: `pytest` 전체 806 통과 · 1 건너뜀, `node --test tests/js/` 128 통과. 시험 DB는 `foreman_test_foreman_3_<pid>`(세션 DB, 공용 경고 없음). 기존 `tests/test_mergeprep.py`는 가짜 `engine=None`이라 저장이 꺼진 채(`store.on = False`) 그대로 돈다.

## 설계와 달랐던 점 · 판단 근거

- **같은 커밋이면 main이 앞서 카드를 다시 재도 `made_at`을 잇는다**(브리지를 다시 띄운 경우만이 아니다). 전엔 main이 움직이면 카드가 새로 만들어져 「오래됨」이 다시 잡혔다. 「오래됨」은 사람이 기다린 시간이라 같은 일(같은 브랜치 끝 커밋)이면 잇는 것이 맞다고 봤다. 브랜치 끝 커밋이 바뀌면 지금처럼 새 시각이다
- **합치는 중(`merging`)에 브리지가 내려간 카드는 되살릴 때 `failed`로 바꾸고 「결과를 모릅니다」를 단다.** 그대로 두면 `prep`이 merging 카드를 늘 그대로 돌려줘 영영 멈춘다. 그래서 합치기 직전에도 DB에 쓴다
- 카드를 칸으로 쪼개지 않고 JSON 한 칸에 넣었다. `Card`에 칸이 더해져도 마이그레이션이 필요 없고, 되살릴 때 모르는 칸은 버리고 없는 칸은 기본값을 쓴다
- 바뀐 곳마다 저장을 부르지 않았다. 카드 칸을 고치는 곳이 여러 군데라(`c.status = …` · `c.note` · `c.manager_told` 등) 견줘서 맞추는 쪽이 빠뜨리지 않는다. 훑기(60초)마다 맞추니 빠진 곳이 있어도 1분 안에 따라온다
- 되살리기 전에는 `sync()`가 쓰지 않는다. 턴 끝 확인이 먼저 돌아도 DB에 남은 카드를 지우지 않게 하려는 것이다. 되살리기 전에 턴 끝이 만든 카드가 같은 커밋이면 DB의 `made_at`을 잇는다
- DB 실패 알림은 `_notify`의 「보낸 적 있나」 DB 확인을 건너뛰고(`check_db=False`) 메모리 표시로 한 번만 보낸다. DB가 문제인데 그 DB로 중복을 보면 안 보내질 수 있어서다
- `keep_h` · `keep_docs_h`는 `MergePrepCfg` 기본값으로만 더했다(`config/handoff.toml`은 안 고침 — 칸이 없으면 기본값). 바꾸려면 `[merge_prep]`에 적고 브리지를 다시 띄운다. `keep_docs_h < keep_h`면 ValueError
- 관리자에게 가는 합친 결과 글의 「6시간 남는다」를 「72시간 남는다 — 브리지를 다시 띄워도 DB에서 되살린다」로 고쳤다

## 정리 후보를 언제까지 두나 (할 일 3)

- 판단: 합친 카드에 정리 후보가 남아 있으면 **72시간** 둔다(그 밖의 끝난 카드는 지금처럼 6시간). 이제 브리지를 다시 띄워도 사라지지 않으니 6시간이 짧은 이유는 「관리자가 고를 시간」 하나뿐이다. 하룻밤 · 주말 하루를 넘기는 값으로 72를 골랐다
- 「관리자가 다 골랐다」를 알리는 신호는 없다. 지금은 시간이 지나야 치운다. 고른 뒤 바로 치우는 action(예: `{"action":"docs_done"}`)을 둘지는 **사람이 정할 것**이다(아래)

## 되돌리는 법

- 코드: 이 커밋 revert. 0031까지의 코드는 `merge_card` 표를 모르니 표는 남아 있어도 된다
- 표: `DROP TABLE merge_card;` + `DELETE FROM schema_migrations WHERE version = '0032_merge_card';`(코드를 먼저 되돌린 뒤)

## 운영 DB 적용 (관리자가 합친 뒤)

**브리지를 다시 띄우기 전에** 원본 폴더에서 적용한다. 순서가 거꾸로면 표가 없어 「합치기 카드를 DB에서 되살리지 못했습니다」 · 「DB에 남기지 못했습니다」 텔레그램이 한 번씩 나간다(카드는 메모리로 돈다 — 적용한 뒤 다음 훑기에서 저절로 쓴다).

```
.venv/bin/python -m bridge.db.migrate --status   # 0032_merge_card 대기 확인
.venv/bin/python -m bridge.db.migrate            # 적용
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user restart foreman-bridge   # 승인 대기 0 확인 뒤
```

확인: 띄운 뒤 journal에 `합치기 카드 0장을 DB에서 되살렸다`가 찍힌다(처음엔 0). 카드가 생긴 뒤 `SELECT session_id, status, made_at FROM merge_card;`로 줄이 있는지 본다. 다음에 다시 띄우면 그 장수가 찍힌다.
**이번 배포에서는 카드가 남지 않는다** — 지금 메모리에 있는 카드는 표가 생기기 전 것이라, 이 코드로 처음 다시 띄울 때 한 번 더 사라진다(그 뒤부터 남는다).

## 사람이 정할 것

1. `keep_docs_h = 72`가 맞는가(정리 후보가 남은 합친 카드를 두는 시간)
2. 「정리 후보를 다 골랐다」 action으로 바로 치울지. 지금은 시간이 지나야 치운다. 만들면 API(`bridge/api/handoff.py`) · 관리자 안내 글을 함께 고친다
3. DB 전체가 죽었을 때는 이 알림도 나가지 않는다. `notifier.send_direct`가 보내기 전에 `notification` 표에 먼저 쓰기 때문이다(적재 감시 등 다른 브리지 알림도 같다 — notifier 한계). 이 경우 텔레그램 없이 패널 사유만 남는다. `bridge.telegram`처럼 기록 없이 보내는 길을 notifier에 둘지

## README에서 뺄 줄

- 「브리지를 다시 띄우면 합치기 카드의 「오래됨」 시각이 다시 잡힌다」 — 카드가 DB에서 `made_at` 그대로 되살아난다. 같은 커밋이면 main이 앞서도 잇는다
