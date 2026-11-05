// 걷기(길찾기) 시험 — node --test tests/js/
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildGrid, findPath, clearLine, footprint, nearestFree, RES } from '../../bridge/static/js/walk.js';

const blocked = (g, x, y) => !!g.block[Math.floor(y * RES) * g.cols + Math.floor(x * RES)];
function walkable(g, path, sx, sy) {           // 마지막 걸음(자리로 들어가기) 말고는 모든 선분이 빈칸 위
  let [x, y] = [sx, sy];
  for (let i = 0; i < path.length - 1; i++) {
    const [nx, ny] = path[i];
    if (i > 0 && !clearLine(g, x, y, nx, ny)) return false;
    [x, y] = [nx, ny];
  }
  return true;
}

test('가로막힌 탁자를 돌아간다', () => {
  // 20×12 방, 가운데 탁자(6..14 × 5..7) — 위에서 아래로 곧장 가면 뚫는다
  const g = buildGrid(20, 12, [[6, 5, 8, 2]]);
  const p = findPath(g, 10, 3, 10, 9.5);
  assert.ok(p.length >= 2, '돌아가는 점이 있다');
  assert.ok(walkable(g, p, 10, 3));
  assert.deepEqual(p[p.length - 1], [10, 9.5]);
});

test('뚫리지 않으면 곧장(점 하나)', () => {
  const g = buildGrid(20, 12, [[6, 5, 8, 2]]);
  assert.deepEqual(findPath(g, 3, 3, 3, 9), [[3, 9]]);
});

test('탁자에 붙은 자리 — 앞 빈칸까지 걷고 마지막 걸음만 곧장', () => {
  const g = buildGrid(20, 12, [[6, 5, 8, 2]]);
  const p = findPath(g, 2, 9, 10, 5.3);           // 자리가 탁자 윗변 안쪽
  assert.ok(walkable(g, p, 2, 9));
  assert.deepEqual(p[p.length - 1], [10, 5.3]);
  const before = p[p.length - 2];
  assert.ok(before && !blocked(g, before[0], before[1]), '마지막 앞 점은 빈칸');
});

test('복도가 있으면 복도를 탄다', () => {
  // 가운데 세로 복도(9..11) — 왼쪽 위에서 오른쪽 위로 가는데 벽처럼 가로막은 줄(2..18 × 6..7)에 틈이 복도 자리뿐
  const g = buildGrid(20, 14, [[1, 6, 8, 1], [11, 6, 8, 1]], [[9, 2, 2, 11], [1, 11, 18, 2]]);
  const p = findPath(g, 3, 4, 3, 10);
  assert.ok(walkable(g, p, 3, 4));
  assert.ok(p.some(([x, y]) => x >= 9 && x <= 11 && y > 5 && y < 8), '틈(복도)을 지난다');
});

test('막힌 칸에서 시작해도 빠져나온다', () => {
  const g = buildGrid(20, 12, [[6, 5, 8, 2]]);
  const p = findPath(g, 10, 5.5, 10, 10);
  assert.deepEqual(p[p.length - 1], [10, 10]);
  assert.ok(!blocked(g, p[0][0], p[0][1]), '첫 점은 빈칸');
});

test('가구 바닥 자리 — 낮은 것은 거의 다, 키 큰 것은 아래만', () => {
  assert.deepEqual(footprint({ x: 2, y: 3 }, 2, 1), [2, 3.2, 2, 0.8]);
  const tall = footprint({ x: 0, y: 0 }, 2, 4);
  assert.deepEqual(tall, [0, 2.5, 2, 1.5]);
  assert.equal(footprint({ x: 0, y: 0, block: false }, 1, 1), null);
  assert.deepEqual(footprint({ x: 1, y: 1, foot: [0, 1, 3, 1] }, 3, 3), [1, 2, 3, 1]);
});

test('벽 안쪽만 걷는다', () => {
  const g = buildGrid(10, 10, []);
  assert.ok(blocked(g, 5, 1), '위 벽');
  assert.deepEqual(nearestFree(g, 10, 1), [10, 4]);   // 위 벽 칸 → 벽 바로 아래 빈칸
});
