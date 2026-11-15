// [＋ 할 일](11-09 사용자 — "할 일에 넣어라"가 메인 세션에 몰려 맥락이 쌓였다, log/dispatch_flow_decision_20261109.md)
// 적은 글을 브리지가 세션 없이 그대로 받는 함(= 포스트잇, 11-15)에 둔다(/api/scribe/inbox, migrations/0027 · 0033).
// 11-15 사용자: 「코더에게」를 없앴다(사용자는 관리자에게만 말한다). 코더에게 맡길 만한 것은 포스트잇이 추천하고 [띄우기]로 띄운다.
// 받은 것 목록은 이 창에 두지 않는다 — 옆 포스트잇(postit.js)이 그 목록이다.

import { firstLine } from './postit.js';

export { firstLine };

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MAX = 8000;

export function mountTodoInbox(store, { onSaved } = {}) {
  const dlg = document.createElement('div');
  dlg.id = 'tiDlg'; dlg.className = 'overlay';
  dlg.innerHTML = `<div class="box ns ti" role="dialog" aria-label="할 일 적기">
    <h2 class="plain">할 일 적기</h2>
    <div class="small muted">세션을 띄우지 않고 그대로 적어 둡니다. 적은 것은 머리줄 포스트잇에 붙습니다.</div>
    <label class="small muted" for="tiProj">프로젝트</label>
    <select id="tiProj"></select>
    <label class="small muted" for="tiBody">할 일(붙여 넣어도 됩니다. 줄바꿈은 그대로 둡니다)</label>
    <textarea id="tiBody" rows="8" maxlength="${MAX}" placeholder="예: 질문 카드는 답한 뒤에도 자리를 먹는다. 한 줄로 접고 [×]로 치우게"></textarea>
    <div class="row ns-act"><span id="tiMsg" class="small"></span>
      <button type="button" id="tiCancel" class="ghost" title="닫기 — 적지 않고 닫습니다. 쓰던 글은 남아 있습니다.">닫기</button>
      <button type="button" id="tiGo" class="primary" title="적기 — 포스트잇에 적습니다. Ctrl+Enter로도 적습니다.">적기</button></div>
  </div>`;
  document.body.appendChild(dlg);
  const $ = (id) => dlg.querySelector('#' + id);
  let busy = false;

  const label = (name) => (store.state.projects.find((p) => p.name === name) || {}).label || name;
  const msg = (t, cls = 'muted') => { $('tiMsg').className = `small ${cls}`; $('tiMsg').textContent = t; };

  async function save() {
    const body = $('tiBody').value.trim();
    if (busy) return;
    if (!body) { msg('적을 글이 비어 있습니다.', 'bad'); $('tiBody').focus(); return; }
    busy = true; $('tiGo').disabled = true;
    try {
      const r = await fetch('/api/scribe/inbox', { method: 'POST', headers: store.headers(true), body: JSON.stringify({ project: $('tiProj').value, body }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.refused || j.detail || `HTTP ${r.status}`);
      $('tiBody').value = '';
      msg(`적었습니다: ${label($('tiProj').value)} 포스트잇 #${j.id}(${firstLine(body, 30)}).`, 'ok');
      if (onSaved) onSaved(j.id);
    } catch (e) { msg(`적지 못했습니다(${e.message}). 글은 칸에 그대로 있습니다.`, 'bad'); }
    busy = false; $('tiGo').disabled = false;
  }

  $('tiGo').onclick = save;
  $('tiCancel').onclick = () => close();
  $('tiBody').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); save(); } });
  dlg.addEventListener('click', (ev) => { if (ev.target === dlg && !busy) close(); });
  dlg.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !busy) { ev.stopPropagation(); close(); } });

  function close() { dlg.classList.remove('on'); }
  function open(project) {
    const names = store.state.projects.map((p) => p.name).filter(Boolean);
    $('tiProj').innerHTML = names.map((n) => `<option value="${esc(n)}">${esc(label(n))}</option>`).join('');
    $('tiProj').value = names.includes(project) ? project : (names.includes('foreman') ? 'foreman' : names[0] || '');
    msg('');
    dlg.classList.add('on');
    $('tiBody').focus();
  }
  return { open, close };
}
