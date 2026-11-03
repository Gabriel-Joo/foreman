// 10단계 테마 매핑 — node --test tests/js/  (pytest가 tests/test_js.py로 부른다)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { matchTool, resolveAction, infraAction, groupSubagents, tokenRate } from '../../bridge/static/js/theme.js';

const theme = JSON.parse(readFileSync(new URL('../../bridge/static/themes/office/theme.json', import.meta.url)));

test('도구 패턴', () => {
  assert.ok(matchTool('Read|Grep', 'Grep'));
  assert.ok(!matchTool('Read|Grep', 'ReadMe'));
  assert.ok(matchTool('mcp__*', 'mcp__codex__ask'));
  assert.ok(matchTool('*', 'Anything'));
  assert.ok(!matchTool('Bash', null));
});

test('상태가 바탕, ACTIVE일 때만 도구', () => {
  assert.equal(resolveAction(theme, { state: 'IDLE', tool: 'Bash' }).anim, 'sit');            // 쉬는 중엔 도구 무시
  const a = resolveAction(theme, { state: 'ACTIVE', tool: 'Bash' });
  assert.equal(a.go, 'server_rack');
  assert.equal(resolveAction(theme, { state: 'ACTIVE', tool: 'WebSearch' }).go, 'window');
  assert.equal(resolveAction(theme, { state: 'ACTIVE', tool: 'mcp__x__y' }).go, 'phone');
  assert.equal(resolveAction(theme, { state: 'ACTIVE', tool: 'Brand-new' }).anim, 'type');    // 기본값
  assert.equal(resolveAction(theme, { state: 'SUSPENDED' }).fx, 'frozen');
  assert.equal(resolveAction(theme, { state: 'DORMANT' }).alpha, 0.45);
});

test('플래그가 위에 덮는다 — 우선순위', () => {
  const a = resolveAction(theme, { state: 'ACTIVE', tool: 'Bash', flags: { approval_pending: true, stuck_turn: true } });
  assert.equal(a.bubble, '?');
  assert.equal(a.anim, 'raise_hand');
  assert.equal(a.go, 'server_rack');                                                            // 자리는 도구 것
  assert.equal(resolveAction(theme, { state: 'SUSPENDED', flags: { approval_pending: true } }).bubble, '?');
});

test('인프라 · 서브에이전트 묶기 · 토큰 속도', () => {
  assert.equal(infraAction(theme, 'failed').fx, 'smoke');
  assert.equal(infraAction(theme, undefined).status, 'none');
  const g = groupSubagents(Array.from({ length: 13 }, (_, i) => `Wide yes/no search wn${i}`));
  assert.equal(g.shown.length, 10);
  assert.equal(g.hidden, 3);
  assert.equal(g.label, 'Wide yes/no search');
  const h = [{ t: 0, v: 100 }, { t: 60e3, v: 150 }, { t: 120e3, v: 20 }, { t: 180e3, v: 70 }];       // 자정에 줄었다
  assert.equal(tokenRate(h, 180e3, 600e3), 100);
});
