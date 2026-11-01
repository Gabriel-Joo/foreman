#!/usr/bin/env bash
# CC hook → FOREMAN 브리지. hook 설정에서 이 스크립트를 부른다(deploy/hooks/foreman-hooks.json).
# CC를 절대 막지 않는다: 2초 타임아웃, 출력 없음(UserPromptSubmit의 stdout은 모델 컨텍스트에 들어간다), 항상 exit 0.
# 토큰은 .env.bridge의 FOREMAN_HOOK_TOKEN. 명령줄 인자에 싣지 않는다(ps에 보이므로) — 헤더는 프로세스 치환으로 넘긴다
REPO="$(cd "$(dirname "$0")/.." && pwd)"
URL="${FOREMAN_HOOK_URL:-http://127.0.0.1:8000/hooks}"
TOKEN="$(sed -n 's/^FOREMAN_HOOK_TOKEN=//p' "$REPO/.env.bridge" 2>/dev/null)"
[ -n "$TOKEN" ] || exit 0
curl -sS -m 2 -o /dev/null -X POST -H 'Content-Type: application/json' \
  -H @<(printf 'Authorization: Bearer %s\n' "$TOKEN") --data-binary @- "$URL" >/dev/null 2>&1
exit 0
