"""서기에게 물어보기(11-10) — 읽기 전용 `claude -p` 한 번. 가짜 claude로 인자 · 답 · 거절을 본다."""

import json
import stat
import subprocess

import pytest

from bridge import scribe_ask as sa
from bridge.inject import Refused


class _Res:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _Conn:
    def __init__(self, repo):
        self.repo = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, *a, **k):
        return _Res((self.repo,) if self.repo else None)


class _Engine:
    def __init__(self, repo):
        self.repo = repo

    def connect(self):
        return _Conn(self.repo)


def _repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    return str(r)


def _fake(tmp_path, body):
    p = tmp_path / "claude"
    p.write_text("#!/bin/bash\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    async def mat(*a, **k):
        return "# 재료"
    async def rec(*a, **k):
        rec.called = (a, k)
        return 1
    monkeypatch.setattr(sa, "material", mat)
    monkeypatch.setattr(sa, "record_cli", rec)
    return rec


async def test_ask_returns_answer_and_is_read_only(tmp_path):
    args_file = tmp_path / "args.txt"
    stdin_file = tmp_path / "stdin.txt"
    bin_ = _fake(tmp_path, f'echo "$@" > {args_file}\ncat > {stdin_file}\necho \'{json.dumps({"result": "README 3절입니다."})}\'\n')
    r = await sa.ask(_Engine(_repo(tmp_path)), "foreman", "나중에 할 일은 어디에 있나?", claude_bin=bin_)
    assert r["answer"] == "README 3절입니다."
    args = args_file.read_text()
    assert "--allowedTools Read,Grep,Glob" in args
    assert "Edit" in args.split("--disallowedTools")[1] and "Bash" in args.split("--disallowedTools")[1]
    assert "--no-session-persistence" in args
    sent = stdin_file.read_text()
    assert "나중에 할 일은 어디에 있나?" in sent and "# 재료" in sent


async def test_ask_refuses_empty_long_and_unknown_repo(tmp_path):
    e = _Engine(_repo(tmp_path))
    with pytest.raises(Refused):
        await sa.ask(e, "foreman", "   ")
    with pytest.raises(Refused):
        await sa.ask(e, "foreman", "가" * (sa.ASK_MAX + 1))
    with pytest.raises(Refused, match="저장소"):
        await sa.ask(_Engine(None), "foreman", "질문")


async def test_ask_refuses_when_no_answer(tmp_path):
    bin_ = _fake(tmp_path, "cat > /dev/null\necho 'not json'\n")
    # json이 아니면 raw 전체가 아니라 빈 답으로 보고 거절한다
    with pytest.raises(Refused, match="답을 받지 못했습니다"):
        await sa.ask(_Engine(_repo(tmp_path)), "foreman", "질문", claude_bin=bin_)
