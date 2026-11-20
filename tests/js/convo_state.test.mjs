// 세션 패널 대화의 세 상태(11-20 foreman-161) — 빈 대화를 「불러오는 중」으로 그리지 않는다.
// 새로 띄운 세션(692)은 대화 요청이 200(턴 0개)으로 돌아왔는데 패널이 「불러오는 중…」에 머물렀다
import test from 'node:test';
import assert from 'node:assert/strict';
import { convoHtml } from '../../bridge/static/js/render.js';

const TURN = { id: 1, origin: 'human', started_at: '2026-11-20T09:21:04Z', prompt: '첫 글', reply: null, end_reason: null };

test('아직 받지 않았거나 받는 중이면 불러오는 중', () => {
  assert.match(convoHtml(undefined), /불러오는 중/);
  assert.match(convoHtml({ turns: [], loading: true }), /불러오는 중/);
});

test('받았는데 턴이 없으면 아직 대화가 없습니다(불러오는 중이 아니다)', () => {
  const h = convoHtml({ turns: [], loading: false, error: null });
  assert.match(h, /아직 대화가 없습니다/);
  assert.doesNotMatch(h, /불러오는 중/);
});

test('못 받았으면 실패로', () => {
  const h = convoHtml({ turns: [], loading: false, error: 'HTTP 500' });
  assert.match(h, /대화를 불러오지 못했습니다\(HTTP 500\)/);
  assert.doesNotMatch(h, /불러오는 중|아직 대화가 없습니다/);
});

test('턴이 있으면 그리고, 다시 받는 중이면 아래에 불러오는 중', () => {
  const h = convoHtml({ turns: [TURN], loading: false });
  assert.match(h, /첫 글/);
  assert.doesNotMatch(h, /불러오는 중|아직 대화가 없습니다/);
  assert.match(convoHtml({ turns: [TURN], loading: true }), /첫 글[\s\S]*불러오는 중/);
});
