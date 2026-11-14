# 세션 패널 호버 셋 · 머리줄 Bash 글 다듬기 (2026-11-14, 디자이너 396, cc/foreman-2)

관리자 362의 일감(사용자 11-14 「설명이 과하다」).

## 한 일

| 곳 | 전 | 뒤 |
|---|---|---|
| 모델 칸 호버(`render.js` `modelChip`) | 모델 — 눌러서 이 세션의 모델을 바꿉니다(/model). 지금 claude-opus-5-5. | 모델 — 눌러서 이 세션의 모델을 바꿉니다. 지금 Opus 5.5. |
| 모델 칩 호버(누르지 않는 칩) | 모델 — 이 세션이 마지막 응답에 쓴 모델입니다(claude-opus-5-5). | …모델입니다(Opus 5.5). |
| 「따로 작업 foreman-2」 호버(`opanel.js` 머리 셋째 줄) | 줄 전체 `title`: 따로 작업 foreman-2 · 세션 <해시> · tmux 창 %N · FOREMAN · /home/…/.worktrees/foreman-2 | 그 글자에만: 따로 작업 — foreman-2(브랜치 cc/foreman-2)에서 일합니다. (합치기 기다리면 「합치기를 기다립니다.」를 붙임, `render.js` `worktreeTip`) |
| 「쌓인 대화 N%」 호버 | …얼마나 채웠는지입니다. 계정 사용 한도(머리의 한도 칩)와는 다릅니다. | …얼마나 채웠는지입니다. |
| 머리줄 지금 하는 일 | Bash S=/tmp/claude-1000/-home-kopo17-AI-programming-foreman--wor… | 화면 점검하는 중(호버 「명령 — 지금 돌리는 명령입니다.」 + 명령 200자) |
| [세션 정리] 탭 「지금」 · classic 카드(`render.js`) | Bash <명령 120 · 90자> | 같은 하는 일 + 호버 |
| 캐릭터 호버(`office.js`) | Bash <명령 70자> | 하는 일, 그 아래 작은 줄에 명령 |

- 하는 일 표 `render.js` `BASH_DOING`: pytest · `node --test` · `npm test` → 시험 돌리는 중, git commit → 커밋하는 중, push · merge-tree(합칠 수 있는지 보는 중) · merge/rebase(합치는 중) · fetch/pull · add/reset 따위(변경 정리하는 중) · 나머지 git(변경 기록 보는 중), `tools/screen.py` → 화면 점검하는 중, grep/find → 찾는 중, cat/sed -n/ls → 파일 보는 중, curl → API 부르는 중, systemctl → 서비스 보는 중, tmux · docker · 설치 · sleep, 그 밖의 python/node → 스크립트 돌리는 중, 모르면 「명령 실행 중」
- `&&` · `;` · `|`로 나눠 앞의 준비 명령(`cd` · `VAR=값` · `timeout N` · mkdir · echo · export)은 건너뛰고 처음 걸리는 일을 쓴다 — 첫 사진에서 `S=…; mkdir …; … screen.py`가 「명령 실행 중」으로 나와 고쳤다
- 다른 도구(Read · Edit · Grep …)는 전처럼 「도구 대상」 — 파일 이름 · 찾는 말이라 읽힌다. [활동] 탭은 도구 호출 기록 자체라 명령을 그대로 둔다
- 시험 `tests/js/now_doing.test.mjs`(6개 — 머리 벗기기 · 표 · description 먼저 · 이스케이프 · 따로 작업 호버 · 모델 호버)

## 조사 결과 · 판단 근거

- **모델 이름 함수는 새로 두지 않았다** — 서버 `bridge/model_choice.py` `label`이 이미 `claude-opus-5-5` → 「Opus 5.5」, `claude-fable-5-2` → 「Fable 5.2」, 모르는 꼴은 id 그대로를 하고 대시보드가 `model_label`로 내준다. 화면은 그것을 쓰고(없으면 id). 388(foreman-3)도 같은 `modelChip` 호버 줄에서 「(/model)」만 빼는 중이라(작업 트리 diff로 확인) 그 줄이 겹친다 — 나중에 합치는 쪽이 rebase로 푼다. 388은 JS에 모델 이름 함수를 따로 만들지 않았다(`sameModel`만)
- **Bash `description`은 화면까지 오지 않는다.** 수집기(`bridge/assembler.py` 851줄)는 tool_use 이벤트 `payload.input`에 입력 전체(description 포함)를 남기지만 `target`에는 명령만 넣고, 대시보드 `bridge/api/dashboard.py` 554줄 `acts` 쿼리는 `e.tool, e.target, e.ts, e.subagent_id`만 꺼낸다. 실시간 이벤트(`store.js` 355줄 `tool_use`)도 payload를 쓰지 않는다. 그래서 화면 쪽 표로 마쳤고, 화면은 `activity.description`이 오면 표보다 먼저 쓰게 해 두었다
- 「쌓인 대화」 ↔ 「한도」: 한도 칩 호버(`office.js` 272줄)의 「세션마다 쌓인 대화 %(패널 머리줄)와는 다릅니다.」는 일감 범위가 아니라 그대로 두었다. 같은 「다릅니다」 문장이라 사용자 기준으로는 이것도 군더더기일 수 있다 — 뺄지는 관리자 · 사용자가 정한다

## 지운 것

| 무엇 | 어디 | 까닭 |
|---|---|---|
| 머리 셋째 줄 전체 `title`(따로 작업 · 세션 해시 · tmux 창 · 프로젝트 · 경로) | `opanel.js` 「제목 아래 한 줄」 `$('pMeta').title = …` | 사람이 알 일이 아닌 것. 「따로 작업」 글자에 자기 호버를 달았다. 세션 해시 · tmux 창은 「세션 N」 호버에 남아 있다 |

이 둘레에 다른 안 쓰는 코드는 없었다(`sessionIds` · `projectLabel` · `oneLine`은 다른 곳에서 쓴다).

## 확인

- `node --test tests/js/` — 178개 통과
- 미리보기(`POST /api/sessions/396/preview`, 8200)에서 `tools/screen.py --no-term --session 396` 세 테마(magic · office · site) × 여섯 크기 18장: 문제 0건(`tipAudit` 0, 페이지 오류 0. 「audit(고정 안 됨)」 수는 고치기 전과 같음). 점검이 도는 동안 머리줄은 「찾는 중」 · 「변경 기록 보는 중」(그때 이 세션이 친 grep · git diff)으로 나왔다
- 사진(scratchpad, 커밋하지 않음): 고치기 전 머리줄 「Bash S=/tmp/claude-1000/-home-kopo17-AI-programming-foreman--wor…」, 고친 뒤 「화면 점검하는 중」 · 「따로 작업 foreman-2」 · 「Opus 5.5 ▾」. DOM에서 뽑은 고친 뒤 호버(`#pMeta [data-tip]`):
  - 쌓인 대화 13% → 「쌓인 대화 — 이 세션의 대화가 모델이 한 번에 읽을 수 있는 양(창)을 얼마나 채웠는지입니다.\n토큰 12만 6천\n창 100만」
  - 따로 작업 foreman-2 → 「따로 작업 — foreman-2(브랜치 cc/foreman-2)에서 일합니다.」
  - Opus 5.5 ▾ → 「모델 — 눌러서 이 세션의 모델을 바꿉니다. 지금 Opus 5.5.」
  - 하는 일 → 「명령 — 지금 돌리는 명령입니다.\n<명령>」

## main 위로 rebase (11-14, 388 `a4d7ecb` 합친 뒤)

- 관리자 merge-tree 확인대로 `render.js` `modelChip` 호버 두 줄 한 곳만 충돌했다(문서는 저절로 합쳐짐). 388은 「(/model)」만 빼고 이름은 `s.model` id 그대로였고, 서버 이름 함수(`model_choice.label`)는 바꾸지 않았다. 바꾸는 중 표시 `pend.label`은 388의 버전별 라벨(`config/models.toml` choices)을 그대로 쓴다
- 이 브랜치 줄(「(/model)」 없음 + `model_label`)로 풀었다 — 388의 버전별 라벨은 `pend.label` · 모델 고르기 창에서, 호버의 지금 모델은 「Opus 5.5」로 둘 다 산다. 푼 내용은 다시 쓴 첫 커밋 `ae4fe74`에 들어 있다
- 다시 돌림: `node --test tests/js/now_doing.test.mjs` 6개 통과, `node --test tests/js/` 181개 통과, `git merge-tree --write-tree main HEAD` 충돌 없음

## 문서

- `docs/10_office_design.md` 「관리자 자리 · 이름표 · 머리줄」에 셋째 줄 호버 · 지금 하는 일 절
- `docs/style_guide.md` 4-1 「쌓인 대화 ↔ 한도」 줄에 쌓인 대화 호버 첫 줄 문구, 「Bash는 하는 일로」 줄(이번에는 사용자가 같은 브랜치에서 맞추라고 함 — 합치기 카드가 사람 승인으로 간다)
- `docs/operations.md`에는 해당 줄이 없어 고치지 않았다

## 남은 일(관리자가 코더에게)

- **Bash description을 화면까지** — `bridge/api/dashboard.py` `acts` 쿼리에 `JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.input.description'))`를 더해 `activity.description`(200자, Masker 거친 값이라 그대로 내도 됨)으로 내고, 실시간 `tool_use` 이벤트(SSE)에도 같은 값을 실어 `store.js` 355줄이 `s.activity.description`에 넣게. 화면(`render.js` `nowDoing`)은 이미 그것을 먼저 쓴다
- ~~한도 칩 호버의 「쌓인 대화 %와는 다릅니다」를 뺄지~~ → 11-14 사용자 「빼라」(관리자 362 전달). `office.js` 한도 칩 호버에서 뺐고 `docs/style_guide.md` 4-1 문구도 맞췄다
- Bash description 서버 몫은 이 카드 · 388이 합쳐진 뒤 관리자가 코더에게 맡긴다(11-14 관리자)

## 규칙

- 파일 고치기는 모두 Edit · Write로 했다. 다만 커밋 메시지를 `git commit -F - <<'EOF'`(heredoc을 git 표준 입력으로)로 넘겼다(11-14, 커밋 `45af6df`를 만들 때). 파일을 쓰지는 않았지만 일감의 「heredoc 리디렉션도 하지 않는다」에 걸릴 수 있는 꼴이라 적는다. 까닭: 본문이 여러 줄이라 습관대로 썼다. 바로잡음: 이 기록을 더하는 수정 커밋은 `-m`을 여러 번 쓰는 꼴로 했다
- 그 밖에 규칙 위반 없음.
