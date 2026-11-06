// 터미널 패널(7단계) — 대시보드 아래 접이식. ttyd 화면(xterm.js)을 iframe으로 그대로 띄운다(파싱하지 않는다).
// CC가 "이 명령을 실행해 주세요"라고 하면 브리지가 셸 입력 줄에 미리 채우고 terminal_request를 보낸다 → 패널을 올린다.
// 사람이 Enter를 치고 암호를 넣는다. 결과는 브리지가 부탁한 세션에 돌려준다(terminal_result).

import { keep } from './render.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const PROJ = { runshoes: '런슈즈', 'petmint-rag-chatbot': '펫퍼민트', foreman: '포먼' };
const BAR_H = 36;

export function createTerminal(store) {
  const el = document.createElement('section');
  el.className = 'term';
  el.innerHTML = `
    <div class="term-bar">
      <button id="termToggle" class="ghost" aria-expanded="false">▲ 터미널</button>
      <span id="termBadge"></span>
      <span id="termLast" class="small muted term-last"></span>
      <span class="right small muted term-note">사람이 직접 치는 셸 · 승인 정책 없음 · 친 명령은 마스킹해서 기록</span>
    </div>
    <div id="termReqs" class="term-reqs"></div>
    <div class="term-body"><iframe id="termFrame" title="FOREMAN 터미널"></iframe><div id="termMsg" class="term-msg"></div></div>`;
  document.body.appendChild(el);
  const $ = (id) => el.querySelector('#' + id);
  const frame = $('termFrame');
  let open = false, loaded = false, seenOpenReq = 0, seenVer = -1, lastConn = null, seenCookie = 0;

  function setHeight() {
    const h = open ? el.getBoundingClientRect().height : BAR_H;
    document.body.style.setProperty('--term-h', `${Math.round(h)}px`);
  }
  async function connect(force) {
    try {
      // 쿠키는 대시보드가 연결될 때 이미 받았다(store.js hello). 패널을 열 때 한 번 더 받아 만료 · 재시작에 대비한다
      const j = await store.terminalSession();
      $('termMsg').textContent = j.running ? '' : 'ttyd가 떠 있지 않다 — 브리지 로그를 본다';
      if (!loaded || force) { frame.src = '/terminal/'; loaded = true; }
    } catch (err) {
      $('termMsg').textContent = `터미널을 열지 못했다 — ${err.message || err}`;
    }
  }
  function focusShell() {
    try {
      frame.contentWindow.focus();
      const ta = frame.contentDocument && frame.contentDocument.querySelector('textarea');
      if (ta) ta.focus();
    } catch { /* 아직 안 떴다 */ }
  }
  function setOpen(v) {
    open = v;
    el.classList.toggle('open', v);
    document.body.classList.toggle('term-open', v);
    $('termToggle').textContent = v ? '▼ 터미널' : '▲ 터미널';
    $('termToggle').setAttribute('aria-expanded', String(v));
    if (v) connect(false).then(() => setTimeout(focusShell, 300));
    requestAnimationFrame(setHeight);
  }
  $('termToggle').onclick = () => setOpen(!open);
  frame.addEventListener('load', () => { if (open) setTimeout(focusShell, 200); });
  window.addEventListener('resize', setHeight);

  $('termReqs').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-act]');
    if (!b) return;
    const id = Number(b.dataset.id);
    if (b.dataset.act === 'dismiss') store.terminalDismiss(id);
    else if (b.dataset.act === 'prefill') store.terminalPrefill(id).then(focusShell);
    else if (b.dataset.act === 'copy') navigator.clipboard?.writeText(b.dataset.cmd || '').catch(() => {});
    else if (b.dataset.act === 'clear') { store.state.terminal.result = null; store.touch('term'); }
  });

  function draw(st) {
    const t = st.terminal;
    if (!t) return;                           // 옛 store.js(캐시)와 섞였을 때 — 대시보드를 막지 않는다
    el.hidden = !t.enabled;
    if (!t.enabled) { document.body.style.setProperty('--term-h', '0px'); return; }
    const reqs = [...t.requests.values()];
    $('termBadge').innerHTML = reqs.length ? `<span class="pill warn">부탁 ${reqs.length}</span>` : '';
    const last = t.shell[t.shell.length - 1];
    $('termLast').textContent = last ? `마지막: ${last.cmd}${last.exit ? ` (종료 ${last.exit})` : ''}` : '';
    let html = reqs.map((r) => {
      const who = `${PROJ[r.project] || r.project || '미분류'}${r.title ? ' · ' + r.title : ''}`;
      const state = r.prefilled
        ? (r.blank ? '셸에 미리 채웠다 — 커서가 비밀번호 자리에 있다. 채우고 Enter' : '셸에 미리 채웠다 — 확인하고 Enter(암호는 물을 때 입력)')
        : `미리 채우지 못했다 — ${r.note || ''}`;
      return `<div class="term-req">
        <div class="term-req-main"><b>${esc(who)}</b>의 부탁 <code>${esc(r.cmd)}</code>
          <div class="small ${r.prefilled ? 'muted' : 'warn'}">${esc(state)} · 결과는 이 세션에 돌려준다</div>
          ${r.others && r.others.length ? `<div class="small muted">같이 적힌 명령: ${r.others.map(esc).join(' · ')}</div>` : ''}</div>
        <div class="appr-act"><button data-act="prefill" data-id="${r.id}">다시 채우기</button>
          <button data-act="copy" data-id="${r.id}" data-cmd="${esc(r.cmd)}" class="ghost">복사</button>
          <button data-act="dismiss" data-id="${r.id}" class="ghost">닫기</button></div></div>`;
    }).join('');
    const res = t.result;
    if (res) {
      html += `<div class="term-req ${res.ok ? 'ok-b' : 'bad-b'}"><div class="term-req-main">
        <span class="${res.ok ? 'ok' : 'bad'}">${esc(PROJ[res.project] || res.project || '')} 결과(종료 ${esc(res.exit)}): ${esc(res.msg)}</span>
        ${res.output ? `<details${keep('term:result')}><summary class="small">출력(마스킹)</summary><code>${esc(res.output)}</code></details>` : ''}</div>
        <div class="appr-act"><button data-act="clear" class="ghost">지우기</button></div></div>`;
    }
    $('termReqs').innerHTML = html;
    if (t.openReq !== seenOpenReq) {          // 새 부탁(WS로 막 왔다) — 패널을 올리고 셸에 초점
      seenOpenReq = t.openReq;
      if (!open) setOpen(true); else setTimeout(focusShell, 100);
    }
    // 다시 연결됐다(브리지를 다시 띄웠을 수 있다) — store가 쿠키를 새로 받으면 화면도 다시 붙인다
    if (t.cookieAt && t.cookieAt !== seenCookie) {
      const again = seenCookie !== 0;
      seenCookie = t.cookieAt;
      if (again && loaded) { frame.src = '/terminal/'; }
    }
    lastConn = st.conn.status;
    requestAnimationFrame(setHeight);
  }

  store.subscribe((st) => {
    if (seenVer !== st.ver.term || lastConn !== st.conn.status) { draw(st); seenVer = st.ver.term; }
  });
}
