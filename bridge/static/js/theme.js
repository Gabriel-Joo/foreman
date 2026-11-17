// 테마 매핑 — 상태 · 도구 · 플래그 → 동작(10단계, docs/00_design.md 3.8). DOM도 Canvas도 모른다(node --test로 시험).
// 판정 순서: 상태(바탕) → ACTIVE일 때만 도구(첫 번째로 맞는 규칙) → 플래그(우선순위가 가장 높은 것 하나)가 위에 덮는다.
// 테마를 바꾸면 이 파일은 그대로, theme.json만 바뀐다.

const _globCache = new Map();

export function matchTool(pattern, tool) {
  // "Read|Grep" · "mcp__*" · "*" — 대소문자 구분, 전체 일치
  if (!tool) return pattern === '*';
  let rx = _globCache.get(pattern);
  if (!rx) {
    const alts = pattern.split('|').map((p) => p.replace(/[.+?^${}()[\]\\]/g, '\\$&').replace(/\*/g, '.*'));
    rx = new RegExp(`^(?:${alts.join('|')})$`);
    _globCache.set(pattern, rx);
  }
  return rx.test(tool);
}

const _rxCache = new Map();
function matchTarget(pattern, target) {
  // 규칙의 target(정규식 문자열)은 도구 대상(Bash 명령 등)에 — 없으면 늘 맞다. 잘못된 정규식은 안 맞는 것으로
  if (!pattern) return true;
  let rx = _rxCache.get(pattern);
  if (rx === undefined) {
    try { rx = new RegExp(pattern); } catch { rx = null; }
    _rxCache.set(pattern, rx);
  }
  return !!rx && rx.test(target || '');
}

// 턴이 끝나도 도는 일 — 서브에이전트 + 백그라운드 Bash · Monitor(11-06)
export function bgCount(s) {
  return s ? (s.subagents_running || 0) + ((s.background || []).length) : 0;
}

// 화면에 그릴 상태 — 서버 상태 값은 늘리지 않고(docs/00_design.md 3.11), IDLE인데 자식 일이 돌면 WAITING(기다림)으로 그린다.
// 11-06: 백그라운드 판정이 도는데 캐릭터가 엎드려 자고 있었다
export function viewState(s) {
  return s && s.state === 'IDLE' && bgCount(s) > 0 ? 'WAITING' : s && s.state;
}

const WAITING_DEFAULT = { anim: 'wait', go: 'desk' };     // 테마에 WAITING이 없으면 — 자는 모습(IDLE 변형)으로 떨어지지 않게

export function resolveAction(theme, { state, tool, target, flags, role } = {}) {
  const states = theme.states || {};
  const base = states[state] || (state === 'WAITING' ? WAITING_DEFAULT : null) || states.IDLE || {};
  const out = { ...base, state: state || 'IDLE', source: 'state' };
  // 역할별 쉼 자리(12a) — 서기는 쉬어도 서고에서 읽는다. 쉼 변형(자기 · 먹기)은 섞지 않는다
  const ri = state === 'IDLE' && role ? ((theme.roles || {}).idle || {})[role] : null;
  if (ri && ri.go) {
    const { _, ...r } = ri;
    Object.assign(out, r, { source: `role:${role}` });
    delete out.variants;
  }
  if (state === 'ACTIVE' && tool) {
    const rule = (theme.tools || []).find((r) => matchTool(r.match, tool) && matchTarget(r.target, target));
    if (rule) {
      const { match, target: t, ...rest } = rule;
      Object.assign(out, rest, { source: `tool:${match}${t ? ' ~ ' + t.slice(0, 24) : ''}` });
    }
  }
  // 플래그 — 얼어붙은(SUSPENDED) · 잠든(DORMANT) 세션도 승인 대기면 손을 든다(사람이 봐야 하는 것)
  let best = null;
  for (const [name, on] of Object.entries(flags || {})) {
    const f = on && (theme.flags || {})[name];
    if (f && (!best || (f.priority || 0) > (best.f.priority || 0))) best = { name, f };
  }
  if (best) {
    const { priority, ...rest } = best.f;
    Object.assign(out, rest, { flag: best.name });
  }
  return out;
}

export function infraAction(theme, status) {
  const m = theme.infra || {};
  return { ...(m[status] || m.none || {}), status: status || 'none' };
}

export function groupSubagents(descs, cap = 10) {
  // 설명의 공통 앞부분으로 묶음 이름 — "Wide yes/no search wn1" · "… wn2" → "Wide yes/no search"(docs/00_design.md 3.8)
  const list = (descs || []).filter(Boolean);
  const shown = list.slice(0, cap);
  const hidden = Math.max(0, list.length - cap);
  let prefix = '';
  if (list.length > 1) {
    prefix = list.reduce((a, b) => { let i = 0; while (i < a.length && a[i] === b[i]) i++; return a.slice(0, i); });
    prefix = prefix.replace(/[\s\-_:·]*\w{0,3}$/, '').trim();
    if (prefix.length < 4) prefix = '';
  }
  return { shown, hidden, label: prefix };
}

export function tokenRate(history, now, windowMs) {
  // history: [{t, v}] 누적 토큰(오늘). 창 안의 증가량 — 자정에 줄어들면 0부터 다시 센다
  const inWin = (history || []).filter((h) => now - h.t <= windowMs);
  if (inWin.length < 2) return 0;
  let sum = 0;
  for (let i = 1; i < inWin.length; i++) sum += Math.max(0, inWin[i].v - inWin[i - 1].v);
  return sum;
}
