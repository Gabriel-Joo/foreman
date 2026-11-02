// FOREMAN 대시보드 — 그리는 쪽(6단계, 실용 화면). store.js의 state만 본다.
// 10단계 테마 렌더러는 이 파일 대신 같은 state를 받아 캐릭터로 그리면 된다(createRenderer(root, store)만 맞추면 된다).
// 영역(conn · approvals · grid · panel)마다 state.ver가 바뀐 것만 다시 그린다. 입력 칸 · 스크롤은 다시 그려도 유지한다.

const STATE_LABEL = { ACTIVE: '작업 중', IDLE: '대기', SUSPENDED: '정지', DORMANT: '종료' };
const ORIGIN_LABEL = { human: '나', task_notification: '완료 알림', subagent_message: '서브에이전트 결과', agent_message: '다른 세션', meta: '시스템' };
const END_LABEL = { stop: '끝남', stop_failure: 'API 오류', interrupted: '중단', session_end: '세션 종료', process_lost: '프로세스 사라짐', merged: '다음 입력에 합쳐짐', no_signal: '신호 없음', abandoned: '끝 신호 없이 버려짐' };

import { stuckTurn } from './store.js';

const ROLE_LABEL = { coder: '코더', foreman: '포먼', cicd: 'CI/CD', inspector: '점검', helper: '도우미', infra: '인프라' };

// 세션을 알아보는 이름 — CC가 붙인 제목 → CC 세션 이름 → 짧은 id. 캐릭터 이름은 아래 줄에(한 캐릭터에 세션 여럿)
export function sessionName(s) { return s.title || s.cc_name || s.short; }
function sessionSub(s) {
  return [s.character, ROLE_LABEL[s.role] || s.role, s.short, s.tmux_pane].filter(Boolean).join(' · ');
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function ago(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
  if (s < 60) return `${s}초 전`;
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}
function since(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
  return s < 60 ? `${s}초째` : s < 3600 ? `${Math.floor(s / 60)}분째` : `${Math.floor(s / 3600)}시간 ${Math.floor((s % 3600) / 60)}분째`;
}
export function tok(n) {
  n = n || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return String(n);
}
function promptText(p) {
  if (!p) return '';
  return p.replace(/^\s*<pasted_content id="[0-9a-f]+">\s*/, '').replace(/\s*<\/pasted_content id="[0-9a-f]+">\s*$/, '').trim();
}
function oneLine(s, n) {
  s = promptText(s).replace(/\s+/g, ' ');
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}
function why(s) {
  if (!s.pid) return '프로세스가 없다';
  if (s.proc === 'T') return '정지(SUSPENDED) — 입력이 셸 명령으로 실행된다';
  if (!s.tmux_pane) return 'tmux 밖 세션 — 주입할 pane이 없다';
  return '';
}

export function createRenderer(root, store) {
  root.innerHTML = `
    <header class="top">
      <div class="brand">FOREMAN</div>
      <div id="summary" class="summary"></div>
      <div id="conn" class="conn"></div>
      <button id="tokBtn" class="ghost" title="API 토큰">토큰</button>
    </header>
    <section id="approvals" class="approvals" aria-label="승인 대기"></section>
    <main class="layout">
      <section id="grid" class="grid" aria-label="세션"></section>
      <aside id="panel" class="panel" aria-label="선택한 세션">
        <div class="panel-head"><button id="back" class="ghost back">← 목록</button><div id="panelHead"></div></div>
        <div id="panelBody" class="panel-body">
          <div id="panelInfo"></div>
          <h3>최근 대화</h3>
          <div id="convo" class="convo"></div>
          <h3>최근 활동</h3>
          <div id="feed" class="feed"></div>
        </div>
        <form id="inputForm" class="input">
          <textarea id="inputText" rows="3" placeholder="이 세션에 보낼 입력 — Ctrl+Enter로 보내기"></textarea>
          <div class="row">
            <label class="small"><input id="cmd" type="checkbox"> '/'를 슬래시 명령으로</label>
            <span id="inputWhy" class="small muted"></span>
            <button id="sendBtn" type="submit">보내기</button>
          </div>
          <div id="inputResult" class="small"></div>
        </form>
      </aside>
    </main>
    <div id="down" class="down" role="alert" aria-live="assertive"><div class="box">
      <h2>서버 연결 끊김</h2><p id="downWhy"></p><p id="downNext"></p>
      <button id="retryNow">지금 다시 연결</button>
    </div></div>
    <div id="tokDlg" class="down"><form class="box" id="tokForm">
      <h2 class="plain">API 토큰</h2>
      <p class="muted small">.env.bridge의 FOREMAN_API_TOKEN 값. 이 브라우저에만 저장한다.</p>
      <input id="tokInput" type="password" autocomplete="new-password" placeholder="FOREMAN_API_TOKEN 값">
      <p><button type="submit">연결</button> <span id="tokLen" class="small muted"></span></p>
    </form></div>`;

  const $ = (id) => root.querySelector('#' + id);
  const seen = { conn: -1, approvals: -1, grid: -1, panel: -1 };
  let lastSel = undefined;

  // ── 동작 연결 ──────────────────────────────────────────
  $('grid').addEventListener('click', (ev) => {
    const card = ev.target.closest('[data-sid]');
    if (card) store.select(Number(card.dataset.sid));
  });
  $('grid').addEventListener('keydown', (ev) => {
    const card = ev.target.closest('[data-sid]');
    if (card && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); store.select(Number(card.dataset.sid)); }
  });
  $('back').onclick = () => store.select(null);
  $('approvals').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-aid]');
    if (!b) return;
    const aid = Number(b.dataset.aid);
    if (b.dataset.act === 'allow') store.decide(aid, 'allow');
    else if (b.dataset.act === 'deny') {
      const m = prompt('거부 이유(모델에게 전달된다)', '사용자가 거부');
      if (m !== null) store.decide(aid, 'deny', m);
    } else if (b.dataset.act === 'open') store.select(Number(b.dataset.sid));
  });
  $('inputForm').onsubmit = async (ev) => {
    ev.preventDefault();
    const id = store.state.selected, text = $('inputText').value;
    if (!id || !text.trim()) return;
    $('sendBtn').disabled = true;
    const r = await store.sendInput(id, text, $('cmd').checked);
    $('sendBtn').disabled = false;
    if (r.ok) $('inputText').value = '';
  };
  $('inputText').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) $('inputForm').requestSubmit(); });
  $('retryNow').onclick = () => store.retryNow();
  $('tokBtn').onclick = () => { $('tokDlg').classList.add('on'); $('tokInput').focus(); };
  $('tokInput').oninput = () => { const n = $('tokInput').value.trim().replace(/^FOREMAN_API_TOKEN=/, '').length; $('tokLen').textContent = n ? `길이 ${n}` : ''; };
  $('tokForm').onsubmit = (ev) => {
    ev.preventDefault();
    store.token = $('tokInput').value;
    $('tokInput').value = '';
    $('tokDlg').classList.remove('on');
    store.start();
  };

  // ── 영역별 그리기 ───────────────────────────────────────
  function drawConn(st) {
    const c = st.conn;
    const label = { idle: '연결 전', connecting: '연결 중…', up: '연결됨', down: '끊김', auth: '토큰 확인 필요' }[c.status];
    $('conn').className = 'conn ' + c.status;
    $('conn').textContent = label;
    const down = c.status === 'down';
    $('down').classList.toggle('on', down);
    if (down) {
      $('downWhy').textContent = `${c.reason || '브리지와 연락이 없다'} — ${new Date(c.since).toLocaleTimeString()}부터`;
      $('downNext').textContent = c.nextIn ? `${c.nextIn}초 뒤 다시 연결 (시도 ${c.attempt})` : `연결 중… (시도 ${c.attempt})`;
    }
    if (c.status === 'auth') $('tokDlg').classList.add('on');
  }

  function drawSummary(st) {
    let active = 0, live = 0, outToday = 0, subs = 0;
    for (const s of st.sessions.values()) {
      if (s.state === 'ACTIVE') active++;
      if (s.state !== 'DORMANT') live++;
      outToday += s.tokens ? s.tokens.today_output : 0;
      subs += s.subagents_running || 0;
    }
    const pending = [...st.approvals.values()].filter((a) => a.status === 'pending').length;
    $('summary').innerHTML =
      `<span>작업 중 <b>${active}</b>/${live}</span>` +
      (subs ? `<span>서브에이전트 <b>${subs}</b></span>` : '') +
      (pending ? `<span class="warn">승인 대기 <b>${pending}</b></span>` : '') +
      `<span class="muted">오늘 출력 ${tok(outToday)}</span>`;
  }

  function drawApprovals(st) {
    const list = [...st.approvals.values()].sort((a, b) => a.id - b.id);
    $('approvals').innerHTML = list.map((a) => {
      const done = a.status !== 'pending';
      const label = (st.projects.find((p) => p.name === a.project) || {}).label || a.project || '미분류';
      return `<div class="appr ${done ? 'done' : ''}">
        <div class="appr-main">
          <div><b>🔐 ${esc(label)}</b> · ${esc(a.tool)} <span class="muted small">#${a.id} · ${esc(a.rule)}</span></div>
          <code>${esc(a.target)}</code>
          <div class="small muted">${esc(a.reason || '')}${a.error ? ` · <span class="bad">${esc(a.error)}</span>` : ''}</div>
        </div>
        <div class="appr-act">${done ? `<span class="small">${esc(a.status)}${a.decided_by ? ' · ' + esc(a.decided_by) : ''}</span>` :
          `<button data-aid="${a.id}" data-act="allow">승인</button><button data-aid="${a.id}" data-act="deny" class="ghost">거부</button>`}
          ${a.session_id ? `<button data-aid="${a.id}" data-sid="${a.session_id}" data-act="open" class="ghost small">세션</button>` : ''}</div>
      </div>`;
    }).join('');
  }

  function card(s, st) {
    const a = s.activity;
    const pend = [...st.approvals.values()].filter((x) => x.session_id === s.id && x.status === 'pending').length;
    const doing = s.state === 'ACTIVE' && a ? `<div class="doing"><b>${esc(a.tool)}</b>${a.subagent ? ' <span class="muted">(서브)</span>' : ''} ${esc(oneLine(a.target, 90))} <span class="muted small">${ago(a.ts)}</span></div>` : '';
    const stuck = stuckTurn(s);
    const turn = s.open_turn ? `<div class="turn small${stuck ? ' warn' : ''}">${stuck ? '⚠ 끝 신호 없는 턴' : '▶'} ${esc(ORIGIN_LABEL[s.open_turn.origin] || '')} ${esc(oneLine(s.open_turn.prompt || '', 80))} <span class="muted">${since(s.open_turn.started_at)}</span></div>` : '';
    const reply = s.replyPreview && s.state === 'ACTIVE' ? `<div class="reply small">${esc(oneLine(s.replyPreview, 100))}</div>` : '';
    return `<article class="card st-${s.state}${st.selected === s.id ? ' sel' : ''}" data-sid="${s.id}" tabindex="0" aria-label="${esc(sessionName(s))} ${STATE_LABEL[s.state]}">
      <div class="card-top">
        <span class="badge st-${s.state}">${s.state}</span>
        <b class="title" title="${esc(sessionName(s))}">${esc(sessionName(s))}</b>
        <span class="right small muted">${s.state === 'DORMANT' ? ago(s.last_ts) : STATE_LABEL[s.state]}</span>
      </div>
      <div class="sub small muted">${esc(sessionSub(s))}</div>
      ${turn}${doing}${reply}
      <div class="meta small">
        ${s.subagents_running ? `<span class="pill">서브에이전트 ${s.subagents_running}</span>` : ''}
        ${pend ? `<span class="pill warn">승인 대기 ${pend}</span>` : ''}
        <span class="muted">출력 ${tok(s.tokens.output)} · 오늘 ${tok(s.tokens.today_output)}</span>
      </div>
    </article>`;
  }

  function drawGrid(st) {
    const html = st.projects.map((p) => {
      const ss = p.sessionIds.map((id) => st.sessions.get(id)).filter(Boolean);
      const live = ss.filter((s) => s.state !== 'DORMANT');
      const dormant = ss.filter((s) => s.state === 'DORMANT');
      return `<section class="proj">
        <h2>${esc(p.label)} <span class="muted small">${live.length}개 살아 있음</span></h2>
        ${live.map((s) => card(s, st)).join('')}
        ${dormant.length ? `<details class="dormant"><summary class="small muted">종료된 세션 ${dormant.length}개</summary>${dormant.map((s) => card(s, st)).join('')}</details>` : ''}
      </section>`;
    }).join('');
    const open = new Set([...$('grid').querySelectorAll('details[open]')].map((d) => d.parentElement.querySelector('h2').textContent));
    $('grid').innerHTML = html + (st.hiddenDormant ? `<p class="small muted">48시간 넘게 활동 없는 세션 ${st.hiddenDormant}개는 숨김</p>` : '');
    for (const d of $('grid').querySelectorAll('details')) if (open.has(d.parentElement.querySelector('h2').textContent)) d.open = true;
  }

  function drawPanel(st) {
    const s = st.selected != null ? st.sessions.get(st.selected) : null;
    root.classList.toggle('has-sel', !!s);
    if (!s) {
      $('panelHead').innerHTML = '<span class="muted">세션을 고르세요</span>';
      $('panelInfo').innerHTML = ''; $('convo').innerHTML = ''; $('feed').innerHTML = '';
      $('inputForm').hidden = true;
      return;
    }
    const t = s.tokens;
    $('panelHead').innerHTML = `<span class="badge st-${s.state}">${s.state}</span> <b>${esc(sessionName(s))}</b><div class="muted small">${esc(sessionSub(s))} · ${esc((s.cwd || '').replace(/^\/home\/[^/]+/, '~'))}</div>`;
    $('panelInfo').innerHTML = `<div class="small kv">
      <span>프로세스</span><span>${s.pid ? `${s.pid} (${esc(s.proc)}) · CC ${esc(s.cc_status || '?')}` : '없음'}${s.tmux_pane ? ' · tmux ' + esc(s.tmux_pane) : ''}</span>
      <span>지금</span><span>${s.activity && s.state === 'ACTIVE' ? `${esc(s.activity.tool)} ${esc(oneLine(s.activity.target, 120))} (${ago(s.activity.ts)})` : (s.state === 'ACTIVE' ? '생각 중' : STATE_LABEL[s.state])}</span>
      <span>서브에이전트</span><span>${s.subagents_running ? `${s.subagents_running}개 — ${esc((s.subagent_descs || []).join(', '))}` : '없음'}</span>
      <span>토큰</span><span>입력(캐시 포함) ${tok(t.input)} · 출력 ${tok(t.output)} · 오늘 입력 ${tok(t.today_input)} · 출력 ${tok(t.today_output)}<br><span class="muted">서브에이전트 입력 ${tok(t.subagent_input)} · 출력 ${tok(t.subagent_output)}(추정)</span></span>
    </div>`;
    const c = st.convo.get(s.id);
    const convo = $('convo');
    const atBottom = convo.scrollHeight - convo.scrollTop - convo.clientHeight < 40 || lastSel !== s.id;
    convo.innerHTML = !c ? '' : (c.error ? `<p class="bad small">${esc(c.error)}</p>` : '') + (c.turns || []).map((x) => `
      <div class="msg in o-${esc(x.origin)}"><div class="who small muted">${esc(ORIGIN_LABEL[x.origin] || x.origin)} · ${ago(x.started_at)}</div><div class="txt">${esc(promptText(x.prompt)).slice(0, 3000)}</div></div>
      ${x.reply ? `<div class="msg out"><div class="who small muted">CC${x.end_reason ? ' · ' + esc(END_LABEL[x.end_reason] || x.end_reason) : ' · 진행 중'}${x.tools ? ` · 도구 ${x.tools}` : ''}${x.subagents ? ` · 서브 ${x.subagents}` : ''}</div><div class="txt">${esc(x.reply)}</div></div>`
        : (x.end_reason ? `<div class="msg out small muted">${esc(END_LABEL[x.end_reason] || x.end_reason)}${x.tools ? ` · 도구 ${x.tools}` : ''}</div>` : '')}`).join('') + (c && c.loading ? '<p class="small muted">불러오는 중…</p>' : '');
    if (atBottom) convo.scrollTop = convo.scrollHeight;
    $('feed').innerHTML = s.feed.slice().reverse().map((f) => `<div class="f f-${f.kind}"><span class="muted">${new Date(f.ts).toLocaleTimeString()}</span> ${esc(f.text)}</div>`).join('') || '<p class="small muted">이 화면을 연 뒤의 활동이 여기에 쌓인다</p>';
    $('inputForm').hidden = false;
    const blocked = !s.injectable;
    $('inputText').disabled = blocked; $('sendBtn').disabled = blocked;
    $('inputWhy').textContent = blocked ? `보낼 수 없음 — ${why(s)}` : (s.state === 'ACTIVE' ? '일하는 중 — 대기열로 들어간다' : '');
    const li = st.lastInput && st.lastInput.sessionId === s.id ? st.lastInput : null;
    $('inputResult').innerHTML = li ? `<span class="${li.ok ? 'ok' : 'bad'}">${esc(li.msg)}${li.guarded ? ' (첫 글자 보호)' : ''}</span>` : '';
    if (lastSel !== s.id) { $('inputText').value = ''; lastSel = s.id; }
  }

  store.subscribe((st) => {
    if (seen.conn !== st.ver.conn) { seen.conn = st.ver.conn; drawConn(st); }
    if (seen.approvals !== st.ver.approvals) { seen.approvals = st.ver.approvals; drawApprovals(st); }
    if (seen.grid !== st.ver.grid) { seen.grid = st.ver.grid; drawGrid(st); drawSummary(st); }
    if (seen.panel !== st.ver.panel) { seen.panel = st.ver.panel; drawPanel(st); }
  });
  // "n초 전" · "n분째" 같은 시간 표시만 갱신
  setInterval(() => store.touch('grid', 'panel'), 10000);
}
