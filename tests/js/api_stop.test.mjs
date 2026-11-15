// API 오류로 멈춘 세션(11-13, log/screen_api_error_bar_20261113.md) — 서버 api_stop을 머리 위 · 배지로
import test from 'node:test';
import assert from 'node:assert/strict';
import { needMark, humanNeed, stateBadge, apiStopTip } from '../../bridge/static/js/render.js';
import { Store } from '../../bridge/static/js/store.js';

const AS = { turn_id: 7, at: '2026-11-12T05:00:17Z', kind: 'safeguard', label: '안전 분류기 거부', detail: 'reasoning_extraction',
  action: '/model로 다른 모델로 바꾸거나 요청 글을 바꿔 다시 보냅니다', request_id: 'req_abc12345', reset: null };

test('머리 위 「API 오류로 멈춤」 — 빨강(bad), 작업 세션에도 사람용', () => {
  for (const role of ['coder', 'scribe', 'designer', 'manager']) {
    const m = needMark({ state: 'IDLE', role, api_stop: AS });
    assert.deepEqual([m.text, m.tone], ['API 오류로 멈춤', 'bad']);
  }
  // 말풍선 칸에 맞는지(넘치면 뭉개진다)는 글자 수가 아니라 그린 폭으로 — tools/screen.py --demo overhead_marks의 bubbleAudit · 사진
});

test('호버 — 종류 · 할 일 · request id, 「~습니다」', () => {
  const tip = apiStopTip(AS);
  assert.match(tip, /^API 오류로 멈춤 — /);
  assert.match(tip, /안전 분류기 거부 \[reasoning_extraction\]/);
  assert.match(tip, /할 일: \/model로 다른 모델로 바꾸거나/);
  assert.match(tip, /req_abc12345/);
  assert.match(tip, /니다\.$/);
  // 종류를 모르면(unknown) 일반 글
  assert.match(apiStopTip({ kind: 'unknown', label: 'API 오류' }), /^API 오류로 멈춤 — 마지막 턴이 API 오류로 끝났고 .*할 일: 그 세션 대화창에서/);
  assert.match(apiStopTip({ kind: 'rate_limit', label: '사용량 한도', reset: '3pm', action: '기다립니다' }), /3pm에 풀림/);
});

test('배지(패널 · 세션 목록)도 사람 몫 — 끝난 세션은 안 띄움', () => {
  assert.equal(humanNeed({ state: 'IDLE', api_stop: AS }).label, 'API 오류로 멈춤');
  assert.match(stateBadge({ state: 'IDLE', api_stop: AS }), /st-NEED.*API 오류로 멈춤/);
  assert.equal(needMark({ state: 'DORMANT', api_stop: AS }), null);
  assert.equal(humanNeed({ state: 'DORMANT', api_stop: AS }), null);
});

test('겹침 — 권한 거부 > API 오류로 멈춤 > 답 기다림 · 그 아래 모두', () => {
  assert.equal(needMark({ state: 'IDLE', denied: { tool: 'Bash' }, api_stop: AS }).text, '권한 거부');
  assert.equal(needMark({ state: 'IDLE', api_stop: AS, asks: {} }).text, 'API 오류로 멈춤');
  assert.equal(needMark({ state: 'IDLE', api_stop: AS, escalate: { question: { id: 1 } }, report: { event_id: 1 } }).text, 'API 오류로 멈춤');
  assert.equal(needMark({ state: 'IDLE', api_stop: AS, merge_wait: { since: '2026-11-13T00:00:00Z' } }).text, 'API 오류로 멈춤');
});

function storeWith(s) {
  const st = new Store();
  st.state.sessions.set(s.id, s);
  st.snaps = [];
  st.scheduleSnapshot = (ms) => st.snaps.push(ms ?? 800);
  st.touch = () => {};
  st.pushFeed = () => {};
  return st;
}

test('store — 새 턴이 열리면 바로 풀리고, API 오류로 닫힌 턴은 곧바로 스냅샷', () => {
  const s = { id: 5, state: 'IDLE', proc: 'S', cc_status: 'idle', open_turn: null, api_stop: AS };
  const st = storeWith(s);
  st.onTurn({ op: 'open', session_id: 5, turn_id: 8, origin: 'human', ts: '2026-11-13T00:00:00Z' });
  assert.equal(s.api_stop, null);
  assert.equal(needMark(s), null);
  st.onTurn({ op: 'close', session_id: 5, turn_id: 8, reason: 'stop_failure', ts: '2026-11-13T00:00:05Z' });
  assert.equal(st.snaps.length, 1);                 // 종류 · 까닭은 스냅샷에만 — 15초를 기다리지 않는다
  st.onTurn({ op: 'open', session_id: 5, turn_id: 9, origin: 'human', ts: '2026-11-13T00:01:00Z' });
  st.onTurn({ op: 'close', session_id: 5, turn_id: 9, reason: 'stop', ts: '2026-11-13T00:01:05Z' });
  assert.equal(st.snaps.length, 1);                 // 보통 끝은 그대로(주기 스냅샷)
});
