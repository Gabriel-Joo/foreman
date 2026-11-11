// 새 세션으로 옮기기 — 한 흐름(11-11 C 2물결 「일곱」, config/handoff.toml [move] one_flow).
// 옛 흐름은 사람이 일곱 번 끼어들었다: [압축으로 잊은 것 찾기] → [목록 뽑기] → [같이 넣을 것 고르기] → 승인 → [승인한 것 쓰기] →
// 위로 올라가 [새 세션으로 옮기기] → 요약 확인 → 폴더 · 역할. 사람이 진짜 판단할 것은 「무엇을 문서에 넣을지 고르기」 하나다.
// 이 흐름은 단추 하나로 시작해 그 고르기에서만 멈추고, 나머지는 서버 상태를 보고 저절로 다음으로 간다.
//   ① 잊은 것 찾기(losscheck) → ② 문서 후보 목록(promote, ①의 결과를 같이 넣음) → ③ 사람이 고르기 → ④ 문서에 쓰기 →
//   ⑤ 요약 → ⑥ 새 세션(요약 확인 창 없음 — 넘어간 글은 새 세션 패널에) → ⑦ 옛 세션 끝내기
// 어디까지 왔는지는 이 브라우저에 세션마다 기억한다(handoff.js flowPut — 새로 고쳐도 이어진다). 패널을 닫으면 멈췄다가 다시 열면 이어 간다.
// 한 단계가 STALL_MS 넘게 그대로면 「멈춘 것 같습니다」를 보이고 [다시 시도] · [멈추기]를 준다(조용히 서 있지 않게).

export const MOVE_STEPS = ['잊은 것 찾기', '문서 후보 목록', '문서에 넣을 것 고르기', '문서에 쓰기', '요약', '새 세션', '옛 세션 끝내기'];
export const MOVE_TIP = '새 세션으로 옮기기 — 압축으로 잊은 것을 찾고, 문서에 넣을 후보를 보여 드립니다. 고르시면 문서에 쓰고 요약해 같은 자리에 새 세션을 띄운 뒤 이 세션을 끝냅니다. 사람이 하는 것은 고르기 하나입니다.';
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
    ? { i, bad: true, stalled: true, msg: `${msg} — ${Math.round((now - flow.at) / 60000)}분째 그대로입니다. 멈춘 것 같습니다.` } : { i, busy: true, msg });
  if (flow.stage === 'find') {
    const lc = byId(data && data.losschecks, flow.lcId);
    if (!lc || lc.status === 'running') return stall(0, lc ? `잊은 것을 찾는 중입니다 ${lc.groups_done || 0}/${lc.groups_total || '?'}` : '잊은 것 찾기를 시작하는 중입니다');
    return { i: 1, auto: 'promote', lost: lc.status === 'done' ? lc.lost_total || 0 : null, lcFailed: lc.status !== 'done' };
  }
  if (flow.stage === 'list') {
    if (!flow.promId) return { i: 1, auto: 'promote' };
    const p = byId(data && data.promotions, flow.promId);
    if (!p || p.status === 'requested') return stall(1, '세션이 문서에 넣을 후보를 고르는 중입니다');
    if (p.status === 'failed' || p.status === 'timeout') return { i: 1, bad: true, msg: `문서 후보 목록을 받지 못했습니다 — ${p.error || p.status}` };
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
    if (p.status === 'write_failed') return { i: 2, wait: true, p, msg: `문서에 쓴 것을 확인하지 못했습니다 — ${p.error || '아래 문제를 봐 주세요'}` };
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

// 고르기 칸 — 항목마다 「넣기」 체크(승인) 하나. 고친 값은 promote.js merged와 같은 draft에 둔다
export function chooseCount(items, draft) {
  let on = 0;
  for (const it of items || []) {
    const d = (draft && draft[it.id]) || {};
    if ((d.state ?? it.state) === 'approved') on += 1;
  }
  return on;
}

// [고른 것을 문서에 쓰고 옮기기] 단추 글 — 고른 것이 없으면 쓰지 않고 바로 옮긴다
export function writeLabel(n) {
  return n ? `고른 ${n}개를 문서에 쓰고 옮기기` : '문서에 넣지 않고 옮기기';
}
