// 디스패처에게 말하기(11-05 · 11-08, docs/11_foreman_dispatch.md · docs/14_dispatcher_note_wake.md) — [+ 세션] 창 맨 위.
// "뭘 하려는지" 말하면 디스패처가 계획(프로젝트 · 방식 · 쓸 요약 · 역할 · 이름 · 넣을 첫 글 · 노트 고치기 제안)을 내고, 사람이 보고 고친 뒤
// [이대로 시작]. 원래 창(직접 고르기)은 아래에 접어 둔다 — 디스패처가 틀릴 때 쓴다.
// 감독실 캐릭터(팀장 · 교장 · 소장 · 디스패처)를 누르면 이 창이 그 방의 프로젝트로 열린다(window.foremanChat.open).
// 실패 이벤트가 만든 자동 제안(2단계)은 텔레그램 링크(?dispatch=N) · 캐릭터 말풍선에서 window.foremanChat.openDispatch(N)으로 연다.
// newsession.js를 고치지 않고 그 창(#nsDlg)이 생기면 위에 붙는다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MODE = { new: '새로 시작', handoff: '옮기기용 요약 넣고 시작', attach: '살아 있는 세션에 보내기', ask: '되묻기(시작하지 않음)' };
const OPK = { add: '더하기', update: '바꾸기', retire: '내리기', touch: '아직 맞음' };
const KIND = { thread: '진행 중인 일', decision: '사람이 정한 판단' };
import { ROLE_PICK as ROLE, bindRoleModel, modelOptions } from './modelpick.js';

// 감독실 캐릭터 이름 — 테마마다(오피스 팀장 · 마법학교 교장 · 현장 소장 · 기본 디스패처)
export const fmName = () => (window.office && window.office.theme && window.office.theme.foreman && window.office.theme.foreman.name) || '감독';   // 화면엔 "디스패처"를 쓰지 않는다(11-09)
// 받침을 보고 주격 조사(팀장이 · 디스패처가)
export function josa(w, a = '이', b = '가') {
  const c = String(w).charCodeAt(String(w).length - 1);
  return w + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? a : b);
}
const projLabel = (name) => ((window.foreman && window.foreman.state.projects.find((p) => p.name === name)) || {}).label || name;

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

let ui = null;   // mount가 만든 조작 함수들

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
    <div id="fmWake" class="fm-q" hidden></div>
    <label class="small muted" for="fmText"><span id="fmWho">감독</span>에게 말하기 — 뭘 하려는지 <span id="fmRoom" class="muted"></span></label>
    <textarea id="fmText" rows="2" placeholder="예: 런슈즈 발볼 검증 이어서 · 펫퍼민트 새로 시작 · 빌드 터진 거 봐줘"></textarea>
    <div class="row fm-row"><span id="fmMsg" class="small muted"></span><button type="button" id="fmAsk">계획 받기</button></div>
    <div id="fmPlan" class="fm-plan" hidden></div>
    <div id="fmHand" class="fm-hand" hidden></div>`;
  h2.after(fm, manual);
  const $ = (id) => box.querySelector('#' + id);
  let disp = null, opts = null, room = null;
  const msg = (t, cls = 'muted') => { $('fmMsg').className = `small ${cls}`; $('fmMsg').textContent = t; };
  const who = () => { $('fmWho').textContent = fmName(); };

  function setRoom(p) {
    room = p || null;
    $('fmRoom').innerHTML = room ? `· ${esc(projLabel(room))} 방에서 <button type="button" class="ghost small" id="fmRoomX" title="방 풀기 — 프로젝트도 ${esc(fmName())}${josa(fmName(), '이', '가')} 고르게 합니다.">✕</button>` : '';
    if (room) $('fmRoomX').onclick = () => setRoom(null);
    drawHand();
  }
  // 이 방의 살아 있는 세션 — [세션] 탭 · 맥락 띠와 같은 [넘기고 새로 시작](11-08 사용자 — 이름이 흩어지지 않게 한 버튼)
  function drawHand() {
    const st = window.foreman && window.foreman.state;
    const ss = !room || !st ? [] : [...st.sessions.values()].filter((s) => s.project === room && s.state !== 'DORMANT' && s.injectable);
    $('fmHand').hidden = !ss.length;
    if (!ss.length) { $('fmHand').innerHTML = ''; return; }
    const tip = window.foremanHandoffTip || '새 세션으로 옮기기 — 지금까지를 요약해 보여 드리고, 확인하면 새 세션을 띄워 요약을 넣은 뒤 이 세션을 끝냅니다.';
    $('fmHand').innerHTML = `<div class="small muted">이 방 세션을 새 세션으로 옮기기</div>` + ss.map((s) => {
      const k = s.context && s.context.tokens ? Math.round(s.context.tokens / 1000) : null;
      const lv = s.context && s.context.level;
      return `<div class="fm-hand-row"><span class="small">${esc(s.custom_title || s.title || s.short)}${k != null ? ` · <span class="${lv === 'late' ? 'bad' : lv ? 'warn' : 'muted'}">맥락 ${k}k</span>` : ''}</span>
        <button type="button" class="small" data-hand="${s.id}" title="${esc(tip)}">새 세션으로 옮기기</button></div>`;
    }).join('');
  }
  $('fmHand').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-hand]');
    if (!b || !window.foremanHandoff) return;
    dlg.classList.remove('on');
    window.foremanHandoff.start(Number(b.dataset.hand));
  });
  function reset(project) {
    who();
    disp = null;
    $('fmWake').hidden = true;
    $('fmPlan').hidden = true;
    $('fmAsk').disabled = false;
    msg('');
    setRoom(project);
  }

  async function ask() {
    const text = $('fmText').value.trim();
    if (!text) { msg('뭘 하려는지 적어 주세요.', 'bad'); return; }
    $('fmAsk').disabled = true; $('fmPlan').hidden = true; $('fmWake').hidden = true;
    msg(`${josa(fmName())} 상황을 보고 계획을 세우는 중입니다… (20초 안팎)`);
    try {
      [disp, opts] = await Promise.all([api('POST', '/api/foreman/plan', { text, project: room }), opts || api('GET', '/api/spawn/options')]);
      msg(`계획이 나왔습니다(${Math.round(disp.ms / 1000)}초). 확인하고 고칠 것은 고친 뒤 시작해 주세요.`, 'ok');
      draw(disp.plan);
    } catch (e) { msg(`계획을 받지 못했습니다 — ${e.message}. 아래 "직접 고르기"를 쓸 수 있습니다.`, 'bad'); }
    $('fmAsk').disabled = false;
  }

  // 이미 만든 계획 하나를 연다(자동 제안 · 텔레그램 링크)
  async function load(id) {
    msg('계획을 불러오는 중입니다…');
    try {
      const [d, o] = await Promise.all([api('GET', `/api/foreman/dispatch/${id}`), opts || api('GET', '/api/spawn/options')]);
      opts = o;
      setRoom(d.project);
      $('fmText').value = d.origin === 'wake' ? '' : d.request;
      if (d.origin === 'wake') {
        $('fmWake').hidden = false;
        $('fmWake').innerHTML = `<b>실패 이벤트가 부른 제안입니다</b><div>• ${esc(d.wake_text || '')}</div>
          <div class="small muted">${esc(josa(fmName()))} 계획만 세웠습니다. [이대로 시작]을 눌러야 시작합니다.</div>`;
      }
      if (!d.plan) { msg(`이 계획은 만들어지지 못했습니다 — ${d.error || d.status}`, 'bad'); return; }
      disp = { dispatch_id: d.dispatch_id, plan: d.plan };
      draw(d.plan, d.status);
      msg(d.status === 'planned' ? '확인하고 고칠 것은 고친 뒤 시작해 주세요.' : `이미 ${d.status === 'started' ? '시작한' : '버린'} 계획입니다.`,
        d.status === 'planned' ? 'ok' : 'warn');
    } catch (e) { msg(`계획을 불러오지 못했습니다 — ${e.message}`, 'bad'); }
  }

  function notesHtml(p) {
    const ups = p.note_updates || [];
    if (!ups.length) return '';
    const line = (o) => o.op === 'retire' ? `${esc(o.was)}${o.why ? ` <span class="muted">— ${esc(o.why)}</span>` : ''}`
      : o.op === 'touch' ? esc(o.was)
      : `${esc(o.body)}${o.op === 'update' ? ` <span class="muted">(전: ${esc(o.was)})</span>` : ''}`;
    return `<div class="fm-notes"><div class="small"><b>노트 고치기 제안</b> <span class="muted">— [이대로 시작]을 누를 때 켠 것만 반영합니다</span></div>${
      ups.map((o, i) => `<label class="small fm-note"><input type="checkbox" data-ni="${i}"${o.on !== false ? ' checked' : ''}>
        <span><b>${OPK[o.op] || o.op}</b> · ${KIND[o.kind] || ''} — ${line(o)} <span class="muted">출처 ${esc(o.source || '이번 요청')}</span></span></label>`).join('')}</div>`;
  }

  function draw(p, status = 'planned') {
    const sums = (opts.summaries || []).filter((s) => !p.project || s.project === p.project);
    const opt = (v, cur, label) => `<option value="${esc(v)}"${String(v) === String(cur ?? '') ? ' selected' : ''}>${esc(label)}</option>`;
    const done = status !== 'planned';
    $('fmPlan').innerHTML = `
      ${(p.warnings || []).length ? `<div class="small warn">${p.warnings.map(esc).join('<br>')}</div>` : ''}
      ${(p.questions || []).length ? `<div class="fm-q"><b>${esc(josa(fmName()))} 묻습니다</b>${p.questions.map((q) => `<div>• ${esc(q)}</div>`).join('')}</div>` : ''}
      <div class="fm-grid">
        <label class="small muted">프로젝트</label>
        <select id="fmProj">${(opts.projects || []).map((x) => opt(x.name, p.project, projLabel(x.name))).join('')}</select>
        <label class="small muted">방식</label>
        <select id="fmMode">${Object.entries(MODE).map(([k, v]) => opt(k, p.mode, v)).join('')}</select>
        <label class="small muted" title="넣을 요약 — 다른 세션에서 새 세션으로 옮길 때 쓴 요약입니다. 고르면 새 세션의 첫 글 뒤에 붙습니다.">넣을 요약</label>
        <select id="fmSum">${opt('', p.summary_id, '쓰지 않음')}${sums.map((s) => opt(s.id, p.summary_id, `세션 ${s.session_id} · ${s.chars}자 — ${(s.head || s.session || '').slice(0, 50)}`)).join('')}</select>
        <label class="small muted">보낼 세션</label>
        <input id="fmAttach" value="${esc(p.attach_session ?? '')}" placeholder="방식이 '살아 있는 세션에 보내기'일 때 세션 번호">
        <label class="small muted">역할</label>
        <select id="fmRole">${Object.entries(ROLE).map(([k, v]) => opt(k, p.role, v)).join('')}</select>
        <label class="small muted" title="모델 — 역할마다 기본값이 있고 바꿀 수 있습니다(config/models.toml).">모델</label>
        <select id="fmModel">${modelOptions(opts.models, p.model, p.role)}</select>
        <label class="small muted">이름</label>
        <input id="fmTitle" value="${esc(p.title || '')}">
      </div>
      <label class="small"><input id="fmRO" type="checkbox"${p.read_only ? ' checked' : ''}> 읽기 전용으로 시작(살펴보기만 — 고치기 전에 승인)</label>
      <label class="small" title="따로 작업 — 저장소 안 .worktrees/에 이 세션만의 폴더 · 브랜치(cc/…)를 만들어 띄웁니다. 끝낸 뒤 [합치기]로 main에 합칩니다."><input id="fmWT" type="checkbox"${p.worktree ? ' checked' : ''}> 따로 작업(worktree)
        <span class="muted">${p.live_here ? `— 이 프로젝트에 살아 있는 세션 ${p.live_here}개와 파일이 겹치지 않습니다` : '— 지금 이 프로젝트에 다른 세션이 없습니다'}</span></label>
      <label class="small muted" for="fmFirst">넣을 첫 글${p.summary_id ? ' (고른 요약은 이 뒤에 붙습니다)' : ''}</label>
      <textarea id="fmFirst" rows="10" class="fm-first">${esc(p.first_prompt || '')}</textarea>
      ${notesHtml(p)}
      <details class="fm-why"${(p.confidence ?? 1) < 0.7 ? ' open' : ''}><summary class="small">왜 이렇게 판단했나 · 확신도 ${Math.round((p.confidence ?? 0) * 100)}%</summary>
        ${(p.reasons || []).map((r) => `<div class="small">• ${esc(r)}</div>`).join('')}</details>
      <div class="row fm-row"><span id="fmStartMsg" class="small"></span>
        <button type="button" id="fmDrop" class="ghost" title="버리기 — 이 계획을 쓰지 않습니다. 기록에는 '사람이 버림'으로 남습니다."${done ? ' disabled' : ''}>버리기</button>
        <button type="button" id="fmAgain" class="ghost">다시 물어보기</button>
        <button type="button" id="fmGo"${p.mode === 'ask' || done ? ` disabled title="${done ? '이미 끝난 계획입니다.' : '되묻는 계획입니다 — 답을 요청에 덧붙여 다시 물어보거나 방식을 바꿔 주세요.'}"` : ''}>이대로 시작</button></div>`;
    $('fmPlan').hidden = false;
    bindRoleModel($('fmRole'), $('fmModel'), opts.models);
    $('fmProj').onchange = () => { draw({ ...collect(), summary_id: null }); };
    $('fmMode').onchange = () => { $('fmGo').disabled = $('fmMode').value === 'ask'; };
    $('fmAgain').onclick = () => { if (!$('fmText').value.trim() && disp) $('fmText').value = (box.querySelector('#fmWake div') || {}).textContent || ''; ask(); };
    $('fmGo').onclick = start;
    $('fmDrop').onclick = drop;
  }
  function collect() {
    const v = (id) => $(id).value;
    const ups = (disp.plan.note_updates || []).map((o, i) => {
      const cb = box.querySelector(`input[data-ni="${i}"]`);
      return { ...o, on: cb ? cb.checked : o.on !== false };
    });
    return { ...disp.plan, project: v('fmProj'), mode: v('fmMode'), summary_id: v('fmSum') ? Number(v('fmSum')) : null,
             attach_session: v('fmAttach') ? Number(v('fmAttach')) : null, role: v('fmRole'), model: v('fmModel') || null, title: v('fmTitle'),
             read_only: $('fmRO').checked, read_only_set: true, worktree: $('fmWT').checked, first_prompt: v('fmFirst'), note_updates: ups };
  }
  async function start() {
    const plan = collect();
    $('fmGo').disabled = true;
    $('fmStartMsg').className = 'small muted';
    $('fmStartMsg').textContent = plan.mode === 'attach' ? '세션에 보내는 중입니다…' : '새 세션을 띄우는 중입니다…';
    try {
      const r = await api('POST', '/api/foreman/start', { dispatch_id: disp.dispatch_id, plan });
      const ok = r.mode === 'attach' ? (r.injected ? '보냈습니다.' : '보냈지만 제출을 확인하지 못했습니다.')
        : `새 세션을 띄웠습니다${r.tmux ? `(tmux ${r.tmux}${r.model ? ' · ' + r.model : ''})` : ''}.${r.worktree ? ` 따로 작업 ${r.worktree.branch}에서 합니다.` : ''}${r.injected ? ' 첫 글을 넣었습니다.' : ''}`;
      $('fmStartMsg').className = `small ${r.note ? 'warn' : 'ok'}`;
      $('fmStartMsg').textContent = ok + (r.notes ? ` 노트 ${r.notes}줄을 고쳤습니다.` : '') + (r.note ? ' ' + r.note : '');
      $('fmDrop').disabled = true;
      if (r.session_id && window.office) setTimeout(() => { dlg.classList.remove('on'); window.office.openSession(r.session_id); }, r.note ? 4000 : 1200);
    } catch (e) {
      $('fmStartMsg').className = 'small bad';
      $('fmStartMsg').textContent = `시작하지 못했습니다 — ${e.message}`;
      $('fmGo').disabled = false;
    }
  }
  async function drop() {
    try {
      await api('POST', `/api/foreman/dispatch/${disp.dispatch_id}/discard`);
      $('fmStartMsg').className = 'small muted';
      $('fmStartMsg').textContent = '버렸습니다.';
      $('fmGo').disabled = true; $('fmDrop').disabled = true;
    } catch (e) { $('fmStartMsg').className = 'small bad'; $('fmStartMsg').textContent = `버리지 못했습니다 — ${e.message}`; }
  }
  $('fmAsk').onclick = ask;
  $('fmText').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); ask(); } });
  who();
  ui = { reset, load, focus: () => $('fmText').focus() };
}

// 감독실 캐릭터 · 말풍선 · 텔레그램 링크가 부른다 — [+ 세션] 창을 열고 위의 말하기 칸으로
async function open(project) {
  if (!window.office || !window.office.newSession) return;
  await window.office.newSession(project || null);
  if (!ui) { const d = document.getElementById('nsDlg'); if (d) mount(d); }
  if (!ui) return;
  const manual = document.querySelector('#nsDlg .fm-manual');
  if (manual) manual.open = false;
  ui.reset(project || null);
  ui.focus();
}
async function openDispatch(id) {
  await open(null);
  if (ui) await ui.load(id);
}
window.foremanChat = { open, openDispatch };

// [+ 세션] 창은 office.js가 처음 그릴 때 만든다 — 생기면 붙는다
const watch = new MutationObserver(() => { const d = document.getElementById('nsDlg'); if (d) { mount(d); watch.disconnect(); } });
watch.observe(document.body, { childList: true });
const d0 = document.getElementById('nsDlg');
if (d0) { mount(d0); watch.disconnect(); }
