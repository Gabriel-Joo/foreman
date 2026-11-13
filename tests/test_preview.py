"""미리보기 브리지(11-05) — worktree 화면 파일 + 지금 브리지로 넘기기."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bridge import previews as previews_mod
from bridge.inject import Refused
from bridge.preview import IDENT_HEADER, IDENT_PATH, create_app
from bridge.previews import PORTS, Previews, free_port


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
        # 11-06 — 미리보기 서버가 꺼지면 탭이 알린다(메인 포트로 가는 길), 화면 코드는 미리보기인 것을 안다
        assert 'window.FOREMAN_PREVIEW={"label": "cc/foreman-2", "mainPort": 8000}' in r.text and "원본 화면 열기" in r.text
        assert (await c.get("/static/js/a.js")).text == "export const v = 'worktree';"
        r = await c.post("/api/echo?q=1", headers={"Authorization": "Bearer T"}, content="hi")
        j = r.json()
        assert r.status_code == 201 and j["auth"] == "Bearer T" and j["q"] == "1" and j["body"] == "hi"
        assert j["host"] == "127.0.0.1:8000"                                   # Host는 지금 브리지 것
        assert r.headers.get_list("set-cookie") == ["a=1; Path=/terminal", "b=2; Path=/"]


def test_free_port():
    assert free_port() in PORTS


# ---- 11-13 — 죽은 미리보기를 「있음」으로 답하지 않는다 ----

async def test_ident_endpoint(tmp_path):
    app = create_app(tmp_path, "http://127.0.0.1:8000", "cc/x", transport=httpx.ASGITransport(app=upstream_app()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8201") as c:
        r = await c.get(IDENT_PATH)
        assert r.headers[IDENT_HEADER] == "1" and r.json()["foreman_preview"] is True


async def _serve(body: bytes, headers: str = ""):
    async def h(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n" + headers.encode()
                     + b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        await writer.drain()
        writer.close()
    srv = await asyncio.start_server(h, "127.0.0.1", 0)
    return srv, srv.sockets[0].getsockname()[1]


async def test_probe_distinguishes_preview_from_other_service():
    ours, p1 = await _serve(b'{"foreman_preview": true}', f"{IDENT_HEADER}: 1\r\n")
    other, p2 = await _serve(b'{"ok": 1}')                      # 포트는 열려 있지만 다른 서비스(model_service 같은)
    async with ours, other:
        assert await Previews._probe(p1) is True
        assert await Previews._probe(p2) is False
    assert await Previews._probe(p1) is False                    # 닫힌 포트


class FakeTmux:
    def __init__(self):
        self.sessions: set[str] = set()
        self.calls: list[tuple] = []

    async def __call__(self, _sock, *a):
        self.calls.append(a)
        if a[0] == "has-session":
            if a[2] not in self.sessions:
                raise Refused("no")
        elif a[0] == "new-session":
            self.sessions.add(a[3])
        elif a[0] == "kill-session":
            self.sessions.discard(a[2])
        return ""


def make(tmp_path, monkeypatch, probe):
    ft = FakeTmux()
    monkeypatch.setattr(previews_mod, "tmux", ft)
    monkeypatch.setattr(Previews, "_probe", staticmethod(probe))
    wtp = tmp_path / "repo" / ".worktrees" / "w1"
    wtp.mkdir(parents=True)
    cfg = tmp_path / "wt.toml"
    cfg.write_text('[preview.p]\ncmd = "echo {port}"\n')
    pv = Previews(cfg, "sock", "http://127.0.0.1:8000", tmp_path / "pv.json")
    return pv, ft, str(wtp)


async def test_alive_dead_tmux_and_restart(tmp_path, monkeypatch):
    async def ok(_p): return True
    pv, ft, path = make(tmp_path, monkeypatch, ok)
    e = await pv.start("p", path)
    assert e["tmux"] == "fm-pv-w1" and (await pv.get(path)) is not None            # 정상
    ft.sessions.clear()                                                             # tmux가 죽음
    assert await pv.get(path) is None and "tmux" in pv.dead[path] and path not in pv.state
    e2 = await pv.start("p", path)                                                  # 다시 띄움
    assert e2["restarted"] is True and path not in pv.dead and "fm-pv-w1" in ft.sessions


async def test_other_service_on_port_is_dead(tmp_path, monkeypatch):
    state = {"up": True}
    async def probe(_p): return state["up"]
    pv, ft, path = make(tmp_path, monkeypatch, probe)
    await pv.start("p", path)
    state["up"] = False                                                             # tmux는 있는데 포트는 남의 것/무응답
    assert await pv.get(path) is None and "미리보기로 답하지 않습니다" in pv.dead[path]
    assert "fm-pv-w1" not in ft.sessions                                            # 남은 tmux도 치웠다


async def test_restart_failure_says_dead(tmp_path, monkeypatch):
    state = {"up": True}
    async def probe(_p): return state["up"]
    pv, ft, path = make(tmp_path, monkeypatch, probe)
    await pv.start("p", path)
    state["up"] = False
    async def no_wait(_p): return False
    monkeypatch.setattr(Previews, "_ready", staticmethod(no_wait))
    with pytest.raises(Refused) as ei:
        await pv.start("p", path)
    assert "미리보기가 죽어 있습니다" in str(ei.value) and "다시 띄우지 못했습니다" in str(ei.value)
    assert path in pv.dead and path not in pv.state                                 # 사유가 남아 패널이 보여 준다


async def test_new_port_when_port_taken(monkeypatch):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    taken = s.getsockname()[1]
    monkeypatch.setattr(previews_mod, "PORTS", [taken, taken + 1])
    try:
        assert free_port() != taken
    finally:
        s.close()
