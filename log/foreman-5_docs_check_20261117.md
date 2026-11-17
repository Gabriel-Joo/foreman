# 문서 도구 합치기 3단계: 문서 점검을 한 묶음 위로, FOREMAN 쪽 (foreman-5, 2026-11-17)

관리자 410 코더 일감. 사용자 결정(11-17) 1~9를 따랐다. 1단계는 `log/foreman-6_doctext_20261117.md`, 2단계는 `log/foreman-4_docrefs_config_20261117.md`. 인프라 저장소는 읽기만 했다(scratchpad의 `git clone --no-hardlinks` 사본에서만 껍데기와 설정을 넣어 보았다. 끝난 뒤 인프라 저장소 `git status` 0줄).

## 1. 결정마다 한 것

| 결정 | 한 것 |
|---|---|
| 1 다루는 곳을 둘로 | 거꾸로 찾기(`bridge/docrefs.py` `refs_in`)가 머리 주석 「다루는 곳」을 아예 읽지 않는다. 다루는 곳은 덮기 검사(`tools/docs.py check`)와 서기실 셈만 읽는다. 칸 이름은 그대로 두고 뜻만 정했다(아래 2절) |
| 2 FOREMAN 밀림 | 근거 표시는 파일 단위 그대로(줄 번호 안 붙임). FOREMAN 편 단위 밀림은 서기실 셈(`bridge/manuscript.py`)이 계속 「다루는 곳」으로 센다(아래 2절) |
| 3 시험 폴더 범위 | `notion/16_tests.md` 하나만 `tests/`를 통째로 덮었다. 그 편이 본문에서 가리키는 시험 장치와 여러 기능에 걸친 시험 13개만 남기고, 나머지 시험 141개는 그 시험이 지키는 기능 편 32편의 다루는 곳으로 옮겼다(아래 표). 덮기 구멍 0(옮기기 전과 같이 덮지 않은 파일 4개였고, 그 넷도 `notion/01_structure.md`에 넣어 0) |
| 4 읽은 커밋 편마다 | 기본값 `read_commit = "piece"` 그대로. 점검은 편마다 그 커밋이 저장소에 있는지 본다. `"set"`이면 원고와 docs가 하나, 포트폴리오끼리 하나(인프라 지금 동작). 인프라는 사본에서 `piece`로도 틀린 것 0(아래 5절) |
| 5 문서 점검 명령 | `tools/docs.py check [-v]`, 판정은 `bridge/doctext/check.py`. 인프라 `docs-check.py` 1~7번 규칙. 저장소마다 다른 것은 `.foreman/docs.toml` 표 `[check]`(아래 3절). 근거 확인기(`bridge/evidence.py`)와 겹치던 판정(근거 파일과 줄 `mark_problem`, 다루는 곳 경로 `covers_problem`, 의심 줄 `is_claim`, `SKIP_LINE`)은 check.py 한 곳이고 근거 확인기가 가져다 쓴다 |
| 6 근거 없는 파일 세기 | 아래 4절 |
| 7 옛 껍데기 지우기 | `tools/docrefs.py`를 지웠다. 쓰던 곳을 모두 `tools/docs.py refs`로: `bridge/docrefs.py` `prompt_block`(코더 첫 글), `bridge/mergeprep.py` 합친 뒤 글, `bridge/foreman.py` 교장 지시문 코더 줄, CLAUDE.md 「따로 작업」 줄, `docs/operations.md` 50줄, `docs/11_worktree.md` 「9.」, `docs/12_scribe.md` 「5.」와 코더 줄, 원고 `notion/06_sessions.md`, `notion/07_merge.md`, `notion/07_merge/01_card.md`(다루는 곳에서도 뺌), `notion/10_scribe.md`, 시험 `tests/test_coder_docs_rule.py`, `tests/test_docrefs.py`, `tests/test_docrefs_config.py` |
| 8 카드에서 나눠 보이기 | 거꾸로 찾기 결과에 문서마다 `by`(코드 파일로 걸린 줄이 하나라도 있으면 `code`, 문서로만 걸렸으면 `doc`)와 맨 위 `by`(둘의 `total`, `unfixed`). 카드 위 줄 둘 「📄 코드로 걸린 문서 N, 안 고침 M」, 「📄 문서로만 걸린 문서 K, 안 고침 L」(0인 쪽은 뺌), 「자세히」 문서마다 「코드로」, 「문서로만」, 목록은 코드로 걸린 것 먼저. 알림, 관리자 카드 글, 합친 뒤 글은 `count_line` 한 줄(` / `로 나눔). `by`가 없는 옛 카드는 옛 한 줄 |
| 9 docs.toml 경고 | 설정은 지금처럼 원본 폴더 작업 트리 판으로 읽는다. 브랜치(`base...브랜치`)가 `.foreman/docs.toml`을 바꿨으면 카드 `docs.config_note` 「이 브랜치가 설정을 바꿨습니다. 이 셈은 main 설정 기준입니다」(base가 main이 아니면 그 이름). 카드 위 줄, 「합치기 준비됨」 알림, 관리자 카드 글에 ⚠로 |

결정 3에서 시험 파일을 받은 편(서브에이전트가 시험 파일의 import와 지키는 것을 읽고 골랐다. 머리 다루는 곳 줄만 바꿨고 읽은 커밋과 본문은 그대로)

| 편 | 더한 다루는 곳 |
|---|---|
| 01_structure | tests/test_units.py (+ 덮지 않던 .gitignore, bridge/__init__.py, bridge/api/__init__.py, bridge/db/__init__.py) |
| 02_ingest/01_transcript, 03_turns | test_lookup.py / test_stage2_db.py |
| 03_session | js slash, xmsg, test_api_error, test_bang_watch, test_human_wait, test_inject, test_inject_screen, test_stallwatch, test_stallwatch_bg, test_xmsg |
| 04_approval/01_rules, 03_summary | tests/fixtures/, test_approval, test_approval_now, test_approval_silent_delete / test_approval_summary |
| 05_roles/01_roles, 02_guards, 03_keys | test_inspector_close, test_session_role / test_roleguard, test_roleguard_inspector, test_pgrep_guard, test_reposcope, test_korean_check / test_scopetoken, test_publish_scope |
| 06_sessions | test_handoff, test_manager_seat, test_preview, test_worktree, test_wt_end, test_wt_truth |
| 07_merge/01_card, 02_reconcile | js coder, mergeprep, test_mergeprep, test_mergeprep_db, test_merge_remind_catchup, test_docs_tool, test_docs_config, test_docrefs_config / test_reconcile |
| 08_handoff/01~04 | js losscheck, test_compactwatch, test_losscheck / test_handoff_state, test_pointers / js promote, test_promote / js moveflow, handoff_flow, test_moveflow, test_switchwatch |
| 09_dispatcher/01~04 | js foremanchat_drop, foremanchat_multi, test_foreman, test_foreman_ctx, test_foreman_fail, test_foreman_multi, test_foreman_redo, test_no_wait_prompt / js fmpanel_notes, test_foreman_note, test_note_auto_retire, test_wake_url, test_instructions_note_threads / test_overlap, test_overlap_base / js handover, test_handover, test_managers, test_escalate_number |
| 10_scribe/01~04 | js scribe, test_scribe, test_scribe_room, test_scribe_two_paths / js postit, test_postit / test_evidence, test_scribe_ask, test_doctext, test_techdoc, test_docs_check(이번 새 시험) / test_docsync, `tests/test_notion*.py`, test_portfolio_projects, test_publish_hold |
| 11_notify, 12_pipeline, 13_usage | test_fail_now_unpriced / js shipstate, test_pipeline / js modelmenu, role_label, test_model_choice, test_usage |
| 14_screen/01~05 | test_app_db, test_human_needs / js grid, theme, walk, banner_wrap, name_ink, role_aura, overhead_stack, stack_side, seat_host / js grip, md, render, uiscale_range, term_cell, api_stop, appr_place, bg_line, escalate_unseen, now_doing / js term_follow, test_ccscreen, test_terminal / js merge_wait, merge_wait_manager, overhead_marks, test_merge_wait, test_merge_wait_manager, test_merge_wait_off_remind, test_overhead_marks |
| 16_tests(새 다루는 곳) | tests/conftest.py, tests/testdb.py, tests/screen_words.py, test_js, test_live_config_shape, test_public_secret_shapes, test_bridge_alert, test_coder_docs_rule, test_docrefs, test_fail_notify_scan, test_hook_timeouts, test_hookmiss, test_roles_agree, pyproject.toml, requirements.lock, deploy/systemd/foreman-bridge.service |

판단이 애매했던 것: `test_handoff.py`는 세션 띄우기 쪽(06)이 커서 06에, `merge_wait*`(화면 대기 표시)는 14_screen/05에, `test_units.py`는 `config.py`를 다루는 편이 01_structure뿐이라 거기에. 16편 본문의 `[code:tests/]`(시험 수 문장)는 근거 표시라 그대로 두었다(머리 다루는 곳만 좁히라는 일감). 이 표시는 거꾸로 찾기에서 시험 파일 하나만 바뀌어도 16편 43줄을 건다. 문장이 「시험 수」를 말하는 것이라 맞는 걸림으로 보았다.

## 2. FOREMAN에서 무엇이 어떻게 바뀌나(결정 1, 2)

- **칸 이름**: 「다루는 곳」 그대로, 뜻만 「파일 단위 덮는 곳」으로 정했다. 까닭: 이름을 「덮는 곳」으로 바꾸면 FOREMAN 66편과 인프라 56편 머리, 서기 지시문(`scribe_room._head_rule`), 화면 말 시험, 게시기 문서를 함께 바꾸고 옛 이름도 한동안 받아야 한다. 이름이 둘이면 어느 쪽을 적을지부터 애매해진다는 결정 7의 까닭이 여기에도 맞는다. 뜻은 `docs/12_scribe.md` 「5.」 머리 주석 줄, `docs/11_worktree.md` 「9.」, 원고 03_evidence와 07_merge/01_card에 적었다
- **거꾸로 찾기(합치기 카드, 코더 도구)**: 다루는 곳을 읽지 않는다. FOREMAN main 최근 60커밋(커밋 하나씩 범위)에 원본 폴더 main 판(`3bda826`)과 이 브랜치 판을 돌렸더니 걸리는 문서 합 654에서 653, 다른 범위 1개, 다루는 곳으로만 걸리던 문서 1개. FOREMAN 원고는 다루는 곳의 파일을 근거 표시로도 거의 다 가리켜 카드 수는 거의 그대로다. 새 판 653은 코드로 걸린 451과 문서로만 걸린 202
- **서기실 셈은 다루는 곳을 계속 읽는다**(판단): FOREMAN 근거 표시는 파일 단위라 줄 단위 밀림 검사가 없다. 서기실 셈을 근거 표시로 바꾸면 다루는 곳에만 있는 파일(4절의 7개)이 어디서도 밀림으로 안 잡혀 덮기 구멍이 생긴다. 다루는 곳을 그대로 읽고 feat, fix 커밋만 세면 헛걸림은 결정 3의 범위 좁히기로 줄인다. 사용자 뜻 「헛걸림을 줄이고 덮기 구멍을 만들지 않는다」에 맞는 쪽으로 보았다
- **서기실 셈 변화(결정 3)**: 같은 HEAD로 main 판 머리와 이 브랜치 머리를 맞대니 33편 합 41에서 39. `16_tests` 8에서 3, `02_ingest/03_turns` 0에서 2, `14_screen/05_check` 3에서 4(시험만 바꾼 fix 커밋이 그 기능 편으로 간 것). 나머지 30편 같음
- **근거 확인기**: 판정 함수를 check.py에서 가져온다. 동작은 같다(의심 줄 길이 20자 넘음, 다루는 곳 경로가 있나, 글롭). `tests/test_evidence.py` 그대로 통과
- **문서 점검을 FOREMAN에 돌린 결과**: 편 66, 근거 표시 4,264, 덮기 492 가운데 492(이 브랜치 끝, 새 시험 파일 포함). 틀린 것은 못 푸는 참조 넷(`notion/10_scribe/04_notion.md` 「제목」 둘과 「승인 카드」, `notion/14_screen/05_check.md` 「Claude Code 창」. 1단계 log 7절, 게시기가 이미 경고하는 것, 서기 몫)뿐. 의심 235(틀림이 아니다)

## 3. 정할 것 표(`.foreman/docs.toml`)

| 칸 | FOREMAN 기본(지금 FOREMAN 동작) | 인프라 값(지금 인프라 동작) |
|---|---|---|
| `read_commit` | `"piece"` | 전환 동안 `"set"`, 끝나면 줄을 지운다 |
| `allowed_domains` | `[]` | 포트폴리오의 그 도메인 하나(이 저장소가 Public이라 이름은 적지 않는다) |
| `[check] sets` 점검할 묶음 | `["notion", "portfolio"]` | `["notion", "portfolio", "docs"]` |
| `[check] numbered_only` 바로 아래 `NN_*.md`만 | `[]` | `["docs", "portfolio"]` |
| `[check] head_at` 머리 주석 자리 | `"first"` 울타리 밖 첫 주석 | `"top"` 빈 줄 뒤 맨 앞 주석만 |
| `[check] fenced` 울타리 안 근거, 참조, 금지어 | `false` | `true` |
| `[check] kinds` 근거 종류 | 다섯 종류 | `["c", "docs", "code"]`(`t`, `log` 막음) |
| `[check] xref` 묶음 건너 참조 | `{}` 같은 묶음 | `{ docs = "notion" }` |
| `[check] files_at` 파일이 있는지 보는 판 | `"worktree"` | `"read"` 읽은 커밋 |
| `[check] claim` 의심 줄 꼴 | 근거 확인기 꼴(숫자, 둥근 따옴표, 네 글자 넘는 "…", 두 글자 넘는 「…」) | 숫자와 둥근 따옴표만 |
| `[check] claim_min` 의심 줄 가장 짧은 글자 수 | `21`(근거 확인기 「20자 넘음」) | `0` |
| `[check] banned` 금지어를 보는 묶음 | `[]`(FOREMAN은 저장소 전체를 `tests/test_public_secret_shapes.py`가 본다) | `["notion", "portfolio"]` |
| `[check] domains_in` `allowed_domains`를 받는 묶음 | `["portfolio"]` | 같음 |
| `[check] cover_by` 덮기에 세는 묶음 | `["notion"]` | 같음 |

- 덮기 대상은 두 저장소 모두 「문서 묶음 폴더와 기록 폴더 밖 추적 파일」이다. 판은 `read_commit = "set"`이고 `files_at = "read"`면 원고 묶음의 읽은 커밋 트리(인프라 지금), 아니면 작업 트리 색인이나 `--rev`
- 칸마다 틀린 값은 기본값으로 떨어지지 않고 `DocsConfigError`(명령 종료 코드 2). 모르는 칸은 경고(시험 `tests/test_docs_check.py`)
- 그림 파일은 두 저장소 모두 점검한 모든 묶음에서 본다(인프라는 포트폴리오만 봤다. 지금 인프라 원고에 그림이 없어 결과는 같다)
- 작업 트리 점검은 아직 `git add` 하지 않은 새 편도 본다(인프라 스크립트가 파일로 보던 것과 같다. 커밋 전에 돌리는 점검이라)

## 4. 근거가 없는 파일 수(결정 6)

「다루는 곳」(원고 묶음)에는 있는데 어떤 근거 표시(docs, 원고, 포트폴리오의 `[code:]`와 `[docs:]`)도 가리키지 않는 파일. 이런 파일은 바뀌어도 거꾸로 찾기에 걸리지 않는다(서기실 셈은 FOREMAN에서 잡는다).

| 저장소 | 다루는 곳 파일 | 근거 표시가 가리키는 파일 | 근거 표시가 없는 파일 | 폴더 근거 표시(`[code:tests/]` 같은 것)를 빼고 셀 때 |
|---|---|---|---|---|
| FOREMAN(이 브랜치) | 499 | 497 | **7** | 248 |
| 인프라(`56718c8` 사본, 읽기만) | 112 | 132 | **0** | 7 |

FOREMAN 7개: `.claude/settings.json`(05_roles/02_guards), `.gitignore`, `bridge/__init__.py`, `bridge/api/__init__.py`, `bridge/db/__init__.py`(01_structure), `bridge/doctext/__init__.py`, `bridge/doctext/repo.py`(10_scribe/03_evidence, 04_notion). FOREMAN은 폴더 근거 표시가 많아 248개는 폴더 표시로만 가리켜진다(바뀌면 걸리지만 그 폴더 문장이 걸린다). 스크립트는 scratchpad에만.

## 5. 인프라 맞대기(읽기만, scratchpad 사본)

- 사본 `56718c8`에 아래 6절 docs.toml을 커밋하지 않고 둠
- **점검, 깨끗한 상태**: 옛 `docs-check.py -v`와 `tools/docs.py --repo <사본> check -v` 모두 틀린 것 0, 의심 2줄(docs/02_nodes.md:7, docs/03_kubernetes.md:7) 같음, 근거 표시 2,020+379와 2,399 같음, 덮기 111/111 같음
- **점검, 틀린 것을 넣은 사본**(근거 파일 없음, 줄 범위 넘침, `[t:]`, 참조 없음, IP, 울타리 안 근거와 참조, 다루는 곳 없음, 그림 없음, 남의 도메인, 머리 없는 새 편): 옛 13, 새 12. 같은 틀림을 같은 줄에서 잡는다. 다른 것 하나는 값 끝 `#절`(`[code:cluster/Vagrantfile#절]`)로 인프라는 「모양을 알아보지 못했다」, FOREMAN은 받는다(1단계부터 FOREMAN 근거 확인기와 게시기가 받던 꼴. 인프라 원고에 이 꼴은 0). 글 끝 말투는 「~다」에서 「~습니다」로
- **읽은 커밋이 갈릴 때**(`set`): 둘 다 「읽은 커밋이 하나가 아닙니다」. 옛 스크립트는 거기서 멈추고 FOREMAN은 그 줄을 알린 뒤 나머지 규칙을 작업 트리 판으로 계속 본다
- **전환 뒤(`read_commit` 줄을 지운 piece)**: 지금 인프라 원고 그대로 틀린 것 0. 56편 머리가 이미 저장소에 있는 커밋을 하나씩 가지고 있어 머리를 고치지 않아도 된다
- **껍데기**: 아래 6절 세 파일을 사본에 넣고 `FOREMAN_DIR`로 이 worktree를 주어 돌렸다. 점검은 옛 스크립트와 같은 결과(틀린 것 0, 의심 2, 종료 코드 0). 환경 변수가 없거나 틀린 폴더면 종료 코드 2와 「FOREMAN 문서 도구를 찾지 못했습니다. FOREMAN_DIR=<FOREMAN 저장소 폴더>로 주거나 CLAUDE.md의 기본 경로를 맞추십시오」. `--self-test`와 틀린 범위도 2
- **거꾸로 찾기, 인프라 커밋 150개**(커밋 하나씩, 옛 `docs_for_code.py --json`과 껍데기): 146개 같음, 4개 다름. 다른 것은 모두 옛 쪽에만 있는 문서 9개이고 9개 모두 다루는 곳으로만 걸렸다(결정 1로 바뀌는 차이). 새 쪽에만 있는 문서 0. 예: `1111853`, `736d833`에서 `notion/14_operations.md`가 CLAUDE.md 변경으로 다루는 곳만으로 걸리던 것이 빠진다(사용자가 말한 헛걸림). 새 판 합은 코드로 170, 문서로만 90
- 끝난 뒤 인프라 저장소 `git status --short` 0줄

## 6. 인프라에 넘길 것(인프라 세션 몫, 이 세션은 인프라를 고치지 않았다)

들어내는 차례는 메모리 「저장소 둘 도구 바꾸는 순서」대로 그 세션 지시서가 끝난 뒤.

1. `.foreman/docs.toml`(2단계 값 + 이번 칸)

```toml
# 문서 규칙(FOREMAN 문서 도구가 읽는다, tools/docs.py). 없는 칸은 FOREMAN 기본값
records = ["docs/history/"]     # 기록 폴더. 문서도 아니고 걸게 하지도 않는다
pair_numbers = true             # docs/NN_*.md가 바뀌면 같은 번호 원고 notion/NN_*도 건다
read_commit = "set"             # 전환 동안만. 끝나면 이 줄을 지운다(FOREMAN 기본 "piece", 편마다)
allowed_domains = ["<포트폴리오에서 받는 도메인>"]

[sets]
notion = "notion/"

[check]
sets = ["notion", "portfolio", "docs"]
numbered_only = ["docs", "portfolio"]
head_at = "top"
fenced = true
kinds = ["c", "docs", "code"]
xref = { docs = "notion" }
files_at = "read"
claim = '\d|“|”'
claim_min = 0
banned = ["notion", "portfolio"]
cover_by = ["notion"]
```

2. 껍데기 세 파일. FOREMAN을 찾는 법(사용자): 환경 변수 `FOREMAN_DIR`가 먼저, 없으면 인프라 CLAUDE.md에 적은 기본 경로(아래 `DEFAULT`에 같은 값), 둘 다 못 찾으면 종료 코드 2와 한 줄 안내. `|| true`로 덮지 않는다. 변수 이름은 2단계 log 껍데기와 같은 `FOREMAN_DIR`로 정했다

`scripts/foreman_tool.py`
```python
"""FOREMAN 문서 도구를 찾아 부른다(2026-11-17 문서 도구 합치기 3단계). scripts/docs-check.py, scripts/docs_for_code.py가 쓴다.

FOREMAN을 찾는 차례
  1. 환경 변수 FOREMAN_DIR
  2. 아래 DEFAULT(이 저장소 CLAUDE.md에 적은 기본 경로와 같은 값)
둘 다 못 찾으면 조용히 넘어가지 않고 종료 코드 2로 끝나며 설정하는 법을 한 줄로 보인다. 부르는 쪽도 || true로 덮지 않는다.
"""
import os
import sys
from pathlib import Path

DEFAULT = None    # 인프라 세션이 CLAUDE.md에 적은 FOREMAN 경로와 같은 값을 넣는다
VAR = "FOREMAN_DIR"


def find() -> Path:
    for where, v in ((f"환경 변수 {VAR}", os.environ.get(VAR)), ("CLAUDE.md 기본 경로", DEFAULT)):
        if v and Path(v, "tools", "docs.py").is_file() and Path(v, ".venv", "bin", "python").is_file():
            return Path(v)
        if v:
            print(f"FOREMAN을 찾지 못했습니다: {where} {v}에 tools/docs.py나 .venv가 없습니다", file=sys.stderr)
    print(f"FOREMAN 문서 도구를 찾지 못했습니다. {VAR}=<FOREMAN 저장소 폴더>로 주거나 CLAUDE.md의 기본 경로를 맞추십시오"
          f"(예: export {VAR}=<FOREMAN 저장소 폴더>)", file=sys.stderr)
    sys.exit(2)


def run(cmd: str, args: list[str]) -> None:
    """FOREMAN `tools/docs.py --repo <이 저장소> <cmd> <args>`로 바꿔 탄다. 종료 코드는 그 명령 것 그대로다."""
    fm = find()
    here = Path(__file__).resolve().parent.parent
    py = fm / ".venv" / "bin" / "python"
    os.execv(py, [str(py), str(fm / "tools" / "docs.py"), "--repo", str(here), cmd, *args])
```

`scripts/docs-check.py`
```python
#!/usr/bin/env python3
"""문서 점검은 FOREMAN 문서 도구로 옮겼다(2026-11-17 문서 도구 합치기 3단계). 이 파일은 그 명령을 부르는 껍데기다.

    FOREMAN_DIR=<FOREMAN 저장소> python3 scripts/docs-check.py [-v]

규칙은 FOREMAN bridge/doctext/check.py, 이 저장소만의 값은 .foreman/docs.toml [check].
틀린 것이 있으면 1, FOREMAN을 못 찾거나 도구가 실패하면 2로 끝난다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_tool import run  # noqa: E402

run("check", sys.argv[1:])
```

`scripts/docs_for_code.py`
```python
#!/usr/bin/env python3
"""거꾸로 찾기는 FOREMAN 문서 도구로 옮겼다(2026-11-17 문서 도구 합치기 2, 3단계). 이 파일은 그 명령을 부르는 껍데기다.

    FOREMAN_DIR=<FOREMAN 저장소> python3 scripts/docs_for_code.py --range main...HEAD --unfixed

인자는 옛 것과 같다(파일, --range, --rev, --unfixed, --brief, --json). 이 저장소만의 값은 .foreman/docs.toml.
3단계부터 머리 주석 「다루는 곳」은 읽지 않는다(덮기 검사 몫). FOREMAN을 못 찾거나 도구가 실패하면 2로 끝난다.
옛 --self-test 장면은 FOREMAN 시험 tests/test_docrefs_config.py로 옮겼다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from foreman_tool import run  # noqa: E402

if "--self-test" in sys.argv[1:]:
    print("자기 점검은 FOREMAN 시험 tests/test_docrefs_config.py로 옮겼습니다", file=sys.stderr)
    sys.exit(2)
run("refs", sys.argv[1:])
```

3. 읽은 커밋을 편마다로 바꾸는 순서
   1. 위 docs.toml(`read_commit = "set"`)과 껍데기를 넣고, 껍데기 점검이 옛 스크립트와 같은지(틀린 것 0, 의심 2) 본다
   2. `read_commit` 줄을 지운다. 지금 56편 머리 값이 모두 저장소에 있는 커밋이라 머리는 고치지 않아도 점검이 통과한다(5절)
   3. 그 뒤로 편 하나를 다시 읽고 고칠 때만 그 편의 읽은 커밋을 올린다. 44편을 한 번에 올리지 않는다(「실제로 열어 본 커밋」 뜻)
   4. 지금 44편이 가진 `736d833`은 한 편만 확인하고 통째로 올린 값이다(2단계 log 7절 사용자 답). 그 값을 그대로 둘지, 실제로 연 커밋으로 되돌릴지는 사람이 정할 것(아래 7절)
4. 인프라 원고에서 「덮는 곳」과 근거로 나눠 적을 곳
   - 14편(`notion/14_operations.md`)은 이미 사용자가 말한 모양(14편이 CLAUDE.md를 덮고 06, 10, 11편은 근거로)이다. 결정 1 뒤로는 14편 머리를 고치지 않아도 CLAUDE.md가 바뀔 때 다루는 곳만으로는 걸리지 않는다(5절 `1111853`, `736d833`)
   - 14편 49줄 「근거 표시나 머리 주석의 다루는 곳으로 그 코드를 가리키는 글과 줄을 찾고」, 같은 줄의 `[code:scripts/docs_for_code.py:2]`, `[code:scripts/docs_for_code.py:38-39]`는 껍데기로 바꾸면 낡는다(근거 줄 번호가 옛 스크립트 줄). 껍데기를 넣는 인프라 코더가 같은 브랜치에서 고칠 것
   - 원고 둘 이상이 같은 파일을 덮는 곳이 67파일(대부분 부모 편과 아래 편, 예 `notion/12_monitoring.md`와 `12_monitoring/01_metrics.md`). 결정 1 뒤로는 겹쳐 덮어도 헛걸리지 않아 꼭 고칠 것은 아니다. 덮기는 「어느 편이든 하나」만 요구한다
5. 인프라 CLAUDE.md에 FOREMAN 기본 경로와 `FOREMAN_DIR` 한 줄(인프라 세션이 그 저장소 규칙으로)

## 7. 사람이 정할 것

1. 인프라 44편의 `736d833`(한 편만 확인하고 통째로 올린 값)을 그대로 둘지, 다시 연 커밋으로 되돌릴지. 점검은 어느 쪽이든 통과한다
2. 문서 점검을 어디에 걸지. 지금은 손으로 부르는 명령뿐이라 아무도 안 돌리면 조용히 낡는다(CLAUDE.md 맨 위 「스스로 알리는가」). 후보: 합치기 카드에 `check` 틀린 수 한 줄, 서기 브랜치 근거 확인과 함께, pytest에 FOREMAN 자체 점검. pytest에 걸면 지금 못 푸는 참조 넷이 먼저 풀려야 한다(서기 몫)
   - 11-17 사용자 결정: 지금은 합치기 카드 한 줄, 못 푸는 참조 넷이 풀린 뒤 pytest에 FOREMAN 자체 점검을 건다(카드 한 줄은 보이게만 할 뿐 아무도 안 보면 조용히 낡는다, 깨지게 만드는 것은 시험뿐). 카드 한 줄은 `log/foreman-4_docs_check_card_20261117.md`
   - FOREMAN 걸리는 문서가 654에서 653으로 거의 그대로인 것은 근거 표시가 파일 단위이기 때문이다(지시 22에서 줄 번호를 붙이지 않기로 한 결과, 지금 바꾸지 않음). 「3단계를 했는데 왜 FOREMAN은 그대로냐」는 물음의 답이다
3. FOREMAN 원고 못 푸는 참조 넷을 서기 일감으로 낼지(1단계부터 남은 것)
4. FOREMAN 「근거 표시가 없는 파일」 7개에 근거 표시를 달지(`__init__.py`, `.gitignore`는 달 문장이 없어 그대로 두는 것이 맞아 보인다. `bridge/doctext/repo.py`, `.claude/settings.json`은 원고에 한 문장 쓸 만하다)

## 8. 고친 문서와 남은 걸림

- 고침: CLAUDE.md(거꾸로 찾기 명령 이름 한 곳), `docs/operations.md`(50줄 명령 이름, 카드 수 두 줄, 문서 점검 명령 줄 새로), `docs/11_worktree.md` 「6-1.」(카드 `by`, 두 줄, 나눈 까닭, 설정 경고)과 「9.」(도구 이름, 출력, 문서 트리거, 가리킴에서 다루는 곳 뺌, 「다루는 곳은 읽지 않는다」 항목, 한계 문장), `docs/12_scribe.md`(머리 주석 뜻, 문서 문법 묶음 `[check]`, 명령, 문서 점검 항목, 근거 확인기 줄, 코더 줄), `docs/10_office_design.md`(카드 수 두 줄), 원고 `notion/01_structure.md`(모듈 표 doctext 줄), `06_sessions.md`, `07_merge.md`, `07_merge/01_card.md`(다루는 곳에서 `tools/docrefs.py` 뺌, 가리키는 꼴 셋, 다루는 곳을 보지 않는 까닭 새 문단, 카드 두 줄, 설정 경고, 줄 번호 한계, 관리자 카드 글), `10_scribe.md`, `10_scribe/03_evidence.md`(점검과 한 함수, 다루는 곳 뜻 새 문단, 인프라 점검을 옮긴 문단, 다루는 곳에 새 시험), `16_tests.md`(시험 수를 지금 수로, 이 편이 맡는 것), 포트폴리오 `portfolio/07_merge.md`(카드 두 줄). 원고와 포트폴리오 머리 「읽은 커밋」은 바꾸지 않았다
- `docs/operations.md`, `docs/style_guide.md`는 사람 승인 문서인데 operations와 CLAUDE.md를 고쳐 합치기 카드가 사람에게 간다
- 걸렸지만 지금 코드와 맞아 그대로 둔 것(`tools/docs.py refs --range main...HEAD --unfixed`): `notion/14_screen.md`, `notion/09_dispatcher.md`, `docs/11_foreman_dispatch.md`, `docs/roles.md`, `notion/15_db/01_tables.md`, `docs/11_handoff_v2.md`, `docs/style_guide.md`, `portfolio/06_handoff.md`, `portfolio/08_foreman_plan.md`, `docs/14_dispatcher_note_wake.md`. 모두 같은 파일(`bridge/foreman.py`, `bridge/mergeprep.py`, `handoff.js`, `tests/`)의 다른 기능 문단이다
- 이 브랜치 끝의 거꾸로 찾기 결과는 「코드로 걸린 문서 37, 안 고침 10 / 문서로만 걸린 문서 14, 안 고침 9」. 문서로만 걸린 9개(`notion/00_foreman.md`, `05_roles.md`, `08_handoff.md`, `01_structure/02_startup.md`, `04_approval/02_flow.md`, `portfolio/01_pixel_office.md`, `02_overhead.md`, `10_scribe_room.md`, `11_postit.md`)는 이 브랜치가 고친 CLAUDE.md, `docs/12_scribe.md`, `docs/operations.md`, `docs/10_office_design.md`를 다른 주제로 파일 단위로 가리키는 편이라 그대로 두었다. 결정 8이 따로 보이려던 성격이 이 브랜치에서 바로 나왔다

## 9. 시험

- 바꾸기 전 기준: 2단계 log의 1296(main `79b0023`). 바꾼 뒤 `.venv/bin/python -m pytest -q` **1323 통과**(경고 1, 전부터 있던 것), `node --test tests/js/` **226 통과**
- 새 시험 `tests/test_docs_check.py` 20: FOREMAN 꼴 깨끗한 것과 틀린 것(규칙 1~7 모두, 울타리 안은 안 봄), 아직 add 안 한 새 편, 의심 줄(짧은 줄, 참조 안 숫자 뺌), 인프라 꼴(설정 읽기, 깨끗한 것, 종류 막기, 금지어와 받는 도메인, 읽은 커밋 판 파일, 울타리 안, 읽은 커밋 묶음, 머리 주석 맨 앞), `head_at`, 틀린 `[check]` 값 9가지, 모르는 칸 경고, 명령 종료 코드 0, 1, 2, 읽기만
- 새 시험 `tests/test_mergeprep.py` `test_card_notes_branch_changed_docs_config`(결정 9), `tests/test_docrefs.py` `test_card_docs_code_first`, js `걸리는 문서: 코드로 걸린 것과 문서로만 걸린 것을 나눠 보이고, 설정을 바꾼 브랜치는 경고`
- 고친 시험: `test_docrefs.py`, `test_docrefs_config.py`(다루는 곳으로 걸던 장면은 이제 안 걸림, 옛 껍데기 맞대기는 `tools/docs.py refs` 인자 시험으로), `test_coder_docs_rule.py`(명령 이름), `test_mergeprep.py`(카드 줄), `test_doctext.py`(docrefs가 머리 주석을 읽지 않음, 근거 확인기가 check.py 함수를 씀)
- 맞대기 스크립트(`cmp_refs.py`, `cmp_infra_refs.py`, `scribe_count.py`, `nomark.py`, `multicover.py`, `cov.py`, `testmap.py`)는 scratchpad에만 두었다

### rebase 뒤(관리자 410, 11-17)

합치기 카드가 `notion/16_tests.md` 시험 수 줄 충돌로 멈춰, main `3bda826`(534 서기방 마지막 게시) 위로 rebase했다. 그 줄은 rebase 뒤 실제로 센 수로 풀었다. pytest 104파일 **1,329 통과**, node 40파일 **226 통과**.
- 534가 더한 `tests/test_docsync_last.py`가 문서 점검에서 덮기 밖으로 잡혔다. 16편이 `tests/`를 통째로 덮지 않게 된 뒤라 새 시험 파일은 그 기능 편에 넣어야 한다(점검이 바로 알린 것). 같은 기능의 `test_docsync.py`를 덮는 `notion/10_scribe/04_notion.md` 다루는 곳에 넣었다. 덮기 493 가운데 493
- `tools/docs.py refs --range main...HEAD` 결과는 rebase 전과 같다(코드로 걸린 문서 37, 안 고침 10 / 문서로만 걸린 문서 14, 안 고침 9). 534 코드(`bridge/docsync.py`, `scribe.js`)는 카드 나누기와 이 브랜치가 고친 문단을 바꾸지 않았다
- 못 푸는 참조 「제목」 하나는 534가 `04_notion.md`를 고쳐 275줄에서 277줄로 밀렸을 뿐 같은 것이다

## 10. 겹침

같은 시각 코더 534가 `bridge/docsync.py`, `bridge/static/js/scribe.js`를 고친다. 이 브랜치는 그 두 파일을 건드리지 않았다. `bridge/static/js/handoff.js`(카드)는 이 브랜치가 고쳤다.

## 11. 규칙

규칙 위반 없음. 저장소 파일과 scratchpad 사본의 파일은 모두 Edit, Write로 만들고 고쳤다(`>` 리디렉션, `sed -i`, `python -c`로 파일을 고치지 않았다). push와 브리지 다시 띄우기는 하지 않았다. 다른 저장소는 읽기만 했다(사본은 scratchpad).

일감 글자와 다르게 판단한 것 둘을 적는다.
- 카드 툴팁 첫 줄 넷(제목이 「코드로 걸린 문서」, 「문서로만 걸린 문서」, 「문서 설정」, 옛 카드 「걸리는 문서」)에서 제목과 설명 사이에 줄표를 썼다. 일감은 화면 글에 줄표를 새로 쓰지 말라고 했지만, `docs/style_guide.md` 4-1이 툴팁 첫 줄의 제목과 설명 사이 줄표만은 예외로 둔다(`tip.js`가 이 기호로 제목을 자른다). 빼면 툴팁 제목이 갈리지 않아 그 예외를 따랐다. 관리자가 다르게 보면 그 넷만 바꾸면 된다
- 읽기만 하는 확인 하나(시험 파일과 원고 편 짝 세기)를 Bash에서 heredoc으로 넘긴 파이썬으로 돌렸다. 파일을 쓰지 않았다(1단계 log와 같은 꼴). 그 뒤로는 scratchpad 스크립트 파일로 돌렸다
- 서브에이전트 하나(sonnet)에 결정 3의 원고 머리 고치기를 맡겼다. 같은 기준(Edit만, 읽은 커밋과 본문은 그대로, 줄표 금지)을 넘겼고, 끝난 뒤 바뀐 줄이 모두 「다루는 곳」 줄인지 직접 다시 봤다. 서브에이전트는 끝났다
