// 서기실 창(12a, 11-06) — 서기를 누르면 패널에 뜬다. D2(11-11)에 한 목록으로 정리했다:
//   물어보기 · 할 일 한 목록(밀린 수는 줄 옆, 받은 할 일은 숫자만) · 포트폴리오 쓰기(마지막 쓴 시각 + 뒤 커밋 + [갱신])
//   · 포트폴리오 게시 / 기술문서 게시(둘로 나눔, 접힘 기본 — 접은 채 숫자만).
// 시킬 일은 worktree 서기 세션을 띄운다(합치기가 사람의 검토). Notion 게시는 세션 없이 [게시] 버튼(bridge/notion.py).
// 조용한 고장 금지: 못 읽은 수는 0이 아니라 「읽지 못했습니다」로 보인다.

import { esc, ago, keep } from './render.js';

// 메뉴 순서 — 문서 점검이 앞이다(찾기 → 고치기가 핵심 흐름). 문서 고치기(docfix)는 메뉴에 없고 결과에서만 뜬다
export const ORDER = ['doccheck', 'readme', 'later', 'trim', 'retro'];
const UNREAD = '읽지 못했습니다';

// 일마다 옆에 붙는 밀린 수 — 「README 갱신 — 13개 밀림」. 밀린 것이 없으면 이름만(빈 문자열)
export function behindText(k, b) {
  if (!b) return { text: '', cls: 'muted', tip: '' };
  if (b.unread) return { text: UNREAD, cls: 'bad', tip: b.unread };
  const n = b.n || 0;
  if (!n) return { text: '', cls: 'muted', tip: '' };
  const text = k === 'trim' ? `${n}줄 넘음` : k === 'doccheck' ? `결과 없는 단계 ${n}개` : b.stale ? `${n}개 밀림` : `${n}개 쌓임`;
  return { text, cls: b.stale ? 'warn' : 'muted', tip: b.why || '' };
}

// 접은 채로 보이는 숫자 한 줄 — 「게시됨 10」
export function pubCounts(p) {
  if (!p) return { text: UNREAD, bad: true };
  const extra = [p.new ? `새 ${p.new}` : '', p.changed ? `바뀜 ${p.changed}` : '', p.deleted ? `지워짐 ${p.deleted}` : '', p.broken ? `못 읽음 ${p.broken}` : '']
    .filter(Boolean);
  return { text: `게시됨 ${p.published}${extra.length ? ` · ${extra.join(' · ')}` : ''}`, bad: false, behind: extra.length > 0 };
}

export function createScribe(store) {
  let todo = null, pub = null, note = null, busy = false, at = 0;
  let todoBad = false, pubBad = false;          // 마지막으로 읽기에 실패했나 — 지난 것을 보이되 「읽지 못했습니다」를 함께 보인다
  let askText = '', asking = false, answer = null;

  async function load(force = false) {
    if (!force && Date.now() - at < 20000) return;
    at = Date.now();
    try {
      const [t, p] = await Promise.all([fetch('/api/scribe/todo', { headers: store.headers() }), fetch('/api/publish', { headers: store.headers() })]);
      todoBad = !t.ok; pubBad = !p.ok;
      todo = t.ok ? await t.json() : todo;
      pub = p.ok ? await p.json() : pub;
    } catch { todoBad = pubBad = true; /* 못 읽으면 지난 것을 보이고, 못 읽었다고 알린다 */ }
    store.touch('panel');
  }

  // 포트폴리오 게시 — 파일 목록은 접힘 기본, 접은 채 「게시됨 10」
  function portPubBlock(room, pj) {
    const head = (inner) => `<details class="hand"${keep(`scribe:${room}:pubport`)}><summary title="포트폴리오 게시 — 바깥 독자에게 내는 portfolio/ 글을 Notion에 올립니다. 원본은 git이고 버튼을 눌러야만 올라갑니다."><b>포트폴리오 게시</b> ${inner}</summary>`;
    if (room !== 'foreman') return '<div class="small muted sc-line"><b>포트폴리오 게시</b> — 이 프로젝트는 포트폴리오를 게시하지 않습니다(지금은 FOREMAN만 연결돼 있습니다).</div>';
    if (pubBad && !pub) return `<div class="small bad sc-line"><b>포트폴리오 게시</b> — 게시 목록을 ${UNREAD}.</div>`;
    if (!pub) return '<div class="small muted sc-line"><b>포트폴리오 게시</b> — 게시 목록을 읽는 중입니다.</div>';
    if (!pub.enabled) return `<div class="small warn sc-line"><b>포트폴리오 게시</b> — ${esc(pub.why || 'Notion 게시가 꺼져 있습니다.')}</div>`;
    const docs = pub.docs || [];
    const c = pubCounts({ published: docs.filter((d) => d.status === 'published').length, new: docs.filter((d) => d.status === 'new').length,
      changed: docs.filter((d) => d.status === 'published' && d.changed).length });
    const rows = docs.map((d) => {
      const st = d.status === 'new' ? '<span class="muted">안 올림</span>' : d.status === 'archived' ? '<span class="muted">휴지통</span>'
        : d.changed ? '<span class="warn">원본이 바뀜</span>' : '<span class="ok">게시됨</span>';
      const btns = [
        d.status !== 'published' || d.changed ? `<button type="button" class="small" data-pub="publish" data-path="${esc(d.path)}" title="게시 — main에 커밋된 원본을 Notion에 올립니다. 이미 올린 글이면 같은 페이지를 덮어씁니다.">${d.status === 'published' ? '다시 게시' : '게시'}</button>` : '',
        d.status === 'published' ? `<button type="button" class="small ghost" data-pub="archive" data-path="${esc(d.path)}" title="내리기 — Notion 페이지를 휴지통으로 보냅니다(30일 안에 되살릴 수 있습니다). 우리가 만든 페이지만 됩니다.">내리기</button>` : '',
        d.url ? `<a class="small" href="${esc(d.url)}" target="_blank" rel="noopener" title="Notion에서 열기 — 새 탭으로 엽니다.">열기</a>` : '',
      ].join(' ');
      return `<div class="sc-row"><div class="small"><code>${esc(d.path)}</code> ${st}${d.commit ? ` <span class="muted">· 커밋 ${esc(d.commit)}</span>` : ''}${d.updated_at ? ` <span class="muted">· ${ago(d.updated_at)}</span>` : ''}</div><div class="hand-btns">${btns}</div></div>`;
    }).join('');
    return `${head(`<span class="${c.behind ? 'warn' : 'muted'}">${esc(c.text)}</span>`)}${rows || '<p class="small muted">게시할 글이 없습니다(main의 portfolio/*.md — 회고는 git에만 둡니다).</p>'}</details>`;
  }

  // 기술문서 게시 — docs/ 전체를 프로젝트별 Notion 페이지로 맞춘다. 읽기 API(docs_pub)가 준 숫자만 보인다
  function docsPubBlock(room, pj) {
    const tag = '<b>기술문서 게시</b>';
    const tip = 'title="기술문서 게시 — docs/의 기술 문서를 Notion에 맞춥니다. push 뒤 조용하면 바뀐 파일만 자동으로 올립니다."';
    if (pj.pub_error) return `<div class="small bad sc-line" ${tip}>${tag} — 게시 상태를 ${UNREAD}(${esc(pj.pub_error)}).</div>`;
    const d = pj.docs_pub;
    if (!d) return `<div class="small muted sc-line" ${tip}>${tag} — 이 프로젝트는 기술문서 게시가 꺼져 있거나 연결돼 있지 않습니다.</div>`;
    const c = pubCounts(d);
    const behindN = (d.new || 0) + (d.changed || 0) + (d.deleted || 0);
    const commits = d.behind_commits === null || d.behind_commits === undefined ? '맞춘 적 없음' : `push 대기 커밋 ${d.behind_commits}개`;
    const l = d.last;
    const lastTxt = !l ? '아직 자동으로 맞춘 기록 없음'
      : `마지막 맞춤 ${l.at ? ago(new Date(l.at * 1000).toISOString()) : ''} — 올림 ${l.done}${l.held ? ` · 사람이 고쳐 멈춤 ${l.held}` : ''}${l.failed ? ` · 실패 ${l.failed}` : ''}`;
    const failed = l && l.failed ? `<div class="small bad">실패: ${esc(l.failed_first || '')}</div>` : '';
    const why = ((pj.items || []).find((x) => x.act === 'docsync') || {}).why;
    const btn = behindN || d.broken
      ? `<button type="button" class="small" data-pub="docsync" data-proj="${esc(room)}"${busy ? ' disabled' : ''} title="지금 맞추기 — 기다리지 않고 지금 바뀐 기술문서만 Notion에 올립니다. 사람이 Notion에서 고친 페이지는 덮지 않습니다.">지금 맞추기</button>` : '';
    return `<div class="sc-row" ${tip}><div class="small">${tag} <span class="${c.behind ? 'warn' : 'ok'}">${esc(c.text)}</span> <span class="muted">/ 문서 ${d.total}개 · ${commits}</span>
      <div class="muted">${esc(lastTxt)}${why ? ` — ${esc(why)}` : ''}</div>${failed}</div>${btn}</div>`;
  }

  // 포트폴리오 쓰기 — 「10/10 썼다」에 마지막 쓴 시각 · 그 뒤 커밋 수를 붙이고 [갱신]. 코드는 바뀌는데 글이 옛 것일 수 있다
  function portfolioBlock(room, pj, tasks) {
    const tps = pj.topics || [];
    if (!tps.length || !tasks.portfolio) return '';
    const pf = pj.portfolio || {};
    let state;
    if (pf.unread) state = `<span class="bad">${esc(pf.unread)}</span>`;
    else if (!pf.written) state = '<span class="muted">아직 쓴 글이 없습니다</span>';
    else state = `<span class="muted">마지막 ${pf.last_at ? ago(pf.last_at) : ''} · 그 뒤 커밋 </span><span class="${pf.since > 20 ? 'warn' : 'muted'}">${pf.since}개</span>`;
    // [갱신] — 쓴 글 중 그 뒤 커밋이 가장 많은(가장 옛) 글을 고쳐 쓰게 한다. 어느 글인지는 아래 목록에서 따로 고를 수도 있다
    const cand = tps.filter((t) => t.written && !t.blocked && t.since !== null && t.since !== undefined).sort((a, b) => b.since - a.since)[0];
    const upd = cand
      ? `<button type="button" class="small" data-sc-task="portfolio" data-topic="${esc(cand.slug)}" data-name="${esc(cand.title)}"${busy ? ' disabled' : ''} title="갱신 — 가장 옛 글 「${esc(cand.title)}」(그 뒤 커밋 ${cand.since}개)을 서기에게 고쳐 쓰게 합니다. 다른 글은 아래 목록에서 고릅니다.">갱신</button>`
      : `<button type="button" class="small" disabled title="갱신 — 지금 고쳐 쓰게 할 글이 없습니다(쓴 글이 없거나 모두 열려 있습니다).">갱신</button>`;
    const rows = tps.map((t) => `<div class="sc-row"><div class="small"><b>${esc(t.title)}</b> ${t.written ? `<span class="ok">씀</span>${t.last_at ? ` <span class="muted">· ${ago(t.last_at)} · 뒤 커밋 ${t.since === null || t.since === undefined ? UNREAD : `${t.since}개`}</span>` : ''}` : '<span class="muted">안 씀</span>'} <span class="muted">— ${esc(t.blocked || t.about)}</span></div>
        <button type="button" class="small" data-sc-task="portfolio" data-topic="${esc(t.slug)}" data-name="${esc(t.title)}"${busy || t.blocked ? ' disabled' : ''} title="${esc(t.blocked ? `포트폴리오 쓰기 — 지금은 시킬 수 없습니다. ${t.blocked}` : `포트폴리오 쓰기 — 「${t.title}」을 서기에게 맡깁니다. ${t.written ? '이미 쓴 글을 고쳐 씁니다.' : '새로 씁니다.'}`)}">${t.written ? '고쳐 쓰기' : '쓰기'}</button></div>`).join('');
    return `<div class="sc-row"><div class="small" title="포트폴리오 쓰기 — 주제를 골라 서기가 portfolio/에 씁니다. 바깥 독자용이라 저장소 링크 없이 게시됩니다."><b>포트폴리오 쓰기</b> <span class="muted">${tps.filter((t) => t.written).length}/${tps.length} 씀 ·</span> ${state}</div>${upd}</div>
      <details class="hand"${keep(`scribe:${room}:topics`)}><summary class="small muted" title="글 목록 — 주제마다 쓴 시각과 그 뒤 커밋 수를 봅니다.">글 목록 ${tps.length}</summary>${rows}</details>`;
  }

  // pick — 서기 머리 위 "정리할까요?"(11-09)를 눌러 열면 그 일(later)을 고른 채: 그 줄을 밝히고 [시키기]를 primary로.
  // 고르기만 한다 — 세션은 사람이 [시키기]를 눌러야 뜬다(자동은 제안까지만)
  function html(room, label, pick = null) {
    load();
    const tasks = (todo && todo.tasks) || {};
    const pj = (todo && todo.projects && todo.projects[room]) || {};
    const items = pj.items || [], opened = pj.open || [], blocked = pj.blocked || {}, behind = pj.behind || {};
    // 동시에 시키기(11-06) — 같은 일 · 같은 파일 · 둘 넘게는 막는다. 막힌 버튼은 끄고 까닭을 호버로(서버도 같은 판단)
    const go = (k, label = '시키기', pri = false) => {
      const why = blocked[k];
      return `<button type="button" class="small${pri && !why ? ' primary' : ''}" data-sc-task="${esc(k)}"${busy || why ? ' disabled' : ''} title="${esc(why ? `${(tasks[k] || {}).title || k} — 지금은 시킬 수 없습니다. ${why}` : `${(tasks[k] || {}).title || k} — 서기 세션을 작업방으로 띄워 맡깁니다. 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.`)}">${label}</button>`;
    };
    // 사람 수정으로 멈춘 파일 — 눈에 띄게 맨 위(조용히 멈춰 있지 않게)
    const alerts = items.filter((x) => x.kind === 'publish' && x.act === 'force').map((x) => `<div class="sc-row"><div class="small bad"><b>${esc(x.title)}</b> <span class="muted">— ${esc(x.why)}</span></div>
        <button type="button" class="small danger" data-pub="publish" data-force="1" data-proj="${esc(x.project)}" data-path="${esc(x.path)}" title="Notion 수정 버리고 덮기 — Notion에서 사람이 고친 곳을 버리고 git 원본으로 덮습니다. 살릴 수정이면 먼저 git에 옮겨 주세요.">Notion 수정 버리고 덮기</button></div>`).join('');
    // 한 목록 — 「문서 할 일」(센 것)과 「시킬 일」(메뉴)이 같은 줄이다. 밀린 수는 이름 옆에
    let nBehind = 0;
    const rows = ORDER.filter((k) => tasks[k]).map((k) => {
      const bt = behindText(k, behind[k]);
      if (bt.text && (bt.cls === 'warn' || bt.cls === 'bad')) nBehind += 1;
      const sub = blocked[k] ? blocked[k] : tasks[k].desc;
      let extra = '';
      if (k === 'doccheck' && pj.report) {          // 문서 점검 결과로 바로 고치기 — 찾기만 하고 끝나지 않게
        const r = pj.report;
        extra = r.fixed
          ? `<div class="sc-row"><div class="small muted">· 점검 결과 <code>${esc(r.name)}</code> — 고쳐서 합쳤습니다</div></div>`
          : `<div class="sc-row"><div class="small">· 점검 결과 <code>${esc(r.name)}</code> <span class="muted">— 합쳐진 결과의 어긋남을 고칩니다</span></div>
            <button type="button" class="small" data-sc-task="docfix" data-topic="${esc(r.name)}" data-name="${esc(r.name)}"${busy || blocked.docfix ? ' disabled' : ''} title="${esc(blocked.docfix ? `문서 고치기 — 지금은 시킬 수 없습니다. ${blocked.docfix}` : `문서 고치기 — ${r.name}에 적힌 어긋남을 서기가 문서에서 고칩니다. 코드는 건드리지 않고, 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.`)}">바로 고치기</button></div>`;
      }
      return `<div class="sc-row${k === pick ? ' sc-pick' : ''}"><div class="small"><b>${esc(tasks[k].title)}</b>${bt.text ? ` <span class="${bt.cls}"${bt.tip ? ` title="${esc(bt.tip)}"` : ''}>— ${esc(bt.text)}</span>` : ''} <span class="muted">${esc(sub)}</span></div>
        ${go(k, '시키기', k === pick)}</div>${extra}`;
    }).join('');
    // 받은 할 일 — 할 일이 아니라 상태다. 단추 없이 숫자만(정리는 「나중에 할 일 정리」 줄이 한다)
    const inboxRow = pj.inbox ? `<div class="small sc-line" title="받은 할 일 — 머리줄 [＋ 할 일]로 받은 글입니다. 「나중에 할 일 정리」가 README 표로 옮깁니다."><b>받은 할 일 ${pj.inbox.n}개</b> <span class="muted">${pj.inbox.oldest_days >= 1 ? `— 가장 오래된 것 ${pj.inbox.oldest_days}일째` : '— 오늘 받음'}</span></div>` : '';
    const openHtml = opened.length ? `<div class="small"><b>열려 있는 일 ${opened.length}</b> <span class="muted">— 합치거나 버리기 전까지(동시에 2개까지, 같은 파일을 고치는 일은 하나씩)</span>${
      opened.map((o) => `<div class="sc-row"><div class="small">· ${esc((tasks[o.task] || {}).title || o.task)}${o.topic ? ` — ${esc(o.topic)}` : ''} <span class="muted">세션 ${o.session_id}</span></div>
        <button type="button" class="small" data-sc-open="${o.session_id}" title="세션 열기 — 이 서기 세션의 [세션 정리] 탭을 엽니다. 「따로 작업」에서 diff를 보고 합치거나 버립니다(끝난 세션은 화면에서 사라져도 여기서 엽니다).">세션 열기</button></div>`).join('')}</div>` : '';
    const nudge = pj.nudge;
    const pickHead = pick && tasks[pick] ? `<div class="small warn">정리할까요? — 받은 할 일이 쌓였습니다(${esc(nudge ? nudge.why : '')}). 「${esc(tasks[pick].title)}」을 골라 두었습니다. [시키기]를 눌러야 서기 세션이 뜹니다.</div>` : '';
    const nAlert = items.filter((x) => x.kind === 'publish' && x.act === 'force').length;
    const bad = todoBad ? ` <span class="bad">· 지금 값을 ${UNREAD}(지난 값입니다)</span>` : '';
    const sumCount = !todo ? '' : (nBehind + nAlert ? `<span class="warn">밀린 것 ${nBehind + nAlert}</span>` : '<span class="muted">밀린 것 없음</span>');
    const listBody = !todo ? (todoBad ? `<p class="small bad">할 일을 ${UNREAD}.</p>` : '<p class="small muted">할 일을 읽는 중입니다.</p>') : pickHead + alerts + rows + inboxRow + openHtml;
    // 물어보기(11-10) — 세션 없이 읽기 전용으로 한 번 묻는다. 답만 하고 파일은 고치지 않는다(고치는 일은 아래 [문서 고치기])
    const fixBtn = answer && !answer.bad && answer.text
      ? `<div class="hand-btns"><button type="button" class="small" data-sc-fix="ask"${busy || blocked.docfix ? ' disabled' : ''} title="${esc(blocked.docfix ? `문서 고치기 — 지금은 시킬 수 없습니다. ${blocked.docfix}` : '문서 고치기 — 위 답을 고칠 목록으로 서기에게 맡깁니다. 서기가 저장소와 다시 맞는지 확인한 뒤 문서만 고치고, 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다.')}">이 답대로 문서 고치기</button></div>` : '';
    const askHtml = `<details class="hand" open><summary title="물어보기 — 서기 세션을 띄우지 않고 문서 · 기록에 대해 한 번 묻습니다. 읽기만 하고 파일은 고치지 않습니다."><b>물어보기</b></summary>
      <textarea id="scAskText" rows="3" maxlength="2000" placeholder="문서나 기록에 대해 물어봅니다 (Ctrl+Enter로 보냅니다)"${asking ? ' disabled' : ''}>${esc(askText)}</textarea>
      <div class="hand-btns"><button type="button" class="small primary" data-sc-ask="1"${asking ? ' disabled' : ''} title="물어보기 — 답만 받습니다. 답에서 찾은 어긋남은 아래 [이 답대로 문서 고치기]로 시킵니다.">${asking ? '묻는 중…' : '물어보기'}</button></div>
      ${asking ? '<div class="small muted">서기가 문서를 읽고 있습니다… 보통 20초쯤 걸립니다.</div>' : ''}
      ${answer ? `<div class="small ${answer.bad ? 'bad' : ''} sc-answer" style="white-space:pre-wrap">${esc(answer.text)}</div>` : ''}${fixBtn}</details>`;
    return `<div class="small muted">${esc(label)} · 서기 — 문서 담당. 시킨 일은 작업방 세션으로 돌고, 끝나면 사람이 diff를 보고 합칩니다.</div>
      ${askHtml}
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}"${note.tip ? ` title="${esc(note.tip)}"` : ''}>${esc(note.msg)}</div>` : ''}
      <details class="hand"${pick ? ' open' : keep(`scribe:${room}:list`, true)}><summary title="할 일 — 서기에게 시킬 일 한 목록입니다. 이름 옆 숫자는 밀린 정도이고, 숫자가 없으면 지금 밀린 것이 없습니다."><b>할 일</b> ${sumCount}${bad}</summary>${listBody}</details>
      <div class="hand">${portfolioBlock(room, pj, tasks)}${portPubBlock(room, pj)}${docsPubBlock(room, pj)}</div>
      ${pubBad && pub ? `<div class="small bad">게시 목록을 ${UNREAD}(지난 값입니다).</div>` : ''}`;
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

  // 서기 일 시키기 — 확인 창 → /api/scribe/start. 문서 고치기는 점검 결과(topic) 또는 물어보기 답(note)을 같이 보낸다
  async function start(room, label, k, topic, nameExtra, noteText) {
    const title = ((todo && todo.tasks) || {})[k]?.title || k;
    const name = title + (nameExtra ? ` — ${nameExtra}` : '');
    if (!confirm(`${label}의 서기에게 「${name}」을 맡깁니다. 서기 세션이 작업방으로 뜨고(Opus), 끝나면 [끝내기 ▾]의 [합치고 끝내기]로 검토해 합칩니다. 진행할까요?`)) return;
    busy = true; note = { msg: `「${name}」 — 서기 세션을 띄우는 중입니다…` }; store.touch('panel');
    const body = { project: room, task: k, topic: topic || null };
    if (noteText) body.note = noteText;
    try {
      const r = await fetch('/api/scribe/start', { method: 'POST', headers: store.headers(true), body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      note = r.ok ? { msg: `「${name}」 — 서기 세션을 띄웠습니다. 서기실에서 일합니다.`, tip: `서기 세션 — tmux 창 ${j.tmux || '?'}` } : { bad: true, msg: `띄우지 못했습니다 — ${j.refused || j.detail || r.status}` };
    } catch { note = { bad: true, msg: '띄우지 못했습니다 — 서버에 닿지 못했습니다.' }; }
    busy = false;
    await load(true);
  }

  async function onClick(ev, room, label, openSession) {
    // 열린 서기 일의 세션 열기(11-06) — 끝난 서기 세션은 3분 뒤 화면에서 사라지고, 서기실의 「서기」를 누르면 이 창이 떠서
    // 합치지 않은 worktree의 [합치기]에 닿을 길이 없었다
    const o = ev.target.closest('[data-sc-open]');
    if (o) { ev.preventDefault(); if (openSession) openSession(Number(o.dataset.scOpen)); return; }
    if (ev.target.closest('[data-sc-ask]')) { ev.preventDefault(); await ask(room); return; }
    if (ev.target.closest('[data-sc-fix]')) {        // 물어보기 답으로 바로 고치기
      ev.preventDefault();
      if (answer && !answer.bad && answer.text) await start(room, label, 'docfix', null, '물어보기 답', answer.text);
      return;
    }
    const t = ev.target.closest('[data-sc-task]'), p = ev.target.closest('[data-pub]');
    if (!t && !p) return;
    ev.preventDefault();
    if (t) {
      const k = t.dataset.scTask, topic = t.dataset.topic || null;
      await start(room, label, k, topic, topic ? (t.dataset.name || topic) : '', null);
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
