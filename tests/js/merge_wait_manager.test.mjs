// 11-13(사용자 — 「나는 관리자하고만 이야기한다」) — 사람 승인 합치기 카드는 관리자 머리 위 「사용자 답 기다림」으로.
// 작업 세션 머리 위 「합치기 기다림」은 관리자에게 올리지 못했을 때만. 승인 막대(mergeWaits)는 그대로 센다
import test from 'node:test';
import assert from 'node:assert/strict';
import { needMark, mergeWaits } from '../../bridge/static/js/render.js';

const MW = { since: '2026-11-13T10:00:00Z', head8: 'abcd1234', files: 2, asks: false, to_manager: null, esc_error: null };

test('관리자에게 올린 카드 — 작업 세션 머리 위에서 빠지고 막대는 센다', () => {
  const coder = { id: 7, state: 'IDLE', merge_wait: { ...MW, to_manager: 3 } };
  assert.equal(needMark(coder), null);
  assert.deepEqual(mergeWaits([coder]).map((s) => s.id), [7]);
  // 관리자에게 넘긴 보고가 있으면 그것(작게)만 남는다
  assert.equal(needMark({ ...coder, relayed: { kind: 'report' } }).text, '관리자에게 보고함');
});

test('작업 세션 — 「관리자 답 기다림」은 남고, 「관리자에게 보고함」과 겹치면 보고함이 이긴다(11-13 사용자)', () => {
  const w = { id: 7, state: 'IDLE' };
  assert.equal(needMark({ ...w, relayed: { kind: 'question' } }).text, '관리자 답 기다림');
  assert.equal(needMark({ ...w, relayed: { kind: 'question', kinds: ['question'] } }).text, '관리자 답 기다림');
  assert.equal(needMark({ ...w, relayed: { kind: 'question', kinds: ['question', 'report'] } }).text, '관리자에게 보고함');
  assert.equal(needMark({ ...w, relayed: { kind: 'report', kinds: ['question', 'report'] } }).text, '관리자에게 보고함');
  assert.equal(needMark({ ...w, relayed: { kind: 'report' } }).tone, 'quiet');
});

test('관리자가 없거나 못 올렸으면 지금처럼 작업 세션 머리 위 「합치기 기다림」 — 까닭을 툴팁에', () => {
  const m = needMark({ id: 7, state: 'IDLE', merge_wait: { ...MW, esc_error: '살아 있는 관리자 세션이 없습니다' } });
  assert.equal(m.text, '합치기 기다림');
  assert.equal(m.mergeSid, 7);
  assert.match(m.tip, /살아 있는 관리자 세션이 없습니다/);
});

test('관리자 머리 위 — 합치기 카드 물음은 「사용자 답 기다림」, 누르면 그 카드 세션(mergeSid)', () => {
  const mgr = { id: 3, state: 'IDLE', role: 'manager', escalate: { question: { id: 9, text: '세션 7 「일」 합치기 카드 — 사람 승인이 필요합니다', merge_sid: 7 }, merges: [7] } };
  const m = needMark(mgr);
  assert.equal(m.text, '사용자 답 기다림');
  assert.equal(m.tone, 'warn');
  assert.equal(m.mergeSid, 7);
  assert.match(m.tip, /^사용자 답 기다림 — 세션 7의 합치기 카드가 사람 승인을 기다립니다/);
  // 관리자가 직접 올린 물음은 지금처럼(누르면 관리자 대화)
  const plain = needMark({ ...mgr, escalate: { question: { id: 8, text: '배포할까요?' } } });
  assert.equal(plain.mergeSid, null);
  assert.match(plain.tip, /관리자가 사람에게 물었습니다/);
});
