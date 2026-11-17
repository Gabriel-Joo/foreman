# 알려진 한계와 할 일 다시 가르기 (문서 정리 C, 조사)

> 2026-11-17 조사 세션(foreman-6). 관리자 410 일감, 사용자 지시 「문서 정리 C: 한계와 할 일 다시 가르기, 보고만」. 원고는 고치지 않았고 이 log 하나만 썼다.
> 읽은 판: FOREMAN `cc/foreman-6` HEAD `be6447a`(541이 읽은 `404aec9` 뒤로 `notion/`, `portfolio/`는 바뀌지 않았다). 인프라 저장소 `origin/main` `1172481`(541과 같은 판, fetch하지 않고 받아 둔 판을 `git show`로 읽었다).
> 541 = `log/foreman-4_limits_todo_split_20261117.md`. 기준은 사용자 한 줄 「안 하는 까닭을 한 줄로 쓸 수 있으면 한계, 못 쓰면 TODO」, 그리고 `docs/manuscript_rules.md` 1절.

## 0. 결론

| 저장소 | 묶음 | 541 한계 | 541 할 일 | 541 애매 | 새 한계(조건) | 새 TODO | 빼기 |
|---|---|---|---|---|---|---|---|
| 인프라 | 기술문서 `notion/` | 58 | 27 | 36 | **79(20)** | **42** | 0 |
| 인프라 | 포트폴리오 `portfolio/` | 38 | 17 | 15 | **51(10)** | **19** | 0 |
| **인프라 합계** | | **96** | **44** | **51** | **130(30)** | **61** | 0 |
| FOREMAN | 기술문서, 한계 절 안 | 67 | 70 | 53 | **83(15)** | **103** | 5 |
| FOREMAN | 기술문서, 결정 절 안(따로 셈) | 24 | 7 | 4 | **24(1)** | **11** | 0 |
| FOREMAN | 포트폴리오 | 0 | 0 | 0 | 0 | 0 | 0 |
| **FOREMAN 합계(한계 절 안)** | | **67** | **70** | **53** | **83(15)** | **103** | **5** |

- 애매 104줄(인프라 51, FOREMAN 한계 절 안 53)과 결정 절 안 애매 4줄을 모두 한계나 TODO로 갈랐다. 인프라 애매 51줄은 한계 36(그 가운데 조건 19), TODO 15로 갈렸다. FOREMAN 애매 53줄은 한계 20(조건 12), TODO 29, 빼기 5로 갈렸다. 한 줄을 둘로 나눈 것이 하나라 FOREMAN은 54가 된다.
- 541이 한계로 둔 줄 가운데 기록에서 까닭을 찾지 못한 줄은 TODO로 내렸다. 인프라 4줄, FOREMAN 한계 절 안 10줄, 결정 절 안 2줄이다.
- 541이 할 일로 둔 줄 가운데 기록에 안 하는 까닭이 분명한 줄은 한계로 올렸다. 인프라 2줄, FOREMAN 한계 절 안 6줄, 결정 절 안 1줄이다. FOREMAN에서 올린 줄은 대부분 커밋 `2a45269` 하나에서 나왔다. 그 커밋에서 사용자가 역할 권한을 기록만 하는 채로 두고 점검이 낸 다섯 가지 고치기도 하지 않기로 정했다.
- 541에서 애매의 큰 몫이던 「서버 한 대」, 「GPU 한 장」, 「바깥 도구의 성질」은 조건인 한계로 모두 넘어갔다. 그 조건이나 성질이 기록에 있었다(인프라 조건 30줄, FOREMAN 조건 16줄).
- 사람이 정할 경계 줄이 남는다. 「사용자가 정했지만 까닭이 기록에 없는 줄」(5-1절)은 사용자가 까닭을 한 줄 남기면 한계로 올라간다.

## 1. 숫자를 어떻게 셌나

541과 같은 셈법을 썼다. 글머리표 한 개가 한 줄이다. 한 줄이 한계와 할 일을 함께 말하면 쪼개 하나씩 셌다. 같은 내용이 여러 편에 나오면 편마다 셌다(겹침은 4절). 541의 줄 번호를 그대로 썼고, 서브에이전트 다섯이 원문을 열어 번호가 모두 맞는 것을 확인했다.

다른 점은 넷이다.
1. **까닭은 기록에서만 찾았다.** 원고 문장이 까닭을 말해도 그 까닭이 log, 커밋, docs, 근거 표시가 가리키는 곳, 코드 주석에 없으면 TODO로 쳤다. 그래서 541이 「확인 못 함」으로 두고 한계로 친 줄 일부가 내려갔다.
2. **「빼기」를 두었다.** 한계도 할 일도 아닌 줄이다. 이미 막았거나(FOREMAN 03_turns 187, 04_shell 98), 이미 대응했거나(08_handoff/02_summary 253), 잃는 것이 없거나(15_db 143 1,024자, 원문이 payload에 남는다), 맞는 동작을 설명한 줄이다(14_screen/01_store 234 지문은 탭 메모리). 541 1절이 「한계도 할 일도 아닌 문장은 세지 않았다」고 한 것과 같은 성격이다. 541이 이미 센 줄이라 숫자를 맞추려고 따로 적었다(FOREMAN 5줄).
3. **미룬 일은 TODO로 쳤다.** 「알려진 한계에는 안 하기로 한 것만 쓴다」(`docs/manuscript_rules.md` 1절)를 따랐다. 「~를 보고 정한다」, 「정하기 전」, 「확인하지 못했다, 알려 오면 고친다」처럼 기다리는 것만 적혀 있고 하면 무엇을 잃는지는 적혀 있지 않으면 TODO다. 하면 잃는 것이 기록에 있으면 미뤘다고 적혀 있어도 한계로 쳤다(예: 샌드박스는 일상 명령을 깨뜨릴 위험이 커서 시험 뒤로).
4. **결정만 있고 얻는 것이 기록에 없으면 TODO로 쳤다.** 기록이 스스로 「고른 까닭은 기록 없음」이라고 적은 줄이 그렇다(인프라 `bl/09_monitoring.md` 109~110, 116). 541은 이런 줄을 결정이 있다는 것만으로 한계로 쳤다.

판정은 서브에이전트 다섯이 묶음(인프라 기술문서 00~08과 09~14, 인프라 포트폴리오, FOREMAN 기술문서 00~08과 09~16)을 하나씩 맡아 했다. 묶음 사이에 판정이 갈린 줄은 내가 기록을 직접 열어 하나로 맞췄다. 인프라 Cloudflare 대시보드 줄(기술문서 01_path 48과 포트폴리오 04 46)은 TODO로 맞췄다. 마이그레이션 되돌림 줄(기술문서 08_build 68과 포트폴리오 07 47)은 조건 한계로 맞췄다. 묶음마다 3~8곳은 원문과 기록을 직접 열어 맞췄다. 그 가운데 고친 판정은 미룬 일 5줄, 결정만 있는 줄 5줄이다(위 3, 4). 서브에이전트가 한계로 올렸던 FOREMAN 01_placement 279와 창 크기 두 줄은 다시 TODO로 내렸다.

경로를 줄여 쓴다. 인프라는 `bl/` = `docs/history/build_log/`, `hist/` = `docs/history/`이고 모두 인프라 저장소 안의 경로다. FOREMAN 경로는 이 저장소 기준이다.

## 2. 편마다 표

「541」 칸은 한계/할 일/애매다. 「새」 칸은 한계(그 가운데 조건)/TODO이고, 빼기가 있으면 뒤에 붙였다.

### 2-1. 인프라 기술문서(29편, 한계 절 없는 5편은 뺌)

| 편 | 541 | 새 |
|---|---|---|
| 00_overview | 1/0/2 | 3(1)/0 |
| 01_server/01_network | 2/0/1 | 3(2)/0 |
| 01_server/02_os_driver | 2/0/2 | 3(2)/1 |
| 01_server/03_remote | 2/2/0 | 2(0)/2 |
| 02_nodes/01_vms | 0/3/2 | 2(2)/3 |
| 02_nodes/02_setup | 1/1/1 | 1(0)/2 |
| 02_nodes/03_roles | 1/2/2 | 2(0)/3 |
| 03_kubernetes | 1/2/2 | 2(0)/3 |
| 04_ingress | 3/0/1 | 3(0)/1 |
| 05_public/01_path | 2/0/2 | 3(1)/1 |
| 05_public/02_tls | 3/0/1 | 4(0)/0 |
| 06_gitops | 4/0/1 | 4(0)/1 |
| 07_registry | 4/2/0 | 4(0)/2 |
| 08_build | 2/1/4 | 3(1)/4 |
| 09_deploy/01_manifests | 4/0/1 | 5(1)/0 |
| 09_deploy/02_first_deploy | 2/0/2 | 4(2)/0 |
| 09_deploy/03_versions | 3/1/2 | 4(1)/2 |
| 10_database | 3/4/0 | 3(0)/4 |
| 11_gpu | 2/2/4 | 5(2)/3 |
| 12_monitoring/01_metrics | 4/3/0 | 5(0)/2 |
| 12_monitoring/02_logs | 3/1/0 | 1(0)/3 |
| 12_monitoring/03_dashboards | 3/1/1 | 3(0)/2 |
| 13_storage | 2/2/4 | 5(4)/3 |
| 14_operations | 4/0/1 | 5(1)/0 |
| **합계** | **58/27/36** | **79(20)/42** |

### 2-2. 인프라 포트폴리오(12편)

| 편 | 541 | 새 |
|---|---|---|
| 00_overview | 1/0/1 | 2(1)/0 |
| 01_kubeadm | 2/0/2 | 4(1)/0 |
| 02_two_nics | 0/4/1 | 1(1)/4 |
| 03_one_door | 4/0/1 | 4(0)/1 |
| 04_tunnel | 4/0/2 | 5(1)/1 |
| 05_tls | 2/0/1 | 3(0)/0 |
| 06_gpu | 4/1/2 | 6(1)/1 |
| 07_delivery | 4/1/0 | 4(1)/1 |
| 08_monitoring | 4/2/0 | 3(0)/3 |
| 09_scale_out | 2/0/2 | 4(1)/0 |
| 10_docs | 3/0/0 | 3(1)/0 |
| 11_limits | 8/9/3 | 12(1)/8 |
| **합계** | **38/17/15** | **51(10)/19** |

09_scale_out 46줄 「지난 비용」 1은 541처럼 따로 두었다.

### 2-3. FOREMAN 기술문서(50편, 한계 절도 결정 절 줄도 없는 편은 뺌)

| 편 | 한계 절 541 | 한계 절 새 | 결정 절 541 | 결정 절 새 |
|---|---|---|---|---|
| 00_foreman | 0/0/0 | 0/0 | 0/1/0 | 0/1 |
| 01_structure | 0/1/1 | 1(1)/1 | | |
| 01_structure/01_placement | 1/5/1 | 2(1)/5 | 1/0/1 | 1/1 |
| 01_structure/02_startup | 0/1/0 | 0/1 | | |
| 02_ingest | 0/0/0 | 0/0 | 1/0/0 | 1/0 |
| 02_ingest/01_transcript | 1/2/0 | 1/2 | 1/0/1 | 1/1 |
| 02_ingest/02_hooks | 0/2/2 | 2(1)/2 | | |
| 02_ingest/03_turns | 1/0/1 | 1/0, 빼기 1 | | |
| 02_ingest/04_bus | 1/3/1 | 1/4 | 2/1/0 | 2/1 |
| 03_session | 3/2/2 | 5(2)/2 | 1/0/0 | 1/0 |
| 04_approval/01_rules | 1/1/2 | 3/2(363을 둘로 나눔) | 2/0/0 | 2/0 |
| 04_approval/02_flow | 1/2/1 | 1/3 | 1/0/0 | 1/0 |
| 04_approval/03_summary | 1/4/2 | 0/7 | | |
| 05_roles | 5/2/0 | 7/0 | 0/1/0 | 0/1 |
| 05_roles/01_roles | 1/1/1 | 2/1 | 0/1/1 | 1(1)/1 |
| 05_roles/02_guards | 3/4/2 | 8/1 | 3/1/0 | 4/0 |
| 05_roles/03_keys | 3/1/0 | 2(1)/2 | | |
| 06_sessions | 0/0/0 | 0/0 | 1/0/0 | 0/1 |
| 07_merge | 0/0/0 | 0/0 | 1/1/0 | 1/1 |
| 07_merge/01_card | 0/0/0 | 0/0 | 2/0/0 | 2/0 |
| 07_merge/02_reconcile | 1/1/2 | 0/4 | | |
| 08_handoff | 3/0/0 | 3/0 | | |
| 08_handoff/01_loss | 1/2/1 | 2/2 | | |
| 08_handoff/02_summary | 1/1/1 | 1/1, 빼기 1 | | |
| 08_handoff/03_promote | 3/1/1 | 3(1)/2 | | |
| 08_handoff/04_move | 3/1/1 | 2/3 | | |
| 09_dispatcher | 0/0/0 | 0/0 | 1/0/0 | 1/0 |
| 09_dispatcher/01_plan | 2/0/2 | 2/2 | | |
| 09_dispatcher/02_note_wake | 1/2/1 | 1/3 | 0/0/1 | 0/1 |
| 09_dispatcher/03_overlap | 3/1/2 | 3/3 | | |
| 09_dispatcher/04_managers | 1/0/2 | 2(1)/1 | | |
| 10_scribe | 1/3/0 | 1/3 | | |
| 10_scribe/01_room | 0/0/1 | 0/1 | 2/0/0 | 1/1 |
| 10_scribe/02_postit | 1/2/0 | 1/2 | | |
| 10_scribe/03_evidence | 3/2/2 | 2(1)/5 | | |
| 10_scribe/04_notion | 0/5/0 | 0/5 | | |
| 11_notify | 2/3/1 | 2/4 | 1/0/0 | 1/0 |
| 12_pipeline | 3/3/3 | 4(1)/5 | 0/1/0 | 0/1 |
| 13_usage | 0/2/6 | 4(4)/4 | | |
| 14_screen | 3/0/0 | 3/0 | | |
| 14_screen/01_store | 2/3/3 | 0/7, 빼기 1 | | |
| 14_screen/02_office | 1/1/3 | 2(1)/3 | | |
| 14_screen/04_shell | 4/2/1 | 3/3, 빼기 1 | | |
| 14_screen/05_check | 1/1/1 | 1/2 | | |
| 15_db | 5/2/2 | 5/3, 빼기 1 | 1/0/0 | 1/0 |
| 15_db/02_migrate | 0/0/0 | 0/0 | 2/0/0 | 2/0 |
| 16_tests | 0/1/1 | 0/2 | 1/0/0 | 1/0 |
| **합계** | **67/70/53** | **83(15)/103, 빼기 5** | **24/7/4** | **24(1)/11** |

FOREMAN 포트폴리오 16편은 541처럼 한계 절이 없어 0이다. 541 6-5절의 절 밖 본문 줄(한계 25, 할 일 4, 애매 6)은 이번 범위가 아니라 다시 보지 않았다.

## 3. 한계로 판정한 줄

꼴: 편 줄: 한 줄 까닭(조건이면 「조건:」) / 기록. 「같음」은 위 줄과 까닭과 기록이 같다는 뜻이다.

### 3-1. 인프라 기술문서(79, 조건 20)

- 00_overview 39: 조건: 이 프로젝트가 쓰는 물리 서버는 한 대다 / `hist/notion_hardware_20261116.md` 12, `bl/01_cluster.md` 699
- 00_overview 40: 「컨트롤 플레인 1대와 워커 여러 대」가 CKA 시험 범위에 든 구조라 그렇게 골랐다 / `bl/01_cluster.md` 136
- 00_overview 41: 터널이 ingress-nginx 하나만 가리켜 앱을 더해도 Ingress만 더하고 포트를 열지 않는다 / `bl/03_cloudflare_tunnel.md` 143~153
- 01_network 33: 공유기 포트를 더 열면 인증 없이 인터넷에 드러나는 보안 위험이 있다 / `hist/cloudflare_tunnel_vcluster.md` 77, `bl/03_cloudflare_tunnel.md` 84
- 01_network 34: 조건: 사무실 서버 여럿이 함께 쓰는 장비라 이 저장소가 맡지 않는다 / `hist/notion_hardware_20261116.md` 3, 9, `docs/style_guide.md` 91
- 01_network 35: 조건: 물리 서버 한 대 / `hist/notion_hardware_20261116.md` 12
- 02_os_driver 49(앞 문장): 조건: 이 서버에서는 드라이버 자동 추천 설치가 실패했다 / `hist/notion_hardware_20261116.md` 23, `bl/00_server.md` 270
- 02_os_driver 50: 셀 단위로 도는 Jupyter에는 명령을 감싸는 flock이 맞지 않아 코드 안 잠금을 골랐다 / `hist/notion_hardware_20261116.md` 35
- 02_os_driver 51: 조건: GPU가 한 장이다 / `hist/notion_hardware_20261116.md` 16, 35
- 03_remote 37: 01_network 33과 같음
- 03_remote 38(앞 문장): 같은 까닭으로 서비스를 바깥에 열지 않고 SSH 터널로 쓴다 / `hist/cloudflare_tunnel_vcluster.md` 72, 77, `hist/notion_hardware_20261116.md` 40
- 01_vms 47: 조건: Vagrant는 이미 만든 VM에 프로비저너를 다시 돌리지 않는다 / `bl/01_cluster.md` 73
- 01_vms 48: 조건: 물리 서버 한 대 / `bl/01_cluster.md` 699
- 02_setup 47: 돌고 있는 노드와 같은 판을 쓰려고 꾸러미 판까지 적었다 / `cluster/setup-node.sh` 27
- 03_roles 39: 노드가 죽으면 무엇이 멈추는지 노드 이름으로 말하려고 역할을 고정했다 / `bl/08_scale_out.md` 129, 434, `cluster/label-nodes.sh` 7~8
- 03_roles 42: 00_overview 40과 같음
- 03_kubernetes 51: 00_overview 40과 같음
- 03_kubernetes 53: Harbor 공개 이름이 Access로 새지 않게 CoreDNS에서 이름을 고쳐 쓴다 / `platform/coredns/configmap.yaml` 3~8
- 04_ingress 51: Calico가 노드마다 BGP를 쓰고 있어 BGP를 하나 더 두지 않고 L2를 쓴다 / `platform/metallb/values.yaml` 2~3
- 04_ingress 53: 업스트림 인자 순서가 바뀌면 apply를 멈추게 한 안전장치다 / `platform/ingress-nginx/overlay/kustomization.yaml` 10, `bl/02_metrics_storage_ingress.md` 383
- 04_ingress 54: platform은 ArgoCD보다 먼저 깐 기반이다 / `bootstrap/root-app.yaml` 13
- 01_path 47: 00_overview 41과 같음
- 01_path 49: 조건: cloudflared는 설정을 켜질 때만 읽는다 / `apps/cloudflared/configmap.yaml` 3
- 01_path 50: 사설망은 호스트와 VM만 있는 망이고 터널이 깨졌을 때 숨구멍이다 / `apps/monitoring/ingress.yaml` 6, `apps/cloudflared/README.md` 24~25
- 02_tls 57: 클러스터 안 통신이고 터널이 암호화된 통로라 원점 인증서 확인을 끈다 / `bl/03_cloudflare_tunnel.md` 160, `hist/notls_check_20261117.md` 20~22
- 02_tls 58: 터널이 이미 HTTPS로 받아 리다이렉트 루프를 피한다 / `bl/05_harbor.md` 218, `bl/07_project_deploy.md` 436
- 02_tls 59: 비밀값 정책, 커밋되는 매니페스트에 실제 값을 박지 않는다 / `bl/03_cloudflare_tunnel.md` 188
- 02_tls 60: 운영 도구만 사설망에서도 그 이름으로 불러 인증서를 두고 앱 둘은 엣지 TLS로 충분하다 / `bl/07_project_deploy.md` 457
- 06_gitops 60: 03_roles 39와 같음
- 06_gitops 61: git에서 지운 것이 바로 사라지면 네임스페이스와 사람이 넣은 Secret까지 지워진다 / `bl/07_project_deploy.md` 80, 261
- 06_gitops 62: 스키마 배포 중 꺼 둔 자동 Sync를 태그 커밋 하나로 루트가 도로 켜지 않게 한다 / `bootstrap/root-app.yaml` 8~10
- 06_gitops 63: 02_tls 59와 같음 / `bl/04_argocd.md` 51, 58~59
- 07_registry 51: 03_roles 39와 같음 / `bl/08_scale_out.md` 129
- 07_registry 52: 앱 이미지는 앱 저장소 커밋에서 다시 빌드할 수 있다 / `apps/harbor-backup/README.md` 15~16
- 07_registry 55: 02_tls 59와 같음 / `bl/05_harbor.md` 485
- 07_registry 56: 분산 저장소는 무겁고 VM이 한 서버 위에 있어 실익이 없다 / `bl/05_harbor.md` 232~235
- 08_build 62: 03_roles 39와 같음 / `bl/06_jenkins.md` 504
- 08_build 65: 기한을 관리할 체계 없이 만료를 두면 조용히 끊긴다 / `bl/06_jenkins.md` 502
- 08_build 68: 조건: 마이그레이션 도구는 적용된 버전을 다시 돌리지 않는다 / `apps/runshoes/README.md` 52, `apps/petmint/README.md` 27
- 01_manifests 47: app 노드가 둘이라 세 번째 파드가 갈 곳이 없어 옛 파드를 먼저 내린다 / `apps/petmint/app/deployment.yaml` 4~6
- 01_manifests 48: 노드 하나가 죽어도 다른 파드가 받게 같은 노드 배치를 막았다 / 같은 파일 1~4, 7
- 01_manifests 49: 조건: envFrom 값은 떠 있는 파드에 들어가지 않는다 / `apps/petmint/app/configmap.yaml` 28
- 01_manifests 50: Ready가 DB까지 보게 바꾼 값이다 / `apps/runshoes/app/deployment.yaml` 3, 115
- 01_manifests 51: 한 파드씩 바꾸는 롤링이라 웹소켓이 한 번 끊기고 프런트가 다시 붙는다 / 같은 파일 2, 4
- 02_first_deploy 44: 02_tls 59와 같음 / `apps/petmint/scripts/create-secrets.sh` 2~3
- 02_first_deploy 45: 조건: Harbor 로봇 비밀번호는 만들 때 한 번만 보인다 / `bl/06_jenkins.md` 174
- 02_first_deploy 46: 네임스페이스를 ArgoCD가 가지면 prune 한 번에 Secret까지 사라지고, NFS는 sudo가 필요하다 / `bl/07_project_deploy.md` 74~80, `apps/petmint/README.md` 50
- 02_first_deploy 47: 조건: 앱 인증 방식상 서명 키를 바꾸면 발급된 토큰이 모두 무효다 / `apps/runshoes/scripts/create-secrets.sh` 10
- 03_versions 75: 배포를 막는 장치라 사람이 직접 끈다(사용자 결정) / `apps/runshoes/runbooks/catalog-v4-v5.md` 37
- 03_versions 76: 조건: 필드를 지우는 patch라 managedFields에 자국이 남지 않는다 / `apps/runshoes/runbooks/v21-grafana-compare-views.md` 167
- 03_versions 77: 공개 사이트를 멈추지 않고 덤프하고 그 구간을 짧게 둔다 / `apps/runshoes/runbooks/auth-v3.md` 28~29
- 03_versions 79: 공개 경로는 Access가 막아 kubelet과 같은 노드 길로 이미지를 받는다 / `apps/runshoes/scripts/check-image-migrations.sh` 3~5, 11
- 10_database 75: Operator는 부품과 메모리가 늘어 쓰지 않았다 / `bl/08_scale_out.md` 132~137
- 10_database 76: limits 여유가 가장 큰 노드를 골랐다 / `apps/runshoes/mysql/statefulset.yaml` 6~7
- 10_database 79: 계정은 초기화 Job이 Secret 값으로 다시 만든다 / `apps/petmint/backup/cronjob.yaml` 2~3
- 11_gpu 51: 조건: GPU 한 장 / `bl/03_cloudflare_tunnel.md` 701
- 11_gpu 52: 조건: 물리 서버 한 대 / `bl/kubernetes_install.md` 198
- 11_gpu 53(첫 문장): GPU 패스스루는 위험이 커 하지 않았다 / `bl/kubernetes_install.md` 117, 200
- 11_gpu 53(둘째 문장): 바깥 이미지를 GPU 권한으로 띄우는 일이라 사람이 한다 / `bl/09_monitoring.md` 122, 124
- 11_gpu 56: 그 대역은 Vagrantfile에 고정 주소로 박혀 VM을 다시 만들어도 바뀌지 않는다 / `apps/petmint/app/configmap.yaml` 21~22
- 01_metrics 37: 03_roles 39와 같음 / `bl/09_monitoring.md` 57~60
- 01_metrics 39(할 일에서 올림): 앱에 /metrics를 붙이는 일은 앱 코드를 고치는 일이라 하지 않았다 / `bl/09_monitoring.md` 50~51
- 01_metrics 41: 11_gpu 53 둘째 문장과 같음
- 01_metrics 42: 01_path 50과 같음
- 01_metrics 43: 노드 디스크를 넘지 않게 보존 크기를 묶었다 / `bl/09_monitoring.md` 113~117
- 02_logs 36: 03_roles 39와 같음
- 03_dashboards 52: 대시보드를 저장소 파일로 두기로 고른 대가다 / `bl/09_monitoring.md` 32, 34
- 03_dashboards 53: 운영 쓰기에 짐을 주지 않으려고 Replica를 읽는다 / `bl/09_monitoring.md` 66, 70
- 03_dashboards 54: 질문과 답 원문을 막으려고 칸 단위 권한을 준다 / `bl/09_monitoring.md` 67, 70
- 13_storage 47: 07_registry 56과 같음 / `bl/05_harbor.md` 228~235
- 13_storage 48: 조건: local-path 기본 회수 정책이 Delete다 / `platform/harbor/pvc-w3.yaml` 6
- 13_storage 49: 조건: local-path와 NFS는 크기를 강제하지 않는다 / `apps/monitoring/README.md` 109
- 13_storage 51: 조건: 물리 서버 한 대 / `bl/kubernetes_install.md` 198
- 13_storage 54: 조건: 앱이 기동할 때 읽고, 복사본을 두지 않는 것은 어긋남을 막으려는 것이다 / `apps/petmint/data/nfs.yaml` 6~7
- 14_operations 65: main이 곧 운영이라는 결정의 대가다 / 인프라 `CLAUDE.md` 9, 26
- 14_operations 66: 조건: 기계 점검은 파일과 줄 범위만 본다 / `docs/style_guide.md` 73
- 14_operations 67: 같은 규칙을 저장소마다 따로 두면 고칠 때마다 어긋난다 / 커밋 `cedba9b` 본문
- 14_operations 68: 노션은 GitHub의 사본이라 push된 판이 기준이다 / FOREMAN `docs/12_scribe.md` 154
- 14_operations 69: 06_gitops 62와 같음

### 3-2. 인프라 포트폴리오(51, 조건 10)

- 00 49: 조건: 물리 서버 한 대 / 인프라 `README.md` 3, `bl/01_cluster.md` 699
- 00 50: 기술문서 00_overview 41과 같음, 터널은 수동 Sync로 지킨다 / `apps/cloudflared/app.yaml` 4~7
- 01 39: 조건: 물리 서버 한 대 / `bl/01_cluster.md` 699
- 01 40: 기술문서 00_overview 40과 같음
- 01 41: 분산을 보이려고 VM을 여럿 두어 남은 메모리를 모델과 학습이 나눠 쓴다 / `bl/01_cluster.md` 27, 136~138
- 01 42: 다시 만들 때 같은 판을 깔려고 판 기록 파일을 둔다(사람 결정) / `hist/human_answers_20261116.md` 19
- 02 36: 조건(경계): 바깥 인터넷으로 나가는 관리망은 vagrant-libvirt가 VM을 만들 때 붙인다 / `bl/01_cluster.md` 37
- 03 47: 문을 하나로 두면 새 앱은 Ingress만 더하고, 두 벌로 늘린 것은 하나가 죽어도 받게 하려는 것이다 / `bl/03_cloudflare_tunnel.md` 153, `platform/ingress-nginx/overlay/deployment-patch.yaml` 2, 24
- 03 48: 기술문서 04_ingress 51과 같음
- 03 50: 기술문서 04_ingress 54와 같음
- 03 51: 이 포트로 붙던 기존 경로를 살려 둔다 / `platform/ingress-nginx/overlay/service-patch.yaml` 2
- 04 41: 00 50과 같음
- 04 42: 잘못된 커밋이 바깥 길 전체를 끊지 않게 수동 Sync로 둔다(사용자 결정) / `apps/cloudflared/README.md` 21~23
- 04 43: 터널이 끊겨도 고칠 길을 남겨 둔다 / `apps/cloudflared/README.md` 24~25
- 04 44: 그 길의 대가로 사설망 주소는 Access를 거치지 않는다 / 같은 곳, `bl/09_monitoring.md` 210
- 04 45: 조건: cloudflared는 설정을 켜질 때만 읽는다 / `apps/cloudflared/configmap.yaml` 3
- 05 31: 기술문서 02_tls 57과 같음
- 05 32: 기술문서 02_tls 58과 같음
- 05 33: 기술문서 02_tls 59와 같음 / 인프라 `CLAUDE.md` 47
- 06 37: 기술문서 11_gpu 53 첫 문장과 같음, 호스트 추론 서버를 계속 써야 했다 / `bl/kubernetes_install.md` 117, 200
- 06 38: 같음
- 06 39(앞 두 문장): 기술문서 11_gpu 53 둘째 문장과 같음
- 06 40: 조건: 물리 서버 한 대 / `bl/kubernetes_install.md` 198
- 06 41: 기술문서 11_gpu 56과 같음
- 06 42: 다른 PC와 GPU 메모리를 나눠 쓰려고 모델 유지 시간을 바꾸지 않는다(사용자 결정) / 인프라 `CLAUDE.md` 34
- 07 45: 03 50과 같음
- 07 46: 사용자 지시로 자동 Sync, 스키마 배포 때만 끄고 한다 / `apps/runshoes/app.yaml` 5, 9~10, `bl/07_project_deploy.md` 260
- 07 47: 조건: 기술문서 08_build 68과 같음 / `apps/runshoes/README.md` 52, 64~65
- 07 49: 기술문서 03_roles 39와 같음
- 08 39: 설정을 저장소에 남기려고 차트를 버리고 손으로 쓴 매니페스트를 골랐다 / `bl/09_monitoring.md` 31~34
- 08 40: 같은 결정의 대가 / `bl/09_monitoring.md` 34
- 08 42: 기술문서 03_dashboards 53, 54와 같음
- 09 43: 기술문서 01_manifests 47과 같음 / `apps/petmint/app/deployment.yaml` 3~6
- 09 44: 기술문서 03_roles 39와 같음
- 09 45: PV가 이미 w1에 묶여 있고 고치면 Primary가 재시작돼 손대지 않았다 / `bl/08_scale_out.md` 378, `apps/runshoes/mysql/statefulset.yaml` 6~7
- 09 47: 조건: 물리 서버 한 대 / `bl/08_scale_out.md` 436
- 10 50: 옛 기록은 지금과 다를 수 있어 문장마다 근거를 단다 / 인프라 `docs/README.md` 3, `docs/style_guide.md` 75
- 10 51: 줄 번호는 읽은 커밋 기준이라는 규칙이다 / `docs/style_guide.md` 61, 73
- 10 52: 조건: 기계 점검은 파일과 줄 범위만 본다 / `docs/style_guide.md` 73
- 11 17: 조건: 물리 서버 한 대 / 인프라 `README.md` 3
- 11 18: 기술문서 00_overview 40과 같음
- 11 20: 기술문서 03_roles 39와 같음
- 11 25: 기술문서 02_tls 57과 같음
- 11 26: 기술문서 02_tls 58과 같음
- 11 27: 00 50과 같음
- 11 31: 기술문서 02_tls 59와 같음 / 인프라 `README.md` 14
- 11 32(앞): 06 37과 같음
- 11 33(앞): 기술문서 10_database 75와 같음 / `docs/runbooks/mysql-replica.md` 4
- 11 33(끝 문장, 할 일에서 올림): 앱 트래픽까지 옮기는 진짜 전환은 운영 쓰기를 멈춰야 하고 되돌리는 데 전환이 한 번 더 들어 하지 않았다 / `bl/08_scale_out.md` 371
- 11 35: 기술문서 06_gitops 61과 같음
- 11 43: 기술문서 07_registry 52와 같음

### 3-3. FOREMAN 기술문서, 한계 절 안(83, 조건 15)

- 01_structure 249(GitLab 웹훅): 조건: 실제 흐름에 GitLab이 없다(GitHub에서 Jenkins로) / `README.md` 804, `log/stage8_cicd_result.md` 14
- 01_placement 226(하루치): 디스크를 지키려 binlog를 끄고 트랜스크립트로 다시 만든다 / `log/stage1_bridge_db_result.md` 64
- 01_placement 283: 조건: 물리 서버가 하나다 / `README.md` 610
- 01_transcript 196(바이트 거름): 트랜스크립트 용량의 76%가 api-request라 미리 거른다 / `README.md` 191, `log/01_kickoff_result.md` 104
- 02_hooks 142(원본과 사용자 설정): 조건: CC는 사용자 설정 파일만 읽는다 / `log/foreman-7_hook_timeout_20261115.md` 22, 커밋 `883c4c9`
- 02_hooks 142(시험이 PC 설정을 보지 않음, 할 일에서 올림): 홈 설정은 기계마다 달라 시험에 넣지 않았다 / `log/foreman-7_hook_timeout_20261115.md` 22
- 03_turns 185: 순서는 그대로이고 BIGINT라 빈틈 없는 id를 문제 삼지 않았다 / `log/stage2_transcript_result.md` 76
- 04_bus 131: 모양 모르는 비밀은 가리기로 못 잡아 도구 결과 본문을 저장하지 않는다(사용자 확인) / `README.md` 833, `log/stage2_transcript_result.md` 85
- 03_session 402(화면 판정): 조건: CC 상태 파일은 창 종류를 가르지 않는다 / `README.md` 181
- 03_session 402(자동 압축 창): 조건: 그 창은 일부러 띄울 수 없다 / `log/prompt_vs_dialog_20261113.md` 39
- 03_session 406: 같은 세션에 넣는다는 전제로 tmux send-keys를 고른 대가다 / `README.md` 153~156
- 03_session 408: 늘 공백을 붙였더니 7건이 조용히 글로 가서 승인 규칙 ask만 막는다 / `bridge/inject.py` 139~140, 148~150
- 03_session 410: 이름과 소켓을 풀지 않고 본문으로 짝짓는다 / `log/alerts_denied_xmsg_bang_20261109.md` 19
- 01_rules 363(해석기 본문): 해석기 본문을 넓게 보면 11-05에 뺀 오탐이 돌아온다 / `log/foreman-6_silent_delete_20261115.md` 20, 56
- 01_rules 363(hook은 글만 봄): 다 막는 샌드박스는 일상 명령을 깨뜨릴 위험이 가장 크다 / 같은 log 50, 57
- 01_rules 365: 알림만 하고 합치기 흐름을 끊지 않는다 / 같은 log 54
- 02_flow 312(실패하면 통과): 브리지가 꺼지면 CC가 스스로 정한다 / `scripts/foreman-decide.sh` 5
- 05_roles 83(앞): 걸린 것이 대부분 데이터 만들기라 해석기 속 소스 고치기와 가를 수 없다 / `log/coder_c_wave2_20261111.md` 99
- 05_roles 83(뒤): 「모름」을 거부로 바꾸면 스크래치 쓰기가 다 걸린다 / `log/inspect_roleguard_20261114.md` 123
- 05_roles 146(둘째): 걸린 정당한 일이 모두 사람이 시킨 일이었다 / 같은 log 89, 커밋 `2a45269`
- 05_roles 146(셋째): 화면이 모듈을 읽자마자 값을 쓴다 / `log/foreman-6_roles_one_place_20261115.md` 20~22
- 05_roles 146(넷째): 05_roles 83 앞과 같음
- 05_roles 146(조사 제안, 할 일에서 올림): 사용자가 점검의 다섯 고치기를 하지 않기로 정했다 / 커밋 `2a45269`, `log/manager318_overhead_20261114.md` 115
- 05_roles 148(할 일에서 올림): 이틀치 걸림 74건이 모두 정당했고 프로젝트별 표가 먼저다 / `log/inspect_roleguard_20261114.md` 11, 84
- 01_roles 266(관리자): 사용자가 기록만 하기로 정했다 / 커밋 `2a45269`
- 01_roles 266(서기 등): 같음
- 02_guards 190: 01_rules 363(hook은 글만 봄)과 같음 / `log/repo_scope_readonly_20261109.md` 9, 29
- 02_guards 312(실패하면 통과): 02_flow 312와 같음
- 02_guards 314(해석기): 05_roles 83 앞과 같음
- 02_guards 314(제안, 할 일에서 올림): 05_roles 146 조사 제안과 같음
- 02_guards 316: 그림은 셸로만 넣을 수 있어 막으면 헛걸림이 크다 / `log/inspect_roleguard_20261114.md` 113
- 02_guards 318: 점검 제안 4번, 사용자가 하지 않기로 정했다 / 커밋 `2a45269`, 같은 log 19
- 02_guards 320(할 일에서 올림): 점검 제안 3번, 같음 / 같은 log 18
- 02_guards 322(할 일에서 올림): 05_roles 148과 같음
- 03_keys 113: 조건: 모든 세션이 같은 유닉스 사용자로 돈다 / `log/coder_c_wave2_20261111.md` 24
- 03_keys 244: 04_bus 131과 같음
- 08_handoff 110(첫째): 2판 결정(문서를 읽게 한다)의 대가다 / `docs/11_handoff_v2.md` 3
- 08_handoff 110(둘째): 그래서 서기의 문서 맞추기가 핵심이 된다 / `docs/11_handoff_v2.md` 96
- 08_handoff 110(셋째): 기계가 뒤집힌 결정을 되살릴 수 있어 사람이 관문이다 / `log/handoff_v2_d_result.md` 65~70
- 01_loss 318(재현율): 사용자가 정밀도 0.91이면 충분하고 사람이 관문이라 했다 / `log/handoff_v2_d_result.md` 57~60
- 01_loss 318(뒤집힘): 같은 결정에 남긴 알려진 약점이다 / 같은 log 65~70
- 02_summary 251: 요약은 컨텍스트를 든 그 세션이 쓴다 / `docs/11_handoff.md` 8, 103
- 03_promote 278(메모리): 조건: CC 메모리는 git 밖이다 / `log/handoff_v2_c_result.md` 19
- 03_promote 280: skipped에 이유가 있으면 통과로 정했다 / 같은 log 18
- 03_promote 282(세션 자신): 02_summary 251과 같음
- 04_move 194: 옛 API를 이어 바뀐 길을 작게 했다 / `log/coder_c_wave2_20261111.md` 100
- 04_move 196: 끝난 세션은 문서를 쓸 세션이 없다 / `docs/11_handoff_v2.md` 82
- 01_plan 308(앞): 교장은 계획만 내니 도구를 읽기만 열었다 / `docs/11_foreman_dispatch.md` 21, 124
- 01_plan 310(겹침을 막지 않음): 일부러 둘에게 시킬 수 있어 막지 않는다 / `bridge/overlap.py` 8
- 02_note_wake 262(텔레그램에서 시작 없음): 링크로 화면에 들어오는 것이 사람 확인 단계다 / `docs/14_dispatcher_note_wake.md` 76(경계, 6절)
- 03_overlap 288(한글 낱말): 형태소 분석 없이는 틀 글 낱말이 너무 겹친다 / `log/overlap_alert_20261106.md` 35
- 03_overlap 288(조사형 겹침은 띠만): 헛경보를 줄이려고 둘 다 실제로 고쳤을 때만 텔레그램을 보낸다 / `log/foreman-2_screen_ctx_switch_overlap_20261109.md` 33
- 03_overlap 288(관리자 빼기): 스키마를 바꾸지 않으려고 골랐다 / `log/judge_three_20261113.md` 24~25
- 04_managers 320: 조건: 입력 칸에 넣은 것까지만 확인할 수 있다 / `log/coder_c_wave2_20261111.md` 102
- 04_managers 322: 판에 박힌 단계는 기계가, 판단은 관리자가 한다 / `log/plan_structure_20261111.md` 26
- 10_scribe 119: 조사 검토는 비용이 1.5배라 portfolio와 trim에만 쓴다 / `docs/12_scribe.md` 114
- 02_postit 130: LLM 판정 대신 비용 0인 정규식을 쓴다 / `log/foreman-6_postit_proposal_20261115.md` 65~66
- 03_evidence 180(모양 모르는 비밀): 조건: 가리개 방식에 남는 위험이다 / `bridge/mask.py` 10~11
- 03_evidence 186(뜻은 사람이 판단): 기계는 확정할 수 있는 것만 보고 뜻 맞대기는 비용 때문에 조사 몫으로 좁혔다 / `docs/12_scribe.md` 104, 114, `bridge/evidence.py` 1, 8
- 11_notify 144(프로젝트 칸 없음): 새 표나 마이그레이션 없이 묶음을 더하려고 / `log/notify_relay_20261112.md` 45
- 11_notify 293(미분류도 보냄): 기다리는 사람이 있는 알림이다 / `bridge/notify.py` 366
- 12_pipeline 301: 운영 도구가 바깥 인증 관문 뒤라 웹훅이 닿지 않고 토큰 없이 로컬 push를 본다 / `log/stage8_cicd_result.md` 16, 99, `README.md` 621~628
- 12_pipeline 310: 같은 선택 / `log/stage8_cicd_result.md` 99, 210
- 12_pipeline 311: 조건: ArgoCD 웹훅 끊김은 FOREMAN이 직접 보기 어렵다 / `log/stage8_cicd_result.md` 61
- 12_pipeline 312: 전권 토큰을 두지 않는다 / `log/stage8_cicd_result.md` 99
- 13_usage 24: 조건: CC 기록에서 서브에이전트 출력은 응답 시작 때 값이다 / `docs/15_usage.md` 11
- 13_usage 27: 조건: 금액은 claude.ai 설정에만 있다 / `docs/15_usage.md` 99
- 13_usage 28: 조건: 웹, 다른 PC, CC 안쪽 호출은 볼 수 없다 / `docs/15_usage.md` 14
- 13_usage 354(한도 셈법): 조건: Anthropic이 한도를 토큰으로 공개하지 않는다 / `docs/15_usage.md` 5, 18
- 14_screen 25, 27, 29(셋): UI는 번들러 없는 순수 JS라 빌드할 것이 없다 / `README.md` 608, `bridge/uiver.py` 1~6
- 02_office 390: 조건: 라이선스가 맞는 에셋에 정면 그림 한 장뿐이다 / `log/stage10_office_result.md` 91, 108
- 02_office 394: 사용자가 도형 테마를 쓰지 않는다 / `bridge/static/js/office.js` 80
- 04_shell 299: 어느 꼴로 칠지는 사용자가 고를 일이다 / `log/stage7_terminal_result.md` 37
- 04_shell 301: 클립보드 애드온 의존과 브라우저 권한 문제를 피했다 / `log/d2_terminal_select_20261111.md` 12
- 04_shell 302: CC가 TUI라 입력을 tmux로 넣는 뼈대다 / `README.md` 151~153
- 05_check 270(버튼 아닌 글 인용): 기계가 가를 수 없고 맞대면 헛걸림이 90%를 넘는다 / `log/foreman-6_screen_text_sync_proposal_20261115.md` 36, 161
- 15_db 88: 값이 단계마다 늘어 ALTER를 피했다 / `migrations/0001_init.sql` 5
- 15_db 100(event에 FK 없음): hook이 먼저 오고 행마다 부모 조회를 피한다 / `migrations/0001_init.sql` 152~153
- 15_db 143(api-request): 용량의 80%를 넘고 대화 복원에 필요 없다 / `README.md` 829
- 15_db 143(도구 결과 본문): 04_bus 131과 같음
- 15_db 145: hook 이벤트는 트랜스크립트에 없어 다시 만들면 사라진다 / `README.md` 831

### 3-4. FOREMAN 기술문서, 결정 절 안(24, 조건 1)

- 01_placement 190: 01_placement 226과 같음
- 02_ingest 38: hook 이벤트는 트랜스크립트로 다시 만들 수 없다 / `log/stage2_transcript_result.md` 75, `README.md` 831
- 01_transcript 176(120일 지난 본문): 04_bus 131과 같음 / `bridge/transcript/lookup.py` 3
- 04_bus 44: 쓰는 쪽을 하나로 두어 id 차례를 들어온 차례로 맞춘다 / `log/stage1_bridge_db_result.md` 62
- 04_bus 85(기록 실패 원칙): 기록 실패가 판정이나 넣기를 바꾸지 않는다 / `bridge/approvals.py` 277, `log/stage1_bridge_db_result.md` 63
- 03_session 287: 폭 없는 공백은 제출되지 않아 공백 한 칸을 골랐다 / `log/stage3_inject_result.md` 69
- 01_rules 274: 셸 파서 라이브러리가 GPL이다 / `README.md` 338
- 01_rules 276: 모를 때 막으면 heredoc과 긴 명령이 다 막힌다 / `README.md` 338
- 02_flow 150: PermissionRequest가 CC의 공식 자리다 / `log/stage5_approval_result.md` 26~30
- 01_roles 138(원본 폴더 조사): 조건: 원본 폴더에 다른 세션의 변경이 섞여 가를 수 없다 / `log/foreman-6_inspector_close_20261115.md` 55
- 02_guards 125: 05_roles 83 앞과 같음
- 02_guards 127: 05_roles 83 뒤와 같음
- 02_guards 137(할 일에서 올림): 05_roles 146 조사 제안과 같음
- 02_guards 178: heredoc 본문(커밋 글)은 막지 않는다 / `log/repo_scope_readonly_20261109.md` 17
- 07_merge 65: 원본 폴더에 중간 상태를 남기지 않으려고 rebase 뒤 ff-only를 쓴다 / `docs/11_worktree.md` 15
- 01_card 97: 두 검사가 한 자리를 쓰던 헛걸림을 없앴다 / `log/foreman-5_docs_check_20261117.md` 91
- 01_card 107: 지시 22에서 줄 번호를 붙이지 않기로 했다 / 같은 log 10, 220
- 09_dispatcher 37: 01_plan 308 앞과 같음
- 01_room 244(저절로 띄우지 않음): 초안이 쌓이면 검토 빚이 되고 문서 충돌이 난다 / `docs/12_scribe.md` 69
- 11_notify 270: 02_note_wake 262와 같음
- 15_db 72: 01_placement 226과 같음
- 02_migrate 64: SQL 나누기를 서버에 맡기고 실패하면 사람이 정리한다 / `bridge/db/migrate.py` 8~11
- 02_migrate 70: 더하기만 하면 되돌려도 옛 코드가 돈다 / `migrations/0032_merge_card.sql` 10
- 16_tests 95: 재시작이 승인 대기와 화면과 hook을 끊어 자동 배포를 하지 않는다 / `README.md` 616

## 4. TODO로 판정한 줄

541이 할 일로 둔 줄은 2절에서 올린 줄(인프라 2, FOREMAN 7)만 빼고 그대로 TODO다. 원문은 541 3절에 있어 다시 옮기지 않는다. 그 줄은 모두 「아직 안 한 일」이다. 아래는 541에서 판정이 바뀌어 TODO가 된 줄이다(애매에서, 한계에서). 원문은 앞부분만 옮겼다.

### 4-1. 인프라 기술문서(애매에서 13, 한계에서 3)

- 02_os_driver 49(뒤, 한계에서): 「Secure Boot가 켜져 있어 새 커널 모듈을 올릴 때마다 서명 키 등록이…」 기록에 까닭 없음(켜져 있어 등록했다는 사실만, `bl/00_server.md` 278)
- 02_setup 46: 「같은 스크립트가 저장소와 호스트 작업 폴더에 따로 복사돼 있다…」 기록에 까닭 없음
- 03_roles 40: 「app 노드가 두 대뿐이다…」 기록에 까닭 없음(배치가 사용자 목표라는 것만, `bl/08_scale_out.md` 14)
- 03_kubernetes 55: 「판 기록 파일은 사람이 손으로 맞춘다…」 아직 안 한 일
- 04_ingress 52: 「컨트롤러가 두 벌이어도 재시작할 때 아주 짧게 끊길 수 있다」 아직 안 한 일(원인 미확인, `bl/08_scale_out.md` 442)
- 01_path 48: 「Cloudflare 쪽 DNS 기록과 Access 정책은 저장소에 없다…」 기록에 까닭 없음(사람이 대시보드에서 한다는 사실만, `bl/09_monitoring.md` 132)
- 06_gitops 59: 「ArgoCD 설치 매니페스트가 저장소에 없다…」 기록에 까닭 없음
- 08_build 64: 「빌드 캐시가 빌드마다 비어 있어…」 기록에 까닭 없음
- 08_build 66: 「태그 줄을 바꾸는 명령은 앱 저장소의 Jenkinsfile에 있어…」 기록에 까닭 없음
- 08_build 67: 「`platform/versions.yaml`은 설치기가 읽지 않는 기록이다…」 아직 안 한 일(03_kubernetes 55와 같음)
- 03_versions 80: 「오래된 런북에는 지금과 다른 값이 남아 있다…」 기록에 까닭 없음
- 11_gpu 55: 「벡터 DB는 가상 머신 사설망에 인증 없이 열려 있다…」 기록에 까닭 없음(다른 포트를 더 연 까닭만, `bl/09_monitoring.md` 211)
- 03_dashboards 55: 「펫퍼민트의 확인 불가 응답 비율은 거절 문구로 판정한다…」 기록에 까닭 없음
- 13_storage 53: 「호스트의 NFS 설정은 이 저장소 밖(펫퍼민트 저장소)에 있다…」 기록에 까닭 없음
- 02_logs 35(한계에서): 「앱이 로그 꼴을 바꾸면 거르지 못한다…」 기록에 까닭 없음(기록이 「수집기에서 거르는 쪽을 고른 까닭은 기록 없음」, `bl/09_monitoring.md` 109)
- 02_logs 37(한계에서): 「로그는 7일만 남는다…」 기록에 까닭 없음(기록이 「Loki 7일의 까닭도 기록 없음」, `bl/09_monitoring.md` 116)

### 4-2. 인프라 포트폴리오(애매에서 2, 한계에서 1)

- 03 49: 「두 벌로 늘린 뒤에도 컨트롤러를 다시 띄울 때 아주 짧은 끊김이…」 아직 안 한 일(원인 미확인, 인프라 `docs/TODO.md` 11)
- 04 46: 「Cloudflare 쪽 DNS 기록과 Access 정책은 저장소가 아니라 대시보드에…」 기록에 까닭 없음
- 08 43(한계에서): 「로그 거르기는 글자 일치입니다…」 기록에 까닭 없음(기술문서 02_logs 35와 같음)

### 4-3. FOREMAN 기술문서, 한계 절 안(애매에서 29, 한계에서 10)

애매에서:
- 02_hooks 142: 「설정 파일 안의 스크립트 경로는 원본 폴더의 절대 경로다…」 기록에 까닭 없음
- 04_bus 257: 「브리지가 꺼질 때 5초 안에 넣지 못한 이벤트도 로그 한 줄과 함께 사라진다」 기록에 까닭 없음(버린다는 동작만, `bridge/bus.py` 91)
- 01_rules 363(나눔): 「rm이 아닌 일부 삭제 꼴은 미해결이다」 아직 안 한 일
- 02_flow 308: 「대화창 답을 알아채는 것은 도구 결과가 트랜스크립트에 적힌 뒤다…」 아직 안 한 일(재지 않음)
- 03_summary 155(`~`): 「`~`는 세션이 아니라 브리지 프로세스를 돌리는 계정의 홈으로 풀린다…」 기록에 까닭 없음
- 03_summary 163: 「요약은 300자에서 잘린다…」 기록에 까닭 없음
- 02_reconcile 119: 「키가 kind와 위치만으로 만들어지는 것은…」 기록에 까닭 없음(값만, `bridge/reconcile.py` 36~41)
- 02_reconcile 121(주기): 「정해진 주기가 없으므로 아무 세션도 끝나지 않으면…」 기록에 까닭 없음
- 04_move 186: 「작업방에서 일하던 세션을 옮기면, 새 세션은 그 작업방으로 돌아가지 않는다…」 아직 안 한 일(고치는 법 미정, `README.md` 863)
- 01_plan 308(뒤): 「남은 둘인 「교장에게 읽기 전용 확인 도구를 주기」와…」 기록에 까닭 없음(사용자가 지웠다는 것만, `log/foreman-4_readme_cleanup_20261115.md` 54~55)
- 01_plan 310(맡을 파일): 「맡을 파일 겹침은 교장이나 사람이 맡을 파일을 적어야 제대로 돈다…」 기록에 까닭 없음
- 02_note_wake 262(3단계): 「3단계로 갈지는 이런 제안이 실제 실패에서 몇 주 동안 맞는지를 보고 정한다」 아직 안 한 일(미룬 일, `docs/14_dispatcher_note_wake.md` 87)
- 03_overlap 288(sed): 「같은 파일 훑기는 Edit, Write 같은 편집 도구만 보므로…」 기록에 까닭 없음
- 03_overlap 288(메모리): 「띠, 「이미 알렸음」 기억, 말뭉치는 모두 브리지 메모리에만 있어서…」 기록에 까닭 없음(메모리에 둔다는 결정만, `log/overlap_alert_20261106.md` 37)
- 04_managers 324: 「물음을 관리자가 답하지 않고 올린다는 것도 지시문 약속이다…」 기록에 까닭 없음
- 01_room 47: 「서기 설계 문서의 일감 표에는 `sync`, `loss`, `polish`도 있다…」 기록에 까닭 없음(문서가 스스로 「왜 두지 않았는지는 기록에 없다」, `docs/12_scribe.md` 44)
- 03_evidence 186(표시 하나면 통과): 「근거 없는 줄은 한 줄에 표시가 하나라도 있으면 지나가고, 표 줄은 보지 않는다」 기록에 까닭 없음
- 11_notify 144(8자): 「`kind`는 8자까지라…」 기록에 까닭 없음
- 12_pipeline 305: 「사무실에 서 있지는 않고 옆 패널의 칩으로만 보인다」 기록에 까닭 없음
- 12_pipeline 313: 「인프라 캐릭터는 첫 웹훅 때 생긴다…」 기록에 까닭 없음
- 13_usage 355: 「5시간 한도 줄이 `/usage`에서 빠지는 까닭이…」 아직 안 한 일(`log/usage_missing_line_20261114.md` 7)
- 13_usage 357: 「계획 세우기와 서기에게 물어보기는 모델을 설정에서 바꿀 수 없거나…」 기록에 까닭 없음
- 01_store 162: 「스냅샷은 비동기로 받아 오므로…」 기록에 까닭 없음
- 01_store 277: 「| 스냅샷이 WS 소식을 덮음 |…」 기록에 까닭 없음(162와 같음)
- 02_office 392: 「서브에이전트는 길을 찾지 않아 가구 위를 지날 수 있다」 기록에 까닭 없음
- 02_office 393: 「셸을 연 채로는 방이 아주 작아진다…」 아직 안 한 일(고르지 않음)
- 05_check 270(`--promises`): 「호버가 약속한 조작이 실제로 되는지를 진짜 입력으로 해 보는…」 기록에 까닭 없음(사용자 결정만, 5-1절)
- 15_db 141: 「그러나 지금 코드에는 오래된 행을 지우는 작업이 없다…」 아직 안 한 일(미룬 일, `README.md` 835)
- 16_tests 24: 「만들지 않은 까닭은 … 이 빈틈은 아는 채로 남겨 둔 것이다」 기록에 까닭 없음

한계에서:
- 03_summary 157: 「변수는 같은 명령 안에서 …」 기록에 까닭 없음(`README.md` 387에는 4초 조건만)
- 03_keys 246: 「가리기가 원본을 고치지 않는다…」 기록에 까닭 없음
- 02_reconcile 121(30일): 「30일로 자른 것은…」 기록에 까닭 없음(까닭은 원고에만)
- 03_promote 278(내용 맞대기 없음): 「세션이 비슷한 줄을 고쳐 합치게 둔다…」 기록에 까닭 없음(지시만, `bridge/promote.py` 70)
- 04_move 198(낱말 목록): 「전환 말은 정해 둔 낱말 목록으로만…」 기록에 까닭 없음(`bridge/switchwatch.py` 24에는 160자의 까닭만)
- 03_evidence 180(.env): 「Read가 허락되어 있으니 모델은 저장소 안의 .env 파일도…」 기록에 까닭 없음
- 03_evidence 182: 「답의 근거도 확인하지 않는다」 기록에 까닭 없음
- 01_store 234(수정 시각 지문): 「지문을 수정 시각으로 만들기 때문에…」 기록에 까닭 없음
- 01_store 276: 「| 상태 판정이 두 곳 |…」 기록에 까닭 없음(원고 113에만)
- 04_shell 297: 「출력 범위를 못 찾는 경우…」 기록에 까닭 없음(대응만, `log/stage7_terminal_result.md` 59)

### 4-4. FOREMAN 기술문서, 결정 절 안(애매에서 3, 한계에서 2)

- 01_placement 192(애매에서): 「`mysqladmin ping`은 계정 없이 부르므로, 인증이 거부돼도 종료 코드 0을…」 기록에 까닭 없음(「의도대로」라는 결정만, `log/stage1_bridge_db_result.md` 39)
- 01_transcript 176(캐시 없음, 애매에서): 「누를 때마다 파일을 여니…」 기록에 까닭 없음
- 02_note_wake 173(애매에서): 「| 3단계 | 실패 이벤트가 부른다 |…」 아직 안 한 일(미룬 일)
- 06_sessions 124(한계에서): 「링크에는 대가가 있다…일부러 받아들였다」 기록에 까닭 없음(링크를 만든 사실만, `log/stage11_worktree_result.md` 8)
- 01_room 244(알림 안 보냄, 한계에서): 「할 일이 쌓였다고 텔레그램 알림을 보내지도 않는다」 기록에 까닭 없음(기록은 이것을 밀림의 원인으로 적는다, `log/foreman-4_scribe_structure_20261115.md` 272)

## 5. 541에서 바뀐 줄

| 바뀜 | 인프라 기술문서 | 인프라 포트폴리오 | FOREMAN 한계 절 안 | FOREMAN 결정 절 안 |
|---|---|---|---|---|
| 애매에서 한계 | 23(조건 17) | 13(조건 6) | 20(조건 12) | 1(조건 1) |
| 애매에서 TODO | 13 | 2 | 29 | 3 |
| 애매에서 빼기 | 0 | 0 | 5 | 0 |
| 한계에서 TODO | 3 | 1 | 10 | 2 |
| 할 일에서 한계 | 1 | 1 | 6 | 1 |

- 애매에서 한계로 간 줄은 3절에 있다(541 애매였던 줄). 애매에서 TODO로, 한계에서 TODO로 간 줄은 4절에 까닭과 함께 있다. 할 일에서 한계로 올린 줄은 3절에 「할 일에서 올림」으로 적었다.
- 541의 한계였고 이번에 조건 한계로 옮긴 줄(분류는 그대로 한계): 인프라 기술문서 13_storage 49, 14_operations 66, 01_network 34, 08_build 68(541 한계), 포트폴리오 04 45, 07 47, 10 52, FOREMAN 03_session 402, 03_keys 113, 02_office 390.
- 541이 「확인 못 함」으로 두고 이번에 기록을 찾아 한계로 굳힌 줄: 인프라 01_network 33, 02_tls 60, 06_gitops 61, 01_manifests 51, 포트폴리오 05 31(운영 도구 다섯도 같은 까닭), 06 41, 09 45. FOREMAN 02_note_wake 262는 541이 든 README 3.13 대신 `docs/14_dispatcher_note_wake.md` 76이 직접 까닭이다.

### 5-1. 경계 줄(사람이 정할 것)

- **사용자가 정했지만 까닭이 기록에 없는 줄.** FOREMAN 01_plan 308 뒤(교장 할 일 둘을 지움), 05_check 270 `--promises`, 16_tests 11(GitHub Actions, 11-15 포스트잇 제안이 L로 갈랐지만 까닭 칸은 「정해 두고 안 만듦」뿐, `log/foreman-6_postit_proposal_20261115.md` 119). 사용자가 까닭을 한 줄 남기면 한계로 올라간다.
- **기록이 스스로 「까닭 기록 없음」이라 적은 결정.** 인프라 02_logs 35, 37, 포트폴리오 08 43. 541은 한계, 이번에는 TODO. 반대로 01_metrics 43(Prometheus 15일)은 「디스크가 차기 전에 스스로 지워야 한다」는 문제가 기록에 있어 한계로 두었다.
- **미룬 일.** 기다리는 조건은 적혀 있으나 하면 잃는 것이 없는 줄이라 TODO로 두었다. FOREMAN 02_note_wake 262(3단계)와 173, 15_db 141, 01_placement 279(재부팅 검증, `CLAUDE.md` 「재부팅은 사용자가 시킬 때만」), 01_loss 320과 04_move 198의 창 크기(`config/models.toml` 41~45 「확인하지 못했다, 알려 오면 고친다」), 13_usage 354의 무게 맞추기(`docs/15_usage.md` 49), 02_note_wake 260과 262(노트, 자동 기상 확인), 10_scribe/04_notion 310(봇 토큰이라 사람 수정을 만들 수 없음, `docs/12_scribe.md` 190), 인프라 07_registry 54(옛 저장 공간은 며칠 뒤 지움, `bl/05_harbor.md` 481), 인프라 알림 넷(「무엇을 누구에게 알릴지 정하기 전」, `bl/09_monitoring.md` 140~145). 사용자가 미룬 일도 한계로 친다고 정하면 이 줄들이 한계로 올라간다.
- **근거가 약한 한계.** 인프라 「컨트롤 플레인 한 대」(기술문서 00_overview 40, 03_roles 42, 03_kubernetes 51, 포트폴리오 01 40, 11 18). 기록(`bl/01_cluster.md` 136)은 「CKA 범위가 이 구조」라고만 적고 고가용 구성과 견준 기록은 없다. 까닭이 한 줄 있어 한계로 두었다.
- **줄을 쪼개면 갈리는 줄.** 인프라 포트폴리오 03 47의 「강제가 아니라 선호 배치」 부분은 까닭이 없다. 포트폴리오 02 36(관리망 기본 경로)은 도구 성질로 읽어 조건으로 두었다. 기본 경로를 바꿀 수 있는데 안 바꾼 것으로 읽으면 TODO다. FOREMAN 01_structure 249의 프로메테우스 부분은 `README.md` 869 「수동으로 설치하지 말고 아껴둔다」가 있어 쪼개면 그 부분만 한계가 된다.
- **할 일에서 올릴 만하지만 올리지 않은 줄.** 인프라 02_nodes/03_roles 41(이름표는 다시 join하면 사라진다는 성질, `cluster/label-nodes.sh` 3. kubelet 설정으로 피하는 길을 안 쓴 까닭은 없음), FOREMAN 05_roles 140(`docs/roles.md` 48 「역할이 늘면」 조건만), 10_scribe/02_postit 280(텔레그램 포스트잇, 「필요하면 같은 API로」, `log/todo_inbox_20261109.md` 29), 14_screen/05_check 270(버튼 글과 호버 제목, 한 번 맞대 진짜 어긋남 0이라 미룸, `log/foreman-6_screen_text_sync_proposal_20261115.md` 102).
- **541 7절이 짚은 인프라 노드 대표 주소.** 기술문서 01_vms 44~46, 포트폴리오 02 31, 33~35, 11 19. 사람 답(`hist/human_answers_20261116.md` 15)은 「의도한 것이 아니라 기본값이 남은 것이다. 문서에는 지금 상태 그대로 적고, 그 때문에 생길 수 있는 일은 알려진 한계로 적는다」이다. 어떻게 적을지만 정했고 고치지 않는 까닭은 없어 TODO로 두었다. 사용자 기준과 그 답이 어긋나므로 사람이 다시 정할 것이다.

## 6. 되풀이(F 단계 재료)

같은 한계가 여러 편에 나오는 묶음이다. 「한 줄 까닭」은 3절의 기록에서 왔다.

인프라(기술문서와 포트폴리오를 함께 셈)
- **물리 서버 한 대**(조건, 10곳): 기술문서 00_overview 39, 01_network 35, 01_vms 48, 11_gpu 52, 13_storage 51, 포트폴리오 00 49, 01 39, 06 40, 09 47, 11 17. 조건: 이 프로젝트가 쓰는 물리 서버는 한 대다(`hist/notion_hardware_20261116.md` 12, `bl/01_cluster.md` 699). 541의 「서버 한 대 9곳」에 기술문서 13_storage 51을 더했다
- **GPU 한 장**(조건, 2곳): 기술문서 02_os_driver 51, 11_gpu 51
- **컨트롤 플레인 한 대**(선택, 5곳): 기술문서 00_overview 40, 03_roles 42, 03_kubernetes 51, 포트폴리오 01 40, 11 18. CKA 범위인 「컨트롤 플레인 1대와 워커 여러 대」 구조를 골랐다(근거 약함, 5-1절)
- **역할 고정, 노드 이름으로 장애 범위**(선택, 9곳): 기술문서 03_roles 39, 06_gitops 60, 07_registry 51, 08_build 62, 01_metrics 37, 02_logs 36, 포트폴리오 07 49, 09 44, 11 20. 노드가 죽으면 무엇이 멈추는지 노드 이름으로 말하려 한다(`bl/08_scale_out.md` 129, 434)
- **터널 하나, 문 하나**(선택, 6곳): 기술문서 00_overview 41, 01_path 47, 포트폴리오 00 50, 03 47, 04 41, 11 27. 앱을 더해도 Ingress만 더한다(`bl/03_cloudflare_tunnel.md` 153)
- **비밀값을 저장소에 두지 않음**(선택, 7곳): 기술문서 02_tls 59, 06_gitops 63, 07_registry 55, 02_first_deploy 44, 46, 포트폴리오 05 33, 11 31. 커밋되는 매니페스트에 실제 값을 박지 않는다(`bl/03_cloudflare_tunnel.md` 188)
- **GPU 일은 호스트에, 사람이 띄움**(선택, 7곳): 기술문서 11_gpu 53 앞 둘, 01_metrics 41, 포트폴리오 06 37, 38, 39 앞, 11 32 앞. GPU 패스스루는 위험이 크다(`bl/kubernetes_install.md` 117)
- **바깥 길은 SSH 하나**(선택, 3곳): 기술문서 01_network 33, 03_remote 37, 38 앞. 공유기 포트를 더 열면 보안 위험이다(`hist/cloudflare_tunnel_vcluster.md` 77)
- **원점 인증서 확인 끔, 사설망 http**(선택, 6곳): 기술문서 02_tls 57, 58, 포트폴리오 05 31, 32, 11 25, 26
- **platform은 ArgoCD 앞의 기반**(선택, 3곳): 기술문서 04_ingress 54, 포트폴리오 03 50, 07 45
- **바깥 도구 성질**(조건): cloudflared는 켤 때만 설정을 읽음(기술문서 01_path 49, 포트폴리오 04 45), 마이그레이션은 되돌아가지 않음(기술문서 08_build 68, 포트폴리오 07 47), local-path 성질(13_storage 48, 49)
- TODO 쪽 되풀이(한계가 아님): 알림 없음(5곳), 노드 대표 주소(8곳), 백업이 같은 물리 서버(4곳), 호스트 서비스 다시 띄우는 기록 없음(3곳), 판 기록 파일 손으로 맞춤(2곳), ingress-nginx 짧은 끊김 원인(3곳)

FOREMAN
- **해석기 안 쓰기**(5곳): 05_roles 83 앞, 146 넷째, 02_guards 314, 125(결정 절), 01_rules 363(해석기 본문). 데이터 만들기와 소스 고치기를 글로 가를 수 없고, 해석기 본문을 넓게 보면 오탐이 돌아온다(`log/coder_c_wave2_20261111.md` 99, `log/foreman-6_silent_delete_20261115.md` 56)
- **관리자 규칙을 기록만 함**(7곳): 05_roles 146 둘째와 조사 제안, 01_roles 266 둘, 02_guards 318, 320, 137(결정 절). 사용자가 기록만 하고 다섯 고치기를 하지 않기로 정했다(커밋 `2a45269`)
- **다른 프로젝트로 넓히지 않음**(2곳): 05_roles 148, 02_guards 322. 걸림 74건이 모두 정당했고 프로젝트별 표가 먼저다(`log/inspect_roleguard_20261114.md` 11, 84)
- **모양 모르는 비밀, 도구 결과 본문을 저장하지 않음**(5곳): 04_bus 131, 03_keys 244, 15_db 143, 01_transcript 176(결정 절), 03_evidence 180(조건). `README.md` 833
- **샌드박스는 시험 뒤로**(2곳): 01_rules 363(hook은 글만 봄), 02_guards 190. 일상 명령을 깨뜨릴 위험이 가장 크다(`log/foreman-6_silent_delete_20261115.md` 50)
- **브리지가 꺼지면 통과**(2곳): 02_flow 312, 02_guards 312. `scripts/foreman-decide.sh` 5
- **세션 자신이 문서를 씀**(3곳): 02_summary 251, 03_promote 282, 04_move 196. `docs/11_handoff.md` 8
- **binlog 끔, 트랜스크립트로 다시 만듦**(3곳): 01_placement 226, 190, 15_db 72. `log/stage1_bridge_db_result.md` 64
- **교장 읽기 전용**(2곳): 09_dispatcher 37, 01_plan 308 앞. `docs/11_foreman_dispatch.md` 21
- **텔레그램은 보내기만, 링크로 화면에**(2곳): 02_note_wake 262, 11_notify 270. `docs/14_dispatcher_note_wake.md` 76
- **로컬 폴링, 전권 토큰 없음**(3곳): 12_pipeline 301, 310, 312. `log/stage8_cicd_result.md` 99
- **빌드 없는 화면**(3곳): 14_screen 25, 27, 29. `README.md` 608
- **사용량을 볼 수 없는 바깥 조건**(4곳, 조건): 13_usage 24, 27, 28, 354. `docs/15_usage.md` 5, 14, 99
- **비용 때문에 LLM 대신 기계 판정**(3곳): 10_scribe 119, 02_postit 130, 03_evidence 186
- **스키마를 바꾸지 않음**(2곳): 11_notify 144, 03_overlap 288 관리자 빼기
- TODO 쪽 되풀이(한계가 아님): 바깥 감시 타이머(01_placement 281 둘, 02_flow 312, 02_guards 312. 「보류」만 있고 감시 목록과 문턱은 사용자가 정할 것, `log/foreman-4_bridge_down_20261115.md` 62, 130), 토큰을 바꾼 뒤 다시 띄우기(04_bus 137, 257, 03_keys 248), 재시작 추세 감시(00_foreman 61, 01_structure 249), 브리지 메모리 상태(03_overlap 288, 12_pipeline 309, 14_screen/04_shell 298, 11_notify 293, 03_session 404), 창 크기 모름(01_loss 320, 04_move 198)

## 7. 함께 찾은 것(고치지 않았다)

- **541 근거 줄 어긋남.** 541 6-2절이 인프라 포트폴리오 04 41의 근거로 든 `bl/03_cloudflare_tunnel.md` 697은 origin/main에서 빈 줄이고 까닭은 153줄에 있다. 541이 기술문서 07_registry 51의 근거로 든 `bl/05_harbor.md` 228~235는 분산 저장소 이야기이고 w3 한 노드의 까닭은 `bl/08_scale_out.md` 129다.
- **원고 근거 표시 어긋남(인프라 origin/main).** 기술문서 14_operations 66의 `[docs:style_guide.md:71]`은 실제로 73줄이다. 14_operations 67의 `style_guide.md:150`은 541 7절대로 없는 줄이다. 포트폴리오가 근거로 든 인프라 `CLAUDE.md` 46은 지금 47줄이다.
- **낡았을 수 있는 근거.** 인프라 `apps/runshoes/mysql/statefulset.yaml` 6~7의 「노드가 3대라 감수」는 지금 워커가 4대라 낡은 문구일 수 있다(기술문서 10_database 76, 포트폴리오 09 45가 근거로 쓴다). FOREMAN `docs/14_dispatcher_note_wake.md` 76의 「화면은 Cloudflare 로그인 뒤라」는 `README.md` 3.13 「터널을 열지 않는다(11-03 결정)」과 맞지 않는다. 02_note_wake 262와 11_notify 270의 한계 까닭이 이 줄에 기대므로 까닭 문구를 고치면 같이 고쳐야 한다.
- **541 셈과 다른 쪼개기.** FOREMAN 01_rules 363은 541이 두 줄로 셌지만 한 문장에 해석기 본문과 rm 밖 삭제 꼴이 함께 있어 셋으로 나눴다(한계 둘, TODO 하나). 그래서 FOREMAN 한계 절 안 합계가 541보다 한 줄 많다(191 = 190 + 1).

## 8. 규칙 위반

규칙 위반 없음. 파일은 이 log 하나만 Write로 썼다. 인프라 저장소는 `git show`, `git grep`으로 origin/main을 읽기만 했고 fetch하지 않았다. 다른 브랜치는 보지 않았다. `pgrep -f`는 쓰지 않았다. 서브에이전트 다섯은 읽기만 했고 파일을 만들지 않았다고 보고했으며, 모두 끝났다(돌고 있는 것 없음). 진행 글은 모두 한국어로 썼다.
