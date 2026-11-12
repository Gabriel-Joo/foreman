import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mpSection, managerCard } from '../../bridge/static/js/handoff.js';

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
  assert.match(h, /승인하면 세션을 끝냅니다/);
  assert.match(h, /README:9 — 할 일 줄/);
  assert.match(h, /data-act="mp-merge" title="합치기 — 세션을 끝내고/);
  assert.match(h, /data-act="mp-skip"/);
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
