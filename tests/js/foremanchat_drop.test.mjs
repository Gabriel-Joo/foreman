import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dropAction, freshText } from '../../bridge/static/js/foremanchat.js';

// 11-11 — 계획을 받고 세션을 띄운 뒤 창을 다시 열면 지난 글이 남아 있었다. 보낸 글은 비우고, 보내지 않은 초안은 남긴다
test('새로 열 때 입력 칸: 보낸 글은 비움 · 초안은 남김', () => {
  assert.equal(freshText(true, '런슈즈 발볼 검증 이어서'), '');
  assert.equal(freshText(false, '쓰다 만 글'), '쓰다 만 글');
  assert.equal(freshText(false, undefined), '');
  // 창을 여는 두 길(감독실 캐릭터 open · 머리줄 [＋ 세션]) 모두 fresh()를 거친다
  const src = readFileSync(new URL('../../bridge/static/js/foremanchat.js', import.meta.url), 'utf8');
  assert.match(src, /function reset\(project\) \{\s*who\(\);\s*fresh\(\);/);
  assert.match(src, /if \(on && !wasOn\) fresh\(\);/);
});

// 11-10 계획을 못 받은 뒤 [버리기]가 "disp is null"로 실패했다 — 계획이 없으면 서버를 부르지 않고 카드만 치운다
test('버리기: 계획이 없거나 이미 끝난 계획이면 카드만 치움', () => {
  assert.equal(dropAction(null), 'clear');
  assert.equal(dropAction({}), 'clear');
  assert.equal(dropAction({ dispatch_id: 7, plan: {}, status: 'started' }), 'clear');
  assert.equal(dropAction({ dispatch_id: 7, plan: {}, status: 'failed' }), 'clear');
});

test('버리기: 세운 계획(planned)만 서버에 버림을 적음', () => {
  assert.equal(dropAction({ dispatch_id: 7, plan: {} }), 'server');            // 방금 받은 계획(상태 없음 = planned)
  assert.equal(dropAction({ dispatch_id: 0, plan: {}, status: 'planned' }), 'server');
});

test('계획 카드의 display가 hidden을 덮지 않음', () => {
  const css = readFileSync(new URL('../../bridge/static/css/panel.css', import.meta.url), 'utf8');
  assert.match(css, /\.fm-plan\[hidden\]\s*\{\s*display:\s*none/);
});
