# 세션 역할 「관리자」(manager) · 제목 앞 역할 · 이름표는 역할만 · 세션 번호 (2026-11-09, worktree foreman-3)

세션 242(`cc/foreman-3`). 지시 중간에 사용자 요청 둘이 더 왔다 — ① 캐릭터 이름표와 패널 머리줄 나누기 ② 세션 번호를 화면에. 같이 했다.

## 한 일

### 역할 `manager`(화면 "관리자")
- 역할 목록 다섯 곳을 맞춤: `bridge/handoff.py` `ROLE_KO`(역할 캐릭터 이름 · 인계 물려주기의 허용 목록) · `bridge/foreman.py` `ROLES` + 계획 프롬프트(관리자 = 코드 안 고치고 거두는 일, 상주 아님, 콕 집어 맡길 때만) · `bridge/api/handoff.py` `SessionRole`(`NewIn.role` · 새 `RoleIn`) · `bridge/wake.py` `ROLE_KO` · `config/models.toml` `[defaults] manager = "opus"`
- 인계(새 세션으로 옮기기) 물려주기: `spawn()`이 `role if role in ROLE_KO else None` — `ROLE_KO`에 넣어 관리자 → 관리자. 시험으로 확인
- 화면 목록 `modelpick.js` `ROLE_PICK`([＋ 세션] · 교장 계획 카드)에 관리자 + **서기**
  - 서기가 빠져 있던 것은 원래 있던 빈틈 — 교장이 `role: "scribe"` 계획을 내도 계획 카드의 역할 칸에 그 값이 없어 첫 값(코더)이 골라지고, [시작]이 그 칸 값(`fmRole`)을 보내 코더로 떴을 것이다(화면에 아무 표시 없이)
- 테마 넷 역할 색에 `manager: #c0392b`(빨강 — 다른 역할 색과 겹치지 않게), `tests/js/theme.test.mjs` 역할 목록에 보탬

### 역할 바꾸기 API `PUT /api/sessions/{sid}/role {role}`
- 허용 값만(pydantic `SessionRole` — `foreman` · 모르는 값 · null은 422), 없는 세션 404, `set_role`의 거부는 409 `{"refused"}`
- `HandoffManager.set_role`: `character_session.role` + 그 역할 캐릭터로 옮김(`_character_for` — 원본 폴더 "관리자", worktree "관리자 foreman-3", 새 세션 역할 캐릭터와 같은 규칙. 프로젝트 밖이면 캐릭터 그대로) → `session_action` `role` "옛 → 새 캐릭터 N"(`action` VARCHAR(12), 스키마 변경 없음). 같은 역할이면 아무것도 쓰지 않음
  - 역할만 바꾸고 캐릭터를 두면 아래 줄이 "코더 foreman-3 · 관리자"처럼 엇갈려서 같이 옮겼다
- 화면: 패널 머리줄 역할 배지를 누르면 그 자리에 고르기 칸(코더 · 관리자 · 서기 · 점검 · CI/CD), 바꾸면 API. 실패 사유는 입력 칸 아래 결과 줄

### 관리자 캐릭터 자리 — 감독실 안 옆자리(사용자가 골랐다)
- 테마마다 `layout.zones.manager.seats` 두 자리(팀장실 · 교장실 · 소장실 · 도형 감독실 안). 일할 때도 그 자리(도구 따라 구역으로 가지 않음), 플래그 모습(손 들기 등)은 그대로. 작업 책상 수 · "+N"에 들지 않음. 상주 아님 — 세션이 있을 때만
- 자리는 사진에서 빈 바닥을 골라 `layoutAudit`(모든 구역 좌석을 가구 · 이름표와 맞대는 점검)로 확인. 상주 코더(`isCoder` = 역할 없음 · coder)로는 원래 잡히지 않는다

### 이름표 · 머리줄 · 세션 번호(사용자 요청 둘)
- **캐릭터 이름표는 역할만**: `[관리자]` · `[코더]` · `[서기]`, 임시 일꾼은 `[코더] 임시`(점선 테두리 그대로), 끝남 · 멈춤 꼬리 그대로. 쉬는 상주 코더 · 서기도 `[코더]` · `[서기]`. 감독실 캐릭터 · 인프라 · 서브에이전트는 그대로
- **캐릭터 호버** 첫 줄 `[관리자] 세션 230`(임시면 `· 임시`), 다음 줄 제목
- **패널 머리줄 두 줄**: 첫 줄 역할 배지 · `세션 230` · [넓게] ✕ ▶, 둘째 줄 제목(폭 전체, 한 줄 말줄임). 처음엔 한 줄 `[코더] 세션 242 — 제목`으로 했는데 좁은 패널(1920 기본 폭)에서 제목이 "서" 한 글자로 줄어 바꿨다. 사용자 예시 "관리자 — 제목"의 줄표는 두 줄이라 뺐다
- 제목 고치기(`pTitle` → `custom_title`)는 제목만 — 역할은 `character_session.role`에서만 그린다. 툴팁 "제목 — … 눌러서 고칩니다. 역할은 바뀌지 않습니다."
- 세션 목록(패널) 줄: 상태 · 역할 배지 · 번호 · 제목. classic 화면 카드 · 머리에도 배지
- `render.js`: `ROLE_LABEL`(scribe · manager 보탬, foreman "감독" 그대로) 내보냄 · `SESSION_ROLES` · `roleTag` · `roleBadge`. `sessionSub`(아래 줄)는 역할을 다시 쓰지 않고 캐릭터 이름에서 역할을 뗀 나머지("코더 foreman-3" → "따로 작업 foreman-3", "코더" → 없음)

## 조사 결과

- "역할 없음"은 실제로 생기지 않는다: FOREMAN 밖에서 띄운 CC 세션은 `assembler.py`가 행을 만들 때 **늘 `coder`**(캐릭터 기본 역할이 아니라 고정값), 터미널 셸은 `helper`(도우미). 밖에서 띄운 세션 대부분이 코딩 세션이라 [코더]로 두고, 아니면 배지를 눌러 바꾼다. `[역할?]` + 호버는 역할 값을 모를 때(목록에 없는 값 · null)만
- [전체] 카드에는 세션 이름이 없다(방마다 작업 중 N · 멈춤 — …). [전체] 화면에서 역할이 보이는 곳은 캐릭터 이름표 — 이름표 변경이 그 몫

## 시험 · 점검

- `tests/test_session_role.py` 7개: 역할 목록 다섯 곳 일치 · 모델 기본값 opus · `set_role`(갱신 · 캐릭터 · `session_action` 글 · 화면 갱신) · 같은 역할 무시 · 거부(foreman · 모르는 값 · 빈 값) · 인계 물려주기(관리자 → `spawn_new(role="manager")`) · API 200 / 422 / 404 / 409 · `NewIn` 관리자
- `tests/js/role_label.test.mjs` 4개: 이름표 · 배지(제목을 `[코더] …`로 고쳐도 배지는 관리자) · 아래 줄
- 전체 pytest **541 통과 · 1 건너뜀**(JS 63 포함, 다른 pytest 없음을 `pgrep -af '[p]ython -m pytest'`로 확인한 뒤)
- `tools/screen.py --ui-scale 1.25` 미리보기(:8200) 세 테마 × 1920 · 1366 · 1024
  - 실제 데이터 × [⌂] · [전체] · FOREMAN · 런슈즈 · 펫퍼민트(`--session 242`): 45화면 점검 **0**
  - 새 시연 장면 `bridge/static/demo/roles.json`(관리자 둘 · 상주 코더 · 임시 · 서기, 런슈즈 관리자 하나) × [⌂] · [전체] · FOREMAN · 런슈즈(`--session 230`): 36화면 **0**
  - "audit(고정 안 됨)" 10 · 13 · 14는 고치기 전 사진(같은 미리보기)과 같은 수
  - 1024에서는 머리줄 첫 줄이 좁아 ▶ 버튼이 한 줄 내려간다(잘리지는 않음)

## 설계 · 지시와 달랐던 점

- 머리줄을 한 줄 "역할 — 제목"이 아니라 두 줄로(위 까닭)
- 역할 바꾸기가 역할 캐릭터도 옮긴다(브리프는 `character_session.role` 갱신만)
- 사용자 "역할은 못 고치게" — 제목 고치기로는 못 바꾸게 했다. 브리프 3번의 역할 바꾸기 버튼(머리줄 배지 누르기)은 그대로 두었다
  - **사용자 결정(11-10): 배지로 바꾸기는 남긴다** — "띄운 뒤에 바꿀 일이 생긴다. 어제 230이 그랬다. 제목 고치기로는 안 바뀌게 한 것으로 충분하다"
- `ROLE_PICK`에 서기를 보탠 것은 브리프 밖(위의 원래 빈틈)
- 규칙 어김: 시험 파일 import 한 줄을 Bash `sed -i`로 고쳤다(CLAUDE.md는 Edit · Write만). 내용은 `from bridge.model_choice import Models` · `Models()`로 맞는다. 사용자(11-10): "sed -i 쓴 것은 앞으로 하지 마라. Edit · Write로만" — 시험 파일 · 한 줄 고치기도 예외가 아니다

## 합친 뒤 확인(원본 세션 몫)

1. 브리지를 다시 띄운다(승인 대기 0 본 뒤) — `ROLE_KO` · API · models.toml이 파이썬 쪽
2. 자기 세션을 관리자로: `curl -s -X PUT -H "Authorization: Bearer $FOREMAN_API_TOKEN" -H 'Content-Type: application/json' -d '{"role":"manager"}' http://127.0.0.1:8000/api/sessions/230/role` → `"changed": true`, `character_id`(새 "관리자" 캐릭터) 확인. DB `session_action` 맨 끝 `role` "coder → manager 캐릭터 N"
3. 화면: 230이 팀장실(교장실 · 소장실) 안 옆자리에 `[관리자]`로 서는지, 패널 머리줄 `[관리자] 세션 230` / `FOREMAN main`, 세션 목록 줄에 배지 · 번호
4. 배지를 눌러 다른 역할로 바꿨다가 되돌려 본다(두 번 다 `session_action`에 남는다)
5. 제목을 고쳐도 배지가 그대로인지
6. [＋ 세션] 역할 칸에 서기 · 관리자, 교장 계획에서 서기 계획이 서기로 뜨는지(다음에 서기를 띄울 때)
7. `tools/screen.py --ui-scale 1.25 --demo roles`로 세 테마 한 번 더(원본 브리지에서)
8. 미리보기 :8200(`fm-pv-foreman-3`)은 합치기 · 버리기 때 정리되는지 본다
