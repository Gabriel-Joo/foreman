// 포스트잇(11-15) — 머리 탭 종이 숫자 · 목록(확인 전 흐리게, 끝난 것 같음, 코더 추천 [띄우기]) · 동작이 부르는 API
import test from 'node:test';
import assert from 'node:assert/strict';
import { badgeOf, listHtml, planText, act, firstLine } from '../../bridge/static/js/postit.js';

const P = {
  foreman: { open: 3, oldest_at: '2026-11-13T01:00:00Z', nudge: null, likely_done: 1 },
  runshoes: { open: 1, oldest_at: '2026-11-10T01:00:00Z', nudge: { why: '가장 오래된 것 8일째' }, likely_done: 0 },
};

test('머리 탭 종이 — 지금 방 숫자와 가장 오래된 날, 방이 아니면 모두 합, 못 읽으면 읽지 못했습니다', () => {
  const b = badgeOf(P, 'foreman');
  assert.equal(b.text, '포스트잇 3, 11/13부터');
  assert.equal(b.cls, '');
  assert.match(b.tip, /^포스트잇 — 열린 할 일 3개.*끝난 것 같음 1/);
  const all = badgeOf(P, null);
  assert.equal(all.text, '포스트잇 4, 11/10부터');
  assert.equal(all.cls, 'warn');                                   // 한 방이라도 쌓이면
  assert.match(all.tip, /방마다: foreman 3, runshoes 1/);
  assert.match(badgeOf(null, 'foreman').tip, /읽지 못했습니다/);
  assert.deepEqual([badgeOf(null, 'foreman').text, badgeOf(null, 'foreman').cls], ['포스트잇 ?', 'warn']);   // 0처럼 보이지 않게
  assert.equal(badgeOf({ x: { open: 0 } }, 'x').text, '포스트잇 0');
});

test('새 화면 글에 가운뎃점 · em dash가 없다(툴팁 첫 줄의 「제목 — 설명」 나눔만)', () => {
  const view = { project: 'foreman', summary: { oldest_at: '2026-11-13T01:00:00Z', oldest_days: 2, nudge: { why: '열린 것 20개' } },
    items: [{ id: 1, body: 'a', source_label: '[＋ 할 일]', created_at: '2026-11-13T01:00:00Z', confirmed: false, state: 'new', label: '열림', source_ref: 't:5' }],
    closed: [{ id: 2, body: 'b', label: '삭제', state: 'drop' }], readme_checks: [] };
  const visible = listHtml(view).replace(/title="[^"]*"|data-tip="[^"]*"/g, '').replace(/<[^>]+>/g, ' ');
  assert.ok(!visible.includes('·') && !visible.includes('—'), visible);
  assert.ok(!badgeOf(P, 'foreman').text.includes('·'));
});

test('목록 — 확인 전은 흐리게, 끝난 것 같음은 근거와 [닫기] · [남기기], 코더 추천은 [띄우기], 줄마다 [x] · [→]', () => {
  const view = {
    project: 'foreman',
    summary: { oldest_at: '2026-11-13T01:00:00Z', oldest_days: 2, check: { state: 'done', at: '2026-11-15T01:00:00Z', session_id: 9 } },
    items: [
      { id: 1, body: '그물이 찾음', source_label: '대화에서 찾음', source_ref: 't:77', created_at: '2026-11-13T01:00:00Z', confirmed: false, state: 'new', label: '열림' },
      { id: 2, body: '질문 카드 접기', source_label: '[＋ 할 일]', created_at: '2026-11-14T01:00:00Z', confirmed: true, state: 'new', label: '열림',
        check: { id: 31, session_id: 9, verdict: 'done', label: '끝난 것 같음', evidence: 'bridge/static/js/opanel.js:120', reason: '접힌다' } },
      { id: 3, body: '시험 DB 나누기', source_label: '대화에서 올림', created_at: '2026-11-14T02:00:00Z', confirmed: true, state: 'new', label: '열림',
        recommend: true, check: { id: 32, verdict: 'left', label: '남음', reason: '반만 됐다', coder: true } },
    ],
    readme_checks: [{ id: 40, item: 'L:2', item_text: '| CI 없음 |', verdict: 'done', evidence: '.github/workflows/test.yml:1', session_id: 9 }],
    closed: [],
  };
  const h = listHtml(view, { label: 'FOREMAN' });
  assert.match(h, /열린 것 3, 확인 전 1, 가장 오래된 것 11\/13\(2일째\)/);
  assert.match(h, /class="pi-row pi-unconf" data-pi-row="1"/);
  assert.match(h, /\(대화에서 찾음, 11\/13, t:77\)/);
  assert.match(h, /<b>끝난 것 같음 2<\/b>/);
  assert.ok(h.includes('data-pi-check="31" data-act="close"') && h.includes('data-pi-check="40" data-act="keep"'));
  assert.ok(h.includes('<code>bridge/static/js/opanel.js:120</code>'));
  assert.ok(h.includes('data-pi-launch="3"') && !h.includes('data-pi-launch="2"'));
  for (const id of [1, 2, 3]) assert.ok(h.includes(`data-pi-close="${id}" data-reason="drop"`) && h.includes(`data-pi-close="${id}" data-reason="limit"`));
  assert.match(h, /저장 \(확인 전 1\)/);
  assert.match(h, /마지막 \[갱신\]/);
});

test('[갱신] 상태 — 보는 중이면 단추가 꺼지고, 결과 없이 끝났으면 그렇게 보인다(조용히 사라지지 않게)', () => {
  const base = { project: 'foreman', items: [], closed: [], readme_checks: [] };
  const run = listHtml({ ...base, summary: { check: { state: 'running', at: new Date().toISOString(), session_id: 5 } } });
  assert.match(run, /점검 세션 5이 코드를 보는 중/);
  assert.match(run, /data-pi-refresh="1" disabled/);
  const bad = listHtml({ ...base, summary: { check: { state: 'failed', session_id: 6 } } });
  assert.match(bad, /class="bad">지난 \[갱신\]이 결과 없이 끝났습니다\(점검 세션 6\)/);
  assert.match(listHtml(null, { bad: true }), /포스트잇을 읽지 못했습니다/);
});

test('계획 창 글 — 번호 · 날 · 본문, 점검 까닭을 덧붙인다', () => {
  const t = planText([{ id: 8, body: '목록에서 바로 시작\n둘째 줄', created_at: '2026-11-11T00:00:00Z', check: { reason: '반만 됐다' } }]);
  assert.match(t, /^포스트잇 하나로 계획을/);
  assert.match(t, /#8 \(11\/11\)\n목록에서 바로 시작\n둘째 줄\n\(점검: 반만 됐다\)$/);
  assert.match(planText([{ id: 1, body: 'a' }, { id: 2, body: 'b' }]), /^포스트잇 2개를 묶어/);
  assert.equal(planText([]), '');
  assert.equal(firstLine('━━━\n질문 카드\n━━━'), '질문 카드');
});

test('동작 — [x] · [→] · [저장](확인 전 함께) · 판정 닫기가 부르는 API', async () => {
  const calls = [];
  globalThis.fetch = async (url, o) => { calls.push([url, JSON.parse(o.body)]); return { ok: true, json: async () => ({ id: 9, confirmed: 1 }) }; };
  const view = { items: [{ id: 1, confirmed: false }, { id: 2, confirmed: true }] };
  let draft = '새로 적은 것', note = null;
  const ctx = { store: { headers: () => ({}) }, project: 'foreman', view, draft: () => draft, setDraft: (v) => { draft = v; }, done: (n) => { note = n; return true; } };
  const ev = (attrs) => ({ preventDefault() {}, target: { closest: (sel) => {
    const k = sel.slice(1, -1);
    return k in attrs ? { dataset: attrs[k] } : null;
  } } });
  await act(ev({ 'data-pi-close': { piClose: '2', reason: 'limit' } }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/2/close', { reason: 'limit' }]);
  assert.match(note.msg, /알려진 한계로 보냈습니다/);
  await act(ev({ 'data-pi-save': {} }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/save', { project: 'foreman', body: '새로 적은 것', confirm: [1] }]);
  assert.equal(draft, '');
  await act(ev({ 'data-pi-check': { piCheck: '31', act: 'close' } }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/check/31', { action: 'close' }]);
  assert.equal(await act(ev({}), ctx), false);                      // 포스트잇 단추가 아니면 넘긴다
});
