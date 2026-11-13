// 자리 말풍선의 주인(11-13 사용자 — 「맡길 일」은 코더 자리, 「문서 할 일」은 서기 자리에 늘). 자리에 멈춰 선 사람이 있으면 그 사람
// 덩어리에 보태고, 없으면 자리의 보이지 않는 몸 위에(office.js prepareStacks). 실제 화면은 tools/screen.py stackAudit ⑤
import test from 'node:test';
import assert from 'node:assert/strict';
import { seatHost } from '../../bridge/static/js/overhead.js';

const seat = { room: 'foreman', x: 10, y: 5 };
const at = (key, x, y, o = {}) => ({ key, room: 'foreman', x, y, moving: false, kind: 'session', ...o });

test('자리에 아무도 없으면 주인 없음(코더 0 · 모두 책상)', () => {
  assert.equal(seatHost([], seat, 0.5, 0), null);
  assert.equal(seatHost([at('s:1', 14, 9), at('s:2', 16, 9), at('s:3', 18, 9)], seat, 0.5, 0), null);
});

test('자리에 멈춰 선 사람이 주인 — 쉬는 코더 · 쓰기 자리의 서기 세션', () => {
  assert.equal(seatHost([at('k:foreman', 10, 5, { kind: 'coder' })], seat, 0.5, 0).key, 'k:foreman');
  assert.equal(seatHost([at('s:9', 10.2, 5.1, { kind: 'session' })], seat, 0.5, 0).key, 's:9');
});

test('여럿이면 가장 가까운 사람', () => {
  assert.equal(seatHost([at('a', 10.4, 5), at('b', 10.1, 5)], seat, 0.5, 0).key, 'b');
});

test('걷는 사람 · 아직 안 나타난 사람 · 서브에이전트 · 다른 방은 주인이 아님', () => {
  assert.equal(seatHost([at('w', 10, 5, { moving: true })], seat, 0.5, 0), null);
  assert.equal(seatHost([at('b', 10, 5, { bornAt: 1000 })], seat, 0.5, 500), null);
  assert.equal(seatHost([at('b', 10, 5, { bornAt: 1000 })], seat, 0.5, 1500).key, 'b');
  assert.equal(seatHost([at('m', 10, 5, { kind: 'mini' })], seat, 0.5, 0), null);
  assert.equal(seatHost([at('o', 10, 5, { room: 'runshoes' })], seat, 0.5, 0), null);
});
