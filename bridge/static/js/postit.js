// 포스트잇(11-15 사용자, 서기 구조 다시 짜기 2번) — 머리 탭 종이와 서기실이 같은 목록을 본다(/api/postit).
// 11-15 늦게: 머리 탭 [＋ 할 일] 단추와 그 창(todoinbox.js)을 뺐다 — 이 창이 적기와 프로젝트 고르기를 다 한다(사용자).
// 들어오는 것: 포스트잇에 바로 적음 · 대화에서 사람이 미룬 것(관리자가 올림 · 브리지 그물은 「확인 전」으로 흐리게) ·
// 옮기기 「문서에 넣을 것 고르기」의 미완. 줄마다 [x] 삭제 · [→] 알려진 한계, 전체 [저장] · [갱신](조사 세션이 코드를 보고 판정).
// 판정은 제안이다 — 「끝난 것 같음」은 사람이 줄마다 닫는다. 코더에게 맡길 만한 것은 [띄우기]로 계획 창을 바로 연다.
// 조용한 고장 금지: 못 읽으면 0이 아니라 「읽지 못했습니다」, [갱신]이 결과 없이 끝나면 그렇게 보인다.
// 11-17 문서 정리 E(사용자): 받은 편지함 겸 TODO 보는 창. 프로젝트마다 세 묶음
//   아직 안 보낸 것  사람이 적은 줄(적는 칸은 이 묶음 위). 줄마다 [TODO로] [한계로]
//   할 일            그 저장소 docs/TODO.md 번호와 한 줄 제목만(내용은 복사하지 않는다). 줄마다 [한계로]
//   30일 넘은 것     올린 날이 30일 넘은 TODO 항목
// [한계로]는 편을 고르고 안 하는 까닭을 적는 칸을 연다. 까닭이 비면 [보내기]가 꺼지고 눌러도 보내지 않는다(서버도 거부한다).
// 커밋 메시지의 `(todo:번호)`가 끝냈다고 한 TODO 항목은 「커밋이 끝냈다고 합니다」로 알리고, 지우기는 사람이 [지우기]로 한다.

import { esc, ago, keep } from './render.js';

const UNREAD = '읽지 못했습니다';
const MAX = 8000;
export const REASON_MAX = 1000;
export const NO_REASON = '안 하는 까닭을 적어야 보낼 수 있습니다. 까닭을 쓸 수 없으면 한계가 아니라 할 일이라 [TODO로] 보냅니다.';

// [한계로] 칸을 보낼 수 있나. 막히면 까닭 글, 보낼 수 있으면 ''
export function limitBlocked(lim) {
  if (!lim) return '보낼 것을 고르지 않았습니다.';
  if (!lim.piece) return '편을 골라야 보낼 수 있습니다.';
  const r = String(lim.reason || '').trim();
  if (!r) return NO_REASON;
  if (r.length > REASON_MAX) return `까닭이 너무 깁니다(${r.length}자). ${REASON_MAX}자까지 받습니다.`;
  return '';
}

export const mmdd = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : `${d.getMonth() + 1}/${d.getDate()}`;
};
// 「11/15 16:30」 — 보는 사람의 시각으로
export const mmddhm = (iso) => {
  const d = new Date(iso);
  const p2 = (n) => String(n).padStart(2, '0');
  return Number.isNaN(d.getTime()) ? '' : `${mmdd(iso)} ${p2(d.getHours())}:${p2(d.getMinutes())}`;
};
// 첫 줄만, 길면 자른다(구분선 줄은 건너뛴다)
export const firstLine = (s, n = 70) => {
  const t = String(s || '').split('\n').map((x) => x.trim()).find((x) => x && !/^[━─=\-]{3,}$/.test(x)) || '';
  return t.length > n ? t.slice(0, n - 1) + '…' : t;
};

// 머리 탭 종이 — 지금 보는 방(없으면 모든 방 합)의 할 일 수. 쌓임 기준을 넘으면 warn이고 까닭은 호버에
// (11-15 「가장 오래된 날」을 뺐다 — 무엇을 하라는 것인지 알 수 없고 줄마다 날짜가 붙어 있다. 주황의 까닭이 사라지지 않게 호버에 적는다)
export function badgeOf(projects, room) {
  if (!projects) return { text: '포스트잇 ?', cls: 'warn', tip: `포스트잇 — 개수를 ${UNREAD}. 누르면 펼쳐 다시 읽습니다.` };
  const one = !!(room && projects[room]);
  const names = one ? [room] : Object.keys(projects);
  const xs = names.map((n) => [n, projects[n] || {}]);
  const open = xs.reduce((a, [, p]) => a + (p.open || 0), 0);
  const piled = xs.filter(([, p]) => p.nudge);
  const done = xs.reduce((a, [, p]) => a + (p.likely_done || 0), 0);
  const per = xs.filter(([, p]) => p.open).map(([n, p]) => `${n} ${p.open}`).join(', ');
  const why = piled.map(([n, p]) => (p.nudge.why ? `${one ? '' : `${n} `}${p.nudge.why}` : '')).filter(Boolean).join(' / ');
  // 11-17 TODO 묶음: 할 일 수, 30일 넘은 것, 커밋이 끝냈다고 한 것(이것이 있으면 주황, 지우기는 창의 [지우기])
  const td = xs.map(([, p]) => p.todo || {});
  const tn = td.reduce((a, t) => a + (t.n || 0), 0), told = td.reduce((a, t) => a + (t.old || 0), 0);
  const tdone = td.reduce((a, t) => a + (t.done || 0), 0);
  const todoTip = tn + told ? ` 할 일 ${tn}${told ? `, 30일 넘은 것 ${told}` : ''}.` : '';
  return {
    text: `포스트잇 ${open}장`,
    cls: piled.length || tdone ? 'warn' : '',
    tip: `포스트잇 — 아직 안 보낸 것 ${open}장${done ? `, 끝난 것 같음 ${done}` : ''}.${todoTip}`
      + `${tdone ? ` 커밋이 끝냈다고 한 할 일 ${tdone}개는 창에서 [지우기]로 지웁니다.` : ''}`
      + `${piled.length ? ` 쌓였습니다${why ? `(${why})` : ''}.` : ''}${one ? '' : per ? ` 방마다: ${per}.` : ''} 누르면 펼칩니다.`,
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
  return `<div class="pi-row pi-check" data-tip="${esc(`끝난 것 같음 — 조사 세션 ${k.session_id}이 코드를 보고 끝났다고 봤습니다. 맞으면 [닫기], 아니면 [남기기]를 누릅니다.`)}">
    <div class="pi-main small"><b>${esc(firstLine(text, 80))}</b>${ev}${k.reason ? `<div class="muted">${esc(k.reason)}</div>` : ''}</div>
    <div class="pi-btns"><button type="button" class="small" data-pi-check="${k.id}" data-act="close" title="닫기 — 끝난 것으로 닫습니다. 근거는 닫은 줄에 남습니다.">닫기</button>
    <button type="button" class="small ghost" data-pi-check="${k.id}" data-act="keep" title="남기기 — 아직 남은 일로 둡니다. 다음 [갱신]에서 다시 봅니다.">남기기</button></div></div>`;
}

function rowHtml(x, busy, project = '') {
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
    <details class="pi-main"${keep(`postit:${project}:p${x.id}`)}><summary class="small">${esc(firstLine(x.body))} <span class="muted">(${esc(x.source_label)}, ${esc(mmdd(x.created_at))}${ref})</span> ${chip}</summary><pre class="hand-body">${esc(x.body)}</pre></details>
    ${x.repo_refused ? `<div class="small bad pi-refused" title="저장소에 못 넣은 까닭 — 마지막으로 [TODO로]를 눌렀을 때 저장소가 거부한 까닭입니다. 정리한 뒤 다시 누릅니다.">${esc(x.repo_refused)}</div>` : ''}
    <div class="pi-btns">${x.recommend ? `<button type="button" class="small primary" data-pi-launch="${x.id}"${dis} title="띄우기 — 이 포스트잇으로 계획 창을 열고 바로 계획을 받습니다. [이대로 시작]을 누르면 코더 세션이 이 일을 가져갑니다.">띄우기</button>` : ''}
    <button type="button" class="small" data-pi-todo="${x.id}"${dis} title="TODO로 — 아직 할 일입니다. 저장소 docs/TODO.md에 다음 번호로 더하고 그 파일만 커밋합니다. push는 하지 않습니다.">TODO로</button>
    <button type="button" class="small" data-pi-limit="${x.id}" data-kind="postit"${dis} title="한계로 — 안 하기로 한 것입니다. 편을 고르고 안 하는 까닭을 적으면 서기가 그 편 「알려진 한계」에 씁니다.">한계로</button>
    <button type="button" class="small ghost" data-pi-close="${x.id}" data-reason="drop"${dis} title="삭제 — 안 하기로 했고 어디에도 남기지 않을 것입니다. 목록에서 사라집니다.">x</button></div></div>`;
}

// [한계로] 칸: 편 고르기와 안 하는 까닭(비면 [보내기]가 꺼진다)
function limitForm(lim, pieces) {
  const list = pieces || [];
  const why = limitBlocked(lim);
  const opts = list.length
    ? list.map((p) => `<option value="${esc(p.path)}"${p.path === lim.piece ? ' selected' : ''}>${esc(`${p.set}: ${p.title}`)}</option>`).join('')
    : '';
  const pick = pieces == null ? '<span class="small muted">편 목록을 읽는 중입니다.</span>'
    : list.length ? `<select class="pi-lim-piece" aria-label="편" title="편 — 이 한계를 적을 기술문서나 포트폴리오 편을 고릅니다."><option value="">편을 고릅니다</option>${opts}</select>`
      : '<span class="small bad">이 저장소에는 기술문서나 포트폴리오 편이 없습니다.</span>';
  return `<div class="pi-lim" data-pi-lim="1">${pick}
    <textarea class="pi-lim-reason" rows="2" maxlength="${REASON_MAX}" placeholder="안 하는 까닭을 적습니다">${esc(lim.reason || '')}</textarea>
    <div class="pi-foot"><span class="small ${why ? 'bad' : 'muted'} pi-lim-why">${esc(why || '보내면 서기 할 일 「알려진 한계 쓰기」에 셉니다.')}</span>
      <button type="button" class="small primary" data-pi-lim-send="1"${why ? ' disabled' : ''} title="보내기 — 고른 편과 까닭으로 알려진 한계에 보냅니다.">보내기</button>
      <button type="button" class="small ghost" data-pi-lim-x="1" title="그만두기 — 보내지 않고 칸을 닫습니다.">그만두기</button></div></div>`;
}

// TODO 항목 한 줄. 번호와 한 줄 제목만(내용은 docs/TODO.md에만 있다)
function todoRowHtml(t, busy) {
  const dis = busy ? ' disabled' : '';
  const day = t.date ? ` <span class="muted">(${esc(t.date.slice(5).replace('-', '/'))}${t.old ? `, ${t.days}일째` : ''})</span>` : '';
  const doneChip = t.done_by
    ? ` <span class="pi-chip pi-rec" title="${esc(`커밋이 끝냈다고 합니다 — 커밋 ${t.done_by.commit} 「${t.done_by.subject}」 메시지에 (todo:${t.id})가 있습니다. 맞으면 [지우기]를 누릅니다.`)}">커밋 ${esc(t.done_by.commit)}이 끝냄</span>` : '';
  const sent = t.limit_sent ? ' <span class="pi-chip" title="알려진 한계로 보냄 — 서기가 그 편에 쓰면 이 항목이 TODO에서 빠집니다.">한계로 보냄</span>' : '';
  return `<div class="pi-row pi-todo" data-pi-trow="${esc(t.id)}"><div class="pi-main small"><b class="pi-tid">${esc(t.id)}</b> ${esc(firstLine(t.title, 90))}${day}${doneChip}${sent}</div>
    <div class="pi-btns">${t.done_by ? `<button type="button" class="small primary" data-pi-tdel="${esc(t.id)}"${dis} title="지우기 — 커밋이 끝냈다고 한 이 항목을 docs/TODO.md에서 지우고 그 파일만 커밋합니다.">지우기</button>` : ''}
    ${t.limit_sent ? '' : `<button type="button" class="small" data-pi-limit="${esc(t.id)}" data-kind="todo"${dis} title="한계로 — 안 하기로 한 것입니다. 편을 고르고 까닭을 적으면 서기가 그 편에 쓰고 이 항목을 TODO에서 지웁니다.">한계로</button>`}</div></div>`;
}

function withForm(rowHtmlStr, kind, id, lim, pieces) {
  return lim && lim.kind === kind && String(lim.id) === String(id) ? rowHtmlStr + limitForm(lim, pieces) : rowHtmlStr;
}

// 할 일 · 30일 넘은 것 묶음 — 파일이 없거나 번호 꼴이 아니면 그렇다고 보인다
export function todoGroups(todo, { busy = false, lim = null, pieces = null } = {}) {
  if (!todo) return { now: `<p class="small bad">docs/TODO.md를 ${UNREAD}.</p>`, old: '', n: '?', nOld: '?' };
  const items = todo.items || [];
  const now = items.filter((t) => !t.old), old = items.filter((t) => t.old);
  const rows = (xs) => xs.map((t) => withForm(todoRowHtml(t, busy), 'todo', t.id, lim, pieces)).join('');
  const msg = todo.error ? `<p class="small muted">${esc(todo.error)}.</p>` : '';
  return {
    now: msg + (now.length ? rows(now) : todo.error ? '' : '<p class="small muted">할 일이 없습니다.</p>'),
    old: old.length ? rows(old) : '<p class="small muted">30일 넘은 할 일이 없습니다.</p>',
    n: now.length, nOld: old.length,
  };
}

function checkState(s) {
  const c = s && s.check;
  // 도는 중 · 실패는 그대로 보인다(조용히 사라지지 않게). 그 밖에는 마지막으로 결과를 받은 [갱신]의 때(요약 last_check_at)
  if (c && c.state === 'running') return `<span class="warn">조사 세션 ${c.session_id}이 코드를 보는 중입니다(${ago(c.at)} 시작).</span>`;
  if (c && c.state === 'failed') return `<span class="bad">지난 [갱신]이 결과 없이 끝났습니다(조사 세션 ${c.session_id}). 다시 [갱신]을 누릅니다.</span>`;
  const at = (s && s.last_check_at) || (c && c.at) || null;
  return `<span class="muted">마지막 갱신: ${at ? esc(mmddhm(at) || String(at)) : '없음'}</span>`;
}

// 머리 탭 창과 서기실이 같이 쓰는 목록(순수 — view = GET /api/postit 응답)
export function listHtml(view, { busy = false, draft = '', note = null, label = '', bad = false, noHead = false, lim = null, pieces = null } = {}) {
  if (!view) return `<div class="postit paper"><p class="small ${bad ? 'bad' : 'muted'}">${bad ? `포스트잇을 ${UNREAD}.` : '포스트잇을 읽는 중입니다.'}</p></div>`;
  const s = view.summary || {};
  const items = view.items || [];
  const unconf = items.filter((x) => !x.confirmed);
  const done = items.filter((x) => x.check && x.check.verdict === 'done');
  const rlim = (view.readme_checks || []).filter((k) => k.verdict === 'done');
  // view.todo가 없으면(옛 브리지) 읽지 못한 것으로 보인다(0으로 보이지 않게)
  const tg = todoGroups(view.todo, { busy, lim, pieces });
  // noHead: 서기실은 프로젝트 이름이 이미 위에 있어 머리줄을 안 그린다(읽지 못한 경고만 남김)
  const head = noHead ? (bad ? `<div class="pi-head small bad">지금 값을 ${UNREAD}. 지난 값입니다.</div>` : '') : `<div class="pi-head small"><b>${esc(label || view.project)}</b>${bad ? ` <span class="bad">(지금 값을 ${UNREAD}. 지난 값입니다)</span>` : ''}</div>`;
  const doneHtml = done.length + rlim.length ? `<div class="pi-sec"><div class="small"><b>끝난 것 같음 ${done.length + rlim.length}</b> <span class="muted">근거가 코드 자리인 것만입니다. 사람이 줄마다 닫습니다.</span></div>
    ${done.map((x) => checkHtml(x.check, x.body)).join('')}${rlim.map((k) => checkHtml(k, `README 「알려진 한계」 ${k.item}: ${k.item_text || ''}`)).join('')}</div>` : '';
  const rows = items.length ? items.map((x) => withForm(rowHtml(x, busy, view.project), 'postit', x.id, lim, pieces)).join('') : '<p class="small muted">아직 안 보낸 것이 없습니다.</p>';
  const closed = view.closed || [];
  const closedHtml = closed.length ? `<details class="pi-closed"${keep(`postit:${view.project}:closed`)}><summary class="small muted" title="끝낸 것 — 최근에 끝내거나 보내거나 지운 포스트잇을 다시 봅니다.">끝낸 것 ${closed.length}</summary>${
    closed.map((x) => `<div class="small muted pi-crow">${esc(x.label)}: ${esc(firstLine(x.body, 60))}${x.closed_note ? ` <span title="${esc(x.closed_note)}">(근거)</span>` : ''}</div>`).join('')}</details>` : '';
  // 저장소에 넣으려고 누른 기록(성공과 거부). 사람이 그 저장소에 가 보지 않아도 알 수 있게
  const rl = view.repo_log || [];
  const logHtml = rl.length ? `<details class="pi-closed"${keep(`postit:${view.project}:repolog`)}><summary class="small muted" title="저장소에 넣은 기록 — [TODO로]와 [지우기]를 눌러 저장소에 커밋한 일과 거부된 일입니다. push는 하지 않았습니다.">저장소에 넣은 기록 ${rl.length}</summary>${
    rl.map((r) => `<div class="small pi-crow ${r.ok ? 'muted' : 'bad'}">${esc(mmddhm(r.created_at) || '')} ${r.ok ? '' : '못 함: '}${esc(r.note)}</div>`).join('')}</details>` : '';
  const saveTip = unconf.length
    ? `저장 — 적은 글을 포스트잇에 올리고, 확인 전 ${unconf.length}줄도 받아들입니다. 아닌 줄은 먼저 [x]로 지웁니다.`
    : '저장 — 적은 글을 포스트잇에 바로 올립니다. DB에만 적고 저장소는 건드리지 않습니다. Ctrl+Enter로도 저장합니다.';
  const running = s.check && s.check.state === 'running';
  // 세 묶음은 접는 칸이다. 처음값 펼침, 사람이 접으면 다시 그려도 새로고침 뒤에도 접힌 채(render.js keep, 열쇠는 프로젝트마다)
  const P = view.project;
  const grp = (name, title, n, tip) => `<details class="pi-group" data-pi-group="${name}"${keep(`postit:${P}:g:${name}`, true)}>`
    + `<summary class="pi-gh small" title="${esc(tip)}"><b>${title} <span class="pi-n">${n}</span></b></summary>`;
  return `<div class="postit paper" data-pi-project="${esc(P)}">${head}${doneHtml}
    ${grp('unsent', '아직 안 보낸 것', items.length, '아직 안 보낸 것 — 사람이 적은 줄입니다. 할 일이면 [TODO로], 안 할 것이면 [한계로] 보냅니다.')}
    <textarea class="pi-draft" rows="2" maxlength="${MAX}" placeholder="할 일을 메모합니다"${busy ? ' disabled' : ''}>${esc(draft)}</textarea>
    <div class="pi-foot"><span class="small">${checkState(s)}</span>
      <button type="button" class="small primary" data-pi-save="1"${busy ? ' disabled' : ''} title="${esc(saveTip)}">저장${unconf.length ? ` (확인 전 ${unconf.length})` : ''}</button>
      <button type="button" class="small" data-pi-refresh="1"${busy || running ? ' disabled' : ''} title="${esc(running ? '갱신 — 조사 세션이 이미 보는 중입니다.' : '갱신 — 조사 세션을 띄워 코드를 보고 이미 끝난 것을 찾습니다. 포스트잇과 README 「알려진 한계」를 함께 봅니다. 지우는 것은 사람이 합니다.')}">갱신</button></div>
    ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}">${esc(note.msg)}</div>` : ''}
    <div class="pi-list">${rows}</div></details>
    ${grp('todo', '할 일', tg.n, '할 일 — 저장소 docs/TODO.md의 항목입니다. 번호와 제목만 보이고 내용은 그 파일에 있습니다.')}
    <div class="pi-list">${tg.now}</div></details>
    ${grp('old', '30일 넘은 것', tg.nOld, '30일 넘은 것 — 올린 날이 30일 넘은 할 일입니다. 아직 할지 다시 봅니다.')}
    <div class="pi-list">${tg.old}</div></details>
    ${logHtml}${closedHtml}</div>`;
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
  const ui = ctx.ui || {};
  const c = t.closest('[data-pi-close]'), sv = t.closest('[data-pi-save]'), rf = t.closest('[data-pi-refresh]');
  const ck = t.closest('[data-pi-check]'), ln = t.closest('[data-pi-launch]');
  const td = t.closest('[data-pi-todo]'), lm = t.closest('[data-pi-limit]'), lx = t.closest('[data-pi-lim-x]');
  const ls = t.closest('[data-pi-lim-send]'), tdel = t.closest('[data-pi-tdel]');
  if (!c && !sv && !rf && !ck && !ln && !td && !lm && !lx && !ls && !tdel) return false;
  ev.preventDefault();
  try {
    if (c) {
      await api(`/api/postit/${c.dataset.piClose}/close`, { reason: c.dataset.reason });
      return ctx.done({ msg: `#${c.dataset.piClose}을 지웠습니다.` });
    }
    if (td) {
      const j = await api(`/api/postit/${td.dataset.piTodo}/todo`, {});
      return ctx.done({ msg: `#${td.dataset.piTodo}을 ${ctx.project} 저장소 docs/TODO.md에 ${j.id}로 더하고 커밋했습니다(${j.commit}). push는 하지 않았습니다.` });
    }
    if (lm) {
      // 칸을 연다. 편 목록은 프로젝트마다 한 번 읽는다
      ui.lim = { kind: lm.dataset.kind, id: lm.dataset.piLimit, piece: '', reason: '' };
      if (ctx.redraw) ctx.redraw();
      ui.pieces = ui.pieces || {};
      if (!ui.pieces[ctx.project]) {
        const r = await fetch(`/api/postit/pieces?project=${encodeURIComponent(ctx.project)}`, { headers: ctx.store.headers() });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.refused || j.detail || `HTTP ${r.status}`);
        ui.pieces[ctx.project] = j.pieces || [];
      }
      if (ctx.redraw) ctx.redraw();
      return true;
    }
    if (lx) {
      ui.lim = null;
      if (ctx.redraw) ctx.redraw();
      return true;
    }
    if (ls) {
      const lim = ui.lim;
      const why = limitBlocked(lim);
      if (why) return ctx.done({ bad: true, msg: why });                // 까닭이 비면 보내지 않는다(칸은 그대로 열려 있다)
      const body = { project: ctx.project, piece: lim.piece, reason: lim.reason.trim() };
      if (lim.kind === 'todo') body.todo = lim.id; else body.postit = Number(lim.id);
      await api('/api/postit/limit', body);
      ui.lim = null;
      return ctx.done({ msg: `${lim.kind === 'todo' ? lim.id : `#${lim.id}`}을 알려진 한계로 보냈습니다. 그 편에 쓰는 것은 서기 「알려진 한계 쓰기」입니다.` });
    }
    if (tdel) {
      const id = tdel.dataset.piTdel;
      if (typeof confirm === 'function' && !confirm(`${id}를 docs/TODO.md에서 지우고 그 파일만 커밋합니다. push는 하지 않습니다.\n\n지울까요?`)) return true;
      const j = await api('/api/postit/todo/remove', { project: ctx.project, id });
      return ctx.done({ msg: `${id}를 ${ctx.project} 저장소 docs/TODO.md에서 지우고 커밋했습니다(${j.commit}). push는 하지 않았습니다.` });
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
      if (typeof confirm === 'function' && !confirm(`${ctx.project}의 포스트잇과 README 「알려진 한계」를 조사 세션이 코드를 보고 판정합니다. 원본 폴더에 조사 세션이 뜨고(역할 조사, 고치지 않음), 끝나면 「끝난 것 같음」이 여기 뜹니다.\n\n띄울까요?`)) return true;
      const j = await api('/api/postit/refresh', { project: ctx.project });
      return ctx.done({ msg: `[갱신]: 조사 세션 ${j.session_id || '?'}을 띄웠습니다(포스트잇 ${j.items} · README 줄 ${j.limits}).${j.note ? ` ${j.note}` : ''}` });
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

// [한계로] 칸의 입력. 다시 그리지 않고(적던 자리를 잃지 않게) 값과 [보내기] 켜짐만 바꾼다. 다룬 입력이면 true
export function onLimitInput(ev, ui) {
  const t = ev.target;
  if (!t || !t.classList || !ui || !ui.lim) return false;
  if (t.classList.contains('pi-lim-reason')) ui.lim.reason = t.value;
  else if (t.classList.contains('pi-lim-piece')) ui.lim.piece = t.value;
  else return false;
  const box = t.closest && t.closest('[data-pi-lim]');
  if (box) {
    const why = limitBlocked(ui.lim);
    const b = box.querySelector('[data-pi-lim-send]');
    if (b) b.disabled = !!why;
    const w = box.querySelector('.pi-lim-why');
    if (w) { w.textContent = why || '보내면 서기 할 일 「알려진 한계 쓰기」에 셉니다.'; w.classList.toggle('bad', !!why); w.classList.toggle('muted', !why); }
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
  const views = new Map(), drafts = new Map(), notes = new Map(), bad = new Map(), at = new Map(), uis = new Map();
  let busy = false;
  const uiOf = (room) => { if (!uis.has(room)) uis.set(room, { lim: null, pieces: {} }); return uis.get(room); };
  async function load(room, force = false) {
    if (!force && Date.now() - (at.get(room) || 0) < 20000) return;
    at.set(room, Date.now());
    try { views.set(room, await fetchView(store, room)); bad.set(room, false); } catch { bad.set(room, true); }
    store.touch('panel');
  }
  function html(room, label, { noHead = false } = {}) {
    load(room);
    const ui = uiOf(room);
    return listHtml(views.get(room) || null, { busy, draft: drafts.get(room) || '', note: notes.get(room) || null, label, bad: !!bad.get(room), noHead,
      lim: ui.lim, pieces: ui.pieces[room] || null });
  }
  function onInput(ev, room) {
    if (onLimitInput(ev, uiOf(room))) return;
    if (ev.target && ev.target.classList && ev.target.classList.contains('pi-draft')) drafts.set(room, ev.target.value);
  }
  async function onClick(ev, room) {
    return act(ev, {
      store, project: room, view: views.get(room), draft: () => drafts.get(room) || '', setDraft: (v) => drafts.set(room, v),
      ui: uiOf(room), redraw: () => store.touch('panel'),
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
  const ui = { lim: null, pieces: {} };       // [한계로] 칸(열린 줄 하나)과 프로젝트마다 편 목록
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
    // 창 전체가 종이 한 장이다(panel.css .pi-pop — 종이 · 접힌 모서리 · 그림자는 창의 ::before · ::after). 글은 .pi-sheet 안에서만 구른다
    const keep = pop.querySelector('.pi-sheet');
    const top = keep ? keep.scrollTop : 0;
    pop.innerHTML = `<div class="pi-sheet"><div class="pi-bar"><select class="pi-proj" aria-label="프로젝트" title="프로젝트 — 어느 프로젝트의 포스트잇을 보고 적을지 고릅니다.">${names.map((n) => `<option value="${esc(n)}"${n === project ? ' selected' : ''}>${esc(lab(n))}</option>`).join('')}</select>
      <button type="button" class="small ghost" data-pi-x="1" title="닫기 — 포스트잇을 접습니다. 적던 글은 남습니다.">닫기</button></div>${listHtml(view, { draft, note, label: lab(project), bad: badRead, lim: ui.lim, pieces: ui.pieces[project] || null })}</div>`;
    if (top) pop.querySelector('.pi-sheet').scrollTop = top;
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
  pop.addEventListener('input', (ev) => { if (onLimitInput(ev, ui)) return; if (ev.target.classList.contains('pi-draft')) draft = ev.target.value; });
  pop.addEventListener('change', (ev) => { if (ev.target.classList.contains('pi-proj')) { project = ev.target.value; view = null; note = null; ui.lim = null; draw(); reload(); } });
  pop.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') { ev.stopPropagation(); close(); return; }
    if (ev.target.classList.contains('pi-draft') && ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault(); const b = pop.querySelector('[data-pi-save]'); if (b) b.click();
    }
  });
  pop.addEventListener('click', async (ev) => {
    if (ev.target.closest('[data-pi-x]')) { close(); return; }
    await act(ev, {
      store, project, view, draft: () => draft, setDraft: (v) => { draft = v; }, close, ui, redraw: draw,
      done: async (n) => { note = n; await reload(); await loadSummary(); if (onChanged) onChanged(); return true; },
    });
  });
  loadSummary();
  setInterval(loadSummary, 60000);
  setInterval(drawBadge, 2000);       // 방을 옮기면 그 방 숫자로(값은 1분마다 다시 받는다)
  return { open, close, reload: async () => { await loadSummary(); if (pop.classList.contains('on')) await reload(); } };
}
