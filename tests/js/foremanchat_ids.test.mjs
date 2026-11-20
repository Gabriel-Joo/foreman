import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// 11-20 감독 창은 한 상자(box) 안에 「이 방 세션을 새 세션으로 옮기기」 목록과 계획 카드를 함께 그리고, 요소를 box.querySelector('#id')로
// 찾는다. 같은 id가 둘이면 DOM 차례로 먼저인 것만 잡혀 다른 쪽이 조용히 듣지 않는다(fmHand를 목록과 [관리자에게 보내기]가 같이 썼다).
// 이 시험 도구에는 DOM이 없어 실제로 그려 보지 않고, 화면 틀의 id가 겹치지 않는지와 두 화면이 각자의 id를 쓰는지를 본다
const src = readFileSync(new URL('../../bridge/static/js/foremanchat.js', import.meta.url), 'utf8');

test('감독 창 화면 틀의 id는 겹치지 않는다', () => {
  const ids = [...src.matchAll(/id="([A-Za-z0-9_]+)"/g)].map((m) => m[1]);
  const dup = ids.filter((x, i) => ids.indexOf(x) !== i);
  assert.deepEqual(dup, []);
  assert.ok(ids.includes('fmMove') && ids.includes('fmHand'));
});

test('옮기기 목록은 fmMove, 관리자에게 보내기 단추는 fmHand를 쓴다', () => {
  const draw = src.slice(src.indexOf('function drawHand()'), src.indexOf("$('fmMove').addEventListener"));
  assert.match(draw, /\$\('fmMove'\)\.innerHTML/);
  assert.doesNotMatch(draw, /\$\('fmHand'\)/);
  assert.match(src, /\$\('fmMove'\)\.addEventListener\('click'/);
  assert.match(src, /<button type="button" id="fmHand"[^>]*>관리자에게 보내기<\/button>/);
  assert.match(src, /\$\('fmHand'\)\.onclick = handOver/);
});

test('옮기기 호버의 기본 글은 지금 흐름 글(MOVE_TIP)이다', () => {
  assert.match(src, /window\.foremanHandoffTip \|\| MOVE_TIP/);
  assert.doesNotMatch(src, /지금까지를 요약해 보여 드리고/);
});
