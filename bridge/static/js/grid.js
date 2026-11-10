// 방 모눈(11-10 사용자 — 「화면 모눈으로 다시 짜기」). DOM · 캔버스를 모른다(node --test로 시험, tests/js/grid.test.mjs).
// 세 테마(현장 · 마법학교 · 오피스)가 themes/_shared/grid.json 한 벌을 쓴다 — 방 칸 · 복도 · 출하 단계 자리는 같고,
// 테마는 방 이름 · 그림 · 색만 갈아끼운다. 한 칸 = 1타일 = 캐릭터 한 명. 이름표는 방 왼쪽 위 칸에 고정(자리 고르기 없음).

export const INFRA_STAGES = ['jenkins', 'harbor', 'argocd'];

// 모눈 입히기 — theme를 그 자리에서 바꾼다.
// ① 구역 키 → 역할(tags.roles) → 모눈의 방 칸을 z.x · y · w · h로 ② 출하장(infra) = 모눈 ship, 단계 x = 출하장 x + ship[단계]
// ③ 자리(seats · seat · stand)는 그 방 기준 — 방이 없는 자리 묶음(manager · designer · coder_home)은 z.in으로 방을 고른다
// ④ 가구(sprites.decor)는 d.in(구역 키)이 있으면 그 방 기준 ⑤ 출하 담당 자리(infra.stands)는 단계 기준, home은 출하장 기준
export function applyGrid(theme, g) {
  const L = theme.layout, roles = (theme.tags && theme.tags.roles) || {};
  L.room = { ...g.room };
  L.corridors = g.corridors.map((r) => r.slice());
  const rooms = {};
  for (const [key, role] of Object.entries(roles)) {
    const r = g.rooms[role], z = L.zones[key];
    if (!r || !z) continue;
    [z.x, z.y, z.w, z.h] = r;
    rooms[key] = r;
  }
  const s = g.rooms.ship, iz = L.zones.infra;
  if (s && iz) {
    [iz.x, iz.y, iz.w, iz.h] = s;
    iz.stageW = g.ship.w;
    for (const k of INFRA_STAGES) iz[k] = { ...(iz[k] || {}), x: s[0] + g.ship[k] };
    rooms.infra = s;
    for (const [k, p] of Object.entries(iz.stands || {})) { p[0] += k === 'home' ? s[0] : iz[k].x; p[1] += s[1]; }
  }
  const shift = (p, o) => { p[0] += o[0]; p[1] += o[1]; };
  for (const [key, z] of Object.entries(L.zones)) {
    if (!z || typeof z !== 'object' || key === 'infra' || key === 'lounge_seats') continue;
    const host = rooms[z.in || key];
    if (!host) continue;
    for (const p of z.seats || []) shift(p, host);
    if (z.seat) shift(z.seat, host);
    if (z.stand) shift(z.stand, host);
  }
  for (const d of (theme.sprites && theme.sprites.decor) || []) {
    const host = d.in && rooms[d.in];
    if (host) { d.x += host[0]; d.y += host[1]; }
  }
  theme.grid = g;
  theme.gridRooms = rooms;
  return theme;
}

// 모눈 점검 ①② — grid.json만 본다(그림 크기를 몰라도 되는 것). 문제 글 목록을 돌려준다(빈 목록 = 통과).
// ① 두 방이 같은 칸을 쓰지 않는가 · 방 · 복도가 걸을 수 있는 안쪽(x 1~27, y 2~17) 밖으로 나가지 않는가 · 방과 복도가 겹치지 않는가 · 칸이 정수인가
// ② 복도 칸이 하나로 이어지는가(끊긴 복도 없음) · 모든 방이 복도 칸에 한 변 이상 닿는가(못 가는 방 없음)
// 가구가 방 밖으로 · 이름표가 왼쪽 위 칸에 · 자리까지 실제로 걸어갈 수 있는가는 그림 크기가 필요해 화면(office.js gridAudit)이 본다
export const INNER = { x0: 1, y0: 2, x1: 27, y1: 17 };
export function gridProblems(g) {
  const out = [], rooms = Object.entries(g.rooms), cells = new Map();
  const isInt = (v) => Math.abs(v - Math.round(v)) < 1e-9;
  const mark = (name, [x, y, w, h], kind) => {
    if (![x, y, w, h].every(isInt)) out.push(`${name} 칸이 정수가 아닙니다 ${JSON.stringify([x, y, w, h])}`);
    if (x < INNER.x0 || y < INNER.y0 || x + w > INNER.x1 || y + h > INNER.y1) out.push(`${name}이(가) 방 안쪽 밖으로 나갑니다 ${JSON.stringify([x, y, w, h])}`);
    for (let j = Math.round(y); j < Math.round(y + h); j++) for (let i = Math.round(x); i < Math.round(x + w); i++) {
      const k = `${i},${j}`, prev = cells.get(k);
      if (prev && prev.name !== name) out.push(`${prev.name} · ${name}이(가) 같은 칸(${k})을 씁니다`);
      else cells.set(k, { name, kind });
    }
  };
  for (const [role, r] of rooms) mark(role, r, 'room');
  g.corridors.forEach((r, i) => mark(`복도${i + 1}`, r, 'corridor'));
  const dedup = [...new Set(out)];
  // 방이 아닌 칸은 복도다 — 방도 복도도 아닌 칸이 남으면 안 된다
  const empty = [];
  for (let j = INNER.y0; j < INNER.y1; j++) for (let i = INNER.x0; i < INNER.x1; i++) if (!cells.has(`${i},${j}`)) empty.push(`${i},${j}`);
  if (empty.length) dedup.push(`방도 복도도 아닌 칸 ${empty.length}개(${empty.slice(0, 5).join(' ')}${empty.length > 5 ? ' …' : ''})`);
  // 복도 칸 — 하나로 이어지는가(4방향)
  const cor = [...cells.entries()].filter(([, v]) => v.kind === 'corridor').map(([k]) => k);
  if (cor.length) {
    const seen = new Set([cor[0]]), q = [cor[0]], set = new Set(cor);
    while (q.length) {
      const [i, j] = q.shift().split(',').map(Number);
      for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const k = `${i + di},${j + dj}`;
        if (set.has(k) && !seen.has(k)) { seen.add(k); q.push(k); }
      }
    }
    if (seen.size !== set.size) dedup.push(`복도가 끊겨 있습니다 — 이어진 칸 ${seen.size} / 복도 칸 ${set.size}`);
  } else dedup.push('복도 칸이 없습니다');
  // 방마다 복도에 닿는가
  const corSet = new Set(cor);
  for (const [role, [x, y, w, h]] of rooms) {
    let touch = false;
    for (let i = x; i < x + w && !touch; i++) touch = corSet.has(`${i},${y - 1}`) || corSet.has(`${i},${y + h}`);
    for (let j = y; j < y + h && !touch; j++) touch = corSet.has(`${x - 1},${j}`) || corSet.has(`${x + w},${j}`);
    if (!touch) dedup.push(`${role} 방이 복도에 닿지 않습니다`);
  }
  return dedup;
}
