// 새 세션으로 옮기기 — 한 흐름(11-11 C 2물결 「일곱」, config/handoff.toml [move] one_flow).
// 옛 흐름은 사람이 일곱 번 끼어들었다: [압축으로 잊은 것 찾기] → [목록 뽑기] → [같이 넣을 것 고르기] → 승인 → [승인한 것 쓰기] →
// 위로 올라가 [새 세션으로 옮기기] → 요약 확인 → 폴더 · 역할. 사람이 진짜 판단할 것은 「무엇을 문서에 넣을지 고르기」 하나다.
// 이 흐름은 단추 하나로 시작해 그 고르기에서만 멈추고, 나머지는 서버 상태를 보고 저절로 다음으로 간다.
//   ① 잊은 것 찾기(losscheck) → ② 문서 후보 목록(promote, ①의 결과를 같이 넣음) → ③ 사람이 고르기 → ④ 문서에 쓰기 →
//   ⑤ 요약 → ⑥ 새 세션(요약 확인 창 없음 — 넘어간 글은 새 세션 패널에) → ⑦ 옛 세션 끝내기
// 어디까지 왔는지는 이 브라우저에 세션마다 기억한다(handoff.js flowPut — 새로 고쳐도 이어진다). 패널을 닫으면 멈췄다가 다시 열면 이어 간다.
// 한 단계가 STALL_MS 넘게 그대로면 「멈춘 것 같습니다」를 보이고 [다시 시도] · [멈추기]를 준다(조용히 서 있지 않게).

export const MOVE_STEPS = ['잊은 것 찾기', '문서 후보 목록', '문서에 넣을 것 고르기', '문서에 쓰기', '요약', '새 세션', '옛 세션 끝내기'];
// 11-14 사용자 — 무엇을 하는지가 먼저(전: 「압축으로 잊은 것을 찾고, … 사람이 하는 것은 고르기 하나입니다.」)
export const MOVE_TIP = '새 세션으로 옮기기 — 지금 세션을 끝내고 같은 자리에 새 세션을 띄웁니다. 잊은 것을 찾아 문서에 넣을 후보를 보여드리니 고르기만 하면 됩니다.';
export const STALL_MS = 10 * 60 * 1000;

const byId = (xs, id) => (xs || []).find((x) => x.id === id) || null;

// 지금 단계 — flow(이 브라우저에 기억한 것)와 서버 데이터로 정한다. 순수 함수(시험).
// 돌려주는 것: { i: MOVE_STEPS 번호, busy?, wait?(사람 차례), auto?(저절로 할 일), bad?, msg?, done? }
//   auto: 'promote'(②를 요청) · 'summary'(⑤를 요청) · 'spawn'(⑥ 띄우고 ⑦ 끝내기) · 'skip-write'(④ 건너뜀 → ⑤)
export function moveStep(flow, data, now = Date.now()) {
  if (!flow || flow.v !== 2) return null;
  if (flow.phase === 'done') return { i: 7, done: true };
  if (flow.phase === 'spawning') return { i: 5, busy: true };
  if (flow.phase === 'ending') return { i: 6, busy: true };
  if (flow.err) return { i: flow.errAt ?? 0, bad: true, msg: flow.err };
  const stall = (i, msg) => (flow.at && now - flow.at > STALL_MS
    ? { i, bad: true, stalled: true, msg: `${msg}. ${Math.round((now - flow.at) / 60000)}분째 그대로입니다. 멈춘 것 같습니다.` } : { i, busy: true, msg });
  if (flow.stage === 'find') {
    const lc = byId(data && data.losschecks, flow.lcId);
    if (!lc || lc.status === 'running') return stall(0, lc ? `잊은 것을 찾는 중입니다 ${lc.groups_done || 0}/${lc.groups_total || '?'}` : '잊은 것 찾기를 시작하는 중입니다');
    const out = lossOutcome(lc);
    return { i: 1, auto: 'promote', lost: lc.status === 'done' ? lc.lost_total || 0 : null, lcFailed: out === 'failed', lcNote: lossNote(lc) };
  }
  if (flow.stage === 'list') {
    if (!flow.promId) return { i: 1, auto: 'promote' };
    const p = byId(data && data.promotions, flow.promId);
    if (!p || p.status === 'requested') return stall(1, '세션이 문서에 넣을 후보를 고르는 중입니다');
    if (p.status === 'failed' || p.status === 'timeout') return { i: 1, bad: true, msg: `문서 후보 목록을 받지 못했습니다. ${p.error || p.status}` };
    if (p.status === 'listed' || p.status === 'write_failed') {
      if (!(p.items || []).length) return { i: 4, auto: 'summary', note: '세션이 문서에 넣을 것이 없다고 했습니다.' };
      return { i: 2, wait: true, p };
    }
    if (p.status === 'writing') return stall(3, '세션이 고른 것을 문서에 쓰는 중입니다');
    if (p.status === 'written') return { i: 4, auto: 'summary' };
    return { i: 1, bad: true, msg: `모르는 상태입니다(${p.status})` };
  }
  if (flow.stage === 'write') {
    const p = byId(data && data.promotions, flow.promId);
    if (!p || p.status === 'writing') return stall(3, '세션이 고른 것을 문서에 쓰는 중입니다');
    if (p.status === 'write_failed') return { i: 2, wait: true, p, msg: `문서에 쓴 것을 확인하지 못했습니다. ${p.error || '아래 문제를 봐 주세요'}` };
    if (p.status === 'written') return { i: 4, auto: 'summary' };
    return { i: 3, bad: true, msg: `모르는 상태입니다(${p.status})` };
  }
  if (flow.stage === 'summary') {
    if (!flow.sumId) return { i: 4, auto: 'summary' };
    const s = byId(data && data.summaries, flow.sumId);
    if (!s || s.status === 'requested') return stall(4, '세션이 옮길 요약을 쓰는 중입니다');
    if (s.status !== 'ok') return { i: 4, bad: true, msg: s.error || '요약을 받지 못했습니다' };
    if (s.injected_at) return data && data.controls && data.controls.live ? { i: 6 } : { i: 7, done: true };
    return { i: 5, auto: 'spawn' };
  }
  return { i: 0, bad: true, msg: '모르는 단계입니다' };
}

// 잊은 것 찾기 결과 — 서버 outcome(bridge/losscheck.py outcome, 11-13). 옛 서버 응답(outcome 없음)은 여기서 맞춘다
export function lossOutcome(lc) {
  if (!lc) return null;
  if (lc.outcome) return lc.outcome;
  if (lc.status === 'running') return 'running';
  if (lc.status === 'nothing' || (lc.status === 'failed' && /^압축된 적이 없습니다/.test(lc.error || ''))) return 'nothing';
  if (lc.status !== 'done') return 'failed';
  if (lc.error) return 'partial';
  return lc.lost_total ? 'found' : 'clean';
}

// 흐름 위에 남길 한 줄 — 「없음」과 「실패」를 다른 글 · 다른 색으로(11-13 사용자 — 실패가 조용히 「없음」으로 보이면 안 된다)
export function lossNote(lc) {
  const o = lossOutcome(lc);
  const why = lc && lc.error ? `(${lc.error})` : '';
  if (o === 'found') return { tone: 'ok', msg: `잊은 것 찾기: 잊은 것 ${lc.lost_total}개를 찾아 문서 후보를 물을 때 같이 넣었습니다.` };
  if (o === 'clean') return { tone: 'ok', msg: '잊은 것 찾기: 끝까지 찾았고 잊은 것이 없습니다.' };
  if (o === 'nothing') return { tone: 'muted', msg: '잊은 것 없음' };   // 11-14 사용자 — 줄은 남기고 글만 짧게
  if (o === 'partial') return { tone: 'warn', msg: `잊은 것 찾기가 일부만 끝났습니다${why}. ${lc.lost_total ? `찾은 ${lc.lost_total}개만 같이 넣었습니다` : '찾은 것은 없지만 「없음」은 아닙니다'}. 흐름은 그대로 이어 갑니다. 다시 찾으려면 [멈추기]를 누른 뒤 [세션 정리] 탭 「옮기기 전 정리」에서 찾습니다.` };
  if (o === 'failed') return { tone: 'bad', msg: `잊은 것 찾기가 실패했습니다${why}. 그 결과 없이 문서 후보를 물었습니다.` };
  return null;
}

// 고를 수 있는 후보 — 목적지 확인에 걸렸거나 세션이 「버림」을 권한 것은 여기서 못 고른다(「옮기기 전 정리」에서 목적지를 고친다)
export function selectable(it) {
  return (it.check || {}).ok !== false && it.dest !== 'drop';
}

// 고르기 칸 — 항목마다 「넣기」 체크(승인) 하나. 고친 값은 promote.js merged와 같은 draft에 둔다.
// 세는 것 · 체크 표시 · 실제 쓰는 것이 같아야 한다(11-13 — 「고른 1개를」인데 여럿 고른 일). 셋 다 chosen()을 본다
export function chosen(it, draft) {
  if (!selectable(it)) return false;
  const d = (draft && draft[it.id]) || {};
  return (d.state ?? it.state) === 'approved';
}
export function chooseCount(items, draft) {
  return (items || []).filter((it) => chosen(it, draft)).length;
}
// [전부 고르기] · [전부 풀기] — 고를 수 있는 것만 바꾼 새 draft
export function chooseAll(items, draft, on) {
  const out = { ...(draft || {}) };
  for (const it of items || []) if (selectable(it)) out[it.id] = { ...(out[it.id] || {}), state: on ? 'approved' : 'dropped' };
  return out;
}
// 쓰기 전에 — 화면에 체크가 없는데 서버 값이 승인인 것(고를 수 없는 후보)을 빼서, 쓰는 것이 화면과 같게
export function chooseFinal(items, draft) {
  const out = { ...(draft || {}) };
  for (const it of items || []) {
    const d = out[it.id] || {};
    if (!selectable(it) && (d.state ?? it.state) === 'approved') out[it.id] = { ...d, state: 'dropped' };
  }
  return out;
}

// 새 세션에 넣을 요약 id(11-15 관리자 410) — [고치기]는 옛 판을 두고 parent_id를 단 새 판으로 저장한다(PUT /api/summaries/{id}).
// 흐름은 처음 잡은 id(flow.sumId)를 들고 있어, 고친 본을 저장해도 [다시 시도]가 옛 판을 보내 같은 「읽을 곳이 틀렸습니다」가 났다.
// 그 판에서 이어 고친 판 중 가장 새 것(저장이 끝난 것만)을 따라간다. 고친 적이 없으면 그대로. 순수 함수(시험)
export function retrySummaryId(summaries, id) {
  let cur = id;
  for (;;) {
    const kids = (summaries || []).filter((s) => s.parent_id === cur && s.status === 'ok' && s.id > cur);
    if (!kids.length) return cur;
    cur = Math.max(...kids.map((s) => s.id));
  }
}

// [고른 것을 문서에 쓰고 옮기기] 단추 글 — 고른 것이 없으면 쓰지 않고 바로 옮긴다
export function writeLabel(n) {
  return n ? `고른 ${n}개를 문서에 쓰고 옮기기` : '문서에 넣지 않고 옮기기';
}
