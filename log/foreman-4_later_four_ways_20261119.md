# 알려진 한계 쓰기 지시문을 네 갈래 기준에 맞춤, README 한계 줄 길 빼기 (2026-11-19, cc/foreman-4)

관리자 410의 코더 일감이다(사용자 결정 11-19). 서기 `later` 지시문을 새 기준에 맞추고, README가 생성물이 된 뒤에도 남은 README 「알려진 한계」 줄 길을 뺀다.

## 한 일

### 1. `later` 지시문
- 지시문 본문의 「안 하기로 한 것만 쓰는 절이다」와 뺄 줄 말을 지웠다.
- 지시문이 기준 문서 줄을 읽어 넣지 않았다(경로만 가리켰다). 그래서 `bridge/manuscript_rules.py` `KINDS`에 `limit` 종류(1절과 2절)를 더하고, `scribe_room.task_prompt`의 `later`가 `_rules_block("limit", repo)`로 그 줄을 받게 했다. 한계, 조건, 설계, 할 일 넷으로 가르는 1절 줄과 2절 「한계 편의 꼴」 줄이 지시문에 들어간다. 기준이 지시문에 따로 한 벌 더 있지 않다.
- 본문에는 기준을 가리키는 말만 남겼다. 사람이 [한계로]로 보냈어도 읽어 보고 한계가 아닌 줄(조건, 설계, 까닭 없는 할 일)이면 쓰지 말고 마지막 응답에 어느 갈래로 보이는지와 까닭을 적게 했다. 사람 화면의 [한계로] 까닭 칸 동작은 건드리지 않았다.
- 여러 편에 되풀이되는 줄을 한계 편으로 모으라는 본문 말도 뺐다(2절 「한계 편의 꼴」 줄이 같은 말을 한다).

### 2. README 한계 줄 길
먼저 이 길이 지금 무엇을 하는지 확인했다.

- `bridge/postit.py` `readme_limits(repo)`는 README에서 머리 줄에 「알려진 한계」가 든 절을 찾는다. 지금 FOREMAN README에는 표 안 링크 글자로만 그 말이 있고 머리 줄은 없다. 실제로 돌려 `None`이 나왔다.
- `None`이면 [갱신] 재료(`check_material`)에 「README에 「알려진 한계」 절이 아직 없다. 볼 줄이 없다.」 한 줄만 들었다. 오류도 빈 재료도 아니고 조용히 넘어갔다. 열린 포스트잇이 없고 이 절도 없으면 「볼 포스트잇도 README … 줄도 없습니다」로 거부했다.
- 서기 할 일 세기(`summary`의 `readme_drop`)는 DB `postit_check`의 `L:` 줄 가운데 사람이 닫은 것을 셌다. 절이 없으면 새 `L:` 줄이 안 생겨 늘 0이었다. 서기 `later`는 `TOUCHES`에 `README.md`를 둬서, README를 고치는 문서 고치기 일과 쓸데없이 겹쳐 막혔다.
- 다른 저장소에서 쓰이는가: 지금 등록된 저장소 가운데 README에 이 절이 있는 곳이 없다(FOREMAN 0, ronanlab-infra 0, runshoes와 petmint-rag-chatbot은 README.md가 없다. 원본 폴더에서 `grep`과 `ls`로 봤다). 그래서 다른 저장소만 위해 남기지 않고 길 전체를 뺐다. README가 손으로 쓰는 글이고 한계 절을 둔 저장소가 생기면 그때 되살려야 한다(할 일이 아니라 지금 없는 길이라는 뜻이다).

뺀 것:
- `postit.py`: `readme_limits`, `readme_drop_pending`, `README_LIMIT`. `check_material`과 `CHECK_PROMPT`에서 README 절, `start_check`의 README 줄 읽기와 `L:` 알아보기, `summary`의 `readme_drop`과 안 쓰게 된 `since` 인자. `checks()`는 `p:` 줄만 읽는다(DB에 남은 옛 `L:` 줄은 지우지 않고 읽지만 않는다).
- `api/postit.py`: 응답의 `readme_checks`.
- `static/js/postit.js`: 「끝난 것 같음」의 README 줄 칸, [갱신] 확인 창과 호버, 결과 글의 README 줄 수.
- `scribe_room.py`: `later_prompts`, `later_material`의 뺄 줄 절, 서기 할 일의 「뺄 줄 M」, `TOUCHES["later"]`의 `README.md`, `TASKS`의 `later` 설명.

### 3. 문서
- `docs/12_scribe.md`: 39줄 표, 64줄, 85줄, 86줄, 309줄, 311줄, 321줄
- `docs/10_office_design.md` 154줄
- `portfolio/10_scribe_room.md` 31줄, `portfolio/11_postit.md` 38줄, 46줄
- `notion/10_scribe.md` 49줄, `notion/10_scribe/01_room.md` 34, 67, 157, 182줄, `notion/10_scribe/02_postit.md` 236, 250줄, `notion/15_db/01_tables.md` 383줄
- 화면 말 시험 `tests/data/screen_words.toml`에 두 줄

## 확인
- `.venv/bin/python -m pytest -q`: 아래 「시험」에 적은 대로.
- `tools/docs.py check`: 틀린 것 0(의심 243은 전과 같은 꼴의 줄 의심이다). `refs --range main...HEAD --unfixed`는 커밋 전이라 바뀐 코드 0개로 나온다. 커밋 전에 코드를 가리키는 문서 18개를 `refs bridge/postit.py bridge/scribe_room.py`로 보고 걸린 곳을 고쳤다.
- 노드 시험 42개 파일 모두 실패 0.
- 실제 서기 세션을 띄워 새 지시문으로 돌려 보지는 않았다. 지시문 글은 시험이 글로만 확인한다.

## 설계와 달랐던 점
- 일감은 「지시문이 이미 기준 문서 줄을 읽어 넣는다면」이라고 했는데 `later`는 읽어 넣지 않았다. 그래서 `KINDS`에 `limit`을 더하는 쪽으로 했다.
- `later_material` 쪽지 이름 `later_prompts`는 11-15 전 이름을 남겨 둔 것이었다. 뺄 줄이 없어져 함께 지웠다.

## 건드리지 않은 것과 걸린 것
- 다른 서기 세션이 고치는 곳이라 건드리지 않았다: `docs/12_scribe.md` 14줄 근처, `notion/10_scribe/02_postit.md` 208줄. 같은 파일 210줄에 「쓸 줄 N, 뺄 줄 M」이 그대로 남아 있다. 208줄과 맞붙어 있어 건드리지 않았다. 코드와 달라진 곳이니 그 서기 세션이 맞추어야 한다. 같은 파일 214줄(옛 [→] 단추를 없앤 까닭 설명)은 지난 일을 적은 글이라 맞다.
- 한계 편 파일과 `docs/12_scribe.md` 303줄 근처(0033 적용 시각 설명)는 그대로 맞아서 두었다.

## 규칙 위반
- 진행 글이 한국어가 아닌 때가 두 번 있었다. 한 번은 `later` 지시문을 고치기 직전 도구 호출 사이 글, 한 번은 시험을 고치기 직전 글이다. 둘 다 훅이 알려 준 뒤 한국어로 바로잡았다.
- `sed -i`를 `/dev/null`에 잘못 쳤다(명령 앞머리를 잘못 붙여 넣었다). 실패했고 어떤 파일도 바뀌지 않았다. 규칙은 Bash `sed -i`로 파일을 고치지 말라는 것이라 그 명령 모양을 쓴 것을 적는다. 파일은 모두 Edit, Write로 고쳤다.
- 그 밖의 규칙 위반은 없다.

## 시험
`.venv/bin/python -m pytest -q`: 1439 passed. 노드 시험 42개 파일은 모두 실패 0. `tools/docs.py check`는 틀린 것 0. 시험은 글과 동작만 확인했고 실제 화면과 실제 서기 세션은 돌려 보지 않았다.

## 사람이 정할 것
- 다른 저장소에서 README 한계 절을 되살릴 일이 생기면(손으로 쓰는 README를 두는 저장소) 이 길을 그 저장소에서만 도는 설정으로 되살릴지. 지금은 없는 길이다.
- DB `postit_check`에 남은 옛 `L:` 줄(열린 것이든 닫은 것이든)을 정리할지. 읽지 않으니 화면과 셈에는 영향이 없다. 지우려면 마이그레이션이 필요해 이번에는 손대지 않았다.
- `notion/10_scribe/02_postit.md` 210줄의 「뺄 줄 M」 맞추기는 그 파일을 고치는 서기 세션이 해야 한다.
