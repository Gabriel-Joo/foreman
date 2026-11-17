<!-- 이 파일은 `tools/docs.py readme`가 만든다. 손으로 고치면 다음에 만들 때 날아간다. 소개는 포트폴리오 00편 첫 문단, 편 목록은 원고 첫 # 줄, 노션 주소는 게시 기록에서 온다 -->
# FOREMAN

**FOREMAN은 한 서버에서 동시에 도는 여러 AI 작업 세션을 브라우저 한 화면에서 보고 다루는 관제 화면입니다. 왼쪽 지도에서 누가 무엇을 하는지 보고, 오른쪽 패널에서 그 세션과 이야기하고, 아래 셸에서 AI에게 맡길 수 없는 명령을 직접 칩니다.**

## 포트폴리오

[노션에서 보기](https://app.notion.com/p/FOREMAN-4103218bb52481a6815acb4b44dc800d)

| 번호 | 제목 | 하위 |
|---|---|---|
| 00 | [한눈에 보는 FOREMAN](portfolio/00_overview.md) |  |
| 01 | [픽셀 지도와 방](portfolio/01_pixel_office.md) |  |
| 02 | [머리 위 표시와 띠](portfolio/02_overhead.md) |  |
| 03 | [출하 라인](portfolio/03_pipeline.md) |  |
| 04 | [세션 패널: 대화와 활동](portfolio/04_session_panel.md) |  |
| 05 | [승인 카드](portfolio/05_approval.md) |  |
| 06 | [세션 정리: 인계와 옮기기](portfolio/06_handoff.md) |  |
| 07 | [합치기 카드와 코더 창](portfolio/07_merge.md) |  |
| 08 | [교장 계획 창과 감독실](portfolio/08_foreman_plan.md) |  |
| 09 | [새 세션 창](portfolio/09_new_session.md) |  |
| 10 | [서기실](portfolio/10_scribe_room.md) |  |
| 11 | [포스트잇](portfolio/11_postit.md) |  |
| 12 | [세션 화면 창](portfolio/12_session_screen.md) |  |
| 13 | [셸 패널](portfolio/13_shell.md) |  |
| 14 | [사용량 화면](portfolio/14_usage.md) |  |
| 15 | [텔레그램 알림](portfolio/15_telegram.md) |  |

## 기술문서

[노션에서 보기](https://app.notion.com/p/00-FOREMAN-4193218bb524814cbbcec87c6bc6ffc0)

| 번호 | 제목 | 하위 |
|---|---|---|
| 00 | [FOREMAN이란](notion/00_foreman.md) |  |
| 01 | [전체 구조](notion/01_structure.md) | 하위 2 |
| 02 | [기록 모으기](notion/02_ingest.md) | 하위 4 |
| 03 | [세션 지켜보기와 글 넣기](notion/03_session.md) |  |
| 04 | [승인](notion/04_approval.md) | 하위 3 |
| 05 | [역할과 권한](notion/05_roles.md) | 하위 3 |
| 06 | [세션 띄우기와 따로 작업](notion/06_sessions.md) |  |
| 07 | [합치기](notion/07_merge.md) | 하위 2 |
| 08 | [인계와 압축 손실](notion/08_handoff.md) | 하위 4 |
| 09 | [교장과 관리자](notion/09_dispatcher.md) | 하위 4 |
| 10 | [서기와 문서](notion/10_scribe.md) | 하위 4 |
| 11 | [알림](notion/11_notify.md) |  |
| 12 | [CI/CD 인과 체인](notion/12_pipeline.md) |  |
| 13 | [사용량과 모델](notion/13_usage.md) |  |
| 14 | [화면](notion/14_screen.md) | 하위 5 |
| 15 | [DB](notion/15_db.md) | 하위 2 |
| 16 | [시험과 배포](notion/16_tests.md) |  |

## 문서

| 문서 | 제목 | 요약 |
|---|---|---|
| [00_design.md](docs/00_design.md) | FOREMAN | 문서 틀(11-17 사용자): 이 문서는 설계 전체이고 세션과 개발자가 읽는다. |
| [01_kickoff.md](docs/01_kickoff.md) | BRIEF 01, 킥오프: 설계 검토 | FOREMAN 프로젝트를 시작한다. |
| [02_cloudflare_tunnel.md](docs/02_cloudflare_tunnel.md) | BRIEF 02, 외부 노출: Cloudflare Tunnel + Access | **터널을 열지 않는다.** |
| [10_office_design.md](docs/10_office_design.md) | 10, 픽셀 오피스: 이상적인 그림 (사용자 구상, 2026-11-03) | 에셋이 무엇을 지원하느냐에 따라 깎는다, 맨 아래 "실제로 가능한 범위"(에셋 조사 뒤 추가). |
| [11_foreman_dispatch.md](docs/11_foreman_dispatch.md) | 11, 포먼이 세션을 띄운다, 자동 인계 (설계, 2026-11-05) | [+ 세션]을 사람이 다 정하던 것(프로젝트, 새로/인계, 어느 요약, 역할)을 포먼이 판단한다. |
| [11_handoff.md](docs/11_handoff.md) | 11, 세션 인계, 세션 조작 (설계, 2026-11-05) | 로드맵 11단계 중 "세션 인계"를 먼저 한다(런슈즈 세션이 730MB, 17일째, auto-compact 17번, 사용자 판단으로 앞당김). |
| [11_handoff_v2.md](docs/11_handoff_v2.md) | 인계 2판, 문서로 옮기고, 읽을 곳을 넘긴다, 압축 알림 (2026-11-05 설계, 사용자 확인 대기) | 1판(`docs/11_handoff.md`)은 세션이 대화 전체를 요약해 새 세션에 넣었다. |
| [11_worktree.md](docs/11_worktree.md) | 11, 세션마다 따로 작업(worktree), 스키마 잠금, 미리보기 브리지 (2026-11-05) | `docs/00_design.md` 「3.4」("한 프로젝트에 캐릭터를 둘 이상 붙이면 같은 파일을 덮어쓴다 → git worktree")를 실제로 만든다. |
| [12_scribe.md](docs/12_scribe.md) | 12, 서기(문서화 캐릭터) 설계 (2026-11-05 초안, 사용자 확인 대기) |  |
| [13_demo_capture.md](docs/13_demo_capture.md) | 13 시연 사진, 녹화, 포트폴리오에 "움직이는 화면"을 (설계, 2026-11-06) | 이 문서의 글 번호(00 ~ 09)는 옛 10편 기준이다. |
| [14_dispatcher_note_wake.md](docs/14_dispatcher_note_wake.md) | 14, 감독실 캐릭터, 디스패처 노트, 자동 기상 2단계 (설계, 2026-11-08) | 디스패처는 여전히 부를 때만 `claude -p` 한 번이다. |
| [15_usage.md](docs/15_usage.md) | 15, 사용량 화면, 한도 역산 (설계, 2026-11-08) | 세션, 모델, 프로젝트, 시간대별 토큰을 보이고, 구독 한도(5시간, 주간)를 "지금 몇 %"로 추정한다. |
| [TODO.md](docs/TODO.md) | TODO, 남은 일 | 꼴과 번호: 항목은 `- **foreman-N** 제목 (올린 날)`, 다음 줄에 내용, 그다음 줄에 나온 곳을 쓴다. |
| [manuscript_rules.md](docs/manuscript_rules.md) | 원고 쓰는 기준 (모든 저장소 공통) | **1~5절의 맨 위 글머리 줄은 서기 지시문과 코더 규칙 절에 그대로 들어간다.** |
| [operations.md](docs/operations.md) | 작업 참고, 환경, 구조, 돌리기 (CLAUDE.md에서 옮긴 상세) |  |
| [roles.md](docs/roles.md) | 역할, 목록, 권한, 새 역할 더하기 (11-15) | 세션 역할의 값, 이름, 설명, 색, 권한을 한눈에 보는 곳이다. |
| [style_guide.md](docs/style_guide.md) | 문서 쓰는 기준 (서기, 모든 세션 공통) | (11-17 바뀜) **저장소와 상관없는 원고 기준(말투, 깊이, 문단, 정직, 옛 기록의 범위, em dash와 가운뎃점)은 `docs/manuscript_rules.md` 한 곳이다.** |
