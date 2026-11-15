import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gripDrag } from '../../bridge/static/js/grip.js';

test('처음 누른 지점과의 차이로 잡는다(위로 끌면 커진다)', () => {
  const st = { y0: 500, h0: 100 };
  assert.equal(gripDrag(st, 450, 40, 300).h, 150);
  assert.equal(gripDrag(st, 530, 40, 300).h, 70);
});

test('글씨 배율로 나눈다', () => {
  assert.equal(gripDrag({ y0: 500, h0: 100 }, 450, 40, 300, 0.9).h, 100 + 50 / 0.9);
});

test('위 끝을 넘겨 더 끈 뒤 되돌리면 바로 따라온다', () => {
  let st = { y0: 500, h0: 100 };
  let r = gripDrag(st, 250, 40, 300);   // 200 이 닿는 곳(y 300)을 넘겨 더 끌었다
  assert.equal(r.h, 300);
  st = r.st;
  r = gripDrag(st, 100, 40, 300);       // 한참 더 끌었다
  assert.equal(r.h, 300);
  st = r.st;
  r = gripDrag(st, 110, 40, 300);       // 10px만 되돌려도 10px 줄어든다
  assert.equal(r.h, 290);
});

test('아래 끝도 같다', () => {
  let st = { y0: 500, h0: 100 };
  let r = gripDrag(st, 700, 40, 300);   // 최소 40
  assert.equal(r.h, 40);
  st = r.st;
  r = gripDrag(st, 900, 40, 300);
  assert.equal(r.h, 40);
  r = gripDrag(r.st, 880, 40, 300);
  assert.equal(r.h, 60);
});

test('원래 낮은 창(위 끝이 처음 높이)은 줄이는 것만 된다', () => {
  let r = gripDrag({ y0: 500, h0: 60 }, 400, 40, 60);
  assert.equal(r.h, 60);
  r = gripDrag(r.st, 420, 40, 60);
  assert.equal(r.h, 40);
});
