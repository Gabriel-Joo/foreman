// 캐릭터 이름표 글자색 · 발밑 원 높이(11-14 사용자) — 이름표는 역할 배지 색, 검은 바탕에 묻히는 색만 이름표에서 밝힌다.
// 원은 발 점에(전에는 0.16칸 위 · 납작함 0.45라 원 위 끝이 허리에 걸렸다)
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ROLE_COLOR, SESSION_ROLES, contrastOf, lighten, nameInkOf, roleNameColor, roleNameInk,
         NAME_BG_WORST, NAME_MIN_CONTRAST, ROLE_NONE_COLOR, ROLE_OTHER_COLOR } from '../../bridge/static/js/render.js';
import { AURA_RX, AURA_FLAT, AURA_LIFT } from '../../bridge/static/js/aura.js';

test('대비 계산 — 검정 · 흰색 21, 같은 색 1', () => {
  assert.equal(+contrastOf('#000000', '#ffffff').toFixed(2), 21);
  assert.equal(+contrastOf('#5b9be6', '#5b9be6').toFixed(2), 1);
  assert.equal(lighten('#000000', 0.5), '#808080');
  assert.equal(lighten('#e0604f', 0), '#e0604f');
});

test('이름표 색은 배지 색 — 역할 · 역할 모름 · 배지 없는 캐릭터', () => {
  for (const r of [...SESSION_ROLES, 'foreman']) assert.equal(roleNameColor(r, true), ROLE_COLOR[r], r);
  assert.equal(roleNameColor(null, true), ROLE_NONE_COLOR);          // 세션인데 역할을 모름 — 배지 「역할?」와 같은 경고 노랑
  assert.equal(roleNameColor(undefined, false), ROLE_OTHER_COLOR);   // 배송 담당 · 인프라 — 배지 기본 회색
  assert.equal(roleNameColor('helper', true), ROLE_OTHER_COLOR);     // 색이 없는 역할 — 배지도 기본 회색
  // panel.css 값과 같아야 한다(배지와 같은 색)
  const panel = readFileSync(new URL('../../bridge/static/css/panel.css', import.meta.url), 'utf8');
  assert.ok(panel.includes(`.rolebadge.role-none { --rc:var(--warn, ${ROLE_NONE_COLOR}); }`));
  assert.ok(panel.includes(`.rolebadge { --rc:${ROLE_OTHER_COLOR};`));
});

test('묻히는 색만 밝힌다 — 가장 나쁜 바탕에서도 4.5 넘게, 이미 넘는 색은 그대로', () => {
  for (const c of [...Object.values(ROLE_COLOR), ROLE_NONE_COLOR, ROLE_OTHER_COLOR]) {
    const x = nameInkOf(c);
    assert.ok(contrastOf(x.ink, NAME_BG_WORST) >= NAME_MIN_CONTRAST, c);
    if (contrastOf(c, NAME_BG_WORST) >= NAME_MIN_CONTRAST) assert.equal(x.ink, c, `${c}는 그대로`);
    else assert.ok(x.lift > 0 && x.lift <= 0.2, `${c} 밝힘 ${x.lift}`);   // 조금만 — 역할 색으로 읽히게
  }
  // 11-14 잰 값: 관리자 빨강만 4.29 → 5% 밝힘(배지 · 원은 그대로)
  assert.deepEqual(nameInkOf(ROLE_COLOR.manager), { ink: '#e26858', lift: 0.05, ratio: 4.58 });
  assert.equal(ROLE_COLOR.manager, '#e0604f');
  assert.equal(roleNameInk('coder', true), ROLE_COLOR.coder);
});

test('발밑 원 — 가운데는 발 점, 위 끝이 발 점보다 반 칸 안쪽(허리에 걸리지 않게)', () => {
  assert.equal(AURA_LIFT, 0);
  assert.ok(AURA_RX * AURA_FLAT + AURA_LIFT <= 0.5, `원 위 끝 ${AURA_RX * AURA_FLAT + AURA_LIFT}칸`);
});
