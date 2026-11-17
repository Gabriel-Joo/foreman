# 생성물 덮기 빼기, 차례 번호 칸, 소개 굵은 표시 벗기기 (foreman-7, 2026-11-17 밤)

관리자 410 일감. 커밋 셋으로 나눴다.

## 한 일

### 1. 생성물을 덮기 대상에서 뺌 (`f979ee1`)
- `bridge/doctext/readme.py`에 `GENERATED = (PATH,)`를 두었다. 생성기가 쓰는 파일 목록 한 곳이다. 지금 생성기가 쓰는 파일은 맨 위 `README.md` 하나뿐이다(`tools/docs.py readme`가 쓰는 곳은 `readme.PATH`뿐임을 코드에서 확인했다). 새 생성물이 생기면 이 목록에 더한다.
- `bridge/doctext/check.py` 덮기: `[readme]` 표가 있는 저장소(`cfg.readme is not None`)만 그 목록을 대상에서 뺀다. 저장소가 `not_code`에 손으로 적지 않는다. 표가 없으면 지금처럼 대상이다.
- `bridge/docrefs.py` 거꾸로 찾기가 `path == "README.md"`로 따로 적어 두었던 같은 규칙을 같은 목록(`readme.GENERATED`)을 보게 맞췄다. 동작은 같다. 규칙이 두 곳에 흩어지지 않게 한 줄만 바꿨다(`bridge/doctext/` 밖 한 줄).
- 시험 `tests/test_docs_check.py::test_cover_skips_generated_readme`: 표 없음은 대상, 표 있음은 맨 위 README.md가 빠지고 덮기 밖 틀림이 안 남음, 다른 폴더의 `apps/README.md`는 그대로 대상.
- `.md`는 덮기에 남긴다는 앞 기록(`log/foreman-6_cover_not_code_20261117.md`)의 판단은 손으로 쓴 문서 이야기이고, 이번은 만들어지는 글이라 따로다.

### 2. 문서 차례 번호 칸 (`ed06236`)
- 칸 이름: `[readme] docs_numbered_only = true`(기존 `[check] numbered_only`와 같은 말). 켜면 docs 차례에 `NN_`로 시작하는 파일만 넣는다. 기본 false, 안 적으면 지금처럼 `*.md` 전부.
- `config.py`에서 불리언 검사(`docs`와 같은 오류 문장), `readme.doc_rows(numbered_only=)`, `check.readme_build`가 넘김.
- 시험: 설정 오류 둘(`"yes"`, `1`), tmp 저장소로 끔과 켬 둘 다(`TODO.md`, `style_guide.md`가 켜면 빠지고 `00_design.md`는 남음, 점검 9번 통과).
- FOREMAN `.foreman/docs.toml`은 건드리지 않았다. 켤지는 아침 판단.

### 3. 소개 문단 굵은 표시 벗기기 (`a16fd35`)
- `readme.intro`가 문단 전체를 굵은 글 하나(`**...**`)로 감싼 꼴일 때만 그 표시를 벗긴다. 굵은 글이 둘 이상이거나 일부만 굵은 문단은 그대로.
- FOREMAN 소개 문단이 통째 굵은 글이었으므로 `README.md`를 `tools/docs.py readme`로 다시 만들어 같은 커밋에 넣었다(소개 줄 하나만 바뀜).
- 시험 `test_intro_unbolds_whole_paragraph_only`.

## 문서
`docs/12_scribe.md` 점검 줄과 README 생성 줄, `notion/10_scribe/03_evidence.md` 두 곳, `bridge/doctext/readme.py` 머리 설명, `config.py` 머리 칸 표. `refs --range main...HEAD --unfixed`에 남는 것은 `bridge/docrefs.py`를 가리키는 다른 편(`notion/08_handoff/04_move.md`, `notion/09_dispatcher/01_plan.md`, `portfolio/07_merge.md`)과 `notion/10_scribe/02_postit.md`(docs/12_scribe.md로 걸림)다. 앞 셋의 걸린 문단은 이번에 바꾼 한 줄(README 건너뛰기 목록)과 상관없는 내용이라 그대로 두었다. 마지막 하나는 포스트잇 이야기라 걸림만 알린다.

## 덮기 수(대상, 덮음), 읽기만

| 저장소 | 고치기 전 | 고친 뒤 | 까닭 |
|---|---|---|---|
| FOREMAN | 496, 496 | 495, 495 | `[readme]`가 있어 README.md가 빠짐 |
| 인프라 | 113, 113 | 113, 113 | `.foreman/docs.toml`에 `[readme]`가 아직 없어 그대로. 인프라는 이 셋이 합쳐진 뒤 표를 넣는다 |
| 런슈즈(작업방 `foreman-tool`) | 828, 828 | 828, 828 | 같은 까닭. 작업방 커밋이 앞 기록 때와 달라 수가 앞 기록(830, 825)과 다르다 |

인프라 README 미리 보기(`--repo ~/ronanlab-infra readme --dry`, 표가 없어도 미리 보기는 됨): 소개 문단이 굵은 표시 없이 나온다(인프라 포트폴리오 00편이 문단 전체를 굵게 쓴 꼴이다). docs 차례는 인프라에 `[readme]`가 없어 보지 못했다.

## 시험
- pytest 전체 1419개 통과, `node --test tests/js/` 227개 통과
- `tools/docs.py check`: 틀린 것 0, 새 줄 줄표 0, 덮기 495 가운데 495
- `tools/docs.py readme`: 이미 같음

## 판단이 필요해 고치지 않은 것
- 앞 커밋 `ed06236`에서 `readme.py`의 상수 줄 사이 줄바꿈이 빠져 그 커밋 시점에는 `readme.py`가 불러와지지 않는다(F 커밋 `a16fd35`에서 바로잡음). 합치기 전에 커밋을 다시 짜지 않았다. 둘을 한꺼번에 합치면 끝 상태는 맞다. 나누어 이어 보는 사람에게만 영향이 있다.

## 규칙 위반 없음
다만 위 커밋 줄바꿈 실수는 규칙 위반이 아니라 편집 실수다. Bash 검사기가 몇 번 일시적으로 판정을 못 해 같은 명령을 다시 쳤다.

## 아침에 사람이 정할 것
1. FOREMAN `[readme]`에 `docs_numbered_only = true`를 켤까(켜면 docs 차례에서 `roles.md`, `style_guide.md`, `operations.md` 같은 번호 없는 글이 빠진다. 지금 README에는 `00_design.md` 같은 번호 글과 이 글들이 함께 있다)
2. 앞 커밋의 깨진 줄바꿈 때문에 커밋을 다시 짤지, 그대로 합칠지
3. 인프라와 런슈즈에 `[readme]` 표를 넣는 때(이번 변경이 합쳐진 뒤)
