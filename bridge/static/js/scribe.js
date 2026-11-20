// 서기실 창(12a, 11-06) — 서기를 누르면 패널에 뜬다. D2(11-11)에 한 목록으로 정리했다:
//   물어보기 · 할 일 한 목록(밀린 수는 줄 옆, 받은 할 일은 숫자만) · 포트폴리오 쓰기(11-15: 글 N편 가운데 코드가 바뀐 편 M + [갱신])
//   · 포트폴리오 게시 / 기술문서 게시(둘로 나눔, 접힘 기본 — 접은 채 숫자만).
// 시킬 일은 worktree 서기 세션을 띄운다(합치기가 사람의 검토). Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py).
// 조용한 고장 금지: 못 읽은 수는 0이 아니라 「읽지 못했습니다」로 보인다.

import { esc, ago, keep, keepSet } from './render.js';
import { createPostitBlock } from './postit.js';

// 메뉴 순서 — 문서 점검이 앞이다(찾기 → 고치기가 핵심 흐름). 문서 고치기(docfix)는 메뉴에 없고 결과에서만 뜬다.
// 기술문서 쓰기(techdoc, 11-15)는 원고 폴더가 notion/인 프로젝트만(서버가 pj.techdoc을 줄 때만 보인다)
export const ORDER = ['doccheck', 'later', 'trim', 'techdoc'];
const UNREAD = '읽지 못했습니다';

// 편이 있는 일(11-19 foreman-125, 서버 bridge/scribe_room.py PIECE_TASKS와 짝). 포트폴리오 쓰기와 기술문서 쓰기가 같은 [갱신]과
// 편 목록 단추를 쓴다. tps는 서버가 준 편 목록({slug, title, commits, why, blocked}), title은 일 이름(「포트폴리오 쓰기」).
// [갱신]은 코드가 가장 많이 바뀐 편 하나(막힌 편은 뺀다), 편 목록은 편마다 [고쳐 쓰기]. 막힌 편은 단추를 끄고 까닭을 호버로
// 11-19 [전체](all): 코드가 바뀐 편(셀 수 없는 편 포함)을 줄을 세워 한 편씩(bridge/scribe_queue.py). 줄은 프로젝트에 하나라
// 도는 줄(queue, 포트폴리오든 기술문서든)이 있으면 끈다
export function pieceButtons(task, title, tps, busy = false, queue = null) {
  const cnt = (t) => (t.commits === null || t.commits === undefined ? -1 : t.commits);
  const nAll = tps.filter((t) => t.commits !== 0).length;
  const qOn = !!queue && !queue.error && (queue.state === 'running' || queue.state === 'paused');
  const allWhy = qOn ? '이미 도는 줄이 있습니다. 끝나거나 닫은 뒤에 세웁니다.' : !nAll ? '코드가 바뀐 편이 없습니다.' : '';
  const all = `<button type="button" class="small" data-sc-queue="${esc(task)}" data-n="${nAll}"${busy || allWhy ? ' disabled' : ''} title="${esc(allWhy
    ? `전체 — 지금은 줄을 세울 수 없습니다. ${allWhy}`
    : `전체 — 코드가 바뀐 편 ${nAll}편을 줄을 세워 한 편씩 서기에게 고쳐 쓰게 합니다. 한 편이 main에 합쳐져야 다음 편이 뜹니다.`)}">전체</button>`;
  const cand = tps.filter((t) => !t.blocked && t.commits).sort((a, b) => cnt(b) - cnt(a))[0];
  const upd = cand
    ? `<button type="button" class="small" data-sc-task="${esc(task)}" data-topic="${esc(cand.slug)}" data-name="${esc(cand.title)}"${busy ? ' disabled' : ''} title="갱신 — 코드가 가장 많이 바뀐 편 「${esc(cand.title)}」(코드 바뀐 커밋 ${cand.commits}개)을 서기에게 고쳐 쓰게 합니다. 다른 편은 아래 목록에서 고릅니다.">갱신</button>`
    : `<button type="button" class="small" disabled title="갱신 — 지금 고쳐 쓰게 할 편이 없습니다(코드가 바뀐 편이 없거나 모두 열려 있습니다).">갱신</button>`;
  const rows = tps.map((t) => {
    const n = t.commits === null || t.commits === undefined
      ? `<span class="warn" title="${esc(t.why || '')}">셀 수 없음</span>` : t.commits ? `<span class="warn">코드 바뀐 커밋 ${t.commits}</span>` : '<span class="ok">그대로</span>';
    return `<div class="sc-row"><div class="small"><b>${esc(t.title)}</b> <code>${esc(t.slug)}</code> ${n}${t.blocked ? ` <span class="muted">(${esc(t.blocked)})</span>` : ''}</div>
        <button type="button" class="small" data-sc-task="${esc(task)}" data-topic="${esc(t.slug)}" data-name="${esc(t.title)}"${busy || t.blocked ? ' disabled' : ''} title="${esc(t.blocked ? `${title} — 지금은 시킬 수 없습니다. ${t.blocked}` : `${title} — 「${t.title}」을 서기에게 고쳐 쓰게 합니다.`)}">고쳐 쓰기</button></div>`;
  }).join('');
  return { upd, rows, all };
}

// 서기실 전체 줄 칸(11-19, bridge/scribe_queue.py view). 줄에 선 편 목록, 지금 편, 멈추기와 이어가기, 실패한 편과 미룬 편 목록.
// 판단거리(편마다 「사람이 정할 것」)와 미룬 카드는 줄이 끝나면 한 번에 보인다(도는 동안은 수만). 오래 안 끝나는 편은 빨갛게
const Q_STATE = { waiting: '기다림', running: '도는 중', failed: '실패', held: '미룸' };
export function queueBlock(q, tasks = {}, busy = false) {
  if (!q) return '';
  if (q.error) return `<div class="small bad sc-line"><b>전체 줄</b>: ${esc(q.error)}</div>`;
  const k = q.counts || {};
  const name = (tasks[q.task] || {}).title || q.task;
  const done = q.state === 'done';
  const open = (sid) => (sid ? ` <button type="button" class="small ghost" data-sc-open="${sid}" title="세션 열기 — 이 편 서기 세션의 [세션 정리] 탭을 엽니다. 합치기 카드와 diff를 봅니다.">세션 열기</button>` : '');
  const stateOf = (i) => (i.state === 'merged' ? (i.how === 'auto' ? '합침(카드 없이)' : '합침(카드로)') : Q_STATE[i.state] || i.state);
  const btn = q.state === 'running'
    ? `<button type="button" class="small" data-sq-act="pause" data-qid="${q.id}"${busy ? ' disabled' : ''} title="멈추기 — 지금 도는 편은 끝까지 돌고, 다음 편은 띄우지 않습니다.">멈추기</button>`
    : q.state === 'paused'
      ? `<button type="button" class="small primary" data-sq-act="resume" data-qid="${q.id}"${busy ? ' disabled' : ''} title="이어가기 — 멈춘 줄을 다시 돌립니다. 지금 도는 편이 없으면 다음 편을 바로 띄웁니다.">이어가기</button>`
      + `<button type="button" class="small ghost" data-sq-act="close" data-qid="${q.id}"${busy ? ' disabled' : ''} title="줄 닫기 — 남은 편을 띄우지 않고 줄을 닫습니다. 지금 도는 편 세션은 건드리지 않습니다.">줄 닫기</button>`
      : `<button type="button" class="small ghost" data-sq-act="close" data-qid="${q.id}"${busy ? ' disabled' : ''} title="줄 닫기 — 끝난 줄을 서기실에서 치웁니다. 판단거리와 미룬 카드를 다 봤을 때 누릅니다.">줄 닫기</button>`;
  const head = `<div class="sc-row"><div class="small"><b>전체 줄</b> ${esc(name)} <span class="${q.state === 'paused' ? 'warn' : done ? 'ok' : 'muted'}">${esc(q.state_ko || q.state)}</span>
    <span class="muted">합침 ${k.merged || 0}(카드 없이 ${k.auto || 0}, 카드로 ${k.card || 0}), 실패 ${k.failed || 0}, 미룸 ${k.held || 0}, 남음 ${k.waiting || 0}</span></div><div class="hand-btns">${btn}</div></div>`;
  const c = q.current;
  const now = c
    ? `<div class="small ${c.stalled ? 'bad' : ''}">지금 편 「${esc(c.title)}」 <span class="muted">세션 ${c.session_id}${c.minutes !== null && c.minutes !== undefined ? `, ${c.minutes}분째` : ''}</span>${c.stalled ? ` 오래 안 끝남(${q.stall_min}분 넘음)` : ''}${c.reason ? `: ${esc(c.reason)}` : ''}${open(c.session_id)}</div>`
    : '';
  const pausedNote = q.state === 'paused' ? `<div class="small warn">${esc(q.note || '멈춤')}${c ? '' : '. 지금 도는 편이 없습니다.'}</div>` : '';
  const items = q.items || [];
  const listRows = items.map((i) => `<div class="small">${i.pos + 1}. ${esc(i.title)} <code>${esc(i.topic)}</code> <span class="${i.state === 'failed' ? 'bad' : i.state === 'held' ? 'warn' : i.state === 'merged' ? 'ok' : 'muted'}">${esc(stateOf(i))}</span></div>`).join('');
  const list = `<details class="hand"${keep(`scribe:queue:${q.id}:list`)}><summary class="small muted" title="줄 목록 — 줄에 선 편과 편마다 지금 상태입니다. 합친 편도 남습니다.">줄 목록 ${items.length}</summary>${listRows}</details>`;
  const failed = items.filter((i) => i.state === 'failed');
  const failHtml = failed.length ? `<div class="small bad"><b>실패 ${failed.length}</b> <span class="muted">줄은 멈추지 않고 다음 편으로 넘어갔습니다</span>${
    failed.map((i) => `<div class="sc-row"><div class="small">· 「${esc(i.title)}」: ${esc(i.reason || '')}</div>${open(i.session_id)}</div>`).join('')}</div>` : '';
  const held = items.filter((i) => i.state === 'held');
  const heldHtml = !held.length ? '' : done
    ? `<div class="small warn"><b>미룬 카드 ${held.length}</b> <span class="muted">사람 승인입니다. 세션을 열어 합치기 카드를 누릅니다</span>${
      held.map((i) => `<div class="sc-row"><div class="small">· 「${esc(i.title)}」: ${esc(i.reason || '')}</div>${open(i.session_id)}</div>`).join('')}</div>`
    : `<div class="small warn">미룬 카드 ${held.length}(사람 승인, 줄이 끝나면 모아 보입니다)</div>`;
  const dec = items.filter((i) => i.has_decisions);
  const decHtml = !dec.length ? '' : done
    ? `<div class="small"><b>판단거리 ${dec.length}편</b> <span class="muted">편마다 서기가 남긴 「사람이 정할 것」입니다</span>${
      dec.map((i) => `<div class="sc-answer"><b>「${esc(i.title)}」</b><div style="white-space:pre-wrap">${esc(i.decisions || '')}</div></div>`).join('')}</div>`
    : `<div class="small muted">판단거리 ${dec.length}편(줄이 끝나면 한 번에 보입니다)</div>`;
  return `<div class="hand sc-queue">${head}${now}${pausedNote}${failHtml}${heldHtml}${decHtml}${list}</div>`;
}

// 일마다 옆에 붙는 밀린 수 — 「알려진 한계 쓰기 — 13개 밀림」. 밀린 것이 없으면 이름만(빈 문자열)
export function behindText(k, b) {
  if (!b) return { text: '', cls: 'muted', tip: '' };
  if (b.unread) return { text: UNREAD, cls: 'bad', tip: b.unread };
  const n = b.n || 0;
  if (!n) return { text: '', cls: 'muted', tip: '' };
  const text = k === 'trim' ? `${n}줄 넘음` : k === 'doccheck' ? `결과 없는 단계 ${n}개`
    : k === 'techdoc' ? `코드가 바뀐 편 ${n}` : b.stale ? `${n}개 밀림` : `${n}개 쌓임`;
  return { text, cls: b.stale ? 'warn' : 'muted', tip: b.why || '' };
}

// 원고(노션 기술문서 · 포트폴리오, 11-15)의 머리줄 — 「글 N편 가운데 코드가 바뀐 편 M」. 셀 수 없는 편(머리 주석 없음 등)은 따로
export function piecesText(t) {
  if (!t || !t.total) return { text: '아직 쓴 글이 없습니다', cls: 'muted' };
  if (typeof t.changed !== 'number') return { text: `글 ${t.total}편, 코드가 바뀐 편은 ${UNREAD}`, cls: 'bad' };   // 11-15 전 서버 응답
  const extra = t.unknown ? `, 머리 주석을 읽지 못한 편 ${t.unknown}` : '';
  return { text: `글 ${t.total}편 가운데 코드가 바뀐 편 ${t.changed}${extra}`, cls: t.changed || t.unknown ? 'warn' : 'muted' };
}

const PORT = 'portfolio/';

// 게시 확인 창(11-15 기술문서, 11-20 포트폴리오도) — 올릴 것과 「그 뒤 다루는 코드가 바뀐 편」을 보인다. 막지는 않는다
export function techdocAsk(label, d) {
  const port = d.src === PORT;
  const relink = d.relink || 0;
  const parts = [d.new ? `새 ${d.new}` : '', d.changed - relink > 0 ? `바뀜 ${d.changed - relink}` : '', relink ? `링크만 ${relink}` : '',
    d.deleted ? `지워짐 ${d.deleted}` : ''].filter(Boolean);
  const lines = [port
    ? `${label}의 portfolio/ 글을 Notion [포트폴리오]에 올립니다(${parts.join(', ') || '바뀐 것 없음'}).`
    : `${label}의 notion/ 원고를 Notion [기술문서]에 올립니다(${parts.join(', ') || '바뀐 것 없음'}).`];
  if (d.deleted) lines.push(`git에서 지운 ${d.deleted}편의 Notion 페이지는 휴지통으로 보냅니다(30일 안에 Notion에서 되살릴 수 있습니다).`);
  if (d.code_changed) lines.push(`읽은 커밋 뒤 다루는 코드가 바뀐 편이 ${d.code_changed}편 있습니다. 올린 뒤에 고쳐 써도 됩니다.`);
  if (d.code_unknown) lines.push(`머리 주석을 읽지 못한 편이 ${d.code_unknown}편 있습니다. 코드가 바뀌었는지 알 수 없습니다.`);
  if (port) lines.push('새 편이 생기면 번호순으로 다시 세웁니다.');
  lines.push('사람이 Notion에서 고친 페이지는 덮지 않습니다.', '', '올릴까요?');
  return lines.join('\n');
}

// 접은 채로 보이는 숫자 한 줄 — 「게시됨 10」. 바뀜 가운데 링크만 다시 걸면 되는 편(11-20)은 따로 센다(글이 바뀐 줄 알지 않게)
export function pubCounts(p) {
  if (!p) return { text: UNREAD, bad: true };
  const relink = p.relink || 0;
  const extra = [p.new ? `새 ${p.new}` : '', p.changed - relink > 0 ? `바뀜 ${p.changed - relink}` : '', relink ? `링크만 ${relink}` : '',
    p.deleted ? `지워짐 ${p.deleted}` : '', p.broken ? `못 읽음 ${p.broken}` : '']
    .filter(Boolean);
  return { text: `게시됨 ${p.published}${extra.length ? ` · ${extra.join(' · ')}` : ''}`, bad: false, behind: extra.length > 0 };
}

// 사람 수정으로 멈춘 편의 덮기 단추(11-19). 전에는 접는 칸 「할 일」 안 맨 위에 있어, 칸을 접어 두면 단추가 안 보였다.
// 이제 접히지 않는 게시 줄 바로 아래(「사람이 고쳐 멈춤 N」을 읽는 자리)에 둔다. 「할 일」 칸은 펴지 않고 머리에 「덮기 N」만.
// 11-20 묶음마다: src가 portfolio/면 포트폴리오 게시 줄 아래, 아니면 기술문서 게시 줄 아래(서버가 줄마다 src를 단다).
// 「멈춤 N」이 보이는데 단추가 없으면 그 까닭을 쓴다(조용히 비지 않게): 목록을 못 읽었거나, 지금 덮을 편이 없거나
export function heldRows(pj, busy = false, src = null) {
  const port = src === PORT;
  const items = (pj.items || []).filter((x) => x.kind === 'publish' && x.act === 'force' && (x.src === PORT) === port);
  const rows = items.map((x) => `<div class="sc-row"><div class="small bad"><b>${esc(x.title)}</b> <span class="muted">(${esc(x.why)})</span></div>
      <button type="button" class="small danger" data-pub="publish" data-force="1" data-proj="${esc(x.project)}" data-path="${esc(x.path)}"${busy ? ' disabled' : ''} title="Notion 수정 버리고 덮기 — Notion에서 사람이 고친 곳을 버리고 git 원본으로 덮습니다. 살릴 수정이면 먼저 git에 옮겨 주세요.">Notion 수정 버리고 덮기</button></div>`).join('');
  if (items.length) return rows;
  const d = port ? pj.port_pub : pj.docs_pub;
  if (!d || d.error) return '';
  if (d.held_error) return `<div class="small bad">사람이 고쳐 멈춘 편 목록을 ${UNREAD}(${esc(d.held_error)}). 덮기 단추를 보일 수 없습니다.</div>`;
  // 목록 자체를 모르는 경우(옛 브리지가 멈춘 편 행을 남기지 않았다). 사람이 기다릴지 맞추기를 돌릴지 정하게 수를 보인다
  if (d.held_list_missing) return `<div class="small warn">멈춘 ${d.held_list_missing}편의 목록이 아직 없습니다. 다음 맞추기 뒤에 보입니다.</div>`;
  if (d.last && d.last.held && d.held_buttons === 0) {
    return `<div class="small warn">사람이 고쳐 멈춘 ${d.last.held}편 가운데 지금 덮을 편이 없습니다. 그 뒤 git이 다시 바뀌었거나 이미 맞춰졌습니다. 다음에 올릴 때 다시 봅니다.</div>`;
  }
  return '';
}

export function createScribe(store) {
  let todo = null, note = null, busy = false, cur = 'foreman';
  // 11-17 포트폴리오 게시는 프로젝트마다: 고른 프로젝트(room)의 게시 목록을 따로 들고, 읽은 시각도 따로 센다
  const pubs = {}, pubBad = {}, at = {};
  let todoBad = false;          // 마지막으로 읽기에 실패했나. 지난 것을 보이되 「읽지 못했습니다」를 함께 보인다
  let askText = '', asking = false, answer = null, pickOpened = '';
  const postit = createPostitBlock(store);        // 11-15 머리 탭 포스트잇과 같은 목록 · 같은 동작

  async function load(force = false, room = cur) {
    if (!force && Date.now() - (at[room] || 0) < 20000) return;
    at[room] = Date.now();
    try {
      const [t, p] = await Promise.all([fetch('/api/scribe/todo', { headers: store.headers() }),
        fetch(`/api/publish?project=${encodeURIComponent(room)}`, { headers: store.headers() })]);
      todoBad = !t.ok; pubBad[room] = !p.ok;
      todo = t.ok ? await t.json() : todo;
      if (p.ok) pubs[room] = await p.json();
    } catch { todoBad = true; pubBad[room] = true; /* 못 읽으면 지난 것을 보이고, 못 읽었다고 알린다 */ }
    store.touch('panel');
  }

  // 포트폴리오 게시(11-20 기술문서와 같은 꼴) — 접히지 않는 한 줄에 숫자, 「마지막으로 올림」, [Notion에 올리기] 하나, 실패, 덮기 단추.
  // [Notion에 올리기] 한 번이 새 편 만들기, 바뀐 편 고치기, 원본이 사라진 편 휴지통으로, 번호순 다시 세우기를 다 한다(서버 docsync.sync).
  // 한 편씩 올리는 단추와 [원본 없는 페이지 내리기]는 없앴다(두 벌이면 한쪽만 고장 난다). 편 목록은 접힘 기본이고 상태, 내리기, 열기만
  function portPubBlock(room, pj, label) {
    const tag = '<b>포트폴리오 게시</b>';
    const tip = 'title="포트폴리오 게시 — 바깥 독자에게 내는 portfolio/ 글을 Notion [포트폴리오]에 올립니다. 자동으로 올라가지 않고 [Notion에 올리기]를 눌러야만 올라갑니다."';
    // 11-17 고른 프로젝트의 portfolio/ 상태(전에는 FOREMAN만 보고 다른 프로젝트는 「게시하지 않습니다」였다)
    const pub = pubs[room];
    if (pubBad[room] && !pub) return `<div class="small bad sc-line" ${tip}>${tag}: 게시 목록을 ${UNREAD}.</div>`;
    if (!pub) return `<div class="small muted sc-line" ${tip}>${tag}: 게시 목록을 읽는 중입니다.</div>`;
    if (!pub.enabled) return `<div class="small warn sc-line" ${tip}>${tag}: ${esc(pub.why || 'Notion 게시가 꺼져 있습니다.')}</div>`;
    const docs = pub.docs || [];
    const ps = pub.portfolio || {};
    if (ps.has_dir === null) return `<div class="small bad sc-line" ${tip}>${tag}: 원본 커밋${ps.ref ? ` ${esc(ps.ref)}` : ''}을 ${UNREAD}.</div>`;
    if (ps.has_dir === false && !docs.length) return `<div class="small muted sc-line" title="포트폴리오 게시 — 이 프로젝트의 main에 portfolio/ 폴더가 생기면 여기서 Notion에 올립니다.">${tag}: 아직 없음. 이 프로젝트에는 portfolio/ 폴더가 없습니다.</div>`;
    // Notion 자리가 정해지지 않은 프로젝트는 상태만 보이고 게시를 막는다(조용히 다른 자리에 올리지 않게. 서버도 같은 까닭으로 거절)
    const noPlace = ps.place === false ? (ps.place_why || 'Notion 자리가 정해지지 않았습니다.') : '';
    const d = pj.port_pub;
    let head;
    if (!d) head = `<div class="small muted">${tag}: 게시 상태를 읽는 중입니다.</div>`;
    else if (d.error) head = `<div class="small bad">${tag}: 게시 상태를 ${UNREAD}(${esc(d.error)}).</div>`;
    else {
      const c = pubCounts(d);
      const behindN = (d.new || 0) + (d.changed || 0) + (d.deleted || 0);
      const pc = piecesText({ total: d.total, changed: d.code_changed || 0, unknown: d.code_unknown || 0 });
      const btn = behindN || d.broken
        ? `<button type="button" class="small" data-pub="docsync" data-proj="${esc(room)}" data-path="${PORT}" data-ask="${esc(techdocAsk(label || room, d))}"${busy || noPlace ? ' disabled' : ''} title="${esc(noPlace
          ? `Notion에 올리기 — 지금은 할 수 없습니다. ${noPlace}`
          : 'Notion에 올리기 — portfolio/ 글 가운데 바뀐 편만 Notion [포트폴리오]에 올리고, git에서 지운 편의 페이지는 휴지통으로 보내고, 번호순으로 다시 세웁니다. 올리기 전에 확인 창을 띄웁니다.')}">Notion에 올리기</button>` : '';
      const l = d.last;
      const failed = l && l.failed ? `<div class="small bad">실패: ${esc(l.failed_first || '')}</div>` : '';
      head = `<div class="sc-row" ${tip}><div class="small">${tag} <span class="${c.behind || noPlace ? 'warn' : 'ok'}">${esc(c.text)}${noPlace ? ', Notion 자리 없음' : ''}</span> <span class="${pc.cls}">/ ${esc(pc.text)}</span>
      <div class="muted">${esc(lastPublishedText(d))}</div>${failed}</div>${btn}</div>`;
    }
    const placeLine = noPlace ? `<div class="small warn">게시할 수 없습니다: ${esc(noPlace)}</div>` : '';
    const rows = docs.map((x) => {
      const st = x.status === 'new' ? '<span class="muted">안 올림</span>' : x.status === 'archived' ? '<span class="muted">휴지통</span>'
        : x.gone ? '<span class="warn" title="원본 없음 — git에서 지운 편입니다. 다음 [Notion에 올리기]가 휴지통으로 보냅니다.">원본 없음</span>'
          : x.relink ? '<span class="warn" title="링크를 다시 걸어야 함 — 글은 그대로이고, 올릴 때 가리킨 편이 Notion에 없어 링크만 못 걸었습니다. [Notion에 올리기]가 다시 겁니다.">링크를 다시 걸어야 함</span>'
            : x.changed ? '<span class="warn">원본이 바뀜</span>' : '<span class="ok">게시됨</span>';
      const btns = [
        x.status === 'published' ? `<button type="button" class="small ghost" data-pub="archive" data-proj="${esc(room)}" data-path="${esc(x.path)}"${busy ? ' disabled' : ''} title="내리기 — Notion 페이지를 휴지통으로 보냅니다(30일 안에 되살릴 수 있습니다). 우리가 만든 페이지만 됩니다. 원본이 git에 남아 있으면 다음 [Notion에 올리기]가 다시 올립니다.">내리기</button>` : '',
        x.url ? `<a class="small" href="${esc(x.url)}" target="_blank" rel="noopener" title="Notion에서 열기 — 새 탭으로 엽니다.">열기</a>` : '',
      ].join(' ');
      return `<div class="sc-row"><div class="small"><code>${esc(x.path)}</code> ${st}${x.commit ? ` <span class="muted">· 커밋 ${esc(x.commit)}</span>` : ''}${x.updated_at ? ` <span class="muted">· ${ago(x.updated_at)}</span>` : ''}</div><div class="hand-btns">${btns}</div></div>`;
    }).join('');
    const list = `<details class="hand"${keep(`scribe:${room}:pubport`)}><summary class="small muted" title="편 목록 — portfolio/ 편마다 Notion 게시 상태입니다. 올리기는 위 [Notion에 올리기] 하나로 합니다.">편 목록 ${docs.length}</summary>${rows || '<p class="small muted">게시할 글이 없습니다(main의 portfolio/*.md).</p>'}</details>`;
    return `${head}${placeLine}${heldRows(pj, busy, PORT)}${list}`;
  }

  // 「마지막으로 올림」(11-17). 서버가 DB 기록에서 읽어 준 값(d.last). 올린 길(한 편씩, 자동 맞추기, [Notion에 올리기])과 상관없다.
  // 「아직 올린 기록 없음」은 기록이 정말 없을 때만, 읽지 못했으면 없다고 하지 않고 읽지 못했다고 한다
  function lastPublishedText(d) {
    if (d.last_error) return `마지막으로 올린 때를 ${UNREAD}`;
    const l = d.last;
    if (!l) return 'Notion에 올린 기록이 없습니다';      // 11-17: 게시 기록(DB)에 이 원고 폴더의 글이 한 편도 없다는 뜻
    return `마지막으로 올림 ${l.at ? ago(new Date(l.at * 1000).toISOString()) : ''}: 올림 ${l.done}${l.held ? `, 사람이 고쳐 멈춤 ${l.held}` : ''}${l.failed ? `, 실패 ${l.failed}` : ''}`;
  }

  // 기술문서 게시 — docs/ 전체를 프로젝트별 Notion 페이지로 맞춘다. 읽기 API(docs_pub)가 준 숫자만 보인다
  function docsPubBlock(room, pj, label) {
    const tag = '<b>기술문서 게시</b>';
    const d = pj.docs_pub;
    // 원고 폴더가 notion/이면(11-15 FOREMAN) 자동 게시가 없고, 사람이 [Notion에 올리기]를 눌러야만 통으로 올라간다
    const manus = !!d && d.src === 'notion/';
    const tip = manus
      ? 'title="기술문서 게시 — notion/ 원고를 Notion [기술문서]에 올립니다. 자동으로 올라가지 않고 [Notion에 올리기]를 눌러야만 올라갑니다."'
      : 'title="기술문서 게시 — docs/의 기술 문서를 Notion에 맞춥니다. push 뒤 조용하면 바뀐 파일만 자동으로 올립니다."';
    if (pj.pub_error) return `<div class="small bad sc-line" ${tip}>${tag}: 게시 상태를 ${UNREAD}(${esc(pj.pub_error)}).</div>`;
    if (!d) return `<div class="small muted sc-line" ${tip}>${tag}: 이 프로젝트는 기술문서 게시가 꺼져 있거나 연결돼 있지 않습니다.</div>`;
    const c = pubCounts(d);
    const behindN = (d.new || 0) + (d.changed || 0) + (d.deleted || 0);
    if (manus) {
      const pc = piecesText({ total: d.total, changed: d.code_changed || 0, unknown: d.code_unknown || 0 });
      const ask = techdocAsk(label || room, d);
      const btn = behindN || d.broken
        ? `<button type="button" class="small" data-pub="docsync" data-proj="${esc(room)}" data-ask="${esc(ask)}"${busy ? ' disabled' : ''} title="Notion에 올리기 — notion/ 원고 가운데 바뀐 편만 Notion [기술문서]에 올립니다. 올리기 전에 확인 창을 띄웁니다.">Notion에 올리기</button>` : '';
      const l = d.last;
      const lastTxt = lastPublishedText(d);
      const failed = l && l.failed ? `<div class="small bad">실패: ${esc(l.failed_first || '')}</div>` : '';
      return `<div class="sc-row" ${tip}><div class="small">${tag} <span class="${c.behind ? 'warn' : 'ok'}">${esc(c.text)}</span> <span class="${pc.cls}">/ ${esc(pc.text)}</span>
      <div class="muted">${esc(lastTxt)}</div>${failed}</div>${btn}</div>${heldRows(pj, busy)}`;
    }
    const commits = d.behind_commits === null || d.behind_commits === undefined ? '맞춘 적 없음' : `push 대기 커밋 ${d.behind_commits}개`;
    const l = d.last;
    const lastTxt = lastPublishedText(d);
    const failed = l && l.failed ? `<div class="small bad">실패: ${esc(l.failed_first || '')}</div>` : '';
    const why = ((pj.items || []).find((x) => x.act === 'docsync' && x.src !== PORT) || {}).why;
    const btn = behindN || d.broken
      ? `<button type="button" class="small" data-pub="docsync" data-proj="${esc(room)}"${busy ? ' disabled' : ''} title="지금 맞추기 — 기다리지 않고 지금 바뀐 기술문서만 Notion에 올립니다. 사람이 Notion에서 고친 페이지는 덮지 않습니다.">지금 맞추기</button>` : '';
    return `<div class="sc-row" ${tip}><div class="small">${tag} <span class="${c.behind ? 'warn' : 'ok'}">${esc(c.text)}</span> <span class="muted">/ 문서 ${d.total}개 · ${commits}</span>
      <div class="muted">${esc(lastTxt)}${why ? ` (${esc(why)})` : ''}</div>${failed}</div>${btn}</div>${heldRows(pj, busy)}`;
  }

  // 포트폴리오 쓰기(11-15 화면 축) — 정해진 주제 없이 portfolio/ 파일이 편이다. 머리줄 「글 N편 가운데 코드가 바뀐 편 M」:
  // 편마다 머리 주석의 읽은 커밋 뒤 다루는 코드를 바꾼 feat · fix 커밋만 센다(저장소 전체 커밋을 세던 것을 고쳤다)
  function portfolioBlock(room, pj, tasks) {
    const pf = pj.portfolio;
    if (!pf || !tasks.portfolio) return '';
    const tps = pj.topics || [];
    const pc = piecesText(pf);
    const state = pf.unread ? `<span class="bad">${esc(pf.unread)}</span>` : `<span class="${pc.cls}">${esc(pc.text)}</span>`;
    // [갱신]은 코드가 가장 많이 바뀐 편을 고쳐 쓰게 한다. 어느 편인지는 아래 목록에서 따로 고를 수도 있다(기술문서 쓰기와 같은 pieceButtons)
    const { upd, rows, all } = pieceButtons('portfolio', tasks.portfolio.title || '포트폴리오 쓰기', tps, busy, pj.queue);
    const whole = `<button type="button" class="small" data-sc-task="portfolio" data-name=""${busy || pf.blocked ? ' disabled' : ''} title="${esc(pf.blocked ? `포트폴리오 쓰기 — 지금은 시킬 수 없습니다. ${pf.blocked}` : '포트폴리오 쓰기 — 서기가 보여줄 화면이 있으면 화면마다, 없으면 결정마다 편 목록을 정해 portfolio/ 글을 새로 쓰거나 고쳐 씁니다.')}">시키기</button>`;
    return `<div class="sc-row"><div class="small" title="포트폴리오 쓰기 — 서기가 화면마다 한 편씩 portfolio/에 씁니다. 바깥 독자용이라 저장소 링크 없이 게시됩니다."><b>포트폴리오 쓰기</b> ${state}</div><div class="hand-btns">${upd}${all}${whole}</div></div>
      <details class="hand"${keep(`scribe:${room}:topics`)}><summary class="small muted" title="편 목록 — 포트폴리오 편마다 읽은 커밋 뒤 다루는 코드를 바꾼 커밋 수를 보고, 한 편만 골라 고쳐 쓰게 합니다.">편 목록 ${tps.length}</summary>${rows || '<p class="small muted">아직 쓴 글이 없습니다.</p>'}</details>`;
  }

  // pick — 서기 머리 위 "정리할까요?"(11-09)를 눌러 열면 그 일(later)을 고른 채: 그 줄을 밝히고 [시키기]를 primary로.
  // 고르기만 한다 — 세션은 사람이 [시키기]를 눌러야 뜬다(자동은 제안까지만)
  function html(room, label, pick = null) {
    cur = room;
    load(false, room);
    // 고른 일이 있으면 할 일 칸을 한 번만 펼친다. 전에는 다시 그릴 때마다 펼쳐서 사람이 접어도 도로 풀렸다(11-17)
    if (!pick) pickOpened = '';
    else if (pickOpened !== `${room}:${pick}`) { pickOpened = `${room}:${pick}`; keepSet(`scribe:${room}:list`, true); }
    const tasks = (todo && todo.tasks) || {};
    const pj = (todo && todo.projects && todo.projects[room]) || {};
    const items = pj.items || [], opened = pj.open || [], blocked = pj.blocked || {}, behind = pj.behind || {};
    // 동시에 시키기(11-06, 11-15 개수 상한을 뺐다) — 같은 일 · 같은 파일만 막는다. 막힌 버튼은 끄고 까닭을 호버로(서버도 같은 판단)
    const go = (k, label = '시키기', pri = false) => {
      const why = blocked[k];
      return `<button type="button" class="small${pri && !why ? ' primary' : ''}" data-sc-task="${esc(k)}"${busy || why ? ' disabled' : ''} title="${esc(why ? `${(tasks[k] || {}).title || k} — 지금은 시킬 수 없습니다. ${why}` : `${(tasks[k] || {}).title || k} — 서기 세션을 작업방으로 띄워 맡깁니다. 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.`)}">${label}</button>`;
    };
    // 사람 수정으로 멈춘 파일의 덮기 줄은 11-19부터 이 칸이 아니라 아래 「기술문서 게시」 줄 밑(heldRows). 접어 둬도 보이게
    // 한 목록 — 「문서 할 일」(센 것)과 「시킬 일」(메뉴)이 같은 줄이다. 밀린 수는 이름 옆에
    let nBehind = 0;
    const rows = ORDER.filter((k) => tasks[k] && (k !== 'techdoc' || pj.techdoc)).map((k) => {
      const bt = behindText(k, behind[k]);
      if (bt.text && (bt.cls === 'warn' || bt.cls === 'bad')) nBehind += 1;
      // 기술문서 쓰기는 일 설명 대신 지금 원고 상태(글 N편 가운데 코드가 바뀐 편 M, 마지막으로 합친 지 며칠)
      const sub = blocked[k] ? blocked[k] : k === 'techdoc' ? pj.techdoc.why : tasks[k].desc;
      let extra = '', btns = go(k, '시키기', k === pick);
      // 11-19 foreman-125 기술문서 쓰기도 포트폴리오 쓰기처럼 [갱신](코드가 가장 많이 바뀐 편 하나)과 펼치는 편 목록(편마다 [고쳐 쓰기]).
      // [시키기]는 편 없이 통째로 쓰기 그대로
      if (k === 'techdoc') {
        const tps = pj.techdoc.topics || [];
        const pb = pieceButtons('techdoc', tasks.techdoc.title, tps, busy, pj.queue);
        btns = `<div class="hand-btns">${pb.upd}${pb.all}${btns}</div>`;
        extra = `<details class="hand"${keep(`scribe:${room}:techdoc_topics`)}><summary class="small muted" title="편 목록 — 기술문서 원고 편마다 읽은 커밋 뒤 다루는 코드를 바꾼 커밋 수를 보고, 한 편만 골라 고쳐 쓰게 합니다.">편 목록 ${tps.length}</summary>${pb.rows || '<p class="small muted">아직 쓴 원고가 없습니다.</p>'}</details>`;
      }
      if (k === 'doccheck' && pj.report) {          // 문서 점검 결과로 바로 고치기 — 찾기만 하고 끝나지 않게
        const r = pj.report;
        extra = r.fixed
          ? `<div class="sc-row"><div class="small muted">· 점검 결과 <code>${esc(r.name)}</code>: 고쳐서 합쳤습니다</div></div>`
          : `<div class="sc-row"><div class="small">· 점검 결과 <code>${esc(r.name)}</code> <span class="muted">(합쳐진 결과의 어긋남을 고칩니다)</span></div>
            <button type="button" class="small" data-sc-task="docfix" data-topic="${esc(r.name)}" data-name="${esc(r.name)}"${busy || blocked.docfix ? ' disabled' : ''} title="${esc(blocked.docfix ? `문서 고치기 — 지금은 시킬 수 없습니다. ${blocked.docfix}` : `문서 고치기 — ${r.name}에 적힌 어긋남을 서기가 문서에서 고칩니다. 코드는 건드리지 않고, 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.`)}">바로 고치기</button></div>`;
      }
      // 기술문서 쓰기는 뒤 한 줄(sub)이 「글 N편 가운데 코드가 바뀐 편 M」이라 앞의 「코드가 바뀐 편 M」은 같은 말이다(11-17). 뒤만 남기되
      // 색은 앞의 것을 따른다. 읽지 못했을 때와 막힌 까닭이 뒤 줄을 대신할 때는 앞 표시를 그대로 둔다(조용히 사라지지 않게)
      const dup = k === 'techdoc' && !blocked[k] && !(behind[k] && behind[k].unread) && sub === pj.techdoc.why;
      const showBt = bt.text && !dup;
      return `<div class="sc-row${k === pick ? ' sc-pick' : ''}"><div class="small"><b>${esc(tasks[k].title)}</b>${showBt ? ` <span class="${bt.cls}"${bt.tip ? ` title="${esc(bt.tip)}"` : ''}>${esc(bt.text)}</span>` : ''} <span class="${dup && bt.text ? bt.cls : 'muted'}">${esc(sub)}</span></div>
        ${btns}</div>${extra}`;
    }).join('');
    // 11-15 받은 할 일 숫자 줄은 없앴다 — 아래 포스트잇이 그 목록이다(머리 탭 포스트잇과 같은 것)
    const inboxRow = '';
    const openHtml = opened.length ? `<div class="small"><b>열려 있는 일 ${opened.length}</b> <span class="muted">합치거나 버리기 전까지(같은 일, 같은 파일을 고치는 일은 하나씩. 계획으로 띄운 서기 세션도 셉니다)</span>${
      opened.map((o) => `<div class="sc-row"><div class="small">· ${esc((tasks[o.task] || {}).title || o.title || '서기 세션')}${o.topic && tasks[o.task] ? `: ${esc(o.topic)}` : ''} <span class="muted">세션 ${o.session_id}</span></div>
        <button type="button" class="small" data-sc-open="${o.session_id}" title="세션 열기 — 이 서기 세션의 [세션 정리] 탭을 엽니다. 「작업방」에서 diff를 보고 합치거나 버립니다(끝난 세션은 화면에서 사라져도 여기서 엽니다).">세션 열기</button></div>`).join('')}</div>` : '';
    const pickHead = pick && tasks[pick] ? `<div class="small warn">「${esc(tasks[pick].title)}」을 골라 두었습니다. [시키기]를 눌러야 서기 세션이 뜹니다.</div>` : '';
    // 포스트잇(11-15) — 서기실에 들어가면 늘 접힌 채(11-15 사용자). 사람이 펼친 것만 keep이 기억한다
    const pst = pj.postit;
    const pstHead = !pst ? '' : `<span class="${pst.nudge ? 'warn' : 'muted'}">${pst.open}장${pst.unconfirmed ? `, 확인 전 ${pst.unconfirmed}` : ''}${pst.likely_done ? `, 끝난 것 같음 ${pst.likely_done}` : ''}</span>`;
    const postitHtml = `<details class="hand"${keep(`scribe:${room}:postit`)}><summary title="포스트잇 — 할 일을 적어 두는 종이입니다. 머리줄 포스트잇과 같은 목록입니다."><b>포스트잇</b> ${pstHead}</summary>
      ${postit.html(room, label, { noHead: true })}</details>`;
    const nAlert = items.filter((x) => x.kind === 'publish' && x.act === 'force').length;
    const bad = todoBad ? ` <span class="bad">· 지금 값을 ${UNREAD}(지난 값입니다)</span>` : '';
    // 덮기 N은 칸 머리에 따로(빨강). 단추는 칸 밖 「기술문서 게시」 아래라 칸을 접어 둔 기억은 그대로 둔다
    const coverTxt = nAlert ? ` <span class="bad" title="덮기 — 사람이 Notion에서 고쳐 멈춘 편입니다. 단추는 아래 「포트폴리오 게시」나 「기술문서 게시」 밑에 있습니다.">덮기 ${nAlert}(아래 게시 칸)</span>` : '';
    const sumCount = !todo ? '' : (nBehind + nAlert ? `<span class="warn">밀린 것 ${nBehind + nAlert}</span>${coverTxt}` : '<span class="muted">밀린 것 없음</span>');
    const listBody = !todo ? (todoBad ? `<p class="small bad">할 일을 ${UNREAD}.</p>` : '<p class="small muted">할 일을 읽는 중입니다.</p>') : pickHead + rows + inboxRow + openHtml;
    // 물어보기(11-10) — 세션 없이 읽기 전용으로 한 번 묻는다. 답만 하고 파일은 고치지 않는다(고치는 일은 아래 [문서 고치기])
    // 답 닫기(11-17 사용자): 답은 화면에만 있고(서버에 남기지 않는다) 닫으면 이 화면에서만 사라진다. 물은 글은 칸에 그대로 둔다
    const fixOne = answer && !answer.bad && answer.text
      ? `<button type="button" class="small" data-sc-fix="ask"${busy || blocked.docfix ? ' disabled' : ''} title="${esc(blocked.docfix ? `문서 고치기 — 지금은 시킬 수 없습니다. ${blocked.docfix}` : '문서 고치기 — 위 답을 고칠 목록으로 서기에게 맡깁니다. 서기가 저장소와 다시 맞는지 확인한 뒤 문서만 고치고, 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.')}">이 답대로 문서 고치기</button>` : '';
    const closeOne = answer ? `<button type="button" class="small ghost" data-sc-close="ask" title="답 닫기 — 위 답을 화면에서 닫습니다. 서버에는 아무것도 남기지 않고, 물은 글은 칸에 그대로 둡니다.">답 닫기</button>` : '';
    const fixBtn = fixOne || closeOne ? `<div class="hand-btns">${fixOne}${closeOne}</div>` : '';
    const askHtml = `<details class="hand"${keep(`scribe:${room}:ask`, true)}><summary title="물어보기 — 서기 세션을 띄우지 않고 문서 · 기록에 대해 한 번 묻습니다. 읽기만 하고 파일은 고치지 않습니다."><b>물어보기</b></summary>
      <textarea id="scAskText" rows="3" maxlength="2000" placeholder="문서나 기록에 대해 물어봅니다 (Ctrl+Enter로 보냅니다)"${asking ? ' disabled' : ''}>${esc(askText)}</textarea>
      <div class="hand-btns"><button type="button" class="small primary" data-sc-ask="1"${asking ? ' disabled' : ''} title="물어보기 — 답만 받습니다. 답에서 찾은 어긋남은 아래 [이 답대로 문서 고치기]로 시킵니다.">${asking ? '묻는 중…' : '물어보기'}</button></div>
      ${asking ? '<div class="small muted">서기가 문서를 읽고 있습니다… 보통 20초쯤 걸립니다.</div>' : ''}
      ${answer ? `<div class="small ${answer.bad ? 'bad' : ''} sc-answer" style="white-space:pre-wrap">${esc(answer.text)}</div>` : ''}${fixBtn}</details>`;
    return `<div class="small muted">${esc(label)} · 서기(문서 담당). 시킨 일은 작업방 세션으로 돌고, 끝나면 사람이 diff를 보고 합칩니다.</div>
      ${askHtml}
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}"${note.tip ? ` title="${esc(note.tip)}"` : ''}>${esc(note.msg)}</div>` : ''}
      ${postitHtml}
      ${queueBlock(pj.queue, tasks, busy)}
      <details class="hand"${keep(`scribe:${room}:list`, true)}><summary title="할 일 — 서기에게 시킬 일 한 목록입니다. 이름 옆 숫자는 밀린 정도이고, 숫자가 없으면 지금 밀린 것이 없습니다."><b>할 일</b> ${sumCount}${bad}</summary>${listBody}</details>
      <div class="hand">${portfolioBlock(room, pj, tasks)}${portPubBlock(room, pj, label)}${docsPubBlock(room, pj, label)}</div>
      ${pubBad[room] && pubs[room] ? `<div class="small bad">게시 목록을 ${UNREAD}(지난 값입니다).</div>` : ''}`;
  }

  // 글 칸은 다시 그려져도 남게 입력마다 적어 둔다(opanel이 #pSel의 input을 넘긴다)
  function onInput(ev, room) {
    if (ev.target && ev.target.id === 'scAskText') askText = ev.target.value;
    if (room) postit.onInput(ev, room);
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
      answer = r.ok ? { text: j.answer } : { bad: true, text: `답을 받지 못했습니다: ${j.refused || j.detail || r.status}. 글은 칸에 그대로 있습니다.` };
    } catch { answer = { bad: true, text: '답을 받지 못했습니다. 서버에 닿지 못했습니다. 글은 칸에 그대로 있습니다.' }; }
    asking = false;
    store.touch('panel');
  }

  // 서기 일 시키기 — 확인 창 → /api/scribe/start. 문서 고치기는 점검 결과(topic) 또는 물어보기 답(note)을 같이 보낸다
  async function start(room, label, k, topic, nameExtra, noteText) {
    const title = ((todo && todo.tasks) || {})[k]?.title || k;
    const name = title + (nameExtra ? `: ${nameExtra}` : '');
    if (!confirm(`${label}의 서기에게 「${name}」을 맡깁니다. 서기 세션이 작업방으로 뜨고(Opus), 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.\n\n진행할까요?`)) return;
    busy = true; note = { msg: `「${name}」: 서기 세션을 띄우는 중입니다…` }; store.touch('panel');
    const body = { project: room, task: k, topic: topic || null };
    if (noteText) body.note = noteText;
    try {
      const r = await fetch('/api/scribe/start', { method: 'POST', headers: store.headers(true), body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      note = r.ok ? { msg: `「${name}」: 서기 세션을 띄웠습니다. 서기실에서 일합니다.`, tip: `서기 세션 — tmux 창 ${j.tmux || '?'}` } : { bad: true, msg: `띄우지 못했습니다: ${j.refused || j.detail || r.status}` };
    } catch { note = { bad: true, msg: '띄우지 못했습니다. 서버에 닿지 못했습니다.' }; }
    busy = false;
    await load(true, room);
  }

  // 전체 줄(11-19). [전체]는 확인 창 뒤 줄을 세우고, [멈추기] [이어가기] [줄 닫기]는 줄 번호로. 결과는 note 한 줄
  async function queueAct(room, label, qb, qa) {
    let body;
    if (qb) {
      const k = qb.dataset.scQueue, title = ((todo && todo.tasks) || {})[k]?.title || k;
      if (!confirm(`${label}의 「${title}」에서 코드가 바뀐 편 ${qb.dataset.n}편을 줄을 세워 한 편씩 서기에게 맡깁니다.\n한 편이 main에 합쳐져야 다음 편이 뜹니다. 원고만 고친 편은 카드 없이 합쳐지고, 다른 파일을 고친 편은 합치기 카드로 갑니다.\n\n진행할까요?`)) return;
      body = { action: 'start', project: room, task: k };
    } else {
      const act = qa.dataset.sqAct;
      if (act === 'close' && !confirm('이 줄을 닫습니다. 남은 편은 띄우지 않고, 판단거리와 실패 목록도 서기실에서 사라집니다.\n\n닫을까요?')) return;
      body = { action: act, queue_id: Number(qa.dataset.qid) };
    }
    busy = true; note = { msg: '전체 줄을 바꾸는 중입니다…' }; store.touch('panel');
    try {
      const r = await fetch('/api/scribe/queue', { method: 'POST', headers: store.headers(true), body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      note = !r.ok ? { bad: true, msg: `하지 못했습니다: ${j.refused || j.detail || r.status}` }
        : body.action === 'start' ? { msg: `줄을 세웠습니다: ${j.items}편. 첫 편 서기 세션을 띄웠습니다.` } : { msg: j.note || '마쳤습니다.' };
    } catch { note = { bad: true, msg: '하지 못했습니다. 서버에 닿지 못했습니다.' }; }
    busy = false;
    await load(true, room);
  }

  async function onClick(ev, room, label, openSession) {
    // 열린 서기 일의 세션 열기(11-06) — 끝난 서기 세션은 3분 뒤 화면에서 사라지고, 서기실의 「서기」를 누르면 이 창이 떠서
    // 합치지 않은 worktree의 [합치기]에 닿을 길이 없었다
    const o = ev.target.closest('[data-sc-open]');
    if (o) { ev.preventDefault(); if (openSession) openSession(Number(o.dataset.scOpen)); return; }
    if (await postit.onClick(ev, room)) { await load(true, room); return; }      // 포스트잇 줄 · [저장] · [갱신]
    if (ev.target.closest('[data-sc-ask]')) { ev.preventDefault(); await ask(room); return; }
    if (ev.target.closest('[data-sc-close]')) { ev.preventDefault(); if (!asking) { answer = null; store.touch('panel'); } return; }
    if (ev.target.closest('[data-sc-fix]')) {        // 물어보기 답으로 바로 고치기
      ev.preventDefault();
      if (answer && !answer.bad && answer.text) await start(room, label, 'docfix', null, '물어보기 답', answer.text);
      return;
    }
    const qb = ev.target.closest('[data-sc-queue]'), qa = ev.target.closest('[data-sq-act]');
    if (qb || qa) { ev.preventDefault(); await queueAct(room, label, qb, qa); return; }
    const t = ev.target.closest('[data-sc-task]'), p = ev.target.closest('[data-pub]');
    if (!t && !p) return;
    ev.preventDefault();
    if (t) {
      const k = t.dataset.scTask, topic = t.dataset.topic || null;
      await start(room, label, k, topic, topic ? (t.dataset.name || topic) : '', null);
      return;
    }
    const act = p.dataset.pub, path = p.dataset.path || 'docs/', project = p.dataset.proj || room, force = !!p.dataset.force;
    if (act === 'archive' && !confirm(`${path}의 Notion 페이지를 휴지통으로 보냅니다(30일 안에 Notion에서 되살릴 수 있습니다).\n\n내릴까요?`)) return;
    if (force && !confirm(`${path}\nNotion에서 사람이 고친 곳을 버리고 git 원본으로 덮습니다. 살릴 수정이면 먼저 git에 옮겨 주세요.\n\n덮을까요?`)) return;
    if (act === 'docsync' && !force && p.dataset.ask && !confirm(p.dataset.ask)) return;      // 원고 — 코드가 바뀐 편을 보이고 묻는다
    const what = path.startsWith(PORT) ? '포트폴리오' : '기술문서';        // 11-20 포트폴리오도 같은 docsync 길(path로 묶음을 가른다)
    note = { msg: `${act === 'archive' ? '내리는' : act === 'docsync' || force ? `${what}를 맞추는` : '올리는'} 중입니다…` }; store.touch('panel');
    // 덮기는 그 파일만 force로 맞춘다(자동 맞추기와 같은 길 — 차례 · 기록이 같이 맞는다)
    const body = act === 'docsync' || force ? { path, action: 'docsync', project, force } : { path, action: act, project };
    const r = await fetch('/api/publish', { method: 'POST', headers: store.headers(true), body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    // 「→ 「제목」」을 링크로 못 바꾼 것(11-17): 없는 제목, 겹치는 제목, 아직 안 올라간 편. 조용히 글자로만 두지 않고 결과 줄에 보인다
    const warns = (j.warnings || []).map((w) => (typeof w === 'string' ? w : `${w.path}: ${w.warning}`));
    if (j.pending && j.pending.length) warns.push(`가리킨 편이 아직 Notion에 없어 링크를 못 걸었습니다(그 편을 올리면 다시 겁니다): ${j.pending.join(', ')}`);
    const warnTxt = warns.length ? ` 링크로 못 바꾼 참조 ${warns.length}: ${warns[0]}` : '';
    if (r.ok && j.action === 'docsync') {
      const arch = j.done.filter((x) => x.action === 'archived').length;
      note = { bad: !!(j.held.length || j.failed.length || warns.length),
        msg: `${what}를 맞췄습니다: 올림 ${j.done.length - arch}${arch ? ` · 휴지통으로 ${arch}` : ''}${j.held.length ? ` · 사람이 고쳐 멈춤 ${j.held.length}` : ''}${j.failed.length ? ` · 실패 ${j.failed.length}(${j.failed[0].path})` : ''}${warns.length ? '.' : ''}${warnTxt}` };
      await load(true, room);
      return;
    }
    note = r.ok ? { bad: !!warns.length, msg: ({ created: '새 페이지로 올렸습니다.', updated: '같은 페이지에 덮어썼습니다.', unchanged: '바뀐 것이 없어 건너뛰었습니다.', archived: '휴지통으로 보냈습니다.' }[j.action] || '마쳤습니다.') + warnTxt }
      : { bad: true, msg: `${j.refused || j.detail || r.status}` };
    await load(true, room);
  }

  return { html, onClick, onInput, onKey, load };
}
