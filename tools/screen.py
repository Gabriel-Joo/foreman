"""화면 확인 — 헤드리스 크로미움을 CDP로 몰아 픽셀 화면을 점검하고 찍는다(11-06, 사용자: "콘솔에서 돌려 달라고 매번 나한테 하지 말고").

    .venv/bin/python tools/screen.py                                  # 세 테마 × 세 크기 × 포먼 현장
    .venv/bin/python tools/screen.py --themes magic --sizes 1366x768 --views hq,foreman,map --session 189
    .venv/bin/python tools/screen.py --base http://127.0.0.1:8201/    # worktree 미리보기 화면

- 테마 × 창 크기 × 화면마다 `window.office.layoutAudit()`(사람이 가구 · 소품 · 이름표에 가려지나) · `propAudit()`(소품 그림) ·
  `audit()`(고정 안 된 것)을 돌리고, 화면마다 `nameAudit()`(사람 이름이 구역 이름표 · 다른 이름과 겹치나, 11-06)를 세고 PNG를 찍는다. 결과는 `<out>/report.json`, 사진은 `<out>/<테마>_<크기>_<화면>.png`
- 브라우저: playwright가 받아 둔 `~/.cache/ms-playwright/chromium_headless_shell-*/…/chrome-headless-shell`(설치 없음)
- API 토큰은 `.env.bridge`에서 읽어 그 페이지의 localStorage에만 넣는다 — 출력 · 파일에 남기지 않는다
- 문제가 하나라도 있으면 종료 코드 1(CLAUDE.md: 테마 자리 · 가구를 바꾸면 세 테마 모두 0건)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import websockets

REPO = Path(__file__).resolve().parent.parent
THEMES = ("magic", "office", "site")


def chrome_path() -> str:
    pats = ["~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell",
            "~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome"]
    for p in pats:
        hits = sorted(glob.glob(os.path.expanduser(p)))
        if hits:
            return hits[-1]
    for name in ("chromium", "chromium-browser", "google-chrome"):
        if shutil.which(name):
            return shutil.which(name)  # type: ignore[return-value]
    sys.exit("헤드리스 크로미움을 찾지 못했습니다 — ~/.cache/ms-playwright 아래를 확인해 주세요")


def api_token() -> str:
    for ln in (REPO / ".env.bridge").read_text(encoding="utf-8").splitlines():
        if ln.startswith("FOREMAN_API_TOKEN="):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(".env.bridge에 FOREMAN_API_TOKEN이 없습니다")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Page:
    def __init__(self, ws: websockets.ClientConnection) -> None:
        self.ws, self.n, self.errors = ws, 0, []

    async def call(self, method: str, **params: object) -> dict:
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("method") == "Runtime.exceptionThrown":         # 페이지의 잡히지 않은 오류도 모은다
                d = m["params"]["exceptionDetails"]
                self.errors.append((d.get("exception") or {}).get("description", d.get("text", ""))[:300])
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    async def ev(self, expr: str) -> object:
        r = await self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"])
        return r["result"].get("value")

    async def wait(self, expr: str, t: float = 20) -> bool:
        end = time.time() + t
        while time.time() < end:
            try:
                if await self.ev(expr):
                    return True
            except RuntimeError:
                pass
            await asyncio.sleep(0.3)
        return False

    async def shot(self, path: Path, clip: tuple[float, float, float, float] | None = None, scale: float = 2) -> None:
        """clip=(x, y, w, h) CSS 픽셀이면 그 부분만 scale배로 — 문맥을 아끼며 자세히 볼 때."""
        kw: dict = {"format": "png"}
        if clip:
            kw["clip"] = {"x": clip[0], "y": clip[1], "width": clip[2], "height": clip[3], "scale": scale}
        r = await self.call("Page.captureScreenshot", **kw)
        path.write_bytes(base64.b64decode(r["data"]))


VIEW_JS = """(()=>{const v=%s; if(v==='hq'||v==='map'){window.office.go(v); return v}
  const b=[...document.querySelectorAll('[data-room]')].find(b=>b.dataset.room===v||b.textContent.includes(v));
  if(b){b.click(); return b.dataset.room} window.office.go(v); return v})()"""


FFMPEG = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux")))


async def record(p: Page, a: argparse.Namespace, out: Path, report: dict) -> int:
    """녹화(13, docs/13_demo_capture.md) — 시연 대본(`/office?demo=<이름>`)을 틀고 초당 fps장 JPEG(clip)를 찍어 GIF(+ WebM)로.
    --record - 이면 대본 없이 실제 화면(시연용이 아니다 — 캡션은 〔실제 화면〕). 테마를 여럿 주면 차례로 이어 찍는다(V4 테마 전환).
    끝은 --secs(테마마다) 또는 대본의 끝(window.demoState.done). 결과가 --max-mb를 넘으면 실패(Notion 파일 한도 5MB)."""
    name = a.name or (a.record if a.record != "-" else "live")
    frames = out / f"{name}_frames"
    frames.mkdir(parents=True, exist_ok=True)
    demo = a.record != "-"
    if demo:                                            # 시연은 실제 /api에 닿지 않게 토큰을 지운다(demo.js도 /api를 막는다)
        await p.ev("localStorage.removeItem('foremanToken'); 1")
    w, h = (int(x) for x in a.sizes.split(",")[0].lower().split("x"))
    await p.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
    kw: dict = {"format": "jpeg", "quality": 90}
    if a.clip:
        x, y, cw, ch = (float(v) for v in a.clip.split(","))
        kw["clip"] = {"x": x, "y": y, "width": cw, "height": ch, "scale": a.scale}
    n, bad, info = 0, 0, []
    for th in a.themes.split(","):
        url = f"{a.base.rstrip('/')}/office?theme={th}" + (f"&demo={a.record}&hold=1" if demo else "")
        await p.call("Page.navigate", url=url)
        if not await p.wait("!!(window.office && window.office.layoutAudit)"):
            print(f"{th}: 화면이 뜨지 않았습니다")
            return 1
        if demo and not await p.wait("!!(window.demoState && (window.demoState.ready || window.demoState.error))"):
            print(f"{th}: 대본을 읽지 못했습니다")
            return 1
        if a.views:
            await p.ev(VIEW_JS % json.dumps(a.views.split(",")[0]))
        await asyncio.sleep(a.lead)                     # 카메라 · 캐릭터가 자리를 잡는 동안 — 대본은 아직 멈춰 있다(hold)
        if demo:
            await p.ev("window.demoStart && window.demoStart(); 1")
        t0, k = time.time(), 0
        while True:
            el = time.time() - t0
            if (a.secs and el >= a.secs) or el >= a.max_secs:
                break
            if not a.secs and demo and await p.ev("window.demoState.done"):
                break
            r = await p.call("Page.captureScreenshot", **kw)
            (frames / f"f{n:05d}.jpg").write_bytes(base64.b64decode(r["data"]))
            n, k = n + 1, k + 1
            await asyncio.sleep(max(0.0, t0 + k / a.fps - time.time()))
        st = await p.ev("window.demoState || null") if demo else None
        if st and st.get("error"):
            print(f"{th}: 대본 오류 — {st['error']}")
            bad += 1
        info.append({"theme": th, "frames": k, "secs": round(time.time() - t0, 1), "source": (st or {}).get("source", "live")})
    bad += len(p.errors)
    gif = out / f"{name}.gif"
    r = subprocess.run(["python3", "-I", str(REPO / "tools" / "frames_to_gif.py"), str(frames), str(gif), "--fps", str(a.fps),
                        "--colors", str(a.colors), "--every", str(a.every)] + (["--width", str(a.gif_width)] if a.gif_width else []),
                       capture_output=True, text=True)
    print((r.stdout or r.stderr).strip())
    made = [gif] if r.returncode == 0 else []
    if a.webm and FFMPEG:                                # Playwright ffmpeg — VP9 · WebM만, JPEG를 파이프로만 받는다
        webm = out / f"{name}.webm"
        cat = b"".join(f.read_bytes() for f in sorted(frames.glob("f*.jpg")))
        subprocess.run([FFMPEG[-1], "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(a.fps),
                        "-c:v", "mjpeg", "-i", "pipe:0", "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36", "-pix_fmt", "yuv420p",
                        str(webm)], input=cat, check=False)
        if webm.exists():
            made.append(webm)
    for f in made:
        mb = f.stat().st_size / 1e6
        over = mb > a.max_mb
        bad += int(over)
        print(f"{f.name} {mb:.2f}MB" + (f" — {a.max_mb}MB를 넘습니다(Notion 파일 한도 5MB): --gif-width · --every · --colors를 줄여 다시" if over else ""))
    report["record"] = {"name": name, "frames": n, "themes": info, "files": [{"path": str(f), "mb": round(f.stat().st_size / 1e6, 2)} for f in made],
                        "page_errors": p.errors[:]}
    return bad or (0 if made else 1)


async def run(a: argparse.Namespace) -> int:
    out = Path(a.out or Path.home() / ".foreman" / "screens" / datetime.now().strftime("%Y%m%d_%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    port = free_port()
    prof = tempfile.mkdtemp(prefix="fm-screen-")
    proc = subprocess.Popen([chrome_path(), f"--remote-debugging-port={port}", "--no-sandbox", "--hide-scrollbars",
                             f"--user-data-dir={prof}", "--window-size=1920,1080", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    report: dict = {"base": a.base, "made": datetime.now().isoformat(timespec="seconds"), "runs": []}
    bad = 0
    try:
        tabs = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                break
            except OSError:
                await asyncio.sleep(0.2)
        if not tabs:
            sys.exit("헤드리스 크로미움이 뜨지 않았습니다")
        wsurl = next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"]
        async with websockets.connect(wsurl, max_size=80_000_000) as ws:
            p = Page(ws)
            await p.call("Page.enable")
            await p.call("Runtime.enable")
            await p.call("Page.navigate", url=a.base)
            await p.wait("document.readyState==='complete'")
            await p.ev(f"localStorage.setItem('foremanToken', {json.dumps(api_token())}); 1")
            if a.ui_scale:                                 # 글씨 크기(가+ · 가−) — 사용자가 보는 배율로 찍는다(11-09)
                await p.ev(f"localStorage.setItem('foremanUiScale', {json.dumps(str(a.ui_scale))}); 1")
            if a.record:                                   # 녹화(13) — 점검 대신
                bad += await record(p, a, out, report)
            for th in ([] if a.record else a.themes.split(",")):
                for size in a.sizes.split(","):
                    w, h = (int(x) for x in size.lower().split("x"))
                    await p.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
                    if a.demo:                             # 시연 장면으로 정지 사진(13e) — 실제 /api에 닿지 않게
                        await p.ev("localStorage.removeItem('foremanToken'); 1")
                    await p.call("Page.navigate", url=f"{a.base.rstrip('/')}/office?theme={th}" + (f"&demo={a.demo}" if a.demo else ""))
                    if not await p.wait("!!(window.office && window.office.layoutAudit)"):
                        report["runs"].append({"theme": th, "size": size, "error": "화면이 뜨지 않았습니다"})
                        bad += 1
                        continue
                    await asyncio.sleep(a.wait)
                    la = await p.ev("window.office.layoutAudit()")
                    pa = await p.ev("window.office.propAudit()")
                    au = await p.ev("window.office.audit().filter(x=>!x.fixed)")
                    base = {"theme": th, "size": size, "layoutAudit": la, "propAudit_issues": (pa or {}).get("issues", []),
                            "audit_unfixed": au}
                    n_bad = len(la or []) + len(base["propAudit_issues"])
                    bad += n_bad
                    shots = []
                    for view in a.views.split(","):
                        got = await p.ev(VIEW_JS % json.dumps(view))
                        await asyncio.sleep(a.wait)
                        if a.session:
                            await p.ev(f"window.office.openSession({int(a.session)}); 1")
                            await asyncio.sleep(a.wait)
                        # 이름 ↔ 구역 이름표 · 다른 이름 겹침(11-06) — 화면마다(이름은 그 화면에 그린 것만), 비켜도 남은 것
                        na = await p.ev("window.office.nameAudit ? window.office.nameAudit() : []") or []
                        base.setdefault("nameAudit", {})[view] = na
                        bad += len(na)
                        # [전체] 카드 · [⌂] 현황판 이름(11-09) — 겹침 · 그림 덮음 · 화면 · 칸 밖 · 잘림. 전엔 --eval로 따로 불러야 봤다
                        ca = await p.ev("window.office.cardAudit ? window.office.cardAudit().problems : []") or []
                        base.setdefault("cardAudit", {})[view] = ca
                        bad += len(ca)
                        if a.eval:
                            base.setdefault("eval", {})[view] = await p.ev(a.eval)
                        f = out / f"{th}_{size}_{view}.png"
                        await p.shot(f)
                        shots.append({"view": view, "went": got, "png": str(f)})
                        if a.clip:
                            cf = out / f"{th}_{size}_{view}_clip.png"
                            await p.shot(cf, tuple(float(v) for v in a.clip.split(",")))  # type: ignore[arg-type]
                            shots.append({"view": view, "clip": a.clip, "png": str(cf)})
                    base["shots"] = shots
                    base["page_errors"] = p.errors[:]
                    bad += len(p.errors)
                    p.errors.clear()
                    report["runs"].append(base)
                    n_names = sum(len(v) for v in base.get("nameAudit", {}).values())
                    n_cards = sum(len(v) for v in base.get("cardAudit", {}).values())
                    print(f"{th} {size}: layoutAudit {len(la or [])} · nameAudit {n_names} · cardAudit {n_cards} · propAudit {len(base['propAudit_issues'])} · "
                          f"audit(고정 안 됨) {len(au or [])} · 페이지 오류 {len(base['page_errors'])} · 사진 {len(shots)}")
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"결과 {out}/report.json — 문제 {bad}건")
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="FOREMAN 픽셀 화면 점검 · 스크린샷(헤드리스 크로미움)")
    ap.add_argument("--base", default="http://127.0.0.1:8000/")
    ap.add_argument("--themes", default=",".join(THEMES))
    ap.add_argument("--sizes", default="1920x1080,1366x768,1024x700")
    ap.add_argument("--views", default="foreman", help="hq · map · 현장 이름(foreman · runshoes …)을 쉼표로")
    ap.add_argument("--session", help="이 세션 패널을 연 채 찍는다(세션 id)")
    ap.add_argument("--eval", help="화면마다 돌려 결과를 report.json에 남길 JS 식")
    ap.add_argument("--wait", type=float, default=2.0, help="화면을 바꾼 뒤 기다릴 초(캐릭터가 걸어 들어갈 시간)")
    ap.add_argument("--clip", help="x,y,w,h(CSS 픽셀) — 그 부분만 2배로 한 장 더(<…>_clip.png)")
    ap.add_argument("--out")
    ap.add_argument("--ui-scale", type=float, help="글씨 크기 배율(가+ · 가−, uiscale.js STEPS 중 하나 — 예: 1.3)")
    # 녹화(13) — 예: --record pipeline --themes office --sizes 1366x768 --views runshoes --clip 60,135,890,570 --gif-width 640
    ap.add_argument("--demo", help="정지 사진을 시연 장면(bridge/static/demo/<이름>.json)으로 — 점검 · 찍기는 그대로")
    ap.add_argument("--record", help="시연 대본 이름(bridge/static/demo/<이름>.json) — '-'면 대본 없이 실제 화면")
    ap.add_argument("--name", help="결과 파일 이름(기본: 대본 이름)")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--secs", type=float, default=0, help="테마마다 찍을 초(0이면 대본이 끝날 때까지)")
    ap.add_argument("--max-secs", type=float, default=60)
    ap.add_argument("--lead", type=float, default=2.5, help="찍기 전 기다릴 초 — 카메라 · 캐릭터가 자리를 잡는 시간(대본은 그동안 멈춤)")
    ap.add_argument("--scale", type=float, default=1, help="--clip 배율(녹화)")
    ap.add_argument("--gif-width", type=int, default=0)
    ap.add_argument("--colors", type=int, default=128, help="GIF 색 수 — 11-06 V2 비교: 64 이하는 작은 소품 색이 빠진다")
    ap.add_argument("--every", type=int, default=1, help="GIF에 n장마다 한 장")
    ap.add_argument("--webm", action="store_true", help="WebM도(5MB 넘는 긴 장면용)")
    ap.add_argument("--max-mb", type=float, default=5.0)
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
