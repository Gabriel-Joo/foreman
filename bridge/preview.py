"""미리보기 브리지(11-05, docs/11_worktree.md 2절 A안) — worktree의 화면 파일 + 지금 브리지의 데이터.

    python -m bridge.preview --port 8201 --static <worktree>/bridge/static --upstream http://127.0.0.1:8000 --label cc/foreman-2

- `/` · `/office` · `/classic` · `/static/*`는 worktree의 파일로 준다. 페이지에는 "미리보기" 띠와 토큰 받기(#t=)를 끼운다
- 그 밖의 HTTP(`/api/*` · `/terminal/*` …)와 웹소켓(`/ws` · `/terminal/ws`)은 지금 브리지로 그대로 넘긴다 — 실시간 데이터가 보이고,
  DB 적재 · 알림 · 승인 · 웹훅은 지금 브리지 한 벌만 돈다. 그래서 미리보기 화면의 버튼도 **실제로** 동작한다
- 웹소켓은 지금 브리지와 같은 규칙으로 Origin이 Host와 같을 때만 넘긴다(다른 사이트가 쿠키로 셸을 여는 것 막기)
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect as ws_connect

PAGES = {"/": "office.html", "/office": "office.html", "/classic": "dashboard.html"}
IDENT_PATH = "/__foreman_preview"      # bridge/previews.py가 살아 있는지 볼 때 두드리는 주소
IDENT_HEADER = "X-Foreman-Preview"
DROP = {"host", "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "content-length",
        "content-encoding", "proxy-authorization", "proxy-authenticate"}


def head_inject(label: str, main_port: int = 8000) -> str:
    """토큰은 주소의 #t=로 받는다(조각은 서버로 안 간다) — 포트가 달라 브라우저 저장소가 따로라서. 받자마자 주소에서 지운다.
    11-06: 미리보기 탭에서 [미리보기 닫기]를 누르면 이 탭을 띄운 서버가 꺼져 "끊김"인 채로 남았다(메인 브리지는 멀쩡했다).
    그래서 이 서버가 꺼지면 화면을 덮어 알리고 원본 화면으로 가는 길을 준다 — 조용히 끊겨 있지 않게."""
    gone = ("미리보기 서버가 꺼져 이 탭은 끊겼습니다(미리보기를 닫았거나 세션을 끝냈습니다). 메인 브리지는 그대로 돕니다.")
    return ("<script>(()=>{const m=location.hash.match(/[#&]t=([^&]+)/);if(!m)return;"
            "try{localStorage.setItem('foremanToken',decodeURIComponent(m[1]))}catch(e){}"
            "history.replaceState(null,'',location.pathname+location.search)})()</script>"
            f"<script>window.FOREMAN_PREVIEW={json.dumps({'label': label, 'mainPort': main_port})};"
            "(()=>{let miss=0;const main=location.protocol+'//'+location.hostname+':'+window.FOREMAN_PREVIEW.mainPort+'/';"
            "const show=()=>{if(document.getElementById('fmGone'))return;const d=document.createElement('div');d.id='fmGone';"
            "d.style.cssText='position:fixed;inset:0;z-index:10000;background:#000c;color:#fff;display:flex;align-items:center;"
            "justify-content:center;flex-direction:column;gap:12px;font:14px/1.6 system-ui,sans-serif;text-align:center;padding:24px';"
            f"d.innerHTML={json.dumps(html.escape(gone))}+'<a style=\"color:#fbbf24\" href=\"'+main+'\">원본 화면 열기</a>';"
            "document.body.appendChild(d)};"
            "setInterval(()=>{fetch('/static/office.html',{method:'HEAD',cache:'no-store'})"
            ".then(r=>{miss=r.ok?0:miss+1}).catch(()=>{miss++}).finally(()=>{if(miss>=2)show()})},5000)})()</script>"
            "<style>#fmPreview{position:fixed;left:50%;top:0;transform:translateX(-50%);z-index:9999;pointer-events:none;"
            "background:#b45309;color:#fff;font:600 12px/1.6 system-ui,sans-serif;padding:1px 12px;border-radius:0 0 8px 8px;"
            "opacity:.92;white-space:nowrap}</style>"
            f"<div id=\"fmPreview\">미리보기 · {html.escape(label)} — 화면만 이 브랜치, 데이터 · 버튼은 실제 브리지입니다</div>")


def create_app(static_dir: str | Path, upstream: str, label: str, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    static = Path(static_dir).resolve()
    up = upstream.rstrip("/")
    up_host = urlsplit(up).netloc
    client = httpx.AsyncClient(base_url=up, timeout=httpx.Timeout(60.0, connect=5.0), transport=transport)   # transport: 시험용

    @asynccontextmanager
    async def life(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await client.aclose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=life)
    inject = head_inject(label, urlsplit(up).port or 8000)

    def page(name: str) -> HTMLResponse:
        s = (static / name).read_text()
        s = s.replace("<head>", "<head>" + inject, 1) if "<head>" in s else inject + s
        return HTMLResponse(s, headers={"Cache-Control": "no-cache"})

    for path, name in PAGES.items():
        app.add_api_route(path, (lambda n=name: page(n)), methods=["GET"], include_in_schema=False)

    @app.middleware("http")
    async def no_stale(request: Request, call_next):  # type: ignore[no-untyped-def]
        resp = await call_next(request)
        if request.url.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get(IDENT_PATH, include_in_schema=False)
    async def ident() -> Response:
        """「이 포트가 미리보기 브리지다」 확인용 — 다른 서비스가 같은 포트를 잡고 있어도 가를 수 있게(11-13)."""
        return Response(json.dumps({"foreman_preview": True, "label": label}), media_type="application/json",
                        headers={IDENT_HEADER: "1", "Cache-Control": "no-store"})

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def proxy(path: str, request: Request) -> Response:
        hdrs = [(k, v) for k, v in request.headers.items() if k.lower() not in DROP]
        r = await client.request(request.method, "/" + path, params=request.query_params.multi_items(),
                                 headers=hdrs, content=await request.body())
        out = Response(r.content, status_code=r.status_code)
        for k, v in r.headers.multi_items():
            if k.lower() not in DROP:
                out.headers.append(k, v)
        return out

    @app.websocket("/{path:path}")
    async def ws_proxy(ws: WebSocket, path: str) -> None:
        origin, host = ws.headers.get("origin"), ws.headers.get("host")
        if origin and urlsplit(origin).netloc != host:
            await ws.close(code=1008)
            return
        url = up.replace("http", "ws", 1) + "/" + path + (f"?{ws.url.query}" if ws.url.query else "")
        extra = [("Cookie", ws.headers["cookie"])] if "cookie" in ws.headers else []
        try:
            upstream_ws = await ws_connect(url, additional_headers=extra, origin=f"http://{up_host}",  # type: ignore[arg-type]
                                           subprotocols=ws.scope.get("subprotocols") or None, max_size=None)
        except Exception:  # noqa: BLE001 — 지금 브리지가 거절하면 같은 뜻으로 닫는다
            await ws.close(code=1011)
            return
        await ws.accept(subprotocol=upstream_ws.subprotocol)

        async def down() -> None:
            async for m in upstream_ws:
                await (ws.send_bytes(m) if isinstance(m, bytes) else ws.send_text(m))

        async def upward() -> None:
            while True:
                m = await ws.receive()
                if m["type"] == "websocket.disconnect":
                    return
                await upstream_ws.send(m["bytes"] if m.get("bytes") is not None else m.get("text") or "")

        tasks = [asyncio.create_task(down()), asyncio.create_task(upward())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except WebSocketDisconnect:
            pass
        finally:
            for t in tasks:
                t.cancel()
            await upstream_ws.close()
            try:
                await ws.close()
            except RuntimeError:
                pass

    app.state.info = {"static": str(static), "upstream": up, "label": label}
    return app


def main() -> None:
    ap = argparse.ArgumentParser(description="FOREMAN 미리보기 브리지")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--static", required=True)
    ap.add_argument("--upstream", default="http://127.0.0.1:8000")
    ap.add_argument("--label", default="미리보기")
    a = ap.parse_args()
    print(json.dumps({"preview": a.port, "static": a.static, "upstream": a.upstream}, ensure_ascii=False), flush=True)
    uvicorn.run(create_app(a.static, a.upstream, a.label), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
