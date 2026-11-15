// 감독실 캐릭터 패널(11-08, docs/14_dispatcher_note_wake.md) — 팀장(교장 · 소장 · 디스패처)을 누르면 패널에 뜬다.
// 이 캐릭터는 세션이 아니라 디스패처의 얼굴이다: 들고 있는 것(진행 중인 일) · 해 온 것(지난 디스패치) · [시작]을 기다리는 자동 제안을 보인다.
// 말하기는 가운데 창(foremanchat.js). 진행 중인 일은 디스패처가 제안하고 사람이 [시작] 때 승인한다 — 여기서는 사람이 내리기만.
// 11-13 사용자 — 노트(foreman_note)는 「진행 중인 일」 한 칸뿐. 옛 「사람이 정한 판단」 칸은 없앴다(규칙은 CLAUDE.md · docs)

import { esc, ago, keep } from './render.js';

// 11-13 — 끝난 일이 「진행 중인 일」로 남아 있었다. 기계로 끝남을 못 가르는 줄 중 오래 확인 안 한 줄은 「낡음 — 확인 필요」로 따로
export function splitNotes(notes) {
  const fresh = [], stale = [];
  for (const n of notes || []) ((n.stale || []).length ? stale : fresh).push(n);
  return { fresh, stale };
}

function noteRow(n, project, staleRow) {
  const btns = (staleRow ? `<button type="button" class="small ghost" data-fm-touch="${n.id}" data-proj="${esc(project)}" title="아직 진행 중 — 확인 시각을 지금으로 바꿉니다. 낡음 표시가 풀립니다.">아직 진행 중</button>` : '')
    + `<button type="button" class="small ghost" data-fm-retire="${n.id}" data-proj="${esc(project)}" title="내리기 — 이 줄을 진행 중인 일에서 뺍니다. 기록은 남습니다.">내리기</button>`;
  return `<div class="sc-row${n.folded ? ' fm-folded' : ''}"><div class="small">
        ${staleRow ? '<b>낡음</b> ' : ''}${esc(n.body)}
        <div class="muted">출처 ${esc(n.source)} · 확인 ${ago(n.checked_at)}${n.folded ? ' · <span class="warn">접힘(상한을 넘어 계획을 세울 때 안 들어갑니다)</span>' : ''}</div>
        ${staleRow ? `<div class="warn">확인 필요: ${(n.stale || []).map(esc).join(' · ')}</div>` : ''}
        ${n.drift.length ? `<div class="warn">⚠ ${n.drift.map(esc).join(' · ')}</div>` : ''}</div>
        <div class="row">${btns}</div></div>`;
}

export function autoBlock(project, auto) {
  if (!(auto || []).length) return '';
  return `<details class="hand"${keep(`fm:${project}:auto`)}><summary class="small" title="끝난 일 — 붙은 세션이 모두 끝나고 합치기나 버리기로 남은 일이 없어 기계가 끝났다고 본 진행 중인 일입니다. 줄마다 어떻게 끝났는지(예: 세션 272 합침)가 붙습니다. 지우지 않았습니다."><b>끝난 일 ${auto.length}</b></summary>${
    auto.map((a) => `<div class="sc-row"><div class="small">${esc(a.body)}<div class="muted">${esc(a.why)} · ${ago(a.retired_at)}</div></div>
      <button type="button" class="small ghost" data-fm-restore="${a.id}" data-proj="${esc(project)}" title="되살리기 — 끝나지 않았으면 되돌립니다. 다시 진행 중인 일로 두고, 다시 자동으로 내리지 않습니다.">되살리기</button></div>`).join('')}</details>`;
}

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
    if (!c) return `<p class="small muted">${esc(label)} 진행 중인 일을 읽는 중입니다.</p>`;
    const d = c.data;
    if (d.error) return '<p class="small warn">진행 중인 일을 읽지 못했습니다.</p>';
    const { fresh, stale } = splitNotes(d.notes);
    const rule = d.stale_rule ? `마지막 확인 뒤 ${d.stale_rule.days}일 또는 커밋 ${d.stale_rule.commits}개가 넘은 진행 중인 일입니다. ` : '';
    const rows = fresh.map((n) => noteRow(n, project, false)).join('')
      + (stale.length ? `<div class="small warn" title="낡음 — 확인 필요: ${esc(rule)}끝났는지 기계로 가르지 못했습니다. 계획을 세울 때 진행 중인 일로 믿지 않게 따로 넣습니다."><b>낡음: 확인 필요 ${stale.length}</b></div>`
        + stale.map((n) => noteRow(n, project, true)).join('') : '')
      + autoBlock(project, d.auto_retired);
    const disp = (d.dispatches || []).length ? `<details class="hand"${keep(`fm:${project}:disp`)}><summary class="small" title="지난 요청 — 사용자가 시킨 요청, 그때 띄운 것(모드, 역할, 제목), 사람이 고친 칸입니다. 계획을 세울 때 함께 들어가 같은 실수를 되풀이하지 않게 합니다."><b>지난 요청 ${d.dispatches.length}</b></summary>${
      d.dispatches.map((x) => `<div class="small">· ${esc(x)}</div>`).join('')}</details>` : '';
    return `<details class="hand"${keep(`fm:${project}:notes`, true)}><summary class="small" title="진행 중인 일 — 계획을 세울 때마다 함께 들어갑니다. 지금 도는 일만 쌓습니다(규칙 · 설계 결정 · 구조 · 명령은 CLAUDE.md · docs에 둡니다)."><b>${esc(label)} 진행 중인 일 ${d.notes.length}</b>
        <span class="muted">· 약 ${d.tokens}/${d.cap}토큰${d.folded ? ` · 접힘 ${d.folded}` : ''}</span></summary>${rows || '<p class="small muted">아직 없습니다. 계획을 세울 때 함께 제안되고, [이대로 시작]을 누를 때 쌓입니다.</p>'}</details>${disp}`;
  }

  function html(room, name, labelOf) {
    const projects = room ? [room] : store.state.projects.map((p) => p.name);
    load(projects);
    const mine = pending.filter((x) => !room || x.project === room);
    const pend = mine.length ? `<div class="fm-q"><b>[시작]을 기다리는 제안 ${mine.length}</b>${mine.map((x) => `<div class="sc-row"><div class="small">· ${esc(x.title || '(이름 없음)')}
        <div class="muted">${esc((x.why || '').split(' — ')[0])} · ${ago(x.created_at)}</div></div>
        <button type="button" class="small" data-fm-open="${x.dispatch_id}" title="계획 보기 — 실패 이벤트가 부른 계획을 엽니다. [이대로 시작]을 눌러야 시작합니다.">계획 보기</button></div>`).join('')}</div>` : '';
    // 11-09 사용자 — "디스패처의 얼굴" 은 디스패처를 모르면 도움이 안 됐다. 화면에는 "디스패처"를 쓰지 않는다(코드 · 문서는 씀)
    return `<div class="small muted">${esc(name)}: 뭘 할지 말하면 계획을 세워줍니다. 어느 프로젝트에서, 새 세션으로 할지 기존 세션에 붙일지, 무엇을 읽어야 하는지를 정해서 보여줍니다. 확인하면 세션이 뜹니다.</div>
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}">${esc(note.msg)}</div>` : ''}
      <div class="row fm-row"><button type="button" class="small" data-fm-talk="${esc(room || '')}" title="말하기 — ${esc(name)}에게 뭘 하려는지 말하면 계획을 냅니다.">${esc(name)}에게 말하기</button></div>
      ${pend}${projects.map((p) => notesBlock(p, labelOf(p))).join('')}`;
  }

  async function onClick(ev) {
    const t = ev.target.closest('[data-fm-talk]'), o = ev.target.closest('[data-fm-open]'), r = ev.target.closest('[data-fm-retire]');
    if (t) { ev.preventDefault(); window.foremanChat && window.foremanChat.open(t.dataset.fmTalk || null); return; }
    if (o) { ev.preventDefault(); window.foremanChat && window.foremanChat.openDispatch(Number(o.dataset.fmOpen)); return; }
    const x = ev.target.closest('[data-fm-restore], [data-fm-touch]');
    if (x) {
      ev.preventDefault();
      const restore = 'fmRestore' in x.dataset;
      if (restore && !confirm('끝나지 않았으면 되돌립니다. 이 줄을 다시 진행 중인 일로 두고, 다시 자동으로 내리지 않습니다.\n\n되살릴까요?')) return;
      const res = await fetch(`/api/foreman/notes/${restore ? x.dataset.fmRestore : x.dataset.fmTouch}/${restore ? 'restore' : 'touch'}`,
        { method: 'POST', headers: store.headers(true) });
      const j = await res.json().catch(() => ({}));
      note = res.ok ? { msg: restore ? '되살렸습니다.' : '확인 시각을 지금으로 바꿨습니다.' }
        : { bad: true, msg: `${restore ? '되살리지' : '바꾸지'} 못했습니다: ${j.refused || j.detail || res.status}` };
      await load([x.dataset.proj], true);
      return;
    }
    if (!r) return;
    ev.preventDefault();
    if (!confirm('이 줄을 진행 중인 일에서 내립니다. 다음 계획부터 들어가지 않습니다(기록은 남습니다).\n\n내릴까요?')) return;
    const res = await fetch(`/api/foreman/notes/${r.dataset.fmRetire}/retire`, { method: 'POST', headers: store.headers(true) });
    const j = await res.json().catch(() => ({}));
    note = res.ok ? { msg: '내렸습니다.' } : { bad: true, msg: `내리지 못했습니다: ${j.refused || j.detail || res.status}` };
    await load([r.dataset.proj], true);
  }

  return { html, onClick, load };
}
