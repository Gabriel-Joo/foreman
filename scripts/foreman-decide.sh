#!/usr/bin/env bash
# CC hook → FOREMAN 브리지 승인 판정(5단계). foreman-decide.sh pre | permission
#   pre         PreToolUse — 4초 안에 판정(allow / ask)을 받아 그대로 stdout으로. 판정이 없으면 아무것도 안 낸다
#   permission  PermissionRequest — 브라우저 결정을 기다린다(설정 timeout보다 짧게). 결정이 없으면 아무것도 안 낸다
# 브리지가 꺼져 있거나 오류면 아무것도 출력하지 않고 exit 0 — CC가 지금처럼 스스로 정한다(허용 쪽으로 새지 않는다).
# 토큰은 .env.bridge의 FOREMAN_HOOK_TOKEN, 헤더는 프로세스 치환으로(ps에 안 보이게)
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${FOREMAN_HOOK_BASE:-http://127.0.0.1:8000}"
TOKEN="$(sed -n 's/^FOREMAN_HOOK_TOKEN=//p' "$REPO/.env.bridge" 2>/dev/null)"
[ -n "$TOKEN" ] || exit 0
case "${1:-}" in
  pre)        url="$BASE/hooks/pre";        max=4 ;;
  permission) url="$BASE/hooks/permission"; max=880 ;;
  *) exit 0 ;;
esac
out="$(curl -sS -f -m "$max" -X POST -H 'Content-Type: application/json' \
  -H @<(printf 'Authorization: Bearer %s\n' "$TOKEN") --data-binary @- "$url" 2>/dev/null)" || exit 0
[ -n "$out" ] && printf '%s\n' "$out"
exit 0
