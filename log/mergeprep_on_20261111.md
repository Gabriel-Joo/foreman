# 합치기 준비 켬 · 시험 세션 280으로 두 길 확인 (2026-11-11 오후, 원본 폴더, 관리자 276)

앞 기록: [merge_wave1_20261111.md](merge_wave1_20261111.md). 만든 세션의 기록: [coder_lifecycle_20261111.md](coder_lifecycle_20261111.md)

## 켬(사용자 지시)

- `config/handoff.toml [merge_prep]` `enabled = true` · `projects = ["foreman"]`(런슈즈 · 펫퍼민트에는 아직 카드가 가지 않음) — `fdc78f3`
- 승인 대기 0 확인 뒤 **브리지 15:23:06**. 로그 「합치기 준비 켬: 60초마다, 1단계」, `/api/merge-prep` = `enabled true · stage 1 · health ok · cards 0`

## 시험 세션 280(코더 · sonnet, `/api/spawn` worktree `foreman-2`)

시킨 것: `log/mergeprep_trial_20261111.md` 하나를 커밋(제목에 README 「시험 DB를 세션마다 나누기」 줄의 낱말), 「main을 가져와 풀라」를 받으면 rebase로 두 쪽 줄을 다 남기고 풂.

| 길 | 한 것 | 본 것 |
|---|---|---|
| 충돌 | 280 커밋 `af518a9` 뒤 관리자가 main에 같은 파일을 다르게 커밋(`8c90f57`) → 카드 다시 훑기 → 승인 | 카드 `ready` · 충돌 `log/mergeprep_trial_20261111.md` · behind 2 · ff 아님. 승인 → `conflict_sent` 「세션을 끝내지 않고 그 세션에 「main을 가져와 풀라」를 보냈습니다」, main · worktree 그대로 |
| 풀기 | 280이 메시지를 받아 rebase, 두 쪽 줄 남김 → `8af40be` | merge-tree 충돌 없음 |
| 깨끗한 합치기 | **다시 훑기를 부르지 않고** 자동 훑기(60초)를 기다림 → 승인 | 15:25:08 새 카드 `ready` · 충돌 없음 · ff · behind 0. 승인 → `merged`, 세션 280 끝냄 · fast-forward · worktree 지움, **관리자 세션에 「[FOREMAN 합치기] … 합쳤다 … 정리 후보 3개」가 들어옴**(`manager_told: true`) |

- README 정리 후보(카드 `docs.readme`): ① 928 「시험 DB를 세션마다 나누기」(낱말 db · foreman_test · 세션마다 · 시험) ② 899 「스키마 잠금 단위」(db · 합치기) ③ 908 「운영 → 브리지」(시험 · 합치기). 후보가 붙는 것을 확인. **실제로 뺄 줄은 없다** — 시험 커밋 글에 일부러 그 낱말을 넣은 것이라 ①도 아직 할 일이다. ② · ③처럼 낱말 둘로 걸리는 것은 헛걸림이 섞인다(그래서 지우기는 사람 승인 뒤)
- 브리지 로그: `mprep-card`(충돌) → `mprep-conf` → `mprep-card`(충돌 없음) → `mprep-merge`. 겹침 감시도 「같은 파일 — 276 · 280: 바탕에 이미 든 것 뺌」으로 C1의 헛경보 고침이 돈 것을 보임
- **확인 못 한 것**: 카드가 생길 때 텔레그램(`notify_ready`)이 실제로 나갔는지 — 브리지 로그에 보낸 줄이 없다. 사용자 텔레그램에서 확인 요청
- 시험 세션 280 `hidden_reason='test'`로 숨김. 띄우기 기록 `dispatch` 맨 끝 = `spawn · started`(C1 ④)
- `log/mergeprep_trial_20261111.md`는 시험 흔적으로 남김(두 쪽 줄)

## D2 띄움 — 첫 번째는 실패

- 교장 경로(dispatch 310)로 띄웠는데 「45초 안에 새 세션을 찾지 못했습니다」. tmux `cc-foreman-2` 화면에 `claude: command not found` — `~/.npm-global/bin/claude` 링크가 15:26에 새로 생겼다(CC 자동 업데이트로 보임). 띄운 시각 15:26:57과 겹쳐 잠깐 실행 파일이 없었다
- 커밋 0 · 변경 0 · 세션 행 없음을 본 뒤 tmux 닫고 `git worktree remove` · `git branch -d cc/foreman-2`
- **조용한 고장**: 세션이 안 떴는데 dispatch 310 · dispatch_session이 `started`(session_id 없음)로 남았다 → 관리자가 `failed` + 사유로 고침. 띄우기가 세션을 못 찾으면 기록도 `failed`가 되고 알림이 가야 한다(C1 ④ 「실패한 띄우기도 failed로」는 예외로 실패한 경우만 잡는다 — 「45초 안에 못 찾음」은 note로만 돌아온다)
- 다시 띄움: dispatch 311 → **세션 281**(디자이너 · sonnet, `.worktrees/foreman-2`), ACTIVE. 지시문 `log/plan_structure_20261111.md` 「D2」 + 공통 규칙 + 시험 DB 겹침 주의 + 합치기 준비가 켜져 있음(끝내지 말고 기다림)

## 다음

- 합치기 준비는 그대로 켜 둔다(사용자). D2가 이 카드를 쓰는 첫 실제 세션
