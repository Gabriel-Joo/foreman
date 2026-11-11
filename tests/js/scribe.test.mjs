// 서기 화면(D2, 11-11) — 한 목록 · 밀린 수 옆 표시 · 받은 할 일 숫자만 · 게시 둘로 · 못 읽으면 「읽지 못했습니다」
import test from 'node:test';
import assert from 'node:assert/strict';
import { createScribe, behindText, pubCounts, ORDER } from '../../bridge/static/js/scribe.js';

const TASKS = { retro: { title: '회고 쓰기', desc: 'r' }, doccheck: { title: '문서 점검', desc: 'd' }, readme: { title: 'README 갱신', desc: 'm' },
  trim: { title: 'CLAUDE.md 정리', desc: 't' }, later: { title: '나중에 할 일 정리', desc: 'l' }, docfix: { title: '문서 고치기', desc: 'f' },
  portfolio: { title: '포트폴리오 쓰기', desc: 'p' } };

function mk(projects, pub, { todoOk = true, pubOk = true } = {}) {
  globalThis.fetch = async (u) => {
    if (u === '/api/scribe/todo') return { ok: todoOk, json: async () => ({ tasks: TASKS, projects }) };
    return { ok: pubOk, json: async () => pub };
  };
  const store = { headers: () => ({}), touch() {} };
  return createScribe(store);
}
const settle = () => new Promise((r) => setTimeout(r, 5));

const PJ = {
  items: [], open: [], blocked: {}, nudge: null, topics: [
    { slug: 'a', title: '글 A', about: 'x', written: true, blocked: null, last_at: '2026-11-08T08:00:00+09:00', since: 208 },
    { slug: 'b', title: '글 B', about: 'y', written: true, blocked: null, last_at: '2026-11-09T08:00:00+09:00', since: 12 }],
  portfolio: { written: 2, total: 2, last_at: '2026-11-09T08:00:00+09:00', since: 12, unread: null },
  behind: { readme: { n: 13, stale: true, unit: '커밋', why: '' }, doccheck: { n: 0, stale: false }, trim: { n: 0, stale: false }, retro: { n: 3, stale: false }, later: { n: 0, stale: false } },
  inbox: { n: 3, oldest_days: 2 }, report: { name: 'doccheck_20261110.md', fixed: false },
  docs_pub: { total: 16, published: 14, new: 1, changed: 1, deleted: 0, broken: 0, behind_commits: 4, last: { at: 1.7e9, done: 2, held: 0, failed: 1, failed_first: 'docs/a.md: 거부' } },
  pub_error: null, port_pub: null,
};

test('밀린 수는 이름 옆에 — 없으면 이름만, 못 읽으면 읽지 못했습니다', () => {
  assert.equal(behindText('readme', { n: 13, stale: true }).text, '13개 밀림');
  assert.equal(behindText('readme', { n: 3, stale: false }).text, '3개 쌓임');
  assert.equal(behindText('readme', { n: 0, stale: false }).text, '');
  assert.equal(behindText('trim', { n: 4, stale: true }).text, '4줄 넘음');
  assert.equal(behindText('readme', { n: null, unread: 'git 기록을 읽지 못했습니다' }).text, '읽지 못했습니다');
  assert.equal(behindText('readme', undefined).text, '');
  assert.equal(pubCounts(null).text, '읽지 못했습니다');
  assert.equal(pubCounts({ published: 10, new: 0, changed: 0 }).text, '게시됨 10');
});

test('한 목록 — 메뉴 다섯이 한 줄씩이고 「문서 할 일」 · 「시킬 일」 칸은 없다', async () => {
  const sc = mk({ foreman: PJ }, { enabled: true, docs: [{ path: 'portfolio/a.md', status: 'published', changed: false }] });
  sc.html('foreman', 'FOREMAN'); await settle();
  const h = sc.html('foreman', 'FOREMAN');
  assert.deepEqual(ORDER.length, 5);
  for (const k of ORDER) assert.ok(h.includes(`data-sc-task="${k}"`), k);
  assert.ok(!h.includes('문서 할 일') && !h.includes('<b>시킬 일</b>'));
  assert.match(h, /README 갱신<\/b> <span class="warn"[^>]*>— 13개 밀림/);
  assert.ok(!/data-sc-task="docfix"[^>]*data-topic=""/.test(h));
  assert.ok(h.includes('밀린 것 1'));
});

test('받은 할 일은 숫자만 — 단추가 없다', async () => {
  const sc = mk({ foreman: PJ }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  const line = h.split('\n').join(' ').match(/<div class="small sc-line"[^>]*><b>받은 할 일 3개<\/b>.*?<\/div>/)[0];
  assert.ok(line.includes('2일째') && !line.includes('<button'));
});

test('포트폴리오 쓰기 — 마지막 쓴 시각 · 그 뒤 커밋 수 · [갱신]은 가장 옛 글을 고른다', async () => {
  const sc = mk({ foreman: PJ }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.match(h, /2\/2 씀/);
  assert.match(h, /그 뒤 커밋 <\/span><span class="muted">12개/);
  assert.match(h, /data-sc-task="portfolio" data-topic="a"[^>]*title="갱신 — 가장 옛 글 「글 A」\(그 뒤 커밋 208개\)/);
});

test('포트폴리오 읽기 실패는 0이 아니라 읽지 못했습니다', async () => {
  const pj = { ...PJ, portfolio: { written: 2, total: 2, last_at: null, since: null, unread: '커밋 기록을 읽지 못했습니다' },
    topics: PJ.topics.map((t) => ({ ...t, since: null })) };
  const sc = mk({ foreman: pj }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.ok(h.includes('커밋 기록을 읽지 못했습니다'));
  assert.ok(h.includes("disabled title=\"갱신 — 지금 고쳐 쓰게 할 글이 없습니다"));        // [갱신]은 고를 글이 없어 꺼진다
});

test('Notion 게시는 둘 — 포트폴리오 게시(접힘, 게시됨 N)와 기술문서 게시(숫자 · 마지막 맞춤)', async () => {
  const docs = Array.from({ length: 10 }, (_, i) => ({ path: `portfolio/${i}.md`, status: 'published', changed: false }));
  const sc = mk({ foreman: PJ }, { enabled: true, docs });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.match(h, /<b>포트폴리오 게시<\/b> <span class="muted">게시됨 10<\/span>/);
  assert.ok(!/<details class="hand"[^>]*data-keep="scribe:foreman:pubport"[^>]* open/.test(h));      // 접힘이 기본
  assert.match(h, /<b>기술문서 게시<\/b> <span class="warn">게시됨 14 · 새 1 · 바뀜 1<\/span>/);
  assert.ok(h.includes('push 대기 커밋 4개') && h.includes('실패 1') && h.includes('docs/a.md: 거부'));
  assert.ok(h.includes('data-pub="docsync"'));
});

test('펫퍼민트처럼 기술문서만이면 포트폴리오 게시는 연결 안 됨, 게시 상태를 못 읽으면 읽지 못했습니다', async () => {
  const pm = { ...PJ, topics: [], portfolio: null, docs_pub: null, pub_error: 'NotionError: 401' };
  const sc = mk({ petmint: pm }, { enabled: true, docs: [] });
  sc.html('petmint', 'P'); await settle();
  const h = sc.html('petmint', 'P');
  assert.ok(h.includes('포트폴리오를 게시하지 않습니다'));
  assert.match(h, /기술문서 게시<\/b> — 게시 상태를 읽지 못했습니다\(NotionError: 401\)/);
});

test('물어보기 답 · 문서 점검 결과에서 바로 고치기', async () => {
  const sc = mk({ foreman: PJ }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.match(h, /data-sc-task="docfix" data-topic="doccheck_20261110.md"/);
  assert.ok(!h.includes('data-sc-fix'));                              // 답이 없으면 답에서 고치기 단추도 없다
  const done = mk({ foreman: { ...PJ, report: { name: 'doccheck_20261110.md', fixed: true } } }, { enabled: true, docs: [] });
  done.html('foreman', 'F'); await settle();
  assert.ok(done.html('foreman', 'F').includes('고쳐서 합쳤습니다'));
});

test('할 일을 못 읽으면 읽는 중이 아니라 읽지 못했습니다', async () => {
  const sc = mk({}, null, { todoOk: false, pubOk: false });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.ok(h.includes('할 일을 읽지 못했습니다'));
});
