// 뒤에서 도는 일 이름표 줄 · 호버(11-14) — 오래 되면 경과, 출력이 멈췄으면 「출력 멈춤」, Monitor는 정상
import test from 'node:test';
import assert from 'node:assert/strict';
import { elapsedText, bgItem, bgLine, bgTip } from '../../bridge/static/js/render.js';

const NOW = Date.parse('2026-11-14T08:00:00Z');
const ago = (min) => new Date(NOW - min * 60000).toISOString();
const x = (since, changed, tool = 'Bash') => ({ task: 't', tool, description: 'pytest', since: ago(since), out_changed: changed == null ? null : ago(changed) });

test('경과 글', () => {
  assert.deepEqual([5, 60, 130, 25 * 60].map((m) => elapsedText(m * 60000)), ['5분', '1시간', '2시간 10분', '1일 1시간']);
});

test('짧은 일은 수만, 오래 되면 경과, 출력이 멈췄으면 「출력 멈춤」', () => {
  assert.deepEqual(bgLine([x(10, 9)], NOW), { text: '뒤에서 도는 일 1', stalled: false });
  assert.deepEqual(bgLine([x(130, 1)], NOW), { text: '뒤에서 도는 일 1 · 2시간 10분째', stalled: false });
  assert.deepEqual(bgLine([x(120, 100)], NOW), { text: '뒤에서 도는 일 1 · 2시간째 · 출력 멈춤', stalled: true });
  assert.equal(bgLine([x(60, null), x(5, 5)], NOW).text, '뒤에서 도는 일 2 · 1시간째');
});

test('Monitor는 오래 돌아도 멈춘 것으로 보지 않는다', () => {
  assert.deepEqual(bgLine([x(300, 300, 'Monitor')], NOW), { text: '뒤에서 도는 일 1', stalled: false });
  assert.ok(bgTip(x(300, null, 'Monitor'), NOW).includes('정상'));
});

test('호버 — 시작 시각 · 경과 · 출력 마지막 변경', () => {
  const t = bgTip(x(120, 100), NOW);
  assert.ok(t.includes('2시간째') && t.includes('출력 마지막 변경 1시간 40분 전'), t);
  assert.ok(bgTip(x(60, null), NOW).includes('출력 파일을 찾지 못했습니다'));
  assert.equal(bgItem(x(60, null), NOW).quiet, false);
});
