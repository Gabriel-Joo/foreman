// 픽셀 화면 옆 패널(10b, 11-05 다시 짬) — 대화가 주인공. 제목 줄 바로 아래부터 입력 칸 바로 위까지 대화가 차지한다.
//   맨 위: 승인 대기(급한 것 — 늘 위)
//   제목 줄: 세션 이름 + 한 줄(상태 · 지금 · 서브 · 오늘 출력) + 넓게/좁게
//   탭: [대화](기본) · [활동](도구 호출 — 누르면 입력 · 결과 본문을 트랜스크립트에서) · [세션](정보 · 인계 · 세션 조작 · 승인 이력)
// 대화는 내용이 바뀔 때만 다시 그린다 — 읽던 자리 · 고른 글자가 10초마다 날아가지 않게. 아래를 보고 있으면 새 답을 따라 내려가고,
// 위를 보고 있으면 그대로 두고 [새 답 ↓]만 띄운다.
// 너비는 두 가지(좁게 = 픽셀 볼 때, 넓게 = 대화 읽을 때)를 오가고, 각각 끌어서 바꾼 값을 따로 기억한다.

import { approvalCard, handleApprovalClick, sessionKv, modelChip, convoHtml, feedHtml, pipeBlock, mountApprovalHistory,
         sessionName, sessionSub, projectLabel, why, oneLine, esc, ago, tok, STATE_LABEL, ORIGIN_LABEL, FEED_DETAIL, FEED_OPEN } from './render.js';
import { stuckTurn } from './store.js';
import { slashIntent } from './slash.js';
import { mountHandoff } from './handoff.js';

const KEY_OPEN = 'foremanPanelOpen', KEY_TAB = 'foremanPanelTab', KEY_MODE = 'foremanPanelMode';
const KEY_W = { narrow: 'foremanPanelW', wide: 'foremanPanelWideW' };
const WIDTH = {                                   // 기본 너비 · 창에 대한 최대 비율
  narrow: { def: () => 360, max: 0.4 },
  wide: { def: () => Math.max(560, Math.round(window.innerWidth * 0.5)), max: 0.72 },
};
const MIN_W = 280;
const TABS = [['convo', '대화'], ['act', '활동'], ['sess', '세션']];
const ls = { get(k) { try { return localStorage.getItem(k); } catch { return null; } },
             set(k, v) { try { localStorage.setItem(k, v); } catch { /* 저장 못 해도 이 탭에서는 된다 */ } } };

// target: null | { kind:'session' } (store.state.selected) | { kind:'infra', room, infra, name, status } | { kind:'foreman', room } (room=null이면 감독실)
export function createSidePanel(host, store, { onSelectSession, onToggle, onClear }) {
  const el = document.createElement('aside');
  el.className = 'oside';
  el.setAttribute('aria-label', '패널');
  el.innerHTML = `
    <div class="oside-grip" title="너비 — 끌어서 바꿉니다. 두 번 누르면 넓게와 좁게를 오갑니다."></div>
    <button id="pStrip" class="oside-strip" title="패널 — 접은 패널을 폅니다.">
      <span>◀</span><span id="pStripBadge"></span><span class="oside-vert">패널</span>
    </button>
    <div class="oside-main">
      <div class="oside-bar">
        <b id="pTitle">패널</b><span id="pCount" class="small"></span>
        <button id="pWide" class="ghost small right" title="너비 — 대화를 읽을 땐 넓게, 픽셀을 볼 땐 좁게 합니다."></button>
        <button id="pClear" class="ghost small" title="선택 해제 — 고른 세션을 놓습니다." hidden>✕</button>
        <button id="pFold" class="ghost small" title="접기 — 패널을 접어 픽셀 화면을 넓힙니다.">▶</button>
      </div>
      <div id="pMeta" class="pmeta small" hidden></div>
      <div id="pCmp" class="pcmp small" hidden></div>
      <section id="pAppr" class="papprs" aria-label="승인 대기"></section>
      <nav id="pTabs" class="ptabs" hidden>${TABS.map(([k, l]) => `<button data-tab="${k}">${l}<span data-n="${k}"></span></button>`).join('')}</nav>
      <div id="pBody" class="oside-body">
        <section id="pSel"></section>
        <div id="pTabConvo" class="ptab ptab-convo" hidden>
          <div id="pConvo" class="convo"></div>
          <button id="pNew" class="pnew" hidden>새 답 ↓</button>
        </div>
        <div id="pTabAct" class="ptab" hidden><div id="pFeed" class="feed"></div></div>
        <div id="pTabSess" class="ptab" hidden>
          <div id="pInfo"></div>
          <section id="pHand"></section>
          <details id="pHist" class="appr-hist"><summary class="small">승인 이력 <span id="pHistHead" class="muted"></span></summary><div id="pHistBody" class="small"></div></details>
        </div>
      </div>
      <form id="pForm" class="input" hidden>
        <textarea id="pText" rows="3" placeholder="이 세션에 보낼 입력 (Ctrl+Enter로 보냅니다)"></textarea>
        <div class="row prow">
          <span id="pWhy" class="pwhy small"></span>
          <button id="pSend" type="submit">보내기</button>
        </div>
        <div id="pResult" class="presult small"></div>
      </form>
    </div>`;
  host.appendChild(el);
  const $ = (id) => el.querySelector('#' + id);
  const hand = mountHandoff($('pHand'), store, { open: true });
  mountApprovalHistory($('pHist'), $('pHistHead'), $('pHistBody'), store);

  let target = null, targetKey = '', lastSel = undefined;
  let open = ls.get(KEY_OPEN) !== '0';
  let tab = TABS.some(([k]) => k === ls.get(KEY_TAB)) ? ls.get(KEY_TAB) : 'convo';
  let mode = ls.get(KEY_MODE) === 'wide' ? 'wide' : 'narrow';
  const seen = { approvals: -1, panel: -1, pipe: -1, grid: -1 };
  const knownPending = new Set();
  let firstAppr = true;
  const last = { convo: '', convoSid: null, feed: '', meta: '', info: '' };

  // ── 접기 · 너비(좁게 / 넓게) ─────────────────────────
  function applyWidth() {
    const w = Number(ls.get(KEY_W[mode])) || WIDTH[mode].def();
    el.style.setProperty('--side-w', Math.max(MIN_W, Math.min(w, window.innerWidth * WIDTH[mode].max)) + 'px');
    $('pWide').textContent = mode === 'wide' ? '⇥ 좁게' : '⇤ 넓게';
    el.classList.toggle('wide', mode === 'wide');
  }
  function setMode(m) { mode = m; ls.set(KEY_MODE, m); applyWidth(); if (onToggle) onToggle(open); }
  function setOpen(v, remember = true) {
    open = v;
    el.classList.toggle('folded', !v);
    if (remember) ls.set(KEY_OPEN, v ? '1' : '0');
    if (onToggle) onToggle(v);
  }
  // 세션 이름 — 제목을 누르면 그 자리에서 고친다(11-05). Enter 저장 · Esc 취소 · [자동 제목]은 CC가 붙인 제목으로
  let editingTitle = false;
  $('pTitle').addEventListener('click', () => {
    const s = target && target.kind === 'session' && store.state.selected != null ? store.state.sessions.get(store.state.selected) : null;
    if (!s || editingTitle) return;
    editingTitle = true;
    const bar = $('pTitle');
    const box = document.createElement('span');
    box.className = 'ptitle-edit';
    box.innerHTML = `<input id="pTitleIn" maxlength="255" placeholder="${esc(s.title || s.cc_name || s.short)}">
      <button type="button" class="small" data-t="save">저장</button>${s.custom_title ? '<button type="button" class="ghost small" data-t="auto" title="자동 제목 — CC가 붙인 제목으로 되돌립니다.">자동 제목</button>' : ''}`;
    bar.hidden = true;
    bar.after(box);
    const inp = box.querySelector('input');
    inp.value = s.custom_title || sessionName(s);
    inp.focus(); inp.select();
    const done = async (val) => {
      if (!editingTitle) return;
      editingTitle = false;
      box.remove(); bar.hidden = false;
      if (val === undefined) return;
      const v = val === null ? null : val.trim();
      if (v !== null && v === (s.custom_title || '')) return;
      if (v !== null && !s.custom_title && v === sessionName(s)) return;      // 그대로 눌렀다
      try { await store.setTitle(s.id, v || null); } catch (e) { $('pTitle').textContent = `이름을 저장하지 못했습니다 — ${e.message}`; }
    };
    inp.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); done(inp.value); }
      if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); done(undefined); }
    });
    box.addEventListener('mousedown', (ev) => { if (ev.target.closest('button')) ev.preventDefault(); });   // 버튼을 눌러도 blur가 먼저 저장하지 않게
    box.addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-t]');
      if (b) done(b.dataset.t === 'auto' ? null : inp.value);
    });
    inp.addEventListener('blur', () => done(inp.value));
  });
  $('pWide').onclick = () => setMode(mode === 'wide' ? 'narrow' : 'wide');
  $('pFold').onclick = () => setOpen(false);
  $('pStrip').onclick = () => setOpen(true);
  $('pClear').onclick = () => { store.select(null); show(null); if (onClear) onClear(); };
  setInterval(() => { if (open && target) store.touch('panel'); }, 10000);   // "n분 전" 같은 시간 표시만 갱신
  const grip = el.querySelector('.oside-grip');
  grip.addEventListener('dblclick', () => setMode(mode === 'wide' ? 'narrow' : 'wide'));
  grip.addEventListener('pointerdown', (ev) => {
    if (!open) return;
    ev.preventDefault();
    grip.setPointerCapture(ev.pointerId);
    const right = el.getBoundingClientRect().right;
    const move = (e) => { ls.set(KEY_W[mode], String(Math.round(right - e.clientX))); applyWidth(); if (onToggle) onToggle(open); };
    const up = () => { grip.removeEventListener('pointermove', move); grip.removeEventListener('pointerup', up); };
    grip.addEventListener('pointermove', move);
    grip.addEventListener('pointerup', up);
  });
  window.addEventListener('resize', applyWidth);
  applyWidth();
  setOpen(open, false);

  // ── 탭 ──────────────────────────────────────────────
  function setTab(k) {
    tab = k; ls.set(KEY_TAB, k);
    for (const b of $('pTabs').querySelectorAll('[data-tab]')) b.classList.toggle('on', b.dataset.tab === k);
    $('pTabConvo').hidden = k !== 'convo'; $('pTabAct').hidden = k !== 'act'; $('pTabSess').hidden = k !== 'sess';
    el.classList.toggle('tab-convo', k === 'convo');
    if (k === 'convo') { const c = $('pConvo'); c.scrollTop = c.scrollHeight; $('pNew').hidden = true; }
  }
  $('pTabs').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-tab]');
    if (b) { setTab(b.dataset.tab); store.touch('panel'); }
  });

  // ── 대화 스크롤 — 아래를 보고 있으면 따라가고, 위를 보고 있으면 그대로 + [새 답 ↓] ──
  const nearBottom = (c) => c.scrollHeight - c.scrollTop - c.clientHeight < 60;
  $('pConvo').addEventListener('scroll', () => { if (nearBottom($('pConvo'))) $('pNew').hidden = true; });
  $('pNew').onclick = () => { const c = $('pConvo'); c.scrollTo({ top: c.scrollHeight, behavior: 'smooth' }); $('pNew').hidden = true; };
  // 긴 글을 접을 때 — 그 글 머리가 화면 위로 사라졌으면 머리로 데려온다(흐름이 끊기지 않게). 펼칠 때는 자리를 그대로
  $('pConvo').addEventListener('click', (ev) => {
    const b = ev.target.closest('button.more');
    if (!b) return;
    requestAnimationFrame(() => {
      const msg = b.closest('.msg'), c = $('pConvo');
      if (msg && !b.previousElementSibling.classList.contains('open') && msg.getBoundingClientRect().top < c.getBoundingClientRect().top) {
        c.scrollTop += msg.getBoundingClientRect().top - c.getBoundingClientRect().top - 8;
      }
    });
  });

  // ── 동작 ────────────────────────────────────────────
  $('pAppr').addEventListener('click', (ev) => handleApprovalClick(ev, store, onSelectSession));
  $('pSel').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-sid]');
    if (b) onSelectSession(Number(b.dataset.sid));
  });
  $('pFeed').addEventListener('click', async (ev) => {
    const f = ev.target.closest('.f[data-eid]');
    if (!f) return;                            // 활동 줄 → 도구 입력 · 결과 본문(트랜스크립트에서 그때그때)
    const eid = Number(f.dataset.eid);
    if (FEED_OPEN.has(eid)) { FEED_OPEN.delete(eid); store.touch('panel'); return; }
    FEED_OPEN.add(eid);
    const have = FEED_DETAIL.get(eid);
    if (!have || have.error || (have.found && !have.found.result)) {   // 결과가 아직 없던 것은 다시 읽는다
      FEED_DETAIL.set(eid, { loading: true });
      store.touch('panel');
      try { FEED_DETAIL.set(eid, await store.eventDetail(eid)); } catch (e) { FEED_DETAIL.set(eid, { error: e.message }); }
    }
    store.touch('panel');
  });
  // 모델 바꾸기(11-05) — 머리줄의 모델 표시를 누르면 목록, 고르면 그 세션에 /model <id>
  const mdlMenu = document.createElement('div');
  mdlMenu.className = 'mdl-menu'; mdlMenu.hidden = true;
  document.body.appendChild(mdlMenu);
  const closeMenu = () => { mdlMenu.hidden = true; };
  $('pMeta').addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-mdl]');
    if (!b) return;
    ev.stopPropagation();
    if (!mdlMenu.hidden) { closeMenu(); return; }
    const s = store.state.sessions.get(store.state.selected);
    const m = await store.modelChoices();
    if (!s || !m) return;
    const busy = s.state === 'ACTIVE';
    mdlMenu.innerHTML = `<div class="small muted">이 세션의 모델 — /model을 보냅니다</div>`
      + m.choices.map((c) => `<button type="button" data-id="${esc(c.id)}" data-label="${esc(c.label)}"${s.model_family === c.id ? ' class="cur"' : ''}>
          ${esc(c.label)}${s.model_family === c.id ? ' · 지금' : ''}<span class="muted small">${c.note ? ' — ' + esc(c.note) : ''}</span></button>`).join('')
      + (busy ? '<div class="small warn">작업 중입니다 — 대기열에 들어가 지금 작업이 끝난 뒤 바뀝니다.</div>' : '')
      + '<div class="small muted">대화가 쌓인 세션은 바꾼 뒤 첫 응답이 전체 대화를 다시 읽느라 느리고 토큰이 더 듭니다(CC가 묻는 확인은 브리지가 대신 답합니다).</div>'
      + '<div class="small muted">이 세션만 바뀝니다. CC가 /model을 새 세션 기본값으로도 저장하는데, 브리지가 바로 원래대로 되돌립니다.</div>';
    const r = b.getBoundingClientRect();
    mdlMenu.style.left = `${Math.max(8, Math.min(r.left, innerWidth - 300))}px`;
    mdlMenu.style.top = `${r.bottom + 4}px`;
    mdlMenu.hidden = false;
  });
  mdlMenu.addEventListener('click', async (ev) => {
    const c = ev.target.closest('button[data-id]');
    if (!c) return;
    closeMenu();
    const id = store.state.selected;
    if (id != null) await store.switchModel(id, c.dataset.id, c.dataset.label);
  });
  document.addEventListener('click', (ev) => { if (!mdlMenu.hidden && !mdlMenu.contains(ev.target)) closeMenu(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !mdlMenu.hidden) { ev.stopPropagation(); closeMenu(); } }, true);
  // 압축 알림 띠(11-05, docs/11_handoff_v2.md 3장) — 2번째 압축부터 "넘어갈 때", 4번째부터 "늦었음".
  // [나중에]는 다음 압축까지 숨긴다(이 브라우저에만 — 압축 횟수로 기억)
  function drawCompact(s) {
    const c = s.compact;
    const snoozed = c && compactSnoozed(s.id, c.count);
    if (!c || !c.level || snoozed) { $('pCmp').hidden = true; return; }
    const late = c.level === 'late';
    const html = `<span class="${late ? 'bad' : 'warn'}">📦 압축 ${c.count}번 — ${late
        ? '늦었습니다. 앞에서 정한 결정 · 금지가 이미 많이 빠졌을 수 있습니다.'
        : '넘어갈 때입니다. 처음에 정한 것이 빠지기 시작합니다.'}${c.short ? ' 압축 간격도 짧습니다.' : ''}</span>
      ${s.injectable ? '<button type="button" data-cmp="handoff" class="small" title="인계 요약 받기 — 세션이 지금까지를 인계 문서로 씁니다. 받은 뒤 [세션] 탭에서 확인하고 새 세션을 띄웁니다.">인계 요약 받기</button>' : ''}
      <button type="button" data-cmp="later" class="ghost small" title="나중에 — 다음 압축까지 이 띠를 숨깁니다.">나중에</button>`;
    put('pCmp', 'cmp', html);
    $('pCmp').className = `pcmp small ${late ? 'late' : 'due'}`;
    $('pCmp').hidden = false;
  }
  function compactSnoozed(id, count) {
    try { return Number(localStorage.getItem('cmpSnooze:' + id) || 0) >= count; } catch { return false; }
  }
  $('pCmp').addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-cmp]');
    const s = store.state.sessions.get(store.state.selected);
    if (!b || !s || !s.compact) return;
    if (b.dataset.cmp === 'later') {
      try { localStorage.setItem('cmpSnooze:' + s.id, String(s.compact.count)); } catch { /* 저장 못 함 — 이번만 숨긴다 */ }
      $('pCmp').hidden = true;
      store.touch('grid');
      return;
    }
    b.disabled = true;
    const r = await fetch(`/api/sessions/${s.id}/summary`, { method: 'POST', headers: store.headers(true), body: JSON.stringify({ kind: 'handoff', mode: 'live' }) });
    const j = await r.json().catch(() => ({}));
    store.state.lastInput = { sessionId: s.id, ts: Date.now(), ok: r.ok,
      msg: r.ok ? '인계 요약을 요청했습니다. 세션이 쓰는 중입니다 — [세션] 탭에서 확인하고 새 세션을 띄울 수 있습니다.' : `요청하지 못했습니다 — ${j.refused || j.detail || r.status}` };
    if (r.ok) setTab('sess');
    b.disabled = false;
    store.touch('panel');
  });
  window.foremanCompactSnoozed = compactSnoozed;     // 픽셀 화면의 📦 표시도 같은 기준으로 숨긴다

  // 바꾸는 중 표시 — 응답 모델이 고른 것과 같아지면(또는 30분이 지나면) 지운다
  function pendModel(st, s) {
    const p = st.pendingModel.get(s.id);
    if (p && (s.model_family === p.model || Date.now() - p.ts > 30 * 60 * 1000)) { st.pendingModel.delete(s.id); return null; }
    return p || null;
  }

  $('pForm').onsubmit = async (ev) => {
    ev.preventDefault();
    const id = store.state.selected, text = $('pText').value;
    if (!id || !text.trim()) return;
    // '/'로 시작하면(11-05, 체크박스 대신) — 아는 CC 명령은 실행, 맥락을 날리는 명령은 확인, 모르는 /낱말은 묻고, 경로 · 여러 줄은 글로
    const si = slashIntent(text);
    let command = si.kind === 'command';
    if (si.kind === 'confirm') {
      if (!confirm(`/${si.name}을(를) 실행할까요? 이 세션의 대화 맥락이 사라지거나 세션이 끝날 수 있습니다.`)) return;
      command = true;
    } else if (si.kind === 'ask') {
      command = confirm(`/${si.name}은(는) 모르는 명령입니다. CC 명령으로 실행할까요?\n[확인] 명령으로 실행 · [취소] 글자 그대로 보내기`);
    }
    $('pSend').disabled = true;
    const r = await store.sendInput(id, text, command);
    $('pSend').disabled = false;
    if (r.ok) { $('pText').value = ''; const c = $('pConvo'); c.scrollTop = c.scrollHeight; }   // 보냈으면 내 글이 보이는 곳으로
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

  function sessionMode(on) {
    $('pSel').hidden = on; $('pTabs').hidden = !on; $('pMeta').hidden = !on; $('pForm').hidden = !on;
    if (!on) $('pCmp').hidden = true;
    if (on) setTab(tab);
    else { $('pTabConvo').hidden = $('pTabAct').hidden = $('pTabSess').hidden = true; el.classList.remove('tab-convo'); }
  }
  const put = (id, key, html) => { if (last[key] !== html) { last[key] = html; $(id).innerHTML = html; return true; } return false; };

  function drawSession(st) {
    const s = st.selected != null ? st.sessions.get(st.selected) : null;
    if (!s) { hand.setSession(null); sessionMode(false); drawHint(st); return; }
    const switched = lastSel !== s.id;
    if (switched) { sessionMode(true); last.convo = last.feed = last.meta = last.info = ''; }
    hand.setSession(s.id);
    if (!editingTitle) {
      $('pTitle').textContent = sessionName(s) + (s.custom_title ? '' : ' ');
      $('pTitle').dataset.tip = `${sessionName(s)} — 눌러서 이름을 바꿉니다.${s.custom_title ? ` 자동 제목은 "${s.title || s.cc_name || s.short}"입니다.` : ''}`;
      $('pTitle').classList.add('editable');
    }
    // 제목 아래 한 줄 — 세션 정보 · 토큰은 여기 작게, 자세한 것은 [세션] 탭
    const t = s.tokens || {}, stuck = stuckTurn(s);
    const now = s.activity && s.state === 'ACTIVE' ? `${esc(s.activity.tool)} ${esc(oneLine(s.activity.target || '', 60))}` : (s.state === 'ACTIVE' ? '생각 중' : '');
    put('pMeta', 'meta', `<span class="badge st-${s.state}">${esc(STATE_LABEL[s.state] || s.state)}</span>
      <span class="muted">${esc(sessionSub(s))}</span> ${modelChip(s, pendModel(st, s), !!s.injectable)}${now ? ` · <b>${now}</b>` : ''}${s.subagents_running ? ` · 서브 ${s.subagents_running}` : ''}
      · <span class="muted">오늘 출력 ${tok(t.today_output)}</span>${stuck ? ' · <span class="warn">⚠ 끝 신호 없는 턴</span>' : ''}`);
    $('pMeta').title = `${sessionSub(s)} · ${projectLabel(st, s.project)} · ${(s.cwd || '')}`;
    drawCompact(s);
    // 대화 — 바뀔 때만
    const c = $('pConvo');
    const follow = switched || nearBottom(c);
    const html = convoHtml(st.convo.get(s.id)) || '<p class="small muted">불러오는 중…</p>';
    if (put('pConvo', 'convo', html)) {
      if (follow) c.scrollTop = c.scrollHeight;
      else if (tab === 'convo') $('pNew').hidden = false;
    }
    $('pTabs').querySelector('[data-n="act"]').textContent = s.feed.length ? ` ${s.feed.length}` : '';
    if (tab === 'act' || switched) put('pFeed', 'feed', feedHtml(s));
    if (tab === 'sess' || switched) {
      put('pInfo', 'info', `<div class="small muted">${esc(projectLabel(st, s.project))} · ${esc((s.cwd || '').replace(/^\/home\/[^/]+/, '~'))}</div>
        ${s.open_turn ? `<div class="small${stuck ? ' warn' : ''}">${stuck ? '⚠ 끝 신호 없는 턴' : '▶ 턴'} ${esc(ORIGIN_LABEL[s.open_turn.origin] || '')} · ${ago(s.open_turn.started_at)} 시작</div>` : ''}
        ${sessionKv(s, pendModel(st, s))}`);
    }
    const blocked = !s.injectable;
    $('pText').disabled = blocked; $('pSend').disabled = blocked;
    // 입력 칸 아래 — 가운데는 세션 상태(짧게), 아래 줄은 보낸 결과(성공은 한 마디, 잘못됐을 때만 자세히)(11-05)
    const why_ = blocked ? why(s) : '';
    $('pWhy').textContent = blocked ? '보낼 수 없음' : (s.state === 'ACTIVE' ? '작업 중 — 대기열' : '');
    $('pWhy').className = `pwhy small${blocked ? ' bad' : s.state === 'ACTIVE' ? ' busy' : ''}`;
    if (blocked) $('pWhy').dataset.tip = `보낼 수 없음 — ${why_}`; else if (s.state === 'ACTIVE') $('pWhy').dataset.tip = '작업 중 — 지금 보내면 대기열에 들어가 진행 중인 작업에 이어 전달됩니다.'; else delete $('pWhy').dataset.tip;
    const li = st.lastInput && st.lastInput.sessionId === s.id && Date.now() - st.lastInput.ts < (st.lastInput.ok ? 8000 : 60000) ? st.lastInput : null;
    $('pResult').innerHTML = blocked ? `<span class="muted">${esc(why_)}</span>` : li ? `<span class="${li.ok ? 'ok' : 'bad'}">${esc(li.msg)}</span>` : '';
    if (switched) { $('pText').value = ''; lastSel = s.id; $('pNew').hidden = true; }
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
    if (!names && st.hiddenDormant) rows.push(`<p class="small muted">48시간 넘게 활동이 없는 세션 ${st.hiddenDormant}개는 숨겼습니다.</p>`);
    return rows.join('') || '<p class="small muted">세션이 없습니다.</p>';
  }

  function drawHint(st) {
    lastSel = undefined;
    $('pTitle').classList.remove('editable'); delete $('pTitle').dataset.tip;
    $('pClear').hidden = !target;
    if (target && target.kind === 'infra') {
      $('pTitle').textContent = target.name;
      $('pSel').innerHTML = `<div class="small muted">${esc(projectLabel(st, target.room))} · 지금 ${esc(target.status || '기록 없음')}</div>
        ${pipeBlock(st.pipeline.get(target.room)) || '<p class="small muted">파이프라인 기록 없음</p>'}`;
      return;
    }
    if (target && target.kind === 'foreman') {
      $('pTitle').textContent = target.room ? `포먼 · ${projectLabel(st, target.room)}` : '포먼(감독)';
      $('pSel').innerHTML = `<p class="small muted">포먼은 아직 자기 세션이 없습니다. 아래에서 세션을 고르면 대화와 입력 칸이 열립니다.</p>
        ${target.room ? pipeBlock(st.pipeline.get(target.room)) : ''}
        ${sessionList(st, target.room ? [target.room] : null)}`;
      return;
    }
    $('pTitle').textContent = '패널';
    $('pSel').innerHTML = `<p class="small muted">캐릭터를 누르면 최근 대화와 입력 칸이 여기 열립니다. 아래에서 세션을 바로 골라도 됩니다.</p>${sessionList(st, null)}`;
  }

  function draw(st) {
    if (target && target.kind === 'session') { $('pClear').hidden = false; drawSession(st); return; }
    sessionMode(false);
    hand.setSession(null);
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
