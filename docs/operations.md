# 작업 참고 — 환경 · 구조 · 돌리기 (CLAUDE.md에서 옮긴 상세)

> 상태: 2026-11-06 서기 `trim`으로 CLAUDE.md에서 옮겼다(`log/trim_20261106.md`). 꼭 지킬 금지 · 결정은 CLAUDE.md에 남아 있고, 여기는 그 상세와 참고다. 내용은 옮기기만 했고 다시 확인하지 않았다.

## 1. 관련 경로 · 환경

| 무엇 | 위치 |
|---|---|
| 런슈즈(쇼핑몰, Spring + React) | `~/AI_programming/runshoes` — 인프라는 `docs/INFRA.md` |
| 펫퍼민트(RAG 챗봇) | `~/AI_programming/petmint-rag-chatbot` — 호스트 서비스는 `deploy/host/`(milvus compose, search-service 유닛) |
| 클러스터 매니페스트 | `~/ronanlab-infra`(GitHub private), ArgoCD가 본다 |
| k8s VM(m-k8s · w1~w3, libvirt) | `~/k8s-cluster` — kubectl은 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'` |
| Python | 브리지는 저장소의 전용 `.venv`(시스템 python 3.14, 1단계 결정). `~/llm_env`는 LLM · 펫퍼민트 작업용 |
| 접속 구조 | 집 PC → 교육 PC → 서버 PC(VNC `DISPLAY=:2`). 서버 PC가 GPU 호스트이고 클러스터 VM도 여기서 돈다 |

서버의 현재 포트 · 컨테이너 · 유닛 상태와 작업 시 주의는 `log/infra_20261102_host-changes.md`.

## 2. 이 저장소의 구조

| 무엇 | 위치 |
|---|---|
| 브리지(FastAPI, 수집 · API · WS · 알림 · 승인 · 입력 주입 · 인계) | `bridge/` — 시작 `bridge/main.py`, 트랜스크립트 적재 `assembler.py` · `transcript/`, 입력 `inject.py`, 인계 · 세션 조작 `handoff.py`, 파이프라인 `pipeline.py`, 승인 `approval*.py`, 알림 `notify.py` |
| 화면 | `bridge/static/` — `/` 픽셀 화면(`office.html` · `js/office.js` · `js/opanel.js`), `/classic` 카드 목록(`dashboard.html` · `js/render.js`), 공통 CSS `css/panel.css`, 테마 `themes/<이름>/theme.json`(magic · office · site · plain) |
| DB(MySQL, 호스트 도커 `127.0.0.1:3308`) | 마이그레이션 `migrations/NNNN_*.sql` — `.venv/bin/python -m bridge.db.migrate` |
| 설정 | `config/approval.toml` · `notify.toml` · `pipeline.toml` · `worktree.toml` · `models.toml`(세션 모델 · 역할 기본값), 비밀은 `.env.bridge` · `.env.telegram`(커밋 안 함) |
| 설계 · 브리프 / 결과 | `README.md`, `docs/NN_*.md` / `log/*.md` |
| 시험 | `.venv/bin/python -m pytest -q`(DB `foreman_test`), `node --test tests/js/` |

## 3. 돌리기 · 확인

- 브리지는 systemd 사용자 유닛 `foreman-bridge`가 돌린다(11-06, `deploy/systemd/foreman-bridge.service`, linger 켬 — 부팅 때 자동 기동). 상태 · 로그: `systemctl --user status foreman-bridge`, `journalctl --user -u foreman-bridge -n 100`. 다시 띄우기(승인 대기 — `/api/dashboard`의 approvals pending — 가 없는지 본 뒤): `systemctl --user restart foreman-bridge`(10초 남짓 끊김)
  - CC 세션 셸에서는 `systemctl --user`가 `Process org.freedesktop.systemd1 exited with status 1`로 실패한다(세션 환경의 DBUS가 VNC 쪽 버스를 가리키고 `XDG_RUNTIME_DIR`가 비어 있다, 11-08). 앞에 `XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`를 붙인다(`journalctl --user`도 같다)
- 브리지 주소는 `127.0.0.1:8000`이다(API 시험 때)
- CC 세션 tmux: 서기 세션은 아직 tmux 세션 `foreman-bridge` 안에 있다(11-06 이름 변경 보류 — `cc-foreman`이 이미 있어서. 정하면 바꾼다). 런슈즈 `cc-runshoes`(11-05 이전, 11-06 정전 뒤 사라짐). 펫퍼민트는 아직 tmux 밖(pts/7) — 입력 주입 불가
- 화면 자리 점검 도구 `.venv/bin/python tools/screen.py`
  - 헤드리스 크로미움으로 세 테마 × 세 크기의 `layoutAudit()` · `propAudit()` + PNG. 문제가 있으면 종료 코드 1
  - 옵션: `--views hq,map,<현장>` · `--session <id>` · `--base`(미리보기 82xx) · `--eval`
  - 자동 재배치 계획은 `--eval "window.office.layoutPlan()"`
- API 토큰은 `.env.bridge`의 `FOREMAN_API_TOKEN` — 셸 변수로만 쓴다

## 4. 작업 규칙의 상세

- **멈춰 둔 CC 프로세스**(11-02 기준 4개): pts/8 — PID 1301867 · 3872105, pts/7 — 1895956 · 1906162. 조사 경위는 `log/01_kickoff_result.md`
- **한국어 진행 글**: 11-05에 최종 답은 한국어인데 중간 진행 글이 영어로 흘러 패널 대화에 그대로 보였다. 컨텍스트가 길어져도 · 요약 뒤에 이어 갈 때도 · 도구 결과(로그 · 코드 · 영문 메시지)가 영어여도 마찬가지다
- **sudo**: 비대화형 sudo가 안 된다. 11-02에 "쳤다"는 명령이 실제로는 실행되지 않은 적이 있어, 쳤다고 하면 journal 등으로 확인한다
- **CI/CD**(11-03 결정, README 3.12): FOREMAN은 한 덩어리로 두고 배포는 systemd, 시험은 GitHub Actions. 둘 다 아직 만들지 않았다(옮기기 전 CLAUDE.md 문구 그대로 — 11-06에 다시 확인하지 않았다)
- **시험 세션 숨김**: 0018 `hidden_at` — `hidden_reason='test'`로 숨기면 카드 · 토큰 집계 · 디스패처 상황 묶음에서 빠지고 행은 남는다
- **worktree 링크**: `.venv` · `.env*` · `node_modules` · CC 메모리는 원본을 가리키는 링크다(그대로 쓰면 된다). 합치기(rebase → fast-forward) · 미리보기(82xx) · 스키마 잠금 상세는 `docs/11_worktree.md`

## 5. 알림(텔레그램) 상세

- 턴 종료 신호(Stop hook 등)로 브리지가 보낸다 — 로드맵 4단계, README 3.2. 규칙은 `config/notify.toml`
- 보낸 것 · 안 보낸 것(+규칙)은 DB `notification`
- 브리지 밖 알림(백업 실패 등): `.venv/bin/python -m bridge.telegram "제목" "줄" …`
- 토큰 · chat_id는 저장소 맨 위 `.env.telegram`(권한 600, `.gitignore`의 `.env*`)
- 접두어: `[런슈즈]` · `[펫퍼민트]` · `[포먼]`. 토큰은 FOREMAN의 `.env.telegram` 하나다(11-02 결정)
- 겹침 알림(11-06, `bridge/overlap.py`, `notify.toml [overlap]`): 사람 입력(UserPromptSubmit)이 같은 프로젝트의 살아 있는 다른 세션이 최근 3시간에 받은 요청과 드문 낱말로 겹치면 텔레그램(`kind = 'overlap'`) + 패널 띠 🔁. 막지 않는다. 포먼의 서기 일감은 맞대지 않는다. 같은 두 세션은 1시간에 한 번
