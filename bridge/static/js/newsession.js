// + 새 세션(11-05) — 화면에서 바로 tmux 세션을 만들고 claude를 띄운다(터미널에 가지 않고).
// 어디서(프로젝트 또는 폴더 고르기 — 떠돌이) · 이름 · 시작(새로 / 인계 요약 넣고 — 넣을 글을 먼저 보여 준다) → [띄우기].
// 띄우면 브리지가 세션 행을 바로 만들어 첫 입력 전에도 캐릭터가 선다. 폴더 신뢰 창이 뜨면 터미널에서 답하라고 알린다.
// 역할 · 모델(11-05) — 역할마다 기본 모델이 있고(config/models.toml) 바꿀 수 있다.
import { ROLE_PICK, bindRoleModel } from './modelpick.js';

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
    <div class="ns-two">
      <label class="small muted">역할<select id="nsRole"></select></label>
      <label class="small muted" title="모델 — 띄울 때 쓸 모델입니다. 역할마다 기본값이 있고 바꿀 수 있습니다(config/models.toml).">모델<select id="nsModel"></select></label>
    </div>
    <div class="small muted">시작</div>
    <label class="small ns-opt"><input type="radio" name="nsMode" value="fresh" checked><span>새로 시작</span></label>
    <label class="small ns-opt" id="nsHandOpt"><input type="radio" name="nsMode" value="handoff"><span>옮기기용 요약 넣고 시작</span><span id="nsNoSum" class="muted" hidden> — 넣을 요약이 없습니다</span></label>
    <div id="nsHand" hidden>
      <label class="small muted" for="nsSum">어느 세션의 요약을 넣을까요</label>
      <select id="nsSum"></select>
      <pre id="nsPrev" class="hand-body ns-prev"></pre>
    </div>
    <div class="row ns-act"><span id="nsMsg" class="small"></span>
      <button type="button" id="nsCancel" class="ghost">취소</button><button type="button" id="nsGo" class="primary">띄우기</button></div>
  </div>`;
  document.body.appendChild(dlg);
  const $ = (id) => dlg.querySelector('#' + id);
  let opts = null, cwd = null, busy = false, rm = null;
  $('nsRole').innerHTML = Object.entries(ROLE_PICK).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');

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
  // 요약 고르기(11-05) — 전에는 가장 최근 요약이 저절로 골라져 시험용 요약이 그대로 들어갔다. 이제 세션별로 묶어 보여 주고
  // 사람이 직접 골라야 한다(빈 칸이 기본). 넣을 요약이 하나도 없으면 [인계 요약 넣고 시작]을 끈다
  // 11-05 — 고른 프로젝트의 요약만 센다(떠돌이는 프로젝트 없는 요약만). 전에는 다른 프로젝트 요약 하나로도 켜졌다.
  // 이름은 세션 제목만으로는 헷갈린다(177은 첫 입력이던 시험 요약으로 CC가 "푸른 고래 인계 시험"이라 제목을 붙였다) — 번호 · 본문 첫 줄을 같이
  const mine = () => opts.summaries.filter((s) => ($('nsWhere').value === '' ? !s.project : s.project === $('nsWhere').value));
  function fillSummaries() {
    const keep = $('nsSum').value;
    const list = mine();
    const none = !list.length;
    const hand = dlg.querySelector('input[value=handoff]');
    hand.disabled = none;
    $('nsHandOpt').classList.toggle('off', none);
    $('nsNoSum').hidden = !none;
    if (none && hand.checked) dlg.querySelector('input[value=fresh]').checked = true;
    // 세션 하나에 요약이 여럿이면 한 묶음으로
    const groups = new Map();
    for (const s of list) {
      if (!groups.has(s.session_id)) groups.set(s.session_id, { head: s, list: [] });
      groups.get(s.session_id).list.push(s);
    }
    const when = (t) => new Date(t).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    const KIND = { snapshot: '지금 요약', handoff: '옮기기용 요약' };
    const cut = (t, n) => (t && t.length > n ? t.slice(0, n) + '…' : t || '');
    $('nsSum').innerHTML = '<option value="">— 세션을 골라 주세요 —</option>' + [...groups.values()].map((g) =>
      `<optgroup label="세션 ${g.head.session_id} · ${esc(cut(g.head.session, 30))}">${g.list.map((s) =>
        `<option value="${s.id}">${esc(when(s.created_at))} ${esc(KIND[s.kind] || s.kind)}${s.source === 'edited' ? '(고침)' : ''} · ${s.chars}자 — ${esc(cut(s.head, 50))}</option>`).join('')}</optgroup>`).join('');
    if (keep && list.some((s) => String(s.id) === keep)) $('nsSum').value = keep;
    preview();
  }
  async function preview() {
    $('nsHand').hidden = mode() !== 'handoff';
    if (mode() !== 'handoff' || !$('nsSum').value) { $('nsPrev').textContent = mode() === 'handoff' ? '세션을 고르면 넣을 글을 여기 보여 드립니다.' : ''; return; }
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
    if (mode() === 'handoff' && !summary_id) { msg(mine().length ? '넣을 요약의 세션을 골라 주세요.' : '이 프로젝트에는 넣을 요약이 없습니다.', 'bad'); return; }
    busy = true; $('nsGo').disabled = true;
    msg(`새 세션을 띄우는 중입니다… (${home(cwd, opts.home)})`);
    try {
      const r = await api('POST', '/api/spawn', { cwd, summary_id, title: $('nsTitle').value.trim() || null,
        role: $('nsRole').value, model: $('nsModel').value || null });
      if (r.session_id) {
        $('nsMsg').title = r.tmux ? `새 세션 — tmux 창 ${r.tmux}` : '';
        msg(`새 세션을 띄웠습니다${r.model ? `(${r.model})` : ''}.${summary_id ? (r.injected ? ' 요약을 넣었습니다.' : ' 요약은 넣지 못했습니다.') : ''}${r.note ? ' ' + r.note : ''}`, r.note ? 'warn' : 'ok');
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
    $('nsSum').value = '';
    dlg.classList.add('on');
    try { opts = await api('GET', '/api/spawn/options'); } catch (e) { msg(`불러오지 못했습니다 — ${e.message}`, 'bad'); return; }
    $('nsRole').value = 'coder';
    if (!rm) rm = bindRoleModel($('nsRole'), $('nsModel'), opts.models);
    rm.reset();
    $('nsWhere').innerHTML = opts.projects.map((p) => `<option value="${esc(p.name)}">${esc(label(p.name))} — ${esc(home(p.repo, opts.home))}</option>`).join('')
      + '<option value="">프로젝트 없이 — 폴더 고르기(떠돌이)</option>';
    $('nsRecent').innerHTML = opts.recent_cwds.length ? '최근: ' + opts.recent_cwds.slice(0, 8).map((c) => `<button type="button" class="ghost small" data-c="${esc(c)}">${esc(home(c, opts.home))}</button>`).join(' ') : '';
    $('nsWhere').value = opts.projects.some((p) => p.name === project) ? project : (opts.projects[0] ? opts.projects[0].name : '');
    whereChanged();
    $('nsTitle').focus();
  }
  return { open };
}
