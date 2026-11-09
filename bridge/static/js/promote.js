// 인계 2판 ① 문서로 옮기기(11-05, docs/11_handoff_v2.md 2장 ①) — 인계 칸 안의 한 묶음.
// 세션이 낸 "문서에 없는 것" 목록을 사람이 고치고(무엇 · 어디로 · 절) 항목마다 승인 · 빼기를 고른다. 승인한 것만 세션이 쓰고
// 커밋하며, 브리지가 그 커밋을 git으로 확인한다. 고치던 값은 draft에 들고 있어 15초 새로 그리기에 날아가지 않는다.

import { esc, ago, keep } from './render.js';

const STATUS = { requested: '목록 기다리는 중…', listed: '고치고 승인해 주세요', failed: '실패', timeout: '시간 초과',
  writing: '쓰는 중…', written: '썼습니다', write_failed: '확인 실패' };
const STATE = { pending: '대기', approved: '승인', dropped: '빼기' };
const EDITABLE = ['what', 'dest', 'section', 'state'];

// 세션이 낸 값 위에 사람이 고친 값(draft)을 얹는다
export function merged(item, draft) {
  const d = (draft && draft[item.id]) || {};
  const out = { ...item };
  for (const k of EDITABLE) if (d[k] !== undefined) out[k] = d[k];
  if (out.dest === 'drop' && out.state === 'approved') out.state = 'dropped';
  return out;
}

// 저장할 고침 — 세션 값과 다른 칸만
export function edits(items, draft) {
  const out = [];
  for (const it of items) {
    const m = merged(it, draft), e = {};
    for (const k of EDITABLE) if (m[k] !== it[k]) e[k] = m[k];
    if (Object.keys(e).length) out.push({ id: it.id, ...e });
  }
  return out;
}

export function counts(items, draft) {
  const c = { pending: 0, approved: 0, dropped: 0 };
  for (const it of items) c[merged(it, draft).state] += 1;
  return c;
}

function itemRow(it, m, editable) {
  const ck = it.check || {};
  const dis = editable ? '' : ' disabled';
  const mark = !ck.ok ? `<span class="bad">✗ ${esc(ck.problem || '')}</span>` : ck.note ? `<span class="warn">${esc(ck.note)}</span>` : '';
  const changed = m.dest !== it.dest || m.section !== it.section ? ' <span class="muted">(고친 목적지는 저장하면 다시 확인합니다)</span>' : '';
  return `<div class="prom-item prom-${esc(m.state)}" data-pid="${it.id}">
    <div class="small"><select data-f="state"${dis} title="상태 — 승인한 것만 씁니다. 빼기는 쓰지 않습니다.">${
      Object.entries(STATE).map(([k, v]) => `<option value="${k}"${m.state === k ? ' selected' : ''}>${v}</option>`).join('')}</select>
      <b>#${it.id}</b> <span class="muted">${esc(it.kind)}</span>
      어디로 <input data-f="dest" class="prom-dest" value="${esc(m.dest)}"${dis} title="어디로 — 저장소 기준 .md 경로, memory(사람 선호), drop(버림)">
      ${m.dest === 'memory' || m.dest === 'drop' ? '' : `「<input data-f="section" class="prom-sec" value="${esc(m.section || '')}"${dis} title="절 — 그 문서의 절 제목. 없으면 새로 만듭니다.">」`}
      ${mark}${changed}</div>
    <textarea data-f="what" rows="2" class="prom-what"${dis}>${esc(m.what)}</textarea>
    ${it.quote ? `<div class="small muted">원문: “${esc(it.quote)}”</div>` : ''}
    ${it.why ? `<div class="small muted">왜 거기: ${esc(it.why)}</div>` : ''}
  </div>`;
}

// 같이 넣을 인계 고르기 — chosen: null이면 후보가 하나일 때만 그것, 여럿이면 "고르기"(빈 값 — 누르면 막는다),
// 'none'이면 넣지 않음, 숫자면 그 인계. 여럿일 때 첫째를 말없이 고르지 않는다(11-06 첫 사례에서 #6 대신 #7이 들어갔다)
export function inputPick(inputs, chosen) {
  if (!inputs || !inputs.length) return '<span class="small muted">같이 넣을 것 없음</span>';
  const cur = chosen != null ? String(chosen) : inputs.length === 1 ? String(inputs[0].id) : '';
  const opt = (v, label, tip) => `<option value="${v}"${cur === String(v) ? ' selected' : ''}${tip ? ` title="${esc(tip)}"` : ''}>${esc(label)}</option>`;
  return `<select id="promIn" class="small" title="같이 넣을 것 — 옮기기용 요약의 「문서와 다른 지금」 절이나 잃은 것 점검의 사라짐 · 약해짐을 목록 요청에 같이 넣습니다.">${
    inputs.length > 1 ? opt('', `같이 넣을 것 고르기(${inputs.length}개)`) : ''}${
    inputs.map((x) => opt(x.id, x.kind === 'loss' ? `${x.title} — ${x.why}` : `#${x.id} ${x.title || x.cc} — ${x.why}`, x.diff)).join('')}${opt('none', '넣지 않음')}</select>`;
}

// 이 목록에 무엇을 같이 넣었나 — 쓰는 사람이 어느 인계로 뽑았는지 바로 보이게
function inputUsed(p) {
  if (p.summary_id) return ` · 요약 #${esc(String(p.summary_id))} 같이 넣음`;
  if (p.loss_check_id) return ` · 잃은 것 점검 #${esc(String(p.loss_check_id))} 같이 넣음`;
  return ' · 같이 넣은 것 없음';
}

// p = 마지막 옮기기(없으면 null), can = 목록 요청 가능, draft = {id: {칸: 값}}, err = 표를 못 읽은 사유
export function promoteGroup(p, can, draft, err, inputs = [], chosen = null) {
  const b = (act, label, on, cls = '', tip = '') => `<button type="button" data-act="${act}" class="small ${cls}"${tip ? ` title="${esc(tip)}"` : ''}${on ? '' : ' disabled'}>${label}</button>`;
  const head = `<div class="hand-btns">${b('prom-req', '목록 뽑기', can, '', '목록 뽑기 — 이 대화에서 정했지만 아직 문서에 없는 결정 · 금지 · 기준을 세션이 목록으로 냅니다. 이때는 파일을 고치지 않고, 고쳐서 승인한 것만 [승인한 것 쓰기]로 문서에 씁니다.')}
    ${can ? inputPick(inputs, chosen) : ''}
    ${p ? `<span class="small">${esc(STATUS[p.status] || p.status)} · ${ago(p.updated_at || p.created_at)}${inputUsed(p)}</span>` : '<span class="small muted">아직 없습니다.</span>'}</div>`;
  if (err) return wrap(head + `<div class="small bad">${esc(err)}</div>`);
  if (!p) return wrap(head);
  let body = '';
  if (p.error) body += `<div class="small bad">${esc(p.error)}</div>`;
  if (p.raw) body += `<details${keep(`prom:${p.id}:raw`)}><summary class="small muted">응답 원문</summary><pre class="hand-body">${esc(p.raw)}</pre></details>`;
  const items = p.items || [];
  const editable = p.status === 'listed' || p.status === 'write_failed';
  if (items.length) {
    // 버튼은 글칸을 고칠 때 다시 그리지 않으므로 고친 수로 켜고 끄지 않는다 — 쓰기를 누를 때 저장 안 된 고침이 있으면 막는다
    const c = counts(items, draft), saved = counts(items, {});
    body += items.map((it) => itemRow(it, merged(it, draft), editable)).join('');
    if (editable) {
      body += `<div class="hand-btns"><span class="small">승인 ${c.approved} · 대기 ${c.pending} · 빼기 ${c.dropped}${c.approved !== saved.approved ? ' <span class="warn">(저장 전)</span>' : ''}</span>
        ${b('prom-save', '고친 것 저장', true, c.approved !== saved.approved ? 'primary' : '', '고친 것 저장 — 문장 · 목적지 · 상태를 저장합니다. 쓰기 전에 저장해야 합니다.')}
        ${b('prom-write', `승인한 것 쓰기(${saved.approved})`, saved.approved > 0, c.approved === saved.approved ? 'primary' : '', '승인한 것 쓰기 — 세션이 저장된 승인 항목만 문서에 쓰고 「인계 전 결정 기록」으로 커밋합니다. 브리지가 커밋을 확인합니다.')}</div>`;
    }
  } else if (p.status === 'listed') {
    body += '<div class="small muted">세션이 문서에 남길 것이 없다고 했습니다.</div>';
  }
  const r = p.result;
  if (r) {
    body += `<div class="small ${r.ok ? 'ok' : 'bad'}">${r.ok ? '✓ 확인했습니다' : '✗ 확인 실패'}${r.commit ? ` — 커밋 <code>${esc(r.commit.slice(0, 8))}</code>` : ''}${r.files && r.files.length ? ` · ${r.files.map(esc).join(', ')}` : ''}${r.memory && r.memory.length ? ` · 메모리 ${r.memory.length}` : ''}</div>`;
    for (const x of r.problems || []) body += `<div class="small bad">- ${esc(x)}</div>`;
    for (const x of r.skipped || []) body += `<div class="small warn">건너뜀 #${esc(String(x.id))}: ${esc(x.why || '')}</div>`;
  }
  return wrap(head + body);
}

function wrap(inner) {
  return `<div class="hand-item"><div class="hand-item-h"><b>대화에서 정한 것 문서에 적기</b> <span class="small muted">대화에서만 정한 결정 · 금지를 README · docs · CLAUDE.md에 적어 다음 세션이 읽게 합니다. 목록 → 고치고 승인 → 커밋.</span></div>
    <div class="prom">${inner}</div></div>`;
}
