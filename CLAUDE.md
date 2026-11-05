# FOREMAN — 이 프로젝트에서만 쓰는 규칙

## 새 세션이 먼저 읽을 것

1. `README.md` — 전체 설계(2026-11-02 킥오프 검토 반영)
2. `log/01_kickoff_result.md` — 조사 결과 · 설계와 달랐던 점 · 판단 근거 · 남은 미검증 · 다음 단계
3. `log/infra_*.md` — 서버 PC에서 바꾼 것, 남겨 둔 되돌리기용 자원, 이 서버에서 작업할 때 알아둘 것

## 작업 규칙

- **항상 한국어로 답한다 — 최종 답만이 아니라 도구 호출 사이의 짧은 진행 글("이제 ~를 본다" 같은 한두 줄)까지 전부.** 컨텍스트가 길어져도 · 요약 뒤에 이어 갈 때도 · 도구 결과(로그 · 코드 · 영문 메시지)가 영어여도 마찬가지다. 11-05에 최종 답은 한국어인데 중간 진행 글이 영어로 흘러 패널 대화에 그대로 보였다 — 쓰기 전에 그 글이 한국어인지 본다
- **멈춰 있는 CC 프로세스(Ctrl+Z, `T` 상태)는 건드리지 않는다.** 사용자가 프로젝트별로 의도적으로 남겨 둔 것이다(11-02 기준 4개 — pts/8: PID 1301867 · 3872105, pts/7: 1895956 · 1906162)
- **실행 중인 다른 프로젝트의 CC 세션(runshoes · petmint)도 사용자 승인 없이 멈추거나 옮기지 않는다.** 로드맵 0단계(tmux 이전)의 대상은 사용자에게 먼저 확인한다
- **서버 재부팅은 사용자가 시킬 때만.** 재부팅 검증 전까지 `-old` 컨테이너 3개와 백업은 그대로 둔다. 정리도 사용자가 시킬 때
- **sudo가 필요한 명령은 직접 치지 않고 사용자에게 한 줄로 알린다**(비대화형 sudo 불가). 쳤다고 하면 journal 등으로 실제 실행 여부를 확인한다 — 11-02에 "쳤다"는 명령이 실제로는 실행되지 않은 적이 있다
- **브리프 실행과 기록은 분리한다.** 브리프가 "파일을 고치지 마라 / 채팅으로만"이라고 하면 실행 중에는 채팅으로만 보고하고, `log/` 기록 · README 반영은 사용자가 시킬 때 한다
- 브리프는 `docs/NN_<이름>.md`, 실행 결과는 `log/NN_<이름>_result.md`. 결과에는 한 일 · 조사 결과 · 설계와 달랐던 점 · 판단 근거만 쓰고 브리프를 재서술하지 않는다. 브리프가 아닌 서버 작업 기록은 `log/infra_<날짜>_<주제>.md`. 브리프 없이 진행한 로드맵 단계의 결과는 `log/stage<N>_<이름>_result.md`(예: `stage1_bridge_db_result.md`) — 쓰는 내용은 브리프 결과와 같다
- **작업을 마치면 `log/`에 기록 → 커밋 → push**(사용자 상시 지시, 11-03~). 커밋 메시지 끝에 `Co-Authored-By` 줄. 브리프가 "기록하지 마라"면 그때만 예외(위). git 원격은 GitHub(`Gabriel-Joo/foreman`)만. GitLab은 로드맵 8단계에서 FOREMAN을 CI/CD에 태울 때 추가한다
- **작업 트리에 내가 만들지 않은 변경이 있으면 건드리지 않고 사용자에게 알린다**(다른 세션이 같은 저장소에서 일할 수 있다). 커밋할 때는 내가 고친 파일만 `git add`
- **화면에 뜨는 글(툴팁 · 안내 · 확인 창 · 결과 · 서버 거부 사유)은 "~습니다"로**, 툴팁은 "무엇 — 한 줄 설명"으로 짧게(11-05 사용자 지시)
- 파일 고치기는 Edit · Write로(Bash의 sed · python으로 고치지 않는다). `approval.toml` · `notify.toml` · 브리지 코드를 바꾸면 브리지를 다시 띄운다
- **다른 저장소(runshoes · petmint-rag-chatbot · ronanlab-infra)는 사용자가 시킬 때만 고치고, 그 저장소의 CLAUDE.md를 따른다**(알림 접두어 · 토큰 파일이 저장소마다 따로다)
- **비밀값을 화면 · 로그 · 커밋에 내지 않는다**: `.env*`, `~/.claude/.credentials.json`, `~/.claude/sessions/*.key`(세션 간 통신 토큰 — 11-02 조사 때 한 번 출력에 찍혔다). 값이 필요 없으면 키 이름만 본다

## 관련 경로 · 환경

| 무엇 | 위치 |
|---|---|
| 런슈즈(쇼핑몰, Spring + React) | `~/AI_programming/runshoes` — 인프라는 `docs/INFRA.md` |
| 펫퍼민트(RAG 챗봇) | `~/AI_programming/petmint-rag-chatbot` — 호스트 서비스는 `deploy/host/`(milvus compose, search-service 유닛) |
| 클러스터 매니페스트 | `~/ronanlab-infra`(GitHub private), ArgoCD가 본다 |
| k8s VM(m-k8s · w1~w3, libvirt) | `~/k8s-cluster` — kubectl은 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'` |
| Python | 브리지는 저장소의 전용 `.venv`(시스템 python 3.14, 1단계 결정). `~/llm_env`는 LLM · 펫퍼민트 작업용 |
| 접속 구조 | 집 PC → 교육 PC → 서버 PC(VNC `DISPLAY=:2`). 서버 PC가 GPU 호스트이고 클러스터 VM도 여기서 돈다 |

서버의 현재 포트 · 컨테이너 · 유닛 상태와 작업 시 주의는 `log/infra_20261102_host-changes.md`.

## 이 저장소의 구조

| 무엇 | 위치 |
|---|---|
| 브리지(FastAPI, 수집 · API · WS · 알림 · 승인 · 입력 주입 · 인계) | `bridge/` — 시작 `bridge/main.py`, 트랜스크립트 적재 `assembler.py` · `transcript/`, 입력 `inject.py`, 인계 · 세션 조작 `handoff.py`, 파이프라인 `pipeline.py`, 승인 `approval*.py`, 알림 `notify.py` |
| 화면 | `bridge/static/` — `/` 픽셀 화면(`office.html` · `js/office.js` · `js/opanel.js`), `/classic` 카드 목록(`dashboard.html` · `js/render.js`), 공통 CSS `css/panel.css`, 테마 `themes/<이름>/theme.json`(magic · office · site · plain) |
| DB(MySQL, 호스트 도커 `127.0.0.1:3308`) | 마이그레이션 `migrations/NNNN_*.sql` — `.venv/bin/python -m bridge.db.migrate` |
| 설정 | `config/approval.toml` · `notify.toml` · `pipeline.toml`, 비밀은 `.env.bridge` · `.env.telegram`(커밋 안 함) |
| 설계 · 브리프 / 결과 | `README.md`, `docs/NN_*.md` / `log/*.md` |
| 시험 | `.venv/bin/python -m pytest -q`(DB `foreman_test`), `node --test tests/js/` |

## 돌리기 · 확인

- 브리지는 tmux `foreman-bridge`에서 돈다. 다시 띄우기: 승인 대기(`/api/dashboard`의 approvals pending)가 없는지 본 뒤
  `tmux kill-session -t foreman-bridge; tmux new-session -d -s foreman-bridge -c ~/AI_programming/foreman 'bash -c ".venv/bin/python -m bridge 2>&1 | tee -a /tmp/foreman-bridge.log"'`(10초 남짓 끊김)
- CC 세션 tmux: 이 세션 `cc-foreman`, 런슈즈 `cc-runshoes`(11-05 이전). 펫퍼민트는 아직 tmux 밖(pts/7) — 입력 주입 불가
- 화면 자리 점검(가구 · 소품 · 이름표가 사람을 가리는지): 브라우저 콘솔 `window.office.layoutAudit()`, 자동 재배치 계획 `layoutPlan()`. 테마의 자리 · 가구를 바꾸면 세 테마 모두 0건인지 본다
- API는 토큰(`.env.bridge`의 `FOREMAN_API_TOKEN`)이 필요하다 — 값은 화면에 찍지 않고 셸 변수로만 쓴다

## 알림(텔레그램)

텔레그램 알림은 **브리지가 턴이 끝날 때 기계적으로 보낸다**(Stop hook 등 턴 종료 신호, 로드맵 4단계 — README 3.2, 규칙은 `config/notify.toml`). **이 세션에서 직접 보내지 않는다.** 런슈즈 · 펫퍼민트도 같다(접두어 `[런슈즈]` · `[펫퍼민트]` · `[포먼]`).

- 무엇을 보낼지 바꾸려면 `config/notify.toml`을 고치고 브리지를 다시 띄운다. 보낸 것 · 안 보낸 것(+규칙)은 DB `notification`
- 브리지 밖 알림(백업 실패 등)은 `.venv/bin/python -m bridge.telegram "제목" "줄" …` — 모델이 판단해 부르는 용도가 아니다
- 토큰 · chat_id는 저장소 맨 위 `.env.telegram`(권한 600, `.gitignore`의 `.env*` — 커밋하지 않는다)
- 토큰 값을 이 파일 · 코드 · 커밋 · 로그 · 화면 출력에 쓰지 않는다
