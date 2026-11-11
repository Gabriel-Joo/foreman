import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseFiles, filesText, startedLine } from '../../bridge/static/js/foremanchat.js';

// 11-11 교장 ① — 계획 카드에 세션 여럿(맡을 파일 · 합칠 순서 · 켜기)
test('맡을 파일 칸: 쉼표 · 줄바꿈으로 나누고 같은 것은 하나', () => {
  assert.deepEqual(parseFiles(' bridge/a.py, migrations/ \n bridge/a.py,,'), ['bridge/a.py', 'migrations/']);
  assert.deepEqual(parseFiles(''), []);
  assert.equal(filesText(['a.py', 'b/']), 'a.py, b/');
  assert.equal(filesText(undefined), '');
});

test('시작 결과: 둘 이상 띄웠을 때만 세션마다 한 마디', () => {
  assert.equal(startedLine({ sessions: [{ idx: 0, session_id: 1, title: 'A' }] }), '');
  assert.equal(startedLine({ sessions: [{ idx: 0, session_id: 1, title: 'A', tmux: 'cc-x', model: 'opus' },
    { idx: 1, session_id: null, title: 'B' }, { idx: 2, session_id: 3, role: 'designer' }] }),
  ' 띄운 세션 2개: 1「A」(tmux cc-x · opus), 3「designer」.');
});

test('카드가 세션별 칸을 보내고 서버는 그 칸을 믿는다(sessions_edit)', () => {
  const src = readFileSync(new URL('../../bridge/static/js/foremanchat.js', import.meta.url), 'utf8');
  assert.match(src, /sessions: \[first, \.\.\.rest\], sessions_edit: true/);
  assert.match(src, /data-k="on"/);
  assert.match(src, /id="fmFiles"/);
});
