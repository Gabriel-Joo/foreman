// 세션 역할 이름표(11-09) — 제목 앞 역할 배지 · 캐릭터 이름표는 역할만 · 아래 줄은 캐릭터 이름에서 역할을 뗀 나머지
import test from 'node:test';
import assert from 'node:assert/strict';
import { roleLabel, roleTag, roleBadge, sessionSub, sessionName, SESSION_ROLES, ROLE_LABEL } from '../../bridge/static/js/render.js';
import { ROLE_PICK } from '../../bridge/static/js/modelpick.js';

test('세션 역할 여섯은 모두 화면 이름이 있다 — 서기 · 관리자 · 디자이너 포함', () => {
  assert.deepEqual(SESSION_ROLES, ['coder', 'designer', 'manager', 'scribe', 'inspector', 'cicd']);
  for (const r of SESSION_ROLES) assert.ok(ROLE_LABEL[r], r);
  for (const r of SESSION_ROLES) assert.ok(ROLE_PICK[r], `[＋ 세션] · 계획 카드 역할 칸에 ${r}`);
  assert.equal(roleLabel('scribe'), '서기');
  assert.equal(roleLabel('manager'), '관리자');
  assert.equal(roleLabel('designer'), '디자이너');
  assert.equal(roleLabel('foreman'), '감독');          // 감독실 캐릭터 몫 — 세션 역할로는 고르지 않는다
  assert.ok(!SESSION_ROLES.includes('foreman'));
});

test('이름표 글은 [역할], 모르는 역할은 [역할?]', () => {
  assert.equal(roleTag('manager'), '[관리자]');
  assert.equal(roleTag('designer'), '[디자이너]');
  assert.equal(roleTag('coder'), '[코더]');
  assert.equal(roleTag(null), '[역할?]');
  assert.equal(roleTag('boss'), '[역할?]');
});

test('역할 배지는 제목과 따로 — 제목을 고쳐도 역할이 남는다', () => {
  const s = { id: 230, role: 'manager', title: '자동 제목', custom_title: null };
  const before = roleBadge(s);
  s.custom_title = '[코더] 사람이 고친 제목';             // 제목 글자에 역할처럼 써도 역할은 role에서만
  assert.equal(roleBadge(s), before);
  assert.match(before, /role-manager/);
  assert.match(before, />관리자</);
  assert.equal(sessionName(s), '[코더] 사람이 고친 제목');
  assert.match(roleBadge({ role: null }), /role-none.*역할\?/);
});

test('아래 줄은 캐릭터 이름에서 역할을 뗀 나머지', () => {
  assert.equal(sessionSub({ character: '코더', role: 'coder' }), '');
  assert.equal(sessionSub({ character: '코더 foreman-3', role: 'manager' }), '따로 작업 foreman-3');
  assert.equal(sessionSub({ character: '서기 foreman-2', role: 'scribe' }), '따로 작업 foreman-2');
  assert.equal(sessionSub({ character: '디자이너 foreman-6', role: 'designer' }), '따로 작업 foreman-6');
  assert.equal(sessionSub({ character: '디자이너', role: 'designer' }), '');
  assert.match(roleBadge({ role: 'designer' }), /role-designer.*>디자이너</);
  assert.equal(sessionSub({ character: '떠돌이', role: 'coder' }), '떠돌이');
  assert.equal(sessionSub({ role: 'coder' }), '');
});
