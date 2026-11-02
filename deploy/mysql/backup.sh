#!/usr/bin/env bash
# FOREMAN DB 매일 백업 — 사용자 crontab에서 부른다(systemd user timer는 linger가 꺼져 있어 못 쓴다)
#   30 4 * * * /home/kopo17/AI_programming/foreman/deploy/mysql/backup.sh >> ~/backups/foreman/backup.log 2>&1
# 앱 계정으로 dump한다(비밀번호는 컨테이너 환경변수에서 읽어 이 스크립트·로그에 나오지 않는다).
# 하루치 손실은 감수한다: 트랜스크립트(120일)를 다시 읽으면 대부분 복원된다. 다시 만들 수 없는 것은 hook·폴링 이벤트뿐
set -euo pipefail
umask 077   # 덤프에는 프롬프트·명령 원문이 들어간다

BACKUP_DIR="${FOREMAN_BACKUP_DIR:-$HOME/backups/foreman}"
KEEP="${FOREMAN_BACKUP_KEEP:-14}"
CONTAINER=foreman-mysql
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

fail() {
  echo "$(date -Is) 실패: $1" >&2
  # 실패는 조용히 지나가면 안 된다(milvus-port-forward 교훈). 브리지와 같은 규칙 · 토큰으로 직접 보낸다(서버가 꺼져 있어도)
  (cd "$REPO" && timeout 30 .venv/bin/python -m bridge.telegram "DB 백업 실패" "$1") || true
  exit 1
}

[ -d "$BACKUP_DIR" ] && [ -w "$BACKUP_DIR" ] || fail "백업 폴더 없음 또는 쓰기 불가: $BACKUP_DIR"

stamp="$(date +%Y%m%d-%H%M%S)"
out="$BACKUP_DIR/foreman-$stamp.sql.gz"
tmp="$out.part"

timeout 600 docker exec "$CONTAINER" sh -c \
  'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump -u"$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"' \
  | gzip > "$tmp" || { rm -f "$tmp"; fail "mysqldump 실패"; }

gzip -t "$tmp" || { rm -f "$tmp"; fail "gzip 검사 실패"; }
zcat "$tmp" | tail -n 1 | grep -q 'Dump completed' || { rm -f "$tmp"; fail "dump 끝 표시 없음(중간에 끊김)"; }
mv "$tmp" "$out"

# 오래된 것 정리 — 최신 KEEP개만 남긴다
ls -1t "$BACKUP_DIR"/foreman-*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

echo "$(date -Is) 백업 $(basename "$out") $(du -h "$out" | cut -f1)"
