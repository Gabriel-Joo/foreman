// 머리 위 표시 다시 설계(11-13 사용자) — 관리자: 사용자에게 보고함 · 사용자 답 기다림, 작업 세션: 관리자에게 보고함 · 관리자 답 기다림
import test from 'node:test';
import assert from 'node:assert/strict';
import { needMark, humanNeed, stateBadge } from '../../bridge/static/js/render.js';

const MW = { since: '2026-11-13T10:00:00Z', head8: 'abcd1234', files: 2, asks: false };

test('관리자가 올린 것 — 글자는 사용자가 정한 그대로', () => {
  assert.equal(needMark({ state: 'IDLE', role: 'manager', escalate: { report: { id: 1, text: '세 가지 합침' } } }).text, '사용자에게 보고함');
  assert.equal(needMark({ state: 'IDLE', role: 'manager', escalate: { question: { id: 2 } } }).text, '사용자 답 기다림');
  assert.equal(needMark({ state: 'IDLE', role: 'manager', escalate: { report: { id: 1 } } }).tone, 'ok');
  assert.equal(needMark({ state: 'IDLE', role: 'manager', escalate: { question: { id: 2 } } }).tone, 'warn');
  assert.match(needMark({ state: 'IDLE', escalate: { report: { id: 1, text: '세 가지 합침' } } }).tip, /^사용자에게 보고함 —.*니다\.\n세 가지 합침$/s);
});

test('작업 세션이 관리자에게 넘긴 것 — 작게(quiet)', () => {
  const r = needMark({ state: 'IDLE', role: 'coder', relayed: { kind: 'report' } });
  assert.deepEqual([r.text, r.tone], ['관리자에게 보고함', 'quiet']);
  const q = needMark({ state: 'IDLE', role: 'scribe', relayed: { kind: 'question' } });
  assert.deepEqual([q.text, q.tone], ['관리자 답 기다림', 'quiet']);
  assert.match(q.tip, /^관리자 답 기다림 — .*니다\.$/);
  assert.equal(humanNeed({ state: 'IDLE', relayed: { kind: 'question' } }), null);       // 사람 몫이 아니다 — 배지도 쉼 그대로
  assert.doesNotMatch(stateBadge({ state: 'IDLE', relayed: { kind: 'question' } }), /st-NEED/);
});

test('겹침 — 권한 거부 > 답 기다림 > 사용자 답 기다림 > 합치기 > 사용자에게 보고함 > 보고 옴 > 관리자에게 넘김', () => {
  let s = { state: 'IDLE', denied: { tool: 'Bash' }, asks: {}, escalate: { question: { id: 1 }, report: { id: 2 } }, merge_wait: MW, report: { event_id: 3 }, relayed: { kind: 'report' } };
  const order = ['권한 거부', '답 기다림', '사용자 답 기다림', '합치기 기다림', '사용자에게 보고함', '보고 옴', '관리자에게 보고함'];
  const drop = [(x) => { delete x.denied; }, (x) => { delete x.asks; }, (x) => { x.escalate = { report: x.escalate.report }; },
                (x) => { delete x.merge_wait; }, (x) => { delete x.escalate; }, (x) => { delete x.report; }];
  for (let i = 0; i < order.length; i++) {
    assert.equal(needMark(s).text, order[i]);
    if (drop[i]) { s = { ...s }; drop[i](s); }
  }
});

test('사용자 답 기다림은 배지 · [답 안 해도 됨]에도 — 끝난 세션은 안 띄움', () => {
  assert.equal(humanNeed({ state: 'IDLE', escalate: { question: { id: 1 } } }).label, '사용자 답 기다림');
  assert.equal(needMark({ state: 'DORMANT', escalate: { question: { id: 1 } } }), null);
});
