// 할 일 목록에서 바로 시작(11-11 받은 할 일 #8) — 여럿을 골라 교장 계획 창으로
import test from 'node:test';
import assert from 'node:assert/strict';
import { planText, pickButton } from '../../bridge/static/js/todoinbox.js';

test('고른 할 일을 묶은 글 — 번호와 본문, 겹침 · 이미 된 것은 빼 달라고', () => {
  const t = planText([{ id: 8, body: '목록에서 바로 시작\n둘째 줄' }, { id: 12, body: '  터미널 복사  ' }]);
  assert.match(t, /^받은 할 일 2개를 묶어 계획을/);
  assert.match(t, /겹치거나 이미 된 것은 까닭과 함께 빼고/);
  assert.match(t, /#8\n목록에서 바로 시작\n둘째 줄/);
  assert.match(t, /#12\n터미널 복사$/);
  assert.match(planText([{ id: 3, body: 'x' }]), /^받은 할 일 하나로/);
  assert.equal(planText([]), '');
});

test('[고른 것으로 계획 받기] — 고른 수 · 열 수 없으면 까닭', () => {
  assert.equal(pickButton(0, true).disabled, true);
  const v = pickButton(3, true);
  assert.equal(v.disabled, false);
  assert.equal(v.label, '고른 것으로 계획 받기 (3)');
  assert.match(v.tip, /^고른 것으로 계획 받기 — .*니다\.$/);
  assert.match(pickButton(2, false).tip, /열 수 없습니다/);
});
