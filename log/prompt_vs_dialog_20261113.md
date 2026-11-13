# 붙여넣기 전 화면 검사 — 입력 칸과 고르기 · 안내 창 가르기 (2026-11-13, worktree foreman-2, 세션 351)

> 상태: ✓ 코드 · 시험 · README 3.1 줄. 브리지 다시 띄우기 · push는 관리자 몫. CC 2.1.323

**결론: 예전 `prompt_showing`은 대화가 있는 세션에선 어떤 창이 떠 있어도 「입력 줄 있음」이었다.** 고르기 줄(들여 쓴 `❯`)만이 아니라, **대화 영역의 지난 사용자 글이 0칸 `❯`로 남기 때문**이다(`❯ /model`, `❯ say ok only`). 그래서 Esc 없이 창에 붙여 넣고 Enter를 보냈다. 폴더 신뢰 창(기본 선택 `❯ No, exit`)과 도구 권한 창(기본 선택 `❯ 1. Yes`)에서도 그랬다 — Enter가 그 선택을 확정한다. 이제 화면을 입력 칸 · 닫아도 되는 창 · 결정 창 · 모르는 창으로 갈라, 닫아도 되는 창만 Esc로 닫고 나머지는 Esc 없이 거부한다.

## 가르는 규칙(`bridge/inject.screen_state`)

실제 화면(tmux `capture-pane -p -J`, 120×40)에서 정했다.

- **입력 칸**: 0칸에서 시작하는 가로줄 `────` 바로 아래(빈 줄 건너)에 **0칸** `❯` 줄, 그 아래 다음 가로줄까지. 지난 사용자 글은 위가 가로줄이 아니라 걸리지 않는다
- **창**:
  - `▔▔▔` 위 테두리가 있으면 그 아래가 창(`/model` · `/config` · `/usage` · `/autocompact`)
  - 입력 칸이 없으면 마지막 가로줄 아래가 창(신뢰 · 도구 권한)
  - 입력 칸이 있어도 그 바로 위 두 줄에 Esc 안내 줄(「 · 」로 나뉜 짧은 토막들 중 하나가 Esc로 시작 — 「Enter to confirm · Esc to cancel」, 「↑/↓ choose · … · esc not now」)이 있으면 그 위가 창. 테두리 꼴을 못 본 자동 압축 권유 창을 위해 둔 것이다
- **창 종류**는 창 안 글(제목)로 고른다. 안내 줄의 Esc 뜻으로는 못 고른다 — CC 안에서 `escape → cancel`이 48곳이고, 도구 권한 창의 「Esc to cancel」은 거부다. 결정 쪽을 먼저 본다(둘 다 걸리면 결정)

## 창 목록과 갈래

| 창 | 알아보는 글 | Esc 뜻 | 갈래 | 어떻게 알았나 |
|---|---|---|---|---|
| 자동 압축 권유(오늘 서기) | We recommend compacting earlier | `answer("esc")` — 「esc not now」, 설정 그대로 | 닫음 | CC 코드(제목 `Out`, 안내 줄 `Nut`, `onCancel`) |
| `/model` | Select model | 「Kept model as …」 | 닫음 | 시험 세션 |
| `/config` · `/usage` · `/status` · `/stats` | 탭 줄 `Settings  Status  Config  Usage` | 첫 Esc는 검색 칸만 비울 수 있다(「Esc to clear」→「Esc to close」), 두 번째에 닫힘 | 닫음 | 시험 세션 |
| `/autocompact` | Auto-compact window | 「… unchanged」 | 닫음 | 시험 세션 |
| 폴더 신뢰 확인 | Quick safety check · trust this folder | 취소 = 끝내기일 수 있음, **기본 선택이 No, exit** | 결정 | 시험 세션 |
| 도구 권한 묻기 | Do you want to proceed? · Do you want to allow · … make this edit · … create | 거부, **기본 선택이 1. Yes** | 결정 | 시험 세션(수동 모드에서 `touch`) |
| 보류된 세션 메시지 승인 | Held message from another session | Deny | 결정 | `log/xsession_socket_test_20261113.md` 화면 |
| 끝내기 확인 | Background work is running | 머묾/끝냄 | 결정 | CC 코드 |
| 계획 승인 | Would you like to proceed? | 거부 | 결정 | CC 코드 |
| 그 밖(질문 창 · 되감기 · 효과 바꾸기 권유 「Switch your default effort to …」 · `/mcp` · `/agents` 등) | — | 창마다 다름 | 모름 → 거부 | CC 문자열에 Esc 동작이 cancel 48 · close 16 · go back 12 · dismiss 5 · skip 2 · keep · decide later · discard and exit 등 |

- 결과 글: 닫음 → 「떠 있던 ○○ 창을 Esc N번으로 닫고 보냈습니다.」(입력 이벤트에 `esc` 수와 `dialog` 이름), 결정 → 「○○ 창이 떠 있어 넣지 못했습니다. Esc가 그 창의 답이 될 수 있어 보내지 않았습니다 — 그 세션 대화창에서 확인해 주세요」, 모름 → 「알 수 없는 창이 떠 있어 넣지 못했습니다. Esc가 무엇을 할지 몰라 …」. 모두 로그(`foreman.inject` warning)에 남는다
- Esc로 닫았더니 밑에 결정 창이 있으면 거기서 멈춘다

## 오늘 안내 창이 이 길로 걸렸나 — 걸렸다(화면 글로 재현)

- 서기 세션은 대화가 길어 화면 위쪽에 지난 사용자 글 `❯ …`가 있었고, 창에도 `❯ Keep auto (1m tokens)`가 있었다 → 예전 판단은 「입력 줄 있음」 → Esc 없이 `/exit`를 붙이고 Enter. 이 창은 붙여넣기를 따로 받고(`onPaste`) Enter는 고른 것(「Keep auto」)을 확정한다 — 끝내기 명령은 창에 먹히고 세션은 안 끝났다
- 시험 `test_old_rule_mistook_dialogs_for_prompt`가 예전 판단으로 이 화면(테두리 꼴 둘)과 다른 창 8개를 모두 입력 줄로 보는 것, 새 판단은 아닌 것을 확인한다. 다만 그 창의 실제 테두리 모양은 못 봤다(일부러 띄울 수 없음) — 테두리 · 가로줄 · 테두리 없음 세 꼴을 다 시험에 넣었다

## 설계와 달랐던 점

- 일감은 「고르기 줄 `❯ 4.`」을 원인으로 봤는데, **더 큰 원인은 지난 사용자 글의 0칸 `❯`**다. 고르기 줄만 걸러서는 안 고쳐진다
- 일감의 「작업 중이면 Esc 안 보냄」은 그대로지만, **권한 창이 떠 있을 때 status는 `waiting`**이라 busy 거르기로는 권한 창을 못 막는다(11-09 기록은 「승인 · 질문 창은 busy」로 봤다). 창 종류 거르기가 그 몫을 한다
- 「Esc 3번」은 `/config` 때문에 필요하다(첫 Esc가 검색만 비움)
- 화면 글 바꿈(관리자 318 지시 더함, 사용자 결정): `inject.py`의 「그 세션 터미널에서 확인해 주세요」 4곳을 「대화창」으로. **이 거부 글들은 모두 CC 창이 떠 있을 때의 것이라, 그 창은 대화창(FOREMAN 대화 화면)에는 안 보이고 터미널에만 보인다** — 사용자에게 알릴 줄:
  - `bridge/inject.py` `clear_screen`의 거부 글 넷: 작업 중 창(「○○ 창이 떠 있습니다. 작업 중이라 Esc를 …」), 결정 창, 모르는 창, Esc 3번에도 안 닫힘
  - 바꾸지 않은 것: `inject.py` 167 `bang_check`의 sudo 거부 「서버 터미널에서 직접 쳐 주세요」 — 확인이 아니라 사람이 실제로 터미널에서 칠 일이라 그대로 뒀다
- `bridge/static/js/store.js` 결과 글 한 줄(창 이름)과 `bridge/api/sessions.py` 입력 이벤트에 `dialog`를 더했다. store.js 바로 위 두 줄(513 · 514 「터미널에서 …」)은 다른 세션 몫이라 건드리지 않았다 — 합칠 때 가까운 줄이라 겹침 확인 필요

## 되돌리는 법

이 브랜치 커밋 하나를 `git revert`. 스키마 · 설정 변경 없음. 브리지(파이썬) 바뀜이라 되돌린 뒤 브리지를 다시 띄운다.

## 쓴 시험 세션

- 따로 띄운 tmux 서버(`tmux -L dlgtest`, 세션 `dlg`)에 스크래치 폴더로 `claude --model sonnet` — CC 세션 id `f14abc65-2139-4264-80f4-4f47b09886be`(PID 1560560). 관리자 · 다른 세션 tmux에는 키를 보내지 않았다
- 한 일: 신뢰 창(「Yes」 고름), `/model` · `/config` · `/usage` · `/autocompact`를 띄우고 Esc, 「say ok only」 한 턴, 수동 모드로 바꿔 `touch probe.txt` 권한 창을 띄우고 Esc(거부), `/exit`로 끝냄(tmux 서버도 닫힘 확인)
- **숨기기(`hidden_reason='test'`)는 못 했다** — API가 없다. 브리지가 이 세션을 잡았다면 관리자가 숨겨 주세요

## 시험

- 새 `tests/test_inject_screen.py`: 실측 화면(입력 칸 · 초안 두 줄 · `/model` · `/config` · `/usage` · `/autocompact` · 신뢰 · 권한) + 보류 승인 · 끝내기 확인 · 자동 압축 권유 세 꼴 · 모르는 창의 판단, 예전 판단 재현, Esc 뒤 넣기 · `/config` Esc 2번 · 결정 · 모르는 창 거부(Esc 0) · Esc 뒤 결정 창 · 작업 중 · `left_in_box`가 입력 칸만 읽음
- 기존 `tests/test_inject.py` 그대로 통과
- 전체: pytest 885 통과 · 1 건너뜀(2분 46초), `node --test tests/js/` 152 통과

## README에서 바꾼 줄

- README 175(3.1 「입력 줄이 가려져 있으면 Esc로 닫고 보낸다(11-09)」)를 「창이 떠 있으면 종류로 갈라 닫거나 거부한다」 줄과 아래 4줄로 바꿨다. 뺄 줄 없음

## 규칙

- **위반 1건 — 진행 글을 영어로 썼다**: 시험을 돌린 뒤 「Pass.」, log를 쓰기 직전 「Now the log file while tests run.」(11-13 21:30 무렵). 까닭: 도구 결과를 보고 바로 짧게 쓰다 한국어 확인을 건너뛰었다. 브리지 훅이 알려 준 뒤 한국어로 바꿨으나, 전체 시험 결과를 본 직후 「Both pass.」를 한 번 더 썼다(같은 까닭). 그 뒤로는 한국어
- 그 밖: 파일은 Edit · Write로만 고쳤다. 화면 분석에 쓴 `python3 -I - <<'EOF'`는 스크래치 파일만 읽었고 저장소 파일을 쓰지 않았다
