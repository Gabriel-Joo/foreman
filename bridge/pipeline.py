"""CI/CD 인과 체인(로드맵 8단계) — 커밋 SHA를 축으로 캐릭터의 작업과 파이프라인 단계를 한 줄로 꿴다.

    캐릭터가 파일을 고쳤다 → 이 커밋(git_commit, 세션 · 도구 호출 이벤트) → 이 빌드(Jenkins) → 이 태그(Harbor)
    → 이 리비전 동기화(ArgoCD) → 실패했다, 여기서

연결 규칙
  - 커밋: 프로젝트 저장소(같은 서버)를 폴링한다. 커밋 시각 직전에 그 프로젝트 세션이 `git commit`을 부른 도구 호출이 있으면
    그 세션의 커밋 — event.commit_sha를 채운다. push는 origin/<브랜치>에 들어간 것으로 본다
  - Jenkins: 웹훅의 GIT_COMMIT이 머리 커밋. 직전 빌드의 머리..이번 머리 사이 커밋들이 이 빌드에 묶인다(build_commit)
    — 2분 폴링 사이에 push된 여러 커밋이 빌드 하나가 된다
  - Harbor: 태그 = 커밋 12자리(두 저장소 Jenkinsfile 규칙) → 로컬 저장소에서 전체 SHA로 푼다
  - ArgoCD: 동기화한 앱의 이미지 태그(같은 12자리)로 빌드를 찾는다. 리비전은 ronanlab-infra 커밋(태그를 바꾼 커밋)

인프라 캐릭터(README 2.2) — 첫 웹훅을 받으면 프로젝트마다 Jenkins · Harbor · ArgoCD 캐릭터가 등장하고, 생존은 폴링한다
  (응답 없음 N번 → STALE, 오래 STALE → 퇴장, 응답 · 웹훅이 오면 돌아온다).
실패는 텔레그램으로(실패로 바뀔 때 한 번).
"""

import asyncio
import json
import logging
import re
import time
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge.mask import Masker
from bridge.models import EventIn, EventSource, EventStatus, EventType

log = logging.getLogger("foreman.pipeline")

STAGES = ("jenkins", "harbor", "argocd")
STAGE_LABEL = {"commit": "커밋", "push": "push", "jenkins": "Jenkins 빌드", "harbor": "Harbor 이미지", "argocd": "ArgoCD 배포"}
TAG_RE = re.compile(r"^[0-9a-f]{12}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RANK = {"running": 0, "waiting": 0, "success": 1, "failed": 1}   # 끝난 상태를 running · waiting으로 되돌리지 않는다


@dataclass
class InfraDef:
    kind: str
    name: str
    host: str
    health: str


@dataclass
class PipeProject:
    name: str
    branch: str = "main"
    jenkins_job: str | None = None
    harbor_project: str | None = None
    argocd_app: str | None = None
    project_id: int = 0
    repo: str = ""


@dataclass
class PipeRules:
    git_poll_s: float = 20
    attribute_window_s: float = 300
    infra_poll_s: float = 60
    stale_after: int = 3
    retire_after_h: float = 24
    ingress: str = "http://192.168.122.240"
    # 빠진 알림 찾기(11-03) — push 뒤 시작 알림이 없으면 warn_s에 화면 노란색, alert_s에 텔레그램. 시작했는데 끝 알림이 없으면 end_s
    watch_warn_s: float = 180
    watch_alert_s: float = 1020
    watch_end_s: float = 2100
    hook_break_after: int = 2
    infra: dict[str, InfraDef] = field(default_factory=dict)
    projects: dict[str, PipeProject] = field(default_factory=dict)

    def by(self, attr: str, value: str | None) -> PipeProject | None:
        return next((p for p in self.projects.values() if value and getattr(p, attr) == value), None)


def load_pipeline(path: str | Path) -> PipeRules:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    g, i, w = raw.get("git", {}), raw.get("infra", {}), raw.get("watch", {})
    r = PipeRules(git_poll_s=g.get("poll_s", 20), attribute_window_s=g.get("attribute_window_s", 300),
                  infra_poll_s=i.get("poll_s", 60), stale_after=i.get("stale_after", 3),
                  retire_after_h=i.get("retire_after_h", 24), ingress=i.get("ingress", "http://192.168.122.240"),
                  watch_warn_s=w.get("started_warn_s", 180), watch_alert_s=w.get("started_alert_s", 1020),
                  watch_end_s=w.get("completed_alert_s", 2100), hook_break_after=w.get("webhook_break_after", 2))
    for k in STAGES:
        d = i.get(k)
        if isinstance(d, dict):
            r.infra[k] = InfraDef(k, d.get("name", k), d["host"], d.get("health", "/"))
    for name, d in raw.get("projects", {}).items():
        r.projects[name] = PipeProject(name, d.get("branch", "main"), d.get("jenkins_job"), d.get("harbor_project"),
                                       d.get("argocd_app"))
    return r


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ts(v: Any) -> datetime:
    """웹훅 시각 — epoch(초 · 밀리초) · ISO 문자열 → UTC naive. 없으면 지금."""
    try:
        if isinstance(v, (int, float)):
            v = v / 1000 if v > 1e11 else v
            return datetime.fromtimestamp(v, UTC).replace(tzinfo=None)
        if isinstance(v, str) and v:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        pass
    return _now()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


# ── 웹훅 → 단계 판정(순수 함수, 시험 대상) ─────────────────────────
def jenkins_status(body: dict[str, Any]) -> tuple[str, str | None]:
    """Jenkinsfile이 보내는 모양: {job, number, phase: started|completed, result, commit, stage, url}."""
    phase = str(body.get("phase") or "").lower()
    result = str(body.get("result") or "").upper()
    if phase in ("started", "start", "running") or (not result and phase != "completed"):
        return "running", None
    if result == "SUCCESS":
        return "success", None
    return "failed", (body.get("stage") or None)


def build_cause(body: dict[str, Any]) -> str | None:
    """Jenkinsfile foremanNotify가 보내는 빌드 원인: webhook(GitHubPushCause) · poll(SCMTrigger) · manual · other."""
    c = str(body.get("cause") or "").lower()
    return c if c in ("webhook", "poll", "manual", "other") else None


def watch_state(elapsed_s: float, warn_s: float, alert_s: float) -> str:
    """push 뒤(앞 빌드가 끝난 뒤) 시작 알림 없이 지난 시간 → ok · late(화면 노란색) · missing(텔레그램)."""
    if elapsed_s >= alert_s:
        return "missing"
    if elapsed_s >= warn_s:
        return "late"
    return "ok"


def webhook_broken(causes: list[str | None], n: int = 2) -> bool:
    """최근 빌드 원인(새것부터). 웹훅으로 시작한 빌드가 있던 job에서 폴링 원인이 연달아 n번 — 웹훅이 끊긴 것으로 본다.
    손으로 누른 빌드(manual)는 건너뛴다(웹훅과 무관)."""
    seq = [c for c in causes if c in ("webhook", "poll")]
    return len(seq) > n and all(c == "poll" for c in seq[:n]) and "webhook" in seq[n:]


def harbor_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Harbor 기본 웹훅 형식(PUSH_ARTIFACT · SCANNING_FAILED · QUOTA_EXCEED …) → [{project, repo, digest, tag, status, step}]."""
    typ = str(body.get("type") or "")
    ed = body.get("event_data") or {}
    repo = ed.get("repository") or {}
    ns, full = repo.get("namespace"), repo.get("repo_full_name") or repo.get("name")
    out = []
    for res in ed.get("resources") or [{}]:
        tag, digest = res.get("tag"), res.get("digest")
        if typ == "PUSH_ARTIFACT":
            st, step = "success", None
        elif typ in ("SCANNING_FAILED", "QUOTA_EXCEED", "REPLICATION"):
            st, step = ("failed", typ.lower()) if typ != "REPLICATION" else ("success", None)
        else:
            continue   # PULL · DELETE · SCANNING_COMPLETED 등은 체인의 단계가 아니다
        out.append({"project": ns, "repo": full, "digest": digest, "tag": tag, "status": st, "step": step, "type": typ})
    return out


def argocd_status(body: dict[str, Any]) -> tuple[str, str | None]:
    """notifications 템플릿 본문: {app, sync, health, revision, images, automated, phase, message, at, op_revision}.

    phase · message는 **마지막 동기화 작업**의 것이라 지금 리비전의 것이 아닐 수 있다(op_revision ≠ revision) —
    새 리비전이 OutOfSync인데 지난 작업이 Failed였다고 실패로 보면 안 된다.
    waiting = 수동 Sync 앱(automated false)이 새 리비전으로 OutOfSync — 사람이 Sync하기를 기다린다. 실패가 아니다(11-03)."""
    phase = str(body.get("phase") or "")
    health = str(body.get("health") or "")
    sync = str(body.get("sync") or "")
    rev, op_rev = body.get("revision"), body.get("op_revision")
    current_op = not rev or not op_rev or rev == op_rev
    if current_op and phase in ("Failed", "Error"):
        return "failed", "sync"
    if health == "Degraded":
        return "failed", "health"
    if sync == "OutOfSync" and not (current_op and phase == "Running"):
        return ("waiting", None) if body.get("automated") is False else ("running", None)
    if phase == "Running" or health in ("Progressing", "Missing"):
        return "running", None
    if health == "Healthy" and sync in ("Synced", ""):
        return "success", None
    return "running", None


_DIR_HOP = re.compile(r"(?:^|[;&|(]\s*)(?:cd|pushd)\s+(['\"]?)([^\s;&|'\"]+)\1|\bgit\s+-C\s+(['\"]?)([^\s;&|'\"]+)\3")


def other_repo(cmd: str, repo: str, cwd: str | None) -> bool:
    """명령이 다른 디렉토리(이 저장소 밖)로 들어가 커밋하나 — `cd X && git commit`, `git -C X commit`."""
    import os.path
    home = os.path.expanduser("~")
    root = os.path.realpath(repo)
    for m in _DIR_HOP.finditer(cmd):
        d = m.group(2) or m.group(4) or ""
        d = d.replace("$HOME", home)
        d = os.path.expanduser(d)
        if not os.path.isabs(d):
            d = os.path.join(cwd or root, d)
        d = os.path.realpath(d)
        if d != root and not d.startswith(root + os.sep):
            return True
    return False


_HAS_MSG = re.compile(r"\bcommit\b[^|;&\n]*?(?:\s-[a-zA-Z]*[mF]\b|\s--message\b|\s--file\b|\s-[a-zA-Z]*[mF]\S)")


def _plain(s: str) -> str:
    return re.sub(r"[\\'\"`]", "", s)


def commit_match(cmd: str, subject: str, repo: str, cwd: str | None) -> int:
    """이 git commit 명령이 이 커밋을 만들었을 가능성. 2 = 명령에 커밋 제목이 있다, 1 = 메시지를 알 수 없는 커밋 명령(가까우면),
    0 = 아니다(다른 제목을 줬다 · 다른 저장소로 들어가 커밋했다). 실측(11-02): 5분 안에 커밋이 여럿이면 가장 가까운 명령이
    다른 커밋의 것이었고, 런슈즈 세션이 인프라 저장소에 한 커밋이 런슈즈 커밋으로 잡혔다."""
    key = _plain(subject or "")[:24].strip()
    if key and key in _plain(cmd):
        return 2
    if other_repo(cmd, repo, cwd) or _HAS_MSG.search(cmd):
        return 0
    return 1


def image_tag(images: Any, harbor_project: str | None) -> str | None:
    """이미지 목록에서 그 프로젝트 이미지의 커밋 태그(12자리)."""
    for img in images or []:
        if not isinstance(img, str) or ":" not in img:
            continue
        name, tag = img.rsplit(":", 1)
        if TAG_RE.match(tag) and (not harbor_project or f"/{harbor_project}/" in name):
            return tag
    return None


# ── 관리자 ────────────────────────────────────────────────────
class PipelineManager:
    def __init__(self, engine: AsyncEngine, rules: PipeRules, pipeline: Any, masker: Masker,
                 notifier: Any = None, on_change: Any = None) -> None:
        self.engine, self.rules, self.pipeline, self.mask = engine, rules, pipeline, masker
        self.notifier = notifier
        self.on_change = on_change or (lambda: None)
        self._tasks: list[asyncio.Task[None]] = []
        self._fails: dict[int, int] = {}
        self._lock = asyncio.Lock()
        # 빠진 알림 찾기 — 메모리 상태(브리지를 다시 띄우면 지금 origin 머리부터 다시 잰다)
        self._origin: dict[str, str] = {}                 # 프로젝트 → 마지막으로 본 origin/<브랜치>
        self._pending: dict[str, dict[str, Any]] = {}     # 프로젝트 → {head, short, subject, at, state, alerted}
        self._end_alerted: set[int] = set()               # 끝 알림 없음을 알린 build id
        self._hook_broken: dict[str, bool] = {}

    # ── 수명 ──
    async def start(self, loops: bool = True) -> None:
        async with self.engine.connect() as c:
            for pid, name, repo in (await c.execute(text("SELECT id, name, repo_path FROM project"))).all():
                if name in self.rules.projects:
                    p = self.rules.projects[name]
                    p.project_id, p.repo = pid, repo
        for name in [n for n, p in self.rules.projects.items() if not p.project_id]:
            log.warning("pipeline.toml의 프로젝트 %s가 DB에 없다 — 건너뜀", name)
            del self.rules.projects[name]
        if loops:
            self._tasks = [asyncio.create_task(self._loop(self.scan_all, self.rules.git_poll_s), name="foreman-git"),
                           asyncio.create_task(self._loop(self.poll_infra, self.rules.infra_poll_s), name="foreman-infra"),
                           asyncio.create_task(self._loop(self.check_watch, 30), name="foreman-watch")]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass

    async def _loop(self, fn: Any, every: float) -> None:
        while True:
            try:
                await fn()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 한 번의 실패가 폴링을 멈추지 않는다
                log.warning("%s 실패: %s: %s", fn.__name__, type(e).__name__, str(e)[:200])
            await asyncio.sleep(every)

    # ── git ──
    async def git(self, repo: str, *args: str, timeout: float = 10.0) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", repo, *args, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            async with asyncio.timeout(timeout):
                out, err = await proc.communicate()
        except TimeoutError:
            proc.kill()
            raise RuntimeError(f"git {args[0]} 시간 초과") from None
        if proc.returncode != 0:
            raise RuntimeError(f"git {args[0]}: {err.decode(errors='replace').strip()[:200]}")
        return out.decode(errors="replace")

    async def resolve(self, p: PipeProject, short: str | None) -> str | None:
        """커밋 12자리(이미지 태그) → 전체 SHA. 모르는 커밋이면 None."""
        if not short:
            return None
        if SHA_RE.match(short):
            return short
        if not TAG_RE.match(short):
            return None
        async with self.engine.connect() as c:
            r = (await c.execute(text("SELECT sha FROM git_commit WHERE sha LIKE :s LIMIT 2"), {"s": short + "%"})).all()
        if len(r) == 1:
            return r[0][0]
        try:
            return (await self.git(p.repo, "rev-parse", "--verify", "--quiet", f"{short}^{{commit}}")).strip() or None
        except RuntimeError:
            return None

    async def scan_all(self) -> None:
        for p in self.rules.projects.values():
            try:
                await self.scan_git(p)
                await self.track_origin(p)
            except Exception as e:  # noqa: BLE001
                log.warning("git 폴링 실패 %s: %s: %s", p.name, type(e).__name__, str(e)[:200])

    # ── 빠진 알림 찾기(토큰 없는 보정) ──
    async def track_origin(self, p: PipeProject) -> None:
        """origin/<브랜치>가 움직였으면(이 서버에서 push · fetch) 빌드 시작 알림을 기다린다. 처음 본 머리는 기준만 잡는다."""
        if not p.jenkins_job:
            return
        head = (await self.git(p.repo, "rev-parse", "--verify", "--quiet", f"origin/{p.branch}")).strip()
        if not SHA_RE.match(head):
            return
        prev = self._origin.get(p.name)
        self._origin[p.name] = head
        if prev is None or prev == head:
            return
        subject = (await self.git(p.repo, "log", "-1", "--format=%s", head)).strip()
        old = self._pending.get(p.name)
        self._pending[p.name] = {"head": head, "short": head[:8], "subject": (self.mask.text(subject) or "")[:200],
                                 "at": _now(), "state": "ok", "alerted": bool(old and old.get("alerted"))}
        log.info("push 감지 %s %s — 빌드 시작 알림을 기다린다", p.name, head[:8])
        self._changed(p.name)

    async def _covered(self, p: PipeProject, head: str, since: datetime) -> bool:
        """push 머리 H를 담은 Jenkins 빌드 알림이 왔나 — 머리가 H이거나, 묶인 커밋에 H가 있거나, 머리가 H의 자손."""
        async with self.engine.connect() as c:
            rows = (await c.execute(text(
                "SELECT b.commit_sha, EXISTS(SELECT 1 FROM build_commit bc WHERE bc.build_id = b.id AND bc.commit_sha = :h) "
                "FROM build b WHERE b.project_id = :p AND b.stage = 'jenkins' AND b.started_at >= :t "
                "AND b.commit_sha IS NOT NULL ORDER BY b.id DESC LIMIT 10"),
                {"p": p.project_id, "h": head, "t": since - timedelta(minutes=2)})).all()
        for sha, linked in rows:
            if sha == head or linked:
                return True
            try:
                await self.git(p.repo, "merge-base", "--is-ancestor", head, sha)
                return True
            except RuntimeError:
                continue
        return False

    async def check_watch(self) -> None:
        now = _now()
        for p in self.rules.projects.values():
            if not p.jenkins_job:
                continue
            # 시작은 왔는데 끝 알림이 없는 빌드
            async with self.engine.connect() as c:
                rows = (await c.execute(text(
                    "SELECT id, external_id, started_at, log_url FROM build WHERE project_id = :p AND stage = 'jenkins' "
                    "AND status = 'running' AND started_at < :t"),
                    {"p": p.project_id, "t": now - timedelta(seconds=self.rules.watch_end_s)})).all()
                busy = (await c.execute(text(
                    "SELECT MAX(COALESCE(ended_at, :n)) FROM build WHERE project_id = :p AND stage = 'jenkins' "
                    "AND started_at >= :t"), {"p": p.project_id, "n": now, "t": now - timedelta(hours=1)})).scalar()
            for bid, ext, started, url in rows:
                if bid not in self._end_alerted:
                    self._end_alerted.add(bid)
                    mins = int((now - started).total_seconds() // 60)
                    self._send(p, f"⚠ 빌드 끝 알림 없음 — {ext} 시작 뒤 {mins}분째 끝 알림이 없다. Jenkins 확인"
                                  f"{chr(10) + str(url) if url else ''}")
            pend = self._pending.get(p.name)
            if not pend:
                continue
            if await self._covered(p, pend["head"], pend["at"]):
                if pend["alerted"]:
                    mins = int((now - pend["at"]).total_seconds() // 60)
                    self._send(p, f"✅ 빌드 알림 늦게 도착 — push {pend['short']} 뒤 {mins}분")
                del self._pending[p.name]
                self._changed(p.name)
                continue
            # 앞 빌드가 아직 돌거나 방금 끝났으면 그때부터 잰다(disableConcurrentBuilds — 줄 서 있다)
            base = max(pend["at"], busy) if busy else pend["at"]
            state = watch_state((now - base).total_seconds(), self.rules.watch_warn_s, self.rules.watch_alert_s)
            if state != pend["state"]:
                pend["state"] = state
                self._changed(p.name)
            if state == "missing" and not pend["alerted"]:
                pend["alerted"] = True
                mins = int((now - pend["at"]).total_seconds() // 60)
                self._send(p, f"⚠ 빌드 알림 없음 — push {pend['short']} \"{pend['subject'][:80]}\" 뒤 {mins}분째 "
                              f"Jenkins 시작 알림이 없다. Jenkins 확인\nhttps://jenkins.ronanlab.dev/job/{p.jenkins_job}/")

    async def _check_hook(self, p: PipeProject) -> None:
        """새 빌드마다 — 최근 빌드 원인으로 웹훅 끊김 · 복구를 판단한다(바뀔 때 한 번 알린다)."""
        async with self.engine.connect() as c:
            causes = [r[0] for r in (await c.execute(text(
                "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.cause')) FROM build WHERE project_id = :p "
                "AND stage = 'jenkins' ORDER BY id DESC LIMIT 30"), {"p": p.project_id})).all()]
        broken = webhook_broken(causes, self.rules.hook_break_after)
        was = self._hook_broken.get(p.name, False)
        if broken and not was:
            self._send(p, f"⚠ 웹훅 끊김 의심 — {p.jenkins_job} 최근 {self.rules.hook_break_after}번이 폴링으로 시작했다"
                          f"(웹훅이면 몇 초, 폴링은 최대 15분). GitHub 웹훅 Recent Deliveries · Cloudflare Bypass 확인")
        elif was and causes and causes[0] == "webhook":
            self._send(p, f"✅ 웹훅 복구 — {p.jenkins_job} 빌드가 다시 웹훅으로 시작했다")
            broken = False
        self._hook_broken[p.name] = broken
        if broken != was:
            self._changed(p.name)

    def _send(self, p: PipeProject, msg: str) -> None:
        log.warning("파이프라인 알림 %s: %s", p.name, msg.splitlines()[0])
        if self.notifier is None:
            return
        rule = self.notifier.rules.for_project(p.name)
        if rule is not None:
            self.notifier.send_direct(p.name, "pipeline", None, f"{rule.prefix} {msg}")

    async def scan_git(self, p: PipeProject, since_days: int = 7) -> int:
        """새 커밋 · push를 찾는다. 돌려주는 값: 새로 본 커밋 수."""
        raw = await self.git(p.repo, "log", p.branch, f"--since={since_days}.days", "-n", "300",
                             "--format=%H%x1f%ct%x1f%an%x1f%s")
        commits = []
        for line in raw.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 4 and SHA_RE.match(parts[0]):
                commits.append((parts[0], int(parts[1]), parts[2], parts[3]))
        try:
            pushed = set((await self.git(p.repo, "rev-list", f"origin/{p.branch}", "-n", "400")).split())
        except RuntimeError:
            pushed = set()
        if not commits:
            return 0
        async with self.engine.connect() as c:
            known = {r[0]: r[1] for r in (await c.execute(text(
                "SELECT sha, pushed_at FROM git_commit WHERE project_id = :p AND committed_at >= :t"),
                {"p": p.project_id, "t": _now() - timedelta(days=since_days + 1)})).all()}
        new = [x for x in commits if x[0] not in known]
        newly_pushed = [sha for sha, pa in known.items() if pa is None and sha in pushed]
        if not new and not newly_pushed:
            return 0
        now = _now()
        mine = 0
        for sha, ct, author, subject in reversed(new):   # 오래된 것부터
            at = datetime.fromtimestamp(ct, UTC).replace(tzinfo=None)
            try:
                files = len([x for x in (await self.git(p.repo, "diff-tree", "--no-commit-id", "--name-only", "-r",
                                                        "--root", sha)).splitlines() if x])
            except RuntimeError:
                files = None
            who = await self._attribute(p, at, subject)
            async with self.engine.begin() as c:
                await c.execute(text(
                    "INSERT IGNORE INTO git_commit (sha, project_id, session_id, character_id, event_id, author, subject, "
                    "files, committed_at, pushed_at) VALUES (:sha, :p, :s, :ch, :e, :a, :subj, :f, :at, :pa)"),
                    {"sha": sha, "p": p.project_id, "s": who[0] if who else None, "ch": who[1] if who else None,
                     "e": who[2] if who else None, "a": author[:128], "subj": (self.mask.text(subject) or "")[:512],
                     "f": files, "at": at, "pa": now if sha in pushed else None})
                if who:
                    mine += 1
                    await c.execute(text("UPDATE event SET commit_sha = :sha WHERE id = :e AND commit_sha IS NULL"),
                                    {"sha": sha, "e": who[2]})
        if newly_pushed:
            async with self.engine.begin() as c:
                await c.execute(text(
                    f"UPDATE git_commit SET pushed_at = :n WHERE pushed_at IS NULL AND sha IN "
                    f"({','.join(repr(s) for s in newly_pushed if SHA_RE.match(s))})"), {"n": now})
        if new:
            log.info("커밋 %s: 새로 %d개(세션이 만든 것 %d개)", p.name, len(new), mine)
        self._changed(p.name)
        return len(new)

    async def _attribute(self, p: PipeProject, at: datetime, subject: str = "") -> tuple[int, int, int] | None:
        """커밋 시각 직전(창 안)에 그 프로젝트 세션이 `git commit`을 부른 도구 호출 — (세션, 캐릭터, 이벤트).
        다른 저장소로 들어가 커밋한 명령(`cd ~/ronanlab-infra && git commit`, `git -C …`)은 뺀다(실측: 런슈즈 세션이
        인프라 저장소에 한 커밋이 런슈즈 커밋으로 잡혔다). 명령에 커밋 제목이 들어 있는 것을 먼저, 그다음 가까운 것."""
        w = timedelta(seconds=self.rules.attribute_window_s)
        async with self.engine.connect() as c:
            # 다른 프로젝트 세션도 본다 — 포먼 세션 · '미분류'(~/AI_programming) 세션이 `cd <저장소> && git commit`으로
            # 커밋한 것이 실측(11-02 펫퍼민트 19개 중 다수). 다른 프로젝트 세션은 제목이 맞을 때만(점수 2)
            rows = (await c.execute(text(
                "SELECT e.session_id, cs.character_id, e.id, "
                "COALESCE(JSON_UNQUOTE(JSON_EXTRACT(e.payload, '$.target_full')), e.target), cs.cwd, "
                "ch.project_id <=> :p FROM event e "
                "JOIN character_session cs ON cs.id = e.session_id JOIN `character` ch ON ch.id = cs.character_id "
                "WHERE cs.type = 'agent' AND e.type = 'tool_use' AND e.tool = 'Bash' "
                "AND e.target LIKE '%git%commit%' AND e.ts BETWEEN :a AND :b "
                "ORDER BY ABS(TIMESTAMPDIFF(MICROSECOND, e.ts, :at)) LIMIT 20"),
                {"p": p.project_id, "a": at - w, "b": at + timedelta(seconds=60), "at": at})).all()
        best, best_score = None, 0
        for r in rows:                       # 가까운 순서 — 같은 점수면 가까운 것
            sc = commit_match(r[3] or "", subject, p.repo, r[4])
            if not r[5] and sc < 2:
                continue
            if sc > best_score:
                best, best_score = r, sc
        return (best[0], best[1], best[2]) if best else None

    # ── 인프라 캐릭터 ──
    async def ensure_infra(self, p: PipeProject, kind: str) -> int | None:
        d = self.rules.infra.get(kind)
        if d is None:
            return None
        async with self.engine.begin() as c:
            r = (await c.execute(text(
                "SELECT id, retired_at, status FROM `character` WHERE project_id = :p AND kind = 'infra' AND infra_type = :k "
                "ORDER BY id DESC LIMIT 1"), {"p": p.project_id, "k": kind})).first()
            if r is None:
                res = await c.execute(text(
                    "INSERT INTO `character` (project_id, name, current_role, status, kind, infra_type, infra_source, "
                    "infra_endpoint, spawned_by, last_seen_at) VALUES (:p, :n, 'infra', 'IDLE', 'infra', :k, 'k8s', :e, "
                    "'auto', :t)"), {"p": p.project_id, "n": d.name, "k": kind, "e": f"https://{d.host}", "t": _now()})
                log.info("인프라 캐릭터 등장: %s %s (첫 웹훅)", p.name, d.name)
                self._record_infra(res.lastrowid, p, d, "등장 — 첫 웹훅")
                return res.lastrowid
            cid, retired, status = r
            if retired is not None or status == "STALE":
                await c.execute(text("UPDATE `character` SET retired_at = NULL, status = 'IDLE', last_seen_at = :t "
                                     "WHERE id = :id"), {"t": _now(), "id": cid})
                self._record_infra(cid, p, d, "돌아옴 — 웹훅")
            else:
                await c.execute(text("UPDATE `character` SET last_seen_at = :t WHERE id = :id"), {"t": _now(), "id": cid})
            self._fails[cid] = 0
            return cid

    def _record_infra(self, cid: int, p: PipeProject, d: InfraDef, what: str) -> None:
        self._submit(EventIn(source=EventSource.POLL, type=EventType.INFRA, character_id=cid,
                             tool=d.kind, target=f"{p.name} {d.name} {what}", payload={"project": p.name, "kind": d.kind}))

    async def poll_infra(self) -> None:
        async with self.engine.connect() as c:
            chars = (await c.execute(text(
                "SELECT ch.id, ch.infra_type, ch.status, ch.last_seen_at, ch.retired_at, p.name FROM `character` ch "
                "JOIN project p ON p.id = ch.project_id WHERE ch.kind = 'infra' AND ch.retired_at IS NULL"))).all()
        if not chars:
            return
        ok: dict[str, bool] = {}
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as cl:
            for kind in {r[1] for r in chars}:
                d = self.rules.infra.get(kind)
                if d is None:
                    continue
                try:
                    r = await cl.get(self.rules.ingress.rstrip("/") + d.health, headers={"Host": d.host})
                    ok[kind] = r.status_code < 500
                except httpx.HTTPError:
                    ok[kind] = False
        now = _now()
        changed = False
        for cid, kind, status, seen, _retired, pname in chars:
            if kind not in ok:
                continue
            async with self.engine.begin() as c:
                if ok[kind]:
                    self._fails[cid] = 0
                    await c.execute(text("UPDATE `character` SET last_seen_at = :t, status = IF(status = 'STALE', 'IDLE', "
                                         "status) WHERE id = :id"), {"t": now, "id": cid})
                    if status == "STALE":
                        log.info("인프라 캐릭터 회복: %s %s", pname, kind)
                        changed = True
                    continue
                n = self._fails[cid] = self._fails.get(cid, 0) + 1
                if n >= self.rules.stale_after and status != "STALE":
                    await c.execute(text("UPDATE `character` SET status = 'STALE' WHERE id = :id"), {"id": cid})
                    log.warning("인프라 캐릭터 STALE: %s %s (응답 없음 %d번)", pname, kind, n)
                    changed = True
                elif status == "STALE" and seen and now - seen > timedelta(hours=self.rules.retire_after_h):
                    await c.execute(text("UPDATE `character` SET retired_at = :t WHERE id = :id"), {"t": now, "id": cid})
                    log.warning("인프라 캐릭터 퇴장: %s %s", pname, kind)
                    changed = True
        if changed:
            self._changed(None)

    # ── 웹훅 ──
    async def on_jenkins(self, body: dict[str, Any]) -> dict[str, Any]:
        job = str(body.get("job") or "").split("/")[-1]
        p = self.rules.by("jenkins_job", job)
        if p is None:
            return {"ignored": f"모르는 Jenkins job: {job[:64]}"}
        try:
            number = int(body.get("number"))
        except (TypeError, ValueError):
            return {"ignored": "number 없음"}
        status, step = jenkins_status(body)
        head = await self.resolve(p, str(body.get("commit") or "").strip().lower())
        infra = await self.ensure_infra(p, "jenkins")
        msg = self.mask.text(str(body.get("message") or "")[:2000]) or None
        bid, prev = await self._upsert(p, "jenkins", f"{job}#{number}", head, head[:12] if head else None, status, step,
                                       _ts(body.get("timestamp")), body.get("url"), msg, infra,
                                       {**{k: body.get(k) for k in ("phase", "result", "stage", "duration")},
                                        "cause": build_cause(body)})
        if head and prev is None:
            await self._link_commits(p, bid, head)
        if prev is None:
            await self._check_hook(p)
        return {"build": bid, "status": status}

    async def on_harbor(self, body: dict[str, Any]) -> dict[str, Any]:
        out = []
        for it in harbor_items(body):
            p = self.rules.by("harbor_project", it["project"])
            if p is None:
                continue
            infra = await self.ensure_infra(p, "harbor")
            sha = await self.resolve(p, it["tag"]) if it["tag"] else None
            bid, _ = await self._upsert(p, "harbor", f"{it['repo']}@{it['digest'] or it['tag']}", sha, it["tag"],
                                        it["status"], it["step"], _ts(body.get("occur_at")), None, None, infra,
                                        {"repo": it["repo"], "type": it["type"], "digest": it["digest"]})
            out.append(bid)
        return {"builds": out} if out else {"ignored": f"체인 밖 이벤트 · 프로젝트({body.get('type')})"}

    async def on_argocd(self, body: dict[str, Any]) -> dict[str, Any]:
        p = self.rules.by("argocd_app", str(body.get("app") or ""))
        if p is None:
            return {"ignored": "모르는 ArgoCD 앱"}
        status, step = argocd_status(body)
        tag = image_tag(body.get("images"), p.harbor_project)
        if str(body.get("sync") or "") == "OutOfSync" and status in ("waiting", "running"):
            # OutOfSync일 때 앱 상태의 이미지는 아직 배포된 옛 태그다 — 그걸로 찾으면 이미 배포된 체인에 붙는다.
            # 대신 Jenkins가 성공했는데 아직 ArgoCD 성공이 없는 가장 최근 빌드(그 빌드가 인프라 저장소 태그를 바꿨다)
            pending = await self._undeployed_tag(p)
            tag = pending or tag
        sha = await self.resolve(p, tag)
        rev = str(body.get("revision") or "")[:40] or "?"
        infra = await self.ensure_infra(p, "argocd")
        msg = self.mask.text(str(body.get("message") or "")[:2000]) or None
        bid, _ = await self._upsert(p, "argocd", f"{p.argocd_app}@{rev}", sha, tag, status, step,
                                    _ts(body.get("at")), None, msg, infra,
                                    {k: body.get(k) for k in ("trigger", "sync", "health", "phase", "revision",
                                                              "op_revision", "automated")})
        return {"build": bid, "status": status}

    async def _undeployed_tag(self, p: PipeProject) -> str | None:
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT j.tag FROM build j WHERE j.project_id = :p AND j.stage = 'jenkins' AND j.status = 'success' "
                "AND j.tag IS NOT NULL AND NOT EXISTS (SELECT 1 FROM build a WHERE a.project_id = j.project_id "
                "AND a.stage = 'argocd' AND a.status = 'success' AND a.commit_sha = j.commit_sha) "
                "ORDER BY j.id DESC LIMIT 1"), {"p": p.project_id})).first()
        return r[0] if r else None

    async def _upsert(self, p: PipeProject, stage: str, ext: str, sha: str | None, tag: str | None, status: str,
                      step: str | None, at: datetime, url: Any, message: str | None, infra: int | None,
                      payload: dict[str, Any]) -> tuple[int, str | None]:
        """단계 행 하나를 만들거나 고친다. (id, 이전 상태 — 새 행이면 None). 실패로 바뀌면 알린다."""
        async with self._lock, self.engine.begin() as c:
            r = (await c.execute(text("SELECT id, status, commit_sha FROM build WHERE project_id = :p AND stage = :s "
                                      "AND external_id = :e FOR UPDATE"),
                                 {"p": p.project_id, "s": stage, "e": ext[:255]})).first()
            char = await self._author_char(c, sha)
            if r is None:
                res = await c.execute(text(
                    "INSERT INTO build (project_id, character_id, infra_character_id, stage, external_id, commit_sha, tag, "
                    "status, step, started_at, ended_at, log_url, message, payload) VALUES (:p, :ch, :inf, :s, :e, :sha, "
                    ":tag, :st, :step, :at, :end, :url, :msg, :pl)"),
                    {"p": p.project_id, "ch": char, "inf": infra, "s": stage, "e": ext[:255], "sha": sha, "tag": tag,
                     "st": status, "step": step, "at": at, "end": None if status == "running" else at,
                     "url": str(url)[:512] if url else None, "msg": message,
                     "pl": json.dumps(payload, ensure_ascii=False, default=str)})
                bid, prev = res.lastrowid, None
            else:
                bid, prev = r[0], r[1]
                if RANK[status] < RANK.get(prev, 0):
                    status = prev            # 늦게 온 running이 끝난 상태를 덮지 않는다
                await c.execute(text(
                    "UPDATE build SET status = :st, step = COALESCE(:step, step), commit_sha = COALESCE(commit_sha, :sha), "
                    "tag = COALESCE(tag, :tag), character_id = COALESCE(character_id, :ch), "
                    "ended_at = IF(:st = 'running', ended_at, COALESCE(ended_at, :at)), log_url = COALESCE(:url, log_url), "
                    "message = COALESCE(:msg, message), payload = :pl WHERE id = :id"),
                    {"st": status, "step": step if status == "failed" else None, "sha": sha, "tag": tag, "ch": char,
                     "at": at, "url": str(url)[:512] if url else None, "msg": message,
                     "pl": json.dumps(payload, ensure_ascii=False, default=str), "id": bid})
        log.info("파이프라인 %s %s %s → %s%s", p.name, stage, ext, status, f" ({step})" if step else "")
        self._submit(EventIn(source=EventSource.WEBHOOK, type=EventType.BUILD, character_id=infra, tool=stage,
                             target=f"{STAGE_LABEL[stage]} {ext} {status}{' · ' + step if step else ''}",
                             commit_sha=sha, status=EventStatus.ERROR if status == "failed" else (
                                 EventStatus.DONE if status == "success" else (
                                     EventStatus.WAITING if status == "waiting" else EventStatus.WORKING)),
                             payload={"project": p.name, "stage": stage, "build_id": bid, "status": status,
                                      "step": step, "tag": tag}))
        if status == "failed" and prev != "failed":
            await self._alert(p, stage, ext, sha, step, message, url)
        self._changed(p.name)
        return bid, prev

    async def _author_char(self, c: Any, sha: str | None) -> int | None:
        if not sha:
            return None
        r = (await c.execute(text("SELECT character_id FROM git_commit WHERE sha = :s"), {"s": sha})).first()
        return r[0] if r else None

    async def _link_commits(self, p: PipeProject, bid: int, head: str) -> None:
        """이 빌드에 묶인 커밋들 — 이 프로젝트의 직전 Jenkins 빌드 머리..이번 머리. 직전이 없으면 머리 하나."""
        async with self.engine.connect() as c:
            r = (await c.execute(text(
                "SELECT commit_sha FROM build WHERE project_id = :p AND stage = 'jenkins' AND id < :id "
                "AND commit_sha IS NOT NULL AND commit_sha <> :h ORDER BY id DESC LIMIT 1"),
                {"p": p.project_id, "id": bid, "h": head})).first()
        shas = [head]
        if r:
            try:
                out = (await self.git(p.repo, "rev-list", f"{r[0]}..{head}", "-n", "100")).split()
                shas = [s for s in out if SHA_RE.match(s)] or [head]
            except RuntimeError:
                pass
        async with self.engine.begin() as c:
            for s in shas:
                await c.execute(text("INSERT IGNORE INTO build_commit (build_id, commit_sha) VALUES (:b, :s)"),
                                {"b": bid, "s": s})

    async def _alert(self, p: PipeProject, stage: str, ext: str, sha: str | None, step: str | None,
                     message: str | None, url: Any) -> None:
        if self.notifier is None:
            return
        rule = self.notifier.rules.for_project(p.name)
        if rule is None:
            return
        who, subj = "", ""
        if sha:
            async with self.engine.connect() as c:
                r = (await c.execute(text(
                    "SELECT gc.subject, cs.title, ch.name FROM git_commit gc LEFT JOIN character_session cs ON cs.id = gc.session_id "
                    "LEFT JOIN `character` ch ON ch.id = gc.character_id WHERE gc.sha = :s"), {"s": sha})).first()
            if r:
                subj = r[0] or ""
                who = f" — {r[2]}{' · ' + r[1] if r[1] else ''}" if r[2] else " — 사람(세션 밖)"
        lines = [f"{rule.prefix} ❌ 파이프라인 실패 · {STAGE_LABEL[stage]}{' · ' + step if step else ''}",
                 f"커밋 {sha[:8] if sha else '?'} {subj[:120]}{who}", f"{ext}"]
        if message:
            lines.append(message[:300])
        if url:
            lines.append(str(url)[:300])
        self.notifier.send_direct(p.name, "pipeline", None, "\n".join(lines))

    def _submit(self, ev: EventIn) -> None:
        try:
            self.pipeline.submit(ev)
        except Exception as e:  # noqa: BLE001
            log.warning("파이프라인 기록 실패: %s", type(e).__name__)

    def _changed(self, project: str | None) -> None:
        try:
            self.pipeline.publish({"type": "pipeline", "project": project})
        except Exception:  # noqa: BLE001
            pass
        self.on_change()

    # ── 화면 ──
    async def snapshot(self, chains: int = 6) -> dict[str, Any]:
        """프로젝트마다: 인프라 캐릭터, 최근 체인(머리 커밋 기준 — 커밋들 → Jenkins → Harbor → ArgoCD), 빌드 대기 커밋."""
        out = []
        async with self.engine.connect() as c:
            for p in self.rules.projects.values():
                infra = [{"id": r[0], "name": r[1], "kind": r[2], "status": r[3], "last_seen_at": _iso(r[4]),
                          "retired": r[5] is not None}
                         for r in (await c.execute(text(
                             "SELECT id, name, infra_type, status, last_seen_at, retired_at FROM `character` "
                             "WHERE project_id = :p AND kind = 'infra' ORDER BY FIELD(infra_type, 'jenkins', 'harbor', "
                             "'argocd')"), {"p": p.project_id})).all()]
                heads = [r[0] for r in (await c.execute(text(
                    "SELECT commit_sha FROM build WHERE project_id = :p AND commit_sha IS NOT NULL "
                    "GROUP BY commit_sha ORDER BY MAX(started_at) DESC LIMIT :n"), {"p": p.project_id, "n": chains})).all()]
                rows = []
                for h in heads:
                    stages = {}
                    for r in (await c.execute(text(
                            "SELECT stage, status, step, external_id, started_at, ended_at, log_url, message FROM build "
                            "WHERE project_id = :p AND commit_sha = :h ORDER BY id"), {"p": p.project_id, "h": h})).all():
                        stages[r[0]] = {"status": r[1], "step": r[2], "ext": r[3], "started_at": _iso(r[4]),
                                        "ended_at": _iso(r[5]), "url": r[6], "message": (r[7] or "")[:500] or None}
                    commits = await self._commits(c, p, h)
                    order = ["commit", "jenkins", "harbor", "argocd"]
                    broke = next((s for s in order[1:] if stages.get(s, {}).get("status") == "failed"), None)
                    rows.append({"head": h, "short": h[:8], "commits": commits, "stages": stages, "broke": broke,
                                 "at": max((v["started_at"] or "" for v in stages.values()), default=None)})
                waiting = [{"sha": r[0], "short": r[0][:8], "subject": r[1], "pushed": r[2] is not None,
                            "at": _iso(r[3]), "session_id": r[4], "who": r[5]} for r in (await c.execute(text(
                    "SELECT gc.sha, gc.subject, gc.pushed_at, gc.committed_at, gc.session_id, "
                    "COALESCE(cs.title, ch.name) FROM git_commit gc "
                    "LEFT JOIN character_session cs ON cs.id = gc.session_id LEFT JOIN `character` ch ON ch.id = gc.character_id "
                    "WHERE gc.project_id = :p AND NOT EXISTS (SELECT 1 FROM build_commit bc WHERE bc.commit_sha = gc.sha) "
                    "AND NOT EXISTS (SELECT 1 FROM build b WHERE b.commit_sha = gc.sha) "
                    "AND gc.committed_at >= :t ORDER BY gc.committed_at DESC LIMIT 5"),
                    {"p": p.project_id, "t": _now() - timedelta(days=2)})).all()]
                pend = self._pending.get(p.name)
                watch = {"state": pend["state"], "short": pend["short"], "subject": pend["subject"],
                         "since": _iso(pend["at"])} if pend else None
                out.append({"project": p.name, "infra": infra, "chains": rows, "waiting": waiting, "watch": watch,
                            "webhook_broken": self._hook_broken.get(p.name, False)})
        return {"projects": out, "generated_at": _iso(_now())}

    async def _commits(self, c: Any, p: PipeProject, head: str) -> list[dict[str, Any]]:
        rows = (await c.execute(text(
            "SELECT gc.sha, gc.subject, gc.session_id, cs.title, ch.name, gc.author FROM git_commit gc "
            "LEFT JOIN character_session cs ON cs.id = gc.session_id LEFT JOIN `character` ch ON ch.id = gc.character_id "
            "WHERE gc.sha IN (SELECT bc.commit_sha FROM build_commit bc JOIN build b ON b.id = bc.build_id "
            "WHERE b.project_id = :p AND b.commit_sha = :h) OR gc.sha = :h ORDER BY gc.committed_at DESC LIMIT 20"),
            {"p": p.project_id, "h": head})).all()
        return [{"sha": r[0], "short": r[0][:8], "subject": r[1], "session_id": r[2], "title": r[3], "character": r[4],
                 "author": r[5]} for r in rows]
