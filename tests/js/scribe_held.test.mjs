// 덮기 단추 자리(11-19 사용자 결정 S4) — 접는 칸 「할 일」을 접어 둬도 [Notion 수정 버리고 덮기]가 보이고,
// 「멈춤 N」이 보이는데 단추가 없으면 그 까닭을 쓴다(조용히 비지 않게)
import test from 'node:test';
import assert from 'node:assert/strict';
import { keepToggle, keepReset } from '../../bridge/static/js/render.js';
import { createScribe, heldRows, TECHDOC_NO_UPDATE } from '../../bridge/static/js/scribe.js';

globalThis.localStorage = (() => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) }; })();
const TASKS = { doccheck: { title: '문서 점검', desc: 'd' } };
const FORCE = { kind: 'publish', act: 'force', project: 'infra', path: 'docs/b.md', title: 'Notion에서 사람이 고친 곳 2개: docs/b.md', why: '덮지 않았습니다' };
const DOCS = (extra) => ({ src: 'docs/', total: 2, published: 2, new: 0, changed: 1, deleted: 0, broken: 0, behind_commits: 1,
  last: { at: 1, done: 0, held: 1, failed: 0, failed_first: null }, last_error: null, ...extra });
const settle = () => new Promise((r) => setTimeout(r, 5));

async function draw(pj) {
  keepReset();
  globalThis.fetch = async (u) => (u === '/api/scribe/todo'
    ? { ok: true, json: async () => ({ tasks: TASKS, projects: { infra: { open: [], blocked: {}, behind: {}, ...pj } } }) }
    : { ok: true, json: async () => ({ enabled: true, docs: [], portfolio: {} }) });
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('infra', 'I'); await settle();
  keepToggle('scribe:infra:list', false, true);           // 사람이 「할 일」 칸을 접어 둠
  return sc.html('infra', 'I');
}

test('「할 일」을 접어 둬도 덮기 단추는 칸 밖 기술문서 게시 줄 아래에 보이고, 칸 머리에 덮기 N', async () => {
  const h = await draw({ items: [FORCE], docs_pub: DOCS({ held_buttons: 1 }) });
  const list = /<details[^>]*data-keep="scribe:infra:list"[^>]*>[\s\S]*?<\/details>/.exec(h)[0];
  assert.ok(!/ open(\s|>)/.test(list.split('>')[0] + '>'), '사람이 접은 기억은 그대로');
  assert.ok(!list.includes('data-force="1"'), '단추는 접는 칸 안에 없다');
  const after = h.slice(h.indexOf(list) + list.length);
  assert.ok(after.includes('data-force="1"') && after.includes('data-path="docs/b.md"') && after.includes('Notion 수정 버리고 덮기'));
  assert.ok(list.includes('덮기 1(아래 기술문서 게시)'));
});

test('기술문서 쓰기 줄에는 [갱신] 대신 까닭 한 줄(11-19 S1)', async () => {
  const h = await draw({ items: [], docs_pub: null, techdoc: { need: 1, due: true, why: '글 3편 가운데 코드가 바뀐 편 1' } });
  const tasks = { ...TASKS, techdoc: { title: '기술문서 쓰기', desc: 't' } };
  keepReset();
  globalThis.fetch = async (u) => (u === '/api/scribe/todo'
    ? { ok: true, json: async () => ({ tasks, projects: { infra: { items: [], open: [], blocked: {}, behind: {}, techdoc: { need: 1, due: true, why: '글 3편 가운데 코드가 바뀐 편 1' } } } }) }
    : { ok: true, json: async () => ({ enabled: true, docs: [], portfolio: {} }) });
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('infra', 'I'); await settle();
  const h2 = sc.html('infra', 'I');
  assert.ok(!h.includes(TECHDOC_NO_UPDATE), '기술문서 쓰기 줄이 없으면 까닭도 없다');
  assert.ok(h2.includes(TECHDOC_NO_UPDATE));
  assert.ok(!/data-sc-task="techdoc"[^>]*>갱신</.test(h2), '기술문서 쓰기에는 [갱신] 단추가 없다(포스트잇의 [갱신]은 다른 단추)');
});

test('멈춤 N인데 덮을 편이 없거나 목록을 못 읽으면 그렇다고 쓴다', () => {
  assert.ok(heldRows({ items: [], docs_pub: DOCS({ held_buttons: 0 }) }).includes('지금 덮을 편이 없습니다'));
  assert.ok(heldRows({ items: [], docs_pub: DOCS({ held_buttons: 0, held_error: 'OSError: 끊김' }) }).includes('읽지 못했습니다'));
  assert.equal(heldRows({ items: [], docs_pub: DOCS({ last: { held: 0 }, held_buttons: 0 }) }), '');
});

test('멈춘 편 목록 자체가 없으면 「덮을 편이 없습니다」가 아니라 목록이 아직 없다고 쓴다(11-19)', () => {
  const t = heldRows({ items: [], docs_pub: DOCS({ last: { held: 5 }, held_buttons: 0, held_list_missing: 5 }) });
  assert.ok(t.includes('멈춘 5편의 목록이 아직 없습니다. 다음 맞추기 뒤에 보입니다.'));
  assert.ok(!t.includes('덮을 편이 없습니다'));
  // 목록이 있는 쪽(held_list_missing이 null)은 지금 글 그대로
  assert.ok(heldRows({ items: [], docs_pub: DOCS({ held_buttons: 0, held_list_missing: null }) }).includes('지금 덮을 편이 없습니다'));
  // 단추가 있으면 단추가 먼저
  assert.ok(heldRows({ items: [FORCE], docs_pub: DOCS({ held_buttons: 1, held_list_missing: null }) }).includes('data-force="1"'));
});
