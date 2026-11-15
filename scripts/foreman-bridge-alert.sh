#!/usr/bin/env bash
# 브리지 밖 알림 — systemd가 브리지 다시 띄우기를 포기했을 때(OnFailure) 텔레그램을 보낸다(11-15 조사 A 1번).
#   foreman-bridge-alert.sh [유닛 이름]      기본 foreman-bridge.service
# 브리지와 함께 죽지 않게 브리지 코드 · .venv · config/notify.toml을 하나도 읽지 않는다. curl과 .env.telegram만 쓴다.
# 그래서 접두어도 notify.toml을 읽지 않고 여기 둔다([projects.foreman] prefix와 같게).
#
# 환경 변수
#   FOREMAN_ALERT_DRYRUN=<파일>   보내지 않고 보낼 글만 그 파일에 덧붙인다(시험용). 토큰을 읽지 않는다
#   FOREMAN_ALERT_ENV=<파일>      토큰 파일(기본 저장소 맨 위 .env.telegram)
#   FOREMAN_ALERT_API=<주소>      텔레그램 API 주소(기본 https://api.telegram.org, 시험에서 실패 경로를 볼 때)
#   MONITOR_SERVICE_RESULT 등    systemd가 OnFailure 유닛에 넣어 준다(있으면 결과 · 종료 코드를 글에 붙인다)
#
# journal 줄은 비밀값이 섞일 수 있어 그대로 싣지 않는다 — 줄 수와 오류 종류(예외 클래스 이름)만 싣는다.
# 실패는 조용히 끝나지 않는다: 까닭을 stderr(→ journal)에 쓰고 1로 끝난다.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT="${1:-foreman-bridge.service}"
PREFIX="[FOREMAN]"
ENV_FILE="${FOREMAN_ALERT_ENV:-$REPO/.env.telegram}"
N=50

# ── 정말 포기했나 ──
# systemd 259 실측(11-15): OnFailure=는 포기할 때만이 아니라 Restart=로 다시 띄우기 전 실패마다 불린다.
# 그때 유닛은 auto-restart(activating)이고, 포기하면 failed에 머문다 — failed일 때만 보낸다.
# 상태를 못 읽으면(버스 오류 등) 알리는 쪽으로 간다(조용히 지나가지 않게)
state="$(systemctl --user show "$UNIT" -p ActiveState --value 2>/dev/null)"
sub="$(systemctl --user show "$UNIT" -p SubState --value 2>/dev/null)"
restarts="$(systemctl --user show "$UNIT" -p NRestarts --value 2>/dev/null)"
if [ -n "$state" ] && [ "$state" != "failed" ]; then
  echo "보내지 않음: $UNIT 상태가 $state/$sub 입니다(failed가 아니므로 포기가 아닙니다)"
  exit 0
fi

# ── 글 만들기 ──
result="${MONITOR_SERVICE_RESULT:-모름}"
exit_info="${MONITOR_EXIT_CODE:-}${MONITOR_EXIT_STATUS:+ $MONITOR_EXIT_STATUS}"
jl="$(journalctl --user -u "$UNIT" -n "$N" -o cat --no-pager 2>/dev/null)"
lines=0
[ -n "$jl" ] && lines="$(printf '%s\n' "$jl" | wc -l)"
# 예외 클래스 이름만 뽑아 많은 순으로 셋(값은 싣지 않는다)
kinds="$(printf '%s\n' "$jl" | grep -oE '\b[A-Z][A-Za-z0-9]*(Error|Exception|Exit)\b' | sort | uniq -c | sort -rn | head -3 \
  | awk '{printf "%s%s %s", (NR>1?", ":""), $2, $1}')"
msg="$PREFIX 브리지가 멈췄습니다(systemd가 다시 띄우기를 포기)
유닛: $UNIT, 상태: ${state:-읽지 못함}${restarts:+, 다시 띄운 횟수 $restarts}, 결과: $result${exit_info:+, 종료: $exit_info}
마지막 journal ${lines}줄의 오류 종류: ${kinds:-찾지 못함}
시각: $(date '+%m-%d %H:%M:%S')
다시 띄우려면 systemctl --user reset-failed 뒤 start"

# ── 시험 모드 ──
if [ -n "${FOREMAN_ALERT_DRYRUN:-}" ]; then
  if printf '%s\n---\n' "$msg" >> "$FOREMAN_ALERT_DRYRUN"; then
    echo "시험 모드: 보내지 않고 $FOREMAN_ALERT_DRYRUN 에 썼습니다"
    exit 0
  fi
  echo "알림 실패: 시험 모드 파일에 쓰지 못했습니다($FOREMAN_ALERT_DRYRUN)" >&2
  exit 1
fi

# ── 보내기 ──
# 값은 이 변수 안에서만 다룬다. URL(토큰)과 chat_id는 프로세스 치환 설정으로 넘겨 ps에 보이지 않게 한다
if [ ! -r "$ENV_FILE" ]; then
  echo "알림 실패: 토큰 파일을 읽을 수 없습니다($ENV_FILE)" >&2
  exit 1
fi
tok="$(sed -n "s/^TELEGRAM_BOT_TOKEN=//p" "$ENV_FILE" | head -1 | tr -d "\"' \r")"
chat="$(sed -n "s/^TELEGRAM_CHAT_ID=//p" "$ENV_FILE" | head -1 | tr -d "\"' \r")"
if [ -z "$tok" ] || [ -z "$chat" ]; then
  echo "알림 실패: 토큰 파일에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID가 없습니다" >&2
  exit 1
fi
resp="$(curl -sS -m 15 -w '\n%{http_code}' \
  -K <(printf 'url = "%s/bot%s/sendMessage"\ndata-urlencode = "chat_id=%s"\n' "${FOREMAN_ALERT_API:-https://api.telegram.org}" "$tok" "$chat") \
  --data-urlencode "text=$msg" --data-urlencode "disable_web_page_preview=true" 2>/dev/null)"
rc=$?
unset tok chat
code="${resp##*$'\n'}"
if [ "$rc" -ne 0 ]; then
  echo "알림 실패: curl 종료 코드 $rc" >&2
  exit 1
fi
case "$resp" in
  *'"ok":true'*) echo "알림 보냄($UNIT, $result)"; exit 0 ;;
esac
echo "알림 실패: 텔레그램 HTTP $code" >&2
exit 1
