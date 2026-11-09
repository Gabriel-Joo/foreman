// 인계 · 세션 조작(11-05, docs/11_handoff.md) — 패널 [세션] 탭의 칸들. 11-06 정리: 자주 쓰는 것만 보이고 나머지는 접는다.
//   인계(늘 보임)  요약하고 끝내기 · 지금 요약 · 새로 띄우기, 요약 카드(머리에 [고치기]) · 요약 이력 · 읽을 곳
//   세션(늘 보임)  세션 끝내기, [더보기]를 눌러야 작업 중단 · 일시정지 · 다시 시작 / 따로 작업(worktree일 때)
//   문서 정리(접힘, 할 일이 있으면 열림)  압축 손실 [잃은 것 찾기] · 문서에 남기기 [남길 것 찾기]
// 자기 데이터(/api/sessions/{id}/handoff)를 따로 받아 따로 그린다 — 세션 칸이 다시 그려져도 고치던 글이 날아가지 않게.

import { esc, ago, keep } from './render.js';
import { promoteGroup, edits as promoteEdits } from './promote.js';
import { lossGroup } from './losscheck.js';

const SOURCE = { self: '세션이 씀', self_headless: '끝난 세션을 잠깐 불러 씀', compact: '자동 압축 요약에서', edited: '사람이 고침' };
const STATUS = { requested: '기다리는 중…', ok: '저장됨', failed: '실패', timeout: '시간 초과' };
// 11-09 화면 말 통일 — "인계"는 "새 세션으로 옮기기"(문서 · log · 세션에 넣는 글은 그대로 "인계")
const KIND = { snapshot: '지금 요약', handoff: '옮기기용 요약' };
export const FLOW_TIP = '새 세션으로 옮기기 — 지금까지를 요약해 보여 드리고, 확인하면 같은 폴더에 새 세션을 띄워 요약을 넣은 뒤 이 세션을 끝냅니다. 어느 단계에서나 멈출 수 있습니다.';

// 넘기고 새로 시작(11-08 사용자 — 흩어진 [요약하고 끝내기] · [지금 요약] · [새로 띄우기] · 압축 요약을 버튼 하나로).
// ① 요약 → ② 확인(넣을 글을 보여 줌) → ③ 새 세션 → ④ 옛 세션 끝내기. 어디까지 왔는지는 이 브라우저에 세션마다 기억한다
// (다른 세션을 봤다 와도, 새로 고쳐도 이어진다). [멈추기]는 어느 단계에서나 — 요약은 남는다.
export const FLOW_STEPS = ['요약', '확인', '새 세션', '옛 세션 끝내기'];
const FLOW_KEY = 'foremanFlow:';
const flowGet = (id) => { try { return JSON.parse(localStorage.getItem(FLOW_KEY + id) || 'null'); } catch { return null; } };
const flowPut = (id, v) => { try { if (v) localStorage.setItem(FLOW_KEY + id, JSON.stringify(v)); else localStorage.removeItem(FLOW_KEY + id); } catch { /* 이 탭에서만 */ } };

// 흐름의 지금 단계 — 저장한 것(flow)과 서버 데이터(요약 상태 · 넣음 · 세션이 살아 있나)로 정한다. 순수 함수(시험)
export function flowStep(flow, summary, live) {
  if (!flow) return null;
  if (flow.phase === 'done') return { i: 4, done: true };
  if (flow.phase === 'spawning') return { i: 2, busy: true };
  if (flow.phase === 'ending') return { i: 3, busy: true };
  if (flow.err) return { i: flow.errAt ?? 0, bad: true, msg: flow.err };
  if (!summary || summary.status === 'requested') return { i: 0, busy: true };
  if (summary.status !== 'ok') return { i: 0, bad: true, msg: summary.error || '요약을 받지 못했습니다' };
  if (summary.injected_at) return live ? { i: 3 } : { i: 4, done: true };   // 넣었는데 옛 세션이 살아 있다 — 끝내기만 남음
  return { i: 1 };
}

export function mountHandoff(el, store, { open: open0 = false, onToggle } = {}) {
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
  }
  function schedule() {
    clearTimeout(timer);
    if (sid == null) return;
    const p0 = data && data.promotions && data.promotions[0];
    const pending = data && (data.controls.pending_req || (data.summaries[0] && data.summaries[0].status === 'requested') || (flow && !flow.phase)
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
    const why = w.live ? '세션을 끝내면서 합치거나 버립니다 — 위 「세션」의 [끝내고 합치기] · [끝내고 버리기].'
      : w.dirty.length ? `커밋 안 된 변경 ${w.dirty.length}개 — 그 세션에서 커밋하거나 버려야 합칠 수 있습니다.` : '';
    return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div>
      <div class="small"><code>${esc(w.branch)}</code> · ${esc(w.base)}보다 커밋 <b>${w.ahead}</b>개 앞${w.behind ? ` · <span title="${esc(w.base)}가 ${w.behind}개 앞서감(합칠 때 rebase) — 이 브랜치를 만든 뒤 ${esc(w.base)}에 들어온 커밋입니다. 합칠 때 그 위로 다시 얹습니다.">${esc(w.base)}에 새 변경 ${w.behind}개</span>` : ''}${w.dirty.length ? ` · <span class="warn">커밋 안 됨 ${w.dirty.length}</span>` : ''}${w.schema_lock ? ' · <span class="warn" title="스키마 잠금 보유 — 이 세션이 DB 구조(migrations)를 바꾸는 중이라 다른 세션은 바꿀 수 없습니다.">DB 구조 바꾸는 중</span>' : ''}</div>
      ${w.commits.length ? `<details${keep(`hand:${sid}:wt-commits`)}><summary class="small muted">커밋 · 바뀐 파일</summary><pre class="hand-body">${esc(w.commits.join('\n'))}\n\n${esc(w.diffstat.join('\n'))}</pre></details>` : ''}
      ${why ? `<div class="small muted">${esc(why)}</div>` : ''}
      ${reviewBlock(w.review)}
      ${w.preview ? `<div class="small ok">미리보기가 :${w.preview.port}에서 돌고 있습니다.</div>` : ''}
      <div class="hand-btns">
        ${w.preview_ok ? b('wt-preview', '미리보기 열기', true, '', '미리보기 열기 — 이 브랜치의 화면 파일로 새 탭을 엽니다. 데이터와 버튼은 실제 브리지입니다. 없으면 빈 포트로 띄웁니다.') : ''}
        ${w.preview ? b('wt-preview-off', '미리보기 닫기', true, 'ghost', '미리보기 닫기 — 미리보기 서버를 끕니다.') : ''}
        ${w.live ? '' : `${b('wt-merge', '합치기', !w.dirty.length, 'primary', `합치기 — ${w.branch}를 ${w.base} 위로 rebase한 뒤 fast-forward로 합치고 worktree를 지웁니다. 충돌이 나면 되돌리고 멈춥니다. push는 하지 않습니다.`)}
        ${b('wt-discard', '버리기', true, 'danger', '버리기 — worktree와 브랜치를 지웁니다. 합치지 않은 커밋도 사라집니다.')}`}
      </div></div></div>`;
  }

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
  const wtNext = (p) => (p && p.worktree_next ? `<div class="small warn" title="따로 작업에서 뜹니다 — 이 프로젝트에 살아 있는 세션이 있어(옮기기는 이 세션을 빼고 셉니다) 새 세션은 .worktrees/ 아래 자기 브랜치에서 뜹니다. 받은 세션은 push · 브리지 재시작을 하지 않고, 끝낸 뒤 [합치기]로 합칩니다.">⑂ 새 세션은 따로 작업(worktree)에서 뜹니다 — 넣을 때 그 사실을 글 맨 앞에 덧붙입니다.</div>` : '');
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
        <div class="row">${b('spawn-go', '이 글을 넣고 시작', !preview.blocked, 'primary', preview.blocked ? '넣을 수 없습니다 — 읽을 곳을 고친 뒤 넣습니다(요약 카드의 [고치기]).' : '이 글을 넣고 시작 — 같은 폴더에 새 세션을 띄우고 위 글을 첫 입력으로 넣습니다.')}${b('spawn-bare', '요약 없이 시작', true, 'ghost', '요약 없이 시작 — 같은 폴더에 빈 새 세션만 띄웁니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 띄우지 않고 돌아갑니다.')}</div>`
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
        const go = !!p && !p.blocked && can.spawn;
        const goTip = p && p.blocked ? '넣을 수 없습니다 — 읽을 곳을 고친 뒤 넣습니다([더보기] → [요약 고치기]).' : '';
        body += `<div class="row flow-act">${noteOpen
          ? `${b('flow-go-note', '덧붙여서 보내기', go, 'primary', goTip || '덧붙여서 보내기 — 위 글 끝에 덧붙일 말을 붙여 새 세션에 넣고, 이 세션을 /exit로 끝냅니다.')}${b('flow-note-off', '덧붙이지 않기', true, 'ghost', '덧붙이지 않기 — 덧붙일 말 칸을 닫습니다. 적은 말은 버립니다.')}`
          : `${b('flow-go', '이대로 보내기', go, 'primary', goTip || '이대로 보내기 — 같은 폴더에 새 세션을 띄워 위 글을 넣고, 이 세션을 /exit로 끝냅니다.')}${b('flow-note', '덧붙여서 보내기', go, 'ghost', goTip || '덧붙여서 보내기 — 보내기 전에 한 줄 덧붙일 칸을 엽니다.')}`}${b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 띄우지 않습니다. 요약은 남습니다.')}</div>`;
      } else if (st.i === 2) body = '<div class="small muted">새 세션을 띄우고 요약을 넣는 중입니다…</div>';
      else if (st.i === 3) body = st.busy ? '<div class="small muted">옛 세션을 끝내는 중입니다… 맥락이 큰 세션은 수십 초 걸립니다.</div>'
        : `<div class="small">새 세션이 이어받았습니다. 옛 세션 끝내기만 남았습니다.</div><div class="row flow-act">${b('flow-end', '옛 세션 끝내기', can.exit, 'primary danger', '옛 세션 끝내기 — 이 세션을 /exit로 끝냅니다.')}${b('flow-stop', '멈추기', true, 'ghost', '멈추기 — 이 세션을 살려 둡니다.')}</div>`;
      main = `<div class="flow">${steps}${body}</div>`;
    }
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
    const html = `
      <section class="hand">
        <div class="hand-h"><b>새 세션으로 옮기기</b>${s0 ? ` <span class="small muted" title="마지막 요약 — ${esc(KIND[s0.kind] || s0.kind)}, ${esc(STATUS[s0.status] || s0.status)}">· 요약 ${esc(STATUS[s0.status] || s0.status)} ${ago(s0.created_at)}</span>` : ''}</div>
        <div class="hand-btns">
          ${st ? '' : b('flow-start', '새 세션으로 옮기기', can.summary || (!c.live && can.headless), 'primary', FLOW_TIP)}
          ${b('hand-more', handMore ? '접기 ▴' : '더보기 ▾', true, 'ghost', handMore ? '접기 — 드문 버튼을 다시 숨깁니다.' : '더보기 — 지금 요약 · 요약만 넣어 띄우기 · 요약 고치기 · 끝난 세션 요약. 드물게 씁니다.')}
          ${handMore ? `${b('summary', '지금 요약(계속 돎)', can.summary, 'ghost', '지금 요약 — 세션이 지금까지 한 일을 정리합니다. 세션은 끝내지 않고 계속 돕니다.')}
          ${b('spawn', '새 세션만 띄우기', can.spawn, 'ghost', '새 세션만 띄우기 — 이 세션은 두고, 같은 폴더에 새 세션을 띄워 마지막 요약(또는 빈 채로)을 넣습니다.')}
          ${!c.live ? b('compact', '압축 요약으로 만들기', can.compact, 'ghost', '압축 요약으로 만들기 — 끝난 세션이 마지막 자동 압축 때 남긴 요약으로 옮기기용 요약을 만듭니다. 토큰을 쓰지 않지만 「읽을 곳」이 없는 거친 요약입니다.') : ''}` : ''}
        </div>
        ${!st && !(can.summary || (!c.live && can.headless)) && c.why ? `<div class="small muted">${esc(c.why === '작업 중입니다' ? '세션이 작업 중이라 지금은 못 합니다. 끝나면 눌러주세요.' : /입니다$/.test(c.why) ? c.why.replace(/입니다$/, '이라 지금은 못 합니다.') : c.why + '.')}</div>` : ''}
        ${note ? `<div class="small ${note.bad ? 'bad' : note.ok ? 'ok' : 'muted'}">${esc(note.msg)}</div>` : ''}
        ${editLink ? `<div class="hand-edit-link">${editLink}</div>` : ''}
        ${main}${hist}
        ${readsLine(c.reads, can.exit)}
      </section>
      <section class="hand">
        <div class="hand-h"><b>세션</b></div>
        <div class="hand-btns">
          ${wtLive ? `${b('wt-end-merge', '끝내고 합치기', can.exit, '', `끝내고 합치기 — 커밋 안 된 변경이 없으면 세션을 끝내고 ${c.worktree.branch}를 ${c.worktree.base}에 합칩니다. 있으면 끝내지 않고 알립니다.`)}
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
      return run('대화 결정 목록 뽑기', () => post(`/api/sessions/${id}/promote`, body).then((r) => ({ msg: `요청을 보냈습니다. 세션이 목록을 만드는 중입니다${
        r.summary_id ? `(요약 #${r.summary_id}의 「문서와 다른 지금」도 같이 넣었습니다)` : r.loss_check_id ? `(잃은 것 점검 #${r.loss_check_id}의 사라짐 · 약해짐도 같이 넣었습니다)` : ''}.` })));
    }
    if (act === 'loss-run') {
      if (!confirm('압축으로 잊은 것 찾기 — 압축 구간마다 사람이 한 말을 뽑아 claude -p로 판정합니다. 프롬프트 20개당 약 0.4달러 · 1.5분이 들고, 끝나면 알림이 갑니다. 진행할까요?')) return;
      return run('압축으로 잊은 것 찾기', () => post(`/api/sessions/${id}/losscheck`).then((r) => ({ msg: `점검을 시작했습니다(#${r.loss_check_id}, ${r.model}). 끝나면 알림이 갑니다.` })));
    }
    if (act === 'loss-use') {
      promIn = 'lc:' + btn.dataset.lc;
      note = { msg: '「대화 결정 문서에 적기」에 같이 넣도록 골랐습니다 — 아래 [목록 뽑기]를 눌러 주세요.' };
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
      return run('승인한 것 쓰기', () => post(`/api/promotions/${p.id}/write`).then(() => ({ msg: '보냈습니다. 세션이 쓰고 커밋하는 중입니다.' })));
    }
    if (act === 'hand-more') { handMore = !handMore; draw(); return; }
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
  async function startFlow() {
    if (sid == null) return;
    if (!data) await load();
    const c = data && data.controls;
    if (!c) return;
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
    } catch (e) { if (id === sid) { setFlow({ ...f, phase: null, err: `새 세션을 띄우지 못했습니다 — ${e.message}`, errAt: 2 }); await load(); } return; }
    await flowEnd(id);
  }
  async function flowEnd(id = sid) {
    const f = flowGet(id) || flow;
    if (id === sid) { setFlow({ ...f, err: null, errAt: null, phase: 'ending' }); draw(); }
    let res;
    try {
      const r = data && data.controls.live === false ? { ok: true } : await api('POST', `/api/sessions/${id}/action`, { action: 'exit' });
      res = r.ok ? { ...f, phase: 'done', err: null } : { ...f, phase: null, err: `옛 세션을 끝내지 못했습니다 — ${r.note || '확인하지 못했습니다'}`, errAt: 3 };
    } catch (e) { res = { ...f, phase: null, err: `옛 세션을 끝내지 못했습니다 — ${e.message}`, errAt: 3 }; }
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
