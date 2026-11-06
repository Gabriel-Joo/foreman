# 11-06 서버 정전 뒤 복구 · 브리지 systemd 유닛

## 무슨 일이 있었나

- 이전 부팅은 11-02 06:00 ~ **11-06 09:32** 에 끝났다(`journalctl --list-boots`). 다음 부팅은 **12:24**. 그 사이 약 3시간 꺼져 있었다.
- 꺼지기 직전 트랜스크립트 마지막 쓰기는 09:30 무렵이었다. 브리지 적재가 그 쓰기를 따라가지 못해 **7개 파일 · 12줄**이 밀려 있었다(전부 개행으로 끝난 완성된 줄).
- 브리지는 **자동으로 뜨지 않았다**(tmux에 손으로 띄우던 방식). 부팅 뒤 8000 포트에 아무도 없었다.
- tmux 세션 `foreman-bridge`는 있었지만 **그 안에서 이 CC 세션이 돌고 있었다**(브리지 프로세스 없음). `cc-foreman` · `cc-runshoes`는 사라졌다. 이 기록을 쓰는 시점에 되살리지 않았다.

## 점검 결과 (복구 전)

| 항목 | 결과 |
|---|---|
| MySQL 컨테이너 `foreman-mysql` | 떠 있음, healthy (restart=unless-stopped로 자동으로 올라옴) |
| 마이그레이션 0001 ~ 0023 | 23개 모두 `schema_migrations`에 적용, 파일과 불일치 없음 |
| 데이터 손상 | `CHECK TABLE` event · message · turn · transcript_file · approval 전부 OK |
| 승인 대기 | `approval` 상태별 집계에 `pending` 0건 |
| 적재 밀림 | 위 7개 파일 · 12줄. 브리지 기동 뒤 백필(0.3초)로 따라잡음. 이후 남은 차이는 이 세션 파일 1개(진행 중이라 정상) |
| 다른 컨테이너 | milvus-standalone · milvus-etcd · ollama · openwebui 떠 있음(healthy) |
| `runshoes-mysql-dev` | Exited(0), 11-06 00:30에 멈춤, restart 정책 없음 — **런슈즈 저장소 소관이라 건드리지 않았다.** 되살릴지는 런슈즈 쪽에서 정한다 |

## 한 일

1. **브리지 기동**: `systemctl --user start foreman-bridge` → 127.0.0.1:8000, DB 127.0.0.1:3308, 와처 켬. `GET /api/dashboard`는 401(토큰 요구 — 정상 응답). 시작 로그에 오류 없음.
2. **유닛 추가**: `deploy/systemd/foreman-bridge.service` (사용자 단위). `systemctl --user link` → `~/.config/systemd/user/`에서 이 파일을 가리키는 링크. `enable`로 `default.target`에 연결.
   - `ExecStart=.venv/bin/python -m bridge`, `WorkingDirectory`는 저장소 루트
   - `Restart=on-failure`, `RestartSec=5`, 시작 제한 300초 안에 10번
   - PATH에 tmux 포함(CC 세션 조회 · 입력 주입용)
   - 로그는 journal: `journalctl --user -u foreman-bridge` (기존 `/tmp/foreman-bridge.log` tee 방식은 쓰지 않는다)
3. **linger 켬**: `loginctl enable-linger kopo17` → `Linger=yes`. 로그인하지 않아도 사용자 매니저(유닛)가 부팅 때 뜬다. sudo 없이 됐다. 되돌리기는 `loginctl disable-linger kopo17`.

## 설계와 달랐던 점 · 판단

- **사용자 단위로 했다.** 시스템 단위(`/etc/systemd/system`)는 설치에 sudo가 필요하고, 브리지가 `kopo17`의 tmux · `~/.claude`를 쓰므로 사용자 단위가 맞다. README 3.12의 "배포는 systemd"에 맞는다.
- **docker 순서는 보장하지 않는다.** 사용자 매니저가 docker를 기다리지 않으므로 DB가 늦게 뜨면 기동이 실패하고 `Restart`가 다시 시도한다. 실제 부팅에서는 docker 컨테이너가 먼저 올라왔다(12:25 시작, 브리지는 12:31).
- **tmux 세션 이름이 겹친다.** `docs/operations.md` 3번은 브리지를 tmux `foreman-bridge`에서 띄운다고 적었는데, 지금은 그 세션에 CC 세션이 들어 있다. 이 상태에서 `tmux kill-session -t foreman-bridge`를 치면 CC 세션이 같이 죽는다. **이제 브리지는 systemd가 돌리므로 그 명령은 쓰지 않는다** — 운영 문서 갱신은 사용자가 시키면 한다.
- **기동 전 확인**: 승인 대기 0건, 8000 포트 비어 있음.

## 아직 남은 것

- **재부팅 검증은 아직 하지 않았다.** 재부팅은 사용자가 시킬 때만 하므로 실제 부팅 뒤 `systemctl --user status foreman-bridge`로 확인해야 한다. 이 유닛이 정말 부팅으로 뜨는지는 그 뒤에야 안다.
- 재시작 스크립트(시험 → import 확인 → 승인 대기 없을 때만 재시작, README 3.12)는 만들지 않았다. 이번 요청 범위 밖.
- `cc-foreman` · `cc-runshoes` 등 CC 세션은 되살리지 않았다. 필요하면 사용자가 정한다.
- `-old` 컨테이너 3개 · 백업은 그대로 둠(재부팅 검증 전까지, CLAUDE.md).
- 알림(텔레그램)은 브리지가 턴 종료 때 보낸다 — 이번 복구에서 따로 확인하지 않았다.

## 되돌리기

- 유닛 끄기: `systemctl --user disable --now foreman-bridge`
- linger 끄기: `loginctl disable-linger kopo17`
- 수동 실행으로 돌아가기: 유닛을 끈 뒤 운영 문서 3번의 tmux 명령(단, 세션 이름 충돌을 먼저 해결할 것)

## 후속 (11-06 같은 날)

- `docs/operations.md` 3번: tmux `kill-session` 명령을 지우고 `systemctl --user restart foreman-bridge`로 바꿨다.
- tmux 이름 변경(`foreman-bridge` → `cc-foreman`)은 **보류**: `cc-foreman` 세션이 이미 있었다(12:32 생성, bash 패널, 제가 만든 것 아님). 남의 세션은 건드리지 않았다. 이 세션은 아직 `foreman-bridge` 안에서 돈다.
- `cc-foreman-2`(12:36, worktree `foreman-2`의 claude)도 제가 만든 것이 아니다.
