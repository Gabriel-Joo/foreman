// 합치기 기다림(11-11) — 머리 위 말풍선 우선순위 · 승인 막대용 정렬
import test from 'node:test';
import assert from 'node:assert/strict';
import { needMark, mergeWaits } from '../../bridge/static/js/render.js';

const MW = { since: '2026-11-11T10:00:00Z', head8: 'abcd1234', files: 2, asks: false };

test('합치기 기다림 — 보라 톤, 보고 옴보다 위', () => {
  const m = needMark({ state: 'IDLE', merge_wait: MW, report: { event_id: 1 } });
  assert.equal(m.text, '합치기 기다림');
  assert.equal(m.tone, 'merge');
  assert.match(m.tip, /^합치기 기다림 — /);
});

test('겹침 기준 — 권한 거부 > 답 기다림 > 합치기 기다림 > 보고 옴', () => {
  const all = { state: 'IDLE', merge_wait: MW, report: { event_id: 1 }, asks: {}, denied: { tool: 'Bash' } };
  assert.equal(needMark(all).text, '권한 거부');
  const { denied, ...noDenied } = all;
  assert.equal(needMark(noDenied).text, '답 기다림');
  const { asks, ...noAsks } = noDenied;
  assert.equal(needMark(noAsks).text, '합치기 기다림');
  const { merge_wait, ...noMerge } = noAsks;
  assert.equal(needMark(noMerge).text, '보고 옴');
});

test('카드가 치워지면(merge_wait 없음) 말풍선도 사라지고, 끝난 세션에는 안 뜬다', () => {
  assert.equal(needMark({ state: 'IDLE', merge_wait: null }), null);
  assert.equal(needMark({ state: 'DORMANT', merge_wait: MW }), null);
});

test('mergeWaits — 가장 오래된 카드부터, 없으면 빈 목록(막대에 아무것도 안 보인다)', () => {
  const ss = [
    { id: 3, merge_wait: { ...MW, since: '2026-11-11T12:00:00Z' } },
    { id: 1, merge_wait: null },
    { id: 2, merge_wait: { ...MW, since: '2026-11-11T09:00:00Z' } },
    { id: 4 },
  ];
  assert.deepEqual(mergeWaits(ss).map((s) => s.id), [2, 3]);
  assert.deepEqual(mergeWaits([{ id: 1 }, { id: 2, merge_wait: null }]), []);
  assert.deepEqual(mergeWaits([]), []);
});

test('시연 장면 merge_wait — 막대 3건 · 가장 오래된 981 · 머리 위 셋의 기준', async () => {
  const { readFileSync } = await import('node:fs');
  const d = JSON.parse(readFileSync(new URL('../../bridge/static/demo/merge_wait.json', import.meta.url), 'utf8'));
  const ss = d.snapshot.projects.flatMap((p) => p.sessions).map((s) => ({ ...s, merge_wait: s.merge_wait && { ...s.merge_wait, since: 2e12 + Number(String(s.merge_wait.since).slice(1)) } }));
  assert.equal(mergeWaits(ss).length, 3);
  assert.equal(mergeWaits(ss)[0].id, 981);
  assert.deepEqual(ss.map((s) => needMark(s).text), ['합치기 기다림', '답 기다림', '합치기 기다림']);
});
