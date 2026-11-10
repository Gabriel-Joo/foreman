// 터미널 칸 폭 보정(11-10) — xterm 장치 칸 = floor(글자 × dpr) + letterSpacing 이 글자(장치 px 올림)보다 좁지 않게
import test from 'node:test';
import assert from 'node:assert/strict';
import { cellSpacing, STEPS } from '../../bridge/static/js/uiscale.js';

const cell = (g, dpr) => Math.floor(g * dpr + 1e-6) + cellSpacing(g, dpr);

test('사용자가 잰 어긋남 — 13px · 14px · 18px(dpr 0.698)은 1 장치 px를 더한다', () => {
  assert.equal(cellSpacing(7.801, 1), 1);        // 13px: 칸 7 → 8 (글자 7.80)
  assert.equal(cellSpacing(8.401, 1), 1);        // 14px: 칸 8 → 9 (글자 8.40)
  assert.equal(cellSpacing(10.802, 0.698), 1);   // 18px · 브라우저 70%: 장치 7.54 → 칸 8
});

test('0.6em이 정수 픽셀인 크기(10 · 15 · 20px)는 그대로 — 측정 소수 오차에 1을 더하지 않는다', () => {
  for (const g of [6, 9, 12, 6.0000001, 8.9999999]) assert.equal(cellSpacing(g, 1), 0, String(g));
});

test('새 계단의 터미널 글씨(11~15px) × dpr 1 · 0.7에서 칸 ≥ 글자, 1 장치 px 넘게 벌리지 않는다', () => {
  const sizes = [...new Set(STEPS.map((s) => Math.round(14 * s)))];
  assert.deepEqual(sizes, [11, 12, 13, 14, 15]);
  for (const fs of sizes) {
    const g = fs * 0.6001;                     // Liberation Mono 0.6em(헤드리스: 14px → 8.4014)
    for (const dpr of [1, 0.7, 0.698]) {
      assert.ok(cell(g, dpr) >= g * dpr - 0.02, `${fs}px dpr ${dpr}: 칸 ${cell(g, dpr)} < 글자 ${(g * dpr).toFixed(2)}`);
      assert.ok(cellSpacing(g, dpr) <= 1);
    }
  }
  assert.equal(cellSpacing(0, 1), 0);
  assert.equal(cellSpacing(NaN, 1), 0);
});
