import { test } from 'node:test';
import assert from 'node:assert/strict';
import { flowStep, FLOW_STEPS, autoNote } from '../../bridge/static/js/handoff.js';

// 11-14 사용자 — 「(자동: CLAUDE.md, CLAUDE.md, CLAUDE.md)」. 같은 이름은 하나로, 셋을 넘으면 「첫 것 외 N개」
test('읽을 곳 자동 목록: 중복을 빼고 넷부터 줄인다', () => {
  assert.equal(autoNote([]), '');
  assert.equal(autoNote(null), '');
  const one = autoNote(['CLAUDE.md', 'CLAUDE.md', './CLAUDE.md']);
  assert.ok(one.includes('(자동: CLAUDE.md)') && one.includes('읽을 곳 3곳이 이 문서를 가리킵니다'));
  assert.ok(autoNote(['a.md', 'b.md', 'c.md']).includes('(자동: a.md, b.md, c.md)'));
  const four = autoNote(['a.md', 'b.md', 'c.md', 'd.md', 'a.md']);
  assert.ok(four.includes('(자동: a.md 외 3개)') && four.includes('d.md'));     // 전부는 호버에
});

// 넘기고 새로 시작(11-08) — 저장한 흐름 + 서버 데이터로 지금 단계를 정한다
test('단계: 요약 중 → 확인 → 새 세션 → 옛 세션 끝내기 → 끝', () => {
  assert.deepEqual(FLOW_STEPS, ['요약', '확인', '새 세션', '옛 세션 끝내기']);
  assert.equal(flowStep(null, null, true), null);                                      // 흐름 없음
  const f = { sumId: 7 };
  assert.deepEqual(flowStep(f, null, true), { i: 0, busy: true });                     // 아직 행이 안 보임
  assert.deepEqual(flowStep(f, { status: 'requested' }, true), { i: 0, busy: true });
  assert.deepEqual(flowStep(f, { status: 'ok' }, true), { i: 1 });                     // 확인 기다림
  assert.deepEqual(flowStep({ ...f, phase: 'spawning' }, { status: 'ok' }, true), { i: 2, busy: true });
  assert.deepEqual(flowStep({ ...f, phase: 'ending' }, { status: 'ok' }, true), { i: 3, busy: true });
  assert.deepEqual(flowStep({ ...f, phase: 'done' }, { status: 'ok' }, false), { i: 4, done: true });
});

test('새로 고친 뒤: 넣었는데 옛 세션이 살아 있으면 끝내기만 남음, 죽었으면 끝', () => {
  const s = { status: 'ok', injected_at: '2026-11-08T05:13:57Z' };
  assert.deepEqual(flowStep({ sumId: 7 }, s, true), { i: 3 });
  assert.deepEqual(flowStep({ sumId: 7 }, s, false), { i: 4, done: true });
});

test('실패: 요약 실패는 1단계, 저장한 오류는 그 단계에 빨갛게', () => {
  assert.deepEqual(flowStep({ sumId: 7 }, { status: 'timeout', error: '시간 초과' }, true), { i: 0, bad: true, msg: '시간 초과' });
  assert.deepEqual(flowStep({ sumId: 7, err: '끝내지 못함', errAt: 3 }, { status: 'ok' }, true), { i: 3, bad: true, msg: '끝내지 못함' });
});
