// 포스트잇(11-15 사용자, 서기 구조 다시 짜기 2번) — 머리 탭 [＋ 할 일] 옆 종이와 서기실이 같은 목록을 본다(/api/postit).
// 들어오는 것: 포스트잇에 바로 적음 · [＋ 할 일] · 대화에서 사람이 미룬 것(관리자가 올림 · 브리지 그물은 「확인 전」으로 흐리게) ·
// 옮기기 「문서에 넣을 것 고르기」의 미완. 줄마다 [x] 삭제 · [→] 알려진 한계, 전체 [저장] · [갱신](점검 세션이 코드를 보고 판정).
// 판정은 제안이다 — 「끝난 것 같음」은 사람이 줄마다 닫는다. 코더에게 맡길 만한 것은 [띄우기]로 계획 창을 바로 연다.
// 조용한 고장 금지: 못 읽으면 0이 아니라 「읽지 못했습니다」, [갱신]이 결과 없이 끝나면 그렇게 보인다.

import { esc, ago } from './render.js';

const UNREAD = '읽지 못했습니다';
const MAX = 8000;

export const mmdd = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : `${d.getMonth() + 1}/${d.getDate()}`;
};
// 첫 줄만, 길면 자른다(구분선 줄은 건너뛴다)
export const firstLine = (s, n = 70) => {
  const t = String(s || '').split('\n').map((x) => x.trim()).find((x) => x && !/^[━─=\-]{3,}$/.test(x)) || '';
  return t.length > n ? t.slice(0, n - 1) + '…' : t;
};

// 머리 탭 종이 — 지금 보는 방(없으면 모든 방 합)의 열린 수와 가장 오래된 날. 쌓임 기준을 넘으면 warn
export function badgeOf(projects, room) {
  if (!projects) return { text: '포스트잇 ?', cls: 'warn', tip: `포스트잇 — 개수를 ${UNREAD}. 누르면 펼쳐 다시 읽습니다.` };
  const names = room && projects[room] ? [room] : Object.keys(projects);
  const xs = names.map((n) => [n, projects[n] || {}]);
  const open = xs.reduce((a, [, p]) => a + (p.open || 0), 0);
  const oldest = xs.map(([, p]) => p.oldest_at).filter(Boolean).sort()[0] || null;
  const nudge = xs.some(([, p]) => p.nudge);
  const done = xs.reduce((a, [, p]) => a + (p.likely_done || 0), 0);
  const per = xs.filter(([, p]) => p.open).map(([n, p]) => `${n} ${p.open}`).join(', ');
  return {
    text: `포스트잇 ${open}${oldest ? `, ${mmdd(oldest)}부터` : ''}`,
    cls: nudge ? 'warn' : '',
    tip: `포스트잇 — 열린 할 일 ${open}개${oldest ? `, 가장 오래된 것 ${mmdd(oldest)}` : ''}${done ? `, 끝난 것 같음 ${done}` : ''}.`
      + `${room && projects[room] ? '' : per ? ` 방마다: ${per}.` : ''} 누르면 펼칩니다.`,
  };
}

// 코더에게 맡길 때 계획 창에 채울 글
export function planText(items) {
  const xs = (items || []).filter((x) => x && x.body);
  if (!xs.length) return '';
  const head = xs.length > 1
    ? `포스트잇 ${xs.length}개를 묶어 계획을 세워 주세요. 겹치거나 이미 된 것은 까닭과 함께 빼고, 맡을 파일이 겹치지 않게 세션을 나눠도 됩니다.`
    : '포스트잇 하나로 계획을 세워 주세요. 이미 된 것이면 까닭과 함께 알려 주세요.';
  return [head, ...xs.map((x) => `\n#${x.id}${x.created_at ? ` (${mmdd(x.created_at)})` : ''}\n${String(x.body).trim()}`
    + (x.check && x.check.reason ? `\n(점검: ${x.check.reason})` : ''))].join('\n');
}

function checkHtml(k, text) {
  const ev = k.evidence ? ` <code>${esc(k.evidence)}</code>` : '';
  return `<div class="pi-row pi-check" data-tip="${esc(`끝난 것 같음 — 점검 세션 ${k.session_id}이 코드를 보고 끝났다고 봤습니다. 맞으면 [닫기], 아니면 [남기기]를 누릅니다.`)}">
    <div class="pi-main small"><b>${esc(firstLine(text, 80))}</b>${ev}${k.reason ? `<div class="muted">${esc(k.reason)}</div>` : ''}</div>
    <div class="pi-btns"><button type="button" class="small" data-pi-check="${k.id}" data-act="close" title="닫기 — 끝난 것으로 닫습니다. 근거는 닫은 줄에 남습니다.">닫기</button>
    <button type="button" class="small ghost" data-pi-check="${k.id}" data-act="keep" title="남기기 — 아직 남은 일로 둡니다. 다음 [갱신]에서 다시 봅니다.">남기기</button></div></div>`;
}

function rowHtml(x, busy) {
  const ck = x.check;
  const chip = [
    !x.confirmed ? '<span class="pi-chip" title="확인 전 — 브리지 그물이 대화에서 찾았습니다. 맞으면 [저장], 아니면 [x]를 누릅니다.">확인 전</span>' : '',
    x.state !== 'new' ? `<span class="pi-chip" title="${esc(`${x.label} — 세션 ${x.taken_by}이 이 일을 가져갔습니다.`)}">${esc(x.label)}</span>` : '',
    ck && ck.verdict !== 'done' ? `<span class="pi-chip" title="${esc(`[갱신] 판정: ${ck.label} — ${ck.reason || '까닭 없음'}`)}">${esc(ck.label)}</span>` : '',
    x.recommend ? '<span class="pi-chip pi-rec" title="코더 추천 — [갱신]이 코더에게 맡길 만하다고 봤습니다. [띄우기]로 계획을 받습니다.">코더 추천</span>' : '',
  ].join('');
  const ref = x.source_ref && x.source_ref.startsWith('t:') ? `, ${esc(x.source_ref)}` : '';
  const dis = busy ? ' disabled' : '';
  return `<div class="pi-row${x.confirmed ? '' : ' pi-unconf'}" data-pi-row="${x.id}">
    <details class="pi-main"><summary class="small">${esc(firstLine(x.body))} <span class="muted">(${esc(x.source_label)}, ${esc(mmdd(x.created_at))}${ref})</span> ${chip}</summary><pre class="hand-body">${esc(x.body)}</pre></details>
    <div class="pi-btns">${x.recommend ? `<button type="button" class="small primary" data-pi-launch="${x.id}"${dis} title="띄우기 — 이 포스트잇으로 계획 창을 열고 바로 계획을 받습니다. [이대로 시작]을 누르면 코더 세션이 이 일을 가져갑니다.">띄우기</button>` : ''}
    <button type="button" class="small ghost" data-pi-close="${x.id}" data-reason="drop"${dis} title="삭제 — 안 하기로 한 것입니다. 목록에서 사라집니다.">x</button>
    <button type="button" class="small ghost" data-pi-close="${x.id}" data-reason="limit"${dis} title="알려진 한계 — 못 풀 것입니다. 포스트잇에서 빼고 README 「알려진 한계」에 쓸 줄로 서기 할 일에 셉니다.">→</button></div></div>`;
}

function checkState(s) {
  const c = s && s.check;
  if (!c) return '<span class="muted">[갱신]을 아직 하지 않았습니다.</span>';
  if (c.state === 'running') return `<span class="warn">점검 세션 ${c.session_id}이 코드를 보는 중입니다(${ago(c.at)} 시작).</span>`;
  if (c.state === 'failed') return `<span class="bad">지난 [갱신]이 결과 없이 끝났습니다(점검 세션 ${c.session_id}). 다시 [갱신]을 누릅니다.</span>`;
  return `<span class="muted">마지막 [갱신] ${ago(c.at)}</span>`;
}

// 머리 탭 창과 서기실이 같이 쓰는 목록(순수 — view = GET /api/postit 응답)
export function listHtml(view, { busy = false, draft = '', note = null, label = '', bad = false } = {}) {
  if (!view) return `<div class="postit paper"><p class="small ${bad ? 'bad' : 'muted'}">${bad ? `포스트잇을 ${UNREAD}.` : '포스트잇을 읽는 중입니다.'}</p></div>`;
  const s = view.summary || {};
  const items = view.items || [];
  const unconf = items.filter((x) => !x.confirmed);
  const done = items.filter((x) => x.check && x.check.verdict === 'done');
  const lim = (view.readme_checks || []).filter((k) => k.verdict === 'done');
  const head = `<div class="pi-head small"><b>포스트잇</b> ${esc(label || view.project)} <span class="muted">열린 것 ${items.length}${unconf.length ? `, 확인 전 ${unconf.length}` : ''}${s.oldest_at ? `, 가장 오래된 것 ${mmdd(s.oldest_at)}(${s.oldest_days}일째)` : ''}</span>${bad ? ` <span class="bad">(지금 값을 ${UNREAD}. 지난 값입니다)</span>` : ''}</div>`;
  const nudge = s.nudge ? `<div class="small warn">쌓였습니다: ${esc(s.nudge.why)}. 끝난 것은 [갱신]으로 찾고, 안 할 것은 [x]로 지웁니다.</div>` : '';
  const doneHtml = done.length + lim.length ? `<div class="pi-sec"><div class="small"><b>끝난 것 같음 ${done.length + lim.length}</b> <span class="muted">근거가 코드 자리인 것만입니다. 사람이 줄마다 닫습니다.</span></div>
    ${done.map((x) => checkHtml(x.check, x.body)).join('')}${lim.map((k) => checkHtml(k, `README 「알려진 한계」 ${k.item}: ${k.item_text || ''}`)).join('')}</div>` : '';
  const rows = items.length ? items.map((x) => rowHtml(x, busy)).join('') : '<p class="small muted">열린 포스트잇이 없습니다.</p>';
  const closed = view.closed || [];
  const closedHtml = closed.length ? `<details class="pi-closed"><summary class="small muted" title="닫은 것 — 최근 닫은 포스트잇을 다시 봅니다.">닫은 것 ${closed.length}</summary>${
    closed.map((x) => `<div class="small muted pi-crow">${esc(x.label)}: ${esc(firstLine(x.body, 60))}${x.closed_note ? ` <span title="${esc(x.closed_note)}">(근거)</span>` : ''}</div>`).join('')}</details>` : '';
  const saveTip = unconf.length
    ? `저장 — 적은 글을 포스트잇에 올리고, 확인 전 ${unconf.length}줄도 받아들입니다. 아닌 줄은 먼저 [x]로 지웁니다.`
    : '저장 — 적은 글을 포스트잇에 바로 올립니다. Ctrl+Enter로도 저장합니다.';
  const running = s.check && s.check.state === 'running';
  return `<div class="postit paper" data-pi-project="${esc(view.project)}">${head}${nudge}${doneHtml}
    <div class="pi-list">${rows}</div>
    <textarea class="pi-draft" rows="2" maxlength="${MAX}" placeholder="여기에 바로 적습니다(붙여 넣어도 됩니다)"${busy ? ' disabled' : ''}>${esc(draft)}</textarea>
    <div class="pi-foot"><span class="small">${checkState(s)}</span>
      <button type="button" class="small primary" data-pi-save="1"${busy ? ' disabled' : ''} title="${esc(saveTip)}">저장${unconf.length ? ` (확인 전 ${unconf.length})` : ''}</button>
      <button type="button" class="small" data-pi-refresh="1"${busy || running ? ' disabled' : ''} title="${esc(running ? '갱신 — 점검 세션이 이미 보는 중입니다.' : '갱신 — 점검 세션을 띄워 코드를 보고 이미 끝난 것을 찾습니다. 포스트잇과 README 「알려진 한계」를 함께 봅니다. 지우는 것은 사람이 합니다.')}">갱신</button></div>
    ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}">${esc(note.msg)}</div>` : ''}${closedHtml}</div>`;
}

// 동작 — 머리 탭 창 · 서기실이 같이 쓴다. ctx: {store, project, view, draft(), setDraft(), done(note)}
export async function act(ev, ctx) {
  const t = ev.target;
  const api = async (url, body) => {
    const r = await fetch(url, { method: 'POST', headers: ctx.store.headers(true), body: JSON.stringify(body || {}) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.refused || j.detail || `HTTP ${r.status}`);
    return j;
  };
  const items = (ctx.view && ctx.view.items) || [];
  const c = t.closest('[data-pi-close]'), sv = t.closest('[data-pi-save]'), rf = t.closest('[data-pi-refresh]');
  const ck = t.closest('[data-pi-check]'), ln = t.closest('[data-pi-launch]');
  if (!c && !sv && !rf && !ck && !ln) return false;
  ev.preventDefault();
  try {
    if (c) {
      const why = c.dataset.reason;
      await api(`/api/postit/${c.dataset.piClose}/close`, { reason: why });
      return ctx.done({ msg: why === 'limit' ? `#${c.dataset.piClose}을 알려진 한계로 보냈습니다. README에 쓰는 것은 서기 「알려진 한계 쓰기」입니다.` : `#${c.dataset.piClose}을 지웠습니다.` });
    }
    if (sv) {
      const body = ctx.draft().trim();
      const confirmIds = items.filter((x) => !x.confirmed).map((x) => x.id);
      if (!body && !confirmIds.length) return ctx.done({ bad: true, msg: '저장할 글이 없습니다. 아래 칸에 적고 [저장]을 누릅니다.' });
      const j = await api('/api/postit/save', { project: ctx.project, body, confirm: confirmIds });
      ctx.setDraft('');
      return ctx.done({ msg: [j.id ? `#${j.id}을 저장했습니다.` : '', j.confirmed ? `확인 전 ${j.confirmed}줄을 받아들였습니다.` : ''].filter(Boolean).join(' ') });
    }
    if (rf) {
      if (typeof confirm === 'function' && !confirm(`${ctx.project}의 포스트잇과 README 「알려진 한계」를 점검 세션이 코드를 보고 판정합니다. 원본 폴더에 점검 세션이 뜨고(역할 점검, 고치지 않음), 끝나면 「끝난 것 같음」이 여기 뜹니다.\n\n띄울까요?`)) return true;
      const j = await api('/api/postit/refresh', { project: ctx.project });
      return ctx.done({ msg: `[갱신]: 점검 세션 ${j.session_id || '?'}을 띄웠습니다(포스트잇 ${j.items} · README 줄 ${j.limits}).${j.note ? ` ${j.note}` : ''}` });
    }
    if (ck) {
      await api(`/api/postit/check/${ck.dataset.piCheck}`, { action: ck.dataset.act });
      return ctx.done({ msg: ck.dataset.act === 'close' ? '끝난 것으로 닫았습니다.' : '남은 일로 두었습니다.' });
    }
    if (ln) {
      const x = items.find((y) => String(y.id) === ln.dataset.piLaunch);
      if (!x || !window.foremanChat || !window.foremanChat.openWith) return ctx.done({ bad: true, msg: '계획 창을 열지 못했습니다. 화면을 새로 고쳐 주세요.' });
      if (ctx.close) ctx.close();
      await window.foremanChat.openWith(ctx.project, planText([x]), [x.id], { ask: true });
      return true;
    }
  } catch (e) {
    return ctx.done({ bad: true, msg: `하지 못했습니다: ${e.message}` });
  }
  return true;
}

async function fetchView(store, project) {
  const r = await fetch(`/api/postit?project=${encodeURIComponent(project)}`, { headers: store.headers() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// 서기실 창 안의 포스트잇(scribe.js가 부른다) — 머리 탭과 같은 목록 · 같은 동작
export function createPostitBlock(store) {
  const views = new Map(), drafts = new Map(), notes = new Map(), bad = new Map(), at = new Map();
  let busy = false;
  async function load(room, force = false) {
    if (!force && Date.now() - (at.get(room) || 0) < 20000) return;
    at.set(room, Date.now());
    try { views.set(room, await fetchView(store, room)); bad.set(room, false); } catch { bad.set(room, true); }
    store.touch('panel');
  }
  function html(room, label) {
    load(room);
    return listHtml(views.get(room) || null, { busy, draft: drafts.get(room) || '', note: notes.get(room) || null, label, bad: !!bad.get(room) });
  }
  function onInput(ev, room) { if (ev.target && ev.target.classList && ev.target.classList.contains('pi-draft')) drafts.set(room, ev.target.value); }
  async function onClick(ev, room) {
    return act(ev, {
      store, project: room, view: views.get(room), draft: () => drafts.get(room) || '', setDraft: (v) => drafts.set(room, v),
      done: async (note) => { notes.set(room, note); busy = false; await load(room, true); if (window.office && window.office.postitChanged) window.office.postitChanged(); return true; },
    });
  }
  return { html, onClick, onInput, load };
}

// 머리 탭 종이 + 펼친 창
export function mountPostit(store, btn, { room = () => null, onChanged } = {}) {
  const pop = document.createElement('div');
  pop.id = 'piPop'; pop.className = 'pi-pop';
  pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', '포스트잇');
  document.body.appendChild(pop);
  let projects = null, project = null, view = null, draft = '', note = null, badRead = false;
  async function loadSummary() {
    try {
      const r = await fetch('/api/postit/summary', { headers: store.headers() });
      if (r.ok) projects = (await r.json()).projects || {};
    } catch { /* 못 읽으면 「읽지 못했습니다」 */ }
    drawBadge();
  }
  function drawBadge() {
    const b = badgeOf(projects, room());
    btn.textContent = b.text; btn.title = b.tip;
    btn.classList.toggle('warn', b.cls === 'warn');
  }
  function draw() {
    const names = store.state.projects.map((p) => p.name).filter(Boolean);
    const lab = (n) => (store.state.projects.find((p) => p.name === n) || {}).label || n;
    pop.innerHTML = `<div class="pi-bar"><select class="pi-proj" aria-label="프로젝트">${names.map((n) => `<option value="${esc(n)}"${n === project ? ' selected' : ''}>${esc(lab(n))}</option>`).join('')}</select>
      <button type="button" class="small ghost" data-pi-x="1" title="닫기 — 포스트잇을 접습니다. 적던 글은 남습니다.">닫기</button></div>${listHtml(view, { draft, note, label: lab(project), bad: badRead })}`;
  }
  async function reload() {
    try { view = await fetchView(store, project); badRead = false; } catch { badRead = true; }
    draw();
  }
  function close() { pop.classList.remove('on'); }
  async function open(p) {
    const names = store.state.projects.map((x) => x.name).filter(Boolean);
    project = names.includes(p) ? p : names.includes(room()) ? room() : names.includes('foreman') ? 'foreman' : names[0];
    note = null; view = null;
    const r = btn.getBoundingClientRect();
    pop.style.top = `${Math.round(r.bottom + 6)}px`;
    pop.style.left = `${Math.max(8, Math.min(Math.round(r.left), window.innerWidth - Math.min(560, window.innerWidth - 16) - 8))}px`;
    pop.classList.add('on');
    draw();
    await reload();
  }
  btn.addEventListener('click', () => (pop.classList.contains('on') ? close() : open(room())));
  pop.addEventListener('input', (ev) => { if (ev.target.classList.contains('pi-draft')) draft = ev.target.value; });
  pop.addEventListener('change', (ev) => { if (ev.target.classList.contains('pi-proj')) { project = ev.target.value; view = null; note = null; draw(); reload(); } });
  pop.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') { ev.stopPropagation(); close(); return; }
    if (ev.target.classList.contains('pi-draft') && ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault(); const b = pop.querySelector('[data-pi-save]'); if (b) b.click();
    }
  });
  pop.addEventListener('click', async (ev) => {
    if (ev.target.closest('[data-pi-x]')) { close(); return; }
    await act(ev, {
      store, project, view, draft: () => draft, setDraft: (v) => { draft = v; }, close,
      done: async (n) => { note = n; await reload(); await loadSummary(); if (onChanged) onChanged(); return true; },
    });
  });
  loadSummary();
  setInterval(loadSummary, 60000);
  setInterval(drawBadge, 2000);       // 방을 옮기면 그 방 숫자로(값은 1분마다 다시 받는다)
  return { open, close, reload: async () => { await loadSummary(); if (pop.classList.contains('on')) await reload(); } };
}
