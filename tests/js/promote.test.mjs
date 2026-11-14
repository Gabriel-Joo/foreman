import { test } from 'node:test';
import assert from 'node:assert/strict';
import { merged, edits, counts, promoteGroup, inputPick } from '../../bridge/static/js/promote.js';

const ITEMS = [
  { id: 1, kind: '기준', what: '시험 세션은 끝낸 뒤 숨긴다', quote: '', dest: 'CLAUDE.md', section: '작업 규칙', why: 'w', state: 'pending', check: { ok: true } },
  { id: 2, kind: '결정', what: '그때뿐', quote: '', dest: 'drop', section: '', why: '', state: 'dropped', check: { ok: true } },
  { id: 3, kind: '결정', what: '<b>범위</b>', quote: '건드리지 마라', dest: '../x.md', section: '', why: '', state: 'pending', check: { ok: false, problem: '저장소 맨 위 기준 경로만 됩니다' } },
];

test('사람이 고친 값만 얹고, 버림은 승인될 수 없다', () => {
  const d = { 1: { state: 'approved', what: '고침' }, 2: { state: 'approved' } };
  assert.equal(merged(ITEMS[0], d).what, '고침');
  assert.equal(merged(ITEMS[1], d).state, 'dropped');
  assert.deepEqual(edits(ITEMS, d), [{ id: 1, what: '고침', state: 'approved' }]);
  assert.deepEqual(edits(ITEMS, { 1: { what: ITEMS[0].what } }), []);   // 같은 값은 고침이 아니다
  assert.deepEqual(counts(ITEMS, d), { pending: 1, approved: 1, dropped: 1 });
});

test('목록 그리기 — 글은 이스케이프, 틀린 목적지 표시, 저장 전 승인은 쓰기에 세지 않는다', () => {
  const p = { id: 7, status: 'listed', items: ITEMS, updated_at: new Date().toISOString() };
  const h = promoteGroup(p, true, { 1: { state: 'approved' } }, null);
  assert.ok(h.includes('&lt;b&gt;범위') && !h.includes('<b>범위'));
  assert.ok(h.includes('✗ 저장소 맨 위 기준 경로만 됩니다'));
  assert.ok(h.includes('승인 1') && h.includes('(저장 전)'));
  assert.match(h, /data-act="prom-write"[^>]*disabled/);               // 저장된 승인은 0개
  const saved = { ...p, items: ITEMS.map((x) => (x.id === 1 ? { ...x, state: 'approved' } : x)) };
  assert.doesNotMatch(promoteGroup(saved, true, {}, null), /data-act="prom-write"[^>]*disabled/);
});

test('쓴 뒤에는 고칠 수 없고 확인 결과를 보인다', () => {
  const p = { id: 7, status: 'write_failed', items: [], result: { ok: false, commit: 'abcdef1234', files: ['CLAUDE.md', 'other.md'], problems: ['승인하지 않은 파일도 바뀌었습니다: other.md'] } };
  const h = promoteGroup(p, false, {}, null);
  assert.ok(h.includes('✗ 확인 실패') && h.includes('abcdef12') && h.includes('other.md'));
  const w = promoteGroup({ ...p, status: 'written', items: ITEMS, result: { ok: true, commit: 'abcdef1234', files: ['CLAUDE.md'] } }, false, {}, null);
  assert.ok(w.includes('✓ 확인했습니다') && !w.includes('prom-save'));
  assert.match(w, /<textarea data-f="what"[^>]* disabled/);
  assert.ok(promoteGroup(null, true, {}, '읽지 못했습니다').includes('읽지 못했습니다'));
  assert.match(promoteGroup(null, false, {}, null), /data-act="prom-req"[^>]*disabled/);
});

test('같이 넣을 인계 — 여럿이면 말없이 첫째를 고르지 않고, 목록에는 무엇을 넣었는지 보인다', () => {
  const two = [{ id: 7, title: '받은 것', why: '이 세션이 받은 인계' }, { id: 6, title: '앞 것', why: '같은 프로젝트의 인계' }];
  const sel = (h) => (h.match(/<option value="([^"]*)" selected/) || [])[1];
  assert.equal(sel(inputPick(two, null)), '');                         // 고르기 칸이 선택된 채
  assert.equal(sel(inputPick(two, '6')), '6');
  assert.equal(sel(inputPick([two[0]], null)), '7');                   // 하나뿐이면 그것
  const p = { id: 9, status: 'listed', items: [], summary_id: 7, updated_at: new Date().toISOString() };
  assert.ok(promoteGroup(p, false, {}, null).includes('요약 #7 같이 넣음'))   // 11-09 화면 말 통일(인계 → 요약);
  assert.ok(promoteGroup({ ...p, summary_id: null }, false, {}, null).includes('같이 넣은 것 없음'));
  assert.ok(promoteGroup({ ...p, summary_id: null, loss_check_id: 3 }, false, {}, null).includes('잃은 것 점검 #3 같이 넣음'));
  const withLoss = inputPick([{ id: 'lc:3', kind: 'loss', title: '잃은 것 점검 #3', why: '사라짐 2 · 약해짐 1' }, two[0]], 'lc:3');
  assert.equal(sel(withLoss), 'lc:3');
  assert.ok(withLoss.includes('잃은 것 점검 #3 — 사라짐 2 · 약해짐 1'));
});

// 11-14 사용자 — 평소 한 줄: [대화에서만 정한 것 문서에 적기] 아직 없습니다 같이 넣을 것(N개). 소제목 · 설명문은 버튼 호버로
test('문서 적기 한 줄: 버튼 이름 그대로, 설명은 호버, 온점 없는 「아직 없습니다」', () => {
  const two = [{ id: 7, title: 'a', why: 'x' }, { id: 6, title: 'b', why: 'y' }];
  const h = promoteGroup(null, true, {}, null, two, null);
  assert.match(h, /data-act="prom-req"[^>]*title="대화에서만 정한 것 문서에 적기 — [^"]+"[^>]*>대화에서만 정한 것 문서에 적기</);
  assert.ok(h.includes('>아직 없습니다<') && !h.includes('아직 없습니다.'));
  assert.ok(!h.includes('hand-item-h'));
  assert.ok(h.indexOf('아직 없습니다') < h.indexOf('같이 넣을 것(2개)'));          // 버튼 · 상태 · 같이 넣을 것 차례
});
