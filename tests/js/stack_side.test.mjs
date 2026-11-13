// 머리 위 옆 붙이기는 위가 정말 막혔을 때만(11-13 사용자 「위에 자리가 있으면 위로 쌓는다. 옆으로 비키는 것은 정말 자리가 없을 때만」).
// 전에는 한 줄 쌓기가 복도로 조금 나가기만 해도(soft) 옆 붙이기가 이겼다(코더 348 「관리자에게 보고함」 옆에 「뒤에서 도는 일」)
import test from 'node:test';
import assert from 'node:assert/strict';
import { stackCandidates, pickStack, overTop, stackCover, freeColumn, isSide, SIDE, RAISE } from '../../bridge/static/js/overhead.js';

const T1 = { w: 40, h: 6 }, A1 = { w: 8, h: 7 };
const sized = (k) => (k === 'dot' ? { texts: [{ w: 6, h: 6 }], acts: [{ w: 4, h: 4 }] } : { texts: [{ w: T1.w * k, h: T1.h * k }], acts: [{ w: A1.w * k, h: A1.h * k }] });
const x = 500, base = 200;

test('위로 복도에 나가기만 하면(soft) 한 줄로 쌓는다 — 옆으로 안 간다', () => {
  // 선 칸 위 끝이 머리 바로 위 8px — 한 줄(13px)이면 동작 카드가 복도로 나가고, 옆 붙이기면 안 나간다
  const top = base - 8;
  const cands = stackCandidates(sized, x, base, { reach: 4, raise: 40 });
  const best = pickStack(cands, { soft: (rs) => overTop(rs, top) });
  assert.equal(best.shape, 'column');
  assert.ok(best.soft > 0);                                 // 복도로 나갔지만(빈 바닥 — 허용)
  assert.equal(freeColumn(cands, { soft: (rs) => overTop(rs, top) }, 1).shape, 'column');
});

test('위 방으로 넘치면(room) 옆에 붙인다 — 정말 자리가 없을 때', () => {
  const roomTop = base - 8;                                 // 복도 없이 바로 위 방
  const tiers = { room: (rs) => overTop(rs, roomTop) };
  const cands = stackCandidates(sized, x, base, { reach: 4, raise: 40 });
  const best = pickStack(cands, tiers);
  assert.ok(isSide(best.shape));
  assert.equal(best.room, 0);
  assert.equal(freeColumn(cands, tiers, best.k), null);    // 위에 자리가 없었다 — 점검(⑥)에 안 걸린다
});

test('위가 덮이면(cover) 옆, 위가 비어 있으면 한 줄', () => {
  const cands = stackCandidates(sized, x, base, { reach: 4, raise: 0 });
  const above = [[x - 30, base - 30, 60, 21]];              // 머리 위 9px 위부터 사람 몸 — 한 줄은 0.85배(12px)로 줄여도 안 들고 옆(7px)은 든다
  let best = pickStack(cands, { cover: (rs) => stackCover(rs, { boxes: above }) });
  assert.ok(isSide(best.shape)); assert.equal(best.cover, 0);
  best = pickStack(cands, { cover: (rs) => stackCover(rs, { boxes: [] }) });
  assert.equal(best.shape, 'column');
});

test('들어 올림이 옆 붙이기보다 싸면 위로 들어 올린다', () => {
  // 머리 바로 위 칸에 이름표(spot) — 올리면 피한다. 올림 값(dy × RAISE)이 SIDE보다 작다
  const tag = [[x - 25, base - 6, 50, 6]];
  const cands = stackCandidates(sized, x, base, { reach: 4, raise: 40, lifts: [7] });
  const best = pickStack(cands, { spot: (rs) => stackCover(rs, { boxes: tag }) });
  assert.equal(best.shape, 'column');
  assert.ok(best.dy > 0 && best.dy * RAISE < SIDE);
});
