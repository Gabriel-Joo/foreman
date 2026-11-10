// 터미널 패널(7단계) — 대시보드 아래 접이식. ttyd 화면(xterm.js)을 iframe으로 그대로 띄운다(파싱하지 않는다).
// CC가 "이 명령을 실행해 주세요"라고 하면 브리지가 셸 입력 줄에 미리 채우고 terminal_request를 보낸다 → 패널을 올린다.
// 사람이 Enter를 치고 암호를 넣는다. 결과는 브리지가 부탁한 세션에 돌려준다(terminal_result).

import { keep } from './render.js';
import { applyTermFont, onDprChange } from './uiscale.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const PROJ = { runshoes: '런슈즈', 'petmint-rag-chatbot': '펫퍼민트', foreman: 'FOREMAN' };
const BAR_H = 36;

// getProject(11-10) — 지금 보는 현장 · 고른 세션의 프로젝트(office.js currentProject). 열 때 그 프로젝트의 셸 창을 보인다.
// 전에는 셸 창이 하나라 [런슈즈]에서 열어도 FOREMAN 셸이 떴다. 프로젝트마다 tmux 창(bridge/terminal.py window_for)
export function createTerminal(store, { getProject } = {}) {
  const el = document.createElement('section');
  el.className = 'term';
  el.innerHTML = `
    <div class="term-bar">
      <button id="termToggle" class="ghost" aria-expanded="false">▲ 터미널</button>
      <select id="termPick" class="term-pick" hidden data-tip="터미널 프로젝트 — 지금 보이는 셸 창입니다. 바꾸면 그 프로젝트 폴더의 셸 창으로 갑니다(프로젝트마다 셸이 따로 있습니다)." aria-label="터미널 프로젝트"></select>
      <button id="termRespawn" class="ghost" hidden data-tip="새 셸 — 이 창의 셸을 새로 띄워 바뀐 설정을 읽습니다. 돌고 있는 명령이나 친 글이 있으면 먼저 묻습니다.">새 셸</button>
      <span id="termProjWarn" class="small warn" hidden></span>
      <span id="termBadge"></span>
      <span id="termLast" class="small muted term-last"></span>
    </div>
    <div id="termReqs" class="term-reqs"></div>
    <div class="term-body"><iframe id="termFrame" aria-label="FOREMAN 터미널"></iframe><div id="termMsg" class="term-msg"></div></div>`;
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
      $('termMsg').textContent = j.running ? '' : '터미널 서버가 꺼져 있습니다 — 브리지 로그를 봅니다';
      if (!loaded || force) { frame.src = '/terminal/'; loaded = true; }
    } catch (err) {
      $('termMsg').textContent = `터미널을 열지 못했습니다 — ${err.message || err}`;
    }
  }
  function focusShell() {
    try {
      frame.contentWindow.focus();
      const ta = frame.contentDocument && frame.contentDocument.querySelector('textarea');
      if (ta) ta.focus();
    } catch { /* 아직 안 떴다 */ }
  }
  // ── 프로젝트 창(11-10) ── want = 고른 것, shown = 브리지가 돌려준 실제 창. 다르면 막대에 경고(고른 것과 다르면 틀린 것)
  let want = null, shown = null;
  const plabel = (p) => (store.state.projects.find((x) => x.name === p) || {}).label || PROJ[p] || p;
  function drawProj(err) {
    const pick = $('termPick'), names = store.state.projects.map((x) => x.name).filter((n) => n && PROJ[n]);
    const cur = shown && shown.project;
    const opts = names.map((n) => `<option value="${esc(n)}"${n === cur ? ' selected' : ''}>${esc(plabel(n))} 터미널</option>`).join('')
      + (cur ? '' : `<option value="" selected>${esc(shown ? shown.window || '터미널' : '터미널')}</option>`);
    if (pick.innerHTML !== opts) pick.innerHTML = opts;
    pick.hidden = !shown;
    if (shown && shown.cwd) pick.dataset.tip = `터미널 프로젝트 — 지금 보이는 셸 창입니다. 바꾸면 그 프로젝트 폴더의 셸 창으로 갑니다.\n지금 폴더 ${shown.cwd.replace(/^\/home\/[^/]+/, '~')}`;
    // title이 아니라 aria-label(11-10) — title은 tip.js가 툴팁으로 바꿔, 마우스가 터미널에 들어가면 「런슈즈 터미널」이 프롬프트 줄 위에 떠 남았다
    frame.setAttribute('aria-label', cur ? `${plabel(cur)} 터미널` : 'FOREMAN 터미널');
    const w = $('termProjWarn');
    const now = cur ? `${plabel(cur)} 터미널` : (shown && shown.window) || '알 수 없는 창';
    // 창 이름은 맞아도 셸이 다른 프로젝트 폴더로 옮겨 가 있을 수 있다(11-10 — FOREMAN 창에서 cd로 petmint 폴더에 들어가 있었다)
    const inDir = shown && shown.cwd ? shown.cwd.split('/').find((seg) => PROJ[seg]) : null;
    // 셸이 뜬 뒤 셸 설정 파일이 바뀌었다(11-10) — 열린 창은 옛 설정 그대로라 알린다. [새 셸]을 눌러야 할 버튼(primary)으로
    const old = !err && shown && shown.shell_old;
    const bad = err ? err
      : want && cur !== want ? `고른 것(${plabel(want)})과 다른 터미널입니다 — 지금 보이는 것은 ${now}입니다`
      : cur && inDir && inDir !== cur ? `${plabel(cur)} 터미널인데 셸은 ${plabel(inDir)} 폴더에 들어가 있습니다`
      : old ? '셸 설정이 바뀌었습니다 — 이 창은 옛 설정입니다. [새 셸]을 누르면 새 설정을 읽습니다' : '';
    w.textContent = bad; w.hidden = !bad;
    if (old) w.dataset.tip = `옛 셸 — 셸이 뜬 뒤 셸 설정 파일이 바뀌었습니다.\n바뀐 파일 ${old.files.join(' · ')} · ${hm(old.changed_at)}\n셸이 뜬 시각 ${hm(old.started_at)}`;
    else delete w.dataset.tip;
    const rb = $('termRespawn');
    rb.hidden = !cur;
    rb.className = old ? 'primary' : 'ghost';
  }
  const hm = (iso) => { const d = new Date(iso); return isNaN(d) ? '?' : `${d.getMonth() + 1}월 ${d.getDate()}일 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
  // [새 셸](11-10) — 명령이 돌고 있거나 친 글이 남아 있으면 확인 창 먼저(사람의 sudo · ssh가 돌 수 있는 셸이다)
  async function respawnShell() {
    const p = shown && shown.project;
    if (!p) return;
    const rb = $('termRespawn');
    rb.disabled = true;
    try {
      let j = await store.terminalRespawn(p, false);
      if (!j.respawned) {
        const b = j.busy || {};
        const what = b.cmd ? `돌고 있는 명령(${b.cmd})이 끝납니다.` : `입력 줄에 친 글(${b.typed})이 지워집니다.`;
        if (!confirm(`${plabel(p)} 터미널의 셸을 새로 띄웁니다. ${what} 계속할까요?`)) return;
        j = await store.terminalRespawn(p, true);
      }
      shown = j; drawProj();
      setTimeout(focusShell, 200);
    } catch (e) {
      drawProj(`셸을 새로 띄우지 못했습니다 — ${e.message || e}`);
    } finally { rb.disabled = false; }
  }
  $('termRespawn').addEventListener('click', respawnShell);
  // 열려 있는 동안 실제 보이는 창을 3초마다 확인한다(11-10) — tmux의 보이는 창은 세션에 하나라 다른 탭 · CC 부탁 · tmux 키가 바꿀 수 있고,
  // 열 때 받은 값만 쥐고 있으면 이름표가 거짓이 된다("런슈즈 터미널"인데 petmint 셸). 못 읽으면 이름표를 못 믿는다고 경고한다
  let winErr = false;
  async function checkWindow() {
    if (!open) return;
    try {
      const j = await store.terminalWindow();
      const was = winErr; winErr = false;
      if (was || !shown || shown.window !== j.window || shown.cwd !== j.cwd || !shown.shell_old !== !j.shell_old) { shown = j; drawProj(); }
    } catch (e) {
      if (!winErr) { winErr = true; drawProj(`지금 보이는 창을 확인하지 못했습니다 — ${e.message || e}`); }
    }
  }
  setInterval(checkWindow, 3000);
  async function pickProject(p) {
    want = p || null;
    try { shown = await store.terminalOpen(want); drawProj(); } catch (e) { drawProj(`터미널 창을 고르지 못했습니다 — ${e.message || e}`); }
  }
  $('termPick').addEventListener('change', (ev) => { pickProject(ev.target.value || null).then(() => setTimeout(focusShell, 100)); });

  function setOpen(v, project) {           // project를 안 주면 지금 보는 현장의 것(getProject)
    open = v;
    el.classList.toggle('open', v);
    document.body.classList.toggle('term-open', v);
    $('termToggle').textContent = v ? '▼ 터미널' : '▲ 터미널';
    $('termToggle').setAttribute('aria-expanded', String(v));
    // 열 때 지금 보는 현장의 프로젝트 창으로(감독실 · 라운지 · 전체 지도면 지금 창 그대로)
    if (v) Promise.all([connect(false), pickProject(project !== undefined ? project : getProject ? getProject() : null)]).then(() => setTimeout(focusShell, 300));
    requestAnimationFrame(setHeight);
  }
  $('termToggle').onclick = () => setOpen(!open);
  // 글씨 크기(11-08, uiscale.js) — ttyd가 xterm을 띄운 뒤(window.term)에 맞춘다. 버튼을 누르면 바로
  function fitFont(tries = 20) { if (!applyTermFont(frame) && tries > 0) setTimeout(() => fitFont(tries - 1), 250); }
  frame.addEventListener('load', () => { fitFont(); if (open) setTimeout(focusShell, 200); });
  window.addEventListener('foreman-uiscale', () => fitFont(0));
  onDprChange(() => fitFont(0));           // 브라우저 확대가 바뀌면 칸 폭 보정(letterSpacing)을 다시(11-10)
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
        ${res.output ? `<details${keep('term:result')}><summary class="small">출력(비밀값 가림)</summary><code>${esc(res.output)}</code></details>` : ''}</div>
        <div class="appr-act"><button data-act="clear" class="ghost">지우기</button></div></div>`;
    }
    $('termReqs').innerHTML = html;
    if (t.openReq !== seenOpenReq) {          // 새 부탁(WS로 막 왔다) — 패널을 올리고 셸에 초점
      seenOpenReq = t.openReq;
      // 브리지가 부탁한 세션의 프로젝트 창에 채우고 그 창을 보였다(11-10) — 막대도 그 프로젝트로
      const r = [...t.requests.values()].sort((a, b) => b.id - a.id)[0];
      const p = r && PROJ[r.project] ? r.project : null;
      if (!open) setOpen(true, p);
      else { pickProject(p); setTimeout(focusShell, 100); }
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
