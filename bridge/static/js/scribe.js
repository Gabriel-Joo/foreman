// 서기실 창(12a, 11-06) — 서기를 누르면 패널에 뜬다. 할 일(기계로 센 것) · 시킬 일 여섯 · Notion 게시.
// 시킬 일은 worktree 서기 세션을 띄운다(합치기가 사람의 검토). Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py).

import { esc, ago } from './render.js';

const ORDER = ['retro', 'doccheck', 'readme', 'trim', 'later', 'publish'];

export function createScribe(store) {
  let todo = null, pub = null, note = null, busy = false, at = 0;

  async function load(force = false) {
    if (!force && Date.now() - at < 20000) return;
    at = Date.now();
    try {
      const [t, p] = await Promise.all([fetch('/api/scribe/todo', { headers: store.headers() }), fetch('/api/publish', { headers: store.headers() })]);
      todo = t.ok ? await t.json() : todo;
      pub = p.ok ? await p.json() : pub;
    } catch { /* 못 읽으면 지난 것을 보인다 */ }
    store.touch('panel');
  }

  function pubBlock(room) {
    if (!pub) return '<p class="small muted">게시 목록을 읽는 중입니다.</p>';
    if (!pub.enabled) return `<p class="small warn">${esc(pub.why || 'Notion 게시가 꺼져 있습니다.')}</p>`;
    if (room !== 'foreman') return '<p class="small muted">Notion 게시는 지금 포먼 프로젝트만 연결돼 있습니다.</p>';
    const rows = (pub.docs || []).map((d) => {
      const st = d.status === 'new' ? '<span class="muted">안 올림</span>' : d.status === 'archived' ? '<span class="muted">휴지통</span>'
        : d.changed ? '<span class="warn">원본이 바뀜</span>' : '<span class="ok">게시됨</span>';
      const btns = [
        d.status !== 'published' || d.changed ? `<button type="button" class="small" data-pub="publish" data-path="${esc(d.path)}" title="게시 — main에 커밋된 원본을 Notion에 올립니다. 이미 올린 글이면 같은 페이지를 덮어씁니다.">${d.status === 'published' ? '다시 게시' : '게시'}</button>` : '',
        d.status === 'published' ? `<button type="button" class="small ghost" data-pub="archive" data-path="${esc(d.path)}" title="내리기 — Notion 페이지를 휴지통으로 보냅니다(30일 안에 되살릴 수 있습니다). 우리가 만든 페이지만 됩니다.">내리기</button>` : '',
        d.url ? `<a class="small" href="${esc(d.url)}" target="_blank" rel="noopener" title="Notion에서 열기 — 새 탭으로 엽니다.">열기</a>` : '',
      ].join(' ');
      return `<div class="sc-row"><div class="small"><code>${esc(d.path)}</code> ${st}${d.commit ? ` <span class="muted">· 커밋 ${esc(d.commit)}</span>` : ''}${d.updated_at ? ` <span class="muted">· ${ago(d.updated_at)}</span>` : ''}</div><div class="hand-btns">${btns}</div></div>`;
    }).join('');
    return rows || '<p class="small muted">게시할 글이 없습니다(main의 log/retro_*.md).</p>';
  }

  function html(room, label) {
    load();
    const tasks = (todo && todo.tasks) || {};
    const items = (todo && todo.projects && todo.projects[room] && todo.projects[room].items) || [];
    const todoHtml = items.length ? items.map((x) => `<div class="sc-row"><div class="small"><b>${esc(x.title)}</b> <span class="muted">— ${esc(x.why)}</span></div>
        ${x.kind !== 'publish' ? `<button type="button" class="small" data-sc-task="${esc(x.kind)}" title="${esc((tasks[x.kind] || {}).title || '')} — 이 일을 서기에게 시킵니다.">시키기</button>` : ''}</div>`).join('')
      : '<p class="small muted">기계로 센 할 일이 없습니다.</p>';
    const taskHtml = ORDER.filter((k) => k !== 'publish' && tasks[k]).map((k) => `<div class="sc-row"><div class="small"><b>${esc(tasks[k].title)}</b> <span class="muted">${esc(tasks[k].desc)}</span></div>
        <button type="button" class="small" data-sc-task="${k}"${busy ? ' disabled' : ''} title="${esc(tasks[k].title)} — 서기 세션을 따로 작업(worktree)으로 띄워 맡깁니다. 끝나면 [끝내고 합치기]로 검토해 합칩니다.">시키기</button></div>`).join('');
    return `<div class="small muted">${esc(label)} · 서기 — 문서 담당. 시킨 일은 따로 작업(worktree) 세션으로 돌고, 끝나면 사람이 diff를 보고 합칩니다.</div>
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}">${esc(note.msg)}</div>` : ''}
      <details class="hand" open><summary title="할 일 — 브리지가 LLM 없이 센 것입니다(커밋은 쌓였는데 README가 그대로 등)."><b>할 일 ${items.length}</b></summary>${todoHtml}</details>
      <details class="hand" open><summary title="시킬 일 — 고르면 서기 세션이 뜹니다."><b>시킬 일</b></summary>${taskHtml}</details>
      <details class="hand" open><summary title="Notion 게시 — 원본은 git 마크다운, Notion은 게시판입니다. 버튼을 눌러야만 올라갑니다."><b>Notion 게시</b></summary>${pubBlock(room)}</details>`;
  }

  async function onClick(ev, room, label) {
    const t = ev.target.closest('[data-sc-task]'), p = ev.target.closest('[data-pub]');
    if (!t && !p) return;
    ev.preventDefault();
    if (t) {
      const k = t.dataset.scTask, name = ((todo && todo.tasks) || {})[k]?.title || k;
      if (!confirm(`${label}의 서기에게 「${name}」을 맡깁니다. 서기 세션이 따로 작업(worktree)으로 뜨고(Opus), 끝나면 [끝내고 합치기]로 검토해 합칩니다. 진행할까요?`)) return;
      busy = true; note = { msg: `「${name}」 — 서기 세션을 띄우는 중입니다…` }; store.touch('panel');
      const r = await fetch('/api/scribe/start', { method: 'POST', headers: store.headers(true), body: JSON.stringify({ project: room, task: k }) });
      const j = await r.json().catch(() => ({}));
      busy = false;
      note = r.ok ? { msg: `「${name}」 — 서기 세션을 띄웠습니다(tmux ${j.tmux || '?'}). 서기실에서 일합니다.` } : { bad: true, msg: `띄우지 못했습니다 — ${j.refused || j.detail || r.status}` };
      await load(true);
      return;
    }
    const act = p.dataset.pub, path = p.dataset.path;
    if (act === 'archive' && !confirm(`${path}의 Notion 페이지를 휴지통으로 보냅니다(30일 안에 Notion에서 되살릴 수 있습니다). 내릴까요?`)) return;
    note = { msg: `${act === 'archive' ? '내리는' : '올리는'} 중입니다…` }; store.touch('panel');
    const r = await fetch('/api/publish', { method: 'POST', headers: store.headers(true), body: JSON.stringify({ path, action: act }) });
    const j = await r.json().catch(() => ({}));
    note = r.ok ? { msg: { created: '새 페이지로 올렸습니다.', updated: '같은 페이지에 덮어썼습니다.', unchanged: '바뀐 것이 없어 건너뛰었습니다.', archived: '휴지통으로 보냈습니다.' }[j.action] || '마쳤습니다.' }
      : { bad: true, msg: `${j.refused || j.detail || r.status}` };
    await load(true);
  }

  return { html, onClick, load };
}
