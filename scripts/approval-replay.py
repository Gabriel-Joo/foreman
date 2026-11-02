"""승인 정책 다시 돌려 보기 — DB에 적재된 과거 도구 호출(event type=tool_use)에 옛 규칙과 지금 규칙을 돌려 하루 ask 수를 센다.

    .venv/bin/python scripts/approval-replay.py [--days 20] [--old REV] [--show N]

옛 규칙 = git REV(기본 HEAD)의 bridge/approval.py + config/approval.toml, 지금 규칙 = 작업 트리의 것. DB는 읽기만 한다.
명령 원문은 마스킹된 것이다(target_full · target) — 비밀값 자리만 다르고 판정에는 영향이 없다.
세션 scratchpad(/tmp/claude-<uid>/<프로젝트 디렉토리>/<세션 id>/scratchpad)도 넣어 실제 판정과 맞춘다.
"""

import argparse
import collections
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import pymysql  # noqa: E402

from bridge.config import get_settings  # noqa: E402

KST = timedelta(hours=9)


def load_old(rev: str):
    d = tempfile.mkdtemp(prefix="approval-old-")
    src = subprocess.check_output(["git", "-C", str(REPO), "show", f"{rev}:bridge/approval.py"])
    toml = subprocess.check_output(["git", "-C", str(REPO), "show", f"{rev}:config/approval.toml"])
    Path(d, "approval_old.py").write_bytes(src)
    Path(d, "approval.toml").write_bytes(toml)
    spec = importlib.util.spec_from_file_location("approval_old", Path(d, "approval_old.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_policy(Path(d, "approval.toml"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--old", default="HEAD")
    ap.add_argument("--show", type=int, default=0, help="새 규칙에서도 ask인 것 · ask에서 빠진 것 예시 N개씩")
    a = ap.parse_args()
    from bridge.approval import load_policy
    new = load_policy(REPO / "config" / "approval.toml")
    old = load_old(a.old)
    s = get_settings()
    c = pymysql.connect(host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
                        password=s.mysql_password.get_secret_value(), database=s.mysql_database)
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=a.days)
    with c.cursor() as cur:
        cur.execute(
            "SELECT e.ts, e.tool, COALESCE(JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.target_full')), e.target), "
            "cs.cwd, cs.cc_session_id, p.name FROM event e JOIN character_session cs ON cs.id = e.session_id "
            "JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
            "WHERE e.type = 'tool_use' AND e.source = 'transcript' AND e.ts >= %s", (since,))
        rows = cur.fetchall()
    uid = os.getuid()
    asks = {"old": collections.Counter(), "new": collections.Counter()}
    rules = {"old": collections.Counter(), "new": collections.Counter()}
    days: dict[str, set] = collections.defaultdict(set)
    dropped, kept = [], []
    today = (datetime.now(UTC).replace(tzinfo=None) + KST).date()
    today_cnt = {"old": collections.Counter(), "new": collections.Counter()}
    for ts, tool, target, cwd, sid, project in rows:
        if not tool or target is None:
            continue
        project = project or "미분류"
        day = (ts + KST).date()
        days[project].add(day)
        inp = {"command": target} if tool == "Bash" else {"file_path": target}
        scratch = None
        if cwd and sid:
            scratch = f"/tmp/claude-{uid}/{re.sub(r'[^A-Za-z0-9]', '-', cwd)}/{sid}/scratchpad"
        out = {}
        for k, pol in (("old", old), ("new", new)):
            try:
                d = pol.decide(tool, inp, cwd, scratch, project if project != "미분류" else None)
            except Exception:  # noqa: BLE001
                continue
            out[k] = d
            if d.verdict == "ask":
                asks[k][project] += 1
                rules[k][(project, d.rule)] += 1
                if day == today:
                    today_cnt[k][project] += 1
        if "old" in out and "new" in out:
            if out["old"].verdict == "ask" and out["new"].verdict != "ask":
                dropped.append((project, out["old"].rule, target))
            elif out["new"].verdict == "ask":
                kept.append((project, out["new"].rule, target))
    print(f"기간: 최근 {a.days}일, 도구 호출 {len(rows)}개 (옛 규칙 = {a.old})\n")
    print("| 프로젝트 | 날 수 | 옛 규칙 ask/일 | 새 규칙 ask/일 | 오늘(KST) 옛 → 새 |")
    print("|---|---|---|---|---|")
    for proj in sorted(days, key=lambda x: -asks["old"][x]):
        n = max(1, len(days[proj]))
        print(f"| {proj} | {n} | {asks['old'][proj] / n:.1f} | {asks['new'][proj] / n:.1f} | "
              f"{today_cnt['old'][proj]} → {today_cnt['new'][proj]} |")
    print("\n빠진 ask(옛 → 새) 규칙별:", collections.Counter((p, r) for p, r, _ in dropped).most_common(12))
    print("남은 ask 규칙별:", rules["new"].most_common(12))
    if a.show:
        print("\n— 빠진 것 예시")
        for p, r, t in dropped[: a.show]:
            print(f"  [{p}] {r}: {t[:160]!r}")
        print("— 남은 것 예시")
        for p, r, t in kept[: a.show]:
            print(f"  [{p}] {r}: {t[:160]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
