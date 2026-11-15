# 발밑 원 모든 역할 같은 값 · 역할마다 따로 정하는 값 목록 (2026-11-15, worktree foreman-6, 코더 454)

관리자 410의 일감(사용자 지시 「조사 역할 캐릭터만 발밑 원이 허리에 떠 있다. 모든 역할에 같은 값이 적용되게. 새 역할이 생겨도 저절로 맞아야 한다. 역할마다 따로 정하는 값이 또 무엇이 있는지 함께 보고」). 이번에 고친 것은 발밑 원뿐이고, 3번 표는 목록만이다.

## 1. 원인 — 역할이 아니라 자세였다

- 원 높이 값(`aura.js` `AURA_RX` · `AURA_FLAT` · `AURA_LIFT`)은 처음부터 상수 하나이고 역할 · 테마마다 따로 없다. 테마 `theme.json`의 `aura`에도 꼴(`style`)만 있고 높이는 없다. `aura.js`에는 역할 이름을 쓴 곳이 없다(`auraOf`의 `kind === 'scribe' · 'coder'`는 역할이 아니라 캐릭터 종류). 조사(inspector) 색도 `ROLE_COLOR`에 있어 기본값으로 떨어지지 않았다
- 진짜 원인: 마법학교 쉬는 자세 `sleep`(엎드려 자기, 대기 세션이 대강당 탁자에서)은 머리를 탁자 위로 대려고 `drawActorS`가 그림만 `4 × K`px 내려 그린다(`office.js`). 원은 `a.y * T`(발 점)에 그대로라 그림 바닥보다 위에 떴다. 마법학교 `K`가 1.5라 6px(몸 높이 26px의 4분의 1 가까이, 허리 쪽)
- 조사만 그렇게 보인 까닭: 조사는 늘 대기(IDLE)라 이 자세로 가장 자주 보인다. 마법학교 대기 변형이 `sleep · eat · read`이고 서기는 쉼 자리가 따로(`roles.idle`), 상주 코더는 걷고, 조사는 가장 오래 쉬기 때문이다. 디자이너도 쉬면 `sleep`이 된다(고친 뒤 디자이너 450이 `sleep`인 화면에서 차 0 확인, 고치기 전 같은 자세는 못 찍었다)
- 오피스(`phone · coffee · read`) · 현장(`lie · coffee · news`)에는 `sleep`이 없어 어긋남이 없었다. 현장의 `lie`(누움)는 11-14에 정한 대로 원을 누운 몸 가운데에 두며, 이것은 조사만이 아니라 누운 모든 역할이 같다(디자이너 450도 같음)

## 2. 고친 것

- `bridge/static/js/aura.js`: `POSE_DROP = { sleep: 4 }`, `poseDrop(anim, K)` 추가. 자세 때문에 그림이 발 점보다 내려앉는 px를 한 곳에서 낸다
- `bridge/static/js/office.js`: `drawActorS`가 `4 * K` 값을 직접 적던 것을 `poseDrop(anim, K)`로 바꾸고, 그 값을 `SILS`의 `drop`에 남긴다. `eachAura`는 원 가운데를 `a.y * T + drop`으로 잡는다. 그림과 원이 같은 값을 쓰므로 새 자세가 그림을 움직여도 `POSE_DROP`에 더하면 원이 따라간다. 새 역할은 자세로만 갈리므로 더할 것이 없다
- `tests/js/role_aura.test.mjs`: `poseDrop` 값(`sleep` 1.5 → 6, 다른 자세 0), office.js가 같은 함수를 쓰는지, 내림 값을 따로 적지 않았는지, `aura.js`(주석 뺀 것)에 `designer · inspector · manager · cicd` 이름이 없는지
- `docs/10_office_design.md` 「발밑 역할 색 원」에 한 줄(「자세로 내려앉는 만큼은 원도 같이」)

## 3. 확인 — 전 · 뒤 숫자

`?roles=demo`로 세 테마 · 1366x768 · 실제 화면. `window.office.auras()`의 원 가운데 y에서 `bodies()`의 그림 바닥 y를 뺀 값(화면 px, 0이면 바닥, 음수면 그 만큼 위).

| 테마 | 캐릭터(자세) | 전 | 뒤 |
|---|---|---|---|
| 마법학교 | 조사 453(`sleep`, 대강당) | **−6** | **+1** |
| 마법학교 | 조사 455(`read`) · 디자이너 · 관리자 · 서기 · 코더(걷기) | 0 ~ −1 | 그대로 |
| 오피스 | 조사 · 코더 · 디자이너 · 관리자 · 서기 | 0 ~ +1 | 그대로 |
| 현장 | 조사 455(`news`) · 코더 · 디자이너 · 관리자 · 서기 | −1 ~ +1 | 그대로 |
| 현장 | 조사 453 · 디자이너 450(`lie`, 누운 그림) | −14 | −14(누운 몸 가운데, 정한 대로) |

- `tools/screen.py --no-term`(세 테마 × 세 크기 × 패널 둘, 미리보기 :8200): 문제 0건 · 페이지 오류 0
- `node --test tests/js/` 204 통과, `tests/test_screen_words.py` 16 통과. 화면 말은 바꾸지 않아 `screen_words.toml`은 그대로
- 사진: 전 `scratchpad/run1`(세 테마), 뒤 `run4`. 이 세션의 스크래치폴더라 지워질 수 있다(숫자는 위 표가 기록)
- 못 한 것: 대강당 조사의 확대 사진 전 · 뒤 한 쌍. 확대 자리를 두 번 놓쳤고 숫자로 대신했다(원 가운데 − 그림 바닥 = +1px)

## 4. 역할마다 따로 정하는 값 목록(표만, 이번에 안 고침)

「더하면」 칸: ✅ = 안 적어도 기본값으로 괜찮다, ⚠ = 적지 않으면 그 역할만 어색하거나 기능이 빠진다, ❌ = 적지 않으면 거부 · 오류 · 깨짐.
역할 5개 = coder · inspector · scribe · manager · designer(세션 역할). foreman · helper · infra는 캐릭터 몫, cicd는 지난 역할(0017 마이그레이션에 이름만).

### 화면 말 · 색 · 목록

| 자리 | 무엇 | 새 역할을 더하면 |
|---|---|---|
| `bridge/static/js/render.js:16` `ROLE_LABEL` | 화면에 뜨는 역할 이름(배지 · 이름표 줄 · 안내) | ⚠ 없으면 「역할?」로 뜬다(`roleLabel` null) |
| `render.js:18` `SESSION_ROLES` | 패널 머리줄 [역할] 고르는 목록 순서(`opanel.js:149`) | ❌ 사람이 고를 수 없다 |
| `render.js:23` `ROLE_COLOR` | 배지 색, 발밑 원 색, 이름표 글자 색(`roleNameInk`) | ⚠ 없으면 원이 안 붙고(`auraOf` null) 배지는 기본 회색 |
| `render.js:36` `ROLE_NONE_COLOR` · `ROLE_OTHER_COLOR` | 「역할?」 노랑, 기본 회색 | ✅ 역할과 무관한 기본값 |
| `bridge/static/js/modelpick.js:6` `ROLE_PICK` | 새 세션 · 교장 채팅의 역할 드롭다운 글 | ❌ 이 목록에 없으면 고를 수 없다 |
| `bridge/handoff.py:46` `ROLE_KO` | 역할 → 캐릭터 이름(`_character_for` 1005), 역할 바꾸기 허용(1183), 새 세션 역할 인정(807) | ❌ 없으면 캐릭터가 안 붙고 바꾸기가 「바꿀 수 없는 역할」로 거부 |
| `bridge/wake.py:33` · `bridge/foreman.py:182` `ROLE_KO` | 알림 · 교장 계획 확인 글의 역할 이름(복사본 셋째, 넷째) | ⚠ 없으면 영어 값이 그대로 뜬다 |
| `bridge/handoff.py:47` `ROLE_OLD_KO` | 옛 화면 이름(점검 → 조사) 되돌리기 | ✅ 이름을 바꿀 때만 |
| `bridge/static/css/panel.css:228~237` `.rolebadge` | 배지 모양. 역할 색은 `roleColorCss()`가 `ROLE_COLOR`에서 만든다(시험이 panel.css에 역할 색이 다시 생기는지 막음) | ✅ |

### 테마

| 자리 | 무엇 | 새 역할을 더하면 |
|---|---|---|
| `bridge/static/themes/{magic,office,site,plain}/theme.json` `roles.colors` (각 66~74줄) | 사원증 끈 · 로브 · 안전모 색. **`ROLE_COLOR`(배지 · 원)와 다른 값이 따로 적혀 있다**(예: 조사 `#2e9e6a` ↔ `#3fbf85`) | ⚠ 없으면 그 역할의 끈 · 안전모가 안 그려진다. `?roles=demo`는 이 키들로 돈다 |
| 각 테마 `roles.idle` | 역할별 쉼 자리. 지금 서기만(`scribe: 필사실 · 문서팀 · 서류실`) | ✅ 없으면 `states.IDLE`의 방 · 변형 |
| 각 테마 `layout.zones.<역할>` (manager · designer · scribe) | 고정 자리 · 구역 이름 · 가구 | 고정 자리가 필요할 때만 ❌ 없으면 일반 자리 |
| `office.js:44` `FIXED_SEAT_ROLES = ['manager','designer']` | 고정 자리를 쓰는 역할 목록(`office.js:485`) | 고정 자리가 필요할 때만 더한다 |
| `office.js:601 · 609 · 627 · 673` | 감독 · 서기 · 코더 캐릭터의 `role` 값을 코드가 직접 박는다(세션 없는 캐릭터) | ✅ 세션 역할에는 해당 없음 |
| `aura.js:14~25` `auraOf` | 원이 붙는 캐릭터 종류(`session · mini · foreman · scribe · coder`) | ✅ 세션이면 `ROLE_COLOR`만 있으면 붙는다 |
| `aura.js` 원 높이 · 크기 상수, `POSE_DROP` | 원 높이는 역할 없이 상수 하나 + 자세로만 | ✅ (이번에 정리) |

### 서버 동작 · 설정

| 자리 | 무엇 | 새 역할을 더하면 |
|---|---|---|
| `bridge/api/handoff.py:42` `SessionRole` | 새 세션 요청 · 역할 바꾸기 API가 받는 역할(Literal) | ❌ 422로 거부 |
| `bridge/foreman.py:37` `ROLES` + 지시문 122~132, 297 | 교장 계획이 쓸 수 있는 역할과 각 역할을 언제 쓰는지 설명. 모르는 역할은 `coder`로 바꾼다(225) | ❌ 계획이 그 역할을 못 쓰고 coder가 된다 |
| `bridge/foreman.py:576~582` | 조사만: `log_only`, 읽기 전용(plan) 시작 | 역할별 권한이 있을 때만 |
| `bridge/models.py:21` `Role` enum | `foreman · coder · inspector · helper · infra`뿐(**scribe · manager · designer가 없다**). 이미 낡았다 | ✅ 쓰이는 곳이 거의 없어 지금은 안 깨진다 |
| `config/models.toml:27~31` `[defaults]` | 역할별 기본 모델. 없는 역할은 `coder` 값(`model_choice.py:47`) | ⚠ 빠지면 coder 모델로 뜬다 |
| `bridge/model_choice.py:47` `default_for` | 위 기본값 조회(`role or "coder"`) | ✅ |
| `config/roles.toml` `manager_allow` · `inspector_allow`, `enforce`, `[roles.rules]` | 역할별 파일 쓰기 허용 목록과 규칙 켜기 | ⚠ 권한 규칙이 없으면 제한이 없다(조용히 풀림) |
| `bridge/roleguard.py:45` `RULES`, `229~250`, `264~390` | 역할별 PreToolUse 거부(조사 log만, 관리자 코드 금지, 서기 코드 금지, worktree push 금지 등) | ⚠ 위와 같다 |
| `bridge/handoff.py:830 · 881 · 915 · 966` | 관리자는 원본 폴더만, 서기는 일감 칸 따위 역할 분기 | 역할별 규칙이 있을 때만 |
| `bridge/xmsg.py:39` · `reposcope.py:179` · `notify.py:526` · `api/dashboard.py:244 · 419` · `overlap.py:163` · `managers.py:120` · `mergeprep.py:1256` · `foreman_note.py:366` | 관리자 역할만 아는 여러 분기(알림 · 승인 · 가로막기) | 다른 역할은 해당 없음(관리자 전용) |
| `bridge/static/js/coder.js:11` `isCoder` · `handoff.js:336` | 코더 · 관리자 화면 분기 | 해당 없음 |
| `bridge/postit.py:378` | 포스트잇 갱신이 `role="inspector"`로 세션을 띄운다 | 해당 없음 |
| `migrations/0001_init.sql:34` 주석, `0017` | 역할 칼럼은 `VARCHAR(16)`이라 값 제한 없음. 캐릭터 이름(점검 · CI/CD)이 박힌 옛 이행 | ✅ |

### 문서 · 시연 · 기준

| 자리 | 무엇 | 새 역할을 더하면 |
|---|---|---|
| `bridge/static/demo/*.json` | 시연 장면의 세션 역할(coder · designer · manager · scribe가 있고 조사는 `stills.json`의 모델 칸뿐) | ⚠ 새 역할이 시연에 안 나온다 |
| `tools/demo_from_db.py:282` | 시연 만들기의 모델 기본값(`coder · inspector · cicd · scribe`) — **낡았다**(manager · designer 없음, cicd는 지난 역할) | ⚠ |
| `tests/data/screen_words.toml`, `tests/js/role_label.test.mjs` | 화면 말 · 역할 이름 시험 | ⚠ 이름이 바뀌면 같이 |
| `CLAUDE.md` 「역할을 가르는 기준」 · `docs/10_office_design.md` · `docs/12_scribe.md` · `docs/11_worktree.md` · `docs/operations.md` | 역할 설명 글 | 서기 몫 |

## 5. 제안(고치지 않음, 하나로 모을 만한 것)

1. **`ROLE_KO` 네 벌**(`handoff.py` · `wake.py` · `foreman.py`와 JS `ROLE_LABEL`)과 `SessionRole` · `ROLES` · `SESSION_ROLES`: 역할 목록과 화면 이름을 파이썬 한 곳(예: `config/roles.toml` 새 `[names]` 또는 `bridge/roles.py` 상수 하나)에 두고 `SessionRole` · `ROLES` · `ROLE_KO`를 거기서 만들고, JS는 `/api` 한 줄로 받으면 역할을 더할 때 한 곳만 고친다. 지금은 이름을 바꾼 11-15(점검 → 조사)에 네 곳을 고쳐야 했다(낡은 `models.py` `Role`이 이미 어긋남)
2. **색 두 벌**: `render.js` `ROLE_COLOR`(배지 · 원)와 theme.json `roles.colors`(끈 · 안전모)가 같은 역할의 같은 색 개념인데 값이 다르다(11-13 사용자가 「원은 배지와 같게」만 정함). 테마 색은 테마 몫으로 두되 키가 빠지면 `ROLE_COLOR`로 떨어지게 하면 새 역할에서 테마 네 곳을 안 고쳐도 된다
3. **`ROLE_PICK`**(드롭다운 글)과 `ROLE_LABEL`과 교장 지시문의 역할 설명: 한 줄 설명이 세 곳에 따로 있다
4. **역할 권한**(`roles.toml` · `roleguard.py`)은 규칙마다 코드가 따로라 새 역할에 「쓰기 가능 범위」를 주려면 코드를 고쳐야 한다. 지금은 역할이 많지 않아 두고, 역할이 늘면 `[roles.<이름>] write = [...]` 같은 표로 올린다
5. **새 역할 더하는 순서 목록**(빠뜨리지 않게): 위 표의 ❌ · ⚠ 줄(`SessionRole` · `ROLE_KO` 셋 · `ROLES`와 지시문 · `SESSION_ROLES` · `ROLE_PICK` · `ROLE_LABEL` · `ROLE_COLOR` · `models.toml` · theme.json `roles.colors` 네 곳 · 권한 규칙 · 시연)을 `docs/` 한 절에 체크리스트로 두면 좋다 — `docs/operations.md` · `docs/style_guide.md`는 이 일감에서 건드리지 않아 서기 몫으로 남긴다

## 6. 규칙

- **위반 1 — 빈 heredoc 실행**: 11-15 오전, 미리보기 결과 폴더를 보려고 `python - <<'EOF' EOF`(본문 없는 heredoc)를 한 번 쳤다. 까닭: 요약 스크립트를 Write로 만들기 전에 급히 쳤다. 바로잡음: 직후 Write로 `sum.py`를 만들어 그것으로 돌렸고, 이후 heredoc을 쓰지 않았다. 파일은 바뀌지 않았다
- 그 밖에 규칙 위반 없음(파일은 Edit · Write로만, 스크래치 스크립트도 Write, `pgrep -f` 없음, 토큰은 셸 변수로만 써 화면에 안 냈고 길이만 셌다, push · 브리지 다시 띄우기 없음)
- 미리보기(:8200, tmux `fm-pv-foreman-6`)는 끝내기 전에 끈다
