// FOREMAN 대시보드 — 데이터 계층(6단계). DOM을 모른다.
// 스냅샷(/api/dashboard)을 한 번 받고, WS(이벤트 · 턴 · 승인 · 세션 상태)로 고친다. 몇 초마다 스냅샷으로 어긋난 것을 맞춘다.
// 그리는 쪽은 subscribe(fn)으로 상태를 받는다 — 알림은 최대 초당 4번(이벤트가 초당 수십 개 와도 화면은 따라간다).
// 테마 렌더러로 바꿀 때는 render.js만 갈아 끼운다. 상태 모양은 아래 state 주석이 계약이다.

const EMIT_MS = 250;          // 그리기 알림 최소 간격
const RESNAP_MS = 15000;      // 스냅샷으로 맞추는 주기
const FEED_MAX = 40;          // 세션별 최근 활동 줄 수

export function charState(proc, ccStatus, openTurn) {
  // 서버(bridge/api/dashboard.py char_state)와 같은 규칙
  if (proc == null) return 'DORMANT';
  if (proc === 'T') return 'SUSPENDED';
  if (ccStatus === 'busy' || openTurn) return 'ACTIVE';
  return 'IDLE';
}

export class Store {
  constructor() {
    /* state — 그리는 쪽과의 계약
       conn:      { status: 'idle'|'connecting'|'up'|'down'|'auth', since, attempt, nextIn, reason }
       projects:  [{ name, label, sessionIds: [id…] }]       프로젝트 순서 · 세션 순서(스냅샷 기준)
       sessions:  Map<id, session>                            session은 /api/dashboard의 세션 + feed · replyPreview
       approvals: Map<id, approval>                           대기 중 + 막 끝난 것(status, 30초 뒤 사라짐)
       selected:  세션 id | null
       convo:     Map<id, { turns, loading, error }>
       generatedAt, hiddenDormant, lastInput: { sessionId, text, ok, ts }
       ver:       { grid, approvals, panel, conn } — 영역별로 바뀌면 1씩 늘어난다(그리는 쪽이 그 영역만 다시 그린다) */
    this.state = {
      conn: { status: 'idle', since: null, attempt: 0, nextIn: 0, reason: '' },
      projects: [], sessions: new Map(), approvals: new Map(), selected: null, convo: new Map(),
      generatedAt: null, hiddenDormant: 0, lastInput: null,
      ver: { grid: 0, approvals: 0, panel: 0, conn: 0 },
    };
    this.subs = new Set();
    this.dirty = false;
    this.emitTimer = null;
    this.lastEmit = 0;
    this.ws = null;
    this.wanted = false;
    this.everUp = false;
    this.retryTimer = null;
    this.watchdog = null;
    this.lastSeen = 0;
    this.hb = 15;
    this.snapTimer = null;
    this.snapSoon = null;
    this.convoSoon = new Map();
    this.byCc = new Map();     // cc_session_id → session id
  }

  // ── 토큰 ─────────────────────────────────────────────
  get token() { try { return localStorage.getItem('foremanToken') || ''; } catch { return this._tok || ''; } }
  set token(v) {
    v = (v || '').trim().replace(/^FOREMAN_API_TOKEN=/, '').replace(/^(['"])(.*)\1$/, '$2');
    this._tok = v;
    try { localStorage.setItem('foremanToken', v); } catch { /* 저장 못 해도 이 탭에서는 쓴다 */ }
  }
  headers(json) {
    const h = { Authorization: `Bearer ${this.token}` };
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }

  // ── 구독 · 그리기 알림(throttle) ───────────────────────
  subscribe(fn) { this.subs.add(fn); fn(this.state); return () => this.subs.delete(fn); }
  touch(...areas) {
    for (const a of areas) this.state.ver[a] += 1;
    this.dirty = true;
    if (this.emitTimer) return;
    const wait = Math.max(0, EMIT_MS - (Date.now() - this.lastEmit));
    this.emitTimer = setTimeout(() => {
      this.emitTimer = null;
      if (!this.dirty) return;
      this.dirty = false;
      this.lastEmit = Date.now();
      for (const fn of this.subs) fn(this.state);
    }, wait);
  }

  // ── 스냅샷 ───────────────────────────────────────────
  async loadSnapshot() {
    const r = await fetch('/api/dashboard', { headers: this.headers() });
    if (r.status === 401) { this.setConn('auth', '토큰이 맞지 않는다'); return; }
    if (!r.ok) return;
    const j = await r.json();
    const st = this.state;
    const keep = st.sessions;
    st.sessions = new Map();
    this.byCc.clear();
    st.projects = j.projects.map(p => ({ name: p.name, label: p.label, sessionIds: p.sessions.map(s => s.id) }));
    for (const p of j.projects) for (const s of p.sessions) {
      const old = keep.get(s.id);
      s.feed = old ? old.feed : [];
      s.replyPreview = old && old.open_turn && s.open_turn && old.open_turn.id === s.open_turn.id ? old.replyPreview : null;
      st.sessions.set(s.id, s);
      if (s.cc_session_id) this.byCc.set(s.cc_session_id, s.id);
    }
    // 승인: 스냅샷의 대기 목록이 기준. 막 끝난 것(status가 pending이 아님)은 남겨 둔다
    for (const [id, a] of st.approvals) if (a.status === 'pending' && !j.approvals.some(x => x.id === id)) st.approvals.delete(id);
    for (const a of j.approvals) st.approvals.set(a.id, { ...st.approvals.get(a.id), ...a, project: this.projectOf(a.session_id) });
    st.generatedAt = j.generated_at;
    st.hiddenDormant = j.hidden_dormant;
    if (st.selected && !st.sessions.has(st.selected)) st.selected = null;
    this.touch('grid', 'approvals', 'panel');
  }
  scheduleSnapshot(ms = 800) {
    if (this.snapSoon) return;
    this.snapSoon = setTimeout(() => { this.snapSoon = null; this.loadSnapshot().catch(() => {}); }, ms);
  }
  projectOf(sessionId) { const s = this.state.sessions.get(sessionId); return s ? s.project : null; }

  // ── 연결 ─────────────────────────────────────────────
  setConn(status, reason = '') {
    const c = this.state.conn;
    if (status === 'down' && c.status !== 'down') c.since = Date.now();
    if (status === 'up') c.since = null;
    c.status = status; c.reason = reason;
    this.touch('conn');
  }

  start() {
    this.wanted = true;
    this.state.conn.attempt = 0;
    clearInterval(this.snapTimer);
    this.snapTimer = setInterval(() => { if (this.state.conn.status === 'up') this.loadSnapshot().catch(() => {}); }, RESNAP_MS);
    this.open();
  }

  open() {
    clearTimeout(this.retryTimer);
    if (this.ws) { this.ws.onclose = null; this.ws.close(); }
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const sock = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws = sock;
    this.setConn(this.everUp ? 'down' : 'connecting', this.state.conn.reason);
    sock.onopen = () => sock.send(JSON.stringify({ type: 'auth', token: this.token }));
    sock.onmessage = (m) => {
      this.lastSeen = Date.now();
      const msg = JSON.parse(m.data);
      if (msg.type === 'batch') { for (const it of msg.items) this.apply(it); return; }
      this.apply(msg);
    };
    sock.onclose = (e) => {
      if (this.ws !== sock) return;
      if (e.code === 1008) { this.wanted = false; this.setConn('auth', e.reason || '토큰이 맞지 않는다'); return; }
      if (!this.wanted) return;
      this.setConn(this.everUp ? 'down' : 'connecting', e.code === 1006 ? '서버가 응답하지 않는다(1006)' : `연결이 닫혔다(${e.code})`);
      this.retry();
    };
    clearInterval(this.watchdog);
    this.lastSeen = Date.now();
    // 하트비트 두 번을 놓치면 끊긴 것으로 본다 — 서버가 멈췄는데 소켓은 안 닫힌 경우(README 3.10)
    this.watchdog = setInterval(() => {
      if (this.ws === sock && sock.readyState === 1 && Date.now() - this.lastSeen > this.hb * 2000 + 2000) sock.close(4000, 'heartbeat');
    }, 1000);
  }

  retry() {
    const c = this.state.conn;
    const wait = Math.min(15, 2 ** Math.min(c.attempt, 4));
    c.attempt += 1;
    c.nextIn = wait;
    this.touch('conn');
    const tick = setInterval(() => { c.nextIn = Math.max(0, c.nextIn - 1); this.touch('conn'); }, 1000);
    this.retryTimer = setTimeout(() => { clearInterval(tick); this.open(); }, wait * 1000);
  }
  retryNow() { this.state.conn.attempt = 0; this.open(); }

  // ── 메시지 적용 ───────────────────────────────────────
  apply(msg) {
    const st = this.state;
    switch (msg.type) {
      case 'hello':
        this.hb = msg.heartbeat_s; this.everUp = true; st.conn.attempt = 0;
        this.setConn('up');
        this.loadSnapshot().catch(() => {});
        if (st.selected) this.loadConversation(st.selected);
        return;
      case 'ping': return;
      case 'resync': this.scheduleSnapshot(0); return;
      case 'session_state': return this.onSessionState(msg);
      case 'turn': return this.onTurn(msg);
      case 'approval': return this.onApproval(msg);
      case 'event': return this.onEvent(msg.event);
    }
  }

  sessionFor(id) {
    const s = this.state.sessions.get(id);
    if (!s && id != null) this.scheduleSnapshot();   // 처음 보는 세션 — 스냅샷으로 가져온다
    return s;
  }

  onSessionState(m) {
    const id = this.byCc.get(m.cc_session_id);
    const s = id != null ? this.state.sessions.get(id) : null;
    if (!s) { if (m.proc) this.scheduleSnapshot(); return; }
    s.proc = m.proc; s.cc_status = m.cc_status; s.pid = m.pid;
    s.state = charState(s.proc, s.cc_status, s.open_turn);
    if (!m.proc) s.injectable = false;
    this.touch('grid', ...(this.state.selected === s.id ? ['panel'] : []));
  }

  onTurn(m) {
    const s = this.sessionFor(m.session_id);
    if (!s) return;
    if (m.op === 'open') {
      s.open_turn = { id: m.turn_id, origin: m.origin, started_at: m.ts, prompt: s.open_turn && s.open_turn.id === m.turn_id ? s.open_turn.prompt : null };
      s.replyPreview = null;
    } else if (s.open_turn && s.open_turn.id === m.turn_id) {
      s.open_turn = null;
      this.pushFeed(s, m.ts, 'turn', `턴 끝 — ${m.reason}`);
      if (this.state.selected === s.id) this.convoLater(s.id);
    }
    s.state = charState(s.proc, s.cc_status, s.open_turn);
    this.touch('grid', ...(this.state.selected === s.id ? ['panel'] : []));
  }

  onApproval(m) {
    const a = { ...m.approval, project: m.approval.project ?? this.projectOf(m.approval.session_id) };
    if (m.op === 'pending') a.status = 'pending';
    this.state.approvals.set(a.id, a);
    if (m.op === 'resolved') setTimeout(() => { this.state.approvals.delete(a.id); this.touch('approvals', 'grid'); }, 30000);
    this.touch('approvals', 'grid');
  }

  onEvent(e) {
    if (e.session_id == null) return;
    const s = this.sessionFor(e.session_id);
    if (!s) return;
    const sub = e.subagent_id ? ' ↳서브' : '';
    switch (e.type) {
      case 'tool_use':
        if (e.source !== 'transcript') return;
        s.activity = { tool: e.tool, target: e.target || '', ts: e.ts, subagent: !!e.subagent_id };
        this.pushFeed(s, e.ts, 'tool', `${e.tool}${sub} ${e.target || ''}`);
        break;
      case 'start':
        if (e.source === 'transcript' && e.target) {
          s.open_turn = { ...(s.open_turn || {}), id: e.turn_id, prompt: e.target, started_at: (s.open_turn && s.open_turn.started_at) || e.ts };
          this.pushFeed(s, e.ts, 'prompt', `입력: ${e.target}`);
        }
        break;
      case 'assistant_msg':
        if (e.subagent_id || !e.summary || e.summary.startsWith('(thinking')) return;
        s.replyPreview = e.summary;
        this.pushFeed(s, e.ts, 'reply', `응답: ${e.summary}`);
        break;
      case 'subagent_start': s.subagents_running = (s.subagents_running || 0) + 1; this.pushFeed(s, e.ts, 'sub', '서브에이전트 시작'); break;
      case 'subagent_stop': s.subagents_running = Math.max(0, (s.subagents_running || 0) - 1); this.pushFeed(s, e.ts, 'sub', '서브에이전트 끝'); break;
      case 'input': {
        const pl = e.payload || {};
        this.pushFeed(s, e.ts, 'input', pl.refused ? `주입 거부: ${pl.refused}` : `주입${pl.queued ? '(대기열)' : ''}: ${e.target || ''}`);
        break;
      }
      case 'approval_req': {
        const pl = e.payload || {};
        if (pl.decision !== 'ask') return;
        this.pushFeed(s, e.ts, 'ask', `승인 ${pl.enforced ? '필요' : '필요했을 것(관찰)'}: ${e.tool} ${e.target || ''} — ${pl.rule}`);
        break;
      }
      case 'error': this.pushFeed(s, e.ts, 'error', `오류: ${e.summary || ''}`); break;
      default: return;
    }
    s.last_ts = e.ts;
    s.state = charState(s.proc, s.cc_status, s.open_turn);
    this.touch('grid', ...(this.state.selected === s.id ? ['panel'] : []));
  }

  pushFeed(s, ts, kind, text) {
    s.feed.push({ ts, kind, text: (text || '').slice(0, 300) });
    if (s.feed.length > FEED_MAX) s.feed.splice(0, s.feed.length - FEED_MAX);
  }

  // ── 동작 ─────────────────────────────────────────────
  select(id) {
    this.state.selected = id;
    this.touch('panel', 'grid');
    if (id != null) this.loadConversation(id);
  }
  convoLater(id) {
    clearTimeout(this.convoSoon.get(id));
    this.convoSoon.set(id, setTimeout(() => this.loadConversation(id), 1500));  // 마지막 응답 줄이 적재될 시간
  }
  async loadConversation(id) {
    const c = this.state.convo.get(id) || { turns: [] };
    c.loading = true; c.error = null;
    this.state.convo.set(id, c);
    this.touch('panel');
    try {
      const r = await fetch(`/api/sessions/${id}/conversation?limit=15`, { headers: this.headers() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      c.turns = (await r.json()).turns;
    } catch (err) { c.error = String(err.message || err); }
    c.loading = false;
    this.touch('panel');
  }
  async sendInput(id, text, command) {
    const r = await fetch(`/api/sessions/${id}/input`, { method: 'POST', headers: this.headers(true), body: JSON.stringify({ text, command }) });
    const j = await r.json().catch(() => ({}));
    const res = r.status === 409 ? { ok: false, msg: `거부 — ${j.refused}` }
      : r.status === 202 ? { ok: true, msg: j.queued ? '대기열에 넣었다(세션이 일하는 중)' : '보냈다 — 새 턴', guarded: j.guarded }
      : r.status === 504 ? { ok: false, msg: '제출이 확인되지 않았다 — 입력 칸에 남았을 수 있다' }
      : { ok: false, msg: `실패 HTTP ${r.status}` };
    this.state.lastInput = { sessionId: id, ts: Date.now(), ...res };
    this.touch('panel');
    return res;
  }
  async decide(aid, decision, message) {
    const r = await fetch(`/api/approvals/${aid}`, { method: 'POST', headers: this.headers(true), body: JSON.stringify({ decision, message: message || null }) });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      const a = this.state.approvals.get(aid);
      if (a) { a.error = j.detail || `HTTP ${r.status}`; this.touch('approvals'); }
    }
  }
}
