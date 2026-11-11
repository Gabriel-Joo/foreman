// 인계 · 세션 조작(11-05, docs/11_handoff.md) — 패널 [세션] 탭의 칸들. 11-06 정리: 자주 쓰는 것만 보이고 나머지는 접는다.
//   인계(늘 보임)  요약하고 끝내기 · 지금 요약 · 새로 띄우기, 요약 카드(머리에 [고치기]) · 요약 이력 · 읽을 곳
//   세션(늘 보임)  세션 끝내기, [더보기]를 눌러야 작업 중단 · 일시정지 · 다시 시작 / 따로 작업(worktree일 때)
//   문서 정리(접힘, 할 일이 있으면 열림)  압축 손실 [잃은 것 찾기] · 문서에 남기기 [남길 것 찾기]
// 자기 데이터(/api/sessions/{id}/handoff)를 따로 받아 따로 그린다 — 세션 칸이 다시 그려져도 고치던 글이 날아가지 않게.

import { esc, ago, keep } from './render.js';
import { promoteGroup, edits as promoteEdits } from './promote.js';
import { lossGroup } from './losscheck.js';
import { moveStep, MOVE_STEPS, MOVE_TIP, chooseCount, writeLabel } from './moveflow.js';

const SOURCE = { self: '세션이 씀', self_headless: '끝난 세션을 잠깐 불러 씀', compact: '자동 압축 요약에서', edited: '사람이 고침' };
const STATUS = { requested: '기다리는 중…', ok: '저장됨', failed: '실패', timeout: '시간 초과' };
// 11-09 화면 말 통일 — "인계"는 "새 세션으로 옮기기"(문서 · log · 세션에 넣는 글은 그대로 "인계")
const KIND = { snapshot: '지금 요약', handoff: '옮기기용 요약' };
export const FLOW_TIP = '새 세션으로 옮기기 — 지금까지를 요약해 보여 드리고, 확인하면 같은 폴더에 새 세션을 띄워 요약을 넣은 뒤 이 세션을 끝냅니다. 어느 단계에서나 멈출 수 있습니다.';

// 넘기고 새로 시작(11-08 사용자 — 흩어진 [요약하고 끝내기] · [지금 요약] · [새로 띄우기] · 압축 요약을 버튼 하나로).
// ① 요약 → ② 확인(넣을 글을 보여 줌) → ③ 새 세션 → ④ 옛 세션 끝내기. 어디까지 왔는지는 이 브라우저에 세션마다 기억한다
// (다른 세션을 봤다 와도, 새로 고쳐도 이어진다). [멈추기]는 어느 단계에서나 — 요약은 남는다.
export const FLOW_STEPS = ['요약', '확인', '새 세션', '옛 세션 끝내기'];
// 쉬게 한 지 며칠째(11-09) — 화면 시계 기준 하루 단위
export const restDays = (iso, now = Date.now()) => Math.max(0, Math.floor((now - Date.parse(iso)) / 86400000)) || 0;
const FLOW_KEY = 'foremanFlow:';
const flowGet = (id) => { try { return JSON.parse(localStorage.getItem(FLOW_KEY + id) || 'null'); } catch { return null; } };
const flowPut = (id, v) => { try { if (v) localStorage.setItem(FLOW_KEY + id, JSON.stringify(v)); else localStorage.removeItem(FLOW_KEY + id); } catch { /* 이 탭에서만 */ } };

// 흐름의 지금 단계 — 저장한 것(flow)과 서버 데이터(요약 상태 · 넣음 · 세션이 살아 있나)로 정한다. 순수 함수(시험)
export function flowStep(flow, summary, live) {
  if (!flow || flow.v === 2) return null;      // 한 흐름(11-11)은 moveflow.js moveStep이 정한다
  if (flow.phase === 'done') return { i: 4, done: true };
  if (flow.phase === 'spawning') return { i: 2, busy: true };
  if (flow.phase === 'ending') return { i: 3, busy: true };
  if (flow.err) return { i: flow.errAt ?? 0, bad: true, msg: flow.err };
  if (!summary || summary.status === 'requested') return { i: 0, busy: true };
  if (summary.status !== 'ok') return { i: 0, bad: true, msg: summary.error || '요약을 받지 못했습니다' };
  if (summary.injected_at) return live ? { i: 3 } : { i: 4, done: true };   // 넣었는데 옛 세션이 살아 있다 — 끝내기만 남음
  return { i: 1 };
}

// 합치기 승인 카드(11-11 1물결 A, bridge/mergeprep.py) — 세션이 일을 마치면 브리지가 merge-tree로 만든다. 사람은 승인만 한다.
// mp = /api/sessions/{id}/handoff의 merge_prep({card, health, stage}), b = 단추 만들기(act, label, on, cls, tip), sid = 세션 번호
const MP_STATUS = { ready: '승인 기다림', merging: '합치는 중…', merged: '합쳤습니다', conflict_sent: '충돌 — 세션에 풀라고 보냈습니다',
  conflict_manager: '충돌 — 관리자에게 넘겼습니다', failed: '멈췄습니다' };
export function mpSection(mp, b, sid) {
  if (!mp) return '';
  const h = mp.health && !mp.health.ok ? `<div class="small bad">⚠ ${esc(mp.health.error || '합치기 준비가 멈췄습니다')}</div>` : '';
  const c = mp.card;
  if (!c) return h ? `<section class="hand mp-card"><div class="hand-h"><b>합치기 승인</b></div>${h}</section>` : '';
  const conf = c.conflict && c.conflict.length;
  const how = conf ? `<span class="bad" title="충돌 — 합치면 ${esc(c.base)}와 같은 줄을 서로 고친 곳이 있습니다. 승인하면 합치지 않고 그 세션(끝났으면 관리자)에게 풀라고 보냅니다.">충돌 ${c.conflict.length}개</span>`
    : c.ff ? '<span class="ok" title="ff 가능 — main이 그대로라 그대로 앞으로 옮깁니다(fast-forward).">충돌 없음 · ff 가능</span>'
      : `<span class="ok" title="main이 앞섬 — 이 브랜치를 만든 뒤 ${esc(c.base)}에 커밋 ${c.behind}개가 들어왔습니다. 합칠 때 그 위로 다시 얹습니다(rebase).">충돌 없음 · ${esc(c.base)}에 새 커밋 ${c.behind}개(rebase)</span>`;
  const d = c.docs || {};
  // 11-11 2물결 「넷」 — 근거(세션 기록 「README에서 뺄 줄」 · 근거 칸 기록 · 받은 할 일 번호)가 있는 것을 앞에, 낱말만 겹친 것(weak)은 접어 둔다
  const rLine = (x) => `<div class="small${x.weak ? ' muted' : ''}">README:${x.line} — ${esc(x.text)} <span class="muted">(${esc((x.why && x.why.length ? x.why : [...(x.files || []), ...(x.words || [])]).slice(0, 5).join(' · '))})</span></div>`;
  const strong = (d.readme || []).filter((x) => !x.weak), weak = (d.readme || []).filter((x) => x.weak);
  const rRows = strong.map(rLine).join('') + (weak.length ? `<details><summary class="small muted" title="낱말만 겹친 후보 — 커밋 글 낱말이 표 줄과 겹치기만 한 것입니다. 헛걸림이 많아 접어 둡니다.">낱말만 겹친 후보 ${weak.length}개</summary>${weak.map(rLine).join('')}</details>` : '');
  const dRows = (d.docs || []).map((x) => `<div class="small"><code>${esc(x.where)}</code> — ${x.count}줄(${x.lines.join(', ')}${x.count > x.lines.length ? ' …' : ''}) <span class="muted">${esc(x.files.join(', '))}</span>${x.stale ? ' <span class="warn" title="맞출 문서 — 이번에 바뀐 파일을 적고 있는데 이 문서는 고치지 않았습니다. 설계가 바뀌었으면 함께 맞춥니다.">이번에 안 고침</span>' : ''}</div>`).join('');
  const docs = d.error ? `<div class="small warn">${esc(d.error)}</div>`
    : rRows || dRows ? `<details${keep(`hand:${sid}:mp-docs`)}><summary class="small" title="정리 후보 — 바뀐 파일 · 커밋 글과 README 「나중에 할 일」 줄 · docs 줄을 기계로 맞댄 것입니다. 고르고 지우는 것은 사람 승인 뒤 관리자가 합니다.">정리 후보 — README ${(d.readme || []).length} · docs ${(d.docs || []).length}</summary>${rRows}${dRows}</details>` : '';
  const open = c.status === 'ready' || c.status === 'failed' || c.status.startsWith('conflict');
  const tip = conf ? '합치기 — 충돌이 있어 합치지 않습니다. 세션이 살아 있으면 그 세션에 main을 가져와 풀라고 보내고, 끝났으면 관리자에게 넘깁니다.'
    : c.live ? '합치기 — 세션을 끝내고 main에 합칩니다(main이 앞섰으면 rebase). push는 하지 않습니다. 시험 · push는 관리자가 합니다.'
      : '합치기 — main에 합칩니다(main이 앞섰으면 rebase). push는 하지 않습니다. 시험 · push는 관리자가 합니다.';
  return `<section class="hand mp-card"><div class="hand-h"><b>합치기 승인</b> <span class="small ${c.status === 'merged' ? 'ok' : c.status === 'ready' ? '' : 'warn'}">· ${esc(MP_STATUS[c.status] || c.status)}</span></div>${h}
    <div class="small"><code>${esc(c.branch)}</code> · 커밋 <b>${c.ahead}</b>개 · ${how}</div>
    <div class="small muted">${esc(c.why)}${c.live ? ' — 승인하면 세션을 끝냅니다(충돌이면 끝내지 않습니다).' : ''}</div>
    ${c.asks && c.status === 'ready' ? `<div class="small warn mp-asks" title="묻는 말 — 일을 마친 보고 끝에 사람에게 묻는 말이 있습니다. 합치기 전에 답할지 정합니다.">❓ 세션이 묻는 말이 있습니다 — 패널에서 답하십시오: ${esc(c.asks.tail || '')}</div>` : ''}
    ${conf ? `<div class="small bad">충돌 파일: ${c.conflict.map(esc).join(', ')}</div>` : ''}
    <details${keep(`hand:${sid}:mp-commits`)}><summary class="small muted">커밋 ${c.commits.length} · 바뀐 파일 ${c.files.length}</summary><pre class="hand-body">${esc(c.commits.join('\n'))}\n\n${esc(c.files.join('\n'))}</pre></details>
    ${docs}
    ${c.note ? `<div class="small ${c.status === 'merged' ? 'ok' : 'muted'}">${esc(c.note)}${c.manager_told === false ? ' 관리자 세션에는 알리지 못했습니다(텔레그램으로 남김).' : c.manager_told ? ' 관리자 세션에 알렸습니다.' : ''}</div>` : ''}
    ${c.error ? `<div class="small bad">${esc(c.error)}</div>` : ''}
    ${c.status === 'merged' ? '<div class="small muted">합치기까지 했습니다 — 시험 · push · 브리지 다시 띄우기는 관리자가 합니다.</div>' : ''}
    ${open ? `<div class="hand-btns">${b('mp-merge', '합치기', !!c.head && c.status !== 'merging', 'primary', tip)}${b('mp-skip', '나중에', true, 'ghost', '나중에 — 이 카드를 치웁니다. 이 세션이 새로 커밋하면 다시 뜹니다.')}</div>` : ''}
  </section>`;
}

export function mountHandoff(el, store,{ open: open0 = false, onToggle } = {}) {
  let sid = null, data = null, mode = null, preview = null, note = null, open = open0;
  let flow = null, flowPrev = null, flowPrevAsk = false, handMore = false;    // 흐름 · ② 확인에 보여 줄 넣을 글 · 드문 버튼 펼침
  let noteOpen = false, noteDraft = '';          // ② 확인의 [덧붙여서 보내기](11-09) — 인계 글 끝에 붙일 한 줄
  let lastHtml = '';                             // 같은 글이면 다시 그리지 않는다(11-09 — 3초마다 다시 그려 글 상자 스크롤이 맨 위로 돌아갔다)
  // 접는 칸을 사람이 열고 닫은 것 — 다시 그려도 그대로(null이면 저절로: 문서 정리는 할 일이 있을 때만 연다)
  let docsOpen = null, moreOpen = false;
  // 고치던 값 — 15초마다 새로 그려도 날아가지 않게 따로 든다(요약 고치기 글 · 옮기기 목록 칸)
  let editDraft = null, promDraft = {}, promId = null, promIn = null;
  const promField = (t) => {
    const f = t.dataset && t.dataset.f, row = t.closest && t.closest('.prom-item');
    if (!f || !row) return false;
    const id = Number(row.dataset.pid);
    promDraft[id] = { ...(promDraft[id] || {}), [f]: t.value };
    return true;
  };
  el.addEventListener('change', (ev) => {
    const mv = ev.target.dataset && ev.target.dataset.mvItem;      // 한 흐름 ③ 고르기(11-11)
    if (mv) { promDraft[Number(mv)] = { ...(promDraft[Number(mv)] || {}), state: ev.target.checked ? 'approved' : 'dropped' }; draw(); return; }
    if (ev.target.id === 'promIn') promIn = ev.target.value;
    // 상태를 고르면 개수 · 버튼을 다시 센다. 글칸은 그리지 않는다(blur 때 다시 그리면 바로 누른 버튼의 click이 사라진다)
    else if (promField(ev.target) && ev.target.tagName === 'SELECT') draw();
  });
  el.addEventListener('input', (ev) => {
    if (ev.target.id === 'hEdit') editDraft = ev.target.value;
    else if (ev.target.id === 'hNote') noteDraft = ev.target.value;
    else promField(ev.target);
  });
  let timer = null;

  const api = async (method, url, body) => {
    const r = await fetch(url, { method, headers: store.headers(!!body), body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({}));
    if (r.status === 409) throw new Error(j.refused || '거부');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return j;
  };
  async function load() {
    if (sid == null) return;
    const want = sid;
    try {
      const j = await api('GET', `/api/sessions/${want}/handoff`);
      if (want !== sid) return;
      data = j;
    } catch (e) { note = { bad: true, msg: `불러오지 못했습니다 — ${e.message}` }; }
    // 글을 고치는 중이면 다시 그리지 않는다(커서 · 글자 위치를 지킨다). 데이터는 받아 두고 다음 번에 그린다
    const a = document.activeElement;
    if (a && el.contains(a) && (a.tagName === 'TEXTAREA' || a.tagName === 'INPUT') && a.type !== 'checkbox') { schedule(); return; }
    draw();
    schedule();
    if (flow && flow.v === 2) moveTick();        // 한 흐름 — 서버 상태가 다음 단계를 가리키면 저절로(11-11)
  }
  function schedule() {
    clearTimeout(timer);
    if (sid == null) return;
    const p0 = data && data.promotions && data.promotions[0];
    const mv = flow && flow.v === 2 ? moveStep(flow, data) : null;      // 한 흐름은 사람 차례(고르기) · 끝 · 오류가 아니면 빨리 본다
    const pending = data && ((mv && !mv.wait && !mv.done && !mv.bad) || data.controls.pending_req || (data.summaries[0] && data.summaries[0].status === 'requested') || (flow && !flow.v && !flow.phase)
      || (p0 && (p0.status === 'requested' || p0.status === 'writing')));
    timer = setTimeout(load, pending ? 3000 : 15000);
  }
  async function run(label, fn) {
    note = { msg: `${label}…` }; draw();
    try { const r = await fn(); note = r && r.msg ? r : { ok: true, msg: `${label} — 마쳤습니다.` }; }
    catch (e) { note = { bad: true, msg: `${label} — ${e.message}` }; }
    await load();
  }

  const latest = () => (data ? data.summaries.find((x) => x.status === 'ok') : null);
  // 마지막 옮기기 — 다른 목록으로 바뀌면 고치던 값은 버린다(id가 다른 항목에 얹히지 않게)
  const prom = () => {
    const p = data && data.promotions && data.promotions[0];
    if ((p ? p.id : null) !== promId) { promId = p ? p.id : null; promDraft = {}; }
    return p || null;
  };

  // 서기 브랜치 검토(12b, 11-06) — 근거 표시 확인(LLM 없음) · 근거 없는 줄(의심) · 고친 양. 틀린 근거가 있으면 합치기 전에 빨갛게
  function reviewBlock(rv) {
    if (!rv) return '';
    if (rv.error) return `<div class="small warn">${esc(rv.error)}</div>`;
    const r = rv.revision || {};
    const head = `<span class="${rv.bad ? 'bad' : 'ok'}">근거 표시 ${rv.marks}개 — ${rv.bad ? `틀림 ${rv.bad}` : '모두 맞음'}</span>`
      + `${rv.unsupported ? ` · <span class="warn">근거 없는 줄 ${rv.unsupported}</span>` : ''}`
      + ` · 고친 양: 초안 ${r.draft_lines || 0}줄${r.revision_lines ? ` → 고침 ${r.revision_lines}줄` : ''}`;
    const rows = (rv.files || []).map((f) => [
      ...f.bad.map((b) => `<div class="small bad">✗ ${esc(f.path)}:${b.line} <code>${esc(b.mark)}</code> — ${esc(b.why)}</div>`),
      ...f.unsupported.slice(0, 8).map((u) => `<div class="small muted">? ${esc(f.path)}:${u.line} ${esc(u.text)}</div>`),
    ].join('')).join('');
    return `<div class="small" title="근거 확인 — 서기 글의 [c:커밋] · [log:파일] · [docs:파일] · [t:턴]이 실제로 있는지 기계로 봅니다. 근거 없는 줄은 숫자 · 인용이 있는데 근거 표시가 없는 줄입니다(의심).">${head}</div>
      ${rows ? `<details${keep(`hand:${sid}:review`, !!rv.bad)}><summary class="small muted">자세히</summary>${rows}</details>` : ''}`;
  }

  // 따로 작업(worktree, 11-05) — 이 세션만의 폴더 · 브랜치. 끝낸 뒤 [합치기](rebase → fast-forward) · [버리기]
  function wtGroup(w, b) {
    if (!w) return '';
    if (w.error) return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div class="small bad">${esc(w.error)}</div></div>`;
    if (!w.exists) return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div class="small muted">${esc(w.branch)} — 합쳤거나 버려서 지금은 없습니다.</div></div>`;
    // 11-11(받은 할 일 #17) — 같은 이름을 뒤 세션이 다시 씀: 지금 폴더는 그 세션 것이라 여기서는 합치기 · 버리기를 보이지 않는다
    if (w.reused_by) return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div class="small muted" title="이름 다시 씀 — worktree 이름은 다시 쓰입니다. 이 세션의 worktree는 이미 합쳤거나 버렸습니다.">${esc(w.branch)} — 이 세션의 일은 끝났습니다. 지금 이 이름은 세션 ${w.reused_by}이 씁니다.</div></div>`;
    const why = w.live ? '세션을 끝내면서 합치거나 버립니다 — 위 「세션」의 [끝내고 합치기] · [끝내고 버리기].'
      : w.dirty.length ? `커밋 안 된 변경 ${w.dirty.length}개 — 그 세션에서 커밋하거나 버려야 합칠 수 있습니다.` : '';
    return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div>
      <div class="small"><code>${esc(w.branch)}</code> · ${esc(w.base)}보다 커밋 <b>${w.ahead}</b>개 앞${w.behind ? ` · <span title="${esc(w.base)}가 ${w.behind}개 앞서감(합칠 때 rebase) — 이 브랜치를 만든 뒤 ${esc(w.base)}에 들어온 커밋입니다. 합칠 때 그 위로 다시 얹습니다.">${esc(w.base)}에 새 변경 ${w.behind}개</span>` : ''}${w.dirty.length ? ` · <span class="warn">커밋 안 됨 ${w.dirty.length}</span>` : ''}${w.schema_lock ? ' · <span class="warn" title="스키마 잠금 보유 — 이 세션이 DB 구조(migrations)를 바꾸는 중이라 다른 세션은 바꿀 수 없습니다.">DB 구조 바꾸는 중</span>' : ''}</div>
      ${w.commits.length ? `<details${keep(`hand:${sid}:wt-commits`)}><summary class="small muted">커밋 · 바뀐 파일</summary><pre class="hand-body">${esc(w.commits.join('\n'))}\n\n${esc(w.diffstat.join('\n'))}</pre></details>` : ''}
      ${why ? `<div class="small muted">${esc(why)}</div>` : ''}
      ${w.stale ? `<div class="small ok" title="이미 원본에 들어 있음 — 밖에서 git merge로 합쳤거나 합칠 커밋이 없습니다. [합치기]는 worktree와 브랜치만 지웁니다.">${esc(w.stale)}</div>` : ''}
      ${w.rested_at ? `<div class="small warn wt-rest" title="쉬는 중 — [쉬게 하기]로 지금까지를 커밋하고 세션만 끝냈습니다. 같은 일을 이어 하려면 [이어서], 끝났으면 [합치기]입니다.">쉬는 중 — 합치기 기다림 · ${esc(ago(w.rested_at))}부터${restDays(w.rested_at) >= 1 ? ` · ${restDays(w.rested_at)}일째` : ''}</div>` : ''}
      ${reviewBlock(w.review)}
      ${w.preview ? `<div class="small ok">미리보기가 :${w.preview.port}에서 돌고 있습니다.</div>` : ''}
      <div class="hand-btns">
        ${w.preview_ok ? b('wt-preview', '미리보기 열기', true, '', '미리보기 열기 — 이 브랜치의 화면 파일로 새 탭을 엽니다. 데이터와 버튼은 실제 브리지입니다. 없으면 빈 포트로 띄웁니다.') : ''}
        ${w.preview ? b('wt-preview-off', '미리보기 닫기', true, 'ghost', '미리보기 닫기 — 미리보기 서버를 끕니다.') : ''}
        ${w.resume_ok ? b('rest-resume', '이어서', true, '', '이어서 — 같은 worktree에서 이 CC 세션을 다시 붙입니다(--resume). 같은 일의 맥락을 그대로 잇습니다. 새 일이면 새 세션으로 띄웁니다.') : ''}
        ${w.live ? '' : `${b('wt-merge', '합치기', !w.dirty.length, 'primary', `합치기 — ${w.branch}를 ${w.base} 위로 rebase한 뒤 fast-forward로 합치고 worktree를 지웁니다. 충돌이 나면 되돌리고 멈춥니다. push는 하지 않습니다.`)}
        ${b('wt-discard', '버리기', true, 'danger', '버리기 — worktree와 브랜치를 지웁니다. 합치지 않은 커밋도 사라집니다.')}`}
      </div></div></div>`;
  }

  // 합치기 승인 카드 — 모듈 밖 mpSection(시험이 부른다)에 이 세션 번호를 넘긴다
  const mpSectionOf = (mp, b) => mpSection(mp, b, sid);

  // 인계 2판(11-05) — 「읽을 곳」 기계 확인 결과. 틀린 곳이 있으면 넣지 않는다(서버도 막는다)
  function pointerList(p) {
    const rows = (p.pointers || []).map((x) => {
      const where = x.path ? `${x.path}${x.start ? `:${x.start}${x.end && x.end !== x.start ? '-' + x.end : ''}` : ''}${x.section ? ` 「${x.section}」` : ''}` : x.raw;
      const mark = !x.ok ? `<span class="bad">✗ ${esc(x.problem)}</span>`
        : x.stale ? `<span class="warn">⚠ 이 문서 뒤로 커밋 ${x.commits_since}개 — 오래됐을 수 있습니다</span>` : '<span class="ok">✓</span>';
      return `<div class="small"><code>${esc(where)}</code> ${mark}${x.why ? ` <span class="muted">— ${esc(x.why)}</span>` : ''}</div>`;
    }).join('');
    return `<div class="hand-ptrs"><div class="small"><b>읽을 곳 ${(p.pointers || []).length}</b> — 새 세션이 먼저 읽습니다</div>${rows}
      ${p.blocked ? `<div class="small bad">${esc(p.blocked)}</div>` : ''}</div>`;
  }
  // 11-09 — 이 프로젝트에 살아 있는 세션이 있으면 새 세션은 따로 작업(worktree)에서 뜬다. 넣을 때 브리지가 그 사실을 글 앞에 붙인다
  // 11-11 아홉 — 관리자는 늘 원본 폴더에서 뜬다. 원본에 관리자가 이미 살아 있으면 띄우기가 거절된다(manager_block)
  const wtNext = (p) => (p && p.role === 'manager' ? (p.manager_block
    ? `<div class="small bad" title="띄울 수 없습니다 — 관리자는 원본 폴더에 하나입니다.">✗ ${esc(p.manager_block)}</div>`
    : '<div class="small ok" title="원본 폴더 — 관리자는 따로 작업(worktree)이 아니라 저장소 맨 위 폴더에서 뜹니다.">관리자라 원본 폴더에서 뜹니다.</div>')
    : p && p.worktree_next ? `<div class="small warn" title="따로 작업에서 뜹니다 — 이 프로젝트에 살아 있는 세션이 있어(옮기기는 이 세션을 빼고 셉니다) 새 세션은 .worktrees/ 아래 자기 브랜치에서 뜹니다. 받은 세션은 push · 브리지 재시작을 하지 않고, 끝낸 뒤 [합치기]로 합칩니다.">⑂ 새 세션은 따로 작업(worktree)에서 뜹니다 — 넣을 때 그 사실을 글 맨 앞에 덧붙입니다.</div>` : '');
  // 인계 검증(11-06) — 만들 때 상태와 지금이 다르면 넣는 글 앞에 붙는 "인계 뒤 바뀐 것"
  function driftList(d, head) {
    if (!d || !d.length) return `<div class="small ok">✓ ${esc(head)} — 요약을 쓴 뒤 바뀐 것이 없습니다(git · 스키마 잠금).</div>`;
    return `<div class="hand-drift"><div class="small warn"><b>⚠ ${esc(head)} ${d.length}</b> — 받은 세션이 「지금 상태」를 다시 판단하도록 글 앞에 붙습니다.</div>
      ${d.map((x) => `<div class="small">· ${esc(x)}</div>`).join('')}</div>`;
  }
  // 2판 인계를 받고 시작한 세션 — 읽을 곳을 실제로 Read했나
  function readsLine(r, can) {
    if (!r) return '';
    const all = r.read === r.total;
    const failed = r.failed || [], miss = r.missing || [];
    const drift = r.drift && r.drift.length ? `<div class="hand-group"><span class="hand-lbl small muted">요약 뒤 바뀐 것</span><div>${driftList(r.drift, '받을 때 요약 뒤 바뀐 것')}</div></div>` : '';
    // 11-09 확인에 실패한 곳(이 세션 폴더에 파일 · 절이 없다)은 읽음으로 세지 않고 따로 — 전에는 "6/6 읽음"에 ✗가 섞였다
    const failRows = failed.map((f) => `<div class="small bad">✗ <code>${esc(f.path)}</code> — ${esc(f.problem || '')}</div>`).join('');
    return `<div class="hand-group"><span class="hand-lbl small muted" title="읽을 곳 — 새 세션이 먼저 읽어야 할 문서 중 실제로 열고, 이 세션 폴더에서 찾던 곳이 맞는 것의 수입니다.">읽을 곳</span><div class="hand-btns">
      <span class="small ${all ? 'ok' : 'warn'}">${r.read}/${r.total} 읽음${miss.length ? ` — 안 읽음: ${miss.map(esc).join(', ')}` : ''}${failed.length ? ` · 확인 실패 ${failed.length}` : ''}${r.auto && r.auto.length ? ` <span class="muted" title="자동 — 세션이 시작할 때 저절로 들어오는 문서라 읽음으로 셉니다.">(자동: ${r.auto.map(esc).join(', ')})</span>` : ''}</span>
      ${failRows}
      ${!miss.length ? '' : `<button data-act="reads-resend" class="small primary"${can ? '' : ' disabled'} title="안 읽은 곳 다시 보내기 — 아직 읽지 않은 문서만 다시 보내고, 읽은 뒤 걸리는 규칙을 말하게 합니다.">안 읽은 곳 다시 보내기</button>`}
    </div></div>${drift}`;
  }

  // 11-11 한 흐름 — 옮기기 전 요약 확인 창을 없앤 대신, 받은 세션 패널에서 무엇이 넘어왔는지 본다(한 시간 안이면 펼침)
  function receivedLine(r) {
    if (!r) return '';
    if (r.error) return `<div class="small warn">${esc(r.error)}</div>`;
    const fresh = !!r.at && Date.now() - Date.parse(r.at) < 3600e3;
    return `<details class="hand-recv"${keep(`hand:${sid}:recv`, fresh)}><summary class="small" title="넘겨받은 글 — 이 세션이 옮기기로 받은 요약입니다. 무엇이 넘어왔는지 여기서 봅니다.">넘겨받은 글 — 세션 ${esc(String(r.from_session))}${r.from_title ? ` 「${esc(r.from_title)}」` : ''}에서 · ${ago(r.at)}</summary><pre class="hand-body">${esc(r.body)}</pre></details>`;
  }
  function moveBody(m, b, c) {
    const steps = `<ol class="flow-steps">${MOVE_STEPS.map((n, k) => `<li class="${k < m.i ? 'done' : k === m.i ? (m.bad ? 'bad' : 'now') : ''}">${k < m.i ? '✓' : k + 1} ${n}</li>`).join('')}</ol>`;
    const stop = b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 옮기기를 그만둡니다. 이미 쓴 문서와 받은 요약은 남습니다.');
    const skip = (label) => b('mv-skip-find', label, true, 'ghost', `${label} — 잊은 것 찾기를 기다리지 않고 세션에게 바로 문서 후보를 묻습니다.`);
    let body;
    if (m.done) body = `<div class="small ok">새 세션으로 옮겼습니다 — 넘어간 글은 새 세션 패널 「넘겨받은 글」에서 봅니다.</div><div class="row">${b('flow-close', '닫기', true, 'ghost', '닫기 — 이 안내를 치웁니다.')}</div>`;
    else if (m.bad) body = `<div class="small bad">${esc(m.msg)}</div><div class="row flow-act">${b('mv-retry', '다시 시도', true, 'primary', '다시 시도 — 이 단계부터 다시 합니다.')}${m.i <= 1 ? skip('문서 후보 없이 묻기') : ''}${m.i === 6 ? b('flow-end', '옛 세션 다시 끝내기', c.can.exit, 'danger', '옛 세션 다시 끝내기 — 새 세션은 이미 이어받았습니다. 옛 세션만 /exit로 끝냅니다.') : ''}${stop}</div>`;
    else if (m.wait) body = chooseHtml(m, b) + stop + '</div>';
    else if (m.i === 0) body = `<div class="small muted">${esc(m.msg)}… 끝나면 문서에 넣을 후보를 보여 드립니다.</div><div class="row">${skip('잊은 것 찾기 건너뛰기')}${stop}</div>`;
    else if (m.i === 6 && !m.busy) body = `<div class="small">새 세션이 이어받았습니다. 옛 세션 끝내기만 남았습니다.</div><div class="row flow-act">${b('flow-end', '옛 세션 끝내기', c.can.exit, 'primary danger', '옛 세션 끝내기 — 이 세션을 /exit로 끝냅니다.')}${stop}</div>`;
    else body = `<div class="small muted">${esc(m.msg || (m.i === 6 ? '옛 세션을 끝내는 중입니다… 맥락이 큰 세션은 수십 초 걸립니다' : m.i === 5 ? '새 세션을 띄우고 요약을 넣는 중입니다' : m.note || '다음 단계로 넘어가는 중입니다'))}…</div><div class="row">${stop}</div>`;
    return `<div class="flow">${steps}${flow && flow.note ? `<div class="small warn">${esc(flow.note)}</div>` : ''}${body}</div>`;
  }
  // ③ 고르기 — 사람이 하는 유일한 판단. 항목마다 「넣기」 하나, 단추 하나로 쓰기 → 옮기기까지
  function chooseHtml(m, b) {
    const items = m.p.items || [];
    const n = chooseCount(items, promDraft);
    const rows = items.map((it) => {
      const ck = it.check || {}, on = ((promDraft[it.id] || {}).state ?? it.state) === 'approved';
      const bad = ck.ok === false;
      return `<label class="mv-item small"${bad ? ' title="고를 수 없음 — 목적지가 틀렸습니다. 아래 「옮기기 전 정리」에서 목적지를 고치면 고를 수 있습니다."' : ''}><input type="checkbox" data-mv-item="${it.id}"${on && !bad ? ' checked' : ''}${bad ? ' disabled' : ''}>
        <span>${esc(it.what)}</span> <span class="muted">→ ${esc(it.dest)}${it.section ? ` 「${esc(it.section)}」` : ''}</span>${bad ? ` <span class="bad">✗ ${esc(ck.problem || '')}</span>` : ''}</label>`;
    }).join('');
    const tip = n ? `${writeLabel(n)} — 고른 것을 세션이 문서에 쓰고 커밋합니다. 브리지가 커밋을 확인하면 요약 · 새 세션 · 옛 세션 끝내기까지 이어서 합니다.`
      : '문서에 넣지 않고 옮기기 — 아무것도 쓰지 않고 요약 · 새 세션 · 옛 세션 끝내기로 갑니다.';
    return `${m.msg ? `<div class="small bad">${esc(m.msg)}</div>` : ''}
      <div class="small"><b>문서에 넣을 것을 고르십시오</b> — 사람이 고르는 곳은 여기 하나입니다. 고른 것만 세션이 문서에 쓰고 커밋한 뒤 이어서 옮깁니다.</div>
      <div class="mv-items">${rows}</div><div class="row flow-act">${b('mv-write', writeLabel(n), true, 'primary', tip)}`;
  }

  function draw() {
    if (sid == null || !data) { el.innerHTML = ''; lastHtml = ''; return; }
    const c = data.controls, can = c.can, s0 = data.summaries[0], ok = latest();
    const b = (act, label, on, cls = '', tip = '') => `<button data-act="${act}" class="small ${cls}"${tip ? ` title="${esc(tip)}"` : ''}${on ? '' : ' disabled'}>${label}</button>`;
    const sumCard = (x) => !x ? '<p class="small muted">아직 요약이 없습니다.</p>' : `
      <div class="hand-sum">
        <div class="small"><b>${esc(KIND[x.kind] || x.kind)}</b> · ${esc(SOURCE[x.source] || x.source)} ·
          <span class="${x.status === 'ok' ? 'ok' : x.status === 'requested' ? '' : 'bad'}">${esc(STATUS[x.status] || x.status)}</span>
          · ${ago(x.created_at)}${x.chars ? ` · ${x.chars.toLocaleString()}자` : ''}${x.injected_at ? ` · <span class="ok">새 세션 ${esc((x.injected_cc_session || '').slice(0, 8))}에 넣음</span>` : ''}</div>
        ${x.error ? `<div class="small bad">${esc(x.error)}</div>` : ''}
        ${x.body ? `<pre class="hand-body">${esc(x.body)}</pre>` : ''}
        ${!x.body && x.raw ? `<details${keep(`hand:sum:${x.id}:raw`)}><summary class="small muted">응답 원문</summary><pre class="hand-body">${esc(x.raw)}</pre></details>` : ''}
      </div>`;
    let main;
    if (mode === 'edit' && ok) {
      main = `<textarea id="hEdit" rows="14" class="hand-edit">${esc(editDraft ?? ok.body)}</textarea>
        <div class="row">${b('edit-save', '고친 본 저장', true, 'primary', '저장 — 원본은 두고 고친 본을 새 판으로 저장합니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 고친 것을 버리고 요약 카드로 돌아갑니다.')}</div>`;
    } else if (mode === 'spawn') {
      main = preview ? `<div class="small">같은 폴더에 새 세션을 띄우고 아래 글을 첫 입력으로 넣습니다.${preview.cut ? ` <span class="warn">길어서 일부 절을 줄였습니다(전체는 ${esc(preview.full_path)}).</span>` : ''}</div>
        ${wtNext(preview)}${driftList(preview.drift, '요약 뒤 바뀐 것')}
        ${preview.v2 ? pointerList(preview) : ''}
        <pre class="hand-body">${esc(preview.text)}</pre>
        <div class="row">${b('spawn-go', '이 글을 넣고 시작', !preview.blocked && !preview.manager_block, 'primary', preview.manager_block ? '띄울 수 없습니다 — 원본 폴더에 관리자가 이미 살아 있습니다.' : preview.blocked ? '넣을 수 없습니다 — 읽을 곳을 고친 뒤 넣습니다(요약 카드의 [고치기]).' : '이 글을 넣고 시작 — 같은 폴더에 새 세션을 띄우고 위 글을 첫 입력으로 넣습니다.')}${b('spawn-bare', '요약 없이 시작', !preview.manager_block, 'ghost', '요약 없이 시작 — 같은 폴더에 빈 새 세션만 띄웁니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 띄우지 않고 돌아갑니다.')}</div>`
        : `<div class="small">넣을 요약이 없습니다.</div><div class="row">${b('spawn-bare', '요약 없이 새로 띄우기', true, 'primary', '요약 없이 새로 띄우기 — 같은 폴더에 빈 새 세션만 띄웁니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 띄우지 않고 돌아갑니다.')}</div>`;
    } else {
      main = sumCard(s0 && s0.status !== 'ok' && ok && s0.id !== ok.id ? s0 : ok || s0) +
        (s0 && ok && s0.id !== ok.id && s0.status !== 'ok' ? `<div class="small muted">이전 저장본 ↓</div>${sumCard(ok)}` : '') +
        '';
    }
    // 넘기고 새로 시작 — 흐름이 있으면 요약 카드 자리에 단계 · 지금 할 일을 그린다
    const fs = flow && data.summaries.find((x) => x.id === flow.sumId);
    const st = flowStep(flow, fs, c.live);
    if (st && mode == null) {
      const steps = `<ol class="flow-steps">${FLOW_STEPS.map((n, k) => `<li class="${k < st.i ? 'done' : k === st.i ? (st.bad ? 'bad' : 'now') : ''}">${k < st.i ? '✓' : k + 1} ${n}</li>`).join('')}</ol>`;
      let body = '';
      if (st.done) body = `<div class="small ok">새 세션으로 옮겼습니다 — 새 세션${fs && fs.injected_cc_session ? ` ${esc(fs.injected_cc_session.slice(0, 8))}` : ''}이 이어받았습니다.</div><div class="row">${b('flow-close', '닫기', true, 'ghost', '닫기 — 이 안내를 치웁니다.')}</div>`;
      else if (st.bad) body = `<div class="small bad">${esc(st.msg)}</div><div class="row flow-act">${st.i === 3 ? b('flow-end', '옛 세션 다시 끝내기', can.exit, 'primary danger', '옛 세션 다시 끝내기 — 새 세션은 이미 이어받았습니다. 옛 세션만 /exit로 끝냅니다.') : st.i === 0 ? b('flow-start', '다시 요약', can.summary || can.headless, 'primary', '다시 요약 — 요약을 새로 요청합니다.') : b('flow-go', '다시 시도', true, 'primary', '다시 시도 — 이 단계부터 다시 합니다.')}${b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 넘기기를 그만둡니다. 받은 요약은 남습니다.')}</div>`;
      else if (st.i === 0) body = `<div class="small muted">세션이 옮길 요약을 쓰는 중입니다… 다 쓰면 넣을 글을 보여 드립니다.</div><div class="row">${b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 기다리지 않습니다. 세션은 쓰던 요약을 마저 쓰고, 요약은 남습니다.')}</div>`;
      else if (st.i === 1) {
        const p = flowPrev && flowPrev.summary_id === flow.sumId ? flowPrev : null;
        if (!p && !flowPrevAsk) { flowPrevAsk = true; setTimeout(() => flowPreview().finally(() => { flowPrevAsk = false; }), 0); }
        body = !p ? '<div class="small muted">넣을 글을 불러오는 중입니다…</div>'
          : `<div class="small">새 세션에 아래 글을 첫 입력으로 넣습니다. 보내면 새 세션을 띄우고 이 세션을 끝냅니다.${p.cut ? ` <span class="warn">길어서 일부 절을 줄였습니다.</span>` : ''}</div>
            ${wtNext(p)}${driftList(p.drift, '요약 뒤 바뀐 것')}${p.v2 ? pointerList(p) : ''}<pre class="hand-body">${esc(p.text)}</pre>`;
        // 11-09 사용자 — 보내기 전에 한 줄 덧붙일 수 있게. 요약은 그대로 두고 넣는 글 끝에만 붙는다(bridge/handoff.py note_block)
        if (p && noteOpen) body += `<div class="hand-note"><label class="small" for="hNote">덧붙일 말 — 위 글 맨 끝에 「사람이 덧붙인 말」로 붙습니다. 요약은 바뀌지 않습니다.</label>
            <textarea id="hNote" rows="2" maxlength="2000" class="hand-edit" placeholder="예: 다음 할 일 중 3번부터 해 주세요.">${esc(noteDraft)}</textarea></div>`;
        const go = !!p && !p.blocked && !p.manager_block && can.spawn;
        const goTip = p && p.manager_block ? '띄울 수 없습니다 — 원본 폴더에 관리자가 이미 살아 있습니다.'
          : p && p.blocked ? '넣을 수 없습니다 — 읽을 곳을 고친 뒤 넣습니다([더보기] → [요약 고치기]).' : '';
        body += `<div class="row flow-act">${noteOpen
          ? `${b('flow-go-note', '덧붙여서 보내기', go, 'primary', goTip || '덧붙여서 보내기 — 위 글 끝에 덧붙일 말을 붙여 새 세션에 넣고, 이 세션을 /exit로 끝냅니다.')}${b('flow-note-off', '덧붙이지 않기', true, 'ghost', '덧붙이지 않기 — 덧붙일 말 칸을 닫습니다. 적은 말은 버립니다.')}`
          : `${b('flow-go', '이대로 보내기', go, 'primary', goTip || '이대로 보내기 — 같은 폴더에 새 세션을 띄워 위 글을 넣고, 이 세션을 /exit로 끝냅니다.')}${b('flow-note', '덧붙여서 보내기', go, 'ghost', goTip || '덧붙여서 보내기 — 보내기 전에 한 줄 덧붙일 칸을 엽니다.')}`}${b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 띄우지 않습니다. 요약은 남습니다.')}</div>`;
      } else if (st.i === 2) body = '<div class="small muted">새 세션을 띄우고 요약을 넣는 중입니다…</div>';
      else if (st.i === 3) body = st.busy ? '<div class="small muted">옛 세션을 끝내는 중입니다… 맥락이 큰 세션은 수십 초 걸립니다.</div>'
        : `<div class="small">새 세션이 이어받았습니다. 옛 세션 끝내기만 남았습니다.</div><div class="row flow-act">${b('flow-end', '옛 세션 끝내기', can.exit, 'primary danger', '옛 세션 끝내기 — 이 세션을 /exit로 끝냅니다.')}${b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 이 세션을 살려 둡니다.')}</div>`;
      main = `<div class="flow">${steps}${body}</div>`;
    }
    // 11-11 한 흐름 — 고르기에서만 멈추고 나머지는 저절로(moveflow.js). 옛 흐름 칸 자리에 그린다
    const mst = moveStep(flow, data);
    if (mst && mode == null) main = moveBody(mst, b, c);
    const hist = data.summaries.length > 1 ? `<details class="hand-hist"${keep(`hand:${sid}:hist`)}><summary class="small muted" title="지난 요약 — 이 세션에서 받은 요약 목록입니다. 맨 위가 지금 쓰는 것입니다.">지난 요약 ${data.summaries.length}</summary>${
      data.summaries.map((x) => `<div class="small">#${x.id} ${esc(KIND[x.kind] || x.kind)} · ${esc(SOURCE[x.source] || x.source)} · ${esc(STATUS[x.status] || x.status)} · ${ago(x.created_at)}${x.chars ? ` · ${x.chars}자` : ''}</div>`).join('')}</details>` : '';
    // 문서 정리 — 평소엔 접고, 사람이 할 일(목록 승인 · 쓰기 확인)이나 도는 점검이 있으면 연다(사람이 닫으면 그대로)
    const p0 = prom(), lc0 = (data.losschecks || [])[0] || null;
    const docsBusy = (p0 && ['requested', 'listed', 'writing', 'write_failed'].includes(p0.status)) || (lc0 && lc0.status === 'running');
    const docsHint = p0 && p0.status === 'listed' ? '승인할 목록이 있습니다' : p0 && p0.status === 'write_failed' ? '확인 실패 — 봐 주세요'
      : docsBusy ? '도는 중…' : lc0 && lc0.status === 'done' && lc0.lost_total ? `잃은 것 ${lc0.lost_total}` : '';
    const docsOn = docsOpen ?? !!docsBusy;
    const wtLive = !!(c.worktree && c.worktree.exists && c.worktree.live);   // 살아 있는 따로 작업 — 끝내기를 세 갈래로
    // 요약 카드 머리의 작은 [고치기] — 자주 안 쓰므로 버튼 줄에서 뺐다(11-06, 이력 1번)
    const editLink = ok && mode == null && !st ? b('edit', '고치기', true, 'ghost', '요약 고치기 — 저장된 요약을 직접 고칩니다. 원본은 두고 새 판으로 저장합니다.') : '';
    const html = `${mpSectionOf(data.merge_prep, b)}
      <section class="hand">
        <div class="hand-h"><b>새 세션으로 옮기기</b>${s0 ? ` <span class="small muted" title="마지막 요약 — ${esc(KIND[s0.kind] || s0.kind)}, ${esc(STATUS[s0.status] || s0.status)}">· 요약 ${esc(STATUS[s0.status] || s0.status)} ${ago(s0.created_at)}</span>` : ''}</div>
        <div class="hand-btns">
          ${st || mst ? '' : b('flow-start', '새 세션으로 옮기기', can.summary || (!c.live && can.headless), 'primary', c.move_flow && c.live ? MOVE_TIP : FLOW_TIP)}
          ${b('hand-more', handMore ? '접기 ▴' : '더보기 ▾', true, 'ghost', handMore ? '접기 — 드문 버튼을 다시 숨깁니다.' : '더보기 — 지금 요약 · 요약만 넣어 띄우기 · 요약 고치기 · 끝난 세션 요약. 드물게 씁니다.')}
          ${handMore ? `${b('summary', '지금 요약(계속 돎)', can.summary, 'ghost', '지금 요약 — 세션이 지금까지 한 일을 정리합니다. 세션은 끝내지 않고 계속 돕니다.')}
          ${b('spawn', '새 세션만 띄우기', can.spawn, 'ghost', '새 세션만 띄우기 — 이 세션은 두고, 같은 폴더에 새 세션을 띄워 마지막 요약(또는 빈 채로)을 넣습니다.')}
          ${!c.live ? b('compact', '압축 요약으로 만들기', can.compact, 'ghost', '압축 요약으로 만들기 — 끝난 세션이 마지막 자동 압축 때 남긴 요약으로 옮기기용 요약을 만듭니다. 토큰을 쓰지 않지만 「읽을 곳」이 없는 거친 요약입니다.') : ''}` : ''}
        </div>
        ${!st && !(can.summary || (!c.live && can.headless)) && c.why ? `<div class="small muted">${esc(c.why === '작업 중입니다' ? '세션이 작업 중이라 지금은 못 합니다. 끝나면 눌러주세요.' : /입니다$/.test(c.why) ? c.why.replace(/입니다$/, '이라 지금은 못 합니다.') : c.why + '.')}</div>` : ''}
        ${note ? `<div class="small ${note.bad ? 'bad' : note.ok ? 'ok' : 'muted'}">${esc(note.msg)}</div>` : ''}
        ${editLink ? `<div class="hand-edit-link">${editLink}</div>` : ''}
        ${main}${hist}
        ${receivedLine(c.received)}
        ${readsLine(c.reads, can.exit)}
      </section>
      <section class="hand">
        <div class="hand-h"><b>세션</b></div>
        <div class="hand-btns">
          ${wtLive ? `${b('rest', '쉬게 하기', can.rest, '', '쉬게 하기 — 지금까지를 이 브랜치에 커밋하고 세션만 끝냅니다. worktree는 남고 코더는 자리로 돌아가 「합치기 기다림」으로 보입니다. 나중에 [이어서] · [합치기] · [버리기]를 고릅니다.')}
          ${b('wt-end-merge', '끝내고 합치기', can.exit, '', `끝내고 합치기 — 커밋 안 된 변경이 없으면 세션을 끝내고 ${c.worktree.branch}를 ${c.worktree.base}에 합칩니다. 있으면 끝내지 않고 알립니다.`)}
          ${b('wt-end-discard', '끝내고 버리기', can.exit, 'danger', '끝내고 버리기 — 세션을 끝내고 worktree와 브랜치를 지웁니다. 합치지 않은 커밋도 사라집니다.')}
          ${b('exit', '그냥 끝내기(나중에 정함)', can.exit, 'ghost', '그냥 끝내기 — 세션만 끝냅니다. worktree는 남고, 이 세션의 [세션] 탭 「따로 작업」에서 나중에 합치거나 버립니다.')}`
    : b('exit', '세션 끝내기', can.exit, 'danger', '세션 끝내기 — /exit로 세션을 완전히 끝냅니다. FOREMAN이 띄운 tmux 창도 닫습니다.')}
          ${b('more', moreOpen ? '접기 ▴' : '더보기 ▾', true, 'ghost', moreOpen ? '접기 — 작업 중단 · 일시정지 · 다시 시작을 다시 숨깁니다.' : '더보기 — 작업 중단 · 일시정지 · 다시 시작. 드물게 씁니다.')}
          ${moreOpen ? `${b('interrupt', '작업 중단(Esc)', can.interrupt, 'ghost', '작업 중단 — 지금 하는 작업만 멈춥니다(Esc). 세션은 살아 있습니다.')}
            ${b('stop', '일시정지', can.stop, 'ghost', '일시정지 — 세션을 잠시 멈춥니다(Ctrl+Z). 맥락은 그대로이고 [다시 시작]으로 이어 갑니다.')}
            ${b('resume', '다시 시작', can.resume, 'ghost', '다시 시작 — FOREMAN이 일시정지한 세션을 이어서 돌립니다.')}` : ''}
        </div>
        ${wtGroup(c.worktree, b)}
      </section>
      <details class="hand hand-docs"${docsOn ? ' open' : ''}><summary title="옮기기 전 정리 — 새 세션으로 옮기기 전에, 압축으로 잊은 것과 대화에서만 정한 것을 찾아 문서에 적습니다. 문서 정리 · 포트폴리오는 서기실에서 합니다."><b>옮기기 전 정리</b> <span class="small muted">잊은 것 · 대화 결정을 문서에${docsHint ? ` · <span class="warn">${esc(docsHint)}</span>` : ''}</span></summary>
        ${lossGroup(lc0, can.losscheck !== false && !!data.losschecks && !data.losschecks_error, data.losschecks_error)}
        ${promoteGroup(p0, !!can.promote, promDraft, data.promotions_error, data.promote_inputs, promIn)}
      </details>`;
    if (html === lastHtml) return;
    // 11-09 사용자 — "스크롤이 자동으로 맨 위로 되돌아가 끝까지 볼 수 없다". 다시 그려도 글 상자(.hand-body)와 패널 스크롤을 지킨다
    const pres = [...el.querySelectorAll('pre.hand-body')].map((p) => p.scrollTop);
    const box = el.closest('.oside-body'), top = box ? box.scrollTop : 0;
    el.innerHTML = html;
    lastHtml = html;
    el.querySelectorAll('pre.hand-body').forEach((p, i) => { if (pres[i]) p.scrollTop = pres[i]; });
    if (box && box.scrollTop !== top) box.scrollTop = top;
    // 그릴 때 open으로 그려도 toggle이 난다 — 그린 상태와 달라질 때만 사람이 바꾼 것으로 기억한다
    el.querySelector('details.hand-docs').addEventListener('toggle', (ev) => { if (ev.target.open !== docsOn) docsOpen = ev.target.open; });
  }

  el.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('button[data-act]');
    if (!btn || btn.disabled || sid == null) return;
    ev.preventDefault();
    const act = btn.dataset.act, id = sid;
    const post = (u, body) => api('POST', u, body || {});
    if (act === 'cancel') { mode = null; preview = null; editDraft = null; draw(); return; }
    // 더보기 — <details>에 display를 주면 브라우저에 따라 접힌 채로도 펼쳐져 보였다(11-06). 눌렀을 때만 그린다(기본 접힘)
    if (act === 'more') { moreOpen = !moreOpen; draw(); return; }
    if (act === 'prom-req') {
      const pick = el.querySelector('#promIn'), v = pick ? pick.value : 'none';
      if (v === '') { note = { bad: true, msg: '같이 넣을 것을 골라 주세요 — 넣지 않으려면 「넣지 않음」을 고릅니다.' }; draw(); return; }
      const body = v === 'none' ? { no_input: true } : v.startsWith('lc:') ? { loss_check_id: Number(v.slice(3)) } : { summary_id: Number(v) };
      return run('문서 후보 묻기', () => post(`/api/sessions/${id}/promote`, body).then((r) => ({ msg: `요청을 보냈습니다. 세션이 목록을 만드는 중입니다${
        r.summary_id ? `(요약 #${r.summary_id}의 「문서와 다른 지금」도 같이 넣었습니다)` : r.loss_check_id ? `(잃은 것 점검 #${r.loss_check_id}의 사라짐 · 약해짐도 같이 넣었습니다)` : ''}.` })));
    }
    if (act === 'loss-run') {
      if (!confirm('압축으로 잊은 것 찾기 — 압축 구간마다 사람이 한 말을 뽑아 claude -p로 판정합니다. 프롬프트 20개당 약 0.4달러 · 1.5분이 들고, 끝나면 알림이 갑니다. 진행할까요?')) return;
      return run('압축으로 잊은 것 찾기', () => post(`/api/sessions/${id}/losscheck`).then((r) => ({ msg: `점검을 시작했습니다(#${r.loss_check_id}, ${r.model}). 끝나면 알림이 갑니다.` })));
    }
    if (act === 'loss-use') {
      promIn = 'lc:' + btn.dataset.lc;
      note = { msg: '잊은 것을 같이 넣도록 골랐습니다 — 아래 「대화에서 정한 것 문서에 적기」의 [문서 후보 묻기]를 누릅니다.' };
      draw();
      return;
    }
    if (act === 'prom-save') {
      const p = prom(), body = { items: promoteEdits(p.items, promDraft) };
      return run('고친 것 저장', async () => { await api('PUT', `/api/promotions/${p.id}`, body); promDraft = {}; return { ok: true, msg: '저장했습니다.' }; });
    }
    if (act === 'prom-write') {
      const p = prom(), n = p.items.filter((x) => x.state === 'approved').length;
      if (promoteEdits(p.items, promDraft).length) { note = { bad: true, msg: '고친 것이 저장되지 않았습니다 — 먼저 [고친 것 저장]을 눌러 주세요.' }; draw(); return; }
      if (!confirm(`승인한 ${n}개를 세션이 문서에 쓰고 커밋합니다. 브리지가 커밋을 확인합니다. 진행할까요?`)) return;
      return run('고른 것을 문서에 쓰기', () => post(`/api/promotions/${p.id}/write`).then(() => ({ msg: '보냈습니다. 세션이 쓰고 커밋하는 중입니다.' })));
    }
    if (act === 'hand-more') { handMore = !handMore; draw(); return; }
    if (act === 'mv-write') return moveWrite();
    if (act === 'mv-retry') return moveRetry();
    if (act === 'mv-skip-find') { setFlow({ ...flow, stage: 'list', lcId: null, promId: null, err: null, errAt: null, at: Date.now() }); await load(); return; }
    if (act === 'flow-start') return startFlow();
    if (act === 'flow-stop' || act === 'flow-close') { setFlow(null); noteOpen = false; noteDraft = ''; note = act === 'flow-stop' ? { msg: '옮기기를 멈췄습니다. 받은 요약은 남아 있습니다.' } : null; draw(); return; }
    if (act === 'flow-go') return flowGo(null);
    if (act === 'flow-note') { noteOpen = true; draw(); const t = el.querySelector('#hNote'); if (t) t.focus(); return; }
    if (act === 'flow-note-off') { noteOpen = false; noteDraft = ''; draw(); return; }
    if (act === 'flow-go-note') {
      const v = (el.querySelector('#hNote') || {}).value ?? noteDraft;
      if (!v.trim()) { note = { bad: true, msg: '덧붙일 말이 비었습니다 — 적거나 [덧붙이지 않기]를 누릅니다.' }; draw(); return; }
      noteDraft = v;
      return flowGo(v);
    }
    if (act === 'flow-end') return flowEnd();
    const fmt = 'v2';           // 1판(요약 통째로) 고르기는 11-06에 뺐다 — 2판이 생긴 뒤 한 번도 안 썼다. API는 v1도 받는다
    if (act === 'summary') return run('요약 요청', () => post(`/api/sessions/${id}/summary`, { kind: 'snapshot', mode: 'live', fmt }).then(() => ({ msg: '요청을 보냈습니다. 세션이 요약을 쓰는 중입니다.' })));
    if (act === 'summary-end') return run('인계 요약 요청', () => post(`/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'live', fmt }).then(() => ({ msg: '요청을 보냈습니다. 요약이 오면 확인한 뒤 [세션 끝내기]를 눌러 주세요.' })));
    if (act === 'headless') {
      if (!confirm('끝난 세션을 잠깐 불러 요약을 받습니다. 그 세션의 맥락을 다시 읽느라 토큰을 씁니다. 진행할까요?')) return;
      return run('죽은 세션 요약', () => post(`/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'headless', fmt }).then(() => ({ msg: '요약을 받는 중입니다. 몇 분 걸릴 수 있습니다.' })));
    }
    if (act === 'reads-resend') return run('안 읽은 곳 다시 보내기', () => post(`/api/sessions/${id}/reads/resend`).then((r) => ({ ok: true, msg: `${r.missing.length}곳을 다시 보냈습니다${r.queued ? '(작업이 끝나면 전달됩니다)' : ''}.` })));
    if (act === 'compact') return run('압축 요약에서 만들기', () => post(`/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'compact' }));
    if (act === 'edit') { mode = 'edit'; editDraft = null; draw(); return; }
    if (act === 'edit-save') {
      const body = el.querySelector('#hEdit').value;
      mode = null; editDraft = null;
      return run('고친 본 저장', () => api('PUT', `/api/summaries/${latest().id}`, { body }));
    }
    if (act === 'spawn') {
      mode = 'spawn'; preview = null;
      const ok = latest();
      if (ok) { try { preview = await api('GET', `/api/summaries/${ok.id}/injection`); } catch (e) { note = { bad: true, msg: e.message }; } }
      draw(); return;
    }
    if (act === 'spawn-go' || act === 'spawn-bare') {
      const summary_id = act === 'spawn-go' && preview ? preview.summary_id : null;
      mode = null; preview = null;
      return run('새로 띄우기', async () => {
        const r = await post(`/api/sessions/${id}/spawn`, { summary_id });
        const where = `tmux ${r.tmux}`;
        return r.note ? { bad: !r.cc_session_id, msg: `${where} — ${r.note}` }
          : { ok: true, msg: `새 세션을 띄웠습니다(${where}).${summary_id ? (r.injected ? ' 요약을 넣었습니다.' : ' 요약은 넣지 못했습니다.') : ''}` };
      });
    }
    if (act === 'wt-preview') {
      // 팝업 차단을 피하려고 누른 순간에 창을 먼저 연다. 포트가 달라 브라우저 저장소가 따로라 토큰은 #t=로 넘긴다(서버로 안 간다)
      const win = window.open('about:blank', '_blank');
      return run('미리보기 열기', async () => {
        let r;
        try { r = await post(`/api/sessions/${id}/preview`); } catch (e) { if (win) win.close(); throw e; }
        const url = `${location.protocol}//${location.hostname}:${r.port}/#t=${encodeURIComponent(store.token || '')}`;
        if (win) win.location.href = url; else window.open(url, '_blank');
        return { ok: true, msg: `미리보기를 열었습니다(:${r.port}${r.reused ? ', 이미 돌던 것' : ''}).` };
      });
    }
    if (act === 'wt-preview-off') {
      // 미리보기 탭 안에서 누르면 이 탭을 띄운 서버가 꺼진다(11-06 — 끊긴 채로 남았다). 먼저 알린다
      if (window.FOREMAN_PREVIEW && !confirm('지금 이 탭이 미리보기입니다. 미리보기를 닫으면 이 탭은 끊깁니다(메인 브리지는 그대로입니다). 닫을까요?')) return;
      return run('미리보기 닫기', () => api('DELETE', `/api/sessions/${id}/preview`).then(() => ({ ok: true, msg: '미리보기를 껐습니다.' })));
    }
    // 쉬게 하기 · 이어서(11-09) — 실패하면 까닭(커밋 실패 · 뒤에서 도는 일 · 끝내기 확인 창 · resume 실패)을 그대로 띄운다
    if (act === 'rest') {
      const w = data.controls.worktree;
      if (!confirm(`지금까지를 ${w.branch}에 커밋하고(커밋 안 한 변경 ${w.dirty.length}개${w.dirty.length ? ' — .env · .venv 링크는 넣지 않습니다' : ''}) 세션만 끝냅니다. worktree는 남습니다. 나중에 [이어서] · [합치기] · [버리기]를 고릅니다. 쉬게 할까요?`)) return;
      return run('쉬게 하기', () => post(`/api/sessions/${id}/rest`).then((r) => ({ ok: !!r.ok, bad: !r.ok, msg: r.note || (r.ok ? '쉬게 했습니다.' : '쉬게 하지 못했습니다.') })));
    }
    if (act === 'rest-resume') {
      return run('이어서', () => post(`/api/sessions/${id}/rest-resume`).then((r) => ({ ok: !!r.ok, bad: !r.ok, msg: r.note || (r.ok ? '이어서 붙였습니다.' : '이어 붙이지 못했습니다.') })));
    }
    // 합치기 승인(11-11 1물결 A) — 브리지가 다시 재고(카드 뒤 커밋이 바뀌면 거절) 충돌이면 끝내지 않고 풀라고 보낸다
    if (act === 'mp-merge' || act === 'mp-skip') {
      const card = data.merge_prep && data.merge_prep.card;
      if (!card) return;
      if (act === 'mp-skip') return run('나중에', () => post(`/api/sessions/${id}/merge-prep`, { action: 'skip' }).then((r) => ({ ok: true, msg: r.note })));
      const ask = card.conflict && card.conflict.length
        ? `${card.branch}가 ${card.base}와 충돌합니다(${card.conflict.join(', ')}). 합치지 않고 ${card.live ? '그 세션에 main을 가져와 풀라고 보냅니다' : '관리자에게 풀라고 넘깁니다'}. 진행할까요?`
        : `${card.live ? '세션을 끝내고 ' : ''}${card.branch}의 커밋 ${card.ahead}개를 ${card.base}에 합칩니다${card.ff ? '' : '(rebase 뒤)'}. push는 하지 않습니다 — 시험 · push는 관리자가 합니다. 합칠까요?`;
      if (!confirm(ask)) return;
      return run('합치기 승인', () => post(`/api/sessions/${id}/merge-prep`, { action: 'merge' })
        .then((r) => ({ ok: !!r.ok, bad: !r.ok && r.status === 'failed', msg: r.note || (r.ok ? '합쳤습니다.' : '합치지 않았습니다.') })));
    }
    if (act === 'wt-merge' || act === 'wt-discard' || act === 'wt-end-merge' || act === 'wt-end-discard') {
      const w = data.controls.worktree;
      const end = act.startsWith('wt-end-');
      const kind = end ? act.slice(7) : act.slice(3);
      let confirmName = '';
      // 서기 글의 근거가 틀렸으면 합치기 전에 한 번 더(12b) — 막지는 않는다, 사람이 정한다
      const rvWarn = w.review && w.review.bad ? `\n\n주의: 근거 표시 ${w.review.bad}개가 틀렸습니다(없는 커밋 · 파일 · 턴). 「따로 작업」의 「자세히」에서 봅니다. 그래도 합칠까요?` : '';
      if (end && kind === 'merge') {
        if (!confirm(`세션을 끝내고 ${w.branch}의 커밋 ${w.ahead}개를 ${w.base}에 합칩니다(rebase → fast-forward). 커밋 안 된 변경이 있으면 끝내지 않고 알립니다. 충돌이 나면 되돌리고 멈춥니다(세션은 이미 끝난 뒤입니다). push는 하지 않습니다. 진행할까요?${rvWarn}`)) return;
        return run('끝내고 합치기', () => post(`/api/sessions/${id}/worktree`, { action: 'merge', end: true })
          .then((r) => (r.ok ? { ok: true, msg: '세션을 끝내고 ' + r.note + (r.schema_unlocked ? ' 스키마 잠금도 풀었습니다.' : '') }
            : { bad: true, msg: '세션은 끝냈습니다. ' + r.note + (r.conflict && r.conflict.length ? ` 충돌 파일: ${r.conflict.join(', ')}` : '') + ' — 「따로 작업」에서 다시 합치거나 버립니다.' })));
      }
      if (act === 'wt-merge') {
        if (!confirm(`${w.branch}의 커밋 ${w.ahead}개를 ${w.base}에 합칩니다(rebase → fast-forward). 충돌이 나면 되돌리고 멈춥니다. push는 하지 않습니다. 합칠까요?${rvWarn}`)) return;
      } else {
        confirmName = prompt(`${end ? '세션을 끝내고 ' : ''}worktree와 브랜치 ${w.branch}를 지웁니다. 합치지 않은 커밋 ${w.ahead}개${w.dirty.length ? `와 커밋 안 된 변경 ${w.dirty.length}개` : ''}도 사라집니다. 지우려면 이름 "${w.name}"을 적어 주세요.`) || '';
        if (!confirmName) return;
      }
      return run(kind === 'merge' ? '합치기' : end ? '끝내고 버리기' : '버리기', () => post(`/api/sessions/${id}/worktree`, { action: kind, confirm: confirmName, end })
        .then((r) => (r.ok ? { ok: true, msg: r.note + (r.schema_unlocked ? ' 스키마 잠금도 풀었습니다.' : '') }
          : { bad: true, msg: r.note + (r.conflict && r.conflict.length ? ` 충돌 파일: ${r.conflict.join(', ')}` : '') })));
    }
    const ACT = { exit: '세션 끝내기', 'exit-after': '세션 끝내기', stop: '일시정지', resume: '다시 시작', interrupt: '작업 중단' };
    const DONE = { exit: '세션을 끝냈습니다.', 'exit-after': '세션을 끝냈습니다.', stop: '일시정지했습니다.', resume: '다시 시작했습니다.', interrupt: '작업을 중단했습니다.' };
    if (ACT[act]) {
      const ask = { exit: '이 세션을 완전히 끝냅니다(/exit). 새 세션으로 옮기지 않고 끝내면 대화는 기록으로만 남습니다. 끝낼까요?',
                    'exit-after': '요약을 확인했으면 이 세션을 완전히 끝냅니다(/exit). 끝낼까요?',
                    stop: '이 세션을 일시정지합니다(Ctrl+Z). [다시 시작]을 누르기 전까지 입력을 받지 않습니다. 멈출까요?' }[act];
      const w = data.controls.worktree;
      const dirtyWarn = (act === 'exit' || act === 'exit-after') && w && w.exists && w.dirty && w.dirty.length
        ? `\n\n주의: 따로 작업(${w.branch})에 커밋 안 된 변경이 ${w.dirty.length}개 있습니다. 끝내면 합칠 수 없고 버리기만 됩니다. 먼저 세션에게 커밋을 시키는 것이 좋습니다.` : '';
      if (ask && !confirm(ask + dirtyWarn)) return;
      const action = act === 'exit-after' ? 'exit' : act;
      return run(ACT[act], () => post(`/api/sessions/${id}/action`, { action }).then((r) => (r.ok
        ? { ok: true, msg: DONE[act] + (r.tmux_closed ? ' tmux 창도 닫았습니다.' : '') }
        : { bad: true, msg: `${ACT[act]} — ${r.note || '확인하지 못했습니다.'}` })));
    }
  });

  // ── 넘기고 새로 시작 ─────────────────────────────────
  function setFlow(v) { flow = v; if (sid != null) flowPut(sid, v); }

  // ── 한 흐름(11-11, moveflow.js) — 잊은 것 찾기 → 문서 후보 → 고르기 → 쓰기 → 요약 → 새 세션 → 옛 세션 끝내기 ──
  let moveBusy = false;
  async function startMove() {
    if (!confirm('새 세션으로 옮기기 — 압축으로 잊은 것 찾기(내가 보낸 말 20개당 약 0.4달러 · 1.5분)부터 시작해, 문서에 넣을 후보를 보여 드립니다. '
      + '고르시면 문서에 쓰고 요약 · 새 세션 · 옛 세션 끝내기까지 이어서 합니다. 진행할까요?')) return;
    note = null; promDraft = {};
    try {
      const r = await api('POST', `/api/sessions/${sid}/losscheck`);
      setFlow({ v: 2, stage: 'find', lcId: r.loss_check_id, at: Date.now() });
    } catch (e) {          // 이미 도는 점검 등 — 그 단계 없이 문서 후보부터(까닭은 흐름 위에 남긴다)
      setFlow({ v: 2, stage: 'list', at: Date.now(), note: `잊은 것 찾기는 건너뜁니다 — ${e.message}` });
    }
    await load();
  }
  // 서버 상태를 보고 저절로 다음 단계로 — load 뒤마다 부른다. 세션이 바쁘면(작업 중) 다음 load에 다시
  async function moveTick() {
    if (!flow || flow.v !== 2 || moveBusy || !data || sid == null) return;
    const m = moveStep(flow, data);
    if (!m || !m.auto) return;
    const id = sid, can = data.controls.can;
    if (m.auto === 'spawn') { await flowGo(null); return; }
    if ((m.auto === 'promote' && !can.promote) || (m.auto === 'summary' && !can.summary)) return;
    moveBusy = true;
    try {
      if (m.auto === 'promote') {
        const r = await api('POST', `/api/sessions/${id}/promote`, m.lost ? { loss_check_id: flow.lcId } : { no_input: true });
        if (id === sid) setFlow({ ...flow, stage: 'list', promId: r.promotion_id, at: Date.now(),
          note: m.lcFailed && flow.lcId ? '잊은 것 찾기가 실패해 그 결과 없이 문서 후보를 물었습니다.' : flow.note });
      } else if (m.auto === 'summary') {
        const r = await api('POST', `/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'live', fmt: 'v2' });
        if (id === sid) setFlow({ ...flow, stage: 'summary', sumId: r.summary_id, at: Date.now() });
      }
    } catch (e) {
      if (id === sid) setFlow({ ...flow, err: `${m.auto === 'promote' ? '문서 후보를 묻지' : '요약을 요청하지'} 못했습니다 — ${e.message}`, errAt: m.i });
    } finally { moveBusy = false; }
    if (id === sid) await load();
  }
  async function moveWrite() {
    const m = moveStep(flow, data);
    if (!m || !m.wait) return;
    const p = m.p, n = chooseCount(p.items, promDraft);
    moveBusy = true;
    try {
      const ed = promoteEdits(p.items, promDraft);
      if (ed.length) await api('PUT', `/api/promotions/${p.id}`, { items: ed });
      promDraft = {};
      if (n) {
        await api('POST', `/api/promotions/${p.id}/write`);
        setFlow({ ...flow, stage: 'write', at: Date.now(), err: null });
      } else {
        setFlow({ ...flow, stage: 'summary', sumId: null, at: Date.now(), err: null });
      }
    } catch (e) { note = { bad: true, msg: `문서에 쓰지 못했습니다 — ${e.message}` }; }
    finally { moveBusy = false; }
    await load();
  }
  async function moveRetry() {
    const m = moveStep(flow, data) || {};
    const f = { ...flow, err: null, errAt: null, at: Date.now() };
    if (m.i === 5 || flow.errAt === 5) { setFlow(f); return flowGo(null); }
    if (m.i === 6 || flow.errAt === 6) { setFlow(f); return flowEnd(); }
    if (f.stage === 'list' && (m.i === 1)) f.promId = null;             // 목록을 다시 묻는다
    if (f.stage === 'summary' && m.i === 4) f.sumId = null;             // 요약을 다시 받는다
    setFlow(f);
    await load();
  }

  async function startFlow() {
    if (sid == null) return;
    if (!data) await load();
    const c = data && data.controls;
    if (!c) return;
    if (c.move_flow && c.live && c.can.summary) return startMove();     // 11-11 한 흐름(끝난 세션은 옛 흐름 — 문서에 쓸 세션이 없다)
    const live = c.live && c.can.summary;
    if (!live && !(c.can.headless && confirm('끝난 세션입니다. 잠깐 불러 요약을 받습니다 — 그 세션의 맥락을 다시 읽느라 토큰을 씁니다(식은 맥락은 비쌉니다). 진행할까요?'))) {
      if (!live && !c.can.headless) { note = { bad: true, msg: `옮기기를 시작할 수 없습니다 —${c.why || '지금은 요약을 받을 수 없습니다'}` }; draw(); }
      return;
    }
    note = null; flowPrev = null;
    try {
      const r = await api('POST', `/api/sessions/${sid}/summary`, { kind: 'handoff', mode: live ? 'live' : 'headless', fmt: 'v2' });
      setFlow({ sumId: r.summary_id, at: Date.now() });
    } catch (e) { note = { bad: true, msg: `옮기기 — 요약을 요청하지 못했습니다:${e.message}` }; }
    await load();
  }
  // ② 확인을 그리기 전에 넣을 글을 한 번 받는다
  async function flowPreview() {
    if (!flow || (flowPrev && flowPrev.summary_id === flow.sumId)) return;
    try { flowPrev = await api('GET', `/api/summaries/${flow.sumId}/injection?replace=1`); } catch (e) { setFlow({ ...flow, err: `넣을 글을 받지 못했습니다 — ${e.message}`, errAt: 1 }); }
    draw();
  }
  async function flowGo(extra) {                 // ③ 새 세션 → ④ 옛 세션 끝내기. extra — [덧붙여서 보내기]의 말
    const id = sid, f = flow;
    // 실패 뒤 [다시 시도](flow-go)도 덧붙일 말 칸이 열려 있으면 그 말을 같이 보낸다
    const add = extra != null ? extra : (noteOpen && noteDraft.trim() ? noteDraft : null);
    setFlow({ ...f, err: null, errAt: null, phase: 'spawning' }); draw();
    try {
      const r = await api('POST', `/api/sessions/${id}/spawn`, { summary_id: f.sumId, replace: true, ...(add ? { note: add } : {}) });   // 옮기기 — 옛 세션은 빼고 worktree 판단
      if (!r.cc_session_id || !r.injected) throw new Error(r.note || '새 세션에 요약을 넣었는지 확인하지 못했습니다');
    } catch (e) { if (id === sid) { setFlow({ ...f, phase: null, err: `새 세션을 띄우지 못했습니다 — ${e.message}`, errAt: f.v === 2 ? 5 : 2 }); await load(); } return; }
    await flowEnd(id);
  }
  async function flowEnd(id = sid) {
    const f = flowGet(id) || flow;
    if (id === sid) { setFlow({ ...f, err: null, errAt: null, phase: 'ending' }); draw(); }
    let res;
    try {
      const r = data && data.controls.live === false ? { ok: true } : await api('POST', `/api/sessions/${id}/action`, { action: 'exit' });
      res = r.ok ? { ...f, phase: 'done', err: null } : { ...f, phase: null, err: `옛 세션을 끝내지 못했습니다 — ${r.note || '확인하지 못했습니다'}`, errAt: f.v === 2 ? 6 : 3 };
    } catch (e) { res = { ...f, phase: null, err: `옛 세션을 끝내지 못했습니다 — ${e.message}`, errAt: f.v === 2 ? 6 : 3 }; }
    flowPut(id, res);
    if (id === sid) { flow = res; await load(); }
  }

  return {
    startFlow,
    setSession(id) {
      if (id === sid) return;
      sid = id; data = null; mode = null; preview = null; note = null; editDraft = null; promDraft = {}; promId = null; promIn = null;
      flow = id != null ? flowGet(id) : null; flowPrev = null; handMore = false; noteOpen = false; noteDraft = ''; lastHtml = '';
      if (flow && flow.phase && flow.phase !== 'done') flow = { ...flow, phase: null };   // 띄우는 · 끝내는 중에 새로 고침 — 서버 데이터로 다시 판단
      el.innerHTML = '';
      clearTimeout(timer);
      if (id != null) load();
    },
    refresh: load,
  };
}
