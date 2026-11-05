// 인계 · 세션 조작(11-05, docs/11_handoff.md) — 패널의 한 칸. 지금 요약 · 요약하고 끝내기 · 끝내기 · 멈춤 · 되살리기 · 작업 중단 ·
// 죽은 세션 요약 · 압축 요약에서 · 새로 띄우기(넣을 글을 먼저 보여주고 확인받는다) · 요약 고치기 · 이력.
// 자기 데이터(/api/sessions/{id}/handoff)를 따로 받아 따로 그린다 — 세션 칸이 다시 그려져도 고치던 글이 날아가지 않게.

import { esc, ago } from './render.js';

const SOURCE = { self: '세션이 씀', self_headless: '세션이 씀(죽은 세션, claude -p)', compact: '자동 압축 요약에서', edited: '사람이 고침' };
const STATUS = { requested: '기다리는 중…', ok: '저장됨', failed: '실패', timeout: '시간 초과' };
const KIND = { snapshot: '지금 요약', handoff: '끝내기 전 인계' };

export function mountHandoff(el, store, { open: open0 = false, onToggle } = {}) {
  let sid = null, data = null, mode = null, preview = null, note = null, open = open0;
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
    } catch (e) { note = { bad: true, msg: `불러오지 못함 — ${e.message}` }; }
    draw();
    schedule();
  }
  function schedule() {
    clearTimeout(timer);
    if (sid == null) return;
    const pending = data && (data.controls.pending_req || (data.summaries[0] && data.summaries[0].status === 'requested'));
    timer = setTimeout(load, pending ? 3000 : 15000);
  }
  async function run(label, fn) {
    note = { msg: `${label}…` }; draw();
    try { const r = await fn(); note = r && r.msg ? r : { ok: true, msg: `${label} — 됨` }; }
    catch (e) { note = { bad: true, msg: `${label} — ${e.message}` }; }
    await load();
  }

  const latest = () => (data ? data.summaries.find((x) => x.status === 'ok') : null);

  function draw() {
    if (sid == null || !data) { el.innerHTML = ''; return; }
    const c = data.controls, can = c.can, s0 = data.summaries[0], ok = latest();
    const b = (act, label, on, cls = '') => `<button data-act="${act}" class="small ${cls}"${on ? '' : ' disabled'}>${label}</button>`;
    const sumCard = (x) => !x ? '<p class="small muted">아직 인계 요약이 없다.</p>' : `
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
      main = `<textarea id="hEdit" rows="14" class="hand-edit">${esc(ok.body)}</textarea>
        <div class="row">${b('edit-save', '고친 본 저장(새 판)', true)}${b('cancel', '취소', true, 'ghost')}</div>`;
    } else if (mode === 'spawn') {
      main = preview ? `<div class="small">새 세션(같은 폴더 · tmux)을 띄우고 아래 글을 첫 입력으로 넣는다${preview.cut ? ` — <span class="warn">길어서 일부 절을 줄였다(전체는 ${esc(preview.full_path)})</span>` : ''}</div>
        <pre class="hand-body">${esc(preview.text)}</pre>
        <div class="row">${b('spawn-go', '이 글을 넣고 시작', true)}${b('spawn-bare', '요약 없이 시작', true, 'ghost')}${b('cancel', '취소', true, 'ghost')}</div>`
        : `<div class="small">넣을 인계 요약이 없다.</div><div class="row">${b('spawn-bare', '요약 없이 새로 띄우기', true)}${b('cancel', '취소', true, 'ghost')}</div>`;
    } else {
      main = sumCard(s0 && s0.status !== 'ok' && ok && s0.id !== ok.id ? s0 : ok || s0) +
        (s0 && ok && s0.id !== ok.id && s0.status !== 'ok' ? `<div class="small muted">이전 저장본 ↓</div>${sumCard(ok)}` : '') +
        (ok && ok.kind === 'handoff' && can.exit && !ok.injected_at ? `<div class="row">${b('exit-after', '이 요약을 확인했다 — 세션 끝내기', true, 'warn')}</div>` : '');
    }
    const hist = data.summaries.length > 1 ? `<details class="hand-hist"><summary class="small muted">이력 ${data.summaries.length}</summary>${
      data.summaries.map((x) => `<div class="small">#${x.id} ${esc(KIND[x.kind] || x.kind)} · ${esc(SOURCE[x.source] || x.source)} · ${esc(STATUS[x.status] || x.status)} · ${ago(x.created_at)}${x.chars ? ` · ${x.chars}자` : ''}</div>`).join('')}</details>` : '';
    el.innerHTML = `
      <details class="hand"${open ? ' open' : ''}><summary><b>인계 · 세션 조작</b> <span class="small muted">${esc(c.why || (c.live ? '살아 있음' : ''))}${s0 ? ` · 요약 ${esc(STATUS[s0.status] || s0.status)} ${ago(s0.created_at)}` : ''}</span></summary>
        <div class="hand-btns">
          ${b('summary', '지금 요약', can.summary)}
          ${b('summary-end', '요약하고 끝내기', can.summary)}
          ${b('spawn', '새로 띄우기', can.spawn)}
          ${b('edit', '고치기', !!ok && mode !== 'edit')}
        </div>
        <div class="hand-btns">
          ${b('exit', '끝내기', can.exit, 'ghost')}
          ${b('stop', '멈춤', can.stop, 'ghost')}
          ${b('resume', '되살리기', can.resume, 'ghost')}
          ${b('interrupt', '작업 중단(Esc)', can.interrupt, 'ghost')}
          ${!c.live ? b('headless', '죽은 세션 요약 받기', can.headless, 'ghost') : ''}
          ${b('compact', '압축 요약에서', can.compact && !c.live, 'ghost')}
        </div>
        ${note ? `<div class="small ${note.bad ? 'bad' : note.ok ? 'ok' : 'muted'}">${esc(note.msg)}</div>` : ''}
        ${main}${hist}
      </details>`;
    el.querySelector('details.hand').addEventListener('toggle', (ev) => { open = ev.target.open; if (onToggle) onToggle(open); });
  }

  el.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('button[data-act]');
    if (!btn || btn.disabled || sid == null) return;
    ev.preventDefault();
    const act = btn.dataset.act, id = sid;
    const post = (u, body) => api('POST', u, body || {});
    if (act === 'cancel') { mode = null; preview = null; draw(); return; }
    if (act === 'summary') return run('요약 요청', () => post(`/api/sessions/${id}/summary`, { kind: 'snapshot', mode: 'live' }).then(() => ({ msg: '요청을 보냈다 — 세션이 쓰는 중' })));
    if (act === 'summary-end') return run('인계 요약 요청', () => post(`/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'live' }).then(() => ({ msg: '요청을 보냈다 — 요약이 오면 확인하고 [세션 끝내기]' })));
    if (act === 'headless') {
      if (!confirm('죽은 세션을 claude -p --resume으로 불러 요약을 받는다. 그 세션의 컨텍스트를 다시 읽어 토큰을 쓴다. 할까?')) return;
      return run('죽은 세션 요약', () => post(`/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'headless' }).then(() => ({ msg: '돌리는 중 — 몇 분 걸릴 수 있다' })));
    }
    if (act === 'compact') return run('압축 요약에서 만들기', () => post(`/api/sessions/${id}/summary`, { kind: 'handoff', mode: 'compact' }));
    if (act === 'edit') { mode = 'edit'; draw(); return; }
    if (act === 'edit-save') {
      const body = el.querySelector('#hEdit').value;
      mode = null;
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
        const where = `tmux ${r.tmux} · 세션 ${(r.cc_session_id || '?').slice(0, 8)}`;
        return r.note ? { bad: !r.cc_session_id, msg: `${where} — ${r.note}` }
          : { ok: true, msg: `${where} 띄움${summary_id ? (r.injected ? ' · 인계 넣음' : ' · 인계 못 넣음') : ''}` };
      });
    }
    const ACT = { exit: '끝내기', 'exit-after': '끝내기', stop: '멈춤', resume: '되살리기', interrupt: '작업 중단' };
    if (ACT[act]) {
      const ask = { exit: '이 세션을 /exit로 끝낸다. 인계 요약 없이 끝내면 맥락은 트랜스크립트에만 남는다. 끝낼까?',
                    'exit-after': '요약을 확인했으면 이 세션을 /exit로 끝낸다. 끝낼까?',
                    stop: '이 세션을 멈춘다(Ctrl+Z). 되살리기 전까지 입력 · hook이 안 된다. 멈출까?' }[act];
      if (ask && !confirm(ask)) return;
      const action = act === 'exit-after' ? 'exit' : act;
      return run(ACT[act], () => post(`/api/sessions/${id}/action`, { action }).then((r) => (r.ok ? { ok: true, msg: `${ACT[act]} — 됨` } : { bad: true, msg: `${ACT[act]} — ${r.note || '확인 안 됨'}` })));
    }
  });

  return {
    setSession(id) {
      if (id === sid) return;
      sid = id; data = null; mode = null; preview = null; note = null;
      el.innerHTML = '';
      clearTimeout(timer);
      if (id != null) load();
    },
    refresh: load,
  };
}
