"""scripts/korean-check.py — 영어 글이면 알리되, 그 글을 인용하지 않는다(11-10)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "korean-check.py"
ENGLISH = "Checking the database migration status carefully before touching anything else here"
KOREAN = "마이그레이션 상태를 먼저 확인한 다음에 다른 곳을 건드리겠습니다. 천천히 진행합니다."


def _transcript(tmp_path, text, uuid="u1"):
    p = tmp_path / "t.jsonl"
    e = {"type": "assistant", "uuid": uuid, "message": {"content": [{"type": "text", "text": text}]}}
    p.write_text(json.dumps(e, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def _run(tmp_path, transcript):
    env = dict(os.environ, FOREMAN_KOCHECK_STATE=str(tmp_path / "state"))
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env,
                       input=json.dumps({"transcript_path": str(transcript), "session_id": "s1"}))
    assert r.returncode == 0
    return r.stdout


def test_english_alerts_without_quoting(tmp_path):
    out = _run(tmp_path, _transcript(tmp_path, ENGLISH))
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "영어였습니다" in ctx
    for word in ("Checking", "database", "migration", "touching"):
        assert word not in out


def test_korean_is_silent(tmp_path):
    assert _run(tmp_path, _transcript(tmp_path, KOREAN)) == ""


def test_same_uuid_only_once(tmp_path):
    t = _transcript(tmp_path, ENGLISH)
    assert _run(tmp_path, t) != ""
    assert _run(tmp_path, t) == ""
