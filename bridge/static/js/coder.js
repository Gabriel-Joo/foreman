// 코더 상주(11-09 사용자, log/coder_resident_20261109.md) — 방마다 늘 있는 코더를 누르면 패널에 뜨는 창.
// 맡길 일 = "코더에게" 받은 할 일(새로) + 기계로 센 것: 쉬게 한 일(합치기 기다림) · 파이프라인 실패 · 빌드 알림 없음 · 승인 대기 · 권한 거부.
// 받은 할 일 · 쉬게 한 일은 /api/coder/todo(DB), 나머지는 화면이 이미 받는 값(store — 대시보드 · 파이프라인 스냅숏)으로 센다. 새로 판정하지 않는다.
// 받은 할 일 줄을 누르면 [＋ 세션] 창의 감독실 말하기 칸에 그 글을 채운다 — 계획으로 가고, 바로 띄우지 않는다.

import { esc, ago, keep } from './render.js';
import { firstLine } from './todoinbox.js';

export const REST_DAYS = 1;          // 쉬게 한 지 이만큼(일) 지나면 "N일째"를 붙인다 — 잊히지 않게

// 코더 세션 — 서기 · 점검 · CI/CD가 아닌 것(역할 없음 = 코더, 0017)
export const isCoder = (s) => !s.role || s.role === 'coder';

// 맡길 일 목록(순수) — room 이름, data = /api/coder/todo의 그 방 값, st = store.state 모양({sessions, approvals, pipeline}: Map)
export function coderJobs(room, data, st) {
  const out = [];
  for (const x of (data && data.inbox) || []) out.push({ kind: 'inbox', id: x.id, title: firstLine(x.body, 50), body: x.body, at: x.created_at });
  for (const r of (data && data.rested) || []) out.push({ kind: 'rested', sid: r.session_id, title: r.title, branch: r.branch, days: r.days || 0, at: r.rested_at });
  const pp = st && st.pipeline && st.pipeline.get ? st.pipeline.get(room) : null;
  const broke = pp && pp.chains && pp.chains[0] && pp.chains[0].broke;
  if (broke) out.push({ kind: 'pipe', title: `파이프라인 실패 · ${broke}` });
  if (pp && pp.watch && pp.watch.state === 'missing') out.push({ kind: 'build', title: '빌드 알림 없음 — push 뒤 Jenkins 시작 알림이 오지 않았습니다' });
  const live = st && st.sessions ? [...st.sessions.values()].filter((s) => s.project === room && s.state !== 'DORMANT') : [];
  const ids = new Set(live.map((s) => s.id));
  const appr = new Map();
  for (const a of (st && st.approvals ? st.approvals.values() : [])) {
    if (a.status !== 'pending' || !ids.has(a.session_id) || a.tool === 'AskUserQuestion') continue;
    appr.set(a.session_id, (appr.get(a.session_id) || 0) + 1);
  }
  const name = (s) => s.custom_title || s.title || s.cc_name || `세션 ${s.id}`;
  for (const s of live) {
    if (appr.get(s.id)) out.push({ kind: 'appr', sid: s.id, n: appr.get(s.id), title: `승인 대기 ${appr.get(s.id)} — ${name(s)}` });
    if (s.denied) out.push({ kind: 'denied', sid: s.id, title: `권한 거부 — ${name(s)}` });
  }
  return out;
}

// 코더 머리 위 말풍선 글(순수) — 없으면 null. 쉬게 한 일만 있으면 "맡은 일 N — 합치기 기다림", 오래되면 "· N일째"
export function coderBubble(jobs) {
  if (!jobs || !jobs.length) return null;
  const rested = jobs.filter((j) => j.kind === 'rested');
  const days = Math.max(0, ...rested.map((j) => j.days || 0));
  const old = rested.length && days >= REST_DAYS ? ` · ${days}일째` : '';
  if (rested.length === jobs.length) return `맡은 일 ${rested.length} — 합치기 기다림${old}`;
  return `맡길 일 ${jobs.length}${rested.length ? ` · 합치기 기다림 ${rested.length}${old}` : ''}`;
}

const WHY = {
  inbox: '머리줄 [＋ 할 일]에서 코더에게 받은 글입니다. 누르면 계획 창에 채워집니다.',
  rested: '쉬게 한 일 — 커밋하고 세션만 끝냈습니다. 세션을 열어 [이어서] · [합치기] · [버리기]를 고릅니다.',
  pipe: '파이프라인 실패 — 출하 라인(빌드 · 이미지 · 배포)에서 멈췄습니다. 고칠 일을 계획으로 맡깁니다.',
  build: '빌드 알림 없음 — Jenkins를 확인합니다. FOREMAN 밖에서 풉니다.',
  appr: '멈춤 — 승인 대기. 세션을 열어 승인 카드에서 답합니다.',
  denied: '멈춤 — 권한 거부(CC 자체 검사). 세션을 열어 허용하거나 다른 방법을 지시합니다.',
};

export function createCoder(store) {
  let data = null, at = 0, note = null;

  async function load(force = false) {
    if (!force && Date.now() - at < 20000) return data;
    at = Date.now();
    try {
      const r = await fetch('/api/coder/todo', { headers: store.headers() });
      if (r.ok) data = await r.json();
    } catch { /* 못 읽으면 지난 것을 보인다 */ }
    store.touch('panel');
    return data;
  }
  const roomData = (room) => (data && data.projects && data.projects[room]) || null;

  function html(room, label) {
    load();
    const st = store.state;
    const jobs = coderJobs(room, roomData(room), st);
    const live = [...st.sessions.values()].filter((s) => s.project === room && s.state !== 'DORMANT' && isCoder(s)).sort((a, b) => a.id - b.id);
    const name = (s) => s.custom_title || s.title || s.cc_name || `세션 ${s.id}`;
    const row = (j) => {
      const btn = j.kind === 'inbox'
        ? `<button type="button" class="small" data-cd-plan="${j.id}" title="계획으로 — 이 글을 감독실 말하기 칸에 채워 계획 창을 엽니다. 바로 띄우지 않습니다.">계획으로</button>
           <button type="button" class="small ghost" data-cd-drop="${j.id}" title="버리기 — 이 할 일을 맡기지 않습니다. 받은 할 일 목록에 「버림」으로 남습니다.">버리기</button>`
        : j.sid ? `<button type="button" class="small" data-cd-open="${j.sid}" title="세션 열기 — 이 세션의 [세션] 탭을 엽니다.">세션 열기</button>` : '';
      const head = j.kind === 'rested' ? `합치기 기다림 — ${esc(j.title)}${j.days >= REST_DAYS ? ` <span class="warn">${j.days}일째</span>` : ''} <span class="muted">· <code>${esc(j.branch)}</code></span>`
        : j.kind === 'inbox' ? `${esc(j.title)} <span class="muted">· ${ago(j.at)}</span>` : esc(j.title);
      return `<div class="sc-row" data-tip="${esc(WHY[j.kind] || '')}"><div class="small"><b>${head}</b></div><div class="hand-btns">${btn}</div></div>`;
    };
    const jobsHtml = jobs.length ? jobs.map(row).join('') : '<p class="small muted">맡길 일이 없습니다.</p>';
    const liveHtml = live.length ? live.map((s, i) => `<div class="sc-row"><div class="small">${i ? '임시 · ' : '코더 · '}${esc(name(s))} <span class="muted">— ${s.state === 'ACTIVE' ? '작업 중' : '쉼'}</span></div>
        <button type="button" class="small" data-cd-open="${s.id}" title="세션 열기 — 이 세션의 [세션] 탭을 엽니다.">세션 열기</button></div>`).join('')
      : '<p class="small muted">지금 도는 코더 세션이 없습니다. 코더는 자리에서 쉽니다.</p>';
    return `<div class="small muted">${esc(label)} · 코더 — 이 방의 코딩 담당입니다. 새 일은 새 세션으로, 같은 일을 이어 할 때만 그 세션으로 합니다. 둘째 세션부터는 임시 일꾼이 맡고, 세션이 끝나면 사라집니다.</div>
      ${note ? `<div class="small ${note.bad ? 'bad' : 'ok'}">${esc(note.msg)}</div>` : ''}
      <details class="hand"${keep(`coder:${room}:jobs`, true)}><summary title="맡길 일 — 코더에게 받은 할 일과, 브리지가 이미 아는 신호(쉬게 한 일 · 파이프라인 실패 · 빌드 알림 없음 · 승인 대기 · 권한 거부)입니다."><b>맡길 일 ${jobs.length}</b></summary>${jobsHtml}
        <div class="hand-btns"><button type="button" class="small ghost" data-cd-add="1" title="할 일 적기 — 받는 칸을 「코더에게」로 골라 엽니다.">＋ 할 일 적기</button></div></details>
      <details class="hand"${keep(`coder:${room}:live`, true)}><summary title="지금 일 — 이 방에서 도는 코더 세션입니다. 첫 세션은 상주 코더가, 둘째부터는 임시 일꾼이 맡습니다."><b>지금 일 ${live.length}</b></summary>${liveHtml}</details>`;
  }

  async function onClick(ev, room, openSession, openTodo) {
    const o = ev.target.closest('[data-cd-open]'), p = ev.target.closest('[data-cd-plan]'),
      d = ev.target.closest('[data-cd-drop]'), a = ev.target.closest('[data-cd-add]');
    if (!o && !p && !d && !a) return;
    ev.preventDefault();
    if (o) { if (openSession) openSession(Number(o.dataset.cdOpen)); return; }
    if (a) { if (openTodo) openTodo(room, 'coder'); return; }
    if (p) {
      const j = ((roomData(room) || {}).inbox || []).find((x) => String(x.id) === p.dataset.cdPlan);
      if (!j) return;
      if (window.foremanChat && window.foremanChat.openWith) window.foremanChat.openWith(room, j.body, j.id);
      else { note = { bad: true, msg: '계획 창을 열지 못했습니다 — 화면을 새로 고쳐 주세요.' }; store.touch('panel'); }
      return;
    }
    if (d) {
      d.disabled = true;
      const r = await fetch(`/api/scribe/inbox/${d.dataset.cdDrop}/drop`, { method: 'POST', headers: store.headers(true), body: '{}' });
      note = r.ok ? { msg: `받은 할 일 #${d.dataset.cdDrop}을 버렸습니다.` } : { bad: true, msg: `버리지 못했습니다 — HTTP ${r.status}` };
      await load(true);
    }
  }

  return { html, onClick, load, roomData };
}
