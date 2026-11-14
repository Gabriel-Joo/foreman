"""실제 설정을 읽어 모양만 본다(11-14) — 값은 보지 않는다.

다른 시험은 실제 config/*.toml 대신 임시 파일 · 고정물을 읽는다(설정을 켜고 끌 때마다 시험이 깨지지 않게,
log/test_isolation_20261114.md). 그래도 실제 설정 하나는 읽어 둔다: 오타 · 빠진 칸이 있으면 브리지는 많은 곳에서
기본값으로 조용히 넘어간다(예: roles.toml을 못 읽으면 역할 검사가 off). 그런 고장은 이 시험이 잡는다.
값(켬 · 끔, 문턱, 가격)을 바꾸는 것으로는 깨지지 않게 — 칸이 있는지, 읽히는지, 값의 꼴(범위 · 정규식)만 본다.
이 저장소(worktree면 그 폴더)의 config/를 읽는다.
"""

import re
import tomllib
from pathlib import Path

import pytest

from bridge.approval import load_policy
from bridge.notify import load_rules as notify_rules
from bridge.pipeline import load_pipeline
from bridge.roleguard import RolesConfig
from bridge.schemalock import SchemaLock
from bridge.usage import load_config as usage_config

CFG = Path(__file__).resolve().parent.parent / "config"


@pytest.mark.parametrize("name", sorted(p.name for p in CFG.glob("*.toml")))
def test_every_config_parses(name):
    tomllib.loads((CFG / name).read_text(encoding="utf-8"))


def test_approval_loads():
    pol = load_policy(CFG / "approval.toml")
    assert pol.ask_bash                                   # 묻는 규칙이 하나도 없으면 읽기가 잘못된 것


def test_notify_has_project_rules():
    r = notify_rules(CFG / "notify.toml")
    assert r.projects and all(p.prefix for p in r.projects.values())


def test_roles_reads_without_error():
    c = RolesConfig.load(CFG / "roles.toml")
    assert c.error is None and c.mode in ("off", "observe", "enforce")


def test_schema_lock_rules(tmp_path):
    sl = SchemaLock(CFG / "worktree.toml", alive=lambda cc: True, state=tmp_path / "lock.json")
    assert "foreman" in sl.rules
    for r in sl.rules.values():
        assert r["paths"] and all(isinstance(c, re.Pattern) for c in r["commands"])


def test_usage_shape():
    u = usage_config(CFG / "usage.toml")
    assert u.prices and all({"input", "output"} <= set(p) for p in u.prices.values())
    assert u.limits and all(x.key and x.match and x.window_h > 0 for x in u.limits)


def test_pipeline_shape():
    r = load_pipeline(CFG / "pipeline.toml")
    assert r.infra and r.projects
