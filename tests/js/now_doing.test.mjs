// 패널 머리줄 · 호버 다듬기(11-14 사용자 「설명이 과하다」) — Bash 명령 대신 하는 일, 따로 작업 호버, 모델 호버
import test from 'node:test';
import assert from 'node:assert/strict';
import { bashHead, bashDoing, nowDoing, doingHtml, worktreeTip, modelChip } from '../../bridge/static/js/render.js';

test('앞의 cd · 변수 · timeout을 벗긴 첫 명령', () => {
  assert.equal(bashHead('cd /x/y && PYTHONPATH=. timeout 300 .venv/bin/python -m pytest -q'), '.venv/bin/python -m pytest -q');
  assert.equal(bashHead('T=$(grep x f) ; curl -s a'), 'T=$(grep x f) ; curl -s a');   // 괄호 든 값은 벗기지 않는다 — 「명령 실행 중」쪽이 낫다
});

test('명령 머리로 흔한 일을 가른다', () => {
  const cases = [
    ['timeout 500 .venv/bin/python -m pytest -q -x 2>&1 | tail -3', '시험 돌리는 중'],
    ['node --test tests/js/', '시험 돌리는 중'],
    ['cd /a && git commit -q -m "fix: x"', '커밋하는 중'],
    ['git push origin main', 'push하는 중'],
    ['git merge-tree --write-tree main cc/x', '합칠 수 있는지 보는 중'],
    ['git add a b && git commit -m x', '변경 정리하는 중'],
    ['git log --oneline -3', '변경 기록 보는 중'],
    ['PYTHONPATH=. .venv/bin/python tools/screen.py --no-term', '화면 점검하는 중'],
    ['grep -rn foo bridge', '찾는 중'],
    ['sed -n 1,20p a.py', '파일 보는 중'],
    ['curl -s http://127.0.0.1:8000/api/dashboard', 'API 부르는 중'],
    ['systemctl --user status foreman-bridge', '서비스 보는 중'],
    ['python3 -c "print(1)"', '스크립트 돌리는 중'],
    ['echo "credit(bridge config tests): $(grep -rn \'c\' x)"', '명령 실행 중'],
    ['S=/tmp/x; mkdir -p $S/a; PYTHONPATH=. timeout 300 .venv/bin/python tools/screen.py --no-term', '화면 점검하는 중'],   // 준비 명령은 건너뛴다
    ['T=$(grep -E x .env.bridge | cut -d= -f2-); curl -s -H "a" http://x', 'API 부르는 중'],
    ['mkdir -p a', '명령 실행 중'],
  ];
  for (const [cmd, want] of cases) assert.equal(bashDoing(cmd), want, cmd);
});

test('Bash는 하는 일 + 호버에 명령, 서버 description이 오면 그것이 먼저', () => {
  const a = { tool: 'Bash', target: 'node --test tests/js/' };
  assert.deepEqual(nowDoing(a), { text: '시험 돌리는 중', tip: '명령 — 지금 돌리는 명령입니다.\nnode --test tests/js/', tool: 'Bash' });
  assert.equal(nowDoing({ ...a, description: '합친 뒤 pytest와 node 시험' }).text, '합친 뒤 pytest와 node 시험');
  const en = { ...a, description: 'Run the node test suite' };      // 영어여도 CC가 쓴 그대로, 끝에 「중」을 붙이지 않는다
  assert.equal(nowDoing(en).text, 'Run the node test suite');
  assert.match(doingHtml(en), /^<span data-tip="명령 — [^"]*">Run the node test suite<\/span>$/);   // 명령은 그대로 호버
  assert.equal(nowDoing({ ...a, description: null }).text, '시험 돌리는 중');                       // 설명이 없으면 표
  assert.equal(nowDoing({ ...a, description: '' }).text, '시험 돌리는 중');
  assert.ok(nowDoing({ ...a, description: 'x'.repeat(100) }).text.length <= 60);
  assert.equal(nowDoing({ tool: 'Read', target: 'a.js', description: '무시' }).text, 'Read a.js');   // Bash가 아니면 쓰지 않는다
  assert.match(doingHtml(a), /^<span data-tip="명령 — [^"]*">시험 돌리는 중<\/span>$/);
  assert.ok(!doingHtml({ tool: 'Bash', target: 'echo "<b>"' }).includes('<b>'));   // 명령 글은 이스케이프
});

test('다른 도구는 전처럼 도구 + 대상, 호버 없음', () => {
  assert.equal(doingHtml({ tool: 'Read', target: 'bridge/static/js/render.js' }), 'Read bridge/static/js/render.js');
  assert.equal(nowDoing(null).text, '');
});

test('따로 작업 호버는 worktree 이름과 브랜치만', () => {
  const s = { cwd: '/home/u/AI_programming/foreman/.worktrees/foreman-2', short: 'abc123', tmux_pane: '%12' };
  assert.equal(worktreeTip(s), '작업방 — foreman-2(브랜치 cc/foreman-2)에서 일합니다.');
  assert.equal(worktreeTip({ ...s, merge_wait: { since: 'x' } }), '작업방 — foreman-2(브랜치 cc/foreman-2)에서 일합니다. 합치기를 기다립니다.');
  assert.equal(worktreeTip({ cwd: '/home/u/AI_programming/foreman' }), '');
  assert.ok(!/abc123|%12|\/home/.test(worktreeTip(s)));
});

test('응답 전에는 띄울 때 고른 모델을 같은 이름 꼴로, 응답이 오면 실제 모델', () => {
  const s = { model: null, model_req: 'claude-sonnet-5-5' };
  const h = modelChip(s, null, true);
  assert.ok(h.includes('Sonnet 5.5') && h.includes('mdl-pre') && h.includes('f-sonnet'), h);
  assert.ok(modelChip(s, null, false).includes('띄울 때 고른 모델입니다. 첫 응답이 오면 실제로 쓴 모델로 바뀝니다.'));
  assert.ok(!modelChip(s, null, false).includes('고른 것'));
  const live = modelChip({ ...s, model: 'claude-opus-5-5', model_label: 'Opus 5.5', model_family: 'opus' }, null, false);
  assert.ok(live.includes('Opus 5.5') && !live.includes('mdl-pre') && !live.includes('Sonnet'), live);
  assert.equal(modelChip({ model: null }, null, false), '');
});

test('모델 호버 — /model을 빼고 읽기 쉬운 이름', () => {
  const s = { model: 'claude-opus-5-5', model_label: 'Opus 5.5', model_family: 'opus' };
  const h = modelChip(s, null, true);
  assert.ok(h.includes('모델 — 눌러서 이 세션의 모델을 바꿉니다. 지금 Opus 5.5.'), h);
  assert.ok(!h.includes('/model') && !h.includes('claude-opus-5-5'));
  assert.ok(modelChip(s, null, false).includes('마지막 응답에 쓴 모델입니다(Opus 5.5)'));
});
