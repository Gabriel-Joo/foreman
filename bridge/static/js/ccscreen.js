// 「CC 화면」 탭(11-14) — 세션 CC 창을 그대로 본다(권한 · 계획 승인 · 안내 · 고르기 창까지). 키도 보낼 수 있다(Esc · 숫자 · Enter).
// 전에는 이런 창이 떠 있으면 FOREMAN에서 볼 수 없어 사용자가 VNC로 들어가 Esc로 닫았다.
// 셸과 같은 틀(ttyd + tmux 그룹 세션)을 따로 하나 더 띄운 것(/ccscreen, bridge/terminal.py). 브라우저는 세션 번호만 보낸다 —
// 붙을 tmux 창은 브리지가 DB · 살아 있는 프로세스로 정한다. 탭을 열 때만 iframe을 붙이고, 다른 탭 · 다른 세션 · 패널 접기에 끊는다.
// 끊기면 tmux 그룹 세션만 사라지고 CC 창은 그대로다. 창 크기는 바꾸지 않는다(CC 창 제 크기 — 80×24면 작게 보인다).
// 열려 있는 동안 5초마다 다시 물어 세션이 끝났거나 CC 화면 서버가 죽었으면 까닭을 띄운다(조용히 빈 화면이 되지 않게).

import { termTabId } from './terminal.js';
import { applyTermFont } from './uiscale.js';

const CHECK_MS = 5000;

export function createCcScreen(store, { frame, msg, info, reload }) {
  const TAB = 'c' + termTabId().slice(1);     // 셸 탭 id와 같은 모양(브리지 TAB_RE)
  let sid = null, attached = false, seq = 0, timer = null;

  const say = (text, cls = 'warn') => { msg.textContent = text || ''; msg.className = `pcc-msg small ${text ? cls : ''}`; };
  function detach() {
    if (attached) { frame.src = 'about:blank'; attached = false; }      // 끊으면 브리지가 「닫음」을 남긴다
    frame.hidden = true;
  }
  async function check(first) {
    const my = seq, id = sid;
    if (id == null) return;
    let j;
    try {
      if (first) await store.terminalSession();               // 쿠키(/ccscreen) — 만료 · 브리지 재시작에 대비해 열 때마다
      j = await store.ccState(id);
    } catch (e) {
      if (my !== seq) return;
      detach(); info.textContent = '';
      say(`CC 화면을 확인하지 못했습니다 — ${e.message || e}`, 'bad');
      return;
    }
    if (my !== seq) return;                                   // 그 사이 다른 세션 · 탭으로 갔다
    if (!j.ok) {
      detach(); info.textContent = '';
      say(j.reason || 'CC 화면을 열 수 없습니다', j.running === false ? 'bad' : 'muted');
      return;
    }
    say('');
    info.textContent = `tmux ${j.tmux_session} · CC 창 ${j.size}`;
    info.dataset.tip = `CC 화면 — 이 세션의 CC 창을 그대로 봅니다. 창 크기는 바꾸지 않습니다(CC 창 ${j.size}).\n여기서 친 키는 CC에 바로 갑니다. 브리지가 글을 넣을 때 입력 칸에 친 글이 있으면 넣지 않고 알립니다.`;
    if (!attached) {
      frame.hidden = false;
      frame.src = `/ccscreen/?arg=${encodeURIComponent(id)}&arg=${TAB}`;
      attached = true;
    }
  }
  function open(id) {
    if (sid === id) return;              // 이미 이 세션을 보고 있다(못 붙었으면 5초 확인이 다시 붙인다)
    close();
    sid = id;
    say('CC 화면을 확인하는 중입니다…', 'muted');
    check(true);
    timer = setInterval(() => check(false), CHECK_MS);
  }
  function close() {
    seq++;
    if (timer) { clearInterval(timer); timer = null; }
    detach();
    sid = null;
  }
  // [다시 붙기] — ttyd 화면이 끊김 표시로 남았을 때(브리지를 다시 띄움 등)
  reload.addEventListener('click', () => { const id = sid; if (id == null) return; close(); open(id); });
  function fitFont(tries = 20) { if (!applyTermFont(frame) && tries > 0) setTimeout(() => fitFont(tries - 1), 250); }
  frame.addEventListener('load', () => { if (attached) fitFont(); });
  window.addEventListener('foreman-uiscale', () => { if (attached) fitFont(0); });
  return { open, close, get sid() { return sid; } };
}
