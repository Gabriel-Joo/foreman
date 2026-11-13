// 새 세션으로 옮기기 한 흐름(11-11 C 2물결 일곱) — 사람이 멈추는 곳은 고르기 하나, 나머지는 저절로
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { moveStep, MOVE_STEPS, chooseCount, writeLabel, STALL_MS, lossNote, chooseAll, chooseFinal, chosen } from '../../bridge/static/js/moveflow.js';
import { edits } from '../../bridge/static/js/promote.js';

test('11-13 잊은 것 찾기 — 없음 · 볼 것 없음 · 일부 · 실패를 다른 줄로', () => {
  assert.equal(lossNote({ status: 'done', outcome: 'clean', lost_total: 0 }).tone, 'ok');
  assert.equal(lossNote({ status: 'nothing', outcome: 'nothing' }).tone, 'muted');
  const p = lossNote({ status: 'done', outcome: 'partial', error: '묶음 1개 실패', lost_total: 0 });
  assert.equal(p.tone, 'warn'); assert.match(p.msg, /「없음」은 아닙니다/);
  const f = lossNote({ status: 'failed', outcome: 'failed', error: 'TimeoutError' });
  assert.equal(f.tone, 'bad'); assert.match(f.msg, /실패했습니다 — TimeoutError/);
  // 흐름 — 볼 것 없음은 실패가 아니다
  const fl = { v: 2, stage: 'find', lcId: 5, at: T };
  const none = moveStep(fl, data({ losschecks: [{ id: 5, status: 'nothing', outcome: 'nothing' }] }), T);
  assert.equal(none.lcFailed, false); assert.equal(none.lcNote.tone, 'muted');
  const bad = moveStep(fl, data({ losschecks: [{ id: 5, status: 'failed', outcome: 'failed', error: 'x' }] }), T);
  assert.equal(bad.lcFailed, true); assert.equal(bad.lcNote.tone, 'bad');
});

test('11-13 고르기 — 센 수 · 체크 · 실제 쓰는 것이 같다, 전부 고르기 · 풀기', () => {
  const items = [{ id: 1, state: 'pending', dest: 'README.md' }, { id: 2, state: 'pending', dest: 'docs/a.md' },
    { id: 3, state: 'dropped', dest: 'drop' }, { id: 4, state: 'approved', dest: 'x.md', check: { ok: false, problem: '없는 파일' } }];
  assert.equal(chooseCount(items, {}), 0);                               // 고를 수 없는 #4는 승인이어도 세지 않는다
  let d = chooseAll(items, {}, true);
  assert.equal(chooseCount(items, d), 2); assert.ok(!chosen(items[2], d));   // 버림 · 틀린 목적지는 안 고른다
  d = { ...d, 3: { state: 'approved' } };                                // 버림을 억지로 고른 draft도 세지 않는다
  assert.equal(chooseCount(items, d), 2);
  const sent = edits(items, chooseFinal(items, d)).filter((e) => e.state === 'approved').map((e) => e.id);
  assert.deepEqual(sent, [1, 2]);                                        // 쓰는 것 = 센 것
  assert.ok(edits(items, chooseFinal(items, d)).some((e) => e.id === 4 && e.state === 'dropped'));
  assert.equal(chooseCount(items, chooseAll(items, d, false)), 0);
  assert.equal(writeLabel(chooseCount(items, d)), '고른 2개를 문서에 쓰고 옮기기');
});
import { flowStep } from '../../bridge/static/js/handoff.js';

const T = 1_000_000;
const data = (o = {}) => ({ losschecks: [], promotions: [], summaries: [], controls: { live: true }, ...o });

test('옛 흐름 · 한 흐름이 서로 끼어들지 않는다', () => {
  assert.equal(moveStep(null, data()), null);
  assert.equal(moveStep({ sumId: 1 }, data()), null);                    // 옛 흐름(v 없음)
  assert.equal(flowStep({ v: 2, stage: 'find' }, null, true), null);     // 한 흐름은 옛 판정이 안 본다
  assert.equal(MOVE_STEPS.length, 7);
});

test('① 잊은 것 찾기 → ② 문서 후보(잊은 것이 있으면 같이) — 실패해도 이어 간다', () => {
  const f = { v: 2, stage: 'find', lcId: 5, at: T };
  assert.deepEqual(moveStep(f, data({ losschecks: [{ id: 5, status: 'running', groups_done: 1, groups_total: 3 }] }), T + 1000),
    { i: 0, busy: true, msg: '잊은 것을 찾는 중입니다 1/3' });
  const done = moveStep(f, data({ losschecks: [{ id: 5, status: 'done', lost_total: 4 }] }), T);
  assert.equal(done.auto, 'promote'); assert.equal(done.lost, 4);
  const failed = moveStep(f, data({ losschecks: [{ id: 5, status: 'failed' }] }), T);
  assert.equal(failed.auto, 'promote'); assert.equal(failed.lcFailed, true); assert.equal(failed.lost, null);
});

test('③ 고르기에서만 사람을 기다린다 — 후보가 없으면 바로 요약', () => {
  const f = { v: 2, stage: 'list', promId: 9, at: T };
  assert.equal(moveStep(f, data({ promotions: [{ id: 9, status: 'requested' }] }), T).busy, true);
  const w = moveStep(f, data({ promotions: [{ id: 9, status: 'listed', items: [{ id: 1, state: 'pending' }] }] }), T);
  assert.equal(w.wait, true); assert.equal(w.i, 2);
  const none = moveStep(f, data({ promotions: [{ id: 9, status: 'listed', items: [] }] }), T);
  assert.equal(none.auto, 'summary'); assert.match(none.note, /넣을 것이 없다/);
  assert.equal(moveStep(f, data({ promotions: [{ id: 9, status: 'failed', error: 'x' }] }), T).bad, true);
});

test('④ 쓰기 → ⑤ 요약 → ⑥ 새 세션(확인 창 없이) → 끝', () => {
  const w = { v: 2, stage: 'write', promId: 9, at: T };
  assert.equal(moveStep(w, data({ promotions: [{ id: 9, status: 'writing' }] }), T).i, 3);
  assert.equal(moveStep(w, data({ promotions: [{ id: 9, status: 'written' }] }), T).auto, 'summary');
  const wf = moveStep(w, data({ promotions: [{ id: 9, status: 'write_failed', error: '커밋 없음', items: [{ id: 1 }] }] }), T);
  assert.equal(wf.wait, true); assert.match(wf.msg, /커밋 없음/);           // 실패하면 다시 고르기로
  const s = { v: 2, stage: 'summary', sumId: 3, at: T };
  assert.equal(moveStep(s, data({ summaries: [{ id: 3, status: 'requested' }] }), T).i, 4);
  assert.equal(moveStep(s, data({ summaries: [{ id: 3, status: 'ok' }] }), T).auto, 'spawn');
  assert.deepEqual(moveStep(s, data({ summaries: [{ id: 3, status: 'ok', injected_at: 'x' }] }), T), { i: 6 });
  assert.deepEqual(moveStep({ ...s, phase: 'done' }, data()), { i: 7, done: true });
  assert.equal(moveStep({ ...s, err: '띄우지 못함', errAt: 5 }, data()).bad, true);
});

test('한 단계가 오래 그대로면 멈춘 것 같다고 알린다(조용히 서 있지 않게)', () => {
  const f = { v: 2, stage: 'find', lcId: 5, at: T };
  const m = moveStep(f, data({ losschecks: [{ id: 5, status: 'running' }] }), T + STALL_MS + 60000);
  assert.equal(m.bad, true); assert.equal(m.stalled, true); assert.match(m.msg, /11분째 그대로입니다/);
});

test('고른 수 · 단추 글', () => {
  const items = [{ id: 1, state: 'pending' }, { id: 2, state: 'approved' }];
  assert.equal(chooseCount(items, {}), 1);
  assert.equal(chooseCount(items, { 1: { state: 'approved' }, 2: { state: 'dropped' } }), 1);
  assert.equal(writeLabel(2), '고른 2개를 문서에 쓰고 옮기기');
  assert.equal(writeLabel(0), '문서에 넣지 않고 옮기기');
});
