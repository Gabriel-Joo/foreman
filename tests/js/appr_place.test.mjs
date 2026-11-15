// 질문 · 승인 카드 자리(11-10 사용자 — 받은 할 일 #2 · #5 · #11): 답하는 카드는 그 세션 패널에만, 다른 세션 것은 보기만,
// 답한 것은 한 줄로 접힘 · [×] 치우기 · 세션마다 최근 FOLD_KEEP줄
import test from 'node:test';
import assert from 'node:assert/strict';
import { apprPlace, apprFoldLine, apprPeekLine, apprAnswer, apprWho, approvalCard, NOTES } from '../../bridge/static/js/render.js';
import { pruneResolved, FOLD_KEEP } from '../../bridge/static/js/store.js';

const st = {
  sessions: new Map([[251, { id: 251, role: 'designer' }], [231, { id: 231, role: 'coder' }]]),
  projects: [{ name: 'foreman', label: 'FOREMAN' }, { name: 'runshoes', label: '런슈즈' }],
};
const Q = (id, sid, status = 'pending', extra = {}) => ({ id, session_id: sid, status, tool: 'AskUserQuestion', project: sid === 231 ? 'runshoes' : 'foreman',
  target: 'Q', questions: [{ question: '어느 쪽으로 할까요?', options: [{ label: '가' }, { label: '나' }], multi: false }], ...extra });
const A = (id, sid, status = 'pending') => ({ id, session_id: sid, status, tool: 'Bash', project: 'runshoes', target: 'git push', summary: 'push', rule: 'r' });

test('답하는 카드는 그 세션 패널에만 — 다른 세션 · 세션 없는 패널에서는 보기만', () => {
  const list = [Q(1, 251), A(2, 231), Q(3, 251, 'allowed'), Q(4, 231, 'allowed')];
  const p = apprPlace(list, 251);
  assert.deepEqual(p.mine.map((a) => a.id), [1]);
  assert.deepEqual(p.peek.map((a) => a.id), [2]);          // 런슈즈 승인은 FOREMAN 세션 패널에서 보기만
  assert.deepEqual(p.folded.map((a) => a.id), [3]);        // 다른 세션의 답한 것은 안 보인다
  const none = apprPlace(list, null);                      // 서기 · 코더 · 라운지 — 세션이 아닌 패널
  assert.deepEqual(none.mine, []);
  assert.deepEqual(none.peek.map((a) => a.id), [1, 2]);
  assert.deepEqual(none.folded, []);
  assert.deepEqual(apprPlace([Q(5, null)], null).mine.map((a) => a.id), [5]);   // 세션 모름 — 갈 패널이 없어 어디서나 답한다
});

test('보기만 하는 줄에는 답 버튼이 없고 어느 세션 것인지 적는다', () => {
  const h = apprPeekLine(Q(1, 231), st);
  assert.ok(!/data-act="(pick|answer|allow|deny|note)"/.test(h));
  assert.match(h, /data-act="open"/);
  assert.match(h, /런슈즈 · \[코더\] 세션 231/);
  assert.equal(apprWho(Q(9, null), st), 'FOREMAN · 세션 모름');
  assert.match(approvalCard(Q(1, 251), st), /FOREMAN · \[디자이너\] 세션 251/);
});

test('답한 카드는 한 줄 — ✓ 답함 「질문」 → 고른 답, 누르면 펼침, [×]', () => {
  const a = Q(7, 251, 'allowed', { message: '어느 쪽으로 할까요? → 나 · 글: 이유는 이렇다', decided_by: 'browser' });
  assert.equal(apprAnswer(a), '나 · 글: 이유는 이렇다');
  const h = apprFoldLine(a, st);
  assert.match(h, /✓ 답함<\/span> 「어느 쪽으로 할까요\?」 → <b>나 · 글: 이유는 이렇다<\/b>/);
  assert.match(h, /data-act="fold"/);
  assert.match(h, /data-act="dismiss"/);
  assert.ok(!/class="appr appr-ask/.test(h));               // 접힌 채로는 카드 본문이 없다
  assert.match(apprFoldLine(Q(8, 251, 'terminal'), st), /터미널에서 답함/);
  assert.match(apprFoldLine({ ...A(9, 251, 'denied') }, st), /✕ 거부함<\/span> ▶ push/);
});

test('질문 카드에 글 칸 · [글만 보내기] — 글이 있어야 켜진다', () => {
  NOTES.delete(1);
  let h = approvalCard(Q(1, 251), st);
  assert.match(h, /<textarea class="appr-note" data-note-aid="1"/);
  assert.match(h, /data-act="note" class="ghost small" disabled/);
  NOTES.set(1, '이것도 같이');
  h = approvalCard(Q(1, 251), st);
  assert.ok(!/data-act="note" class="ghost small" disabled/.test(h));
  NOTES.delete(1);
  assert.ok(!/appr-note/.test(approvalCard(Q(1, 251, 'allowed'), st)));   // 답한 뒤에는 글 칸이 없다
});

test('세션마다 답한 줄은 최근 FOLD_KEEP개만 — 기다리는 것 · 다른 세션은 그대로', () => {
  const m = new Map();
  for (let i = 1; i <= FOLD_KEEP + 2; i++) m.set(i, Q(i, 251, 'allowed'));
  m.set(100, Q(100, 251));
  m.set(101, Q(101, 231, 'allowed'));
  pruneResolved(m, 251);
  assert.deepEqual([...m.keys()].sort((a, b) => a - b), [3, 4, 5, 100, 101]);
});
