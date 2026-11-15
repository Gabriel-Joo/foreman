import { test } from 'node:test';
import assert from 'node:assert/strict';
import { flowStep, FLOW_STEPS, autoNote, endMenu, END_ITEMS, showMove, FLOW_TIP, chooseCountText, writeTip } from '../../bridge/static/js/handoff.js';

// 11-15 — 고르기 체크는 줄만 고친다(chooseSync). 그 수 줄 · 쓰기 단추 호버는 전부 그리기와 같은 함수에서 나온다
test('고르기 수 줄 · 쓰기 단추 호버', () => {
  assert.equal(chooseCountText(10, 1), '후보 10개 중 1개 고름');
  assert.match(writeTip(2), /^고른 2개를 문서에 쓰고 옮기기 — 고른 2개를 세션이/);
  assert.match(writeTip(0), /^문서에 넣지 않고 옮기기 — /);
});
import { MOVE_TIP } from '../../bridge/static/js/moveflow.js';

// 11-14 사용자 — 「세션」 [끝내기 ▾] 셋, 「끝내고 버리기」 없음, 설명은 줄 아래, 할 수 없는 것은 꺼진 버튼 + 까닭 호버
test('끝내기 메뉴: 셋 · 버리기 없음 · 같은 동작 · 꺼진 항목 까닭', () => {
  assert.deepEqual(END_ITEMS.map((x) => x[1]), ['합치고 끝내기', '커밋만 하고 끝내기', '그냥 끝내기']);
  assert.deepEqual(END_ITEMS.map((x) => x[0]), ['wt-end-merge', 'rest', 'exit']);     // 전 버튼과 같은 data-act → 같은 확인 창
  const all = endMenu({ exit: true, rest: true }, null);
  assert.ok(!all.includes('wt-end-discard') && !all.includes('버리기'));
  assert.ok(all.includes('<span class="small muted">작업방에 커밋만 해두고 끝냅니다</span>'));
  assert.ok(!all.includes('disabled') && !all.includes('title='));                    // 켜진 항목은 호버 없이 설명 줄로
  const dim = endMenu({ exit: true, rest: false }, '작업 중입니다');
  assert.match(dim, /data-act="rest" class="end-item" role="menuitem" disabled title="커밋만 하고 끝내기 — 지금은 할 수 없습니다. 작업 중입니다\."/);
  assert.match(dim, /data-act="exit" class="end-item" role="menuitem"><b>/);
});

// 11-14 사용자 — 작업방(worktree)이 있는 세션은 「새 세션으로 옮기기」 묶음을 뺀다. 관리자(worktree 없음)는 그대로
test('옮기기 묶음: 작업방 있으면 뺌, 도는 흐름이면 보임', () => {
  assert.equal(showMove({ worktree: null }, null), true);
  assert.equal(showMove({ worktree: { exists: true, live: true, branch: 'cc/x' } }, null), false);
  assert.equal(showMove({ worktree: { exists: false, branch: 'cc/x' } }, null), false);
  assert.equal(showMove({ worktree: { error: '못 읽음' } }, null), true);
  assert.equal(showMove({ worktree: { exists: true } }, { i: 1 }), true);
});

test('옮기기 호버: 무엇을 하는지 먼저, 패널 머리와 같은 글', () => {
  assert.equal(MOVE_TIP, '새 세션으로 옮기기 — 지금 세션을 끝내고 같은 자리에 새 세션을 띄웁니다. 잊은 것을 찾아 문서에 넣을 후보를 보여드리니 고르기만 하면 됩니다.');
  assert.equal(FLOW_TIP, MOVE_TIP);
});

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
