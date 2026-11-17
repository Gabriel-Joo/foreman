import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mpSection, managerCard, humanFiles, mergedNote, ruleNote } from '../../bridge/static/js/handoff.js';

// 11-15 규칙 파일(D2) — 바뀐 파일 중 승인 규칙 · 게이트 파일이 있으면 카드에 한 줄. 없으면 그리지 않는다
test('규칙 파일이 바뀌면 카드에 🛡 한 줄, 확인 실패도 보인다', () => {
  const c = { sid: 7, branch: 'cc/w', base: 'main', head: 'abc', ahead: 1, behind: 0, live: false, commits: ['a1'], status: 'ready',
    files: ['config/approval.toml', 'bridge/x.py'], conflict: null, docs: null };
  assert.equal(ruleNote(c), '');
  const h = mpSection({ card: { ...c, rule_files: ['config/approval.toml'] } }, () => '', 7);
  assert.match(h, /🛡 규칙 파일이 바뀝니다: approval\.toml/);
  assert.match(ruleNote({ ...c, rule_files: ['config/approval.toml'] }), /title="규칙 파일 — [^"]*&#10;config\/approval\.toml"/);
  assert.match(ruleNote({ ...c, rule_files_error: '규칙 파일이 바뀌는지 확인하지 못했습니다(OSError)' }), /확인하지 못했습니다/);
});

// 합치기 승인 카드(11-11 1물결 A) — 브리지가 만든 카드를 패널이 그린다. 사람은 [합치기] · [나중에]만
const b = (act, label, on, cls = '', tip = '') => `<button data-act="${act}"${on ? '' : ' disabled'} title="${tip}">${label}</button>`;
const card = (o = {}) => ({ sid: 7, branch: 'cc/w', base: 'main', head: 'abc', ahead: 2, behind: 0, ff: true, live: true,
  why: '보고 옴', commits: ['a1 하나', 'b2 둘'], files: ['bridge/x.py'], conflict: null, status: 'ready',
  docs: { readme: [], docs: [{ where: 'docs/11.md', lines: [9], count: 1, files: ['bridge/x.py'], stale: false }] }, ...o });

test('꺼져 있거나 카드가 없으면 그리지 않는다 — 준비가 멈췄으면 사유만', () => {
  assert.equal(mpSection(null, b, 7), '');
  assert.equal(mpSection({ card: null, health: { ok: true } }, b, 7), '');
  const h = mpSection({ card: null, health: { ok: false, error: '합치기 준비가 10분째 끝나지 않아 끊었습니다' } }, b, 7);
  assert.match(h, /10분째/);
});

test('깨끗한 카드: ff · 걸리는 문서 · 승인 단추, 살아 있으면 끝낸다고 알린다', () => {
  const h = mpSection({ card: card(), health: { ok: true } }, b, 7);
  assert.match(h, /합치기 승인/);
  assert.match(h, /<span class="ok"[^>]*>충돌 없음<\/span><\/div>/);
  assert.ok(!h.includes('ff 가능') && !h.includes('합치는 방법'));                // 11-15 사용자 — 「충돌 없음」은 둘째 줄에 한 번만
  assert.match(h, /📄 걸리는 문서 1, 안 고침 0/);
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
  assert.match(h, /<span title="[^"]*">커밋 <b>6<\/b>개<\/span> · <span title="[^"]*">바뀐 파일 3개<\/span> · <span class="ok"[^>]*>충돌 없음<\/span><\/div>/);
  // 커밋 · 바뀐 파일 목록은 호버로(「제목 — 설명」 꼴, 줄마다 하나)
  assert.match(h, /title="커밋 — [^"]*&#10;a1 하나&#10;b2 둘"/);
  assert.match(h, /title="바뀐 파일 — [^"]*&#10;backend\/src\/main\/resources\/db\/migration\/V19__chatbot_turns\.sql&#10;/);
  const many = mpSection({ card: card({ commits: Array.from({ length: 12 }, (_, i) => `h${i} t${i}`) }) }, b, 7);
  assert.match(many, /h9 t9&#10;외 2개"/);
  assert.ok(!many.includes('h10 t10'));
  assert.match(h, /승인해야 할 파일 2개<\/b><div class="mp-hf-row" title="backend\/src\/main\/resources\/db\/migration\/V19__chatbot_turns\.sql">V19__chatbot_turns\.sql<\/div>/);
  const [top, rest] = h.split('<details class="mp-more"');
  for (const s of ['보고 옴', 'class="small mp-doc"']) {
    assert.ok(!top.includes(s), `위에 ${s}`);
    assert.ok(rest.includes(s), `자세히에 ${s}`);
  }
  assert.ok(top.includes('걸리는 문서 1') && !rest.includes('걸리는 문서 1'));   // 수는 위 줄에만(11-17)
  // 11-15 사용자(410) — 위 줄과 겹치는 말은 「자세히」에 없다(커밋 목록 접는 칸도 없다)
  for (const s of ['합치는 방법', '사람 승인 카드입니다', '늘 사람이 승인해야 하는 파일', '커밋 2 · 바뀐 파일 3', 'V19__chatbot_turns', '관리자 세션에 알렸습니다', 'hand-body']) assert.ok(!rest.includes(s), `자세히에 없어야 ${s}`);
  assert.ok(!h.includes('— 승인하면 세션을 끝냅니다'));                       // 카드 글에서는 빠지고 호버에만
  assert.match(h, /data-act="mp-merge"/);
  assert.ok(!rest.includes('사람에게 올린 까닭'));
  assert.ok(!h.includes('늘 사람 경로'));
  // 파일이 없는 까닭은 글 그대로 한 줄, 다른 까닭의 파일은 그 까닭이 머리
  const k2 = mpSection({ card: card({ files: ['x/a.sql', 'd.txt'], human_why: ['늘 사람 경로(*.sql): x/a.sql', '지우기(파일 1개를 지움): d.txt', '이력 다시 쓰기 · force push(커밋 글에 「force」)'] }) }, b, 7);
  // 11-15 사용자(410) — 위 「승인해야 할 파일」에 이미 보이는 것(늘 사람 경로 파일 · 안 잘린 파일 없는 까닭)은 「자세히」에 없고, 위에 안 보이는 까닭(지우기 · 잘린 긴 까닭)만 남는다
  assert.doesNotMatch(k2, /mp-hw">늘 사람이 승인해야 하는 파일/);
  assert.match(k2, /mp-hw">지우기\(파일 1개를 지움\)<div class="mp-hf-row" title="d\.txt">d\.txt<\/div><\/div>/);
  assert.doesNotMatch(k2, /mp-hw">이력 다시 쓰기/);
  const longWhy = '이력 다시 쓰기 · force push(커밋 글에 「force」가 있어 서버가 늘 사람에게 올립니다 그래서 길게 씁니다)';
  assert.match(mpSection({ card: card({ human_why: [longWhy] }) }, b, 7), new RegExp(`mp-hw">${longWhy.replace(/[()·「」]/g, '\\$&')}</div>`));
  // 관리자 승인 카드(사람에게 안 걸림)는 걸린 파일 줄이 없다
  assert.doesNotMatch(mpSection({ card: card({ approver: 'manager', human_why: [] }) }, b, 7), /승인해야 할 파일/);
  // 충돌 카드 — 배지는 빨강, 둘째 줄에 충돌 수
  const k = mpSection({ card: card({ conflict: ['a.txt'], status: 'conflict_sent' }) }, b, 7);
  assert.match(k, /mp-badge mp-bad">충돌: 세션에 풀라고 보냈습니다/);
  assert.match(k, /바뀐 파일 1개<\/span> · <span class="bad"/);
  assert.doesNotMatch(k, /합치는 방법/);
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
  assert.match(m, /관리자 세션이 승인합니다\. 사람이 누를 것은 없습니다\./);
  const h = mpSection({ card: card({ approver: 'manager', human_why: ['x'] }) }, b, 7);
  assert.match(h, /data-act="mp-merge"/);
  // 충돌을 보낸 뒤 · 멈춘 카드는 다시 단추가 보인다(누군가 손봐야 한다)
  assert.match(mpSection({ card: card({ approver: 'manager', human_why: [], status: 'failed' }) }, b, 7), /data-act="mp-merge"/);
});

test('조사 log 카드(승인자 auto)는 브리지가 스스로 합친다. 사람이 누를 것이 없다(11-15)', () => {
  assert.ok(managerCard(card({ approver: 'auto', human_why: [] })));
  const a = mpSection({ card: card({ approver: 'auto', human_why: [] }) }, b, 7);
  assert.doesNotMatch(a, /data-act="mp-merge"/);
  assert.match(a, /브리지가 스스로 합치고 조사 세션을 끝냅니다\. 사람이 누를 것은 없습니다\./);
  assert.doesNotMatch(a, /관리자 세션이 승인합니다/);
  // 스스로 합치다 멈추면 단추가 다시 보인다
  assert.match(mpSection({ card: card({ approver: 'auto', human_why: [], status: 'failed' }) }, b, 7), /data-act="mp-merge"/);
});

test('main이 앞섬 · 충돌 · 합친 뒤', () => {
  const rb = mpSection({ card: card({ ff: false, behind: 3 }) }, b, 7);
  assert.match(rb, /<div class="small"><span class="ok"[^>]*>main에 새 커밋 3개\(rebase\)<\/span><\/div>/);
  assert.ok(!rb.includes('충돌 없음, main') && !rb.includes('합치는 방법'));
  // 사람 승인 · 관리자 승인 서버 note는 위 줄과 겹쳐 안 그린다. 못 알린 것만 경고, 다른 note(관리자 세션 없음)는 남는다
  const nr = (o) => mpSection({ card: card({ ff: true, why: '', docs: null, ...o }) }, b, 7);
  assert.ok(!nr({ note: '관리자가 승인합니다. 관리자 세션에 카드를 알렸습니다. 사람 화면에는 띄우지 않습니다.', manager_told: true }).includes('<details class="mp-more"'));   // 남은 것이 없으면 「자세히」도 없다
  assert.match(nr({ note: '관리자 세션에 알리지 못해 사람이 승인합니다.', manager_told: false }), /<div class="small warn">관리자 세션에 알리지 못해 사람이 승인합니다\.<\/div>/);
  assert.match(nr({ note: '관리자가 승인합니다. 관리자 세션에 카드를 알렸습니다.', manager_told: false }), /<div class="small warn">관리자 세션에는 알리지 못했습니다\(텔레그램으로 남김\)\./);
  assert.match(nr({ note: '승인자는 관리자지만 살아 있는 관리자 세션이 없어 사람이 승인합니다.' }), /살아 있는 관리자 세션이 없어/);
  const c = mpSection({ card: card({ conflict: ['a.txt'] }) }, b, 7);
  assert.match(c, /충돌 1개/);
  assert.match(c, /충돌 파일: a.txt/);
  assert.match(c, /충돌이 있어 합치지 않습니다/);
  const m = mpSection({ card: card({ status: 'merged', note: 'main에 커밋 2개를 합쳤습니다.', manager_told: true }) }, b, 7);
  assert.match(m, /합쳤습니다/);
  assert.doesNotMatch(m, /관리자 세션에 알렸습니다/);                 // 11-15 사용자(410) — 알렸다는 말은 그리지 않는다. 못 알린 것만 경고
  assert.match(m, /시험 · push · 브리지 다시 띄우기는 관리자가/);
  assert.doesNotMatch(m, /mp-merge/);                         // 합친 카드에는 단추가 없다
});

test('걸리는 문서(옛 카드 모양): 안 고친 문서 표시. 옛 카드의 README 줄은 그리지 않는다(11-15 표를 없앰)', () => {
  const docs = { readme: [
    { line: 4, text: '권한 거부 줄', why: ['세션 기록(x.md)'], score: 105, weak: false }],
  docs: [{ where: 'docs/11.md', lines: [3], count: 1, files: ['bridge/a.py'], stale: true }] };
  const h = mpSection({ card: card({ docs }) }, b, 7);
  assert.doesNotMatch(h, /README:4|권한 거부 줄/);
  assert.match(h, /<div class="small mp-docs warn"[^>]*>📄 걸리는 문서 1, 안 고침 1<\/div>/);   // total 없는 옛 카드는 목록으로 센다
  assert.match(h, /<span class="warn">안 고침<\/span>/);
  assert.equal(mpSection({ card: card({ docs: { readme: docs.readme, docs: [] } }) }, b, 7).includes('mp-doc'), false);
});

// 11-17 사용자 지시 21. 바뀐 코드를 가리키는 문서를 위 줄에 수로, 「자세히」에 문서마다 줄. 호버에 안 고친 것 먼저
test('걸리는 문서: 수는 위 줄, 목록은 자세히, 원고 표시, 찾지 못하면 경고', () => {
  const docs = { readme: [], total: 14, unfixed: 2, docs: [
    { where: 'docs/11_worktree.md', kind: 'docs', lines: [18], count: 1, files: ['bridge/mergeprep.py'], stale: false,
      hits: [{ line: 18, heading: '6-1. 합치기 준비', text: '카드는 …', code: 'bridge/mergeprep.py' }] },
    { where: 'notion/07_merge/01_card.md', kind: 'notion', lines: [1, 94], count: 2, files: ['bridge/mergeprep.py'], stale: true, hits: [] },
    { where: 'portfolio/07_merge.md', kind: 'portfolio', lines: [1], count: 1, files: ['bridge/mergeprep.py'], stale: true }] };
  const h = mpSection({ card: card({ docs }) }, b, 7);
  const [top, rest] = h.split('<details class="mp-more"');
  assert.match(top, /📄 걸리는 문서 14, 안 고침 2/);
  assert.match(top, /title="걸리는 문서 — [^"]*&#10;안 고침 notion\/07_merge\/01_card\.md&#10;안 고침 portfolio\/07_merge\.md&#10;고침 docs\/11_worktree\.md&#10;외 4개"/);
  assert.match(rest, /<code>notion\/07_merge\/01_card\.md<\/code> <span class="muted">원고<\/span> 줄 1, 94/);
  assert.match(rest, /<code>portfolio\/07_merge\.md<\/code> <span class="muted">포트폴리오<\/span>/);
  assert.match(rest, /title="docs\/11_worktree\.md&#10;18: 「6-1\. 합치기 준비」 카드는 …"/);
  assert.match(rest, /<span class="ok">고침<\/span>/);
  const e = mpSection({ card: card({ docs: { error: '걸리는 문서를 찾지 못했습니다(OSError)', readme: [], docs: [] } }) }, b, 7);
  assert.match(e.split('<details')[0], /class="small warn mp-docs"[^>]*>📄 걸리는 문서를 찾지 못했습니다\(OSError\)/);
});

// 11-17 사용자 결정 8, 9(문서 도구 합치기 3단계). 코드로 걸린 것과 문서로만 걸린 것은 위 줄 둘로, 설정을 바꾼 브랜치는 경고 한 줄
test('걸리는 문서: 코드로 걸린 것과 문서로만 걸린 것을 나눠 보이고, 설정을 바꾼 브랜치는 경고', () => {
  const docs = { readme: [], total: 3, unfixed: 2, by: { code: { total: 1, unfixed: 0 }, doc: { total: 2, unfixed: 2 } }, docs: [
    { where: 'docs/11_worktree.md', kind: 'docs', by: 'code', lines: [18], count: 1, files: ['bridge/mergeprep.py'], stale: false },
    { where: 'notion/14_screen.md', kind: 'notion', by: 'doc', lines: [3], count: 1, files: ['CLAUDE.md'], stale: true },
    { where: 'notion/06_sessions.md', kind: 'notion', by: 'doc', lines: [7], count: 1, files: ['docs/11_worktree.md'], stale: true }],
    config_note: '이 브랜치가 설정을 바꿨습니다. 이 셈은 main 설정 기준입니다' };
  const h = mpSection({ card: card({ docs }) }, b, 7);
  const [top, rest] = h.split('<details class="mp-more"');
  assert.match(top, /<div class="small mp-docs muted" title="코드로 걸린 문서 — [^"]*&#10;고침 docs\/11_worktree\.md">📄 코드로 걸린 문서 1, 안 고침 0<\/div>/);
  assert.match(top, /<div class="small mp-docs warn" title="문서로만 걸린 문서 — [^"]*&#10;안 고침 notion\/14_screen\.md&#10;안 고침 notion\/06_sessions\.md">📄 문서로만 걸린 문서 2, 안 고침 2<\/div>/);
  assert.match(top, /⚠ 이 브랜치가 설정을 바꿨습니다\. 이 셈은 main 설정 기준입니다/);
  assert.ok(!top.includes('걸리는 문서 3'));                                  // 섞은 수는 보이지 않는다
  assert.match(rest, /<code>notion\/14_screen\.md<\/code> <span class="muted">원고<\/span> <span class="muted">문서로만<\/span> 줄 3/);
  assert.match(rest, /<code>docs\/11_worktree\.md<\/code> <span class="muted">코드로<\/span> 줄 18/);
  const only = mpSection({ card: card({ docs: { ...docs, total: 1, by: { code: { total: 1, unfixed: 0 }, doc: { total: 0, unfixed: 0 } }, config_note: undefined } }) }, b, 7);
  assert.ok(only.includes('코드로 걸린 문서 1') && !only.includes('문서로만 걸린 문서') && !only.includes('설정을 바꿨습니다'));
  const none = mpSection({ card: card({ docs: { readme: [], total: 0, docs: [], config_note: docs.config_note } }) }, b, 7);
  assert.match(none, /설정을 바꿨습니다/);                                   // 걸린 문서가 없어도 경고는 보인다
});

test('묻는 말이 있어도 카드는 뜬다 — 묻는 말을 함께 보인다(11-11 D2 281)', () => {
  const h = mpSection({ card: card({ asks: { tail: '한 번씩 확인해 주세요.' } }), health: { ok: true } }, b, 7);
  assert.match(h, /세션이 묻는 말이 있습니다\. 패널에서 답하십시오: 한 번씩 확인해 주세요/);
  assert.match(h, /data-act="mp-merge"/);
  assert.doesNotMatch(mpSection({ card: card() }, b, 7), /묻는 말/);
});

test('사람이 답 안 해도 됨으로 끈 카드 — 카드 · [합치기]는 남고 끈 것을 보인다(11-13)', () => {
  const h = mpSection({ card: card({ esc_off_at: '2026-11-13T03:00:00Z' }) }, b, 7);
  assert.match(h, /mp-off/);
  assert.match(h, /사람이 답 안 해도 됨으로 둠\(/);
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
  for (const s of ['git log refs/foreman/squashed/0cc3633e66ca', '원래 커밋의 날짜, 해시, 제목']) {
    assert.ok(!top.includes(s) && rest.includes(s), s);
  }
  // 11-15 사용자 — 같은 말이 세 번 떴다. 서버 note 원문 · 「합치기 결과 원문」은 새 카드에서 그리지 않는다
  for (const s of ['합치기 결과 원문', '본문에 원래 날짜', '관리자 세션에 알렸습니다']) assert.ok(!h.includes(s), s);
  assert.match(mpSection({ card: { ...c, manager_told: false } }, b, 7), /관리자 세션에는 알리지 못했습니다/);   // 못 알린 것은 남긴다
  assert.equal((h.match(/<details class="mp-more"/g) || []).length, 1);          // 「자세히」는 하나
  assert.match(mpSection({ card: { ...c, pushed: true } }, b, 7), /push까지 했습니다\./);
  assert.match(mpSection({ card: { ...c, pushed: null } }, b, 7), /push는 아직입니다\./);    // 알 길이 없으면 「아직」
  assert.equal(mergedNote(card({ status: 'merged', note })), null);
  const old = mpSection({ card: card({ status: 'merged', note, manager_told: true }) }, b, 7);   // 갈래 없는 옛 카드는 전처럼
  assert.ok(old.split('<details class="mp-more"')[1].includes('본문에 원래 날짜') && old.includes('시험 · push · 브리지 다시 띄우기는 관리자가'));
  assert.match(mpSection({ card: card({ status: 'merged', merge_result: { ...mr, squash: false, count: 1, orig_ref: null } }) }, b, 7), /main에 커밋 1개를 합쳤습니다\./);
});
