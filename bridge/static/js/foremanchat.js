// 포먼에게 말하기(11-05, docs/11_foreman_dispatch.md) — [+ 세션] 창 맨 위. "뭘 하려는지" 말하면 포먼이 계획(프로젝트 · 방식 · 쓸 요약 ·
// 역할 · 이름 · 넣을 첫 글)을 내고, 사람이 보고 고친 뒤 [이대로 시작]. 원래 창(직접 고르기)은 아래에 접어 둔다 — 포먼이 틀릴 때 쓴다.
// newsession.js를 고치지 않고 그 창(#nsDlg)이 생기면 위에 붙는다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LABEL = { runshoes: '런슈즈', 'petmint-rag-chatbot': '펫퍼민트', foreman: '포먼' };
const MODE = { new: '새로 시작', handoff: '인계 요약 넣고 시작', attach: '살아 있는 세션에 보내기', ask: '되묻기(시작하지 않음)' };
const ROLE = { coder: '코더 — 고치기 · 만들기', inspector: '점검 — 살펴보기 · 원인 찾기', cicd: 'CI/CD — 빌드 · 배포' };

function headers(json) {
  let t = '';
  try { t = localStorage.getItem('foremanToken') || ''; } catch { /* 없음 */ }
  return { Authorization: `Bearer ${t}`, ...(json ? { 'Content-Type': 'application/json' } : {}) };
}
async function api(method, url, body) {
  const r = await fetch(url, { method, headers: headers(!!body), body: body ? JSON.stringify(body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.refused || j.detail || `HTTP ${r.status}`);
  return j;
}

function mount(dlg) {
  const box = dlg.querySelector('.box');
  if (!box || box.querySelector('.fm')) return;
  const h2 = box.querySelector('h2');
  // 원래 창(직접 고르기)을 접는다 — 버튼 · 칸 id는 그대로라 newsession.js가 그대로 쓴다
  const manual = document.createElement('details');
  manual.className = 'fm-manual';
  manual.innerHTML = '<summary class="small">직접 고르기 — 프로젝트 · 시작 방식을 내가 정한다</summary>';
  const act = box.querySelector('.ns-act');          // [취소] · [띄우기] 줄은 접지 않는다
  while (h2.nextSibling && h2.nextSibling !== act) manual.appendChild(h2.nextSibling);
  const fm = document.createElement('section');
  fm.className = 'fm';
  fm.innerHTML = `
    <label class="small muted" for="fmText">포먼에게 말하기 — 뭘 하려는지</label>
    <textarea id="fmText" rows="2" placeholder="예: 런슈즈 발볼 검증 이어서 · 펫퍼민트 새로 시작 · 빌드 터진 거 봐줘"></textarea>
    <div class="row fm-row"><span id="fmMsg" class="small muted"></span><button type="button" id="fmAsk">계획 받기</button></div>
    <div id="fmPlan" class="fm-plan" hidden></div>`;
  h2.after(fm, manual);
  const $ = (id) => box.querySelector('#' + id);
  let disp = null, opts = null;
  const msg = (t, cls = 'muted') => { $('fmMsg').className = `small ${cls}`; $('fmMsg').textContent = t; };

  async function ask() {
    const text = $('fmText').value.trim();
    if (!text) { msg('뭘 하려는지 적어 주세요.', 'bad'); return; }
    $('fmAsk').disabled = true; $('fmPlan').hidden = true;
    msg('포먼이 상황을 보고 계획을 세우는 중입니다… (20초 안팎)');
    try {
      [disp, opts] = await Promise.all([api('POST', '/api/foreman/plan', { text }), opts || api('GET', '/api/spawn/options')]);
      msg(`계획이 나왔습니다(${Math.round(disp.ms / 1000)}초). 확인하고 고칠 것은 고친 뒤 시작해 주세요.`, 'ok');
      draw(disp.plan);
    } catch (e) { msg(`계획을 받지 못했습니다 — ${e.message}. 아래 "직접 고르기"를 쓸 수 있습니다.`, 'bad'); }
    $('fmAsk').disabled = false;
  }
  function draw(p) {
    const sums = (opts.summaries || []).filter((s) => !p.project || s.project === p.project);
    const opt = (v, cur, label) => `<option value="${esc(v)}"${String(v) === String(cur ?? '') ? ' selected' : ''}>${esc(label)}</option>`;
    $('fmPlan').innerHTML = `
      ${(p.warnings || []).length ? `<div class="small warn">${p.warnings.map(esc).join('<br>')}</div>` : ''}
      ${(p.questions || []).length ? `<div class="fm-q"><b>포먼이 묻습니다</b>${p.questions.map((q) => `<div>• ${esc(q)}</div>`).join('')}</div>` : ''}
      <div class="fm-grid">
        <label class="small muted">프로젝트</label>
        <select id="fmProj">${(opts.projects || []).map((x) => opt(x.name, p.project, LABEL[x.name] || x.name)).join('')}</select>
        <label class="small muted">방식</label>
        <select id="fmMode">${Object.entries(MODE).map(([k, v]) => opt(k, p.mode, v)).join('')}</select>
        <label class="small muted">인계 요약</label>
        <select id="fmSum">${opt('', p.summary_id, '쓰지 않음')}${sums.map((s) => opt(s.id, p.summary_id, `#${s.id} ${s.session} · ${s.chars}자`)).join('')}</select>
        <label class="small muted">보낼 세션</label>
        <input id="fmAttach" value="${esc(p.attach_session ?? '')}" placeholder="방식이 '살아 있는 세션에 보내기'일 때 세션 번호">
        <label class="small muted">역할</label>
        <select id="fmRole">${Object.entries(ROLE).map(([k, v]) => opt(k, p.role, v)).join('')}</select>
        <label class="small muted">이름</label>
        <input id="fmTitle" value="${esc(p.title || '')}">
      </div>
      <label class="small"><input id="fmRO" type="checkbox"${p.read_only ? ' checked' : ''}> 읽기 전용으로 시작(살펴보기만 — 고치기 전에 승인)</label>
      <label class="small" title="따로 작업 — 저장소 안 .worktrees/에 이 세션만의 폴더 · 브랜치(cc/…)를 만들어 띄웁니다. 끝낸 뒤 [합치기]로 main에 합칩니다."><input id="fmWT" type="checkbox"${p.worktree ? ' checked' : ''}> 따로 작업(worktree)
        <span class="muted">${p.live_here ? `— 이 프로젝트에 살아 있는 세션 ${p.live_here}개와 파일이 겹치지 않습니다` : '— 지금 이 프로젝트에 다른 세션이 없습니다'}</span></label>
      <label class="small muted" for="fmFirst">넣을 첫 글${p.summary_id ? ' (고른 인계 요약은 이 뒤에 붙습니다)' : ''}</label>
      <textarea id="fmFirst" rows="10" class="fm-first">${esc(p.first_prompt || '')}</textarea>
      <details class="fm-why"${(p.confidence ?? 1) < 0.7 ? ' open' : ''}><summary class="small">왜 이렇게 판단했나 · 확신도 ${Math.round((p.confidence ?? 0) * 100)}%</summary>
        ${(p.reasons || []).map((r) => `<div class="small">• ${esc(r)}</div>`).join('')}</details>
      <div class="row fm-row"><span id="fmStartMsg" class="small"></span>
        <button type="button" id="fmAgain" class="ghost">다시 물어보기</button>
        <button type="button" id="fmGo"${p.mode === 'ask' ? ' disabled title="포먼이 되묻고 있습니다 — 답을 요청에 덧붙여 다시 물어보거나 방식을 바꿔 주세요."' : ''}>이대로 시작</button></div>`;
    $('fmPlan').hidden = false;
    $('fmProj').onchange = () => { draw({ ...collect(), summary_id: null }); };
    $('fmMode').onchange = () => { $('fmGo').disabled = $('fmMode').value === 'ask'; };
    $('fmAgain').onclick = ask;
    $('fmGo').onclick = start;
  }
  function collect() {
    const v = (id) => $(id).value;
    return { ...disp.plan, project: v('fmProj'), mode: v('fmMode'), summary_id: v('fmSum') ? Number(v('fmSum')) : null,
             attach_session: v('fmAttach') ? Number(v('fmAttach')) : null, role: v('fmRole'), title: v('fmTitle'),
             read_only: $('fmRO').checked, worktree: $('fmWT').checked, first_prompt: v('fmFirst') };
  }
  async function start() {
    const plan = collect();
    $('fmGo').disabled = true;
    $('fmStartMsg').className = 'small muted';
    $('fmStartMsg').textContent = plan.mode === 'attach' ? '세션에 보내는 중입니다…' : '새 세션을 띄우는 중입니다…';
    try {
      const r = await api('POST', '/api/foreman/start', { dispatch_id: disp.dispatch_id, plan });
      const ok = r.mode === 'attach' ? (r.injected ? '보냈습니다.' : '보냈지만 제출을 확인하지 못했습니다.')
        : `새 세션을 띄웠습니다${r.tmux ? `(tmux ${r.tmux})` : ''}.${r.worktree ? ` 따로 작업 ${r.worktree.branch}에서 합니다.` : ''}${r.injected ? ' 첫 글을 넣었습니다.' : ''}`;
      $('fmStartMsg').className = `small ${r.note ? 'warn' : 'ok'}`;
      $('fmStartMsg').textContent = ok + (r.note ? ' ' + r.note : '');
      if (r.session_id && window.office) setTimeout(() => { dlg.classList.remove('on'); window.office.openSession(r.session_id); }, r.note ? 4000 : 1200);
    } catch (e) {
      $('fmStartMsg').className = 'small bad';
      $('fmStartMsg').textContent = `시작하지 못했습니다 — ${e.message}`;
      $('fmGo').disabled = false;
    }
  }
  $('fmAsk').onclick = ask;
  $('fmText').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); ask(); } });
}

// [+ 세션] 창은 office.js가 처음 그릴 때 만든다 — 생기면 붙는다
const watch = new MutationObserver(() => { const d = document.getElementById('nsDlg'); if (d) { mount(d); watch.disconnect(); } });
watch.observe(document.body, { childList: true });
const d0 = document.getElementById('nsDlg');
if (d0) { mount(d0); watch.disconnect(); }
