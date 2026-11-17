// 11-17 사용자 결정 (다): 관리자 물음은 번호(#id)로 답하면 끝나고, 번호 없이 넘어가면 「아직 안 본 물음 N」으로 남는다
import test from 'node:test';
import assert from 'node:assert/strict';
import { needMark, humanNeed, escUnseen, unseenTip } from '../../bridge/static/js/render.js';

const U = [{ id: 3058, at: '2026-11-17T01:00:00Z', text: '배포를 오늘 할까요?' }, { id: 3060, at: '2026-11-17T02:00:00Z', text: '둘 중 무엇으로?' }];

test('아직 안 본 물음: 머리 위에 개수, 호버에 번호와 글', () => {
  const m = needMark({ state: 'IDLE', role: 'manager', escalate: { unseen: U } });
  assert.deepEqual([m.text, m.tone], ['아직 안 본 물음 2', 'warn']);
  assert.match(m.tip, /^아직 안 본 물음 — .*니다\./);
  assert.match(m.tip, /\n#3058 배포를 오늘 할까요\?\n#3060 둘 중 무엇으로\?$/);
  assert.equal(unseenTip(U), m.tip);
});

test('떠 있는 물음이 먼저, 그다음 아직 안 본 물음, 합치기 기다림과 보고는 그 아래', () => {
  const s = { state: 'IDLE', escalate: { question: { id: 3061, text: 'x' }, unseen: U, report: { id: 1 } }, merge_wait: { since: '2026-11-17T00:00:00Z' } };
  assert.equal(needMark(s).text, '사용자 답 기다림');
  assert.match(needMark(s).tip, /#3061/);                                       // 물음 번호를 호버에
  assert.equal(needMark({ ...s, escalate: { unseen: U, report: { id: 1 } } }).text, '아직 안 본 물음 2');
  assert.equal(needMark({ ...s, escalate: { unseen: [], report: { id: 1 } } }).text, '합치기 기다림');
});

test('아직 안 본 물음은 막힘이 아니라 배지는 그대로, 끝난 세션은 안 띄움', () => {
  assert.equal(humanNeed({ state: 'IDLE', escalate: { unseen: U } }), null);
  assert.equal(needMark({ state: 'DORMANT', escalate: { unseen: U } }), null);
  assert.deepEqual(escUnseen({}), []);
  assert.equal(escUnseen({ escalate: { unseen: U } }).length, 2);
});
