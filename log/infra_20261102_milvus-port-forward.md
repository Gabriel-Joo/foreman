# milvus-port-forward.service 정지 — 2026-11-02

브리프 결과가 아니라 서버 PC 정리 기록이다.

## 상태

- 유닛: `/etc/systemd/system/milvus-port-forward.service` (2026-10-01 생성)
- `ExecStart=/usr/local/bin/kubectl port-forward -n milvus svc/milvus 19530:19530`, `Restart=always`(3초)
- `/usr/local/bin/kubectl`이 호스트에 없다 → 매번 `203/EXEC`로 실패. 첫 실패 2026-10-01 12:54, 11-02까지 **NRestarts 567,740**
- 클러스터에 `milvus` 네임스페이스도 없다(`kubectl get ns milvus` → NotFound). 예전 실험의 잔재

## 조치

`systemctl stop` + `disable`. 유닛 파일은 지우지 않고 남겨 둔다.

## 다시 켜기 전에 볼 것

- **19530 충돌**: 지금 호스트 Milvus(docker, petmint-rag-chatbot `deploy/host/milvus`)가 `127.0.0.1:19530`·`192.168.122.1:19530`을 쓴다.
  kubectl을 깔고 이 유닛을 켜면 `kubectl port-forward`의 기본 바인딩(`127.0.0.1:19530`)이 docker와 부딪힌다 —
  먼저 뜬 쪽이 포트를 잡고 다른 쪽은 실패한다. 재부팅 때는 어느 쪽이 먼저 뜰지 정해져 있지 않다.
- 대상 `svc/milvus -n milvus`가 클러스터에 없다. 켜도 kubectl 단계에서 실패한다.

## FOREMAN과의 관계

한 달 넘게 아무도 몰랐다. 텔레그램 알림은 CC 턴 종료만, 인프라 감시는 웹훅·엔드포인트 폴링만 보므로
"계속 실패하며 재시작하는 호스트 유닛"은 어느 경로에도 걸리지 않았다. README 인프라 캐릭터 감시 대상 논의의 근거.
