import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lossGroup } from '../../bridge/static/js/losscheck.js';

const NOW = new Date().toISOString();

test('잃은 것 — 없으면 시작 버튼, 도는 중이면 묶음 진행', () => {
  const none = lossGroup(null, true, null);
  assert.match(none, /data-act="loss-run"(?![^>]*disabled)/);
  assert.ok(none.includes('아직 없습니다'));
  const run = lossGroup({ id: 4, status: 'running', groups_done: 2, groups_total: 5, cost_usd: 0.8, model: 'sonnet', created_at: NOW }, false, null);
  assert.ok(run.includes('도는 중') && run.includes('2/5 진행') && run.includes('0.80달러'));
  assert.match(run, /data-act="loss-run"[^>]*disabled/);                  // 도는 동안 다시 못 누른다
});

test('잃은 것 — 끝나면 사라짐 · 약해짐만, 글은 이스케이프, 문서에 남기기로 넘기기', () => {
  const lc = { id: 4, status: 'done', prompts: 68, counts: { '사라짐': 1, '약해짐': 1, '뒤집힘': 2 }, lost_total: 2, created_at: NOW,
    lost: [{ id: '구간0-1-a', kind: '금지', status: '사라짐', gist: '<b>ttyd</b> 밖에 열지 않음', quote: '열지 마', where: 'repo:README.md', dropped_at: 'summary_00' },
           { id: '구간2-3-b', kind: '기준', status: '약해짐', gist: '조용한 고장', missing: '이유', where: '' }] };
  const h = lossGroup(lc, true, null);
  assert.ok(h.includes('사라짐 1 · 약해짐 1') && h.includes('뒤집힘 2'));
  assert.ok(h.includes('&lt;b&gt;ttyd') && !h.includes('<b>ttyd'));
  assert.ok(h.includes('빠진 요약: summary_00') && h.includes('빠진 것: 이유'));
  assert.match(h, /data-act="loss-use"[^>]*data-lc="4"/);
  assert.ok(h.includes('뒤집힌) 결정이 섞일 수 있습니다'));                    // 사람이 마지막 관문이라는 안내
  assert.ok(lossGroup({ ...lc, lost_total: 0, lost: [] }, true, null).indexOf('loss-use') < 0);
  assert.ok(lossGroup({ id: 5, status: 'failed', error: '압축된 적이 없습니다', created_at: NOW }, true, null).includes('압축된 적이 없습니다'));
});
