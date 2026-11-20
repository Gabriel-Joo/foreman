// FOREMAN 대시보드 — 데이터 계층(6단계). DOM을 모른다.
// 스냅샷(/api/dashboard)을 한 번 받고, WS(이벤트 · 턴 · 승인 · 세션 상태)로 고친다. 몇 초마다 스냅샷으로 어긋난 것을 맞춘다.
// 그리는 쪽은 subscribe(fn)으로 상태를 받는다 — 알림은 최대 초당 4번(이벤트가 초당 수십 개 와도 화면은 따라간다).
// 테마 렌더러로 바꿀 때는 render.js만 갈아 끼운다. 상태 모양은 아래 state 주석이 계약이다.

// 점검 페이지(11-11 사용자 — tools/screen.py를 라이브에 돌리니 저절로 열린 패널이 「보고 옴」을 읽음으로 남겨 227의 보고가 사라졌다).
// screen.py는 모든 주소에 ?probe=1을 붙인다. 같은 탭 안에서 테마를 바꿔도 유지(sessionStorage). 자동화 브라우저(navigator.webdriver)도 같게.
// 점검 페이지는 사람이 본 것이 아니므로 읽음 같은 「사람 흔적」을 남기지 않는다 — 헤더 X-Foreman-Probe로 서버도 거절한다
export const PROBE = (() => {
  let on = false;
  try {
    if (new URLSearchParams(location.search).has('probe')) sessionStorage.setItem('foremanProbe', '1');
    on = sessionStorage.getItem('foremanProbe') === '1';
  } catch { /* 저장소를 못 쓰면 주소만 */ }
  try { on = on || new URLSearchParams(location.search).has('probe') || !!navigator.webdriver; } catch { /* node 시험 */ }
  return on;
})();
const EMIT_MS = 250;          // 그리기 알림 최소 간격
const RESNAP_MS = 15000;      // 스냅샷으로 맞추는 주기
const FEED_MAX = 40;          // 세션별 최근 활동 줄 수
// 입력 확인 결과를 묻는 간격(ms, 11-20). 합이 서버의 늦게 다시 보기 상한(bridge/inject.py LATE_S, 잰 값이 아님)보다 조금 길다
const INPUT_POLL_MS = [2000, 3000, 5000, 5000, 10000, 10000, 15000, 15000, 15000, 15000, 15000, 15000, 15000];
export const FOLD_KEEP = 3;   // 세션마다 남기는 답한 카드(접힌 줄) 수(11-10) — 넘으면 오래된 것부터 지운다. 다시 보기는 승인 기록에
export function pruneResolved(approvals, sid) {
  const done = [...approvals.values()].filter((x) => x.status !== 'pending' && x.session_id === sid).sort((x, y) => x.id - y.id);
  for (const x of done.slice(0, Math.max(0, done.length - FOLD_KEEP))) approvals.delete(x.id);
}

// 세션 간 메시지(SendMessage) 줄 꼬리 — 받는 쪽 트랜스크립트로 본 도착 · 읽음(11-09, bridge/xmsg.py)
export function xmsgText(x) {
  if (!x || !Object.keys(x).length) return '';
  const hm = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const to = x.to_label ? ` (${x.to_label})` : '';
  if (x.read_at) return `, ✓ 읽음 ${hm(x.read_at)}${x.how === 'mid_turn' ? ' · 작업 중에' : ''}${to}`;
  if (x.arrived_at) return `, 도착 ${hm(x.arrived_at)}, 아직 안 읽음${to}`;
  return ', 도착 기록 없음(받는 세션이 꺼졌거나 FOREMAN이 보지 않는 세션)';
}

export function charState(proc, ccStatus, openTurn) {
  // 서버(bridge/api/dashboard.py char_state)와 같은 규칙 — 살아 있으면 CC가 적는 status가 기준, 열린 턴은 status를 모를 때만
  if (proc == null) return 'DORMANT';
  if (proc === 'T') return 'SUSPENDED';
  if (ccStatus != null) return ccStatus === 'busy' ? 'ACTIVE' : 'IDLE';
  return openTurn ? 'ACTIVE' : 'IDLE';
}
export function stuckTurn(s) {
  // 열린 턴이 있는데 CC는 일하지 않는다 — 끝 신호 없이 멈춘 턴
  return !!(s.open_turn && s.proc && s.proc !== 'T' && s.cc_status != null && s.cc_status !== 'busy');
}

export class Store {
  constructor() {
    /* state — 그리는 쪽과의 계약
       conn:      { status: 'idle'|'connecting'|'up'|'down'|'auth', since, attempt, nextIn, reason }
       projects:  [{ name, label, sessionIds: [id…] }]       프로젝트 순서 · 세션 순서(스냅샷 기준)
       sessions:  Map<id, session>                            session은 /api/dashboard의 세션 + feed · replyPreview
       approvals: Map<id, approval>                           대기 중 + 답한 것(status). 답한 것은 그 세션 패널에 접힌 줄로 남고 세션마다 FOLD_KEEP개까지
       selected:  세션 id | null
       convo:     Map<id, { turns, loading, error }>
       generatedAt, hiddenDormant, lastInput: { sessionId, text, ok, ts }
       terminal, pipeline                                     셸 패널, 파이프라인(아래 칸 주석)
       ver:       { grid, approvals, panel, conn, term, pipe }. 영역별로 바뀌면 1씩 늘어난다(그리는 쪽이 그 영역만 다시 그린다) */
    this.state = {
      conn: { status: 'idle', since: null, attempt: 0, nextIn: 0, reason: '' },
      projects: [], sessions: new Map(), approvals: new Map(), selected: null, convo: new Map(),
      generatedAt: null, hiddenDormant: 0, lastInput: null,
      pendingModel: new Map(),     // 세션 id → { model, label, queued, ts } — /model을 보냈고 아직 응답 모델이 안 바뀜(11-05)
      // 7단계 터미널 패널: enabled · running, requests(Map id → CC가 부탁한 명령), result(마지막 결과), shell(최근 친 명령)
      terminal: { enabled: false, running: false, requests: new Map(), result: null, shell: [], openReq: 0 },
      // 8단계 파이프라인: 프로젝트 이름 → { infra, chains, waiting } (/api/pipeline)
      pipeline: new Map(),
      ver: { grid: 0, approvals: 0, panel: 0, conn: 0, term: 0, pipe: 0 },
    };
    this.subs = new Set();
    this.inputPollMs = INPUT_POLL_MS;                       // 시험에서 바꾼다
    this.sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
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
    if (PROBE) h['X-Foreman-Probe'] = '1';
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
    if (this.demo) return;                    // 시연 재생 중(13, demo.js) — 실제 데이터로 덮지 않는다
    const r = await fetch('/api/dashboard', { headers: this.headers() });
    if (r.status === 401) { this.setConn('auth', '토큰이 맞지 않습니다'); return; }
    if (!r.ok) return;
    const j = await r.json();
    this.checkUi(j.ui);
    this.applySnapshot(j);
  }
  // 화면 코드 지문(11-09, bridge/uiver.py) — 처음 받은 것과 다르면 이 탭은 옛 코드로 돈다. 맨 위에 [새로 고침] 띠.
  // 저절로 고치지 않는다(입력 칸에 쓰던 글이 날아간다). 11-09: 질문 카드 버튼을 만들었는데 탭이 옛 코드라 안 보였다
  checkUi(ver) {
    if (!ver) return;
    if (!this.uiVer) { this.uiVer = ver; return; }
    if (ver === this.uiVer || document.getElementById('uiStale')) return;
    const d = document.createElement('div');
    d.id = 'uiStale';
    d.style.cssText = 'position:fixed;top:0;left:50%;transform:translateX(-50%);z-index:9999;background:#f2c14e;color:#141414;'
      + 'padding:6px 12px;border-radius:0 0 8px 8px;font:600 15px system-ui,sans-serif;display:flex;gap:10px;align-items:center;box-shadow:0 2px 8px #0008';
    d.innerHTML = '<span>화면 코드가 바뀌었습니다. 새로 고쳐야 바뀐 기능이 보입니다.</span>'
      + '<button style="font:inherit;padding:2px 10px;cursor:pointer" title="새로 고침 — 이 페이지를 다시 불러옵니다. 입력 칸에 쓰던 글은 사라집니다.">새로 고침</button>';
    d.querySelector('button').onclick = () => location.reload();
    document.body.appendChild(d);
  }
  // 스냅샷(/api/dashboard 모양)을 상태에 넣는다 — 시연 재생은 대본의 스냅샷을 여기로 넣는다(같은 코드)
  applySnapshot(j) {
    const st = this.state;
    const keep = st.sessions;
    st.sessions = new Map();
    this.byCc.clear();
    st.projects = j.projects.map(p => ({ name: p.name, label: p.label, sessionIds: p.sessions.map(s => s.id) }));
    for (const p of j.projects) for (const s of p.sessions) {
      const old = keep.get(s.id);
      s.feed = old ? old.feed : [];
      s.replyAt = old ? old.replyAt : 0;     // 화면이 받은 "새 답" 시각 — 스냅샷을 다시 받아도 잇는다
      s.replyPreview = old && old.open_turn && s.open_turn && old.open_turn.id === s.open_turn.id ? old.replyPreview : null;
      st.sessions.set(s.id, s);
      if (s.cc_session_id) this.byCc.set(s.cc_session_id, s.id);
    }
    // 승인: 스냅샷의 대기 목록이 기준. 막 끝난 것(status가 pending이 아님)은 남겨 둔다
    for (const [id, a] of st.approvals) if (a.status === 'pending' && !j.approvals.some(x => x.id === id)) st.approvals.delete(id);
    for (const a of j.approvals) st.approvals.set(a.id, { ...st.approvals.get(a.id), ...a, project: this.projectOf(a.session_id) });
    st.generatedAt = j.generated_at;
    st.hiddenDormant = j.hidden_dormant;
    st.ingest = j.ingest || null;   // 적재(수집기) 상태 — 막히면 머리에 띄운다(11-03)
    if (j.terminal) {
      const t = st.terminal;
      t.enabled = !!j.terminal.enabled; t.running = !!j.terminal.running;
      t.requests = new Map((j.terminal.pending || []).map(r => [r.id, r]));
    }
    if (st.selected && !st.sessions.has(st.selected)) st.selected = null;
    this.touch('grid', 'approvals', 'panel', 'term');
  }
  async loadPipeline() {
    if (this.demo) return;
    const r = await fetch('/api/pipeline', { headers: this.headers() });
    if (!r.ok) return;
    const j = await r.json();
    this.state.pipeline = new Map((j.projects || []).map((p) => [p.project, p]));
    this.touch('pipe');
  }
  scheduleSnapshot(ms = 800) {
    if (this.snapSoon || this.demo) return;
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
      if (e.code === 1008) { this.wanted = false; this.setConn('auth', e.reason || '토큰이 맞지 않습니다'); return; }
      if (!this.wanted) return;
      this.setConn(this.everUp ? 'down' : 'connecting', e.code === 1006 ? '서버가 응답하지 않습니다(1006)' : `연결이 닫혔습니다(${e.code})`);
      this.retry();
    };
    clearInterval(this.watchdog);
    this.lastSeen = Date.now();
    // 하트비트 두 번을 놓치면 끊긴 것으로 본다 — 서버가 멈췄는데 소켓은 안 닫힌 경우(docs/00_design.md 3.10)
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
        this.checkUi(msg.ui);
        this.setConn('up');
        this.loadSnapshot().catch(() => {});
        // 한 번 인증으로 둘 다 — 같은 토큰으로 터미널 쿠키도 받는다(iframe은 헤더를 못 붙여 쿠키가 필요하다).
        // 브리지를 다시 띄우면 쿠키가 사라지므로 연결될 때마다 새로 받는다
        this.terminalSession().then(() => { this.state.terminal.cookieAt = Date.now(); this.touch('term'); }).catch(() => {});
        this.loadPipeline().catch(() => {});
        if (st.selected) this.loadConversation(st.selected);
        return;
      case 'ping': return;
      case 'resync': this.scheduleSnapshot(0); return;
      case 'session_state': return this.onSessionState(msg);
      case 'turn': return this.onTurn(msg);
      case 'approval': return this.onApproval(msg);
      case 'event': return this.onEvent(msg.event);
      case 'foreman':                        // 디스패처가 계획을 세우기 시작 · 끝 · 시작 · 버림(11-08) — 감독실 캐릭터가 다시 읽는다
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('foreman-state'));
        return;
      case 'usage':                          // 사용량을 새로 읽었다(11-08) — 머리 칩이 바로 다시 읽는다
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('foreman-usage'));
        return;
      case 'pipeline':                       // 단계가 바뀌었다 — 몰려와도 한 번만 다시 읽는다
        clearTimeout(this.pipeSoon);
        this.pipeSoon = setTimeout(() => this.loadPipeline().catch(() => {}), 500);
        return;
      case 'terminal_request': {
        const t = st.terminal;
        for (const [id, r] of t.requests) if (r.session_id === msg.request.session_id) t.requests.delete(id);
        t.requests.set(msg.request.id, msg.request);
        t.openReq += 1;                      // 패널을 올리라는 신호
        this.touch('term');
        return;
      }
      case 'terminal_result': {
        const t = st.terminal;
        t.requests.delete(msg.request_id);
        if (!msg.dismissed) t.result = { ...msg, project: this.projectOf(msg.session_id), at: Date.now() };
        this.touch('term');
        return;
      }
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
      s.api_stop = null;                       // 11-13 새 턴이 시작되면 「API 오류로 멈춤」은 풀린다(서버 api_stops와 같은 기준)
    } else if (s.open_turn && s.open_turn.id === m.turn_id) {
      s.open_turn = null;
      // 11-13 API 오류로 닫힌 턴 — 종류 · 까닭(api_stop)은 스냅샷에만 있어 곧바로 받는다(15초 주기를 기다리면 그동안 쉼으로 보인다)
      if (m.reason === 'stop_failure') this.scheduleSnapshot();
      s.replyAt = Date.now();                  // 새 답이 왔다 — 머리말 프로젝트 줄이 "안 본 답" 점을 붙인다(11-05)
      this.pushFeed(s, m.ts, 'turn', `턴 끝: ${m.reason}`);
      if (this.state.selected === s.id) this.convoLater(s.id);
    }
    s.state = charState(s.proc, s.cc_status, s.open_turn);
    this.touch('grid', ...(this.state.selected === s.id ? ['panel'] : []));
  }

  onApproval(m) {
    const a = { ...m.approval, project: m.approval.project ?? this.projectOf(m.approval.session_id) };
    if (m.op === 'pending') a.status = 'pending';
    this.state.approvals.set(a.id, a);
    // 11-10 답한 카드는 30초 뒤 지우지 않고 그 세션 패널에서 한 줄로 접힌다 — 사람이 [×]로 치운다. 세션마다 최근 FOLD_KEEP줄만 남긴다
    if (m.op === 'resolved') pruneResolved(this.state.approvals, a.session_id);
    this.touch('approvals', 'grid');
  }
  dismissApproval(aid) {
    const a = this.state.approvals.get(aid);
    if (a && a.status !== 'pending') { this.state.approvals.delete(aid); this.touch('approvals'); }
  }

  onEvent(e) {
    if (e.source === 'shell') {              // 터미널 패널에서 친 명령 — 셸 세션은 카드가 아니다
      const t = this.state.terminal;
      t.shell.push({ ts: e.ts, cmd: e.target || '', exit: (e.payload || {}).exit });
      if (t.shell.length > 20) t.shell.splice(0, t.shell.length - 20);
      this.touch('term');
      return;
    }
    if (e.session_id == null) return;
    const s = this.sessionFor(e.session_id);
    if (!s) return;
    const sub = e.subagent_id ? ' ↳서브' : '';
    switch (e.type) {
      case 'tool_use':
        if (e.source !== 'transcript') return;
        s.activity = { tool: e.tool, target: e.target || '', ts: e.ts, subagent: !!e.subagent_id, description: e.description || null };
        this.pushFeed(s, e.ts, 'tool', `${e.tool}${sub} ${e.target || ''}`, e.id);
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
      case 'queued':                           // 작업 중에 보낸 글이 열린 턴에 끼어들었다 — 대화에 내 글로 뜨게 다시 읽는다(11-05)
        if (this.state.selected === s.id) this.convoLater(s.id);
        return;
      case 'input': {
        const pl = e.payload || {};
        if (pl.late) {
          // 늦게 다시 본 결과(11-20). 「주입:」이 아니라 「늦게 확인:」으로, 걸린 시간을 붙인다(120초 상한을 맞출 근거)
          const body = (e.target || '').replace(/^\(늦게 확인\) /, '');      // 옛 줄은 글 앞에 이 말이 붙어 있었다
          const waited = pl.waited_s != null ? ` (${Math.round(pl.waited_s)}초 뒤)` : '';
          this.pushFeed(s, e.ts, pl.late === 'not_found' ? 'error' : 'input', `늦게 확인: ${body}${waited}`);
          break;
        }
        this.pushFeed(s, e.ts, 'input', pl.refused ? `주입 거부: ${pl.refused}` : `주입${pl.queued ? '(대기열)' : ''}: ${e.target || ''}`);
        break;
      }
      case 'approval_req': {
        const pl = e.payload || {};
        if (pl.decision !== 'ask') return;
        this.pushFeed(s, e.ts, 'ask', `승인 ${pl.enforced ? '필요' : '필요했을 것(관찰)'}: ${e.tool} ${e.target || ''} (규칙 ${pl.rule})`);
        break;
      }
      case 'error': this.pushFeed(s, e.ts, 'error', `오류: ${e.summary || ''}`); break;
      case 'term_request': this.pushFeed(s, e.ts, 'ask', `셸 부탁: ${e.target || ''}`); break;
      case 'term_result': {
        const pl = e.payload || {};
        this.pushFeed(s, e.ts, pl.delivered ? 'input' : 'error',
          `셸 결과(종료 ${pl.exit}) ${pl.delivered ? '전달' : `전달 못 함(${pl.refused || ''})`}: ${e.target || ''}`);
        break;
      }
      default: return;
    }
    s.last_ts = e.ts;
    s.state = charState(s.proc, s.cc_status, s.open_turn);
    this.touch('grid', ...(this.state.selected === s.id ? ['panel'] : []));
  }

  pushFeed(s, ts, kind, text, eid = null) {
    if (eid && s.feed.some((f) => f.eid === eid)) return;      // DB에서 먼저 받은 줄과 겹치지 않게
    s.feed.push({ ts, kind, text: (text || '').slice(0, 300), eid });
    if (s.feed.length > FEED_MAX) s.feed.splice(0, s.feed.length - FEED_MAX);
  }

  // ── 동작 ─────────────────────────────────────────────
  select(id) {
    this.state.selected = id;
    this.touch('panel', 'grid');
    if (id != null) { this.loadConversation(id); this.loadActivity(id); }
  }
  // 최근 도구 호출을 DB에서(11-05) — 화면을 연 뒤의 것만 쌓이던 "최근 활동"을 처음부터 채운다. 실시간 줄(입력 · 응답 · 턴 끝)은 그 뒤에 이어 붙는다
  async loadActivity(id) {
    try {
      const r = await fetch(`/api/sessions/${id}/activity?limit=${FEED_MAX}`, { headers: this.headers() });
      if (!r.ok) return;
      const j = await r.json();
      const s = this.state.sessions.get(id);
      if (!s) return;
      const have = new Map(s.feed.filter((f) => f.eid).map((f) => [f.eid, f]));
      const line = (x) => `${x.tool}${x.subagent ? ' ↳서브' : ''} ${x.target || ''}`.slice(0, 300) + xmsgText(x.xmsg);
      for (const x of j.items) { const f = have.get(x.id); if (f && x.xmsg) f.text = line(x); }   // 읽음은 나중에 바뀐다
      const add = j.items.filter((x) => !have.has(x.id)).map((x) => ({
        ts: x.ts, kind: x.status === 'error' ? 'error' : 'tool', eid: x.has_body ? x.id : null, text: line(x) }));
      s.feed = [...add, ...s.feed].sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0)).slice(-FEED_MAX);
      if (this.state.selected === id) this.touch('panel');
    } catch { /* 화면 편의 — 못 받아도 실시간 줄은 쌓인다 */ }
  }
  // 사람이 붙인 세션 이름(11-05) — null이면 자동 제목(CC가 붙인 것)으로
  async setTitle(id, title) {
    const r = await fetch(`/api/sessions/${id}/title`, { method: 'PUT', headers: this.headers(true), body: JSON.stringify({ title }) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const s = this.state.sessions.get(id);
    if (s) s.custom_title = j.custom_title;
    this.touch('grid', 'panel');
    return j;
  }
  // 세션 역할 바꾸기(11-09) — 허용 값만(서버가 거부하면 그 사유를 던진다). 역할 캐릭터도 서버가 옮긴다 — 화면은 다음 스냅숏에서
  async setRole(id, role) {
    const r = await fetch(`/api/sessions/${id}/role`, { method: 'PUT', headers: this.headers(true), body: JSON.stringify({ role }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.refused || (r.status === 422 ? '고를 수 없는 역할입니다' : `HTTP ${r.status}`));
    const s = this.state.sessions.get(id);
    if (s) s.role = j.role;
    this.touch('grid', 'panel');
    return j;
  }
  // 답 기다림 끄기(11-11, 받은 할 일 #13) — 지금 잡힌 응답 하나만. 다음 응답이 오면 서버가 다시 판정한다
  async asksOff(id) {
    const r = await fetch(`/api/sessions/${id}/asks-off`, { method: 'POST', headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.ok) throw new Error(j.note || j.detail || `HTTP ${r.status}`);
    const s = this.state.sessions.get(id);
    if (s && j.escalate_id && s.escalate) s.escalate = { ...s.escalate, question: null };   // 관리자가 올린 물음을 끔(11-13)
    else if (s) s.asks = null;
    this.touch('grid', 'panel');
    return j;
  }
  // 「사용자에게 보고함」 읽음(11-13) — 관리자가 사람에게 올린 보고. 그 관리자 패널을 열면 opanel이 부른다
  async escalateRead(id, escId) {
    if (PROBE || this.demo) return { ok: false, note: '점검 · 시연 화면은 읽음으로 세지 않습니다' };
    const r = await fetch(`/api/sessions/${id}/escalate-read?id=${encodeURIComponent(escId)}`, { method: 'POST', headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.note || j.detail || `HTTP ${r.status}`);
    const s = this.state.sessions.get(id);
    if (s && s.escalate && s.escalate.report && s.escalate.report.id === escId) s.escalate = { ...s.escalate, report: null };
    this.touch('grid', 'panel');
    return j;
  }
  // 아직 안 본 물음을 [봤다]로 지움(11-17). 사람이 누를 때만 부른다(패널을 연 것만으로는 지우지 않는다)
  async escalateSeen(id, escId) {
    if (PROBE || this.demo) return { ok: false, note: '점검이나 시연 화면은 봤다로 세지 않습니다' };
    const r = await fetch(`/api/sessions/${id}/escalate-seen?id=${encodeURIComponent(escId)}`, { method: 'POST', headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.ok) throw new Error(j.note || j.detail || `HTTP ${r.status}`);
    const s = this.state.sessions.get(id);
    if (s && s.escalate && s.escalate.unseen) s.escalate = { ...s.escalate, unseen: s.escalate.unseen.filter((u) => u.id !== escId) };
    this.touch('grid', 'panel');
    return j;
  }
  // 보고 옴 읽음(11-11) — 그 세션 패널을 열면 opanel이 부른다. 다음 응답이 오면 서버가 다시 띄운다
  async reportRead(id, eventId) {
    if (PROBE || this.demo) return { ok: false, note: '점검 · 시연 화면은 읽음으로 세지 않습니다' };
    const r = await fetch(`/api/sessions/${id}/report-read?event_id=${encodeURIComponent(eventId)}`, { method: 'POST', headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.note || j.detail || `HTTP ${r.status}`);
    const s = this.state.sessions.get(id);
    if (s && s.report && s.report.event_id === eventId) s.report = null;
    this.touch('grid', 'panel');
    return j;
  }
  async eventDetail(eid) {
    const r = await fetch(`/api/events/${eid}/detail`, { headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    return j;
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
    // 결과 글(11-05) — 잘 갔으면 한 마디("보냈습니다."), 잘못됐을 때만 무엇이 왜인지와 할 일. 내부 동작(기록 확인 등)은 말하지 않는다
    // 202 + verified:false + check(11-20) = 입력 칸은 비었지만 기록에서는 아직 못 찾았다. 서버가 뒤에서 다시 보고 있으므로
    // 「확인 중」으로 띄우고 결과를 물어 바꾼다(followInput). 504는 입력 칸에 글이 남았거나(left) 화면도 기록도 못 읽은 것뿐이다
    const checking = r.status === 202 && j.verified === false && !!j.check;
    const sent = j.queued ? '보냈습니다. 작업이 끝나면 이어서 전달됩니다.' : '보냈습니다.';
    const res = r.status === 409 ? { ok: false, msg: `보내지 못했습니다. ${j.refused}` }
      : r.status === 202 ? { ok: true, msg: checking ? `${sent} 기록을 확인하는 중입니다.` : sent, pending: checking }
      : r.status === 504 ? (j.left_in_box
          ? { ok: false, msg: '제출되지 않았습니다. 입력 칸에 글이 남아 있으니 대화창에서 Enter를 누르거나 지워 주세요.' }
          : { ok: false, msg: '제출됐는지 확인하지 못했습니다. 대화창에서 입력 칸을 확인해 주세요.' })
      : { ok: false, msg: `보내지 못했습니다 (HTTP ${r.status}).` };
    // 11-09 — 입력 줄을 가리던 창을 Esc로 닫고 보냈다(bridge/inject.clear_screen). 반복되는지 알 수 있게 한 마디. 11-13부터 창 이름도
    if (j.esc && r.status !== 409) res.msg += ` 떠 있던 ${j.dialog ? `${j.dialog} 창` : '설정 화면'}을 Esc ${j.esc}번으로 닫고 보냈습니다.`;
    const mine = this.state.lastInput = { sessionId: id, ts: Date.now(), ...res };
    if (res.ok) this.convoLater(id);           // 새 턴이든 대기열이든 대화에 내 글이 뜨게
    this.touch('panel');
    if (checking) this.followInput(id, j.check, mine, j.queued).catch(() => { /* 물음이 실패해도 보냈다는 글은 남는다 */ });
    return res;
  }
  // 늦게 다시 보기의 결과를 물어 「확인 중」 글을 바꾼다(GET /api/sessions/{id}/input/{check}). 서버가 120초(inject.LATE_S) 안에 끝내므로
  // 그 뒤까지 물으면 멈춘다. 그 사이에 새로 보낸 글이 있으면(lastInput이 바뀜) 그 글을 덮지 않는다
  async followInput(id, check, mine, queued) {
    const end = (msg, ok) => {
      if (this.state.lastInput !== mine) return;
      this.state.lastInput = { sessionId: id, ts: Date.now(), ok, msg };
      this.touch('panel');
    };
    for (const ms of this.inputPollMs) {
      await this.sleep(ms);
      const r = await fetch(`/api/sessions/${id}/input/${encodeURIComponent(check)}`, { headers: this.headers() });
      if (r.status === 404) return end('보냈습니다. 기록 확인 결과를 알 수 없습니다. 대화에서 내 글이 보이는지 확인해 주세요.', true);
      if (!r.ok) continue;
      const c = await r.json();
      if (c.state === 'checking') continue;
      if (c.state === 'not_found') return end('보냈지만 기록에서 찾지 못했습니다. 대화창에서 입력 칸을 확인해 주세요.', false);
      this.convoLater(id);                     // 늦게 기록된 글이 대화에 뜨게
      return end(queued ? '보냈습니다. 작업이 끝나면 이어서 전달됩니다.' : '보냈습니다.', true);
    }
    return end('보냈습니다. 기록 확인이 끝나지 않았습니다. 대화에서 내 글이 보이는지 확인해 주세요.', true);
  }
  // 모델 바꾸기(11-05) — 그 세션에 /model <id>. 화면은 다음 응답의 모델이 고른 것과 같아질 때까지 "→ 고른 모델"을 보인다
  async switchModel(id, model, label) {
    const r = await fetch(`/api/sessions/${id}/model`, { method: 'POST', headers: this.headers(true), body: JSON.stringify({ model }) });
    const j = await r.json().catch(() => ({}));
    // 11-20: 입력 칸이 비었으면(unconfirmed) 서버가 202로 준다. 슬래시 명령은 기록 모양이 달라 늦게 다시 보기도 없다(check 없음).
    // 504는 입력 칸에 명령이 남았거나(left_in_box) 화면도 기록도 못 읽은 것뿐이다
    const ok = r.status === 202;
    const left = r.status === 504 && !!j.left_in_box;
    const res = r.status === 409 ? { ok: false, msg: `모델을 바꾸지 못했습니다. ${j.refused}` }
      : ok ? { ok: true, msg: j.queued ? `${label}(으)로 바꾸기를 대기열에 넣었습니다. 지금 작업이 끝나면 바뀝니다.` : `${label}(으)로 바꿨습니다. 다음 응답부터 적용됩니다.` }
      : left ? { ok: false, msg: '모델 바꾸기가 제출되지 않았습니다. 입력 칸에 명령이 남아 있으니 대화창에서 Enter를 누르거나 지워 주세요.' }
      : r.status === 504 ? { ok: false, msg: '모델 바꾸기가 제출됐는지 확인하지 못했습니다. 대화창에서 입력 칸을 확인해 주세요.' }
      : { ok: false, msg: `모델을 바꾸지 못했습니다 (HTTP ${r.status}).` };
    if (ok || (r.status === 504 && !left)) this.state.pendingModel.set(id, { model, label, queued: !!j.queued, ts: Date.now() });
    this.state.lastInput = { sessionId: id, ts: Date.now(), ...res };
    this.touch('panel');
    return res;
  }
  async modelChoices() {           // 고를 수 있는 모델(config/models.toml) — 한 번 받아 둔다
    if (!this._models) {
      const r = await fetch('/api/spawn/options', { headers: this.headers() });
      this._models = r.ok ? ((await r.json()).models || null) : null;
    }
    return this._models;
  }
  // ── 터미널 패널 ───────────────────────────────────────
  async terminalSession() {          // 쿠키(Path=/terminal · /ccscreen)를 받는다 — iframe이 이걸로 ttyd에 붙는다
    const r = await fetch('/api/terminal/session', { method: 'POST', headers: this.headers() });
    if (!r.ok) throw new Error(r.status === 503 ? '셸 · 세션 화면이 꺼져 있습니다' : `HTTP ${r.status}`);
    return r.json();
  }
  // 프로젝트마다 터미널 창(11-10) — project의 셸 창을 보인다(null이면 지금 창 그대로). 돌려받은 것 = 실제로 보이는 창
  // tab(11-10) — 이 탭의 그룹 세션에서 고른다(다른 탭의 터미널을 끌고 가지 않는다)
  async terminalOpen(project, tab) {
    const r = await fetch('/api/terminal/open', { method: 'POST', headers: this.headers(true), body: JSON.stringify({ project: project || null, tab: tab || null }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    return j;
  }
  // [새 셸](11-10) — 그 프로젝트 창의 셸을 새로 띄운다. 명령이 돌거나 친 글이 있으면 force 없이는 {respawned:false, busy}
  async terminalRespawn(project, force) {
    const r = await fetch('/api/terminal/respawn', { method: 'POST', headers: this.headers(true), body: JSON.stringify({ project, force: !!force }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    return j;
  }
  // 지금 실제로 보이는 창(바꾸지 않는다, 11-10) — 다른 탭 · CC 부탁이 창을 바꿔도 이름표가 따라가게 열려 있는 동안 묻는다
  // [위로] · [아래로] · [입력으로](11-11) — tmux 복사 모드로 올려 보기. action: up | down | exit
  async terminalScroll(tab, action) {
    const r = await fetch('/api/terminal/scroll', { method: 'POST', headers: this.headers(true), body: JSON.stringify({ tab, action }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    return j;
  }
  // [셸 비우기](11-14) — 그 프로젝트 창의 셸 화면 · 스크롤백을 비운다. 명령이 돌거나 친 글이 있으면 force 없이는 {cleared:false, busy}
  async terminalClear(project, force) {
    const r = await fetch('/api/terminal/clear', { method: 'POST', headers: this.headers(true), body: JSON.stringify({ project, force: !!force }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    return j;
  }
  // 「세션 화면」 탭(11-14) — 그 세션 CC 창에 붙을 수 있나. {ok, tmux_session, size} 또는 {ok:false, reason}
  async ccState(sid) {
    const r = await fetch(`/api/terminal/cc/${sid}`, { headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    // 404 — 도는 브리지가 세션 화면을 모른다(옛 코드 · worktree 미리보기). 세션이 없을 때는 200 + 까닭이다
    if (r.status === 404) throw new Error('도는 브리지에 세션 화면 길이 없습니다. 브리지를 새 코드로 다시 띄워야 합니다');
    if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
    return j;
  }
  async terminalWindow(tab) {
    const r = await fetch('/api/terminal/window' + (tab ? `?tab=${encodeURIComponent(tab)}` : ''), { headers: this.headers() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }
  async terminalDismiss(id) {
    await fetch(`/api/terminal/requests/${id}`, { method: 'DELETE', headers: this.headers() });
    this.state.terminal.requests.delete(id);
    this.touch('term');
  }
  async terminalPrefill(id) {
    const r = await fetch(`/api/terminal/requests/${id}/prefill`, { method: 'POST', headers: this.headers() });
    const j = await r.json().catch(() => ({}));
    const q = this.state.terminal.requests.get(id);
    if (q) { q.prefilled = !!j.ok; q.note = j.note || null; this.touch('term'); }
  }
  // 세션의 질문(AskUserQuestion)에 답한다(11-09) — picks: 질문 글 → 고른 선택지 이름들
  // note — 답과 함께 보낼 글(11-10). 글만 보내면 고르지 않은 질문은 "(글만)"으로 간다(브리지 approvals.answer)
  async answer(aid, picks, note = null) {
    const r = await fetch(`/api/approvals/${aid}/answer`, { method: 'POST', headers: this.headers(true), body: JSON.stringify({ picks, note }) });
    const a = this.state.approvals.get(aid);
    if (!a) return;
    a.error = r.ok ? null : ((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
    this.touch('approvals');
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
