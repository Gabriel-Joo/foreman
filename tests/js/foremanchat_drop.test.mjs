import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dropAction } from '../../bridge/static/js/foremanchat.js';

// 11-10 계획을 못 받은 뒤 [버리기]가 "disp is null"로 실패했다 — 계획이 없으면 서버를 부르지 않고 카드만 치운다
test('버리기: 계획이 없거나 이미 끝난 계획이면 카드만 치움', () => {
  assert.equal(dropAction(null), 'clear');
  assert.equal(dropAction({}), 'clear');
  assert.equal(dropAction({ dispatch_id: 7, plan: {}, status: 'started' }), 'clear');
  assert.equal(dropAction({ dispatch_id: 7, plan: {}, status: 'failed' }), 'clear');
});

test('버리기: 세운 계획(planned)만 서버에 버림을 적음', () => {
  assert.equal(dropAction({ dispatch_id: 7, plan: {} }), 'server');            // 방금 받은 계획(상태 없음 = planned)
  assert.equal(dropAction({ dispatch_id: 0, plan: {}, status: 'planned' }), 'server');
});

test('계획 카드의 display가 hidden을 덮지 않음', () => {
  const css = readFileSync(new URL('../../bridge/static/css/panel.css', import.meta.url), 'utf8');
  assert.match(css, /\.fm-plan\[hidden\]\s*\{\s*display:\s*none/);
});
