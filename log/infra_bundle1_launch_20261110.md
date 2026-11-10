# 인프라 묶음 1 세션(265) · 인프라 방 등록 코더(266) 띄움 (2026-11-10 저녁, 원본 폴더, 관리자 244)

앞 기록: [merge_designer_grid_20261110.md](merge_designer_grid_20261110.md)

## 사용자 지시

- 인프라 묶음 1: runshoes replicas 2 + anti-affinity · petmint anti-affinity 확인 · Harbor DB pg_dump 백업 + 복구 시험 · w4 생성 · w1 ~ w3 증설(4 → 8GB), 문서(펫퍼민트 docs 우선 · 인프라 · 런슈즈), 알려진 한계. 알아서 진행 · push도 · w1 직전에만 알림 · 확인 실패면 되돌리고 멈춤. 묶음 2는 나중
- 방은 만들되 인프라 작업은 기다리지 않는다. 순서: ① 떠돌이 인프라 세션으로 바로 시작 ② FOREMAN 코더가 인프라를 프로젝트로 등록 ③ 인프라 docs/를 만들고 Notion 자동 게시
- 시작 전에: ① 런슈즈 정리 작업 임시로 막기(ShedLock은 런슈즈 세션에 따로) ② 승인 카드를 이 작업 동안 풀고 끝나면 다시 걸기, 증설 중 펫퍼민트 배포 금지

## 미리 본 것(읽기만)

- 호스트 메모리 61GB, 쓸 수 있는 것 35GB. 묶음 1 뒤 VM 합 16 → 36GB
- 펫퍼민트: `apps/petmint/README.md`에 replicas 2 · required anti-affinity · PDB(minAvailable 1) — 설정이다. 롤링이 2+1이라 워커 3대가 다 필요하다(74줄)
- 런슈즈 `ActivityCleanup` `@Scheduled(cron = "${app.activity.cleanup-cron}")`, `ACTIVITY_CLEANUP_CRON` 기본 `0 0 4 * * *`, Spring Boot 3.5.16 → **임시로 deployment env `ACTIVITY_CLEANUP_CRON: "-"`(cron 끄기)**, replicas 2와 같은 커밋 이전에. 코드 주석은 "멱등"이라 했지만 사용자는 충돌을 막기로
- 승인: 앞서 "인프라 저장소가 민감 경로라 drain에도 카드가 뜬다"고 말한 것은 **틀렸다** — `~/ronanlab-infra`는 통째로 지우기 목록에만 있다. 실제로 걸릴 것은 운영 DB DROP · PVC/네임스페이스 삭제 · VM 안 poweroff 정도. 떠돌이 세션은 `[defaults]`를 따른다(`bridge/approval.py for_project`)

## 한 일

- `config/approval.toml` `[defaults] mode` enforce → **observe(임시, 사용자 지시)**. 살아 있는 떠돌이 세션이 없어 사실상 인프라 세션에만 걸린다. FOREMAN은 `[projects.foreman] enforce` 그대로. 승인 대기 0 확인 뒤 **브리지 18:50:03 다시 띄움**
  - **되돌릴 것**: 인프라 방 등록(266)을 합친 뒤 defaults를 enforce로, 묶음 1이 끝나면 `[projects.ronanlab-infra]`도 enforce로
- **세션 265**(opus, coder, `~/ronanlab-infra`, worktree 없이 — ArgoCD가 main을 본다): `/api/spawn`으로 띄움. 처음 쓰는 폴더라 CC 신뢰 확인 창(기본 선택이 "No, exit")이 떠 관리자가 "Yes, I trust this folder"로 옮겨 확정 → 지시문이 들어가 시작. 지시문: 사용자 원문 + 위 「미리 본 것」 + 다른 세션(259 런슈즈 코더 · 260 펫퍼민트 서기)과 docs 겹침 주의 + 되돌릴 수 없는 것은 하지 않기
  - 교장 경로가 아니라 계획 기록(dispatch)이 없다 — 인프라가 프로젝트가 아니어서
- **세션 266**(코더 · opus, dispatch 218, `cc/foreman`): 인프라를 프로젝트 `ronanlab-infra`(화면 「인프라」)로 등록 — project 표 · 박힌 곳(terminal · office.js · overlap · notify · approval observe · notion off) · 출하장 비움 · 265가 합친 뒤 인프라 방 소속이 되는지

## 266 합침 · 265 옮김 (19:4x)

- 266 커밋 넷: 인프라 등록(0029 시드, 출하장 「출하장 없음」) · **사용자가 266에 직접 더 시킨 것** — 인프라도 「다른 저장소 읽기만」 + 예외 `[repo_scope.writable]`(런슈즈 · 펫퍼민트 원본 docs/만 Edit · Write), 그 저장소 git은 경로 적은 `add` · `commit`만 허용 · **push 막음** · worktree 안내(`wt_block`)에서 FOREMAN만의 규칙 빼기(런슈즈 세션 요청)
- `merge-tree` 충돌 없음 → `end:true` 합침(`361801a` ~ `9adbc65`) → 다른 pytest 없음 확인 뒤 **564 통과** → push
- `bridge.db.migrate` → 0029 적용(project id 4, 포먼 35 · 코더 36)
- 265는 저절로 안 옮겨진다(이미 '미분류' 캐릭터 4에 붙음, 266 기록) → `UPDATE character_session SET character_id=36 WHERE id=265 AND character_id=4`(1행)
- `approval.toml` `[defaults] mode` observe → **enforce로 되돌림**(인프라 임시 observe는 `[projects.ronanlab-infra]`가 맡음). 승인 대기 0 → **브리지 19:43:18 다시 띄움**(경고 없음)
- 확인: `/api/dashboard` 인프라(label 「인프라」)에 265 coder ACTIVE. `screen.py --no-term` 오피스 · 현장 1366 좁게 · 넓게 × [⌂] · 인프라 방 점검 0, 사진: 머리줄 「인프라 작업 1」, 방 아래 줄 「출하장 없음」 · 코더가 커밋 데스크, 현장 현황판 넷째 칸 「인프라」, 패널 목록 「인프라 — 265」
- **알아둘 것(뒤에 정함)**: 사용자 — 런슈즈 · 펫퍼민트 docs 커밋은 관리자가 확인하고 push. 265에 "커밋까지만 · 해시 남기기" 보냄. 첫 커밋 런슈즈 `d27e1ba`(docs 3개, 265)를 관리자가 확인했으나 **관리자 push도 reposcope에 막혀** 사용자가 직접 push(`3dc5e3b..d27e1ba`) → 사용자: 규칙 고쳐라 → 코더 267(dispatch 232) `49d1585` `[repo_scope.manager_push]`(role manager + 원본 폴더 세션만, origin/main보다 앞선 커밋이 전부 docs/일 때) → `merge-tree` 충돌 없음 · `end:true` 합침 · **570 통과** · push · 244 DB 역할 manager · cwd 원본 · worktree 없음 확인 · 승인 대기 0 → **브리지 21:00:50**. 실제 push는 다음 docs 커밋 때(먼저 `log --stat origin/main..main`)
- (처음 적은 것) 265 지시문에는 "push도 네가 한다"가 있었는데, 이제 런슈즈 · 펫퍼민트 docs는 커밋까지만 되고 push는 막힌다(사용자가 266에 정한 규칙). 그 두 저장소 docs push는 누가 할지 사용자에게
