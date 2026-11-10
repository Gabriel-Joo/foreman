// 글씨 배율 범위(11-10 사용자) — 브라우저 100%에서 90%가 기준, 80~110% · 5씩. 모든 곳이 uiscale.js 하나를 쓴다
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { STEPS, DEF, snapScale } from '../../bridge/static/js/uiscale.js';

const read = (p) => readFileSync(new URL(`../../bridge/static/${p}`, import.meta.url), 'utf8');

test('계단은 80~110% · 5씩, 처음 값 90%', () => {
  assert.deepEqual(STEPS, [0.8, 0.85, 0.9, 0.95, 1, 1.05, 1.1]);
  assert.equal(DEF, 0.9);
  assert.ok(STEPS.includes(DEF));
});

test('저장된 값 맞추기 — 없으면 처음 값, 범위 밖 · 계단에 없으면 가까운 계단', () => {
  for (const v of [null, undefined, '', '  ', 'abc', '0', '-1']) assert.equal(snapScale(v), DEF, String(v));
  assert.equal(snapScale('1.2'), 1.1);           // 옛 기본값(브라우저 70%로 볼 때)
  assert.equal(snapScale('1.6'), 1.1);
  assert.equal(snapScale('0.5'), 0.8);
  assert.equal(snapScale('0.9'), 0.9);
  assert.equal(snapScale('0.93'), 0.95);
  assert.equal(snapScale('1.01'), 1);
  for (const s of STEPS) assert.equal(snapScale(String(s)), s);
});

test('CSS 처음 값(--ui-zoom)은 DEF 하나 — 대체값을 곳마다 따로 두지 않는다', () => {
  const files = ['css/panel.css', 'usage.html', 'office.html'];
  for (const f of files) {
    const s = read(f);
    assert.doesNotMatch(s, /var\(--ui-zoom\s*,/, `${f}: var(--ui-zoom, …) 대체값`);
    assert.doesNotMatch(s, /var\(--tz\s*,/, `${f}: var(--tz, …) 대체값`);
  }
  for (const f of ['css/panel.css', 'usage.html']) {
    const m = read(f).match(/--ui-zoom:\s*([\d.]+)/);
    assert.ok(m, `${f}: :root 처음 값`);
    assert.equal(Number(m[1]), DEF, f);
  }
});

test('터미널 글씨 14 × 배율 — 새 계단은 11~15px, 90%는 13px', () => {
  assert.deepEqual([...new Set(STEPS.map((s) => Math.round(14 * s)))], [11, 12, 13, 14, 15]);
  assert.equal(Math.round(14 * DEF), 13);
});
