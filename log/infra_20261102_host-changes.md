# 서버 PC 변경 기록 — 2026-11-02

브리프 결과가 아니라 FOREMAN 킥오프 세션 중에 서버 PC(GPU 호스트)에서 바꾼 것의 기록이다.
FOREMAN 설계의 근거가 된 사고들이 여기서 나왔다(README 2.2 호스트 서비스 감시, 01 결과의 "부수적으로 확인한 것").

## 바꾼 것 — 최종 상태

| 대상 | 전 | 후 | 근거 · 위치 |
|---|---|---|---|
| CC `cleanupPeriodDays` | 없음(기본 30일) | 120 | 서버 사용 기간. `~/.claude/settings.json` |
| 호스트 MySQL `mysql` | `0.0.0.0:3306` | `127.0.0.1:3306` | 펫퍼민트 로컬 개발 · 측정용(243MB, 클러스터에 없음 — 지우지 않는다) |
| `openwebui` | `0.0.0.0:3000` | `127.0.0.1:3000` | 14일간 접속 기록 없음 |
| `ollama` | `0.0.0.0:11434` | `127.0.0.1` · `192.168.122.1` · `172.17.0.1` | 터널(localhost) · 클러스터 파드(VM 게이트웨이) · openwebui(`host.docker.internal`) |
| milvus | embedded etcd, `0.0.0.0:19530/2379/9091` | **외부 etcd 3.5.33** + `127.0.0.1` · `192.168.122.1`:19530, `127.0.0.1:9091`, etcd는 호스트에 안 엶 | 재시작 때 `leader changed` panic(17분 루프). petmint-rag-chatbot `deploy/host/milvus/docker-compose.yml`(`17da4b9`) |
| search-service | 손으로 띄운 프로세스 | systemd `petmint-search`(enabled), ExecStartPre로 milvus healthz 최대 240초 대기 | petmint-rag-chatbot `deploy/host/petmint-search.service`(`cc5a523`) |
| 펫퍼민트 앱 | `MilvusClient`(timeout 없음) | `ResilientMilvusClient`(timeout 10초 + 새 연결로 1회 재시도), 이미지 `5331ebdb6596` 배포 | "검색 중" 멈춤. petmint-rag-chatbot `5331ebd` |
| k8s VM 4대 | 자동 시작 안 함 | `virsh autostart` | 재부팅 후 클러스터가 안 뜸 |
| `milvus-port-forward.service` | enabled, 567,740회 재시작 | stop + disable(유닛 파일 유지) | [`infra_20261102_milvus-port-forward.md`](infra_20261102_milvus-port-forward.md) |
| `ollama-old` | 정지, 30.5GB(`/tmp`의 GGUF 원본) | 삭제 | 모델은 `ollama_data` 볼륨에 20개, 운영 모델 `tri-7b` · `kabyul-tri-7b-rag1-rebuild4-ckpt462` 확인 후. 디스크 84% → 80% |

중단: 펫퍼민트 검색이 milvus 첫 재시작 시도 때 약 17분(05:20~05:37), 외부 etcd 전환 때 약 30초, search-service 재시작 때마다 약 30초.

## FOREMAN 로드맵 1단계로 생긴 것 (같은 날 07:43~)

FOREMAN 자체의 자원이다. 근거는 README 3.12, 결과는 [`stage1_bridge_db_result.md`](stage1_bridge_db_result.md).

| 대상 | 상태 | 비고 |
|---|---|---|
| 컨테이너 `foreman-mysql` | `mysql:8.0.46`, restart unless-stopped, mem 1g. compose 프로젝트 `foreman`(`foreman/deploy/mysql/compose.yml`) | 호스트 3306 `mysql`(펫퍼민트)과 별개 |
| 포트 3308 | `127.0.0.1:3308` → 컨테이너 3306 | 호스트 밖에는 열지 않는다 |
| `~/volumes/foreman-mysql` | 데이터(bind mount). compose가 만들어 소유자가 컨테이너 쪽(mysql uid) | `docker volume prune`에 지워지지 않는다. 지우면 FOREMAN 기록이 사라진다 |
| `~/backups/foreman` | kopo17 소유 700(사용자가 sudo로 생성, 07:57:30). `foreman-*.sql.gz` 14개 보관 + `backup.log` | |
| 사용자 crontab | `30 4 * * * …/foreman/deploy/mysql/backup.sh >> ~/backups/foreman/backup.log 2>&1` — 이 crontab의 유일한 줄 | 실패하면 텔레그램(`[포먼] DB 백업 실패`) — 4단계부터 `python -m bridge.telegram`으로(스크립트 삭제) |
| 런슈즈 · 펫퍼민트 `.env.telegram` | 5단계 때 삭제(사용자 지시, 쓰는 곳 없음). foreman 것만 남음 | |
| tmux 세션 `foreman-bridge` | 브리지(`.venv/bin/python -m bridge`) → `127.0.0.1:8000`. 로그 `/tmp/foreman-bridge.log`. 2단계부터 `~/.claude/projects`를 inotify로 감시하고 `~/.claude/sessions/*.json`을 읽는다(.key는 안 읽음) | 손으로 띄운 것 — 재부팅하면 안 뜬다(systemd 유닛은 6단계 즈음). 같은 tmux 서버에 `cc-foreman`(FOREMAN 작업 세션)도 있다 |
| `~/.claude/settings.json` `hooks` | UserPromptSubmit · Stop · StopFailure · SessionEnd · SubagentStart/Stop → `foreman/scripts/foreman-hook.sh`(3단계, 08:44). 5단계에 PreToolUse · PermissionRequest → `foreman-decide.sh` 추가(백업 `settings.json.before-foreman-approval`). **모든 CC 세션에 걸린다** | 백업 `~/.claude/backups/settings.json.before-foreman-hooks`. 되돌리려면 그 파일로. 08:57:53~08:58:10에 시험용 hook을 잠깐 더했다가 백업으로 되돌림(동일 확인) |
| `foreman/.tools/ttyd` · tmux 세션 `foreman-shell` | 7단계 터미널 패널. ttyd 1.7.7 정적 바이너리(GitHub 릴리스, SHA256SUMS 확인 — sudo 없이, apt 미사용). 브리지가 자식으로 띄워 `foreman/.run/ttyd.sock`(디렉토리 0700)에만 묶는다 — **TCP 포트 없음**. 로그 `.run/ttyd.log`. 셸은 tmux `foreman-shell`(`bash --rcfile deploy/shell/foreman-bashrc`) — 브리지를 다시 띄워도 남는다 | 둘 다 `.gitignore`. 지우려면 브리지를 내리고 `tmux kill-session -t foreman-shell`, `.tools/` · `.run/` 삭제. 이 셸에서 친 명령은 DB `event(source=shell)`에 마스킹되어 남는다 |
| 브리지 웹훅 포트 `192.168.122.1:8001` | 8단계. virbr0(libvirt 내부망)에만 — 클러스터의 Jenkins · Harbor · ArgoCD가 보낸다. `/webhooks/*`만, 보낸 곳 IP가 VM 망(192.168.121/122.x)이어야 하고 `FOREMAN_WEBHOOK_TOKEN`(`.env.bridge`) 필요. LAN(enp5s0)에는 열지 않았다(바인드 주소가 virbr0) | 브리지를 내리면 같이 닫힌다. 끄려면 `.env.bridge`에서 토큰을 빼거나 `WEBHOOK_BIND_HOST=` |
| 클러스터 쪽 웹훅 설정 | **아직 안 함** — CC 자동 모드가 공유 클러스터 변경을 막았다. 사람이 `scripts/cicd-apply.sh`(ArgoCD `argocd-notifications-cm`/`-secret`, Secret `jenkins/foreman-webhook`, Harbor 프로젝트 웹훅 정책 `foreman`)와 Jenkinsfile 패치(`deploy/cicd/jenkinsfile-*.patch`)를 적용한다 | 되돌리기는 스크립트 머리말 |
| DB `foreman_test` | `foreman-mysql` 안의 테스트용 데이터베이스, `foreman_app`에 ALL 권한(2단계, root로 생성) | pytest가 매번 테이블을 지우고 다시 만든다. 운영 `foreman`과 별개 |
| ~~`~/.claude/projects/-tmp-foreman-hooktest-6j5TYq`~~ | hook 시험용 트랜스크립트 — 3단계 때 지움(사용자 지시). 3단계 probe 트랜스크립트도 지움. DB의 '미분류' 행은 남김(재적재 금지 원칙) | |

## 남겨 둔 것 (되돌리기용) — 재부팅 검증 뒤 정리

| 대상 | 용량 | 상태 |
|---|---|---|
| `milvus-standalone-old` | 쓰기 계층 405MB | 정지, restart=no |
| `openwebui-old` | 62MB | 정지, restart=no |
| `mysql-old` | 29kB | 정지, restart=no(전엔 `0.0.0.0:3306` — 켜면 노출이 돌아온다) |
| `~/volumes/milvus/etcd` | 123MB | embedded etcd 원본. 지금 milvus는 `~/volumes/milvus-etcd`를 쓴다 |
| `~/backups/milvus-volume-20261102.tar.gz` | 136MB | 전환 직전 milvus 볼륨 전체(소유자 999 유지) |

## 아직 안 한 것

- **실제 재부팅 검증.** 사용자 지시로 하지 않았다(복구할 시간이 없을 때 하지 않는다). 순서 보장은 리허설(같은 이미지로 동시 재시작 3회 · etcd를 늦게 켜는 재부팅 흉내 1회, panic 0)까지만 확인
- 재부팅 때 자동으로 안 뜨는 것: `runshoes-mysql-dev` · `runshoes-spring-dev`(compose 기본 restart=no, 개발용), `neo4j`(9-29부터 정지)
- 0.0.0.0에 남은 것: 22(ssh), 2049와 RPC 포트(NFS), 3200(`runshoes-spring-dev`, host 네트워크), 3389, 5902(VNC). 이번 범위 밖
- ArgoCD `petmint`: `17da4b9` · `cc5a523` push 뒤 Jenkins 빌드로 OutOfSync일 수 있다(바뀐 것은 `deploy/`뿐, Sync는 선택)

## 이 서버에서 작업할 때 알아둘 것

- kubectl은 호스트에 없다 — `cd ~/k8s-cluster && vagrant ssh m-k8s -c '<kubectl …>'`
- 이 셸의 `find`는 `bfs`라 `find -- <dir>` 형태가 안 된다 — 디렉토리 이름이 `-`로 시작하는 `~/.claude/projects/*`는 Python glob으로
- sudo는 비대화형으로 안 된다 — 필요한 명령은 사용자에게 알려 직접 치게 한다
- 트랜스크립트를 통째로 grep · `docker logs --since`로 훑으면 수백 MB라 느리다 — `--tail`, 오프셋, `"type":"api-request` 선필터
