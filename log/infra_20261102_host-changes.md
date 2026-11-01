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
