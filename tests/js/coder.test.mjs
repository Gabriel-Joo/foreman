// 코더 상주(11-09) — 맡길 일 세기 · 머리 위 말풍선 · 받은 할 일 상태 호버 · 쉬게 한 날수
import test from 'node:test';
import assert from 'node:assert/strict';
import { coderJobs, coderBubble, isCoder } from '../../bridge/static/js/coder.js';
import { stateTip } from '../../bridge/static/js/todoinbox.js';
import { restDays } from '../../bridge/static/js/handoff.js';

const st = (o = {}) => ({
  sessions: new Map((o.sessions || []).map((s) => [s.id, s])),
  approvals: new Map((o.approvals || []).map((a, i) => [i, a])),
  pipeline: new Map(Object.entries(o.pipeline || {})),
});

test('맡길 일 — 받은 할 일 · 쉬게 한 일 · 파이프라인 실패 · 빌드 알림 없음 · 승인 대기 · 권한 거부, 다른 방 · 끝난 세션 · 질문은 빼고', () => {
  const data = { inbox: [{ id: 7, body: '━━━\n화면 고치기\n둘째', created_at: '2026-11-09T10:00:00Z' }],
                 rested: [{ session_id: 3, title: '화면', branch: 'cc/x', days: 2, rested_at: '2026-11-07T10:00:00Z' }] };
  const s = st({
    sessions: [{ id: 1, project: 'foreman', state: 'IDLE', denied: { tool: 'Bash' }, title: '하나' },
               { id: 2, project: 'foreman', state: 'DORMANT', denied: { tool: 'Bash' } },
               { id: 9, project: 'runshoes', state: 'IDLE', denied: { tool: 'Bash' } }],
    approvals: [{ status: 'pending', session_id: 1, tool: 'Bash' }, { status: 'pending', session_id: 1, tool: 'AskUserQuestion' },
                { status: 'pending', session_id: 9, tool: 'Bash' }, { status: 'done', session_id: 1, tool: 'Bash' }],
    pipeline: { foreman: { chains: [{ broke: '빌드' }], watch: { state: 'missing' } } },
  });
  const j = coderJobs('foreman', data, s);
  assert.deepEqual(j.map((x) => x.kind), ['inbox', 'rested', 'pipe', 'build', 'appr', 'denied']);
  assert.equal(j[0].title, '화면 고치기');
  assert.equal(j.find((x) => x.kind === 'appr').n, 1);                         // 질문(AskUserQuestion)은 승인이 아니다
  assert.deepEqual(coderJobs('petmint', null, st()), []);
});

test('맡길 일 — 끝난 뒤 어긋난 것(11-11 drift)은 쉬게 한 일 뒤에', () => {
  const j = coderJobs('foreman', { rested: [], drift: [{ kind: 'dirty', session_id: 4, detail: '세션 4이 끝났는데 커밋 안 된 변경이 2개 있습니다' }] }, st());
  assert.deepEqual(j.map((x) => [x.kind, x.sid]), [['drift', 4]]);
  assert.match(j[0].title, /커밋 안 된 변경/);
});

test('말풍선 — 쉬게 한 일만이면 "맡은 일 N — 합치기 기다림", 하루 넘으면 N일째, 섞이면 맡길 일', () => {
  assert.equal(coderBubble([]), null);
  assert.equal(coderBubble([{ kind: 'rested', days: 0 }]), '맡은 일 1 — 합치기 기다림');
  assert.equal(coderBubble([{ kind: 'rested', days: 3 }, { kind: 'rested', days: 1 }]), '맡은 일 2 — 합치기 기다림 · 3일째');
  assert.equal(coderBubble([{ kind: 'inbox' }, { kind: 'appr' }]), '맡길 일 2');
  assert.equal(coderBubble([{ kind: 'inbox' }, { kind: 'rested', days: 2 }]), '맡길 일 2 · 합치기 기다림 1 · 2일째');
});

test('코더 세션 — 역할 없음 · coder만', () => {
  assert.ok(isCoder({}) && isCoder({ role: 'coder' }));
  assert.ok(!isCoder({ role: 'scribe' }) && !isCoder({ role: 'inspector' }) && !isCoder({ role: 'cicd' }));
});

test('받은 할 일 상태 호버 — 받는 사람마다', () => {
  assert.match(stateTip({ state: 'moved', label: '끝남', assignee: 'coder', taken_by: 5 }), /^끝남 — 세션 5이 이 일을 마쳤습니다/);
  assert.match(stateTip({ state: 'moved', label: '옮김', assignee: 'scribe' }), /README/);
  assert.match(stateTip({ state: 'new', label: '새로', assignee: 'coder' }), /코더를 누르면/);
});

test('쉬게 한 날수', () => {
  const now = Date.parse('2026-11-09T12:00:00Z');
  assert.equal(restDays('2026-11-09T01:00:00Z', now), 0);
  assert.equal(restDays('2026-11-07T11:00:00Z', now), 2);
});
