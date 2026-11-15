"""합치기 준비(11-11 1물결 A 「하나」 · 「넷」, log/plan_structure_20261111.md) — 판에 박힌 단계는 브리지가 기계로.

worktree 세션이 「일을 마침」이 되면 merge-tree를 돌려 **합치기 승인 카드**를 만든다. 사람 화면에는 승인만 뜬다.
- 언제 보나(11-11 사용자): 세션이 응답을 마치는 순간(턴 끝 — on_turn_closed) 바로. 1분 훑기는 놓친 것을 줍는 그물
- 일을 마침: 살아 있고 · 일하지 않고(busy 아님, 열린 턴 없음, 뒤에서 도는 일 없음) · 권한 거부로 멈추지 않음 — 또는 세션이 끝남.
  그리고 worktree에 합칠 커밋이 있고(ahead > 0) 커밋 안 한 변경이 0. 마지막 응답이 묻는 말이어도 일을 마친 것으로 보고, 카드에
  「세션이 묻는 말이 있습니다」를 함께 싣는다(답 기다림과 일을 마침은 따로 — D2 281은 보고 끝 확인 부탁 때문에 카드가 안 떴다)
  (「보고 옴」(대시보드 human_needs의 report)은 사람이 패널을 열면 읽음으로 사라진다 — 읽었든 아니든 일을 마친 것은 같아 묻지 않는다)
- 카드: 브랜치 · 커밋 · 바뀐 파일 · 충돌 여부(`git merge-tree --write-tree`) · ff 가능 / main이 앞섬 · 정리 후보(넷)
- [합치기]: 다시 잰다(카드 뒤 커밋이 바뀌었으면 거절하고 카드를 새로). 충돌 없고 깨끗하면 HandoffManager.worktree_act(merge,
  end=살아 있음) — 살아 있는 세션은 끝내고 합친다. main이 앞섰으면 worktree.merge가 rebase한다(살아 있으면 끝내기 전에 임시
  worktree에서 rebase가 되는지 먼저 본다 — 끝낸 뒤 충돌이면 풀 세션이 없다, docs/11_worktree.md 「6.」).
  충돌이면 끝내지 않고 그 세션에 「main을 가져와 풀라」를 보낸다. 세션이 끝났으면 관리자 세션에
- 결과는 관리자 세션(원본 폴더의 역할 관리자)에 deliver로 남긴다 — 「합쳤습니다 — 시험 · push는 관리자」. 관리자가 없으면 텔레그램
- 1단계는 합치기까지. 2단계(시험 → push → 승인 대기 0 → 브리지 → 점검)는 after_merge 자리만
- 승인자(11-12, log/merge_approver_20261112.md): 프로젝트마다 `[merge_prep.per_project.<이름>] approver = human | manager`.
  manager면 카드가 생길 때 그 프로젝트 관리자 세션에 알리고, 관리자가 `POST …/merge-prep {"action":"merge","by":"manager"}`로
  승인한다(프로젝트 토큰이면 by는 저절로 manager). 늘 사람에게 올릴 것(human_reasons)에 걸리거나 관리자가 없으면 그 카드는 사람 승인.
  squash = true면 bridge/worktree.py merge가 커밋 하나로 묶는다(SQUASH_OF)

조용한 고장 금지: 준비 실패 · 훑기가 stuck_min 넘게 안 끝남 · 합치기 실패 · 관리자에게 못 알림 → 텔레그램 한 번 + 카드(목록)에 사유.
카드는 메모리(self.cards)에서 돌고 DB 표 merge_card(0032)에 맞춰 남긴다(11-13, log/mergeprep_db_20261113.md) — 브리지를 다시
띄우면 뜰 때 되살린다(made_at · 정리 후보 그대로). DB 쓰기가 실패해도 카드는 메모리로 계속 돌고, 텔레그램 한 번 + 목록에 사유.
[나중에]는 session_action 'mprep-skip'(detail = 브랜치 끝 커밋)에 남아 그 커밋이 바뀌기 전까지 다시 띄우지 않는다.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from bridge import worktree as wt
from bridge.inject import Refused, _status, deliver
from bridge.liveness import live_sessions

log = logging.getLogger("foreman.mergeprep")

ACT_CARD, ACT_SKIP, ACT_MERGE, ACT_CONFLICT = "mprep-card", "mprep-skip", "mprep-merge", "mprep-conf"   # session_action(12자까지)
ACT_DOCS = "mprep-docs"      # 11-13 정리 후보를 다 골랐다 — 합친 카드를 치움(detail = 브랜치 끝 커밋)
NOTIFY_KIND = "merge"                                                                                # notification.kind(8자까지)
TURN_END_DELAYS = (3.0, 10.0)        # 턴 끝 뒤 두 번 본다(초) — 시험이 바꾼다


# ── 설정 ────────────────────────────────────────────────
@dataclass
class DocsCfg:
    docs_dir: str = "docs"
    max: int = 12


APPROVERS = ("human", "manager")


@dataclass
class HumanAlways:
    """늘 사람에게 올릴 것(11-12 사용자 확정) — 승인자가 관리자여도 카드의 바뀐 파일 · 커밋이 걸리면 그 카드는 사람 승인."""
    paths: list[str] = field(default_factory=list)          # fnmatch(`*`는 `/`도 넘는다) — 경로 전체와 파일 이름 둘 다에 맞대 본다
    resource_keys: list[str] = field(default_factory=list)  # *.yaml · *.yml에서 이 키 줄이 바뀌면 자원 크기
    history_words: list[str] = field(default_factory=list)  # 커밋 글에 이 말이 있으면 이력 다시 쓰기 · force push
    deletions: bool = True                                  # 파일을 지운 커밋
    submodules: bool = True                                 # 서브모듈(gitlink) 바뀜 = 다른 저장소


@dataclass
class ProjectRule:
    approver: str = "human"            # human = 사람이 [합치기], manager = 그 프로젝트 관리자가 API로 승인
    squash: bool = False               # True면 커밋 하나로 묶어 합친다(bridge/worktree.py merge)
    human_paths: list[str] = field(default_factory=list)   # 이 프로젝트에만 더하는 늘-사람 경로


@dataclass
class MergePrepCfg:
    enabled: bool = False
    every_s: int = 60
    stuck_min: int = 10
    notify_ready: bool = True
    stage: int = 1
    projects: list[str] = field(default_factory=list)     # 비면 모든 프로젝트
    keep_h: int = 6                # 끝난 카드(merged · failed · 충돌 넘김)를 남기는 시간 — updated_at(DB에 남은 시각) 기준
    keep_docs_h: int = 72          # 그중 합친 카드에 정리 후보가 남아 있으면 이만큼(11-13 — 관리자가 고를 시간)
    # 관리자 머리 위 합치기 물음이 이 날수째 떠 있으면 텔레그램 바로 한 번(11-13 사용자 — 7일(ESC_KEEP)이 지나 조용히 묻히지 않게).
    # 0이면 끈다. ESC_KEEP 날수보다 작아야 한다
    remind_days: int = 5
    docs: DocsCfg = field(default_factory=DocsCfg)
    human_always: HumanAlways = field(default_factory=HumanAlways)
    per_project: dict[str, ProjectRule] = field(default_factory=dict)

    def rule(self, project: str | None) -> ProjectRule:
        return self.per_project.get(project or "") or ProjectRule()

    def approver_of(self, project: str | None) -> str:
        return self.rule(project).approver

    def human_paths(self, project: str | None) -> list[str]:
        return [*self.human_always.paths, *self.rule(project).human_paths]


def load(path: str | Path) -> MergePrepCfg:
    """config/handoff.toml [merge_prep]. 파일이 없으면 꺼진 기본값. 값이 틀리면 ValueError — 조용히 기본값으로 가지 않는다."""
    p = Path(path)
    if not p.exists():
        return MergePrepCfg()
    raw = tomllib.loads(p.read_text(encoding="utf-8")).get("merge_prep") or {}
    d = raw.get("docs") or {}
    ha = raw.get("human_always") or {}
    per = {}
    for name, r in (raw.get("per_project") or {}).items():
        a = str(r.get("approver", "human"))
        if a not in APPROVERS:
            raise ValueError(f"merge_prep.per_project.{name}.approver는 human · manager 중 하나입니다(받은 값: {a})")
        per[str(name)] = ProjectRule(approver=a, squash=bool(r.get("squash", False)),
                                     human_paths=[str(x) for x in r.get("human_paths") or []])
    cfg = MergePrepCfg(enabled=bool(raw.get("enabled", False)), every_s=int(raw.get("every_s", 60)),
                       stuck_min=int(raw.get("stuck_min", 10)), notify_ready=bool(raw.get("notify_ready", True)),
                       stage=int(raw.get("stage", 1)), projects=[str(x) for x in raw.get("projects") or []],
                       keep_h=int(raw.get("keep_h", 6)), keep_docs_h=int(raw.get("keep_docs_h", 72)),
                       remind_days=int(raw.get("remind_days", 5)),
                       docs=DocsCfg(docs_dir=str(d.get("docs_dir", "docs")), max=int(d.get("max", 12))),
                       human_always=HumanAlways(paths=[str(x) for x in ha.get("paths") or []],
                                                resource_keys=[str(x) for x in ha.get("resource_keys") or []],
                                                history_words=[str(x) for x in ha.get("history_words") or []],
                                                deletions=bool(ha.get("deletions", True)), submodules=bool(ha.get("submodules", True))),
                       per_project=per)
    if cfg.every_s < 10 or cfg.stuck_min < 1 or cfg.stage not in (1, 2) or cfg.keep_h < 1 or cfg.keep_docs_h < cfg.keep_h:
        raise ValueError("merge_prep 값이 맞지 않습니다(every_s ≥ 10, stuck_min ≥ 1, stage 1 · 2, keep_h ≥ 1, keep_docs_h ≥ keep_h)")
    from bridge.api.dashboard import ESC_KEEP
    if not 0 <= cfg.remind_days < ESC_KEEP.days:
        raise ValueError(f"merge_prep.remind_days는 0(끔) 이상 {ESC_KEEP.days} 미만입니다(받은 값: {cfg.remind_days})")
    return cfg


# ── 늘 사람에게 올릴 것(11-12) ─────────────────────────────────
def parse_raw(out: str) -> list[dict[str, str]]:
    """`git diff --raw --no-renames -z` → [{status, path, old_mode, new_mode}]."""
    parts = out.split("\0")
    res, i = [], 0
    while i < len(parts) - 1:
        head = parts[i]
        if not head.startswith(":"):
            i += 1
            continue
        f = head[1:].split()
        res.append({"old_mode": f[0], "new_mode": f[1], "status": f[4][:1], "path": parts[i + 1]})
        i += 2
    return res


def _yaml_key_hits(diff: str, keys: list[str]) -> dict[str, set[str]]:
    """`git diff -U0` 글 → {파일: {바뀐 자원 키}} — 더하거나 뺀 줄이 `키:`로 시작하면(목록 `- 키:`도)."""
    if not keys:
        return {}
    pat = re.compile(r"^[+-]\s*(?:-\s*)?(" + "|".join(re.escape(k) for k in keys) + r")\s*:")
    out: dict[str, set[str]] = {}
    cur = ""
    for ln in diff.splitlines():
        if ln.startswith("diff --git "):
            cur = ln.split(" b/", 1)[-1]
            continue
        if ln.startswith(("+++", "---")):
            continue
        m = pat.match(ln)
        if m and cur:
            out.setdefault(cur, set()).add(m.group(1))
    return out


def human_reasons(changes: list[dict[str, str]], messages: str, yaml_diff: str, paths: list[str], rules: HumanAlways) -> list[str]:
    """카드를 사람 승인으로 올릴 까닭들(없으면 []). 기계로 가를 수 있는 것만 — 「사람이 직접 쓴 글」은 git으로 가르지 못한다
    (커밋이 모두 같은 사용자 · Co-Authored-By라 — log/merge_approver_20261112.md). 그런 것은 경로(human_paths)로 더하거나 관리자 규칙."""
    why: list[str] = []
    by_pat: dict[str, list[str]] = {}
    for ch in changes:
        p = ch["path"]
        for pat in paths:
            if fnmatch.fnmatchcase(p, pat) or fnmatch.fnmatchcase(os.path.basename(p), pat):
                by_pat.setdefault(pat, []).append(p)
                break
    for pat, ps in by_pat.items():
        why.append(f"늘 사람 경로({pat}): {', '.join(ps[:5])}" + (" …" if len(ps) > 5 else ""))
    hits = _yaml_key_hits(yaml_diff, rules.resource_keys)
    for f, ks in sorted(hits.items()):
        if not any(f in ps for ps in by_pat.values()):
            why.append(f"자원 크기({' · '.join(sorted(ks))}): {f}")
    if rules.deletions:
        gone = [ch["path"] for ch in changes if ch["status"] == "D"]
        if gone:
            why.append(f"지우기(파일 {len(gone)}개를 지움): {', '.join(gone[:5])}" + (" …" if len(gone) > 5 else ""))
    if rules.submodules:
        sub = [ch["path"] for ch in changes if "160000" in (ch["old_mode"], ch["new_mode"])]
        if sub:
            why.append(f"다른 저장소(서브모듈) 바뀜: {', '.join(sub[:5])}")
    low = messages.lower()
    words = [w for w in rules.history_words if w.lower() in low]
    if words:
        why.append(f"이력 다시 쓰기 · force push(커밋 글에 「{'」 · 「'.join(words[:4])}」)")
    return why


def merge_result_of(res: dict[str, Any], base: str) -> dict[str, Any] | None:
    """합치기 결과(bridge/worktree.py merge) → 화면 갈래(11-14). 새 커밋 해시가 없으면(옛 결과 등) None — 화면은 note 원문을 그린다."""
    commit = res.get("into") or res.get("squash")
    if not commit:
        return None
    return {"count": res.get("merged"), "commit": str(commit)[:12], "title": res.get("title"), "squash": bool(res.get("squash")),
            "orig_ref": res.get("orig_ref"), "base": base}


async def pushed_to_origin(repo: str, base: str, commit: str | None) -> bool | None:
    """합친 커밋이 원격 추적 ref(refs/remotes/origin/<base>)에 들어갔나(11-14). push하면 그 ref가 갱신된다.
    True · False, 알 길이 없으면(ref가 없음 · git 실패 · 커밋 모름) None. 원격에 직접 묻지 않는다(fetch 없음 — 1분마다 네트워크를 쓰지 않게)."""
    if not commit:
        return None
    ref = f"refs/remotes/origin/{base}"
    rc, _ = await wt.git(repo, "rev-parse", "--verify", "--quiet", ref, check=False)
    if rc:
        return None
    rc, _ = await wt.git(repo, "merge-base", "--is-ancestor", commit, ref, check=False)
    return True if rc == 0 else False if rc == 1 else None


# ── 순수 판정(시험하기 쉽게 git · DB와 떼어 둠) ────────────────────
def parse_merge_tree(rc: int, out: str) -> list[str] | None:
    """`git merge-tree --write-tree --name-only --no-messages` 결과 → None(충돌 없음) · [충돌 파일]. 그 밖의 실패는 Refused."""
    if rc == 0:
        return None
    if rc == 1:
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        return sorted(set(lines[1:])) or ["(파일 이름을 읽지 못함)"]
    raise Refused(f"git merge-tree 실패(종료 코드 {rc}): {out[-300:]}")


_STOP = {"main", "index", "config", "test", "tests", "api", "init", "readme", "md", "py", "js", "toml", "the", "and", "for",
         "합침", "기록", "고침", "더함", "뺌", "그대로", "있으면", "없으면", "때", "것", "뒤", "전", "수", "줄"}


def _file_keys(files: list[str]) -> dict[str, str]:
    """바뀐 파일 → 찾을 글자(전체 경로 · 파일 이름 · 이름 줄기). 줄기는 4자 이상만(짧은 줄기는 헛걸림)."""
    keys: dict[str, str] = {}
    for f in files:
        keys[f] = f
        base = os.path.basename(f)
        keys.setdefault(base, f)
        stem = os.path.splitext(base)[0].removeprefix("test_")
        if len(stem) >= 4 and stem.lower() not in _STOP:
            keys.setdefault(stem, f)
    return keys


def _has_key(line: str, key: str) -> bool:
    """낱말 경계로만 — `handoff`가 `stage11_handoff_result`에, 줄기가 다른 확장자(`handoff.js`)에 걸리지 않게(11-11 라이브 점검).
    경로 · 파일 이름 앞의 `/`는 같은 파일이라 허용한다."""
    stem = "." not in key and "/" not in key
    tail = r"(?![\w.-])" if stem else r"(?![\w-])"
    return re.search(r"(?<![\w.-])" + re.escape(key) + tail, line) is not None


def doc_candidates(docs: dict[str, str], files: list[str], limit: int = 12) -> dict[str, Any]:
    """이번 작업으로 맞출 수 있는 docs 줄 **후보**(고르기 · 고치기는 승인 뒤 관리자 — 승인자가 사람인 프로젝트는 사람
    승인 뒤, 관리자인 프로젝트는 관리자가 혼자(11-12)). 브리지는 맞대기만 한다.
    바뀐 파일의 경로나 이름을 적은 줄을 문서마다 묶는다. 이번에 그 문서를 고치지 않았으면 `stale`이고, 설계가 바뀌었으면 맞출 후보다.
    README 「나중에 할 일」 표 줄 후보는 11-15에 뺐다(사용자가 표를 없앴다. 할 일은 포스트잇, 알려진 한계는 사람이 포스트잇에서 보낸다.
    합치기나 옮기기가 README에 할 일을 넣거나 그 줄을 세는 길은 없다). 옛 카드 모양과 맞게 "readme"는 늘 빈 목록이다."""
    keys = _file_keys(files)
    changed = set(files)
    dgroups: list[dict[str, Any]] = []
    fkeys = {k: v for k, v in keys.items() if "/" in k or "." in k}       # docs는 경로 · 파일 이름만(줄기는 헛걸림이 많다)
    for path, body in sorted(docs.items()):
        lines = []
        hit: set[str] = set()
        for i, ln in enumerate(body.splitlines(), 1):
            h = {fkeys[k] for k in fkeys if _has_key(ln, k)}
            if h:
                lines.append(i)
                hit |= h
        if lines:
            dgroups.append({"where": path, "lines": lines[:8], "count": len(lines), "files": sorted(hit),
                            "stale": path not in changed})
    dgroups.sort(key=lambda x: -x["count"])
    return {"readme": [], "docs": dgroups[:limit]}


# ── 카드 ─────────────────────────────────────────────────
@dataclass
class Card:
    sid: int
    title: str | None
    project: str | None
    role: str | None
    repo: str
    name: str
    branch: str
    base: str
    head: str                     # 브랜치 끝 커밋(카드의 열쇠 — 바뀌면 다시 만든다)
    base_head: str
    live: bool
    why: str                      # 「일을 마침」의 근거(사람이 읽는 말)
    ahead: int
    behind: int
    commits: list[str]
    files: list[str]
    conflict: list[str] | None    # None = 충돌 없음
    docs: dict[str, Any] | None
    asks: dict[str, Any] | None = None   # 마지막 응답이 묻는 말이면(human_needs의 asks) — 일을 마친 것과 따로 본다. 카드는 뜬다
    via: str = "sweep"            # turn_end(턴 끝에서 바로) · sweep(1분 훑기가 주움)
    status: str = "ready"         # ready · merging · merged · conflict_sent · conflict_manager · failed
    note: str | None = None
    error: str | None = None
    manager_told: bool | None = None
    approver: str = "human"       # 이 카드를 누가 승인하나(11-12) — human · manager. 늘-사람에 걸리거나 관리자가 없으면 human
    human_why: list[str] = field(default_factory=list)   # 늘 사람에게 올린 까닭(비면 걸린 것 없음)
    approved_by: str | None = None    # human · manager — 누가 [합치기]를 눌렀나
    # 11-13 사람 승인 카드를 관리자 머리 위 「사용자 답 기다림」으로 올린 escalate 물음(session_action id) · 그 관리자 세션 id.
    # 못 올렸으면 esc_error에 까닭 — 이때는 작업 세션 머리 위 「합치기 기다림」으로 남는다. 카드 JSON에 실려 DB(merge_card)에도 남는다
    esc_id: int | None = None
    esc_mgr: int | None = None
    esc_error: str | None = None
    # 11-13 사람이 그 물음을 [답 안 해도 됨]으로 끈 시각(브리지가 내린 것과 다르다 — 브리지는 내릴 때 esc_id를 비운다).
    # 있으면 다시 올리지 않고 승인 막대 · 머리 위에서도 뺀다(merge_waits). 카드는 남는다. 새 커밋으로 카드가 다시 만들어지면 비워진다
    esc_off_at: str | None = None
    # 11-14 사용자 「합쳤다는 것과 push가 아직인지 둘뿐」 — 합친 결과를 화면이 나눠 그릴 갈래(note 원문은 그대로 둔다).
    # {count, commit(12), title, squash(bool), orig_ref, base}. pushed = 그 커밋이 refs/remotes/origin/<base>에 들어갔나(훑기가 본다,
    # 모르면 None — 원격 추적 ref가 없거나 git이 실패). 합치기(1단계)는 push하지 않으니 처음엔 False
    merge_result: dict[str, Any] | None = None
    pushed: bool | None = None
    made_at: str = ""
    updated_at: str = ""

    @property
    def ff(self) -> bool:
        return self.behind == 0

    def view(self) -> dict[str, Any]:
        return asdict(self) | {"ff": self.ff, "head8": self.head[:8]}

    def has_docs(self) -> bool:
        d = self.docs or {}
        return bool(d.get("docs"))       # 11-15, 옛 카드에 남은 README 후보는 세지 않는다

    @classmethod
    def from_saved(cls, d: dict[str, Any]) -> Card:
        """DB(merge_card.card)의 JSON → 카드. 모르는 칸은 버리고(뒤 버전이 칸을 더해도 뜬다) 없는 칸은 기본값."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds") + "Z"


def _dt(s: str | None) -> datetime:
    """카드 시각 글(…Z, UTC) → DB DATETIME. 읽지 못하면 지금(칸이 NOT NULL이라)."""
    try:
        return datetime.fromisoformat((s or "").removesuffix("Z"))
    except ValueError:
        return _now()


def card_json(c: Card) -> str:
    return json.dumps(asdict(c), ensure_ascii=False, sort_keys=True)


STORE_UPSERT = text(
    "INSERT INTO merge_card (session_id, project, head, status, card, made_at, updated_at) "
    "VALUES (:sid, :project, :head, :status, :card, :made, :upd) "
    "ON DUPLICATE KEY UPDATE project = VALUES(project), head = VALUES(head), status = VALUES(status), card = VALUES(card), "
    "made_at = VALUES(made_at), updated_at = VALUES(updated_at)")


class MergePrep:
    def __init__(self, handoff: Any, cfg: MergePrepCfg, notifier: Any = None, on_change: Any = None) -> None:
        self.h, self.cfg, self.notifier, self.on_change = handoff, cfg, notifier, on_change
        self.engine, self.sessions_dir = handoff.engine, handoff.sessions_dir
        self.cards: dict[int, Card] = {}
        self.health: dict[str, Any] = {"ok": True, "last": None, "error": None}
        self._lock = asyncio.Lock()          # 훑기 · 턴 끝 · 합치기가 겹치지 않게
        self._task: asyncio.Task[Any] | None = None
        self._tasks: set[asyncio.Task[Any]] = set()       # 턴 끝 확인
        self._touched = False                # 있던 카드의 표시(묻는 말)만 바뀜 — 화면을 다시 그린다
        self.turn_end: dict[str, Any] = {"ok": 0, "fail": 0, "error": None, "at": None}   # 턴 끝 넘기기 — health로 보인다
        self.health["turn_end"] = self.turn_end
        # 카드를 DB(merge_card, 0032)에 남긴다(11-13). engine이 없으면(시험의 가짜) 메모리로만
        self.store: dict[str, Any] = {"on": self.engine is not None, "ok": True, "error": None, "at": None,
                                      "restored": None}
        self._saved: dict[int, str] = {}    # DB에 쓴 카드 JSON — 바뀐 것만 다시 쓰고, 메모리에서 빠진 것은 지운다
        self._sync_lock = asyncio.Lock()
        self._restored = False
        self._reminded: set[int] = set()    # 오래된 합치기 물음 알림을 낸 escalate id — 매 맞추기마다 DB를 보지 않게(DB 키가 진짜 한 번)
        wt.SQUASH_OF = self.squash_for_repo  # 패널 [합치기]도 같은 squash 설정을 따르게(handoff.worktree_act → wt.merge)

    # ── 보기 ──
    def view(self, project: str | None = None) -> dict[str, Any]:
        """project를 주면 그 프로젝트 카드만(관리자가 자기 카드를 모아 본다 — GET /api/merge-prep?project=, 11-12)."""
        cards = [c for c in self.cards.values() if project is None or c.project == project]
        return {"enabled": self.cfg.enabled, "stage": self.cfg.stage, "health": self.health, "store": self.store,
                **({"project": project, "approver": self.cfg.approver_of(project),
                    "squash": self.cfg.rule(project).squash} if project is not None else {}),
                "cards": [c.view() for c in sorted(cards, key=lambda c: c.made_at, reverse=True)]}

    async def squash_for_repo(self, repo: str) -> bool:
        """저장소 경로 → 그 프로젝트의 squash 설정(project.repo_path로 찾는다). 못 찾으면 False(지금 동작)."""
        if not any(r.squash for r in self.cfg.per_project.values()):
            return False
        try:
            async with self.engine.connect() as c:
                rows = (await c.execute(text("SELECT name, repo_path FROM project"))).all()
        except Exception as e:  # noqa: BLE001 — 못 읽으면 지금 동작(ff)으로. 조용히 넘어가지 않게 남긴다
            log.warning("squash 설정을 위한 프로젝트 찾기 실패 — ff로 합친다: %s", type(e).__name__)
            return False
        real = os.path.realpath(repo)
        for name, rp in rows:
            if rp and os.path.realpath(rp) == real:
                return self.cfg.rule(name).squash
        return False

    def card_for(self, sid: int) -> dict[str, Any] | None:
        c = self.cards.get(sid)
        return c.view() if c else None

    # ── DB에 남기기(11-13, merge_card) ──
    async def restore(self) -> int:
        """브리지가 뜰 때 DB의 카드를 되살린다 — made_at · updated_at · 정리 후보 그대로(「오래됨」이 다시 잡히지 않게, 끝난 카드의
        남김 시간도 DB 시각 기준). 브랜치 끝 커밋이 바뀌었으면 다음 훑기가 지금처럼 다시 만든다(prep). 합치는 중(merging)이던
        카드는 결과를 모르니 failed로 바꿔 사유를 단다. 읽기가 실패하면 빈 카드로 돌고 텔레그램 한 번 + 목록에 사유."""
        if not self.store["on"]:
            self._restored = True
            return 0
        async with self._lock:
            try:
                async with asyncio.timeout(15):
                    async with self.engine.connect() as cn:
                        rows = (await cn.execute(text("SELECT session_id, card FROM merge_card"))).all()
            except Exception as e:  # noqa: BLE001 — 못 읽어도 브리지 · 훑기는 돈다(카드는 다시 만든다)
                self._store_bad(f"합치기 카드를 DB에서 되살리지 못했습니다({type(e).__name__}: {str(e)[:160]}). 카드는 다시 "
                                "만들지만 정리 후보 · 「오래됨」 시각 · 합친 카드가 사라졌을 수 있습니다", "load")
                self._restored = True
                return 0
            n = 0
            for sid, raw in rows:
                try:
                    d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    c = Card.from_saved(d)
                except Exception as e:  # noqa: BLE001 — 한 장이 깨져도 나머지는 되살린다
                    log.warning("합치기 카드 %s를 되살리지 못함: %s", sid, type(e).__name__)
                    continue
                self._saved[int(sid)] = card_json(c)   # DB에 있는 그대로 — 바뀌면 다시 쓴다
                if c.status == "merging":
                    c.status = "failed"
                    c.error = "합치는 중에 브리지가 다시 떴습니다. 결과를 모릅니다. git log · 작업방을 확인해 주세요"
                    c.updated_at = _iso(_now())
                cur = self.cards.get(int(sid))
                if cur is not None:                    # 되살리기 전에 턴 끝이 먼저 만든 카드 — 같은 커밋이면 처음 시각을 잇는다
                    if cur.head == c.head:
                        cur.made_at = c.made_at
                    continue
                self.cards[int(sid)] = c
                n += 1
            self.store["restored"] = n
            self._restored = True
        await self.sync()
        if n and self.on_change:
            self.on_change()
        log.info("합치기 카드 %d장을 DB에서 되살렸다", n)
        return n

    async def sync(self) -> None:
        """메모리 카드 → DB. 바뀐 카드만 쓰고(card JSON을 견준다) 메모리에서 빠진 카드는 지운다. 실패하면 다음 번에 다시 —
        카드는 메모리로 계속 돈다. 되살리기 전에는 쓰지 않는다(DB에 남은 카드를 지우지 않게)."""
        if not self.store["on"] or not self._restored:
            return
        async with self._sync_lock:
            try:
                await self._esc_sync()       # 사람 승인 카드 → 관리자 머리 위 물음(카드 칸 esc_*가 바뀌면 아래에서 함께 쓴다)
            except Exception as e:  # noqa: BLE001 — 올리기 실패가 카드 저장을 막지 않는다. 카드에 까닭이 남고 작업 세션 머리 위로
                log.warning("합치기 카드 물음 맞추기 실패: %s", type(e).__name__)
            snap = {sid: (c, card_json(c)) for sid, c in list(self.cards.items())}
            put = {sid: v for sid, v in snap.items() if self._saved.get(sid) != v[1]}
            gone = [sid for sid in self._saved if sid not in snap]
            if not put and not gone:
                return
            try:
                async with asyncio.timeout(15):
                    async with self.engine.begin() as cn:
                        for sid, (c, js) in put.items():
                            await cn.execute(STORE_UPSERT, {"sid": sid, "project": c.project, "head": c.head or "", "status": c.status,
                                                            "card": js, "made": _dt(c.made_at), "upd": _dt(c.updated_at)})
                        if gone:
                            from sqlalchemy import bindparam
                            await cn.execute(text("DELETE FROM merge_card WHERE session_id IN :s")
                                             .bindparams(bindparam("s", expanding=True)), {"s": gone})
            except Exception as e:  # noqa: BLE001 — 저장 실패가 카드 · 합치기를 막지 않는다
                self._store_bad(f"합치기 카드를 DB에 남기지 못했습니다({type(e).__name__}: {str(e)[:160]}). 카드는 메모리로 돌지만 "
                                "브리지를 다시 띄우면 사라집니다", "save")
                return
            for sid, (_, js) in put.items():
                self._saved[sid] = js
            for sid in gone:
                self._saved.pop(sid, None)
            if not self.store["ok"]:
                log.info("합치기 카드 DB 저장이 다시 됩니다")
                self.store.update(ok=True, error=None, at=_iso(_now()))
                self._apply_store_health()
                if self.on_change:
                    self.on_change()

    def _sync_soon(self) -> None:
        """잠금 밖 · 동기 자리(worktree_gone 등)에서 — 저장을 예약만 한다."""
        if not self.store["on"]:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        t = loop.create_task(self.sync())
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def _store_bad(self, why: str, what: str) -> None:
        """조용한 고장 금지 — 처음 실패할 때 텔레그램 한 번 + 목록(health)에 사유. 다시 될 때까지 또 보내지 않는다.
        _notify는 보낸 적이 있는지 DB에서 보는데, DB가 문제일 수 있어 여기서는 메모리 표시로 한 번만 보낸다(DB 전체가 죽었으면
        알림 기록도 못 해 텔레그램이 안 나간다 — notifier 한계, log/mergeprep_db_20261113.md)."""
        first = self.store["ok"]
        self.store.update(ok=False, error=why, at=_iso(_now()))
        self._apply_store_health()
        log.warning(why)
        if first:
            self._notify(None, f"mergeprep:db:{what}:{_now():%Y%m%d%H%M}", f"⚠ {why}", check_db=False)
        if self.on_change:
            self.on_change()

    def _apply_store_health(self) -> None:
        """저장 실패는 health에도 싣는다 — 패널 「합치기 승인」이 health.error를 띄운다(handoff.js)."""
        if not self.store["ok"]:
            self.health = {**self.health, "ok": False, "error": self.store["error"], "store": False}
        elif self.health.get("store") is False:
            self.health = {**self.health, "ok": True, "error": None, "store": True}

    def _expired(self, c: Card, cut: str, cut_docs: str) -> bool:
        """끝난 카드를 치울 때인가 — updated_at 기준 keep_h, 합친 카드에 정리 후보가 남았으면 keep_docs_h(11-13)."""
        if c.status == "merged" and c.has_docs():
            return c.updated_at < cut_docs
        return c.updated_at < cut

    # ── 사람 승인 카드 → 관리자 머리 위(11-13 사용자 — 「나는 관리자하고만 이야기한다」) ──
    @staticmethod
    def human_card(c: Card) -> bool:
        """사람이 눌러야 하는 대기 카드인가 — dashboard.merge_waits와 같은 기준(관리자가 승인하는 카드는 뺀다)."""
        return c.status == "ready" and not (c.approver == "manager" and not c.human_why)

    def esc_text(self, c: Card) -> str:
        why = "; ".join(c.human_why) if c.human_why else (c.note or "이 프로젝트의 합치기 승인자는 사람입니다")
        cf = f" 충돌 파일 {len(c.conflict)}개." if c.conflict else ""
        return (f"세션 {c.sid} 「{c.title or ''}」 합치기 카드에 사람 승인이 필요합니다(사유: {why}).{cf} "
                f"패널 [합치기]를 눌러 주십시오(세션 {c.sid} 패널 「세션 정리」 탭)")

    async def _esc_manager(self, c: Card) -> int | None:
        """그 저장소 원본 폴더에 살아 있는 관리자 세션 id — 없으면 None."""
        m = await self.manager_of(c.repo)
        if m is None:
            return None
        async with self.engine.connect() as cn:
            r = (await cn.execute(text("SELECT MAX(id) FROM character_session WHERE cc_session_id = :c AND hidden_at IS NULL"),
                                  {"c": m[0]})).first()
        return int(r[0]) if r and r[0] is not None else None

    async def _esc_open(self) -> dict[int, tuple[int, datetime]]:
        """아직 떠 있는 합치기 카드 물음 {escalate id: (관리자 세션 id, 올린 시각)} — DB에서 본다(메모리에서 빠진 카드 · 다시 띄운
        사이 것도 줍는다)."""
        from bridge.api.dashboard import ESC_ACT, ESC_KEEP, ESC_OFF_ACT
        async with self.engine.connect() as cn:
            rows = (await cn.execute(text(
                "SELECT a.id, a.session_id, a.created_at FROM session_action a WHERE a.action = :a AND a.ok AND a.detail LIKE :p "
                "AND a.created_at > :cut AND NOT EXISTS (SELECT 1 FROM session_action o WHERE o.session_id = a.session_id "
                "  AND o.action = :o AND o.ok AND o.detail = CAST(a.id AS CHAR))"),
                {"a": ESC_ACT, "o": ESC_OFF_ACT, "p": "question:#merge:%", "cut": _now() - ESC_KEEP})).all()
        return {int(a): (int(s), at) for a, s, at in rows}

    async def _esc_offs(self, ids: list[int]) -> dict[int, datetime]:
        """이 물음들 중 꺼진 것 {escalate id: 끈 시각}. 카드가 아직 쥔 물음에 대한 esc-off는 사람의 [답 안 해도 됨]이다 —
        브리지가 내릴 때(_esc_close)는 카드의 esc_id를 함께 비운다."""
        from sqlalchemy import bindparam

        from bridge.api.dashboard import ESC_OFF_ACT
        async with self.engine.connect() as cn:
            rows = (await cn.execute(text(
                "SELECT detail, MIN(created_at) FROM session_action WHERE action = :o AND ok AND detail IN :d GROUP BY detail")
                .bindparams(bindparam("d", expanding=True)), {"o": ESC_OFF_ACT, "d": [str(i) for i in ids]})).all()
        return {int(d): at for d, at in rows}

    def esc_remind_text(self, c: Card) -> str:
        from bridge.api.dashboard import ESC_KEEP
        left = ESC_KEEP.days - self.cfg.remind_days
        when = {1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새"}.get(left, f"{left}일")
        return (f"⏳ 합치기 카드가 {self.cfg.remind_days}일째 사람 승인을 기다립니다 — {when} 뒤 관리자 머리 위에서 사라집니다"
                f"(카드는 남음) · 세션 {c.sid} 「{c.title or ''}」")

    def esc_expired_text(self, c: Card) -> str:
        return (f"⏳ 합치기 카드 물음이 7일이 지나 관리자 머리 위에서 사라졌습니다 — 카드는 남아 있습니다 · 세션 {c.sid} "
                f"「{c.title or ''}」 · 브리지가 꺼져 있던 동안 지났습니다")

    def _esc_catchup(self, c: Card, eid: int) -> None:
        """7일(ESC_KEEP)이 지나 머리 위에서 사라졌는데 5일째 알림을 못 받은 물음 — 브리지가 다시 떠서 보게 되면 한 번 알린다
        (11-13 사용자). 열쇠는 5일째 알림과 같아 이미 보냈으면 _notify가 안 보낸다. 사람이 끈 것은 부르는 쪽이 걸러 둔다."""
        if not self.cfg.remind_days or eid in self._reminded:
            return
        self._reminded.add(eid)
        self._notify(c, f"mergeprep:remind:{eid}", self.esc_expired_text(c), later=False)
        log.info("합치기 카드 %s — 물음 %s가 7일이 지나 사라졌다(이미 알렸으면 안 보냄)", c.sid, eid)

    def _esc_remind(self, c: Card, eid: int, at: datetime) -> None:
        """관리자 머리 위 합치기 물음이 remind_days째 떠 있으면 텔레그램 바로 한 번(묶음 아님). 열쇠는 그 물음 id —
        브리지를 다시 띄워도 한 번(_notify가 notification.rule을 본다). 사람이 끈 물음은 _esc_open에 없으니 알리지 않는다."""
        if not self.cfg.remind_days or eid in self._reminded or _now() - at < timedelta(days=self.cfg.remind_days):
            return
        self._reminded.add(eid)
        self._notify(c, f"mergeprep:remind:{eid}", self.esc_remind_text(c), later=False)
        log.info("합치기 카드 %s — 관리자 머리 위 물음 %s가 %d일째라 알렸다", c.sid, eid, self.cfg.remind_days)

    async def _esc_close(self, eid: int, msid: int) -> None:
        from bridge.api.dashboard import ESC_OFF_ACT, invalidate
        async with self.engine.begin() as cn:
            await cn.execute(text("INSERT INTO session_action (session_id, action, ok, detail) VALUES (:s, :a, 1, :d)"),
                             {"s": msid, "a": ESC_OFF_ACT, "d": str(eid)})
        invalidate()

    async def _esc_sync(self) -> None:
        """사람 승인 카드가 있으면 그 프로젝트 관리자에게 escalate 물음을 기계적으로 만든다(관리자가 잊으면 조용히 묻히니 모델 판단에
        맡기지 않는다). 카드가 합쳐지거나 · 미뤄지거나 · 없어지거나 · 관리자가 바뀌면 그 물음을 내린다(esc-off).
        관리자가 없거나 올리지 못하면 esc_error에 까닭 — 작업 세션 머리 위 「합치기 기다림」으로 남는다(dashboard.merge_waits)."""
        if self.engine is None or not self._restored:
            return
        from bridge.api.dashboard import escalate, merge_tag
        want = {sid: c for sid, c in list(self.cards.items()) if self.cfg.enabled and self.human_card(c)}
        changed = False
        opened = await self._esc_open()
        held = {c.esc_id for c in want.values() if c.esc_id}
        # 사람이 끈 것 알아보기(11-13 사용자 — 「답 안 해도 됨은 답을 안 하겠다는 뜻이다」) — 카드가 쥔 물음이 떠 있지 않으면 esc-off를
        # 찾는다. 있으면 사람이 끈 것, 없으면 7일(ESC_KEEP)이 지나 사라진 것(이때는 지금처럼 둔다)
        gone = [c for c in want.values() if c.esc_id and not c.esc_off_at and c.esc_id not in opened]
        if gone:
            offs = await self._esc_offs([c.esc_id for c in gone if c.esc_id])
            for c in gone:
                if c.esc_id in offs:
                    c.esc_off_at, changed = _iso(offs[c.esc_id]), True
                    log.info("합치기 카드 %s — 사람이 관리자 머리 위 물음 %s를 껐다(다시 올리지 않음)", c.sid, c.esc_id)
                elif c.esc_id:                              # 끈 것도 아닌데 떠 있지 않다 = 7일이 지나 사라졌다 — 못 받은 알림을 따라 보낸다
                    self._esc_catchup(c, c.esc_id)
        for eid, (msid, _) in opened.items():               # 내리기 — 그 물음을 쥔 대기 카드가 없다
            if eid in held:
                continue
            await self._esc_close(eid, msid)
            for c in self.cards.values():
                if c.esc_id == eid:
                    c.esc_id, c.esc_mgr = None, None
            changed = True
        for sid, c in want.items():                         # 올리기 — 관리자가 바뀌었으면 옛 것을 내리고 새 관리자에게
            if c.esc_off_at:                                # 사람이 끈 카드 — 관리자가 바뀌어도 다시 올리지 않는다(새 커밋이면 새 카드)
                continue
            try:
                msid = await self._esc_manager(c)
            except Exception as e:  # noqa: BLE001 — 관리자를 못 찾으면 작업 세션 머리 위로(안전한 쪽)
                msid, why = None, f"관리자를 찾지 못했습니다({type(e).__name__})"
            else:
                why = "살아 있는 관리자 세션이 없습니다"
            if c.esc_id and c.esc_mgr == msid:
                if c.esc_id in opened:                      # 같은 관리자에게 떠 있다 — 오래됐으면 한 번 알린다(인계로 다시 올리면 7일도 새로)
                    self._esc_remind(c, c.esc_id, opened[c.esc_id][1])
                continue
            if c.esc_id:
                if c.esc_id in opened:
                    await self._esc_close(c.esc_id, c.esc_mgr or 0)
                c.esc_id = c.esc_mgr = None
                changed = True
            if msid is None:
                if c.esc_error != why:
                    c.esc_error, changed = why, True
                continue
            try:
                r = await escalate(self.engine, msid, "question", self.esc_text(c),
                                   notifier=None if self.cfg.notify_ready else self.notifier, tag=merge_tag(sid))
            except Exception as e:  # noqa: BLE001 — 못 올리면 작업 세션 머리 위로
                why = f"관리자에게 올리지 못했습니다({type(e).__name__}: {str(getattr(e, 'detail', e))[:120]})"
                if c.esc_error != why:
                    c.esc_error, changed = why, True
                log.warning("합치기 카드 %s 물음 올리기 실패: %s", sid, why)
                continue
            cur = self.cards.get(sid)                       # 기다리는 사이 같은 커밋으로 카드가 바뀌었으면 그 카드에도
            for x in [c] + ([cur] if cur is not None and cur is not c and cur.head == c.head else []):
                x.esc_id, x.esc_mgr, x.esc_error = int(r["id"]), msid, None
            changed = True
            log.info("합치기 카드 %s를 관리자 세션 %s 머리 위로 올렸다(escalate %s)", sid, msid, r["id"])
        if changed and self.on_change:
            self.on_change()

    # ── 훑기 ──
    async def _candidates(self) -> list[tuple[Any, ...]]:
        """worktree에서 띄운 세션 — 그 worktree 폴더의 마지막 세션만(이름을 다시 쓴 앞 세션은 뺀다). 숨긴 세션은 보지 않는다."""
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cs.id, cs.cc_session_id, cs.cwd, COALESCE(cs.custom_title, cs.title), p.name, cs.role "
                "FROM character_session cs JOIN `character` ch ON ch.id = cs.character_id LEFT JOIN project p ON p.id = ch.project_id "
                "WHERE cs.type = 'agent' AND cs.hidden_at IS NULL AND cs.cwd LIKE :w AND cs.id IN ("
                "  SELECT MAX(id) FROM character_session WHERE cwd LIKE :w GROUP BY cwd)"), {"w": f"%/{wt.WT_DIR}/%"})).all()
        out = []
        seen: set[str] = set()
        for r in sorted(rows, key=lambda r: -r[0]):
            repo, name = wt.split(r[2] or "")
            key = f"{repo}/{name}"
            if not name or key in seen or not os.path.isdir(os.path.join(repo, wt.WT_DIR, name)):
                continue
            if self.cfg.projects and r[4] not in self.cfg.projects:
                continue
            seen.add(key)
            out.append(r)
        return out

    async def _done_live(self, sid: int, cc: str, pid: int) -> str | None:
        """살아 있는 세션이 일을 마쳤나 — 마쳤으면 근거 글, 아니면 None.
        11-11(사용자): 답을 기다리는 것과 일을 마친 것은 따로 본다 — 보고 끝 확인 부탁(「…한 번씩 확인해 주세요」)이 답 기다림으로
        잡혀 카드가 아예 안 떴다(D2 281). 묻는 말은 _asks로 카드에 함께 싣는다. 권한 거부로 멈춘 것은 일을 마친 것이 아니다."""
        if _status(self.sessions_dir, pid) == "busy":
            return None
        from bridge.api.dashboard import human_needs
        async with self.engine.connect() as c:
            if (await c.execute(text("SELECT 1 FROM turn WHERE session_id = :s AND ended_at IS NULL LIMIT 1"), {"s": sid})).first():
                return None
            if not (await c.execute(text("SELECT 1 FROM event WHERE session_id = :s AND type = 'assistant_msg' LIMIT 1"),
                                    {"s": sid})).first():
                return None
            needs = (await human_needs(c, f"({int(sid)})")).get(sid) or {}
        if needs.get("denied"):
            return None
        row = await self.h.session(sid)
        if row is None or await self.h._running_work(row, pid):
            return None
        return "보고 옴(일하지 않고 응답을 마쳤습니다)"

    async def _asks(self, sid: int) -> dict[str, Any] | None:
        """마지막 응답이 사람에게 묻는 말이면 {at, tail, event_id}(대시보드 「답 기다림」과 같은 판정). 사람이 [답 안 해도 됨]으로
        끈 것은 없다."""
        from bridge.api.dashboard import human_needs
        async with self.engine.connect() as c:
            return ((await human_needs(c, f"({int(sid)})")).get(sid) or {}).get("asks")

    async def _skipped(self, sid: int, head: str) -> bool:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT detail FROM session_action WHERE session_id = :s AND action = :a ORDER BY id DESC LIMIT 1"),
                {"s": sid, "a": ACT_SKIP})).first()
        return bool(r and r[0] == head)

    async def _git_facts(self, repo: str, name: str) -> dict[str, Any]:
        st = await wt.status(repo, name)
        if not st.get("exists"):
            return st
        _, head = await wt.git(repo, "rev-parse", st["branch"])
        _, bhead = await wt.git(repo, "rev-parse", st["base"])
        st["head"], st["base_head"] = head.strip(), bhead.strip()
        return st

    async def _conflict(self, repo: str, base: str, branch: str) -> list[str] | None:
        rc, out = await wt.git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", base, branch, check=False)
        return parse_merge_tree(rc, out)

    async def _docs(self, repo: str, base: str, branch: str, st: dict[str, Any]) -> dict[str, Any]:
        d = self.cfg.docs
        _, files = await wt.git(repo, "diff", "--name-only", f"{base}...{branch}")
        rc2, names = await wt.git(repo, "ls-tree", "-r", "--name-only", base, "--", d.docs_dir, check=False)
        docs: dict[str, str] = {}
        for n in (names.splitlines() if rc2 == 0 else [])[:200]:
            if n.endswith(".md"):
                r3, body = await wt.git(repo, "show", f"{base}:{n}", check=False)
                if r3 == 0:
                    docs[n] = body
        return doc_candidates(docs, files.splitlines(), d.max)

    async def prep(self, r: tuple[Any, ...], live: dict[str, Any], via: str = "sweep") -> Card | None:
        """한 세션 — 일을 마쳤고 합칠 것이 있으면 카드(같은 커밋이면 있던 카드 그대로). 아니면 None(있던 ready 카드는 치운다)."""
        sid, cc, cwd, title, project, role = r
        repo, name = wt.split(cwd)
        ls = live.get(cc or "")
        if ls is not None and ls.state == "T":
            return None                                   # 사람이 멈춰 둔 세션은 건드리지 않는다
        why = await self._done_live(sid, cc, ls.pid) if ls else "세션이 끝났습니다"
        if not why:
            return None
        st = await self._git_facts(repo, name)
        if not st.get("exists") or st["ahead"] == 0 or st["dirty"]:
            return None
        asks = await self._asks(sid) if ls else None       # 끝난 세션은 답할 곳이 없다
        old = self.cards.get(sid)
        if old and (old.status == "merging" or (old.head == st["head"] and old.base_head == st["base_head"] and old.live == bool(ls))):
            if old.status == "ready" and old.asks != asks:  # 같은 커밋에서 묻는 말만 생기거나 풀림 — 카드는 그대로, 표시만
                old.asks, old.updated_at = asks, _iso(_now())
                self._touched = True
            return old
        if await self._skipped(sid, st["head"]):
            return None
        conflict = await self._conflict(repo, st["base"], st["branch"])
        try:
            docs = await self._docs(repo, st["base"], st["branch"], st)
        except Exception as e:  # noqa: BLE001 — 후보를 못 뽑아도 카드는 낸다(사유를 붙여)
            docs = {"error": f"정리 후보를 뽑지 못했습니다({type(e).__name__})", "readme": [], "docs": []}
        _, files = await wt.git(repo, "diff", "--name-only", f"{st['base']}...{st['branch']}")
        now = _iso(_now())
        # 같은 커밋(main만 앞섬 · live만 바뀜)이면 처음 만든 시각을 잇는다 — 「오래됨」은 사람이 기다린 시간이다(11-13)
        made = old.made_at if old is not None and old.status == "ready" and old.head == st["head"] and old.made_at else now
        card = Card(sid=sid, title=title, project=project, role=role, repo=repo, name=name, branch=st["branch"], base=st["base"],
                    head=st["head"], base_head=st["base_head"], live=bool(ls), why=why, ahead=st["ahead"], behind=st["behind"],
                    commits=st["commits"], files=files.splitlines()[:60], conflict=conflict, docs=docs, asks=asks, via=via,
                    made_at=made, updated_at=now)
        mgr = None
        if self.cfg.approver_of(project) == "manager":
            try:
                card.human_why = await self._human_why(repo, st["base"], st["branch"], project)
            except Exception as e:  # noqa: BLE001 — 가르지 못하면 사람에게(안전한 쪽)
                card.human_why = [f"늘-사람 판정 실패({type(e).__name__}), 사람 승인으로 둡니다"]
            mgr = await self.manager_of(repo)
            if card.human_why:
                card.note = "사람 승인 카드입니다. 승인자는 관리자지만 늘 사람에게 올릴 것에 걸렸습니다: " + "; ".join(card.human_why)
            elif mgr is None:
                card.note = "승인자는 관리자지만 살아 있는 관리자 세션이 없어 사람이 승인합니다."
            else:
                card.approver = "manager"
                card.note = "관리자가 승인합니다. 관리자 세션에 카드를 알렸습니다. 사람 화면(승인 막대 · 말풍선 · [합치기])에는 띄우지 않습니다."
        if old is None or old.head != card.head:
            await self.h._act(sid, ACT_CARD, None, True, f"{name} {card.head[:8]} " + ("충돌 " + ",".join(conflict)[:300] if conflict else "충돌 없음")
                              + (" · 묻는 말 있음" if asks else "") + (" · 턴 끝" if via == "turn_end" else " · 훑기")
                              + (f" · 승인 {card.approver}" + (f"(사람 까닭 {len(card.human_why)})" if card.human_why else "")
                                 if self.cfg.approver_of(project) == "manager" else ""))
            if self.cfg.notify_ready:
                self._notify(card, f"mergeprep:ready:{sid}:{card.head[:12]}",
                             f"⑂ 합치기 준비됨 — 「{title or sid}」(세션 {sid}) {card.branch} 커밋 {card.ahead}개, "
                             + (f"충돌 {len(conflict)}개" if conflict else ("충돌 없음 · ff 가능" if card.ff else f"충돌 없음 · {card.base}에 새 커밋 {card.behind}개(rebase)"))
                             + (f"\n❓ 세션이 묻는 말이 있습니다 — 패널에서 답하십시오: {asks.get('tail') or ''}" if asks else "")
                             + ("\n▶ 관리자 세션이 승인합니다(사람 승인 필요 없음)" if card.approver == "manager"
                                else (f"\n⚠ 사람 승인 — {'; '.join(card.human_why)}" if card.human_why else "")
                                + "\n▶ 그 세션 패널의 「합치기 승인」에서 승인합니다"))
            if mgr is not None:
                self._spawn(self._tell_manager_card(card, mgr))
        elif old is not None and old.status == "ready":
            card.manager_told = old.manager_told              # 같은 커밋 — 관리자에게 다시 알리지 않는다(live만 바뀐 경우)
            card.esc_id, card.esc_mgr, card.esc_error = old.esc_id, old.esc_mgr, old.esc_error   # 올린 물음도 그대로
            card.esc_off_at = old.esc_off_at                  # 사람이 끈 것도 그대로(같은 일)
        return card

    async def _human_why(self, repo: str, base: str, branch: str, project: str | None) -> list[str]:
        _, raw = await wt.git(repo, "diff", "--raw", "--no-renames", "-z", f"{base}...{branch}")
        _, msgs = await wt.git(repo, "log", "--format=%B", f"{base}..{branch}")
        _, ydiff = await wt.git(repo, "diff", "-U0", "--no-renames", f"{base}...{branch}", "--", "*.yaml", "*.yml")
        return human_reasons(parse_raw(raw), msgs, ydiff, self.cfg.human_paths(project), self.cfg.human_always)

    def _card_msg(self, c: Card) -> str:
        """카드가 생겼을 때 관리자에게(승인자 = 관리자인 프로젝트만)."""
        how = (f"충돌 {len(c.conflict)}개({', '.join(c.conflict[:5])})" if c.conflict
               else ("충돌 없음 · ff 가능" if c.ff else f"충돌 없음 · {c.base}에 새 커밋 {c.behind}개(rebase)"))
        dn = len((c.docs or {}).get("docs") or [])
        sq = (" 이 프로젝트는 squash로 합친다(커밋 하나, 본문에 원래 날짜 · 해시 · 제목). 제목은 세션 제목으로 기계가 만든다 — "
              "묶은 일을 더 잘 말하는 제목이 있으면 승인할 때 \"title\": \"…\"로 넘긴다(그 저장소 커밋 꼴로)."
              if self.cfg.rule(c.project).squash and c.ahead >= 2 else "")
        head = (f"[FOREMAN 합치기 카드] 세션 {c.sid} 「{c.title or ''}」 {c.branch} 커밋 {c.ahead}개 · 바뀐 파일 {len(c.files)}개 · {how}."
                f"{' 세션이 살아 있다 — 승인하면 끝낸다.' if c.live else ''}"
                f"{' 세션이 묻는 말이 있다: ' + str((c.asks or {}).get('tail') or '') if c.asks else ''}")
        see = f" 카드 전부: GET /api/merge-prep?project={c.project}(커밋 · 바뀐 파일 · 정리 후보 {dn}개)."
        if c.human_why:
            return (head + " 이 카드는 **사람 승인**이다 — 승인자는 관리자지만 늘 사람에게 올릴 것에 걸렸다: " + "; ".join(c.human_why)
                    + ". 관리자는 승인하지 않는다(API가 거부한다). 브리지가 이 카드를 관리자 머리 위 「사용자 답 기다림」으로 올린다"
                    "(따로 escalate하지 않는다 — 카드가 합쳐지거나 미뤄지면 브리지가 내린다). 사람이 볼 것을 짧게 정리해 두는 것은 좋다." + see)
        return (head + " 이 프로젝트 합치기 승인자는 관리자다 — 커밋 · 바뀐 파일 · 시험을 보고 합칠지 정한다. 합치기: "
                f"POST /api/sessions/{c.sid}/merge-prep {{\"action\":\"merge\",\"by\":\"manager\"}}(프로젝트 토큰이면 by는 저절로 관리자). "
                "미루기: {\"action\":\"skip\",\"by\":\"manager\"}(새 커밋이 생기면 다시 뜬다). 판단이 안 서면 사람에게 묻는다."
                + sq + see + " 합친 뒤 시험 · push · 정리 후보 고르기는 관리자 몫이다.")

    async def _tell_manager_card(self, c: Card, mgr: tuple[str, str]) -> None:
        ok = await self._deliver(mgr[0], mgr[1], self._card_msg(c))
        c.manager_told = ok
        if not ok:
            self._notify(c, f"mergeprep:mcard:{c.sid}:{c.head[:12]}",
                         f"관리자 세션에 합치기 카드를 알리지 못했습니다 — 「{c.title or c.sid}」(세션 {c.sid}) {c.branch}. 패널에서 승인합니다")
            if c.approver == "manager":
                c.approver = "human"
                c.note = "관리자 세션에 알리지 못해 사람이 승인합니다."
        await self.sync()
        if self.on_change:
            self.on_change()

    def _spawn(self, coro: Any) -> None:
        t = asyncio.get_running_loop().create_task(coro)
        self.h._tasks.add(t)
        t.add_done_callback(self.h._tasks.discard)

    async def check(self) -> int:
        """한 번 훑는다 — 카드 수를 돌려준다. 세션마다 실패는 그 카드에 사유로 남기고 다음 세션으로 간다.
        11-11부터 카드는 턴 끝(on_turn_closed)에서 바로 만든다. 훑기는 놓친 것을 줍는 그물이다(브리지를 다시 띄운 사이 끝난 세션,
        턴 끝 확인이 실패한 세션, 끝난 세션 · 다시 일하는 세션의 카드 치우기)."""
        async with self._lock:
            self._touched = False
            rows = await self._candidates()
            live = await asyncio.to_thread(live_sessions, self.sessions_dir)
            keep: set[int] = set()
            changed = False
            for r in rows:
                sid = r[0]
                try:
                    card = await self.prep(r, live)
                except Exception as e:  # noqa: BLE001
                    card = self._failed_card(r, f"합치기 준비 실패: {type(e).__name__}: {str(e)[:200]}")
                if card is None:
                    continue
                keep.add(sid)
                if self.cards.get(sid) is not card:
                    self.cards[sid] = card
                    changed = True
            changed = changed or self._touched
            for sid in [s for s, c in self.cards.items() if s not in keep and c.status == "ready"]:
                del self.cards[sid]                       # 더는 일을 마친 상태가 아니다(다시 일함 · 합침 · 버림)
                changed = True
            # 끝난 카드(merged 등)는 keep_h(6시간) 뒤 치운다 — 합친 카드에 정리 후보가 남았으면 keep_docs_h(11-13)
            cut = _iso(_now() - timedelta(hours=self.cfg.keep_h))
            cut_docs = _iso(_now() - timedelta(hours=self.cfg.keep_docs_h))
            for sid in [s for s, c in self.cards.items() if s not in keep and c.status != "ready" and self._expired(c, cut, cut_docs)]:
                del self.cards[sid]
                changed = True
            # 11-14 합친 카드가 남아 있는 동안 push됐는지 본다(관리자가 나중에 push한다). 한 번 True면 다시 보지 않는다
            for c in self.cards.values():
                if c.status == "merged" and c.merge_result and c.pushed is not True:
                    try:
                        p = await pushed_to_origin(c.repo, c.base, c.merge_result.get("commit"))
                    except Exception:  # noqa: BLE001 — 표시용이다. 실패해도 훑기를 멈추지 않는다
                        p = None
                    if p != c.pushed:
                        c.pushed, changed = p, True
            self.health = {"ok": True, "last": _iso(_now()), "error": None, "turn_end": self.turn_end}
            self._apply_store_health()
        await self.sync()
        if changed and self.on_change:
            self.on_change()
        return len(self.cards)

    async def check_one(self, sid: int, via: str = "turn_end") -> Card | None:
        """한 세션만 본다(턴 끝). worktree 세션이 아니거나 그 폴더의 마지막 세션이 아니면 아무것도 하지 않는다."""
        async with self._lock:
            self._touched = False
            rows = [r for r in await self._candidates() if r[0] == sid]
            if not rows:
                return None
            live = await asyncio.to_thread(live_sessions, self.sessions_dir)
            try:
                card = await self.prep(rows[0], live, via=via)
            except Exception as e:  # noqa: BLE001
                card = self._failed_card(rows[0], f"합치기 준비 실패: {type(e).__name__}: {str(e)[:200]}")
            changed = self._touched
            old = self.cards.get(sid)
            if card is None:
                if old is not None and old.status == "ready":
                    del self.cards[sid]                   # 다시 일함 · 커밋 안 한 변경 — 훑기와 같다
                    changed = True
            elif old is not card:
                self.cards[sid] = card
                changed = True
        await self.sync()
        if changed and self.on_change:
            self.on_change()
        return card

    def on_turn_closed(self, session_id: int, *_: Any, **__: Any) -> None:
        """조립기가 턴을 닫은 직후(트랜잭션 안일 수 있다 — 여기서는 예약만). 11-11(사용자): 세션이 응답을 마치는 순간 관리자 몫
        (합치기 준비)으로 바로 넘긴다 — 1분 훑기에 기대지 않는다. Stop hook이 마지막 응답 줄 · CC 상태 파일보다 먼저 올 수 있어
        TURN_END_DELAYS 뒤 두 번 본다(두 번째는 묻는 말 표시를 바로잡는다). 실패는 health에 남기고 다음 훑기가 줍는다 —
        훑기마저 실패하면 _health_bad가 텔레그램으로 알린다."""
        if not self.cfg.enabled:
            return

        async def go() -> None:
            for d in TURN_END_DELAYS:
                await asyncio.sleep(d)
                try:
                    async with asyncio.timeout(60):
                        await self.check_one(session_id)
                    self.turn_end["ok"] += 1
                except Exception as e:  # noqa: BLE001 — 실패가 적재를 막지 않는다. 그물(훑기)이 줍는다
                    self.turn_end["fail"] += 1
                    self.turn_end["error"] = f"세션 {session_id}: {type(e).__name__}: {str(e)[:160]}"
                    self.turn_end["at"] = _iso(_now())
                    log.warning("턴 끝 합치기 준비 실패 — 다음 훑기가 줍는다: %s", self.turn_end["error"])
                    return
        t = asyncio.get_running_loop().create_task(go())
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def _failed_card(self, r: tuple[Any, ...], err: str) -> Card:
        sid, cc, cwd, title, project, role = r
        repo, name = wt.split(cwd)
        old = self.cards.get(sid)
        if old and old.error == err:
            return old
        now = _iso(_now())
        c = Card(sid=sid, title=title, project=project, role=role, repo=repo, name=name, branch=wt.BRANCH_PREFIX + name, base="",
                 head=(old.head if old else ""), base_head="", live=False, why="", ahead=0, behind=0, commits=[], files=[],
                 conflict=None, docs=None, status="failed", error=err, made_at=now, updated_at=now)
        log.warning("합치기 준비 실패 세션 %s: %s", sid, err)
        self._notify(c, f"mergeprep:fail:{sid}:{now[:13]}", f"⚠ {err} — 「{title or sid}」(세션 {sid}). 패널 「합치기 승인」에 사유가 있습니다")
        return c

    def worktree_gone(self, sid: int) -> bool:
        """worktree가 합쳐지거나 버려졌다(HandoffManager.worktree_act가 부른다) — 그 세션의 대기 카드를 바로 치운다.
        11-11: 승인은 approve가 카드 상태를 바꿔 막대에서 바로 빠졌지만, 버리기 · 카드 밖 합치기는 카드를 몰라 ready로 남았다가
        1분 훑기에서야 사라졌다(그 사이 막대를 누르면 없는 세션으로 갔다). 합치는 중(merging) 카드는 approve가 마저 쓰니 둔다.
        잠금을 잡지 않는다(approve가 잠근 채 worktree_act를 부른다) — 딕셔너리 한 줄이라 이벤트 루프 안에서 안전하다."""
        c = self.cards.get(sid)
        if c is None or c.status == "merging":
            return False
        del self.cards[sid]
        self._sync_soon()
        return True

    # ── 승인 ──
    def _manager_may(self, c: Card, what: str) -> None:
        """관리자가 승인 · 미루기를 해도 되는가(11-12). 안 되면 Refused — 까닭을 적는다."""
        if self.cfg.approver_of(c.project) != "manager":
            raise Refused(f"이 프로젝트({c.project or '모름'})의 합치기 승인자는 사람입니다. 관리자는 {what}할 수 없습니다"
                          "(config/handoff.toml [merge_prep.per_project] approver)")
        if c.human_why:
            raise Refused(f"이 카드는 사람 승인입니다. 관리자는 {what}할 수 없습니다. 까닭: " + "; ".join(c.human_why))

    async def skip(self, sid: int, by: str = "human") -> dict[str, Any]:
        """[나중에] — 이 브랜치 끝 커밋이 바뀌기 전까지 카드를 다시 띄우지 않는다."""
        c = self.cards.get(sid)
        if not c or c.status not in ("ready", "failed", "conflict_sent", "conflict_manager"):
            raise Refused("치울 합치기 카드가 없습니다")
        if by == "manager":
            self._manager_may(c, "미루기")
        await self.h._act(sid, ACT_SKIP, None, True, c.head)
        del self.cards[sid]
        await self.sync()
        if self.on_change:
            self.on_change()
        return {"ok": True, "note": "카드를 치웠습니다. 이 세션이 새로 커밋하면 다시 만듭니다."}

    async def docs_done(self, sid: int, by: str = "human") -> dict[str, Any]:
        """정리 후보를 다 골랐다(11-13 사용자) — 합친 카드를 바로 치운다(DB merge_card에서도). 안 부르면 지금처럼 keep_docs_h 뒤 치운다.
        합친 카드만 — 대기 · 충돌 카드는 skip(나중에)으로 치운다."""
        c = self.cards.get(sid)
        if not c:
            raise Refused("치울 합치기 카드가 없습니다. 이미 치웠거나 시간이 지나 사라졌습니다")
        if c.status != "merged":
            raise Refused(f"합친 카드가 아닙니다(지금 {c.status}). 정리 후보는 합친 뒤에 고릅니다. 대기 카드를 치우려면 skip")
        dn = len((c.docs or {}).get("docs") or [])
        await self.h._act(sid, ACT_DOCS, None, True, f"{c.name} {c.head[:8]} 정리 후보 {dn}개 · {by}")
        del self.cards[sid]
        await self.sync()
        if self.on_change:
            self.on_change()
        return {"ok": True, "note": f"정리 후보를 다 골랐다고 보고 합친 카드를 치웠습니다(정리 후보 {dn}개)."}

    async def approve(self, sid: int, by: str = "human", title: str | None = None) -> dict[str, Any]:
        """[합치기] — 사람(패널) 또는 관리자(by=manager, 11-12 — 그 프로젝트 승인자가 관리자이고 늘-사람에 안 걸린 카드만).
        다시 재고 → 충돌이면 그 세션(끝났으면 관리자)에 풀라고 보냄 · 깨끗하면 (끝내고) 합침. 결과(거부 포함)는 DB에도 남긴다.
        title(11-13) — squash 커밋 제목을 정해 넘길 때(그 저장소 꼴이 아니면 아무것도 하기 전에 거부). 안 넘기면 세션 제목으로 기계가 만든다."""
        try:
            return await self._approve(sid, by, title)
        finally:
            await self.sync()

    async def _approve(self, sid: int, by: str, title: str | None = None) -> dict[str, Any]:
        c = self.cards.get(sid)
        if not c or c.status not in ("ready", "conflict_sent", "conflict_manager", "failed"):
            raise Refused("승인할 합치기 카드가 없습니다. 카드가 사라졌거나 이미 합치는 중입니다")
        if not c.head:
            raise Refused("준비가 실패한 카드입니다. 사유를 보고 다음 훑기를 기다리거나 패널 [합치기]로 합칩니다")
        if by == "manager":
            self._manager_may(c, "승인")
        c.approved_by = by
        async with self._lock:
            row = await self.h.session(sid)
            if row is None:
                raise Refused("세션이 없습니다")
            st = await self._git_facts(c.repo, c.name)
            if not st.get("exists"):
                del self.cards[sid]
                raise Refused("작업방이 없습니다. 이미 합쳤거나 버렸습니다")
            if st["dirty"]:
                raise Refused(f"커밋 안 된 변경이 {len(st['dirty'])}개 생겼습니다. 그 세션이 커밋한 뒤 카드가 다시 뜹니다. 아무것도 하지 않았습니다")
            if st["head"] != c.head:
                del self.cards[sid]
                raise Refused("카드를 만든 뒤 브랜치에 커밋이 더 생겼습니다. 다음 훑기에서 새 카드를 만듭니다. 아무것도 하지 않았습니다")
            if title is not None:            # 끝내기 · 충돌 넘기기 전에 — 꼴이 틀린 제목으로 세션만 끝나는 일이 없게
                title = await wt.check_title_for(c.repo, st["base"], title)
            live = bool(row.cc and row.cc in live_sessions(self.sessions_dir))
            conflict = await self._conflict(c.repo, st["base"], st["branch"])
            if not conflict and live and st["behind"]:
                conflict = await self._rebase_check(c.repo, st["base"], st["branch"])
            c.behind, c.base_head, c.live, c.conflict, c.updated_at = st["behind"], st["base_head"], live, conflict, _iso(_now())
            if conflict:
                return await self._send_conflict(c, row, live)
            c.status, c.error = "merging", None
            await self.sync()            # 합치는 중에 브리지가 내려가면 되살릴 때 「결과 모름」으로 보이게
            if self.on_change:
                self.on_change()
            try:
                res = await self.h.worktree_act(row, "merge", end=live, title=title)
            except Refused as e:
                c.status, c.error = "failed", str(e)
                await self.h._act(sid, ACT_MERGE, None, False, f"{c.name} 거부: {e}"[:500])
                self._notify(c, f"mergeprep:mfail:{sid}:{c.head[:12]}", f"⚠ 합치기 승인 뒤 멈춤 — 「{c.title or sid}」 {e}")
                if self.on_change:
                    self.on_change()
                raise
            c.updated_at = _iso(_now())
            if res.get("ok"):
                c.status, c.note = "merged", res.get("note")
                c.merge_result = merge_result_of(res, c.base)
                c.pushed = await pushed_to_origin(c.repo, c.base, (c.merge_result or {}).get("commit"))
                await self.h._act(sid, ACT_MERGE, None, True, f"{c.name} {c.head[:8]} 커밋 {res.get('merged')}개"
                                  + (f" squash {res['squash'][:8]}" if res.get("squash") else "")
                                  + (" · 관리자 승인" if by == "manager" else " · 사람 승인"))
                c.manager_told = await self._tell_manager(c, self._merged_msg(c, res))
                await self.after_merge(c, res)
            else:
                c.status, c.error = "failed", (res.get("note") or "합치지 못했습니다") + (
                    f" 충돌 파일: {', '.join(res['conflict'])}" if res.get("conflict") else "")
                await self.h._act(sid, ACT_MERGE, None, False, f"{c.name} {c.error}"[:500])
                self._notify(c, f"mergeprep:mfail:{sid}:{c.head[:12]}", f"⚠ 합치기 실패 — 「{c.title or sid}」 {c.error}")
                if res.get("ended") is not None or not live:
                    c.manager_told = await self._tell_manager(c, (
                        f"[FOREMAN 합치기] 세션 {sid} 「{c.title or ''}」의 {c.branch}를 합치지 못했다 — {c.error}. 그 세션은 끝났다. "
                        f"관리자가 원본 폴더에서 풀어 합친다(docs/11_worktree.md 「6.」). 시험 · push도 관리자 몫이다."))
            if self.on_change:
                self.on_change()
            return {"ok": c.status == "merged", "status": c.status, "note": c.note or c.error, "card": c.view(),
                    "manager_told": c.manager_told, "result": res}

    async def _rebase_check(self, repo: str, base: str, branch: str) -> list[str] | None:
        """살아 있는 세션을 끝내기 전에 — main 위로 rebase가 되는지 임시 worktree(분리된 HEAD)에서 본다. merge-tree는 세 갈래
        합치기라 깨끗해도 커밋 하나씩 얹는 rebase는 중간 커밋에서 충돌할 수 있다. 끝낸 뒤 알면 풀 세션이 없다."""
        tmp = tempfile.mkdtemp(prefix="foreman-mprep-")
        path = os.path.join(tmp, "wt")
        try:
            await wt.git(repo, "worktree", "add", "--detach", path, branch)
            rc, out = await wt.git(path, "rebase", base, check=False)
            if rc == 0:
                return None
            _, files = await wt.git(path, "diff", "--name-only", "--diff-filter=U", check=False)
            await wt.git(path, "rebase", "--abort", check=False)
            return sorted(set(files.splitlines())) or ["(rebase 중 충돌, 파일 이름을 읽지 못함)"]
        finally:
            await wt.git(repo, "worktree", "remove", "--force", path, check=False)
            await wt.git(repo, "worktree", "prune", check=False)
            try:
                os.rmdir(tmp)
            except OSError:
                pass

    async def _send_conflict(self, c: Card, row: Any, live: bool) -> dict[str, Any]:
        files = ", ".join(c.conflict or [])
        who = "관리자가" if c.approved_by == "manager" else "사람이"
        if live:
            msg = (f"[FOREMAN 합치기] {who} 합치기를 승인했는데 {c.branch}가 {c.base}와 충돌한다(파일: {files}). "
                   f"`git rebase {c.base}`로 {c.base}를 가져와 충돌을 풀고 커밋한 뒤 보고해라. push · 브리지 다시 띄우기는 하지 마라. "
                   f"풀고 나면 브리지가 합치기 카드를 다시 만든다.")
            ok = await self._deliver(row.cc, row.cwd, msg)
            c.status = "conflict_sent"
            c.note = ("세션을 끝내지 않고 그 세션에 「main을 가져와 풀라」를 보냈습니다." if ok
                      else "그 세션에 보내지 못했습니다. 입력 칸을 확인해 주세요.")
            if not ok:
                c.error = c.note
                self._notify(c, f"mergeprep:cfail:{c.sid}:{c.head[:12]}", f"⚠ 충돌 풀기를 보내지 못함 — 「{c.title or c.sid}」(세션 {c.sid})")
        else:
            c.status = "conflict_manager"
            c.manager_told = await self._tell_manager(c, (
                f"[FOREMAN 합치기] {who} 세션 {c.sid} 「{c.title or ''}」의 {c.branch} 합치기를 승인했는데 {c.base}와 충돌한다(파일: {files}). "
                f"그 세션은 끝났다 — 관리자가 원본 폴더에서 풀어 합친다(docs/11_worktree.md 「6.」). 시험 · push도 관리자 몫이다."))
            c.note = "세션이 끝나 관리자에게 충돌 풀기를 넘겼습니다." if c.manager_told else "세션이 끝났고 관리자 세션도 없어 넘기지 못했습니다. 텔레그램으로 알렸습니다."
        await self.h._act(c.sid, ACT_CONFLICT, None, c.status == "conflict_sent" and not c.error or bool(c.manager_told),
                          f"{c.name} {c.head[:8]} {files}"[:500])
        if self.on_change:
            self.on_change()
        return {"ok": False, "status": c.status, "note": c.note, "card": c.view(), "manager_told": c.manager_told}

    def _merged_msg(self, c: Card, res: dict[str, Any]) -> str:
        how = "fast-forward" if c.ff else f"{c.base} 위로 rebase 뒤 fast-forward"
        if res.get("squash"):
            how = (f"커밋 {res.get('merged', c.ahead)}개를 커밋 하나({res['squash'][:8]}"
                   + (f" 「{res['title']}」" if res.get("title") else "") + ")로 묶어 squash — 본문에 원래 날짜 · 해시 · 제목"
                   + (f", 원래 커밋은 `git log {res['orig_ref']}`" if res.get("orig_ref") else "") + ", " + how)
        who = "관리자가" if c.approved_by == "manager" else "사람이"
        mgr_picks = self.cfg.approver_of(c.project) == "manager" and not c.human_why
        ended = " 세션은 끝냈다." if res.get("ended") is not None else ""
        docs = (c.docs or {})
        dn = len(docs.get("docs") or [])      # README 「나중에 할 일」 후보는 11-15에 뺐다(doc_candidates)
        stale = [x["where"] for x in docs.get("docs") or [] if x.get("stale")][:5]
        extra = ""
        if stale:
            extra += f" 이번에 바뀐 파일을 적었는데 고치지 않은 문서: {', '.join(stale)} — 설계가 바뀌었으면 맞출 후보."
        # 11-13 다 골랐으면 카드를 바로 치운다(안 부르면 keep_docs_h 뒤 치운다 — 다 고르고도 카드가 남지 않게)
        done = (f" 다 골랐으면 POST /api/sessions/{c.sid}/merge-prep {{\"action\":\"docs_done\",\"by\":\"manager\"}}로 카드를 치운다"
                f"(안 부르면 {self.cfg.keep_docs_h}시간 뒤 치운다).")
        if not dn:
            pick = ""
        elif mgr_picks:     # 11-12 — 승인자가 관리자인 프로젝트는 정리 후보 고르기 · 지우기도 관리자
            pick = (f" docs 정리 후보 {dn}개는 카드에 있다(GET /api/merge-prep?project={c.project} 의 card.docs, "
                    f"{self.cfg.keep_docs_h}시간 남는다 — 브리지를 다시 띄워도 DB에서 되살린다) — "
                    "관리자가 골라 지운다. 판단이 안 서는 줄만 사람에게 묻는다." + done)
        else:
            pick = (f" docs 정리 후보 {dn}개는 그 세션 패널 카드에 있다 — 고르고 지우는 것은 사람 승인 뒤"
                    "(판단이 필요하면 사람에게 묻고, 혼자 지우지 않는다)." + done)
        return (f"[FOREMAN 합치기] {who} 승인해 세션 {c.sid} 「{c.title or ''}」의 {c.branch}(커밋 {res.get('merged', c.ahead)}개)를 "
                f"{c.base}에 합쳤다({how}).{ended} 1단계라 브리지는 합치기까지만 했다 — 시험 · push · 브리지 다시 띄우기 · 화면 점검은 "
                f"관리자가 한다." + pick + extra)

    async def after_merge(self, c: Card, res: dict[str, Any]) -> None:
        """2단계 자리 — 승인 뒤 시험 → push → 승인 대기 0 확인 → 브리지 다시 띄우기 → 화면 점검. 사용자가 1단계를 써 본 뒤 정한다.
        stage = 2로 켜도 지금은 아무것도 하지 않고 그렇다고 남긴다(조용히 넘어가지 않게)."""
        if self.cfg.stage >= 2:
            c.note = (c.note or "") + " (2단계는 아직 만들지 않았습니다. 시험 · push는 관리자가 합니다.)"
            log.warning("merge_prep stage=2지만 2단계는 아직 없다 — 합치기까지만 했다(세션 %s)", c.sid)

    # ── 알리기 ──
    async def _deliver(self, cc: str | None, cwd: str | None, msg: str) -> bool:
        if not cc:
            return False
        from bridge.handoff import transcript_path
        try:
            r = await deliver(cc, msg, sessions_dir=self.sessions_dir, transcript=transcript_path(cwd or "", cc), verify_s=15.0)
        except Refused as e:
            log.warning("합치기 결과를 보내지 못함 %s: %s", cc[:8], e)
            return False
        return bool(r.get("delivered") or r.get("queued"))

    async def manager_of(self, repo: str) -> tuple[str, str] | None:
        """원본 폴더에 살아 있는 역할 관리자 (cc, cwd). 여럿이면 마지막 행."""
        ccs = self.h._live_in_base(repo)
        if not ccs:
            return None
        from sqlalchemy import bindparam
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT cc_session_id, role, cwd FROM character_session WHERE cc_session_id IN :c ORDER BY id")
                .bindparams(bindparam("c", expanding=True)), {"c": ccs})).all()
        latest = {cc: (role, cwd) for cc, role, cwd in rows}
        mgr = [(cc, cwd) for cc, (role, cwd) in latest.items() if role == "manager"]
        return mgr[-1] if mgr else None

    async def _tell_manager(self, c: Card, msg: str) -> bool:
        m = await self.manager_of(c.repo)
        ok = bool(m) and await self._deliver(m[0], m[1], msg)
        if not ok:
            self._notify(c, f"mergeprep:mgr:{c.sid}:{c.head[:12]}:{c.status[:8]}",
                         ("관리자 세션이 없어" if not m else "관리자 세션에 보내지 못해") + f" 텔레그램으로 남깁니다 — {msg}")
        return ok

    def _notify(self, c: Card | None, key: str, msg: str, check_db: bool = True, later: bool | None = None) -> None:
        """텔레그램 한 번(key가 이미 있으면 보내지 않는다 — 브리지를 다시 띄워도). c가 없으면 FOREMAN 전체 알림.
        check_db=False면 보낸 적을 DB에서 보지 않는다(DB 문제 알림 — 부른 쪽이 한 번만 부른다).
        later=False면 묶음을 켠 프로젝트여도 바로 보낸다(None이면 notifier가 정한다)."""
        if self.notifier is None:
            return
        project, sid = (c.project, c.sid) if c else ("foreman", None)

        async def go() -> None:
            try:
                if check_db:
                    async with self.engine.connect() as cn:
                        if (await cn.execute(text("SELECT 1 FROM notification WHERE rule = :r LIMIT 1"), {"r": key[:64]})).first():
                            return
                rule = self.notifier.rules.for_project(project) if project else None
                prefix = (rule and rule.prefix) or "[" + (project or "FOREMAN") + "]"
                self.notifier.send_direct(project, NOTIFY_KIND, sid, f"{prefix} {msg}"[:3500], rule=key[:64],
                                          **({"later": later} if later is not None else {}))
            except Exception as e:  # noqa: BLE001 — 알림 실패가 합치기를 막지 않는다
                log.warning("합치기 알림 실패: %s", type(e).__name__)
        t = asyncio.get_running_loop().create_task(go())
        self.h._tasks.add(t)
        t.add_done_callback(self.h._tasks.discard)

    # ── 돌기 ──
    async def run(self) -> None:
        stuck_s = self.cfg.stuck_min * 60
        try:
            await self.restore()               # 실패는 restore가 알린다(텔레그램 + 사유)
        except Exception as e:  # noqa: BLE001 — 되살리기가 감시를 막지 않는다
            self._restored = True
            self._store_bad(f"합치기 카드 되살리기 실패: {type(e).__name__}: {str(e)[:160]}", "load")
        while True:
            await asyncio.sleep(self.cfg.every_s)
            try:
                await asyncio.wait_for(self.check(), stuck_s)
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                why = f"합치기 준비가 {self.cfg.stuck_min}분째 끝나지 않아 끊었습니다(git · DB가 막혔을 수 있습니다)"
                self._health_bad(why, f"mergeprep:stuck:{_now():%Y%m%d%H}")
            except Exception as e:  # noqa: BLE001 — 한 번의 실패가 감시를 멈추지 않는다
                self._health_bad(f"합치기 준비 실패: {type(e).__name__}: {str(e)[:200]}", f"mergeprep:err:{_now():%Y%m%d%H}")

    def _health_bad(self, why: str, key: str) -> None:
        log.warning(why)
        self.health = {"ok": False, "last": self.health.get("last"), "error": why, "at": _iso(_now()), "turn_end": self.turn_end,
                       **({"store": self.health["store"]} if "store" in self.health else {})}
        self._notify(None, key, f"⚠ {why}")
        if self.on_change:
            self.on_change()

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.create_task(self.run(), name="foreman-merge-prep")
        return self._task
