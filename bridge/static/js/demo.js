// 시연 재생(13, docs/13_demo_capture.md) — `/?demo=<이름>`이면 실제 연결(WS · 스냅샷 · /api)을 열지 않고 `static/demo/<이름>.json`
// 대본을 같은 화면 코드에 흘린다. 녹화(tools/screen.py --record)가 window.demoState로 시작 · 끝을 본다.
//
// 대본 { "title", "source": "record"|"script", "snapshot": /api/dashboard 모양, "pipeline": {프로젝트: /api/pipeline 항목},
//        "api": {"/api/…": 응답 JSON}, "steps": [{"at": ms, "msg": WS 메시지} | {"at", "pipeline": {…}} | {"at", "js": "…"} | {"at", "end": true}] }
// - source: record = 실제 기록 재생(이름만 시연용), script = 대본(실제 기록으로 안 되는 장면) — 캡션 표시(〔실제 기록 재생〕/〔시연 재생〕)의 근거

// 대본 안의 "@+1500" · "@-60000" — 재생 시작 기준 상대 시각(ms)을 그 순간의 ISO 시각으로. 화면은 Date.now()와 견주는 곳이
// 많아서(출하 라인 진행 · 끝난 세션 3분) 녹화한 날의 시각을 그대로 넣으면 다르게 그린다
function rebase(v, t0) {
  if (typeof v === 'string') {
    const m = /^@([+-]\d+)$/.exec(v);
    return m ? new Date(t0 + Number(m[1])).toISOString() : v;
  }
  if (Array.isArray(v)) return v.map((x) => rebase(x, t0));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, rebase(x, t0)]));
  return v;
}

export async function runDemo(store, name) {
  const st = (window.demoState = { name, started: null, done: false, step: 0, error: null });
  try {
    const r = await fetch(`/static/demo/${encodeURIComponent(name)}.json`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`대본이 없습니다: ${name} (${r.status})`);
    const raw = await r.json();
    const sc = rebase(raw, Date.now());          // 스냅샷 · api — 불러온 순간 기준(단계는 시작한 순간 기준으로 아래에서 다시)
    st.source = sc.source || 'script';
    // 실제 /api는 부르지 않는다 — 대본에 있는 응답만, 나머지는 빈 404(실제 데이터가 화면에 섞이지 않게)
    const realFetch = window.fetch.bind(window);
    window.fetch = (url, opt) => {
      const u = new URL(typeof url === 'string' ? url : url.url, location.href);
      if (!u.pathname.startsWith('/api/')) return realFetch(url, opt);
      let body = (sc.api || {})[u.pathname];
      // 대본에 없는 대화 · 활동은 빈 목록 — 404면 패널이 "HTTP 404"를 그려 실제 화면에 없는 오류가 영상에 남는다
      if (body === undefined && /\/conversation$/.test(u.pathname)) body = { turns: [] };
      if (body === undefined && /\/activity$/.test(u.pathname)) body = { items: [] };
      return Promise.resolve(new Response(JSON.stringify(body ?? {}), { status: body === undefined ? 404 : 200,
        headers: { 'Content-Type': 'application/json' } }));
    };
    store.demo = true;
    store.token = store.token || 'demo';
    store.setConn('up');
    store.applySnapshot(sc.snapshot);
    if (sc.pipeline) { store.state.pipeline = new Map(Object.entries(sc.pipeline)); store.touch('pipe'); }
    // &hold=1 — 녹화기가 카메라 · 캐릭터가 자리를 잡을 때까지 기다렸다가 window.demoStart()로 단계를 시작한다
    // (기다리는 동안 대본이 흘러 앞부분이 잘렸다 — 11-06 V2). 스냅샷은 이미 들어가 있다
    st.ready = true;
    if (new URLSearchParams(location.search).get('hold') === '1') await new Promise((ok) => { window.demoStart = ok; });
    st.started = performance.now();
    const steps = [...rebase(raw.steps || [], Date.now())].sort((a, b) => a.at - b.at);
    for (const s of steps) {
      setTimeout(() => {
        try {
          if (s.msg) store.apply(s.msg);
          if (s.pipeline) {
            for (const [k, v] of Object.entries(s.pipeline)) store.state.pipeline.set(k, v);
            store.touch('pipe');
          }
          if (s.js) new Function('store', s.js)(store);
          if (s.end) st.done = true;
        } catch (e) { st.error = String(e); }
        st.step += 1;
      }, s.at);
    }
    if (!steps.some((s) => s.end)) setTimeout(() => { st.done = true; }, (steps.length ? steps[steps.length - 1].at : 0) + 1000);
  } catch (e) {
    st.error = String(e);
    st.done = true;
  }
}
