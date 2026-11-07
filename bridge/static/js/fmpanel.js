// 감독실 캐릭터 패널(11-08, docs/14_dispatcher_note_wake.md) — 팀장(교장 · 소장 · 디스패처)을 누르면 패널에 뜬다.
// 이 캐릭터는 세션이 아니라 디스패처의 얼굴이다: 들고 있는 것(노트) · 해 온 것(지난 디스패치) · [시작]을 기다리는 자동 제안을 보인다.
// 말하기는 가운데 창(foremanchat.js). 노트는 디스패처가 제안하고 사람이 [시작] 때 승인한다 — 여기서는 사람이 내리기만.

import { esc, ago, keep } from './render.js';

const KIND = { thread: '진행 중인 일', decision: '사람이 정한 판단' };

export function createForemanPanel(store) {
  const cache = new Map();          // 프로젝트 → {at, data}
  let pending = [], note = null, pat = 0;

  async function load(projects, force = false) {
    const now = Date.now();
    const need = projects.filter((p) => force || !cache.has(p) || now - cache.get(p).at > 20000);
    if (!need.length && !force && now - pat < 20000) return;
    pat = now;
    try {
      const [st, ...rs] = await Promise.all([fetch('/api/foreman/state', { headers: store.headers() }),
        ...need.map((p) => fetch(`/api/foreman/notes?project=${encodeURIComponent(p)}`, { headers: store.headers() }))]);
      if (st.ok) pending = (await st.json()).pending || [];
      for (let i = 0; i < need.length; i++) {
        const r = rs[i];
        cache.set(need[i], { at: now, data: r.ok ? await r.json() : { error: true } });
      }
    } catch { /* 못 읽으면 지난 것 */ }
    store.touch('panel');
  }

  function notesBlock(project, label) {
    const c = cache.get(project);
    if (!c) return `<p class="small muted">${esc(label)} 노트를 읽는 중입니다.</p>`;
    const d = c.data;
    if (d.error) return '<p class="small warn">노트를 읽지 못했습니다.</p>';
    const rows = d.notes.map((n) => `<div class="sc-row${n.folded ? ' fm-folded' : ''}"><div class="small">
        <b>${KIND[n.kind] || esc(n.kind)}</b> ${esc(n.body)}
        <div class="muted">출처 ${esc(n.source)} · 확인 ${ago(n.checked_at)}${n.folded ? ' · <span class="warn">접힘 — 상한을 넘어 디스패처에 안 들어갑니다</span>' : ''}</div>
        ${n.drift.length ? `<div class="warn">⚠ ${n.drift.map(esc).join(' · ')}</div>` : ''}</div>
        <button type="button" class="small ghost" data-fm-retire="${n.id}" data-proj="${esc(project)}" title="내리기 — 이 줄을 노트에서 뺍니다. 기록은 남습니다.">내리기</button></div>`).join('');
    const disp = (d.dispatches || []).length ? `<details class="hand"${keep(`fm:${project}:disp`)}><summary class="small" title="지난 디스패치 — 디스패처에게도 이 목록(사람이 고친 칸)이 들어갑니다. 같은 실수를 되풀이하지 않게 합니다."><b>지난 디스패치 ${d.dispatches.length}</b></summary>${
      d.dispatches.map((x) => `<div class="small">· ${esc(x)}</div>`).join('')}</details>` : '';
    return `<details class="hand"${keep(`fm:${project}:notes`, true)}><summary class="small" title="노트 — 디스패처를 부를 때마다 함께 들어갑니다. 진행 중인 일과 사람이 정한 판단만 쌓습니다(구조 · 명령은 쌓지 않습니다)."><b>${esc(label)} 노트 ${d.notes.length}줄</b>
        <span class="muted">· 약 ${d.tokens}/${d.cap}토큰${d.folded ? ` · 접힘 ${d.folded}` : ''}</span></summary>${rows || '<p class="small muted">아직 없습니다. 디스패처가 계획과 함께 제안하고, [이대로 시작]을 누를 때 쌓입니다.</p>'}</details>${disp}`;
  }

  function html(room, name, labelOf) {
    const projects = room ? [room] : store.state.projects.map((p) => p.name);
    load(projects);
    const mine = pending.filter((x) => !room || x.project === room);
    const pend = mine.length ? `<div class="fm-q"><b>[시작]을 기다리는 제안 ${mine.length}</b>${mine.map((x) => `<div class="sc-row"><div class="small">· ${esc(x.title || '(이름 없음)')}
        <div class="muted">${esc((x.why || '').split(' — ')[0])} · ${ago(x.created_at)}</div></div>
        <button type="button" class="small" data-fm-open="${x.dispatch_id}" title="계획 보기 — 실패 이벤트가 부른 계획을 엽니다. [이대로 시작]을 눌러야 시작합니다.">계획 보기</button></div>`).join('')}</div>` : '';
    return `<div class="small muted">${esc(name)} — 디스패처의 얼굴입니다. 세션은 없고, 부를 때마다 상황과 노트를 모아 계획 하나를 냅니다.</div>
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}">${esc(note.msg)}</div>` : ''}
      <div class="row fm-row"><button type="button" class="small" data-fm-talk="${esc(room || '')}" title="말하기 — ${esc(name)}에게 뭘 하려는지 말하면 계획을 냅니다.">${esc(name)}에게 말하기</button></div>
      ${pend}${projects.map((p) => notesBlock(p, labelOf(p))).join('')}`;
  }

  async function onClick(ev) {
    const t = ev.target.closest('[data-fm-talk]'), o = ev.target.closest('[data-fm-open]'), r = ev.target.closest('[data-fm-retire]');
    if (t) { ev.preventDefault(); window.foremanChat && window.foremanChat.open(t.dataset.fmTalk || null); return; }
    if (o) { ev.preventDefault(); window.foremanChat && window.foremanChat.openDispatch(Number(o.dataset.fmOpen)); return; }
    if (!r) return;
    ev.preventDefault();
    if (!confirm('이 줄을 노트에서 내립니다. 다음 디스패치부터 들어가지 않습니다(기록은 남습니다). 내릴까요?')) return;
    const res = await fetch(`/api/foreman/notes/${r.dataset.fmRetire}/retire`, { method: 'POST', headers: store.headers(true) });
    const j = await res.json().catch(() => ({}));
    note = res.ok ? { msg: '내렸습니다.' } : { bad: true, msg: `내리지 못했습니다 — ${j.refused || j.detail || res.status}` };
    await load([r.dataset.proj], true);
  }

  return { html, onClick, load };
}
