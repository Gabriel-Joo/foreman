# 가리기 대상 비밀값 파일 빠짐 고치기 (foreman-4, 2026-11-17)

관리자 410의 코더 일감(보안 건). 근거: `log/foreman-5_notion_evidence_scope_20261117.md` 「코드가 이상해 보이는 곳」.

## 고친 것

- `bridge/mask.py`
  - 손으로 적던 목록 `ENV_FILES`(db, bridge, telegram 셋)를 없애고 `secret_env_files()`로 고른다. 대상은 저장소 맨 위 `.env*`에서 예시 꼬리(`.example`, `.sample`, `.template`, `.dist`)를 뺀 전부, 그리고 config가 가리키는 토큰 파일(`config/notify.toml`의 `[telegram] env_file`, `config/tokens.toml`의 `[project_tokens] file`)이다. config에서 경로를 바꿔도 따라간다
  - 형식 패턴에 Notion 통합 토큰 꼴(`ntn_`, 옛 꼴 `secret_` 뒤에 영숫자 40자 이상)을 더했다. 정확한 값 가리기와 별개로 다른 곳에서 온 Notion 토큰도 DB에 들어가기 전에 가려진다
- 판단 근거(고르는 방식): 손 목록은 새 비밀값 파일이 생길 때마다 빠진다(이번 두 파일이 그렇게 빠졌다). 예시 꼬리는 `config/approval.toml`의 secret 규칙과 같게 맞췄다. 비밀이 아닌 키(`MYSQL_USER` 등)는 그대로 `SECRET_KEY` 판정으로 거르므로 파일을 넓게 골라도 엉뚱한 값이 가려지지 않는다
- `.env.notion`, `.env.project_tokens`의 키 이름은 모두 `SECRET_KEY`에 걸린다(`NOTION_TOKEN`, `FOREMAN_TOKEN_<프로젝트>` 셋). 그래서 키 판정은 고치지 않았다

## 확인한 비밀값 파일(이름만)

| 파일 | 어디서 읽나 | 전 | 후 |
|---|---|---|---|
| `.env.db` | `bridge/config.py`, compose | 가림 | 가림 |
| `.env.bridge` | `bridge/config.py`, `tools/screen.py`, `tools/demo_from_db.py` | 가림 | 가림 |
| `.env.telegram` | `bridge/notify.py`(경로는 `config/notify.toml`) | 가림 | 가림 |
| `.env.notion` | `bridge/notion.py`, `bridge/main.py` | 빠짐 | 가림 |
| `.env.project_tokens` | `bridge/scopetoken.py`(경로는 `config/tokens.toml`) | 빠짐 | 가림 |

- 하위 폴더의 `.env*`: 없음(`.venv`, `node_modules`, `.git` 밖에서 찾았다)
- 저장소에 추적되는 `.env`는 `.env.db.example`, `.env.bridge.example` 둘뿐이고 값이 없다
- `config/*.toml`에 비밀값 자리는 없다. 경로를 가리키는 칸 둘(위 표)만 있다
- 키 이름은 `=` 왼쪽만 내는 명령으로 봤다. `=` 없는 줄은 길이만 내게 했고, 그런 줄은 없었다

## 건 시험 둘

1. `tests/test_secret_files.py`: 비밀값 파일이 가리기 대상에서 빠지면 깨진다
   - tmp 저장소에서 고르기(예시 꼬리 빼기, config 경로 따라가기)
   - tmp의 가짜 값(접두어 없음)이 `.env.notion`, `.env.project_tokens`에서 정확한 값으로 가려지는지
   - `bridge/`, `tools/`, `config/`가 이름으로 여는 `.env.*`를 모두 찾아, 그 이름의 파일이 있으면 가리기 대상이 되는지
   - 실제 저장소에 있는 `.env*`(이름만)와 config가 가리키는 파일이 모두 대상인지
   - 실제 비밀값 파일의 키 이름이 `SECRET_KEY`에 걸리는지(비밀 아닌 키 넷은 이름으로 따로 적었다). 새 키가 둘 다에 없으면 깨진다. 이 시험은 파일을 읽지만 `=` 왼쪽만 남기고, 실패 글에도 `파일:키`만 낸다
2. `tests/test_public_secret_shapes.py`: `log/`, `notion/`, `portfolio/`, `docs/`의 글에 비밀값 꼴이 있으면 깨진다
   - 꼴: `mask.py` 형식 패턴 전부(개인키 블록, 텔레그램 봇, Anthropic, GitHub, AWS, Notion `ntn_`와 `secret_`, Bearer)와 키=값 꼴. 실제 값과 비교하지 않는다
   - 걸리면 `파일:줄 꼴이름`만 낸다
   - 가짜 꼴을 잡는지, 설명 글과 실제 오탐 꼴을 그냥 두는지도 시험한다
   - 프로젝트 토큰은 접두어 없는 무작위 값이라 키와 붙은 대입(`FOREMAN_TOKEN_<프로젝트>=값`)으로만 잡는다

### 오탐과 꼴 좁히기

`mask.py`의 키=값 패턴을 그대로 쓰니 5줄이 걸렸다. 값은 보지 않고 키 이름, 값 길이, 앞 세 글자, 글자 종류만 보고 가렸다. 모두 오탐이었다.

- `log/foreman-6_secret_scan_foreman_20261115.md` 42줄: 소문자 `password=` 뒤에 코드 식
- `log/stage8_cicd_result.md` 197줄: 소문자 `token=` 뒤에 경로
- `notion/02_ingest/03_turns.md` 158줄: `token_output = ` 뒤에 SQL 식
- `notion/02_ingest/04_bus.md` 99줄, 122줄: 한글 예시값과 이미 가린 `«masked»`

그래서 공개 글용 키=값 꼴은 키를 대문자 환경변수 이름(실제 비밀값 파일의 키 꼴)으로, 값을 ASCII 토큰 글자 8자 이상(`MIN_EXACT`와 같게)으로 좁히고 `/`로 시작하는 값을 뺐다. DB에 넣기 전 가리기(`mask.py`)는 넓은 꼴 그대로 둔다(거기서는 오탐이 해가 없다). 좁힌 뒤 지금 저장소에서 0건이다. 다른 꼴(`ntn_`, `secret_` 포함)은 처음부터 0건이었다.

## 시험 결과

- `.venv/bin/python -m pytest -q`: 1184 passed
- `node --test tests/js/`: 210 pass, 0 fail

## docs

가리기를 따로 설명하는 docs 절은 없다(`docs/operations.md`, `docs/style_guide.md`에도 없음). 고친 docs 없음. 서기 몫 없음.

## 규칙

규칙 위반 없음. 다만 판단한 곳 둘을 적는다.

- 오탐 확인 때 `.venv/bin/python - <<'EOF'`로 읽기만 하는 짧은 스크립트를 두 번 돌렸다. 파일을 만들거나 고치지 않았고 heredoc은 표준 입력으로만 썼다(금지는 heredoc 리디렉션으로 파일 만들기)
- 시험 하나(`test_real_secret_keys_are_secret_named`)가 실제 비밀값 파일을 연다. 키 이름을 알려면 파일을 읽어야 해서 `=` 왼쪽만 남기고 값은 버린다. 출력에는 키 이름만 나온다. 관리자가 이것도 원하지 않으면 이 시험만 빼면 된다(나머지 시험은 실제 파일을 열지 않는다)
- `.env*` 파일은 Edit, Write, cat, Read로 열지 않았다. 비밀값은 화면, log, 커밋, 시험 출력에 나오지 않았다
