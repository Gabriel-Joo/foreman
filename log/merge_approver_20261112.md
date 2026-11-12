# 승인 지옥 줄이기 — 합치기(코더 C, worktree `cc/foreman-4`, 2026-11-12)

사용자 결정(11-12): 합치기 승인 · 품질 판단 · 정리 후보 고르기를 프로젝트 관리자에게 넘긴다. 이 세션은 합치기 쪽만(알림 묶음은 코더 B, `pipeline.py`는 코더 311).
처음엔 모든 프로젝트가 지금 동작(사람 승인 · ff)이다 — 켜기는 합친 뒤 관리자가 `config/handoff.toml`에서.

## 한 일

| 무엇 | 어디 |
|---|---|
| 프로젝트마다 승인자 `approver = human \| manager` · `squash` · `human_paths` | `config/handoff.toml [merge_prep.per_project.<이름>]`, `bridge/mergeprep.py` `ProjectRule` · `load` |
| 승인자가 관리자면 카드가 생길 때 그 프로젝트 관리자 세션에 알림(`manager_of(c.repo)` → deliver, 뒤에서). 글에 커밋 · 바뀐 파일 · 충돌 · 승인 API · 카드 목록 API. 못 보내면 텔레그램 + 그 카드는 사람 승인으로 | `MergePrep._card_msg` · `_tell_manager_card` |
| 관리자 승인: `POST /api/sessions/{sid}/merge-prep {"action":"merge","by":"manager"}`. 프로젝트 토큰이면 `by`는 저절로 manager. 승인자가 사람인 프로젝트 · 늘-사람 카드면 409와 까닭. `skip`도 같은 규칙 | `api/handoff.py` `MergePrepIn.by`, `MergePrep.approve(by)` · `skip(by)` · `_manager_may` |
| 관리자가 자기 카드를 모아 봄: `GET /api/merge-prep?project=<이름>` — 그 프로젝트 카드만 + `approver` · `squash`. 프로젝트 토큰은 `?project=자기`로만(그 밖 403) | `scopetoken._FOREMAN_QUERY`, `api/handoff.py merge_prep_list`, `MergePrep.view(project)` |
| 정리 후보 고르기: 승인자가 관리자이고 늘-사람에 안 걸린 카드는 합친 뒤 관리자 글이 「관리자가 골라 지운다(card.docs, 카드는 6시간 남음) — 판단이 안 서는 줄만 사람에게」. 그 밖은 예전 글(사람 승인 뒤) | `MergePrep._merged_msg` |
| 늘 사람에게 올릴 것 — 승인자가 관리자여도 걸리면 그 카드는 사람 승인. 까닭은 `card.human_why` · `card.note`(패널에 이미 보이는 칸) · 관리자 글 · 텔레그램에 | `human_reasons` · `parse_raw` · `_human_why`, `config/handoff.toml [merge_prep.human_always]` |
| 프로젝트 토큰이 `POST …/worktree {"action":"merge"}`(패널 길)로 늘-사람 카드를 돌아 합치는 것도 409 | `api/handoff.py worktree_act` |
| squash 합치기: rebase까지 같고, 브랜치 트리로 `commit-tree`(부모 = 원본 끝) → 원본에서 `merge --ff-only`. 글은 `합침(cc/<이름>, 커밋 N개): <첫 제목>` + 「원래 커밋(오래된 차례)」 `- 날짜 제목` 줄 + Co-Authored-By 모음. 원본 트리 = 브랜치 트리일 때만 브랜치 `-D`(아니면 남기고 알림). 커밋 하나면 그냥 ff. 결과 `squash`(해시) · 「커밋 N개를 커밋 하나로 묶어」 글이 카드 · 관리자 글 · session_action에 | `bridge/worktree.py` `merge(squash)` · `squash_message` · `remove(drop_branch)` |
| 패널 [합치기]도 같은 squash 설정을 따르게: `worktree_act`(고치지 않은 `bridge/handoff.py`)가 `wt.merge(repo, name)`으로 부르므로 `wt.SQUASH_OF` 훅에 `MergePrep.squash_for_repo`(project.repo_path → 설정)를 넣음 | `worktree.SQUASH_OF`, `MergePrep.__init__` |
| 시험 — 설정 읽기 · 지금 설정이 모두 사람 · ff인지 · 늘-사람 판정 · `--raw` 읽기 · 관리자 승인 흐름 · 관리자 거부 둘 · 관리자 없음 · 정리 후보 글 · squash 훅 · API(`?project=`, 토큰 = manager) · squash 합치기(글 · 차례 · `-D`) · squash 충돌 | `tests/test_mergeprep.py` · `tests/test_worktree.py` · `tests/test_scopetoken.py` |

시험: `pytest -q` 775 통과 · 1 건너뜀, `node --test tests/js/` 123 통과.

## 늘-사람 판정 — 기계로 가르는 것 · 못 가르는 것

| 목록(사용자 확정) | 판정 | 비고 |
|---|---|---|
| 설정 · 값 파일(`values*.yaml`, `config/*.toml`) | 경로(`paths`) | fnmatch, 경로 전체 또는 파일 이름 |
| 자원 크기 | **반만** — `*.yaml` · `*.yml` 차이에서 `cpu · memory · replicas · limits · requests · storage · ephemeral-storage:` 줄이 바뀌면 | values 파일은 경로로 이미 걸린다. Helm 템플릿 식(`{{ .Values… }}`) · JSON · Terraform 같은 다른 꼴은 못 본다 → 관리자 규칙 |
| CLAUDE.md · 규칙 문서 | 경로 — 공통 `CLAUDE.md` · `AGENTS.md` · `.claude/*`, FOREMAN은 `docs/style_guide.md` · `docs/operations.md`를 `human_paths`로 더함 | 프로젝트마다 규칙 문서가 다르다 — `human_paths`로 더한다 |
| 마이그레이션 | 경로 `*migrations/*` · `*db/migration/*`(Flyway) · `*alembic/versions/*` | |
| 이력 다시 쓰기 · force push · 지우기 | **반만** — 지우기 = 파일을 지운(`D`) 커밋. 이력 · force push = 커밋 글에 `force push` 등 말이 있으면 | 합치기 자체는 ff라 이력을 다시 쓸 수 없다. 관리자가 합친 **뒤** 하는 force push는 카드로 못 본다 → 관리자 규칙(사람에게 먼저) |
| 다른 저장소 | **반만** — 서브모듈(gitlink 160000) 바뀜만 | 세션이 다른 저장소를 고친 것은 이 저장소 git에 안 남는다. 다른 저장소 쓰기는 이미 브리지가 PreToolUse에서 막는다(`bridge/reposcope.py`, 11-09) → 관리자 규칙 |
| 사람이 직접 쓴 글을 고친 것 | **못 함** | 이 저장소 커밋 467개가 모두 작성자 `ronanlabs`, Co-Authored-By 없는 것 1개 — git blame으로 가를 수 없다(사람 말을 세션이 받아 적어 커밋한다). 사람이 쓴 문서를 알면 `human_paths`에 더하고, 나머지는 관리자 규칙: 「사람 말을 옮긴 줄(인용 · 결정 문장)을 지우거나 바꾸는 합치기는 사람에게」 |

가르지 못해 틀리는 쪽은 사람에게 올리는 쪽으로 두었다(판정이 실패하면 사람 승인, 커밋 글에 `force push`를 적기만 해도 사람 — 이 브랜치도 `config/handoff.toml`을 바꿔 사람 승인이다).

## 설계와 달랐던 점 · 판단 근거

- **`bridge/handoff.py`(맡은 파일 밖)를 고치지 않으려고 squash는 훅으로**: 패널 [합치기]와 카드 승인 모두 `HandoffManager.worktree_act → wt.merge(repo, name)`이라, `merge`가 `squash=None`이면 `wt.SQUASH_OF(repo)`에 묻는다. 합치기 준비가 꺼져 있으면(훅 없음) 늘 ff — squash는 `[merge_prep] enabled`일 때만 산다
- **`merge --squash` 대신 `commit-tree` + `merge --ff-only`**: 원본 작업 트리에서 squash 합치기를 돌리면 실패했을 때 원본 인덱스를 되돌려야 한다(원본에는 다른 세션 변경이 있을 수 있다). 트리로 커밋을 먼저 만들고 ff하면 실패 꼴이 지금과 같다
- **카드 상태는 `ready` 그대로, 승인자는 `approver` · `human_why` · `note` 칸으로**: 새 상태(예: 관리자 기다림)를 만들면 화면(`handoff.js` `MP_STATUS` · 단추)과 대시보드 `merge_waits`를 고쳐야 한다 — 맡은 파일 밖이라 멈추고 묻는 몫. `note`는 패널이 이미 보여 주므로 까닭은 화면에 뜬다
- **FOREMAN 관리자는 관리 토큰을 쓴다** → 브리지가 사람 화면과 가를 수 없어 `by:"manager"`를 스스로 적게 했다(칸막이지 벽이 아니다 — scopetoken 머리말과 같은 선). 프로젝트 토큰은 늘 manager로 본다
- **승인자가 사람(지금 동작)이면 관리자에게 카드 알림을 보내지 않는다** — 처음엔 지금 동작 그대로라는 지시를 따랐다. 관리자로 켠 프로젝트만 카드 생김을 관리자에게
- **관리자 세션이 없으면 그 카드는 사람 승인**(note에 「관리자 세션이 없어」). 알림 실패도 사람으로 돌린다
- 텔레그램 카드 생김은 지금처럼 notifier(`_notify`)에 — 글 끝만 「관리자 세션이 승인합니다」 / 「⚠ 사람 승인 — 까닭」으로 바뀐다. 하루 묶음은 B

## 남은 것 · 물을 것

- **화면**: 승인자가 관리자인 카드도 사람의 승인 막대(대시보드 `merge_waits`, status=ready)와 세션 패널 [합치기]에 그대로 뜬다(사람이 눌러도 된다 — 막지 않음). 사람 막대에서 빼려면 `bridge/api/dashboard.py merge_waits`에서 `approver == "manager"`를 빼고 `handoff.js`에 「관리자가 승인합니다」 표시를 더해야 한다 — 화면 일이라 이번엔 하지 않았다(사용자가 정할 것)
- 켜기: 합친 뒤 관리자가 `[merge_prep.per_project.foreman]` · `[…ronanlab-infra]`의 `approver = "manager"` · `squash = true` + 브리지 다시 띄우기. 관리자 세션 CLAUDE.md에 승인 API · 늘-사람 거부 · 정리 후보 고르기를 적는 것도 그때
- 런슈즈 · 펫퍼민트는 `[merge_prep] projects`에 없어 카드가 아직 안 생긴다(지금 그대로)

## 되돌리는 법

- 설정만: `config/handoff.toml`에서 `approver = "human"` · `squash = false`(지금 값) + 브리지 다시 띄우기 → 지금 동작
- 코드: 이 브랜치를 합친 커밋을 `git revert`. 마이그레이션 · DB 바뀜 없음(카드는 메모리, session_action detail 글만 늘었다). squash로 합친 커밋은 보통 커밋이라 revert로 되돌린다

## README에서 뺄 줄

- 「승인 지옥 줄이기」 줄은 **합치기 몫(관리자 승인 · 늘 사람 · squash)을 이번에 했다**. 「다 되면 한 번만 보고」(알림 묶음)는 코더 B 몫 — 둘 다 합친 뒤 뺀다
