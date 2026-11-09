// [＋ 할 일] 목록 한 줄(11-09) — 사용자 지시서는 ━━━ 줄로 시작하는 일이 많다. 그 줄을 건너뛰고 첫 글 줄을 보인다
import test from 'node:test';
import assert from 'node:assert/strict';
import { firstLine } from '../../bridge/static/js/todoinbox.js';

test('구분선은 건너뛰고 첫 글 줄, 길면 자른다', () => {
  assert.equal(firstLine('━━━━━━━━\n질문 카드 — 답한 뒤에도 자리를 먹는다\n━━━━'), '질문 카드 — 답한 뒤에도 자리를 먹는다');
  assert.equal(firstLine('\n\n  터미널 입력 칸  \n둘째'), '터미널 입력 칸');
  assert.equal(firstLine('가'.repeat(80), 10), '가'.repeat(9) + '…');
  assert.equal(firstLine(''), '');
});
