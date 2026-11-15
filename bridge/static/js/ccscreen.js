// 「CC 화면」 띄우는 창(11-14 — 368의 탭을 사용자 지시로 바꿈). 세션 CC 창을 그대로 본다(권한 · 계획 승인 · 안내 · 고르기 창까지).
// 키도 보낼 수 있다(화살표 · Esc · 숫자 · Enter). 전에는 이런 창이 떠 있으면 FOREMAN에서 볼 수 없어 사용자가 VNC로 들어가 Esc로 닫았다.
// - 패널 탭 줄 「세션 정리」 오른쪽 [CC 화면] 단추가 연다. 창은 패널 위에 떠 있고(모달 아님) 대화 탭을 보면서 함께 둘 수 있다
// - 머리줄을 끌어 옮기고, 오른쪽 아래 모서리를 끌어 크기를 바꾼다. 크기는 놓을 때 한 번만 적용한다(끄는 동안은 테두리만) —
//   CC 창(tmux)이 이 창 크기를 따르므로 끄는 동안 계속 바뀌지 않게. 정한 크기 · 자리는 이 브라우저에 기억해 다음에 같은 크기로 연다
//   (사용자 까닭: 크기를 한 번 정해 두면 CC 창이 흔들리는 것이 열 때 한 번뿐). 옮기기만으로는 크기가 바뀌지 않는다
// - 띄운 채 다른 세션을 골라도 띄운 세션 그대로(사용자 결정 11-14 — 따라 바뀌면 헷갈린다). 머리줄에 세션 번호 · 제목.
//   [CC 화면] 단추를 다른 세션에서 누르면 그 세션으로 바꾼다(창은 하나)
// - 닫으면(✕) iframe을 끊는다 → 보기 스크립트가 CC 창을 80×24로 되돌린다(deploy/shell/foreman-cc-view, 브리지 CC_REST_SIZE)
// - 붙을 수 없으면 창 안에 까닭(GET /api/terminal/cc/{sid}의 reason)과 [다시 붙기]. 열려 있는 동안 5초마다 다시 묻는다
// 셸과 같은 틀(ttyd + tmux 그룹 세션)을 따로 하나 더 띄운 것(/ccscreen, bridge/terminal.py). 브라우저는 세션 번호만 보낸다.

import { termTabId } from './terminal.js';
import { applyTermFont } from './uiscale.js';
import { sessionName } from './render.js';
import { hideTip } from './tip.js';

const CHECK_MS = 5000;
const KEY_GEO = 'foreman.ccwin.geo';          // {x, y, w, h} px — 이 브라우저만(서버에 남기지 않음)
const MIN_W = 360, MIN_H = 220, DEF = { w: 760, h: 480 };
const ls = { get() { try { return JSON.parse(localStorage.getItem(KEY_GEO) || 'null'); } catch { return null; } },
             set(v) { try { localStorage.setItem(KEY_GEO, JSON.stringify(v)); } catch { /* 저장 못 해도 이 창에서는 된다 */ } } };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export function createCcWindow(store) {
  const TAB = 'c' + termTabId().slice(1);     // 셸 탭 id와 같은 모양(브리지 TAB_RE)
  const box = document.createElement('section');
  box.className = 'ccwin';
  box.hidden = true;
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', '세션 화면');
  const GRIP_TIP = '크기 — 끌어 바꿉니다. 놓을 때 Claude Code 창도 이 크기로 맞추고, 다음에 열 때 같은 크기로 엽니다.';
  box.innerHTML = `
    <header class="ccwin-head" data-tip="세션 화면 — 머리줄을 끌어 옮깁니다. 크기는 네 모서리를 끌어 바꿉니다.">
      <b class="ccwin-title"></b><span class="ccwin-info small muted"></span>
      <button type="button" class="ghost small ccwin-sync" hidden></button>
      <button type="button" class="ghost small ccwin-reload" data-tip="다시 붙기 — 세션 화면에 다시 붙습니다. 끊김 표시가 남았을 때 누릅니다.">다시 붙기</button>
      <button type="button" class="ghost small ccwin-x" aria-label="닫기" data-tip="닫기 — 세션 화면을 닫습니다. Claude Code 창은 80×24로 돌아갑니다.">✕</button>
    </header>
    <div class="ccwin-msg small"></div>
    <div class="ccwin-body"><iframe aria-label="세션 화면" hidden></iframe></div>
    ${['nw', 'ne', 'sw', 'se'].map((c) => `<div class="ccwin-grip" data-c="${c}" data-tip="${GRIP_TIP}"></div>`).join('')}`;
  document.body.appendChild(box);
  const ghost = document.createElement('div');
  ghost.className = 'ccwin-ghost';
  ghost.hidden = true;
  document.body.appendChild(ghost);
  const q = (c) => box.querySelector(c);
  const frame = q('iframe'), msg = q('.ccwin-msg'), info = q('.ccwin-info'), title = q('.ccwin-title');
  let sid = null, attached = false, seq = 0, timer = null;

  // ── 자리 · 크기 ─────────────────────────────────────
  let geo = (() => {
    const g = ls.get();
    const ok = g && [g.x, g.y, g.w, g.h].every(Number.isFinite);
    return ok ? g : { ...DEF, x: Math.max(8, window.innerWidth - DEF.w - 80), y: 80 };
  })();
  function place(save) {
    const vw = window.innerWidth, vh = window.innerHeight;
    // 화면보다 크지 않게(모서리를 늘 잡을 수 있게). 브라우저 창을 줄여 넘칠 때만 줄고, 그때는 기억하지 않는다(place(false))
    geo.w = Math.max(MIN_W, Math.round(Math.min(geo.w, vw - 16))); geo.h = Math.max(MIN_H, Math.round(Math.min(geo.h, vh - 16)));
    geo.x = Math.round(Math.min(Math.max(geo.x, 8 - geo.w + 120), vw - 120));   // 머리줄 일부는 늘 화면 안에(다시 잡을 수 있게)
    geo.y = Math.round(Math.min(Math.max(geo.y, 0), vh - 40));
    Object.assign(box.style, { left: geo.x + 'px', top: geo.y + 'px', width: geo.w + 'px', height: geo.h + 'px' });
    if (save) ls.set(geo);
  }
  function drag(ev, onMove, onUp) {          // 포인터를 잡아 iframe이 움직임을 가로채지 않게
    const t = ev.currentTarget;
    hideTip();       // 움직이기 시작하면 호버를 끈다 — preventDefault가 mousedown을 막아 tip.js의 끄는 길이 안 불린다
    t.setPointerCapture(ev.pointerId);
    const x0 = ev.clientX, y0 = ev.clientY;
    const mv = (e) => onMove(e.clientX - x0, e.clientY - y0);
    const up = (e) => { t.removeEventListener('pointermove', mv); t.removeEventListener('pointerup', up); t.removeEventListener('pointercancel', up);
                        onUp(e.clientX - x0, e.clientY - y0); };
    t.addEventListener('pointermove', mv); t.addEventListener('pointerup', up); t.addEventListener('pointercancel', up);
    ev.preventDefault();
  }
  q('.ccwin-head').addEventListener('pointerdown', (ev) => {
    if (ev.button !== 0 || ev.target.closest('button')) return;
    const { x, y } = geo;
    drag(ev, (dx, dy) => { geo.x = x + dx; geo.y = y + dy; place(false); }, () => place(true));
  });
  // 네 모서리 모두(11-14 사용자) — data-c: nw · ne · sw · se. 서(w) · 북(n) 모서리는 반대쪽 모서리를 붙들고 크기와 자리가 함께 바뀐다
  box.querySelectorAll('.ccwin-grip').forEach((grip) => grip.addEventListener('pointerdown', (ev) => {
    if (ev.button !== 0) return;
    const c = grip.dataset.c, west = c.includes('w'), north = c.includes('n');
    const { x, y, w, h } = geo;
    const vw = window.innerWidth, vh = window.innerHeight;
    const g = (dx, dy) => {                    // 모서리가 화면 밖으로 가지 않게, 가장 작게 MIN_W × MIN_H
      const nw = Math.max(MIN_W, west ? Math.min(w - dx, x + w - 8) : Math.min(w + dx, vw - x - 8));
      const nh = Math.max(MIN_H, north ? Math.min(h - dy, y + h) : Math.min(h + dy, vh - y - 8));
      return { w: nw, h: nh, x: west ? x + w - nw : x, y: north ? y + h - nh : y };
    };
    const show = (s) => Object.assign(ghost.style, { left: s.x + 'px', top: s.y + 'px', width: s.w + 'px', height: s.h + 'px' });
    show({ x, y, w, h });
    ghost.hidden = false;
    drag(ev, (dx, dy) => show(g(dx, dy)),
         (dx, dy) => { ghost.hidden = true; Object.assign(geo, g(dx, dy)); place(true); sizeSoon(); });   // 놓을 때 한 번 → Claude Code 창도 한 번
  }));
  window.addEventListener('resize', () => { if (!box.hidden) place(false); });

  // ── 붙기 ───────────────────────────────────────────
  const say = (text, cls = 'warn') => { msg.textContent = text || ''; msg.className = `ccwin-msg small ${text ? cls : ''}`; };
  function drawTitle() {
    const s = sid != null && store.state.sessions ? store.state.sessions.get(sid) : null;
    const name = s ? sessionName(s) : '';
    title.innerHTML = `세션 ${esc(sid ?? '')}${name ? ` <span class="ccwin-name">${esc(name)}</span>` : ''}`;
    title.dataset.tip = `세션 ${sid}${name ? ` — ${name}` : ''}\n띄운 세션입니다. 패널에서 다른 세션을 골라도 바뀌지 않습니다.`;
  }
  function detach() {
    if (attached) { frame.src = 'about:blank'; attached = false; }      // 끊으면 브리지가 「닫음」을 남기고 CC 창이 80×24로
    frame.hidden = true;
  }
  // 머리줄 「Claude Code 창 WxH」 — 서버 확인(5초마다)을 기다리지 않게 iframe 안 xterm의 열 · 줄 수를 바로 읽는다(11-14 사용자 — 숫자가 5초 늦었다).
  // 그룹 세션 상태줄을 꺼 두어 손님 크기 = Claude Code 창 크기이고, xterm 열 · 줄 = 손님 크기라 같은 값이다(서버 값과 대조해 같음을 봤다).
  // 5초 확인은 그대로(죽음 · 까닭 확인, 그리고 xterm 값이 서버 값과 어긋나면 서버 값으로 고친다)
  function showSize(s) { info.textContent = s ? `Claude Code 창 ${String(s).replace('x', '×')}` : ''; }
  let hooked = null;                                  // 크기 변화를 듣고 있는 xterm — 같은 것에 두 번 걸지 않는다
  function readTerm() {
    try { const t = frame.contentWindow && frame.contentWindow.term; return t && Number.isFinite(t.cols) ? t : null; } catch { return null; }
  }
  function readSize() { const t = readTerm(); if (t) showSize(`${t.cols}x${t.rows}`); return !!t; }
  function hookTerm(tries = 20) {
    const t = readTerm();
    if (!t) { if (tries > 0 && attached) setTimeout(() => hookTerm(tries - 1), 100); return; }
    readSize();
    if (hooked !== t && typeof t.onResize === 'function') {
      hooked = t;
      t.onResize(() => { if (attached && hooked === t) readSize(); });   // 모서리를 놓은 뒤 · 글씨 맞춤 · 보기 스크립트가 크기를 맞출 때마다
    }
  }
  async function check(first) {
    const my = seq, id = sid;
    if (id == null) return;
    drawTitle();
    let j;
    try {
      if (first) await store.terminalSession();               // 쿠키(/ccscreen) — 만료 · 브리지 재시작에 대비해 열 때마다
      j = await store.ccState(id);
    } catch (e) {
      if (my !== seq) return;
      detach(); info.textContent = '';
      say(`세션 화면을 확인하지 못했습니다: ${e.message || e}`, 'bad');
      return;
    }
    if (my !== seq) return;                                   // 그 사이 닫았거나 다른 세션으로 바꿨다
    if (!j.ok) {
      detach(); info.textContent = '';
      say(j.reason || '세션 화면을 열 수 없습니다', j.running === false ? 'bad' : 'muted');
      return;
    }
    say('');
    // 붙기 전 크기는 아직 80×24(맞추기 전) — 보이면 5초쯤 그 숫자로 남아 보인다. 붙기 전에는 비워 두고 붙은 뒤 xterm 크기가 채운다
    if (attached || !info.textContent) showSize(attached ? j.size : null);
    info.dataset.tip = `Claude Code 창 크기 — 이 창(세션 화면) 크기에 맞춥니다. 닫으면 80×24로 돌아갑니다.\n여기서 친 키는 CC에 바로 갑니다. 브리지가 글을 넣을 때 입력 칸에 친 글이 있으면 넣지 않고 알립니다.`;
    if (!attached) {
      frame.hidden = false;
      frame.src = `/ccscreen/?arg=${encodeURIComponent(id)}&arg=${TAB}`;
      attached = true;
    }
  }
  // 패널에서 고른 세션이 띄운 세션과 다르면 머리줄에 「N번으로」 단추 — 띄운 창이 패널 탭 줄의 [세션 화면] 단추를 덮어도 바꿀 수 있게
  // (11-14 사용자가 다른 세션 패널에서 단추를 눌러도 안 바뀐다고 했다 — 단추가 창에 가려 클릭이 창 안으로 갔다)
  const syncBtn = q('.ccwin-sync');
  let picked = null;
  function drawSync() {
    const show = !box.hidden && picked != null && picked !== sid;
    syncBtn.hidden = !show;
    if (!show) return;
    syncBtn.textContent = `세션 ${picked}로`;
    syncBtn.dataset.tip = `세션 ${picked}로 — 패널에서 고른 세션 ${picked}의 세션 화면으로 바꿉니다. 패널의 [세션 화면] 단추가 이 창에 가려져도 누를 수 있습니다.`;
  }
  syncBtn.addEventListener('click', () => { if (picked != null) open(picked); });
  function sync(id) { picked = id ?? null; drawSync(); }
  function open(id) {
    place(false);
    box.hidden = false;
    picked = id;
    if (sid === id) { drawSync(); return; }   // 이미 이 세션을 보고 있다(못 붙었으면 5초 확인이 다시 붙인다)
    stop();
    sid = id;
    say('세션 화면을 확인하는 중입니다…', 'muted');
    drawSync();
    check(true);
    timer = setInterval(() => check(false), CHECK_MS);
  }
  function stop() {
    seq++;
    if (timer) { clearInterval(timer); timer = null; }
    detach();
    sid = null;
    hooked = null; info.textContent = ''; clearTimeout(confirmT);
  }
  function close() { stop(); box.hidden = true; ghost.hidden = true; drawSync(); }
  q('.ccwin-x').addEventListener('click', close);
  // [다시 붙기] — ttyd 화면이 끊김 표시로 남았을 때(브리지를 다시 띄움 등)
  q('.ccwin-reload').addEventListener('click', () => { const id = sid; if (id == null) return; stop(); open(id); });
  function fitFont(tries = 20) { if (!applyTermFont(frame) && tries > 0) setTimeout(() => fitFont(tries - 1), 250); }
  // 붙은 뒤 · 모서리를 놓은 뒤: xterm 크기를 바로 읽고, 보기 스크립트가 크기를 맞출 틈(~1초) 뒤 서버 값으로 한 번 확인한다
  let confirmT = null;
  function sizeSoon() {
    if (!attached) return;
    readSize();
    clearTimeout(confirmT);
    confirmT = setTimeout(() => { if (attached) check(false); }, 1200);
  }
  frame.addEventListener('load', () => { if (attached) { hooked = null; hookTerm(); sizeSoon(); fitFont(); } });
  window.addEventListener('foreman-uiscale', () => { if (attached) fitFont(0); });
  return { open, close, sync, get sid() { return sid; } };
}
