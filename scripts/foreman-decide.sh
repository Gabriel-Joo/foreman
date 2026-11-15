#!/usr/bin/env bash
# CC hook → FOREMAN 브리지 승인 판정(5단계). foreman-decide.sh pre | permission
#   pre         PreToolUse — 4초 안에 판정(allow / ask)을 받아 그대로 stdout으로. 판정이 없으면 아무것도 안 낸다
#   permission  PermissionRequest — 브라우저 결정을 기다린다(설정 timeout보다 짧게). 결정이 없으면 아무것도 안 낸다
# 브리지가 꺼져 있거나 오류면 아무것도 출력하지 않고 exit 0 — CC가 지금처럼 스스로 정한다(허용 쪽으로 새지 않는다).
# 토큰은 .env.bridge의 FOREMAN_HOOK_TOKEN, 헤더는 프로세스 치환으로(ps에 안 보이게)
#
# 판정 없이 통과한 갈래(토큰 없음 · 연결 거부 · 시간 초과 · 5xx · 401 · 빈 본문 · 깨진 JSON, 11-15 조사 A 3-1)는
# .run/hook_miss.log에 한 줄 남긴다(통과는 그대로, 사실만). 명령 글 · 입력 값은 쓰지 않는다 — 시각, 갈래, 세션, 도구 이름만.
# 정상 판정 길에서는 아무것도 쓰지 않는다. 1MB를 넘으면 .1로 한 벌만 돌려 둔다. 브리지 안 갈래는 bridge/hookmiss.py
#
# 입력은 한 바이트도 바꾸지 않고 브리지에 넘긴다(11-15 400 사고). 셸 변수에 담지 않는다 — 명령 치환은 끝 줄바꿈과 NUL을
# 지우고, `$(</dev/stdin)`은 stdin이 소켓이면(Node가 자식에게 주는 꼴) 열지 못해 빈 본문이 나간다.
# tee가 fd 0을 그대로 읽어 curl에 흘리고, 앞 4KB만 곁가지로 떼어 세션 id와 도구 이름만 이름 없는 파이프로 받는다(파일 안 만듦).
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${FOREMAN_HOOK_BASE:-http://127.0.0.1:8000}"
MISS="${FOREMAN_HOOK_MISS_LOG:-$REPO/.run/hook_miss.log}"
MISS_MAX=1048576
IDS_HEAD=4096          # CC 입력은 session_id, tool_name이 tool_input보다 앞이라 이 안에 든다
MODE="${1:-}"

ids_of() {  # stdin 앞부분 → 「키 값」 줄들(값은 따옴표 안 글자만, 명령 글은 키가 달라 안 걸린다) + 끝 표시 「.」
  head -c "$IDS_HEAD" | LC_ALL=C grep -aoE '"(session_id|tool_name)"[[:space:]]*:[[:space:]]*"[^"]{0,200}"' 2>/dev/null
  echo .
}

miss() {  # $1 갈래, $2 까닭(curl · HTTP 코드). 쓰기에 실패해도 통과는 그대로
  local sid=- tool=- d="${MISS%/*}" size line k v
  if [ -n "${IDS:-}" ]; then
    while IFS= read -r -t 1 -u "$IDS" line && [ "$line" != . ]; do
      [[ $line =~ ^\"([a-z_]+)\"[[:space:]]*:[[:space:]]*\"(.*)\"$ ]] || continue
      k="${BASH_REMATCH[1]}" v="${BASH_REMATCH[2]}"
      if [ "$k" = session_id ] && [ -z "${seen_sid:-}" ]; then
        seen_sid=1; [[ $v =~ ^[A-Za-z0-9-]{1,64}$ ]] && sid="$v"
      elif [ "$k" = tool_name ] && [ -z "${seen_tool:-}" ]; then
        seen_tool=1; [[ $v =~ ^[A-Za-z0-9_.:-]{1,80}$ ]] && tool="$v"
      fi
    done
  fi
  [ -d "$d" ] || mkdir -p -m 700 "$d" 2>/dev/null
  if [ -f "$MISS" ]; then
    size="$(stat -c %s "$MISS" 2>/dev/null)"
    [ "${size:-0}" -gt "$MISS_MAX" ] && mv -f "$MISS" "$MISS.1" 2>/dev/null
  fi
  printf '%(%Y-%m-%dT%H:%M:%S%z)T script-%s %s %s session=%s tool=%s\n' -1 "$MODE" "$1" "${2:--}" "$sid" "$tool" >> "$MISS" 2>/dev/null
}

case "$MODE" in
  pre)        url="$BASE/hooks/pre";        max=4 ;;
  permission) url="$BASE/hooks/permission"; max=3630 ;;   # 브리지 wait_s(3600)보다 길고 CC hook timeout(3660)보다 짧게
  *) exit 0 ;;
esac
exec {IDS}<> <(:) 2>/dev/null || IDS=""   # 이름 없는 파이프(읽기 쓰기 한 fd). 못 만들면 기록에 세션, 도구가 「-」일 뿐
TOKEN="$(sed -n 's/^FOREMAN_HOOK_TOKEN=//p' "$REPO/.env.bridge" 2>/dev/null)"
if [ -z "$TOKEN" ]; then
  [ -n "$IDS" ] && ids_of >&"$IDS"
  miss 토큰없음; exit 0
fi
if [ -n "$IDS" ]; then
  # tee -p: 곁가지(head)가 4KB 뒤 닫혀도 끊기지 않고 curl 쪽에 끝까지 흘린다
  resp="$(tee -p >(exec >&"$IDS"; ids_of) 2>/dev/null | curl -sS -f -m "$max" -w '\n%{http_code}' -X POST \
    -H 'Content-Type: application/json' -H @<(printf 'Authorization: Bearer %s\n' "$TOKEN") \
    --data-binary @- "$url" 2>/dev/null)"
else
  resp="$(curl -sS -f -m "$max" -w '\n%{http_code}' -X POST \
    -H 'Content-Type: application/json' -H @<(printf 'Authorization: Bearer %s\n' "$TOKEN") \
    --data-binary @- "$url" 2>/dev/null)"
fi
rc=$?
code="${resp##*$'\n'}"
out="${resp%$'\n'*}"
[ "$resp" = "$code" ] && out=""     # -w 줄만 있음(본문 없음)
if [ "$rc" -ne 0 ]; then
  case "$rc:$code" in
    7:*)        miss 연결거부 "curl=$rc" ;;
    28:*)       miss 시간초과 "curl=$rc" ;;
    22:401)     miss 인증실패 "http=$code" ;;
    22:5??)     miss 서버오류 "http=$code" ;;
    *)          miss curl오류 "curl=$rc,http=$code" ;;
  esac
  exit 0
fi
if [ -z "$out" ]; then
  [ "$code" = 204 ] || miss 빈본문 "http=$code"   # 204 = 브리지가 판정하지 않기로 한 정상 길
  exit 0
fi
[[ $out == \{*\} ]] || miss 깨진JSON "http=$code"     # 지금처럼 그대로 내보낸다(CC가 판정으로 쓰지 않는다)
printf '%s\n' "$out"
exit 0
