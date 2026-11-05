// 10단계 테마 매핑 — node --test tests/js/  (pytest가 tests/test_js.py로 부른다)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { matchTool, resolveAction, infraAction, groupSubagents, tokenRate, viewState, bgCount } from '../../bridge/static/js/theme.js';

test('기다림 — IDLE인데 서브에이전트 · 백그라운드가 돌면 WAITING, 자는 모습으로 떨어지지 않는다(11-06)', () => {
  const s = { state: 'IDLE', subagents_running: 0, background: [{ task: 'b1', tool: 'Bash' }] };
  assert.equal(bgCount(s), 1);
  assert.equal(viewState(s), 'WAITING');
  assert.equal(viewState({ ...s, background: [] }), 'IDLE');
  assert.equal(viewState({ ...s, background: [], subagents_running: 2 }), 'WAITING');
  assert.equal(viewState({ ...s, state: 'ACTIVE' }), 'ACTIVE');            // 일하는 중은 그대로
  assert.equal(viewState({ ...s, state: 'SUSPENDED' }), 'SUSPENDED');      // 멈춘 세션은 멈춤
  for (const name of ['plain', 'office', 'magic', 'site']) {
    const t = JSON.parse(readFileSync(new URL(`../../bridge/static/themes/${name}/theme.json`, import.meta.url)));
    const a = resolveAction(t, { state: 'WAITING', tool: 'Bash' });
    assert.equal(a.anim, 'wait', name);
    assert.equal(a.go, 'desk', name);
    assert.ok(!a.variants, name);                                            // 쉼 변형(엎드려 자기)이 섞이지 않는다
  }
  assert.equal(resolveAction({ states: { IDLE: { anim: 'sleep' } } }, { state: 'WAITING' }).anim, 'wait');   // 테마에 없어도
});

const theme = JSON.parse(readFileSync(new URL('../../bridge/static/themes/plain/theme.json', import.meta.url)));

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

// ── 10d 마법학교 — 같은 렌더러, 다른 theme.json. 규칙이 Bash 명령(target)까지 본다 ──
const magic = JSON.parse(readFileSync(new URL('../../bridge/static/themes/magic/theme.json', import.meta.url)));

test('마법학교: 도구 → 구역 9개', () => {
  const go = (tool, target) => resolveAction(magic, { state: 'ACTIVE', tool, target }).go;
  assert.equal(go('Read'), 'library');
  assert.equal(go('Edit'), 'desk');
  assert.equal(go('Bash', '.venv/bin/pytest -q tests/'), 'test');
  assert.equal(go('Bash', 'cd x && node --test tests/js/'), 'test');
  assert.equal(go('Bash', 'git status --short'), 'seal');
  assert.equal(go('Bash', 'cd ~/r && git push -q'), 'seal');
  assert.equal(go('Bash', 'echo "git is fine"'), 'potion');      // 명령 자리의 git만
  assert.equal(go('Bash', 'ls -la'), 'potion');
  assert.equal(go('Bash'), 'potion');                            // 대상을 모르면 일반
  assert.equal(go('WebFetch'), 'window');
  assert.equal(go('Agent'), 'circle');
  assert.equal(resolveAction(magic, { state: 'IDLE' }).go, 'hall');
  assert.equal(resolveAction(magic, { state: 'SUSPENDED' }).fx, 'stone');
  assert.equal(resolveAction(magic, { state: 'DORMANT' }).fx, 'faded');   // 11-05 — 푸른 유령은 얼음(멈춤)과 헷갈려 흐리게만
  assert.equal(resolveAction(magic, { state: 'ACTIVE', tool: 'Bash', target: 'pytest', flags: { approval_pending: true } }).anim, 'raise_wand');
});

const sheetThemes = ['magic', 'office', 'site'].map((n) => {
  try { return JSON.parse(readFileSync(new URL(`../../bridge/static/themes/${n}/theme.json`, import.meta.url))); } catch { return null; }
}).filter(Boolean);

for (const th of sheetThemes) {
  test(`${th.name}: 모든 go에 구역이 있고, 장식 · 소품 · 캐릭터 · 감독실이 정의된 스프라이트를 쓴다`, () => {
    const z = th.layout.zones, defs = th.sprites.defs, ch = th.sprites.chars;
    for (const r of th.tools) assert.ok(r.go === 'desk' || z[r.go], r.go);
    for (const st of Object.values(th.states)) assert.ok(st.go === 'desk' || z[st.go], st.go);
    const all = [...th.sprites.decor, ...((th.hq && th.hq.decor) || []), ...Object.values(th.sprites.infra_decor).filter(Array.isArray).flat()];
    for (const d of all) if (d.s) assert.ok(defs[d.s], d.s);
    for (const p of Object.values(th.sprites.props)) if (p.s) assert.ok(defs[p.s], p.s);
    for (const def of Object.values(defs)) assert.ok(th.sprites.sheets[def[0]], def[0]);
    const fl = th.sprites.room.floor;
    if (fl) for (const s of fl) assert.ok(defs[s], s); else assert.ok(th.sprites.room.proc.floor, 'proc floor');
    if (ch.kind === 'static') for (const n of [...ch.pool, ch.foreman, ...Object.values(ch.infra)]) assert.ok(ch.list[n] || defs[n], n);
    for (const s of Object.values(z)) if (s && s.seats) for (const p of s.seats) assert.ok(p[0] > 0 && p[0] < th.layout.room.w && p[1] > 1 && p[1] < th.layout.room.h, JSON.stringify(p));
    assert.ok(th.hq && th.hq.board, 'hq.board');
  });

  test(`${th.name}: 도구 → 구역(테스트 · git은 명령으로)`, () => {
    const go = (tool, target) => resolveAction(th, { state: 'ACTIVE', tool, target }).go;
    assert.notEqual(go('Bash', 'pytest -q'), go('Bash', 'ls'));
    assert.notEqual(go('Bash', 'git status'), go('Bash', 'ls'));
    assert.notEqual(go('Read'), go('Edit'));
    assert.ok(z0(th, go('Agent')), 'Agent 구역');
  });
}
function z0(th, name) { return th.layout.zones[name]; }

test('잘못된 target 정규식은 안 맞는 것으로', () => {
  const t = { states: { ACTIVE: { go: 'desk' } }, tools: [{ match: 'Bash', target: '(', go: 'x' }, { match: '*', go: 'y' }] };
  assert.equal(resolveAction(t, { state: 'ACTIVE', tool: 'Bash', target: 'ls' }).go, 'y');
});

test('역할 색 이름은 DB · 디스패처와 같다(11-05 — 전에는 lead · builder …라 실제 세션 색이 한 번도 안 맞았다)', () => {
  const ROLES = ['foreman', 'coder', 'inspector', 'cicd', 'helper'];
  for (const name of ['office', 'magic', 'site', 'plain']) {
    const t = JSON.parse(readFileSync(new URL(`../../bridge/static/themes/${name}/theme.json`, import.meta.url)));
    assert.deepEqual(Object.keys(t.roles.colors).sort(), [...ROLES].sort(), name);
  }
});
