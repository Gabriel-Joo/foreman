// FOREMAN 픽셀 오피스 — 테마 렌더러(10단계). store.js(데이터)는 그대로, 이 파일은 그리기만.
// 10a: 지도 ↔ 방 줌, 도형 캐릭터, 상태별 모습, 방 배지(작업 · 승인 · 파이프라인 · 토큰). 동작은 theme.json이 정한다(theme.js).
// 좌표: 월드는 타일 단위로 정하고 px = 타일 × layout.tile. 카메라가 월드 → 화면.

import { resolveAction, infraAction, groupSubagents, tokenRate } from './theme.js';
import { loadSprites } from './sprites.js';
import { createSidePanel } from './opanel.js';
import { buildGrid, findPath, footprint, RES } from './walk.js';

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
      <span class="brand">FOREMAN</span><span class="muted small">${esc(theme.label)}</span>
      <button id="oMap" class="ghost" title="감독실로(Esc)">${esc((theme.hq && theme.hq.label) || '감독실')}</button>
      <button id="oAll" class="ghost" title="모든 현장을 한눈에">전체</button>
      <span id="oAlerts" class="oalerts"></span>
      <span class="small muted otheme">테마 ${[['office', '오피스'], ['magic', '마법학교'], ['site', '현장'], ['plain', '도형']].map(([k, v]) => k === theme.name ? `<b>${v}</b>` : `<a href="/?theme=${k}">${v}</a>`).join(' · ')}</span>
      <a class="small" href="/classic" title="카드 목록 화면">클래식</a>
      <span id="oConn" class="conn"></span>
      <button id="oTok" class="ghost" title="API 토큰">토큰</button>
    </header>
    <div class="obody">
      <div id="oStage" class="ostage"><canvas id="oCv"></canvas><div id="oTip" class="otip" hidden></div>
        <div id="oDown" class="odown" role="alert" aria-live="assertive" hidden>
          <b>⚠ 서버 연결 끊김</b> <span id="oDownWhy" class="small"></span> <span id="oDownNext" class="small muted"></span>
          <button id="oRetry" class="small">지금 다시 연결</button>
          <div class="small muted">화면의 캐릭터는 끊기기 전 상태다 — 다시 연결되면 맞춘다</div>
        </div>
      </div>
    </div>
    <div id="tokDlg" class="overlay"><form class="box" id="tokForm">
      <h2 class="plain">API 토큰</h2>
      <p class="muted small">.env.bridge의 FOREMAN_API_TOKEN 값. 이 브라우저에만 저장한다(클래식 화면과 같이 쓴다).</p>
      <input id="tokInput" type="password" autocomplete="new-password" placeholder="FOREMAN_API_TOKEN 값">
      <p><button type="submit">연결</button> <button type="button" id="tokCancel" class="ghost">닫기</button> <span id="tokLen" class="small muted"></span></p>
    </form></div>`;
  const $ = (id) => root.querySelector('#' + id);
  const cv = $('oCv'), ctx = cv.getContext('2d');
  // 10b: 옆 패널(승인 · 대화 · 입력). 캔버스를 덮지 않고 옆에 붙는다 — 패널을 펴고 접으면 캔버스 크기가 바뀌고 카메라가 다시 맞춘다
  const panel = createSidePanel(root.querySelector('.obody'), store, { onSelectSession: (sid) => openSession(sid), onClear: () => { selected = null; } });

  // ── 상태 ───────────────────────────────────────────
  let world = { rooms: [], lounge: null, w: 0, h: 0 };
  const actors = new Map();            // key → actor
  const tokHist = new Map();           // 방 이름 → [{t, v, o}]
  let lastSnap = null;
  let view = 'hq';                     // 'hq'(감독실, 1단) | 'map'(전체) | 방 이름(현장, 2단) | '_lounge'
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
    // 감독실(1단) — 현장들 위쪽에 따로 선 방. 벽의 현황판에 현장마다 표시(촛불 · 모니터 · 자석 — 테마가 정한다)
    const hs = (theme.hq && theme.hq.size) || { w: 28, h: 16 };
    const hq = { name: '_hq', label: (theme.hq && theme.hq.label) || '감독실', x: Math.max(0, (lx + L.lounge.w - hs.w) / 2),
                 y: -(hs.h + 8), w: hs.w, h: hs.h, hq: true };
    return { rooms: out, lounge, hq, w: lx + L.lounge.w, h: L.room.h };
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
        const char = CH.pool ? CH.pool[s.id % CH.pool.length] : null;
        upsert(key, { kind: 'session', room: room.name, tx, ty, face, act, desk, s, hue: hueOf(s.id), char, role: roleOf(s),
                      name: s.title || s.cc_name || ('세션 ' + s.id) });
        seen.add(key);
        // 서브에이전트 — 부모의 축소판. 10명까지 보이고 나머지는 +N(10c). 새로 생기면 원탁방 마법진에서 소환, 끝나면 연기
        const n = s.subagents_running || 0;
        const g = groupSubagents(s.subagent_descs || [], MINI_CAP);
        const shown = Math.min(n, MINI_CAP);
        for (let i = 0; i < shown; i++) {
          const mk = `m:${s.id}:${i}`;
          const born = !actors.has(mk);
          const from = born ? summonPoint(room, tx, ty) : null;
          upsert(mk, { kind: 'mini', room: room.name, parent: key, idx: i, of: shown, char, hue: hueOf(s.id), role: roleOf(s),
                       act: { anim: 'walk' }, name: g.shown[i] || g.label || '서브에이전트', tx: from ? from[0] : tx, ty: from ? from[1] : ty });
          if (born) {
            const a = actors.get(mk);
            a.x = from[0]; a.y = from[1]; a.bornAt = performance.now() + i * 180;   // 하나씩 차례로 나온다
            summons.push({ x: from[0], y: from[1], t0: a.bornAt });
          }
          seen.add(mk);
        }
        const self = actors.get(key);
        self.subHidden = Math.max(0, n - shown);
        self.subLabel = g.label;
      });
      if (!room.lounge) {
        // 포먼 캐릭터 — 자기 세션이 아직 없다(README 2.4 임시 상태). 구석 사무실에 서 있다
        const f = L.zones.foreman_office;
        const key = 'f:' + room.name;
        upsert(key, { kind: 'foreman', room: room.name, tx: room.x + f.seat[0], ty: room.y + f.seat[1], face: 'down',
                      act: { anim: 'stand' }, hue: 45, name: '포먼', char: CH.foreman || null, role: 'foreman' });
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
    // 감독실의 포먼(교장) — 늘 자리에 있다
    const hz = (theme.hq && theme.hq.seat) || [14, 8.6];
    upsert('f:_hq', { kind: 'foreman', room: '_hq', tx: world.hq.x + hz[0], ty: world.hq.y + hz[1], face: 'down',
                      act: { anim: 'stand' }, hue: 45, name: '포먼(감독)', char: CH.foreman || null, role: 'foreman' });
    seen.add('f:_hq');
    for (const k of [...actors.keys()]) if (!seen.has(k)) vanish(k);
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
    if (view !== 'map' && view !== 'hq' && !world.rooms.concat(world.lounge).some((r) => (r.name || '_lounge') === view)) view = 'hq';
    aim();
    header(st);
    const sa = selected && actors.get(selected);
    if (sa && sa.kind === 'infra') info();          // 인프라 상태가 바뀌었으면 패널 제목 줄도 바꾼다(세션은 패널이 store를 직접 본다)
    if (store.state.selected == null && sa && (sa.kind === 'session' || sa.kind === 'mini')) selected = null;   // 패널에서 ✕
  }

  // 역할(로브 · 사원증 끈 · 안전모 색) — 11단계에서 포먼이 캐릭터를 만들면 세션에 role이 온다(지금은 없음).
  // 미리 보기: /office?roles=demo — 세션 id로 돌려 가며 붙인다
  const ROLES = (theme.roles && theme.roles.colors) || {};
  const ROLE_MODE = (theme.roles && theme.roles.mode) || 'robe';   // robe(옷 색) · lanyard(사원증 끈) · helmet(안전모)
  const DEMO_ROLES = new URLSearchParams(location.search).get('roles') === 'demo' ? Object.keys(ROLES) : null;
  function roleOf(s) { return s.role || (DEMO_ROLES && DEMO_ROLES.length ? DEMO_ROLES[s.id % DEMO_ROLES.length] : null); }
  // 역할이 없을 때의 색(현장: 노란 안전모), 포먼(감독)의 색 — 테마가 정한다. 없으면 표시 안 함
  function roleColor(role) {
    const R = theme.roles || {};
    if (role === 'foreman') return R.foreman || null;
    return (role && ROLES[role]) || R.default || null;
  }

  // 서브에이전트(10c) — 소환 자리: 그 방에 마법진(circle 구역)이 있으면 그 가운데, 없으면 부모 자리
  const MINI_CAP = 10;
  const MINI = theme.sprites.mini_scale || 0.6;
  const summons = [];
  function summonPoint(room, px, py) {
    const z = L.zones.circle || L.zones[(theme.spawn && theme.spawn.zone) || ''];
    if (!z || room.lounge) return [px, py];
    return [room.x + z.x + z.w / 2, room.y + z.y + z.h / 2];
  }
  // 작은 일꾼은 부모 둘레를 천천히 돈다 — 목표를 매 프레임 다시 정한다
  function miniTarget(a, now) {
    const p = actors.get(a.parent);
    if (!p) return [a.tx, a.ty];
    const ang = (a.idx / Math.max(1, a.of)) * Math.PI * 2 + now / 6000 + (a.idx % 2) * 0.4;
    const rx = 1.1 + 0.25 * (a.idx % 3), ry = 0.55;
    return [p.x + Math.cos(ang) * rx, p.y + 0.35 + Math.sin(ang) * ry];
  }

  // 사라지기 — 서브에이전트(작은 일꾼)는 연기로 흩어진다(10c). 나머지는 그냥 지운다
  const puffs = [];
  function vanish(k) {
    const a = actors.get(k);
    if (a && a.kind === 'mini') puffs.push({ x: a.x, y: a.y, t0: performance.now() });
    actors.delete(k);
  }

  function upsert(key, a) {
    const cur = actors.get(key);
    if (cur) { Object.assign(cur, a); return; }
    actors.set(key, { ...a, key, x: a.tx, y: a.ty, phase: Math.random() * 6 });
  }

  // ── 걷기(11-05) — 가구를 피해 ㅗ자 복도로. 방마다 배치가 같아 격자는 현장 방 하나 · 라운지 하나(방 안 좌표) ──
  const WALK_DEBUG = new URLSearchParams(location.search).get('walk') === '1';
  const CORRIDORS = L.corridors || [];
  function sizeT(d) { const [w, h] = SP.size(d.s); const sc = d.scale || 1; return [w * sc / T, h * sc / T]; }
  function obstacles() {
    const out = [];
    const add = (d, ox, oy) => {
      if (d.fx === 'glasswall') {
        // 유리벽 — 옆 · 아래 테두리만 벽, 아래 가운데에 문(서버룸처럼 안에 자리가 있다). 위는 원래 벽
        const x = ox + d.x, y = oy + d.y, w = d.w || 1, h = d.h || 1, door = d.door ?? 1.5, th = 0.35;
        out.push([x, y, th, h], [x + w - th, y, th, h],
                 [x, y + h - th, (w - door) / 2, th], [x + (w + door) / 2, y + h - th, (w - door) / 2, th]);
        return;
      }
      if (!d.s || d.fx || d.z === 'wall' || d.z === 'floor' || d.z === 'top') return;
      const [w, h] = sizeT(d);
      for (let i = 0; i < (d.n || 1); i++) {
        const f = footprint({ ...d, x: ox + d.x + i * (d.dx || 1), y: oy + d.y }, w, h);
        if (f) out.push(f);
      }
    };
    for (const d of theme.sprites.decor || []) add(d, 0, 0);
    const iz = L.zones.infra;
    for (const kind of ['jenkins', 'harbor', 'argocd']) for (const d of (theme.sprites.infra_decor || {})[kind] || []) add(d, iz[kind].x, iz.y);
    return out;
  }
  // 라운지는 의자(앉는 자리)뿐이라 막을 가구가 없다 — 벽만
  const GRID = SP ? { room: buildGrid(L.room.w, L.room.h, obstacles(), CORRIDORS), lounge: buildGrid(L.lounge.w, L.lounge.h, []) } : null;
  function roomOf(a) {
    if (a.room === '_hq') return null;
    return a.room == null ? world.lounge : world.rooms.find((r) => r.name === a.room);
  }
  // 목표가 바뀌면 길을 새로 찾는다(월드 좌표 점 목록). 작은 일꾼(서브에이전트)은 부모 둘레를 날아다녀 길을 찾지 않는다
  function routeOf(a) {
    const key = a.tx + ',' + a.ty;
    if (a.routeKey === key) return a.route;
    a.routeKey = key;
    const r = GRID && a.kind !== 'mini' ? roomOf(a) : null;
    if (!r) { a.route = [[a.tx, a.ty]]; return a.route; }
    const g = r.lounge ? GRID.lounge : GRID.room;
    a.route = findPath(g, a.x - r.x, a.y - r.y, a.tx - r.x, a.ty - r.y).map(([x, y]) => [x + r.x, y + r.y]);
    return a.route;
  }
  function drawWalkDebug() {
    if (!WALK_DEBUG || !GRID) return;
    for (const r of [...world.rooms, world.lounge]) {
      if (!r) continue;
      const g = r.lounge ? GRID.lounge : GRID.room;
      for (let i = 0; i < g.cols * g.rows; i++) {
        const c = i % g.cols, rr = Math.floor(i / g.cols);
        if (g.block[i]) ctx.fillStyle = '#ff303055';
        else if (g.cost[i] <= 1) ctx.fillStyle = '#30a0ff33';
        else continue;
        ctx.fillRect((r.x + c / RES) * T, (r.y + rr / RES) * T, T / RES, T / RES);
      }
    }
    ctx.strokeStyle = '#ffee00'; ctx.lineWidth = 1;
    for (const a of actors.values()) {
      if (!a.route || a.kind === 'mini') continue;
      ctx.beginPath(); ctx.moveTo(a.x * T, a.y * T);
      for (const [x, y] of a.route) ctx.lineTo(x * T, y * T);
      ctx.stroke();
    }
  }

  // ── 카메라 ──────────────────────────────────────────
  function roomByView() { return [...world.rooms, world.lounge].find((r) => (r.name || '_lounge') === view); }
  function aim() {
    const q = view === 'hq' ? world.hq : view === 'map' ? null : roomByView();
    const r = !q ? { x: -1, y: -3, w: world.w + 2, h: world.h + 4 }
      : q.hq ? { x: q.x - 0.5, y: q.y - 0.5, w: q.w + 1, h: q.h + 6 }          // 아래에 현장 카드 자리
      : { x: q.x - 0.5, y: q.y - 2.5, w: q.w + 1, h: q.h + 3 };
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
      if (a.kind === 'mini') {
        if (a.bornAt && now < a.bornAt) continue;              // 아직 소환 중 — 마법진 가운데서 기다린다
        [a.tx, a.ty] = miniTarget(a, now);
      }
      // 길(점 목록)의 다음 점으로 걷는다 — 점에 닿으면 다음 점, 남은 걸음은 이어서 쓴다
      const route = routeOf(a);
      let step = SPEED * dt * (a.kind === 'mini' ? 0.8 : 1);
      a.moving = false;
      while (route.length && step > 0) {
        const [px, py] = route[0];
        const dx = px - a.x, dy = py - a.y, d = Math.hypot(dx, dy);
        if (d > 0.05) { a.moving = true; a.dir = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up'); }
        if (d <= step) { a.x = px; a.y = py; step -= d; if (route.length > 1) route.shift(); else break; }
        else { a.x += dx / d * step; a.y += dy / d * step; step = 0; }
      }
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
      drawHQS(now, sorted);
      for (const r of world.rooms) drawRoomS(r, now, sorted);
      if (world.lounge) drawLoungeS(world.lounge, now, sorted);
      for (const a of list) if (!(a.bornAt && now < a.bornAt)) sorted.push({ y: a.y, draw: () => drawActorS(a, now) });
      sorted.sort((p, q) => p.y - q.y);
      for (const it of sorted) it.draw();
      for (const a of list) drawOverlay(a, now);
    } else {
      drawHQShapes(now);
      for (const r of world.rooms) drawRoom(r, now);
      if (world.lounge) drawLounge(world.lounge);
      for (const a of list) if (!(a.bornAt && now < a.bornAt)) drawActor(a, now);
    }
    drawSummonsPuffs(now);
    drawWalkDebug();
    // 글자는 화면 좌표로(선명하게)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    HITS = [];
    const zoomedIn = view !== 'map';
    for (const r of [...world.rooms, world.lounge]) drawBadge(r, zoomedIn);
    if (view === 'hq') {
      drawHQCards();
      const hqName = (theme.hq && theme.hq.label) || '감독실';
      drawTag(world.hq.x + 0.3, world.hq.y + 2.2, hqName, true, null, null,
        `<div class="otip-h">${esc(hqName)}</div><b>감독실</b><div>현장(프로젝트)마다 지금 상태를 한눈에 — 현황판의 칸을 누르면 그 현장으로 들어간다</div>`);
      for (const a of list) if (a.room === '_hq') drawName(a);
    } else if (zoomedIn) {
      const room = roomByView();
      if (room && !room.lounge) drawZoneTags(room);
      for (const a of list) if (a.room === (view === '_lounge' ? null : view)) drawName(a);
    }
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
    if (a.kind === 'mini') {                                  // 도형 테마의 축소판
      const s = MINI, x = a.x * T, yb = a.y * T, h = sp.h * s, w = sp.w * s, bob = Math.abs(Math.sin(a.phase)) * 1.5;
      ctx.fillStyle = roleColor(a.role) || `hsl(${a.hue} 55% 55%)`; ctx.fillRect(x - w / 2, yb - h * 0.7 - bob, w, h * 0.7);
      ctx.fillStyle = '#f1c9a5'; ctx.beginPath(); ctx.arc(x, yb - h * 0.8 - bob, sp.head * s, 0, Math.PI * 2); ctx.fill();
      return;
    }
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
    if (a.subHidden) drawBubble(x + 10, y + 2, `+${a.subHidden}`, P.act, 7);              // 10명 넘는 서브에이전트는 접는다
    const rc = roleColor(a.role);
    if (rc) { ctx.fillStyle = rc; ctx.fillRect(x - 1, y + sp.head * 1.6, 2, h - sp.head * 1.6 - 2); }   // 역할 — 사원증 끈 색
    if (a.key === selected) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - 9, y - 3, 18, h + 6); }
  }

  // ── 시트 테마 그리기(10d) ────────────────────────────
  const RS = (SP && theme.sprites.room) || {};
  function tileHash(i, j) { return ((i * 73856093) ^ (j * 19349663)) >>> 0; }

  function spriteBottom(name, y) { const [, h] = SP.size(name); return y + h / T; }

  // 탁자 위 소품의 그리는 순서 — 소품 가운데가 들어 있는 받침(같은 목록의 가구) 중 발밑이 가장 아래인 것 바로 다음.
  // 전에는 y + 3(어림)이라 받침 앞(아래)에 선 사람보다 늦게 그려져 사람 머리 위로 소품이 덮였다(11-05)
  function topKey(d) {
    if (d._k != null) return d._k;
    const list = (theme.sprites.decor || []).includes(d) ? theme.sprites.decor
      : Object.values(theme.sprites.infra_decor || {}).find((l) => l.includes(d)) || [];
    const [w, h] = sizeT(d), cx = d.x + w / 2, cy = d.y + h / 2;
    let best = null;
    for (const b of list) {
      if (!b.s || b.fx || b.z) continue;
      const [bw, bh] = sizeT(b);
      for (let i = 0; i < (b.n || 1); i++) {
        const bx = b.x + i * (b.dx || 1);
        if (cx >= bx && cx <= bx + bw && cy >= b.y && cy <= b.y + bh && (best == null || b.y + bh > best)) best = b.y + bh;
      }
    }
    d._k = best != null ? best - 0.005 : d.y + h + 0.3;   // 받침보다 0.005 뒤 = 받침 발밑(-0.01)보다 뒤, 받침 앞 사람보다 앞
    return d._k;
  }

  // 장식 하나 — z: wall · floor는 바로, top(탁자 위)은 탁자 바로 뒤, 그 밖은 발밑 순서로
  function placeDecor(d, ox, oy, now, sorted) {
    const n = d.n || 1;
    for (let i = 0; i < n; i++) {
      const x = ox + d.x + i * (d.dx || 1), y = oy + d.y;
      if (d.fx === 'glasswall') { sorted.push({ y: y + (d.h || 1) + 0.05, draw: () => drawFx(d.fx, x, y, now, d) }); continue; }   // 유리벽은 그 구역 앞에
      if (d.fx) { sorted.push({ y: y + 0.1, draw: () => drawFx(d.fx, x, y, now, d) }); continue; }
      const scale = d.scale || 1;
      const draw = () => {
        if (d.alpha != null) ctx.globalAlpha = d.alpha * (d.pulse ? 0.65 + 0.35 * Math.sin(now / 700) : 1);
        SP.draw(ctx, d.s, x * T, y * T, now, scale, d.frame != null ? d.frame : null);
        ctx.globalAlpha = 1;
      };
      if (d.z === 'wall' || d.z === 'floor') draw();
      else if (d.z === 'top') sorted.push({ y: oy + topKey(d), draw });       // 탁자 · 선반 위 — 받침 바로 다음(받침 앞에 선 사람보다는 먼저)
      else sorted.push({ y: spriteBottom(d.s, y) * 1 - 0.01, draw });
    }
  }

  // 바닥 — 시트 타일이거나(room.floor 이름 목록) 테마 색으로 그린 타일(room.proc.floor: 오피스 파란 타일 · 현장 콘크리트)
  function drawFloor(x0, y0, w, h, spec, salt = 0) {
    if (spec && typeof spec === 'object' && !Array.isArray(spec)) {
      const tw = spec.tile || 1, th = spec.tileH || tw;
      ctx.save();
      ctx.beginPath(); ctx.rect(x0 * T, y0 * T, w * T, h * T); ctx.clip();   // 엇갈린 타일이 구역 밖으로 넘치지 않게
      ctx.fillStyle = spec.a; ctx.fillRect(x0 * T, y0 * T, w * T, h * T);
      for (let j = 0; j < h / th; j++) for (let i = 0; i <= w / tw; i++) {
        const hsh = tileHash(i + salt, j);
        const off = spec.stagger && j % 2 ? tw / 2 : 0;
        const px0 = (x0 + i * tw - off) * T, py0 = (y0 + j * th) * T;
        if (spec.b && hsh % 3 === 0) { ctx.fillStyle = spec.b; ctx.fillRect(Math.max(px0, x0 * T), py0, tw * T, th * T); }
        if (spec.spot && hsh % 7 === 0) { ctx.fillStyle = spec.spot; ctx.fillRect(px0 + (hsh % 11), py0 + ((hsh >>> 4) % 11), 2, 2); }
        ctx.fillStyle = spec.grout || '#0003';
        ctx.fillRect(Math.max(px0, x0 * T), py0, tw * T, 1); ctx.fillRect(px0, py0, 1, th * T);
      }
      ctx.restore();
      return;
    }
    const fl = Array.isArray(spec) ? spec : [spec];
    for (let i = 0; i < w; i++) for (let j = 0; j < h; j++) SP.draw(ctx, fl[tileHash(x0 + i + salt, y0 + j) % fl.length], (x0 + i) * T, (y0 + j) * T);
  }
  const FLOOR = (RS.proc && RS.proc.floor) || RS.floor || ['floor_1'];

  function drawRoomS(r, now, sorted) {
    const z = L.zones;
    drawFloor(r.x + 1, r.y + 2, r.w - 2, r.h - 3, FLOOR);
    for (const zz of Object.values(z)) {
      if (!zz || !zz.floor) continue;
      drawFloor(r.x + zz.x, r.y + zz.y, zz.w, zz.h, (RS.proc && RS.proc[zz.floor]) || zz.floor, 3);
    }
    // 출하 라인 바닥은 조금 어둡게
    const iz = z.infra;
    ctx.fillStyle = P.infraFloor; ctx.fillRect((r.x + 1) * T, (r.y + iz.y) * T, (r.w - 2) * T, iz.h * T);
    drawCorridors(r);
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

  // ㅗ자 복도 — 바닥에 깐 길(마법학교 붉은 융단 · 오피스 회색 카펫 · 현장 초록 보행로 + 노란 선). 사각형이 겹친 곳은 테두리 없이 이어진다
  function drawCorridors(r) {
    const cs = RS.corridor;
    if (!cs || !CORRIDORS.length) return;
    const px = (v) => v * T, e = 1.5;
    ctx.fillStyle = cs.a;
    for (const [x, y, w, h] of CORRIDORS) ctx.fillRect(px(r.x + x), px(r.y + y), px(w), px(h));
    if (cs.b) {                                            // 결 — 융단 · 카펫은 가로 줄무늬, 보행로는 빗금
      ctx.fillStyle = cs.b;
      for (const [x, y, w, h] of CORRIDORS) {
        ctx.save(); ctx.beginPath(); ctx.rect(px(r.x + x), px(r.y + y), px(w), px(h)); ctx.clip();
        if (cs.kind === 'walkway') for (let k = -h; k < w; k += 1) { ctx.beginPath(); ctx.moveTo(px(r.x + x + k), px(r.y + y + h)); ctx.lineTo(px(r.x + x + k + h), px(r.y + y)); ctx.lineTo(px(r.x + x + k + h + 0.3), px(r.y + y)); ctx.lineTo(px(r.x + x + k + 0.3), px(r.y + y + h)); ctx.fill(); }
        else for (let k = 0.25; k < Math.max(w, h); k += 0.5) w >= h ? ctx.fillRect(px(r.x + x), px(r.y + y + (k % h)), px(w), 1) : ctx.fillRect(px(r.x + x + (k % w)), px(r.y + y), 1, px(h));
        ctx.restore();
      }
    }
    ctx.fillStyle = cs.edge;
    for (const [x, y, w, h, side] of CORRIDOR_EDGES) {   // 바깥 테두리만(사각형이 맞닿은 곳은 이어진다)
      const X = px(r.x + x), Y = px(r.y + y);
      if (side === 't') ctx.fillRect(X, Y, px(w), e); else if (side === 'b') ctx.fillRect(X, Y - e, px(w), e);
      else if (side === 'l') ctx.fillRect(X, Y, e, px(h)); else ctx.fillRect(X - e, Y, e, px(h));
    }
  }
  // 복도 바깥 테두리 — 사각형 변을 잘게 나눠 바깥쪽이 다른 복도가 아닌 구간만 남긴다(한 번만 계산)
  const CORRIDOR_EDGES = (() => {
    const inAny = (x, y) => CORRIDORS.some(([a, b, w, h]) => x > a && x < a + w && y > b && y < b + h);
    const out = [], S = 0.05, o = 0.02;
    for (const [x, y, w, h] of CORRIDORS) {
      const sides = [['t', x, y, w, 0, 0, -o], ['b', x, y + h, w, 0, 0, o], ['l', x, y, 0, h, -o, 0], ['r', x + w, y, 0, h, o, 0]];
      for (const [side, sx, sy, lw, lh, ox, oy] of sides) {
        const len = lw || lh;
        let start = null;
        for (let t = 0; t <= len + 1e-9; t += S) {
          const qx = sx + (lw ? t : 0), qy = sy + (lh ? t : 0);
          const edge = t < len && !inAny(qx + (lw ? S / 2 : 0) + ox, qy + (lh ? S / 2 : 0) + oy);
          if (edge && start == null) start = t;
          if ((!edge || t + S > len + 1e-9) && start != null) {
            const end = edge ? len : t;
            out.push(lw ? [sx + start, sy, end - start, 0, side] : [sx, sy + start, 0, end - start, side]);
            start = null;
          }
        }
      }
    }
    return out;
  })();

  // 벽 — 위 두 줄은 시트(머리 · 면), 옆 · 아래 테두리는 어두운 두께(위에서 내려다본 벽 윗면)
  function drawWalls(r) {
    const pw = RS.proc && RS.proc.wall;
    if (pw) {
      // 색으로 그린 벽 — 위 띠 + 면 + 가로줄(2dPig 벽 · 현장 철판 벽)
      ctx.fillStyle = pw.top; ctx.fillRect(r.x * T, r.y * T, r.w * T, T * 0.5);
      ctx.fillStyle = pw.face; ctx.fillRect(r.x * T, (r.y + 0.5) * T, r.w * T, T * 1.5);
      ctx.fillStyle = pw.stripe;
      for (let k = 0; k < (pw.stripes || 3); k++) ctx.fillRect(r.x * T, (r.y + 0.75 + k * 0.4) * T, r.w * T, 1);
      if (pw.rivet) { ctx.fillStyle = pw.rivet; for (let i = 0; i < r.w; i += 2) ctx.fillRect((r.x + i + 0.5) * T, (r.y + 0.6) * T, 2, 2); }
      ctx.fillStyle = pw.base || '#0004'; ctx.fillRect(r.x * T, (r.y + 2) * T - 2, r.w * T, 2);
    } else for (let i = 0; i < r.w; i++) {
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
    drawFloor(r.x + 1, r.y + 2, r.w - 2, r.h - 3, FLOOR, 7);
    ctx.fillStyle = P.lounge + '88'; ctx.fillRect((r.x + 1) * T, (r.y + 2) * T, (r.w - 2) * T, (r.h - 3) * T);
    drawWalls(r);
    const z = L.zones.lounge_seats;
    for (let k = 0; k < z.cols * z.rows; k++) {
      const sx = r.x + z.x + (k % z.cols) * z.dx, sy = r.y + z.y + Math.floor(k / z.cols) * z.dy + 1;
      sorted.push({ y: sy + 0.6, draw: () => SP.draw(ctx, 'stool', (sx - 0.5) * T, (sy - 0.4) * T) });
    }
  }

  // 엔진이 그리는 빛 — 수정구 · 스테인드글라스 · 촛불(에셋에 없는 것)
  function drawFx(kind, x, y, now, d = {}) {
    const t = now / 1000;
    if (kind === 'stripes') {
      // 안전 줄무늬 — 노랑 · 검정 빗금 띠
      const w = (d.w || 1) * T, h = (d.h || 0.3) * T;
      ctx.save(); ctx.beginPath(); ctx.rect(x * T, y * T, w, h); ctx.clip();
      ctx.fillStyle = P.stripeA || '#f2c14e'; ctx.fillRect(x * T, y * T, w, h);
      ctx.fillStyle = P.stripeB || '#2b2f3a';
      for (let k = -h; k < w; k += 8) { ctx.beginPath(); ctx.moveTo(x * T + k, y * T + h); ctx.lineTo(x * T + k + 4, y * T + h); ctx.lineTo(x * T + k + 4 + h, y * T); ctx.lineTo(x * T + k + h, y * T); ctx.fill(); }
      ctx.restore();
      return;
    }
    if (kind === 'glasswall') {
      // 유리벽 — 옅은 하늘색 면 + 밝은 테두리, 위쪽 반사광(사람이 비쳐 보인다)
      const w = (d.w || 1) * T, h = (d.h || 1) * T, c = P.glassWall || '#bfe8ff';
      const door = (d.door ?? 1.5) * T, dl = x * T + (w - door) / 2;   // 아래 가운데 문(걷기 격자와 같은 자리 — 사람이 여기로 드나든다)
      ctx.globalAlpha = 0.10; ctx.fillStyle = c; ctx.fillRect(x * T, y * T, w, h);
      ctx.globalAlpha = 0.7; ctx.strokeStyle = c; ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(dl, y * T + h - 0.5); ctx.lineTo(x * T + 0.5, y * T + h - 0.5); ctx.lineTo(x * T + 0.5, y * T + 0.5);
      ctx.lineTo(x * T + w - 0.5, y * T + 0.5); ctx.lineTo(x * T + w - 0.5, y * T + h - 0.5); ctx.lineTo(dl + door, y * T + h - 0.5);
      ctx.stroke();
      ctx.fillStyle = c; ctx.fillRect(dl - 1, y * T + h - 4, 2, 4); ctx.fillRect(dl + door - 1, y * T + h - 4, 2, 4);   // 문설주
      ctx.globalAlpha = 0.35; ctx.beginPath(); ctx.moveTo(x * T + 4, y * T + h - 4); ctx.lineTo(x * T + 14, y * T + h - 14); ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }
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
  // 소환(마법진이 밝아지고 불꽃) · 퇴장(연기) — 10c
  function drawSummonsPuffs(now) {
    for (let i = summons.length - 1; i >= 0; i--) {
      const s = summons[i], e = now - s.t0;
      if (e > 500) { summons.splice(i, 1); continue; }
      if (e < -600) continue;
      const k = 1 - Math.abs(e + 50) / 550;
      if (SP && SP.has('fx_circle')) {
        ctx.globalAlpha = Math.max(0, k);
        SP.draw(ctx, 'fx_circle', s.x * T - 16, s.y * T - 16, now);
        if (SP.has('fx_spark')) SP.draw(ctx, 'fx_spark', s.x * T - 15, s.y * T - 30, now);
        ctx.globalAlpha = 1;
      } else {
        ctx.strokeStyle = P.act; ctx.globalAlpha = Math.max(0, k); ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(s.x * T, s.y * T, 6 + (1 - k) * 10, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1;
      }
    }
    for (let i = puffs.length - 1; i >= 0; i--) {
      const p = puffs[i], e = now - p.t0;
      if (e > 600) { puffs.splice(i, 1); continue; }
      if (e < 0) continue;
      if (SP && SP.has('fx_smoke')) SP.draw(ctx, 'fx_smoke', p.x * T - 16, p.y * T - 26, now, 1, Math.floor(e / 100));
      else drawSmoke(p.x, p.y - 0.3, now);
    }
  }

  function drawActorS(a, now) {
    if (a.kind === 'mini') {                                  // 부모의 축소판 — 늘 걷는 그림(돌아다닌다)
      const dir = a.dir || 'down';
      const c = SP.charFrame(a.char, 'walk', dir, Math.floor(a.phase * 0.8) % 4, null, ROLE_MODE === 'robe' ? roleColor(a.role) : null);
      if (!c) return;
      const w = Math.round(c.width * MINI), h = Math.round(c.height * MINI);
      const bob = c.static ? Math.round(Math.abs(Math.sin(a.phase * 1.3)) * 1.5) : 0;
      ctx.drawImage(c, Math.round(a.x * T - w / 2), Math.round(a.y * T - h) - bob, w, h);
      return;
    }
    const act = a.act || {};
    const anim = a.moving ? 'walk' : (act.anim || 'stand');
    const dir = a.moving ? (a.dir || 'down') : (a.face || 'down');
    const mode = act.fx === 'stone' || act.fx === 'frozen' ? 'stone' : act.fx === 'ghost' ? 'ghost' : null;
    const walking = a.moving || anim === 'work';
    const f = walking && !mode ? Math.floor(a.phase * 0.8) % 4 : 0;
    const c = SP.charFrame(a.char, walking ? 'walk' : 'idle', dir, f, mode, mode || ROLE_MODE !== 'robe' ? null : roleColor(a.role));
    if (!c) return;
    let px = Math.round(a.x * T - c.width / 2), py = Math.round(a.y * T - c.height);
    a.drawH = c.height;
    if (c.static && walking && !mode) py -= Math.round(Math.abs(Math.sin(a.phase * 1.3)) * 2);   // 정면 한 장 — 출렁여서 걷는 흉내
    if (anim === 'sleep') py += 4;                                               // 엎드려 잔다 — 머리를 탁자 위로
    if (mode === 'ghost') py += Math.round(Math.sin(a.phase * 0.6) * 1.5) - 2;  // 유령은 떠 있다
    ctx.globalAlpha = act.alpha != null ? act.alpha : 1;
    if (anim === 'lie' && !a.moving) {
      // 간이침대에 눕기 — 그림을 옆으로 눕힌다(엔진 흉내). 머리는 왼쪽(베개 쪽)
      ctx.save();
      ctx.translate(Math.round(a.x * T), Math.round(a.y * T - 5));
      ctx.rotate(-Math.PI / 2);
      ctx.drawImage(c, -c.width / 2, -c.height / 2);
      ctx.restore();
      ctx.globalAlpha = 1;
      a.drawH = 10;
      return;
    }
    ctx.drawImage(c, px, py);
    // 역할 표시 — 오피스는 사원증 끈, 현장은 안전모 색(마법학교는 위에서 로브 색을 바꿨다)
    const rc = !mode && roleColor(a.role);
    if (rc && ROLE_MODE === 'lanyard') {
      const cx = Math.round(a.x * T), ny = py + Math.round(c.height * 0.42);
      ctx.fillStyle = rc;
      for (let k = 0; k < 4; k++) { ctx.fillRect(cx - 3 + Math.floor(k / 1.4), ny + k, 1, 1); ctx.fillRect(cx + 2 - Math.floor(k / 1.4), ny + k, 1, 1); }
      ctx.fillStyle = '#ffffff'; ctx.fillRect(cx - 1, ny + 4, 3, 3); ctx.fillStyle = rc; ctx.fillRect(cx - 1, ny + 4, 3, 1);
    } else if (rc && ROLE_MODE === 'helmet') {
      const hw = Math.round(c.width * 0.62), hx = Math.round(a.x * T - hw / 2), hy = py - 1;
      ctx.fillStyle = rc; ctx.fillRect(hx, hy, hw, 3); ctx.fillRect(hx - 1, hy + 3, hw + 2, 1);
      ctx.fillStyle = '#ffffff55'; ctx.fillRect(hx + 1, hy, 2, 1);
    }
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
    const x = a.x * T, top = a.y * T - (a.drawH || 16);
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
    if (a.subHidden) drawBubble(x + 11, top + 4, `+${a.subHidden}`, P.act, 7);      // 10명 넘는 서브에이전트는 접는다
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

  // ── 구역 이름표(화면 좌표 — 줌과 상관없이 작고 선명하게) ─────
  const TAG = (theme.tags && theme.tags.style) || { bg: '#000000cc', fg: '#ffffff', border: '#ffffff55', font: '600 10px system-ui, sans-serif', kind: 'sign' };
  // (wx, wy) 월드 타일 → 그 자리에 이름표 하나. big: 감독실 이름처럼 조금 크게. dot: 앞에 붙는 상태 색
  function drawTag(wx, wy, text, big = false, dot = null, sub = null, tip = null) {
    const box = drawTagBox(wx, wy, text, big, dot, sub);
    if (tip) HITS.push({ ...box, tip });
    return box;
  }
  function drawTagBox(wx, wy, text, big, dot, sub) {
    const [sx, sy] = toScreen(wx * T, wy * T);
    const font = big ? TAG.font.replace(/(\d+)px/, (m, n) => `${+n + 3}px`) : TAG.font;
    ctx.font = font; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    const fs = +(font.match(/(\d+)px/) || [0, 10])[1];
    const tw = ctx.measureText(text).width;
    ctx.font = TAG.font;
    const sw = sub ? ctx.measureText(sub).width + 8 : 0;
    const padL = TAG.kind === 'hazard' ? 9 : TAG.kind === 'sign' ? 7 : 6;
    const w = Math.ceil(padL + (dot ? 9 : 0) + tw + 6 + sw), h = fs + 7;
    const x = Math.round(sx), y = Math.round(sy);
    ctx.fillStyle = TAG.bg; ctx.fillRect(x, y, w, h);
    if (TAG.kind === 'hazard') {                                     // 안전 표지판 — 왼쪽에 검정 · 노랑 빗금, 검정 테두리
      ctx.save(); ctx.beginPath(); ctx.rect(x, y, 6, h); ctx.clip();
      ctx.fillStyle = TAG.border; ctx.fillRect(x, y, 6, h);
      ctx.fillStyle = TAG.bg; for (let k = -h; k < 6; k += 5) { ctx.beginPath(); ctx.moveTo(x + k, y + h); ctx.lineTo(x + k + 2, y + h); ctx.lineTo(x + k + 2 + h, y); ctx.lineTo(x + k + h, y); ctx.fill(); }
      ctx.restore();
      ctx.strokeStyle = TAG.border; ctx.lineWidth = 1.5; ctx.strokeRect(x + 0.75, y + 0.75, w - 1.5, h - 1.5);
    } else if (TAG.kind === 'sign') {                                // 사인판 — 왼쪽 색 띠
      ctx.fillStyle = TAG.border; ctx.fillRect(x, y, 3, h);
      ctx.strokeStyle = '#00000022'; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
    } else {                                                         // 양피지 — 테두리 + 모서리 말림
      ctx.strokeStyle = TAG.border; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
      ctx.fillStyle = TAG.border; ctx.beginPath(); ctx.moveTo(x + w - 5, y + h); ctx.lineTo(x + w, y + h - 5); ctx.lineTo(x + w, y + h); ctx.fill();
      ctx.fillStyle = '#c9b282'; ctx.fillRect(x + 1, y + h - 2, w - 7, 1);
    }
    let cx = x + padL;
    if (dot) { ctx.fillStyle = dot; ctx.beginPath(); ctx.arc(cx + 3, y + h / 2, 3, 0, Math.PI * 2); ctx.fill(); cx += 9; }
    ctx.font = font; ctx.fillStyle = TAG.fg; ctx.fillText(text, cx, y + h / 2 + 0.5);
    if (sub) {                                                       // 상태 — 이름표 바탕 위에서 읽히게 글자색, 앞에 구분선
      ctx.fillStyle = TAG.fg; ctx.globalAlpha = 0.35; ctx.fillRect(cx + tw + 4, y + 3, 1, h - 6); ctx.globalAlpha = 1;
      ctx.font = TAG.font.replace(/^(italic )?\d*\s*/, 'bold '); ctx.fillStyle = TAG.fg; ctx.fillText(sub, cx + tw + 8, y + h / 2 + 0.5);
    }
    return { x, y, w, h };
  }

  const STATUS_KO = { running: '진행 중', success: '성공', failed: '실패', waiting: 'Sync 대기', none: '기록 없음' };
  // 구역이 하는 일 — 테마마다 이름(비유)은 달라도 설명은 같다(theme.tags.roles: 구역 → 아래 열쇠). 이름표에 마우스를 올리면 뜬다(11-05)
  const ZONE_ROLE = {
    hq:   { what: '감독 자리', tools: '', desc: '포먼 자리. 감독실에서는 현장마다의 상태를 현황판으로 본다' },
    read: { what: '파일 읽기', tools: 'Read · Grep · Glob', desc: '코드 · 문서를 읽거나 찾을 때 여기로 온다' },
    edit: { what: '코드 수정', tools: 'Edit · Write', desc: '파일을 고치거나 새로 쓸 때. 할 일 정리(TodoWrite)와 그 밖의 도구도 여기서' },
    bash: { what: '명령 실행', tools: 'Bash', desc: '셸 명령을 돌릴 때(테스트 · git은 따로)' },
    test: { what: '테스트 실행', tools: 'Bash — pytest · node --test · jest · ruff · mypy …', desc: '테스트 · 린트 · 문법 검사를 돌릴 때' },
    git:  { what: 'git 작업', tools: 'Bash — git …', desc: '커밋 · 푸시 · 이력 보기 등 git 명령' },
    web:  { what: '웹 검색', tools: 'WebSearch · WebFetch · MCP', desc: '밖에서 정보를 찾거나 페이지를 열 때, 외부 도구(MCP)를 쓸 때' },
    sub:  { what: '보조 호출', tools: 'Agent(서브에이전트)', desc: '서브에이전트를 띄우는 곳. 작은 일꾼이 여기서 생겨나 부모 둘레에서 일한다' },
    idle: { what: '대기 중', tools: '', desc: '할 일이 없을 때 쉬는 곳. 입력을 받으면 다시 자리로 간다' },
  };
  const INFRA_ROLE = {
    jenkins: { what: '빌드', tools: 'Jenkins', desc: '푸시한 커밋이 빌드 · 테스트되는 곳. 실패하면 여기서 멈춘다' },
    harbor:  { what: '이미지 저장', tools: 'Harbor', desc: '빌드된 컨테이너 이미지가 올라가 보관되는 곳' },
    argocd:  { what: '배포', tools: 'ArgoCD', desc: '저장된 새 이미지가 클러스터(k8s)에 배포되는 곳. 수동 Sync 앱은 "Sync 대기"로 멈춰 있다' },
  };
  const tipOf = (r) => r && `<b>${r.what}</b>${r.tools ? ` <span class="otip-t">${r.tools}</span>` : ''}<div>${r.desc}</div>`;
  let HITS = [];                     // 이번 프레임에 그린 이름표 자리(화면 좌표) — 마우스를 올리면 설명
  function drawZoneTags(r) {
    const names = (theme.tags && theme.tags.zones) || {};
    for (const [key, v] of Object.entries(names)) {
      const z = L.zones[key];
      if (!z || z.x == null) continue;
      const [label, dx, dy] = Array.isArray(v) ? v : [v, 0, 0];      // ["아치 창", dx, dy] — 옆 구역 이름표와 겹치면 비켜 둔다
      const role = ZONE_ROLE[((theme.tags && theme.tags.roles) || {})[key]];
      drawTag(r.x + z.x + 0.1 + (dx || 0), r.y + z.y + 0.08 + (dy || 0), label, false, null, null, role ? `<div class="otip-h">${esc(label)}</div>${tipOf(role)}` : null);
    }
    // 출하 라인 — 이름 · 세 단계(번호 · 무엇 · 지금 상태) · 단계 사이 화살표
    const iz = L.zones.infra, it = (theme.tags && theme.tags.infra) || {};
    if (!iz) return;
    if (it.title) drawTag(r.x + 1.1, r.y + iz.y - 0.6, it.title, false, null, null,
      `<div class="otip-h">${esc(it.title)}</div><b>출하 라인</b><div>커밋 → ① 빌드(Jenkins) → ② 이미지 저장(Harbor) → ③ 배포(ArgoCD). 단계마다 지금 상태가 이름표 오른쪽에 붙는다</div>`);
    const kinds = ['jenkins', 'harbor', 'argocd'];
    kinds.forEach((kind, i) => {
      const st = r['st_' + kind] || 'none';
      const col = { running: P.act, success: P.ok, failed: P.bad, waiting: P.warn, none: P.muted }[st] || P.muted;
      const label = `${'①②③'[i]} ${it[kind] || (iz[kind] && iz[kind].label) || kind}`;
      drawTag(r.x + iz[kind].x + 0.1, r.y + iz.y + 0.25, label, false, col, STATUS_KO[st] || st,
        `<div class="otip-h">${esc(label)}</div>${tipOf(INFRA_ROLE[kind])}<div class="otip-s">지금: ${esc(STATUS_KO[st] || st)}</div>`);
      if (i < kinds.length - 1) {                                     // 다음 단계로 화살표
        const [ax, ay] = toScreen((r.x + iz[kind].x + 4.7) * T, (r.y + iz.y + 1.5) * T);
        const [bx] = toScreen((r.x + iz[kinds[i + 1]].x - 0.1) * T, 0);
        if (bx - ax > 16) {
          // 이름표 바탕색(양피지 · 흰색 · 안전 노랑)에 테두리색 그림자 — 어느 바닥에서도 보이게
          for (const [col, wdt] of [[TAG.border, 5], [TAG.bg.slice(0, 7), 3]]) {
            ctx.strokeStyle = col; ctx.lineWidth = wdt; ctx.globalAlpha = 0.9;
            ctx.setLineDash([8, 5]); ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx - 9, ay); ctx.stroke(); ctx.setLineDash([]);
          }
          ctx.fillStyle = TAG.bg.slice(0, 7); ctx.strokeStyle = TAG.border; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.moveTo(bx, ay); ctx.lineTo(bx - 10, ay - 6); ctx.lineTo(bx - 10, ay + 6); ctx.closePath(); ctx.fill(); ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }
    });
  }

  function drawName(a) {
    if (a.kind === 'mini' && a.key !== selected) return;     // 작은 일꾼 이름은 누른 것만(묶음 이름은 부모 밑에)
    const [sx, sy] = toScreen(a.x * T, a.y * T);
    const text = a.kind === 'session' ? short(a.name, 18) : short(a.name, 30);
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const w = ctx.measureText(text).width + 6;
    ctx.fillStyle = '#000a'; ctx.fillRect(sx - w / 2, sy + 2, w, 14);
    ctx.fillStyle = a.kind === 'foreman' ? P.warn : P.label;
    ctx.fillText(text, sx, sy + 3);
    const n = a.kind === 'session' && a.s ? a.s.subagents_running || 0 : 0;
    if (n) {
      const sub = `일꾼 ${n}${a.subLabel ? ' · ' + short(a.subLabel, 22) : ''}${a.subHidden ? ` (+${a.subHidden} 접음)` : ''}`;
      const w2 = ctx.measureText(sub).width + 6;
      ctx.fillStyle = '#000a'; ctx.fillRect(sx - w2 / 2, sy + 17, w2, 14);
      ctx.fillStyle = P.act; ctx.fillText(sub, sx, sy + 18);
    }
  }

  function fmt(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(n); }

  // 현장 상태 하나 — 감독실 표시(촛불 · 모니터 · 자석)와 카드 테두리가 같은 판단을 쓴다
  function siteState(r) {
    const st = r.stats || {}, pp = r.pipe;
    const broke = pp && pp.chains && pp.chains[0] && pp.chains[0].broke;
    if (broke || (pp && pp.webhook_broken) || (pp && pp.watch && pp.watch.state === 'missing')) return 'fail';
    if (st.pending) return 'alert';
    if (st.ACTIVE) return 'busy';
    if ((st.IDLE || 0) + (st.SUSPENDED || 0) + (st.DORMANT || 0)) return 'idle';
    return 'empty';
  }

  function badgeLines(r) {
    const st = r.stats || {};
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
    const border = st.pending || broke ? P.warn : hot;
    return { lines, border, thick: r.rate > 3e5 || st.pending };
  }

  function drawCard(r, bx, by, w, minW = 160, maxW = 300) {
    const { lines, border, thick } = badgeLines(r);
    w = Math.max(minW, Math.min(w, maxW));
    const h = lines.length * 15 + 8;
    ctx.fillStyle = '#0d0f14e6'; ctx.fillRect(bx, by, w, h);
    ctx.strokeStyle = border; ctx.lineWidth = thick ? 2 : 1;
    ctx.strokeRect(bx + 0.5, by + 0.5, w - 1, h - 1);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    const maxc = Math.max(18, Math.floor((w - 12) / 6.2));
    lines.forEach(([t, c, f], i) => { ctx.font = `${f} system-ui, sans-serif`; ctx.fillStyle = c; ctx.fillText(short(t, maxc), bx + 6, by + 5 + i * 15); });
    return { x: bx, y: by, w, h };
  }

  function drawBadge(r, zoomedIn) {
    if (view === 'hq' || (zoomedIn && (r.name || '_lounge') !== view)) { r.badge = null; return; }   // 안 그린 배지는 클릭도 안 받는다
    const [sx, sy] = toScreen(r.x * T, r.y * T);
    const [ex] = toScreen((r.x + r.w) * T, 0);
    const h = badgeLines(r).lines.length * 15 + 8;
    r.badge = drawCard(r, sx, Math.max(4, sy - h - 6), ex - sx);
  }

  // ── 감독실(1단) ────────────────────────────────────
  const HQ = theme.hq || {};
  function sites() { return [...world.rooms, world.lounge].filter(Boolean); }
  // 현황판 위 현장 자리(월드 타일) — 판을 현장 수로 나눈다
  function boardSlots() {
    const b = HQ.board || { x: 3, y: 0.4, w: 22, h: 5.4 };
    const ss = sites(), q = world.hq;
    return ss.map((r, i) => ({ r, x: q.x + b.x + (b.w / ss.length) * i, y: q.y + b.y, w: b.w / ss.length, h: b.h }));
  }

  // 현장 카드 — 감독실 아래에 현장마다(화면 좌표, 선명하게). 누르면 그 현장으로
  function drawHQCards() {
    const q = world.hq;
    for (const s of boardSlots()) {
      const [sx, sy] = toScreen((s.x + 0.15) * T, (q.y + q.h + 0.4) * T);
      const [ex] = toScreen((s.x + s.w - 0.15) * T, 0);
      s.r.badge = drawCard(s.r, sx, sy, ex - sx, 120, 400);
      // 현황판 위 이름 — 지도 위 땅 · 모니터 위
      const [lx, ly] = toScreen((s.x + s.w / 2) * T, (s.y + 0.35) * T);
      const st = siteState(s.r);
      ctx.font = 'bold 13px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      const tw = ctx.measureText(s.r.label).width + 10;
      ctx.fillStyle = '#000000aa'; ctx.fillRect(lx - tw / 2, ly, tw, 18);
      ctx.fillStyle = st === 'fail' ? P.bad : st === 'alert' ? P.warn : P.label;
      ctx.fillText(s.r.label + (st === 'alert' ? ' ❗' : st === 'fail' ? ' 🔥' : ''), lx, ly + 2);
    }
  }

  // 현황판 — 마법학교: 거대한 양피지 지도 + 현장마다 촛불(작업중 밝게 · 승인 대기 붉게 맥박 · 실패면 꺼지고 연기 · 쉼 작게 · 없음 꺼짐)
  function drawBoard(now) {
    const b = HQ.board || {}, q = world.hq;
    const bx = q.x + (b.x ?? 3), by = q.y + (b.y ?? 0.4), bw = b.w ?? 22, bh = b.h ?? 5.4;
    const style = b.style || 'map';
    if (style === 'map') {
      rect(bx - 0.15, by - 0.15, bw + 0.3, bh + 0.3, '#3b2a1c');
      rect(bx, by, bw, bh, '#d8c49a');
      ctx.fillStyle = '#c4ab7a';
      for (let i = 0; i < 60; i++) { const h = tileHash(i, 3); ctx.fillRect((bx + (h % 1000) / 1000 * bw) * T, (by + ((h >>> 10) % 1000) / 1000 * bh) * T, 2, 2); }
    } else {
      rect(bx - 0.15, by - 0.15, bw + 0.3, bh + 0.3, style === 'monitors' ? '#11141a' : '#8a8f99');
      rect(bx, by, bw, bh, style === 'monitors' ? '#1b2230' : '#eef1f4');
    }
    boardSlots().forEach((s, i) => {
      const state = siteState(s.r);
      const cx = s.x + s.w / 2, top = s.y;
      if (style === 'map') {
        // 땅 모양 — 현장마다 다른 섬(해시로 정한 울퉁불퉁한 다각형) + 길
        ctx.fillStyle = ['#a9b97a', '#c9a46a', '#9fb0b8', '#b59ac0'][i % 4];
        ctx.beginPath();
        for (let k = 0; k < 12; k++) {
          const ang = (k / 12) * Math.PI * 2, rr = 0.75 + ((tileHash(i, k) % 100) / 100) * 0.35;
          const px = (cx + Math.cos(ang) * rr * s.w * 0.36) * T, py = (top + 2.3 + Math.sin(ang) * rr * 1.5) * T;
          k ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
        }
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = '#6b4f33'; ctx.lineWidth = 1; ctx.stroke();
        if (i) { ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo((s.x - s.w * 0.15) * T, (top + 2.3) * T); ctx.lineTo((s.x + s.w * 0.15) * T, (top + 2.3) * T); ctx.stroke(); ctx.setLineDash([]); }
        drawSiteCandle(cx, top + 3.3, state, now, i);
      } else if (style === 'monitors') {
        // 모니터 하나 — 어두운 화면, 위 띠가 상태 색(이상이면 깜빡), 안에 작업중 칸 · 토큰 막대 · 아이콘
        const c = { fail: P.bad, alert: P.warn, busy: P.act, idle: P.ok, empty: '#3a4356' }[state];
        const st = s.r.stats || {};
        rect(s.x + 0.4, top + 0.5, s.w - 0.8, bh - 1.4, '#0c0f15');
        rect(s.x + 0.6, top + 0.7, s.w - 1.2, bh - 1.8, state === 'empty' ? '#121722' : '#0f1a2a');
        ctx.globalAlpha = state === 'alert' || state === 'fail' ? 0.55 + 0.45 * Math.sin(now / 250) : 1;
        rect(s.x + 0.6, top + 0.7, s.w - 1.2, 0.35, c);
        if (state === 'alert' || state === 'fail') { ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.strokeRect((s.x + 0.6) * T, (top + 0.7) * T, (s.w - 1.2) * T, (bh - 1.8) * T); }
        ctx.globalAlpha = 1;
        if (state !== 'empty') {
          for (let k = 0; k < Math.min(8, (st.ACTIVE || 0) + (st.IDLE || 0)); k++)   // 사람 칸 — 작업중은 밝게, 쉼은 어둡게
            rect(s.x + 0.9 + k * 0.55, top + 1.5, 0.4, 0.4, k < (st.ACTIVE || 0) ? P.act : '#3a4a66');
          const tok = Math.min(1, Math.log10(1 + (st.tout || 0)) / 6);
          rect(s.x + 0.9, top + 2.3, (s.w - 1.8) * tok, 0.25, '#5dd39e');                // 오늘 출력 토큰(로그 눈금)
          ctx.fillStyle = '#5dd39e55';
          for (let k = 0; k < 10; k++) { const v = (tileHash(k, i) % 100) / 100; ctx.fillRect((s.x + 0.9 + k * (s.w - 1.8) / 10) * T, (top + bh - 1.2 - v * 1.2) * T, 2, v * 1.2 * T); }
          if (state === 'alert') { ctx.fillStyle = P.warn; ctx.font = 'bold 12px ui-monospace, monospace'; ctx.textAlign = 'right'; ctx.fillText('!', (s.x + s.w - 0.9) * T, (top + 1.9) * T); }
          if (state === 'fail') { ctx.fillStyle = P.bad; ctx.font = 'bold 12px ui-monospace, monospace'; ctx.textAlign = 'right'; ctx.fillText('✕', (s.x + s.w - 0.9) * T, (top + 1.9) * T); }
        }
      } else {
        // 화이트보드 + 자석(현장마다) — 이상이면 빨간 자석
        const c = { fail: '#e03b2f', alert: '#e03b2f', busy: '#2f7de0', idle: '#2fae5a', empty: '#9aa0a8' }[state];
        ctx.strokeStyle = '#7d8590'; ctx.lineWidth = 1;
        for (let k = 0; k < 4; k++) { ctx.beginPath(); ctx.moveTo((s.x + 0.4) * T, (top + 1 + k) * T); ctx.lineTo((s.x + s.w - 0.4) * T, (top + 1 + k) * T); ctx.stroke(); }
        // 공정 막대(현장마다 고정 모양) — 손으로 그린 공정표 느낌
        for (let k = 0; k < 3; k++) {
          const hsh = tileHash(i * 5 + k, 9), len = 0.3 + (hsh % 60) / 100, st0 = ((hsh >>> 8) % 30) / 100;
          ctx.fillStyle = ['#7fb7ff', '#f2c14e', '#9fd8a8'][k] + 'cc';
          ctx.fillRect((s.x + 0.5 + st0 * (s.w - 1)) * T, (top + 1.15 + k) * T, len * (s.w - 1.6) * T, 5);
        }
        ctx.fillStyle = c; ctx.beginPath(); ctx.arc((s.x + s.w - 0.9) * T, (top + 1.4) * T, 5 + (state === 'alert' ? Math.sin(now / 200) * 1.5 : 0), 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#333'; ctx.stroke();
        // 사람마다 자석 — 작업중 파랑 · 쉼 초록 · 멈춤 회색, 승인 대기는 빨강
        const st = s.r.stats || {};
        const mags = [...Array(Math.min(st.pending || 0, 4)).fill('#e03b2f'), ...Array(st.ACTIVE || 0).fill('#2f7de0'), ...Array(st.IDLE || 0).fill('#2fae5a'),
                      ...Array((st.SUSPENDED || 0) + (st.DORMANT || 0)).fill('#9aa0a8')].slice(0, 10);
        mags.forEach((mc, k) => { ctx.fillStyle = mc; ctx.beginPath(); ctx.arc((s.x + 0.8 + k * 0.6) * T, (top + 4.2) * T, 3.5, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = '#0006'; ctx.stroke(); });
      }
      s.hit = { x: s.x, y: s.y, w: s.w, h: bh };
    });
  }

  function drawSiteCandle(x, y, state, now, i) {
    const t = now / 1000;
    // 촛대 · 초
    ctx.fillStyle = '#7a5a2e'; ctx.fillRect(x * T - 5, y * T + 6, 10, 2);
    ctx.fillStyle = state === 'fail' ? '#9a948a' : '#efe6cf'; ctx.fillRect(x * T - 2, y * T - 2, 4, 8);
    if (state === 'empty') return;                                   // 아무도 없다 — 꺼져 있다
    if (state === 'fail') {                                          // 꺼졌다 — 연기 한 줄
      for (let k = 0; k < 3; k++) {
        const p = ((t * 0.6) + k / 3) % 1;
        ctx.globalAlpha = 0.5 * (1 - p); ctx.fillStyle = '#5b5560';
        ctx.beginPath(); ctx.arc(x * T + Math.sin(p * 7 + i) * 2, y * T - 4 - p * 14, 1.5 + p * 2.5, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;
      return;
    }
    const red = state === 'alert';
    const big = state === 'busy' || red;
    const flick = Math.sin(t * 11 + i * 2) * 0.5 + Math.sin(t * 17 + i) * 0.3;
    const size = big ? 1 : 0.55;
    const col = red ? '#ff4b3a' : '#ffb347';
    glow(x * T, (y - 0.35) * T, (big ? 26 : 12) * (red ? 0.9 + 0.25 * Math.sin(t * 5) : 1), col, big ? 0.45 : 0.25);
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.ellipse(x * T, y * T - 5 * size - 2, 2.2 * size + 0.6, (5 + flick) * size, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = red ? '#ffd0c8' : '#fff3c0';
    ctx.beginPath(); ctx.ellipse(x * T, y * T - 3 * size - 2, 1 * size, 2.5 * size, 0, 0, Math.PI * 2); ctx.fill();
  }

  function drawHQS(now, sorted) {
    const q = world.hq;
    drawFloor(q.x + 1, q.y + 2, q.w - 2, q.h - 3, (HQ.floor && ((RS.proc && RS.proc[HQ.floor]) || HQ.floor)) || FLOOR, 5);
    drawWalls(q);
    for (const d of HQ.decor || []) if (d.s || d.fx) placeDecor(d, q.x, q.y, now, sorted);
    drawBoard(now);
  }

  function drawHQShapes(now) {
    const q = world.hq;
    for (let i = 0; i < q.w; i++) for (let j = 0; j < q.h; j++) rect(q.x + i, q.y + j, 1, 1, (i + j) % 2 ? P.office : '#3f3a56');
    ctx.strokeStyle = P.officeGlass; ctx.lineWidth = 3; ctx.strokeRect(q.x * T, q.y * T, q.w * T, q.h * T);
    rect(q.x + 11, q.y + 9, 6, 1.2, P.deskTop); rect(q.x + 11, q.y + 10.2, 6, 0.3, P.desk);
    rect(q.x + 12.3, q.y + 8.4, 1.2, 0.8, '#1b1f27'); rect(q.x + 14.5, q.y + 8.4, 1.2, 0.8, '#1b1f27');   // 듀얼 모니터
    drawBoard(now);
  }

  // ── 머리말 · 정보 패널 ──────────────────────────────
  function header(st) {
    const c = st.conn;
    $('oConn').className = 'conn ' + c.status;
    $('oConn').textContent = { up: '연결됨', down: '끊김', connecting: '연결 중', auth: '토큰 필요', idle: '연결 전' }[c.status] || c.status;
    const pend = [...st.approvals.values()].filter((a) => a.status === 'pending').length;
    const ig = st.ingest;
    // 전체 요약(클래식 머리말과 같은 숫자) + 적재가 막히면 무엇이 막혔는지(마우스를 올리면)
    let active = 0, live = 0, outToday = 0, subs = 0;
    for (const s of st.sessions.values()) {
      if (s.state === 'ACTIVE') active++;
      if (s.state !== 'DORMANT') live++;
      outToday += (s.tokens && s.tokens.today_output) || 0;
      subs += s.subagents_running || 0;
    }
    const igWhy = !ig ? '' : ig.stalled ? `트랜스크립트 감시 루프가 ${ig.tick_age_s}초째 돌지 않는다`
      : (ig.stuck || []).map((x) => `${x.session} ${x.minutes}분 · ${x.failures}번 — ${x.error}`).join('\n');
    $('oAlerts').innerHTML = (pend ? `<button id="oPend" class="ghost warn" title="패널에서 승인 · 거부">❗ 승인 대기 ${pend}</button>` : '') +
      (ig && !ig.ok ? `<span class="bad" title="${esc(igWhy)}">⚠ ${ig.stalled ? '와처 멈춤' : `적재 막힘 ${(ig.stuck || []).length}개 세션`}</span>` : '') +
      `<span class="small muted">작업 중 <b>${active}</b>/${live}${subs ? ` · 서브 ${subs}` : ''} · 오늘 출력 ${fmt(outToday)}</span>`;
    $('oMap').disabled = view === 'hq';
    $('oAll').disabled = view === 'map';
    // 연결 끊김 — 캔버스를 가리지 않는 띠 + 캔버스를 흐리게(보이는 모습이 끊기기 전 것이라는 표시)
    const down = c.status === 'down';
    $('oDown').hidden = !down;
    $('oStage').classList.toggle('offline', down || c.status === 'auth');
    if (down) {
      $('oDownWhy').textContent = `${c.reason || '브리지와 연락이 없다'} — ${new Date(c.since).toLocaleTimeString()}부터`;
      $('oDownNext').textContent = c.nextIn ? `${c.nextIn}초 뒤 다시 연결 (시도 ${c.attempt})` : `연결 중… (시도 ${c.attempt})`;
    }
    if (c.status === 'auth') $('tokDlg').classList.add('on');
  }

  // 고른 캐릭터를 패널에 알린다 — 세션은 store.select(대화를 불러온다), 서브에이전트는 부모 세션, 인프라 · 포먼은 파이프라인 · 세션 목록
  function info() {
    const a = selected && actors.get(selected);
    if (!a) return;
    const owner = a.kind === 'mini' ? actors.get(a.parent) : a;
    if (owner && owner.kind === 'session') {
      if (store.state.selected !== owner.s.id) store.select(owner.s.id);
      panel.show({ kind: 'session' });
    } else if (a.kind === 'infra') {
      const r = world.rooms.find((q) => q.name === a.room), st = r ? r['st_' + a.infra] : 'none';
      panel.show({ kind: 'infra', room: a.room, infra: a.infra, name: a.name, status: STATUS_KO[st] || st });
    } else if (a.kind === 'foreman') {
      panel.show({ kind: 'foreman', room: a.room === '_hq' ? null : a.room });
    }
  }
  // 패널(승인 카드의 "세션" · 세션 목록)에서 고르면 그 현장으로 가서 캐릭터를 고른다
  function openSession(sid) {
    const key = 's:' + sid, a = actors.get(key);
    if (a && view !== a.room) { view = a.room || '_lounge'; aim(); header(store.state); }
    selected = a ? key : null;
    store.select(sid);
    panel.show({ kind: 'session' });
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
    if (view === 'hq') {                                   // 현황판의 현장 자리를 눌러도 들어간다
      const s = boardSlots().find((b) => wx >= b.x * T && wx <= (b.x + b.w) * T && wy >= b.y * T && wy <= (b.y + b.h) * T);
      if (s) { go(s.r.name || '_lounge'); return; }
    }
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
    if (!best) return;                   // 빈 바닥을 눌러도 패널은 그대로(입력하던 것을 잃지 않게). 해제는 패널의 ✕
    selected = best;
    info();
  });
  // ── 마우스를 올리면(11-05) — 이름표는 그 구역이 하는 일, 캐릭터는 이름 · 지금 하는 일. 누르지 않아도 보인다 ──
  function actorAt(wx, wy) {
    let best = null, bd = 1.4 * T;
    for (const [k, a] of actors) {
      if (view !== 'map' && a.room !== (view === '_lounge' ? null : view) && !(view === 'hq' && a.room === '_hq')) continue;
      const d = Math.hypot(a.x * T - wx, a.y * T - 8 - wy);
      if (d < bd) { bd = d; best = a; }
    }
    return best;
  }
  function actorTip(a) {
    const roleKey = (r) => ((theme.tags && theme.tags.roles) || {})[r];
    const zoneName = (go) => {                     // 지금 가 있는 구역의 이름표 · 하는 일
      const key = go === 'desk' ? 'desks' : go;
      const v = ((theme.tags && theme.tags.zones) || {})[key];
      const nm = Array.isArray(v) ? v[0] : v;
      const role = ZONE_ROLE[roleKey(key)];
      return nm ? `${esc(nm)}${role ? ` — ${esc(role.what)}` : ''}` : '';
    };
    if (a.kind === 'session' && a.s) {
      const s = a.s;
      const now = s.state === 'ACTIVE' ? (s.activity ? `${esc(s.activity.tool)} ${esc(short(s.activity.target || '', 70))}` : '생각 중') : '';
      return `<div class="otip-h">${esc(a.name)}</div><b>${esc({ ACTIVE: '작업 중', IDLE: '쉬는 중', SUSPENDED: '멈춤', DORMANT: '종료' }[s.state] || s.state)}</b>${
        a.act && a.act.go ? ` · ${zoneName(a.act.go)}` : ''}${now ? `<div>${now}</div>` : ''}${
        s.subagents_running ? `<div>서브에이전트 ${s.subagents_running}개 돎</div>` : ''}${
        a.act && a.act.flag ? `<div class="otip-s">${esc({ approval_pending: '승인 대기', stuck_turn: '끝 신호 없는 턴' }[a.act.flag] || a.act.flag)}</div>` : ''}
        <div class="otip-t">누르면 대화 · 입력</div>`;
    }
    if (a.kind === 'mini') return `<div class="otip-h">서브에이전트</div><div>${esc(a.name)}</div><div class="otip-t">누르면 부모 세션</div>`;
    if (a.kind === 'infra') {
      const r = world.rooms.find((q) => q.name === a.room), st = r ? r['st_' + a.infra] : 'none';
      return `<div class="otip-h">${esc(a.name)}</div>${tipOf(INFRA_ROLE[a.infra])}<div class="otip-s">지금: ${esc(STATUS_KO[st] || st)}</div>`;
    }
    if (a.kind === 'foreman') return `<div class="otip-h">포먼</div>${tipOf(ZONE_ROLE.hq)}<div class="otip-t">자기 세션은 아직 없다(11단계)</div>`;
    return `<div class="otip-h">${esc(a.name || '')}</div>`;
  }
  const tipEl = $('oTip');
  cv.addEventListener('mousemove', (ev) => {
    const r = cv.getBoundingClientRect();
    const px = ev.clientX - r.left, py = ev.clientY - r.top;
    const hit = HITS.find((h) => px >= h.x && px <= h.x + h.w && py >= h.y && py <= h.y + h.h);
    let html = hit ? hit.tip : null, onActor = false;
    if (!html && view !== 'map') {
      const [wx, wy] = toWorld(px, py);
      const a = actorAt(wx, wy);
      if (a) { html = actorTip(a); onActor = true; }
    }
    cv.style.cursor = onActor ? 'pointer' : '';
    if (!html) { tipEl.hidden = true; return; }
    if (tipEl.innerHTML !== html) tipEl.innerHTML = html;
    tipEl.hidden = false;
    const sw = cv.clientWidth, tw = tipEl.offsetWidth, th = tipEl.offsetHeight;
    tipEl.style.left = Math.min(px + 14, sw - tw - 6) + 'px';
    tipEl.style.top = (py + 18 + th > cv.clientHeight ? py - th - 10 : py + 18) + 'px';
  });
  cv.addEventListener('mouseleave', () => { tipEl.hidden = true; cv.style.cursor = ''; });
  // 현장을 옮겨도 고른 세션 · 패널은 그대로 둔다
  function go(v) { view = v; aim(); header(store.state); }
  $('oMap').onclick = () => go('hq');
  $('oAll').onclick = () => go('map');
  window.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    if (ev.target.closest && ev.target.closest('input, textarea, select')) return;   // 입력 칸에서 친 Esc는 칸이 처리
    if ($('tokDlg').classList.contains('on')) { $('tokDlg').classList.remove('on'); return; }
    go('hq');
  });
  $('oAlerts').addEventListener('click', (ev) => { if (ev.target.closest('#oPend')) panel.setOpen(true); });
  $('oRetry').onclick = () => store.retryNow();
  $('oTok').onclick = () => { $('tokDlg').classList.add('on'); $('tokInput').focus(); };
  $('tokCancel').onclick = () => $('tokDlg').classList.remove('on');
  $('tokInput').oninput = () => { const n = $('tokInput').value.trim().replace(/^FOREMAN_API_TOKEN=/, '').length; $('tokLen').textContent = n ? `길이 ${n}` : ''; };
  $('tokForm').onsubmit = (ev) => {
    ev.preventDefault();
    store.token = $('tokInput').value;
    $('tokInput').value = '';
    $('tokDlg').classList.remove('on');
    store.start();
  };
  // 패널 · 터미널이 펴지고 접히면 무대 크기가 바뀐다 — 창 크기만 보지 않고 무대를 직접 본다
  new ResizeObserver(() => resize()).observe($('oStage'));
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    running = !document.hidden;
    if (running) { last = performance.now(); requestAnimationFrame(frame); }
  });

  resize();
  store.subscribe(rebuild);
  requestAnimationFrame(frame);
  return { go, theme, openSession, panel, actors, debug: () => [...actors.values()].map((a) => ({ key: a.key, room: a.room, x: String(a.x), y: String(a.y), tx: a.tx, ty: a.ty,
                                                                       anim: a.act && a.act.anim, go: a.act && a.act.go, face: a.face, dir: a.dir, char: a.char })) };
}

function hueOf(id) { return (id * 47) % 360; }
function short(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
