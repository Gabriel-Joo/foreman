// 패널 머리줄 모델 창(「이 세션의 모델」, 11-14 사용자) — 버전별 목록 · 지금 모델 표시 · 창 글
import test from 'node:test';
import assert from 'node:assert/strict';
import { modelMenuHtml, sameModel, modelOptions } from '../../bridge/static/js/modelpick.js';

const M = {
  choices: [
    { id: 'claude-opus-5-5', label: 'Opus 5.5', note: '가장 잘하지만 비쌉니다' },
    { id: 'claude-opus-5', label: 'Opus 5', note: 'Opus 5.5의 앞 버전입니다' },
    { id: 'claude-fable-5-2', label: 'Fable 5.2', note: '가장 비싸고, 주간 한도가 따로 있습니다' },
  ],
  defaults: { coder: 'claude-opus-5-5' },
  aliases: { opus: 'claude-opus-5-5' },
};

test('같은 모델 — 버전까지 가른다, 날짜 꼬리는 같다', () => {
  assert.equal(sameModel('claude-opus-5-5', 'claude-opus-5-5'), true);
  assert.equal(sameModel('claude-opus-5-5', 'claude-opus-5'), false);      // 전에는 family로 맞춰 둘 다 「지금」이었다
  assert.equal(sameModel('claude-opus-5', 'claude-opus-5-5'), false);
  assert.equal(sameModel('claude-haiku-4-5-20251001', 'claude-haiku-4-5'), true);
  assert.equal(sameModel(null, 'claude-opus-5'), false);
});

test('창 글 — 사용자가 고친 글, 속 이야기 · 가운뎃점 없음', () => {
  const h = modelMenuHtml(M, 'claude-opus-5', false);
  assert.match(h, /<div class="mdl-head">이 세션의 모델<\/div>/);
  assert.doesNotMatch(h, /\/model|브리지가 대신|되돌립니다|·/);
  assert.match(h, /토큰이 더 들 수 있습니다\./);
  assert.match(h, /다른 세션은 바뀌지 않습니다\. 이 세션이 이어지는 동안에는 바꾼 모델을 씁니다\./);
  assert.match(h, /바뀐 모델이 적용됩니다\.<\/div><div class="small muted">\[\+ 세션\]으로 따로 띄우는 세션은 이 값을 따르지 않습니다\./);
  assert.doesNotMatch(h, /이 세션만 바뀝니다/);
  // 지금 모델은 Opus 5 하나만
  assert.equal((h.match(/class="cur"/g) || []).length, 1);
  assert.match(h, /data-id="claude-opus-5" data-label="Opus 5" class="cur"><span><b>Opus 5<\/b> <span class="muted">\(지금\)<\/span>/);
  assert.match(h, /Fable 5\.2/);
  assert.doesNotMatch(h, /작업 중입니다/);
  assert.match(modelMenuHtml(M, null, true), /작업 중입니다\. 대기열에 들어가/);
});

test('계획 카드 목록 — 11-14 전 별칭 값도 그 칸을 고른다', () => {
  const h = modelOptions(M, 'opus', 'coder');
  assert.match(h, /<option value="claude-opus-5-5" selected/);
  assert.match(h, /Opus 5\.5 \(역할 기본\)/);
  assert.match(modelOptions(M, '', 'coder'), /<option value="" selected>CC 설정 따르기/);
});
