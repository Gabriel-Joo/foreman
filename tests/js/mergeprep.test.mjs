import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mpSection, managerCard, humanFiles, mergedNote } from '../../bridge/static/js/handoff.js';

// 합치기 승인 카드(11-11 1물결 A) — 브리지가 만든 카드를 패널이 그린다. 사람은 [합치기] · [나중에]만
const b = (act, label, on, cls = '', tip = '') => `<button data-act="${act}"${on ? '' : ' disabled'} title="${tip}">${label}</button>`;
const card = (o = {}) => ({ sid: 7, branch: 'cc/w', base: 'main', head: 'abc', ahead: 2, behind: 0, ff: true, live: true,
  why: '보고 옴', commits: ['a1 하나', 'b2 둘'], files: ['bridge/x.py'], conflict: null, status: 'ready',
  docs: { readme: [{ line: 9, text: '할 일 줄', files: ['bridge/x.py'], words: [] }], docs: [] }, ...o });

test('꺼져 있거나 카드가 없으면 그리지 않는다 — 준비가 멈췄으면 사유만', () => {
  assert.equal(mpSection(null, b, 7), '');
  assert.equal(mpSection({ card: null, health: { ok: true } }, b, 7), '');
  const h = mpSection({ card: null, health: { ok: false, error: '합치기 준비가 10분째 끝나지 않아 끊었습니다' } }, b, 7);
  assert.match(h, /10분째/);
});

test('깨끗한 카드: ff · 정리 후보 · 승인 단추, 살아 있으면 끝낸다고 알린다', () => {
  const h = mpSection({ card: card(), health: { ok: true } }, b, 7);
  assert.match(h, /합치기 승인/);
  assert.match(h, /충돌 없음 · ff 가능/);
  assert.match(h, /README:9 — 할 일 줄/);
  assert.match(h, /data-act="mp-merge" title="합치기 — 승인하면 세션을 끝내고[^"]*충돌이면 끝내지 않습니다/);   // 11-14 안내는 [합치기] 호버로
  assert.match(h, /data-act="mp-skip"/);
});

// 11-14 사용자 — 판단에 필요한 것(배지 · 수 · 걸린 파일)만 위에, 나머지는 「자세히」 안. 지우지 않는다
test('카드 줄이기: 배지 · 한 줄 수 · 승인해야 할 파일 · 자세히', () => {
  const files = ['backend/src/main/resources/db/migration/V19__chatbot_turns.sql', 'backend/src/main/resources/db/migration/V20__summary_batch_runs.sql', 'a.java'];
  const why = [`늘 사람 경로(*db/migration/*): ${files[0]}, ${files[1]}`];
  const c = card({ why: '보고 옴 — 일하지 않고 응답을 마쳤습니다', files, ahead: 6, human_why: why, approver: 'manager',
    note: '사람 승인 카드입니다 — 승인자는 관리자지만 늘 사람에게 올릴 것에 걸렸습니다: ' + why[0], manager_told: true });
  const h = mpSection({ card: c }, b, 7);
  assert.match(h, /<b>합치기 승인<\/b> <span class="mp-badge mp-wait">승인 기다림<\/span><code class="mp-branch"[^>]*>cc\/w<\/code>/);
  assert.match(h, /커밋 <b>6<\/b>개 · 바뀐 파일 3개 · <span class="ok"[^>]*>충돌 없음<\/span><\/div>/);
  assert.match(h, /승인해야 할 파일 2개<\/b><div class="mp-hf-row" title="backend\/src\/main\/resources\/db\/migration\/V19__chatbot_turns\.sql — 늘 사람 경로\(\*db\/migration\/\*\)">V19__chatbot_turns\.sql<\/div>/);
  const [top, rest] = h.split('<details class="mp-more"');
  for (const s of ['ff 가능', '보고 옴', '사람 승인 카드입니다', '정리 후보', '커밋 2 · 바뀐 파일 3']) {
    assert.ok(!top.includes(s), `위에 ${s}`);
    assert.ok(rest.includes(s), `자세히에 ${s}`);
  }
  assert.ok(!h.includes('— 승인하면 세션을 끝냅니다'));                       // 카드 글에서는 빠지고 호버에만
  assert.match(h, /data-act="mp-merge"/);
  // 관리자 승인 카드(사람에게 안 걸림)는 걸린 파일 줄이 없다
  assert.doesNotMatch(mpSection({ card: card({ approver: 'manager', human_why: [] }) }, b, 7), /승인해야 할 파일/);
  // 충돌 카드 — 배지는 빨강, 둘째 줄에 충돌 수
  const k = mpSection({ card: card({ conflict: ['a.txt'], status: 'conflict_sent' }) }, b, 7);
  assert.match(k, /mp-badge mp-bad">충돌 — 세션에 풀라고 보냈습니다/);
  assert.match(k, /바뀐 파일 1개 · <span class="bad"/);
});

test('승인해야 할 파일 뽑기: 바뀐 파일에 있는 경로만, 파일 없는 까닭은 글 그대로', () => {
  assert.deepEqual(humanFiles(card()), []);
  const c = card({ files: ['x/a.sql', 'b.toml'], human_why: ['늘 사람 경로(*.sql): x/a.sql', '늘 사람 경로(*.toml): b.toml, x/a.sql …', '이력 다시 쓰기 · force push — 커밋 글에 「force push」'] });
  assert.deepEqual(humanFiles(c), [{ path: 'x/a.sql', why: '늘 사람 경로(*.sql)' }, { path: 'b.toml', why: '늘 사람 경로(*.toml)' },
    { path: null, why: '이력 다시 쓰기 · force push — 커밋 글에 「force push」' }]);
});

test('관리자가 승인하는 카드는 [합치기]를 숨긴다 — 늘-사람 카드 · 사람 승인자 카드는 그대로(11-12)', () => {
  assert.ok(managerCard(card({ approver: 'manager', human_why: [] })));
  assert.ok(!managerCard(card({ approver: 'manager', human_why: ['늘 사람 경로(config/*.toml): config/x.toml'] })));
  assert.ok(!managerCard(card({ approver: 'human' })) && !managerCard(card()) && !managerCard(null));
  const m = mpSection({ card: card({ approver: 'manager', human_why: [] }) }, b, 7);
  assert.doesNotMatch(m, /data-act="mp-merge"/);
  assert.match(m, /관리자 세션이 승인합니다 — 사람이 누를 것은 없습니다\./);
  const h = mpSection({ card: card({ approver: 'manager', human_why: ['x'] }) }, b, 7);
  assert.match(h, /data-act="mp-merge"/);
  // 충돌을 보낸 뒤 · 멈춘 카드는 다시 단추가 보인다(누군가 손봐야 한다)
  assert.match(mpSection({ card: card({ approver: 'manager', human_why: [], status: 'failed' }) }, b, 7), /data-act="mp-merge"/);
});

test('main이 앞섬 · 충돌 · 합친 뒤', () => {
  assert.match(mpSection({ card: card({ ff: false, behind: 3 }) }, b, 7), /main에 새 커밋 3개\(rebase\)/);
  const c = mpSection({ card: card({ conflict: ['a.txt'] }) }, b, 7);
  assert.match(c, /충돌 1개/);
  assert.match(c, /충돌 파일: a.txt/);
  assert.match(c, /충돌이 있어 합치지 않습니다/);
  const m = mpSection({ card: card({ status: 'merged', note: 'main에 커밋 2개를 합쳤습니다.', manager_told: true }) }, b, 7);
  assert.match(m, /합쳤습니다/);
  assert.match(m, /관리자 세션에 알렸습니다/);
  assert.match(m, /시험 · push · 브리지 다시 띄우기는 관리자가/);
  assert.doesNotMatch(m, /mp-merge/);                         // 합친 카드에는 단추가 없다
});

test('정리 후보 — 근거 있는 것은 까닭과 함께 앞에, 낱말만 겹친 것은 접고, 안 고친 문서 표시(11-11 2물결 넷)', () => {
  const docs = { readme: [
    { line: 4, text: '권한 거부 줄', why: ['세션 기록 「README에서 뺄 줄」(x.md)'], score: 105, weak: false },
    { line: 9, text: '낱말 줄', words: ['카드', '승인', '화면'], why: ['커밋 글 낱말만 겹침'], score: 3, weak: true }],
  docs: [{ where: 'docs/11.md', lines: [3], count: 1, files: ['bridge/a.py'], stale: true }] };
  const h = mpSection({ card: card({ docs }) }, b, 7);
  assert.match(h, /README:4 — 권한 거부 줄 <span class="muted">\(세션 기록 「README에서 뺄 줄」/);
  assert.match(h, /낱말만 겹친 후보 1개<\/summary><div class="small muted">README:9/);
  assert.match(h, /이번에 안 고침/);
});

test('묻는 말이 있어도 카드는 뜬다 — 묻는 말을 함께 보인다(11-11 D2 281)', () => {
  const h = mpSection({ card: card({ asks: { tail: '한 번씩 확인해 주세요.' } }), health: { ok: true } }, b, 7);
  assert.match(h, /세션이 묻는 말이 있습니다 — 패널에서 답하십시오: 한 번씩 확인해 주세요/);
  assert.match(h, /data-act="mp-merge"/);
  assert.doesNotMatch(mpSection({ card: card() }, b, 7), /묻는 말/);
});

test('사람이 답 안 해도 됨으로 끈 카드 — 카드 · [합치기]는 남고 끈 것을 보인다(11-13)', () => {
  const h = mpSection({ card: card({ esc_off_at: '2026-11-13T03:00:00Z' }) }, b, 7);
  assert.match(h, /mp-off/);
  assert.match(h, /사람이 답 안 해도 됨으로 둠 — /);
  assert.match(h, /data-act="mp-merge"/);
  assert.doesNotMatch(mpSection({ card: card() }, b, 7), /mp-off/);
  assert.doesNotMatch(mpSection({ card: card({ esc_off_at: '2026-11-13T03:00:00Z', status: 'merged' }) }, b, 7), /mp-off/);
});

// 11-14 사용자 — 합친 뒤 안내는 「합쳤다 · push 여부」 한 줄 + 「해시 「제목」」, 나머지는 「자세히」 안(없애지 않는다)
test('합친 뒤 안내: 두 줄, push 아직 · push까지, 옛 카드는 원문', () => {
  const note = 'main에 커밋 6개를 커밋 하나(663d945e 「feat: 관측 바닥과 대시보드」)로 묶어 합쳤습니다(squash — 본문에 원래 날짜 · 해시 · 제목). 원래 커밋은 `git log refs/foreman/squashed/0cc3633e66ca`로 봅니다. push는 하지 않았습니다.';
  const mr = { count: 6, commit: '663d945e1234', title: 'feat: 관측 바닥과 대시보드', squash: true, orig_ref: 'refs/foreman/squashed/0cc3633e66ca', base: 'main' };
  const c = card({ status: 'merged', note, merge_result: mr, pushed: false, manager_told: true });
  const h = mpSection({ card: c }, b, 7);
  const [top, rest] = h.split('<details class="mp-more"');
  assert.match(top, /main에 커밋 6개를 하나로 합쳤습니다\. <span[^>]*>push는 아직입니다\.<\/span>/);
  assert.match(top, /<code class="sha">663d945e<\/code> 「feat: 관측 바닥과 대시보드」/);
  for (const s of ['git log refs/foreman/squashed/0cc3633e66ca', '원래 커밋의 날짜, 해시, 제목', '합치기 결과 원문: main에 커밋 6개', '관리자 세션에 알렸습니다']) {
    assert.ok(!top.includes(s) && rest.includes(s), s);
  }
  assert.equal((h.match(/<details class="mp-more"/g) || []).length, 1);          // 「자세히」는 하나
  assert.match(mpSection({ card: { ...c, pushed: true } }, b, 7), /push까지 했습니다\./);
  assert.match(mpSection({ card: { ...c, pushed: null } }, b, 7), /push는 아직입니다\./);    // 알 길이 없으면 「아직」
  assert.equal(mergedNote(card({ status: 'merged', note })), null);
  const old = mpSection({ card: card({ status: 'merged', note, manager_told: true }) }, b, 7);   // 갈래 없는 옛 카드는 전처럼
  assert.ok(old.split('<details class="mp-more"')[1].includes('본문에 원래 날짜') && old.includes('시험 · push · 브리지 다시 띄우기는 관리자가'));
  assert.match(mpSection({ card: card({ status: 'merged', merge_result: { ...mr, squash: false, count: 1, orig_ref: null } }) }, b, 7), /main에 커밋 1개를 합쳤습니다\./);
});
