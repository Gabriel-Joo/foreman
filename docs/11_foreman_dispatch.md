# 11 — 포먼이 세션을 띄운다 · 자동 인계 (설계, 2026-11-05)

[+ 세션]을 사람이 다 정하던 것(프로젝트 · 새로/인계 · 어느 요약 · 역할)을 포먼이 판단한다. 사람은 "뭘 하려는지"만 말하고,
포먼이 낸 계획을 보고 승인한다. 지금의 [+ 세션] 창(직접 고르기)은 그대로 남긴다 — 포먼이 틀리거나 안 될 때 쓴다.

## 0. 먼저 바로잡을 사실

- 프로젝트 CLAUDE.md는 거의 비어 있다: 런슈즈 461B · 펫퍼민트 390B(한국어 · 텔레그램 규칙뿐). 규칙 · 구조는
  **CC 자동 메모리**(런슈즈 10개 13KB · 펫퍼민트 15개 20KB, `~/.claude/projects/<cwd>/memory/`)와 **docs/**(193KB · 495KB)에 있다
- 새 CC 세션은 그 폴더의 CLAUDE.md와 메모리 색인(MEMORY.md)을 **스스로** 읽는다 — 포먼이 그 내용을 새 세션에 다시 넣을 필요는 없다.
  포먼이 넣어야 하는 것은 **세션이 자동으로 못 보는 것**: 이번 일에 맞는 docs 위치, 직전 인계 요약, 압축으로 잃은 결정(점검 목록), 지금 상태(파이프라인 · 다른 세션)
- 압축 손실 점검에서 "살아남은 것"은 대부분 메모리에 적힌 것이었다 — 오래 갈 규칙은 메모리(또는 CLAUDE.md)로 옮기는 게 근본 대책이다(포먼이 제안 · 사람이 승인)

## 1. 포먼 세션 — 상주가 아니라 "부를 때만"

| 방식 | 장점 | 단점 |
|---|---|---|
| 상주(tmux에 늘 떠 있는 포먼) | 대화하듯 이어 갈 수 있다 | 컨텍스트가 쌓여 결국 압축 — 오늘 런슈즈에서 본 손실이 포먼에게도. 쉴 때도 맥락이 낡는다 |
| **부를 때만(추천)** — 요청마다 `claude -p` 한 번 | 매번 새 맥락(브리지가 지금 상태를 모아 줌), 압축 없음, 판단이 재현 가능(같은 입력 → 기록) | 대화가 이어지지 않는다(되묻기는 계획 안의 질문으로) |

- 실행: 브리지가 "상황 묶음"(2절)을 만들어 `claude -p --model sonnet --output-format json`에 넣는다. 도구는 읽기만(Read · Grep · Glob — docs를 찾아보게), 쓰기 · 셸 없음. 작업 폴더는 어느 프로젝트도 아닌 브리지 전용 폴더 `~/.foreman/dispatch`다(`bridge/foreman.py` `ForemanDispatcher.workdir`). 이 폴더에서 돌아 교장에게는 CLAUDE.md가 저절로 읽히지 않는다 [log:manager318_overhead_20261113.md]. 이 문서는 처음 FOREMAN 저장소라고 적었지만 코드는 처음 만든 커밋부터 이 폴더였다(`98b4e23`). 설계와 달라진 까닭은 기록에 없다
- 출력은 정해진 모양의 계획(JSON, 3절). 자유 대화가 아니다
- 나중에 포먼을 "말 거는 캐릭터"(상주)로 키울 때도 이 디스패처를 그 안에서 부르면 된다 — 순서를 바꿔도 버리는 게 없다

## 2. 맥락을 어디서 — "상황 묶음"(브리지가 만든다, LLM 없이)

| 출처 | 무엇 | 크기(대략) |
|---|---|---|
| 프로젝트 목록 | 이름 · 저장소 경로 · 브랜치 · 최근 커밋 5 · 더러운 파일 수 | 1k 토큰 |
| CLAUDE.md · 메모리 색인 | 프로젝트마다 CLAUDE.md 전문 + MEMORY.md 한 줄 목록(본문은 포먼이 필요하면 Read). **파일 mtime이 바뀌면 다시 읽는다**(요청마다 확인, 바뀐 것만) | 2~3k |
| docs 색인 | docs/*.md 파일 이름 + 첫 제목 한 줄(본문은 Read로) | 1~2k |
| 세션(DB) | 프로젝트별 살아 있는 · 최근 세션: 이름 · 상태 · 마지막 프롬프트 · 마지막 답 앞부분 · 열린 턴 | 2~3k |
| 인계 요약(summary) | 세션마다 최신 ok 요약의 머리(목표 · 다음 할 일 · 주의 — 전문은 id로) | 2~4k |
| 압축 손실 점검 | 있으면 그 프로젝트의 "사라짐 · 약해짐" 중 지금 일과 겹치는 것(log 파일) | 0~2k |
| 파이프라인 | 체인 상태 · 실패 · 대기 | 0.5k |

합계 **입력 10~15k 토큰** + 포먼이 Read로 더 읽는 docs 0~10k.

## 3. 포먼의 계획(출력)

```json
{ "project": "runshoes", "mode": "handoff | new | attach | ask",
  "base_session": 156, "summary_id": 12,           // handoff일 때 — 어느 세션의 어느 요약
  "attach_session": null,                          // 이미 같은 일을 하는 살아 있는 세션이 있으면 새로 띄우지 말고 그쪽으로
  "role": "coder | inspector | scribe | manager | designer", "read_only": false,
  "title": "발볼 120켤레 검증 이어서",
  "first_prompt": "…새 세션에 넣을 글 — 목표 · 읽을 docs 경로 · 인계 요약 · 잃었던 결정 · 하지 말 것…",
  "reasons": ["…왜 이 프로젝트 · 이 요약인지…"], "confidence": 0.8,
  "questions": ["…모호하면 사람에게 물을 것…"] }
```

- `ask`면 띄우지 않고 질문만 보여 준다("런슈즈의 어떤 검증? A · B 중")
- `attach` — 같은 일을 이미 하는 세션이 살아 있으면 그쪽 입력 칸으로 보낼 글만 만든다(세션을 늘리지 않는다)

## 4. 화면 흐름

1. [＋ 세션] → 창 맨 위에 **"포먼에게 말하기"** 칸(기본). 아래에 지금의 "직접 고르기"(접어 둠)
2. "런슈즈 발볼 검증 이어서" → [계획 받기] → 10~30초
3. 계획 카드: 프로젝트 · 방식(인계/새로/붙이기) · 쓸 요약(누구 것 · 언제) · 역할 · 이름 · **넣을 글 전문** · 이유 · 확신도 · 질문
   — 모든 칸을 고칠 수 있다(프로젝트를 바꾸면 요약 목록도 바뀐다)
4. [이대로 시작] → 기존 `spawn_new`(tmux + claude + 행 만들기 + 넣기). [다시 물어보기] · [직접 고르기]로 넘어가기

## 5. 토큰

- 요청 1번: 입력 10~25k + 출력 1~2k 토큰(Sonnet). 하루 10번이면 10~25만 토큰 — 지금 런슈즈 한 세션이 하루 쓰는 입력(1억 단위)에 비하면 작다
- 띄운 새 세션이 첫 입력(넣을 글 2~8k)을 읽는 비용은 사람이 직접 띄워도 드는 것
- 줄이는 법: 상황 묶음의 프로젝트 부분은 mtime이 안 바뀌면 그대로(프롬프트 캐시가 먹는다), 요청 문장에 프로젝트 이름이 있으면 그 프로젝트만 싣는다

## 6. 포먼이 틀리면

- **승인 없이는 아무것도 시작하지 않는다** — 틀린 계획은 화면에서 끝난다(비용: 그 요청의 토큰뿐)
- 계획에 이유 · 확신도를 붙여 틀린 걸 알아보기 쉽게. 확신도가 낮거나 후보가 둘 이상이면 `ask`로 되묻는다
- 고쳐서 시작한 경우 "포먼 계획 → 사람이 고친 것"을 남긴다(`dispatch` 표: 요청 · 계획 · 고친 칸 · 결과). 자주 틀리는 유형이 보이면 상황 묶음이나 지시문을 고친다
- 시작한 뒤 틀린 게 보이면: 사람이 그 세션을 멈춘다. 새 세션은 받으면 바로 시작한다 — 11-10까지는 첫 입력 끝에 "이해한 것을 5줄 안으로 말하고 확인을 기다려라"를 붙였지만, 사람이 계획 카드에서 이미 보고 고치므로 같은 확인을 두 번 하는 것이라 뺐다(5줄 요약을 보고 되돌린 일은 없었다). 교장 계획에 인계 요약을 붙일 때도 인계 글의 「확인을 기다려라」를 「바로 시작하라」로 바꿔 넣는다(인계만 하는 [새 세션으로 옮기기]는 그대로)
- 포먼 호출 자체가 실패(시간 초과 · 형식 오류) → "직접 고르기"를 연다. 화면에는 원인을 한 줄로 적는다(11-10 `bridge.foreman.diagnose`): 사용량 한도 · claude 호출 실패 · 빈 답 · JSON 없음 · 형식 깨짐. 답 앞부분 400자와 JSON이 깨진 자리 앞뒤는 비밀값을 가려 `dispatch.error`와 브리지 로그(`계획 받기 실패 dispatch=N [종류]`)에 남긴다. 실패해도 dispatch 행은 'failed'로 남으니 화면 [버리기]는 서버를 부르지 않는다
- **다시 받기는 앞 계획을 끊는다**(11-14, 받은 할 일 #18): 같은 방(프로젝트)에서 사람이 계획을 또 받으면 아직 도는 앞 사람 계획의 `claude -p` 프로세스를 PID로 끊는다(`ForemanDispatcher._cut_earlier`, 패턴 찾기 아님). 끊긴 dispatch 행은 status `replaced` · error 「다시 받기로 끊었습니다」로 남고, 늦게 온 결과는 화면 · 사용량 기록에 섞지 않는다(`_cut` 번호로 거름). 남은 시간(`running`)도 새 계획 하나만 남는다. 자동 기상(wake) 계획과 다른 방 계획은 끊지 않는다. 화면은 그대로이고 앞 창에는 「다시 받기로 이 계획을 끊었습니다」가 뜬다

## 7. 자동화는 어디까지 — 3.5 "자동 기상" 규칙 다시 보기

| 규칙(`docs/00_design.md` 「3.5」) | 지금도 맞나 | 의견 |
|---|---|---|
| 실패 이벤트만 | 맞다 | Jenkins · ArgoCD 실패, 재시작 루프, 적재 막힘. 성공은 무시 |
| 동시 ACTIVE 최대 3 | 고쳐야 | 지금은 사람 세션만으로 3~4개가 늘 돈다. **사람 세션과 따로 — 자동으로 깬 세션은 동시에 1개** |
| 읽기 전용으로 시작 | 맞다 — 구체화 | CC `--permission-mode plan`(읽기만)으로 띄우고, 승인 정책에서 그 세션의 쓰기 도구를 막는다(wake_reason=auto_failure). 분석 · 보고까지, 고치기는 사람 승인 |
| 30분 강제 IDLE | 고쳐야 | 보고(요약 저장)하면 스스로 끝낸다. 최대 20분 |
| 일일 N회 | 맞다 | 하루 5회 |
| 야간 끔 | 맞다 | 밤의 실패는 텔레그램으로 알리고 아침에 [포먼에게 맡기기] 버튼 |

**순서 의견** — 한 번에 자동으로 가지 말고:
1. 지금: 포먼 디스패처(사람이 말하고 → 계획 → 승인)
2. 다음: 실패 이벤트가 오면 포먼이 **계획만** 만들어 텔레그램 · 화면에 계획을 올리고 사람이 [시작]을 누름(설계 때의 예시 글은 "이렇게 보자고 합니다 — [시작]"이었고, 11-08에 만든 실제 텔레그램 글은 「🧭 <실패 종류> — 이렇게 살펴보자는 계획을 세웠습니다」 · 「[시작]? 화면에서 계획을 보고 눌러 주세요 — <링크>」, `bridge/wake.py` 112 · 119). (11-15 바뀜 → 둘째 줄은 「[시작]? 계획을 보고 화면에서 눌러 주세요. <여는 법>: <링크>」이고, 자리는 `bridge/wake.py` `_wake_inner`다(줄 번호는 뺐다). 링크가 열리지 않는 주소였던 것을 고치며 여는 법을 글에 넣었다, `10e1e5b`) [log:wake_link_20261115.md]
3. 2가 몇 주 동안 맞으면: 실패 시 읽기 전용 조사 세션을 자동으로(1개 · 20분 · 하루 5회 · 낮에만)

## 8. 만들 것(구현 순서)

1. 상황 묶음 만들기(`bridge/foreman.py`) + CLAUDE.md · 메모리 · docs 색인 mtime 캐시
2. 디스패치 API(`POST /api/foreman/plan` → claude -p, `dispatch` 표 기록)
3. [＋ 세션] 창에 "포먼에게 말하기" + 계획 카드(고치기 · 시작 · 다시 · 직접 고르기)
4. 시험: 오늘 대화에서 나온 요청 문장 10개로 계획이 맞는지(사람이 기대하는 답과 비교)

## 9. 세션은 교장 경로로 띄운다 · 관리자는 상주하지 않는다 (11-09 사용자) [log:dispatch_flow_decision_20261109.md]

**흐름을 "교장 → 관리자 → worktree"로 고정하지 않고 교장을 키운다. 관리자(FOREMAN 원본 폴더 세션)는 상주로 두지 않고 필요할 때만 쓴다.**

> (11-11 바뀜) 관리자 상주는 11-11 2물결에서 **프로젝트마다 상주 관리자(원본 폴더)**로 바뀌었다 — 지금 FOREMAN · 인프라 · 런슈즈에 관리자가 서 있고, 합치기 · 시험 · push · 브리지 다시 띄우기 · 사람에게 올리기(escalate)를 맡는다 [log:plan_structure_20261111.md] [log:enable_c_wave2_20261111.md]. 아래 「9-1.」의 **띄우는 길 하나**(계획 → 시작)와 「9-2.」가 든 까닭은 그대로 읽는다 — 상주하면 맥락이 쌓이는 문제는 인계(새 세션으로 옮기기)로 이어 간다(관리자 309 → 318 인계처럼 — [log:manager318_overhead_20261113.md]).

### 9-1. 띄우는 길 — 하나로

- 관리자가 세션을 띄울 때도 **`POST /api/foreman/plan`(짧은 요청) → 계획을 받아 `first_prompt`를 지시문으로 바꿔 `POST /api/foreman/start`**로 한다. 바꾼 칸은 `dispatch.edited`에 남는다 — 계획 카드에서 사람이 칸을 고치는 것과 같은 경로
- **관리자도 `POST /api/spawn`을 직접 쓰지 않는다.** `/api/spawn`은 `dispatch` 기록을 남기지 않았다 — 11-09 18:25 서기 세션을 관리자가 `/api/spawn`으로 띄워 기록이 없었다. 이것은 약속이다(코드가 막지는 않는다). 11-11부터는 `/api/spawn` · 새 세션으로 옮기기도 `record_direct`로 `dispatch`(origin `spawn` · `move`)와 `dispatch_session`에 한 줄을 남긴다(`bridge/api/handoff.py` → `bridge/api/foreman.py`) — 약속을 어겨도 기록은 남지만, 계획을 거치지 않은 띄우기라는 것은 그대로다. [＋ 세션] 「직접 고르기」는 사람이 쓰는 길로 그대로 남는다
- 첫 적용: 코더 상주 일 — dispatch #152(경고 · 질문 없음, 확신도 0.75) → 첫 글을 지시문으로 바꿔 시작 → 세션 233(worktree `foreman-2`). 관리자 역할 화면 · API — dispatch #158 → 세션 242(`foreman-3`, opus)
- 받은 할 일에서 띄우면 `start`에 `inbox_id`를 같이 보내 뜬 세션이 그 할 일을 가져간다 → `docs/12_scribe.md` 「11. 포스트잇」(11-15 바뀜: 절 이름이 「받는 함 [＋ 할 일]」에서 바뀌었고 [＋ 할 일] 창은 뺐다)

### 9-2. 관리자를 상주로 두지 않는 까닭

- 하는 일을 나눠 보면 세션이 꼭 들고 있어야만 하는 것이 없다 — 띄우기 · 지시문은 교장 + 버튼, 합친 뒤 시험 · push · 다시 띄우기 · 확인 목록은 브리지가 할 수 있고, 조사 · 설계 답 · 코드 · 기록은 그때 띄우는 조사 · 코더 · 서기 세션으로
- 상주면 맥락이 쌓여 압축된다 — 교장을 "부를 때만"으로 둔 까닭(1절)과 같다. 11-09 관리자 세션은 두 번 인계했고, 주된 까닭은 띄우기가 아니라 "할 일에 넣어라"(≈ 10) · 질문(≈ 5)이었다 → 할 일은 받는 함으로(`docs/12_scribe.md` 「11.」)
- 잃는 것(대신할 곳을 정해야 함): 하루의 결정을 한곳에 드는 것(→ 서기 · log), CLAUDE.md의 "원본 세션 몫"(README 로드맵 표 · push · 브리지 다시 띄우기 → 브리지 · 서기), 세션 간 메시지를 받는 "메인"(→ 사람 패널 · 브리지)
- 안 가는 것: "지시는 관리자에게, 띄우기만 기록" — 맥락이 쌓이는 문제를 그대로 남긴다

### 9-3. 교장이 못 보는 것 — 관리자 검토가 값을 낸 자리

- 11-09 17:10 교장은 알림 셋이 이미 있다는 것을 이유 칸에 적었지만 `warnings` · `questions`가 비어 카드에서 눈에 띄지 않았다. 교장은 문서로 읽었고, 관리자는 코드 · 기록 · 브리지 기동 시각으로 실제로 도는지 확인했다
- 교장 도구(Read · Grep · Glob)로는 못 보는 것: 프로세스 · tmux 화면(끝내기 확인 창 등), worktree 브랜치 · 커밋 안 한 변경, 브리지를 언제 다시 띄웠는지, 시험 결과, 노트 · log에 적히기 전의 대화 결정
- 그래서 할 일 넷(그때 README 「나중에 할 일」에 적었다. ①과 ④는 됐고 ② ③은 11-15에 표와 함께 지웠다): ① 교장이 한 번에 여러 세션 계획(먼저) ② 읽기 전용 확인 도구 ③ 교장의 발견을 경고 · 질문 칸에 ④ 모든 띄우기가 dispatch를 남김
  - **11-11: ① · ④는 됐다**(아래 「11.」). ② · ③은 README에 남아 있다

## 10. 역할 관리자(manager) (11-09, 세션 242) [log:manager_role_20261109.md]

- 값 `manager`, 화면 "관리자". `foreman`은 감독실 교장 · 팀장 캐릭터(세션 없는 계획 창구)라 섞지 않는다
- 하는 일: **코드를 고치지 않고 다른 세션의 일을 거둔다** — 교장 경로로 세션 띄우기 · 합치기 · 시험 · push · 브리지 다시 띄우기 · 화면 점검 · 기록. 직접 고쳐도 되는 것은 CLAUDE.md 「작업 규칙」의 셋뿐(11-09 사용자)
- 교장 계획 프롬프트(`bridge/foreman.py`): "상주 세션이 아니다. 사람이 그런 일을 콕 집어 맡길 때만 고른다(코드를 고치는 일이면 coder)". 모델 기본 `claude-opus-5-5`(`config/models.toml`, 11-14 전 `opus` 별칭)
- 역할 목록은 11-15부터 파이썬 `bridge/roles.py`, 화면 `bridge/static/js/roles.js` 두 한 곳이다(전에는 `ROLE_KO` 세 벌 · `ROLES` · `SessionRole` · `ROLE_PICK` · `ROLE_LABEL`에 따로). 교장 지시문 「3. role」의 역할 한 줄 설명도 `roles.py`에서 만든다(화면 역할 고르기 칸과 같은 글). 시험 `tests/test_roles_agree.py`가 둘과 `config/models.toml [defaults]`의 일치를 본다. 새 역할 더하는 순서는 `docs/roles.md` 「3.」
- 교장 지시문 「3. role」의 코더 줄(11-17 사용자 지시 21): 고친 코드를 가리키는 문서도 그 코더 세션이 함께 고친다. 브리지가 코더 첫 글 끝에 규칙과 거꾸로 찾는 도구를 붙이니(`docrefs.prompt_block`) first_prompt에 옮기지 않고, 코드 고침 뒤 그 문서만 맞추는 서기 세션을 따로 내지 않는다. 상세는 `docs/11_worktree.md` 「9.」
- 인계(새 세션으로 옮기기)는 역할을 물려준다 — 관리자 → 관리자
- **관리자는 늘 원본 폴더, 하나**(11-11 아홉): `spawn_new`가 관리자를 worktree로 띄우는 것을 거절하고 `will_worktree(role="manager")`는 False, 계획 check도 관리자 세션의 따로 작업 기본값을 끈다(`bridge/handoff.py` · `bridge/foreman.py`). 원본 폴더에 관리자가 이미 살아 있으면 둘째를 거절한다(`manager_conflict`) [log:merge_misplaced_admin_20261111.md]
- **역할 바꾸기 `PUT /api/sessions/{sid}/role {role}`**: 허용 값만(`foreman` · 모르는 값 · null은 422), 없는 세션 404, 거부 409 `{refused}`. `character_session.role`과 **그 역할 캐릭터도 같이 옮긴다**(원본 폴더 "관리자", worktree "관리자 <이름>") — 역할만 바꾸면 아래 줄이 "코더 foreman-3 · 관리자"처럼 엇갈린다. `session_action` `role` "옛 → 새 캐릭터 N". 같은 역할이면 아무것도 쓰지 않는다
  - 11-10 관리자 세션 230을 이 API로 manager로 바꿨다(캐릭터 22) [log:merge_237_242_20261110.md]
- 화면에서 바꾸기(패널 머리줄 배지) · 자리 · 이름표는 `docs/10_office_design.md` 「관리자 자리 · 이름표 · 머리줄」
- "역할 없음"은 실제로 생기지 않는다: FOREMAN 밖에서 띄운 CC 세션은 `assembler.py`가 늘 `coder`로, 터미널 셸은 `helper`로 만든다. 아니면 배지로 바꾼다

### 10-1. 역할 디자이너(designer) (11-10 사용자) [log:designer_role_20261110.md]

- 값 `designer`, 화면 "디자이너". **화면 담당** — `office.js` · `panel.css` · 테마(자리 · 가구 · 색) · 캐릭터 · 이름표 · 카드 · 툴팁 글. 파이썬 · 브리지 · API · DB는 코더
- 관리자와 같은 다섯 곳 + `ROLE_PICK` · `render.js` `ROLE_LABEL` · `SESSION_ROLES`에 넣었다. 역할 바꾸기 API · 배지 고르기 칸 · 인계 물려주기도 같은 규칙(원본 폴더 "디자이너", worktree "디자이너 <이름>"). 모델 기본 `opus`(코더와 같은 까닭 — 사진을 보고 자리 · 겹침을 판단, `office.js`가 크다)
- 교장 계획 프롬프트: 화면 일은 designer, 파이썬 · 브리지 · DB는 coder. **둘이 걸치면**(새 API + 그 화면) 화면이 API에 기대니 coder를 먼저 내고 first_prompt에 "화면은 다음 디자이너 세션 몫 — API 응답 모양을 log에 적고 끝낸다", reasons에 나눈 까닭. 화면 쪽이 몇 줄뿐이면 coder 하나로. 계획은 한 번에 하나라 둘을 같이 내지는 못한다
- 자리 · 이름표는 `docs/10_office_design.md` 「관리자 자리 · 이름표 · 머리줄」의 디자이너 줄

### 10-2. 역할 조사(inspector) (11-15 사용자) [log:foreman-6_inspector_rename_20261115.md]

- 값 `inspector`, 화면 이름 「조사」(전 이름 「점검」). 사용자: 「점검이면 고치는 일도 포함될 것처럼 들린다. 조사가 맞다」. 읽고 알아보고 고치지 않는다. 조사와 제안은 모두 여기다
- 코드 값은 그대로 두었다(DB `character_session.role`, 설정 키, 함수 이름). 화면 이름만 `ROLE_KO`(`bridge/handoff.py`, `bridge/foreman.py`, `bridge/wake.py`), `ROLE_PICK`, `render.js` `ROLE_LABEL`에서 바꿨다. 이미 있는 「점검」 캐릭터(DB)는 마이그레이션 없이, 그 프로젝트에서 다음 조사 세션이 뜰 때 「조사」로 이름을 바꿔 이어 쓴다(`ROLE_OLD_KO`, `_character_for`)
  - (11-15 바뀜 → 같은 날 역할 목록을 한 곳으로 모아, 화면 이름과 `ROLE_OLD_KO`는 지금 `bridge/roles.py` `ROLE_INFO`, 화면 쪽은 `bridge/static/js/roles.js` `ROLE_LABEL`에만 있다. `handoff.py`, `foreman.py`, `wake.py`, `ROLE_PICK`은 거기서 가져간다. 「10.」 끝 줄)
- **조사는 자기 결과 log를 승인 없이 쓰고 커밋한다.** 전에는 CC plan 모드(읽기 전용)로 떠서 log 하나에도 계획 승인이 한 번 필요했고, 그래서 관리자가 조사를 피하고 코더로 띄웠다. 이제 보통 모드로 뜨고 브리지(PreToolUse, `bridge/roleguard.py` `inspector-write`)가 막는다
  - 허용: `log/` 아래 새 파일 Write, 이 세션이 만든 log(또는 git이 아직 모르는 log) Edit, `git add log/<파일>`, 스테이지가 log 파일뿐인 `git commit`, `git restore --staged`, 읽기 명령, 저장소 밖(스크래치, /tmp) 쓰기
  - 거부: log 밖 Edit, Write, NotebookEdit. 다른 세션이 커밋한 log 고치기. Bash로 저장소 파일 쓰기(리디렉션, `sed -i`, `tee`, `rm`, `mv`, `cp`, `touch`, `mkdir` 등). `git push`. 저장소를 바꾸는 git(checkout, reset, rebase, merge, stash, 브랜치나 태그 만들기 등). log 밖 `git add`(`-A`, `.` 포함). `git commit -a`, 경로를 준 커밋, 스테이지에 log 밖 파일이 있는 커밋
  - 거부 글은 「조사 세션은 log 파일만 쓸 수 있습니다. …」로 세션에 돌아가고, 승인 기록(`approval_req` 이벤트, 브리지 로그 warning)에 남는다
  - 이 규칙만 `config/roles.toml [roles] enforce = ["inspector-write"]`로 막는다. 다른 역할 규칙은 사용자 결정대로 관찰 그대로(11-12 「켜지 마라」)
  - 못 막는 것: 해석기 안 쓰기(`python -c "open(…,'w')"`). 다른 역할 규칙과 같은 한계다(`notion/17_limits.md`). `cd $X` 뒤처럼 폴더를 모르는 명령은 할 일이다(`docs/TODO.md` foreman-134)
- **교장 계획**: 조사 세션은 그 프로젝트에서 이 규칙이 막고 있으면(`RoleGuard.enforces`, 지금 foreman만) 읽기 전용을 끄고 띄운다. 막지 않는 프로젝트(런슈즈, 펫퍼민트, 인프라)는 예전처럼 읽기 전용으로 켜고 「역할이 조사라 읽기 전용으로 시작합니다」 경고를 붙인다. **자동 기상 계획은 막는 프로젝트여도 읽기 전용**(`docs/00_design.md` 「3.5」의 「자는 사이에 커밋이 쌓이면 안 된다」). 사람이 계획 카드에서 바꾼 값은 그대로. 계획 카드의 읽기 전용 칸 아래에 「조사 세션은 읽기 전용이 아니어도 log 파일만 쓰고 커밋할 수 있습니다」가 뜬다(계획의 `log_only`)
- [+ 세션] 창으로 바로 띄운 조사도 같은 규칙에 걸린다(역할은 DB에서 읽는다)
- **조사는 결과를 보고하면 스스로 끝난다**(11-15 사용자: 「조사는 읽고 알려 주는 것이 전부라 끝나면 남을 까닭이 없다」, `bridge/inspector_close.py`) [log:foreman-6_inspector_close_20261115.md]. 턴이 끝나고 15초 뒤 브리지가 본다. 그 턴이 마지막 턴이고, 일하는 중(busy, 열린 턴, 승인 대기, 뒤에서 도는 일)이 아니고, 묻는 말(마지막 응답의 물음, 사람 답 기다림 escalate)이나 권한 거부가 없으면 끝낸다. 묻는 말을 남긴 턴은 답을 받아야 하니 끝내지 않는다
  - 원본 폴더 조사(포스트잇 [갱신] 등): 세션만 끝낸다. 커밋은 이미 main에 있고 push는 관리자 몫이다. 포스트잇 [갱신] 세션이면 결과 블록을 먼저 읽고 끝낸다. 관리자 입력 칸에 「[작업 보고 — 세션 N 「제목」(조사) → 프로젝트 관리자]」로 끝냈다는 것과 마지막 응답 끝을 넣는다
  - 작업방 조사: 결과 log를 main에 합치고 세션을 끝내고 작업방을 지운다. 합치는 판단은 `docs/11_worktree.md` 「6-2.」
  - 다른 역할(코더, 디자이너, 서기, 관리자)은 그대로다. 켜는 프로젝트는 foreman만(`config/handoff.toml [inspector_close]`, 칸이 없으면 켜짐)

## 11. 11-11에 더한 것 — 여러 세션 · 관리자에게 넘기기 · 프로젝트별 관리자 · 토큰 범위 · 역할 권한

**켜져 있는 것** [log:coder_foreman_multi_20261111.md]
- **한 계획에 여러 세션**(할 일 ①, 0030): 계획 JSON에 `sessions[]`(최대 `MAX_SESSIONS = 6`, `bridge/foreman.py`) — 세션마다 `role · model · title · first_prompt · read_only · worktree · files(맡을 파일) · merge_order · on`. `sessions`가 없는 옛 계획은 위쪽 칸으로 하나를 만든다(`sessions_of`). [시작]은 켠 세션을 차례로 `spawn_new` — 둘째부터 worktree 기본 켬(관리자는 예외), 첫 세션이 못 뜨면 거절, 둘째부터 못 뜨면 띄운 것은 두고 화면 note + 텔레그램 한 번. 세션마다 한 줄이 `dispatch_session`(0030)에 `started · failed · off`로 남는다. 계획 카드(`foremanchat.js`)는 세션 칸이 여럿이고 [자세히]에 「맡을 파일」 · 「합칠 순서」. `GET /api/foreman/merge-order`가 합칠 순서를 알려 준다
- **맡을 파일 겹침 경고**: 새로 띄울 세션의 맡을 파일이 이미 도는 세션이 고치는 파일과 겹치면 계획 경고에 뜬다(11-11 282 때 286 계획이 `tests/test_terminal.py`로 처음 잡았다)
  - (11-15 바뀜) 맞대는 상대는 「살아 있는 세션」에 「열려 있는 세션」을 더한다. 열려 있다 = 합치거나 버리기 전. worktree 세션은 폴더가 남아 있는 동안, 원본 폴더 세션은 끝나기 전(`foreman.py` `UNMERGED_SQL`, `still_open`). 서기실 열린 일과 같은 판단이다. CC가 끝나도 합치지 않은 worktree는 합칠 때 충돌하니 겹침에 넣는다. 합치기 기록 없이 지운 worktree(296, 311)는 폴더가 없어 빠진다
  - 서기실 [시키기]로 띄운 서기 세션도 잡힌다. 서기실이 `dispatch`(origin `scribe`)와 `dispatch_session`(맡을 파일 = 그 일의 `scribe_room.touches`. 포트폴리오와 기술문서 편 하나면 그 편 파일)을 남기고, 그 기록이 없던 11-15 전 서기실 세션은 `scribe_room.open_tasks`로 더한다 → `docs/12_scribe.md` 「2.」
- **서기 일 종류(`task`, 11-15)**: 계획 세션 칸에 `task`(서기실 일 이름: later, trim, doccheck, docfix, portfolio. readme는 11-15에 뺐다). 이 다섯은 교장 지시문이 고르게 하는 이름이다. 서기실에 11-15에 생긴 techdoc(기술문서 쓰기)은 지시문 목록에 없다(`bridge/foreman.py` 「10. sessions」, `bridge/scribe_room.py` `TASKS`). 역할 scribe면 `spawn_new`가 `session_action scribe-task`로 남긴다(없으면 `plan`). `POST /api/spawn`도 `task`를 받는다. 계획 카드는 이 칸을 보이지 않고 그대로 넘긴다
- **포스트잇에서 바로**(받은 할 일 #8, 11-15 포스트잇으로 옮김): 코더 추천이 붙은 포스트잇의 [띄우기]가 교장 계획 창을 열고 바로 계획을 받는다(`foremanChat.openWith(…, {ask: true})`). 번호는 `inbox_ids`로 [이대로 시작]에 실려 뜬 세션이 가져간다. 11-11의 [＋ 할 일] 창 목록과 [고른 것으로 계획 받기]는 11-15에 뺐다(목록은 포스트잇이 맡는다, `docs/12_scribe.md` 「11.」). 열린 것 고치기는 `PUT /api/todo/{id}` 그대로 [log:coder_c_wave2_20261111.md] [log:foreman-5_postit_20261115.md]

**설정 스위치 뒤에 있던 것 — 합칠 때(11-11 286)는 하나도 켜지 않았고, 같은 날 저녁 사용자 지시로 넷을 켰다(역할 권한만 관찰)** [log:coder_c_wave2_20261111.md] [log:merge_c_wave2_20261111.md] [log:enable_c_wave2_20261111.md]

| 기능 | 스위치(지금 커밋된 값) | 하는 일 |
|---|---|---|
| 프로젝트 토큰 범위 | `config/tokens.toml [project_tokens] enabled = true`(**켜짐**, 첫 토큰 ronanlab-infra) | 관리 토큰(`FOREMAN_API_TOKEN`)은 그대로 모든 API. 프로젝트 토큰(`.env.project_tokens`의 `FOREMAN_TOKEN_<프로젝트>`)은 그 프로젝트 세션 · 방 API와, **11-12부터 자기 프로젝트의 Notion 게시**(`POST /api/publish` · `GET /api/publish?project=` · `POST /api/publish/pair` — 본문 · 쿼리의 project가 자기 프로젝트일 때)만 열고 나머지는 403 + 사유. **force 덮기 · `action=docsync`(한꺼번에 맞추기)는 관리 토큰만**(사람에게 묻는 일이라서). 같은 유닉스 사용자 세션은 `.env.bridge`도 읽을 수 있어 **벽이 아니라 잘못 부르는 것을 막는 칸막이**다(`bridge/scopetoken.py` · `bridge/api/auth.py`) |
| 프로젝트별 관리자 | `config/managers.toml [managers] enabled = true`(**켜짐**, `projects = []` — 비면 DB의 모든 프로젝트) | `GET /api/managers`(프로젝트마다 관리자 또는 「관리자가 없습니다」 — 꺼져 있어도 읽힘), `POST /api/managers/{project}/ask`(그 관리자 입력 칸에 부탁 — 꺼져 있으면 503). 관리자가 없거나 못 넣으면 텔레그램 한 번 + `delivered:false, reason`(`bridge/managers.py`) |
| 계획을 관리자에게 | `config/managers.toml [handover] enabled = true`(**켜짐**, `wait_min = 15`) | 계획 카드 [관리자에게 보내기] — 고친 계획을 저장(`dispatch.handed_to · handed_at`, 0031)하고 그 프로젝트 관리자 입력 칸에 계획 요약 + 시작 명령(`POST /api/foreman/start {"dispatch_id": N, "use_saved": true}`)을 넣는다. 못 넣으면 되돌리고 카드에 사유 + 텔레그램. 넘기고 15분 안에 안 띄우면 텔레그램 한 번(`bridge/handover.py`). 꺼져 있으면 단추가 없고 [이대로 시작]은 그대로 |
| 역할 권한 | `config/roles.toml [roles] mode = "observe"` | **관찰이 켜져 있다 — 막지 않고 기록만.** PreToolUse에서 `worktree-push` · `bash-file-edit` · `manager-code` · `scribe-code` · `inspector-write`(11-15)를 판정해 `approval_req` 이벤트 payload에 `role_rule` · `role_reason`을 남긴다. `enforce`면 거부 + 사유, `off`면 보지 않음. **예외: `[roles] enforce`에 적은 조사 규칙(`inspector-write`)은 관찰 모드에서도 막는다**(11-15, 「10-2.」). 기본 `projects = ["foreman"]`(`bridge/roleguard.py`). 해석기 안 쓰기(`python -c "open(…,'w')"`)는 못 막는다 |
| 새 세션으로 옮기기 한 흐름 | `config/handoff.toml [move] one_flow = true`(**켜짐**) | 잊은 것 찾기 → 문서 후보 → (사람이 문서에 넣을 것 고르기) → 문서에 쓰기 → 요약 → 새 세션 → 옛 세션 끝내기를 단추 하나로(`bridge/static/js/moveflow.js`). 요약 확인 창 없음, 넘어간 글은 새 세션 패널 「넘겨받은 글」에 보인다. 끄면 옛 흐름(요약 → 확인 → 새 세션 → 옛 세션 끝내기). 화면이 다음에 그릴 때 읽어 브리지 재시작이 필요 없다 |

- **켜는 법**(기록 `log/coder_c_wave2_20261111.md`에 있는 것만): 토큰 · 관리자 — ① `python -m bridge.scopetoken new <프로젝트>`(값은 화면에 안 찍히고 파일에만) ② `tokens.toml enabled = true` · `managers.toml [managers] enabled = true` ③ 그 저장소 CLAUDE.md에 관리자 규칙 줄(초안은 같은 log, 그 저장소 세션에 부탁) ④ 관리자 세션을 원본 폴더에 띄움(역할 manager) ⑤ 필요하면 `roles.toml projects` · `handoff.toml [merge_prep] projects`에 그 프로젝트를 더함. 계획 넘기기 · 옮기기 한 흐름은 `[handover] enabled = true` · `[move] one_flow = true`로 켜 보고 시험 계획 · 시험 세션 하나로 15분 알림 · ①~⑦을 확인한다(끝나면 시험 세션은 `hidden_reason='test'`). 역할 권한은 하루 관찰 뒤 규칙별 걸린 수를 보고 사용자가 `enforce`로 올린다(그 쿼리는 같은 log 「합친 뒤 관리자가 할 일」 2). 바꾼 뒤에는 모두 브리지를 다시 띄운다(`[move]`만 제외). 이 문단은 켜기 전에 정한 순서이고, 토큰 · 관리자 · 넘기기 · 옮기기 한 흐름은 11-11 저녁 사용자 지시로 켜졌다 — 켠 경위 · 시험은 [log:enable_c_wave2_20261111.md]
- **기능 사이에 무엇을 먼저 켤지, enforce로 켠 뒤 무엇을 볼지는 정해지지 않았다**(기록에도 없다 — [log:merge_c_wave2_20261111.md] 「켜는 순서가 기록에 있는가」)
- (11-12 바뀜) 인프라 · 런슈즈(310)에 관리자가 섰다. `[merge_prep] projects`는 `["foreman", "ronanlab-infra"]` — 런슈즈는 사용자가 정할 때 더한다(`docs/11_worktree.md` 「6-1.」). (11-13 바뀜 → 펫퍼민트 관리자를 세우며 펫퍼민트를, 런슈즈 5-2를 합친 뒤 런슈즈를 더해 지금은 네 프로젝트다(`config/handoff.toml`, `ddb9d15`, `eab68a0`))
- **역할 권한은 관찰만 하고 켜지 않는다**(11-12 사용자 — "확인만이다. 켜지 마라")(11-15 바뀜 → 조사 규칙 `inspector-write` 하나만 `[roles] enforce`로 막는다, 「10-2.」. 나머지 규칙은 그대로 관찰). enforce와 런슈즈 · 인프라로 넓히는 것은 사용자가 정한다. 넓히려면 `projects`, 프로젝트별 `manager_allow` · `scribe_deny`(코드), 무시되는 작업 폴더 빼기, 관찰 기간이 있어야 한다(지난 7일 다시 돌리기 290건). 해석기 · `$` 경로 · cp/mv 같은 지나가는 길도 같이 막아야 한다 [log:approval_hell_plan_20261112.md]
