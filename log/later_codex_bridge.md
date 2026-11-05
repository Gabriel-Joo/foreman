# 나중에 할 일 — Claude Code와 Codex 같이 쓰기 (11-03 조사 · 결정, 설치는 나중)

- **상태**: 조사 · 방향 결정까지. **설치하지 않았다**(사용자: "설치는 나중에 하자. 지금 FOREMAN 할 게 남아서")
- 서버 지금: Codex CLI 없음(`~/.codex` 없음), Node 20 · npm(사용자 전역 `~/.npm-global`), 사용자 범위 MCP 서버 0개, CC 2.1.316

## 쓸 데 — 두 가지 (11-06 사용자)

1. **일감 떠넘기기** — 양이 많은 반복 작업. 예: 런슈즈 상품 문구 쓰기
   - Opus 토큰을 아끼는 용도
   - 이 일은 Codex가 **글을 써야** 한다. 아래 11-03 방향(읽기 전용 잠금)과 부딪힌다. 할 때 둘 중 하나를 정한다
     - (가) Codex는 읽기 전용으로 답(글)만 내고, CC 세션이 그것을 파일에 반영한다
     - (나) worktree 안에서만 `workspace-write`. 합치기가 검토 관문이다(11단계 worktree와 같은 방식)
2. **다른 모델의 의견** — 설계 리뷰, 교차 검증
   - 읽기 전용으로 충분하다(11-03 방향 그대로)

## 왜 모델 하나보다 여럿인가 (11-06 사용자)

- **같은 모델끼리 보면 같은 것을 놓친다.** 리뷰 · 점검을 같은 모델에 시키면 만든 쪽과 같은 맹점을 공유한다. 다른 회사 · 다른 학습의 모델이 보는 것이 교차 검증이다
- **일의 무게에 맞는 모델을 쓴다.** 판단이 드는 일은 Opus, 양이 많은 반복은 더 싼 모델. 11-06 [압축으로 잊은 것 찾기]도 Opus 대신 Sonnet으로 충분했다(재현율 0.71 · 정밀도 0.91, 한 번 약 2달러 — `log/handoff_v2_d_result.md`)

## 시작하기 전에 — Sonnet과 먼저 비교한다 (11-06 사용자)

- Codex를 붙이기 전에 **같은 일을 Sonnet으로 시켜 비용 · 품질을 본다.** Sonnet으로 충분하면 Codex는 붙이지 않는다(설치 · sudo 잠금 · 따로 청구가 다 드는 일이다)
- 비교 방법은 d단계와 같게 한다: 정답(사람이 확인한 결과)을 하나 두고 맞댄다
  - 일감 떠넘기기: 런슈즈 문구 N개를 Sonnet `claude -p`로 → 사용자가 고친 양 · 비용 · 시간
  - 다른 모델의 의견: 지난 설계 리뷰 하나를 Sonnet에 다시 시켜 → Opus가 놓친 것을 Sonnet이 찾나(같은 회사 모델이라 맹점이 겹칠 수 있다 — 이 경우는 Sonnet이 충분해도 Codex를 따로 볼 이유가 남는다)
- 결과는 이 파일에 표로 남기고 Codex를 붙일지 정한다

## 후보 조사 (11-03, 코드는 실행하지 않음)

| 후보 | 라이선스 | 동작 | 이 서버에 끼치는 영향 |
|---|---|---|---|
| w4sspr/codex-bridge | MIT | 열어 둔 Codex 화면 세션에 메시지를 넣고 답을 읽는다(4라운드는 명령 안내문) | macOS에서만 시험, 모든 Codex 기록을 읽는다 |
| naldomadeira/agents-bridge-mcp(→ agentmate) | MIT | `mate_ask` = 한 번 묻고 답(`--sandbox read-only`, 120초), 양방향 | 전역 hook 2개, npx 버전 고정 없음, 팀 리더는 `danger-full-access` |
| raysonmeng/agent-bridge | MIT | 상주 데몬이 메시지만 중계 | 전역 hook · 데몬, 기본값 `--dangerously-skip-permissions` · `--yolo`, 전용 실행기로 CC를 띄워야 한다(tmux 세션과 충돌) |
| McAvity/bidirectional-bridge-claude-codex | MIT | 양방향 위임, 도구 30여 개 | 무겁다, Codex가 `approval never` · `workspace-write` |
| catesandrew/mcp-agent-bridge | Apache-2.0 | 한 번 묻고 답 + Copilot | 프록시 데몬, Codex 호출 시간 제한 없음, 관계없는 도구 18개 |

## 방향 — 처음 추천이 틀려서 고쳤다

**처음 추천**(11-03, 사용자 승인): "Codex CLI에 든 `codex mcp-server`를 FOREMAN 저장소에만 프로젝트 범위로 등록". **틀렸다** — sandbox 고정을 확인하다 알았다:
- `codex mcp-server`는 **없어졌다** — 2026-08-20 폐기 예고, 2026-09-05 제거(커밋 531f383 "Remove the deprecated `codex mcp-server` command (#42993)"). `rust-v0.153.2`의 `cli/src/main.rs`에는 있고 `rust-v0.154.0`에는 없다(직접 확인). 지금 최신은 0.166.0(`npm view`). 쓰려면 폐기된 0.153.2에 묶여야 한다
- 그 버전에서도 **서버 쪽에서 sandbox를 잠글 수 없었다**: 도구 호출마다 설정을 새로 만들고, 호출자가 보낸 `sandbox` · `approval-policy` · `config`가 이긴다. `codex mcp-server -c sandbox_mode="read-only"`는 도구 세션에 전해지지 않는다(`mcp-server/src/codex_tool_config.rs` — 조사 에이전트가 소스로 확인, 직접 다시 보지는 않음)

**고친 방향**: MCP 서버 없이 **Bash로 `codex exec -s read-only "질문"`**, 잠금은 Codex의 시스템 요구사항 파일로.
- `/etc/codex/requirements.toml`(Linux, **sudo 필요 — 사용자가 친다**, 이 서버의 모든 Codex 실행에 걸린다 — kopo02 포함이므로 알리고):
  ```toml
  allowed_sandbox_modes = ["read-only"]
  allowed_approval_policies = ["never"]
  ```
  허용되지 않는 sandbox를 요청하면 읽기 전용으로 떨어지고, `danger-full-access` + `never`면 실행을 거부한다. **approval도 `never`로 잠그는 이유**: `on-request`면 Codex가 sandbox 밖 실행 승인을 호출자에게 물을 수 있다. 0.138.0부터 문서는 `allowed_permission_profiles`를 권한다 — 설치할 때 그 버전 문서로 다시 맞춘다
- Linux sandbox는 bubblewrap을 쓴다 — `sudo apt install bubblewrap`(사용자)
- 설치: `npm i -g @openai/codex`(sudo 없음) + `codex login`(ChatGPT 요금제 또는 API 키 — 사용자가)
- 설치 뒤 확인: `codex exec -s danger-full-access "create /tmp/codex_probe.txt"` → 요구사항 오류로 거부, `codex exec -s workspace-write "create ./codex_probe.txt"` → "falling back" 경고 + 파일 없음

## 비용

Codex 쪽은 로그인한 ChatGPT 요금제나 API 키로 청구, CC 쪽은 Codex의 답을 다시 읽는 만큼. 여러 라운드는 라운드 수만큼 곱해진다.

## FOREMAN에서 잡기

- MCP가 아니라 **Bash 도구 호출**(`codex exec …`)로 남는다 — 수집기는 이미 모든 tool_use를 이벤트로 저장한다. 명령 모양(`codex exec`)으로 "Codex에게 물어봤다"를 가려내고, tool_use ~ tool_result를 서브에이전트처럼 일꾼 하나로 그릴 수 있다
- 한계: Codex 쪽 토큰은 CC 트랜스크립트에 없다 — `~/.codex`의 Codex 세션 기록을 따로 읽어야 한다
- 승인 정책: `codex exec`는 지금 규칙에 걸리지 않는다(pass). 요구사항 파일로 잠그면 `-s read-only`가 아닌 호출을 따로 묻게 할 필요는 없다 — 그래도 잠금을 확인하기 전에는 `codex exec`(read-only 아닌 것)를 ask로 두는 게 안전하다

## 할 때 순서

1. 사용자: `sudo apt install bubblewrap`, `/etc/codex/requirements.toml` 작성(위 내용, 그때 버전 문서로 확인)
2. `npm i -g @openai/codex`, 사용자: `codex login`
3. 위 두 확인 명령으로 잠금 확인
4. FOREMAN: `codex exec` 이벤트 가려내기 · 일꾼으로 그리기, (선택) Codex 세션 기록에서 토큰
