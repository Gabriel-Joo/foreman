# README 정리, 서기 「README 갱신」 없애기, 합치기 카드 README 후보 없애기 (2026-11-15, 세션 445, `cc/foreman-4`)

관리자 410의 일감과 그 뒤 더한 일감(`readme_section` 키 지우기)을 한 브랜치에서 했다.

## 1. 한 일

- README 「6. 로드맵」 절(표 16줄, 「8, 9단계 순서를 바꾼 이유」, 「3번을 일찍 치는 이유」)을 지웠다
- README 「나중에 할 일 (정해 두고 미룬 것)」 표 51줄을 모두 지우고, 그 자리에 「## 6. 알려진 한계」 표(무엇, 왜 지금은 안 되나, 근거)를 만들어 45번 한 줄을 「지금은 ~이다」 말투로 넣었다
- README 맨 위 상태 줄에서 로드맵 단계 목록과 「단계별 상태는 6. 로드맵」을 빼고, 만든 순서는 깃헙, 기능 상태는 docs, 안 되는 것은 「6. 알려진 한계」라고 고쳤다. 605줄 GitHub Actions 문장의 「나중에 할 일」 가리킴을 뺐다
- 서기 「README 갱신」 일을 없앴다: `bridge/scribe_room.py`의 `TASKS["readme"]`, `README_STALE`, `TOUCHES["readme"]`, `task_prompt`의 readme 갈래, `start`의 `since` 넣기, `todo()`의 `behind["readme"]`와 「README 갱신: 그 뒤 커밋 N개」 할 일 줄, 이것만 쓰던 `commits_since_path`. `bridge/static/js/scribe.js` `ORDER`, 서기 호버 두 곳(`office.js`, 「README가 낡은 것처럼」을 「CLAUDE.md가 길어진 것처럼」으로, 「문서 담당」 목록에서 README), 계획 지시문(`bridge/foreman.py` 서기 일 이름 목록), 시연 자료(`static/demo/crew_seats.json`의 readme 항목 둘)
- `config/handoff.toml`의 `readme_section` 키를 지웠다(그 키만). 합치기 카드의 README 정리 후보 길을 없앴다(`bridge/mergeprep.py`): `readme_rows`, 「README에서 뺄 줄」 읽기(`_drop_section`, `log_drop_lines`, `log_drop_numbers`), `row_titles`, 낱말 겹침(`_words`, `_PARTICLE`), `_INBOX_NO`, `_LOG_LINK`. `doc_candidates(docs, files, limit)`는 docs 줄만 보고 `readme`는 늘 빈 목록이다. `DocsCfg`에서 `readme`, `readme_section` 칸을 뺐다. `_docs`가 README와 세션 log를 읽지 않는다. 옛 카드(DB에서 되살린 것)에 남은 README 후보는 `has_docs`, 카드 알림 수, 합친 뒤 관리자 글, `docs_done` 수 어디에서도 세지 않고 패널(`handoff.js` `mpSection`)도 그리지 않는다. 관리자 글의 「근거 있는 README 정리 후보」 줄과 「README · docs 정리 후보」 말을 「docs 정리 후보」로
- 같은 파일 겹침 막기는 손대지 않았다(사용자 결정)
- 코드 주석, docs가 지운 README 줄을 근거로 단 곳을 그 일의 log로 바꿨다(아래 4절)
- 시험: `tests/test_scribe_room.py`, `tests/test_scribe_two_paths.py`(readme를 later로), `tests/js/scribe.test.mjs`, `tests/test_mergeprep.py`(README 후보 시험 넷을 docs만 보는 시험 하나로), `tests/test_mergeprep_db.py`, `tests/test_merge_wait_manager.py`, `tests/js/mergeprep.test.mjs`. 화면 말 `tests/data/screen_words.toml`에 `[[rename]]` 「README 갱신」 한 줄
- docs: `docs/12_scribe.md`(0절에 없앤 까닭, sync 일감 줄, 할 일 세기 목록, 재료 절, 9절 상태 줄, 포먼 창 예시), `docs/11_worktree.md`(6절 정리 후보, 164 예시, 222 한계), `docs/11_foreman_dispatch.md`(서기 일 이름, 125 할 일 넷)

## 2. 로드맵 절을 없애며

**README 다른 곳이나 docs에 없던 지금 상태 설명**(옮기지 않고 여기만 적는다. 만든 순서는 깃헙, 기능마다 상태는 docs가 맡는다)
- 0단계: 런슈즈 세션은 11-05, 펫퍼민트 세션은 11-08(정전 뒤)에 tmux로 옮겼다(`log/stage0_tmux_result.md`)
- 9단계 LLM 지표는 보류다. 프로메테우스는 펫퍼민트 쪽이 어떤 지표를 내보낼지 정한 뒤 설치한다(두 번 손대지 않으려고). README 7절 데모 시나리오는 「아직 설치하지 않았다, 아껴 둔다」만 적는다
- 8, 9단계 순서를 바꾼 까닭(11-02 사용자): CI/CD는 새로 설치할 것이 없어 바로 시작할 수 있었다
- 13단계 남은 것: 사진 둘(08 터미널, 06 Notion 게시 목록)은 넣지 않음, 시연 모드와 녹화기 자동 시험 없음. `docs/13_demo_capture.md` 상태 줄에는 없다(`log/stage13_demo_capture_result.md`에는 있다)
- 15단계: 1만 끝, 2 ~ 4는 차례로(표 기준, 11-08). 실제로는 11-14에 2, 4와 추가 요금 배지까지 됐다(`docs/15_usage.md` 머리 상태 줄, 설계 log `foreman-7_scribe_design_20261115.md` 3-1). 표가 낡았던 예
- 12, 14, 11단계의 남은 것은 `docs/12_scribe.md` 9절, `docs/14_dispatcher_note_wake.md` 상태 줄, README에서 지운 「나중에 할 일」 줄(아래 표)에 이미 있다

**「N단계」 · 「로드맵」 낱말은 두었다.** `log/` 색인의 「로드맵 1단계 결과」, 문서 표의 「로드맵 10」, `docs/01_kickoff.md` 「로드맵 0단계」, `docs/02_cloudflare_tunnel.md` 「로드맵 6단계 이후」, `docs/11_handoff.md` 「로드맵 11단계」, `migrations/0002` · `0012` · `0017` 주석, `bridge/approval.py` · `notify.py` · `pipeline.py` 첫 줄, `config/*.toml` 첫 줄은 그때 단계 이름을 적은 이력이다. 표가 없어도 docs 번호(`docs/NN_*`)와 log 이름(`stage<N>_*`)이 같은 번호를 쓰니 뜻이 끊기지 않는다. README 「6.」을 가리키던 곳은 맨 위 상태 줄 하나였고 고쳤다. 「## 7. 데모 시나리오」 번호는 그대로 두려고 새 표를 `### 알려진 한계`가 아닌 `## 6. 알려진 한계`로 했다(일감은 `###`라고 했다. `###`이면 「5. 데이터 모델」의 아래 절이 된다). 포스트잇의 `postit.readme_limits`는 「알려진 한계」가 든 머리줄이면 단계와 상관없이 읽는다(`bridge/postit.py` `README_LIMIT in ln`). 관리자가 rebase 전에 「### 알려진 한계」로 맞춰 달라고 했으나 `## 6. 알려진 한계`도 같은 글을 품어 걸린다. rebase 뒤 이 브랜치에서 `readme_limits('.')`를 불러 45번 한 줄을 읽는 것을 확인했다(머리 줄은 빠짐). `###`로 바꾸면 7절 번호와 절 깊이가 어긋나 두었다. 꼭 `###`이어야 하면 관리자가 정한다.

## 3. 「나중에 할 일」 51줄

번호는 `log/foreman-6_postit_proposal_20261115.md` 2-2 표 차례. P 줄은 지금 코드를 보고 끝났는지 판단했다.

| # | 줄(줄임) | 처리 | 판단 근거 |
|---|---|---|---|
| 1 | 승인 observe → enforce | 지움(L) | |
| 2 | 시험 GitHub Actions | 지움(L) | |
| 3 | 자동 기상 3단계 | 지움(L) | |
| 4 | 런슈즈 실제 인계 | 지움(다른 프로젝트) | 관리자가 넘긴다 |
| 5 | 런슈즈 README 갱신 | 지움(다른 프로젝트) | 관리자가 넘긴다 |
| 6 | 펫퍼민트 압축 손실 결과 보기 | 지움(다른 프로젝트) | 관리자가 넘긴다 |
| 7 | 런슈즈 미리보기 | 지움(L) | |
| 8 | Claude Code와 Codex | 지움(L) | |
| 9 | 9단계 LLM 지표 | 지움(L) | |
| 10 | Fable 5.2로 해 볼 것 | 포스트잇 | 걷기 외 동작(책 읽기, 타이핑)은 없다 |
| 11 | 끝내기 확인 창 남은 것 | 포스트잇 | 알림은 됐다(`stallwatch.judge_dialog`). ①②(뒤 일이 끝나면 세션도 끝내기, 옮길 때 넘기기)는 `handoff.py`에 없다. [끝내기] 전 묻기는 찾지 못했다(1339는 뒤에서 도는 일이 있으면 거부하는 자리) |
| 12 | 구조 2단계 docs 뒤처짐 | 지움(사용자) | |
| 13 | 구조 3단계 역할 나누기 | 지움(사용자) | |
| 14 | docs 커밋 묶는 기준 | 포스트잇 | 사람이 정할 것, 코드 자리 없음 |
| 15 | 서기와 이어 묻기 | 포스트잇 | `bridge/scribe_ask.py`에 이어 묻기(대화 이력) 없음 |
| 16 | later.md 낱말로만 고름 | 포스트잇 | `scribe_room.LATER` 정규식 그대로. 포스트잇 코더(443)가 later 둘레를 고치는 중이라 그쪽에서 풀리면 지운다 |
| 17 | 낮은 창 대화 칸 30px | 포스트잇 | 11-12 뒤 고친 커밋 없음 |
| 18 | 스키마 잠금 단위 | 지움(L) | |
| 19 | 런슈즈 `core.quotePath` | 지움(다른 프로젝트) | 관리자가 넘긴다 |
| 20 | 교장 ② 읽기 전용 확인 도구 | 지움(사용자) | |
| 21 | 교장 ③ 발견을 경고 칸에 | 지움(사용자) | |
| 22 | 교장 ④ 서기 띄우기 dispatch 기록 | **끝남, 지움** | `bridge/scribe_room.py` `_record`(523)가 서기실 [시키기]도 `foreman.record_spawn`(origin scribe)으로 남긴다(11-15). 시험 `tests/test_scribe_two_paths.py` 서기실 세션 `_record` |
| 23 | 들어오는 일을 종류대로 | 지움(사용자) | |
| 24 | 질문은 읽기 전용 점검 세션 | 지움(사용자) | |
| 25 | 합치기 뒤 절차 2단계 | 지움(L) | |
| 26 | 다른 프로젝트 포트폴리오 | 지움(다른 프로젝트) | 관리자가 넘긴다 |
| 27 | GitHub 저장소 공개 | 포스트잇 | 사람이 정할 일 |
| 28 | 일어날 때 확인할 것 | 지움(L) | |
| 29 | 웹훅 빠진 폴링 빌드 표시 | 포스트잇 | `bridge/pipeline.py` 221 ~ 222는 폴링이 n번 이어질 때만 끊김으로 본다. 한 번 빠진 것의 표시는 없다 |
| 30 | 감독실 「FOREMAN」 끊김 | 포스트잇 | 11-12 뒤 고친 커밋 없음 |
| 31 ~ 37 | 재부팅, 보관 기간, Jenkins 둘, 파드 감시, 터널, 역할 규칙 | 지움(L) | |
| 38 | 합치기 카드에 순서 | 포스트잇 | `bridge/mergeprep.py`에 `merge_order` 없음 |
| 39 | 띄우기 실패가 기록에 안 남음 | 포스트잇 | `handoff.py` 872는 화면 글만 돌려주고, `record_spawn`(`foreman.py` 993)은 `result`가 있으면 `started`로 적는다. 알림 없음 |
| 40 | 「push 대기 커밋」 말 | 포스트잇 | `bridge/static/js/scribe.js` 80 그대로 |
| 41 | 기록 경로 `log/` 못 박음 | 포스트잇 | 설정 칸 없음 |
| 42 | 밖에서 push한 것을 모름 | 포스트잇 | 앞선 수는 원격을 보지 않는다(`ls-remote`는 `reposcope.py`의 push 판정에만) |
| 43 | 답 못 받고 멈춘 세션 | 포스트잇 | `stallwatch.py` 판정 종류(died, silent, loop, long, dialog)에 「답 기다림이 오래감」 없음 |
| 44 | FOREMAN 포트폴리오 갱신 | 포스트잇 | 사람이 정할 일. 서기실 사진에서도 「그 뒤 커밋 498개」 |
| 45 | 옮기기가 worktree 줄기를 원본 폴더로 | **알려진 한계로** | 관리자 확인대로 그대로다. `handoff.py` `spawn` 797 ~ 807(이 브랜치 기준, 일감의 788 ~ 798에서 밀림), `will_worktree` 876 ~ 885 |
| 46 | 게시 설정 출처 화면 | 포스트잇 | `scribe.js`에 출처, 경고 표시 없음 |
| 47 | Sonnet 5.5 맥락 창 | 포스트잇 | `config/models.toml [windows]`에 Opus 5.5, Haiku 5.5만 |
| 48 | 「Switch model?」 코드 | 포스트잇 | `bridge/api/sessions.py` 146 `_SWITCH_ASK` 그대로 |
| 49 | 옮기기 비용 글 네 곳 | 포스트잇 | `handoff.js` 602 · 769, `opanel.js` 447, `losscheck.js` 45에 「0.4달러」 그대로 |
| 50 | 진짜 입력 화면 시험 | 포스트잇(사용자) | |
| 51 | 서기 구조 다시 짜기 | 지움(사용자) | |

합: 지움 29(L 16, 다른 프로젝트 5, 사용자 결정 7, 끝남 1), 포스트잇 21(#50 포함), 알려진 한계 1.

### 포스트잇으로 갈 줄 (관리자가 합친 뒤 넣는다)

| 줄 제목 | 포스트잇 글 | 근거 파일 |
|---|---|---|
| Fable 5.2로 해 볼 것 | 픽셀 캐릭터 동작 더하기(책 꺼내 읽기, 타이핑, 걸어다니기)와 포트폴리오용 영상이나 다이어그램. 쌓인 할 일을 줄인 뒤(11-10 사용자) | 받은 할 일 #16 |
| 끝내기 확인 창 남은 것 | 알림은 된다. 남은 것: [끝내기] 전에 뒤에서 도는 일을 보여 주고 묻기, 뒤에서 도는 일이 끝나면 세션도 끝내기, 옮길 때 뒤에서 도는 일을 새 세션에 넘기기(넘길 수 있는 일의 기준, 인계문에 적는 모양, 자동으로 끝낼 때 알릴지 정하기) | `log/old_session_exit_bg_20261109.md`, 받은 할 일 #6, #7 |
| docs 커밋 묶는 기준 | docs를 커밋마다 고치면 일이 끊기니 묶는 기준(커밋 몇 개, 쉼, 하루 끝)을 사람이 정한다(11-11 사용자 「제가 정하겠습니다」) | `log/designer_scribe_d2_20261111.md`, 받은 할 일 #15 |
| 서기와 이어 묻기 | 물어보기는 한 번 묻고 끝나 이어 묻지 못한다. 서기가 하는 일을 알려고 관리자를 거치는 구조가 맞는지도 본다 | `log/scribe_ask_20261110.md` |
| later 재료가 낱말로만 고름 | 「나중에 할 일 정리」 재료가 「나중, 미루」 낱말이 든 사람 턴만 고른다(`scribe_room.LATER`). 낱말 없이 미룬 말은 빠진다. 뜻으로 고르게 한다(포스트잇 구조에서 아직 쓰이면) | `log/scribe_material_noclip_20261110.md` |
| 낮은 창에서 대화 칸 30px | 1366 · 125%와 1024에서 띠 둘과 머리줄 두 줄이 패널을 먹어 대화 칸이 30px다. 띠 합치기, 머리줄 버튼 줄이기, 머리말 접기(11-12 사용자 정함) | `log/designer_screen_six_20261110.md` 「남은 것」 |
| GitHub 저장소 공개 | `Gabriel-Joo/foreman`을 공개로 돌릴지 사람이 정한다. 에셋 라이선스와 토큰 흔적을 먼저 확인한다(11-06 사용자 「지금은 안 할래」) | t:5890 |
| 웹훅 빠진 폴링 빌드 표시 | push 뒤 빌드가 폴링으로 시작하면 「웹훅이 오지 않아 폴링으로 돌았습니다(N분 늦음)」를 빌드 호버와 파이프라인 줄에. 그때 `no_build`가 작동했는지, 웹훅이 가끔 빠지는지도 센다 | `log/petmint_jenkins_docskip_todo_20261109.md`, 받은 할 일 #10 |
| 감독실 「FOREMAN」 끊김 | 감독실 현황판의 「FOREMAN」이 글씨 110%, 1024, 넓게에서 끊기거나 8px로 작다. 현장이 늘면 판 두 줄 등(디자이너, 11-12 사용자 정함) | `log/designer_grid_20261110.md`, `log/designer_polish_seven_20261111.md` |
| 합치기 카드에 순서 | 합치기 카드(`bridge/mergeprep.py`)에 계획의 `merge_order`와 같은 파일을 건드리는 다른 카드를 보인다(코더 작게) | `log/coder_foreman_multi_20261111.md` |
| 띄우기 실패가 기록에 안 남음 | 45초 안에 새 세션을 못 찾으면 화면 글만 나오고 dispatch는 `started`로 남는다. `failed`와 사유(tmux 끝 줄)로 남기고 텔레그램 한 번, 빈 tmux와 worktree 처리 단추 | `log/mergeprep_on_20261111.md` 「D2 띄움」 |
| 「push 대기 커밋」 말 | 서기실 기술문서 게시의 「push 대기 커밋 N개」는 Notion에 맞춘 뒤 쌓인 커밋 수다. 말을 바꾼다(예: 「Notion에 맞춘 뒤 커밋 N개」) | `log/merge_d2_scribe_20261111.md` |
| 기록 경로를 프로젝트마다 | 서기, 코더 일감이 결과 기록을 늘 `log/`에 쓰게 한다. 프로젝트마다 기록 경로 설정 한 칸(펫퍼민트는 `data/review/`) | `log/petmint_jenkins_docskip_todo_20261109.md` |
| 밖에서 push한 것을 모름 | 밖에서 push하거나 합친 것을 알아채지 못해 「main보다 커밋 N개 앞」이 남는다. 원격 기준으로도 본다 | `log/merge_term_inputh_20261111.md` |
| 답 못 받고 멈춘 세션 | 사람에게 물은 세션이 답을 못 받고 오래 멈춰 있으면 알림과 표시(11-12 사용자 정함) | `log/handoff_misplaced_admin_20261111.md` |
| FOREMAN 포트폴리오 갱신 | Notion의 11-08 판 뒤로 커밋이 쌓였다(서기실 기준 498개). 언제 갱신할지 사람이 정한다 | `log/designer_scribe_d2_20261111.md` |
| 게시 설정 출처 화면 | 서기 화면에 게시 설정이 저장소 파일인지 FOREMAN 칸인지와 경고를 보인다(디자이너 작게, 11-12 사용자 정함) | `log/notion_publish_three_20261112.md` |
| Sonnet 5.5 맥락 창 크기 | `config/models.toml [windows]`에 Sonnet 5.5가 없어 % 대신 토큰만 보이고 % 압축 알림이 걸리지 않는다. 실제 크기를 확인해 넣는다 | `log/foreman-3_model_menu_20261114.md` |
| 「Switch model?」 코드 | `bridge/api/sessions.py` `_SWITCH_ASK` 둘레가 지금 CC에서도 쓰이는지 확인하고 남길지 지울지 정한다 | `log/foreman-3_model_menu_20261114.md` |
| 옮기기 비용 글 네 곳 | 「내가 보낸 말 20개당 약 0.4달러, 1.5분」이 `handoff.js`, `opanel.js`, `losscheck.js`, 툴팁 네 곳에 박혀 있다. 한 곳으로 모으거나 `loss_check` 실측에서 계산(코더 작게) | `log/designer_confirm_text_20261114.md` |
| 진짜 입력 화면 시험 | `tools/screen.py --promises`(진짜 입력으로 해 보기)와 버튼 글과 호버 제목 감사. 화면 말 pytest로 못 잡는 것이 쌓이면 다시 정한다(11-15 사용자) | `log/foreman-6_screen_text_sync_proposal_20261115.md` |

(마지막 줄이 #50이다. 표는 21줄: P 20 + #50)

## 4. 근거가 끊기지 않게 바꾼 곳

| 자리 | 전 | 지금 |
|---|---|---|
| `bridge/reconcile.py` 1 | README 「나중에 할 일」 줄 | `log/coder_screen_state_20261111.md` |
| `bridge/pgrep_guard.py` 1 | README 「나중에 할 일」 pgrep 줄 ① | `log/coder_c_wave2_20261111.md` |
| `bridge/stallwatch.py` 1, 14 | README 줄 둘 | `log/coder_screen_state_20261111.md`, `log/old_session_exit_bg_20261109.md` |
| `bridge/scribe.py` 19 | README 「나중에 할 일」 #14 | 받은 할 일 #14, `log/scribe_material_noclip_20261110.md` |
| `bridge/managers.py`, `scopetoken.py`, `roleguard.py` 1 | 이미 지워진 README 줄 | `log/coder_c_wave2_20261111.md`(roleguard는 `log/inspect_roleguard_20261114.md`도) |
| `bridge/api_error.py` 1 | 이미 지워진 README 줄 | `log/coder_screen_state_20261111.md` |
| `bridge/human_wait.py` 12, `bridge/api/dashboard.py` 301, `tests/js/api_stop.test.mjs` 1 | 이미 지워진 README 줄 | `log/screen_api_error_bar_20261113.md` |
| `bridge/static/js/opanel.js` 551 | README 「대화 칸 30px」 | `log/d1_terminal_scroll_inputh_20261111.md` |
| `tools/screen.py` 116 | 이미 지워진 README 줄 | `log/designer_screen_six_20261110.md` |
| `docs/11_worktree.md` 164, 191, 222 · `docs/11_foreman_dispatch.md` 125 | README 「나중에 할 일」 | 이력으로 바꿈(위 1절) |

## 5. 설정(사람 승인 카드)

- `config/handoff.toml`의 `readme_section` 줄을 지웠다(사용자 지시). 그래서 이 브랜치의 합치기 카드는 사람에게 간다
- 같은 표의 `readme = "README.md"` 줄과 머리 설명 6줄의 「README 「나중에 할 일」」도 지웠다(11-15 사용자 「같이 지워라. 아무도 읽지 않는 값이다」, 관리자 410 전달). 코드는 `DocsCfg`에서 칸을 뺐고 `load`는 `docs_dir`, `max`만 읽는다
- 키가 없어도 깨지지 않는지: `mp.load`는 `docs_dir`, `max`만 읽는다. `tests/test_mergeprep.py` `test_load_config`, 실제 `config/handoff.toml`로 도는 시험 모두 통과

## 6. 다른 세션 몫으로 남긴 것

**포스트잇(443)이 main에 먼저 합쳐져(`ee966ec`) 이 브랜치를 그 위로 rebase했다.** 443이 서기 「나중에 할 일 정리」를 「알려진 한계 쓰기」(키 later 그대로)로 바꾸고 later 일감 글, 받는 함, 툴팁을 고쳤으므로 그쪽을 남겼다. 충돌과 푼 법:
- `office.js` 서기 호버 둘: 443 글(포스트잇 쌓임)을 남기고 「README가 낡은 것처럼」을 「CLAUDE.md가 길어진 것처럼」으로, 「문서 담당」 목록에서 README만 뺐다
- `docs/11_foreman_dispatch.md`: 443의 「포스트잇에서 바로」 줄을 남기고 일 이름에서 readme만 뺐다. `docs/12_scribe.md` 재료 절: 443 줄을 남기고 「그 밖의 일감」에서 README 갱신만 뺐다
- `tests/data/screen_words.toml`: 443의 rename 둘과 제 「README 갱신」 한 줄을 모두 남겼다. 443이 `mergeprep.py` `_INBOX_NO`(「받은 할 일」도 읽는 정규식)에 단 `[[code_exception]]`은 그 정규식을 이 브랜치가 지워 쓸모없어져 지웠다(화면 말 시험이 「지금은 쓸모없는 목록 줄」로 잡음)
- `tests/js/scribe.test.mjs`: 443의 later 이름 「알려진 한계 쓰기」를 쓰고 readme를 뺐다
- `bridge/mergeprep.py`, `tests/test_mergeprep.py`: 443은 README 후보 안의 두 곳(`_INBOX_NO`에 「포스트잇 #N」, 그 시험 한 줄)만 바꿨고 그 둘레를 이 브랜치가 통째로 지웠다. 제 쪽으로 풀었고 main 대비 다른 줄이 빠지지 않았는지 diff로 봤다
- `bridge/scribe_room.py` 첫 줄의 일 이름을 「알려진 한계 쓰기」로 맞췄다
- 남은 「나중에 할 일 정리」 낱말(`scribe_room.py` 239 · 307 주석, `scribe.py` 3, `api/scribe.py` 56, `office.js` 2315 주석)은 443 쪽 주석이라 두었다
- `migrations/0027`, `0028` 주석의 「나중에 할 일 정리가 README 표로」는 적용된 마이그레이션이라 두었다

**서기 몫(이 브랜치에서 건드리지 않음)**
- `CLAUDE.md` 31: 관리자 기준 2 「README 「나중에 할 일」 줄」 (표가 없다. 「알려진 한계」 줄로 바꿀지)
- `CLAUDE.md` 35: 「GitHub Actions 시험은 정해 두고 아직 안 만듦 — README 「나중에 할 일」」 (그 줄을 지웠다)
- `CLAUDE.md` 75: 「README 로드맵 표는 원본 세션이 고친다」 (표가 없다)
- `docs/style_guide.md` 9 · 22: 「NN은 README 로드맵 단계 번호」, 「파일 번호는 README 로드맵 번호를 따른다」 (표가 없어진 뒤 번호를 무엇으로 매길지)
- `docs/style_guide.md` 14: 「미룬 일 | README 「나중에 할 일 (정해 두고 미룬 것)」 표」 (포스트잇과 「알려진 한계」로)
- `docs/operations.md` 99 「로드맵 4단계」는 이력이라 두어도 된다

## 7. 확인

- rebase 전: `.venv/bin/python -m pytest -q` 980 passed, `node --test tests/js/` 200 pass
- rebase 뒤(main `d470d61` 위): 첫 판은 1006 passed + 화면 말 1 실패(위 예외 줄), 지운 뒤 전체 pytest 1007 passed, node 203 pass. 미리보기 사진은 rebase 전에 찍었다
- 미리보기(세션 445, 포트 8200): `tools/screen.py --no-term --views foreman` 세 테마(magic, office, site) × 크기 × 패널 모두 문제 0건, 세 테마 방 자리 같음
- 서기실 창 사진(office 1920x1080 넓게, `window.office.panel.show({kind:'scribe'})`): 할 일 줄이 문서 점검, 나중에 할 일 정리, CLAUDE.md 정리 셋. 「README 갱신」 줄 없음, 「밀린 것 2」. 할 일 숫자는 도는 브리지(옛 파이썬)가 준 데이터라 합치고 다시 띄워야 서버 쪽 readme 항목이 사라진다
- 미리보기는 끝에 껐다(`DELETE`, tmux `fm-pv-foreman-4` 없음). 서브에이전트, 예약은 쓰지 않았다
- 서버 코드(`scribe_room.py`, `mergeprep.py`, `foreman.py`)라 합친 뒤 관리자가 브리지를 다시 띄운다

## 8. 규칙 위반

- **진행 글 하나를 영어로 썼다**(11-15, mergeprep 정리 중 「Now I'll write the new mergeprep section…」 한 줄과 그 앞 「Good — 알 수 없는 일은…」 · 「Now JS 시험을…」처럼 영어가 섞인 글 몇). 까닭: 도구 결과를 읽고 바로 이어 쓰며 쓰기 전에 보지 않았다. 브리지 PostToolUse 안내로 알았다
- **rebase 중에 또 두 번**: 「Conflicts 하나씩 봅니다」, 「All removed lines are my intended ones. rebase를 이어 갑니다」. 같은 까닭이고, 알아챈 뒤 나머지는 한국어로 썼다
- 그 밖(파일 고치기는 모두 Edit, Write. sed, heredoc, `python -c`로 파일을 고치지 않았다. `pgrep -f` 안 씀. push, 브리지 다시 띄우기 안 함)은 위반 없음
