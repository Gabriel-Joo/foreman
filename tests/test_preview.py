"""미리보기 브리지(11-05) — worktree 화면 파일 + 지금 브리지로 넘기기."""

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bridge.preview import create_app
from bridge.previews import PORTS, free_port


def upstream_app() -> FastAPI:
    up = FastAPI()

    @up.post("/api/echo")
    async def echo(request: Request) -> JSONResponse:
        r = JSONResponse({"auth": request.headers.get("authorization"), "q": request.query_params.get("q"),
                          "body": (await request.body()).decode(), "host": request.headers.get("host")}, status_code=201)
        r.headers.append("set-cookie", "a=1; Path=/terminal")
        r.headers.append("set-cookie", "b=2; Path=/")
        return r
    return up


async def test_pages_static_and_proxy(tmp_path):
    (tmp_path / "office.html").write_text("<html><head><title>x</title></head><body>원본</body></html>")
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "a.js").write_text("export const v = 'worktree';")
    app = create_app(tmp_path, "http://127.0.0.1:8000", "cc/foreman-2", transport=httpx.ASGITransport(app=upstream_app()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8201") as c:
        r = await c.get("/")
        assert r.status_code == 200 and "미리보기 · cc/foreman-2" in r.text and "foremanToken" in r.text
        assert r.text.index("foremanToken") < r.text.index("<title>")          # 모듈보다 먼저 토큰을 받는다
        assert (await c.get("/static/js/a.js")).text == "export const v = 'worktree';"
        r = await c.post("/api/echo?q=1", headers={"Authorization": "Bearer T"}, content="hi")
        j = r.json()
        assert r.status_code == 201 and j["auth"] == "Bearer T" and j["q"] == "1" and j["body"] == "hi"
        assert j["host"] == "127.0.0.1:8000"                                   # Host는 지금 브리지 것
        assert r.headers.get_list("set-cookie") == ["a=1; Path=/terminal", "b=2; Path=/"]


def test_free_port():
    assert free_port() in PORTS
