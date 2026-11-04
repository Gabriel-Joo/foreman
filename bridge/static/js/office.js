// FOREMAN 픽셀 오피스 — 테마 렌더러(10단계). store.js(데이터)는 그대로, 이 파일은 그리기만.
// 10a: 지도 ↔ 방 줌, 도형 캐릭터, 상태별 모습, 방 배지(작업 · 승인 · 파이프라인 · 토큰). 동작은 theme.json이 정한다(theme.js).
// 좌표: 월드는 타일 단위로 정하고 px = 타일 × layout.tile. 카메라가 월드 → 화면.

import { resolveAction, infraAction, groupSubagents, tokenRate } from './theme.js';
import { loadSprites } from './sprites.js';

const KNOWN = [['runshoes', '런슈즈'], ['petmint-rag-chatbot', '펫퍼민트'], ['foreman', '포먼']];
const RATE_WIN = 10 * 60 * 1000;          // 토큰 속도 창 — 최근 10분
const SPEED = 3.2;                         // 걷는 속도(타일/초)

export async function createOffice(root, store, themeUrl = '/static/themes/office/theme.json') {
  const theme = await (await fetch(themeUrl, { cache: 'no-cache' })).json();
  const L = theme.layout, T = L.tile, P = theme.palette;
  // 10d: 시트 테마면 원본 PNG를 받아 둔다(자르기 · 외곽선 · 색조는 sprites.js). 도형 테마(office)는 그대로
  const SP = theme.sprites.kind === 'sheets' ? await loadSprites(theme, new URL(themeUrl, location.href)) : null;
  const CH = (SP && theme.sprites.chars) || {};

  root.innerHTML = `
    <header class="otop">
      <span class="brand">FOREMAN</span><span class="muted small">픽셀 오피스 · ${esc(theme.label)}</span>
      <button id="oMap" class="ghost" title="지도로(Esc)">지도</button>
      <span id="oAlerts" class="oalerts"></span>
      <span class="small muted">테마 ${[['office', '오피스'], ['magic', '마법학교']].map(([k, v]) => k === theme.name ? `<b>${v}</b>` : `<a href="/office?theme=${k}">${v}</a>`).join(' · ')}</span>
      <a class="small" href="/">클래식 화면</a>
      <span id="oConn" class="conn"></span>
      <button id="oTok" class="ghost" title="API 토큰">토큰</button>
    </header>
    <div id="oStage" class="ostage"><canvas id="oCv"></canvas></div>
    <aside id="oInfo" class="oinfo" hidden></aside>`;
  const $ = (id) => root.querySelector('#' + id);
  const cv = $('oCv'), ctx = cv.getContext('2d');

  // ── 상태 ───────────────────────────────────────────
  let world = { rooms: [], lounge: null, w: 0, h: 0 };
  const actors = new Map();            // key → actor
  const tokHist = new Map();           // 방 이름 → [{t, v, o}]
  let lastSnap = null;
  let view = 'map';                    // 'map' | 방 이름
  let selected = null;                 // actor key
  const cam = { x: 0, y: 0, s: 1 }, camT = { x: 0, y: 0, s: 1 };
  let W = 0, H = 0, dpr = 1, last = performance.now(), running = true;

  // ── 월드 만들기(store가 바뀔 때마다) ─────────────────
  function rooms(st) {
    const byName = new Map(st.projects.map((p) => [p.name, p]));
    const names = [...KNOWN.map(([n]) => n), ...st.projects.map((p) => p.name).filter((n) => n && !KNOWN.some(([k]) => k === n))];
    const out = [];
    names.forEach((name, i) => {
      const p = byName.get(name);
      const label = (p && p.label) || (KNOWN.find(([k]) => k === name) || [])[1] || name;
      out.push({ name, label, x: i * (L.room.w + L.gap), y: 0, w: L.room.w, h: L.room.h,
                 sessionIds: p ? p.sessionIds : [] });
    });
    const lp = byName.get(null);
    const lx = out.length * (L.room.w + L.gap);
    const lounge = { name: null, label: '라운지(떠돌이)', x: lx, y: 0, w: L.lounge.w, h: L.lounge.h,
                     sessionIds: lp ? lp.sessionIds : [], lounge: true };
    return { rooms: out, lounge, w: lx + L.lounge.w, h: L.room.h };
  }

  // 구역 자리 — theme.json의 seats([x, y, 방향?] 목록) · stand(한 점). 자리보다 사람이 많으면 옆으로 조금씩 비켜 선다
  function zoneSeat(room, name, k) {
    const z = L.zones[name];
    if (!z) return null;
    if (z.seats && z.seats.length) {
      const s = z.seats[k % z.seats.length], extra = Math.floor(k / z.seats.length);
      return [room.x + s[0] + extra * 0.45, room.y + s[1] + extra * 0.2, s[2] || z.face];
    }
    if (z.stand) return [room.x + z.stand[0], room.y + z.stand[1], z.face];
    return null;
  }
  function seat(room, k) {
    if (room.lounge) {
      const z = L.zones.lounge_seats;
      return [room.x + z.x + (k % z.cols) * z.dx, room.y + z.y + Math.floor(k / z.cols) * z.dy + 1, 'down'];
    }
    const z = L.zones.desks;
    if (z.seats) return zoneSeat(room, 'desks', k);
    return [room.x + z.x + (k % z.cols) * z.dx + 1, room.y + z.y + Math.floor(k / z.cols) * z.dy + 2];
  }
  function seatCount(room) {
    const z = room.lounge ? L.zones.lounge_seats : L.zones.desks;
    return z.seats ? z.seats.length : z.cols * z.rows;
  }
  function spot(room, go, deskXY, k) {
    if (room.lounge || go === 'desk') return deskXY;
    return zoneSeat(room, go, k) || deskXY;
  }

  function rebuild(st) {
    world = rooms(st);
    const pending = new Map();
    for (const a of st.approvals.values()) if (a.status === 'pending' && a.session_id != null) pending.set(a.session_id, (pending.get(a.session_id) || 0) + 1);
    const seen = new Set();
    for (const room of [...world.rooms, world.lounge]) {
      // 세션 — 깨어 있는 것 먼저 자리를 준다. 자리가 모자라면 배지에 "+N"
      const ss = room.sessionIds.map((id) => st.sessions.get(id)).filter(Boolean);
      ss.sort((a, b) => (a.state === 'DORMANT') - (b.state === 'DORMANT') || a.id - b.id);
      const cap = seatCount(room);
      room.overflow = Math.max(0, ss.length - cap);
      room.stats = { ACTIVE: 0, IDLE: 0, SUSPENDED: 0, DORMANT: 0, pending: 0, subs: 0, tin: 0, tout: 0 };
      ss.forEach((s, k) => {
        room.stats[s.state] = (room.stats[s.state] || 0) + 1;
        room.stats.pending += pending.get(s.id) || 0;
        room.stats.subs += s.subagents_running || 0;
        room.stats.tin += (s.tokens && s.tokens.today_input) || 0;
        room.stats.tout += (s.tokens && s.tokens.today_output) || 0;
        if (k >= cap) return;
        let act = resolveAction(theme, { state: s.state, tool: s.activity && s.activity.tool, target: s.activity && s.activity.target,
                                         flags: { approval_pending: pending.has(s.id), stuck_turn: !!s.stuck_turn } });
        // 쉬는 모습은 사람마다 다르게(마법학교: 엎드려 자기 · 먹기 · 책) — 플래그가 덮은 동작은 그대로
        if (act.variants && !act.flag) act = { ...act, anim: act.variants[s.id % act.variants.length] };
        const desk = seat(room, k);
        const [tx, ty, face] = spot(room, act.go, desk, k);
        const key = 's:' + s.id;
        upsert(key, { kind: 'session', room: room.name, tx, ty, face, act, desk, s, hue: hueOf(s.id),
                      char: CH.pool ? CH.pool[s.id % CH.pool.length] : null,
                      name: s.title || s.cc_name || ('세션 ' + s.id) });
        seen.add(key);
      });
      if (!room.lounge) {
        // 포먼 캐릭터 — 자기 세션이 아직 없다(README 2.4 임시 상태). 구석 사무실에 서 있다
        const f = L.zones.foreman_office;
        const key = 'f:' + room.name;
        upsert(key, { kind: 'foreman', room: room.name, tx: room.x + f.seat[0], ty: room.y + f.seat[1], face: 'down',
                      act: { anim: 'stand' }, hue: 45, name: '포먼', char: CH.foreman || null });
        seen.add(key);
        // 인프라 — 자리(가구)는 늘 있고, 캐릭터는 첫 웹훅으로 등장한 것만(README 2.2 · 8단계)
        const pp = st.pipeline.get(room.name);
        room.pipe = pp || null;
        const chain = pp && pp.chains && pp.chains[0];
        const stages = (chain && chain.stages) || {};
        const present = new Set(((pp && pp.infra) || []).filter((c) => !c.retired).map((c) => c.kind));
        for (const kind of ['jenkins', 'harbor', 'argocd']) {
          let status = stages[kind] && stages[kind].status;
          if (kind === 'harbor' && !status && stages.jenkins) status = stages.jenkins.status === 'failed' && stages.jenkins.step !== '빌드·push' ? 'success' : stages.jenkins.status;
          room['st_' + kind] = status || 'none';
          if (!present.has(kind) && !(kind === 'harbor' && present.has('jenkins'))) continue;
          const z = L.zones.infra;
          const key = `i:${room.name}:${kind}`;
          upsert(key, { kind: 'infra', infra: kind, room: room.name, tx: room.x + z[kind].x + 3, ty: room.y + z.y + 2, face: 'down',
                        char: (CH.infra && CH.infra[kind]) || null,
                        act: infraAction(theme, status), hue: { jenkins: 0, harbor: 200, argocd: 25 }[kind],
                        name: { jenkins: 'Jenkins', harbor: 'Harbor', argocd: 'ArgoCD' }[kind] });
          seen.add(key);
        }
      }
    }
    for (const k of [...actors.keys()]) if (!seen.has(k)) actors.delete(k);
    if (selected && !actors.has(selected)) selected = null;
    // 토큰 이력 — 스냅샷이 새로 올 때마다 방별 누적(오늘)을 적는다
    if (st.generatedAt && st.generatedAt !== lastSnap) {
      lastSnap = st.generatedAt;
      const now = Date.now();
      for (const room of [...world.rooms, world.lounge]) {
        const k = room.name || '_lounge';
        const h = tokHist.get(k) || [];
        h.push({ t: now, v: room.stats.tin + room.stats.tout, o: room.stats.tout });
        while (h.length && now - h[0].t > RATE_WIN * 1.5) h.shift();
        tokHist.set(k, h);
      }
    }
    for (const room of [...world.rooms, world.lounge]) {
      const h = tokHist.get(room.name || '_lounge') || [];
      room.rate = tokenRate(h, Date.now(), RATE_WIN);
      room.rateOut = tokenRate(h.map((x) => ({ t: x.t, v: x.o })), Date.now(), RATE_WIN);
      room.rateSpan = h.length > 1 ? h[h.length - 1].t - h[0].t : 0;     // 화면을 연 지 얼마 안 되면 아직 잴 수 없다
    }
    if (view !== 'map' && !world.rooms.concat(world.lounge).some((r) => (r.name || '_lounge') === view)) view = 'map';
    aim();
    header(st);
    info(st);
  }

  function upsert(key, a) {
    const cur = actors.get(key);
    if (cur) { Object.assign(cur, a); return; }
    actors.set(key, { ...a, key, x: a.tx, y: a.ty, phase: Math.random() * 6 });
  }

  // ── 카메라 ──────────────────────────────────────────
  function roomByView() { return [...world.rooms, world.lounge].find((r) => (r.name || '_lounge') === view); }
  function aim() {
    const r = view === 'map' ? { x: -1, y: -3, w: world.w + 2, h: world.h + 4 } : (() => { const q = roomByView(); return { x: q.x - 0.5, y: q.y - 2.5, w: q.w + 1, h: q.h + 3 }; })();
    const s = Math.min(W / (r.w * T), H / (r.h * T)) * 0.96;
    camT.s = s; camT.x = (r.x + r.w / 2) * T; camT.y = (r.y + r.h / 2) * T;
  }
  function toWorld(px, py) { return [(px - W / 2) / cam.s + cam.x, (py - H / 2) / cam.s + cam.y]; }
  function toScreen(wx, wy) { return [(wx - cam.x) * cam.s + W / 2, (wy - cam.y) * cam.s + H / 2]; }

  function resize() {
    const r = $('oStage').getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    W = r.width; H = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    aim();
    if (!cam.init) { Object.assign(cam, camT); cam.init = true; }
  }

  // ── 그리기 ──────────────────────────────────────────
  function frame(now) {
    if (!running) return;
    // rAF 시각은 그 프레임의 시작이라 앞서 잰 performance.now()보다 이를 수 있다 — 음수 dt면 제자리(d = 0)에서 0/0 = NaN이 됐다
    const dt = Math.max(0, Math.min(0.1, (now - last) / 1000));
    last = now;
    const k = Math.min(1, dt * 6);
    cam.x += (camT.x - cam.x) * k; cam.y += (camT.y - cam.y) * k; cam.s += (camT.s - cam.s) * k;
    for (const a of actors.values()) {
      const dx = a.tx - a.x, dy = a.ty - a.y, d = Math.hypot(dx, dy);
      const step = SPEED * dt;
      a.moving = d > 0.05;
      if (a.moving) a.dir = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
      if (d <= step) { a.x = a.tx; a.y = a.ty; } else { a.x += dx / d * step; a.y += dy / d * step; }
      a.phase += dt * (a.moving ? 10 : 4);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#15171c';
    ctx.fillRect(0, 0, W, H);
    ctx.setTransform(cam.s * dpr, 0, 0, cam.s * dpr, (W / 2 - cam.x * cam.s) * dpr, (H / 2 - cam.y * cam.s) * dpr);
    ctx.imageSmoothingEnabled = false;
    const list = [...actors.values()].sort((a, b) => a.y - b.y);
    if (SP) {
      // 시트 테마 — 바닥 · 벽은 먼저, 가구와 사람은 발밑(아래 끝) 순서로 함께 그린다: 탁자 뒤에 앉은 사람은 다리가 가려진다(앉기 흉내)
      const sorted = [];
      for (const r of world.rooms) drawRoomS(r, now, sorted);
      if (world.lounge) drawLoungeS(world.lounge, now, sorted);
      for (const a of list) sorted.push({ y: a.y, draw: () => drawActorS(a, now) });
      sorted.sort((p, q) => p.y - q.y);
      for (const it of sorted) it.draw();
      for (const a of list) drawOverlay(a, now);
    } else {
      for (const r of world.rooms) drawRoom(r, now);
      if (world.lounge) drawLounge(world.lounge);
      for (const a of list) drawActor(a, now);
    }
    // 글자는 화면 좌표로(선명하게)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const zoomedIn = view !== 'map';
    for (const r of [...world.rooms, world.lounge]) drawBadge(r, zoomedIn);
    if (zoomedIn) for (const a of list) if (a.room === (view === '_lounge' ? null : view)) drawName(a);
    requestAnimationFrame(frame);
  }

  function rect(x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(x * T, y * T, w * T, h * T); }

  function drawRoom(r, now) {
    const z = L.zones;
    for (let i = 0; i < r.w; i++) for (let j = 0; j < r.h; j++) rect(r.x + i, r.y + j, 1, 1, (i + j) % 2 ? P.floor : P.floorAlt);
    // 벽
    ctx.strokeStyle = P.wallTop; ctx.lineWidth = 3;
    ctx.strokeRect(r.x * T, r.y * T, r.w * T, r.h * T);
    // 포먼 사무실(구석, 유리벽)
    const f = z.foreman_office;
    rect(r.x + f.x, r.y + f.y, f.w, f.h, P.office);
    ctx.strokeStyle = P.officeGlass; ctx.lineWidth = 2;
    ctx.strokeRect((r.x + f.x) * T, (r.y + f.y) * T, f.w * T, f.h * T);
    rect(r.x + f.x + 1, r.y + f.y + 1, 3, 1, P.deskTop);
    // 책상
    const d = z.desks;
    for (let k = 0; k < d.cols * d.rows; k++) {
      const sx = r.x + d.x + (k % d.cols) * d.dx, sy = r.y + d.y + Math.floor(k / d.cols) * d.dy;
      rect(sx, sy, 2, 1, P.deskTop); rect(sx, sy + 1, 2, 0.25, P.desk);
      rect(sx + 0.6, sy - 0.1, 0.8, 0.5, '#1b1f27');      // 모니터
    }
    // 서버랙 · 창 · 전화
    const s = z.server_rack;
    rect(r.x + s.x, r.y + s.y, s.w, s.h, P.rack);
    for (let i = 0; i < 6; i++) if (Math.sin(now / 300 + i * 1.7) > 0) rect(r.x + s.x + 0.4 + (i % 3) * 0.8, r.y + s.y + 0.5 + Math.floor(i / 3) * 1.2, 0.3, 0.2, P.rackLed);
    const w = z.window;
    rect(r.x + w.x, r.y + w.y, w.w, w.h, P.window);
    rect(r.x + z.phone.x, r.y + z.phone.y, 1, 1, '#c9a227');
    // 파이프라인 구역
    const iz = z.infra;
    rect(r.x + 1, r.y + iz.y, r.w - 2, iz.h, P.infraFloor);
    for (const kind of ['jenkins', 'harbor', 'argocd']) {
      const st = r['st_' + kind] || 'none';
      const c = { running: P.act, success: P.ok, failed: P.bad, waiting: P.warn, none: P.muted }[st] || P.muted;
      rect(r.x + iz[kind].x, r.y + iz.y + 0.5, 4, 2, '#1f252c');
      ctx.strokeStyle = c; ctx.lineWidth = 2;
      ctx.strokeRect((r.x + iz[kind].x) * T, (r.y + iz.y + 0.5) * T, 4 * T, 2 * T);
      if (kind !== 'argocd') { ctx.fillStyle = P.muted; ctx.fillRect((r.x + iz[kind].x + 4.3) * T, (r.y + iz.y + 1.4) * T, 4.4 * T, 2); }
      if (st === 'waiting') drawSign(r.x + iz[kind].x + 2, r.y + iz.y + 0.1, '⏸');
      if (st === 'failed') drawSmoke(r.x + iz[kind].x + 2, r.y + iz.y + 0.4, now);
    }
  }

  function drawLounge(r) {
    for (let i = 0; i < r.w; i++) for (let j = 0; j < r.h; j++) rect(r.x + i, r.y + j, 1, 1, (i + j) % 2 ? P.lounge : '#332d34');
    ctx.strokeStyle = '#6b5f6e'; ctx.lineWidth = 3; ctx.setLineDash([6, 4]);
    ctx.strokeRect(r.x * T, r.y * T, r.w * T, r.h * T); ctx.setLineDash([]);
    const z = L.zones.lounge_seats;
    for (let k = 0; k < z.cols * z.rows; k++) rect(r.x + z.x + (k % z.cols) * z.dx - 0.5, r.y + z.y + Math.floor(k / z.cols) * z.dy + 1.5, 2, 0.6, '#5a4a5e');
  }

  function drawActor(a, now) {
    const sp = theme.sprites.person, act = a.act || {};
    const x = a.x * T, yBase = a.y * T;
    const anim = a.moving ? 'walk' : (act.anim || 'stand');
    const sit = !a.moving && (anim === 'sit' || anim === 'type' || anim === 'read' || anim === 'think' || anim === 'call');
    const bob = anim === 'walk' ? Math.abs(Math.sin(a.phase)) * 2 : (anim === 'work' ? Math.abs(Math.sin(a.phase)) : 0);
    const h = sit ? sp.h - 4 : sp.h;
    const y = yBase - h - bob;
    ctx.globalAlpha = act.alpha != null ? act.alpha : 1;
    const body = act.fx === 'frozen' ? P.frozen : `hsl(${a.hue} 55% ${a.kind === 'foreman' ? 45 : 55}%)`;
    // 몸 · 머리
    ctx.fillStyle = body; ctx.fillRect(x - sp.w / 2, y + sp.head * 1.6, sp.w, h - sp.head * 1.6);
    ctx.fillStyle = act.fx === 'frozen' ? '#dff3ff' : '#f1c9a5';
    ctx.beginPath(); ctx.arc(x, y + sp.head, sp.head, 0, Math.PI * 2); ctx.fill();
    if (a.kind === 'foreman') { ctx.fillStyle = '#f2c14e'; ctx.fillRect(x - 5, y - 1, 10, 2); }       // 포먼 표시(모자 띠)
    if (a.kind === 'infra') { ctx.fillStyle = '#ff9f1c'; ctx.fillRect(x - 6, y - 1, 12, 3); }           // 안전모
    // 손 · 소품
    ctx.fillStyle = body;
    if (anim === 'type' && !a.moving) { const j = Math.sin(a.phase * 3) > 0 ? 1 : 0; ctx.fillRect(x - 6, y + 9 + j, 3, 2); ctx.fillRect(x + 3, y + 9 + (1 - j), 3, 2); }
    if (anim === 'read' && !a.moving) { ctx.fillStyle = '#e8e0c8'; ctx.fillRect(x - 5, y + 8, 10, 4); }
    if (anim === 'raise_hand') { ctx.fillRect(x + 4, y - 4, 2, 9); }
    if (anim === 'talk' || anim === 'call') { ctx.fillStyle = '#c9a227'; ctx.fillRect(x + 4, y + 2, 3, 5); }
    if (act.fx === 'frozen') { ctx.strokeStyle = '#bfe8ff'; ctx.lineWidth = 1; ctx.strokeRect(x - sp.w / 2 - 2, y - 2, sp.w + 4, h + 4); }
    ctx.globalAlpha = 1;
    if (act.fx === 'smoke') drawSmoke(a.x, a.y - 1.4, now);
    if (act.bubble) drawBubble(x, y - 6, act.bubble, act.flag === 'approval_pending' ? P.warn : '#e8e8f0');
    if (a.kind === 'session' && a.s && a.s.subagents_running) drawBubble(x + 10, y + 2, `+${a.s.subagents_running}`, P.act, 7);   // 10c에 축소판 일꾼으로
    if (a.key === selected) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - 9, y - 3, 18, h + 6); }
  }

  // ── 시트 테마 그리기(10d) ────────────────────────────
  const RS = (SP && theme.sprites.room) || {};
  function tileHash(i, j) { return ((i * 73856093) ^ (j * 19349663)) >>> 0; }

  function spriteBottom(name, y) { const [, h] = SP.size(name); return y + h / T; }

  // 장식 하나 — z: wall · floor는 바로, top(탁자 위)은 탁자 바로 뒤, 그 밖은 발밑 순서로
  function placeDecor(d, ox, oy, now, sorted) {
    const n = d.n || 1;
    for (let i = 0; i < n; i++) {
      const x = ox + d.x + i * (d.dx || 1), y = oy + d.y;
      if (d.fx) { sorted.push({ y: y + 0.1, draw: () => drawFx(d.fx, x, y, now) }); continue; }
      const scale = d.scale || 1;
      const draw = () => {
        if (d.alpha != null) ctx.globalAlpha = d.alpha * (d.pulse ? 0.65 + 0.35 * Math.sin(now / 700) : 1);
        SP.draw(ctx, d.s, x * T, y * T, now, scale, d.frame != null ? d.frame : null);
        ctx.globalAlpha = 1;
      };
      if (d.z === 'wall' || d.z === 'floor') draw();
      else if (d.z === 'top') sorted.push({ y: y + 3, draw });               // 탁자 · 선반 위 — 받침보다 뒤에
      else sorted.push({ y: spriteBottom(d.s, y) * 1 - 0.01, draw });
    }
  }

  function drawRoomS(r, now, sorted) {
    const z = L.zones, fl = RS.floor || ['floor_1'];
    for (let i = 1; i < r.w - 1; i++) for (let j = 2; j < r.h - 1; j++) SP.draw(ctx, fl[tileHash(i, j) % fl.length], (r.x + i) * T, (r.y + j) * T);
    for (const zz of Object.values(z)) {
      if (!zz || !zz.floor) continue;
      for (let i = 0; i < zz.w; i++) for (let j = 0; j < zz.h; j++) SP.draw(ctx, zz.floor, (r.x + zz.x + i) * T, (r.y + zz.y + j) * T);
    }
    // 출하 라인 바닥은 조금 어둡게
    const iz = z.infra;
    ctx.fillStyle = P.infraFloor; ctx.fillRect((r.x + 1) * T, (r.y + iz.y) * T, (r.w - 2) * T, iz.h * T);
    drawWalls(r);
    const b = RS.banners;
    if (b) for (let i = b.from, k = 0; i < r.w - 1; i += b.every, k++) SP.draw(ctx, b.s[(k + r.x) % b.s.length], (r.x + i) * T, (r.y + 1) * T);
    for (const d of theme.sprites.decor || []) if (d.s || d.fx) placeDecor(d, r.x, r.y, now, sorted);
    // 출하 라인 — 구역마다 가구 + 상태 테두리(실패 연기 · Sync 대기 표지)
    for (const kind of ['jenkins', 'harbor', 'argocd']) {
      const ox = r.x + iz[kind].x, oy = r.y + iz.y;
      for (const d of (theme.sprites.infra_decor || {})[kind] || []) placeDecor(d, ox, oy, now, sorted);
      const st = r['st_' + kind] || 'none';
      const c = { running: P.act, success: P.ok, failed: P.bad, waiting: P.warn, none: P.muted }[st] || P.muted;
      ctx.strokeStyle = c; ctx.globalAlpha = st === 'none' ? 0.35 : 0.9; ctx.lineWidth = 1;
      ctx.strokeRect(ox * T + 0.5, (oy + 0.2) * T + 0.5, 4.5 * T, 2.6 * T);
      ctx.globalAlpha = 1;
      if (st === 'waiting') sorted.push({ y: oy + 3, draw: () => drawSign(ox + 2.2, oy + 0.2, '⏸') });
      if (st === 'failed') sorted.push({ y: oy + 3, draw: () => drawSmokeS(ox + 2, oy + 1.2, now) });
    }
  }

  // 벽 — 위 두 줄은 시트(머리 · 면), 옆 · 아래 테두리는 어두운 두께(위에서 내려다본 벽 윗면)
  function drawWalls(r) {
    for (let i = 0; i < r.w; i++) {
      SP.draw(ctx, RS.wall_top, (r.x + i) * T, r.y * T);
      SP.draw(ctx, RS.wall, (r.x + i) * T, (r.y + 1) * T);
    }
    ctx.fillStyle = P.wallCap || '#1c1820';
    ctx.fillRect(r.x * T, (r.y + 1) * T, T * 0.6, (r.h - 1) * T);
    ctx.fillRect((r.x + r.w - 0.6) * T, (r.y + 1) * T, T * 0.6, (r.h - 1) * T);
    ctx.fillRect(r.x * T, (r.y + r.h - 0.6) * T, r.w * T, T * 0.6);
    ctx.fillStyle = P.wallEdge || '#4a4150';
    ctx.fillRect((r.x + 0.6) * T, (r.y + 2) * T, 1, (r.h - 2.6) * T);
    ctx.fillRect((r.x + r.w - 0.6) * T - 1, (r.y + 2) * T, 1, (r.h - 2.6) * T);
    ctx.fillRect((r.x + 0.6) * T, (r.y + r.h - 0.6) * T - 1, (r.w - 1.2) * T, 1);
  }

  function drawLoungeS(r, now, sorted) {
    const fl = RS.floor || ['floor_1'];
    for (let i = 1; i < r.w - 1; i++) for (let j = 2; j < r.h - 1; j++) SP.draw(ctx, fl[tileHash(i + 7, j) % fl.length], (r.x + i) * T, (r.y + j) * T);
    ctx.fillStyle = P.lounge + '88'; ctx.fillRect((r.x + 1) * T, (r.y + 2) * T, (r.w - 2) * T, (r.h - 3) * T);
    drawWalls(r);
    const z = L.zones.lounge_seats;
    for (let k = 0; k < z.cols * z.rows; k++) {
      const sx = r.x + z.x + (k % z.cols) * z.dx, sy = r.y + z.y + Math.floor(k / z.cols) * z.dy + 1;
      sorted.push({ y: sy + 0.6, draw: () => SP.draw(ctx, 'stool', (sx - 0.5) * T, (sy - 0.4) * T) });
    }
  }

  // 엔진이 그리는 빛 — 수정구 · 스테인드글라스 · 촛불(에셋에 없는 것)
  function drawFx(kind, x, y, now) {
    const t = now / 1000;
    if (kind === 'orb') {
      const p = 0.6 + 0.4 * Math.sin(t * 2.2);
      glow(x * T, y * T, 10 + p * 4, P.orb, 0.35 * p);
      ctx.fillStyle = '#d8f6ff'; ctx.beginPath(); ctx.arc(x * T, y * T, 3, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = P.orb; ctx.beginPath(); ctx.arc(x * T - 1, y * T - 1, 1.2, 0, Math.PI * 2); ctx.fill();
    } else if (kind === 'glass') {
      const cols = [P.glass1, P.glass2, P.glass3];
      for (let i = 0; i < 3; i++) {
        ctx.globalAlpha = 0.16 + 0.06 * Math.sin(t + i);
        ctx.fillStyle = cols[i]; ctx.fillRect((x - 0.6 + i * 0.4) * T, y * T, 0.4 * T, 1.4 * T);
      }
      ctx.globalAlpha = 1;
    } else if (kind === 'candle') {
      const f = Math.sin(t * 9 + x * 3) > 0 ? 1 : 0;
      glow(x * T, (y - 0.15) * T, 9, P.candle, 0.28);
      ctx.fillStyle = '#efe6cf'; ctx.fillRect(Math.round(x * T) - 1, Math.round(y * T) - 2, 2, 4);
      ctx.fillStyle = P.candle; ctx.fillRect(Math.round(x * T) - 1, Math.round(y * T) - 4 - f, 2, 2);
    }
  }
  function glow(px, py, rad, color, alpha) {
    const g = ctx.createRadialGradient(px, py, 0, px, py, rad);
    g.addColorStop(0, color); g.addColorStop(1, color + '00');
    ctx.globalAlpha = alpha; ctx.fillStyle = g; ctx.fillRect(px - rad, py - rad, rad * 2, rad * 2); ctx.globalAlpha = 1;
  }
  function drawSmokeS(tx, ty, now) {
    if (SP.has('fx_smoke')) SP.draw(ctx, 'fx_smoke', tx * T - 16, ty * T - 30, now);
    else drawSmoke(tx, ty, now);
  }

  // 사람 — Ninja 시트. 걷기는 진짜 프레임, 앉기는 탁자가 가리고, 자기 · 들기 · 석화 · 유령은 엔진 흉내
  function drawActorS(a, now) {
    const act = a.act || {};
    const anim = a.moving ? 'walk' : (act.anim || 'stand');
    const dir = a.moving ? (a.dir || 'down') : (a.face || 'down');
    const mode = act.fx === 'stone' || act.fx === 'frozen' ? 'stone' : act.fx === 'ghost' ? 'ghost' : null;
    const walking = a.moving || anim === 'work';
    const f = walking && !mode ? Math.floor(a.phase * 0.8) % 4 : 0;
    const c = SP.charFrame(a.char, walking ? 'walk' : 'idle', dir, f, mode);
    if (!c) return;
    let px = Math.round(a.x * T - 8), py = Math.round(a.y * T - 16);
    if (anim === 'sleep') py += 4;                                               // 엎드려 잔다 — 머리를 탁자 위로
    if (mode === 'ghost') py += Math.round(Math.sin(a.phase * 0.6) * 1.5) - 2;  // 유령은 떠 있다
    ctx.globalAlpha = act.alpha != null ? act.alpha : 1;
    ctx.drawImage(c, px, py);
    // 손에 든 것
    const prop = !a.moving && !mode && (theme.sprites.props || {})[anim];
    if (prop) {
      const bob = prop.bob ? Math.round(Math.abs(Math.sin(a.phase * 1.5)) * prop.bob) : 0;
      const sh = prop.shake ? Math.round(Math.sin(a.phase * 6) * prop.shake) : 0;
      const [pw, ph] = SP.size(prop.s);
      SP.draw(ctx, prop.s, a.x * T + prop.dx - pw / 2 + sh, a.y * T + prop.dy - ph / 2 - bob, now);
      if (prop.fx) SP.draw(ctx, prop.fx, a.x * T + prop.dx - 15, a.y * T + prop.dy - 26, now);
    }
    ctx.globalAlpha = 1;
  }

  // 사람 위에 뜨는 것 — 말풍선(이모트) · 연기 · 자는 Zz · 일꾼 수 · 선택 표시(가구에 가리지 않게 마지막에)
  function drawOverlay(a, now) {
    const act = a.act || {};
    const x = a.x * T, top = a.y * T - 16;
    if (act.fx === 'smoke') drawSmokeS(a.x, a.y - 0.6, now);
    if (act.bubble) {
      const e = 'e_' + act.bubble;
      if (SP.has(e)) SP.draw(ctx, e, x - 7, top - 13 - Math.round(Math.abs(Math.sin(now / 300)) * 2), now);
      else drawBubble(x, top - 4, act.bubble, P.warn);
    }
    if (!a.moving && act.anim === 'sleep' && !act.flag) {
      const t = (now / 1400 + (a.phase % 1)) % 1;
      ctx.globalAlpha = 1 - t; ctx.fillStyle = P.zz; ctx.font = 'bold 7px ui-monospace, monospace'; ctx.textAlign = 'left';
      ctx.fillText('z', x + 5 + t * 4, top + 2 - t * 8); ctx.globalAlpha = 1;
    }
    if (a.kind === 'session' && a.s && a.s.subagents_running) drawBubble(x + 10, top + 4, `+${a.s.subagents_running}`, P.act, 7);   // 10c에 작은 로브로
    if (a.key === selected) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - 9, top - 2, 18, 20); }
  }

  function drawBubble(x, y, text, color, size = 9) {
    ctx.font = `bold ${size}px ui-monospace, monospace`;
    const w = Math.max(10, ctx.measureText(text).width + 6);
    ctx.fillStyle = color; ctx.fillRect(x - w / 2, y - size - 2, w, size + 4);
    ctx.fillStyle = '#111'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y - size / 2);
  }
  function drawSign(tx, ty, ch) { drawBubble(tx * T, ty * T, ch, P.warn, 10); }
  function drawSmoke(tx, ty, now) {
    for (let i = 0; i < 3; i++) {
      const t = ((now / 900) + i / 3) % 1;
      ctx.globalAlpha = 0.6 * (1 - t);
      ctx.fillStyle = '#8a8f99';
      ctx.beginPath(); ctx.arc(tx * T + Math.sin(t * 6 + i) * 3, ty * T - t * 18, 3 + t * 5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawName(a) {
    const [sx, sy] = toScreen(a.x * T, a.y * T);
    const text = a.kind === 'session' ? short(a.name, 18) : a.name;
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const w = ctx.measureText(text).width + 6;
    ctx.fillStyle = '#000a'; ctx.fillRect(sx - w / 2, sy + 2, w, 14);
    ctx.fillStyle = a.kind === 'foreman' ? P.warn : P.label;
    ctx.fillText(text, sx, sy + 3);
  }

  function fmt(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(n); }

  function drawBadge(r, zoomedIn) {
    if (zoomedIn && (r.name || '_lounge') !== view) { r.badge = null; return; }   // 안 그린 배지는 클릭도 안 받는다
    const st = r.stats || {};
    const [sx, sy] = toScreen(r.x * T, r.y * T);
    const [ex] = toScreen((r.x + r.w) * T, 0);
    const lines = [];
    lines.push([`${r.label}`, P.label, 'bold 13px']);
    lines.push([`작업 ${st.ACTIVE || 0} · 쉼 ${st.IDLE || 0}${st.SUSPENDED ? ' · 멈춤 ' + st.SUSPENDED : ''}${st.subs ? ' · 일꾼 ' + st.subs : ''}${r.overflow ? ' · 자리 밖 +' + r.overflow : ''}`, P.muted, '11px']);
    if (st.pending) lines.push([`❗ 승인 대기 ${st.pending}`, P.warn, 'bold 12px']);
    const pp = r.pipe;
    const broke = pp && pp.chains && pp.chains[0] && pp.chains[0].broke;
    if (broke) lines.push([`🔥 파이프라인 실패 · ${broke}`, P.bad, 'bold 11px']);
    else if (r.st_argocd === 'waiting') lines.push(['⏸ Sync 대기', P.warn, '11px']);
    if (pp && pp.webhook_broken) lines.push(['⚠ 웹훅 끊김 의심', P.bad, '11px']);
    if (pp && pp.watch && pp.watch.state !== 'ok') lines.push([`⚠ 빌드 알림 ${pp.watch.state === 'missing' ? '없음' : '늦음'}`, pp.watch.state === 'missing' ? P.bad : P.warn, '11px']);
    // 토큰 — 지금 어느 방이 쓰고 있나(사용자 요청 11-03). 오늘 누적 + 최근 10분 증가
    const hot = r.rate > 2e6 ? P.bad : r.rate > 3e5 ? P.warn : r.rate > 0 ? P.act : P.muted;
    lines.push([`토큰 오늘 출력 ${fmt(st.tout || 0)} · 입력 ${fmt(st.tin || 0)}`, P.muted, '11px']);
    const span = Math.round((r.rateSpan || 0) / 60000);
    lines.push([r.rate ? `최근 ${Math.max(1, Math.min(10, span))}분 +${fmt(r.rate)} (출력 +${fmt(r.rateOut)})`
      : (r.rateSpan || 0) < 60000 ? '최근 사용량 재는 중…(화면을 연 뒤부터)' : `최근 ${Math.min(10, span)}분 사용 없음`,
      hot, r.rate ? 'bold 11px' : '11px']);
    const w = Math.max(160, Math.min(ex - sx, 300));
    const h = lines.length * 15 + 8;
    const bx = sx, by = Math.max(4, sy - h - 6);
    ctx.fillStyle = '#0d0f14e6'; ctx.fillRect(bx, by, w, h);
    ctx.strokeStyle = st.pending || broke ? P.warn : hot; ctx.lineWidth = r.rate > 3e5 || st.pending ? 2 : 1;
    ctx.strokeRect(bx + 0.5, by + 0.5, w - 1, h - 1);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    lines.forEach(([t, c, f], i) => { ctx.font = `${f} system-ui, sans-serif`; ctx.fillStyle = c; ctx.fillText(short(t, 44), bx + 6, by + 5 + i * 15); });
    r.badge = { x: bx, y: by, w, h };
  }

  // ── 머리말 · 정보 패널 ──────────────────────────────
  function header(st) {
    const c = st.conn;
    $('oConn').className = 'conn ' + c.status;
    $('oConn').textContent = { up: '연결됨', down: '끊김', connecting: '연결 중', auth: '토큰 필요', idle: '연결 전' }[c.status] || c.status;
    const pend = [...st.approvals.values()].filter((a) => a.status === 'pending').length;
    const ig = st.ingest;
    $('oAlerts').innerHTML = (pend ? `<a class="warn" href="/" title="승인은 클래식 화면에서(10b에 이 화면으로)">❗ 승인 대기 ${pend}</a>` : '') +
      (ig && !ig.ok ? ` <span class="bad">⚠ 적재 막힘</span>` : '');
    $('oMap').disabled = view === 'map';
  }

  function info(st) {
    const box = $('oInfo');
    const a = selected && actors.get(selected);
    if (!a) { box.hidden = true; return; }
    box.hidden = false;
    if (a.kind !== 'session') {
      const status = a.kind === 'infra' ? (a.act && a.act.status) : '세션 없음(11단계에 캐릭터 재배치)';
      box.innerHTML = `<b>${esc(a.name)}</b><div class="muted small">${esc(a.room || '')} · ${esc(String(status))}</div>`;
      return;
    }
    const s = a.s, t = s.tokens || {};
    const g = groupSubagents(s.subagent_descs || []);
    box.innerHTML = `
      <div><b>${esc(a.name)}</b> <span class="badge st-${s.state}">${s.state}</span></div>
      <div class="small muted">${esc(s.cc_name || '')} · ${esc((s.cwd || '').replace(/^\/home\/[^/]+/, '~'))}</div>
      <div class="small">지금: ${s.activity && s.state === 'ACTIVE' ? esc(s.activity.tool) + ' ' + esc(short(s.activity.target || '', 80)) : esc(s.state)}</div>
      <div class="small">동작: ${esc(a.act.anim || '')} @ ${esc(a.act.go || '')} <span class="muted">(${esc(a.act.source || '')}${a.act.flag ? ' · ' + esc(a.act.flag) : ''})</span></div>
      ${s.open_turn ? `<div class="small">턴: ${esc(short(s.open_turn.prompt || '', 90))}</div>` : ''}
      ${s.subagents_running ? `<div class="small">서브에이전트 ${s.subagents_running}${g.label ? ' — ' + esc(g.label) : ''}</div>` : ''}
      <div class="small">토큰 오늘 출력 ${fmt(t.today_output || 0)} · 입력 ${fmt(t.today_input || 0)}</div>
      <div class="small"><a href="/">대화 · 입력은 클래식 화면에서</a> <span class="muted">(10b에 이 화면으로)</span></div>`;
  }

  // ── 입력 ───────────────────────────────────────────
  cv.addEventListener('click', (ev) => {
    const r = cv.getBoundingClientRect();
    const px = ev.clientX - r.left, py = ev.clientY - r.top;
    for (const room of [...world.rooms, world.lounge]) {
      const b = room.badge;
      if (b && px >= b.x && px <= b.x + b.w && py >= b.y && py <= b.y + b.h) { go(room.name || '_lounge'); return; }
    }
    const [wx, wy] = toWorld(px, py);
    if (view === 'map') {
      const room = [...world.rooms, world.lounge].find((q) => wx >= q.x * T && wx <= (q.x + q.w) * T && wy >= q.y * T && wy <= (q.y + q.h) * T);
      if (room) go(room.name || '_lounge');
      return;
    }
    let best = null, bd = 1.4 * T;
    for (const [k, a] of actors) {
      const d = Math.hypot(a.x * T - wx, a.y * T - 8 - wy);
      if (d < bd) { bd = d; best = k; }
    }
    selected = best;
    info(store.state);
  });
  function go(v) { view = v; selected = null; aim(); header(store.state); info(store.state); }
  $('oMap').onclick = () => go('map');
  window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') go('map'); });
  $('oTok').onclick = () => {
    const v = prompt('API 토큰(.env.bridge의 FOREMAN_API_TOKEN 값)');
    if (v) { store.token = v; store.start(); }
  };
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    running = !document.hidden;
    if (running) { last = performance.now(); requestAnimationFrame(frame); }
  });

  resize();
  store.subscribe(rebuild);
  requestAnimationFrame(frame);
  return { go, theme, debug: () => [...actors.values()].map((a) => ({ key: a.key, room: a.room, x: String(a.x), y: String(a.y), tx: a.tx, ty: a.ty,
                                                                       anim: a.act && a.act.anim, go: a.act && a.act.go, face: a.face, dir: a.dir, char: a.char })) };
}

function hueOf(id) { return (id * 47) % 360; }
function short(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
