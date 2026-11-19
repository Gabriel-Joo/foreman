<!--
다루는 곳: tests/conftest.py, tests/testdb.py, tests/screen_words.py, tests/test_js.py, tests/test_live_config_shape.py, tests/test_public_secret_shapes.py, tests/test_bridge_alert.py, tests/test_coder_docs_rule.py, tests/test_docrefs.py, tests/test_fail_notify_scan.py, tests/test_hook_timeouts.py, tests/test_hookmiss.py, tests/test_roles_agree.py, pyproject.toml, requirements.lock, deploy/systemd/foreman-bridge.service
읽은 커밋: fb7121b
-->
# 16 시험과 배포

FOREMAN의 시험과 배포는 둘 다 손으로 한다. 저장소를 GitHub에 올리기는 하지만 거기서 자동으로 도는 것은 없고, 서버에 새 코드를 반영하는 일도 사람이 고른 때에 유닛 하나를 다시 띄우는 것으로 끝난다. 이 편은 그 손일이 무엇이고, 왜 자동으로 만들지 않았는지, 시험 묶음이 어떻게 짜여 있는지를 짧게 모아 둔다. 시험 하나하나의 깊은 내용은 그 기능을 다루는 편에 있고, 여기서는 묶음의 모양과 가리킬 곳만 적는다.

## 1. CI가 없다

CI(지속 통합, 커밋이 올라올 때마다 시험을 자동으로 돌려 주는 장치)는 없다. 저장소에 GitHub Actions 워크플로 폴더(`.github/workflows`)가 없다 [code:CLAUDE.md]. GitHub Actions는 쓰지 않는다 [docs:00_design.md]. Jenkins, Harbor, ArgoCD를 익히려고 그 묶음을 골랐고, 채용 공고에서도 이 도구들이 자주 보였다. 그리고 GitHub Actions는 깃허브 쪽 러너에서 돌아 사설망 안의 Harbor에 닿지 않는다. 닿게 하려면 러너를 따로 세워야 하는데, 그러면 Jenkins를 세우는 것과 다르지 않다 [log:foreman-5_todo_collect_20261117.md]. 그래서 지금 시험을 돌리는 사람은 관리자(원본 폴더에서 도는 메인 세션)다. 작업방(git worktree, 따로 떨어진 작업 폴더)에서 일한 코더의 브랜치를 관리자가 합친 뒤, 원본 폴더에서 pytest와 node 시험을 손으로 돌린다. 통과하면 push하고, 실패하면 되돌리거나 몇 줄로 막고 제대로 고치는 일은 다시 작업방으로 보낸다 [code:CLAUDE.md].

코드가 서버에 반영되기까지의 길을 그리면 아래와 같다. 사람 손이 닿는 칸이 셋이고, 자동으로 넘어가는 칸은 없다.

```mermaid
flowchart LR
  A[작업방에서 코더가 커밋] --> B[관리자가 충돌 확인 뒤 합침]
  B --> C[관리자가 pytest, node 시험]
  C -->|통과| D[관리자가 GitHub에 push]
  C -->|실패| E[되돌리거나 몇 줄로 막고 작업방으로]
  D --> F[승인 대기 0을 보고 사람이 유닛 재시작]
```

이 선택으로 치른 값은 하나다. 지금까지는 합칠 때마다 관리자가 돌리는 것으로 퇴행이 잡혀 왔지만, 사람이 돌리는 시험은 사람이 잊으면 돌지 않는다. 승인 정책(`bridge/approval.py`)처럼 한 번 고친 것이 몰래 되돌아가면 안 되는 보안 규칙도 같은 길로만 지켜진다. 이 빈틈은 아는 채로 남겨 둔 것이다.

## 2. 돌리는 명령

| 무엇 | 명령 | 어디서 |
|---|---|---|
| 파이썬 시험 전체 | `.venv/bin/python -m pytest -q` | 저장소 맨 위 |
| 화면 쪽 js 시험만 | `node --test tests/js/` | 저장소 맨 위 |
| 파일 하나만 | `.venv/bin/python -m pytest -q tests/test_approval.py` | 저장소 맨 위 |
| 남은 시험 DB 보기, 치우기 | `.venv/bin/python tests/testdb.py`, `… --clean` | 저장소 맨 위 |

pytest 기본 옵션은 `pyproject.toml`의 `[tool.pytest.ini_options]`에 있다 [code:pyproject.toml]. 시험 폴더는 `tests` 하나이고, 비동기 시험은 `asyncio_mode = "auto"`로 따로 표시하지 않아도 돈다. 기본으로 붙는 옵션은 `-rs` 하나다. 건너뛴 시험이 있으면 그 까닭을 끝 요약에 한 줄씩 찍는다. 이 옵션이 생긴 까닭은 작업방에 셸 패널용 바이너리 폴더(`.tools`)가 없어 ttyd 시험이 조용히 건너뛰어진 일이다. `-q` 끝 줄에는 「1 skipped」라는 개수만 보여서, 하필 그 작업방에서 고친 코드가 터미널 프록시일 때 가장 필요한 시험이 빠진 것을 아무도 몰랐다 [log:test_isolation_20261114.md]. 작업방에 `.tools`를 원본을 가리키는 링크로 두고, 그래도 없을 때를 위해 `-rs`를 기본으로 넣었다 [c:1b286ca]. 반대로 `-l`(실패한 시험의 지역 변수를 모두 찍는 옵션)은 일부러 넣지 않았다. 시험 안에서 API 토큰을 지역 변수로 들고 있으면 실패할 때 그 값이 화면에 그대로 찍힌다 [code:pyproject.toml][log:test_isolation_20261114.md].

js 시험은 따로 돌리지 않아도 pytest 한 번에 같이 돈다. `tests/test_js.py`가 `node --test tests/js`를 하위 프로세스로 부르고, 종료 코드가 0이 아니면 출력 끝을 붙여 실패시킨다 [code:tests/test_js.py]. 그래서 관리자는 pytest 한 줄로 둘 다 본다. node가 서버에 없으면 이 시험은 「node 없음」으로 건너뛰고, 위의 `-rs` 덕에 그 까닭이 요약에 남는다.

`pyproject.toml`에는 `db` 표시도 등록되어 있다. 실행 중인 FOREMAN 전용 MySQL(루프백 3308 포트)이 있어야 도는 시험에 붙인다 [code:pyproject.toml]. 지금은 따로 걸러 돌리는 길을 쓰지 않고 늘 함께 돌린다. 서버에 DB가 늘 떠 있기 때문이다.

## 3. 시험 묶음의 짜임

지금 `tests/` 아래 파이썬 시험 파일(`test_*.py`)은 107개이고, pytest가 모으는 시험은 1,369개다(값을 바꿔 여러 번 도는 시험을 하나씩 센 수, js 시험을 부르는 시험 하나 포함) [code:tests/]. js 시험은 `tests/js/` 아래 40개 파일, 227개다 [code:tests/js/]. 시험 파일 하나하나는 그 시험이 지키는 기능을 설명하는 편이 머리 주석 「다루는 곳」에 둔다. 이 편은 아래 시험 장치와 여러 기능에 걸친 시험만 맡는다. 전에는 이 편이 시험 폴더 전체를 맡아서 시험 하나만 바뀌어도 이 편이 다시 볼 편으로 떴다 [log:foreman-5_docs_check_20261117.md]. 시험 파일 말고 시험을 돕는 파일과 폴더는 아래와 같다.

| 자리 | 하는 일 |
|---|---|
| `tests/conftest.py` | pytest가 뜰 때 시험 DB를 만들고 끝날 때 지운다. 표가 필요한 시험이 받는 고정물, 모든 시험의 훅 통과 기록 자리를 임시 폴더로 돌리는 고정물, 끝 요약 줄 [code:tests/conftest.py] |
| `tests/testdb.py` | 시험 DB 이름 짓기, 만들기, 남은 것 치우기. 손으로 부르는 명령도 이 파일 [code:tests/testdb.py] |
| `tests/screen_words.py` | 화면 말 검사기. 손으로도 돌릴 수 있다 [code:tests/screen_words.py] |
| `tests/fixtures/` | 승인 정책 시험용 설정 파일 둘 [code:tests/fixtures/] |
| `tests/data/screen_words.toml` | 바꾼 화면 이름, 예외, 호버 약속 목록 [code:tests/data/screen_words.toml] |

### 파이썬 시험

대부분은 기능 하나에 파일 하나다. 승인 규칙, 턴 조립, 합치기 준비, 포스트잇, 노션 게시처럼 편 하나가 다루는 기능마다 그 이름의 시험 파일이 있다. 시험이 무엇을 지키는지는 각 기능 편에서 함께 다룬다. 몇몇 시험은 여러 곳이 어긋나지 않는지를 맞대어 본다. 예를 들어 역할 목록 시험은 파이썬 한 곳(`bridge/roles.py`)과 JS 한 곳(`bridge/static/js/roles.js`), 그것을 쓰는 API와 화면 칸, 배지 색과 DB 역할 값이 모두 같은지 보고, 새 역할이 한 곳만 빠져도 실패한다 [code:tests/test_roles_agree.py]. 이런 시험은 → 05 역할과 권한에서 다시 본다.

코드와 문서가 어긋나지 않게 하는 장치에도 시험이 붙는다. 코드를 고친 세션이 그 코드를 가리키는 문서까지 함께 고치게 하려고, 브리지는 코더 세션의 첫 글 끝에 그 규칙과 「어느 문서가 걸리는지 거꾸로 찾는 도구」를 붙인다. 규칙 시험은 그 문장이 코더에게만 붙고 디자이너, 조사, 서기, 관리자에게는 붙지 않는지, 계획을 짜는 지시문에도 같은 줄이 있는지 본다 [code:tests/test_coder_docs_rule.py]. 거꾸로 찾는 도구의 시험은 임시 폴더에 가짜 저장소를 만들어 docs, 노션 원고, 포트폴리오가 고친 파일을 가리키는지 찾고, 도구가 파일을 읽기만 하고 바꾸지 않는지도 본다. 문서 폴더 아래 사진 같은 파일을 코드로 세지 않는지도 본다 [code:tests/test_docrefs.py]. 실패 알림이 저녁 묶음으로 미뤄지지 않는지는 브리지 코드 전체에서 알림을 부르는 곳을 훑어 본다. 실패를 말하는 글이 묶음 종류로 나가는데 바로 보내는 표시가 없으면 깨진다 [code:tests/test_fail_notify_scan.py]. 비밀값이 든 파일을 빠짐없이 가리는지, 공개되는 글에 비밀값처럼 생긴 글자가 없는지 보는 시험도 같은 꼴로 따로 있다 [code:tests/test_secret_files.py][code:tests/test_public_secret_shapes.py].

시험은 파일 하나만 혼자 돌려도 통과해야 한다. 당연해 보이지만 실제로 깨져 있었다. 몇몇 시험이 표를 스스로 만들지 않고, 앞서 돈 다른 시험이 올려 둔 표에 기대고 있었다. 전체를 돌리면 통과하는데 그 파일만 돌리면 「표가 없다」로 깨졌다. 한 시험은 혼자 돌려도 통과했는데, 그 까닭이 운영 DB에 표가 있어서였다. 시험이 운영 DB에 줄을 쓰고 지우고 있었던 것이다 [log:test_isolation_20261114.md]. 시험 파일 77개를 하나씩 혼자 돌려 찾았고, 표가 필요한 시험이 받는 공용 고정물 `migrated_db`를 두어 풀었다. 이 고정물은 pytest 한 번에 한 번, 이 폴더의 마이그레이션을 시험 DB에 올린다 [code:tests/conftest.py][c:424a9bf].

시험이 운영 파일에 쓰던 일은 DB 밖에서도 한 번 더 있었다. 브리지는 훅(작업 세션이 도구를 쓰기 전에 브리지에 묻는 장치)이 판정을 받지 못하고 그냥 통과할 때마다 그 까닭을 기록 파일 한 줄로 남긴다. 이 파일은 갈래마다 몇 번 일어났는지 세어 나중에 알림 문턱을 정할 재료다. 그런데 브리지 쪽 판정에 일부러 예외를 일으켜 보는 시험들이 기록 자리를 바꾸지 않아, pytest를 돌릴 때마다 실제 기록 파일에 가짜 줄이 쌓였다. 그대로 두면 거짓 통계와 거짓 알림이 된다 [log:foreman-5_hook_miss_test_isolation_20261115.md]. 그래서 모든 시험이 따로 부르지 않아도 받는 고정물을 두어, 시험마다 기록 자리를 임시 폴더로 돌린다. 시험이 하위 프로세스로 부르는 훅 스크립트도 같은 임시 폴더로 간다. 실제 기록 파일이 시험 뒤에도 그대로인지 보는 시험도 함께 두었다 [code:tests/conftest.py][code:tests/test_hookmiss.py]. 이렇게 시험이 운영 파일을 건드리지 않게 따로 떼는 것을 격리라고 부른다.

### js 시험

화면 쪽 코드 가운데 DOM 없이 돌릴 수 있는 순수 함수를 `node --test`로 시험한다. 테마의 자리 배치, 머리 위 표시를 쌓는 순서, 승인 카드의 위치, 마크다운 그리기, 셸 패널 칸 계산 같은 것이다 [code:tests/js/]. 화면은 번들러 없는 순수 JS라 따로 빌드할 것이 없고, 저장소의 모듈 파일을 그대로 불러 시험한다. 화면이 실제로 어떻게 보이는지(겹침, 잘림)는 이 시험이 아니라 헤드리스 브라우저 점검이 본다(→ 화면 점검과 시연).

### 시험 DB

DB를 쓰는 시험은 pytest를 돌릴 때마다 새로 만든 시험 DB에서 돈다. 이름은 `foreman_test_<자리>_<pid>`이다. 자리는 작업방 이름(원본 폴더면 `main`), pid는 그 pytest 프로세스 번호다 [code:tests/testdb.py]. pytest가 뜰 때 만들고 끝날 때 지운다. 강제로 죽어 남은 것은 다음 pytest가 뜰 때, 이름 끝 pid가 더 이상 살아 있지 않은 것만 골라 치운다. 다른 작업방에서 지금 돌고 있는 시험 DB는 건드리지 않는다.

이렇게 만든 까닭은 여러 세션이 같은 서버에서 동시에 시험을 돌리기 때문이다. 전에는 모두 공용 시험 DB 하나를 썼고, 두 세션이 동시에 돌리면 한쪽이 다른 쪽의 표를 지워 한 번에 31건이 실패한 일이 있었다 [docs:operations.md][log:repo_scope_readonly_20261109.md]. 시험 파일은 지금도 `Settings(mysql_database="foreman_test")`라고만 쓴다. 설정 읽기가 그 값일 때만 이번 pytest의 DB로 바꿔 읽으므로, 시험 파일을 고치지 않아도 새 시험이 저절로 갈린다 [log:test_db_per_session_20261111.md]. 만들기와 지우기는 정해진 이름 꼴에 맞는 것만 받아서, 운영 DB나 옛 공용 시험 DB를 지울 수 없다 [code:tests/testdb.py]. 시험 DB를 만들지 못하면 공용 DB로 돌되 시작 머리글과 끝 요약에 경고를 찍는다. 조용히 넘어가지 않게 한 것이다 [code:tests/conftest.py]. 마이그레이션 잠금을 DB마다 따로 잡는 것까지 포함한 자세한 내용은 → 마이그레이션에서 다룬다.

### 실제 설정 모양 시험

다른 시험은 대부분 실제 `config/*.toml`을 읽지 않고 임시 파일이나 고정물을 읽는다. 설정을 켜고 끌 때마다 시험이 깨지면 안 되기 때문이다. 실제로 합치기 설정 시험이 실제 설정의 값(사람 승인인지 관리자 승인인지)을 기대하다가, 사용자가 설정을 바꾸자 깨진 적이 있다 [log:test_live_config_20261112_result.md]. 그런데 그렇게만 하면 반대쪽 고장을 못 잡는다. 브리지는 설정을 못 읽으면 많은 곳에서 기본값으로 조용히 넘어간다. 역할 설정을 못 읽으면 역할 검사가 꺼지는 식이다.

그래서 실제 설정을 읽는 시험을 하나 따로 두었다. 이 시험은 값을 보지 않고 모양만 본다. 모든 `config/*.toml`이 읽히는지, 승인 규칙에 묻는 규칙이 하나라도 있는지, 알림 설정에 프로젝트마다 머리말이 있는지, 역할 설정이 오류 없이 읽히고 모드가 셋 가운데 하나인지, 사용량 가격과 한도 칸이 다 있는지 같은 것이다 [code:tests/test_live_config_shape.py]. 켬과 끔, 문턱, 가격을 바꾸는 것으로는 깨지지 않고, 오타나 빠진 칸이 생기면 깨진다. 작업방에서 돌리면 그 작업방의 `config/`를 읽는다.

실제 설정 값을 읽되 값 자체가 아니라 값끼리의 순서만 보는 시험도 하나 있다. 승인을 기다리는 한도는 세 곳에 겹쳐 있다. 브리지가 사람의 결정을 기다리는 시간, 훅 스크립트가 브리지 답을 기다리는 시간, Claude Code가 훅 스크립트를 기다리는 시간이다. 바깥쪽이 안쪽보다 길어야 사람이 결정할 때까지 끊기지 않는다. 그런데 저장소에 둔 훅 설정 견본의 한도가 실제 설정보다 훨씬 짧아, 그 견본으로 다시 깔면 Claude Code가 먼저 훅을 끊고 브리지만 계속 기다리는 상태였다 [log:foreman-7_hook_timeout_20261115.md]. 견본을 고치고, 실제 승인 설정과 스크립트, 견본의 세 값이 안쪽부터 차례로 길어지는지 보는 시험을 더했다 [code:tests/test_hook_timeouts.py]. 순서만 지키면 값을 바꿔도 깨지지 않는다. 사용자 홈의 Claude Code 설정은 기계마다 달라 이 시험이 읽지 않는다.

### 화면 말 시험

화면 말 시험은 화면에 뜨는 이름과 문서가 어긋나는 것을 기계로 찾는다 [code:tests/screen_words.py]. 세 가지를 본다. 화면 이름을 바꿨으면 옛 이름이 코드 문자열과 문서의 인용 안에 남으면 안 된다. 문서가 대괄호로 버튼 이름을 인용하면 그 글이 지금 코드에 있어야 한다. 호버 설명이 끌기나 더블클릭 같은 조작을 약속하면 약속 목록에 올라 있어야 한다. 목록은 `tests/data/screen_words.toml` 한 파일에 있고, 화면 말을 바꾼 사람이 거기 한 줄을 더한다. 옛 이름이 남아 걸린 문서는 이름을 바꾼 코더가 같은 브랜치에서 고친다. 고칠 수 없는 까닭이 있을 때만 목록의 「서기 몫」에 적고 통과시키며, 서기가 맞춘 뒤 그 줄을 지운다 [code:tests/screen_words.py]. pytest 끝 요약에는 서기가 맞출 몫이 몇 줄 남았는지, 시험이 없는 호버 약속이 몇 곳인지가 매번 찍힌다 [code:tests/conftest.py]. 판정 규칙과 고치는 법은 → 화면 점검과 시연에서 다룬다.

## 4. 원고가 시험을 깨뜨린 일

문서 점검도 pytest가 돈다. 명령 `tools/docs.py check`와 같은 판정을 이 저장소 작업 트리에 돌려, 틀린 것이 하나라도 있으면 시험이 깨지고 실패 글에 틀린 줄(파일, 줄, 까닭)이 처음 몇 개 나온다. 의심은 실패시키지 않는다. 점검을 카드 한 줄로만 보이게 하면 아무도 안 볼 때 문서가 조용히 낡는다. 깨지게 만드는 것은 시험뿐이어서 시험에 걸었다. 작업 트리 판이라 아직 커밋 안 한 새 원고도 본다 [code:tests/test_docs_selfcheck.py] [code:bridge/doctext/check.py]. 새 시험 파일은 그 기능 편 머리의 다루는 곳에 넣어야 점검의 덮기 검사를 통과한다. 점검에는 새 줄의 em dash와 가운뎃점 검사도 들어 있어서, 기준 커밋 뒤로 문서나 코드 주석에 둘을 새로 쓰면 이 시험도 깨진다(→ 「근거 확인과 물어보기」) [code:bridge/doctext/dashdot.py].

노션 원고를 처음 쓰고 pytest를 끝까지 돌렸을 때 1,060개 가운데 화면 말 시험 하나만 실패했다(js 209개 포함, 약 3분). 원고의 코드 근거 표시(대괄호 안에 `code:`와 파일 경로를 쓴 것)를 시험이 문서가 인용한 버튼 이름으로 읽었고, 그런 버튼 글이 코드에 없으니 「버튼 이름이 코드에 없다」로 걸렸다. 원고가 틀린 것이 아니라 검사기가 새 근거 표시 종류를 몰랐던 것이다. 원고 쪽에서 근거 표시를 바꾸지 않고 시험 쪽을 고쳤다. 화면 말 시험이 근거 표시 종류를 근거 확인기의 정규식 한 곳에서 가져오게 했다 [code:tests/screen_words.py] [c:e5d584b]. 원고를 쓰는 세션은 시험 코드를 고치지 않으므로, 이런 실패는 원고를 합치기 전에 관리자가 코더에게 넘겨 먼저 풀어야 한다. 자세한 판정은 → 화면 점검과 시연에서 다룬다.

## 5. 배포는 유닛 재시작

FOREMAN에는 「배포」라는 단계가 따로 없다. 브리지는 systemd 사용자 유닛 `foreman-bridge`로 돈다. 유닛의 실행 폴더가 곧 저장소 원본 폴더이고, 실행 명령은 그 폴더의 `.venv`로 `python -m bridge`를 띄우는 한 줄이다 [code:deploy/systemd/foreman-bridge.service]. 받아올 코드도, 만들 이미지도 없다. 합친 코드를 반영하는 일은 `systemctl --user restart foreman-bridge` 한 줄이고, 그동안 10초 남짓 끊긴다 [docs:operations.md].

이 한 줄은 사람이 친다. push할 때마다 자동으로 다시 띄우지 않는다 [docs:00_design.md]. 다시 띄우면 기다리고 있던 승인이 끊기고, 화면 연결이 끊기고, 방금 커밋한 그 세션의 hook까지 끊길 수 있다. 그래서 화면 데이터에서 승인 대기 수가 0인지 보고 나서 다시 띄운다. 끊긴 승인이 사람 눈에 어떻게 보이는지, 왜 「조용한 고장」이 되는지는 → 브리지가 뜨는 차례에서 자세히 다룬다. 시험, import 확인, 대기 0 확인을 한 스크립트로 묶는 안도 있었지만 아직 만들지 않았다 [docs:00_design.md].

| 유닛 칸 | 값 | 뜻 |
|---|---|---|
| `Type` | `simple` | 띄운 프로세스가 곧 브리지다 |
| `Restart`, `RestartSec` | `on-failure`, `5` | 실패로 죽으면 5초 뒤 다시 띄운다 |
| `StartLimitIntervalSec`, `StartLimitBurst` | `300`, `10` | 5분 안에 10번까지 다시 시도한다 |
| `OnFailure` | `foreman-bridge-alert.service` | 위 한도에 걸려 systemd가 포기하면 브리지 밖 알림 유닛을 부른다 |
| `KillMode`, `TimeoutStopSec` | `mixed`, `20` | 멈출 때 주 프로세스에 먼저 알리고, 20초 넘으면 강제로 끝낸다 |
| `Environment` | `PATH=…`, `PYTHONUNBUFFERED=1` | 아래 설명. 로그를 바로바로 내보낸다 |
| `WantedBy` | `default.target` | 사용자 매니저가 뜰 때 함께 뜬다 |

표의 값은 모두 유닛 파일에 있다 [code:deploy/systemd/foreman-bridge.service]. 다시 시도 횟수를 넉넉히 둔 까닭은 DB다. MySQL은 도커가 올리는데 사용자 유닛은 도커가 먼저 뜬다는 순서를 보장하지 못한다. 그래서 부팅 직후 DB가 아직 없으면 브리지는 실패하고, 5초마다 다시 시도하다 DB가 올라오면 붙는다. `PATH`에는 사용자의 npm 전역 폴더를 넣었다. 브리지가 `claude`를 불러 계획을 세우고 인계 요약을 쓰는데, 처음 유닛으로 옮겼을 때 이 폴더가 빠져 있어 이틀 동안 계획 세우기가 「claude를 띄우지 못했습니다」로 실패했다. 그 사이 인계 요약 요청이 없어 같은 고장이 드러나지 않았다 [code:deploy/systemd/foreman-bridge.service]. 지금은 브리지가 뜰 때 `claude`를 찾아 보고, 못 찾으면 로그와 계획 거절 사유로 알린다.

다시 시도에는 끝이 있다. 5분 안에 10번을 넘기면 systemd는 다시 띄우기를 포기하고 유닛을 실패 상태로 둔다. 그런데 텔레그램 알림은 평소 브리지가 보내므로, 브리지가 죽은 바로 그때는 아무도 알리지 못한다. 가장 알려야 할 고장이 가장 조용해지는 셈이다. 그래서 유닛에 `OnFailure` 한 줄을 두어, 포기하는 순간 systemd가 따로 둔 알림 유닛을 부르게 했다 [code:deploy/systemd/foreman-bridge.service]. 알림 유닛은 한 번 돌고 끝나는 유닛이고, 브리지 코드나 파이썬 환경을 쓰지 않는 셸 스크립트 하나로 텔레그램을 보낸다 [code:deploy/systemd/foreman-bridge-alert.service]. 브리지가 아직 다시 뜨는 중일 때는 보내지 않고 정말 포기했을 때만 보내며, 글에는 다시 띄운 횟수와 오류 종류만 싣고 로그 내용은 싣지 않는다. 이 스크립트도 시험이 있다 [code:tests/test_bridge_alert.py][log:foreman-6_bridge_alert_20261115.md]. 유닛을 어디에 두고 어떻게 부팅 때 띄우는지는 → 어디에 두었나에 있다.

## 6. GitLab과 Jenkins에 태우지 않는다

이 서버에는 GitLab과 Jenkins로 이어지는 CI/CD 길이 이미 있다. 런슈즈 같은 서비스는 그 길로 이미지를 만들어 Harbor(이미지 저장소)에 올리고 클러스터에 배포한다. FOREMAN은 이 길에 태우지 않았다 [docs:00_design.md][code:CLAUDE.md].

까닭은 그 길이 하는 일이 FOREMAN에 하나도 해당되지 않기 때문이다. 그 길의 끝은 이미지인데 FOREMAN에는 이미지가 없다. 화면은 번들러 없는 순수 JS를 저장소에서 그대로 내고, 브리지는 작업 폴더에서 바로 돈다. 태우려면 Jenkinsfile을 새로 쓰고, Jenkins 쪽에 시험 DB를 마련하고, 인프라 저장소를 고쳐야 한다. 얻는 것 없이 「다른 프로젝트와 같게」만 맞추는 일이 된다 [docs:00_design.md]. 브리지와 DB를 클러스터 밖 호스트에 둔 까닭(감시하는 쪽이 감시받는 쪽과 함께 죽지 않게)과도 이어진다. 클러스터가 흔들릴 때 FOREMAN의 배포 길까지 같이 흔들리면 안 된다(→ 어디에 두었나). FOREMAN은 거꾸로 그 CI/CD 길을 지켜보는 쪽이다(→ 12 CI/CD 인과 체인).

## 7. 버전은 requirements.lock로 묶는다

의존성은 두 파일에 나눠 적는다. `pyproject.toml`에는 호환 범위만 적고(예: FastAPI는 0.162 이상 1 미만), 정확한 버전은 `requirements.lock`에 `pip freeze`로 묶는다 [code:pyproject.toml]. 지금 lock 파일에는 시험 도구(pytest, pytest-asyncio)까지 38개 패키지가 정확한 버전으로 적혀 있다 [code:requirements.lock]. 파이썬은 3.14 이상을 요구한다.

묶는 까닭은 이 프로젝트에서 `.venv` 하나를 여럿이 함께 쓰기 때문이다. 작업방마다 `.venv`를 새로 만들지 않고 원본의 `.venv`를 가리키는 링크를 둔다 [docs:operations.md]. 운영 브리지, 관리자의 시험, 작업방 코더들의 시험이 모두 같은 패키지로 돈다. 그 환경을 다시 만들어야 할 때(서버를 옮기거나 `.venv`가 망가졌을 때) 범위만 있으면 그날의 최신판이 깔려 지금 통과하던 시험이 왜 깨지는지 알 수 없게 된다. lock 파일이 있으면 지금과 같은 환경을 그대로 되살릴 수 있다. 다만 lock을 고르게 된 까닭을 따로 적은 기록은 없고, 위는 지금 쓰는 모양에서 읽은 것이다.

의존성 하나가 빠진 것이 시험으로 잡히지 않은 일도 있었다. MySQL 8은 재시작으로 인증 캐시가 비면 RSA로 전체 인증을 하는데, 그때 드라이버가 `cryptography` 패키지를 요구한다. 처음에는 이것이 빠져 있었지만 캐시가 이미 차 있어 DB 시험이 모두 통과했고, DB를 다시 띄우는 시험에서야 드러났다 [log:stage1_bridge_db_result.md][c:1ec1bfd]. `pyproject.toml`의 그 줄 옆에 까닭이 주석으로 남아 있다 [code:pyproject.toml].
