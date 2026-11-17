// 접은 칸 기억(11-17 디자이너) — 다시 그려도 사람이 접은 대로 · 새로고침 뒤에도 · 그릴 때 난 toggle은 선택으로 안 적는다
import test from 'node:test';
import assert from 'node:assert/strict';
import { keep, keepSet, keepToggle, keepReset } from '../../bridge/static/js/render.js';
import { createScribe } from '../../bridge/static/js/scribe.js';

function fakeLs() {
  const m = new Map();
  globalThis.localStorage = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => { m.set(k, String(v)); } };
  return m;
}
const isOpen = (h) => / open(\s|>|$)/.test(h);

test('사람이 접거나 편 것은 다시 그려도 그대로, 처음값이 아니다', () => {
  fakeLs(); keepReset();
  assert.ok(isOpen(keep('a:x', true)) && !isOpen(keep('a:y', false)));
  keepToggle('a:x', false, true);          // 사람이 접음
  keepToggle('a:y', true, false);          // 사람이 폄
  assert.ok(!isOpen(keep('a:x', true)));
  assert.ok(isOpen(keep('a:y', false)));
});

test('그릴 때 브라우저가 쏘는 toggle(처음값 그대로)은 사람의 선택으로 굳히지 않는다', () => {
  fakeLs(); keepReset();
  keepToggle('b:fresh', true, true);       // dflt 펼침으로 그렸더니 toggle이 한 번 옴
  assert.ok(!keep('b:fresh', false).includes(' open'), '기록이 없으면 처음값이 바뀌면 따라간다');
  assert.ok(isOpen(keep('b:fresh', true)));
});

test('새로고침 뒤에도 유지(localStorage), 못 쓰면 이 탭에서만', () => {
  const ls = fakeLs(); keepReset();
  keepToggle('c:z', false, true);
  assert.ok(ls.get('foremanDetails').includes('"c:z":false'));
  keepReset();                              // 새로고침
  assert.ok(!isOpen(keep('c:z', true)));
  delete globalThis.localStorage; keepReset();   // 막힌 브라우저
  keepToggle('c:q', true, false);
  assert.ok(isOpen(keep('c:q', false)));
});

test('오래된 기록은 200개를 넘으면 앞에서부터 버린다', () => {
  fakeLs(); keepReset();
  for (let i = 0; i < 205; i++) keepSet(`d:${i}`, true);
  assert.ok(!isOpen(keep('d:0', false)) && isOpen(keep('d:204', false)));
});

// ── 서기실 ──
const TASKS = { doccheck: { title: '문서 점검', desc: 'd' }, trim: { title: 'CLAUDE.md 정리', desc: 't' }, later: { title: '알려진 한계 쓰기', desc: 'l' } };
function mk() {
  globalThis.fetch = async (u) => (u === '/api/scribe/todo'
    ? { ok: true, json: async () => ({ tasks: TASKS, projects: { foreman: { items: [], open: [], blocked: {}, behind: {} } } }) }
    : { ok: true, json: async () => ({ enabled: true, docs: [], portfolio: {} }) });
  globalThis.confirm = () => true;
  return createScribe({ headers: () => ({}), touch() {} });
}
const settle = () => new Promise((r) => setTimeout(r, 5));
const fold = (h, k) => new RegExp(`<details[^>]*data-keep="scribe:foreman:${k}"[^>]*>`).exec(h)[0];

test('서기실 물어보기 · 할 일 칸은 접으면 다시 그려도 접힌 채', async () => {
  fakeLs(); keepReset();
  const sc = mk(); sc.html('foreman', 'F'); await settle();
  let h = sc.html('foreman', 'F');
  assert.ok(isOpen(fold(h, 'ask')) && isOpen(fold(h, 'list')));
  keepToggle('scribe:foreman:ask', false, true);
  keepToggle('scribe:foreman:list', false, true);
  h = sc.html('foreman', 'F');
  assert.ok(!isOpen(fold(h, 'ask')) && !isOpen(fold(h, 'list')));
});

test('고른 일(pick)로 열면 할 일 칸을 한 번만 펴고, 사람이 접으면 다음 그림에서 도로 펴지 않는다', async () => {
  fakeLs(); keepReset();
  const sc = mk(); sc.html('foreman', 'F'); await settle();
  keepToggle('scribe:foreman:list', false, true);
  assert.ok(isOpen(fold(sc.html('foreman', 'F', 'later'), 'list')));      // 새로 고르면 펴진다
  keepToggle('scribe:foreman:list', false, true);                         // 사람이 접음
  assert.ok(!isOpen(fold(sc.html('foreman', 'F', 'later'), 'list')));     // 같은 pick으로 다시 그려도 접힌 채
});

test('물어본 답은 [답 닫기]로 닫고, 물은 글은 칸에 남는다', async () => {
  fakeLs(); keepReset();
  const sc = mk();
  globalThis.fetch = async (u, o) => (u === '/api/scribe/ask'
    ? { ok: true, json: async () => ({ answer: '답입니다' }) }
    : u === '/api/scribe/todo' ? { ok: true, json: async () => ({ tasks: TASKS, projects: { foreman: { items: [], open: [], blocked: {}, behind: {} } } }) }
      : { ok: true, json: async () => ({ enabled: true, docs: [], portfolio: {} }) });
  sc.html('foreman', 'F'); await settle();
  sc.onInput({ target: { id: 'scAskText', value: '물어볼 글' } }, 'foreman');
  const ask = { target: { closest: (s) => (s === '[data-sc-ask]' ? {} : null) }, preventDefault() {} };
  await sc.onClick(ask, 'foreman', 'F');
  let h = sc.html('foreman', 'F');
  assert.ok(h.includes('답입니다') && h.includes('data-sc-close="ask"'));
  const close = { target: { closest: (s) => (s === '[data-sc-close]' ? {} : null) }, preventDefault() {} };
  await sc.onClick(close, 'foreman', 'F');
  h = sc.html('foreman', 'F');
  assert.ok(!h.includes('답입니다') && !h.includes('data-sc-close'));
  assert.ok(h.includes('물어볼 글'));
});

test('「올린 기록 없음」은 무엇이 없는지 말한다', async () => {
  fakeLs(); keepReset();
  globalThis.fetch = async (u) => (u === '/api/scribe/todo'
    ? { ok: true, json: async () => ({ tasks: TASKS, projects: { foreman: { items: [], open: [], blocked: {}, behind: {},
      docs_pub: { src: 'docs/', total: 3, published: 0, new: 3, changed: 0, deleted: 0, broken: 0, behind_commits: null, last: null, last_error: null } } } }) }
    : { ok: true, json: async () => ({ enabled: true, docs: [], portfolio: {} }) });
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.ok(h.includes('Notion에 올린 기록이 없습니다') && !h.includes('아직 올린 기록 없음'));
});
