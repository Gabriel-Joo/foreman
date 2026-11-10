// 방 모눈(11-10 사용자 — 「화면 모눈으로 다시 짜기」) — 세 테마가 grid.json 한 벌을 쓰고, 방 안 좌표(in)가 방 좌표로 바뀌는가
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyGrid, INFRA_STAGES } from '../../bridge/static/js/grid.js';

const read = (p) => JSON.parse(readFileSync(new URL(`../../bridge/static/themes/${p}`, import.meta.url), 'utf8'));
const GRID = read('_shared/grid.json');
const THEMES = ['site', 'magic', 'office'];
const load = (t) => applyGrid(read(`${t}/theme.json`), read('_shared/grid.json'));

test('세 테마 모두 모눈을 쓴다 — 방 열한 개(구역 열 + 출하장), 역할마다 한 방', () => {
  for (const t of THEMES) {
    const th = read(`${t}/theme.json`);
    assert.equal(th.layout.grid, '../_shared/grid.json', t);
    const roles = Object.values(th.tags.roles);
    assert.equal(new Set(roles).size, roles.length, `${t} 역할이 겹친다`);
    assert.deepEqual([...roles, 'ship'].sort(), Object.keys(GRID.rooms).sort(), t);
  }
});

test('테마 셋의 방 자리가 같다(역할 기준) — 테마는 이름 · 그림 · 색만 다르다', () => {
  const byRole = THEMES.map((t) => {
    const th = load(t), out = {};
    for (const [k, role] of Object.entries(th.tags.roles)) { const z = th.layout.zones[k]; out[role] = [z.x, z.y, z.w, z.h]; }
    const iz = th.layout.zones.infra;
    out.ship = [iz.x, iz.y, iz.w, iz.h, ...INFRA_STAGES.map((k) => iz[k].x)];
    out.corridors = th.layout.corridors;
    return out;
  });
  assert.deepEqual(byRole[1], byRole[0]);
  assert.deepEqual(byRole[2], byRole[0]);
});

test('방 안 좌표 → 방 좌표 — 자리 · 가구 · 출하 담당 자리', () => {
  const th = load('site'), z = th.layout.zones, read0 = read('site/theme.json');
  const [sx, sy] = GRID.rooms.read;
  assert.deepEqual(z.store.seats[0].slice(0, 2), [read0.layout.zones.store.seats[0][0] + sx, read0.layout.zones.store.seats[0][1] + sy]);
  const [ex, ey] = GRID.rooms.edit;                           // 디자이너 자리는 in: desks → 작업대 방 기준
  assert.deepEqual(z.designer.seats[0].slice(0, 2), [read0.layout.zones.designer.seats[0][0] + ex, read0.layout.zones.designer.seats[0][1] + ey]);
  const d0 = read0.sprites.decor.find((d) => d.in === 'tools' && d.s === 'workbench');
  const d1 = th.sprites.decor.find((d) => d.in === 'tools' && d.s === 'workbench');
  const [bx, by] = GRID.rooms.bash;
  assert.deepEqual([d1.x, d1.y], [d0.x + bx, d0.y + by]);
  const iz = z.infra, [px, py] = GRID.rooms.ship;
  assert.equal(iz.jenkins.x, px + GRID.ship.jenkins);
  assert.deepEqual(iz.stands.home, [read0.layout.zones.infra.stands.home[0] + px, read0.layout.zones.infra.stands.home[1] + py]);
  assert.deepEqual(iz.stands.jenkins, [read0.layout.zones.infra.stands.jenkins[0] + iz.jenkins.x, read0.layout.zones.infra.stands.jenkins[1] + py]);
});
