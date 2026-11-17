# 노션 원고 「판단이 필요한 것」 13건 나누기 (foreman-4, 11-17)

> 관리자 410 서기 일감, 사용자 지시 22의 4번. 대상은 `log/foreman-5_notion_evidence_scope_20261117.md` 「판단이 필요한 것」 13건. 기준 main `4386b3a`. 고친 편 머리 「읽은 커밋」은 바꾸지 않았다

## 항목마다

종류: 수 바뀜 / 기능 생김 / 기준에 따라 맞음 / 애매함(사람에게)

| # | 항목 | 종류 | 한 것 | 근거 파일과 커밋 |
|---|---|---|---|---|
| 1 | `notion/00_foreman.md` 「인프라처럼 새로 붙인 프로젝트는 처음엔 지켜보기만」 | 애매함 | 고치지 않음. 아래 「사람에게 물을 것」 1 | `config/approval.toml` 149~163행 |
| 2 | `notion/04_approval.md`, `notion/04_approval/02_flow.md` 「세 프로젝트 모두 자동 모드」 | 수 바뀜 | 현재형 셋(`04_approval.md` 설계 문단 끝, `02_flow.md` 브리지 꺼짐 문단과 실측 절 첫 문단)을 「네 프로젝트」로. 11-02 조사를 말하는 과거형(`04_approval.md` 첫 문단, `01_rules.md`, `02_flow.md` 「실측 20일」)은 그때 셋이 맞아 둠 | 아래 「자동 모드 확인」. `config/approval.toml` `[projects.ronanlab-infra]` |
| 3 | `notion/01_structure/01_placement.md` 토큰 셋, `/healthz` 하나뿐 | 기준에 따라 맞음 | 「셋」은 설정 칸 수로 맞아 두고, 프로젝트 토큰이 따로 켜져 있다는 것과 화면 파일은 토큰 없이 나간다는 것을 한 줄로. 「하나뿐」은 `02_startup.md`처럼 「데이터를 내는 경로 가운데」로 좁힘 | `bridge/config.py`, `config/tokens.toml`(`enabled = true`, 11-11), `bridge/main.py`(`/`, `/usage` 등 페이지와 `/static`) |
| 4 | `notion/01_structure/02_startup.md` 연결이 끊기면 「조용히」 끝난다 | 기능 생김 | 「CC에는 아무것도 내지 않고」로 바꾸고, 11-15부터 `.run/hook_miss.log`에 한 줄 남긴다는 문장을 더함 | `scripts/foreman-decide.sh`(연결 끊김은 `curl오류` 등 갈래로 기록), `cd14ed6` |
| 5 | `notion/03_session.md` Esc 「취소」 48곳 | 기준에 따라 맞음 | 그때 판(11-13, CC 2.1.323)을 밝히고 판이 바뀌면 달라질 수 있다고 한 구절 | `log/prompt_vs_dialog_20261113.md` 3행, 16행 |
| 6 | `notion/14_screen/02_office.md` `plain` 구역 다섯뿐 | 기준에 따라 맞음 | 「방 구역」으로 좁히고, 나머지 키 넷(관리자 좌석, 디자이너 좌석, 쉼 좌석 묶음, 출하 줄)을 한 줄로 | `bridge/static/themes/plain/theme.json` `layout.zones`(9키) |
| 7 | `notion/09_dispatcher/04_managers.md` 네 프로젝트에 관리자 기록 | 기준에 따라 맞음(문장은 맞고 근거만 좁았음) | 네 프로젝트를 덮는 근거를 한 줄로 보탬 | `config/handoff.toml` `merge_prep.per_project` 넷 모두 `approver = "manager"`(11-12 FOREMAN, 인프라 / 11-13 펫퍼민트, 런슈즈) |
| 8 | `notion/08_handoff.md`, `notion/08_handoff/01_loss.md` 「같은 비율로 깎는다」 | 기준에 따라 맞음 | 두 곳에 「잰 것은 세션 둘이라 표본이 넉넉하지 않다」 한 줄 | `log/foreman_compaction_loss_20261105.md`, `log/runshoes_compaction_loss_20261105.md` |
| 9 | `notion/06_sessions.md` 「FOREMAN 저장소에서만 15개」 | 기준에 따라 맞음 | 「에서만」을 빼고 log 표 그대로 「FOREMAN 15개, 펫퍼민트 1개」. 펫퍼민트 1이 260과 같은 세션인지는 가르지 않아도 되는 문장이 됨 | `log/foreman-4_scribe_two_paths_20261115.md` 「숫자 전과 뒤」 표 |
| 10 | `notion/05_roles/02_guards.md` 「이 꼴이 200건이 넘었다」 | 기준에 따라 맞음 | 앞 문장(FOREMAN에서 소스를 고친 것 1건)과 짝인 「해석기 안에서 소스를 찾아 바꾼 꼴 206건」으로 풀어 씀 | `log/inspect_roleguard_20261114.md` 21행, 116행 |
| 11 | `notion/08_handoff/02_summary.md` 「보는 것은 네 가지」와 표 다섯 줄 | 기준에 따라 맞음 | 「표는 첫째를 두 줄로 나눠 다섯 줄」 한 줄 | `bridge/handoff_state.py` `drift` ①~④ |
| 12 | `notion/10_scribe.md` 서기 갈색이 「파랑, 초록, 보라」와 안 겹침 | 기능 생김 | 지금 역할 색(포먼 금색, 코더 파랑, 조사 초록, 관리자 빨강, 디자이너 분홍)으로 고치고, 처음 견준 목록의 보라가 어느 역할이었는지는 기록에 없다고 적음 | `bridge/static/js/roles.js` `ROLE_COLOR`, `docs/12_scribe.md` 「1.」 표 |
| 13 | `notion/15_db.md` 「이 편을 쓸 때」 event 약 24만 행, 덤프 약 36MB | 애매함 | 고치지 않음. 아래 「사람에게 물을 것」 2 | 원고 첫 커밋 `e285e57`(11-15) |

이미 풀린 항목: 없다. 일감에 든 포트폴리오 예(10편, 03편, 15편)는 포트폴리오 쪽이라 이 13건과 겹치지 않았다. 13건 모두 `4386b3a`에서도 log에 적힌 그대로였다(`bridge/hookmiss.py` 머리 주석 「7갈래」는 이미 8갈래로 고쳐져 있으나 이 13건 밖이다).

### 자동 모드 확인(2번)

CC 트랜스크립트(CC 설정 폴더 아래 프로젝트별 폴더)에서 가장 최근 파일 두세 개의 `"permissionMode"` 값만 셌다(대화 내용은 보지 않았다). 11-17 기준:

| 프로젝트 | 값 |
|---|---|
| FOREMAN | 모두 `auto` |
| 런슈즈 | 모두 `auto` |
| 펫퍼민트 | `auto` 90, `plan` 7(계획 모드로 잠깐 바꾼 것) |
| 인프라(원본, worktree) | 모두 `auto` |

원고는 이 확인을 근거로 이 log를 건다(`[log:foreman-4_notion_judgment_20261117.md]`).

## 사람에게 물을 것

1. **`notion/00_foreman.md` 6절 끝 문장(인프라를 「새로 붙인 프로젝트는 처음엔 지켜보기만」의 예로 든 것)**
   - 애매한 것: 넷 가운데 어디에도 들지 않는다. 원고를 쓸 때도 설정은 같았다. 「관찰로 시작」은 런슈즈, 펫퍼민트의 주석이고, 인프라가 observe인 까닭은 「인프라 묶음 1 동안 사용자가 승인 카드를 풀었고, 끝나면 enforce로」인 임시값이다. 묶음 1이 끝났는지(그래서 enforce로 바꿀지)는 사용자 확인이 필요하다
   - 고친다면: 「승인 규칙도 프로젝트마다 따로 정할 수 있다. 런슈즈와 펫퍼민트는 처음부터 묻지 않고 지켜보기만 하는 모드로 시작했고, 인프라는 클러스터 작업 동안 사용자가 승인 카드를 풀어 같은 모드에 두었다 [code:config/approval.toml].」
2. **`notion/15_db.md` 「이 편을 쓸 때」 수(요약 표 「가장 큰 표」, 7절 보관 문단, 8절 백업 문단)**
   - 애매한 것: 수가 바뀌었을 것이라 사용자 기준으로는 「지금 상태로 고친다」에 들지만, `event` 행 수와 DB 크기는 운영 DB라 이 일감에서 확인할 수 없다. 덤프 크기는 서브에이전트가 백업 폴더에서 잰 값이 있다(11-15 37.4MB, 11-17 45.0MB, 하루 약 3.5MB, `log/foreman-5_notion_evidence_scope_20261117.md`). 또 「이 편을 쓸 때」가 언제인지(11-15) 원고에 없다
   - 고친다면 둘 가운데 하나: (가) 지금 값을 관리자가 DB에서 세어 넘겨 주면 「11-17에 `event`는 약 N만 행, …」으로. (나) 그대로 두고 「이 편을 쓸 때(11-15)」로 날짜만 붙임

## 521 뒤 볼 것

없다. 13건 가운데 `notion/10_scribe/04_notion.md`, `notion/15_db/01_tables.md`에 걸린 항목은 없었고, 두 파일은 건드리지 않았다(13번은 `notion/15_db.md`).

## 일감 밖에서 본 것

- `docs/12_scribe.md` 「1.」 표 32행 (금색 포먼, 파랑, 초록, 보라와 겹치지 않는다)도 12번과 같은 옛 색 목록이다. docs는 이 일감에서 손대지 않는 파일이라 두었다

## 시험

- `.venv/bin/python -m pytest -q`: 1227 통과(화면 말, 비밀값 꼴, 근거 확인 포함). 화면 말 요약 줄 「서기 몫 0줄 남음」
- 새로 쓴 줄과 이 log에 em dash, 가운뎃점 0개

## 규칙 위반

규칙 위반 없음. 파일은 Edit, Write로만 고쳤고, `pgrep -f`, 리디렉션으로 파일 쓰기를 쓰지 않았다. 손대지 않기로 한 파일(`portfolio/`, `bridge/`, `tests/`, `config/`, `docs/`, README.md, CLAUDE.md, 521이 고치는 두 원고)은 건드리지 않았다. 서브에이전트는 쓰지 않았다.
