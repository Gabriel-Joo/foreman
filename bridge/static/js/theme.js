// 테마 매핑 — 상태 · 도구 · 플래그 → 동작(10단계, README 3.8). DOM도 Canvas도 모른다(node --test로 시험).
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

export function resolveAction(theme, { state, tool, flags } = {}) {
  const states = theme.states || {};
  const base = states[state] || states.IDLE || {};
  const out = { ...base, state: state || 'IDLE', source: 'state' };
  if (state === 'ACTIVE' && tool) {
    const rule = (theme.tools || []).find((r) => matchTool(r.match, tool));
    if (rule) {
      const { match, ...rest } = rule;
      Object.assign(out, rest, { source: `tool:${match}` });
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
  // 설명의 공통 앞부분으로 묶음 이름 — "Wide yes/no search wn1" · "… wn2" → "Wide yes/no search"(README 3.8)
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
