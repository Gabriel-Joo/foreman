#!/usr/bin/env bash
# FOREMAN 8단계 — 클러스터 쪽 설정(웹훅 보내는 쪽). 사람이 읽고 실행한다: ! scripts/cicd-apply.sh [argocd|jenkins|harbor|all]
#
# 바꾸는 것(모두 더하기만 — 동기화 · 빌드 · push 동작은 그대로다):
#   argocd   argocd-notifications-cm에 webhook 서비스 · 템플릿 · 트리거 · 구독(deploy/cicd/argocd-notifications-foreman.yaml)
#            argocd-notifications-secret에 키 foreman-webhook-token
#   jenkins  Secret jenkins/foreman-webhook(키 authorization = "Authorization: Bearer …") — Jenkinsfile이 jnlp에 optional로 붙인다.
#            Jenkins 설정 · 재시작 없음. Jenkinsfile 변경은 따로(deploy/cicd/jenkinsfile-*.patch — 그 저장소에서 git apply · push)
#   harbor   프로젝트 runshoes · petmint에 웹훅 정책 "foreman"(PUSH_ARTIFACT · SCANNING_FAILED · QUOTA_EXCEED →
#            http://192.168.122.1:8001/webhooks/harbor, Auth Header). 이미 있으면 고친다
#
# 비밀값은 화면 · 명령줄에 내지 않는다: 토큰은 .env.bridge에서 읽어 vagrant ssh의 표준 입력으로만 넘긴다.
# Harbor admin 비밀번호는 m-k8s 안에서 Secret harbor/harbor-core를 읽어 그 안에서만 쓴다.
# 되돌리기: argocd — cm에서 service.webhook.foreman · template.foreman · trigger.foreman-* · subscriptions 키 삭제,
#           secret 키 삭제 / jenkins — kubectl -n jenkins delete secret foreman-webhook / harbor — UI 프로젝트 › 웹훅 › foreman 삭제
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
K8S="${K8S_DIR:-$HOME/k8s-cluster}"
TOKEN="$(sed -n 's/^FOREMAN_WEBHOOK_TOKEN=//p' "$REPO/.env.bridge")"
[ "${#TOKEN}" -ge 32 ] || { echo ".env.bridge에 FOREMAN_WEBHOOK_TOKEN이 없다"; exit 1; }
what="${1:-all}"
vm() { (cd "$K8S" && vagrant ssh m-k8s -c "$1"); }   # kubectl 오류는 보이게 둔다(비밀값은 표준 입력으로만 지난다)

if [ "$what" = argocd ] || [ "$what" = all ]; then
  echo "== ArgoCD notifications"
  vm 'kubectl -n argocd patch cm argocd-notifications-cm --type merge --patch-file /dev/stdin' \
    < "$REPO/deploy/cicd/argocd-notifications-foreman.yaml"
  printf '{"stringData":{"foreman-webhook-token":"%s"}}' "$TOKEN" \
    | vm 'kubectl -n argocd patch secret argocd-notifications-secret --type merge --patch-file /dev/stdin'
fi

if [ "$what" = jenkins ] || [ "$what" = all ]; then
  echo "== Jenkins Secret foreman-webhook"
  printf 'Authorization: Bearer %s\n' "$TOKEN" \
    | vm 'kubectl -n jenkins create secret generic foreman-webhook --from-file=authorization=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -'
fi

if [ "$what" = harbor ] || [ "$what" = all ]; then
  echo "== Harbor 웹훅 정책(runshoes · petmint)"
  # 스크립트를 표준 입력으로 보낸다. 토큰은 그 첫 줄(TOKEN = "…")로만 — 명령줄에도 화면에도 안 나온다(urlsafe 문자뿐)
  { printf 'TOKEN = "%s"\n' "$TOKEN"; cat "$REPO/deploy/cicd/harbor-webhook.py"; } | vm 'python3 -'
fi
echo "끝 — 브리지 로그(/tmp/foreman-bridge.log)에서 '웹훅'을 본다"
