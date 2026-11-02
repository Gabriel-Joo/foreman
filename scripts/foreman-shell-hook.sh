#!/usr/bin/env bash
# 터미널 패널 셸(foreman-bashrc)이 명령마다 부른다 — 명령 · 종료 코드 · 위치를 브리지에 보낸다(7단계).
# 2초 타임아웃, 출력 없음, 항상 exit 0. 브리지가 꺼져 있어도 셸은 그대로 쓴다.
# 토큰은 .env.bridge의 FOREMAN_HOOK_TOKEN, 헤더는 프로세스 치환으로(ps에 안 보이게). 명령 원문은 브리지가 마스킹한다
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TOKEN="$(sed -n 's/^FOREMAN_HOOK_TOKEN=//p' "$REPO/.env.bridge" 2>/dev/null)"
[ -n "$TOKEN" ] || exit 0
body="$(python3 -I -c 'import json, os; print(json.dumps({"cmd": os.environ.get("FOREMAN_CMD", ""), "exit": int(os.environ.get("FOREMAN_EXIT") or 0), "cwd": os.environ.get("FOREMAN_CWD", "")}))' 2>/dev/null)" || exit 0
printf '%s' "$body" | curl -sS -m 2 -o /dev/null -X POST -H 'Content-Type: application/json' \
  -H @<(printf 'Authorization: Bearer %s\n' "$TOKEN") --data-binary @- "${FOREMAN_HOOK_BASE:-http://127.0.0.1:8000}/hooks/shell" >/dev/null 2>&1
exit 0
