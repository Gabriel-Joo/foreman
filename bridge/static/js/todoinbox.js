// [＋ 할 일](11-09 사용자 — "할 일에 넣어라"가 메인 세션에 몰려 맥락이 쌓였다, log/dispatch_flow_decision_20261109.md)
// 적은 글을 브리지가 세션 없이 그대로 받는 함에 둔다(/api/scribe/inbox, migrations/0027). 정리 · 우선순위는 서기의 「나중에 할 일 정리」가
// 몰아서 README 표로 옮긴다. 상태(새로 · 서기가 정리 중 · 옮김 · 버림)는 브리지가 계산한다 — 적은 것은 여기서 다시 볼 수 있다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MAX = 8000;
const kst = (iso) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getMonth() + 1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
// 첫 줄만, 길면 자른다 — 목록에서 무엇인지 알아볼 만큼
export const firstLine = (s, n = 60) => {
  const t = String(s || '').split('\n').map((x) => x.trim()).find((x) => x && !/^[━─=\-]{3,}$/.test(x)) || '';
  return t.length > n ? t.slice(0, n - 1) + '…' : t;
};

export function mountTodoInbox(store, { onSaved } = {}) {
  const dlg = document.createElement('div');
  dlg.id = 'tiDlg'; dlg.className = 'overlay';
  dlg.innerHTML = `<div class="box ns ti" role="dialog" aria-label="할 일 적기">
    <h2 class="plain">할 일 적기</h2>
    <div class="small muted">세션을 띄우지 않고 그대로 적어 둡니다. 서기가 「나중에 할 일 정리」로 모아 README 표에 옮깁니다.</div>
    <label class="small muted" for="tiProj">프로젝트</label>
    <select id="tiProj"></select>
    <label class="small muted" for="tiBody">할 일(붙여 넣어도 됩니다 — 줄바꿈 그대로 둡니다)</label>
    <textarea id="tiBody" rows="8" maxlength="${MAX}" placeholder="예: 질문 카드 — 답한 뒤에도 자리를 먹는다. 한 줄로 접고 [×]로 치우게"></textarea>
    <div class="row ns-act"><span id="tiMsg" class="small"></span>
      <button type="button" id="tiCancel" class="ghost" title="닫기 — 적지 않고 닫습니다. 쓰던 글은 남아 있습니다.">닫기</button>
      <button type="button" id="tiGo" class="primary" title="적기 — 받은 할 일에 적습니다. Ctrl+Enter로도 적습니다.">적기</button></div>
    <details id="tiListBox" class="ti-list"><summary class="small muted" id="tiListHead">받은 할 일</summary><div id="tiList"></div></details>
  </div>`;
  document.body.appendChild(dlg);
  const $ = (id) => dlg.querySelector('#' + id);
  let busy = false;

  const api = async (method, url, body) => {
    const r = await fetch(url, { method, headers: store.headers(!!body), body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.refused || j.detail || `HTTP ${r.status}`);
    return j;
  };
  const label = (name) => (store.state.projects.find((p) => p.name === name) || {}).label || name;
  const msg = (t, cls = 'muted') => { $('tiMsg').className = `small ${cls}`; $('tiMsg').textContent = t; };

  async function loadList() {
    try {
      const j = await api('GET', `/api/scribe/inbox?project=${encodeURIComponent($('tiProj').value)}&limit=20`);
      const items = j.items || [];
      const nNew = items.filter((x) => x.state === 'new').length;
      $('tiListHead').textContent = `받은 할 일 — ${label($('tiProj').value)} ${items.length ? `최근 ${items.length}개 · 새로 ${nNew}` : '없음'}`;
      $('tiList').innerHTML = items.map((x) => `<div class="ti-item st-${esc(x.state)}">
          <span class="ti-st small" data-tip="${esc(x.label)} — ${x.state === 'new' ? '아직 서기가 가져가지 않았습니다.' : x.state === 'taking' ? `서기 세션 ${x.taken_by}이 README 표로 옮기는 중입니다.` : x.state === 'moved' ? '서기가 README 「나중에 할 일」 표로 옮겼습니다.' : '사람이 버렸습니다.'}">${esc(x.label)}</span>
          <details class="ti-body"><summary class="small">${esc(kst(x.created_at))} · ${esc(firstLine(x.body))}</summary><pre class="hand-body">${esc(x.body)}</pre></details>
          ${x.state === 'new' ? `<button type="button" class="ghost small" data-drop="${x.id}" title="버리기 — 이 할 일을 서기에게 넘기지 않습니다. 목록에는 「버림」으로 남습니다.">버리기</button>` : ''}
        </div>`).join('');
    } catch (e) { $('tiListHead').textContent = `받은 할 일 — 불러오지 못했습니다(${e.message})`; }
  }

  async function save() {
    const body = $('tiBody').value.trim();
    if (busy) return;
    if (!body) { msg('적을 글이 비어 있습니다.', 'bad'); $('tiBody').focus(); return; }
    busy = true; $('tiGo').disabled = true;
    try {
      const r = await api('POST', '/api/scribe/inbox', { project: $('tiProj').value, body });
      $('tiBody').value = '';
      msg(`적었습니다 — ${label($('tiProj').value)} 받은 할 일 #${r.id}. 서기가 정리할 때 README 표로 옮깁니다.`, 'ok');
      if (onSaved) onSaved(r.id);
      await loadList();
    } catch (e) { msg(`적지 못했습니다 — ${e.message}. 글은 칸에 그대로 있습니다.`, 'bad'); }
    busy = false; $('tiGo').disabled = false;
  }

  $('tiGo').onclick = save;
  $('tiCancel').onclick = () => close();
  $('tiProj').onchange = loadList;
  $('tiBody').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); save(); } });
  dlg.addEventListener('click', async (ev) => {
    if (ev.target === dlg && !busy) { close(); return; }
    const b = ev.target.closest('[data-drop]');
    if (!b) return;
    b.disabled = true;
    try { await api('POST', `/api/scribe/inbox/${b.dataset.drop}/drop`, {}); msg('버렸습니다 — 목록에 「버림」으로 남습니다.', 'muted'); } catch (e) { msg(`버리지 못했습니다 — ${e.message}`, 'bad'); }
    await loadList();
  });
  dlg.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !busy) { ev.stopPropagation(); close(); } });

  function close() { dlg.classList.remove('on'); }
  function open(project) {
    const names = store.state.projects.map((p) => p.name);
    $('tiProj').innerHTML = names.map((n) => `<option value="${esc(n)}">${esc(label(n))}</option>`).join('');
    $('tiProj').value = names.includes(project) ? project : (names.includes('foreman') ? 'foreman' : names[0] || '');
    msg('');
    dlg.classList.add('on');
    loadList();
    $('tiBody').focus();
  }
  return { open, close };
}
