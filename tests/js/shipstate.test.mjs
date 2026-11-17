// 출하 라인 Harbor 칸(11-17) — Jenkins가 push 앞 단계에서 실패했는데 Harbor 칸이 ✓로 보이던 것
import test from 'node:test';
import assert from 'node:assert/strict';
import { harborStatus } from '../../bridge/static/js/shipstate.js';

const J = (status, step, extra = {}) => ({ jenkins: { status, step, ...extra } });

test('push 앞 단계(태그 · 시험)에서 실패하면 Harbor 칸은 성공이 아니다', () => {
  assert.equal(harborStatus(J('failed', '태그')), 'none');
  assert.equal(harborStatus(J('failed', 'Test')), 'none');
  assert.equal(harborStatus(J('failed', '시험')), 'none');
});

test('모르는 단계나 단계 이름이 없는 실패도 이미지가 올라갔다고 하지 않는다', () => {
  assert.equal(harborStatus(J('failed', '처음 보는 단계')), 'none');
  assert.equal(harborStatus(J('failed', null)), 'none');
  assert.equal(harborStatus(J('failed')), 'none');
});

test('빌드·push에서 실패하면 Harbor 칸도 실패', () => {
  assert.equal(harborStatus(J('failed', '빌드·push')), 'failed');
});

test('push 뒤 단계(매니페스트 태그)에서 실패하면 이미지는 올라갔으니 성공', () => {
  assert.equal(harborStatus(J('failed', '매니페스트 태그')), 'success');
});

test('Jenkins가 진행 중이거나 성공이면 그대로 따른다', () => {
  assert.equal(harborStatus(J('running', '빌드·push')), 'running');
  assert.equal(harborStatus(J('success', null)), 'success');
});

test('문서만 바뀐 빌드는 이미지 없음(정상)', () => {
  assert.equal(harborStatus(J('success', null, { skipped: true })), 'none');
});

test('Harbor가 직접 알려 온 상태가 있으면 그것이 먼저', () => {
  assert.equal(harborStatus({ ...J('failed', '태그'), harbor: { status: 'success' } }), 'success');
});

test('빌드 기록이 없으면 none', () => {
  assert.equal(harborStatus({}), 'none');
  assert.equal(harborStatus(null), 'none');
});
