// 서기실 전체 줄 칸(11-19 사용자, bridge/scribe_queue.py view → scribe.js queueBlock).
// 줄 목록, 지금 편, 멈추기와 이어가기, 실패와 미룬 목록, 판단거리는 줄이 끝날 때 한 번에. [전체] 단추는 포트폴리오와 기술문서가 한 벌
import test from 'node:test';
import assert from 'node:assert/strict';
import { keepReset } from '../../bridge/static/js/render.js';
import { createScribe, pieceButtons, queueBlock } from '../../bridge/static/js/scribe.js';

globalThis.localStorage = (() => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) }; })();
const TASKS = { techdoc: { title: '기술문서 쓰기', desc: 'd' }, portfolio: { title: '포트폴리오 쓰기', desc: 'd' } };
const item = (pos, topic, state, extra = {}) => ({ id: pos + 1, pos, topic, title: topic.toUpperCase(), state, session_id: null, how: null,
  reason: null, has_decisions: false, ...extra });
const Q = (state, items, extra = {}) => {
  const k = { waiting: 0, running: 0, merged: 0, auto: 0, card: 0, failed: 0, held: 0, decisions: 0 };
  for (const i of items) { k[i.state] += 1; if (i.state === 'merged') k[i.how === 'auto' ? 'auto' : 'card'] += 1; if (i.has_decisions) k.decisions += 1; }
  const cur = items.find((i) => i.state === 'running');
  return { id: 7, task: 'techdoc', state, state_ko: { running: '도는 중', paused: '멈춤', done: '끝남' }[state], note: null, items, counts: k,
    current: cur ? { topic: cur.topic, title: cur.title, session_id: cur.session_id, reason: cur.reason, minutes: 12, stalled: false } : null,
    stall_min: 60, ...extra };
};

test('도는 줄: 지금 편, 줄 목록(합친 편도 남음), 실패는 바로, 판단거리와 미룬 카드는 수만', () => {
  keepReset();
  const q = Q('running', [
    item(0, 'a', 'merged', { how: 'auto', has_decisions: true }), item(1, 'b', 'failed', { reason: '커밋 없이 끝났습니다', session_id: 41 }),
    item(2, 'c', 'held', { reason: '사람 승인: config', session_id: 42 }), item(3, 'd', 'running', { session_id: 43, reason: '서기가 고쳐 쓰는 중' }),
    item(4, 'e', 'waiting')]);
  const h = queueBlock(q, TASKS);
  assert.match(h, /<b>전체 줄<\/b> 기술문서 쓰기/);
  assert.match(h, /합침 1\(카드 없이 1, 카드로 0\), 실패 1, 미룸 1, 남음 1/);
  assert.match(h, /지금 편 「D」[\s\S]*세션 43, 12분째[\s\S]*서기가 고쳐 쓰는 중/);
  assert.match(h, /data-sq-act="pause" data-qid="7"[^>]*>멈추기</);
  assert.match(h, /<b>실패 1<\/b>[\s\S]*「B」: 커밋 없이 끝났습니다[\s\S]*data-sc-open="41"/);     // 실패는 줄이 도는 동안에도 따로
  assert.match(h, /미룬 카드 1\(사람 승인, 줄이 끝나면 모아 보입니다\)/);
  assert.match(h, /판단거리 1편\(줄이 끝나면 한 번에 보입니다\)/);
  assert.ok(!h.includes('data-sc-open="42"'), '미룬 카드 목록은 끝날 때');
  assert.match(h, /줄 목록 5<\/summary>[\s\S]*A <code>a<\/code> <span class="ok">합침\(카드 없이\)/);
  assert.match(h, /E <code>e<\/code> <span class="muted">기다림/);
});

test('오래 안 끝나는 편은 빨갛게, 멈춘 줄은 [이어가기]와 [줄 닫기]', () => {
  const q = Q('running', [item(0, 'a', 'running', { session_id: 9 })]);
  q.current.stalled = true; q.current.minutes = 75;
  assert.match(queueBlock(q, TASKS), /<div class="small bad">지금 편 「A」[\s\S]*75분째[\s\S]*오래 안 끝남\(60분 넘음\)/);
  const p = Q('paused', [item(0, 'a', 'merged', { how: 'card' }), item(1, 'b', 'waiting')], { note: '멈추기: 지금 편이 끝나면 다음 편을 띄우지 않습니다' });
  const h = queueBlock(p, TASKS);
  assert.match(h, /data-sq-act="resume"[^>]*>이어가기</);
  assert.match(h, /data-sq-act="close"[^>]*>줄 닫기</);
  assert.ok(!h.includes('data-sq-act="pause"'));
  assert.match(h, /멈추기: 지금 편이 끝나면 다음 편을 띄우지 않습니다\. 지금 도는 편이 없습니다/);
});

test('끝난 줄: 판단거리 글과 미룬 카드 목록을 한 번에', () => {
  const q = Q('done', [
    item(0, 'a', 'merged', { how: 'auto', has_decisions: true, decisions: '- 가 편을 나눌지' }),
    item(1, 'b', 'held', { reason: '사람 승인: docs/style_guide.md', session_id: 52, has_decisions: true, decisions: '1. <b>둘</b>' })]);
  const h = queueBlock(q, TASKS);
  assert.match(h, /<b>판단거리 2편<\/b>[\s\S]*「A」[\s\S]*- 가 편을 나눌지[\s\S]*「B」[\s\S]*1\. &lt;b&gt;둘&lt;\/b&gt;/);
  assert.match(h, /<b>미룬 카드 1<\/b>[\s\S]*「B」: 사람 승인: docs\/style_guide\.md[\s\S]*data-sc-open="52"/);
  assert.match(h, /data-sq-act="close"/);
  assert.equal(queueBlock(null, TASKS), '');
  assert.match(queueBlock({ error: '줄을 읽지 못했습니다(X)' }, TASKS), /bad[\s\S]*줄을 읽지 못했습니다/);
});

test('[전체]는 코드가 바뀐 편 수를 싣고, 도는 줄이 있거나 바뀐 편이 없으면 꺼진다(포트폴리오와 기술문서가 한 벌)', () => {
  const tps = [{ slug: 'a', title: 'A', commits: 2 }, { slug: 'b', title: 'B', commits: 0 }, { slug: 'c', title: 'C', commits: null }];
  for (const task of ['techdoc', 'portfolio']) {
    const { all } = pieceButtons(task, 'X', tps);
    assert.match(all, new RegExp(`data-sc-queue="${task}" data-n="2"(?![^>]*disabled)[^>]*>전체<`));
    assert.match(all, /코드가 바뀐 편 2편을 줄을 세워 한 편씩/);
  }
  const on = pieceButtons('portfolio', 'X', tps, false, { state: 'paused' }).all;
  assert.match(on, /disabled[^>]*이미 도는 줄이 있습니다/);
  assert.ok(!pieceButtons('portfolio', 'X', tps, false, { state: 'done' }).all.includes('disabled'));
  assert.match(pieceButtons('techdoc', 'X', [{ slug: 'b', title: 'B', commits: 0 }]).all, /disabled[^>]*코드가 바뀐 편이 없습니다/);
});

test('서기실 창: 줄 칸이 보이고, 포트폴리오 쓰기와 기술문서 쓰기 줄에 [전체], 포트폴리오도 「편 목록」', async () => {
  keepReset();
  const tps = [{ slug: 'a', title: 'A', commits: 1, blocked: null }];
  const pj = { open: [], blocked: {}, behind: {}, items: [], topics: tps, portfolio: { total: 1, changed: 1, unknown: 0, written: 1 },
    techdoc: { why: 'w', topics: tps }, queue: Q('running', [item(0, 'a', 'running', { session_id: 3 })]) };
  globalThis.fetch = async (u) => (u === '/api/scribe/todo'
    ? { ok: true, json: async () => ({ tasks: { ...TASKS, doccheck: { title: '문서 점검', desc: 'd' } }, projects: { foreman: pj } }) }
    : { ok: true, json: async () => ({ enabled: true, docs: [], portfolio: {} }) });
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('foreman', 'F'); await new Promise((r) => setTimeout(r, 5));
  const h = sc.html('foreman', 'F');
  assert.match(h, /<b>전체 줄<\/b> 기술문서 쓰기/);
  assert.match(h, /data-sc-queue="portfolio"[^>]*disabled/);          // 줄은 프로젝트에 하나
  assert.match(h, /data-sc-queue="techdoc"[^>]*disabled/);
  assert.match(h, /<summary[^>]*>편 목록 1<\/summary>/);
  assert.ok(!h.includes('글 목록'), '포트폴리오도 「편 목록」(11-19 사용자)');
});
