# 줄표 검사에 not_code 거름을 넣음 (foreman-4, 2026-11-19)

규칙 위반: 있음 (아래 「규칙 위반」)

- 시작한 main 커밋: `97abf04`
- 일감: 관리자 410(펫퍼민트 관리자 부탁, FOREMAN 사용자 승인 11-19)

## 한 일

- `bridge/doctext/config.py`에 `not_code_skip(patterns)`를 더했다. `not_code`에서 확장자 `.md`만 뺀 무늬를 돌려준다.
- 덮기 검사(`check.py`)가 따로 적던 `[p for p in cfg.not_code if p != ".md"]`를 이 함수로 바꿨다. 줄표 검사도 같은 함수를 부른다.
- `bridge/doctext/dashdot.py`의 `wanted()`가 `not_code` 무늬를 받아 덮기 검사와 같은 판정(`config.not_code_match`)으로 거른다. `hunks`, `scan`, `for_repo`가 이 값을 넘긴다.
- 추적하지 않는 파일을 빼지 않았다. 같은 `wanted()`를 지나므로 거름에 들지 않는 새 파일은 그대로 걸린다.
- 시험: `tests/test_manuscript_rules.py` `test_not_code_and_records_filter_untracked_and_tracked`.
- 문서: `docs/12_scribe.md` 줄표 검사 줄, `notion/10_scribe/03_evidence.md` 줄표 문단. 기준 문서 `docs/manuscript_rules.md`는 바꾸지 않았다.

## 조사 결과

- records 거름은 이미 두 길 모두에 있었다. `for_repo`가 `skip = records + TOOL_DIRS`를 `wanted()`에 넘기고, 추적하는 파일의 diff와 추적하지 않는 파일 목록이 모두 `wanted()`를 지난다. 빠진 것은 `not_code`뿐이었다.
- 추적하는 파일 쪽도 같은 고장이었다. 고친 코드를 `wanted()` 한 곳에 두어 추적하는 파일의 고친 줄도 `not_code`에 들면 빠진다. 시험이 이 쪽(`data/tracked.py`)도 확인한다.
- 덮기 검사에서는 `readme.GENERATED`와 `header_file`도 거르지만, 줄표 검사는 README를 보는 대상으로 두므로 이번에 옮기지 않았다.

## 시험과 재기

- 새 시험이 통과하고, `not_code`를 주지 않으면(옛 동작) 거를 파일 둘이 더 걸리는 것도 같은 시험에서 확인했다.
- 펫퍼민트 재기(읽기만, 2026-11-19). 펫퍼민트 원본 폴더 HEAD `95eea99`. 재는 동안 그 폴더의 `.foreman/docs.toml`은 커밋 전 변경이 있었고, 작업 트리판 `not_code` 끝에 `"data/search_experiments.py"`가 이미 들어 있었다(사람 결정, 펫퍼민트 쪽 줄). 그래서 설정을 둘로 나누어 main 코드(고치기 전, 원본 폴더 `b2b4210`)와 이 브랜치 코드(고친 뒤)를 같은 때에 나란히 쟀다. 재는 스크립트는 스크래치의 `measure.py`(코드 루트, 저장소, 설정판을 받아 `dashdot.for_repo`만 돌림).
  - 넣기 전 판(`git show HEAD:.foreman/docs.toml`, `not_code`에 그 파일 없음): 두 코드 모두 그 파일이 걸린다(전도 후도 포함, 나머지 틀림은 펫퍼민트 문서 작업 중인 것). 그 파일은 그대로 걸리는 것이 맞다.
  - 작업 트리판(그 파일이 `not_code`에 있음): main 코드는 틀림 59건에 그 파일 6건 포함, 브랜치 코드는 53건에 그 파일 없음. 이 차이 6건이 거름이 도는 증거다.
  - 추적하지 않는 다른 파일 가운데 `not_code`나 `records`에 들면서 줄표 검사 대상 확장자인 것(`.py`, `.js`, `.css`, `.toml`, `.sh`)은 펫퍼민트에 없다. 추적 안 하는 파일은 `data/review/*.md`와 `docs/archive/*.md`뿐이라 둘 다 원래 검사 밖이다. 그래서 펫퍼민트로는 「넣기 전 판에서 빠지는 파일」을 확인할 수 없었고, 거름 확인은 위 작업 트리판 전후 차이와 시험으로 했다.
  - 관리자 410이 옮기라고 한 「고치기 전」 값(관리자가 main 코드로 넣기 전 판에서 쟀다, 내가 다시 재지 않았다): 펫퍼민트 원본 폴더 HEAD `95eea99`, `.foreman/docs.toml` `records = ["log/", "docs/ops/", "backups/"]`, `not_code`는 `.md`, `.png`, `.jpg`, `.svg`, `.lock`, `*package-lock.json`, `*package.json`, `*tsconfig*.json`, `*vite.config.ts`, `.gitignore`, `*/.gitignore`, `.claude/*`, `.foreman/*`, `data/review/*`, `models/gguf/Modelfile.*`(`data/search_experiments.py` 없음). 추적 안 하는 파일 63개 가운데 줄표 틀림에 걸린 것은 `data/search_experiments.py` 하나(가운뎃점 3줄 등), `docs/archive/`와 `data/eval/`은 0건. main 코드 줄표 검사 「기준 커밋 261913e 뒤 새 줄에서 50건」. 이 판에서는 그 파일이 `not_code`에 들지 않아 고친 뒤에도 걸리는 것이 맞고, 거름이 도는지 보일 파일이 펫퍼민트에 없다. **펫퍼민트로는 확인할 수 없었다, 시험으로만 확인했다**(위 작업 트리판 전후 차이 6건은 보조 증거).
  - 고친 뒤 값을 이 브랜치 코드로 한 번 쟀다(`tools/docs.py --repo <펫퍼민트> check`). HEAD는 그때도 `95eea99`였으나 작업 트리의 `.foreman/docs.toml`이 이미 바뀌어 있어(그 파일을 `not_code`에, `docs/archive/`를 records에 넣음) 넣기 전 판이 아니다. 결과는 「새 줄에서 52건」이고 그 파일은 없다. 관리자 값 50건과 맞댈 수 없다(설정이 다르고, 펫퍼민트 docs가 작업 중이라 그 사이 줄이 바뀌었다). 그래서 「50건 그대로」인지는 이 쟀음으로 확인하지 못했다. 넣기 전 판 설정을 그대로 두고 쟀을 방법은 앞의 `measure.py`로 `HEAD` 설정판을 읽는 것뿐이었고, 그 값은 두 코드 모두 200건(그 파일 포함, `docs/archive/`도 걸림)으로 서로 같았다. 관리자 값 50건과 다른 것은 `measure.py`가 작업 트리의 고치는 중인 docs를 읽고 HEAD판 records에는 `docs/archive/`가 없어서다. 까닭을 더 가르지는 않았다.
  - 앞서 한 `tools/docs.py check` 재기(전 6건, 후 6건)는 그 파일이 `not_code`에 들기 전 판이어서 변화가 없었다. 위 값이 대신 증거다.

- 시험 차례대로: `tools/docs.py check` 틀린 것 0, pytest 1493건 통과, `node --test tests/js/` 244건 통과.

## 설계와 달랐던 점

- 일감은 `records` 거름도 빠졌다고 보았으나 이미 있었다. 고친 것은 `not_code` 하나다.

## 규칙 위반

- 영어 진행 글: 2026-11-19, 시험 파일을 쓰고 `config`를 `dcfg`로 고치기 전후에 도구 호출 사이 짧은 진행 글 두 번(「Test goes in after…」, 「The test file imports…」)을 영어로 썼다. 쓰기 전에 첫 낱말을 보지 않았다. 훅이 알려 준 뒤 바로 한국어로 돌아왔다.
- 그 밖에 heredoc, sed, `python -c`, `pgrep -f`는 쓰지 않았다.

## 사람이 정할 것

- 펫퍼민트의 `data/search_experiments.py` 6건을 어떻게 할지(지우기, `.gitignore`, `not_code` 가운데). 다른 저장소라 쓰지 않았다.
- 덮기 검사의 생성물과 `header_file` 거름(`readme.GENERATED`)을 줄표 검사에도 같이 적용할지. 지금은 README를 줄표 검사 대상으로 둔다.
