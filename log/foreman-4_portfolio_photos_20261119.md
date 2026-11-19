# 포트폴리오 사진을 지금 화면에 맞춤 (디자이너, 세션 573, 2026-11-19)

**낡음 21장 / 55장** (맞음 34, 모름 0). 21장 모두 다시 찍어 200KB 아래로 줄였다(PNG 19, GIF 2).

- 맞대 본 화면: 지금 도는 브리지(main 코드) `http://127.0.0.1:8000`. 브리지는 다시 띄우지 않았다
- 옛 사진 55장은 모두 11-15 19:19(`2a00175`) 사진이고, `10_scribe_room_publish.png`만 11-17(`35171b8`)이다. 그 뒤 화면 변경은 `git log 2a00175..HEAD -- bridge/static/` 17커밋
- 판정 기준: 화면 코드가 바뀌어 사진 속 그림이나 단추, 글이 지금과 다르면 낡음. 수(포스트잇 장 수, 금액 등)만 다른 것은 맞음으로 셌다(실제 화면 사진은 찍은 때 수다)
- 기준 열: 다시 찍은 사진에 적용한 사용자 찍는 법(11-19 관리자가 전한 고친 두 줄). T=테마(생김새는 마법학교, 캐릭터·자리는 지금 테마, 세 테마 편만 셋), F=채우기(화면 전체는 꽉 차게, 부분은 가까이)

## 1. 판정 표

| 사진 | 판정 | 무엇이 다른가 | 다시 찍은 기준 |
|---|---|---|---|
| 00_overview_screen.png | 낡음 | FOREMAN 방 아래 출하 라인 세 칸(봉인실·봉인 문양·보물창고·전송 아치)이 지금은 「봉인실 없음」(`9ac4527`) | T 마법학교, F 전체 꽉(1920×830) |
| 00_overview_map.png | 낡음 | 지도의 FOREMAN 방 그림에 출하 라인, 아래 빈 바닥이 넓음 | T 마법학교, F 전체 꽉(1920×760) |
| 01_pixel_office_three_themes.png | 낡음 | 세 테마 모두 FOREMAN 방에 출하 라인과 배송 담당 | T 셋(세 테마 편), F 방만 가까이, FOREMAN 방(11-19 사용자 결정) |
| 01_pixel_office_role_colors.png | 맞음 | 위 두 줄 방만 잘라 출하 라인이 안 찍힘 | |
| 01_pixel_office_state_looks.png | 낡음 | 아래에 커밋 데스크·배포 파이프·빌드 모니터·저장소가 걸림 | T 오피스 그대로(캐릭터 상태), F 라운지·워크스테이션·문서팀 줄만 2배 |
| 01_pixel_office_zone_tip.png | 맞음 | | |
| 01_pixel_office_walk.gif | 낡음 | 오피스 FOREMAN 방 아래 출하 라인과 배포 담당 | T 오피스 그대로(걷는 길), F 위 두 줄 방 |
| 01_pixel_office_summon.gif | 낡음 | 같음 | T 오피스 그대로, F 위 두 줄 방 |
| 02_overhead_manager.png | 맞음 | 위 두 줄만 잘림 | |
| 02_overhead_report.png | 맞음 | | |
| 02_overhead_api_error.png | 맞음 | 인프라 방(원래 출하 라인 없음) | |
| 02_overhead_denied.png | 낡음 | 아래에 봉인실·봉인 문양·보물창고·전송 아치 이름표 | T 마법학교, F 위 두 줄 방 2배 |
| 02_overhead_seats.png | 맞음 | 런슈즈 방(출하 라인 있음, 그대로) | |
| 02_overhead_map.png | 낡음 | 지도의 FOREMAN 방 그림에 출하 라인, 아래 빈 바닥 | T 마법학교, F 전체 꽉(1920×760) |
| 02_overhead_refresh.png | 맞음 | 띠 글 그대로(`store.js`) | |
| 02_overhead_ingest.png | 맞음 | | |
| 03_pipeline_line.gif | 맞음 | 성공 장면이라 Harbor 칸 규칙이 바뀌어도 ✓ 그대로 | |
| 03_pipeline_real.png | 맞음 | | |
| 03_pipeline_fail.png | 낡음 | Test 단계 실패인데 저장소 칸이 ✓. 지금은 push 앞 실패면 저장소 칸을 ✓로 그리지 않는다(`shipstate.js`, `9ac4527`) | T 오피스 그대로(편 안 다른 사진과 같게), F 방 전체 |
| 03_pipeline_hq_fail.png | 맞음 | | |
| 03_pipeline_no_build.png | 맞음 | | |
| 04_session_panel_convo.png | 낡음 | 왼쪽 FOREMAN 방에 출하 라인 | T 마법학교, F 넓은 패널 2560×690(방 꽉) |
| 04_session_panel_activity.png | 맞음 | 패널만 | |
| 04_session_panel_input.png | 낡음 | FOREMAN 방에 출하 라인, 아래 빈 바닥 | T 마법학교, F 전체 꽉 |
| 05_approval_card.png | 낡음 | FOREMAN 방에 출하 라인, 아래 빈 바닥 | T 마법학교, F 전체 꽉 |
| 05_approval_flow.gif | 맞음 | 위쪽 방과 패널만 | |
| 06_handoff_choose.png | 맞음 | 같은 장면을 지금 찍어 맞댐 | |
| 06_handoff_fail.png | 맞음 | 같음 | |
| 06_handoff_none.png | 맞음 | 같음 | |
| 06_handoff_summary.png | 맞음 | 같음 | |
| 07_merge_wait.png | 맞음 | 위 두 줄만 | |
| 07_merge_coder.png | 맞음 | 런슈즈 방 · 코더 창 그대로 | |
| 08_foreman_plan_card.png | 맞음 | | |
| 08_foreman_plan_card_more.png | 맞음 | | |
| 08_foreman_plan_hq.png | 맞음 | | |
| 08_foreman_plan_overlap.png | 맞음 | | |
| 08_foreman_plan_panel.png | 낡음 | FOREMAN 방에 출하 라인 | T 마법학교, F 전체 꽉 |
| 08_foreman_plan_wake.png | 맞음 | | |
| 09_new_session_window.png | 맞음 | 지금 창과 맞댐 | |
| 09_new_session_role_model.png | 맞음 | | |
| 10_scribe_room.png | 낡음 | 서기실 창: 「기술문서 쓰기」 까닭 줄, 「열려 있는 일」, 기술문서 게시 줄과 덮기 자리가 바뀜(`5a5031e`, `054783b`). 방 아래 출하 라인 | T 마법학교, F 전체 꽉 |
| 10_scribe_room_panel.png | 낡음 | 같은 창, 「포트폴리오 쓰기」 줄 꼴과 글 목록 표시가 바뀜(`5adb03a`) | 패널만 1.5배 |
| 10_scribe_room_publish.png | 낡음 | 게시 머리줄(「바뀜」 칸 빠짐), 접은 칸 | 패널만 1.5배 |
| 11_postit.png | 낡음 | 포스트잇이 받은 편지함과 TODO 창이 됨: [x] [→] 대신 [TODO로] [한계로], 「아직 안 보낸 것」 「할 일」 묶음(`da5ceba`) | 종이만 1.5배 |
| 11_postit_closed.png | 낡음 | 같음, 「30일 넘은 것」 묶음 생김 | 종이만 1.5배 |
| 11_postit_coder.png | 낡음 | 같음, [띄우기] 자리 | 종이만 1.5배 |
| 12_session_screen.png | 맞음 | | |
| 13_shell_bar.png | 맞음 | (11-17 foreman-7 확인과 같다) | |
| 14_usage_cards.png | 낡음 | 한도 카드 값이 「+ 모름」을 붙이는 꼴, Fable 가격 비움(`afcad6b`) | 위 카드 줄만 |
| 14_usage_where.png | 맞음 | | |
| 14_usage_chart.png | 맞음 | | |
| 14_usage_tables.png | 맞음 | | |
| 14_usage_chip.png | 낡음 | 머리 칩 끝이 「Fable 주간 N%」에서 「… 소진 예상」으로 바뀜 | 머리 두 줄만 2배 |
| 15_telegram_suggest.png | 맞음 | | |
| 15_telegram_plan.png | 맞음 | | |

## 2. 다시 찍은 것과 크기

모두 한 번에 찍었다(찍기 일감 한 벌을 스크래치에 두고 헤드리스 크로미움 한 번, `tools/screen.py`의 브라우저·토큰 처리를 그대로 씀). 서기실 셋, 지도 둘은 첫 찍기에서 창이 아직 읽는 중이거나 지도 위가 잘려 기다림·창 높이만 바꿔 다시 찍었다.

| 사진 | 전 | 후 | 크기, 줄인 법 |
|---|---|---|---|
| 01_pixel_office_three_themes.png | 756KB | 115KB | 3392×720, 256색 |
| 01_pixel_office_state_looks.png | 58KB | 47KB | 1760×460 PNG |
| 01_pixel_office_walk.gif | 392KB | 191KB | 560폭, 초당 5장, 80색 |
| 01_pixel_office_summon.gif | 543KB | 181KB | 560폭, 초당 5장, 96색 |
| 02_overhead_denied.png | 152KB | 128KB | 2016×924 PNG |
| 02_overhead_map.png | 168KB | 192KB | 1920×760 PNG |
| 03_pipeline_fail.png | 77KB | 94KB | 1152×700 PNG |
| 00_overview_screen.png | 201KB | 169KB | 1920×830 PNG |
| 00_overview_map.png | 206KB | 72KB | 1920×760, 256색 |
| 04_session_panel_convo.png | 343KB | 98KB | 2560×690, 256색 |
| 04_session_panel_input.png | 167KB | 169KB | 1920×830 PNG |
| 05_approval_card.png | 174KB | 176KB | 1920×830 PNG |
| 08_foreman_plan_panel.png | 349KB | 123KB | 1920×830, 256색 |
| 10_scribe_room.png | 260KB | 95KB | 1920×830, 256색 |
| 10_scribe_room_panel.png | 266KB | 101KB | 1152×2132, 256색 |
| 10_scribe_room_publish.png | 257KB | 112KB | 1152×2132, 256색 |
| 11_postit.png | 505KB | 137KB | 864×1374, 256색 |
| 11_postit_closed.png | 469KB | 159KB | 864×1374, 256색 |
| 11_postit_coder.png | 476KB | 137KB | 864×1374, 256색 |
| 14_usage_cards.png | 125KB | 84KB | 1366×480 PNG |
| 14_usage_chip.png | 51KB | 56KB | 1800×144 PNG |

- 줄이는 법: PNG optimize로 200,000바이트 아래면 그대로, 넘으면 256색(중앙 자르기, 디더 없음 — 픽셀 그림과 글씨 가장자리가 남는다), 그래도 넘으면 폭을 0.9배씩. 이번에는 폭을 줄인 사진이 없다. JPEG는 픽셀 그림 가장자리가 번져 쓰지 않았다
- GIF: `tools/screen.py --record <대본> --themes office --sizes 1920x830 --clip 16,91,1120,540 --fps 10 --gif-width 560 --every 2 --colors 96`. 640폭 128색은 253KB·228KB였다. walk는 96색에서 201,340바이트라 같은 프레임을 80색으로 다시 만들었다(196,601바이트)
- 꽉 채우기: 좁은 패널에서 창 높이 830이면 방(2.5배)이 캔버스를 채우고 아래 바깥 띠가 7px만 남는다(900이면 풍경 47px, 1080이면 넓은 풀밭). 지도는 1920×760이 감독실과 방 카드까지 들어가며 가장 꽉 찬다
- 세 테마 사진은 FOREMAN 방, 시연 장면 `still`(같은 순간)을 테마만 바꿔 같은 창 크기·같은 자르기로 찍어 나란히 붙였다(왼쪽부터 현장, 오피스, 마법학교)
- **세 장에서 같게 보이는 것(서기가 캡션에 씀)**: 구역 배치(위 줄 다섯 칸, 가운데 줄 네 칸, 아래 줄 접수대와 「출하 라인 없음」 자리)와 구역 이름표 자리, 왼쪽 위 감독(팀장·소장·교장) 책상, 코더 넷과 서기 하나가 앉은 자리와 발밑 역할 원이 세 장에서 같다. 이름과 그림, 색만 테마마다 다르다
- 03_pipeline_fail은 대본에 실패 장면이 없어 11-15처럼 페이지 안 값만 바꿨다(`pipeline` 대본 끝난 뒤 Jenkins `failed`, step `Test`, `broke: jenkins`). 대본 파일은 그대로
- 02_overhead_denied는 `crew_seats` 대본에서 세션 하나에 `denied` 값을 넣어 띄웠다(11-15 캡션과 같은 방식). 런슈즈 방이 아니라 FOREMAN 방
- 04_session_panel_convo는 끝난 디자이너 세션 555(서기실 화면 거리 다섯)의 [대화] 탭이다 — 실제 화면
- 열어 보고 비밀값, 토큰, 서버 경로, 다른 프로젝트 글이 없음을 확인했다. 실제 화면 사진에 보이는 다른 프로젝트 것은 머리줄 현장 탭 이름(런슈즈·펫퍼민트·인프라)뿐이다. 포스트잇 한 줄에 `Gabriel-Joo/foreman`(이 저장소 이름)이 보인다

## 3. 찍는 법 적기

- `docs/style_guide.md` 「3.」 화면 사진 줄 바로 아래에 「FOREMAN 찍는 법」(테마, 채우기, 한 번에, 크기와 줄이는 법, 낡지 않은 큰 사진)을 `(11-19 사용자)`로 적었다. 테마·채우기 두 줄은 관리자가 전한 고친 말 그대로다
- 2차에 테마 줄을 「모든 사진은 마법학교, 테마 셋을 함께 보여 주는 사진만 예외(테마마다 한 장씩 따로)」로 바꾸고, 다른 프로젝트 방을 찍지 않는다는 줄을 더했다. GIF 줄에 움직이는 곳만 자르기와 바뀐 곳만 담기를 더했고, 「낡지 않은 큰 사진은 줄이지 않는다」 줄은 이번에 모두 줄였으므로 뺐다
- 서기 포트폴리오 지시문(`bridge/scribe_room.py` `task_prompt` portfolio)은 공통 머리(`COMMON`, 513줄)에서 `docs/style_guide.md`를 읽게 하므로 새 줄이 닿는다
- 지시문에 따로 적힌 옛 사진 말(코드는 고치지 않음):
  - 584줄 예시 `--sizes 1920x1080` — 이 크기면 아래 풀밭이 넓게 남는다(새 약속은 1920×830)
  - 586줄 「사진은 … 한 장에 1MB 안쪽」 — 새 약속 200KB와 다르다
  - 585줄 「GIF 하나 3MB, WebM 하나 4MB 안쪽」 — 200KB와 다르다
  - 테마 말이 없다(예시만 `--themes magic`)
- `bridge/manuscript_rules.py`에는 사진 말이 없다(원고 기준 한 벌만)
- 디자이너 지시문에는 사진 찍는 법을 따로 적은 곳을 찾지 못했다

## 4. 시험

- `.venv/bin/python -m pytest -q`: 1461 통과, 실패 0
- `tools/docs.py check`: 틀린 것 0(의심 242, 요약 못 찾은 문서 2는 이번 일과 상관없는 알림)

## 5. 규칙

- 스크래치 폴더의 찍기 일감 JSON(`final.json`) 하나를 Bash heredoc 속 python으로 고쳤다(서기실 셋의 기다림 초를 늘림, 16:2x). 일감의 「heredoc, `python -c`로 파일 고치기 금지」에 걸린다. 저장소 파일이 아니고 바로 다음부터 Edit으로 고쳤다
- 그 밖의 규칙 위반 없음. 브리지 다시 띄우기, push 하지 않음. 포트폴리오 글은 2차 일감이 허락한 01편 사진 줄만 고쳤다
- 3차, 4차, 5차에 새로 어긴 것 없음(스크래치 스크립트 고치기는 모두 Edit. 5차 DB는 읽기만)
- 2차 중 01편 사진 줄을 나누며 설명 글의 「왼쪽부터」를 한 번 「위부터」로 바꿨다가 바로 되돌렸다(설명 글은 서기 몫). 커밋에는 들어가지 않았다

## 6. 2차(같은 날, 관리자 410이 전한 사용자 지시 넷)

사용자가 카드를 미루고 이 브랜치에서 이어서 고치게 했다. 1차의 「캐릭터·자리 사진은 지금 테마 그대로」는 거둬졌다.

1. **테마를 모두 마법학교로**: 오피스·현장으로 찍힌 것을 모두 다시 찍었다 — 01편 넷(`zone_tip`, `state_looks`, `walk`, `summon`), 02 `report`·`refresh`, 03편 다섯(`fail`, `hq_fail`, `line`, `no_build`, `real`), 07 `merge_coder`(런슈즈 방이 오피스 지도에 걸려 있었다), 13 `shell_bar`(바닥 풀밭), 15편 둘. 1차에서 다시 찍지 않은 34장을 모두 열어 보았고, 나머지는 마법학교이거나 방이 안 보이는 패널·창이다(아래 7절 표)
2. **세 테마 사진을 세 장으로**: `01_pixel_office_theme_site.png`, `_office.png`, `_magic.png`(각 1120×720, 같은 순간·창 크기·자르기). 옛 `01_pixel_office_three_themes.png`는 지웠다. `portfolio/01_pixel_office.md` 11줄 사진 줄을 셋으로 나눴다. 설명 글은 마지막 줄(마법학교)에 그대로 두고 앞 둘은 `![현장 테마]`, `![오피스 테마]`만 달았다. 설명 글의 「왼쪽부터」는 서기 몫이라 고치지 않았다
3. **다른 프로젝트 방**: `02_overhead_seats.png`(런슈즈 방), `07_merge_coder.png`(런슈즈 방, 1차에 놓침), `02_overhead_api_error.png`(인프라 방)를 FOREMAN 방으로 다시 찍었다. 대본 파일은 그대로 두고, 찍을 때만 대본 JSON을 읽는 순간 프로젝트 이름을 맞바꿨다(`runshoes`↔`foreman`, `ronanlab-infra`↔`foreman`)
4. **200KB 넘던 넷**: 모두 아래로(`05_approval_flow.gif` 1,054,505 → 197,036, `03_pipeline_line.gif` 474,414 → 189,374, `08_foreman_plan_card_more.png` 308,132 → 119,941, `06_handoff_choose.png` 202,439 → 77,490). 뒤 둘은 테마 없는 창이라 다시 찍지 않고 256색으로만 줄였다

### 마법학교 GIF 줄이기

마법학교는 돌바닥 무늬 탓에 같은 설정에서 오피스보다 두 배쯤 크다(walk 96색 560폭 394KB). 그래서
- 움직이는 곳만 가까이 잘랐다: walk는 작업 책상 → 물약실 → 시약대가 든 660×515, summon은 필사실·원탁방 460×340, approval은 1366×768 창에서 물약실과 패널 996×300, line은 출하 라인 줄 1120×215
- 기존 `tools/frames_to_gif.py`로는 그래도 넘어서, 스크래치 변환(`gifdelta.py`)으로 앞 장과 거의 같은 점(JPEG 잡음, RGB 차 합이 문턱 아래)을 투명으로 두고 바뀐 곳만 담았다. 팔레트는 여러 장에서 한 번 뽑는다. 문턱이 높으면(120) 글씨가 바뀐 곳에 잔상이 남아 approval은 24로 낮췄다
- 결과: walk 440폭·초당 3.3장·80색, summon 460폭·3.3장·80색, line 560폭·5장·96색, approval 720폭·1.7장·80색(카메라가 옮겨 가는 앞 1.5초는 뺐다). approval은 ❗ → 카드 → 「✓ 허용함」 한 줄 세 장면이 남는다
- 이 변환은 저장소 도구에 넣지 않았다(코더 몫, 아래 사람이 정할 것)

#### 변환 재료(코더 일감용, 3차에 덧붙임)

스크래치 `gifdelta.py`(시스템 `python3 -I`, PIL 12.3과 numpy 2.5 — `.venv`에는 PIL이 없다). 입력은 `screen.py --record`가 남긴 `<이름>_frames/`(JPEG 85)

| 옵션 | 기본 | 뜻 |
|---|---|---|
| `--width` | 0(그대로) | 폭. 줄일 때 NEAREST(픽셀 그림이 뭉개지지 않게, `frames_to_gif.py`와 같다) |
| `--every` | 2 | n장마다 한 장. 장 길이는 `1000 / fps × every` ms |
| `--colors` | 96 | 팔레트 색 수. 투명 칸 하나를 그 뒤 번호로 더 쓴다(그래서 최대 255) |
| `--thr` | 40 | 앞 장과 같다고 볼 점의 문턱: 세 채널 차의 합(0~765)이 이 값 아래면 투명 |
| `--fps` | 10 | 녹화한 초당 장수 |

하는 일
1. 팔레트를 한 번만 뽑는다: 장 목록에서 고르게 8장 남짓을 세로로 붙여 MEDIANCUT, 디더 없음. 모든 장을 이 팔레트로 양자화(프레임마다 색이 흔들리면 같은 점이 달라 보여 투명으로 못 바꾼다)
2. 첫 장은 통째로. 다음 장부터 「지금 화면에 보이는 그림」(앞서 투명으로 둔 점은 그 전 값)과 견줘 문턱 아래 점은 투명 칸으로. 견줄 기준을 바로 앞 원본 장이 아니라 보이는 그림으로 두어야 작은 잡음이 장마다 조금씩 쌓여 번지지 않는다
3. 모두 투명인 장은 따로 두지 않고 앞 장 시간에 더한다
4. 저장: `transparency=<투명 칸>`, `disposal=1`(앞 장 위에 그림), `loop=0`, `optimize=False`(PIL optimize가 팔레트를 다시 줄이면 투명 칸 번호가 바뀐다)

문턱 고른 까닭
- JPEG 85 잡음은 같은 점에서 채널 합 10~30쯤 흔들린다. 40이면 잡음은 거의 투명이 되고 캐릭터와 촛불 같은 실제 움직임은 남는다
- 80은 크기가 더 줄지만(walk 2장마다 96색: 40 294,703 → 80 259,086) 마법학교 어두운 바닥 위 회색 캐릭터처럼 대비가 낮은 움직임 가장자리가 덜 그려지기 시작한다. walk·summon은 가까이 본 결과 괜찮아 80을 썼다
- 120은 approval 패널 글씨가 바뀐 곳에 잔상이 남았다(카드가 접힌 뒤 옛 글자가 겹쳐 보임). 글씨가 바뀌는 장면은 24로 낮췄다
- 그러니 도구에 넣으면 기본 40, 글씨가 바뀌는 장면은 낮게, 픽셀 그림만 움직이는 장면은 높게 고를 수 있어야 한다
- 실측(마법학교, 폭과 장수 같음): `frames_to_gif.py`로 walk 480폭 3장마다 96색 245,124 → 이 변환 40 문턱 같은 설정 223,271 수준, 80 문턱과 80색이면 205,250. 촛불처럼 늘 깜빡이는 점이 남는 몫이 크다(바뀐 곳 지도에서 촛불 두 개만 장의 30% 넘게 바뀜)

### 2차 다시 찍은 것과 크기(바이트)

| 사진 | 전 | 후 | 크기, 줄인 법 |
|---|---|---|---|
| 01_pixel_office_theme_magic.png | 새 파일 | 122,440 | 1120×720 PNG |
| 01_pixel_office_theme_office.png | 새 파일 | 86,320 | 1120×720 PNG |
| 01_pixel_office_theme_site.png | 새 파일 | 95,204 | 1120×720 PNG |
| 01_pixel_office_three_themes.png | 115KB | 지움 | |
| 01_pixel_office_zone_tip.png | 47,567 | 44,004 | 시약대 툴팁, 560×280을 2배 |
| 01_pixel_office_state_looks.png | 48,572 | 75,159 | 가운데 줄 방 2배 |
| 01_pixel_office_walk.gif | 196,601 | 180,227 | 위 GIF 절 |
| 01_pixel_office_summon.gif | 186,010 | 186,322 | 위 GIF 절 |
| 02_overhead_api_error.png | 133,025 | 52,161 | FOREMAN 방 위 두 줄 2배, 256색 |
| 02_overhead_report.png | 75,510 | 114,357 | FOREMAN 방 전체 |
| 02_overhead_seats.png | 131,147 | 113,821 | FOREMAN 방 위 두 줄 2배 |
| 02_overhead_refresh.png | 27,625 | 23,908 | 머리줄과 띠 |
| 03_pipeline_fail.png | 96,879 | 124,136 | 런슈즈 방 |
| 03_pipeline_hq_fail.png | 15,293 | 55,533 | 교장실 전체(현황판만 자르던 것을 방째로) |
| 03_pipeline_line.gif | 474,414 | 189,374 | 위 GIF 절 |
| 03_pipeline_no_build.png | 4,141 | 4,520 | 방 머리 띠 2배 |
| 03_pipeline_real.png | 27,589 | 120,774 | 런슈즈 방 전체(실제 화면) |
| 05_approval_flow.gif | 1,054,505 | 197,036 | 위 GIF 절 |
| 06_handoff_choose.png | 202,439 | 77,490 | 다시 찍지 않음, 256색 |
| 07_merge_coder.png | 170,434 | 169,904 | FOREMAN 방과 코더 창 |
| 08_foreman_plan_card_more.png | 308,132 | 119,941 | 다시 찍지 않음, 256색 |
| 13_shell_bar.png | 29,130 | 11,427 | 아래 200px |
| 15_telegram_suggest.png | 31,319 | 57,001 | 교장실 전체, 머리 위 「시작할 일 1」 |
| 15_telegram_plan.png | 62,346 | 69,114 | 실패 이벤트 제안 창 |

- 03_hq_fail, 03_no_build, 15 둘은 대본에 없는 값을 페이지 안에서만 넣었다(Jenkins 실패, `watch: missing`, 교장 `pending` 하나와 그 제안 계획). 15_telegram_plan의 계획 글은 시연용으로 새로 적었다(실패 한 줄, 「런슈즈 빌드 실패 원인 살펴보기」)
- 다시 찍은 사진을 모두 열어 비밀값, 서버 경로가 없음을 확인했다

## 6-1. 3차(같은 날, 관리자 410이 전한 사용자 답)

- `08_foreman_plan_wake.png`(펫퍼민트 Jenkins 503 실제 글)와 `15_telegram_plan.png`(런슈즈 빌드 실패 시연 글)를 FOREMAN 일로 다시 찍었다. 마법학교, `stills` 대본 위에 제안 계획 하나만 페이지 안에서 넣음
  - 08: 「기록 적재 멈춤 — 세션 기록을 12분째 읽지 못했습니다」, FOREMAN, 새로 시작, 「기록 적재가 멈춘 원인 조사」, 버린 계획(옛 캡션의 「버린 계획이다」와 같은 상태). 169,401 → 126,917바이트(1584×1750, 2배)
  - 15: 「브리지 응답 없음 — FOREMAN 브리지가 3분째 하트비트를 보내지 않았습니다」, FOREMAN, 새로 시작, 「브리지 응답 없음 원인 살펴보기」, 시작 기다림. 69,114 → 65,209바이트(792×875)
  - 입력 칸 회색 예시 글(「예: 런슈즈 발볼 검증 이어서 · 펫퍼민트 새로 시작 …」)은 화면 코드에 박힌 안내 글이라 그대로 찍혔다(프로젝트 이름만, 실제 글 아님)
- `docs/style_guide.md`: 57줄 「화면 사진」 줄의 「다른 프로젝트 글」을 「실제 글과 시연 글」로 좁히고, 「FOREMAN 찍는 법」의 다른 프로젝트 줄을 이름은 되고 실제 글·시연 글은 안 된다로 갈랐다. 출하 라인 줄을 더했다. 둘 다 `(11-19 사용자)`
- 03편 「런슈즈 방」 밝히기와 01편 「왼쪽부터」는 서기 몫이라 고치지 않았다
- 남은 것: `15_telegram_suggest.png`는 교장실 현황판에 런슈즈 칸 🔥와 교장 머리 위 「시작할 일 1」이다. 이름만 보이는 화면이라 새 약속에 맞지만, 15편 안에서 「런슈즈 실패가 부른 제안」(suggest)과 「FOREMAN 브리지 제안」(plan)이 이어지지 않는다. 캡션은 서기 몫이고, suggest를 FOREMAN 실패로 바꿀지는 사람이 정한다(FOREMAN 칸을 빨갛게 하는 실패는 출하 라인이 아니라 웹훅이나 적재 쪽이라 값을 따로 넣어야 한다)

## 6-2. 4차(같은 날, 사용자 답 — 걸린 셋을 고치고 57장을 한 번에 다 훑기)

### 15편을 한 사건으로

- 3차의 「브리지 응답 없음」은 실제 기상 종류에 없다(`bridge/wake.py` `KINDS`: 파이프라인 실패, 빌드 알림 없음, 웹훅 끊김 의심, 인프라 응답 없음, 적재 막힘. 브리지가 죽으면 알릴 수도 없다). FOREMAN에 실제로 생기는 것은 「적재 막힘」(`ingest_health.py`가 `foreman`으로 `ingest_stuck`을 부른다)이라 그것 하나로 이었다
- 사건: 세션 `3f2a9c1e`의 기록이 23분째 같은 자리에서 7번 실패(JSONDecodeError)
  - 텔레그램: `ingest_health.py` 글 꼴 「⚠ 적재 막힘 — 세션 3f2a9c1e 23분째 같은 자리에서 실패(7번). 이 세션의 기록이 쌓이지 않는다 …」와 `wake.py` 「🧭 적재 막힘 — 이렇게 살펴보자는 계획을 세웠습니다 …」(사진 없음, 15편 글의 알림 글 꼴은 서기 몫)
  - `15_telegram_suggest.png`: 교장실, 교장 머리 위 「시작할 일 1」, 머리줄 「⚠ 기록 못 읽는 세션 1」(같은 세션). 현황판 FOREMAN 칸은 빨개지지 않는다 — 적재 막힘은 현황판 실패(출하 라인, 웹훅)가 아니라 머리줄 표시다(실제 코드 그대로)
  - `15_telegram_plan.png`: 같은 제안(#9)을 연 창. wake_text는 `wake.py`가 만드는 꼴 그대로 「적재 막힘 — ⚠ 적재 막힘 — 세션 3f2a9c1e …」(앞말이 두 번 붙는 것도 실제 코드대로), 조사·읽기 전용·새로 시작, 「적재 막힘 원인 조사 — 세션 3f2a9c1e」
- `08_foreman_plan_wake.png`도 같은 꼴로 다시 찍었다(세션 `b71d04e2`, 14분 5번, 버린 계획). 3차에 지어 넣은 「기록 적재 멈춤 — 세션 기록을 12분째…」는 실제 글 꼴이 아니었다

### 다시 찍은 것

| 사진 | 걸린 것 | 바꾼 것 | 바이트 |
|---|---|---|---|
| 07_merge_coder.png | 맡길 일 제목 「발볼 검증 화면」(런슈즈 시연 글) | 「포스트잇 창 접힌 칸 기억」 `cc/foreman-2`(페이지 안 `/api/coder/todo`만) | 170,702 |
| 08_foreman_plan_overlap.png | 겹침 띠·대화의 「jenkins-0 Unknown · harbor-jobservice CrashLoopBackOff」(인프라 일) | 983 「코더 — 적재 막힘 조사」, 요청 「ingest_health 적재 막힘 알림이랑 hook_miss.log 늘어난 것도 원인 봐 줘」, 겹친 낱말도 그 넷. 패널만 1.5배 | 71,037 |
| 15_telegram_suggest.png | 런슈즈 빌드 실패로 15편 사건이 갈림 | 위 적재 막힘, 교장실 전체와 머리줄 | 95,076 |
| 15_telegram_plan.png | 3차 「브리지 응답 없음」은 실제에 없는 실패 | 위 적재 막힘 #9 | 72,300 |
| 08_foreman_plan_wake.png | 3차 글이 실제 글 꼴이 아님 | 적재 막힘 #8, 버린 계획, 2배 | 142,197 |
| 00_overview_map.png | 패널 세션 목록에 런슈즈 시연 세션 제목 「카탈로그 정리」 「합친 뒤 배포 확인」 「상품 카드 다듬기」 | 세 제목을 「시연용 세션」으로(방 카드·프로젝트 이름은 그대로) | 74,149 |
| 02_overhead_map.png | 패널 목록에 인프라 시연 세션 제목 「코더 — 백업」 「코더 — 인증서」 | 「코더」로 | 195,446 |
| 14_usage_where.png | 런슈즈 세션의 실제 제목 「RSG 근거 설명문 시험 30켤레」 | 지금 값으로 다시 찍음(런슈즈 줄은 세션 이름 「런슈즈 관리자 (11-17 인수)」뿐) | 78,445 |
| 14_usage_cards.png, _chart, _tables, _chip | 편 안 다섯 장의 찍은 때가 달라 숫자가 안 맞음(카드 11-19 16:10, 표·막대 11-15) | 사용량 화면 한 장(17:15 읽음)에서 넷을 자르고 머리 칩을 바로 이어 찍음(카드 주간 약 40% = 칩 약 40%) | 124,138 / 15,521 / 26,321 / 57,253 |

- 찍을 때만 대본을 바꾸는 칸에 한쪽으로만 바꾸기(`replace`)를 더했다. 맞바꾸기(`swap`)로 「코더 — 백업」↔「코더」를 하자 FOREMAN 세션 「코더 — …」까지 거꾸로 바뀌어 한 번 버리고 다시 찍었다. 또 스크립트 값 순서를 잘못 넣어 패널이 빈 채 한 번 찍혔고 고쳐 다시 찍었다(둘 다 넣기 전에 열어 보고 잡음)
- `07_merge_coder` 머리 띠의 「migrations/ 28개 … 0028_todo_inbox_assignee」는 FOREMAN 저장소의 실제 마이그레이션 이름이다(`migrations/` 34개 가운데 28번) — 걸리지 않음

### 57장 훑기(4차 뒤, 새 약속 전부)

기준: 마법학교(세 테마 사진만 예외) · 출하 라인은 이미지를 만드는 프로젝트 방 · 방 카드와 프로젝트 이름은 됨 · 다른 프로젝트의 실제 글과 시연 글은 안 됨 · 비밀값 · 서버 경로 · 200KB 아래 · 한 편 안의 사진이 한 사건을 따라가는지. 다시 찍은 것과 1~3차에 다시 찍은 것도 모두 한 번 더 열어 보았다.

| 사진 | 걸린 것 | 한 일 |
|---|---|---|
| 00_overview_map.png | 런슈즈 시연 세션 제목 | 4차 다시 찍음 |
| 00_overview_screen.png | 없음(FOREMAN 방, 세션 991 대화) | 없음 |
| 01_pixel_office_role_colors.png | 없음 | 없음 |
| 01_pixel_office_state_looks.png | 없음 | 없음 |
| 01_pixel_office_summon.gif | 없음 | 없음 |
| 01_pixel_office_theme_magic.png | 없음 | 없음 |
| 01_pixel_office_theme_office.png | 없음(세 테마 예외) | 없음 |
| 01_pixel_office_theme_site.png | 없음(세 테마 예외) | 없음 |
| 01_pixel_office_walk.gif | 없음 | 없음 |
| 01_pixel_office_zone_tip.png | 없음 | 없음 |
| 02_overhead_api_error.png | 없음(2차에 FOREMAN 방) | 없음 |
| 02_overhead_denied.png | 없음 | 없음 |
| 02_overhead_ingest.png | 없음(머리줄, 이름만) | 없음 |
| 02_overhead_manager.png | 없음 | 없음 |
| 02_overhead_map.png | 인프라 시연 세션 제목 | 4차 다시 찍음 |
| 02_overhead_refresh.png | 없음 | 없음 |
| 02_overhead_report.png | 없음 | 없음 |
| 02_overhead_seats.png | 없음(2차에 FOREMAN 방) | 없음 |
| 03_pipeline_fail.png | 런슈즈 방(출하 라인 예외). 성공 GIF와 같은 빌드 #68 | 5차에 실제 실패 빌드 #108로 다시 찍음(8절) |
| 03_pipeline_hq_fail.png | 현황판은 이름만. 성공 GIF와 같은 빌드 #68 | 5차에 #108로 다시 찍음(8절) |
| 03_pipeline_line.gif | 런슈즈 방(출하 라인 예외) | 없음 |
| 03_pipeline_no_build.png | 런슈즈 방 머리 띠(출하 라인 예외) | 없음 |
| 03_pipeline_real.png | 런슈즈 방 실제 화면(출하 라인 예외), 글은 이름표뿐 | 없음 |
| 04_session_panel_activity.png | 없음(FOREMAN 세션의 명령과 결과) | 없음 |
| 04_session_panel_convo.png | 없음(FOREMAN 세션 555) | 없음 |
| 04_session_panel_input.png | 없음 | 없음 |
| 05_approval_card.png | 없음(card와 flow가 같은 승인 한 건) | 없음 |
| 05_approval_flow.gif | 없음 | 없음 |
| 06_handoff_choose.png | 없음(FOREMAN 세션 981, 넷은 같은 세션의 갈래) | 없음 |
| 06_handoff_fail.png | 없음 | 없음 |
| 06_handoff_none.png | 없음 | 없음 |
| 06_handoff_summary.png | 없음 | 없음 |
| 07_merge_coder.png | 런슈즈 시연 맡길 일 제목 | 4차 다시 찍음 |
| 07_merge_wait.png | 없음 | 없음 |
| 08_foreman_plan_card.png | 없음(FOREMAN 실제 계획) | 없음 |
| 08_foreman_plan_card_more.png | 없음(FOREMAN 실제 계획) | 없음 |
| 08_foreman_plan_hq.png | 없음(현황판, 이름만) | 없음 |
| 08_foreman_plan_overlap.png | 인프라 일 낱말 | 4차 다시 찍음 |
| 08_foreman_plan_panel.png | 없음(FOREMAN 진행 중인 일) | 없음 |
| 08_foreman_plan_wake.png | 3차 글이 실제 꼴 아님 | 4차 다시 찍음 |
| 09_new_session_role_model.png | 없음(시연 경로 `~/foreman`) | 없음 |
| 09_new_session_window.png | 없음 | 없음 |
| 10_scribe_room.png | 없음(FOREMAN 실제) | 없음 |
| 10_scribe_room_panel.png | 없음 | 없음 |
| 10_scribe_room_publish.png | 없음 | 없음 |
| 11_postit.png | 없음(FOREMAN 포스트잇) | 없음 |
| 11_postit_closed.png | 없음 | 없음 |
| 11_postit_coder.png | 없음 | 없음 |
| 12_session_screen.png | 없음(FOREMAN 세션 477) | 없음 |
| 13_shell_bar.png | 없음 | 없음 |
| 14_usage_cards.png | 편 안 찍은 때가 다름 | 4차 다시 찍음 |
| 14_usage_chart.png | 편 안 찍은 때가 다름 | 4차 다시 찍음 |
| 14_usage_chip.png | 편 안 찍은 때가 다름 | 4차 다시 찍음 |
| 14_usage_tables.png | 편 안 찍은 때가 다름(프로젝트 이름과 환산액은 됨) | 4차 다시 찍음 |
| 14_usage_where.png | 런슈즈 세션의 실제 제목 | 4차 다시 찍음. 남은 「런슈즈 관리자 (11-17 인수)」는 사람이 정할 것 2 |
| 15_telegram_plan.png | 실제에 없는 실패 | 4차 다시 찍음 |
| 15_telegram_suggest.png | 런슈즈 실패로 편 사건이 갈림 | 4차 다시 찍음 |

비밀값·서버 경로: 57장 모두 없음(경로는 시연용 `/demo`, `~/foreman`과 저장소 안 상대 경로뿐). 200,000바이트 넘는 것: 0장(가장 큰 것 `05_approval_flow.gif` 197,036).

## 7. 사진마다 테마(57장, 2차 뒤. 3차·4차에 다시 찍은 것은 테마가 같고 크기만 바뀜 — 크기는 6-2 표)

「다시 찍음」: 1차 = 이 log 1절의 낡음 21장, 2차 = 6절. 「없음」은 픽셀 방이 안 보이는 패널·창·사용량 화면이다.

| 사진 | 테마 | 이번에 다시 찍음 | 크기(바이트) |
|---|---|---|---|
| 00_overview_map.png | 마법학교 | 1차 | 73,828 |
| 00_overview_screen.png | 마법학교 | 1차 | 173,886 |
| 01_pixel_office_role_colors.png | 마법학교 | 아니오 | 164,585 |
| 01_pixel_office_state_looks.png | 마법학교 | 1차, 2차 | 75,159 |
| 01_pixel_office_summon.gif | 마법학교 | 1차, 2차 | 186,322 |
| 01_pixel_office_theme_magic.png | 마법학교(세 테마 사진) | 2차 새 파일 | 122,440 |
| 01_pixel_office_theme_office.png | 오피스(세 테마 사진, 예외) | 2차 새 파일 | 86,320 |
| 01_pixel_office_theme_site.png | 현장(세 테마 사진, 예외) | 2차 새 파일 | 95,204 |
| 01_pixel_office_walk.gif | 마법학교 | 1차, 2차 | 180,227 |
| 01_pixel_office_zone_tip.png | 마법학교 | 2차 | 44,004 |
| 02_overhead_api_error.png | 마법학교 | 2차 | 52,161 |
| 02_overhead_denied.png | 마법학교 | 1차 | 131,909 |
| 02_overhead_ingest.png | 마법학교(머리줄) | 아니오 | 23,203 |
| 02_overhead_manager.png | 마법학교 | 아니오 | 150,488 |
| 02_overhead_map.png | 마법학교 | 1차 | 196,999 |
| 02_overhead_refresh.png | 마법학교(머리줄) | 2차 | 23,908 |
| 02_overhead_report.png | 마법학교 | 2차 | 114,357 |
| 02_overhead_seats.png | 마법학교 | 2차 | 113,821 |
| 03_pipeline_fail.png | 마법학교 | 1차, 2차 | 124,136 |
| 03_pipeline_hq_fail.png | 마법학교 | 2차 | 55,533 |
| 03_pipeline_line.gif | 마법학교 | 2차 | 189,374 |
| 03_pipeline_no_build.png | 마법학교(방 머리 띠) | 2차 | 4,520 |
| 03_pipeline_real.png | 마법학교 | 2차 | 120,774 |
| 04_session_panel_activity.png | 없음(패널) | 아니오 | 113,535 |
| 04_session_panel_convo.png | 마법학교 | 1차 | 101,001 |
| 04_session_panel_input.png | 마법학교 | 1차 | 174,010 |
| 05_approval_card.png | 마법학교 | 1차 | 180,695 |
| 05_approval_flow.gif | 마법학교 | 2차 | 197,036 |
| 06_handoff_choose.png | 없음(패널) | 줄이기만 | 77,490 |
| 06_handoff_fail.png | 없음(패널) | 아니오 | 123,963 |
| 06_handoff_none.png | 없음(패널) | 아니오 | 119,014 |
| 06_handoff_summary.png | 없음(패널) | 아니오 | 140,682 |
| 07_merge_coder.png | 마법학교 | 2차 | 169,904 |
| 07_merge_wait.png | 마법학교 | 아니오 | 154,073 |
| 08_foreman_plan_card.png | 없음(창) | 아니오 | 146,800 |
| 08_foreman_plan_card_more.png | 없음(창) | 줄이기만 | 119,941 |
| 08_foreman_plan_hq.png | 마법학교 | 아니오 | 78,713 |
| 08_foreman_plan_overlap.png | 없음(패널) | 아니오 | 89,130 |
| 08_foreman_plan_panel.png | 마법학교 | 1차 | 126,584 |
| 08_foreman_plan_wake.png | 없음(창) | 3차 | 126,917 |
| 09_new_session_role_model.png | 없음(창) | 아니오 | 63,062 |
| 09_new_session_window.png | 없음(창) | 아니오 | 128,282 |
| 10_scribe_room.png | 마법학교 | 1차 | 97,495 |
| 10_scribe_room_panel.png | 없음(패널) | 1차 | 103,694 |
| 10_scribe_room_publish.png | 없음(패널) | 1차 | 115,138 |
| 11_postit.png | 없음(포스트잇 종이) | 1차 | 140,898 |
| 11_postit_closed.png | 없음(포스트잇 종이) | 1차 | 163,166 |
| 11_postit_coder.png | 없음(포스트잇 종이) | 1차 | 141,100 |
| 12_session_screen.png | 없음(세션 화면 창) | 아니오 | 39,892 |
| 13_shell_bar.png | 마법학교 | 2차 | 11,427 |
| 14_usage_cards.png | 없음(사용량 화면) | 1차 | 86,375 |
| 14_usage_chart.png | 없음(사용량 화면) | 아니오 | 21,838 |
| 14_usage_chip.png | 마법학교(머리줄) | 1차 | 57,743 |
| 14_usage_tables.png | 없음(사용량 화면) | 아니오 | 35,058 |
| 14_usage_where.png | 없음(사용량 화면) | 아니오 | 83,561 |
| 15_telegram_plan.png | 없음(창) | 2차, 3차 | 65,209 |
| 15_telegram_suggest.png | 마법학교 | 2차 | 57,001 |

200,000바이트 넘는 사진: 0장(가장 큰 것 `05_approval_flow.gif` 197,036, `02_overhead_map.png` 196,999).

## 8. 사람이 정할 것

4차 훑기 뒤 판단이 갈리던 둘은 5차에 사용자가 정했다(아래 「정해진 것」). 남은 것은 서기·코더 몫뿐이다.

### 정해진 것(5차, 11-19 사용자)

1. **03편 실패 사진은 성공 GIF(빌드 #68)와 다른 빌드로** — 「같은 빌드가 성공도 하고 실패도 한 화면이면 틀린 화면이다」(사용자). 아래 「5차」대로 다시 찍었다
2. **`14_usage_where.png`의 「런슈즈 관리자 (11-17 인수)」는 그대로** — 이름은 된다

### 5차: 03편 실패를 실제 실패 빌드 #108로

- 런슈즈 Jenkins 기록(FOREMAN DB `build`, 읽기만)은 109건이고 실패는 `runshoes-app#108` 하나다: 2026-11-10 10:15 시작, 커밋 `3dc5e3b5`, 「빌드·push」 단계 실패. 같은 커밋은 10:28 다시 돌려 성공했다
- 실제로 있었던 다른 빌드를 실패로 보이게 하지 않으려고, 새 번호를 짓지 않고 실제로 실패한 #108을 그 실패 단계 그대로 썼다. 성공 GIF의 #68(11-05 성공)과 겹치지 않는다. 앞으로 생길 번호(#161 뒤)는 나중에 실제 빌드와 부딪힐 수 있어 고르지 않았다
- 바꾼 값(페이지 안에서만, 대본 파일은 그대로): 체인 머리 커밋 `3dc5e3b5`, Jenkins `failed`, step `빌드·push`, ext `runshoes-app#108`, `broke: jenkins`. 커밋 제목은 화면에 안 보이고 호버에만 있어 「시연용 커밋」으로 두었다(런슈즈 실제 커밋 글을 넣지 않음)
- 지금 코드(`shipstate.js` `harborStatus`)에서는 push 단계 실패면 이미지가 올라가지 않은 것이라 **봉인 문양(Jenkins)과 보물창고(Harbor) 둘이 ✗**로 그려진다. 4차 사진(Test 실패, 봉인 문양만 ✗)과 다르다 — 캡션 「빌드 모니터 이름표가 빨간 점, ✗」는 서기 몫
- `03_pipeline_fail.png` 124,136 → 124,776바이트, `03_pipeline_hq_fail.png` 55,533 → 55,447바이트(마법학교, 같은 자르기)
- `03_pipeline_no_build.png`는 빌드가 시작되지 않은 장면이라 빌드 번호가 없다. 그대로 둔다

### 서기·코더 몫(앞서 적은 것)
3. **01편 세 테마 사진 줄**: 노션 게시(`bridge/notion.py` 309줄)는 그림 줄 하나를 그림 블록 하나로 만들어 위아래로 놓는다. 가로로 나란히 놓는 길(열 블록)은 없다. 깃허브 미리보기에서는 세 줄이 한 문단이라 폭이 남으면 옆으로 붙는다. 캡션의 「왼쪽부터」는 서기 몫
4. 캡션이 새 사진과 어긋나는 것(포트폴리오 서기 몫): 1차 것(10편 수, 11편 단추와 묶음 이름, 14편 칩 글, 01편 「출하 라인 세 단계」, 03편 저장소 ✓)에 더해 2차로 생긴 것 — 01편 GIF 둘·상태 사진·툴팁 사진의 「오피스 테마」, 「워크스테이션」「서버룸」「QA 부스」「라운지 소파」 같은 오피스 구역 이름(마법학교는 작업 책상·물약실·시약대 등), 01 툴팁 캡션 「QA 부스」, 02 report 「라운지의 코더 셋 — 오피스 테마」(지금은 FOREMAN 방 대강당), 02 seats·07 coder 「런슈즈 방」, 02 api_error 「인프라 방」, 03 hq_fail 「감독실 현황판」(지금은 교장실 전체), 03 line 「① 빌드 모니터, ② 저장소, ③ 배포 보드」(마법학교는 봉인 문양·보물창고·전송 아치), 15 suggest 「팀장」(교장). 4차로 생긴 것 — 08 overlap 「jenkins-0 조사」·「낱말과 시각은 실제 사례」(지금은 FOREMAN 적재 낱말, 시연), 08 wake 「Jenkins 응답 없음 … 펫퍼민트」(지금은 FOREMAN 적재 막힘, 버린 계획), 15 suggest 「런슈즈 칸이 빨갛고(빌드 실패)」(지금은 머리줄 「기록 못 읽는 세션 1」과 교장 「시작할 일 1」), 15 plan 계획 내용, 15편 알림 글 꼴 예시(적재 막힘 한 사건으로), 07 coder 맡길 일 제목, 14편 숫자(17:15 한 순간), 00·02 지도 패널 세션 제목(「시연용 세션」)
5. GIF 「바뀐 곳만 담기」 변환을 `tools/frames_to_gif.py`나 `screen.py --record`에 옵션으로 넣을지 — 코더 몫. 지금은 스크래치 스크립트로만 했다
6. 서기 지시문의 옛 사진 말 셋(3절)을 새 약속에 맞출지 — 코더 몫
