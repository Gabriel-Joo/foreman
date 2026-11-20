# 역할 — 목록 · 권한 · 새 역할 더하기 (11-15) [log:foreman-6_roles_one_place_20261115.md]

세션 역할의 값 · 이름 · 설명 · 색 · 권한을 한눈에 보는 곳이다. 역할을 가르는 기준 글은 `CLAUDE.md` 「역할을 가르는 기준」이고, 아래 한 줄 설명은 그 글과 같은 뜻이다.
11-15 전에는 역할 목록 · 이름이 일곱 곳(`ROLE_KO` 세 벌 · `ROLES` · `SessionRole` · `ROLE_PICK` · `ROLE_LABEL`), 테마 옷 색이 네 곳, 한 줄 설명이 세 곳에 따로 있었다(조사 log `log/foreman-6_aura_all_roles_20261115.md` 4절).

## 1. 역할과 한 곳

| 값 | 화면 이름 | 한 줄 설명(역할 고르기 칸 · 교장 지시문) | 배지 · 발밑 원 색 | 옷 색(끈 · 로브 · 안전모) | 기본 모델 |
|---|---|---|---|---|---|
| `coder` | 코더 | 코드를 고치거나 만듭니다. 그 코드를 가리키는 문서도 함께 고칩니다 | `#5b9be6` | `#3f7fd0`(현장 `#2f6fb0`) | Opus 5.5 |
| `designer` | 디자이너 | 화면을 고칩니다. js, css, 테마, 캐릭터, 호버 글 | `#e8619f` | `#d6408a` | Opus 5.5 |
| `manager` | 관리자 | 합치고 시험하고 push하고 기록합니다 | `#e0604f` | `#c0392b` | Opus 5.5 |
| `scribe` | 서기 | 문서를 쓰고 맞춥니다 | `#d08b4f` | `#b0713a` | Opus 5.5 |
| `inspector` | 조사 | 읽고 알아봅니다. 고치지 않고 결과 log만 씁니다. 조사와 제안은 모두 여기입니다 | `#3fbf85` | `#2e9e6a` | Sonnet 5.5 |

캐릭터 몫(세션으로 고를 수 없다): `foreman` 감독(배지 `#c9a227`, 옷 `#d4a72c`, 현장 흰 안전모 `#f4f4f4`) · `helper` 도우미(옷 `#8a8f98`) · `infra` 인프라.

- **파이썬 한 곳 `bridge/roles.py`**: `ROLE_INFO`(값 → 화면 이름 · 한 줄 설명)에서 `SESSION_ROLES` · `ROLE_KO` · `ROLE_DESC` · `role_line()`(교장 지시문 「3. role」 첫 줄)이 나온다. API 검증 `bridge/api/handoff.py` `SessionRole`, 교장 `bridge/foreman.py` `ROLES` · 지시문 · 계획 확인 글, 캐릭터 이름 · 역할 바꾸기 `bridge/handoff.py`, 알림 글 `bridge/wake.py`가 여기서 가져간다. 턴 끝을 관리자에게 넘기는 작업 역할 `WORKER_ROLES`(코더 · 서기 · 디자이너)도 여기(`notify.py` · `api/dashboard.py`)
- **화면 한 곳 `bridge/static/js/roles.js`**: `SESSION_ROLES`(역할 고르기 칸 순서, 첫째가 기본값) · `ROLE_LABEL` · `ROLE_DESC` · `ROLE_COLOR`(배지 · 발밑 원 · 이름표 글자) · `ROLE_CLOTH`(옷 색) · `themeCloth` · `clothColor`. `render.js`가 앞의 것들을 다시 내보내 전처럼 가져다 쓸 수 있다. `modelpick.js` `ROLE_PICK`(「이름 — 설명」)은 이 셋으로 만든다
- **왜 서버가 내려주지 않고 JS에 한 벌 더 두는가**: 배지 색 CSS · 픽셀 화면 · 미리보기(브리지 없이 도는 시연 페이지) · node 시험이 모듈을 읽자마자 쓴다. 서버에서 받으면 받기 전 그리기를 다 기다리게 고쳐야 한다. 대신 `tests/test_roles_agree.py`가 파이썬과 JS를 맞대어 한 역할이라도 어긋나면 실패한다
- **옷 색**: 테마는 다른 값이 필요한 역할만 `theme.json roles.colors`에 적어 덮는다(지금은 현장 감독 · 코더). 표에도 테마에도 없는 역할은 배지 색으로 그린다(`clothColor`)
- **기본 모델**: `config/models.toml [defaults]`(사람 승인 카드). 없는 역할은 CC 설정을 따른다

## 2. 역할 권한 표 — 할 수 있는 것과 막히는 것

`config/roles.toml` `[roles] mode = "observe"`라 역할 규칙은 대부분 **기록만** 한다(그 호출의 승인 이벤트에 `role_rule` · `role_reason`). `enforce = ["inspector-write"]`에 든 조사 규칙만 observe여도 **막는다**. `projects = ["foreman"]` — 이 프로젝트 세션만 본다. 판정은 `bridge/roleguard.py`.

| 역할 | 자리 | 쓸 수 있는 곳 | 역할 규칙(roleguard) | 그 밖에 역할로 갈리는 것 |
|---|---|---|---|---|
| 코더 | 살아 있는 세션이 있으면 작업방(worktree), 없으면 원본 폴더 | 저장소 전체 | 역할 규칙 없음(공통만) | 턴 끝을 관리자에게 넘긴다(`WORKER_ROLES`). 첫 글 끝에 「고친 코드의 문서도 함께」 절이 붙는다(11-17, `DOCS_RULE_ROLES`, `docs/11_worktree.md` 「9.」) |
| 디자이너 | 코더와 같다. 픽셀 화면에서는 고정 자리(`office.js` `FIXED_SEAT_ROLES`) | 저장소 전체(화면만 고치는 것은 글 규칙, 막지 않는다) | 역할 규칙 없음(공통만) | 턴 끝을 관리자에게 넘긴다 |
| 서기 | 코더와 같다(교장은 서기를 작업방으로 띄운다) | `bridge/` · `tests/` · `migrations/` · `tools/` 밖 | `scribe-code`: 위 네 곳(`scribe_deny`)을 Edit · Write — **기록만** | 턴 끝을 관리자에게 넘긴다. 띄울 때 서기 일 종류를 남긴다(`scribe-task`) |
| 조사 | 코더와 같다 | `log/` 아래 새 파일 · 이 세션이 만든 파일(`inspector_allow`) | `inspector-write` — **막는다**: log 밖 Edit · Write, Bash 저장소 쓰기(리디렉션 · `sed -i` · `rm` · `mv` …), `git push`, 저장소를 바꾸는 git, log 밖 `git add` · 섞인 `git commit` | 교장 계획: log만 막는 프로젝트면 보통 모드, 아니면 읽기 전용(plan 모드), 자동 기상 계획은 늘 읽기 전용(`foreman.py`). log 새 파일만이면 브리지가 승인 없이 합친다(`mergeprep.py`) |
| 관리자 | **원본 폴더만, 프로젝트에 하나**(`handoff.py` — worktree로 띄우면 거부) | `config/*.toml` · `log/*` · `docs/TODO.md`(`manager_allow`) | `manager-code`: 그 밖 Edit · Write — **기록만** | 다른 저장소 문서 push 예외(`approval.toml [repo_scope.manager_push]`), 합치기 카드 승인자(`mergeprep.py`), 작업 세션 보고를 받는 곳(`notify.py` · `managers.py` · `xmsg.py`) |

공통(역할 무관):

| 규칙 | 무엇 | 모드 |
|---|---|---|
| `worktree-push`(roleguard) | 작업방 세션의 `git push` | 기록만 |
| `bash-file-edit`(roleguard) | Bash로 저장소 파일 고치기(`sed -i` · 리디렉션 · heredoc · `tee`). /tmp · 스크래치는 뺀다 | 기록만 |
| `config/approval.toml` | 도구 호출 승인 규칙(`[projects.foreman] mode = "enforce"`) | 막는다 |
| `approval.toml [repo_scope]`(`reposcope.py`) | 다른 저장소는 읽기만 | 막는다 |
| `pgrep_guard.py` | `pgrep -f` · `pkill -f` | 막는다 |
| `schemalock.py` | DB 스키마는 한 세션만 | 막는다 |

- 규칙 하나 끄기: `roles.toml [roles.rules]`. 막게 하기: `[roles] enforce`에 규칙 이름(사용자 결정). 바꾸면 브리지를 다시 띄운다
- 새 역할에 쓰기 범위를 주려면 지금은 `roleguard.py`에 규칙 코드를 더해야 한다(규칙마다 코드가 따로). 역할이 늘면 `[roles.<이름>] write = [...]` 같은 표로 올린다(454 제안 4, 아직 안 함)

## 3. 새 역할을 더할 때 — 체크리스트

❌ = 빠뜨리면 시험이 실패하거나 거부 · 오류, ⚠ = 빠뜨리면 그 역할만 어색하거나 조용히 풀린다.

1. ❌ `bridge/roles.py` `ROLE_INFO`에 한 줄(값 · 화면 이름 · 한 줄 설명). API · 교장 계획 · 캐릭터 이름 · 역할 바꾸기 · 알림 글이 따라온다
2. ❌ `bridge/static/js/roles.js` `SESSION_ROLES` · `ROLE_LABEL` · `ROLE_DESC`에 같은 값(`tests/test_roles_agree.py`)
3. ❌ 같은 파일 `ROLE_COLOR`(배지 · 원), `ROLE_CLOTH`(옷). 다른 역할 색과 겹치지 않게(`tests/js/theme.test.mjs`). 테마마다 다른 옷 색이 필요할 때만 `theme.json roles.colors`
4. ❌ `config/models.toml [defaults]`(사람 승인 카드). 빠지면 CC 설정 모델로 뜬다
5. ❌ `bridge/models.py` `Role`에 값
6. ❌ `tests/js/role_label.test.mjs`의 역할 순서 줄
7. ⚠ 교장 지시문 `bridge/foreman.py` 「3. role」 아래 그 역할을 언제 고를지 줄. 첫 줄(이름 · 설명)은 1이 만든다
8. ⚠ 권한: 쓰기 범위가 있는 역할이면 `config/roles.toml`과 `bridge/roleguard.py` 규칙. 없으면 아무 제한이 없다(조용히 풀림). 위 2절 표에 줄
9. ⚠ 턴 끝을 관리자에게 넘기는 작업 역할이면 `roles.py` `WORKER_ROLES`
10. ⚠ 픽셀 화면: 고정 자리가 필요하면 `office.js` `FIXED_SEAT_ROLES` + 테마 넷 `layout.zones.<역할>.seats`, 쉼 자리가 따로면 테마 `roles.idle`. 바꾸면 `tools/screen.py`로 세 테마 0건
11. ⚠ 시연 장면 `bridge/static/demo/*.json`에 그 역할 세션(없으면 시연에 안 나온다)
12. ⚠ 문서: `CLAUDE.md` 「역할을 가르는 기준」(관리자가 사용자에게 묻고), 이 파일 1 · 2절. 화면 이름을 바꾸면 `tests/data/screen_words.toml`과 `roles.py` `ROLE_OLD_KO`

역할 이름만 바꿀 때(11-15 점검 → 조사처럼): 1 · 2의 화면 이름, `ROLE_OLD_KO`(DB의 옛 이름 캐릭터를 새 이름으로), `screen_words.toml`.
