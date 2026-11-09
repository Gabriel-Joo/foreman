# 펫퍼민트 create = true 준비 — 하위 폴더 · 번호식 제목 · 휴지통 분리 · 제목 단계, 모의 실행 (2026-11-09 오후, 원본 폴더)

앞 기록: [alerts_denied_xmsg_bang_20261109.md](alerts_denied_xmsg_bang_20261109.md). **`create`는 여전히 `false`** — 사용자가 아래 모의 실행을 보고 정한다.

## 고친 것(사용자 네 가지, 모두 프로젝트 옵션 — 런슈즈 · FOREMAN은 그대로)

1. **하위 폴더를 따라간다** `new_parent = "folder"`: `docs/<폴더>/x.md` 새 문서는 같은 폴더의 게시된 형제들이 모두 걸린 부모 페이지 아래(`docs/02_pipeline/` → 「02. 파이프라인 설계」). 형제가 없거나 부모가 여럿이면 만들지 않고 실패
2. **번호식 제목** `new_title = "numbered"`: 번호는 파일 이름(`17_` → "17", `03a_` → "03-1"), 이름은 부모 페이지의 원본 문서(`pipeline.md`)에서 그 번호로 시작하는 **마지막** 줄(「7. 단계별 문서」 — 앞쪽 목록 "15. 모니터링 (Prometheus + Grafana) — △ …"보다 짧다). 펫퍼민트 docs엔 H1이 없어 이름을 다른 데서 가져올 수 없었다. 번호 · 이름을 못 정하면 만들지 않고 실패("그 목록에 한 줄 더한 뒤 맞춥니다")
3. **휴지통 분리** `archive = false`: `create`와 따로. 원본이 사라지면 실패로만 남긴다(`docsync.sync` · `Publisher.archive`). 기본값 true(런슈즈 그대로)
4. **제목 단계** `headings = "md"`: 마크다운 단계 그대로 `##` → heading_2 · `###` → 3 · `####` 이상 → 4(사람이 옮긴 페이지 모양). 새 페이지뿐 아니라 git만 바뀌어 끼우는 블록(`shape_patch`)도 같은 변환. 비교는 글만 보고 지문은 기본 변환이라 지금 20쪽 맞추기 결과는 같다

## 모의 실행 — 펫퍼민트 복제본(스크래치)에 가정 커밋, Notion 읽기만 · 쓰기 기록만 · DB 안 씀

가정: 새 `docs/02_pipeline/17_dry_check.md`(+ `pipeline.md` 7절에 "17. 모의 점검 문서 (가정)" 한 줄) · 새 `docs/02_pipeline/05a_question_rewrite.md`(목록 줄 안 더함) · 새 `docs/03_extra.md` · `docs/02_pipeline/16_code_answers.md` 지움

| 파일 | 결과 |
|---|---|
| 17_dry_check | 「02. 파이프라인 설계」 아래 **"17. 모의 점검 문서 (가정)"** 만듦 — 블록 quote · heading_2 · heading_3 · paragraph · **heading_4** · 목록 · 꼬리 줄 |
| 05a_question_rewrite | 같은 부모 아래 **"05-1. 질문 재작성 (문어체 → 구어체)"** — 이름은 pipeline.md 앞쪽 목록 줄(7절엔 없음) |
| pipeline.md | 목록 줄이 새 하위 페이지 제목과 같아 글 비교에서 빠짐 → **꼬리 줄만** 고침(본문에 "17. …" 글 블록을 따로 끼우지 않는다) |
| 03_extra | **실패** — 상위 폴더 문서는 이름을 정할 원본 문서가 없다(부모가 [기술문서]) |
| 16_code_answers 지움 | **실패로만** — 휴지통 안 보냄 |

차례(부모 아래 하위 페이지): 00 … 16 다음에 **19번째 "05-1. …", 20번째 "17. …"** — Notion은 새 하위 페이지를 부모 **끝**에 붙인다. 17처럼 맨 뒤 번호는 맞지만 05-1처럼 **중간 번호는 차례가 어긋난다**. API로는 자리를 정할 수 없고, 다시 세우려면 18쪽을 모두 옮겨야 한다(옮기면 「02」 본문 7절 안에 있던 하위 페이지 자리도 모두 끝으로 간다) — 그래서 `order = "keep"`은 그대로 두었다. 새 페이지 링크는 「02」 본문 맨 아래(꼬리 줄 뒤)에 생긴다

## 확인 안 된 것

- **heading_4 만들기** — 사람이 옮긴 페이지에 heading_4 블록이 있으니 Notion이 아는 종류지만, 우리 통합이 만들 수 있는지는 쓰기를 해 봐야 안다(모의 실행은 쓰지 않음). 안 되면 그 파일이 실패로 남고 알린다(조용히 넘어가지 않음)

## 확인

- 파이썬 508(새 `test_heading_md_keeps_markdown_levels` · `test_archive_separate_from_create`) · JS 53
- 브리지 16:09:59 다시 띄움(승인 대기 0 뒤) — `archive = false` · `headings = "md"` 적용, `create = false` 그대로

## 켬(사용자 — 모의 실행에서 17 만듦 · 05-1 실패 확인 뒤)

- 켜기 전 상태(쓰기 없음): 새 0 · 바뀜 0 · 지워짐 0 · 못 읽음 0, `@docs-sync` = origin/main `2e287cb` — 펫퍼민트에 새 docs 커밋 없음(상태를 보려고 펫퍼민트 저장소에서 `git fetch` 한 번 — 원격 추적 기록만)
- **16:51:18 KST `create = true`로 브리지 다시 띄움**(승인 대기 0 뒤). 첫 맞추기(뜬 뒤 60초)는 할 일이 없어 쓰기 0 · 새 페이지 0
- **heading_4 만들기는 아직 확인 못 함** — 펫퍼민트가 `####`가 든 새 문서나 절을 push해야 처음 쓴다. 안 되면 그 파일이 실패로 남고 텔레그램으로 온다(사용자: 그때 보면 된다)

## 런슈즈 서브에이전트 기본 모델 sonnet(사용자 지시, 런슈즈 저장소)

- CC 문서(code.claude.com/docs/en/sub-agents.md 「Choose a model」): 환경 변수 `CLAUDE_CODE_SUBAGENT_MODEL`(별칭 가능). 순서 = 호출의 `model` → 에이전트 정의 `model:` → 이 변수 → 부모 모델. `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`는 호출 인자까지 무시하게 해 넣지 않았다. 기본 제공 Explore · Plan은 이 변수로 안 바뀐다. 떠 있는 세션에 바로 걸리는지는 문서에 분명하지 않다. CC 2.1.319
- 런슈즈 `4576062`(커밋만, push는 그 세션 몫): 새 `.claude/settings.json` `{"env": {"CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"}}`, CLAUDE.md 「서브에이전트 모델」 절 — 판단이 결과를 좌우하는 일(데이터 검증 · 판정, 여러 파일 설계 변경, 코드 리뷰)은 부를 때 `model: "opus"`. 런슈즈 세션의 커밋 안 한 docs 두 파일은 건드리지 않음
- 확인: 16:58 KST 이후 런슈즈 서브에이전트 응답 없음 — 첫 응답의 모델을 지켜보는 중
- **결과(20:29 KST, 세션 168ece53이 이어받아 DB 감시)**: 첫 응답은 런슈즈 세션 234(`3d924709`, 19:57 KST 새로 뜸 — 설정 뒤에 뜬 세션)의 두 호출. 둘 다 호출에 `model` 인자 없음, 메타 `launchedWithDefaults: true`
  - general-purpose("docs에서 낱말 위치 찾기 2"): 응답 **sonnet 4번** → 설정이 먹는다
  - Explore("docs에서 낱말 위치 찾기"): 응답 **opus 5번** → 기본 제공 Explore는 이 변수로 안 바뀐다(문서 그대로). 부모 모델(opus)을 따른다
  - Explore도 싸게 하려면: 부를 때 `model` 인자를 주거나, 같은 이름의 사용자 에이전트 정의로 덮는다 — 런슈즈 저장소 일(사용자가 시킬 때)
  - 떠 있던 세션(225)에 설정이 걸리는지는 그 세션이 서브에이전트를 부르지 않아 아직 모름
- **Explore도 sonnet으로(사용자 20:3x)**: 런슈즈에 같은 이름 에이전트를 정의해 기본 제공을 덮어쓰는 쪽(부를 때마다 지정은 모델이 지키는지에 달려 쓰지 않음). 런슈즈 세션 `runshoes-99`(234)에 세션 간 메시지로 전함 — **바꾸기 전에 파일 · 내용 · 덮어쓰기 근거(CC 문서) · CLAUDE.md 문장 · 확인 방법을 먼저 보여 주고 그 세션 사용자 확인 뒤 고치게**. FOREMAN · 펫퍼민트는 런슈즈 확인 뒤 사용자가 정한다
- **결과(20:4x)**: 런슈즈 `57420bd`(push 안 함 — 그 세션 사용자가 말할 때) — `.claude/agents/Explore.md`(model: sonnet, 쓰기 도구 막음 · 읽기 전용 본문), CLAUDE.md 「서브에이전트 모델」 한 문장. 근거 CC 문서 sub-agents "A user or project subagent named `Explore` overrides the built-in and keeps its own `model` field"
  - FOREMAN이 서브에이전트 기록으로 다시 셈: 저장소 안 새 세션 `cf4dd796` Explore → **sonnet 7**(+ opus 1줄 — general-purpose에서도 보인 응답 아닌 줄), 저장소 밖 비교 `639dd193` 기본 제공 Explore → opus 9 ✓
  - 같은 찾기 일(compare.view 쓰는 곳)에서 둘 다 정답 8곳(런슈즈 보고)
  - FOREMAN · 펫퍼민트에 넣을지는 사용자가 정한다
