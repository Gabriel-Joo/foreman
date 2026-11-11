"""화면 확인 — 헤드리스 크로미움을 CDP로 몰아 픽셀 화면을 점검하고 찍는다(11-06, 사용자: "콘솔에서 돌려 달라고 매번 나한테 하지 말고").

    .venv/bin/python tools/screen.py                                  # 세 테마 × 세 크기 × 포먼 현장
    .venv/bin/python tools/screen.py --themes magic --sizes 1366x768 --views hq,foreman,map --session 189
    .venv/bin/python tools/screen.py --base http://127.0.0.1:8201/    # worktree 미리보기 화면

- 테마 × 창 크기 × 화면마다 `window.office.layoutAudit()`(사람이 가구 · 소품 · 이름표에 가려지나) · `propAudit()`(소품 그림) ·
  `audit()`(고정 안 된 것)을 돌리고, 화면마다 `nameAudit()`(사람 이름이 구역 이름표 · 다른 이름과 겹치나, 11-06)를 세고 PNG를 찍는다. 결과는 `<out>/report.json`, 사진은 `<out>/<테마>_<크기>_<화면>.png`
- 화면마다 `labelAudit()`(11-10) — 지금 그린 그대로: 이름표(구역 · 출하 라인 · 캐릭터 이름 · 말풍선) ↔ 사람 몸, 이름표끼리, 구역 · 출하 라인 이름표 ↔ 가구(그림의 불투명 범위).
  layoutAudit(좌석 자리 기준) · nameAudit(이름 ↔ 구역 이름표)이 0건인데 실제로는 겹치던 것을 잡는다
- 테마 × 크기마다 `termAudit`(11-10) — 패널 입력 칸이 패널 · 창 밖으로 넘치나 · 터미널과 겹치나, 터미널을 연 채로 한 번 더(`<…>_term.png`, `--no-term`이면 닫힌 채만).
  연 채로는 xterm 칸 폭 ≥ 글자 폭 · 이름표 줄 ↔ 터미널 겹침 · 툴팁이 터미널을 덮나(마우스를 올린 뒤도), 글씨 배율 전 단계 × dpr 1 · 0.7(`--no-term-sweep`이면 건너뜀)
- **터미널을 여는 점검은 `/api/terminal/open`을 불러 실제 tmux 창을 바꾼다(select-window)** — :8000(라이브 셸)에서는 `--no-term`으로 돌리거나,
  시험 ttyd를 따로 띄운 서버를 `--base`로 준다(11-10 `log/terminal_cell_20261110.md`)
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


# 터미널 · 입력 칸 겹침(11-10 — README 「터미널 — 입력 칸이 터미널 글자를 덮어 오른쪽이 잘린다」). 문제 글 목록을 돌려준다.
# 패널 입력 칸(pForm)이 패널 밖 · 창 밖으로 넘치나, 터미널 칸과 겹치나, 패널과 터미널이 겹치나, xterm 글자 칸이 iframe보다 넓은가
TERM_AUDIT_JS = """(()=>{
  const R=(e)=>{if(!e||e.hidden||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height]};
  const ov=(a,b)=>a&&b?Math.max(0,Math.min(a[0]+a[2],b[0]+b[2])-Math.max(a[0],b[0]))*Math.max(0,Math.min(a[1]+a[3],b[1]+b[3])-Math.max(a[1],b[1])):0;
  const side=R(document.querySelector('.oside')), form=R(document.getElementById('pForm')), term=R(document.querySelector('.term'));
  const out=[]; const H=innerHeight, W=innerWidth;
  if(form){ if(side&&form[1]+form[3]>side[1]+side[3]+1) out.push(`입력 칸이 패널 아래로 넘침 ${Math.round(form[1]+form[3]-side[1]-side[3])}px`);
    if(form[1]+form[3]>H+1) out.push(`입력 칸이 창 아래로 넘침 ${Math.round(form[1]+form[3]-H)}px`);
    const o=ov(form,term); if(o>0) out.push(`입력 칸 · 터미널 겹침 ${Math.round(o)}px²`); }
  const os=ov(side,term); if(side&&side[0]>0&&os>0) out.push(`패널 · 터미널 겹침 ${Math.round(os)}px²`);
  const f=document.getElementById('termFrame');
  if(term&&f&&document.querySelector('.term.open')){ let sw=0; try{const s=f.contentDocument.querySelector('.xterm-screen'); sw=s?s.getBoundingClientRect().width:0}catch(e){}
    const fw=f.getBoundingClientRect().width; if(sw>fw+1) out.push(`터미널 글자 칸(${Math.round(sw)})이 터미널(${Math.round(fw)})보다 넓음`);
    if(term[0]+term[2]>W+1) out.push('터미널이 창 오른쪽 밖으로 넘침'); }
  return out})()"""

# 터미널을 연 채 그리기 점검(11-10 사용자 — "git push"가 "it push", 커서가 줄 끝이 아니라 `b` 자리, 「런슈즈 터미널」이 프롬프트 줄을 가림).
# ① xterm 칸 폭 ≥ 글자 폭(장치 px 올림) ② 글씨 = 배율의 터미널 글씨 ③ 이름표 줄 ↔ iframe 겹침 ④ 툴팁 등 떠 있는 것이 터미널을 덮음.
# 함수 하나를 페이지에 두고(window.__fmTermCheck) 연 직후 · 마우스를 올린 뒤 · 배율 단계마다(dpr 1 · 0.7) 부른다
TERM_CHECK_DEF = """window.__fmTermCheck = async () => {
  const out=[], f=document.getElementById('termFrame');
  if(!f||!document.querySelector('.term.open')) return out;
  let w,t; try{w=f.contentWindow;t=w.term}catch(e){return ['터미널 안을 읽지 못함']}
  if(!t||!t.options) return ['xterm이 뜨지 않음'];
  const m=await import('/static/js/uiscale.js');
  const dpr=w.devicePixelRatio||1, cv=w.document.createElement('canvas').getContext('2d');
  cv.font=`${t.options.fontSize}px ${t.options.fontFamily}`;
  const g=cv.measureText('W'.repeat(50)).width/50;
  const d=t._core&&t._core._renderService&&t._core._renderService.dimensions;
  let cell=d&&d.css&&d.css.cell?d.css.cell.width:0;
  if(!cell){const s=w.document.querySelector('.xterm-screen'); cell=s&&t.cols?s.getBoundingClientRect().width/t.cols:0}
  const tag=`글씨 ${t.options.fontSize}px · dpr ${+dpr.toFixed(3)} · 간격 ${t.options.letterSpacing||0}`;
  if(!(cell>0)) out.push(`xterm 칸 폭을 읽지 못함 — ${tag}`);
  else if(cell*dpr+0.01<Math.ceil(g*dpr-0.02)) out.push(`xterm 칸 폭(${cell.toFixed(2)})이 글자 폭(${g.toFixed(2)})보다 좁음 — ${tag}`);
  if(t.options.fontSize!==m.termFont()) out.push(`터미널 글씨 ${t.options.fontSize}px ≠ 배율 글씨 ${m.termFont()}px`);
  const fr=f.getBoundingClientRect();
  const ov=(a,b)=>Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
  const bar=document.querySelector('.term-bar');
  if(bar){const o=ov(bar.getBoundingClientRect(),fr); if(o>0.5) out.push(`이름표 줄 · 터미널 겹침 ${Math.round(o)}px²`);
    for(const e of bar.querySelectorAll('select,button,span')){ if(e.hidden||!e.getClientRects().length) continue;
      const r=e.getBoundingClientRect(), o2=ov(r,fr);
      if(o2>0.5) out.push(`이름표 줄의 ${e.id||e.className||e.tagName} · 터미널 겹침 ${Math.round(o2)}px²(y ${Math.round(r.top)}~${Math.round(r.bottom)}, 터미널 ${Math.round(fr.top)}부터)`)}}
  for(const e of document.querySelectorAll('.tip:not([hidden]), .term-msg:not(:empty)')){
    const o=ov(e.getBoundingClientRect(),fr); if(o>0.5) out.push(`${e.className}이(가) 터미널을 덮음 — ${e.textContent.trim().slice(0,30)}`)}
  return out};
1"""

# 마우스가 터미널(iframe)에 들어갈 때 툴팁이 뜨나(11-10 ③ — iframe의 title이 툴팁이 되어 프롬프트 줄 위에 남았다). 안에서는 mouseout이 안 와 남는다
TERM_HOVER_JS = """(async()=>{const f=document.getElementById('termFrame');
  f.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));
  await new Promise(r=>setTimeout(r,500));
  const out=(await window.__fmTermCheck()).map(x=>`마우스를 터미널에 올린 뒤: ${x}`);
  document.body.dispatchEvent(new MouseEvent('mousedown',{bubbles:true})); return out})()"""

# 글씨 배율 단계마다 바꾼 직후(한 프레임 뒤) 점검 — 가장 작은 단계부터 끝까지, 끝나면 처음 배율로 돌려놓는다
TERM_SWEEP_JS = """(async()=>{const m=await import('/static/js/uiscale.js'), out=[], i0=m.STEPS.indexOf(m.uiScale());
  const frame=()=>new Promise(r=>requestAnimationFrame(()=>setTimeout(r,30)));
  // 맨 위로 갔다가 맨 아래로 — 첫 측정 전에 글씨가 꼭 한 번 바뀌게(이미 맨 아래면 안 바뀌어, dpr을 바꾼 뒤 xterm이 옛 dpr 칸을 쥔 채였다)
  for(let k=0;k<m.STEPS.length;k++) m.step(1);
  for(let k=0;k<m.STEPS.length;k++) m.step(-1);
  for(let i=0;i<m.STEPS.length;i++){ if(i) m.step(1); await frame();
    for(const x of await window.__fmTermCheck()) out.push(`배율 ${Math.round(m.uiScale()*100)}%: ${x}`)}
  while(m.STEPS.indexOf(m.uiScale())>Math.max(0,i0)) m.step(-1);
  return out})()"""

TERM_DPRS = (1, 0.7)            # 브라우저 확대 100% · 70%(11-10 사용자 측정 dpr 0.698)

VIEW_JS = """(()=>{const v=%s; if(v==='hq'||v==='map'){window.office.go(v); return v}
  const b=[...document.querySelectorAll('[data-room]')].find(b=>b.dataset.room===v||b.textContent.includes(v));
  if(b){b.click(); return b.dataset.room} window.office.go(v); return v})()"""


FFMPEG = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux")))


async def probe_ok(p: Page, where: str) -> bool:
    """화면이 점검 화면(?probe=1)으로 떴는가(11-11). 아니면 저절로 열린 패널이 라이브의 「보고 옴」을 읽음으로 남긴다 — 조용히 넘기지 않고 문제로 센다."""
    if await p.ev("!!(window.office.probeMode && window.office.probeMode())"):
        return True
    print(f"{where}: 점검 표시(probe)가 없습니다 — 이 화면이 연 패널이 「보고 옴」을 읽음으로 남길 수 있습니다")
    return False


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
        url = f"{a.base.rstrip('/')}/office?probe=1&theme={th}" + (f"&demo={a.record}&hold=1" if demo else "")
        await p.call("Page.navigate", url=url)
        if not await p.wait("!!(window.office && window.office.layoutAudit)"):
            print(f"{th}: 화면이 뜨지 않았습니다")
            return 1
        if not await probe_ok(p, th):
            bad += 1
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
            # ?probe=1 — 점검 도구가 연 화면이라는 표시(11-11). 저절로 열린 패널이 「보고 옴」을 읽음으로 남기지 않게(store.js PROBE)
            await p.call("Page.navigate", url=a.base + ("&" if "?" in a.base else "?") + "probe=1")
            await p.wait("document.readyState==='complete'")
            await p.ev(f"localStorage.setItem('foremanToken', {json.dumps(api_token())}); 1")
            if a.ui_scale:                                 # 글씨 크기(가+ · 가−) — 사용자가 보는 배율로 찍는다(11-09)
                await p.ev(f"localStorage.setItem('foremanUiScale', {json.dumps(str(a.ui_scale))}); 1")
            if a.record:                                   # 녹화(13) — 점검 대신
                bad += await record(p, a, out, report)
            # 패널 너비는 좁게 · 넓게 두 값뿐이다(11-10 모눈) — 둘 다 본다. 크기 이름에 붙인다(1366x768w = 넓게)
            panels = [x.strip() for x in a.panel.split(",") if x.strip()]
            grid_rooms: dict = {}                          # 테마 → 역할별 방 칸(gridAudit) — 셋이 같아야 한다
            for th in ([] if a.record else a.themes.split(",")):
                for size0, panel in [(s, q) for s in a.sizes.split(",") for q in panels]:
                    size = size0 + ("w" if panel == "wide" else "")
                    w, h = (int(x) for x in size0.lower().split("x"))
                    await p.ev(f"localStorage.setItem('foremanPanelMode', {json.dumps(panel)}); localStorage.setItem('foremanPanelOpen', '1'); 1")
                    await p.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
                    if a.demo:                             # 시연 장면으로 정지 사진(13e) — 실제 /api에 닿지 않게
                        await p.ev("localStorage.removeItem('foremanToken'); 1")
                    await p.call("Page.navigate", url=f"{a.base.rstrip('/')}/office?probe=1&theme={th}" + (f"&demo={a.demo}" if a.demo else ""))
                    if not await p.wait("!!(window.office && window.office.layoutAudit)"):
                        report["runs"].append({"theme": th, "size": size, "error": "화면이 뜨지 않았습니다"})
                        bad += 1
                        continue
                    if not await probe_ok(p, f"{th} {size}"):
                        bad += 1
                    await asyncio.sleep(a.wait)
                    # 좌석 점검만 — 이름표 점검(labelAudit, 지금 화면 그대로)은 아래 화면마다 센다(11-10)
                    la = await p.ev("window.office.layoutAudit({labels: false})")
                    pa = await p.ev("window.office.propAudit()")
                    au = await p.ev("window.office.audit().filter(x=>!x.fixed)")
                    # 모눈 점검(11-10) — 방 겹침 · 끊긴 복도 · 못 가는 자리 · 방 밖 가구 · 이름표가 방 왼쪽 위 칸인가. 방 자리는 테마끼리 견준다(아래)
                    ga = await p.ev("window.office.gridAudit ? window.office.gridAudit() : {problems: [], rooms: null}") or {}
                    if ga.get("rooms") is not None:
                        grid_rooms.setdefault(th, ga["rooms"])
                    base = {"theme": th, "size": size, "layoutAudit": la, "propAudit_issues": (pa or {}).get("issues", []),
                            "audit_unfixed": au, "gridAudit": ga.get("problems") or []}
                    n_bad = len(la or []) + len(base["propAudit_issues"]) + len(base["gridAudit"])
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
                        # 이름표 ↔ 가구 · 사람 몸 · 이름표끼리(11-10) — 지금 그린 그대로. nameAudit · layoutAudit이 못 잡던 겹침
                        lb = await p.ev("window.office.labelAudit ? window.office.labelAudit() : []") or []
                        base.setdefault("labelAudit", {})[view] = lb
                        bad += len(lb)
                        # [전체] 카드 · [⌂] 현황판 이름(11-09) — 겹침 · 그림 덮음 · 화면 · 칸 밖 · 잘림. 전엔 --eval로 따로 불러야 봤다
                        ca = await p.ev("window.office.cardAudit ? window.office.cardAudit().problems : []") or []
                        base.setdefault("cardAudit", {})[view] = ca
                        bad += len(ca)
                        # 방 바깥(11-11) — 띠 · 풍경 높이(px) · 소품 · 행인 수. 점검(띠가 방 그림 · 이름표를 덮나 등)은 cardAudit 안에
                        base.setdefault("outside", {})[view] = await p.ev("window.office.outside ? window.office.outside() : null")
                        # 호버 잘림(11-09) — 지금 화면의 모든 호버 글을 실제 툴팁 상자에 넣어 넘침 · 낱말 끊김 · 화면보다 큼
                        ta = await p.ev("window.office.tipAudit ? window.office.tipAudit() : {n: 0, problems: []}") or {}
                        base.setdefault("tipAudit", {})[view] = ta
                        bad += len(ta.get("problems") or [])
                        if a.eval:
                            base.setdefault("eval", {})[view] = await p.ev(a.eval)
                        f = out / f"{th}_{size}_{view}.png"
                        await p.shot(f)
                        shots.append({"view": view, "went": got, "png": str(f)})
                        if a.clip:
                            cf = out / f"{th}_{size}_{view}_clip.png"
                            await p.shot(cf, tuple(float(v) for v in a.clip.split(",")))  # type: ignore[arg-type]
                            shots.append({"view": view, "clip": a.clip, "png": str(cf)})
                    # 터미널 · 입력 칸 겹침(11-10) — 닫힌 채, 그리고 터미널을 연 채(마지막 화면 · --session 패널 그대로). 사진 한 장 더
                    ta = {"closed": await p.ev(TERM_AUDIT_JS) or [], "open": None}
                    if not a.demo and not a.no_term and await p.ev(
                            "!!document.getElementById('termToggle') && !document.querySelector('.term[hidden]')"):
                        await p.ev("document.getElementById('termToggle').click(); 1")
                        await p.wait("(()=>{try{return !!document.getElementById('termFrame').contentWindow.term}catch(e){return false}})()", 8)
                        await asyncio.sleep(1.0)
                        await p.ev(TERM_CHECK_DEF)
                        ta["open"] = (await p.ev(TERM_AUDIT_JS) or []) + (await p.ev("window.__fmTermCheck()") or [])
                        f = out / f"{th}_{size}_term.png"
                        await p.shot(f)
                        shots.append({"view": "term", "png": str(f)})
                        ta["open"] += await p.ev(TERM_HOVER_JS) or []
                        # 글씨 배율 전 단계 × 브라우저 확대(dpr 1 · 0.7). dpr을 바꾼 "직후"는 보지 않는다 — 헤드리스의 Emulation은
                        # matchMedia(resolution) change를 내지 않아(11-10 잼) xterm도 uiscale.js onDprChange도 반응하지 않는다. 배율을 바꾸면 그때 dpr로 다시 잰다
                        if not a.no_term_sweep:
                            for dpr in TERM_DPRS:
                                if dpr != 1:
                                    await p.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=dpr, mobile=False)
                                    await asyncio.sleep(0.4)
                                ta["open"] += [f"dpr {dpr} {x}" for x in await p.ev(TERM_SWEEP_JS) or []]
                            await p.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
                            await asyncio.sleep(0.3)
                        await p.ev("document.getElementById('termToggle').click(); 1")
                    base["termAudit"] = ta
                    bad += len(ta["closed"]) + len(ta["open"] or [])
                    base["shots"] = shots
                    base["page_errors"] = p.errors[:]
                    bad += len(p.errors)
                    p.errors.clear()
                    report["runs"].append(base)
                    for x in base["gridAudit"][:5]:
                        print(f"  gridAudit {x.get('kind')}: {x.get('text')}")
                    n_names = sum(len(v) for v in base.get("nameAudit", {}).values())
                    n_labels = sum(len(v) for v in base.get("labelAudit", {}).values())
                    n_cards = sum(len(v) for v in base.get("cardAudit", {}).values())
                    n_tips = sum(len(v.get("problems") or []) for v in base.get("tipAudit", {}).values())
                    n_tipn = sum(v.get("n") or 0 for v in base.get("tipAudit", {}).values())
                    n_term = len(ta["closed"]) + len(ta["open"] or [])
                    print(f"{th} {size}: gridAudit {len(base['gridAudit'])} · layoutAudit {len(la or [])} · labelAudit {n_labels} · nameAudit {n_names} · cardAudit {n_cards} · "
                          f"tipAudit {n_tips}/{n_tipn} · propAudit {len(base['propAudit_issues'])} · "
                          f"termAudit {n_term}{'' if ta['open'] is not None else '(닫힘만)'} · "
                          f"audit(고정 안 됨) {len(au or [])} · 페이지 오류 {len(base['page_errors'])} · 사진 {len(shots)}")
            # ⑤ 테마 셋의 방 자리가 같은가(11-10 모눈 — 테마는 이름 · 그림 · 색만 다르다)
            if len(grid_rooms) > 1:
                same = len({json.dumps(v, sort_keys=True) for v in grid_rooms.values()}) == 1
                report["gridRooms"] = {"same": same, "rooms": grid_rooms}
                print(f"테마 {' · '.join(grid_rooms)} 방 자리 — {'같음' if same else '다름(문제)'}")
                bad += 0 if same else 1
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
    ap.add_argument("--panel", default="narrow,wide", help="패널 너비 — narrow(좁게) · wide(넓게)를 쉼표로(11-10 두 값뿐, 기본 둘 다). 넓게는 크기 이름 끝에 w")
    ap.add_argument("--session", help="이 세션 패널을 연 채 찍는다(세션 id)")
    ap.add_argument("--eval", help="화면마다 돌려 결과를 report.json에 남길 JS 식")
    ap.add_argument("--no-term", action="store_true", help="터미널을 열어 보는 점검(termAudit 열림)을 건너뛴다 — 닫힌 채 점검은 한다")
    ap.add_argument("--no-term-sweep", action="store_true",
                    help="터미널을 연 채 글씨 배율 전 단계 × dpr 1 · 0.7 점검(11-10)을 건너뛴다 — 연 직후 점검 · 마우스 올림 점검은 한다")
    ap.add_argument("--wait", type=float, default=2.0, help="화면을 바꾼 뒤 기다릴 초(캐릭터가 걸어 들어갈 시간)")
    ap.add_argument("--clip", help="x,y,w,h(CSS 픽셀) — 그 부분만 2배로 한 장 더(<…>_clip.png)")
    ap.add_argument("--out")
    ap.add_argument("--ui-scale", type=float, help="글씨 크기 배율(가+ · 가−, uiscale.js STEPS 0.8~1.1 중 하나, 처음 값 0.9 — 양 끝 예: 0.8 · 1.1)")
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
