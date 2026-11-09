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
  // 11-09 사용자 — "직접 고르기 — … 내가 정한다"로는 뭘 하는지 안 보였다. 하는 일로
  manual.innerHTML = '<summary title="계획 없이 직접 띄우기 — 감독실을 거치지 않고 프로젝트(폴더) · 이름 · 역할 · 시작 방식을 직접 골라 새 세션을 바로 띄웁니다. 계획이 틀렸을 때 씁니다.">계획 없이 직접 띄우기 <span class="muted">— 폴더 · 이름 · 시작 방식을 내가 고릅니다</span></summary>';
  const act = box.querySelector('.ns-act');          // [취소] · [띄우기] 줄은 접지 않는다
  while (h2.nextSibling && h2.nextSibling !== act) manual.appendChild(h2.nextSibling);
  const fm = document.createElement('section');
  fm.className = 'fm';
  fm.innerHTML = `
    <div id="fmWake" class="fm-q" hidden></div>
    <label class="fm-lbl" for="fmText"><b><span id="fmWho">감독</span>에게 말하기</b> <span id="fmRoom" class="muted"></span>
      <span class="muted fm-hint">하려는 일을 적으면 <span id="fmWho2">감독</span> 어느 프로젝트에서 어떻게 할지 계획을 세워 보여 줍니다. 확인해야 세션이 뜹니다.</span></label>
    <textarea id="fmText" rows="6" placeholder="예: 런슈즈 발볼 검증 이어서 · 펫퍼민트 새로 시작 · 빌드 터진 거 봐줘&#10;(Ctrl+Enter로 계획 받기)"></textarea>
    <div class="row fm-row"><button type="button" id="fmAsk" class="primary">계획 받기</button></div>
    <div id="fmMsg" class="fm-status" hidden></div>
    <div id="fmPlan" class="fm-plan" hidden></div>
    <div id="fmHand" class="fm-hand" hidden></div>`;
  h2.after(fm, manual);
  const $ = (id) => box.querySelector('#' + id);
  let disp = null, opts = null, room = null;
  // 상태 글(11-09 사용자 — 버튼 옆 작은 회색 글은 읽기 힘들었다): 입력칸 아래 상자, 기다리는 중이면 움직이는 점
  const msg = (t, cls = 'muted') => {
    const busy = cls === 'muted' && /…/.test(t);
    $('fmMsg').hidden = !t;
    $('fmMsg').className = `fm-status ${busy ? 'busy' : cls}`;
    $('fmMsg').textContent = t;
  };
  const who = () => { $('fmWho').textContent = fmName(); $('fmWho2').textContent = josa(fmName()); };

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
    const t0 = Date.now();
    const wait = () => msg(`${josa(fmName())} 계획을 세우고 있습니다… ${Math.round((Date.now() - t0) / 1000)}초\n프로젝트 상황 · 노트 · 문서를 읽느라 보통 20초쯤 걸립니다.`);
    wait();
    const tick = setInterval(wait, 1000);
    try {
      [disp, opts] = await Promise.all([api('POST', '/api/foreman/plan', { text, project: room }), opts || api('GET', '/api/spawn/options')]);
      clearInterval(tick);
      msg(`계획이 나왔습니다(${Math.round(disp.ms / 1000)}초). 아래에서 확인하고, 고칠 것은 고친 뒤 [이대로 시작]을 누릅니다.`, 'ok');
      draw(disp.plan);
    } catch (e) { clearInterval(tick); msg(`계획을 받지 못했습니다 — ${e.message}\n아래 "계획 없이 직접 띄우기"로 띄울 수 있습니다.`, 'bad'); }
    $('fmAsk').disabled = false;
  }

  // 이미 만든 계획 하나를 연다(자동 제안 · 텔레그램 링크)
  async function load(id) {
    msg('계획을 불러오고 있습니다…');
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
      msg(d.status === 'planned' ? '아래에서 확인하고, 고칠 것은 고친 뒤 [이대로 시작]을 누릅니다.' : `이미 ${d.status === 'started' ? '시작한' : '버린'} 계획입니다.`,
        d.status === 'planned' ? 'ok' : 'warn');
    } catch (e) { msg(`계획을 불러오지 못했습니다 — ${e.message}`, 'bad'); }
  }

  function notesHtml(p) {
    const ups = p.note_updates || [];
    if (!ups.length) return '';
    const line = (o) => o.op === 'retire' ? `${esc(o.was)}${o.why ? ` <span class="muted">— ${esc(o.why)}</span>` : ''}`
      : o.op === 'touch' ? esc(o.was)
      : `${esc(o.body)}${o.op === 'update' ? ` <span class="muted">(전: ${esc(o.was)})</span>` : ''}`;
    // 11-09 사용자 — 접어 두고 몇 개인지만. 펼치면 줄마다 켜고 끄기
    return `<details class="fm-fold fm-notes-box"><summary title="노트 고치기 제안 — ${esc(fmName())}${josa(fmName(), '이', '가')} 이 방 노트(진행 중인 일 · 사람이 정한 판단)를 이렇게 고치자고 합니다. [이대로 시작]을 누를 때 켠 것만 반영합니다.">노트 고치기 제안 ${ups.length}개</summary>
      <div class="fm-notes">${
      ups.map((o, i) => `<label class="small fm-note"><input type="checkbox" data-ni="${i}"${o.on !== false ? ' checked' : ''}>
        <span><b>${OPK[o.op] || o.op}</b> · ${KIND[o.kind] || ''} — ${line(o)} <span class="muted">출처 ${esc(o.source || '이번 요청')}</span></span></label>`).join('')}</div></details>`;
  }
  // "자세히"가 접혀 있어도 지금 값이 보이게 — 접힌 줄에 한 줄 요약
  function moreLine() {
    const sel = (id) => { const e = $(id); return e && e.selectedOptions && e.selectedOptions[0] ? e.selectedOptions[0].textContent : ''; };
    const bits = [sel('fmRole'), sel('fmModel'), $('fmWT').checked ? '따로 작업(worktree)' : '원본 폴더', $('fmRO').checked ? '읽기 전용' : ''];
    if ($('fmMode').value === 'attach') bits.unshift($('fmAttach').value ? `세션 ${$('fmAttach').value}에 보냄` : '보낼 세션을 골라 주세요');
    $('fmMoreSum').textContent = bits.filter(Boolean).join(' · ');
  }
  function modeChanged() {
    const m = $('fmMode').value;
    $('fmGo').disabled = m === 'ask';
    $('fmSumL').hidden = $('fmSum').hidden = m !== 'handoff';   // 넣을 요약 줄은 "요약 넣고 시작"일 때만(라벨 · 칸 둘 다)
    if (m === 'attach') $('fmMore').open = true;      // 보낼 세션은 "자세히" 안에 있다 — 이 방식이면 꼭 필요하니 펼친다
    moreLine();
  }

  function draw(p, status = 'planned') {
    const sums = (opts.summaries || []).filter((s) => !p.project || s.project === p.project);
    const opt = (v, cur, label) => `<option value="${esc(v)}"${String(v) === String(cur ?? '') ? ' selected' : ''}>${esc(label)}</option>`;
    const done = status !== 'planned';
    // 11-09 사용자("칸 8개에 체크박스에 긴 글까지 한 화면에") — 먼저 보이는 것은 프로젝트 · 방식 · 이름 · 넣을 첫 글.
    // 역할 · 모델 · 보낼 세션 · 읽기 전용 · worktree는 [자세히], 노트 제안은 개수만. 칸 id는 그대로(collect가 읽는다)
    const warns = (p.warnings || []).filter((w) => !/^노트 /.test(w));   // 11-09 전 계획에 남은 노트 다듬기 글(지금은 로그로만)
    $('fmPlan').innerHTML = `
      ${warns.length ? `<div class="fm-warn">${warns.map(esc).join('<br>')}</div>` : ''}
      ${(p.questions || []).length ? `<div class="fm-q"><b>${esc(josa(fmName()))} 묻습니다</b>${p.questions.map((q) => `<div>• ${esc(q)}</div>`).join('')}</div>` : ''}
      <div class="fm-grid">
        <label class="muted" for="fmProj">프로젝트</label>
        <select id="fmProj">${(opts.projects || []).map((x) => opt(x.name, p.project, projLabel(x.name))).join('')}</select>
        <label class="muted" for="fmMode">방식</label>
        <select id="fmMode">${Object.entries(MODE).map(([k, v]) => opt(k, p.mode, v)).join('')}</select>
        <label class="muted" id="fmSumL" for="fmSum" title="넣을 요약 — 다른 세션에서 새 세션으로 옮길 때 쓴 요약입니다. 고르면 새 세션의 첫 글 뒤에 붙습니다.">넣을 요약</label>
        <select id="fmSum">${opt('', p.summary_id, '쓰지 않음')}${sums.map((s) => opt(s.id, p.summary_id, `세션 ${s.session_id} · ${s.chars}자 — ${(s.head || s.session || '').slice(0, 50)}`)).join('')}</select>
        <label class="muted" for="fmTitle">이름</label>
        <input id="fmTitle" value="${esc(p.title || '')}">
      </div>
      <label class="muted" for="fmFirst">넣을 첫 글${p.summary_id ? ' (고른 요약은 이 뒤에 붙습니다)' : ''}</label>
      <textarea id="fmFirst" rows="12" class="fm-first">${esc(p.first_prompt || '')}</textarea>
      <details class="fm-fold" id="fmMore"><summary title="자세히 — 역할 · 모델 · 보낼 세션 · 읽기 전용 · 따로 작업(worktree)입니다. 접혀 있어도 오른쪽에 지금 값이 보입니다.">자세히 <span id="fmMoreSum" class="muted"></span></summary>
        <div class="fm-grid">
          <label class="muted" for="fmRole">역할</label>
          <select id="fmRole">${Object.entries(ROLE).map(([k, v]) => opt(k, p.role, v)).join('')}</select>
          <label class="muted" for="fmModel" title="모델 — 역할마다 기본값이 있고 바꿀 수 있습니다(config/models.toml).">모델</label>
          <select id="fmModel">${modelOptions(opts.models, p.model, p.role)}</select>
          <label class="muted" for="fmAttach">보낼 세션</label>
          <input id="fmAttach" value="${esc(p.attach_session ?? '')}" placeholder="방식이 '살아 있는 세션에 보내기'일 때 세션 번호">
        </div>
        <label class="fm-check"><input id="fmRO" type="checkbox"${p.read_only ? ' checked' : ''}> 읽기 전용으로 시작 <span class="muted">— 살펴보기만, 고치기 전에 승인</span></label>
        <label class="fm-check" title="따로 작업 — 저장소 안 .worktrees/에 이 세션만의 폴더 · 브랜치(cc/…)를 만들어 띄웁니다. 끝낸 뒤 [합치기]로 main에 합칩니다."><input id="fmWT" type="checkbox"${p.worktree ? ' checked' : ''}> 따로 작업(worktree)
          <span class="muted">${p.live_here ? `— 이 프로젝트에 살아 있는 세션 ${p.live_here}개와 파일이 겹치지 않습니다` : '— 지금 이 프로젝트에 다른 세션이 없습니다'}</span></label>
      </details>
      ${notesHtml(p)}
      <details class="fm-why"${(p.confidence ?? 1) < 0.7 ? ' open' : ''}><summary class="small">왜 이렇게 판단했나 · 확신도 ${Math.round((p.confidence ?? 0) * 100)}%</summary>
        ${(p.reasons || []).map((r) => `<div class="small">• ${esc(r)}</div>`).join('')}</details>
      <div class="row fm-row"><span id="fmStartMsg" class="small"></span>
        <button type="button" id="fmDrop" class="ghost" title="버리기 — 이 계획을 쓰지 않습니다. 기록에는 '사람이 버림'으로 남습니다."${done ? ' disabled' : ''}>버리기</button>
        <button type="button" id="fmAgain" class="ghost">다시 물어보기</button>
        <button type="button" id="fmGo" class="primary"${p.mode === 'ask' || done ? ` disabled title="${done ? '이미 끝난 계획입니다.' : '되묻는 계획입니다 — 답을 요청에 덧붙여 다시 물어보거나 방식을 바꿔 주세요.'}"` : ''}>이대로 시작</button></div>`;
    $('fmPlan').hidden = false;
    bindRoleModel($('fmRole'), $('fmModel'), opts.models);
    $('fmProj').onchange = () => { draw({ ...collect(), summary_id: null }); };
    $('fmMode').onchange = modeChanged;
    for (const id of ['fmRole', 'fmModel', 'fmAttach', 'fmRO', 'fmWT']) $(id).addEventListener('change', moreLine);
    $('fmAttach').addEventListener('input', moreLine);
    modeChanged();
    if (done) $('fmGo').disabled = true;
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
