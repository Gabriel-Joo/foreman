import { test } from 'node:test';
import assert from 'node:assert/strict';
import { slashIntent } from '../../bridge/static/js/slash.js';

test('/로 시작하지 않으면 글', () => {
  assert.equal(slashIntent('확인해줘').kind, 'text');
  assert.equal(slashIntent(' /compact').kind, 'text');
});

test('경로 · 여러 줄 · 기호는 글로 보낸다', () => {
  assert.equal(slashIntent('/api/sessions 왜 404야?').kind, 'text');
  assert.equal(slashIntent('/home/kopo17/foo 봐줘').kind, 'text');
  assert.equal(slashIntent('/compact\n그리고 이것도').kind, 'text');
  assert.equal(slashIntent('/ 이거').kind, 'text');
  assert.equal(slashIntent('/123').kind, 'text');
});

test('아는 명령은 바로, 맥락을 날리는 명령은 확인, 모르는 것은 묻는다', () => {
  assert.deepEqual(slashIntent('/compact 결정만 남겨'), { kind: 'command', name: 'compact' });
  assert.deepEqual(slashIntent('/model sonnet'), { kind: 'command', name: 'model' });
  assert.deepEqual(slashIntent('/anthropic-skills:docs'), { kind: 'command', name: 'anthropic-skills:docs' });
  assert.deepEqual(slashIntent('/clear'), { kind: 'confirm', name: 'clear' });
  assert.deepEqual(slashIntent('/EXIT'), { kind: 'confirm', name: 'exit' });
  assert.deepEqual(slashIntent('/etc 폴더 봐줘'), { kind: 'ask', name: 'etc' });
});
