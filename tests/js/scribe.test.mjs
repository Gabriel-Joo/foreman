// 서기 화면(D2, 11-11) — 한 목록 · 밀린 수 옆 표시 · 받은 할 일 숫자만 · 게시 둘로 · 못 읽으면 「읽지 못했습니다」
import test from 'node:test';
import assert from 'node:assert/strict';
import { createScribe, behindText, pubCounts, piecesText, techdocAsk, ORDER } from '../../bridge/static/js/scribe.js';

const TASKS = { doccheck: { title: '문서 점검', desc: 'd' },
  trim: { title: 'CLAUDE.md 정리', desc: 't' }, later: { title: '알려진 한계 쓰기', desc: 'l' }, docfix: { title: '문서 고치기', desc: 'f' },
  portfolio: { title: '포트폴리오 쓰기', desc: 'p' }, techdoc: { title: '기술문서 쓰기', desc: 'k' } };

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
  items: [], open: [], blocked: {}, nudge: null, techdoc: null, topics: [
    { slug: '01_a', title: '글 A', written: true, blocked: null, commits: 3, why: null, read: 'abc1234' },
    { slug: '02_b', title: '글 B', written: true, blocked: null, commits: 0, why: null, read: 'abc1234' },
    { slug: '03_c', title: '글 C', written: true, blocked: null, commits: null, why: '머리 주석이 없습니다', read: null }],
  portfolio: { total: 3, changed: 1, unknown: 1, written: 3, blocked: null, unread: null },
  behind: { doccheck: { n: 0, stale: false }, trim: { n: 0, stale: false }, later: { n: 13, stale: true, unit: '건', why: '' } },
  inbox: { n: 3, oldest_days: 2 }, report: { name: 'doccheck_20261110.md', fixed: false },
  docs_pub: { total: 16, published: 14, new: 1, changed: 1, deleted: 0, broken: 0, behind_commits: 4, last: { at: 1.7e9, done: 2, held: 0, failed: 1, failed_first: 'docs/a.md: 거부' } },
  pub_error: null, port_pub: null,
};

test('밀린 수는 이름 옆에 — 없으면 이름만, 못 읽으면 읽지 못했습니다', () => {
  assert.equal(behindText('later', { n: 13, stale: true }).text, '13개 밀림');
  assert.equal(behindText('later', { n: 3, stale: false }).text, '3개 쌓임');
  assert.equal(behindText('later', { n: 0, stale: false }).text, '');
  assert.equal(behindText('trim', { n: 4, stale: true }).text, '4줄 넘음');
  assert.equal(behindText('later', { n: null, unread: 'git 기록을 읽지 못했습니다' }).text, '읽지 못했습니다');
  assert.equal(behindText('later', undefined).text, '');
  assert.equal(pubCounts(null).text, '읽지 못했습니다');
  assert.equal(pubCounts({ published: 10, new: 0, changed: 0 }).text, '게시됨 10');
});

test('한 목록 — 메뉴 셋이 한 줄씩이고 「문서 할 일」 · 「시킬 일」 칸은 없다', async () => {
  const sc = mk({ foreman: PJ }, { enabled: true, docs: [{ path: 'portfolio/a.md', status: 'published', changed: false }] });
  sc.html('foreman', 'FOREMAN'); await settle();
  const h = sc.html('foreman', 'FOREMAN');
  assert.deepEqual(ORDER, ['doccheck', 'later', 'trim', 'techdoc']);     // 회고 쓰기와 README 갱신은 11-15에 뺐다
  for (const k of ['doccheck', 'later', 'trim']) assert.ok(h.includes(`data-sc-task="${k}"`), k);
  assert.ok(!h.includes('data-sc-task="techdoc"'));            // 원고 폴더가 notion/이 아니면(techdoc 없음) 기술문서 쓰기 줄이 없다
  assert.ok(!h.includes('회고') && !h.includes('README 갱신'));
  assert.ok(!h.includes('문서 할 일') && !h.includes('<b>시킬 일</b>'));
  assert.match(h, /알려진 한계 쓰기<\/b> <span class="warn"[^>]*>13개 밀림/);
  assert.ok(!/data-sc-task="docfix"[^>]*data-topic=""/.test(h));
  assert.ok(h.includes('밀린 것 1'));
});

test('포스트잇(11-15) — 받은 할 일 숫자 줄 대신 머리 탭과 같은 포스트잇 목록, pick이 있어도 접힌 채', async () => {
  const pj = { ...PJ, postit: { open: 2, unconfirmed: 1, likely_done: 0, nudge: { why: '열린 것 20개' } }, nudge: { why: '열린 것 20개' } };
  globalThis.fetch = async (u) => {
    if (u === '/api/scribe/todo') return { ok: true, json: async () => ({ tasks: TASKS, projects: { foreman: pj } }) };
    if (u.startsWith('/api/postit')) return { ok: true, json: async () => ({ project: 'foreman', summary: {}, closed: [], readme_checks: [],
      items: [{ id: 3, body: '질문 카드 접기', source_label: '포스트잇에 적음', created_at: '2026-11-14T00:00:00Z', confirmed: true, state: 'new', label: '열림' }] }) };
    return { ok: true, json: async () => ({ enabled: true, docs: [] }) };
  };
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('foreman', 'F', 'postit'); await settle();
  const h = sc.html('foreman', 'F', 'postit');
  assert.ok(!h.includes('받은 할 일'));
  assert.match(h, /<details class="hand"[^>]*><summary[^>]*><b>포스트잇<\/b> <span class="warn">2장, 확인 전 1/);
  assert.ok(!/<details class="hand"[^>]* open[^>]*><summary[^>]*><b>포스트잇<\/b>/.test(h));      // 쌓여도 pick이 있어도 접힌 채
  assert.ok(!h.includes('쌓였습니다') && !h.includes('pi-head'));   // 11-15 서기실은 머리줄과 쌓임 줄을 그리지 않는다
  assert.ok(h.includes('data-pi-row="3"') && h.includes('data-pi-save="1"') && h.includes('data-pi-refresh="1"'));
});

test('포트폴리오 쓰기(11-15) — 「글 N편 가운데 코드가 바뀐 편 M」, [갱신]은 코드가 가장 많이 바뀐 편, 편 없이 [시키기]', async () => {
  const sc = mk({ foreman: PJ }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.match(h, /<b>포트폴리오 쓰기<\/b> <span class="warn">글 3편 가운데 코드가 바뀐 편 1, 머리 주석을 읽지 못한 편 1/);
  assert.match(h, /data-sc-task="portfolio" data-topic="01_a"[^>]*title="갱신 — 코드가 가장 많이 바뀐 편 「글 A」\(코드 바뀐 커밋 3개\)/);
  assert.match(h, /data-sc-task="portfolio" data-name=""[^>]*>시키기</);         // 편 없이 — 서기가 편 목록을 정한다
  assert.ok(h.includes('코드 바뀐 커밋 3') && h.includes('그대로') && h.includes('셀 수 없음'));
  assert.ok(!h.includes('본 판') && !h.includes('그 뒤 커밋 '));
  assert.equal(piecesText({ total: 2, changed: 0, unknown: 0 }).cls, 'muted');
  assert.equal(piecesText({ total: 0 }).text, '아직 쓴 글이 없습니다');
  assert.equal(piecesText({ total: 10, written: 10, since: 485 }).cls, 'bad');      // 옛 서버 응답 — undefined가 아니라 읽지 못했습니다
});

test('포트폴리오 읽기 실패는 0이 아니라 읽지 못했습니다, 바뀐 편이 없으면 [갱신]이 꺼진다', async () => {
  const pj = { ...PJ, portfolio: { ...PJ.portfolio, unread: '커밋 기록을 읽지 못했습니다' }, topics: PJ.topics.map((t) => ({ ...t, commits: 0 })) };
  const sc = mk({ foreman: pj }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.ok(h.includes('커밋 기록을 읽지 못했습니다'));
  assert.ok(h.includes("disabled title=\"갱신 — 지금 고쳐 쓰게 할 편이 없습니다"));
});

test('기술문서(11-15) — notion/ 원고면 [Notion에 올리기]와 코드가 바뀐 편을 보이는 확인 창, 기술문서 쓰기 줄', async () => {
  const td = { total: 5, changed: 2, unknown: 1, need: 3, due: true, why: '글 5편 가운데 코드가 바뀐 편 2, 머리 주석을 읽지 못한 편 1. 마지막으로 합친 지 3일' };
  const pj = { ...PJ, techdoc: td, behind: { ...PJ.behind, techdoc: { n: 3, stale: true, why: td.why } },
    docs_pub: { src: 'notion/', total: 5, published: 3, new: 2, changed: 0, deleted: 0, broken: 0, code_changed: 2, code_unknown: 1, behind_commits: null, last: null } };
  const sc = mk({ foreman: pj }, { enabled: true, docs: [] });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  // 11-17 앞의 「코드가 바뀐 편 3」은 뒤 줄과 같은 말이라 뒤만 남긴다(색은 밀림 표시를 따른다)
  assert.match(h, /<b>기술문서 쓰기<\/b> <span class="warn">글 5편 가운데 코드가 바뀐 편 2/);
  assert.ok(!h.includes('>코드가 바뀐 편 3<'));
  assert.ok(h.includes('data-sc-task="techdoc"'));
  assert.match(h, /data-pub="docsync"[^>]*data-ask="[^"]*코드가 바뀐 편이 2편[^"]*"[^>]*>Notion에 올리기</);
  assert.ok(h.includes('글 5편 가운데 코드가 바뀐 편 2, 머리 주석을 읽지 못한 편 1') && !h.includes('지금 맞추기'));
  const ask = techdocAsk('FOREMAN', { new: 1, changed: 2, deleted: 0, code_changed: 0, code_unknown: 0 });
  assert.ok(ask.startsWith('FOREMAN의 notion/ 원고를 Notion [기술문서]에 올립니다(새 1, 바뀜 2)') && !ask.includes('코드가 바뀐 편'));
});

// 포트폴리오 게시 요약(11-20 서버 docsync.summary(src=portfolio/)) — 기술문서 docs_pub과 같은 꼴
const PP = (extra) => ({ src: 'portfolio/', total: 2, published: 2, new: 0, changed: 0, relink: 0, deleted: 0, broken: 0, code_changed: 0, code_unknown: 0,
  behind_commits: null, last: { at: 1.7e9, done: 2, held: 0, failed: 0, failed_first: null }, last_error: null, held_buttons: 0, ...extra });
const GONE_DOCS = [{ path: 'portfolio/00_old.md', status: 'published', changed: null, gone: true },
  { path: 'portfolio/01_a.md', status: 'published', changed: true, relink: true }, { path: 'portfolio/02_b.md', status: 'published', changed: true }];

test('포트폴리오 게시(11-20) — 기술문서와 같은 꼴: [Notion에 올리기] 하나, 마지막으로 올림, 실패. 한 편씩 단추와 따로 내리기는 없다', async () => {
  const pj = { ...PJ, port_pub: PP({ total: 2, changed: 2, relink: 1, deleted: 1, last: { at: 1.7e9, done: 3, held: 0, failed: 1, failed_first: 'portfolio/02_b.md: 거부' } }) };
  const sc = mk({ foreman: pj }, { enabled: true, portfolio: { has_dir: true, place: true, ref: 'HEAD' }, docs: GONE_DOCS });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.match(h, /<b>포트폴리오 게시<\/b> <span class="warn">게시됨 2 · 바뀜 1 · 링크만 1 · 지워짐 1<\/span>/);
  const btn = /<button[^>]*data-pub="docsync" data-proj="foreman" data-path="portfolio\/" data-ask="([^"]*)"[^>]*>Notion에 올리기</.exec(h);
  assert.ok(btn, '[Notion에 올리기] 하나');
  assert.ok(btn[1].includes('portfolio/ 글을 Notion [포트폴리오]에 올립니다(바뀜 1, 링크만 1, 지워짐 1)') && btn[1].includes('휴지통') && btn[1].includes('번호순'));
  assert.ok(!h.includes('data-pub="prune"') && !h.includes('원본 없는 페이지 내리기') && !h.includes('>다시 게시<') && !h.includes('>게시<'));
  assert.ok(!/data-pub="publish"(?![^>]*data-force)/.test(h), '한 편씩 올리는 단추가 없다(덮기만 남는다)');
  assert.ok(h.includes('마지막으로 올림') && h.includes('실패: portfolio/02_b.md: 거부'));
  assert.ok(h.includes('원본 없음</span>') && h.includes('링크를 다시 걸어야 함</span>') && h.includes('원본이 바뀜</span>'));
  assert.match(h, /<summary[^>]*>편 목록 3<\/summary>/);
  assert.ok(h.includes('data-pub="archive"'));                            // 내리기와 열기는 편 목록에 남는다
});

test('Notion 게시는 둘 — 포트폴리오 게시(편 목록 접힘, 게시됨 N)와 기술문서 게시(숫자 · 마지막 맞춤)', async () => {
  const docs = Array.from({ length: 10 }, (_, i) => ({ path: `portfolio/${i}.md`, status: 'published', changed: false }));
  const sc = mk({ foreman: { ...PJ, port_pub: PP({ total: 10, published: 10 }) } }, { enabled: true, docs });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.match(h, /<b>포트폴리오 게시<\/b> <span class="ok">게시됨 10<\/span>/);
  assert.ok(!h.includes('data-path="portfolio/"'), '올릴 것이 없으면 단추가 없다');
  assert.ok(!/<details class="hand"[^>]*data-keep="scribe:foreman:pubport"[^>]* open/.test(h));      // 편 목록은 접힘이 기본
  assert.match(h, /<b>기술문서 게시<\/b> <span class="warn">게시됨 14 · 새 1 · 바뀜 1<\/span>/);
  assert.ok(h.includes('push 대기 커밋 4개') && h.includes('실패 1') && h.includes('docs/a.md: 거부'));
  assert.ok(h.includes('data-pub="docsync"'));
});

test('펫퍼민트처럼 portfolio/가 없으면 포트폴리오 게시는 아직 없음, 게시 상태를 못 읽으면 읽지 못했습니다', async () => {
  const pm = { ...PJ, topics: [], portfolio: null, docs_pub: null, pub_error: 'NotionError: 401' };
  const sc = mk({ petmint: pm }, { enabled: true, docs: [], portfolio: { has_dir: false, place: true, ref: 'origin/main' } });
  sc.html('petmint', 'P'); await settle();
  const h = sc.html('petmint', 'P');
  assert.ok(h.includes('<b>포트폴리오 게시</b>: 아직 없음. 이 프로젝트에는 portfolio/ 폴더가 없습니다.'));
  assert.ok(!h.includes('포트폴리오를 게시하지 않습니다') && !h.includes('FOREMAN만'));      // 11-17 전 FOREMAN만 연결 글
  assert.match(h, /기술문서 게시<\/b>: 게시 상태를 읽지 못했습니다\(NotionError: 401\)/);
  // 원본 커밋을 못 읽으면 「없음」이 아니라 읽지 못했습니다
  const un = mk({ petmint: pm }, { enabled: true, docs: [], portfolio: { has_dir: null, place: true, ref: 'origin/main' } });
  un.html('petmint', 'P'); await settle();
  assert.ok(un.html('petmint', 'P').includes('<b>포트폴리오 게시</b>: 원본 커밋 origin/main을 읽지 못했습니다.'));
});

test('포트폴리오 게시는 고른 프로젝트로(11-17, 11-20 한 단추): 목록, [Notion에 올리기], 덮기 모두 그 프로젝트', async () => {
  const calls = [];
  const infra = { enabled: true, portfolio: { has_dir: true, place: true, ref: 'origin/main' }, docs: GONE_DOCS };
  const pj = { ...PJ, port_pub: PP({ new: 1, deleted: 1 }) };
  globalThis.fetch = async (u, o = {}) => {
    calls.push({ u, body: o.body ? JSON.parse(o.body) : null });
    if (u === '/api/scribe/todo') return { ok: true, json: async () => ({ tasks: TASKS, projects: { 'ronanlab-infra': pj, foreman: PJ } }) };
    if (o.method === 'POST') return { ok: true, json: async () => ({ action: 'docsync', src: 'portfolio/', done: [{ path: 'portfolio/01_a.md', action: 'created' }, { path: 'portfolio/00_old.md', action: 'archived' }], held: [], failed: [], warnings: [] }) };
    return { ok: true, json: async () => (u.includes('ronanlab-infra') ? infra : { enabled: true, docs: [] }) };
  };
  const asked = [];
  globalThis.confirm = (m) => { asked.push(m); return true; };
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('ronanlab-infra', '인프라'); await settle();
  const h = sc.html('ronanlab-infra', '인프라');
  assert.ok(calls.some((c) => c.u === '/api/publish?project=ronanlab-infra'));
  assert.ok(!calls.some((c) => c.u === '/api/publish' || c.u === '/api/publish?project=foreman'));
  assert.match(h, /data-pub="docsync" data-proj="ronanlab-infra" data-path="portfolio\/"/);
  const ask = /data-path="portfolio\/" data-ask="([^"]*)"/.exec(h)[1];
  const btn = (sel) => ({ target: { closest: (q) => (q === '[data-pub]' ? sel : null) }, preventDefault() {} });
  await sc.onClick(btn({ dataset: { pub: 'docsync', proj: 'ronanlab-infra', path: 'portfolio/', ask } }), 'ronanlab-infra', '인프라');
  assert.ok(asked[0].startsWith('인프라의 portfolio/ 글을 Notion [포트폴리오]에 올립니다'));
  assert.match(sc.html('ronanlab-infra', '인프라'), /포트폴리오를 맞췄습니다: 올림 1 · 휴지통으로 1/);
  await sc.onClick(btn({ dataset: { pub: 'publish', force: '1', path: 'portfolio/02_b.md' } }), 'ronanlab-infra', '인프라');  // 덮기, data-proj 없어도 고른 방
  const posts = calls.filter((c) => c.body).map((c) => c.body);
  assert.deepEqual(posts, [{ path: 'portfolio/', action: 'docsync', project: 'ronanlab-infra', force: false },
    { path: 'portfolio/02_b.md', action: 'docsync', project: 'ronanlab-infra', force: true }]);
  // 다시 읽기도 그 프로젝트(FOREMAN을 부르지 않는다)
  assert.ok(!calls.some((c) => c.u.startsWith('/api/publish?project=foreman')));
});

test('Notion 자리가 정해지지 않은 프로젝트(11-17): 상태는 보이고 [Notion에 올리기]는 까닭과 함께 막힌다', async () => {
  const sc = mk({ newproj: { ...PJ, port_pub: PP({ total: 1, published: 0, new: 1, last: null }) } },
    { enabled: true, portfolio: { has_dir: true, place: false, place_why: 'Notion 자리가 정해지지 않았습니다(config/notion.toml portfolio_page)' },
      docs: [{ path: 'portfolio/01_a.md', status: 'new', changed: null }] });
  sc.html('newproj', 'N'); await settle();
  const h = sc.html('newproj', 'N');
  assert.match(h, /<b>포트폴리오 게시<\/b> <span class="warn">게시됨 0 · 새 1, Notion 자리 없음<\/span>/);
  assert.ok(h.includes('게시할 수 없습니다: Notion 자리가 정해지지 않았습니다') && h.includes('Notion에 올린 기록이 없습니다'));
  assert.match(h, /data-path="portfolio\/"[^>]* disabled title="Notion에 올리기 — 지금은 할 수 없습니다\. Notion 자리가 정해지지 않았습니다/);
});

test('포트폴리오 덮기 단추는 포트폴리오 게시 줄 아래, 기술문서 덮기는 기술문서 줄 아래(11-20 서버가 줄마다 src)', async () => {
  const items = [
    { kind: 'publish', act: 'force', project: 'foreman', path: 'portfolio/01_a.md', src: 'portfolio/', title: 'Notion에서 사람이 고친 곳 1개: portfolio/01_a.md', why: '덮지 않았습니다' },
    { kind: 'publish', act: 'force', project: 'foreman', path: 'docs/b.md', src: 'docs/', title: 'Notion에서 사람이 고친 곳 2개: docs/b.md', why: '덮지 않았습니다' }];
  const sc = mk({ foreman: { ...PJ, items, port_pub: PP({ changed: 1, held_buttons: 1, last: { at: 1.7e9, done: 0, held: 1, failed: 0 } }) } },
    { enabled: true, portfolio: { has_dir: true, place: true, ref: 'HEAD' }, docs: GONE_DOCS });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  const port = h.indexOf('<b>포트폴리오 게시</b>'), docs = h.indexOf('<b>기술문서 게시</b>');
  const pf = h.indexOf('data-path="portfolio/01_a.md"'), df = h.indexOf('data-force="1" data-proj="foreman" data-path="docs/b.md"');
  assert.ok(port < pf && pf < docs && docs < df, '각 묶음 줄 아래');
  assert.ok(h.includes('사람이 고쳐 멈춤 1') && h.includes('덮기 2(아래 게시 칸)'));
});

test('FOREMAN은 그대로: 자리 있음이면 [Notion에 올리기]가 열려 있고 FOREMAN으로 부른다', async () => {
  const calls = [];
  globalThis.fetch = async (u) => {
    calls.push(u);
    if (u === '/api/scribe/todo') return { ok: true, json: async () => ({ tasks: TASKS, projects: { foreman: { ...PJ, port_pub: PP({ changed: 1 }) } } }) };
    return { ok: true, json: async () => ({ enabled: true, portfolio: { has_dir: true, place: true, ref: 'HEAD' }, docs: [{ path: 'portfolio/01_a.md', status: 'published', changed: true }] }) };
  };
  const sc = createScribe({ headers: () => ({}), touch() {} });
  sc.html('foreman', 'F'); await settle();
  const h = sc.html('foreman', 'F');
  assert.ok(calls.includes('/api/publish?project=foreman'));
  assert.match(h, /data-pub="docsync" data-proj="foreman" data-path="portfolio\/" data-ask="[^"]*" title="Notion에 올리기 — portfolio\/ 글 가운데 바뀐 편만/);
  assert.ok(!h.includes('Notion 자리 없음'));
});

test('바뀜 가운데 링크만 다시 걸면 되는 편은 따로 센다(11-20, 기술문서도 같다)', () => {
  assert.equal(pubCounts({ published: 5, new: 0, changed: 3, relink: 2 }).text, '게시됨 5 · 바뀜 1 · 링크만 2');
  assert.equal(pubCounts({ published: 5, new: 0, changed: 2, relink: 2 }).text, '게시됨 5 · 링크만 2');
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
