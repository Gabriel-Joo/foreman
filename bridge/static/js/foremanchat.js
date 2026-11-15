// 디스패처에게 말하기(11-05 · 11-08, docs/11_foreman_dispatch.md · docs/14_dispatcher_note_wake.md) — [+ 세션] 창 맨 위.
// "뭘 하려는지" 말하면 디스패처가 계획(프로젝트 · 방식 · 쓸 요약 · 역할 · 이름 · 넣을 첫 글 · 진행 중인 일 고치기 제안)을 내고, 사람이 보고 고친 뒤
// [이대로 시작]. 원래 창(직접 고르기)은 아래에 접어 둔다 — 디스패처가 틀릴 때 쓴다.
// 감독실 캐릭터(팀장 · 교장 · 소장 · 디스패처)를 누르면 이 창이 그 방의 프로젝트로 열린다(window.foremanChat.open).
// 실패 이벤트가 만든 자동 제안(2단계)은 텔레그램 링크(?dispatch=N) · 캐릭터 말풍선에서 window.foremanChat.openDispatch(N)으로 연다.
// newsession.js를 고치지 않고 그 창(#nsDlg)이 생기면 위에 붙는다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MODE = { new: '새로 시작', handoff: '옮기기용 요약 넣고 시작', attach: '살아 있는 세션에 보내기', ask: '되묻기(시작하지 않음)' };
const OPK = { add: '더하기', update: '바꾸기', retire: '내리기', touch: '아직 맞음' };
import { ROLE_PICK as ROLE, bindRoleModel, modelOptions } from './modelpick.js';

// 감독실 캐릭터 이름 — 테마마다(오피스 팀장 · 마법학교 교장 · 현장 소장 · 기본 디스패처)
export const fmName = () => (window.office && window.office.theme && window.office.theme.foreman && window.office.theme.foreman.name) || '감독';   // 화면엔 "디스패처"를 쓰지 않는다(11-09)
// 받침을 보고 주격 조사(팀장이 · 디스패처가)
export function josa(w, a = '이', b = '가') {
  const c = String(w).charCodeAt(String(w).length - 1);
  return w + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? a : b);
}
// [버리기]가 할 일(11-10) — 계획(dispatch)이 있고 아직 'planned'일 때만 서버에 버림을 적는다. 계획을 못 받았으면(실패한 계획은
// 서버에 'failed'로 이미 남는다) 서버를 부르지 않고 카드만 치운다
// 창을 새로 열 때 입력 칸(11-11) — 계획으로 보낸 글이면 비우고, 보내지 않은 초안은 그대로(조용히 날리지 않는다)
export const freshText = (sent, value) => (sent ? '' : value || '');
// 11-11 맡을 파일 — 칸에는 쉼표로, 서버에는 배열로
export const parseFiles = (s) => [...new Set(String(s || '').split(/[,\n]/).map((x) => x.trim()).filter(Boolean))];
export const filesText = (a) => (Array.isArray(a) ? a.join(', ') : String(a || ''));
// 시작 결과 — 세션이 둘 이상이면 세션마다 한 마디(못 띄운 것은 note에 서버가 적는다)
export const startedLine = (r) => {
  const ss = (r.sessions || []).filter((s) => s.session_id);
  if (ss.length < 2) return '';
  return ` 띄운 세션 ${ss.length}개: ${ss.map((s) => `${s.idx + 1}「${s.title || s.role}」${s.tmux ? `(tmux ${s.tmux}${s.model ? ' · ' + s.model : ''})` : ''}`).join(', ')}.`;
};
// [관리자에게 보내기] 단추 — 켜져 있고(handover) 새로 띄우는 계획일 때. 그 프로젝트 관리자가 없으면 누르지 못하게 하고 까닭을 툴팁에
export function handButton(st, project, mode, done) {
  if (!st || !st.enabled || mode === 'attach') return { show: false, disabled: true, tip: '' };
  const sid = (st.managers || {})[project];
  if (done) return { show: true, disabled: true, tip: '관리자에게 보내기 — 이미 끝난 계획입니다.' };
  if (mode === 'ask') return { show: true, disabled: true, tip: '관리자에게 보내기 — 되묻는 계획은 보낼 수 없습니다.' };
  if (!sid) return { show: true, disabled: true, tip: `관리자에게 보내기 — ${projLabel(project)}에 관리자 세션이 없습니다. [이대로 시작]으로 직접 띄웁니다.` };
  return { show: true, disabled: false, tip: `관리자에게 보내기 — 고친 계획을 ${projLabel(project)} 관리자(세션 ${sid})에게 넘깁니다. 관리자가 띄우고, ${st.wait_min || 15}분 안에 띄우지 않으면 알립니다.` };
}
export const dropAction =(disp) => (disp && disp.dispatch_id != null && (disp.status || 'planned') === 'planned' ? 'server' : 'clear');
const projLabel = (name) => ((typeof window !== 'undefined' && window.foreman &&window.foreman.state.projects.find((p) => p.name === name)) || {}).label || name;

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
  manual.innerHTML = '<summary title="계획 없이 직접 띄우기 — 감독실을 거치지 않고 프로젝트(폴더) · 이름 · 역할 · 시작 방식을 직접 골라 새 세션을 바로 띄웁니다. 계획이 틀렸을 때 씁니다.">계획 없이 직접 띄우기 <span class="muted">(폴더 · 이름 · 시작 방식을 내가 고릅니다)</span></summary>';
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
  let inboxIds = [];       // 받은 할 일에서 연 계획(11-09 하나 · 11-11 여럿) — [이대로 시작]하면 그 세션이 가져간다(창을 다시 열면 풀린다)
  let sent = false;        // 11-11 이 칸의 글을 계획으로 보냈는가 — 보낸 글은 창을 다시 열면 비운다(보내지 않은 초안은 남긴다)
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
  // 이 방의 살아 있는 세션 — [세션 정리] 탭 · 맥락 띠와 같은 [넘기고 새로 시작](11-08 사용자 — 이름이 흩어지지 않게 한 버튼)
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
  // 계획 카드와 그 계획(disp)은 함께 치운다(11-10) — 전에는 disp만 비우고 카드는 남아(.fm-plan의 display가 hidden을 덮었다)
  // 계획을 못 받은 뒤 남은 옛 카드의 [버리기]가 "disp is null"로 실패했다
  function clearPlan() {
    disp = null;
    $('fmPlan').hidden = true;
    $('fmPlan').innerHTML = '';
  }
  // 창을 새로 열 때(11-11 사용자 — 계획을 받고 세션을 띄운 뒤에도 다시 열면 지난 글이 그대로 있었다)
  function fresh() {
    $('fmText').value = freshText(sent, $('fmText').value);
    sent = false;
    clearPlan();
    msg('');
  }
  function reset(project) {
    who();
    fresh();
    inboxIds = [];
    $('fmWake').hidden = true;
    $('fmAsk').disabled = false;
    msg('');
    setRoom(project);
  }

  async function ask() {
    const text = $('fmText').value.trim();
    if (!text) { msg('뭘 하려는지 적어 주세요.', 'bad'); return; }
    if ($('fmAsk').disabled) return;        // Ctrl+Enter · [다시 물어보기]도 여기로 — 이미 묻는 중이면 겹치지 않는다
    sent = true;
    $('fmAsk').disabled = true; clearPlan(); $('fmWake').hidden = true;
    const t0 = Date.now();
    const wait = () => msg(`${josa(fmName())} 계획을 세우고 있습니다… ${Math.round((Date.now() - t0) / 1000)}초\n프로젝트 상황 · 진행 중인 일 · 문서를 읽느라 보통 20초쯤 걸립니다.`);
    wait();
    const tick = setInterval(wait, 1000);
    try {
      const [d, o] = await Promise.all([api('POST', '/api/foreman/plan', { text, project: room }), opts || api('GET', '/api/spawn/options')]);
      clearInterval(tick);
      disp = d; opts = o;
      msg(`계획이 나왔습니다(${Math.round(disp.ms / 1000)}초). 아래에서 확인하고, 고칠 것은 고친 뒤 [이대로 시작]을 누릅니다.`, 'ok');
      draw(disp.plan);
    } catch (e) { clearInterval(tick); msg(`계획을 받지 못했습니다: ${e.message}\n아래 "계획 없이 직접 띄우기"로 띄울 수 있습니다.`, 'bad'); }
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
      sent = true;                         // 이미 보낸 요청 — 다음에 열면 비운다
      if (d.origin === 'wake') {
        $('fmWake').hidden = false;
        $('fmWake').innerHTML = `<b>실패 이벤트가 부른 제안입니다</b><div>• ${esc(d.wake_text || '')}</div>
          <div class="small muted">${esc(josa(fmName()))} 계획만 세웠습니다. [이대로 시작]을 눌러야 시작합니다.</div>`;
      }
      if (!d.plan) { clearPlan(); msg(`이 계획은 만들어지지 못했습니다: ${d.error || d.status}`, 'bad'); return; }
      disp = { dispatch_id: d.dispatch_id, plan: d.plan, status: d.status };
      draw(d.plan, d.status);
      msg(d.status === 'planned' ? '아래에서 확인하고, 고칠 것은 고친 뒤 [이대로 시작]을 누릅니다.' : `이미 ${d.status === 'started' ? '시작한' : '버린'} 계획입니다.`,
        d.status === 'planned' ? 'ok' : 'warn');
      if (d.handed && d.status === 'planned') {
        msg(`관리자(세션 ${d.handed.to_session})에게 넘긴 계획입니다. 관리자가 아직 띄우지 않았습니다${d.handed.alerted ? '(오래 지나 알렸습니다)' : ''}. 직접 띄우려면 [이대로 시작]을 누릅니다.`, 'warn');
      }
    } catch (e) { msg(`계획을 불러오지 못했습니다: ${e.message}`, 'bad'); }
  }

  function notesHtml(p) {
    const ups = p.note_updates || [];
    if (!ups.length) return '';
    const line = (o) => o.op === 'retire' ? `${esc(o.was)}${o.why ? ` <span class="muted">(${esc(o.why)})</span>` : ''}`
      : o.op === 'touch' ? esc(o.was)
      : `${esc(o.body)}${o.op === 'update' ? ` <span class="muted">(전: ${esc(o.was)})</span>` : ''}`;
    // 11-09 사용자 — 접어 두고 몇 개인지만. 펼치면 줄마다 켜고 끄기
    return `<details class="fm-fold fm-notes-box"><summary title="진행 중인 일 고치기 제안 — ${esc(fmName())}${josa(fmName(), '이', '가')} 이 방의 진행 중인 일을 이렇게 고치자고 합니다. [이대로 시작]을 누를 때 켠 것만 반영합니다.">진행 중인 일 고치기 제안 ${ups.length}개</summary>
      <div class="fm-notes">${
      ups.map((o, i) => `<label class="small fm-note"><input type="checkbox" data-ni="${i}"${o.on !== false ? ' checked' : ''}>
        <span><b>${OPK[o.op] || o.op}</b>: ${line(o)} <span class="muted">출처 ${esc(o.source || '이번 요청')}</span></span></label>`).join('')}</div></details>`;
  }
  // "자세히"가 접혀 있어도 지금 값이 보이게 — 접힌 줄에 한 줄 요약
  function moreLine() {
    const sel = (id) => { const e = $(id); return e && e.selectedOptions && e.selectedOptions[0] ? e.selectedOptions[0].textContent : ''; };
    const bits = [sel('fmRole'), sel('fmModel'), $('fmWT').checked ? '작업방' : '원본 폴더', $('fmRO').checked ? '읽기 전용' : ''];
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
    // 11-11 한 계획에 여러 세션 — 첫 세션은 위 칸(칸 id 그대로), 둘째부터는 아래 세션 칸. 옛 계획은 sessions가 없어 하나
    const ss = (p.sessions && p.sessions.length) ? p.sessions : [p];
    const s0 = ss[0];
    const many = ss.length > 1 && p.mode !== 'attach';
    $('fmPlan').innerHTML = `
      ${warns.length ? `<div class="fm-warn">${warns.map(esc).join('<br>')}</div>` : ''}
      ${(p.questions || []).length ? `<div class="fm-q"><b>${esc(josa(fmName()))} 묻습니다</b>${p.questions.map((q) => `<div>• ${esc(q)}</div>`).join('')}</div>` : ''}
      <div class="fm-grid">
        <label class="muted" for="fmProj">프로젝트</label>
        <select id="fmProj">${(opts.projects || []).map((x) => opt(x.name, p.project, projLabel(x.name))).join('')}</select>
        <label class="muted" for="fmMode">방식</label>
        <select id="fmMode">${Object.entries(MODE).map(([k, v]) => opt(k, p.mode, v)).join('')}</select>
        <label class="muted" id="fmSumL" for="fmSum" title="넣을 요약 — 다른 세션에서 새 세션으로 옮길 때 쓴 요약입니다. 고르면 새 세션의 첫 글 뒤에 붙습니다.">넣을 요약</label>
        <select id="fmSum">${opt('', p.summary_id, '쓰지 않음')}${sums.map((s) => opt(s.id, p.summary_id, `세션 ${s.session_id} · ${s.chars}자: ${(s.head || s.session || '').slice(0, 50)}`)).join('')}</select>
        <label class="muted" for="fmTitle">이름</label>
        <input id="fmTitle" value="${esc(p.title || '')}">
      </div>
      <label class="muted" for="fmFirst">넣을 첫 글${p.summary_id ? ' (고른 요약은 이 뒤에 붙습니다)' : ''}</label>
      <textarea id="fmFirst" rows="12" class="fm-first">${esc(p.first_prompt || '')}</textarea>
      <details class="fm-fold" id="fmMore"><summary title="자세히 — 역할 · 모델 · 보낼 세션 · 읽기 전용 · 작업방입니다. 접혀 있어도 오른쪽에 지금 값이 보입니다.">자세히 <span id="fmMoreSum" class="muted"></span></summary>
        <div class="fm-grid">
          <label class="muted" for="fmRole">역할</label>
          <select id="fmRole">${Object.entries(ROLE).map(([k, v]) => opt(k, p.role, v)).join('')}</select>
          <label class="muted" for="fmModel" title="모델 — 역할마다 기본값이 있고 바꿀 수 있습니다(config/models.toml).">모델</label>
          <select id="fmModel">${modelOptions(opts.models, p.model, p.role)}</select>
          <label class="muted" for="fmAttach">보낼 세션</label>
          <input id="fmAttach" value="${esc(p.attach_session ?? '')}" placeholder="방식이 '살아 있는 세션에 보내기'일 때 세션 번호">
          <label class="muted" for="fmFiles" title="맡을 파일 — 이 세션이 고칠 파일입니다. 살아 있는 세션 · 다른 계획과 겹치면 위 경고에 뜹니다.">맡을 파일</label>
          <input id="fmFiles" value="${esc(filesText(s0.files))}" placeholder="쉼표로 나눔 (예: bridge/foreman.py, migrations/)">
          ${many ? `<label class="muted" for="fmOrder" title="합칠 순서 — 작은 것부터 합칩니다. 맡을 파일이 겹칠 때 먼저 합칠 세션을 정합니다.">합칠 순서</label>
          <input id="fmOrder" type="number" min="1" max="99" value="${esc(s0.merge_order ?? 1)}">` : ''}
        </div>
        <label class="fm-check"><input id="fmRO" type="checkbox"${p.read_only ? ' checked' : ''}> 읽기 전용으로 시작 <span class="muted">(살펴보기만, 고치기 전에 승인)</span></label>
        <label class="fm-check" title="작업방 — 저장소 안 .worktrees/에 이 세션만의 폴더 · 브랜치(cc/…)를 만들어 띄웁니다. 끝낸 뒤 [합치기]로 main에 합칩니다."><input id="fmWT" type="checkbox"${p.worktree ? ' checked' : ''}> 작업방
          <span class="muted">${p.live_here ? `(이 프로젝트에 살아 있는 세션 ${p.live_here}개와 파일이 겹치지 않습니다)` : '(지금 이 프로젝트에 다른 세션이 없습니다)'}</span></label>
      </details>
      ${many ? sessionsHtml(ss, opt) : ''}
      ${notesHtml(p)}
      <details class="fm-why"${(p.confidence ?? 1) < 0.7 ? ' open' : ''}><summary class="small">왜 이렇게 판단했나 · 확신도 ${Math.round((p.confidence ?? 0) * 100)}%</summary>
        ${(p.reasons || []).map((r) => `<div class="small">• ${esc(r)}</div>`).join('')}</details>
      <div class="row fm-row"><span id="fmStartMsg" class="small"></span>
        <button type="button" id="fmDrop" class="ghost" title="버리기 — 이 계획을 쓰지 않습니다. 기록에는 '사람이 버림'으로 남습니다."${done ? ' disabled' : ''}>버리기</button>
        <button type="button" id="fmAgain" class="ghost">다시 물어보기</button>
        <button type="button" id="fmHand" class="ghost" hidden>관리자에게 보내기</button>
        <button type="button" id="fmGo" class="primary"${p.mode === 'ask' || done ? ` disabled title="${done ? '이미 끝난 계획입니다.' : '되묻는 계획입니다. 답을 요청에 덧붙여 다시 물어보거나 방식을 바꿔 주세요.'}"` : ''}>이대로 시작</button></div>`;
    $('fmPlan').hidden = false;
    bindRoleModel($('fmRole'), $('fmModel'), opts.models);
    for (const el of box.querySelectorAll('.fm-sess')) {
      bindRoleModel(el.querySelector('[data-k=role]'), el.querySelector('[data-k=model]'), opts.models);
      const sum = () => { el.querySelector('[data-sum]').textContent = sessLine(el); };
      el.addEventListener('change', sum); el.addEventListener('input', sum); sum();
    }
    $('fmProj').onchange = () => { draw({ ...collect(), summary_id: null }); };
    $('fmMode').onchange = modeChanged;
    for (const id of ['fmRole', 'fmModel', 'fmAttach', 'fmRO', 'fmWT']) $(id).addEventListener('change', moreLine);
    $('fmAttach').addEventListener('input', moreLine);
    modeChanged();
    if (done) $('fmGo').disabled = true;
    $('fmAgain').onclick = () => { if (!$('fmText').value.trim() && disp) $('fmText').value = (box.querySelector('#fmWake div') || {}).textContent || ''; ask(); };
    $('fmGo').onclick = start;
    $('fmDrop').onclick = drop;
    $('fmHand').onclick = handOver;
    showHand(p, done);
  }
  // 11-11 [관리자에게 보내기] — config/managers.toml [handover]가 켜져 있을 때만 보인다(GET /api/foreman/handover)
  let handState = null;
  async function showHand(p, done) {
    const b = $('fmHand');
    if (!b) return;
    try { handState = handState || await api('GET', '/api/foreman/handover'); } catch { handState = { enabled: false }; }
    const v = handButton(handState, $('fmProj') ? $('fmProj').value : p.project, p.mode, done);
    b.hidden = !v.show; b.disabled = v.disabled; b.title = v.tip;
  }
  async function handOver() {
    const plan = collect();
    $('fmHand').disabled = true; $('fmGo').disabled = true;
    $('fmStartMsg').className = 'small muted';
    $('fmStartMsg').textContent = '관리자에게 보내는 중입니다…';
    try {
      const r = await api('POST', '/api/foreman/handover', { dispatch_id: disp.dispatch_id, plan, ...(inboxIds.length ? { inbox_ids: inboxIds } : {}) });
      $('fmStartMsg').className = `small ${r.handed ? 'ok' : 'warn'}`;
      $('fmStartMsg').textContent = r.note || (r.handed ? '보냈습니다.' : `보내지 못했습니다: ${r.reason}`);
      if (!r.handed) { $('fmGo').disabled = false; $('fmHand').disabled = false; }
    } catch (e) {
      $('fmStartMsg').className = 'small bad';
      $('fmStartMsg').textContent = `보내지 못했습니다: ${e.message}. [이대로 시작]으로 직접 띄울 수 있습니다.`;
      $('fmGo').disabled = false; $('fmHand').disabled = false;
    }
  }
  // 11-11 세션 칸(둘째부터) — 칸마다 data-k로 읽는다
  function sessionsHtml(ss, opt) {
    const on0 = ss[0].on !== false;
    return `<div class="fm-sessions">
      <div class="small muted">세션 ${ss.length}개입니다. 세션 1은 위 칸입니다. 끈 세션은 띄우지 않습니다.</div>
      <label class="fm-check" title="세션 1 띄우기 — 끄면 위 칸의 세션은 띄우지 않습니다."><input id="fmOn0" type="checkbox"${on0 ? ' checked' : ''}> 세션 1 띄우기 <span class="muted">(${esc(ss[0].title || '')})</span></label>
      ${ss.slice(1).map((s, j) => { const i = j + 1; return `<div class="fm-sess" data-si="${i}">
        <label class="fm-check" title="세션 ${i + 1} 띄우기 — 끄면 이 세션은 띄우지 않습니다."><input type="checkbox" data-k="on"${s.on !== false ? ' checked' : ''}> 세션 ${i + 1} 띄우기 <span class="muted" data-sum></span></label>
        <details class="fm-fold"><summary title="세션 ${i + 1} — 펼쳐서 이름 · 역할 · 모델 · 맡을 파일 · 첫 글을 고칩니다.">세션 ${i + 1} 고치기</summary>
          <div class="fm-grid">
            <label class="muted">이름</label><input data-k="title" value="${esc(s.title || '')}">
            <label class="muted">역할</label><select data-k="role">${Object.entries(ROLE).map(([k, v]) => opt(k, s.role, v)).join('')}</select>
            <label class="muted" title="모델 — 역할마다 기본값이 있고 바꿀 수 있습니다(config/models.toml).">모델</label><select data-k="model">${modelOptions(opts.models, s.model, s.role)}</select>
            <label class="muted" title="맡을 파일 — 이 세션이 고칠 파일입니다. 다른 세션과 겹치면 위 경고에 뜹니다.">맡을 파일</label><input data-k="files" value="${esc(filesText(s.files))}" placeholder="쉼표로 나눔">
            <label class="muted" title="합칠 순서 — 작은 것부터 합칩니다.">합칠 순서</label><input data-k="merge_order" type="number" min="1" max="99" value="${esc(s.merge_order ?? i + 1)}">
          </div>
          <label class="muted">넣을 첫 글</label>
          <textarea data-k="first_prompt" rows="8" class="fm-first">${esc(s.first_prompt || '')}</textarea>
          <label class="fm-check"><input type="checkbox" data-k="read_only"${s.read_only ? ' checked' : ''}> 읽기 전용으로 시작 <span class="muted">(살펴보기만, 고치기 전에 승인)</span></label>
          <label class="fm-check" title="작업방 — 이 세션만의 폴더 · 브랜치(cc/…)에서 띄웁니다. 둘째 세션부터는 기본으로 켭니다."><input type="checkbox" data-k="worktree"${s.worktree !== false ? ' checked' : ''}> 작업방</label>
        </details></div>`; }).join('')}
    </div>`;
  }
  function sessLine(el) {
    const q = (k) => el.querySelector(`[data-k=${k}]`);
    const t = (sel) => (sel && sel.selectedOptions && sel.selectedOptions[0] ? sel.selectedOptions[0].textContent.split(' — ')[0] : '');
    const n = parseFiles(q('files').value).length;
    return `(${q('title').value || '이름 없음'} · ${t(q('role'))} · ${t(q('model')) || '기본 모델'}${n ? ` · 맡을 파일 ${n}개` : ''})`;
  }
  function collect() {
    const v = (id) => $(id).value;
    const ups = (disp.plan.note_updates || []).map((o, i) => {
      const cb = box.querySelector(`input[data-ni="${i}"]`);
      return { ...o, on: cb ? cb.checked : o.on !== false };
    });
    const first = { ...((disp.plan.sessions || [])[0] || {}), role: v('fmRole'), model: v('fmModel') || null, title: v('fmTitle'),
                    read_only: $('fmRO').checked, read_only_set: true, worktree: $('fmWT').checked, first_prompt: v('fmFirst'),
                    files: parseFiles(v('fmFiles')), merge_order: $('fmOrder') ? Number(v('fmOrder')) || 1 : 1,
                    on: $('fmOn0') ? $('fmOn0').checked : true };
    const rest = [...box.querySelectorAll('.fm-sess')].map((el) => {
      const q = (k) => el.querySelector(`[data-k=${k}]`);
      return { ...((disp.plan.sessions || [])[Number(el.dataset.si)] || {}), on: q('on').checked, title: q('title').value, role: q('role').value,
               model: q('model').value || null, files: parseFiles(q('files').value), merge_order: Number(q('merge_order').value) || null,
               first_prompt: q('first_prompt').value, read_only: q('read_only').checked, read_only_set: true, worktree: q('worktree').checked };
    });
    return { ...disp.plan, project: v('fmProj'), mode: v('fmMode'), summary_id: v('fmSum') ? Number(v('fmSum')) : null,
             attach_session: v('fmAttach') ? Number(v('fmAttach')) : null, role: v('fmRole'), model: v('fmModel') || null, title: v('fmTitle'),
             read_only: $('fmRO').checked, read_only_set: true, worktree: $('fmWT').checked, first_prompt: v('fmFirst'), note_updates: ups,
             sessions: [first, ...rest], sessions_edit: true };
  }
  async function start() {
    const plan = collect();
    $('fmGo').disabled = true;
    $('fmStartMsg').className = 'small muted';
    $('fmStartMsg').textContent = plan.mode === 'attach' ? '세션에 보내는 중입니다…' : '새 세션을 띄우는 중입니다…';
    try {
      const r = await api('POST', '/api/foreman/start', { dispatch_id: disp.dispatch_id, plan, ...(inboxIds.length ? { inbox_ids: inboxIds } : {}) });
      const ok = r.mode === 'attach' ? (r.injected ? '보냈습니다.' : '보냈지만 제출을 확인하지 못했습니다.')
        : `새 세션을 띄웠습니다${r.tmux ? `(tmux ${r.tmux}${r.model ? ' · ' + r.model : ''})` : ''}.${r.worktree ? ` 작업방 ${r.worktree.branch}에서 합니다.` : ''}${r.injected ? ' 첫 글을 넣었습니다.' : ''}${startedLine(r)}`;
      $('fmStartMsg').className = `small ${r.note ? 'warn' : 'ok'}`;
      $('fmStartMsg').textContent = ok + (r.notes ? ` 진행 중인 일 ${r.notes}줄을 고쳤습니다.` : '') + (r.note ? ' ' + r.note : '');
      $('fmDrop').disabled = true;
      if (r.session_id && window.office) setTimeout(() => { dlg.classList.remove('on'); window.office.openSession(r.session_id); }, r.note ? 4000 : 1200);
    } catch (e) {
      $('fmStartMsg').className = 'small bad';
      $('fmStartMsg').textContent = `시작하지 못했습니다: ${e.message}`;
      $('fmGo').disabled = false;
    }
  }
  async function drop() {
    if (dropAction(disp) === 'clear') { clearPlan(); msg(''); return; }
    try {
      await api('POST', `/api/foreman/dispatch/${disp.dispatch_id}/discard`);
      $('fmStartMsg').className = 'small muted';
      $('fmStartMsg').textContent = '버렸습니다.';
      $('fmGo').disabled = true; $('fmDrop').disabled = true;
    } catch (e) { $('fmStartMsg').className = 'small bad'; $('fmStartMsg').textContent = `버리지 못했습니다: ${e.message}`; }
  }
  $('fmAsk').onclick = ask;
  $('fmText').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); ask(); } });
  who();
  // 11-09 코더의 맡길 일 → 받은 할 일 글을 말하기 칸에 채운다. 바로 계획을 받지 않는다(사람이 읽고 [계획 받기])
  // id — 하나(코더 맡길 일) 또는 여럿(11-11 할 일 목록에서 골라 [골라서 계획 받기]). 여럿이면 바로 계획을 받는다(사람이 이미 골랐다)
  function prefill(text, id) {
    $('fmText').value = text || '';
    sent = false;
    inboxIds = (Array.isArray(id) ? id : id ? [id] : []).map(Number);
    const tag = inboxIds.map((i) => `#${i}`).join(' · ');
    msg(inboxIds.length ? `받은 할 일 ${tag}을 채웠습니다. 고칠 것은 고친 뒤 [계획 받기]를 누릅니다. 시작하면 그 세션이 ${inboxIds.length > 1 ? '이 할 일들을' : '이 할 일을'} 가져갑니다.` : '', 'muted');
    if (inboxIds.length > 1) ask();
  }
  ui = { reset, load, prefill, focus: () => $('fmText').focus() };
  // 머리줄 [＋ 세션](office.js → newsession.js open)으로 열 때는 이 칸을 거치지 않는다 — 창이 열리는 것을 보고 같이 비운다.
  // 감독실 캐릭터로 열 때(open)는 이 뒤에 reset · prefill · load가 이어서 온다(관찰 콜백이 먼저 돈다)
  let wasOn = dlg.classList.contains('on');
  new MutationObserver(() => {
    const on = dlg.classList.contains('on');
    if (on && !wasOn) fresh();
    wasOn = on;
  }).observe(dlg, { attributes: true, attributeFilter: ['class'] });
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
// 코더의 맡길 일(11-09) — 받은 할 일을 말하기 칸에 채워 연다(계획으로 — 바로 띄우지 않는다)
async function openWith(project, text, inboxId) {
  await open(project || null);
  if (ui) ui.prefill(text, inboxId);
}
// [+ 세션] 창은 office.js가 처음 그릴 때 만든다 — 생기면 붙는다. document가 없으면(node 시험) 붙이지 않는다
if (typeof document !== 'undefined') {
  window.foremanChat = { open, openDispatch, openWith };
  const watch = new MutationObserver(() => { const d = document.getElementById('nsDlg'); if (d) { mount(d); watch.disconnect(); } });
  watch.observe(document.body, { childList: true });
  const d0 = document.getElementById('nsDlg');
  if (d0) { mount(d0); watch.disconnect(); }
}
