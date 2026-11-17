# 브리지 쪽 이상해 보이는 곳 고치기 (foreman-5, 2026-11-17)

관리자 410의 코더 일감(사용자 지시 19 뒤 4번). 근거 기록: `log/foreman-4_docs_four_sync_20261117.md` 「3.」, `log/foreman-6_portfolio_scope_check_20261117.md` 「코드가 이상해 보이는 곳」, `log/foreman-5_notion_evidence_scope_20261117.md` 「코드가 이상해 보이는 곳」.

브랜치 `cc/foreman-5`, 커밋 다섯 개(push 안 함, 브리지 다시 띄우지 않음).

| 커밋 | 제목 |
|---|---|
| `e7b131f` | fix: 서기 말풍선 기준을 설정 파일 한 곳에서 읽게 함 |
| `26bfefb` | fix: 규칙 파일이 걸린 합치기 알림을 바로 보냄 |
| `ee1d57f` | fix: 교장 지시문의 서기 일 이름을 서기실 목록에서 만듦 |
| `8529d38` | refactor: 코더 맡길 일에서 늘 비어 있던 받은 할 일 칸을 뺌 |
| `fc2b57a` | docs: 낡은 주석과 설명 글을 지금 코드에 맞춤 |

## 1. 고친 것

### 1-1. `config/scribe.toml` 설정이 말풍선을 정하게 (`e7b131f`)

- 남긴 쪽: `bridge/postit.py` `conf`, `nudge_of`. 까닭: 서기 말풍선을 실제로 그리는 길(`postit.summary`가 `nudge_of`를 `cf` 없이 부름)이 이쪽이고, `scribe_room.nudge_of`는 시험만 불렀다
- `config/scribe.toml`: `[nudge]`(new_min 3, oldest_days 3)를 빼고 `[postit]`(open_max 20, stale_days 7, refresh_days 7)을 적었다. 값은 코드 기본값 `CONF_DEFAULT`와 같아 화면 문턱은 그대로다. 머리 주석도 지금 뜻(포스트잇 쌓임)으로 다시 썼다
- `bridge/scribe_room.py`: `NUDGE_FILE`, `NUDGE_DEFAULT`, `nudge_conf`, `nudge_of`를 지우고 한 줄 주석으로 어디로 갔는지 남겼다
- `bridge/postit.py` `conf`: 읽지 않는 표(`[postit]` 밖), 모르는 칸, 0 이상 정수가 아닌 값, 읽기 실패를 브리지 로그에 한 번씩 경고한다(전에는 모두 조용히 기본값). 파일이 없을 때는 경고하지 않는다(시험, 새 설치)
- 시험: `tests/test_postit.py` `test_scribe_toml_drives_nudge` 새로. 실제 파일의 표가 `[postit]` 하나이고 칸이 모두 코드가 읽는 칸인지, 파일 값이 기본값과 같은지(문턱 그대로), `CONF_FILE`을 바꾸면 `cf` 없이 부르는 `nudge_of`가 따라 바뀌는지, 옛 `[nudge]`와 틀린 값에 경고가 남는지. `tests/test_stage2_db.py`의 옛 `nudge_of` 시험 줄은 지웠다
- docs: `docs/12_scribe.md` 11-6 두 줄

### 1-2. 🛡 붙은 「⑂ 합치기 준비됨」을 바로 (`26bfefb`)

- `bridge/mergeprep.py`: `rule_urgent(card)`(규칙 파일이 바뀌거나 확인 못 함)를 두고, 참이면 「합치기 준비됨」을 `later=False`로 보낸다. 합친 뒤 🛡 알림(`kind=rulefile`, 묶음 종류가 아님)이 바로 가는 것과 같은 기준. 🛡 없는 카드는 전처럼 `later=None`(notifier가 정함)
- 같은 종류로 같은 파일에서 더 찾아 고친 것 둘(묶음 종류 `merge`, 급한 표시 없음, 사람이 움직여야 함):
  - `_tell_manager_card` 실패 알림 「관리자 세션에 합치기 카드를 알리지 못했습니다 … 패널에서 승인합니다」. 승인자가 사람으로 바뀌는데 21:00까지 미뤄지면 그동안 아무도 승인하지 않는다(승인 대기 알림이 바로 가는 것과 같게)
  - `_tell_manager` 실패 알림 「관리자 세션이 없어 텔레그램으로 남깁니다」. 끝난 세션의 충돌 풀기, 합친 뒤 시험과 push처럼 관리자 몫을 받을 곳이 없어 사람에게 넘기는 글이다
- 시험: `tests/test_mergeprep.py` `test_ready_notify_with_shield_is_not_digested`(규칙 파일 없음, 바뀜, 확인 못 함 세 갈래), `test_manager_unreachable_notify_is_not_digested`. 기존 `test_asks_card_shows_question_and_updates_in_place`의 `_notify` 가짜를 키워드 인자를 받게 고쳤다
- docs: `docs/11_worktree.md` 「규칙 파일 표시」 줄

### 1-3. 505 log 「3.」의 브리지 쪽

| 무엇 | 고친 것 | 커밋 |
|---|---|---|
| `scribe_room.start` later 거절 글(화면에 나옴) | 「포스트잇에서 [→]로 보낸 것도, [갱신]에서 끝났다고 닫은 한계 줄도 없습니다」로. 같은 함수의 `session_action` detail 「미룬 말 N개 받은 할 일 M개」도 「뺄 줄 N개 쓸 줄 M개」로(앞 시각만 읽으므로 `later_since`에 영향 없음). `tests/data/screen_words.toml`에서 이 두 곳을 봐주던 낡은 `[[code_exception]]` 두 줄을 지웠다 | `ee1d57f` |
| `bridge/foreman.py` 교장 지시문 서기 줄 | role 칸 「sync, trim, loss, 포트폴리오」와 task 칸 목록을 `scribe_room.TASKS`에서 만든다(`SCRIBE_SESSION_TASKS`, publish만 뺌). 이제 doccheck, trim, later, docfix, portfolio, techdoc. 시험 `test_instructions_scribe_tasks_follow_tasks`. docs `12_scribe.md` 1절 줄 | `ee1d57f` |
| `bridge/coder_room.py` `todo`의 죽은 길 | `sr.inbox_new(..., "coder")` 호출과 응답 `inbox` 칸을 뺐다(늘 `[]`, `coder.js`는 읽지 않음, 확인함). 응답은 `{rested}` + api가 붙이는 `drift`. 시험 줄, docs `10_office_design.md` 두 곳 | `8529d38` |
| 낡은 주석, docstring | `scribe_room.py` 머리 시킬 일 목록, `scribe.py` 머리(재료 이름, 700은 날짜 폴더이고 파일 600), `api/coder.py` `coder_todo`(`{rested, drift}`), `coder_room.py` 머리, `hookmiss.py` 머리 7갈래를 8갈래로(스크립트 `miss` 부르는 곳을 셈: 토큰없음, 연결거부, 시간초과, 인증실패, 서버오류, curl오류, 빈본문, 깨진JSON), `notion.py` 머리 「FOREMAN 페이지에만 연결」을 「프로젝트」 페이지(11-09, `config/notion.toml` 머리와 같게), 「저장소가 비공개라」 주석 다섯 곳(당시 비공개, 지금 공개, 링크 없이 두는 동작은 그대로), `config/handoff.toml` 5~6줄 「일을 마침」(묻는 말이어도 마친 것으로 봄) | `fc2b57a` |

### 1-4. `bridge/handoff.py` `will_worktree` (주석만, `fc2b57a`)

- 판단: **의도로 본다.** 이 판정은 원본 폴더 작업 트리에 쓰는 세션이 둘이 되지 않게 새 세션을 worktree로 보내는 것이다. Ctrl+Z로 멈춘 세션은 사람이 다시 살릴 수 있고(CLAUDE.md 「멈춰 있는 CC 프로세스는 건드리지 않는다」, 사용자가 일부러 남긴 것), 살리면 같은 트리를 함께 쓰게 되므로 세는 쪽이 안전하다
- 근거: 함수가 처음 들어온 `bdcd0cd`와 기록에는 멈춘 세션을 따로 다룬 말이 없다(그래서 「의도」는 코드의 목적에서 읽은 것이다). `foreman.py`가 멈춘 세션을 빼는 곳은 둘이고 묻는 것이 다르다: attach 대상(608줄 근처, 지금 글을 받을 수 있나), 계획 겹침 `file_conflicts`(685줄 근처, `9bac043`에서 들어옴. 빼는 까닭은 커밋 본문에도 없다)
- docstring에 위 내용을 적었다. 동작은 바꾸지 않았다

## 2. 같은 종류로 더 찾은 것

- **조용히 무시되는 설정 칸**: `config/*.toml` 모든 칸 이름이 `bridge/`, `scripts/`, `tools/` 코드에 문자열로 나오는지 기계로 셌다(스크립트는 세션 임시 폴더, 저장소에 넣지 않음). 걸린 것은 `approval.toml`의 규칙 이름, `models.toml` `aliases.fable`, `usage.toml` `prices.fable`(이름이 실행 때 정해지는 표의 키)와 `notify.toml [overlap]` 일곱 칸(`overlap.load_rules`가 dataclass 칸 이름으로 읽음)뿐이고 모두 읽힌다. `[nudge]` 밖에 죽은 칸은 찾지 못했다. 한계: 이름이 다른 파일에 같은 글자로 나오면 읽는 것으로 센다
- **급한데 묶음으로 미뤄지는 알림**: 묶음 종류(`turn, batch, merge, handoff, docsync, recon`)로 보내는 곳을 모두 읽었다. 고친 것은 위 1-2의 셋. 아래는 찾았지만 고치지 않았다(3절)

## 3. 찾았지만 고치지 않은 것과 까닭

- `bridge/handoff.py` `_notify`의 「인계 요약 실패」, 「인계 요약 시간 초과」(종류 `handoff`, ⚠ 없음): 실패인데 묶음을 켠 프로젝트면 21:00로 간다. 급한 표시가 붙은 것이 아니라 이번 기준(표시가 붙었는데 미뤄짐) 밖이고, 원문은 패널에 남아 일이 막히지는 않는다. 「실패는 바로」로 할지(⚠를 붙일지)는 사람이 정할 것
- `bridge/docsync.py` 「✋ Notion 기술문서, 사람이 고친 곳이 있어 덮지 않았습니다」 알림(종류 `docsync`): `config/notify.toml [digest]` 주석이 묶음 종류로 일부러 적었다(「Notion 문서(✋ 덮지 않음)」). 의도라 그대로
- `bridge/reconcile.py` 「🧹 끝난 뒤 어긋난 것」(종류 `recon`): 같은 주석에 묶음으로 적혀 있다. 그대로
- 🛡를 `config/notify.toml [digest] urgent_marks`에 넣는 길은 쓰지 않았다. 설정을 바꾸는 일이라(다른 세션 요청으로 설정을 바꾸지 않는다) 코드에서 카드 기준으로 정했다
- `bridge/approvals.py` 판정 앞 예외(포스트잇 p:61): 일감대로 하지 않았다
- `config/usage.toml` `[prices.fable]` 캐시 읽기 비율(505 log): 출처 확인이 필요한 값이라 이번 범위(조용히 무시되는 설정, 급한 알림) 밖
- 화면 js 쪽(`office.js` 경고등 호버, Harbor ✓, 머리 칩 옛 글, `render.js` `sessionSub`, `themes/*/theme.json` `aura._`): 디자이너 세션 몫이라 건드리지 않았다
- `bridge/mask.py` `ENV_FILES`: 같은 시각 다른 코더가 맡은 파일이라 건드리지 않았다
- `bridge/scribe_room.py` `inbox_new`의 `assignee != "scribe"` 갈래: 이제 부르는 곳이 scribe뿐이지만 함수 docstring이 까닭을 적고 있어 그대로 두었다

## 4. 원고가 다시 볼 곳 (서기 몫, `notion/`, `portfolio/`는 건드리지 않음)

- `notion/10_scribe.md` 77~78줄: `[nudge]` `new_min = 3` 예시. 이제 `config/scribe.toml`에는 `[postit]`(20, 7, 7)만 있다
- `notion/10_scribe/01_room.md` 230줄: 「`[nudge]`는 이 말풍선의 옛 기준이다」. 그 표는 11-17에 파일에서 빠졌다
- `notion/07_merge/01_card.md` 102줄 근처, 263줄 표: 🛡가 붙은 「합치기 준비됨」과 관리자에게 못 전한 알림 둘이 이제 21:00 묶음으로 가지 않고 바로 간다
- `notion/10_scribe/04_notion.md` 263줄, `notion/10_scribe/03_evidence.md` 47줄: 「비공개 저장소」를 까닭으로 쓴다. 저장소는 지금 공개이고 링크 없이 두는 동작만 그대로다
- 코더 패널을 다루는 원고에 `/api/coder/todo`의 `inbox` 칸이 있으면 빠졌다(이번에 찾은 곳은 없음)
- 교장 지시문의 서기 일 이름을 다룬 원고가 있으면 이제 `TASKS`에서 만든다

## 5. 서기 몫 (docs/operations.md, docs/style_guide.md)

- `docs/operations.md` 「5. 알림(텔레그램) 상세」에 묶음에서 빠지는 것을 적는 곳이 있다면, 「⑂ 합치기 준비됨」 중 🛡가 붙은 것과 관리자에게 못 전한 합치기 알림 둘이 바로 간다는 것을 더할 곳. 이번에 그 파일은 열어 보지 않았다(건드리지 말라는 일감)

## 6. 시험

- `.venv/bin/python -m pytest -q`: 1182 passed(화면 말 시험 서기 몫 0줄)
- `node --test tests/js/`: 210 pass
- 합치기 참고: 이 브랜치를 만든 뒤 main에 커밋 3개가 더 들어왔다. `git merge-tree --write-tree --name-only main HEAD`는 충돌 없이 트리 하나를 냈다(확인만, 합치지 않음)

## 7. 알릴 것

- 바뀐 설정 파일 둘(`config/scribe.toml` 표 바꿈, `config/handoff.toml` 주석만)은 합치기 카드에서 늘 사람 승인에 걸린다
- 합친 뒤 브리지를 다시 띄워야 반영되는 것: 1-2 알림, 교장 지시문, 코더 todo 응답, later 거절 글, `postit.conf` 경고. `config/scribe.toml` 값 자체는 다시 띄우지 않아도 서기실을 읽을 때마다 다시 읽는다

## 규칙 위반

규칙 위반 없음. 다만 처음 두 커밋(`e7b131f`, `26bfefb`)에서 새로 쓴 코드 주석과 시험 docstring에 em dash와 가운뎃점을 썼다. 일감의 금지 범위(화면 글, 커밋, log)에는 들지 않지만 `fc2b57a`에서 쉼표로 바꿨다. 화면 글, 커밋 메시지, 이 log에는 새로 쓰지 않았다.
