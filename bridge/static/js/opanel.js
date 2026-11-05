// 픽셀 화면 옆 패널(10b) — 승인 · 대화 · 입력 · 파이프라인 · 승인 이력. 픽셀을 덮지 않게 캔버스 옆에 붙는다(캔버스가 좁아지고 카메라가 다시 맞춘다).
// 접으면 얇은 띠만 남는다(승인 대기 수는 띠에도). 너비는 왼쪽 모서리를 끌어 바꾼다. 접힘 · 너비는 이 브라우저에 기억한다.
// 조각(승인 카드 · 대화 · 세션 정보 · 파이프라인)은 클래식 화면(render.js)과 같은 함수를 쓴다.

import { approvalCard, handleApprovalClick, sessionKv, convoHtml, feedHtml, pipeBlock, mountApprovalHistory,
         sessionName, sessionSub, projectLabel, why, oneLine, esc, ago, tok, STATE_LABEL, ORIGIN_LABEL } from './render.js';
import { stuckTurn } from './store.js';
import { mountHandoff } from './handoff.js';

const KEY_OPEN = 'foremanPanelOpen', KEY_W = 'foremanPanelW', KEY_SECS = 'foremanPanelSecs';
// 칸별 기본 펼침(11-05 다시 정함) — 대화는 늘 보인다(접을 수 없다). 최근 활동은 터미널의 도구 호출 줄에 해당해 편다.
// 세션 정보는 핵심 한 줄(지금 · 서브 · 토큰)을 늘 보이게 따로 두고 자세한 표만 접는다. 승인 이력 · 인계는 가끔 보는 것 — 접는다.
// 사람이 바꾼 펼침은 이 브라우저에 기억한다
const SEC_DEFAULT = { pInfo: false, pFeed: true, pHist: false, hand: false };
const DEFAULT_W = 340, MAX_FRAC = 0.4;     // 픽셀 화면을 덮지 않게 — 기본 340px, 창의 40%를 넘지 않는다
const MIN_W = 280;
const ls = { get(k) { try { return localStorage.getItem(k); } catch { return null; } },
             set(k, v) { try { localStorage.setItem(k, v); } catch { /* 저장 못 해도 이 탭에서는 된다 */ } } };

// target: null | { kind:'session' } (store.state.selected) | { kind:'infra', room, infra, name, status } | { kind:'foreman', room } (room=null이면 감독실)
export function createSidePanel(host, store, { onSelectSession, onToggle, onClear }) {
  const el = document.createElement('aside');
  el.className = 'oside';
  el.setAttribute('aria-label', '패널');
  el.innerHTML = `
    <div class="oside-grip" title="끌어서 너비 바꾸기"></div>
    <button id="pStrip" class="oside-strip" title="패널 펴기">
      <span>◀</span><span id="pStripBadge"></span><span class="oside-vert">패널</span>
    </button>
    <div class="oside-main">
      <div class="oside-bar">
        <b id="pTitle">패널</b><span id="pCount" class="small"></span>
        <button id="pClear" class="ghost small right" title="선택 해제" hidden>✕</button>
        <button id="pFold" class="ghost small" title="접기 — 픽셀 화면을 넓게">▶ 접기</button>
      </div>
      <div id="pBody" class="oside-body">
        <section id="pAppr" class="papprs" aria-label="승인 대기"></section>
        <section id="pSel"></section>
        <section id="pHand"></section>
        <details id="pHist" class="appr-hist"><summary class="small">승인 이력 <span id="pHistHead" class="muted"></span></summary><div id="pHistBody" class="small"></div></details>
      </div>
      <form id="pForm" class="input" hidden>
        <textarea id="pText" rows="3" placeholder="이 세션에 보낼 입력 — Ctrl+Enter로 보내기"></textarea>
        <div class="row">
          <label class="small"><input id="pCmd" type="checkbox"> '/'를 슬래시 명령으로</label>
          <span id="pWhy" class="small muted"></span>
          <button id="pSend" type="submit">보내기</button>
        </div>
        <div id="pResult" class="small"></div>
      </form>
    </div>`;
  host.appendChild(el);
  const $ = (id) => el.querySelector('#' + id);
  let secs = { ...SEC_DEFAULT };
  try { secs = { ...SEC_DEFAULT, ...JSON.parse(ls.get(KEY_SECS) || '{}') }; } catch { /* 기본값 */ }
  const setSec = (k, v) => { if (secs[k] === v) return; secs[k] = v; ls.set(KEY_SECS, JSON.stringify(secs)); };
  el.addEventListener('toggle', (ev) => {           // toggle은 버블링하지 않는다 — capture
    const id = ev.target && ev.target.id;
    if (id && id in SEC_DEFAULT) setSec(id, ev.target.open);
  }, true);
  const hand = mountHandoff($('pHand'), store, { open: secs.hand, onToggle: (v) => setSec('hand', v) });
  $('pHist').open = secs.pHist;

  let target = null, targetKey = '', lastSel = undefined;
  let open = ls.get(KEY_OPEN) !== '0';
  const seen = { approvals: -1, panel: -1, pipe: -1, grid: -1 };
  const knownPending = new Set();
  let firstAppr = true;

  // ── 접기 · 너비 ──────────────────────────────────────
  function applyWidth() {
    const w = Number(ls.get(KEY_W)) || DEFAULT_W;
    el.style.setProperty('--side-w', Math.max(MIN_W, Math.min(w, window.innerWidth * MAX_FRAC)) + 'px');
  }
  function setOpen(v, remember = true) {
    open = v;
    el.classList.toggle('folded', !v);
    if (remember) ls.set(KEY_OPEN, v ? '1' : '0');
    if (onToggle) onToggle(v);
  }
  $('pFold').onclick = () => setOpen(false);
  $('pStrip').onclick = () => setOpen(true);
  $('pClear').onclick = () => { store.select(null); show(null); if (onClear) onClear(); };
  setInterval(() => { if (open && target) store.touch('panel'); }, 10000);   // "n분 전" 같은 시간 표시만 갱신
  const grip = el.querySelector('.oside-grip');
  grip.addEventListener('pointerdown', (ev) => {
    if (!open) return;
    ev.preventDefault();
    grip.setPointerCapture(ev.pointerId);
    const right = el.getBoundingClientRect().right;
    const move = (e) => { ls.set(KEY_W, String(Math.round(right - e.clientX))); applyWidth(); if (onToggle) onToggle(open); };
    const up = () => { grip.removeEventListener('pointermove', move); grip.removeEventListener('pointerup', up); };
    grip.addEventListener('pointermove', move);
    grip.addEventListener('pointerup', up);
  });
  window.addEventListener('resize', applyWidth);
  applyWidth();
  setOpen(open, false);

  // ── 동작 ────────────────────────────────────────────
  $('pAppr').addEventListener('click', (ev) => handleApprovalClick(ev, store, onSelectSession));
  $('pSel').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-sid]');
    if (b) onSelectSession(Number(b.dataset.sid));
  });
  mountApprovalHistory($('pHist'), $('pHistHead'), $('pHistBody'), store);
  $('pForm').onsubmit = async (ev) => {
    ev.preventDefault();
    const id = store.state.selected, text = $('pText').value;
    if (!id || !text.trim()) return;
    $('pSend').disabled = true;
    const r = await store.sendInput(id, text, $('pCmd').checked);
    $('pSend').disabled = false;
    if (r.ok) $('pText').value = '';
  };
  $('pText').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); $('pForm').requestSubmit(); }
    if (ev.key === 'Escape') { ev.stopPropagation(); $('pText').blur(); }   // 입력 중 Esc는 감독실로 가지 않고 칸만 빠져나온다
  });

  // ── 그리기 ──────────────────────────────────────────
  function drawAppr(st) {
    const list = [...st.approvals.values()].sort((a, b) => a.id - b.id);
    const sel = st.selected;
    list.sort((a, b) => (b.session_id === sel) - (a.session_id === sel));    // 고른 세션 것을 맨 위에
    const pend = list.filter((a) => a.status === 'pending');
    $('pAppr').innerHTML = list.length ? `<h3>승인 대기 ${pend.length}</h3>` + list.map((a) => approvalCard(a, st)).join('') : '';
    $('pCount').innerHTML = pend.length ? `<span class="warn">❗${pend.length}</span>` : '';
    $('pStripBadge').innerHTML = pend.length ? `<span class="oside-badge">${pend.length}</span>` : '';
    // 새 승인 요청이 오면 접혀 있어도 편다 — 승인은 기다리는 사람이 있다
    let fresh = false;
    for (const a of pend) if (!knownPending.has(a.id)) { knownPending.add(a.id); fresh = true; }
    if (fresh && !firstAppr && !open) setOpen(true, false);
    firstAppr = false;
  }

  function drawSession(st) {
    const s = st.selected != null ? st.sessions.get(st.selected) : null;
    if (!s) { hand.setSession(null); drawHint(st); return; }
    hand.setSession(s.id);
    $('pTitle').textContent = sessionName(s);
    const stuck = stuckTurn(s);
    const keep = $('pConvo');
    const atBottom = !keep || lastSel !== s.id || keep.scrollHeight - keep.scrollTop - keep.clientHeight < 40;
    const t = s.tokens || {};
    const now = s.activity && s.state === 'ACTIVE' ? `${esc(s.activity.tool)} ${esc(oneLine(s.activity.target || '', 70))}` : (s.state === 'ACTIVE' ? '생각 중' : esc(STATE_LABEL[s.state] || ''));
    $('pSel').innerHTML = `
      <div class="psel-head"><span class="badge st-${s.state}">${esc(STATE_LABEL[s.state] || s.state)}</span>
        <span class="small muted">${esc(sessionSub(s))} · ${esc(projectLabel(st, s.project))}</span></div>
      <div class="small muted">${esc((s.cwd || '').replace(/^\/home\/[^/]+/, '~'))}</div>
      <div class="small psel-now">지금 <b>${now}</b>${s.subagents_running ? ` · 서브 ${s.subagents_running}개 돎` : ''} · 오늘 출력 ${tok(t.today_output)}</div>
      ${s.open_turn ? `<div class="small${stuck ? ' warn' : ''}">${stuck ? '⚠ 끝 신호 없는 턴' : '▶ 턴'} ${esc(ORIGIN_LABEL[s.open_turn.origin] || '')} · ${ago(s.open_turn.started_at)} 시작</div>` : ''}
      <details id="pInfo"${secs.pInfo ? ' open' : ''}><summary class="small muted">세션 정보 · 토큰 자세히</summary>${sessionKv(s)}</details>
      <h3>최근 대화</h3>
      <div id="pConvo" class="convo">${convoHtml(st.convo.get(s.id)) || '<p class="small muted">불러오는 중…</p>'}</div>
      <details id="pFeed"${secs.pFeed ? ' open' : ''}><summary class="small muted">최근 활동 ${s.feed.length}</summary><div class="feed">${feedHtml(s)}</div></details>`;
    const convo = $('pConvo');
    if (atBottom) convo.scrollTop = convo.scrollHeight;
    else if (keep) convo.scrollTop = keep.scrollTop;
    $('pForm').hidden = false;
    const blocked = !s.injectable;
    $('pText').disabled = blocked; $('pSend').disabled = blocked;
    $('pWhy').textContent = blocked ? `보낼 수 없음 — ${why(s)}` : (s.state === 'ACTIVE' ? '일하는 중 — 대기열로 들어간다' : '');
    const li = st.lastInput && st.lastInput.sessionId === s.id ? st.lastInput : null;
    $('pResult').innerHTML = li ? `<span class="${li.ok ? 'ok' : 'bad'}">${esc(li.msg)}${li.guarded ? ' (첫 글자 보호)' : ''}</span>` : '';
    if (lastSel !== s.id) { $('pText').value = ''; lastSel = s.id; }
  }

  function sessionList(st, names) {
    const rows = [];
    const btn = (s) => `
        <button class="plist" data-sid="${s.id}"><span class="badge st-${s.state}">${esc(STATE_LABEL[s.state])}</span>
          <b>${esc(oneLine(sessionName(s), 40))}</b>${s.activity && s.state === 'ACTIVE' ? ` <span class="muted">${esc(s.activity.tool)}</span>` : ''}${s.state === 'DORMANT' ? ` <span class="muted small">${ago(s.last_ts)}</span>` : ''}</button>`;
    for (const p of st.projects) {
      if (names && !names.includes(p.name)) continue;
      const all = p.sessionIds.map((id) => st.sessions.get(id)).filter(Boolean);
      const ss = all.filter((s) => s.state !== 'DORMANT'), dd = all.filter((s) => s.state === 'DORMANT');
      if (!all.length) continue;
      // 종료된 세션은 접어 둔다 — 자리가 모자라 캐릭터가 없는 세션도 여기서 고를 수 있다
      rows.push(`<div class="small muted plist-h">${esc(p.label)}</div>` + ss.map(btn).join('') +
        (dd.length ? `<details class="small" data-k="${esc(p.name)}"><summary class="muted">종료된 세션 ${dd.length}개</summary>${dd.map(btn).join('')}</details>` : ''));
    }
    if (!names && st.hiddenDormant) rows.push(`<p class="small muted">48시간 넘게 활동 없는 세션 ${st.hiddenDormant}개는 숨김</p>`);
    return rows.join('') || '<p class="small muted">세션 없음</p>';
  }

  function drawHint(st) {
    $('pForm').hidden = true;
    $('pClear').hidden = !target;
    if (target && target.kind === 'infra') {
      $('pTitle').textContent = target.name;
      $('pSel').innerHTML = `<div class="small muted">${esc(projectLabel(st, target.room))} · 지금 ${esc(target.status || '기록 없음')}</div>
        ${pipeBlock(st.pipeline.get(target.room)) || '<p class="small muted">파이프라인 기록 없음</p>'}`;
      return;
    }
    if (target && target.kind === 'foreman') {
      $('pTitle').textContent = target.room ? `포먼 · ${projectLabel(st, target.room)}` : '포먼(감독)';
      $('pSel').innerHTML = `<p class="small muted">포먼은 아직 자기 세션이 없다(11단계). 아래에서 세션을 고르면 대화 · 입력이 뜬다.</p>
        ${target.room ? pipeBlock(st.pipeline.get(target.room)) : ''}
        ${sessionList(st, target.room ? [target.room] : null)}`;
      return;
    }
    $('pTitle').textContent = '패널';
    $('pSel').innerHTML = `<p class="small muted">캐릭터를 누르면 최근 대화와 입력 칸이 여기 뜬다. 세션을 바로 골라도 된다.</p>${sessionList(st, null)}`;
  }

  function draw(st) {
    if (target && target.kind === 'session') { $('pClear').hidden = false; drawSession(st); return; }
    // 목록은 이벤트마다 다시 그린다 — 펴 둔 "종료된 세션"은 펴진 채로
    const keys = [...$('pSel').querySelectorAll('details[open][data-k]')].map((d) => d.dataset.k);
    drawHint(st);
    for (const d of $('pSel').querySelectorAll('details[data-k]')) if (keys.includes(d.dataset.k)) d.open = true;
  }

  // office.js가 고를 때마다 부른다 — 같은 대상이면 다시 그리지 않는다(입력 칸 · 스크롤 유지)
  function show(t) {
    const key = t ? `${t.kind}:${t.kind === 'session' ? store.state.selected : (t.room || '') + ':' + (t.infra || '') + ':' + (t.status || '')}` : '';
    if (key === targetKey) return;
    targetKey = key; target = t;
    if (t && !open) setOpen(true, false);
    draw(store.state);
    drawAppr(store.state);
  }

  store.subscribe((st) => {
    if (seen.approvals !== st.ver.approvals) { seen.approvals = st.ver.approvals; drawAppr(st); }
    const sessionView = target && target.kind === 'session';
    if (seen.panel !== st.ver.panel || (!sessionView && (seen.pipe !== st.ver.pipe || seen.grid !== st.ver.grid))) {
      seen.panel = st.ver.panel; seen.pipe = st.ver.pipe; seen.grid = st.ver.grid;
      draw(st);
    }
  });

  return { show, setOpen, get open() { return open; }, el };
}
