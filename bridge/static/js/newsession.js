// + 새 세션(11-05) — 화면에서 바로 tmux 세션을 만들고 claude를 띄운다(터미널에 가지 않고).
// 어디서(프로젝트 또는 폴더 고르기 — 떠돌이) · 이름 · 시작(새로 / 인계 요약 넣고 — 넣을 글을 먼저 보여 준다) → [띄우기].
// 띄우면 브리지가 세션 행을 바로 만들어 첫 입력 전에도 캐릭터가 선다. 폴더 신뢰 창이 뜨면 터미널에서 답하라고 알린다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const home = (p, h) => (h && p && p.startsWith(h) ? '~' + p.slice(h.length) : p);

export function mountNewSession(store, { onCreated }) {
  const dlg = document.createElement('div');
  dlg.id = 'nsDlg'; dlg.className = 'overlay';
  dlg.innerHTML = `<div class="box ns" role="dialog" aria-label="새 세션">
    <h2 class="plain">새 세션</h2>
    <label class="small muted" for="nsWhere">어디서</label>
    <select id="nsWhere"></select>
    <div id="nsPick" class="ns-pick" hidden>
      <div class="row"><button type="button" id="nsUp" class="ghost small" title="위 폴더 — 한 단계 위 폴더로 갑니다.">↑</button><code id="nsPath" class="ns-path"></code></div>
      <div id="nsDirs" class="ns-dirs"></div>
      <div id="nsRecent" class="small"></div>
    </div>
    <label class="small muted" for="nsTitle">이름(비우면 CC가 붙이는 제목)</label>
    <input id="nsTitle" maxlength="255" placeholder="예: 펫퍼민트 검색 품질 점검">
    <div class="small muted">시작</div>
    <label class="small"><input type="radio" name="nsMode" value="fresh" checked> 새로 시작</label>
    <label class="small"><input type="radio" name="nsMode" value="handoff"> 인계 요약 넣고 시작</label>
    <div id="nsHand" hidden>
      <select id="nsSum"></select>
      <pre id="nsPrev" class="hand-body ns-prev"></pre>
    </div>
    <div class="row ns-act"><span id="nsMsg" class="small"></span>
      <button type="button" id="nsCancel" class="ghost">취소</button><button type="button" id="nsGo">띄우기</button></div>
  </div>`;
  document.body.appendChild(dlg);
  const $ = (id) => dlg.querySelector('#' + id);
  let opts = null, cwd = null, busy = false;

  const api = async (method, url, body) => {
    const r = await fetch(url, { method, headers: store.headers(!!body), body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.refused || j.detail || `HTTP ${r.status}`);
    return j;
  };
  const label = (name) => (store.state.projects.find((p) => p.name === name) || {}).label || name;
  const mode = () => dlg.querySelector('input[name=nsMode]:checked').value;
  const msg = (t, cls = 'muted') => { $('nsMsg').className = `small ${cls}`; $('nsMsg').textContent = t; };

  async function browse(path) {
    try {
      const j = await api('GET', `/api/fs/dirs?path=${encodeURIComponent(path)}`);
      cwd = j.path;
      $('nsPath').textContent = home(j.path, opts.home) + (j.is_repo ? '  (git 저장소)' : '');
      $('nsUp').disabled = !j.parent;
      $('nsUp').dataset.p = j.parent || '';
      $('nsDirs').innerHTML = j.dirs.map((d) => `<button type="button" class="ghost small" data-d="${esc(d)}">${esc(d)}/</button>`).join('') || '<span class="small muted">하위 폴더가 없습니다.</span>';
    } catch (e) { msg(`폴더를 읽지 못했습니다 — ${e.message}`, 'bad'); }
  }
  $('nsUp').onclick = () => { if ($('nsUp').dataset.p) browse($('nsUp').dataset.p); };
  $('nsDirs').onclick = (ev) => { const b = ev.target.closest('[data-d]'); if (b) browse(cwd.replace(/\/$/, '') + '/' + b.dataset.d); };
  $('nsRecent').onclick = (ev) => { const b = ev.target.closest('[data-c]'); if (b) browse(b.dataset.c); };

  function whereChanged() {
    const v = $('nsWhere').value;
    $('nsPick').hidden = v !== '';
    if (v === '') browse(cwd || opts.home);
    else cwd = (opts.projects.find((p) => p.name === v) || {}).repo || null;
    fillSummaries();
  }
  function fillSummaries() {
    const v = $('nsWhere').value;
    // 같은 프로젝트(떠돌이면 같은 폴더) 요약이 위에
    const list = opts.summaries.slice().sort((a, b) => ((b.project || '') === v) - ((a.project || '') === v));
    $('nsSum').innerHTML = list.map((s) => `<option value="${s.id}">${esc(label(s.project) || '떠돌이')} · ${esc(s.session)} · ${s.chars}자 · ${esc(new Date(s.created_at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }))}</option>`).join('')
      || '<option value="">넣을 수 있는 인계 요약이 없습니다</option>';
    preview();
  }
  async function preview() {
    $('nsHand').hidden = mode() !== 'handoff';
    if (mode() !== 'handoff' || !$('nsSum').value) { $('nsPrev').textContent = ''; return; }
    $('nsPrev').textContent = '넣을 글을 불러오는 중입니다…';
    try {
      const j = await api('GET', `/api/summaries/${$('nsSum').value}/injection`);
      $('nsPrev').textContent = j.text + (j.cut ? `\n\n(길어서 일부 절을 줄였습니다. 전체는 ${j.full_path}에 있습니다.)` : '');
    } catch (e) { $('nsPrev').textContent = `불러오지 못했습니다 — ${e.message}`; }
  }
  $('nsWhere').onchange = whereChanged;
  $('nsSum').onchange = preview;
  for (const r of dlg.querySelectorAll('input[name=nsMode]')) r.onchange = preview;
  $('nsCancel').onclick = () => close();
  dlg.addEventListener('click', (ev) => { if (ev.target === dlg && !busy) close(); });
  dlg.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !busy) { ev.stopPropagation(); close(); } });

  $('nsGo').onclick = async () => {
    if (busy || !cwd) { if (!cwd) msg('폴더를 골라 주세요.', 'bad'); return; }
    const summary_id = mode() === 'handoff' && $('nsSum').value ? Number($('nsSum').value) : null;
    if (mode() === 'handoff' && !summary_id) { msg('넣을 인계 요약이 없습니다.', 'bad'); return; }
    busy = true; $('nsGo').disabled = true;
    msg(`새 세션을 띄우는 중입니다… (${home(cwd, opts.home)})`);
    try {
      const r = await api('POST', '/api/spawn', { cwd, summary_id, title: $('nsTitle').value.trim() || null });
      if (r.session_id) {
        msg(`새 세션을 띄웠습니다(tmux ${r.tmux}).${summary_id ? (r.injected ? ' 인계를 넣었습니다.' : ' 인계는 넣지 못했습니다.') : ''}${r.note ? ' ' + r.note : ''}`, r.note ? 'warn' : 'ok');
        await store.loadSnapshot();
        if (onCreated) onCreated(r.session_id);
        setTimeout(close, r.note ? 4000 : 900);
      } else {
        msg(r.note || '새 세션을 찾지 못했습니다.', 'warn');
      }
    } catch (e) { msg(`띄우지 못했습니다 — ${e.message}`, 'bad'); }
    busy = false; $('nsGo').disabled = false;
  };

  function close() { dlg.classList.remove('on'); }
  async function open(project) {
    msg('');
    $('nsTitle').value = '';
    dlg.querySelector('input[value=fresh]').checked = true;
    dlg.classList.add('on');
    try { opts = await api('GET', '/api/spawn/options'); } catch (e) { msg(`불러오지 못했습니다 — ${e.message}`, 'bad'); return; }
    $('nsWhere').innerHTML = opts.projects.map((p) => `<option value="${esc(p.name)}">${esc(label(p.name))} — ${esc(home(p.repo, opts.home))}</option>`).join('')
      + '<option value="">프로젝트 없이 — 폴더 고르기(떠돌이)</option>';
    $('nsRecent').innerHTML = opts.recent_cwds.length ? '최근: ' + opts.recent_cwds.slice(0, 8).map((c) => `<button type="button" class="ghost small" data-c="${esc(c)}">${esc(home(c, opts.home))}</button>`).join(' ') : '';
    $('nsWhere').value = opts.projects.some((p) => p.name === project) ? project : (opts.projects[0] ? opts.projects[0].name : '');
    whereChanged();
    $('nsTitle').focus();
  }
  return { open };
}
