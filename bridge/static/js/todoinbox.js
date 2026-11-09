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

// 받은 할 일 상태 호버 글(11-09 받는 사람별) — 서기 정리 · 코더에게. 이름(label)은 브리지가 받는 사람에 맞게 준다
export function stateTip(x) {
  const coder = x.assignee === 'coder';
  const why = {
    new: coder ? '아직 아무 세션도 가져가지 않았습니다. 그 방 코더를 누르면 맡길 수 있습니다.' : '아직 서기가 가져가지 않았습니다.',
    taking: coder ? `세션 ${x.taken_by}이 이 일을 하는 중입니다.` : `서기 세션 ${x.taken_by}이 README 표로 옮기는 중입니다.`,
    moved: coder ? `세션 ${x.taken_by}이 이 일을 마쳤습니다(합쳐짐).` : '서기가 README 「나중에 할 일」 표로 옮겼습니다.',
    dropped: '사람이 버렸습니다.',
  }[x.state] || '';
  return `${x.label} — ${why}`;
}
export const TO = { scribe: '서기 정리', coder: '코더에게' };

export function mountTodoInbox(store, { onSaved } = {}) {
  const dlg = document.createElement('div');
  dlg.id = 'tiDlg'; dlg.className = 'overlay';
  dlg.innerHTML = `<div class="box ns ti" role="dialog" aria-label="할 일 적기">
    <h2 class="plain">할 일 적기</h2>
    <div class="small muted">세션을 띄우지 않고 그대로 적어 둡니다. 서기 정리는 「나중에 할 일 정리」가 README 표로 옮기고, 코더에게는 그 방 코더 머리 위 "맡길 일"에 뜹니다.</div>
    <label class="small muted" for="tiProj">프로젝트</label>
    <select id="tiProj"></select>
    <div class="small muted">누구에게</div>
    <div class="row ti-to" role="radiogroup" aria-label="누구에게">
      <label class="small ns-opt" title="서기 정리 — 서기가 「나중에 할 일 정리」로 모아 README 「나중에 할 일」 표에 옮깁니다."><input type="radio" name="tiTo" value="scribe" checked><span>서기 정리</span></label>
      <label class="small ns-opt" title="코더에게 — 그 방 코더 머리 위 「맡길 일」에 뜹니다. 코더를 눌러 줄을 고르면 계획 창에 이 글이 채워집니다."><input type="radio" name="tiTo" value="coder"><span>코더에게</span></label>
    </div>
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
          <span class="ti-st small" data-tip="${esc(stateTip(x))}">${esc(x.label)}</span>
          <details class="ti-body"><summary class="small">${esc(kst(x.created_at))} · ${x.assignee === 'coder' ? '코더 · ' : ''}${esc(firstLine(x.body))}</summary><pre class="hand-body">${esc(x.body)}</pre></details>
          ${x.state === 'new' ? `<button type="button" class="ghost small" data-drop="${x.id}" title="버리기 — 이 할 일을 아무에게도 넘기지 않습니다. 목록에는 「버림」으로 남습니다.">버리기</button>` : ''}
        </div>`).join('');
    } catch (e) { $('tiListHead').textContent = `받은 할 일 — 불러오지 못했습니다(${e.message})`; }
  }

  async function save() {
    const body = $('tiBody').value.trim();
    if (busy) return;
    if (!body) { msg('적을 글이 비어 있습니다.', 'bad'); $('tiBody').focus(); return; }
    busy = true; $('tiGo').disabled = true;
    const to = dlg.querySelector('input[name=tiTo]:checked').value;
    try {
      const r = await api('POST', '/api/scribe/inbox', { project: $('tiProj').value, body, assignee: to });
      $('tiBody').value = '';
      msg(`적었습니다 — ${label($('tiProj').value)} 받은 할 일 #${r.id}. ${to === 'coder' ? '그 방 코더의 「맡길 일」에 뜹니다.' : '서기가 정리할 때 README 표로 옮깁니다.'}`, 'ok');
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
  // to — 'coder'면 코더에게를 고른 채(코더 목록의 [＋ 할 일]에서 열 때). 기본은 서기 정리
  function open(project, to = 'scribe') {
    const names = store.state.projects.map((p) => p.name).filter(Boolean);
    $('tiProj').innerHTML = names.map((n) => `<option value="${esc(n)}">${esc(label(n))}</option>`).join('');
    $('tiProj').value = names.includes(project) ? project : (names.includes('foreman') ? 'foreman' : names[0] || '');
    const r = dlg.querySelector(`input[name=tiTo][value=${to === 'coder' ? 'coder' : 'scribe'}]`);
    if (r) r.checked = true;
    msg('');
    dlg.classList.add('on');
    loadList();
    $('tiBody').focus();
  }
  return { open, close };
}
