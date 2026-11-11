import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handButton } from '../../bridge/static/js/foremanchat.js';

// 11-11 교장 계획을 관리자에게 바로(bridge/handover.py) — 카드 단추
test('꺼져 있거나 보내기 방식이면 단추가 없다', () => {
  assert.equal(handButton({ enabled: false }, 'foreman', 'new', false).show, false);
  assert.equal(handButton(null, 'foreman', 'new', false).show, false);
  assert.equal(handButton({ enabled: true, managers: { foreman: 276 } }, 'foreman', 'attach', false).show, false);
});

test('관리자가 있으면 누를 수 있고, 없으면 까닭을 보인다', () => {
  const st = { enabled: true, wait_min: 15, managers: { foreman: 276, runshoes: null } };
  const ok = handButton(st, 'foreman', 'new', false);
  assert.equal(ok.show, true); assert.equal(ok.disabled, false);
  assert.match(ok.tip, /세션 276/); assert.match(ok.tip, /15분/);
  const none = handButton(st, 'runshoes', 'new', false);
  assert.equal(none.disabled, true); assert.match(none.tip, /관리자 세션이 없습니다/);
  assert.equal(handButton(st, 'foreman', 'new', true).disabled, true);
  assert.equal(handButton(st, 'foreman', 'ask', false).disabled, true);
  for (const v of [ok, none]) assert.match(v.tip, /^관리자에게 보내기 — .*니다\.$/);
});
