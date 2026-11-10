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
