// 머리 위 표시 쌓기(11-13 사용자) — 캐릭터 위에 쌓는다. 덮지 않는다. 하나만 떠도 위로(옆 · 발밑으로 비키지 않는다).
// 아래 = 글씨 카드, 위 = 동작 카드. 자리 계산(bridge/static/js/overhead.js)만 — 그리기 · 실제 화면은 tools/screen.py stackAudit
import test from 'node:test';
import assert from 'node:assert/strict';
import { column, side, stackCandidates, pickStack, stackCover, overTop, leapOver, liftsOver, nearBoxes, TIER, DOT, SHRINK } from '../../bridge/static/js/overhead.js';

const T1 = { w: 40, h: 6 }, T2 = { w: 30, h: 6 }, A1 = { w: 8, h: 7 };
const sized = (texts, acts) => (k) => (k === 'dot'
  ? { texts: texts.map(() => ({ w: 6, h: 6 })), acts: acts.map(() => ({ w: 4, h: 4 })) }
  : { texts: texts.map((c) => ({ w: c.w * k, h: c.h * k })), acts: acts.map((c) => ({ w: c.w * k, h: c.h * k })) });
const bottom = (r) => r[1] + r[3];

test('한 줄 쌓기 — 글씨 카드가 머리 바로 위, 동작 카드가 그 위', () => {
  const rs = column([T1, A1], 100, 1);
  assert.deepEqual(rs[0], [-20, 94, 40, 6]);            // 맨 아래 = 글씨, 아래 끝 = base
  assert.equal(bottom(rs[1]), rs[0][1] - 1);           // 동작 카드는 글씨 카드 위(틈 1)
  assert.ok(rs.every((r) => bottom(r) <= 100));        // 머리(base) 아래로 내려가지 않는다
});

test('옆에 붙이기 — 동작 카드를 글씨 카드 옆 같은 높이에, 덩어리는 머리 가운데', () => {
  const rs = side([T1], [A1], 100, 1, 1);
  assert.equal(bottom(rs[1]), 100);                    // 같은 아래 끝(머리 위)
  assert.equal(rs[1][0], rs[0][0] + rs[0][2] + 1);     // 오른쪽에 바로 붙음
  const lo = Math.min(...rs.map((r) => r[0])), hi = Math.max(...rs.map((r) => r[0] + r[2]));
  assert.ok(Math.abs(lo + hi) < 1e-9);                 // 가운데 맞춤
  const ls = side([T1], [A1], 100, -1, 1);
  assert.equal(ls[1][0] + ls[1][2], ls[0][0] - 1);     // 왼쪽
});

test('후보는 모두 머리 위 — 아래(몸 · 발밑) · 옆으로 머리를 벗어난 자리는 없다', () => {
  const x = 500, base = 200, reach = 4;
  const cands = stackCandidates(sized([T1], [A1]), x, base, { reach, raise: 40, lifts: [17] });
  assert.ok(cands.length > 10);
  assert.deepEqual([cands[0].shape, cands[0].k, cands[0].dx, cands[0].dy], ['column', 1, 0, 0]);   // 첫 후보 = 제자리
  for (const c of cands) {
    assert.ok(c.rects.every((r) => bottom(r) <= base + 1e-9), '머리 아래로 내려감');
    const lo = Math.min(...c.rects.map((r) => r[0])), hi = Math.max(...c.rects.map((r) => r[0] + r[2]));
    assert.ok(lo < x + reach && hi > x - reach, '머리 위를 벗어남');
  }
  assert.ok(cands.some((c) => c.dy === 17));           // 막는 칸 바로 위 높이(lifts)
  assert.ok(cands.some((c) => c.shape === 'side-right') && cands.some((c) => c.k === 'dot'));
  // 동작 카드만이면 옆에 붙일 글씨 카드가 없다 — 한 줄만
  assert.ok(stackCandidates(sized([], [A1]), 0, 0).every((c) => c.shape === 'column'));
});

test('고르기 — 막는 것이 없으면 제자리, 있으면 옆으로 조금 · 위로 조금(덮음은 언제나 더 무겁다)', () => {
  const x = 500, base = 200, s = sized([T1], []);
  const cands = stackCandidates(s, x, base, { reach: 4, raise: 30 });
  assert.deepEqual([pickStack(cands, {}).dx, pickStack(cands, {}).dy], [0, 0]);
  // 머리 위 왼쪽에 이웃 몸 — 오른쪽으로 비킨다
  const nb = [[470, 180, 12, 30]];
  const b1 = pickStack(cands, { cover: (rs) => stackCover(rs, { boxes: nb }) });
  assert.equal(b1.cover, 0); assert.ok(b1.dx > 0); assert.equal(b1.dy, 0);
  // 머리 위 전체를 가로지르는 이름표 — 옆으로는 못 피해 그 위로 올린다
  const tag = [[440, 190, 120, 8]];
  const lifts = liftsOver(tag, x, 30, base);
  const b2 = pickStack(stackCandidates(s, x, base, { reach: 4, raise: 30, lifts }), { cover: (rs) => stackCover(rs, { boxes: tag }) });
  assert.equal(b2.cover, 0); assert.ok(bottom(b2.rects[0]) <= 190);
});

test('위 칸(복도)은 피하되 허용, 위 방은 더 무겁게 — 동작 카드를 옆에 붙여 피한다', () => {
  const x = 500, base = 200;
  const cands = stackCandidates(sized([T1], [A1]), x, base, { reach: 4, raise: 30 });
  // 11-13 바로잡음 — 전에는 위 방 끝이 186이라 한 줄(높이 14, 위 끝 186)이 딱 들어갔는데 복도(soft)만으로 옆에 붙인 것을 맞다고 봤다.
  // 옆 붙이기는 위가 정말 막혔을 때만(SIDE, tests/js/stack_side.test.mjs) — 위 방 끝 190이면 한 줄은 0.85배(높이 12)로 줄여도 넘친다
  const tiers = { room: (rs) => overTop(rs, 190), soft: (rs) => overTop(rs, 194) };
  const b = pickStack(cands, tiers);
  assert.match(b.shape, /^side-/);                     // 한 줄(높이 14 · 줄여 12)은 위 방(190)을 넘는다 — 옆에 붙임(높이 7)
  assert.equal(b.room, 0);
});

test('점 — 줄여도 들어갈 틈이 없고 건너뛰어야 하면 머리 바로 위 색 점', () => {
  const x = 500, base = 200;
  const cands = stackCandidates(sized([{ w: 40, h: 10 }], []), x, base, { reach: 4, raise: 60, lifts: [30] });
  const nb = [[470, 180, 60, 12]];                     // 바로 위 줄 이웃(몸) — 머리와 사이 틈 8px: 글씨(10 · 줄여도 8.5)는 안 들고 점(6)은 든다
  const b = pickStack(cands, { cover: (rs) => stackCover(rs, { boxes: nb }), leap: (rs) => leapOver(rs, base, nb) });
  assert.equal(b.k, 'dot'); assert.equal(b.dy, 0); assert.equal(b.cover, 0);
  assert.ok(DOT > SHRINK && TIER.cover > DOT);
});

test('잴 것들', () => {
  assert.equal(overTop([[0, 10, 5, 4]], 12), 10);      // 위로 2 넘침 × 폭 5
  assert.equal(overTop([[0, 10, 5, 4]], null), 0);
  assert.equal(leapOver([[0, 100, 10, 5]], 105.2, [[0, 0, 100, 200]]), 0);   // 들어 올리지 않음
  assert.equal(leapOver([[0, 80, 10, 5]], 100, [[0, 90, 10, 5]]), 50);       // 사이에 낀 넓이
  assert.equal(stackCover([[0, 0, 10, 10]], { view: [5, 0, 100, 100] }), 50); // 보이는 칸 밖(잘림)
  // 둘레만 — 머리 아래(몸 쪽) · 너무 높은 곳 · 옆으로 먼 곳은 뺀다
  assert.deepEqual(nearBoxes([[95, 80, 10, 10], [95, 201, 10, 5], [95, 10, 10, 5], [300, 80, 10, 10]], 100, 50, 200, 150), [[95, 80, 10, 10]]);
});
