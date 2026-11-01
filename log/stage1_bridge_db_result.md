# 로드맵 1단계 — 브리지 · 스키마 · MySQL · WebSocket 결과

- **실행일**: 2026-11-02
- **범위**: 1단계 설계안의 1~6(MySQL · 백업 · 복원 연습 / venv · 설정 / 마이그레이션 · 시드 / FastAPI 뼈대 / 디버그 엔드포인트 / 확인용 페이지). 브리프 없이 채팅으로 설계 → 승인 → 구현
- **커밋**: `197909a` MySQL · `23e93e6` 마이그레이션 · `1ec1bfd` FastAPI 뼈대 · `b5b422a` 디버그 엔드포인트
- 배치 결정(브리지 · DB를 클러스터 밖 호스트에)과 그 근거는 README 3.12

## 실제로 한 일

| 무엇 | 위치 · 상태 |
|---|---|
| FOREMAN 전용 MySQL | 컨테이너 `foreman-mysql`(`mysql:8.0.46`, compose 프로젝트 `foreman`), `127.0.0.1:3308`, restart unless-stopped, mem 1g. 데이터 `~/volumes/foreman-mysql`(bind mount). 설정 `deploy/mysql/` |
| 백업 | `deploy/mysql/backup.sh` — 앱 계정 mysqldump → gzip, 끝 표시 검사, 14개 보관, 실패 시 텔레그램. 사용자 crontab 매일 04:30 → `~/backups/foreman/`(로그 `backup.log`). cron과 같은 최소 환경(`env -i`)으로 1회 실행 확인 |
| 비밀값 | `.env.db`(root · 앱 비밀번호), `.env.bridge`(API 토큰 · hook 토큰 · `DEBUG_ENDPOINTS=true`). 둘 다 600, 커밋 안 함, 값은 화면에 낸 적 없음. 견본 `.env.*.example`은 커밋 |
| 파이썬 | 전용 `.venv`(시스템 python 3.14.4). `pyproject.toml` + `requirements.lock` |
| 스키마 | `migrations/0001_init.sql`(테이블 8 + `schema_migrations`), `0002_seed.sql`(프로젝트 3 · 포먼 3, DORMANT, sprite NULL). 실행기 `python -m bridge.db.migrate [--status]` |
| 브리지 | `python -m bridge` → `127.0.0.1:8000`. `/healthz`(인증 없음) · `/ws` · `/api/debug/*` · `/`(확인용 페이지). `/docs` · `/openapi.json` 닫음 |
| 실행 위치 | tmux 세션 `foreman-bridge`에서 손으로 띄움. 로그 `/tmp/foreman-bridge.log` |

## 설계 확인 다섯 가지 (구현 전 사용자 질문)

1. **event FK 제거.** 일괄 삭제는 event가 자식이라 원래 FK 검사가 걸리지 않는다(느려지는 것은 부모를 지울 때). 그래도 뺀 이유: hook 이벤트가 그 사건을 만드는 트랜스크립트 줄(message · turn 행)보다 먼저 오고, 가장 자주 쓰는 테이블에서 행마다 부모 조회 5번 + FK용 보조 인덱스를 없앤다. 무결성은 event를 쓰는 유일한 곳 `bridge/store.py`가 맡는다(디버그 emit은 없는 character_id를 422로 거절)
2. **`turn.prompt_text` MEDIUMTEXT 유지.** 트랜스크립트 프롬프트 731개: p50 368자 · p99 6,114자 · 최대 18,395자(32,688바이트). TEXT(64KB)의 절반. 붙여넣기 접힘 `[Pasted text #N]`이 user 줄에 0건 — 원문이 기록되는 정황(README 3.1 미검증 항목을 확정할 근거는 아님)
3. **`event.target` 1,024자 + `target_truncated` + `payload.target_full`.** 실측 Bash 명령 9,979개: p50 455 · p90 2,139 · p99 7,435 · 최대 24,528자, 1,024자 초과 25.2%. Read · Edit · Write · WebFetch는 최대 170자. 잘린 값 끝에 `…`
4. **`character.sprite` NULL.** placeholder 문자열은 나중에 진짜 키와 구별되지 않는다. 10단계에서 채운다
5. **복원 연습은 별도 임시 컨테이너**(네트워크 없음, tmpfs). 운영 인스턴스에 잘못 덮어쓸 수 없고, 대비하는 상황(인스턴스를 잃음)과 같다. 결과: 테이블 9 · FK 11 · 인덱스 34 · 행 수 · 한글 바이트(`ED8FACEBA8BC`)가 운영과 일치. 컨테이너 · 임시 디렉토리 남지 않음

## 시험에서 찾은 것

- **`cryptography` 누락 — DB 재시작 뒤 브리지가 영영 복구되지 않았다.** MySQL 8 `caching_sha2_password`는 재시작으로 서버의 인증 캐시가 비면 비TLS 연결에서 RSA 전체 인증을 하고, PyMySQL은 그때 `cryptography`를 요구한다(`RuntimeError: 'cryptography' package is required …`). 첫 기동 때는 마이그레이션 · CLI 로그인으로 캐시가 차 있어 드러나지 않았다. pytest(DB 연결 포함)도 통과했으므로 **재시작 시험이 아니면 못 잡았다.** 의존성에 추가(`1ec1bfd`)
- **healthz가 원인을 삼키고 있었다.** 위 버그를 찾을 때 응답이 `down`뿐이라 바로 알 수 없었다 → 상태가 바뀔 때 한 번 원인을 로그로 남기게 고침
- 컨테이너 healthcheck(`mysqladmin ping`, 계정 없음)는 Access denied여도 종료 코드 0 — "서버가 살아 있다"만 본다. 의도대로지만 앱 계정 인증까지 보지는 않는다

## 확인한 동작 (실행 중인 브리지에서)

| 시험 | 결과 |
|---|---|
| 마이그레이션 두 번 실행 | 두 번째 "적용할 것 없음" |
| `docker restart foreman-mysql` | healthz 503 약 5초 → 저절로 200(1초 간격 기록 50회 중 200 45 · 503 5) |
| `docker pause`(서버가 답하지 않음) | healthz가 정확히 5.0초(타임아웃)에 503 — 멈추지 않음. unpause 4초 안에 200 |
| pause 중 emit 2회 | 202 `queued`(버리지 않음). unpause 직후 id 5 · 6이 순서대로 DB와 WS에 도착 |
| WS | 틀린 토큰 · JSON 아닌 첫 메시지 → close 1008. 15초 하트비트 ping 수신 |
| HTTP 인증 | 토큰 없음 · 틀림 → 401 |
| pytest | 14개(단위 5 + DB 9) |

## 설계와 달랐던 점

- README 5장 스키마와 다른 점(사용자 승인): `transcript_file` 분리(읽기 위치를 파일 단위로 — `--resume`이 한 파일을 여러 세션 행에 걸치게 하고, 와처는 주인을 알기 전에 파일을 먼저 본다), `character_session.token_usage` 제거, `subagent_run.reported_*` 추가, `build` · `summary` 보류(9 · 11단계), `sprite` NULL, event FK 없음, `event.target_truncated`, enum은 VARCHAR. **실제 DDL의 기준은 `migrations/0001_init.sql`**
- `~/volumes` · `~/backups`가 root 소유라 하위 폴더를 만들 수 없었다. 데이터 폴더는 compose bind mount가 만들었고(그래서 소유자가 컨테이너 쪽), 백업 폴더는 사용자가 sudo로 만들었다(07:57:30 journal 확인)
- 기본 이벤트 소스에 `debug`를 더했다(확인용 이벤트를 구별해 지우려고)

## 판단 근거

- **단일 writer + 적재 후 전송**: event.id 순서 = 들어온 순서가 보장되고, 화면에 보인 것은 DB에도 있다
- **DB 장애 때 붙들고 재시도, 영구 오류만 버림**: 중복 uuid · 잘못된 값은 다시 해도 같으니 대기열을 막지 않는다. 대기열이 차면 생산자가 받는다(2단계 와처는 offset을 멈춘다)
- **binlog 끔 + 매일 dump**: 디스크 80%. 트랜스크립트 120일과 멱등 적재로 대부분 다시 만들 수 있다. 못 만드는 것은 hook · 폴링 이벤트뿐
- **토큰 둘**: hook 토큰이 새도 API · 입력 주입은 못 쓴다. WS 토큰은 쿼리스트링이 아니라 첫 메시지(주소는 로그에 남는다)
- **전용 venv**: `~/llm_env`는 LLM · 펫퍼민트 작업과 공유 — 3.12와 같은 장애 범위 논리

## 아직 안 한 것

- **집 PC 브라우저 접속 확인** — `ssh -L 8000:localhost:8000` → `http://localhost:8000/` → 토큰 → 연결 → 이벤트 보내기. 서버 안에서는 같은 경로를 확인했다
- 브리지 systemd 유닛(sudo · linger 꺼짐) — 매일 쓰기 시작하는 6단계 즈음
- 재부팅 검증(사용자가 시킬 때) — `foreman-mysql`은 restart unless-stopped라 docker와 함께 뜨는 것이 기대값
- `DEBUG_ENDPOINTS`는 터널(브리프 02) 전에 false로
- 정기 고아 행 점검 쿼리(event FK 없음의 대가) — 적재가 생기는 2단계에서
- starlette TestClient가 `httpx` 대신 `httpx2`를 쓰라는 경고 — 테스트만 해당, 미조치
