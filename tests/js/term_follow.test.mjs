// 터미널이 방을 따라가기 · 탭마다 보이는 창(11-10)
import test from 'node:test';
import assert from 'node:assert/strict';
import { termTabId, followProject } from '../../bridge/static/js/terminal.js';

const TAB_RE = /^[A-Za-z0-9_-]{6,40}$/;   // bridge/terminal.py TAB_RE · deploy/shell/foreman-term-view와 같은 규칙

test('탭 id는 브리지 · 감싸는 스크립트가 받는 모양이고 탭마다 다르다', () => {
  const a = termTabId(), b = termTabId();
  assert.match(a, TAB_RE);
  assert.notEqual(a, b);
  assert.match(termTabId(() => 0.999999), TAB_RE);
  assert.match(termTabId(() => 0), TAB_RE);
});

test('방이면 그 프로젝트, 방이 아니면(감독실 · 전체 · 라운지) 고른 세션의 프로젝트, 없으면 FOREMAN 창', () => {
  assert.equal(followProject(() => 'runshoes'), 'runshoes');
  assert.equal(followProject(() => 'petmint-rag-chatbot'), 'petmint-rag-chatbot');
  assert.equal(followProject(() => null), 'foreman');
  assert.equal(followProject(() => 'other-repo'), 'foreman');    // 터미널 창이 없는 프로젝트
  assert.equal(followProject(undefined), null);                  // 대시보드 — 따라가지 않는다
});
