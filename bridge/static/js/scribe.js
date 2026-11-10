// 서기실 창(12a, 11-06) — 서기를 누르면 패널에 뜬다. 할 일(기계로 센 것) · 시킬 일 여섯 · Notion 게시.
// 시킬 일은 worktree 서기 세션을 띄운다(합치기가 사람의 검토). Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py).

import { esc, ago, keep } from './render.js';

const ORDER = ['retro', 'doccheck', 'readme', 'trim', 'later', 'publish'];

export function createScribe(store) {
  let todo = null, pub = null, note = null, busy = false, at = 0;
  let askText = '', asking = false, answer = null;

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
    if (room !== 'foreman') return '<p class="small muted">Notion 게시는 지금 FOREMAN 프로젝트만 연결돼 있습니다.</p>';
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
    return rows || '<p class="small muted">게시할 글이 없습니다(main의 portfolio/*.md — 회고는 git에만 둡니다).</p>';
  }

  // pick — 서기 머리 위 "정리할까요?"(11-09)를 눌러 열면 그 일(later)을 고른 채: 그 줄을 밝히고 [시키기]를 primary로.
  // 고르기만 한다 — 세션은 사람이 [시키기]를 눌러야 뜬다(자동은 제안까지만)
  function html(room, label, pick = null) {
    load();
    const tasks = (todo && todo.tasks) || {};
    const pj = (todo && todo.projects && todo.projects[room]) || {};
    const items = pj.items || [], opened = pj.open || [], blocked = pj.blocked || {};
    // 동시에 시키기(11-06) — 같은 일 · 같은 파일 · 둘 넘게는 막는다. 막힌 버튼은 끄고 까닭을 호버로(서버도 같은 판단)
    const go = (k, label = '시키기', pri = false) => {
      const why = blocked[k];
      return `<button type="button" class="small${pri && !why ? ' primary' : ''}" data-sc-task="${esc(k)}"${busy || why ? ' disabled' : ''} title="${esc(why ? `${(tasks[k] || {}).title || k} — 지금은 시킬 수 없습니다. ${why}` : `${(tasks[k] || {}).title || k} — 서기 세션을 따로 작업(worktree)으로 띄워 맡깁니다. 끝나면 [끝내고 합치기]로 검토해 합칩니다.`)}">${label}</button>`;
    };
    const todoHtml = items.length ? items.map((x) => `<div class="sc-row"><div class="small"><b>${esc(x.title)}</b> <span class="muted">— ${esc(x.why)}</span></div>
        ${x.kind !== 'publish' ? go(x.kind) : x.act === 'docsync'
          ? `<button type="button" class="small" data-pub="docsync" data-proj="${esc(x.project)}" title="지금 맞추기 — 기다리지 않고 지금 바뀐 기술문서만 Notion에 올립니다. 사람이 Notion에서 고친 페이지는 덮지 않습니다.">지금 맞추기</button>`
          : x.act === 'force'
            ? `<button type="button" class="small danger" data-pub="publish" data-force="1" data-proj="${esc(x.project)}" data-path="${esc(x.path)}" title="Notion 수정 버리고 덮기 — Notion에서 사람이 고친 곳을 버리고 git 원본으로 덮습니다. 살릴 수정이면 먼저 git에 옮겨 주세요.">Notion 수정 버리고 덮기</button>`
            : ''}</div>`).join('')
      : '<p class="small muted">기계로 센 할 일이 없습니다.</p>';
    const openHtml = opened.length ? `<div class="small"><b>열려 있는 일 ${opened.length}</b> <span class="muted">— 합치거나 버리기 전까지(동시에 2개까지, 같은 파일을 고치는 일은 하나씩)</span>${
      opened.map((o) => `<div class="sc-row"><div class="small">· ${esc((tasks[o.task] || {}).title || o.task)}${o.topic ? ` — ${esc(o.topic)}` : ''} <span class="muted">세션 ${o.session_id}</span></div>
        <button type="button" class="small" data-sc-open="${o.session_id}" title="세션 열기 — 이 서기 세션의 [세션] 탭을 엽니다. 「따로 작업」에서 diff를 보고 합치거나 버립니다(끝난 세션은 화면에서 사라져도 여기서 엽니다).">세션 열기</button></div>`).join('')}</div>` : '';
    const nudge = pj.nudge;
    const pickHead = pick && tasks[pick] ? `<div class="small warn">정리할까요? — 받은 할 일이 쌓였습니다(${esc(nudge ? nudge.why : '')}). 「${esc(tasks[pick].title)}」을 골라 두었습니다. [시키기]를 눌러야 서기 세션이 뜹니다.</div>` : '';
    const taskHtml = pickHead + openHtml + ORDER.filter((k) => k !== 'publish' && tasks[k]).map((k) => `<div class="sc-row${k === pick ? ' sc-pick' : ''}"><div class="small"><b>${esc(tasks[k].title)}</b> <span class="muted">${esc(blocked[k] ? blocked[k] : tasks[k].desc)}</span></div>
        ${go(k, '시키기', k === pick)}</div>`).join('');
    // 포트폴리오 쓰기(12c, 11-06) — 주제마다 따로 연다(다른 주제는 다른 파일이라 동시에 둘까지 된다). 주제는 config/portfolio.toml
    const tps = pj.topics || [];
    const tpHtml = tps.length && tasks.portfolio ? `<details class="hand"${keep(`scribe:${room}:portfolio`)}><summary title="포트폴리오 쓰기 — 주제를 골라 서기가 portfolio/에 씁니다. 바깥 독자용이라 저장소 링크 없이 게시됩니다."><b>포트폴리오 쓰기</b> <span class="muted">${tps.filter((t) => t.written).length}/${tps.length} 씀</span></summary>${
      tps.map((t) => `<div class="sc-row"><div class="small"><b>${esc(t.title)}</b> ${t.written ? '<span class="ok">씀</span>' : '<span class="muted">안 씀</span>'} <span class="muted">— ${esc(t.blocked || t.about)}</span></div>
        <button type="button" class="small" data-sc-task="portfolio" data-topic="${esc(t.slug)}" data-name="${esc(t.title)}"${busy || t.blocked ? ' disabled' : ''} title="${esc(t.blocked ? `포트폴리오 쓰기 — 지금은 시킬 수 없습니다. ${t.blocked}` : `포트폴리오 쓰기 — 「${t.title}」을 서기에게 맡깁니다. ${t.written ? '이미 쓴 글을 고쳐 씁니다.' : '새로 씁니다.'}`)}">${t.written ? '고쳐 쓰기' : '쓰기'}</button></div>`).join('')}</details>` : '';
    // 물어보기(11-10) — 세션 없이 읽기 전용으로 한 번 묻는다. 답만 하고 파일은 고치지 않는다(고치는 일은 [시키기])
    const askHtml = `<details class="hand" open><summary title="물어보기 — 서기 세션을 띄우지 않고 문서 · 기록에 대해 한 번 묻습니다. 읽기만 하고 파일은 고치지 않습니다."><b>물어보기</b></summary>
      <textarea id="scAskText" rows="3" maxlength="2000" placeholder="문서나 기록에 대해 물어봅니다 (Ctrl+Enter로 보냅니다)"${asking ? ' disabled' : ''}>${esc(askText)}</textarea>
      <div class="hand-btns"><button type="button" class="small primary" data-sc-ask="1"${asking ? ' disabled' : ''} title="물어보기 — 답만 받습니다. 문서를 고치는 일은 아래 [시키기]로 시킵니다.">${asking ? '묻는 중…' : '물어보기'}</button></div>
      ${asking ? '<div class="small muted">서기가 문서를 읽고 있습니다… 보통 20초쯤 걸립니다.</div>' : ''}
      ${answer ? `<div class="small ${answer.bad ? 'bad' : ''} sc-answer" style="white-space:pre-wrap">${esc(answer.text)}</div>` : ''}</details>`;
    return `<div class="small muted">${esc(label)} · 서기 — 문서 담당. 시킨 일은 따로 작업(worktree) 세션으로 돌고, 끝나면 사람이 diff를 보고 합칩니다.</div>
      ${askHtml}
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}"${note.tip ? ` title="${esc(note.tip)}"` : ''}>${esc(note.msg)}</div>` : ''}
      <details class="hand"${keep(`scribe:${room}:todo`, true)}><summary title="문서 할 일 — 브리지가 CC를 부르지 않고 센 문서 정리 거리입니다(커밋은 쌓였는데 README가 그대로 등)."><b>문서 할 일 ${items.length}</b></summary>${todoHtml}</details>
      <details class="hand"${pick ? ' open' : keep(`scribe:${room}:tasks`, true)}><summary title="시킬 일 —고르면 서기 세션이 뜹니다."><b>시킬 일</b></summary>${taskHtml}${tpHtml}</details>
      <details class="hand"${keep(`scribe:${room}:publish`, true)}><summary title="Notion 게시 —원본은 git 마크다운, Notion은 게시판입니다. 버튼을 눌러야만 올라갑니다."><b>Notion 게시</b></summary>${pubBlock(room)}</details>`;
  }

  // 글 칸은 다시 그려져도 남게 입력마다 적어 둔다(opanel이 #pSel의 input을 넘긴다)
  function onInput(ev) {
    if (ev.target && ev.target.id === 'scAskText') askText = ev.target.value;
  }
  function onKey(ev, room) {
    if (ev.target && ev.target.id === 'scAskText' && ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); ask(room); }
  }

  async function ask(room) {
    const text = askText.trim();
    if (asking) return;
    if (!text) { answer = { bad: true, text: '묻는 글을 적어 주십시오.' }; store.touch('panel'); return; }
    asking = true; answer = null; store.touch('panel');
    try {
      const r = await fetch('/api/scribe/ask', { method: 'POST', headers: store.headers(true), body: JSON.stringify({ project: room, text }) });
      const j = await r.json().catch(() => ({}));
      answer = r.ok ? { text: j.answer } : { bad: true, text: `답을 받지 못했습니다 — ${j.refused || j.detail || r.status}. 글은 칸에 그대로 있습니다.` };
    } catch { answer = { bad: true, text: '답을 받지 못했습니다 — 서버에 닿지 못했습니다. 글은 칸에 그대로 있습니다.' }; }
    asking = false;
    store.touch('panel');
  }

  async function onClick(ev, room, label, openSession) {
    // 열린 서기 일의 세션 열기(11-06) — 끝난 서기 세션은 3분 뒤 화면에서 사라지고, 서기실의 「서기」를 누르면 이 창이 떠서
    // 합치지 않은 worktree의 [합치기]에 닿을 길이 없었다
    const o = ev.target.closest('[data-sc-open]');
    if (o) { ev.preventDefault(); if (openSession) openSession(Number(o.dataset.scOpen)); return; }
    if (ev.target.closest('[data-sc-ask]')) { ev.preventDefault(); await ask(room); return; }
    const t = ev.target.closest('[data-sc-task]'), p = ev.target.closest('[data-pub]');
    if (!t && !p) return;
    ev.preventDefault();
    if (t) {
      const k = t.dataset.scTask, topic = t.dataset.topic || null;
      const name = (((todo && todo.tasks) || {})[k]?.title || k) + (topic ? ` — ${t.dataset.name || topic}` : '');
      if (!confirm(`${label}의 서기에게 「${name}」을 맡깁니다. 서기 세션이 따로 작업(worktree)으로 뜨고(Opus), 끝나면 [끝내고 합치기]로 검토해 합칩니다. 진행할까요?`)) return;
      busy = true; note = { msg: `「${name}」 — 서기 세션을 띄우는 중입니다…` }; store.touch('panel');
      const r = await fetch('/api/scribe/start', { method: 'POST', headers: store.headers(true), body: JSON.stringify({ project: room, task: k, topic }) });
      const j = await r.json().catch(() => ({}));
      busy = false;
      note = r.ok ? { msg: `「${name}」 — 서기 세션을 띄웠습니다. 서기실에서 일합니다.`, tip: `서기 세션 — tmux 창 ${j.tmux || '?'}` } : { bad: true, msg: `띄우지 못했습니다 — ${j.refused || j.detail || r.status}` };
      await load(true);
      return;
    }
    const act = p.dataset.pub, path = p.dataset.path || 'docs/', project = p.dataset.proj || 'foreman', force = !!p.dataset.force;
    if (act === 'archive' && !confirm(`${path}의 Notion 페이지를 휴지통으로 보냅니다(30일 안에 Notion에서 되살릴 수 있습니다). 내릴까요?`)) return;
    if (force && !confirm(`${path} — Notion에서 사람이 고친 곳을 버리고 git 원본으로 덮습니다. 살릴 수정이면 먼저 git에 옮겨 주세요. 덮을까요?`)) return;
    note = { msg: `${act === 'archive' ? '내리는' : act === 'docsync' ? '기술문서를 맞추는' : '올리는'} 중입니다…` }; store.touch('panel');
    // 덮기는 그 파일만 force로 맞춘다(자동 맞추기와 같은 길 — 차례 · 기록이 같이 맞는다)
    const body = act === 'docsync' || force ? { path, action: 'docsync', project, force } : { path, action: act, project };
    const r = await fetch('/api/publish', { method: 'POST', headers: store.headers(true), body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (r.ok && j.action === 'docsync') {
      note = { bad: !!(j.held.length || j.failed.length),
        msg: `기술문서를 맞췄습니다 — 올림 ${j.done.length}${j.held.length ? ` · 사람이 고쳐 멈춤 ${j.held.length}` : ''}${j.failed.length ? ` · 실패 ${j.failed.length}(${j.failed[0].path})` : ''}` };
      await load(true);
      return;
    }
    note = r.ok ? { msg: { created: '새 페이지로 올렸습니다.', updated: '같은 페이지에 덮어썼습니다.', unchanged: '바뀐 것이 없어 건너뛰었습니다.', archived: '휴지통으로 보냈습니다.' }[j.action] || '마쳤습니다.' }
      : { bad: true, msg: `${j.refused || j.detail || r.status}` };
    await load(true);
  }

  return { html, onClick, onInput, onKey, load };
}
