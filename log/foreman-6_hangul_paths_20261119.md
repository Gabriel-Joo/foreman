# 문서 도구의 한글 이름 파일 고장 (11-19, 코더 foreman-6, 관리자 410)

규칙 위반 없음. 시작한 main 커밋은 `14c40a8`.

## 한 일

git은 기본값(`core.quotepath=true`)으로 한글 이름을 `"data/review/answer_\352\261..md"`처럼 따옴표와 8진수로 내보낸다. 문서 도구는 그것을 줄 단위로 읽어, 그런 파일이 `not_code`와 `records`에 걸리지 않고 덮기 밖으로 세어졌다.

- `bridge/doctext/repo.py`: `git()`이 늘 `-c core.quotepath=false`를 붙인다. 파일 목록용 `git_z()`(명령 이름 뒤에 `-z`를 넣고 `\0`로 나눔)를 새로 두고 `tree()`가 그것을 쓴다. 따옴표로 싸인 경로를 알아보는 `is_quoted()`와 알림 글 `quoted_problem()`도 여기 한 곳에 둔다.
- `bridge/doctext/check.py`: 작업 트리 편 목록(`ls-files --cached --others`)을 `git_z`로 읽는다. 덮기 계산 앞에서 따옴표 경로가 있으면 덮기 대상에서 빼고 틀림 하나(「git이 경로를 따옴표로 내보내 파일 이름을 읽지 못했습니다(경로). 같은 경로 N개를 덮기 대상에서 뺐습니다」)로 알린다.
- `bridge/doctext/dashdot.py`: 이미 `core.quotepath=off`였던 `_git`을 `false`로 맞췄다. 추적 안 하는 파일 목록은 `-z`로 읽는다. diff 머리 읽기를 `_header_path()` 한 곳으로 모으고, 따옴표 경로가 오면 `DashDotError`(점검에서 「줄표, 가운뎃점 검사를 돌리지 못했습니다: …」 틀림)로 알린다.
- `bridge/docrefs.py`: 바뀐 파일 목록(`diff --name-only`)을 `git_z`로 읽는다. `changed_lines`는 diff 머리에 따옴표 경로가 오면 `DocrefsError`를 낸다(호출한 쪽이 경고로 띄운다). 일감 밖이지만 같은 고장의 반대쪽이라 하나 더 고쳤다(아래 「설계와 달랐던 점」).
- 시험 `tests/test_docs_hangul.py` 12개. 한글 이름 가짜 저장소에서 덮기 대상 수와 `records`와 `not_code` 거름, 덮기 밖 글의 바른 이름, 작업 트리의 새 한글 편, 따옴표 경로 알림(덮기, 줄표 검사, 거꾸로 찾기), `refs --range`와 `changed_lines`, 줄표 검사의 한글 새 파일과 diff. 고치기 전 코드에서 10개가 실패하는 것을 확인했다(stash로 `bridge/`만 잠시 치워 봄).
- 문서: `docs/12_scribe.md` 문서 문법 묶음 줄, `docs/11_worktree.md` 도구 줄, `notion/10_scribe/03_evidence.md`(한글 이름 문단 추가, 다루는 곳에 새 시험 파일).

## 설계와 달랐던 점

- 일감 7자리 가운데 `dashdot.py` 112(diff)는 이미 `core.quotepath=off`로 읽고 있었다. 그래서 `dashdot.py`는 이름 읽기 자체가 아니라 `ls-files --others`의 `-z`와 따옴표 경로 알림이 고친 몫이다.
- 따옴표 경로를 알리는 길은 `-z`로 읽는 목록에서는 생기지 않는다(`-z`는 싸지 않는다). 실제로 나올 수 있는 곳은 diff 머리뿐이라(따옴표, 역슬래시, 제어 글자가 든 이름은 `quotepath=false`여도 싸인다) 거기서 잡고, 파일 목록 쪽 검사는 설정이 풀리거나 새 길이 생길 때를 위한 안전망이다. 시험은 목록 쪽을 모의 `tree`로 본다.
- 일감에 없던 것: `docrefs.TOKEN`이 백틱 안 경로를 `[A-Za-z0-9_./*-]`로만 읽어, 문서가 `` `bridge/한글.py` ``처럼 한글 이름 파일을 가리키면 `bridge/`와 `.py` 조각으로 쪼개져 거꾸로 찾기가 그 문서를 걸지 못했다. `\w`로 넓히고 경로다운지 보는 글자 검사(`[A-Za-z]`)를 모든 글자로 넓혔다. 같은 고장이 거꾸로 찾기의 문서 쪽에 있어서다. 되돌리려면 `TOKEN`과 `_pathlike` 두 줄이다.
- diff 머리에서 공백이 든 이름 끝에 git이 붙이는 탭은 이번에 고치지 않았다(한글과 무관, 전부터 그랬다).

## 다른 저장소 재기(읽기만)

덮기 대상 가운데 덮은 수. 「전」은 FOREMAN, 런슈즈, 인프라는 관리자가 잰 값을 그대로 옮겼고(이쪽에서 다시 재지 않았다), 펫퍼민트는 main 코드로 오늘 같은 방법으로 다시 쟀다. 「후」는 모두 이 브랜치 코드로 쟀다.

| 저장소 | 전 | 후 | 틀린 것 후 |
|---|---|---|---|
| FOREMAN | 504 / 504 | 505 / 505 (새 시험 파일 포함) | 0 |
| 런슈즈 | 827 / 827 | 827 / 827 | 0 |
| 인프라 | 112 / 112 | 112 / 112 | 0 |
| 펫퍼민트 | 341 가운데 230(관리자 기록은 341 가운데 10) | 298 가운데 235 | 79(전 259) |

펫퍼민트에서 따옴표 경로로 덮기 밖에 세어진 것은 52줄에서 0줄이 됐다(`덮기 밖: "` 줄 수). 덮기 대상이 341에서 298로 43개 줄어든 것은 한글 이름 기록(`records`)과 `not_code` 파일이 제대로 걸러졌기 때문이다. 덮기 밖 전체 줄은 111에서 63으로 줄었다. 남은 63줄은 진짜 덮이지 않은 파일이다(이 일 밖). 관리자가 잰 「341 가운데 10」과 오늘 main 코드로 잰 「230」이 다른 까닭은 기록에 없다(그 사이 펫퍼민트 쪽이 바뀌었을 수 있다). 펫퍼민트 틀린 것에는 줄표와 가운뎃점 검사가 건 것이 섞여 있고 이번 고침과 무관하다.

거꾸로 찾기: 펫퍼민트 `--range origin/main~20..origin/main`은 전후 같다(그 범위에 따옴표 이름 파일이 없다). `origin/main~150..origin/main`(한글 이름 파일 6개가 바뀐 범위)은 걸리는 문서 18, 안 고침 0으로 같고, 바뀐 코드 파일 221개가 214개로(한글 이름 기록 7개가 코드에서 빠짐), 바뀐 문서가 78개에서 82개로(한글 이름 문서 4개가 문서로 잡힘) 달라졌다. 새로 걸린 문서는 없다.

## 문서 도구 밖에서 git 출력을 줄 단위로 읽는 곳(고치지 않음, 따로 정한다)

`-z` 없이 이름을 읽는다. quotepath 설정을 따로 안 주면 한글 이름이 싸인다.

- `bridge/overlap.py` 282, 283, 317, 323(`diff --name-only`, `ls-files --others`, `status --porcelain`). 세션 사이 겹침이라 한글 이름 파일이 겹침으로 잡히지 않는다.
- `bridge/worktree.py` 383, 434와 `bridge/mergeprep.py` 878, 1288, 840(`diff --name-only`, 충돌 파일). 합치기 카드와 충돌 목록의 이름.
- `bridge/roleguard.py` 384(`diff --cached --name-only`, `-z` 없음).
- `bridge/evidence.py` 136, `bridge/handoff_state.py` 115, `bridge/promote.py` 227, `bridge/scribe.py` 54, `bridge/notion.py` 562(`ls-tree`, `-z` 없음), `bridge/pipeline.py` 731(개수만).
- `bridge/reconcile.py`, `bridge/coder_room.py`, `bridge/worktree.py`의 `status --porcelain`은 더러움 여부만 보면 영향이 작다.
- 이미 `-z`로 읽는 곳: `bridge/manuscript.py`, `bridge/docsync.py`, `bridge/reposcope.py`, `bridge/notion.py` 775, 1597, `bridge/worktree.py` 188.

## 시험

pytest 1490 통과, node 244 통과, `tools/docs.py check` 틀린 것 0, `docs.py readme`는 이미 같음. 합치기 카드의 거꾸로 찾기는 커밋 뒤에 안 고친 것이 0인지 본다. 실제 브리지나 합치기 카드 화면은 보지 않았다.

## 사람이 정할 것

- 위 「문서 도구 밖」 목록을 고칠지와 순서. 한 번에 `bridge/` 공용 git 함수로 모으는 길이 있다(`overlap`, `worktree`, `mergeprep`이 각자 git을 부른다).
- `docrefs.TOKEN`의 한글 확장을 이 브랜치에 둘지(일감 밖).
- 펫퍼민트에 남은 덮기 밖 63줄과 틀린 것 79개는 펫퍼민트 관리자 몫이다.
