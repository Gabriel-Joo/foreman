import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitNotes, autoBlock } from '../../bridge/static/js/fmpanel.js';

// 11-13 — 끝난 일이 교장 노트 「진행 중인 일」로 남아 있었다. 낡은 줄은 따로, 기계가 내린 줄은 되살릴 수 있게 보인다
test('낡음 줄은 따로 가름', () => {
  const { fresh, stale } = splitNotes([
    { id: 1, kind: 'thread', stale: [] },
    { id: 2, kind: 'thread', stale: ['확인 뒤 5일'] },
    { id: 3, kind: 'decision' },
  ]);
  assert.deepEqual(fresh.map((n) => n.id), [1, 3]);
  assert.deepEqual(stale.map((n) => n.id), [2]);
  assert.deepEqual(splitNotes(undefined), { fresh: [], stale: [] });
});

test('끝난 일: 개수 · 까닭 · 되살리기 단추', () => {
  assert.equal(autoBlock('foreman', []), '');
  const h = autoBlock('foreman', [{ id: 994, body: '한국어 훅 <b>', why: '자동: 세션 247 합침', retired_at: '2026-11-13T05:00:00Z' }]);
  assert.match(h, /끝난 일 1/);
  assert.match(h, /data-fm-restore="994"/);
  assert.match(h, /자동: 세션 247 합침/);
  assert.ok(h.includes('한국어 훅 &lt;b&gt;'));                    // 본문은 이스케이프
});
