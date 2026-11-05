// FOREMAN 픽셀 오피스 — 테마 렌더러(10단계). store.js(데이터)는 그대로, 이 파일은 그리기만.
// 10a: 지도 ↔ 방 줌, 도형 캐릭터, 상태별 모습, 방 배지(작업 · 승인 · 파이프라인 · 토큰). 동작은 theme.json이 정한다(theme.js).
// 좌표: 월드는 타일 단위로 정하고 px = 타일 × layout.tile. 카메라가 월드 → 화면.

import { resolveAction, infraAction, groupSubagents, tokenRate, viewState } from './theme.js';
import { loadSprites } from './sprites.js';
import { createSidePanel } from './opanel.js';
import { mountNewSession } from './newsession.js';
import { showTip, hideTip, themeTips, attachDomTips } from './tip.js';
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
      <button id="oMap" class="ghost" title="감독실 — 현장 전체를 보는 곳으로 갑니다. Esc로도 갑니다.">${esc((theme.hq && theme.hq.label) || '감독실')}</button>
      <button id="oAll" class="ghost" title="전체 — 모든 현장을 한 화면에 봅니다.">전체</button>
      <nav id="oProj" class="oproj" aria-label="프로젝트"></nav>
      <button id="oNew" class="ghost onew" title="새 세션 — 프로젝트나 폴더를 골라 새 세션을 띄웁니다.">＋ 세션</button>
      <span id="oAlerts" class="oalerts"></span>
      <span class="small muted otheme">테마 ${[['office', '오피스'], ['magic', '마법학교'], ['site', '현장'], ['plain', '도형']].map(([k, v]) => k === theme.name ? `<b>${v}</b>` : `<a href="/?theme=${k}">${v}</a>`).join(' · ')}</span>
      <a class="small" href="/classic" title="클래식 — 카드 목록 화면으로 갑니다.">클래식</a>
      <span id="oConn" class="conn"></span>
      <button id="oTok" class="ghost" title="토큰 — API 토큰을 다시 넣습니다.">토큰</button>
    </header>
    <div class="obody">
      <div id="oStage" class="ostage"><canvas id="oCv"></canvas>
        <div id="oDown" class="odown" role="alert" aria-live="assertive" hidden>
          <b>⚠ 서버 연결 끊김</b> <span id="oDownWhy" class="small"></span> <span id="oDownNext" class="small muted"></span>
          <button id="oRetry" class="small">지금 다시 연결</button>
          <div class="small muted">화면의 캐릭터는 끊기기 전 상태입니다. 다시 연결되면 맞춥니다.</div>
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
  // 서기 머리 위 "할 일 N"(12a) — 방(프로젝트) → {items:[{kind, title, why}]}. 브리지가 LLM 없이 센다(/api/scribe/todo)
  const scribeTodo = new Map();
  async function loadScribeTodo() {
    try {
      const r = await fetch('/api/scribe/todo', { headers: store.headers() });
      if (!r.ok) return;
      const j = await r.json();
      scribeTodo.clear();
      for (const [k, v] of Object.entries(j.projects || {})) scribeTodo.set(k, v);
    } catch { /* 못 읽으면 배지만 안 뜬다 */ }
  }
  loadScribeTodo();
  setInterval(loadScribeTodo, 60000);
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

  // ── 출하 라인 — 배송 담당 한 명(11-05) ─────────────────
  // 평소엔 라인 맨 앞 자기 자리. 새 빌드가 보이면 그 커밋을 한 세션 캐릭터가 걸어와 일감을 넘기고(6초), 배송 담당이
  // ① 빌드 → ② 이미지 → ③ 배포 중 지금 단계 앞으로 걸어간다. 끝나면(성공) 배포 앞에 잠깐 있다가 제자리, 실패면 그 단계에 30분.
  // 한 방에 빌드가 여럿이면 가장 오래된 진행 중인 것을 맡고 나머지는 자기 자리 옆 "대기 n". 방마다 따로.
  const COURIER = { seen: new Set(), primed: false, handoff: new Map(), timers: new Map() };
  const HANDOFF_MS = 6000, DONE_LINGER_MS = 25000, FAIL_STAY_MS = 30 * 60000;
  function chainStage(ch) {
    const s = ch.stages || {}, j = s.jenkins || {}, a = s.argocd || {};
    const pushy = /push|harbor|이미지/i.test(j.step || '');
    if (a.status === 'running' || a.status === 'waiting') return { k: 'argocd', st: a.status, active: true };
    if (a.status === 'failed') return { k: 'argocd', st: 'failed', end: Date.parse(a.ended_at || ch.at) };
    if (a.status === 'success') return { k: 'argocd', st: 'success', end: Date.parse(a.ended_at || ch.at) };
    if (j.status === 'running') return { k: pushy ? 'harbor' : 'jenkins', st: 'running', active: true };
    if (j.status === 'failed') return { k: pushy ? 'harbor' : 'jenkins', st: 'failed', end: Date.parse(j.ended_at || ch.at) };
    if (j.status === 'success') {                          // 이미지가 올라갔고 배포를 기다린다 — 30분까지는 진행 중으로 본다
      const end = Date.parse(j.ended_at || ch.at);
      return Date.now() - end < FAIL_STAY_MS ? { k: 'harbor', st: 'running', active: true } : { k: 'harbor', st: 'success', end };
    }
    return null;
  }
  function courierPlan(room, pp) {
    const chains = (pp && pp.chains) || [], now = Date.now();
    for (const ch of chains) {
      if (COURIER.seen.has(ch.head)) continue;
      COURIER.seen.add(ch.head);
      const sid = ch.commits && ch.commits[0] && ch.commits[0].session_id;
      if (COURIER.primed && sid) {                         // 새 빌드 — 커밋한 세션이 일감을 넘기러 온다
        COURIER.handoff.set(room.name, { sid, until: now + HANDOFF_MS });
        laterRebuild(room.name, HANDOFF_MS + 50);
      }
    }
    const staged = chains.map((ch) => ({ ch, s: chainStage(ch) })).filter((x) => x.s);
    // 진행 중으로 보는 것 — 2시간 안에 시작했고, 더 새 빌드(chains는 최신이 앞)가 그 단계를 아직 끝내지 않은 것만.
    // 끝 알림이 영영 안 온 옛 행이 "배포 진행 중"으로 남아 담당을 붙잡던 것(11-05)을 화면에서도 막는다
    const STALE_MS = 2 * 3600000;
    const active = staged.filter((x, i) => {
      if (!x.s.active) return false;
      const st = (x.ch.stages || {})[x.s.k === 'harbor' ? 'jenkins' : x.s.k] || {};
      if (Date.now() - Date.parse(st.started_at || x.ch.at || 0) > STALE_MS) return false;
      return !staged.slice(0, i).some((y) => y.s.k === x.s.k && !y.s.active);
    });
    const ho = COURIER.handoff.get(room.name);
    const handing = ho && now < ho.until ? ho : null;
    let at = null, st = 'none', ch = null;
    if (active.length) { const x = active[active.length - 1]; at = x.s.k; st = x.s.st; ch = x.ch; }   // chains는 최신이 앞 — 가장 오래된 것
    else if (staged.length) {
      const x = staged[0];
      if (x.s.st === 'failed' && now - x.s.end < FAIL_STAY_MS) { at = x.s.k; st = 'failed'; ch = x.ch; laterRebuild(room.name, FAIL_STAY_MS - (now - x.s.end) + 50); }
      else if (x.s.st === 'success' && now - x.s.end < DONE_LINGER_MS) { at = x.s.k; st = 'success'; ch = x.ch; laterRebuild(room.name, DONE_LINGER_MS - (now - x.s.end) + 50); }
    }
    if (handing) at = null;                                // 일감을 받는 동안은 제자리
    return { at, st, ch, handing, queue: active.slice(0, -1).map((x) => x.ch) };
  }
  const STAGE_KO = { jenkins: '① 빌드', harbor: '② 이미지', argocd: '③ 배포' };
  function courierNow(p) {
    if (!p) return '쉬는 중';
    if (p.handing) return '일감 받는 중';
    if (!p.at) return '쉬는 중 — 진행 중인 빌드 없음';
    return `${STAGE_KO[p.at]} ${({ running: '진행 중', waiting: 'Sync 대기', success: '✓ 끝', failed: '✗ 실패' })[p.st] || ''}`;
  }
  function laterRebuild(key, ms) {
    clearTimeout(COURIER.timers.get(key));
    COURIER.timers.set(key, setTimeout(() => store.touch('grid'), Math.min(ms, 2 ** 31 - 1)));
  }
  // 출하 라인 전용 자리(11-05) — 구조물 바로 앞(발밑보다 아래)에 못 박은 칸. theme.layout.zones.infra.stands(방 좌표):
  // { jenkins:[x,y], harbor:[x,y], argocd:[x,y], home:[x,y] }. 그 칸엔 가구를 두지 않는다(window.office.audit()가 확인)
  const HANDOFF_DX = 1.3;
  function stageStand(room, k) {
    const z = L.zones.infra, s = z.stands && z.stands[k];
    return s ? [room.x + s[0], room.y + s[1]] : [room.x + z[k].x + 3, room.y + z.y + 2];
  }
  function courierHome(room) {
    const z = L.zones.infra, s = z.stands && z.stands.home;
    return s ? [room.x + s[0], room.y + s[1]] : [room.x + Math.max(0.8, z.jenkins.x - 0.6), room.y + z.y + 2.3];
  }

  const DORMANT_SHOW_MS = 3 * 60000;
  function dormantGone(s, roomName) {
    if (s.state !== 'DORMANT') return false;
    const end = Date.parse(s.detached_at || s.last_ts || 0) || 0;
    const left = end + DORMANT_SHOW_MS - Date.now();
    if (left > 0) laterRebuild('dormant:' + roomName + ':' + s.id, left + 100);   // 3분이 지나면 다시 그려 지운다
    return left <= 0;
  }

  function rebuild(st) {
    world = rooms(st);
    const pending = new Map();
    for (const a of st.approvals.values()) if (a.status === 'pending' && a.session_id != null) pending.set(a.session_id, (pending.get(a.session_id) || 0) + 1);
    const seen = new Set();
    for (const room of [...world.rooms, world.lounge]) {
      const plan = !room.lounge && L.zones.infra ? courierPlan(room, st.pipeline.get(room.name)) : null;
      room.courier = plan;
      // 세션 — 깨어 있는 것 먼저 자리를 준다. 자리가 모자라면 배지에 "+N"
      const ss = room.sessionIds.map((id) => st.sessions.get(id)).filter(Boolean);
      ss.sort((a, b) => (a.state === 'DORMANT') - (b.state === 'DORMANT') || a.id - b.id);
      const cap = seatCount(room);
      // 끝난 세션(DORMANT)은 끝나고 3분 동안만 흐리게 자리에 남았다가 화면에서 사라진다(11-05 사용자 요청).
      // 패널 세션 목록의 "종료된 세션"에는 그대로 있다 — 거기서 골라 [새로 띄우기]. 멈춘 세션(SUSPENDED)은 그대로 보인다
      const shown = ss.filter((s) => !dormantGone(s, room.name));
      room.overflow = Math.max(0, shown.length - cap);
      room.stats = { ACTIVE: 0, IDLE: 0, SUSPENDED: 0, DORMANT: 0, pending: 0, subs: 0, tin: 0, tout: 0, opus_out: 0, all_out: 0 };
      let slot = 0;
      ss.forEach((s) => {
        // 기다림(IDLE + 자식 일)은 작업으로 센다 — 현장이 "쉼"으로 보이면 돌고 있는 일을 놓친다(11-06)
        const vs = viewState(s) === 'WAITING' ? 'ACTIVE' : s.state;
        room.stats[vs] = (room.stats[vs] || 0) + 1;
        room.stats.pending += pending.get(s.id) || 0;
        room.stats.subs += s.subagents_running || 0;
        room.stats.tin += (s.tokens && s.tokens.today_input) || 0;
        room.stats.tout += (s.tokens && s.tokens.today_output) || 0;
        // 모델별은 서브에이전트까지 센다(위 tout은 본 대화만) — 비율은 모델별 합끼리 낸다
        for (const m of (s.tokens && s.tokens.by_model) || []) {
          room.stats.all_out += m.today_output || 0;
          if (m.family === 'opus') room.stats.opus_out += m.today_output || 0;
        }
        if (dormantGone(s, room.name)) return;
        const k = slot++;
        if (k >= cap) return;
        let act = resolveAction(theme, { state: viewState(s), role: roleOf(s), tool: s.activity && s.activity.tool, target: s.activity && s.activity.target,
                                         flags: { approval_pending: pending.has(s.id), stuck_turn: !!s.stuck_turn } });
        // 쉬는 모습은 사람마다 다르게(마법학교: 엎드려 자기 · 먹기 · 책) — 플래그가 덮은 동작은 그대로
        if (act.variants && !act.flag) act = { ...act, anim: act.variants[s.id % act.variants.length] };
        // 서기(12a) — 서기실 안에서만 움직인다. 일할 때 도구에 따라 쓰기(Edit · Write) · 서가(Read · Grep) · 대조대(Bash),
        // 쉬거나 기다릴 때는 쓰기 자리. 승인 대기 같은 플래그는 그대로 둔다
        let seatK = k;
        const sz = L.zones.scribe;
        if (roleOf(s) === 'scribe' && sz && !act.flag) {
          const vs = viewState(s);
          if (vs === 'ACTIVE') {
            const t = (s.activity && s.activity.tool) || '';
            seatK = /^(Read|Grep|Glob|WebFetch|WebSearch)$/.test(t) ? 1 : /^(Bash|Monitor)$/.test(t) ? 2 : 0;
            act = { ...act, go: 'scribe', anim: ['type', 'read', 'think'][seatK] };
          } else if (vs === 'IDLE' || vs === 'WAITING') {
            seatK = 0;
            act = { ...act, go: 'scribe', anim: vs === 'WAITING' ? 'wait' : 'read' };
            delete act.variants;
          }
        }
        const desk = seat(room, k);
        let [tx, ty, face] = spot(room, act.go, desk, act.go === 'scribe' ? seatK : k);
        if (plan && plan.handing && plan.handing.sid === s.id) {      // 새 빌드 — 배송 담당에게 일감을 넘기러 간다
          const [hx, hy] = courierHome(room);
          tx = hx + HANDOFF_DX; ty = hy; face = 'left';
          act = { ...act, anim: 'idle', handoff: true };
        }
        const key = 's:' + s.id;
        const char = CH.pool ? CH.pool[s.id % CH.pool.length] : null;
        upsert(key, { kind: 'session', room: room.name, tx, ty, face, act, desk, s, hue: hueOf(s.id), char, role: roleOf(s),
                      name: s.custom_title || s.title || s.cc_name || ('세션 ' + s.id) });
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
        // 서기(12a) — 서기실에 늘 있다. 그 방에 살아 있는 서기 세션이 있으면 그 세션 캐릭터가 대신 선다(일 → 끝나면 다시 서기실)
        const sz = L.zones.scribe;
        if (sz && sz.seats && !ss.some((s) => roleOf(s) === 'scribe' && s.state !== 'DORMANT')) {
          const p = sz.seats[0], wkey = 'w:' + room.name;
          upsert(wkey, { kind: 'scribe', room: room.name, tx: room.x + p[0], ty: room.y + p[1], face: p[2] || 'down',
                         act: { anim: 'read', go: 'scribe' }, hue: 25, name: '서기', char: (CH.pool && CH.pool[3 % CH.pool.length]) || null,
                         role: 'scribe', todo: scribeTodo.get(room.name) || null });
          seen.add(wkey);
        }
        // 출하 라인 — 단계 이름표의 상태는 배송 담당이 맡은 빌드(없으면 마지막 빌드) 것.
        // 단계마다 서 있던 Jenkins · Harbor · ArgoCD 캐릭터 대신 배송 담당 한 명이 돌아다닌다(11-05 사용자 요청)
        const pp = st.pipeline.get(room.name);
        room.pipe = pp || null;
        const chain = (plan && plan.ch) || (pp && pp.chains && pp.chains[0]);
        const stages = (chain && chain.stages) || {};
        for (const kind of ['jenkins', 'harbor', 'argocd']) {
          let status = stages[kind] && stages[kind].status;
          if (kind === 'harbor' && !status && stages.jenkins) status = stages.jenkins.status === 'failed' && stages.jenkins.step !== '빌드·push' ? 'success' : stages.jenkins.status;
          room['st_' + kind] = status || 'none';
        }
        if (plan) {
          const z = L.zones.infra, key = `c:${room.name}`;
          const [hx, hy] = courierHome(room);
          const at = plan.at;
          const [tx, ty] = at ? stageStand(room, at) : [hx, hy];
          const c = theme.courier || {};
          upsert(key, { kind: 'courier', room: room.name, tx, ty, face: 'down',
                        char: c.char || (CH.infra && (CH.infra.courier || CH.infra.jenkins)) || null,
                        act: plan.handing ? { anim: 'idle', status: 'handoff' } : at ? infraAction(theme, plan.st) : { anim: 'idle', status: 'idle' },
                        hue: 30, name: c.name || '배송 담당', plan });
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
    if (sa && (sa.kind === 'infra' || sa.kind === 'courier')) info();          // 인프라 상태가 바뀌었으면 패널 제목 줄도 바꾼다(세션은 패널이 store를 직접 본다)
    COURIER.primed = true;                        // 첫 그리기 뒤부터 새로 보이는 빌드만 "일감 넘기기"
    if (store.state.selected == null && sa && (sa.kind === 'session' || sa.kind === 'mini')) selected = null;   // 패널에서 ✕
  }

  // 역할(로브 · 사원증 끈 · 안전모 색) — 세션의 role(DB character_session.role: foreman coder inspector cicd helper).
  // 11-05 전에는 테마 이름(lead builder …)이 DB와 달라 실제 세션 색이 한 번도 맞지 않았다. 미리 보기: /office?roles=demo
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
      for (const a of list) {
        if (a.bornAt && now < a.bornAt) continue;
        // 소파 · 침대 같은 "위에 앉는" 가구에 자리 잡은 사람은 그 가구 바로 다음(가구 위에). 걸어가는 동안은 발 위치 순서
        const onIt = !a.moving && Math.abs(a.x - a.tx) < 0.05 && Math.abs(a.y - a.ty) < 0.05 && seatFurniture(a);
        sorted.push({ y: onIt ? Math.max(a.y, onIt.key) : a.y, draw: () => drawActorS(a, now) });
        const prop = propOf(a);
        if (prop) {                                                         // 그 동작의 소품 — 앞 탁자 위나 발치에 놓는다
          const tbl = Math.abs(a.x - a.tx) < 0.05 && Math.abs(a.y - a.ty) < 0.05 ? sleepTable(a) : null;
          sorted.push({ y: tbl ? tbl.key + 0.002 : (onIt ? Math.max(a.y, onIt.key) : a.y) + 0.001, draw: () => drawPropS(a, prop, tbl, now) });
        }
        const tbl = !a.moving && a.act && a.act.anim === 'sleep' && sleepTable(a);
        if (tbl) sorted.push({ y: tbl.key, draw: () => {                   // 엎드린 머리를 탁자 위에
          ctx.save(); ctx.beginPath();
          ctx.rect((a.x - 1) * T, (a.y - 2.5) * T, 2 * T, (tbl.clipBottom - a.y + 2.5) * T); ctx.clip();
          drawActorS(a, now); ctx.restore();
        } });
      }
      sorted.sort((p, q) => p.y - q.y);
      for (const it of sorted) it.draw();
      for (const r of world.rooms) overTopItems(r, list, now);       // 탁자 위 소품이 사람 앞에 그려진 자리만 사람을 덧그린다
      if (world.hq) overTopItems(world.hq, list, now, 'hq');        // 감독실(교장실 · 팀장실 · 감독 컨테이너) 탁자도
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
        `<div class="tip-h">${esc(hqName)}</div><div class="tip-b">감독실</div><div>현장마다 지금 상태를 한눈에 보는 곳입니다.</div>`);
      for (const a of list) if (a.room === '_hq') drawName(a);
    } else if (zoomedIn) {
      const room = roomByView();
      if (room && !room.lounge) { drawZoneTags(room); if (SP) overTags(room, list, now); }
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
    if (a.kind === 'infra' || a.kind === 'courier') { ctx.fillStyle = '#ff9f1c'; ctx.fillRect(x - 6, y - 1, 12, 3); }           // 안전모
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
    else if (anim === 'wait' && !act.flag) drawBubble(x, y - 6, '·'.repeat(1 + Math.floor(now / 500) % 3).padEnd(3, ' '), P.act, 7);   // 기다림
    else if (a.kind === 'scribe' && a.todo && a.todo.items && a.todo.items.length) drawBubble(x, y - 6, `할 일 ${a.todo.items.length}`, P.warn, 8);
    if (a.subHidden) drawBubble(x + 10, y + 2, `+${a.subHidden}`, P.act, 7);              // 10명 넘는 서브에이전트는 접는다
    drawCompactMark(a, x + 8, y - 4);
    const rc = roleColor(a.role);
    if (rc) { ctx.fillStyle = rc; ctx.fillRect(x - 1, y + sp.head * 1.6, 2, h - sp.head * 1.6 - 2); }   // 역할 — 사원증 끈 색
    if (a.key === selected) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - 9, y - 3, 18, h + 6); }
  }

  // ── 시트 테마 그리기(10d) ────────────────────────────
  const RS = (SP && theme.sprites.room) || {};
  function tileHash(i, j) { return ((i * 73856093) ^ (j * 19349663)) >>> 0; }

  function spriteBottom(name, y) { const [, h] = SP.size(name); return y + h / T; }

  // ── 자리 점검(11-05, 디버그) — 캐릭터가 서는 모든 자리에서 가구가 사람 윗몸(머리 · 가슴)을 덮는지, 자리가 가구 발밑 안인지.
  // 화면 시험이 window.office.audit()으로 부른다. 앉은 자리에서 책상이 다리를 가리는 것은 정상(윗몸만 본다)
  function standSpots() {
    const out = [], z = L.zones;
    for (const [name, zz] of Object.entries(z)) {
      if (!zz || name === 'infra' || name === 'lounge_seats') continue;
      if (zz.seats) zz.seats.forEach((s, i) => out.push({ where: `${name}#${i}`, x: s[0], y: s[1] }));
      if (zz.stand) out.push({ where: `${name}.stand`, x: zz.stand[0], y: zz.stand[1] });
      if (zz.seat) out.push({ where: `${name}.seat`, x: zz.seat[0], y: zz.seat[1] });
    }
    if (z.infra) {
      for (const k of ['jenkins', 'harbor', 'argocd']) { const [x, y] = stageStand({ x: 0, y: 0 }, k); out.push({ where: `infra.${k}`, x, y }); }
      const [hx, hy] = courierHome({ x: 0, y: 0 });
      out.push({ where: 'infra.home', x: hx, y: hy }, { where: 'infra.handoff', x: hx + HANDOFF_DX, y: hy });
    }
    return out;
  }
  // where: 'room'(방 가구 + 출하 라인, 방 좌표) · 'hq'(감독실 가구, 감독실 좌표)
  function decorRects(where = 'room') {
    const out = [], iz = L.zones.infra;
    const add = (d, ox, oy, src) => {
      if (!d.s || d.fx || d.z === 'wall' || d.z === 'floor') return;
      const [w, h] = sizeT(d);
      for (let i = 0; i < (d.n || 1); i++) {
        const x = ox + d.x + i * (d.dx || 1), y = oy + d.y;
        const top = d.z === 'top';
        const key = top ? oy + topKey(d) : y + h - 0.01;
        out.push({ s: d.s, src, d, ox, oy, x, y, w, h, key, top, host: top ? d._host : null,
                   hostTop: top && d._hostTop != null ? oy + d._hostTop : null,
                   foot: top ? null : footprint({ ...d, x, y }, w, h) });
      }
    };
    if (where === 'hq') { for (const d of HQ.decor || []) add(d, 0, 0, 'hq'); return out; }
    for (const d of theme.sprites.decor || []) add(d, 0, 0, 'decor');
    if (iz) for (const k of ['jenkins', 'harbor', 'argocd']) for (const d of (theme.sprites.infra_decor || {})[k] || []) add(d, iz[k].x, iz.y, 'infra.' + k);
    return out;
  }
  // 한 점(방 좌표)에 사람이 서면 — 윗몸 · 머리가 가려지는 비율, 가구 발밑 안인가. 자리를 고를 때 쓴다
  function probe(x, y) {
    const rects = decorRects();
    let body = 0, head = 0, inFoot = false;
    for (const r of rects) {
      const f = r.foot;
      if (f && x > f[0] - 0.15 && x < f[0] + f[2] + 0.15 && y > f[1] - 0.1 && y < f[1] + f[3] + 0.1) inFoot = true;
      if (r.key <= y) continue;
      const cov = (bx, by, bw, bh) => Math.max(0, Math.min(bx + bw, r.x + r.w) - Math.max(bx, r.x)) * Math.max(0, Math.min(by + bh, r.y + r.h) - Math.max(by, r.y)) / (bw * bh);
      body = Math.max(body, cov(x - 0.4, y - 1.6, 0.8, 0.85));
      head = Math.max(head, cov(x - 0.35, y - 1.6, 0.7, 0.5));
    }
    return { body: +body.toFixed(2), head: +head.toFixed(2), inFoot };
  }
  // 소품이 사람 앞에 그려지는 부분 — 소품 칸 ∩ 사람 몸 ∩ 받침 윗면 선 위쪽(아래쪽은 원래 탁자가 사람을 가린다). [x, y, w, h] | null
  function topOverlap(r, px, py) {
    const x0 = Math.max(px - 0.45, r.x), x1 = Math.min(px + 0.45, r.x + r.w);
    const y0 = Math.max(py - 1.6, r.y), y1 = Math.min(py, r.y + r.h, r.hostTop != null ? r.hostTop : Infinity);
    return x1 - x0 > 0.05 && y1 - y0 > 0.05 ? [x0, y0, x1 - x0, y1 - y0] : null;
  }
  function audit() {
    const issues = [];
    const check = (spots, rects) => {
      for (const p of spots) {
        const body = [p.x - 0.4, p.y - 1.6, 0.8, 0.85];               // 윗몸(머리 · 가슴)
        for (const r of rects) {
          if (r.top) continue;                                        // 소품은 아래에서 따로
          const ix = Math.min(body[0] + body[2], r.x + r.w) - Math.max(body[0], r.x);
          const iy = Math.min(body[1] + body[3], r.y + r.h) - Math.max(body[1], r.y);
          if (r.key > p.y && ix > 0.15 && iy > 0.15) issues.push({ where: p.where, at: [p.x, p.y], kind: '가림', by: r.s, src: r.src, overlap: +(ix * iy / (body[2] * body[3])).toFixed(2) });
        }
        for (const r of rects) {
          const f = r.foot;
          if (f && p.x > f[0] && p.x < f[0] + f[2] && p.y > f[1] && p.y < f[1] + f[3]) issues.push({ where: p.where, at: [p.x, p.y], kind: '가구 안', by: r.s, src: r.src });
        }
        // 탁자 위 소품(z: top)이 사람 앞에 — 받침 윗면 위로 보이는 몸과 겹치고 사람보다 나중에 그려지는 것.
        // 그림 단계의 덧그리기(overTopItems)가 그 칸만 사람을 다시 그린다(fixed: true)
        for (const r of rects) {
          if (!r.top || r.key <= p.y) continue;
          const o = topOverlap(r, p.x, p.y);
          if (o) issues.push({ where: p.where, at: [p.x, p.y], kind: '소품 앞', by: r.s, src: r.src, overlap: +(o[2] * o[3] / (0.9 * 1.6)).toFixed(2), fixed: true });
        }
      }
      for (const r of rects) if (r.top && !r.host) issues.push({ where: r.src, at: [r.x, r.y], kind: '받침 없음', by: r.s, src: r.src });
    };
    check(standSpots(), decorRects('room'));
    if (HQ.seat) check([{ where: 'hq.seat', x: HQ.seat[0], y: HQ.seat[1] }], decorRects('hq'));
    return issues;
  }

  // ── 자리 배치 점검 · 다시 짜기(11-05 사용자 요청: 겹침을 하나씩 고치지 말고 근본적으로) ─────────────
  // 사람 자리를 먼저 본다 — 모든 자리에 캐릭터를 세워 머리 · 몸통(몸 위쪽 60%)을 무엇이 가리는지: 나중에 그려지는 가구,
  // 탁자 위 소품(받침 윗면 위로 솟은 부분), 구역 이름표(몸 전체). 머리만 보이는 것도 가려짐이다.
  // 괜찮은 것: 앉은 자리에서 탁자가 다리(아래 40%)를 가리는 것, "위에 앉는" 가구(소파 · 침대 — 사람보다 먼저 그린다).
  function bodySize() {
    if (bodySize._v) return bodySize._v;
    let w = 0.9, h = 1.5;
    for (const ch of (CH.pool || []).slice(0, 8)) {
      const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
      if (c) { w = Math.max(w, c.width / T); h = Math.max(h, c.height / T); }
    }
    return (bodySize._v = [Math.min(w, 1.3), Math.min(h, 2.4)]);
  }
  // 구역 이름표의 방 좌표 칸 — 이름표는 화면에 같은 크기로 그리므로 칸 크기는 지금 확대 배율에 달렸다(방 하나를 보는 보통 배율로 잰다)
  function tagRects(where = 'room') {
    const out = [], fontPx = +((TAG.font.match(/(\d+)px/) || [0, 10])[1]);
    const padL = TAG.kind === 'hazard' ? 9 : TAG.kind === 'sign' ? 7 : 6, s = cam.s * T;
    ctx.save(); ctx.font = TAG.font;
    if (where === 'hq') {
      const label = HQ.label || '감독실';
      ctx.font = TAG.font.replace(/(\d+)px/, (m, n) => `${+n + 3}px`);
      out.push({ zone: 'hq', label, x: 0.3, y: 2.2, w: (padL + ctx.measureText(label).width + 6) / s, h: (fontPx + 10) / s });
    } else {
      for (const [key, v] of Object.entries((theme.tags && theme.tags.zones) || {})) {
        const z = L.zones[key];
        if (!z || z.x == null) continue;
        const [label] = Array.isArray(v) ? v : [v];
        const p = tagPlace(key, (padL + ctx.measureText(label).width + 6) / s, (fontPx + 7) / s);
        out.push({ zone: key, label, x: p[0], y: p[1], w: p[2], h: p[3] });
      }
    }
    ctx.restore();
    return out;
  }
  // 구역 이름표 자리(11-05) — 이름표는 화면에 같은 크기로 그려서, 창이 작아 배율이 작으면 방 안에서 커진다. 테마에 적은 자리(dx · dy)는
  // 한 배율에서만 맞았다(1100×700 창에서 사람 몸을 최대 25% 덮음). 이제 지금 배율에서 고른다: 테마 자리 → 구역 네 모서리 → 구역 바로 위
  // 순서로, 어느 사람 자리(모든 구역의 standSpots, 몸 전체)도 덮지 않는 첫 자리. 없으면 가장 덜 덮는 자리. [x, y, w, h] 방 좌표
  const TAG_PLACE = new Map();
  const tagPadL = () => (TAG.kind === 'hazard' ? 9 : TAG.kind === 'sign' ? 7 : 6);
  function tagW(label) { ctx.save(); ctx.font = TAG.font; const w = ctx.measureText(label).width; ctx.restore(); return (tagPadL() + w + 6) / (cam.s * T); }
  function tagH() { return (+((TAG.font.match(/(\d+)px/) || [0, 10])[1]) + 7) / (cam.s * T); }
  function tagPlace(key, w, h) {
    w = Math.ceil(w * 20) / 20; h = Math.ceil(h * 20) / 20;               // 0.05칸 단위로(확대 중 배율이 계속 바뀐다)
    const ck = `${key}:${w}:${h}`;
    if (TAG_PLACE.has(ck)) return TAG_PLACE.get(ck);
    if (TAG_PLACE.size > 400) TAG_PLACE.clear();
    const z = L.zones[key], v = ((theme.tags && theme.tags.zones) || {})[key];
    const [, dx = 0, dy = 0] = Array.isArray(v) ? v : [v, 0, 0];
    const zw = z.w || 1, zh = z.h || 1;
    const cands = [[z.x + 0.1 + dx, z.y + 0.08 + dy], [z.x + 0.1, z.y + 0.08], [z.x + zw - w - 0.1, z.y + 0.08],
                   [z.x + 0.1, z.y + zh - h - 0.08], [z.x + zw - w - 0.1, z.y + zh - h - 0.08], [z.x + 0.1, z.y - h - 0.05]];
    const [bw, bh] = bodySize();
    const bodies = standSpots().map((p) => [p.x - bw / 2 + 0.05, p.y - bh, bw - 0.1, bh]);
    const others = Object.entries((theme.tags && theme.tags.zones) || {}).filter(([k]) => k !== key && L.zones[k] && L.zones[k].x != null)
      .map(([k, vv]) => { const zz = L.zones[k], [, ox = 0, oy = 0] = Array.isArray(vv) ? vv : [vv, 0, 0]; return [zz.x + 0.1 + ox, zz.y + 0.08 + oy, w, h]; });
    const rw = L.room ? L.room.w : Infinity, rh = L.room ? L.room.h : Infinity;   // 방 밖으로는 내지 않는다
    const scoreOf = (x, y) => {
      const box = [x, y, w, h];
      const cover = bodies.reduce((m, b) => Math.max(m, areaOf(box, b) / (b[2] * b[3])), 0);
      const clash = others.some((o) => areaOf(box, o) > 0) ? 0.001 : 0;      // 다른 이름표(테마 자리)와 겹치면 조금 덜 좋게
      return cover + clash;
    };
    let best = null;
    for (const [x, y] of cands) {
      const score = scoreOf(x, y);
      if (!best || score < best.score) best = { score, box: [x, y, w, h] };
      if (score === 0) break;
    }
    if (best.score > 0) {
      // 후보가 모두 덮으면 — 구역과 둘레 2칸을 0.1칸 간격으로 훑어, 덮지 않는 자리 중 테마 자리에 가장 가까운 곳(없으면 가장 덜 덮는 곳)
      const [x0, y0] = cands[0];
      let pick = null;
      for (let y = Math.max(0.05, z.y - 2); y <= Math.min(rh - h - 0.05, z.y + zh + 2 - h); y += 0.1) {
        for (let x = Math.max(0.05, z.x - 2); x <= Math.min(rw - w - 0.05, z.x + zw + 2 - w); x += 0.1) {
          const score = scoreOf(x, y), dist = Math.hypot(x - x0, y - y0);
          if (!pick || score < pick.score - 1e-9 || (Math.abs(score - pick.score) < 1e-9 && dist < pick.dist)) pick = { score, dist, box: [x, y, w, h] };
        }
      }
      if (pick && pick.score < best.score) best = pick;
    }
    TAG_PLACE.set(ck, best.box);
    return best.box;
  }
  const areaOf = (a, b) => Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) *
                           Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));
  function spotProblems(p, rects, tags) {
    const [bw, bh] = bodySize();
    const up = [p.x - bw / 2 + 0.05, p.y - bh, bw - 0.1, bh * 0.6], full = [p.x - bw / 2 + 0.05, p.y - bh, bw - 0.1, bh];
    const out = [];
    for (const r of rects) {
      if (r.key <= p.y) continue;                                                  // 사람보다 먼저 그려진다
      if (!r.top && SIT_ON.test(r.s) && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h) continue;   // 위에 앉은 가구
      const box = r.top && r.hostTop != null ? [r.x, r.y, r.w, Math.max(0, Math.min(r.y + r.h, r.hostTop) - r.y)] : [r.x, r.y, r.w, r.h];
      const c = areaOf(up, box) / (up[2] * up[3]);
      if (c > 0.02) out.push({ kind: r.top ? '소품' : '가구', by: r.s, r, cover: +c.toFixed(2) });
    }
    for (const t of tags) {
      const c = areaOf(full, [t.x, t.y, t.w, t.h]) / (full[2] * full[3]);
      if (c > 0.02) out.push({ kind: '이름표', by: t.label, t, cover: +c.toFixed(2) });
    }
    return out;
  }
  // 자리 점검 — 모든 자리(구역 좌석 · 책상 · 감독 자리 · 출하 라인 · 대기 · 일감 넘기기 · 감독실)
  function layoutAudit() {
    const out = [], rects = decorRects('room'), tags = tagRects('room');
    for (const p of standSpots()) { const pr = spotProblems(p, rects, tags); if (pr.length) out.push({ where: p.where, at: [p.x, p.y], problems: pr.map(({ kind, by, cover }) => ({ kind, by, cover })) }); }
    if (HQ.seat) {
      const p = { where: 'hq.seat', x: HQ.seat[0], y: HQ.seat[1] }, pr = spotProblems(p, decorRects('hq'), tagRects('hq'));
      if (pr.length) out.push({ where: p.where, at: [p.x, p.y], problems: pr.map(({ kind, by, cover }) => ({ kind, by, cover })) });
    }
    return out;
  }
  // 자리 다시 짜기 — ① 이름표가 사람 몸을 가리면 이름표를 옮긴다 ② 소품이 가리면 소품을 받침 탁자 위에서 옆으로 ③ 그래도 가리면
  // 사람 자리를 가장 가까운 깨끗한 곳으로(원래 가구 칸 안에 있던 자리는 그 가구 곁에서, 빈 바닥 자리는 걸을 수 있는 칸에서).
  // 이 페이지 안의 테마 값을 바꿔 가며 풀고, 바뀐 값만 돌려준다 — theme.json에 옮겨 적는다
  function layoutPlan() {
    const before = layoutAudit();
    const spots = () => standSpots();
    const blocked = (x, y) => { const g = GRID && GRID.room; if (!g) return false; const c = Math.floor(x * RES), r = Math.floor(y * RES); return c < 0 || r < 0 || c >= g.cols || r >= g.rows || !!g.block[r * g.cols + c]; };
    const changes = { tags: {}, items: [], seats: {}, stands: {}, unsolved: [] };
    // ① 이름표
    for (let pass = 0; pass < 2; pass++) {
      const tags = tagRects('room');
      for (const t of tags) {
        const others = tags.filter((o) => o !== t);
        const hits = (x, y) => spots().some((p) => spotProblems(p, [], [{ ...t, x, y }]).length) ||
          others.some((o) => areaOf([x, y, t.w, t.h], [o.x, o.y, o.w, o.h]) > 0);
        if (!hits(t.x, t.y)) continue;
        const z = L.zones[t.zone], v = theme.tags.zones[t.zone];
        const [, dx0 = 0, dy0 = 0] = Array.isArray(v) ? v : [v, 0, 0];
        let best = null;
        for (let dy = -0.6; dy <= 1.6; dy += 0.1) for (let dx = -0.8; dx <= 2.4; dx += 0.1) {
          const x = z.x + 0.1 + dx0 + dx, y = z.y + 0.08 + dy0 + dy;
          if (x < 0.7 || y < 1.9 || x + t.w > L.room.w - 0.7 || hits(x, y)) continue;
          const d = Math.hypot(dx, dy * 1.4);
          if (!best || d < best.d) best = { d, dx: +(dx0 + dx).toFixed(2), dy: +(dy0 + dy).toFixed(2) };
        }
        if (best) { theme.tags.zones[t.zone] = [t.label, best.dx, best.dy]; changes.tags[t.zone] = [t.label, best.dx, best.dy]; }
        else changes.unsolved.push({ tag: t.zone });
      }
    }
    // ② 소품
    for (const r of decorRects('room').filter((x) => x.top && x.d._hostSpan)) {
      const covering = () => spots().filter((p) => spotProblems(p, [r], []).length);
      if (!covering().length) continue;
      const [s0, s1] = r.d._hostSpan, x0 = r.d.x;
      let best = null;
      for (let nx = s0; nx <= s1 - r.w + 1e-9; nx += 0.05) {
        r.d.x = nx; r.x = r.ox + nx;
        if (!covering().length && (!best || Math.abs(nx - x0) < Math.abs(best - x0))) best = nx;
      }
      r.d.x = best != null ? +best.toFixed(2) : x0; r.x = r.ox + r.d.x;
      if (best != null) changes.items.push({ s: r.s, src: r.src, from: [x0, r.d.y], to: [r.d.x, r.d.y] });
    }
    // ③ 사람 자리
    const rects = decorRects('room'), tags = tagRects('room');
    for (const p of spots()) {
      if (!spotProblems(p, rects, tags).length) continue;
      const [zone, idx] = p.where.split(/[#.]/);
      const host = rects.find((r) => !r.top && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h);
      const sameZone = spots().filter((o) => o.where !== p.where && o.where.split(/[#.]/)[0] === zone);
      let best = null;
      for (let ny = p.y - 0.6; ny <= p.y + 1.0 + 1e-9; ny += 0.05) for (let nx = p.x - 1.2; nx <= p.x + 1.2 + 1e-9; nx += 0.05) {
        const d = Math.hypot(nx - p.x, (ny - p.y) * 1.2);
        if (best && d >= best.d) continue;
        if (host ? !(nx >= host.x - 0.3 && nx <= host.x + host.w + 0.3 && ny >= host.y - 0.3 && ny <= host.y + host.h + 0.3) : blocked(nx, ny)) continue;
        if (sameZone.some((o) => Math.hypot(o.x - nx, o.y - ny) < 0.75)) continue;
        if (spotProblems({ x: nx, y: ny }, rects, tags).length) continue;
        best = { d, x: +nx.toFixed(2), y: +ny.toFixed(2) };
      }
      if (!best) { changes.unsolved.push({ spot: p.where, at: [p.x, p.y], problems: spotProblems(p, rects, tags).map(({ kind, by, cover }) => ({ kind, by, cover })) }); continue; }
      if (zone === 'infra') {
        const z = L.zones.infra; z.stands = z.stands || {};
        if (idx === 'handoff') { changes.unsolved.push({ spot: p.where, note: '일감 넘기는 자리는 대기 자리 + 1.3칸 — 대기 자리를 옮겨야 한다' }); continue; }
        z.stands[idx] = [best.x, best.y]; changes.stands[idx] = [best.x, best.y];
      } else if (idx === 'seat') { L.zones[zone].seat = [best.x, best.y]; changes.seats[zone + '.seat'] = [best.x, best.y]; }
      else if (idx === 'stand') { L.zones[zone].stand = [best.x, best.y]; changes.seats[zone + '.stand'] = [best.x, best.y]; }
      else {
        const s = L.zones[zone].seats[+idx];
        s[0] = best.x; s[1] = best.y;
        changes.seats[zone] = L.zones[zone].seats.map((q) => q.slice());
      }
    }
    TOP_RECTS.room = null;
    return { before, changes, after: layoutAudit() };
  }

  // 탁자 위 소품 덧그리기(11-05) — 탁자 뒤에 앉은 사람은 탁자보다 먼저 그려져야 다리가 가려지는데, 그러면 탁자 위 소품
  // (책 · 머그 · 촛대)이 사람 몸 위로 그려진다. 한 줄 정렬로는 둘 다 만족할 수 없어서, 다 그린 뒤 소품과 겹치는 사람만
  // 소품 자리 안에서 한 번 더 그린다 — 탁자는 다리를 가리고, 소품은 사람 뒤로 간다
  // 구역 이름표 위로 사람을 덧그린다(11-05) — 이름표는 화면에 같은 크기라 화면이 좁을수록(패널을 넓히면) 방 안에서 커져서,
  // 이름표 자리를 옮기는 것만으로는 모든 배율에서 사람 자리를 피할 수 없다. 이름표를 그린 뒤 이름표 칸 안의 사람만 한 번 더 —
  // 이름표는 읽히고, 사람은 어떤 배율에서도 이름표에 가리지 않는다
  function overTags(room, list, now) {
    const tags = HITS.filter((h) => h.zone);
    if (!tags.length) return;
    const toW = (sx, sy) => [((sx - W / 2) / cam.s + cam.x), ((sy - H / 2) / cam.s + cam.y)];   // 화면 → 월드 픽셀
    const boxes = tags.map((h) => { const [x0, y0] = toW(h.x, h.y), [x1, y1] = toW(h.x + h.w, h.y + h.h); return [x0, y0, x1 - x0, y1 - y0]; });
    const [bw, bh] = bodySize();
    ctx.save();
    ctx.setTransform(cam.s * dpr, 0, 0, cam.s * dpr, (W / 2 - cam.x * cam.s) * dpr, (H / 2 - cam.y * cam.s) * dpr);
    for (const a of list) {
      if (a.room !== room.name || (a.bornAt && now < a.bornAt)) continue;
      const body = [(a.x - bw / 2) * T, (a.y - bh) * T, bw * T, bh * T];
      const hit = boxes.filter((b) => areaOf(body, b) > 0);
      if (!hit.length) continue;
      ctx.save(); ctx.beginPath();
      for (const b of hit) ctx.rect(b[0], b[1], b[2], b[3]);
      ctx.clip(); drawActorS(a, now); ctx.restore();
    }
    ctx.restore();
  }

  const TOP_RECTS = {};
  function overTopItems(room, list, now, where = 'room') {
    if (!TOP_RECTS[where]) TOP_RECTS[where] = decorRects(where).filter((r) => r.top);
    const rects = TOP_RECTS[where];
    if (!rects.length || window.__noTopFix) return;      // __noTopFix — 화면 시험에서 고치기 전 모습과 견줄 때만
    for (const a of list) {
      if (a.room !== room.name || (a.bornAt && now < a.bornAt)) continue;
      const ax = a.x - room.x, ay = a.y - room.y;          // 방(감독실) 좌표
      const parts = rects.filter((r) => r.key > ay).map((r) => topOverlap(r, ax, ay)).filter(Boolean);
      if (!parts.length) continue;
      ctx.save();
      ctx.beginPath();
      for (const [x, y, w, h] of parts) ctx.rect((room.x + x) * T, (room.y + y) * T, w * T, h * T);
      ctx.clip();
      drawActorS(a, now);
      ctx.restore();
    }
  }

  // 탁자 위 소품의 그리는 순서 — 소품 가운데가 들어 있는 받침(같은 목록의 가구) 중 발밑이 가장 아래인 것 바로 다음.
  // 전에는 y + 3(어림)이라 받침 앞(아래)에 선 사람보다 늦게 그려져 사람 머리 위로 소품이 덮였다(11-05)
  function topKey(d) {
    if (d._k != null) return d._k;
    // 소품이 들어 있는 목록 — 방 가구 · 출하 라인 · 감독실(theme.hq.decor). 감독실을 빠뜨려서 그 탁자 위 책 · 두루마리가
    // 받침을 못 찾고 어림값(y + h + 0.3)으로 떨어져 탁자에 앉은 포먼 위로 그려졌다(11-05 사용자 보고)
    const lists = [theme.sprites.decor || [], ...Object.values(theme.sprites.infra_decor || {}), (theme.hq && theme.hq.decor) || []];
    const list = lists.find((l) => l.includes(d)) || [];
    // 받침을 가운데가 아니라 소품의 밑동(아래쪽)으로 찾는다 — 모니터 · PC처럼 키 큰 소품은 가운데가 탁자 윗면보다 위라 못 찾았다
    const [w, h] = sizeT(d), cx = d.x + w / 2, cy = d.y + h * 0.85;
    let best = null, bestTop = null, span = null;
    const pieces = [];
    for (const b of list) {
      if (!b.s || b.fx || b.z) continue;
      const [bw, bh] = sizeT(b);
      for (let i = 0; i < (b.n || 1); i++) {
        const bx = b.x + i * (b.dx || 1);
        pieces.push([bx, bx + bw, b.y]);
        if (cx >= bx && cx <= bx + bw && cy >= b.y && cy <= b.y + bh && (best == null || b.y + bh > best)) { best = b.y + bh; bestTop = b.y; span = [bx, bx + bw]; }
      }
    }
    // 받침 탁자의 좌우 끝 — 이어 붙인 조각(왼끝 · 가운데 · 오른끝)까지. 자리 다시 짜기(layoutPlan)가 소품을 이 안에서만 옮긴다
    if (span) for (let grew = true; grew;) {
      grew = false;
      for (const [a0, a1, ay] of pieces) {
        if (Math.abs(ay - bestTop) > 0.05) continue;
        if (a1 >= span[0] - 0.06 && a0 < span[0] - 0.01) { span[0] = a0; grew = true; }
        if (a0 <= span[1] + 0.06 && a1 > span[1] + 0.01) { span[1] = a1; grew = true; }
      }
    }
    // 받침보다 0.005 뒤 = 받침 발밑(-0.01)보다 뒤, 받침 앞 사람보다 앞. 받침을 못 찾으면 제 발밑(audit()이 "받침 없음"으로 알린다)
    d._host = best != null;
    d._hostSpan = span;
    d._hostTop = bestTop;                                // 받침 윗면 선 — 덧그리기는 이 선 위쪽만(아래는 탁자가 사람을 가리는 자리)
    d._k = best != null ? best - 0.005 : d.y + h - 0.01;
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

  // "위에 앉거나 눕는" 가구 — 소파 · 빈백 · 간이침대 · 벤치 · 그루터기 · 의자. 자리 점이 이 가구 칸 안이면 사람은 그 가구
  // 바로 다음에 그린다(가구 위에 앉은/누운 모습). 탁자 · 책상 · 작업대는 아니다 — 거기선 탁자가 다리를 가리는 지금 모습이 맞다.
  // (11-05 — 발 위치 순서로는 소파 · 침대 · 의자 등받이가 나중에 그려져 사람이 뒤로 숨었다: 오피스 라운지 소파, 현장 함바 간이침대,
  //  마법학교 책상 · 대강당 아래 줄 — 등을 보이고 의자에 앉은 사람의 몸 절반을 등받이가 가렸다)
  const SIT_ON = /(^|_)(sofa|couch|bean|cot|bed|bench|stump|stool|hammock|futon|chair)(_|\d|$)/i;   // 낱말 단위 — workbench(작업대)는 아니다
  function seatFurniture(a) {
    const key = `${a.room}:${a.tx}:${a.ty}`;
    if (a._bedKey === key) return a._bed;
    a._bedKey = key;
    const room = world.rooms.find((r) => r.name === a.room);
    a._bed = null;
    if (!room) return null;
    const px = a.tx - room.x, py = a.ty - room.y;
    for (const r of decorRects('room')) {
      if (r.top || !SIT_ON.test(r.s) || px < r.x || px > r.x + r.w || py < r.y || py > r.y + r.h) continue;
      if (!a._bed || r.key > a._bed.key - room.y) a._bed = { s: r.s, lx: room.x + r.x, cx: room.x + r.x + r.w / 2, cy: room.y + r.y + r.h * 0.5, key: room.y + r.key + 0.002 };
    }
    return a._bed;
  }
  const lieBed = seatFurniture;
  // 엎드려 자기(sleep) — 탁자 뒤에 앉아 머리를 탁자 위에 댄다. 탁자가 나중에 그려져 머리까지 가렸다(11-05 마법학교 대강당).
  // 앞의 탁자를 찾아, 탁자를 그린 뒤 머리 쪽(탁자 윗면 + 0.55칸 위쪽)만 한 번 더 그린다
  function sleepTable(a) {
    const key = `s:${a.room}:${a.tx}:${a.ty}`;
    if (a._tblKey === key) return a._tbl;
    a._tblKey = key; a._tbl = null;
    const room = world.rooms.find((r) => r.name === a.room);
    if (!room) return null;
    const t = tableAt(a.tx - room.x, a.ty - room.y);
    if (t) a._tbl = { key: room.y + t.key + 0.003, top: room.y + t.y, clipBottom: room.y + t.y + 0.55,
                      lx: room.x + t.x, rx: room.x + t.x + t.w, h: t.h };
    return a._tbl;
  }
  // 자리(방 좌표) 바로 앞 탁자 — 자는 사람 머리 · 놓는 소품이 올라간다. 위에 앉는 가구 · 탁자 위 소품은 아니다
  function tableAt(px, py) {
    let best = null;
    for (const r of decorRects('room')) {
      if (r.top || SIT_ON.test(r.s) || px < r.x || px > r.x + r.w || r.y < py - 0.8 || r.y > py + 0.6) continue;
      if (!best || r.y < best.y) best = r;
    }
    return best;
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
      // 간이침대에 눕기 — 그림을 왼쪽으로 90도 눕힌다(머리가 왼쪽 = 베개 쪽). 자리 점이 아니라 그 아래 침대의 가운데에
      // 몸을 맞춘다(11-05 — 전에는 자리 점에 그려 몸이 침대 오른쪽 · 위로 반쯤 벗어났다). 그리는 순서는 lieBed().key
      const bed = lieBed(a);
      // 누우면 그림 높이가 가로 길이 — 머리(왼쪽 끝)가 베개(침대 왼쪽 끝 + 0.25칸)에 닿게
      const cx = bed ? Math.min(bed.cx, bed.lx + 0.25 + c.height / T / 2) : a.x, cy = bed ? bed.cy : a.y - 5 / T;
      ctx.save();
      ctx.translate(Math.round(cx * T), Math.round(cy * T));
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
    ctx.globalAlpha = 1;
  }

  // ── 소품은 들지 않고 놓는다(11-05 사용자 지시) ─────────────────────────────────────────────
  // 전에는 테마마다 발밑 기준 dx · dy와 원래 크기로 손에 들려, 16px 캐릭터 앞에 16px 책 · 깃펜 · 플라스크가 얼굴 높이에 얹혀
  // 사람이 안 보였다(마법학교 서고). 이제 사람은 서 있거나 앉아 있기만 하고, 그 동작의 소품은 곁에 놓는다:
  //  · 앞에 탁자가 있으면(tableAt — 자는 사람 머리를 얹는 그 탁자) 탁자 윗면, 사람 손 쪽으로 조금
  //  · 없으면 사람 옆 바닥(손 쪽 발치)
  //  · 크기: 폭 ≤ 캐릭터 폭의 절반, 높이 ≤ 캐릭터 키의 55%(16px 캐릭터 → 8 × 9px). 비율은 지킨다
  //  · 얼굴 칸(그림 위쪽 FACE_H, 가운데 FACE_W 폭)과 겹치면 손 쪽 바깥으로 민다 — 얼굴은 늘 보인다
  // 테마 props에는 그림(s) · 손 쪽(dx 부호, 양수 오른쪽) · shake(플라스크 흔들기 등) · fx(소품 위 효과)만 둔다
  const FACE_H = 0.5, FACE_W = 0.64;
  function faceBox(cw, ch, cx, foot) {
    const top = foot - ch;
    return [cx - Math.ceil(cw * FACE_W / 2), top, Math.ceil(cw * FACE_W), Math.ceil(ch * FACE_H)];
  }
  // tbl: { top(px, 탁자 그림 위 끝), h(px), lx, rx(px) } | null. 돌려주는 값은 px 칸 + 어디에 놓였는지
  function placeProp(prop, cw, ch, cx, foot, tbl, shake = 0) {
    const [sw, sh] = SP.size(prop.s);
    const k = Math.min(1, Math.floor(cw * 0.5) / sw, Math.floor(ch * 0.55) / sh);
    const w = Math.max(2, Math.round(sw * k)), h = Math.max(2, Math.round(sh * k));
    const side = (prop.dx || 0) < 0 ? -1 : 1;
    let x, y, on;
    if (tbl) {
      on = 'table';
      x = cx - Math.round(w / 2) + side * Math.round(cw * 0.35);
      x = Math.max(tbl.lx + 1, Math.min(x, tbl.rx - w - 1));              // 탁자 밖으로 삐져나가지 않게
      y = tbl.top + Math.min(6, Math.round(tbl.h * 0.45)) - h;            // 바닥이 윗면 위에 닿게
    } else {
      on = 'floor';
      x = side > 0 ? cx + Math.floor(cw / 2) - 1 : cx - Math.ceil(cw / 2) - w + 1;   // 발치 옆
      y = foot - h;
    }
    x += shake;                                                            // 흔들기를 먼저 — 그다음 얼굴 검사
    const [fx, fy, fw, fh] = faceBox(cw, ch, cx, foot);
    if (areaOf([x, y, w, h], [fx, fy, fw, fh]) > 0) x = side > 0 ? fx + fw : fx - w;   // 얼굴을 덮으면 옆으로
    return { x, y, w, h, on, k: +k.toFixed(2) };
  }
  function propOf(a) {
    if (a.kind === 'mini' || a.moving) return null;
    const act = a.act || {};
    if (act.fx === 'stone' || act.fx === 'frozen' || act.fx === 'ghost') return null;
    return (theme.sprites.props || {})[act.anim] || null;
  }
  // 놓인 소품 그리기 — 그리기 목록에서 탁자 위면 그 탁자 바로 다음, 바닥이면 사람 바로 다음 순서
  function drawPropS(a, prop, tbl, now) {
    const c = SP.charFrame(a.char, 'idle', a.face || 'down', 0, null, null);
    if (!c) return;
    const sh = prop.shake ? Math.round(Math.sin(a.phase * 6) * prop.shake) : 0;
    const t = tbl && { top: tbl.top * T, h: tbl.h * T, lx: tbl.lx * T, rx: tbl.rx * T };
    const r = placeProp(prop, c.width, c.height, Math.round(a.x * T), Math.round(a.y * T), t, sh);
    ctx.globalAlpha = (a.act && a.act.alpha != null) ? a.act.alpha : 1;
    const pc = SP.scaled(prop.s, r.w, r.h, now);
    if (pc) ctx.drawImage(pc, r.x - pc.pad, r.y - pc.pad);
    if (prop.fx) { const [fw, fh] = SP.size(prop.fx); SP.draw(ctx, prop.fx, r.x + r.w / 2 - fw / 2, r.y - fh / 2 - 2, now); }
    ctx.globalAlpha = 1;
  }
  // 소품 점검 — ① 모든 테마 캐릭터 × 모든 소품을 바닥 · 탁자(tableAt이 잡는 가장 높은 탁자) 두 경우로 놓아 얼굴 칸과 겹치는지 · 너무 큰지
  // ② 모든 자리(standSpots)의 실제 앞 탁자 위에 놓아 얼굴 칸과 겹치는지, 자리마다 어디에 놓이는지(탁자 / 바닥).
  // 화면 시험이 window.office.propAudit()으로 부른다. issues가 빈 배열이면 통과
  function propAudit() {
    const issues = [], props = theme.sprites.props || {};
    const chars = [...new Set([...(CH.pool || []), CH.foreman, ...Object.values(CH.infra || {})].filter(Boolean))];
    for (const ch of chars) {
      const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
      if (!c) { issues.push({ char: ch, problem: '캐릭터 그림 없음' }); continue; }
      const face = faceBox(c.width, c.height, 0, c.height);
      const high = { top: c.height - Math.round(0.8 * T), h: T, lx: -T, rx: T };       // tableAt이 잡는 가장 높은 탁자
      for (const [anim, prop] of Object.entries(props)) {
        if (anim.startsWith('_')) continue;
        if (!SP.has(prop.s)) { issues.push({ char: ch, anim, problem: '소품 그림 없음', s: prop.s }); continue; }
        for (const tbl of [null, high]) for (const sh of [-(prop.shake || 0), prop.shake || 0]) {
          const r = placeProp(prop, c.width, c.height, 0, c.height, tbl, sh);
          const ov = areaOf([r.x, r.y, r.w, r.h], face);
          if (ov > 0) issues.push({ char: ch, anim, s: prop.s, on: r.on, problem: '얼굴 가림', px: ov });
          if (r.w > c.width / 2 + 0.5 || r.h > c.height * 0.55 + 0.5) issues.push({ char: ch, anim, s: prop.s, problem: '너무 큼', size: [r.w, r.h], char_size: [c.width, c.height] });
        }
      }
    }
    // 실제 자리 — 앞 탁자가 잡히는 자리마다 모든 캐릭터 × 소품을 그 탁자 위에 놓아 본다
    const spots = standSpots().map((p) => ({ ...p, t: tableAt(p.x, p.y) }));
    for (const p of spots) {
      if (!p.t) continue;
      const tb = { top: p.t.y * T, h: p.t.h * T, lx: p.t.x * T, rx: (p.t.x + p.t.w) * T };
      for (const ch of chars) {
        const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
        if (!c) continue;
        const cx = Math.round(p.x * T), foot = Math.round(p.y * T), face = faceBox(c.width, c.height, cx, foot);
        for (const [anim, prop] of Object.entries(props)) {
          if (anim.startsWith('_') || !SP.has(prop.s)) continue;
          const r = placeProp(prop, c.width, c.height, cx, foot, tb);
          const ov = areaOf([r.x, r.y, r.w, r.h], face);
          if (ov > 0) issues.push({ where: p.where, char: ch, anim, s: prop.s, on: 'table', problem: '얼굴 가림', px: ov });
        }
      }
    }
    return { issues: issues.filter((x, i, a) => a.findIndex((y) => JSON.stringify(y) === JSON.stringify(x)) === i),
             spots: spots.map((p) => ({ where: p.where, on: p.t ? 'table' : 'floor', by: p.t ? p.t.s : null })) };
  }
  // 소품 견본(디버그) — 줄 = 소품 동작, 칸 = 캐릭터. 실제 그리기와 같은 placeProp · scaled로 그려 PNG data URL을 돌려준다.
  // 칸마다 왼쪽은 바닥에 놓은 것, 오른쪽은 앞 탁자(회색 띠) 위에 놓은 것. 얼굴 칸은 빨간 테두리(showFace)
  function propSheet(zoom = 6, showFace = true) {
    const props = Object.entries(theme.sprites.props || {}).filter(([k]) => !k.startsWith('_'));
    const chars = [...new Set([...(CH.pool || []), CH.foreman].filter(Boolean))].slice(0, 6);
    const cell = 56, lab = 46;
    const cv = document.createElement('canvas');
    cv.width = (lab + chars.length * cell) * zoom; cv.height = props.length * cell * zoom;
    const g = cv.getContext('2d');
    g.imageSmoothingEnabled = false; g.fillStyle = '#d8d4c8'; g.fillRect(0, 0, cv.width, cv.height);
    g.scale(zoom, zoom);
    props.forEach(([anim, prop], r) => {
      g.fillStyle = '#222'; g.font = '6px monospace'; g.textBaseline = 'middle'; g.fillText(anim, 2, r * cell + cell / 2);
      chars.forEach((ch, i) => {
        const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
        if (!c) return;
        const foot = r * cell + cell - 6;
        for (const [j, withTbl] of [[0, false], [1, true]]) {
          const cx = Math.round(lab + i * cell + 14 + j * 26);
          g.drawImage(c, Math.round(cx - c.width / 2), foot - c.height);
          let tbl = null;
          if (withTbl) {                                                  // 사람 바로 앞 탁자 — 윗면이 몸 아래 40%(layoutAudit이 허용하는 높이). 사람보다 나중에
            tbl = { top: foot - Math.round(c.height * 0.4), h: T, lx: cx - 12, rx: cx + 12 };
            g.fillStyle = '#8a7a66'; g.fillRect(tbl.lx, tbl.top, 24, T);
            g.fillStyle = '#a8977f'; g.fillRect(tbl.lx, tbl.top, 24, 6);
          }
          const pr = placeProp(prop, c.width, c.height, cx, foot, tbl);
          const pc = SP.scaled(prop.s, pr.w, pr.h, 0);
          if (pc) g.drawImage(pc, pr.x - pc.pad, pr.y - pc.pad);
          if (showFace) { const f = faceBox(c.width, c.height, cx, foot); g.strokeStyle = '#e0303088'; g.lineWidth = 1 / zoom; g.strokeRect(f[0], f[1], f[2], f[3]); }
        }
      });
    });
    return cv.toDataURL('image/png');
  }

  // 압축 알림(11-05) — 2번째 압축부터 머리 오른쪽에 📦(4번째부터 빨간 테두리). 패널 띠의 [나중에]로 숨긴 것은 같이 숨긴다
  function drawCompactMark(a, x, y) {
    const c = a.kind === 'session' && a.s && a.s.compact;
    if (!c || !c.level) return;
    if (window.foremanCompactSnoozed && window.foremanCompactSnoozed(a.s.id, c.count)) return;
    if (c.level === 'late') { ctx.fillStyle = P.bad; ctx.beginPath(); ctx.arc(x + 4, y - 3, 6, 0, Math.PI * 2); ctx.fill(); }
    ctx.font = '8px "Noto Color Emoji", "Apple Color Emoji", sans-serif'; ctx.textAlign = 'left';
    ctx.fillText('📦', x, y);
  }

  // 사람 위에 뜨는 것 — 말풍선(이모트) · 연기 · 자는 Zz · 일꾼 수 · 선택 표시(가구에 가리지 않게 마지막에)
  function drawOverlay(a, now) {
    const act = a.act || {};
    const x = a.x * T, top = a.y * T - (a.drawH || 16);
    if (act.fx === 'smoke') drawSmokeS(a.x, a.y - 0.6, now);
    drawCompactMark(a, x + 7, top + 4);
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
    if (!a.moving && act.anim === 'wait' && !act.flag) {                       // 기다림 — 책상에 서서 "…"이 차오른다
      drawBubble(x, top - 3, '·'.repeat(1 + Math.floor(now / 500) % 3).padEnd(3, ' '), P.act, 7);
    }
    if (a.kind === 'scribe' && a.todo && a.todo.items && a.todo.items.length) {  // 서기 — 할 일 N(누르면 목록)
      drawBubble(x, top - 3, `할 일 ${a.todo.items.length}`, P.warn, 8);
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
  themeTips(theme.tags && theme.tags.style);     // 툴팁 색 · 글꼴도 이름표를 따른다(양피지 · 사인판 · 안전 표지판). 구조 · 크기 · 지연은 같다
  attachDomTips();
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
      // 실패는 빨강 글자(✗), 그 밖은 이름표 글자색 — 성공 ✓ 은 앞의 초록 점이 이미 말한다
      ctx.font = TAG.font.replace(/^(italic )?\d*\s*/, 'bold '); ctx.fillStyle = sub.startsWith('✗') ? '#d23b3b' : TAG.fg;
      ctx.fillText(sub, cx + tw + 8, y + h / 2 + 0.5);
    }
    return { x, y, w, h };
  }

  const STATUS_KO = { running: '진행 중', success: '성공', failed: '실패', waiting: 'Sync 대기', stale: '나중 배포로 대체', none: '기록 없음' };
  // 구역이 하는 일 — 테마마다 이름(비유)은 달라도 설명은 같다(theme.tags.roles: 구역 → 아래 열쇠). 이름표에 마우스를 올리면 뜬다(11-05)
  // 툴팁 글은 짧게 — "무엇" 한 마디 + 한 줄 설명. 화면 글은 "~습니다"로(11-05 사용자 요청: 도구 목록 · 판별 명령은 넣지 않는다)
  const ZONE_ROLE = {
    hq:   { what: '감독 자리', desc: '포먼이 현장 전체를 보는 자리입니다.' },
    read: { what: '파일 읽기', desc: '코드와 문서를 읽고 찾는 곳입니다.' },
    edit: { what: '코드 수정', desc: '파일을 고치거나 새로 쓰는 곳입니다.' },
    bash: { what: '명령 실행', desc: '셸 명령을 돌리는 곳입니다.' },
    test: { what: '테스트 실행', desc: '테스트를 돌리는 곳입니다.' },
    git:  { what: 'git 작업', desc: '커밋하고 푸시하는 곳입니다.' },
    web:  { what: '웹 검색', desc: '밖에서 정보를 찾는 곳입니다.' },
    sub:  { what: '보조 호출', desc: '서브에이전트에게 일을 나눠 맡기는 곳입니다.' },
    idle: { what: '대기 중', desc: '할 일이 없을 때 쉬는 곳입니다.' },
    scribe: { what: '서기실', desc: '서기가 늘 머무는 곳입니다. 서기를 누르면 문서 일을 맡길 수 있습니다.' },
  };
  const INFRA_ROLE = {
    jenkins: { what: '빌드', desc: '커밋을 빌드하고 테스트하는 곳입니다.' },
    harbor:  { what: '이미지 저장', desc: '빌드한 이미지를 보관하는 곳입니다.' },
    argocd:  { what: '배포', desc: '새 이미지를 서버에 내보내는 곳입니다.' },
  };
  const tipOf = (r) => r && `<div class="tip-b">${r.what}</div><div>${r.desc}</div>`;
  let HITS = [];                     // 이번 프레임에 그린 이름표 자리(화면 좌표) — 마우스를 올리면 설명
  function drawZoneTags(r) {
    const names = (theme.tags && theme.tags.zones) || {};
    for (const [key, v] of Object.entries(names)) {
      const z = L.zones[key];
      if (!z || z.x == null) continue;
      const [label] = Array.isArray(v) ? v : [v];                    // ["아치 창", dx, dy] — dx · dy는 첫 후보 자리(tagPlace)
      const role = ZONE_ROLE[((theme.tags && theme.tags.roles) || {})[key]];
      const n0 = HITS.length;
      const [tx, ty] = tagPlace(key, tagW(label), tagH());
      const box = drawTag(r.x + tx, r.y + ty, label, false, null, null, role ? `<div class="tip-h">${esc(label)}</div>${tipOf(role)}` : null);
      if (HITS.length > n0) HITS[HITS.length - 1].zone = key; else HITS.push({ ...box, zone: key, tip: null });   // overTags가 쓴다
      if (!HITS[HITS.length - 1].tip) HITS[HITS.length - 1].tip = `<div class="tip-h">${esc(label)}</div>`;
    }
    // 출하 라인 — 이름 · 세 단계(번호 · 무엇 · 지금 상태) · 단계 사이 화살표
    const iz = L.zones.infra, it = (theme.tags && theme.tags.infra) || {};
    if (!iz) return;
    if (it.title) drawTag(r.x + 1.1, r.y + iz.y - 0.6, it.title, false, null, null,
      `<div class="tip-h">${esc(it.title)}</div><div class="tip-b">출하 라인</div><div>커밋이 빌드 → 이미지 → 배포 순서로 나가는 곳입니다.</div>`);
    // 한 방에 빌드가 여럿 — 담당은 가장 오래된 것을 맡고, 나머지는 담당 자리 옆에 줄 선다
    const q = r.courier && r.courier.queue;
    if (q && q.length) {
      const [hx, hy] = courierHome(r);
      drawTag(hx - 0.6, hy - 2.6, `대기 ${q.length}`, false, P.warn, null,
        `<div class="tip-h">출하 대기</div><div class="tip-b">대기 ${q.length}개</div><div>먼저 온 빌드가 끝나기를 기다리고 있습니다.</div>${q.map((ch) => {
          const c = ch.commits && ch.commits[0];
          return `<div class="tip-t">${esc(ch.short)} ${esc(short((c && c.subject) || '', 60))}</div>`;
        }).join('')}`);
    }
    const kinds = ['jenkins', 'harbor', 'argocd'];
    kinds.forEach((kind, i) => {
      const st = r['st_' + kind] || 'none';
      // 평소(기록 없음)엔 아무 표시도 없다 — "기록 없음"이라고 쓰면 뭔가 잘못된 것처럼 보였다(11-05). 성공 ✓ · 실패 ✗ 빨강
      const col = { running: P.act, success: P.ok, failed: P.bad, waiting: P.warn }[st] || null;
      const mark = { running: '진행 중', success: '✓', failed: '✗ 실패', waiting: 'Sync 대기' }[st] || null;
      const label = `${'①②③'[i]} ${it[kind] || (iz[kind] && iz[kind].label) || kind}`;
      drawTag(r.x + iz[kind].x + 0.1, r.y + iz.y + 0.25, label, false, col, mark,
        `<div class="tip-h">${esc(label)}</div>${tipOf(INFRA_ROLE[kind])}${st !== 'none' ? `<div class="tip-s">${esc(STATUS_KO[st] || st)}</div>` : ''}`);
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
    // 끝난 세션(DORMANT)과 멈춘 세션(SUSPENDED)이 그림만으로는 헷갈렸다(11-05) — 이름 뒤에 글로 붙인다
    const suffix = a.kind === 'session' && a.s ? ({ DORMANT: ' · 끝남', SUSPENDED: ' · 멈춤' }[a.s.state] || '') : '';
    const text = (a.kind === 'session' ? short(a.name, 18) : short(a.name, 30)) + suffix;
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
    // 백그라운드 Bash · Monitor — "IDLE + 백그라운드 n개"(README 3.11). 일꾼 줄이 있으면 그 아래
    const bg = a.kind === 'session' && a.s ? a.s.background || [] : [];
    if (bg.length) {
      const d = bg[0].description || bg[0].tool;
      const line = `백그라운드 ${bg.length}${d ? ' · ' + short(d, 22) : ''}`;
      const w3 = ctx.measureText(line).width + 6, y3 = sy + (n ? 32 : 17);
      ctx.fillStyle = '#000a'; ctx.fillRect(sx - w3 / 2, y3, w3, 14);
      ctx.fillStyle = P.act; ctx.fillText(line, sx, y3 + 1);
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
    // 그중 Opus(11-05 사용자 요청 — 비싼 모델을 어디서 쓰나). 다른 모델이 하나도 없으면 줄이 같아 생략
    if (st.opus_out && st.opus_out < st.all_out) lines.push([`Opus 출력 ${fmt(st.opus_out)} (서브에이전트 포함 ${Math.round(100 * st.opus_out / st.all_out)}%)`, P.muted, '11px']);
    else if (st.opus_out) lines.push(['오늘은 전부 Opus', P.muted, '11px']);
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
  // 머리말 프로젝트 줄(11-05) — 감독실에 나갔다 오지 않고 바로 다른 방으로. 지금 방은 눌린 모양.
  // 숫자: 작업 중 n · 승인 대기 n. 점: 승인 대기(노랑 깜빡) · 안 본 새 답(파랑) — 그 방을 보면 지워진다
  const seenAt = new Map();                 // 방 → 마지막으로 본 때(이 화면을 연 때부터 센다)
  const openedAt = Date.now();
  function drawProjects(st) {
    if (!world) return;
    const rooms = [...world.rooms, ...(world.lounge && world.lounge.sessionIds && world.lounge.sessionIds.length ? [world.lounge] : [])];
    const now = Date.now();
    const html = rooms.map((r) => {
      const key = r.name || '_lounge';
      if (view === key) seenAt.set(key, now);
      const ss = (r.sessionIds || []).map((id) => st.sessions.get(id)).filter(Boolean);
      const act = ss.filter((s) => s.state === 'ACTIVE' || viewState(s) === 'WAITING').length;
      const pend = (r.stats && r.stats.pending) || 0;
      const lastReply = Math.max(0, ...ss.map((s) => s.replyAt || 0));
      const unseen = lastReply > Math.max(openedAt, seenAt.get(key) || 0);
      const dot = pend ? '<i class="pdot warn"></i>' : unseen ? '<i class="pdot new"></i>' : '';
      const nums = [act ? `<span class="pn">작업 ${act}</span>` : '', pend ? `<span class="pn warn">승인 ${pend}</span>` : ''].join('');
      const tip = `${r.label} — 이 방으로 갑니다.${act ? ` 작업 중 ${act}.` : ''}${pend ? ` 승인 대기 ${pend}.` : ''}${unseen ? ' 안 본 새 답이 있습니다.' : ''}`;
      return `<button class="ghost oproj-b${view === key ? ' on' : ''}${pend ? ' pend' : ''}" data-room="${esc(key)}" data-tip="${esc(tip)}" aria-pressed="${view === key}">${dot}${esc(r.label)}${nums}</button>`;
    }).join('');
    if ($('oProj').innerHTML !== html) $('oProj').innerHTML = html;
  }
  function header(st) {
    const c = st.conn;
    $('oConn').className = 'conn ' + c.status;
    $('oConn').textContent = { up: '연결됨', down: '끊김', connecting: '연결 중', auth: '토큰 필요', idle: '연결 전' }[c.status] || c.status;
    const pend = [...st.approvals.values()].filter((a) => a.status === 'pending').length;
    const ig = st.ingest;
    // 전체 요약(클래식 머리말과 같은 숫자) + 적재가 막히면 무엇이 막혔는지(마우스를 올리면)
    let active = 0, live = 0, outToday = 0, subs = 0;
    for (const s of st.sessions.values()) {
      if (s.state === 'ACTIVE' || viewState(s) === 'WAITING') active++;
      if (s.state !== 'DORMANT') live++;
      outToday += (s.tokens && s.tokens.today_output) || 0;
      subs += s.subagents_running || 0;
    }
    const igWhy = !ig ? '' : ig.stalled ? `트랜스크립트 감시가 ${ig.tick_age_s}초째 멈춰 있습니다`
      : (ig.stuck || []).map((x) => `${x.session} ${x.minutes}분 · ${x.failures}번 — ${x.error}`).join('\n');
    $('oAlerts').innerHTML = (pend ? `<button id="oPend" class="ghost warn" title="승인 대기 — 패널에서 승인하거나 거부합니다.">❗ 승인 대기 ${pend}</button>` : '') +
      (ig && !ig.ok ? `<span class="bad" title="${esc(igWhy)}">⚠ ${ig.stalled ? '와처 멈춤' : `적재 막힘 ${(ig.stuck || []).length}개 세션`}</span>` : '') +
      `<span class="small muted">작업 중 <b>${active}</b>/${live}${subs ? ` · 서브 ${subs}` : ''} · 오늘 출력 ${fmt(outToday)}</span>`;
    $('oMap').disabled = view === 'hq';
    $('oAll').disabled = view === 'map';
    drawProjects(st);
    // 연결 끊김 — 캔버스를 가리지 않는 띠 + 캔버스를 흐리게(보이는 모습이 끊기기 전 것이라는 표시)
    const down = c.status === 'down';
    $('oDown').hidden = !down;
    $('oStage').classList.toggle('offline', down || c.status === 'auth');
    if (down) {
      $('oDownWhy').textContent = `${c.reason || '브리지와 연락이 없습니다'} — ${new Date(c.since).toLocaleTimeString()}부터`;
      $('oDownNext').textContent = c.nextIn ? `${c.nextIn}초 뒤 다시 연결합니다 (시도 ${c.attempt})` : `연결하는 중입니다… (시도 ${c.attempt})`;
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
    } else if (a.kind === 'courier') {
      panel.show({ kind: 'infra', room: a.room, infra: 'courier', name: a.name, status: courierNow(a.plan) });
    } else if (a.kind === 'foreman') {
      panel.show({ kind: 'foreman', room: a.room === '_hq' ? null : a.room });
    } else if (a.kind === 'scribe') {
      panel.show({ kind: 'scribe', room: a.room });           // 서기실 — 무엇을 시킬지 고르는 창 · 할 일 · Notion 게시
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
      const vs = viewState(s), bg = s.background || [];
      return `<div class="tip-h">${esc(a.name)}</div><div class="tip-b">${esc({ ACTIVE: '작업 중', IDLE: '쉬는 중', WAITING: '기다리는 중', SUSPENDED: '멈춤', DORMANT: '종료' }[vs] || vs)}${
        a.act && a.act.go ? ` · ${zoneName(a.act.go)}` : ''}</div>${now ? `<div>${now}</div>` : ''}${
        s.subagents_running ? `<div>서브에이전트 ${s.subagents_running}개 돎</div>` : ''}${
        bg.length ? `<div>백그라운드 ${bg.length}개 돎${bg.map((x) => `<div class="tip-s">· ${esc(x.tool)} ${esc(short(x.description || x.task, 50))}</div>`).join('')}</div>` : ''}${
        a.act && a.act.flag ? `<div class="tip-s">${esc({ approval_pending: '승인 대기', stuck_turn: '끝 신호 없는 턴' }[a.act.flag] || a.act.flag)}</div>` : ''}${
        s.compact && s.compact.level ? `<div class="tip-s">📦 압축 ${s.compact.count}번 — ${s.compact.level === 'late' ? '늦었습니다' : '새 세션으로 넘어갈 때입니다'}</div>` : ''}
        <div class="tip-t">누르면 대화가 열립니다.</div>`;
    }
    if (a.kind === 'mini') return `<div class="tip-h">서브에이전트</div><div>${esc(a.name)}</div><div class="tip-t">누르면 부모 세션이 열립니다.</div>`;
    if (a.kind === 'infra') {
      const r = world.rooms.find((q) => q.name === a.room), st = r ? r['st_' + a.infra] : 'none';
      return `<div class="tip-h">${esc(a.name)}</div>${tipOf(INFRA_ROLE[a.infra])}<div class="tip-s">지금: ${esc(STATUS_KO[st] || st)}</div>`;
    }
    if (a.kind === 'courier') {
      const ch = a.plan && a.plan.ch, c = ch && ch.commits && ch.commits[0];
      return `<div class="tip-h">${esc(a.name)}</div><div class="tip-b">출하 라인 담당</div><div>커밋을 받아 단계마다 옮기는 사람입니다.</div>
        <div class="tip-s">${esc(courierNow(a.plan))}</div>${c ? `<div class="tip-t">${esc(c.short)} ${esc(short(c.subject || '', 70))}</div>` : ''}${
        a.plan && a.plan.queue.length ? `<div class="tip-t">대기 ${a.plan.queue.length}개</div>` : ''}<div class="tip-t">누르면 파이프라인이 열립니다.</div>`;
    }
    if (a.kind === 'foreman') return `<div class="tip-h">포먼</div>${tipOf(ZONE_ROLE.hq)}<div class="tip-t">자기 세션은 아직 없습니다.</div>`;
    if (a.kind === 'scribe') {
      const t = a.todo;
      return `<div class="tip-h">서기</div><div class="tip-b">문서 담당 — 회고 · 문서 점검 · README · CLAUDE.md · 나중에 할 일 · Notion 게시</div>${
        t && t.items && t.items.length ? `<div>할 일 ${t.items.length}개${t.items.slice(0, 3).map((x) => `<div class="tip-s">· ${esc(x.title)}</div>`).join('')}</div>` : ''}
        <div class="tip-t">누르면 일을 고르는 창이 열립니다.</div>`;
    }
    return `<div class="tip-h">${esc(a.name || '')}</div>`;
  }
  // 툴팁은 화면 전체가 하나(tip.js) — 이름표 · 캐릭터 · 버튼이 같은 모양 · 같은 지연으로 뜬다(11-05)
  cv.addEventListener('mousemove', (ev) => {
    const r = cv.getBoundingClientRect();
    const px = ev.clientX - r.left, py = ev.clientY - r.top;
    const hit = HITS.find((h) => px >= h.x && px <= h.x + h.w && py >= h.y && py <= h.y + h.h);
    let html = hit ? hit.tip : null, key = hit ? 'tag:' + hit.x + ':' + hit.y : null, onActor = false;
    if (!html && view !== 'map') {
      const [wx, wy] = toWorld(px, py);
      const a = actorAt(wx, wy);
      if (a) { html = actorTip(a); key = 'actor:' + a.key; onActor = true; }
    }
    cv.style.cursor = onActor ? 'pointer' : '';
    if (!html) { hideTip(); return; }
    showTip(html, ev.clientX, ev.clientY, key);
  });
  cv.addEventListener('mouseleave', () => { hideTip(); cv.style.cursor = ''; });
  // 현장을 옮겨도 고른 세션 · 패널은 그대로 둔다
  function go(v) { view = v; aim(); header(store.state); }
  $('oMap').onclick = () => go('hq');
  $('oAll').onclick = () => go('map');
  $('oProj').addEventListener('click', (ev) => { const b = ev.target.closest('[data-room]'); if (b) go(b.dataset.room); });
  // + 새 세션(11-05) — 지금 보고 있는 현장을 기본 프로젝트로. 띄우면 그 세션을 골라 패널에 연다
  const newSession = mountNewSession(store, { onCreated: (sid) => setTimeout(() => openSession(sid), 300) });
  $('oNew').onclick = () => newSession.open(view !== 'hq' && view !== 'map' && view !== '_lounge' ? view : null);
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
  return { go, theme, openSession, panel, actors, audit: () => audit(), propAudit: () => propAudit(), propSheet: (z, f) => propSheet(z, f), probe: (x, y) => probe(x, y), rects: (w) => decorRects(w), layoutAudit: () => layoutAudit(), layoutPlan: () => layoutPlan(), debug: () => [...actors.values()].map((a) => ({ key: a.key, room: a.room, x: String(a.x), y: String(a.y), tx: a.tx, ty: a.ty,
                                                                       anim: a.act && a.act.anim, go: a.act && a.act.go, face: a.face, dir: a.dir, char: a.char })) };
}

function hueOf(id) { return (id * 47) % 360; }
function short(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
