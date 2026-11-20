// 입력 제출 확인(11-20) — 202 + verified:false + check면 「확인 중」으로 띄우고, 결과를 물어 바꾼다.
// 「늦게 확인:」 활동 줄과 모델 바꾸기의 504 갈래도 본다. 가짜 fetch, 가짜 sleep으로 돌린다
import test from 'node:test';
import assert from 'node:assert/strict';
import { Store } from '../../bridge/static/js/store.js';

function mk(responses) {
  const st = new Store();
  st.sleep = async () => {};
  st.inputPollMs = [0, 0, 0, 0];
  st.touch = () => {};
  st.convoLater = () => { st.later = (st.later || 0) + 1; };
  st.calls = [];
  st.state.sessions.set(5, { id: 5, feed: [] });
  globalThis.fetch = async (url, opt) => {
    st.calls.push(url);
    const r = responses.shift();
    return { status: r.status, ok: r.status >= 200 && r.status < 300, json: async () => r.body };
  };
  return st;
}

const wait = () => new Promise((r) => setImmediate(r));

test('202 + verified:false + check면 확인 중으로 띄우고, 들어간 걸 물어 보냈습니다로 바꾼다', async () => {
  const st = mk([
    { status: 202, body: { verified: false, check: 'c1', queued: false } },
    { status: 200, body: { state: 'checking' } },
    { status: 200, body: { state: 'delivered' } },
  ]);
  const res = await st.sendInput(5, '글', false);
  assert.deepEqual([res.ok, res.msg, res.pending], [true, '보냈습니다. 기록을 확인하는 중입니다.', true]);
  assert.equal(st.state.lastInput.pending, true);
  await wait(); await wait(); await wait();
  assert.equal(st.state.lastInput.msg, '보냈습니다.');
  assert.equal(st.state.lastInput.ok, true);
  assert.ok(!st.state.lastInput.pending);
  assert.match(st.calls[1], /\/api\/sessions\/5\/input\/c1$/);
  assert.equal(st.later, 2);                       // 보낸 직후 한 번, 늦게 기록된 뒤 한 번
});

test('끝내 기록에서 찾지 못하면 실패 글로 바뀐다', async () => {
  const st = mk([
    { status: 202, body: { verified: false, check: 'c2' } },
    { status: 200, body: { state: 'not_found' } },
  ]);
  await st.sendInput(5, '글', false);
  await wait(); await wait();
  assert.equal(st.state.lastInput.ok, false);
  assert.match(st.state.lastInput.msg, /기록에서 찾지 못했습니다/);
});

test('확인 번호가 사라졌으면(404) 알 수 없다고 하고, 그 사이 새로 보낸 글이 있으면 덮지 않는다', async () => {
  const st = mk([
    { status: 202, body: { verified: false, check: 'c3' } },
    { status: 404, body: {} },
  ]);
  await st.sendInput(5, '글', false);
  await wait(); await wait();
  assert.match(st.state.lastInput.msg, /알 수 없습니다/);

  const st2 = mk([
    { status: 202, body: { verified: false, check: 'c4' } },
    { status: 200, body: { state: 'checking' } },
  ]);
  st2.sleep = () => new Promise((r) => { st2.release = r; });
  await st2.sendInput(5, '글', false);
  const newer = { sessionId: 5, ts: Date.now(), ok: true, msg: '다른 글을 보냈습니다.' };
  st2.state.lastInput = newer;
  st2.release();
  await wait(); await wait();
  assert.equal(st2.state.lastInput, newer);
});

test('기록으로 확인했거나 슬래시 명령(check 없음)이면 물을 것 없이 보냈습니다', async () => {
  const st = mk([{ status: 202, body: { verified: true } }]);
  const a = await st.sendInput(5, '글', false);
  assert.deepEqual([a.ok, a.msg, !!a.pending], [true, '보냈습니다.', false]);
  const st2 = mk([{ status: 202, body: { verified: false, check: null, queued: true } }]);
  const b = await st2.sendInput(5, '/model x', true);
  assert.deepEqual([b.ok, b.msg, !!b.pending], [true, '보냈습니다. 작업이 끝나면 이어서 전달됩니다.', false]);
  assert.equal(st2.calls.length, 1);
});

test('504는 입력 칸에 남았거나 알 수 없을 때만', async () => {
  const left = await mk([{ status: 504, body: { left_in_box: true } }]).sendInput(5, '글', false);
  assert.equal(left.ok, false);
  assert.match(left.msg, /입력 칸에 글이 남아 있으니/);
  const unknown = await mk([{ status: 504, body: { left_in_box: null } }]).sendInput(5, '글', false);
  assert.match(unknown.msg, /제출됐는지 확인하지 못했습니다/);
});

test('모델 바꾸기 — 202는 바꿨습니다, 504 입력 칸에 남음은 실패(고른 모델 표시 안 함), 504 알 수 없음은 표시 유지', async () => {
  const ok = mk([{ status: 202, body: { queued: false } }]);
  assert.match((await ok.switchModel(5, 'opus', 'Opus')).msg, /바꿨습니다/);
  assert.ok(ok.state.pendingModel.has(5));
  const left = mk([{ status: 504, body: { left_in_box: true } }]);
  const l = await left.switchModel(5, 'opus', 'Opus');
  assert.equal(l.ok, false);
  assert.match(l.msg, /입력 칸에 명령이 남아 있으니/);
  assert.ok(!left.state.pendingModel.has(5));
  const unk = mk([{ status: 504, body: {} }]);
  assert.match((await unk.switchModel(5, 'opus', 'Opus')).msg, /확인하지 못했습니다/);
  assert.ok(unk.state.pendingModel.has(5));
});

test('늦은 결과 활동 줄은 「늦게 확인:」으로 걸린 시간과 함께, 옛 줄의 앞말은 떼고 그린다', () => {
  const st = new Store();
  st.touch = () => {};
  st.state.sessions.set(5, { id: 5, feed: [] });
  const ev = (target, payload) => ({ type: 'input', source: 'bridge', session_id: 5, ts: '2026-11-20T10:00:00Z', target, payload });
  st.onEvent(ev('들어갔습니다: 첫 글', { late: 'delivered', waited_s: 12.4 }));
  st.onEvent(ev('기록에서 찾지 못했습니다: 첫 글', { late: 'not_found', waited_s: 120 }));
  st.onEvent(ev('(늦게 확인) 들어갔습니다: 옛 글', { late: 'delivered' }));
  st.onEvent(ev('보낸 글', { queued: false }));
  const f = st.state.sessions.get(5).feed;
  assert.deepEqual(f.map((x) => [x.kind, x.text]), [
    ['input', '늦게 확인: 들어갔습니다: 첫 글 (12초 뒤)'],
    ['error', '늦게 확인: 기록에서 찾지 못했습니다: 첫 글 (120초 뒤)'],
    ['input', '늦게 확인: 들어갔습니다: 옛 글'],
    ['input', '주입: 보낸 글'],
  ]);
});
