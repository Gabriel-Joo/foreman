// 픽셀 화면 옆 패널(10b, 11-05 다시 짬) — 대화가 주인공. 제목 줄 바로 아래부터 입력 칸 바로 위까지 대화가 차지한다.
//   맨 위: 승인 대기(급한 것 — 늘 위)
//   제목 줄: 세션 이름 + 한 줄(상태 · 지금 · 서브 · 오늘 출력) + 넓게/좁게
//   탭: [대화](기본) · [활동](도구 호출 — 누르면 입력 · 결과 본문을 트랜스크립트에서) · [세션](정보 · 인계 · 세션 조작 · 승인 이력)
// 대화는 내용이 바뀔 때만 다시 그린다 — 읽던 자리 · 고른 글자가 10초마다 날아가지 않게. 아래를 보고 있으면 새 답을 따라 내려가고,
// 위를 보고 있으면 그대로 두고 [새 답 ↓]만 띄운다.
// 너비는 두 가지(좁게 = 픽셀 볼 때, 넓게 = 대화 읽을 때)뿐이다(11-10 사용자 — 손잡이를 끌어 만든 중간 너비마다 픽셀 화면 자리가
// 달라져 이름표 자리 고르기가 복잡해졌다. 끌기를 막고 두 값만). 손잡이는 두 번 누르면 오간다.

import { approvalCard, handleApprovalClick, handleApprovalInput, restoreNotes, apprPlace, apprFoldLine, apprPeekLine, keep, sessionKv, modelChip, convoHtml, feedHtml, pipeBlock, mountApprovalHistory,
         sessionName, sessionSub, sessionIds, worktreeTip, doingHtml, projectLabel, roleBadge, panelRole, ROLE_LABEL, SESSION_ROLES, ROLE_UNKNOWN_TIP, why, oneLine, esc, ago, tok, STATE_LABEL, ORIGIN_LABEL, FEED_DETAIL, FEED_OPEN, stateBadge, humanNeed, stallChip } from './render.js';
import { stuckTurn } from './store.js';
import { slashIntent } from './slash.js';
import { hideTip } from './tip.js';
import { modelMenuHtml, sameModel } from './modelpick.js';
import { mountHandoff, FLOW_TIP } from './handoff.js';
import { createScribe } from './scribe.js';
import { createCoder } from './coder.js';
import { createForemanPanel } from './fmpanel.js';
import { createCcWindow } from './ccscreen.js';

const KEY_OPEN = 'foremanPanelOpen', KEY_TAB = 'foremanPanelTab', KEY_MODE = 'foremanPanelMode';
const KEY_W = { narrow: 'foremanPanelW', wide: 'foremanPanelWideW' };      // 11-10 전 끌어서 기억한 너비 — 읽지 않고 지운다
// 11-11 사용자 — 화면 : 패널을 좁게 6 : 4, 넓게 4 : 6(전엔 좁게 패널 420px 남짓이라 너무 작아 쓰지 않게 됐다).
// 넓게도 픽셀 화면이 STAGE_MIN 밑으로는 줄지 않는다 — 방 모눈 28칸이 한 칸 16px(방 배율 1, 원본 그림 1배)로 들어가는 폭(office.js roomViewScale).
// 1024 창은 넓게가 4 : 6이 아니라 화면 464 : 패널 560이 된다(log/designer_polish_seven_20261111.md)
const STAGE_MIN = 464;
const WIDTH = {                                   // 기본 너비 · 창에 대한 최대 비율
  narrow: { def: () => Math.round(window.innerWidth * 0.4), max: 0.4 },
  wide: { def: () => Math.round(Math.min(window.innerWidth * 0.6, window.innerWidth - STAGE_MIN)), max: 0.6 },
};
const MIN_W = 280;
// 「세션」 → 「세션 정리」(11-14 사용자). 「CC 화면」은 탭이 아니라 탭 줄 끝 단추 → 띄우는 창(11-14 사용자, ccscreen.js)
const TABS = [['convo', '대화'], ['act', '활동'], ['sess', '세션 정리']];
const TAB_TIP = {
  sess: '세션 정리 — 세션 정보 · 넘기기 · 합치기 · 끝내기 · 승인 기록입니다.',
};
const CC_TIP = '세션 화면 — 이 세션의 Claude Code 창을 띄우는 창으로 봅니다. 권한 · 계획 승인 · 고르기 창도 보이고, 여기서 친 키(화살표 · Esc · 숫자 · Enter)는 CC에 바로 갑니다.';
const ls = { get(k) { try { return localStorage.getItem(k); } catch { return null; } },
             set(k, v) { try { localStorage.setItem(k, v); } catch { /* 저장 못 해도 이 탭에서는 된다 */ } },
             del(k) { try { localStorage.removeItem(k); } catch { /* 없어도 된다 */ } } };

// target: null | { kind:'session' } (store.state.selected) | { kind:'infra', room, infra, name, status } | { kind:'foreman', room } (room=null이면 감독실)
export function createSidePanel(host, store, { onSelectSession, onToggle, onClear }) {
  const el = document.createElement('aside');
  el.className = 'oside';
  el.setAttribute('aria-label', '패널');
  el.innerHTML = `
    <div class="oside-grip" title="너비 — 두 번 누르면 넓게와 좁게를 오갑니다. 너비는 이 둘뿐입니다."></div>
    <button id="pStrip" class="oside-strip" title="패널 — 접은 패널을 폅니다.">
      <span>◀</span><span id="pStripBadge"></span><span class="oside-vert">패널</span>
    </button>
    <div class="oside-main">
      <div class="oside-bar">
        <button id="pRole" type="button" class="rolebadge" hidden></button><span id="pSid" class="small muted psid" hidden></span><b id="pTitle">패널</b><span id="pCount" class="small"></span>
        <button id="pWide" class="ghost small right" title="너비 — 대화를 읽을 땐 넓게, 픽셀을 볼 땐 좁게 합니다."></button>
        <button id="pClear" class="ghost small" title="선택 해제 — 고른 세션을 놓습니다." hidden>✕</button>
        <button id="pFold" class="ghost small" title="접기 — 패널을 접어 픽셀 화면을 넓힙니다.">▶</button>
      </div>
      <div id="pMeta" class="pmeta small" hidden></div>
      <div id="pSw" class="pcmp small switch" hidden></div>
      <div id="pCmp" class="pcmp small" hidden></div>
      <div id="pOvl" class="pcmp small" hidden></div>
      <section id="pAppr" class="papprs" aria-label="승인 대기"></section>
      <nav id="pTabs" class="ptabs" hidden>${TABS.map(([k, l]) => `<button data-tab="${k}"${TAB_TIP[k] ? ` data-tip="${TAB_TIP[k]}"` : ''}>${l}<span data-n="${k}"></span></button>`).join('')}<button type="button" id="pCcOpen" class="ptab-cc" data-tip="${CC_TIP}">세션 화면 ↗</button></nav>
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
          <details id="pKvBox" class="hand"><summary title="세션 정보 — 켜져 있는지, 지금 무엇을 하는지, 어떤 모델을 쓰는지, 얼마나 썼는지 봅니다."><b>세션 정보 · 토큰</b> <span id="pKvHead" class="small muted"></span></summary><div id="pKv"></div></details>
          <details id="pHist" class="appr-hist"><summary class="small" title="승인 기록 — 세션이 위험할 수 있는 명령을 하려다 나에게 물은 것과, 내가 어떻게 답했는지입니다.">승인 기록<span id="pHistHead" class="muted"></span></summary><div id="pHistBody" class="small"></div></details>
        </div>
      </div>
      <form id="pForm" class="input" hidden>
        <div id="pGrip" class="pgrip" role="separator" aria-orientation="horizontal" tabindex="0" aria-label="입력 칸 높이" data-tip="높이 조절 — 위아래로 끌어 입력 칸 높이를 바꿉니다(키보드는 ↑ ↓). 더블클릭하면 기본 높이로 돌아갑니다."></div>
        <button type="button" id="pAskHint" class="ghost small pask" data-tip="입력 칸 — 세션이 질문의 답을 기다리는 동안은 질문 카드의 글 칸으로 보냅니다. 누르면 이 입력 칸을 펼칩니다.">질문에 답하는 중 — 글은 질문 카드의 글 칸으로 · 입력 칸 펼치기</button>
        <textarea id="pText" rows="6"placeholder="이 세션에 보낼 입력 (Ctrl+Enter로 보냅니다)"></textarea>
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
  // 서기실 창(12a) — 서기를 누르면 pSel에 그린다. 버튼은 여기서 한 번만 받는다(다시 그려도 그대로)
  const scribe = createScribe(store);
  const fmp = createForemanPanel(store);       // 감독실 캐릭터(11-08) — 노트 · 지난 디스패치 · 자동 제안
  const coder = createCoder(store);           // 코더 상주(11-09) — 맡길 일 · 지금 일
  // CC 화면 띄우는 창(11-14) — 패널을 접거나 다른 세션을 골라도 그대로 둔다(사용자 결정 — 띄운 세션 그대로, 머리줄에 번호 · 제목)
  const ccw = createCcWindow(store);
  $('pCcOpen').addEventListener('click', () => { if (store.state.selected != null) ccw.open(store.state.selected); });
  $('pSel').addEventListener('click', (ev) => {
    if (target && target.kind === 'scribe') scribe.onClick(ev, target.room, projectLabel(store.state, target.room),
      (sid) => { onSelectSession(sid); setTab('sess'); });     // 열린 서기 일 → 그 세션의 「따로 작업」(11-06)
    if (target && target.kind === 'coder') coder.onClick(ev, target.room, (sid) => { onSelectSession(sid); setTab('sess'); },
      (p, to) => window.office && window.office.openTodo && window.office.openTodo(p, to));
    if (target && target.kind === 'foreman') fmp.onClick(ev);
  });
  $('pSel').addEventListener('input', (ev) => { if (target && target.kind === 'scribe') scribe.onInput(ev); });
  $('pSel').addEventListener('keydown', (ev) => { if (target && target.kind === 'scribe') scribe.onKey(ev, target.room); });
  window.addEventListener('foreman-state', () => { if (target && target.kind === 'foreman') fmp.load([], true); });
  mountApprovalHistory($('pHist'), $('pHistHead'), $('pHistBody'), store);

  let target = null, targetKey = '', lastSel = undefined;
  let reportSent = null;           // 「보고 옴」 읽음을 보낸 응답 이벤트 id(같은 것을 두 번 보내지 않게)
  let escSent = null;              // 「사용자에게 보고함」 읽음을 보낸 escalate id(11-13)
  let open = ls.get(KEY_OPEN) !== '0';
  let tab = TABS.some(([k]) => k === ls.get(KEY_TAB)) ? ls.get(KEY_TAB) : 'convo';
  let mode = ls.get(KEY_MODE) === 'wide' ? 'wide' : 'narrow';
  const seen = { approvals: -1, panel: -1, pipe: -1, grid: -1 };
  const knownPending = new Set();
  let firstAppr = true;
  const last = { convo: '', convoSid: null, feed: '', meta: '', info: '' };

  // ── 접기 · 너비(좁게 / 넓게) ─────────────────────────
  for (const k of Object.values(KEY_W)) ls.del(k);
  function applyWidth() {
    const w = WIDTH[mode].def();
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
  // 세션 역할(11-09) — 머리줄 역할 배지를 누르면 그 자리에서 고른다. 제목 고치기와 따로(제목을 고쳐도 역할은 남는다)
  let pickingRole = false;
  $('pRole').addEventListener('click', () => {
    const s = target && target.kind === 'session' && store.state.selected != null ? store.state.sessions.get(store.state.selected) : null;
    if (!s || pickingRole) return;
    pickingRole = true;
    const btn = $('pRole');
    const sel = document.createElement('select');
    sel.className = 'prole-pick';
    sel.innerHTML = SESSION_ROLES.map((r) => `<option value="${r}"${r === s.role ? ' selected' : ''}>${esc(ROLE_LABEL[r])}</option>`).join('');
    btn.hidden = true;
    btn.after(sel);
    sel.focus();
    const done = async (role) => {
      if (!pickingRole) return;
      pickingRole = false;
      sel.remove(); btn.hidden = false;
      if (!role || role === s.role) return;
      try { await store.setRole(s.id, role); } catch (e) { $('pResult').innerHTML = `<span class="bad">역할을 바꾸지 못했습니다 — ${esc(e.message)}</span>`; }
    };
    sel.addEventListener('change', () => done(sel.value));
    sel.addEventListener('blur', () => done(undefined));
    sel.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); done(undefined); } });
  });
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
  grip.addEventListener('dblclick', () => setMode(mode === 'wide' ? 'narrow' : 'wide'));   // 끌기는 없다(11-10) — 두 값만
  window.addEventListener('resize', applyWidth);
  // 터미널은 패널 왼쪽까지만(11-10) — 패널이 오른쪽에 붙어 있으면(휴대폰 폭은 아래에 쌓여 아님) 터미널 오른쪽을 패널 폭만큼 비우고,
  // 패널은 office.html body.term-beside 규칙으로 창 바닥까지 늘어난다. 너비를 끌거나 접고 펴면 ResizeObserver가 따라간다
  function syncTermSide() {
    const r = el.getBoundingClientRect(), beside = r.width > 0 && r.left > 0 && Math.abs(r.right - window.innerWidth) < 2;
    document.body.classList.toggle('term-beside', beside);
    document.body.style.setProperty('--term-right', beside ? `${Math.round(window.innerWidth - r.left)}px` : '0px');
  }
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(syncTermSide).observe(el);
  window.addEventListener('resize', syncTermSide);
  requestAnimationFrame(syncTermSide);
  applyWidth();
  setOpen(open, false);

  // ── 탭 ──────────────────────────────────────────────
  function setTab(k, remember = true) {
    tab = k; if (remember) ls.set(KEY_TAB, k);
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
  $('pConvo').addEventListener('scroll', () => { noteConvo(); if (nearBottom($('pConvo'))) $('pNew').hidden = true; });
  // 대화 칸 높이가 바뀌면(입력 칸 끌기 · ↑↓ · 더블클릭 · 모서리 · 창 크기) 아래쪽 기준으로 붙인다(11-11 사용자 — 입력 칸을 끌어 올리면
  // 대화 칸이 아래부터 줄어 맨 아래 글이 가려졌다). 맨 아래를 보고 있었으면 끄는 동안에도 맨 아래, 위를 읽던 중이면 보던 글이 제자리.
  // ResizeObserver는 그리기 전에 불려 끄는 동안 흔들리지 않는다. 숨은 칸(다른 탭 · 높이 0)은 건드리지 않는다
  // 맨 아래를 보고 있었는지(convoStick)는 따로 기억한다 — 글씨 배율(zoom) 아래에서 scrollTop이 소수라 아래쪽 거리가 1~2px 남던 것을 없앤다(11-11 사용자)
  let convoFromBottom = 0, convoH = -1, convoStick = true;
  const STICK_PX = 4;
  function noteConvo() {
    const c = $('pConvo');
    if (!c.clientHeight) return;
    convoFromBottom = Math.max(0, c.scrollHeight - c.scrollTop - c.clientHeight);
    convoStick = convoFromBottom < STICK_PX;
  }
  function pinConvo() {
    const c = $('pConvo');
    if (!c.clientHeight) return;
    c.scrollTop = convoStick ? c.scrollHeight : c.scrollHeight - c.clientHeight - convoFromBottom;
  }
  // 끌기를 마친 뒤 한 번 더 — 마지막 높이 변화 뒤 레이아웃이 가라앉은 다음에도 맨 아래에 붙게(opanel 아래 띠 끝내기에서 부른다)
  const repinConvo = () => requestAnimationFrame(() => { pinConvo(); requestAnimationFrame(pinConvo); });
  if (typeof ResizeObserver === 'function') {
    new ResizeObserver(() => {
      const c = $('pConvo');
      if (!c.clientHeight || c.clientHeight === convoH) return;
      const first = convoH < 0;
      convoH = c.clientHeight;
      if (!first) pinConvo();
    }).observe($('pConvo'));
  }
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
  $('pAppr').addEventListener('input', handleApprovalInput);
  $('pAppr').addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && ev.target.matches('textarea')) { ev.stopPropagation(); ev.target.blur(); } });
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
  // 모델 바꾸기(11-05) — 머리줄의 모델 표시를 누르면 목록, 고르면 그 세션에 /model <id>(창 글은 modelpick.js modelMenuHtml)
  const mdlMenu = document.createElement('div');
  mdlMenu.className = 'mdl-menu'; mdlMenu.hidden = true;
  document.body.appendChild(mdlMenu);
  const closeMenu = () => { mdlMenu.hidden = true; };
  $('pMeta').addEventListener('click', async (ev) => {
    const off = ev.target.closest('[data-asksoff]');
    if (off) {
      ev.stopPropagation();
      off.disabled = true;
      try { await store.asksOff(Number(off.dataset.asksoff)); }
      catch (e) { off.disabled = false; off.title = `끄지 못했습니다 — ${e.message}`; }
      return;
    }
    const b = ev.target.closest('[data-mdl]');
    if (!b) return;
    ev.stopPropagation();
    if (!mdlMenu.hidden) { closeMenu(); return; }
    const s = store.state.sessions.get(store.state.selected);
    const m = await store.modelChoices();
    if (!s || !m) return;
    mdlMenu.innerHTML = modelMenuHtml(m, s.model, s.state === 'ACTIVE');
    const r = b.getBoundingClientRect();
    mdlMenu.hidden = false;                  // 폭(글씨 배율을 따른다)을 잰 뒤 자리를 잡는다
    mdlMenu.style.left = `${Math.max(8, Math.min(r.left, innerWidth - mdlMenu.offsetWidth - 8))}px`;
    mdlMenu.style.top = `${r.bottom + 4}px`;
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
    if (!c || !c.level || snoozed) { drawContext(s); return; }
    const late = c.level === 'late';
    const html = `<span class="${late ? 'bad' : 'warn'}" title="대화 자동 요약 — 대화가 길어 앞부분을 요약해 줄였습니다. 줄일수록 처음에 정한 것을 잊습니다.">📦 대화 자동 요약 ${c.count}번 — ${late
        ? '늦었습니다. 앞에서 정한 결정 · 금지가 이미 많이 빠졌을 수 있습니다.'
        : '넘어갈 때입니다. 처음에 정한 것이 빠지기 시작합니다.'}${c.short ? ' 요약 간격도 짧습니다.' : ''}</span>
      ${s.injectable ? `<button type="button" data-cmp="handoff" class="small primary" title="${esc(FLOW_TIP)}">새 세션으로 옮기기</button>` : ''}
      <button type="button" data-cmp="loss" class="small" title="압축으로 잊은 것 찾기 — 압축으로 사라지거나 약해진 지시 · 결정을 판정합니다. 내가 보낸 말 20개당 약 0.4달러 · 1.5분이 들고, 결과는 [세션 정리] 탭 「넘기기 전 정리」에 나옵니다.">압축으로 잊은 것 찾기</button>
      <button type="button" data-cmp="later" class="ghost small" title="나중에 — 다음 압축까지 이 띠를 숨깁니다.">나중에</button>`;
    put('pCmp', 'cmp', html);
    $('pCmp').className = `pcmp small ${late ? 'late' : 'due'}`;
    $('pCmp').hidden = false;
  }
  // 맥락 크기 띠(11-08) — 압축 단계가 없을 때. 토큰(300k · 500k)이나 창 비율(50% · 75%) 중 먼저 닿는 쪽(11-09). [나중에]는 다음 단계까지
  // 작업 전환 권유 띠가 떠 있으면 그쪽이 같은 [새 세션으로 옮기기]를 더 분명한 까닭과 함께 권하므로 이 띠는 숨긴다
  function drawContext(s) {
    const x = s.context;
    const lv = x && x.level;
    let snz = '';
    try { snz = localStorage.getItem('ctxSnooze:' + s.id) || ''; } catch { /* 기억 못 함 */ }
    if (!lv || snz === lv || (snz === 'late' && lv === 'due') || !$('pSw').hidden) { $('pCmp').hidden = true; return; }
    const late = lv === 'late';
    // 11-09 사용자 문구 — 겉은 짧게, 호버에 크기를 사람 말로(한글 ≈ 토큰 × 0.9자, 책 한 권 ≈ 10만 자)
    const usd = x.usd_reply != null ? ` · 응답당 약 $${x.usd_reply < 0.1 ? x.usd_reply.toFixed(2) : x.usd_reply.toFixed(1)}` : '';
    // 툴팁 모양(11-09): 제목 — 설명 / 숫자 한 줄에 하나
    const tip = '지금까지 쌓인 대화 — 답할 때마다 이걸 전부 다시 읽고, 그만큼 비용이 듭니다. 새 세션으로 옮기면 수십k에서 다시 시작합니다.'
      + `\n토큰 ${koNum(x.tokens)}${x.pct != null ? ` — 창 ${koNum(x.window)}의 ${x.pct}%` : ''}\n한글 약 ${koNum(Math.round(x.tokens * 0.9 / 10000) * 10000)} 자 (책 ${koBooks(x.tokens * 0.9 / 100000)}쯤)`
      + (x.usd_reply != null ? `\n응답당 약 $${x.usd_reply.toFixed(2)}` : '');
    const html = `<span class="${late ? 'bad' : 'warn'}" title="${esc(tip)}">🧠 지금까지 쌓인 대화 ${Math.round(x.tokens / 1000)}k${x.pct != null ? ` (${x.pct}%)` : ''}${usd}</span>
      ${s.injectable ? `<button type="button" data-cmp="handoff" class="small primary" title="${esc(FLOW_TIP)}">새 세션으로 옮기기</button>` : ''}
      <button type="button" data-cmp="ctxlater" class="ghost small" title="나중에 — 다음 단계까지 이 띠를 숨깁니다.">나중에</button>`;
    put('pCmp', 'cmp', html);
    $('pCmp').className = `pcmp small ${late ? 'late' : 'due'}`;
    $('pCmp').hidden = false;
  }
  // 33만 6천 · 책 세 권 — 맥락 띠 호버(11-09)
  function koNum(n) {
    const man = Math.floor(n / 10000), cheon = Math.floor((n % 10000) / 1000);
    return man ? `${man}만${cheon ? ` ${cheon}천` : ''}` : cheon ? `${cheon}천` : String(n);
  }
  function koBooks(b) {
    const n = Math.max(1, Math.round(b));
    return `${['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열'][n] || n} 권`;
  }
  // 머리줄 "쌓인 대화 N%"(11-09) — 세션의 대화가 모델 창을 얼마나 채웠나. 계정의 사용 한도(머리 칩 "한도")와 같은 %라
  // 헷갈리지 않게 이름을 나눈다(호버에 「한도와는 다릅니다」는 11-14 사용자 「군더더기」로 뺐다). 창을 모르는 모델은 k로, 설정한 창보다 크면 ⚠(창 크기 값이 틀렸다)
  function ctxChip(s) {
    const x = s.context;
    if (!x || !x.tokens) return '';
    const k = `${Math.round(x.tokens / 1000)}k`;
    const cls = x.window_over ? 'warn' : x.level === 'late' ? 'bad' : x.level === 'due' ? 'warn' : 'muted';
    const label = x.window_over ? `쌓인 대화 ${k} ⚠` : x.pct != null ? `쌓인 대화 ${x.pct}%` : `쌓인 대화 ${k}`;
    const tip = x.window_over
      ? `쌓인 대화 — 설정한 창보다 커서 %를 낼 수 없습니다. 창 크기 값이 틀렸습니다(config/models.toml [windows]).\n토큰 ${koNum(x.tokens)}\n설정한 창 ${koNum(x.window)}`
      : `쌓인 대화 — 이 세션의 대화가 모델이 한 번에 읽을 수 있는 양(창)을 얼마나 채웠는지입니다.${x.window ? '' : ' 창 크기를 모르는 모델이라 %는 내지 않습니다.'}`
        + `\n토큰 ${koNum(x.tokens)}${x.window ? `\n창 ${koNum(x.window)}` : ''}`;
    return `<span class="${cls}" data-tip="${esc(tip)}">${label}</span> · `;
  }
  // 작업 전환 권유 띠(11-09, bridge/switchwatch.py) — 텔레그램과 같은 판정을 dashboard가 싣는다(s.switch).
  // 전환 말 + (30분 안 커밋 | 20분 넘는 쉼) + 쌓인 대화 문턱 이상. [나중에]는 그 사람 턴 동안만(다음 입력에서 다시 판정)
  function drawSwitch(s) {
    const w = s.switch;
    let snz = '';
    try { snz = localStorage.getItem('swSnooze:' + s.id) || ''; } catch { /* 기억 못 함 */ }
    if (!w || snz === String(w.turn_id)) { $('pSw').hidden = true; return; }
    const why = w.committed && w.idle ? '방금 커밋했고 한참 쉬었다 오셨고' : w.committed ? '방금 커밋했고' : '한참 쉬었다 오셨고';
    const tip = `작업 전환 권유 — 새 일을 시작하는 말에, 방금 한 커밋이나 긴 쉼이 겹치고 쌓인 대화가 많을 때 띄웁니다. 옮기기 전에 대화에서만 정한 결정은 문서로 옮겨 둡니다.`
      + `\n걸린 말 「${w.phrase}」\n쌓인 대화 ${w.pct}%`;
    put('pSw', 'sw', `<span data-tip="${esc(tip)}">🔀 다른 일로 넘어가시는 것 같습니다 — ${why} 쌓인 대화가 ${w.pct}%입니다. 새 일은 새 세션에서 시작하면 빠르고 쌉니다.</span>
      ${s.injectable ? `<button type="button" data-sw="handoff" class="small primary" title="${esc(FLOW_TIP)}">새 세션으로 옮기기</button>` : ''}
      <button type="button" data-sw="later" class="ghost small" title="나중에 — 이 띠를 숨깁니다. 다음에 다른 일로 넘어갈 때 다시 판단합니다.">나중에</button>`);
    $('pSw').hidden = false;
  }
  $('pSw').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-sw]');
    const s = store.state.sessions.get(store.state.selected);
    if (!b || !s || !s.switch) return;
    if (b.dataset.sw === 'later') {
      try { localStorage.setItem('swSnooze:' + s.id, String(s.switch.turn_id)); } catch { /* 이번만 숨긴다 */ }
      $('pSw').hidden = true;
      drawCompact(s);                 // 숨긴 자리에 쌓인 대화 띠가 다시 보일 수 있다
      return;
    }
    startHandoff(s.id);
  });
  function compactSnoozed(id, count) {
    try { return Number(localStorage.getItem('cmpSnooze:' + id) || 0) >= count; } catch { return false; }
  }
  $('pCmp').addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-cmp]');
    const s = store.state.sessions.get(store.state.selected);
    if (b && s && b.dataset.cmp === 'ctxlater') {
      try { localStorage.setItem('ctxSnooze:' + s.id, (s.context && s.context.level) || ''); } catch { /* 이번만 숨긴다 */ }
      $('pCmp').hidden = true;
      return;
    }
    if (!b || !s || (!s.compact && !(s.context && s.context.level))) return;
    if (b.dataset.cmp === 'later') {
      try { localStorage.setItem('cmpSnooze:' + s.id, String(s.compact.count)); } catch { /* 저장 못 함 — 이번만 숨긴다 */ }
      $('pCmp').hidden = true;
      store.touch('grid');
      return;
    }
    if (b.dataset.cmp === 'loss') {
      if (!confirm('압축으로 잊은 것 찾기 — 압축 구간마다 사람이 한 말을 뽑아 claude -p로 판정합니다. 내가 보낸 말 20개당 약 0.4달러 · 1.5분이 들고, 끝나면 알림이 갑니다. 진행할까요?')) return;
      b.disabled = true;
      const r = await fetch(`/api/sessions/${s.id}/losscheck`, { method: 'POST', headers: store.headers(true), body: '{}' });
      const j = await r.json().catch(() => ({}));
      store.state.lastInput = { sessionId: s.id, ts: Date.now(), ok: r.ok,
        msg: r.ok ? `압축으로 잊은 것 찾기를 시작했습니다(#${j.loss_check_id}). 진행과 결과는 [세션 정리] 탭 「옮기기 전 정리」에 나옵니다.` : `시작하지 못했습니다 — ${j.refused || j.detail || r.status}` };
      if (r.ok) setTab('sess');
      b.disabled = false;
      store.touch('panel');
      return;
    }
    if (b.dataset.cmp === 'handoff') startHandoff(s.id);
  });
  window.foremanCompactSnoozed = compactSnoozed;     // 픽셀 화면의 📦 표시도 같은 기준으로 숨긴다
  // 넘기고 새로 시작(11-08) — 띠 · 교장실 창 · [세션 정리] 탭이 모두 이것 하나를 부른다: 그 세션을 열고 [세션 정리] 탭에서 흐름을 시작
  function startHandoff(id) {
    if (onSelectSession) onSelectSession(id); else store.select(id);
    setOpen(true);
    setTab('sess');
    hand.setSession(id);
    hand.startFlow();
    store.touch('panel');
  }
  window.foremanHandoff = { start: startHandoff };
  window.foremanHandoffTip = FLOW_TIP;

  // 겹침 알림 띠(11-06, bridge/overlap.py) — 방금 넣은 요청이 다른 살아 있는 세션의 최근 일과 겹친다. 막지 않는다.
  // [나중에]는 이 겹침(시각으로 기억)만 숨긴다 — 이 브라우저에만
  function drawOverlap(s) {
    const o = s.overlap;
    let snoozed = false;
    try { snoozed = !!o && localStorage.getItem('ovlSnooze:' + s.id) === o.at; } catch { /* 읽지 못함 — 보인다 */ }
    if (!o || snoozed) { $('pOvl').hidden = true; return; }
    // 11-08 다른 프로젝트 — 같은 글이 다른 프로젝트 세션에 이미 들어갔다(잘못된 창에 붙였을 수 있다). 바로 일을 시작하므로 [작업 중단]도
    // 11-09 세 갈래 더: 같은 파일(두 세션이 실제로 고침 — 가장 확실) · 낱말 + 상대가 그 파일을 고침 · 낱말만(지시서에 나왔을 뿐일 수 있음)
    const files = o.files || [];
    // 겉은 파일 이름만(좁은 패널에서 경로가 띠를 다 먹었다), 전체 경로는 호버
    const fileList = files.slice(0, 3).map((f) => f.split('/').pop()).join(', ') + (o.files_n > 3 ? ` 외 ${o.files_n - 3}개` : '');
    const wordsTip = o.words && o.words.length ? `\n겹친 낱말 ${o.words.join(', ')}` : '';
    let soft = false;
    const html = files.length
      ? `<span class="bad" data-tip="${esc(`같은 파일 — 이 세션과 세션 ${o.with}이 최근 3시간 안에 같은 파일을 고쳤습니다. 합칠 때 부딪치거나 서로 고친 것을 덮을 수 있습니다. 일부러 나눈 것이면 그대로 두면 됩니다.\n${files.join('\n')}`)}">📝 같은 파일 — 세션 ${o.with}「${esc(o.with_title || '')}」도 ${esc(fileList)}를 고쳤습니다(마지막 ${esc(o.since_kst)}).</span>
      <button type="button" data-ovl="go" class="small" title="그 세션 보기 — 같은 파일을 고친 세션을 고릅니다.">세션 ${o.with} 보기</button>`
      : !o.cross && !(o.edited && o.edited.length)       // 근거(상대가 고친 파일)가 없으면 약한 띠 — 11-09 전 형식(edited 없음)도
      ? ((soft = true), `<span class="muted" data-tip="${esc(`겹칠 수도 — 세션 ${o.with}이 ${o.since_kst}부터 받은 요청과 드문 낱말이 겹칩니다. 그 세션이 고친 파일과는 겹치지 않습니다. 두 세션에 같은 지시서를 보냈다면 말에 나왔을 뿐입니다. 두 세션이 같은 파일을 고치면 「같은 파일」 알림이 갑니다.${wordsTip}`)}">🔁 겹칠 수도 — 세션 ${o.with}「${esc(o.with_title || '')}」과 요청 낱말이 겹칩니다. 말에 나왔을 뿐일 수 있습니다.</span>
      <button type="button" data-ovl="go" class="small ghost" title="그 세션 보기 — 낱말이 겹친 세션을 고릅니다.">세션 ${o.with} 보기</button>`)
      : !o.cross
      ? `<span class="warn" data-tip="${esc(`겹침 — 세션 ${o.with}이 ${o.since_kst}부터 비슷한 일을 하고, 요청에 나온 파일을 실제로 고쳤습니다. 이 세션도 같은 파일을 고치면 「같은 파일」 알림이 갑니다.${wordsTip}`)}">🔁 겹침 — 세션 ${o.with}「${esc(o.with_title || '')}」이 ${esc(o.since_kst)}부터 비슷한 일을 하고 ${esc((o.edited || []).join(', '))}를 실제로 고쳤습니다.</span>
      <button type="button" data-ovl="go" class="small" title="그 세션 보기 — 겹친 세션을 고릅니다.">세션 ${o.with} 보기</button>`
      : `<span class="bad">📋 다른 프로젝트 — 이 글은 ${esc(o.with_label || o.with_project || '')} 세션 ${o.with}「${esc(o.with_title || '')}」에 ${esc(o.since_kst)}에 들어간 글과 거의 같습니다. 잘못된 창에 붙여 넣었을 수 있습니다.</span>
      ${s.state === 'ACTIVE' ? '<button type="button" data-ovl="stop" class="small warn" title="이 세션 작업 중단 — 지금 하는 작업만 멈춥니다(Esc). 세션은 살아 있습니다.">이 세션 작업 중단</button>' : ''}
      <button type="button" data-ovl="go" class="small" title="그 세션 보기 — 같은 글을 받은 세션을 고릅니다.">세션 ${o.with} 보기</button>`;
    const later = `
      <button type="button" data-ovl="later" class="ghost small" title="나중에 — 이 띠를 숨깁니다. 일부러 그렇게 시킨 것이면 그대로 두면 됩니다.">나중에</button>`;
    put('pOvl', 'ovl', html + later);
    $('pOvl').className = `pcmp small${soft ? ' soft' : files.length ? ' late' : ''}`;
    $('pOvl').hidden = false;
  }
  $('pOvl').addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-ovl]');
    const s = store.state.sessions.get(store.state.selected);
    if (!b || !s || !s.overlap) return;
    if (b.dataset.ovl === 'stop') {
      b.disabled = true;
      const r = await fetch(`/api/sessions/${s.id}/action`, { method: 'POST', headers: store.headers(true), body: JSON.stringify({ action: 'interrupt' }) });
      const j = await r.json().catch(() => ({}));
      store.state.lastInput = { sessionId: s.id, ts: Date.now(), ok: r.ok, msg: r.ok ? '이 세션의 작업을 중단했습니다.' : `중단하지 못했습니다 — ${j.refused || j.detail || r.status}` };
      store.touch('panel');
      return;
    }
    if (b.dataset.ovl === 'later') {
      try { localStorage.setItem('ovlSnooze:' + s.id, s.overlap.at); } catch { /* 저장 못 함 — 이번만 숨긴다 */ }
      $('pOvl').hidden = true;
      return;
    }
    if (store.state.sessions.has(s.overlap.with)) store.select(s.overlap.with);
  });

  // 바꾸는 중 표시 — 응답 모델이 고른 것과 같아지면(또는 30분이 지나면) 지운다
  function pendModel(st, s) {
    const p = st.pendingModel.get(s.id);
    if (p && (sameModel(s.model, p.model) || Date.now() - p.ts > 30 * 60 * 1000)) { st.pendingModel.delete(s.id); return null; }
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
  // 입력 칸 높이(11-11 사용자) — 위쪽 띠를 끌어 바꾼다. 기억은 localStorage(막혀도 기본 높이로 뜬다).
  // 낮은 창에서 대화 칸이 사라지지 않게 대화 칸이 MIN_CONVO 아래로 줄지 않는 높이까지만(README 「대화 칸 30px」)
  const INPUT_H_KEY = 'foremanInputH', MIN_INPUT_H = 40, MIN_CONVO = 80;
  let inputHRestored = false;
  const savedH = () => { try { return localStorage.getItem(INPUT_H_KEY) || ''; } catch { return ''; } };
  // 패널 안쪽은 글씨 배율(zoom, uiscale.js)이 걸려 있다 — 높이는 배율 앞(CSS px)으로 다루고, 마우스 움직임(화면 px)은 배율로 나눈다
  const textH = () => $('pText').offsetHeight;
  const zoomF = () => { const e = $('pText'), r = e.getBoundingClientRect().height; return e.offsetHeight && r ? r / e.offsetHeight : 1; };
  function maxInputH() {
    const cv = $('pConvo'), vp = Math.round(window.innerHeight * 0.45 / zoomF());
    if (!cv || $('pForm').hidden) return vp;
    // 지금 대화 칸이 MIN_CONVO보다 작으면(원래 낮은 창) 지금 높이가 상한 — 더 키우지 못하고 줄이는 것만 된다
    return Math.max(MIN_INPUT_H, Math.min(vp, Math.floor(textH() + cv.clientHeight - MIN_CONVO)));
  }
  function setInputH(px, save) {
    const h = Math.round(Math.max(MIN_INPUT_H, Math.min(px, maxInputH())));
    $('pText').style.height = `${h}px`;
    if (save) { try { localStorage.setItem(INPUT_H_KEY, String(h)); } catch { /* 기억 못 해도 된다 */ } }
    return h;
  }
  function resetInputH() { $('pText').style.height = ''; try { localStorage.removeItem(INPUT_H_KEY); } catch { /* 위와 같다 */ } }
  function restoreInputH() {
    let v = null;
    try { v = Number(localStorage.getItem(INPUT_H_KEY)); } catch { /* 기본 높이 */ }
    if (v > 0 && !$('pForm').hidden) setInputH(v, false);
  }
  (() => {
    const g = $('pGrip');
    let y0 = 0, h0 = 0, max0 = 0, z0 = 1, tipText = '';
    g.addEventListener('pointerdown', (ev) => {
      if (ev.button) return;
      ev.preventDefault();
      y0 = ev.clientY; h0 = textH(); max0 = maxInputH(); z0 = zoomF(); g.setPointerCapture(ev.pointerId); g.classList.add('drag');
      // 끄는 동안 쪽지는 끈다 — preventDefault로 mousedown이 오지 않아 tip.js가 못 숨겼다. 놓으면 되돌려 다시 올리면 뜬다
      hideTip(); tipText = g.dataset.tip || tipText; g.removeAttribute('data-tip');
    });
    g.addEventListener('pointermove', (ev) => {
      if (!g.classList.contains('drag')) return;
      $('pText').style.height = `${Math.round(Math.max(MIN_INPUT_H, Math.min(h0 + (y0 - ev.clientY) / z0, Math.max(max0, h0))))}px`;   // 위로 끌면 커진다
    });
    // 안 바뀐 클릭은 기억하지 않는다(원래 낮은 창에서 클릭만으로 높이가 저장 · 줄어들지 않게)
    const end = () => { if (!g.classList.contains('drag')) return; g.classList.remove('drag'); g.dataset.tip = tipText; repinConvo(); if (textH() === h0) { if (!savedH()) $('pText').style.height = ''; } else setInputH(textH(), true); };
    g.addEventListener('pointerup', end); g.addEventListener('pointercancel', end);
    g.addEventListener('dblclick', resetInputH);
    g.addEventListener('keydown', (ev) => {
      if (ev.key !== 'ArrowUp' && ev.key !== 'ArrowDown') return;
      ev.preventDefault(); setInputH(textH() + (ev.key === 'ArrowUp' ? 24 : -24), true);
    });
    $('pText').addEventListener('mouseup', () => { if ($('pText').style.height && String(textH()) !== savedH()) setInputH(textH(), true); });   // 오른쪽 아래 모서리로 바꿔도 기억
    window.addEventListener('resize', () => { if ($('pText').style.height && !$('pForm').hidden) setInputH(textH(), false); });
  })();
  $('pText').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); $('pForm').requestSubmit(); }
    if (ev.key === 'Escape') { ev.stopPropagation(); $('pText').blur(); }   // 입력 중 Esc는 감독실로 가지 않고 칸만 빠져나온다
  });

  // ── 그리기 ──────────────────────────────────────────
  // 승인 · 질문 칸(11-10 다시 짬 — render.js apprPlace): 답하는 카드는 그 세션 패널에만, 다른 세션 것은 한 줄(보기만 · [세션 열기]),
  // 답한 것은 그 세션 패널에서 한 줄로 접힘. 같은 내용이면 다시 그리지 않는다 — 치는 중인 글 칸이 날아가지 않게
  let lastAppr = '', askOpen = '', askNow = '';
  $('pAskHint').addEventListener('click', () => { askOpen = askNow; drawAppr(store.state); $('pText').focus(); });
  function drawAppr(st) {
    const list = [...st.approvals.values()].sort((a, b) => a.id - b.id);
    const sid = target && target.kind === 'session' ? st.selected : null;
    const { mine, peek, folded } = apprPlace(list, sid);
    const pend = list.filter((a) => a.status === 'pending');
    // 질문(AskUserQuestion)은 승인이 아니다 — 머리말도 따로 센다(11-09)
    const cnt = (xs) => { const nq = xs.filter((a) => a.tool === 'AskUserQuestion').length, na = xs.length - nq;
      return [na ? `승인 대기 ${na}` : '', nq ? `질문 ${nq}` : ''].filter(Boolean).join(' · '); };
    // 이 세션의 답 카드가 맨 위(좁은 패널에서 카드 머리 · 질문이 먼저 보이게 — 카드가 ❓ · 세션을 적어 머리 줄은 두지 않는다),
    // 그 아래 답한 줄, 끝에 다른 세션 것 한 줄 요약(누르면 펼침). 답은 그 세션 패널에서(사용자: 보여 주는 것은 되지만 그 자리에서 답하면 안 된다)
    const html = mine.map((a) => approvalCard(a, st)).join('')
      + folded.map((a) => apprFoldLine(a, st)).join('')
      + (peek.length ? `<details class="appr-peeks"${keep('appr:peeks', false)}><summary class="small" data-tip="다른 세션 — 다른 세션이 기다리는 것입니다. 여기서는 보기만 하고, 답은 [세션 열기]로 그 세션 패널에서 합니다."><span class="warn">다른 세션 ${cnt(peek)}</span> <span class="muted">— 답은 그 세션 패널에서</span></summary>${peek.map((a) => apprPeekLine(a, st)).join('')}</details>` : '');
    if (html !== lastAppr) { lastAppr = html; $('pAppr').innerHTML = html; restoreNotes($('pAppr')); }
    $('pAppr').classList.toggle('has-mine', mine.length > 0);    // 이 세션이 답할 카드 — 좁은 패널에서도 칸을 지킨다(office.html)
    // 이 세션이 질문의 답을 기다리면 패널 입력 칸은 한 줄 안내로 접는다 — 카드에 글 칸이 있고, 좁은 패널에서 카드가 입력 칸 밑에 묻혔다(11-10).
    // 사람이 [입력 칸 펼치기]를 누르면 그 질문 동안은 펼친 채
    askNow = mine.filter((a) => a.tool === 'AskUserQuestion').map((a) => a.id).join(',');
    el.classList.toggle('asking', !!askNow && askNow !== askOpen);
    // 머리줄 숫자는 이 패널에서 답할 것만(11-10) — 전에는 모든 세션 수라 FOREMAN 세션에 런슈즈 승인까지 셌다. 접은 띠 배지는 전체
    $('pCount').innerHTML = mine.length ? `<span class="warn" data-tip="이 세션이 기다리는 것 — 승인 · 질문 ${mine.length}개입니다.">❗${mine.length}</span>` : '';
    $('pStripBadge').innerHTML = pend.length ? `<span class="oside-badge">${pend.length}</span>` : '';
    // 새 승인 요청이 오면 접혀 있어도 편다 — 승인은 기다리는 사람이 있다
    let fresh = false;
    for (const a of pend) if (!knownPending.has(a.id)) { knownPending.add(a.id); fresh = true; }
    if (fresh && !firstAppr && !open) setOpen(true, false);
    firstAppr = false;
  }

  function sessionMode(on) {
    $('pSel').hidden = on; $('pTabs').hidden = !on; $('pMeta').hidden = !on; $('pForm').hidden = !on;
    if (on && !inputHRestored) { inputHRestored = true; requestAnimationFrame(restoreInputH); }   // 처음 보일 때 한 번 — 기억한 높이로
    if (!on) $('pCmp').hidden = $('pOvl').hidden = $('pSw').hidden = true;
    if (on) setTab(tab);
    else { $('pTabConvo').hidden = $('pTabAct').hidden = $('pTabSess').hidden = true; el.classList.remove('tab-convo'); }
  }
  const put = (id, key, html) => { if (last[key] !== html) { last[key] = html; $(id).innerHTML = html; return true; } return false; };

  function drawSession(st) {
    const s = st.selected != null ? st.sessions.get(st.selected) : null;
    if (!s) { hand.setSession(null); sessionMode(false); drawHint(st); return; }
    const switched = lastSel !== s.id;
    if (switched) { sessionMode(true); last.convo = last.feed = last.meta = last.info = ''; }   // CC 화면 창은 띄운 세션 그대로
    hand.setSession(s.id);
    // 머리줄 = 첫 줄 [역할] 세션 번호 + 버튼, 둘째 줄 제목(11-09 사용자 — 역할 + 지금 하는 일). 한 줄에 두면 좁은 패널에서 제목이 한 글자로 줄었다
    if (!pickingRole) drawRole({ kind: 'session' }, s);
    $('pSid').textContent = `세션 ${s.id}`;
    $('pSid').dataset.tip = `세션 ${s.id} — FOREMAN 세션 번호입니다. 기록 · 세션 사이 말에 이 번호로 나옵니다.${sessionIds(s) ? '\n' + sessionIds(s) : ''}`;
    $('pSid').hidden = false;
    $('pTitle').parentElement.classList.add('sess');
    if (!editingTitle) {
      $('pTitle').textContent = sessionName(s) + (s.custom_title ? '' : ' ');
      $('pTitle').dataset.tip = `제목 — 이 세션이 지금 하는 일입니다. 눌러서 고칩니다. 역할은 바뀌지 않습니다.${s.custom_title ? ` 자동 제목은 "${s.title || s.cc_name || s.short}"입니다.` : ''}\n${sessionName(s)}`;
      $('pTitle').classList.add('editable');
    }
    // 제목 아래 한 줄 — 세션 정보 · 토큰은 여기 작게, 자세한 것은 [세션 정리] 탭
    const t = s.tokens || {}, stuck = stuckTurn(s);
    const now = s.activity && s.state === 'ACTIVE' ? doingHtml(s.activity) : (s.state === 'ACTIVE' ? '생각 중' : '');   // Bash는 하는 일, 명령은 호버(11-14)
    // "쌓인 대화 N%"는 상태 바로 뒤 — 머리줄은 한 줄이라 좁은 패널에서 뒤쪽이 말줄임으로 잘린다(11-09 1366 사진)
    // 답 기다림 끄기(11-11, 받은 할 일 #13) — 판정이 묻지 않는 끝맺음을 잡았을 때 사람이 끈다. 다음 응답이 오면 다시 판정
    const asksOff = ['답 기다림', '사용자 답 기다림'].includes(humanNeed(s)?.label)
      ? `<button type="button" class="small" data-asksoff="${s.id}" title="답 안 해도 됨 — 이 응답은 답을 기다리는 것이 아니라고 표시합니다. 다음 응답이 오면 다시 판정합니다.">답 안 해도 됨</button> ` : '';
    // 끝난 세션(11-11, UI 불만 (나)) — 옛 보고가 새 일처럼 읽히지 않게 어떻게 · 언제 끝났는지를 맨 앞에
    const ended = s.state === 'DORMANT' && s.ended
      ? `<span class="muted" title="끝난 세션 — 이 세션은 ${esc(s.ended.at ? ago(s.ended.at) : '')} ${esc(s.ended.label)}. 아래 대화는 지난 일입니다.">끝난 세션 · ${esc(s.ended.label)}${s.ended.at ? ` · ${esc(ago(s.ended.at))}` : ''}</span> · ` : '';
    put('pMeta', 'meta', `${ended}${stateBadge(s)} ${asksOff}${stallChip(s)}${ctxChip(s)}<span class="muted"${worktreeTip(s) ? ` data-tip="${esc(worktreeTip(s))}"` : ''}>${esc(sessionSub(s))}</span> ${modelChip(s, pendModel(st, s), !!s.injectable)}${now ? ` · <b>${now}</b>` : ''}${s.subagents_running ? ` · 서브 ${s.subagents_running}` : ''}
      · <span class="muted" title="오늘 출력 토큰 — 이 세션이 오늘 쓴 글의 양입니다.">오늘 출력 토큰 ${tok(t.today_output)}</span>${stuck ? ' · <span class="warn" title="끝났는지 모름 — 작업이 끝났다는 신호가 오지 않았습니다. 대화창을 확인하거나 [작업 중단]을 누릅니다.">⚠ 끝났는지 모름</span>' : ''}`);
    // 보고 옴(11-11) — 이 세션 패널에 대화가 떠 있으면 읽은 것으로 본다(창이 가려져 있으면 아직). 캐릭터 위 「보고 옴」이 사라진다
    if (s.report && !document.hidden && reportSent !== s.report.event_id) {
      reportSent = s.report.event_id;
      store.reportRead(s.id, s.report.event_id).catch(() => { reportSent = null; });
    }
    // 사용자에게 보고함(11-13) — 관리자가 사람에게 올린 보고. 패널을 열면 읽은 것(같은 방식)
    const er = s.escalate && s.escalate.report;
    if (er && !document.hidden && escSent !== er.id) {
      escSent = er.id;
      store.escalateRead(s.id, er.id).catch(() => { escSent = null; });
    }
    drawSwitch(s);                   // 먼저 — 떠 있으면 쌓인 대화 띠는 숨긴다(같은 버튼, 까닭은 이쪽이 분명)
    drawCompact(s);
    drawOverlap(s);
    // 대화 — 바뀔 때만
    const c = $('pConvo');
    const follow = switched || nearBottom(c);
    const html = convoHtml(st.convo.get(s.id)) || '<p class="small muted">불러오는 중…</p>';
    if (put('pConvo', 'convo', html)) {
      if (follow) c.scrollTop = c.scrollHeight;
      else if (tab === 'convo') $('pNew').hidden = false;
      noteConvo();                   // 새 글이 아래에 붙어 아래쪽 거리가 바뀌었다(스크롤 이벤트는 오지 않는다)
    }
    $('pTabs').querySelector('[data-n="act"]').textContent = s.feed.length ? ` ${s.feed.length}` : '';
    if (tab === 'act' || switched) put('pFeed', 'feed', feedHtml(s));
    if (tab === 'sess' || switched) {
      // 11-06 정리 — 위에는 어디서 무엇을 하는지 한 줄, 표(프로세스 · 모델 · 토큰)는 아래 접는 칸으로
      // 11-14 사용자 — 「프로젝트 · 서버 경로」 줄은 뺐다(사람이 서버 경로를 볼 일이 없다). 작업 중 줄만 남는다
      put('pInfo', 'info', `${s.open_turn ? (() => {           // 11-09 "턴 나 · 10분 전 시작" → "작업 중 · 10분째"(무엇으로 시작했는지는 호버)
          const o = s.open_turn, el = ago(o.started_at).replace(/ 전$/, '째'), by = o.origin === 'human' ? '내 입력' : (ORIGIN_LABEL[o.origin] || '');
          const tip = stuck ? `끝났는지 모름 — ${by}으로 시작한 작업이 끝났다는 신호가 오지 않았습니다. 대화창을 확인하거나 [작업 중단]을 누릅니다.`
            : `작업 중 — ${by}으로 시작한 작업이 ${el} 돌고 있습니다.`;
          return `<div class="small${stuck ? ' warn' : ''}" title="${esc(tip)}">${stuck ? '⚠ 끝났는지 모름' : '▶ 작업 중'} · ${esc(el)}</div>`;
        })() : ''}`);
      put('pKv', 'kv', sessionKv(s, pendModel(st, s)));
      const t_ = s.tokens || {};
      $('pKvHead').textContent = `${s.model_label || ''}${s.model_label ? ' · ' : ''}오늘 출력 토큰 ${tok(t_.today_output)}`;
    }
    const blocked = !s.injectable;
    $('pText').disabled = blocked; $('pSend').disabled = blocked;
    // 입력 칸 아래 — 가운데는 세션 상태(짧게), 아래 줄은 보낸 결과(성공은 한 마디, 잘못됐을 때만 자세히)(11-05)
    const why_ = blocked ? why(s) : '';
    $('pWhy').textContent = blocked ? '보낼 수 없음' : (s.state === 'ACTIVE' ? '작업 중 — 끝나면 전달' : '');
    $('pWhy').className = `pwhy small${blocked ? ' bad' : s.state === 'ACTIVE' ? ' busy' : ''}`;
    if (blocked) $('pWhy').dataset.tip = `보낼 수 없음 — ${why_}`; else if (s.state === 'ACTIVE') $('pWhy').dataset.tip = '작업 중 — 지금 보내면 하던 일이 끝난 뒤 이어서 전달됩니다.'; else delete $('pWhy').dataset.tip;
    const li = st.lastInput && st.lastInput.sessionId === s.id && Date.now() - st.lastInput.ts < (st.lastInput.ok ? 8000 : 60000) ? st.lastInput : null;
    $('pResult').innerHTML = blocked ? `<span class="muted">${esc(why_)}</span>` : li ? `<span class="${li.ok ? 'ok' : 'bad'}">${esc(li.msg)}</span>` : '';
    if (switched) { $('pText').value = ''; lastSel = s.id; $('pNew').hidden = true; }
  }

  function sessionList(st, names) {
    const rows = [];
    const btn = (s) => `
        <button class="plist" data-sid="${s.id}">${stateBadge(s)}
          ${roleBadge(s)}<span class="muted small" title="세션 ${s.id} — FOREMAN 세션 번호입니다.">${s.id}</span>
          <b>${esc(oneLine(sessionName(s), 40))}</b>${s.activity && s.state === 'ACTIVE' ? ` <span class="muted">${esc(s.activity.tool)}</span>` : ''}${s.state === 'DORMANT' ? ` <span class="muted small">${s.ended && s.ended.kind !== 'gone' ? `${esc(s.ended.label.split(' — ')[0])} · ` : ''}${ago((s.ended && s.ended.at) || s.last_ts)}</span>` : ''}</button>`;
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

  // 머리줄 배지 — 대상 캐릭터의 역할(panelRole). 세션 없는 캐릭터는 자기 역할, 누를 수 있는 것은 세션 배지만
  function drawRole(t, s) {
    const r = panelRole(t, s), b = $('pRole');
    b.hidden = !r;
    if (!r) return;
    b.textContent = r.label;
    b.className = `rolebadge role-${r.role}${r.editable ? '' : ' fixed'}`;
    b.dataset.tip = r.tip;
  }

  function drawHint(st) {
    lastSel = undefined;
    $('pSid').hidden = true;
    drawRole(target, null);
    $('pTitle').parentElement.classList.remove('sess');
    $('pTitle').classList.remove('editable'); delete $('pTitle').dataset.tip;
    $('pClear').hidden = !target;
    if (target && target.kind === 'infra') {
      $('pTitle').textContent = target.name;
      $('pSel').innerHTML = `<div class="small muted">${esc(projectLabel(st, target.room))} · 지금 ${esc(target.status || '기록 없음')}</div>
        ${pipeBlock(st.pipeline.get(target.room)) || '<p class="small muted">파이프라인 기록 없음</p>'}`;
      return;
    }
    if (target && target.kind === 'scribe') {
      $('pTitle').textContent = `서기 · ${projectLabel(st, target.room)}`;
      const typing = document.activeElement && document.activeElement.id === 'scAskText';     // 다시 그려도 쓰던 칸을 놓치지 않는다
      $('pSel').innerHTML = scribe.html(target.room, projectLabel(st, target.room), target.pick || null);
      if (typing) { const q = $('pSel').querySelector('#scAskText'); if (q && !q.disabled) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); } }
      if (target.pick) { const r = $('pSel').querySelector('.sc-pick'); if (r) r.scrollIntoView({ block: 'nearest' }); }
      return;
    }
    if (target && target.kind === 'coder') {
      $('pTitle').textContent = `코더 · ${projectLabel(st, target.room)}`;
      $('pSel').innerHTML = coder.html(target.room, projectLabel(st, target.room));
      return;
    }
    if (target && target.kind === 'foreman') {
      const nm = target.name || (window.office && window.office.foremanName) || '감독';
      $('pTitle').textContent = target.room ? `${nm} · ${projectLabel(st, target.room)} 건` : `${nm}(감독실)`;
      $('pSel').innerHTML = fmp.html(target.room, nm, (p) => projectLabel(st, p));
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
    const key = t ? `${t.kind}:${t.kind === 'session' ? store.state.selected : (t.room || '') + ':' + (t.infra || '') + ':' + (t.status || '') + ':' + (t.pick || '')}` : '';
    if (key === targetKey) return;
    targetKey = key; target = t;
    ccw.sync(t && t.kind === 'session' ? store.state.selected : null);   // 띄운 세션과 다르면 창 머리줄에 「N번으로」
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
      drawAppr(st);                // 고른 세션이 바뀌면 카드 자리도(같은 내용이면 다시 그리지 않는다)
    }
  });

  // 11-11 합치기 막대 — 합치기 카드는 「세션 정리」 탭 안에만 있다. 이번만 그 탭으로 열고 다음에 열 탭(기억)은 바꾸지 않는다
  function showTab(k) { setTab(k, false); store.touch('panel'); }

  return { show, showTab, setOpen, get open() { return open; }, el };
}
