// '/'로 시작하는 입력을 CC 명령으로 실행할지 글로 보낼지(11-05 사용자 요청 — '/ 명령' 체크박스를 없앴다).
// 경로("/api/foo …")나 여러 줄은 글, 아는 명령은 명령, 맥락을 날리는 명령은 확인, 모르는 /낱말은 묻는다.
// 서버(bridge/inject.guarded)는 이 판정을 command 값으로 받는다 — false면 앞에 공백을 붙여 글로, true면 그대로 명령으로 보낸다.
// '!'(bash 모드)는 여기서 가르지 않는다. 입력 API가 bang_check로 승인 규칙 ask, sudo, 여러 줄, 빈 명령만 막고 나머지는 그대로 보낸다(11-09).

// CC 내장 명령 중 자주 쓰는 것(+ 이 저장소 · 사용자 스킬은 모를 수 있다 → ask)
export const KNOWN = new Set(['compact', 'model', 'cost', 'context', 'usage', 'status', 'memory', 'help', 'config', 'init',
  'review', 'mcp', 'agents', 'hooks', 'permissions', 'effort', 'rewind', 'todos', 'export', 'add-dir', 'doctor', 'plan',
  'fast', 'loop', 'schedule', 'resume', 'rename', 'btw', 'code-review', 'simplify', 'security-review', 'ide', 'vim',
  'statusline', 'release-notes', 'bug', 'feedback', 'insights', 'artifacts', 'tasks', 'workflows', 'skills']);
// 실행하면 맥락이 사라지거나 세션이 끝난다 — 한 번 묻는다(끝내기는 패널 버튼이 있다)
export const RISKY = new Set(['clear', 'exit', 'quit', 'logout', 'login']);

// → { kind: 'text' } | { kind: 'command', name } | { kind: 'confirm', name } | { kind: 'ask', name }
export function slashIntent(text) {
  const t = String(text || '');
  if (!t.startsWith('/')) return { kind: 'text' };
  if (t.trim().includes('\n')) return { kind: 'text' };            // 여러 줄 붙여넣기는 글
  const m = /^\/([A-Za-z][\w:.-]*)(?=\s|$)/.exec(t);
  if (!m) return { kind: 'text' };                                  // "/api/foo", "/ 뭐" — 경로 · 기호
  const name = m[1].toLowerCase();
  if (RISKY.has(name)) return { kind: 'confirm', name };
  if (KNOWN.has(name) || name.includes(':')) return { kind: 'command', name };   // plugin:skill 꼴은 명령
  return { kind: 'ask', name };
}
