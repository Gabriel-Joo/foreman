// 한 방 볼 때 경고 배너의 줄바꿈(11-09) — 폭을 넘으면 자르지 않고 낱말 단위로 줄을 나눈다. 줄 수만큼 배너가 높아지고 방이 내려간다
import test from 'node:test';
import assert from 'node:assert/strict';
import { wrapWords } from '../../bridge/static/js/wrap.js';

const m = (s) => s.length * 10;          // 한 글자 10px

test('폭 안이면 한 줄 그대로', () => {
  assert.deepEqual(wrapWords('⏸ 배포 승인 기다림', 200, m), ['⏸ 배포 승인 기다림']);
});

test('폭을 넘으면 낱말 단위로 두 줄', () => {
  const out = wrapWords('⏸ 배포 승인 기다림', 80, m);
  assert.deepEqual(out, ['⏸ 배포 승인', '기다림']);
  assert.ok(out.every((l) => m(l) <= 80));
});

test('띄어쓰기가 없으면 여는 괄호 앞에서 — 괄호 하나만 남지 않게', () => {
  assert.deepEqual(wrapWords('라운지(떠돌이)', 60, m), ['라운지', '(떠돌이)']);
});

test('낱말 하나가 폭보다 길면 글자로 자른다 — 글을 잃지 않는다', () => {
  const t = '파이프라인실패진행중입니다';
  const out = wrapWords(t, 50, m);
  assert.ok(out.every((l) => m(l) <= 50));
  assert.equal(out.join(''), t);
});
