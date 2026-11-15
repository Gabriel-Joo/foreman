// 발밑 역할 색 원(11-13 사용자) — 색은 역할 배지와 같은 한 곳(render.js ROLE_COLOR), 늘 켜 두되 쉴 때 옅게, 역할이 있는 캐릭터에만
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ROLE_COLOR, roleColorCss, SESSION_ROLES } from '../../bridge/static/js/render.js';
import { auraOf, auraStyle, AURA_STYLES, AURA_REST, AURA_OFF, poseDrop } from '../../bridge/static/js/aura.js';

test('색은 한 곳 — 세션 역할 모두와 감독에 색이 있고, 배지 CSS도 같은 값에서 만든다', () => {
  for (const r of [...SESSION_ROLES, 'foreman']) assert.match(ROLE_COLOR[r] || '', /^#[0-9a-f]{6}$/, r);
  const css = roleColorCss();
  for (const [r, c] of Object.entries(ROLE_COLOR)) assert.ok(css.includes(`.rolebadge.role-${r} { --rc:${c}; }`), r);
  // panel.css에 역할마다의 색이 다시 생기면 두 곳이 된다(역할 없음 · 기본 회색만 남긴다)
  const panel = readFileSync(new URL('../../bridge/static/css/panel.css', import.meta.url), 'utf8');
  for (const r of Object.keys(ROLE_COLOR)) assert.ok(!new RegExp(`\\.role-${r}\\s*\\{\\s*--rc`).test(panel), `panel.css에 role-${r} 색`);
});

test('누구에게 — 역할이 있는 캐릭터만, 색은 배지 색', () => {
  const s = (role, state) => ({ kind: 'session', role, s: { state } });
  assert.equal(auraOf(s('coder', 'ACTIVE')).color, ROLE_COLOR.coder);
  assert.equal(auraOf(s('manager', 'IDLE')).color, ROLE_COLOR.manager);
  assert.equal(auraOf(s(null, 'ACTIVE')), null);                       // 역할을 모름 — 경고색 원은 경고로 읽힌다
  assert.equal(auraOf({ kind: 'courier', role: undefined }), null);     // 배송 담당 · 인프라 — 배지 없는 파이프라인 캐릭터
  assert.equal(auraOf({ kind: 'infra' }), null);
  assert.equal(auraOf({ kind: 'foreman', role: 'foreman', fm: { running: false } }).color, ROLE_COLOR.foreman);
  assert.equal(auraOf({ kind: 'scribe', role: 'scribe' }).color, ROLE_COLOR.scribe);   // 세션 없는 서기
  assert.equal(auraOf({ kind: 'coder', role: 'coder' }).color, ROLE_COLOR.coder);      // 쉬는 · 돌아가는 코더
  const m = auraOf({ kind: 'mini', role: 'designer' }, 0.6);                            // 서브에이전트 — 부모 역할, 작게
  assert.equal(m.color, ROLE_COLOR.designer); assert.equal(m.s, 0.6);
});

test('늘 켜 둔다 — 일할 때 1, 쉴 때 옅게, 멈춤 · 끝남은 더 옅게(0은 아님)', () => {
  const k = (state) => auraOf({ kind: 'session', role: 'coder', s: { state } }).k;
  assert.equal(k('ACTIVE'), 1);
  assert.equal(k('IDLE'), AURA_REST);
  assert.equal(k('SUSPENDED'), AURA_OFF); assert.equal(k('DORMANT'), AURA_OFF);
  assert.ok(AURA_OFF > 0 && AURA_OFF < AURA_REST && AURA_REST < 1);
  assert.equal(auraOf({ kind: 'foreman', role: 'foreman', fm: { running: true } }).k, 1);
  assert.equal(auraOf({ kind: 'scribe', role: 'scribe' }).k, AURA_REST);
});

test('꼴 — 테마 기본 · theme.json · 주소 ?aura= 순서, 모르는 꼴은 기본으로', () => {
  assert.equal(auraStyle('magic', null, null), AURA_STYLES.magic[0]);
  assert.equal(auraStyle('office', { style: 'mat' }, null), 'mat');
  assert.equal(auraStyle('office', { style: 'mat' }, 'glow'), 'glow');
  assert.equal(auraStyle('site', null, 'rune'), AURA_STYLES.site[0]);   // 다른 테마 꼴은 안 받는다
  assert.equal(auraStyle('site', null, 'off'), 'off');
  assert.equal(auraStyle('nope', null, null), 'glow');
});

// 11-15 사용자 「조사 캐릭터만 발밑 원이 허리에 떠 있다」 — 원인은 역할이 아니라 자세: 마법학교 sleep(엎드려 자기)은 그림만 내려 그려 원이 6px 위에 떴다.
test('원 높이는 역할이 아니라 자세로만 — 그림을 내리는 값과 원을 내리는 값이 한 함수(poseDrop)', () => {
  assert.equal(poseDrop('sleep', 1.5), 6);                              // 마법학교 K 1.5에서 어긋났던 px
  assert.equal(poseDrop('sleep', 1), 4);
  for (const anim of ['idle', 'walk', 'work', 'stand', 'read', 'lie', undefined]) assert.equal(poseDrop(anim, 1.5), 0, String(anim));
  const src = readFileSync(new URL('../../bridge/static/js/office.js', import.meta.url), 'utf8');
  assert.ok(/py \+= drop/.test(src) && /poseDrop\(anim, K\)/.test(src), '그림은 poseDrop으로 내린다');
  assert.ok(/a\.y \* T \+ \(\(s && s\.drop\) \|\| 0\)/.test(src), '원도 그림이 내려앉은 만큼(SILS drop) 내린다');
  assert.ok(!/anim === 'sleep'\) py \+=/.test(src), '자세 내림 값을 office.js에 다시 따로 적지 않는다');
  // 원 높이 상수는 역할 이름으로 갈리지 않는다 — aura.js에 역할 이름이 없다(새 역할이 생겨도 같은 자리)
  const aura = readFileSync(new URL('../../bridge/static/js/aura.js', import.meta.url), 'utf8').split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
  // (auraOf의 kind === 'scribe' · 'coder'는 역할이 아니라 캐릭터 종류 — 세션 없는 서기 · 쉬는 코더 — 라 뺀다)
  for (const r of ['designer', 'inspector', 'manager', 'cicd']) assert.ok(!new RegExp(`['"]${r}['"]`).test(aura), `aura.js에 역할 ${r}`);
});
