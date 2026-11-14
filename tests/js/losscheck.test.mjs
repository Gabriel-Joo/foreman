import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lossGroup } from '../../bridge/static/js/losscheck.js';

const NOW = new Date().toISOString();

test('잃은 것 — 없으면 시작 버튼, 도는 중이면 묶음 진행', () => {
  const none = lossGroup(null, true, null);
  assert.match(none, /data-act="loss-run"(?![^>]*disabled)/);
  assert.ok(none.includes('>아직 없습니다<'));                                 // 11-14 온점 없이
  assert.match(none, /title="압축으로 잊은 것 찾기 — [^"]+"[^>]*>압축으로 잊은 것 찾기</);   // 설명문은 버튼 호버로
  assert.ok(!none.includes('hand-item-h'));
  const run = lossGroup({ id: 4, status: 'running', groups_done: 2, groups_total: 5, cost_usd: 0.8, model: 'sonnet', created_at: NOW }, false, null);
  assert.ok(run.includes('도는 중') && run.includes('2/5 진행') && run.includes('0.80달러'));
  assert.match(run, /data-act="loss-run"[^>]*disabled/);                  // 도는 동안 다시 못 누른다
});

test('잃은 것 — 끝나면 사라짐 · 약해짐만, 글은 이스케이프, 문서에 남기기로 넘기기', () => {
  const lc = { id: 4, status: 'done', prompts: 68, counts: { '사라짐': 1, '약해짐': 1, '뒤집힘': 2 }, lost_total: 2, created_at: NOW,
    lost: [{ id: '구간0-1-a', kind: '금지', status: '사라짐', gist: '<b>ttyd</b> 밖에 열지 않음', quote: '열지 마', where: 'repo:README.md', dropped_at: 'summary_00' },
           { id: '구간2-3-b', kind: '기준', status: '약해짐', gist: '조용한 고장', missing: '이유', where: '' }] };
  const h = lossGroup(lc, true, null);
  assert.ok(/loss-n gone[^>]*>사라짐 1</.test(h) && /loss-n weak[^>]*>약해짐 1</.test(h));   // 사람이 볼 두 수만 크게
  assert.ok(h.includes('그 밖 2개') && h.includes('뒤집힘 2'));                              // 나머지는 호버로
  assert.ok(h.includes('&lt;b&gt;ttyd') && !h.includes('<b>ttyd'));
  assert.ok(h.includes('빠진 요약: summary_00') && h.includes('빠진 것: 이유'));
  assert.match(h, /data-act="loss-use"[^>]*data-lc="4"/);
  assert.ok(h.includes('뒤집힌) 결정이 섞일 수 있습니다'));                    // 사람이 마지막 관문이라는 안내
  assert.ok(lossGroup({ ...lc, lost_total: 0, lost: [] }, true, null).indexOf('loss-use') < 0);
});

test('잃은 것 — 「없음」과 「실패」를 다른 글 · 다른 색으로(11-13 조용한 고장)', () => {
  const ok = [{ error: null, skipped: [] }];
  const clean = lossGroup({ id: 6, status: 'done', outcome: 'clean', prompts: 9, counts: { '살아 있음': 9 }, lost_total: 0, lost: [], runs: ok, created_at: NOW }, true, null);
  assert.ok(clean.includes('잊은 것이 없습니다') && !clean.includes('class="small bad"'));
  const fail = lossGroup({ id: 7, status: 'failed', outcome: 'failed', error: 'TimeoutError', created_at: NOW }, true, null);
  assert.ok(fail.includes('찾기 실패') && fail.includes('class="small bad"') && fail.includes('TimeoutError'));
  assert.ok(!fail.includes('잊은 것이 없습니다'));
  const part = lossGroup({ id: 8, status: 'done', outcome: 'partial', error: '묶음 1개 실패', prompts: 9, counts: {}, lost_total: 0, lost: [], groups_failed: 1, created_at: NOW }, true, null);
  assert.ok(part.includes('일부만') && part.includes('「없음」이 아닙니다') && !part.includes('잊은 것이 없습니다'));
  const none = lossGroup({ id: 9, status: 'nothing', outcome: 'nothing', error: '압축된 적이 없습니다 — 볼 것이 없습니다', created_at: NOW }, true, null);
  assert.ok(none.includes('찾을 것 없음') && !none.includes('찾기 실패'));
  // 11-14 사용자 — 밑의 설명 줄은 「찾을 것 없음」 호버로
  assert.match(none, /title="찾을 것 없음 — 이 세션은 압축된 적이 없어 잊은 것이 생기지 않았습니다\."[^>]*>찾을 것 없음</);
  assert.ok(!/<div[^>]*>찾을 것 없음 —/.test(none));
  // 서버가 outcome을 주지 않던 11-13 전 기록 — 압축 없음은 실패가 아니다
  assert.ok(!lossGroup({ id: 5, status: 'failed', error: '압축된 적이 없습니다 — 볼 것이 없습니다', created_at: NOW }, true, null).includes('찾기 실패'));
});

// 11-14 사용자 — 「찾을 것 없음 · 1분 전 · claude-sonnet-5-5」 → 칸마다 띄우고, 모델은 패널 모델 칩과 같은 배지
test('잃은 것 줄 — 가운뎃점 없이 칸마다, 모델은 이름 배지', () => {
  const h = lossGroup({ id: 9, status: 'nothing', outcome: 'nothing', model: 'claude-sonnet-5-5', created_at: NOW }, true, null);
  assert.match(h, /<span class="mdl f-sonnet"[^>]*>Sonnet 5\.5<\/span>/);
  assert.ok(!h.includes('claude-sonnet-5-5'));
  const head = h.slice(0, h.indexOf('</div>'));
  assert.ok(!head.includes(' · '));
});
