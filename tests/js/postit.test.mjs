// 포스트잇(11-15) — 머리 탭 종이 숫자 · 목록(확인 전 흐리게, 끝난 것 같음, 코더 추천 [띄우기]) · 동작이 부르는 API
import test from 'node:test';
import assert from 'node:assert/strict';
import { badgeOf, listHtml, planText, act, firstLine, mmddhm, limitBlocked, todoGroups, onLimitInput, NO_REASON } from '../../bridge/static/js/postit.js';

const P = {
  foreman: { open: 3, oldest_at: '2026-11-13T01:00:00Z', nudge: null, likely_done: 1 },
  runshoes: { open: 1, oldest_at: '2026-11-10T01:00:00Z', nudge: { why: '가장 오래된 것 8일째' }, likely_done: 0 },
};

test('머리 탭 종이 — 지금 방 숫자(N장, 가장 오래된 날은 뺐다), 방이 아니면 모두 합, 못 읽으면 읽지 못했습니다', () => {
  const b = badgeOf(P, 'foreman');
  assert.equal(b.text, '포스트잇 3장');
  assert.equal(b.cls, '');
  assert.match(b.tip, /^포스트잇 — 아직 안 보낸 것 3장, 끝난 것 같음 1\. 누르면 펼칩니다\.$/);
  const all = badgeOf(P, null);
  assert.equal(all.text, '포스트잇 4장');
  assert.equal(all.cls, 'warn');                                   // 한 방이라도 쌓이면
  assert.match(all.tip, /쌓였습니다\(runshoes 가장 오래된 것 8일째\)\./);   // 주황의 까닭은 호버에(단추 글에서 날짜를 뺐다)
  assert.match(all.tip, /방마다: foreman 3, runshoes 1/);
  assert.match(badgeOf(P, 'runshoes').tip, /쌓였습니다\(가장 오래된 것 8일째\)\./);
  assert.ok(!all.text.includes('부터') && !all.tip.includes('11/10'));
  assert.match(badgeOf(null, 'foreman').tip, /읽지 못했습니다/);
  assert.deepEqual([badgeOf(null, 'foreman').text, badgeOf(null, 'foreman').cls], ['포스트잇 ?', 'warn']);   // 0처럼 보이지 않게
  assert.equal(badgeOf({ x: { open: 0 } }, 'x').text, '포스트잇 0장');
});

test('머리 탭 종이 — TODO 할 일 수와 30일 넘은 것은 호버에, 커밋이 끝냈다고 한 할 일이 있으면 주황(지우기는 사람이)', () => {
  const b = badgeOf({ infra: { open: 2, todo: { n: 40, old: 3, done: 0 } } }, 'infra');
  assert.equal(b.cls, '');
  assert.match(b.tip, /아직 안 보낸 것 2장\. 할 일 40, 30일 넘은 것 3\./);
  const d = badgeOf({ infra: { open: 0, todo: { n: 5, old: 0, done: 1 } } }, 'infra');
  assert.equal(d.cls, 'warn');
  assert.match(d.tip, /커밋이 끝냈다고 한 할 일 1개는 창에서 \[지우기\]로 지웁니다\./);
});

test('새 화면 글에 가운뎃점 · em dash가 없다(툴팁 첫 줄의 「제목 — 설명」 나눔만)', () => {
  const view = { project: 'foreman', summary: { oldest_at: '2026-11-13T01:00:00Z', oldest_days: 2, nudge: { why: '할 일 20장' } },
    items: [{ id: 1, body: 'a', source_label: '포스트잇에 적음', created_at: '2026-11-13T01:00:00Z', confirmed: false, state: 'new', label: '열림', source_ref: 't:5' }],
    closed: [{ id: 2, body: 'b', label: '삭제', state: 'drop' }], readme_checks: [] };
  const visible = listHtml(view).replace(/title="[^"]*"|data-tip="[^"]*"/g, '').replace(/<[^>]+>/g, ' ');
  assert.ok(!visible.includes('·') && !visible.includes('—'), visible);
  assert.ok(!badgeOf(P, 'foreman').text.includes('·'));
  // 11-15 포스트잇에 맞는 말 — 옛 말이 보이는 글에도 호버에도 남지 않는다
  const all = listHtml(view) + listHtml({ ...view, items: [] });
  for (const old of ['열린 것', '닫은 것', '열린 포스트잇', '가장 오래된 것', '여기에 바로 적습니다']) assert.ok(!all.includes(old), old);
  assert.match(all, /placeholder="할 일을 메모합니다"/);
  assert.match(all, /끝낸 것 1<\/summary>/);
  assert.match(all, /아직 안 보낸 것이 없습니다\./);
  assert.match(all, /docs\/TODO\.md를 읽지 못했습니다\./);           // 옛 브리지(view.todo 없음)는 0이 아니라 읽지 못함
});

const TODO = {
  path: 'docs/TODO.md', exists: true, error: null, prefix: 'infra', n: 3, old: 1, done: 1,
  items: [
    { id: 'infra-2', title: 'MySQL 승격을 앱 트래픽까지', date: '2026-11-10', days: 7, old: false, done_by: null },
    { id: 'infra-5', title: 'ingress-nginx 끊김 원인', date: '2026-10-01', days: 47, old: true, done_by: null },
    { id: 'infra-7', title: 'runshoes MySQL 정기 백업', date: '2026-11-12', days: 5, old: false, done_by: { commit: 'abc1234', subject: 'ops: 백업 (todo:infra-7)' }, limit_sent: false },
  ],
};

test('세 묶음 — 아직 안 보낸 것(적는 칸이 위, 줄마다 [TODO로] [한계로]), 할 일(번호와 제목만, [한계로]), 30일 넘은 것', () => {
  const view = { project: 'ronanlab-infra', summary: {}, readme_checks: [], closed: [], todo: TODO,
    items: [{ id: 11, body: '첫 줄\n둘째 줄 내용', source_label: '포스트잇에 적음', created_at: '2026-11-17T01:00:00Z', confirmed: true, state: 'new', label: '열림' }] };
  const h = listHtml(view);
  const at = (s) => h.indexOf(s);
  // 차례: 아직 안 보낸 것 머리 → 적는 칸 → 그 줄들 → 할 일 → 30일 넘은 것
  assert.ok(at('아직 안 보낸 것 <span class="pi-n">1</span>') < at('pi-draft') && at('pi-draft') < at('data-pi-row="11"'));
  assert.ok(at('data-pi-row="11"') < at('할 일 <span class="pi-n">2</span>') && at('할 일 <span class="pi-n">2</span>') < at('30일 넘은 것 <span class="pi-n">1</span>'));
  assert.ok(h.includes('data-pi-todo="11"') && h.includes('data-pi-limit="11" data-kind="postit"') && h.includes('data-pi-close="11" data-reason="drop"'));
  assert.ok(!h.includes('data-reason="limit"'));                                  // 옛 [→]는 없다
  // 세 묶음과 줄마다 펼침은 keep 열쇠로 기억한다(다시 그려도 접힘이 풀리지 않게, 처음값은 묶음 펼침 줄 접힘)
  for (const g of ['unsent', 'todo', 'old']) assert.match(h, new RegExp(`<details class="pi-group" data-pi-group="${g}"[^>]*data-keep="postit:ronanlab-infra:g:${g}"[^>]* open`));
  assert.match(h, /<details class="pi-main"[^>]*data-keep="postit:ronanlab-infra:p11"/);
  // 할 일 줄: 번호와 한 줄 제목, [한계로]. 내용(둘째 줄 등)은 없다
  assert.ok(h.includes('<b class="pi-tid">infra-2</b> MySQL 승격을 앱 트래픽까지'));
  assert.ok(h.includes('data-pi-limit="infra-2" data-kind="todo"') && !h.includes('data-pi-todo="infra-2"'));
  // 커밋이 끝냈다고 한 항목: 알림 칩과 [지우기](사람 단추)
  assert.ok(h.includes('커밋 abc1234이 끝냄') && h.includes('data-pi-tdel="infra-7"') && !h.includes('data-pi-tdel="infra-2"'));
  // 30일 넘은 것은 할 일 묶음에 겹쳐 보이지 않는다
  const g = todoGroups(TODO);
  assert.ok(g.old.includes('infra-5') && !g.now.includes('infra-5') && g.n === 2 && g.nOld === 1);
  assert.match(g.old, /47일째/);
});

test('할 일 묶음 — 파일이 없거나 번호 꼴이 아니면 그렇다고 보인다', () => {
  const none = todoGroups({ exists: false, error: '이 저장소에는 docs/TODO.md가 없습니다', items: [] });
  assert.match(none.now, /이 저장소에는 docs\/TODO\.md가 없습니다\./);
  const plain = todoGroups({ exists: true, error: 'docs/TODO.md에 번호 붙은 항목이 없습니다(이 저장소 꼴은 번호가 없습니다)', items: [] });
  assert.match(plain.now, /번호 붙은 항목이 없습니다/);
  assert.match(todoGroups({ exists: true, error: null, items: [] }).now, /할 일이 없습니다\./);
  assert.equal(todoGroups(null).n, '?');
});

test('[한계로] 칸 — 편 고르기와 까닭. 까닭이 비면 [보내기]가 꺼지고 막는 글이 보인다', () => {
  assert.equal(limitBlocked({ piece: 'notion/09.md', reason: '  ' }), NO_REASON);
  assert.match(limitBlocked({ piece: '', reason: '까닭' }), /편을 골라야/);
  assert.equal(limitBlocked({ piece: 'notion/09.md', reason: '서버가 한 대라 둘째 디스크가 없다' }), '');
  assert.match(limitBlocked({ piece: 'p', reason: 'x'.repeat(1001) }), /1000자까지/);
  const view = { project: 'foreman', summary: {}, readme_checks: [], closed: [], todo: TODO,
    items: [{ id: 4, body: 'a', source_label: '포스트잇에 적음', created_at: '2026-11-17T01:00:00Z', confirmed: true, state: 'new', label: '열림' }] };
  const pieces = [{ path: 'notion/09_limits.md', title: '알려진 한계', set: '기술문서' }];
  const open = listHtml(view, { lim: { kind: 'postit', id: '4', piece: 'notion/09_limits.md', reason: '' }, pieces });
  assert.match(open, /data-pi-lim-send="1" disabled/);
  assert.ok(open.includes('<option value="notion/09_limits.md" selected>기술문서: 알려진 한계</option>'));
  assert.ok(open.includes(NO_REASON.replace(/\[/g, '[')));
  const ok = listHtml(view, { lim: { kind: 'postit', id: '4', piece: 'notion/09_limits.md', reason: '까닭' }, pieces });
  assert.ok(!/data-pi-lim-send="1" disabled/.test(ok));
  // TODO 줄에서 연 칸은 그 줄 밑에만
  const t = listHtml(view, { lim: { kind: 'todo', id: 'infra-2', piece: '', reason: '' }, pieces });
  assert.ok(t.indexOf('data-pi-lim="1"') > t.indexOf('data-pi-trow="infra-2"') && t.indexOf('data-pi-lim="1"') < t.indexOf('data-pi-trow="infra-7"'));
  // 입력은 다시 그리지 않고 [보내기]만 켠다
  const send = { disabled: true }, why = { textContent: '', classList: { toggle() {} } };
  const box = { querySelector: (s) => (s === '[data-pi-lim-send]' ? send : why) };
  const ui = { lim: { kind: 'postit', id: '4', piece: 'notion/09_limits.md', reason: '' } };
  assert.equal(onLimitInput({ target: { value: '까닭 있음', classList: { contains: (c) => c === 'pi-lim-reason' }, closest: () => box } }, ui), true);
  assert.equal(ui.lim.reason, '까닭 있음');
  assert.equal(send.disabled, false);
  onLimitInput({ target: { value: '', classList: { contains: (c) => c === 'pi-lim-reason' }, closest: () => box } }, ui);
  assert.equal(send.disabled, true);
});

test('목록 — 확인 전은 흐리게, 끝난 것 같음은 근거와 [닫기] · [남기기], 코더 추천은 [띄우기], 줄마다 [TODO로] · [한계로] · [x]', () => {
  const view = {
    project: 'foreman',
    summary: { oldest_at: '2026-11-13T01:00:00Z', oldest_days: 2, last_check_at: '2026-11-15T07:30:00Z', check: { state: 'done', at: '2026-11-15T07:30:00Z', session_id: 9 } },
    items: [
      { id: 1, body: '그물이 찾음', source_label: '대화에서 찾음', source_ref: 't:77', created_at: '2026-11-13T01:00:00Z', confirmed: false, state: 'new', label: '열림' },
      { id: 2, body: '질문 카드 접기', source_label: '포스트잇에 적음', created_at: '2026-11-14T01:00:00Z', confirmed: true, state: 'new', label: '열림',
        check: { id: 31, session_id: 9, verdict: 'done', label: '끝난 것 같음', evidence: 'bridge/static/js/opanel.js:120', reason: '접힌다' } },
      { id: 3, body: '시험 DB 나누기', source_label: '대화에서 올림', created_at: '2026-11-14T02:00:00Z', confirmed: true, state: 'new', label: '열림',
        recommend: true, check: { id: 32, verdict: 'left', label: '남음', reason: '반만 됐다', coder: true } },
    ],
    readme_checks: [{ id: 40, item: 'L:2', item_text: '| CI 없음 |', verdict: 'done', evidence: '.github/workflows/test.yml:1', session_id: 9 }],
    closed: [],
  };
  const h = listHtml(view, { label: 'FOREMAN' });
  assert.match(h, /<div class="pi-head small"><b>FOREMAN<\/b><\/div>/);
  assert.match(h, /아직 안 보낸 것 <span class="pi-n">3<\/span>/);
  assert.match(listHtml({ ...view, items: view.items.slice(1) }, { label: 'FOREMAN' }).replace(/<[^>]+>/g, ''), /^FOREMAN끝난 것 같음/);
  // 11-15 쌓임 안내 줄은 뺐다(쌓임 표시는 단추 주황과 호버, 서기 말풍선이 맡는다). 쌓였어도 창에는 줄이 없다
  assert.ok(!listHtml({ ...view, summary: { ...view.summary, nudge: { why: '할 일 26장' } } }).includes('쌓였습니다'));
  assert.match(h, /class="pi-row pi-unconf" data-pi-row="1"/);
  assert.match(h, /\(대화에서 찾음, 11\/13, t:77\)/);
  assert.match(h, /<b>끝난 것 같음 2<\/b>/);
  assert.ok(h.includes('data-pi-check="31" data-act="close"') && h.includes('data-pi-check="40" data-act="keep"'));
  assert.ok(h.includes('<code>bridge/static/js/opanel.js:120</code>'));
  assert.ok(h.includes('data-pi-launch="3"') && !h.includes('data-pi-launch="2"'));
  for (const id of [1, 2, 3]) assert.ok(h.includes(`data-pi-close="${id}" data-reason="drop"`) && h.includes(`data-pi-todo="${id}"`) && h.includes(`data-pi-limit="${id}" data-kind="postit"`));
  assert.match(h, /저장 \(확인 전 1\)/);
  assert.ok(h.includes(`<span class="muted">마지막 갱신: ${mmddhm('2026-11-15T07:30:00Z')}</span>`));
});

test('[갱신] 옆 글 — 마지막으로 갱신한 때(월/일 시:분), 한 적이 없으면 「없음」', () => {
  assert.match(mmddhm('2026-11-15T07:30:00Z'), /^11\/1[56] \d\d:30$/);       // 보는 사람의 시각(시험 기계의 시간대에 따라 날 · 시가 다르다)
  assert.equal(mmddhm('x'), '');
  const base = { project: 'foreman', items: [], closed: [], readme_checks: [] };
  assert.match(listHtml({ ...base, summary: { check: null, last_check_at: null } }), /<span class="muted">마지막 갱신: 없음<\/span>/);
  assert.match(listHtml(base), /마지막 갱신: 없음/);
  assert.ok(!listHtml(base).includes('아직 하지 않았습니다'));
  // 지난 것이 실패였어도 그 전에 결과를 받은 때가 있으면 실패 글이 먼저다(조용히 가려지지 않게)
  const failed = listHtml({ ...base, summary: { last_check_at: '2026-11-14T07:30:00Z', check: { state: 'failed', session_id: 6 } } });
  assert.ok(failed.includes('결과 없이 끝났습니다') && !failed.includes('마지막 갱신:'));
});

test('[갱신] 상태 — 보는 중이면 단추가 꺼지고, 결과 없이 끝났으면 그렇게 보인다(조용히 사라지지 않게)', () => {
  const base = { project: 'foreman', items: [], closed: [], readme_checks: [] };
  const run = listHtml({ ...base, summary: { check: { state: 'running', at: new Date().toISOString(), session_id: 5 } } });
  assert.match(run, /조사 세션 5이 코드를 보는 중/);
  assert.match(run, /data-pi-refresh="1" disabled/);
  const bad = listHtml({ ...base, summary: { check: { state: 'failed', session_id: 6 } } });
  assert.match(bad, /class="bad">지난 \[갱신\]이 결과 없이 끝났습니다\(조사 세션 6\)/);
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

// 11-09 todoinbox.test.mjs에서 옮김(11-15 [＋ 할 일] 창을 빼며) — 사용자 지시서는 ━━━ 줄로 시작하는 일이 많다
test('목록 한 줄 — 구분선은 건너뛰고 첫 글 줄, 길면 자른다', () => {
  assert.equal(firstLine('━━━━━━━━\n질문 카드 — 답한 뒤에도 자리를 먹는다\n━━━━'), '질문 카드 — 답한 뒤에도 자리를 먹는다');
  assert.equal(firstLine('\n\n  터미널 입력 칸  \n둘째'), '터미널 입력 칸');
  assert.equal(firstLine('가'.repeat(80), 10), '가'.repeat(9) + '…');
  assert.equal(firstLine(''), '');
});

test('저장소에 넣은 기록 — 못 넣은 줄 밑에 까닭이 보이고, 맨 아래 접는 칸에 성공과 거부가 시각과 함께 남는다', () => {
  const view = { project: 'ronanlab-infra', summary: {}, readme_checks: [], closed: [], todo: { items: [] },
    items: [
      { id: 7, body: '백업 한 벌 더', source_label: '포스트잇에 적음', created_at: '2026-11-19T01:00:00Z', confirmed: true, state: 'new', label: '열림',
        repo_refused: '[TODO로] 못 넣었습니다. 저장소에 커밋 안 된 변경이 2개 있어 커밋하지 않았습니다(a.txt, b.txt)' },
      { id: 8, body: '다른 일', source_label: '포스트잇에 적음', created_at: '2026-11-19T01:00:00Z', confirmed: true, state: 'new', label: '열림', repo_refused: null },
    ],
    repo_log: [
      { id: 2, ok: false, note: '[TODO로] 못 넣었습니다. 저장소에 커밋 안 된 변경이 2개 있어 커밋하지 않았습니다(a.txt, b.txt)', created_at: '2026-11-19T01:05:00Z' },
      { id: 1, ok: true, note: 'ronanlab-infra 저장소 docs/TODO.md에 infra-44로 더했습니다(커밋 abc1234, push 안 함)', created_at: '2026-11-18T01:05:00Z' },
    ] };
  const h = listHtml(view);
  assert.equal((h.match(/class="small bad pi-refused"/g) || []).length, 1);               // 거부된 줄에만
  assert.match(h, /pi-refused[^>]*>\[TODO로\] 못 넣었습니다\. 저장소에 커밋 안 된 변경이 2개/);
  assert.match(h, /저장소에 넣은 기록 2/);
  assert.match(h, /못 함: \[TODO로\] 못 넣었습니다/);
  assert.match(h, /ronanlab-infra 저장소 docs\/TODO\.md에 infra-44로 더했습니다\(커밋 abc1234, push 안 함\)/);
  const none = listHtml({ ...view, repo_log: [], items: [] });
  assert.ok(!none.includes('저장소에 넣은 기록') && !none.includes('pi-refused'));        // 기록이 없으면 칸도 없다
  const old = listHtml({ ...view, repo_log: undefined });                                 // 옛 브리지 응답에도 그려진다
  assert.ok(!old.includes('저장소에 넣은 기록'));
});

test('동작 — [x] · [TODO로] · [한계로](까닭이 비면 보내지 않음) · [지우기] · [저장](확인 전 함께) · 판정 닫기가 부르는 API', async () => {
  const calls = [];
  globalThis.fetch = async (url, o) => {
    calls.push([url, o && o.body ? JSON.parse(o.body) : null]);
    if (url.startsWith('/api/postit/pieces')) return { ok: true, json: async () => ({ pieces: [{ path: 'notion/09.md', title: '한계', set: '기술문서' }] }) };
    return { ok: true, json: async () => ({ id: url.endsWith('/todo') ? 'foreman-124' : 9, confirmed: 1, commit: 'abc1234' }) };
  };
  const view = { items: [{ id: 1, confirmed: false }, { id: 2, confirmed: true }] };
  let draft = '새로 적은 것', note = null, drawn = 0;
  const ui = { lim: null, pieces: {} };
  const ctx = { store: { headers: () => ({}) }, project: 'foreman', view, draft: () => draft, setDraft: (v) => { draft = v; }, done: (n) => { note = n; return true; },
    ui, redraw: () => { drawn += 1; } };
  const ev = (attrs) => ({ preventDefault() {}, target: { closest: (sel) => {
    const k = sel.slice(1, -1);
    return k in attrs ? { dataset: attrs[k] } : null;
  } } });
  await act(ev({ 'data-pi-close': { piClose: '2', reason: 'drop' } }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/2/close', { reason: 'drop' }]);
  assert.match(note.msg, /지웠습니다/);
  await act(ev({ 'data-pi-todo': { piTodo: '2' } }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/2/todo', {}]);
  assert.match(note.msg, /foreman 저장소 docs\/TODO\.md에 foreman-124로 더하고 커밋했습니다\(abc1234\)\. push는 하지 않았습니다\./);
  // [한계로] — 칸을 열고 편 목록을 읽는다. 까닭이 비면 API를 부르지 않는다
  await act(ev({ 'data-pi-limit': { piLimit: 'foreman-3', kind: 'todo' } }), ctx);
  assert.deepEqual(ui.lim, { kind: 'todo', id: 'foreman-3', piece: '', reason: '' });
  assert.equal(ui.pieces.foreman.length, 1);
  assert.ok(drawn >= 2);
  ui.lim.piece = 'notion/09.md';
  const before = calls.length;
  await act(ev({ 'data-pi-lim-send': {} }), ctx);
  assert.equal(calls.length, before);                               // 까닭이 비어 보내지 않았다
  assert.equal(note.bad, true);
  assert.equal(note.msg, NO_REASON);
  assert.ok(ui.lim);                                                 // 칸은 열린 채
  ui.lim.reason = '  물리 서버가 한 대다  ';
  await act(ev({ 'data-pi-lim-send': {} }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/limit', { project: 'foreman', piece: 'notion/09.md', reason: '물리 서버가 한 대다', todo: 'foreman-3' }]);
  assert.equal(ui.lim, null);
  ui.lim = { kind: 'postit', id: '2', piece: 'notion/09.md', reason: '까닭' };
  await act(ev({ 'data-pi-lim-send': {} }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/limit', { project: 'foreman', piece: 'notion/09.md', reason: '까닭', postit: 2 }]);
  ui.lim = { kind: 'postit', id: '2', piece: '', reason: '' };
  await act(ev({ 'data-pi-lim-x': {} }), ctx);
  assert.equal(ui.lim, null);
  globalThis.confirm = () => true;
  await act(ev({ 'data-pi-tdel': { piTdel: 'infra-7' } }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/todo/remove', { project: 'foreman', id: 'infra-7' }]);
  delete globalThis.confirm;
  await act(ev({ 'data-pi-save': {} }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/save', { project: 'foreman', body: '새로 적은 것', confirm: [1] }]);
  assert.equal(draft, '');
  await act(ev({ 'data-pi-check': { piCheck: '31', act: 'close' } }), ctx);
  assert.deepEqual(calls.at(-1), ['/api/postit/check/31', { action: 'close' }]);
  assert.equal(await act(ev({}), ctx), false);                      // 포스트잇 단추가 아니면 넘긴다
});
