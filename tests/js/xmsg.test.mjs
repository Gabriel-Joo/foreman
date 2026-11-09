// 세션 간 메시지 줄 꼬리(11-09) — 받는 쪽 트랜스크립트로 본 도착 · 읽음
import test from 'node:test';
import assert from 'node:assert/strict';
import { xmsgText } from '../../bridge/static/js/store.js';

test('읽음 · 작업 중에 읽음 · 안 읽음 · 도착 기록 없음 · 대상 아님', () => {
  const at = '2026-11-09T06:00:00Z';
  assert.match(xmsgText({ arrived_at: at, read_at: at, how: 'prompt', to_label: 'foreman · 인계' }), /^ — ✓ 읽음 .+\(foreman · 인계\)$/);
  assert.match(xmsgText({ arrived_at: at, read_at: at, how: 'mid_turn' }), /작업 중에/);
  assert.match(xmsgText({ arrived_at: at, read_at: null }), /아직 안 읽음/);
  assert.match(xmsgText({ arrived_at: null }), /도착 기록 없음/);
  assert.equal(xmsgText(undefined), '');
  assert.equal(xmsgText({}), '');
});
