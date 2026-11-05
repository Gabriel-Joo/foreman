// 인계 · 세션 조작(11-05, docs/11_handoff.md) — 패널 [세션] 탭의 칸들. 11-06 정리: 자주 쓰는 것만 보이고 나머지는 접는다.
//   인계(늘 보임)  요약하고 끝내기 · 지금 요약 · 새로 띄우기, 요약 카드(머리에 [고치기]) · 요약 이력 · 읽을 곳
//   세션(늘 보임)  세션 끝내기, 「더」 안에 작업 중단 · 일시정지 · 다시 시작 / 따로 작업(worktree일 때)
//   문서 정리(접힘, 할 일이 있으면 열림)  압축 손실 [잃은 것 찾기] · 문서에 남기기 [남길 것 찾기]
// 자기 데이터(/api/sessions/{id}/handoff)를 따로 받아 따로 그린다 — 세션 칸이 다시 그려져도 고치던 글이 날아가지 않게.

import { esc, ago } from './render.js';
import { promoteGroup, edits as promoteEdits } from './promote.js';
import { lossGroup } from './losscheck.js';

const SOURCE = { self: '세션이 씀', self_headless: '세션이 씀(죽은 세션, claude -p)', compact: '자동 압축 요약에서', edited: '사람이 고침' };
const STATUS = { requested: '기다리는 중…', ok: '저장됨', failed: '실패', timeout: '시간 초과' };
const KIND = { snapshot: '지금 요약', handoff: '끝내기 전 인계' };

export function mountHandoff(el, store, { open: open0 = false, onToggle } = {}) {
  let sid = null, data = null, mode = null, preview = null, note = null, open = open0;
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
    const pending = data && (data.controls.pending_req || (data.summaries[0] && data.summaries[0].status === 'requested')
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

  // 따로 작업(worktree, 11-05) — 이 세션만의 폴더 · 브랜치. 끝낸 뒤 [합치기](rebase → fast-forward) · [버리기]
  function wtGroup(w, b) {
    if (!w) return '';
    if (w.error) return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div class="small bad">${esc(w.error)}</div></div>`;
    if (!w.exists) return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div class="small muted">${esc(w.branch)} — 합쳤거나 버려서 지금은 없습니다.</div></div>`;
    const why = w.live ? '세션을 끝낸 뒤 합칠 수 있습니다.' : w.dirty.length ? `커밋 안 된 변경 ${w.dirty.length}개 — 그 세션에서 커밋하거나 버려야 합칠 수 있습니다.` : '';
    return `<div class="hand-group"><span class="hand-lbl small muted">따로 작업</span><div>
      <div class="small"><code>${esc(w.branch)}</code> · ${esc(w.base)}보다 커밋 <b>${w.ahead}</b>개 앞${w.behind ? ` · ${esc(w.base)}가 ${w.behind}개 앞서감(합칠 때 rebase)` : ''}${w.dirty.length ? ` · <span class="warn">커밋 안 됨 ${w.dirty.length}</span>` : ''}${w.schema_lock ? ' · <span class="warn">스키마 잠금 보유</span>' : ''}</div>
      ${w.commits.length ? `<details><summary class="small muted">커밋 · 바뀐 파일</summary><pre class="hand-body">${esc(w.commits.join('\n'))}\n\n${esc(w.diffstat.join('\n'))}</pre></details>` : ''}
      ${why ? `<div class="small muted">${esc(why)}</div>` : ''}
      ${w.preview ? `<div class="small ok">미리보기가 :${w.preview.port}에서 돌고 있습니다.</div>` : ''}
      <div class="hand-btns">
        ${w.preview_ok ? b('wt-preview', '미리보기 열기', true, '', '미리보기 열기 — 이 브랜치의 화면 파일로 새 탭을 엽니다. 데이터와 버튼은 실제 브리지입니다. 없으면 빈 포트로 띄웁니다.') : ''}
        ${w.preview ? b('wt-preview-off', '미리보기 닫기', true, 'ghost', '미리보기 닫기 — 미리보기 서버를 끕니다.') : ''}
        ${b('wt-merge', '합치기', !w.live && !w.dirty.length, '', `합치기 — ${w.branch}를 ${w.base} 위로 rebase한 뒤 fast-forward로 합치고 worktree를 지웁니다. 충돌이 나면 되돌리고 멈춥니다. push는 하지 않습니다.`)}
        ${b('wt-discard', '버리기', !w.live, 'danger', '버리기 — worktree와 브랜치를 지웁니다. 합치지 않은 커밋도 사라집니다.')}
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
  // 2판 인계를 받고 시작한 세션 — 읽을 곳을 실제로 Read했나
  function readsLine(r, can) {
    if (!r) return '';
    const all = r.read === r.total;
    return `<div class="hand-group"><span class="hand-lbl small muted">읽을 곳</span><div class="hand-btns">
      <span class="small ${all ? 'ok' : 'warn'}">${r.read}/${r.total} 읽음${all ? '' : ` — 안 읽음: ${r.missing.map(esc).join(', ')}`}${r.auto && r.auto.length ? ` <span class="muted" title="자동 — 세션이 시작할 때 저절로 들어오는 문서라 읽음으로 셉니다.">(자동: ${r.auto.map(esc).join(', ')})</span>` : ''}</span>
      ${all ? '' : `<button data-act="reads-resend" class="small"${can ? '' : ' disabled'} title="안 읽은 곳 다시 보내기 — 아직 읽지 않은 문서만 다시 보내고, 읽은 뒤 걸리는 규칙을 말하게 합니다.">안 읽은 곳 다시 보내기</button>`}
    </div></div>`;
  }

  function draw() {
    if (sid == null || !data) { el.innerHTML = ''; return; }
    const c = data.controls, can = c.can, s0 = data.summaries[0], ok = latest();
    const b = (act, label, on, cls = '', tip = '') => `<button data-act="${act}" class="small ${cls}"${tip ? ` title="${esc(tip)}"` : ''}${on ? '' : ' disabled'}>${label}</button>`;
    const sumCard = (x) => !x ? '<p class="small muted">아직 인계 요약이 없습니다.</p>' : `
      <div class="hand-sum">
        <div class="small"><b>${esc(KIND[x.kind] || x.kind)}</b> · ${esc(SOURCE[x.source] || x.source)} ·
          <span class="${x.status === 'ok' ? 'ok' : x.status === 'requested' ? '' : 'bad'}">${esc(STATUS[x.status] || x.status)}</span>
          · ${ago(x.created_at)}${x.chars ? ` · ${x.chars.toLocaleString()}자` : ''}${x.injected_at ? ` · <span class="ok">새 세션 ${esc((x.injected_cc_session || '').slice(0, 8))}에 넣음</span>` : ''}</div>
        ${x.error ? `<div class="small bad">${esc(x.error)}</div>` : ''}
        ${x.body ? `<pre class="hand-body">${esc(x.body)}</pre>` : ''}
        ${!x.body && x.raw ? `<details><summary class="small muted">응답 원문</summary><pre class="hand-body">${esc(x.raw)}</pre></details>` : ''}
      </div>`;
    let main;
    if (mode === 'edit' && ok) {
      main = `<textarea id="hEdit" rows="14" class="hand-edit">${esc(editDraft ?? ok.body)}</textarea>
        <div class="row">${b('edit-save', '고친 본 저장', true, '', '저장 — 원본은 두고 고친 본을 새 판으로 저장합니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 고친 것을 버리고 요약 카드로 돌아갑니다.')}</div>`;
    } else if (mode === 'spawn') {
      main = preview ? `<div class="small">같은 폴더에 새 세션을 띄우고 아래 글을 첫 입력으로 넣습니다.${preview.cut ? ` <span class="warn">길어서 일부 절을 줄였습니다(전체는 ${esc(preview.full_path)}).</span>` : ''}</div>
        ${preview.v2 ? pointerList(preview) : ''}
        <pre class="hand-body">${esc(preview.text)}</pre>
        <div class="row">${b('spawn-go', '이 글을 넣고 시작', !preview.blocked, '', preview.blocked ? '넣을 수 없습니다 — 읽을 곳을 고친 뒤 넣습니다(요약 카드의 [고치기]).' : '이 글을 넣고 시작 — 같은 폴더에 새 세션을 띄우고 위 글을 첫 입력으로 넣습니다.')}${b('spawn-bare', '요약 없이 시작', true, 'ghost', '요약 없이 시작 — 같은 폴더에 빈 새 세션만 띄웁니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 띄우지 않고 돌아갑니다.')}</div>`
        : `<div class="small">넣을 인계 요약이 없습니다.</div><div class="row">${b('spawn-bare', '요약 없이 새로 띄우기', true, '', '요약 없이 새로 띄우기 — 같은 폴더에 빈 새 세션만 띄웁니다.')}${b('cancel', '취소', true, 'ghost', '취소 — 띄우지 않고 돌아갑니다.')}</div>`;
    } else {
      main = sumCard(s0 && s0.status !== 'ok' && ok && s0.id !== ok.id ? s0 : ok || s0) +
        (s0 && ok && s0.id !== ok.id && s0.status !== 'ok' ? `<div class="small muted">이전 저장본 ↓</div>${sumCard(ok)}` : '') +
        (ok && ok.kind === 'handoff' && can.exit && !ok.injected_at ? `<div class="row">${b('exit-after', '요약을 확인했습니다 — 세션 끝내기', true, 'danger', '세션 끝내기 — 위 인계 요약을 확인했으면 이 세션을 /exit로 끝냅니다. 요약은 남고 [새로 띄우기]로 넣을 수 있습니다.')}</div>` : '');
    }
    const hist = data.summaries.length > 1 ? `<details class="hand-hist"><summary class="small muted">요약 이력 ${data.summaries.length}</summary>${
      data.summaries.map((x) => `<div class="small">#${x.id} ${esc(KIND[x.kind] || x.kind)} · ${esc(SOURCE[x.source] || x.source)} · ${esc(STATUS[x.status] || x.status)} · ${ago(x.created_at)}${x.chars ? ` · ${x.chars}자` : ''}</div>`).join('')}</details>` : '';
    // 문서 정리 — 평소엔 접고, 사람이 할 일(목록 승인 · 쓰기 확인)이나 도는 점검이 있으면 연다(사람이 닫으면 그대로)
    const p0 = prom(), lc0 = (data.losschecks || [])[0] || null;
    const docsBusy = (p0 && ['requested', 'listed', 'writing', 'write_failed'].includes(p0.status)) || (lc0 && lc0.status === 'running');
    const docsHint = p0 && p0.status === 'listed' ? '승인할 목록이 있습니다' : p0 && p0.status === 'write_failed' ? '확인 실패 — 봐 주세요'
      : docsBusy ? '도는 중…' : lc0 && lc0.status === 'done' && lc0.lost_total ? `잃은 것 ${lc0.lost_total}` : '';
    const docsOn = docsOpen ?? !!docsBusy;
    // 요약 카드 머리의 작은 [고치기] — 자주 안 쓰므로 버튼 줄에서 뺐다(11-06, 이력 1번)
    const editLink = ok && mode == null ? b('edit', '고치기', true, 'ghost', '요약 고치기 — 저장된 요약을 직접 고칩니다. 원본은 두고 새 판으로 저장합니다.') : '';
    el.innerHTML = `
      <section class="hand">
        <div class="hand-h"><b>인계</b> <span class="small muted">${esc(c.why || (c.live ? '살아 있음' : ''))}${s0 ? ` · 요약 ${esc(STATUS[s0.status] || s0.status)} ${ago(s0.created_at)}` : ''}</span></div>
        <div class="hand-btns">
          ${b('summary-end', '요약하고 끝내기', can.summary, '', '요약하고 끝내기 — 세션이 다음 세션에 넘길 인계를 씁니다. 받은 요약을 확인한 뒤 [세션 끝내기]를 눌러야 끝납니다.')}
          ${b('summary', '지금 요약', can.summary, '', '지금 요약 — 세션이 지금까지 한 일을 스스로 정리합니다. 세션은 계속 돕니다.')}
          ${b('spawn', '새로 띄우기', can.spawn, '', '새로 띄우기 — 같은 폴더에 새 세션을 띄우고 마지막 요약을 넣습니다. 넣을 글을 먼저 보여 줍니다.')}
          ${!c.live ? b('headless', '죽은 세션 요약 받기', can.headless, 'ghost', '죽은 세션 요약 받기 — 끝난 세션을 잠깐 불러 요약을 받습니다. 그 세션의 맥락을 다시 읽느라 토큰을 씁니다.') : ''}
          ${!c.live ? b('compact', '압축 요약에서', can.compact, 'ghost', '압축 요약에서 — 끝난 세션이 마지막으로 자동 압축한 요약으로 인계를 만듭니다. 토큰을 쓰지 않습니다.') : ''}
        </div>
        ${note ? `<div class="small ${note.bad ? 'bad' : note.ok ? 'ok' : 'muted'}">${esc(note.msg)}</div>` : ''}
        ${editLink ? `<div class="hand-edit-link">${editLink}</div>` : ''}
        ${main}${hist}
        ${readsLine(c.reads, can.exit)}
      </section>
      <section class="hand">
        <div class="hand-h"><b>세션</b></div>
        <div class="hand-btns">
          ${b('exit', '세션 끝내기', can.exit, 'danger', '세션 끝내기 — /exit로 세션을 완전히 끝냅니다. FOREMAN이 띄운 tmux 창도 닫습니다.')}
          <details class="hand-more"${moreOpen ? ' open' : ''}><summary class="small muted" title="더 — 일시정지 · 다시 시작 · 작업 중단. 드물게 씁니다.">더</summary>
            ${b('interrupt', '작업 중단(Esc)', can.interrupt, 'ghost', '작업 중단 — 지금 하는 작업만 멈춥니다(Esc). 세션은 살아 있습니다.')}
            ${b('stop', '일시정지', can.stop, 'ghost', '일시정지 — 세션을 잠시 멈춥니다(Ctrl+Z). 맥락은 그대로이고 [다시 시작]으로 이어 갑니다.')}
            ${b('resume', '다시 시작', can.resume, 'ghost', '다시 시작 — FOREMAN이 일시정지한 세션을 이어서 돌립니다.')}
          </details>
        </div>
        ${wtGroup(c.worktree, b)}
      </section>
      <details class="hand hand-docs"${docsOn ? ' open' : ''}><summary title="문서 정리 — 대화에서만 정한 것과 압축으로 잊은 것을 찾아 문서에 남깁니다."><b>문서 정리</b> <span class="small muted">대화에서 정한 것을 문서에 남깁니다${docsHint ? ` · <span class="warn">${esc(docsHint)}</span>` : ''}</span></summary>
        ${lossGroup(lc0, can.losscheck !== false && !!data.losschecks && !data.losschecks_error, data.losschecks_error)}
        ${promoteGroup(p0, !!can.promote, promDraft, data.promotions_error, data.promote_inputs, promIn)}
      </details>`;
    // 그릴 때 open으로 그려도 toggle이 난다 — 그린 상태와 달라질 때만 사람이 바꾼 것으로 기억한다
    el.querySelector('details.hand-docs').addEventListener('toggle', (ev) => { if (ev.target.open !== docsOn) docsOpen = ev.target.open; });
    el.querySelector('details.hand-more').addEventListener('toggle', (ev) => { moreOpen = ev.target.open; });
  }

  el.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('button[data-act]');
    if (!btn || btn.disabled || sid == null) return;
    ev.preventDefault();
    const act = btn.dataset.act, id = sid;
    const post = (u, body) => api('POST', u, body || {});
    if (act === 'cancel') { mode = null; preview = null; editDraft = null; draw(); return; }
    if (act === 'prom-req') {
      const pick = el.querySelector('#promIn'), v = pick ? pick.value : 'none';
      if (v === '') { note = { bad: true, msg: '같이 넣을 것을 골라 주세요 — 넣지 않으려면 「넣지 않음」을 고릅니다.' }; draw(); return; }
      const body = v === 'none' ? { no_input: true } : v.startsWith('lc:') ? { loss_check_id: Number(v.slice(3)) } : { summary_id: Number(v) };
      return run('남길 것 찾기', () => post(`/api/sessions/${id}/promote`, body).then((r) => ({ msg: `요청을 보냈습니다. 세션이 목록을 만드는 중입니다${
        r.summary_id ? `(인계 #${r.summary_id}의 「문서와 다른 지금」도 같이 넣었습니다)` : r.loss_check_id ? `(잃은 것 점검 #${r.loss_check_id}의 사라짐 · 약해짐도 같이 넣었습니다)` : ''}.` })));
    }
    if (act === 'loss-run') {
      if (!confirm('잃은 것 찾기 — 압축 구간마다 사람이 한 말을 뽑아 claude -p로 판정합니다. 프롬프트 20개당 약 0.4달러 · 1.5분이 들고, 끝나면 알림이 갑니다. 진행할까요?')) return;
      return run('잃은 것 찾기', () => post(`/api/sessions/${id}/losscheck`).then((r) => ({ msg: `점검을 시작했습니다(#${r.loss_check_id}, ${r.model}). 끝나면 알림이 갑니다.` })));
    }
    if (act === 'loss-use') {
      promIn = 'lc:' + btn.dataset.lc;
      note = { msg: '[남길 것 찾기]에 같이 넣도록 골랐습니다 — 아래 [남길 것 찾기]를 눌러 주세요.' };
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
      if (!confirm(`승인한 ${n}개를 세션이 문서에 쓰고 「인계 전 결정 기록」으로 커밋합니다. 브리지가 커밋을 확인합니다. 진행할까요?`)) return;
      return run('승인한 것 쓰기', () => post(`/api/promotions/${p.id}/write`).then(() => ({ msg: '보냈습니다. 세션이 쓰고 커밋하는 중입니다.' })));
    }
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
          : { ok: true, msg: `새 세션을 띄웠습니다(${where}).${summary_id ? (r.injected ? ' 인계를 넣었습니다.' : ' 인계는 넣지 못했습니다.') : ''}` };
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
    if (act === 'wt-preview-off') return run('미리보기 닫기', () => api('DELETE', `/api/sessions/${id}/preview`).then(() => ({ ok: true, msg: '미리보기를 껐습니다.' })));
    if (act === 'wt-merge' || act === 'wt-discard') {
      const w = data.controls.worktree;
      let confirmName = '';
      if (act === 'wt-merge') {
        if (!confirm(`${w.branch}의 커밋 ${w.ahead}개를 ${w.base}에 합칩니다(rebase → fast-forward). 충돌이 나면 되돌리고 멈춥니다. push는 하지 않습니다. 합칠까요?`)) return;
      } else {
        confirmName = prompt(`worktree와 브랜치 ${w.branch}를 지웁니다. 합치지 않은 커밋 ${w.ahead}개${w.dirty.length ? `와 커밋 안 된 변경 ${w.dirty.length}개` : ''}도 사라집니다. 지우려면 이름 "${w.name}"을 적어 주세요.`) || '';
        if (!confirmName) return;
      }
      return run(act === 'wt-merge' ? '합치기' : '버리기', () => post(`/api/sessions/${id}/worktree`, { action: act.slice(3), confirm: confirmName })
        .then((r) => (r.ok ? { ok: true, msg: r.note + (r.schema_unlocked ? ' 스키마 잠금도 풀었습니다.' : '') }
          : { bad: true, msg: r.note + (r.conflict && r.conflict.length ? ` 충돌 파일: ${r.conflict.join(', ')}` : '') })));
    }
    const ACT = { exit: '세션 끝내기', 'exit-after': '세션 끝내기', stop: '일시정지', resume: '다시 시작', interrupt: '작업 중단' };
    const DONE = { exit: '세션을 끝냈습니다.', 'exit-after': '세션을 끝냈습니다.', stop: '일시정지했습니다.', resume: '다시 시작했습니다.', interrupt: '작업을 중단했습니다.' };
    if (ACT[act]) {
      const ask = { exit: '이 세션을 완전히 끝냅니다(/exit). 인계 요약 없이 끝내면 맥락은 기록으로만 남습니다. 끝낼까요?',
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

  return {
    setSession(id) {
      if (id === sid) return;
      sid = id; data = null; mode = null; preview = null; note = null; editDraft = null; promDraft = {}; promId = null; promIn = null;
      el.innerHTML = '';
      clearTimeout(timer);
      if (id != null) load();
    },
    refresh: load,
  };
}
