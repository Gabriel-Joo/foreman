// 걷기 — 가구를 피해 가는 길찾기(10단계, 11-05). DOM · 캔버스를 모른다(node --test로 시험).
// 방 하나를 RES(칸당 2) 격자로 나눠 막힌 칸(벽 · 가구 바닥 자리)을 적고, A*로 길을 찾은 뒤 보이는 곳까지 곧게 편다.
// 복도(theme.layout.corridors)는 걷는 값이 싸다 — 사람들이 가운데 ㅗ자 복도를 타고 다닌다(설계 docs/10_office_design.md).
// 좌표는 방 안 타일 단위(방 왼쪽 위 = 0,0).

export const RES = 2;                 // 한 타일을 2×2 칸으로
const OFF = 3;                        // 복도 밖 바닥을 걷는 값(복도 = 1)

// rects: 막는 사각형 [x, y, w, h](타일). corridors: 복도 사각형. walls: 벽 두께(위 · 옆 · 아래)
export function buildGrid(w, h, rects, corridors = [], walls = { top: 2, side: 0.6, bottom: 0.6 }) {
  const cols = Math.round(w * RES), rows = Math.round(h * RES);
  const block = new Uint8Array(cols * rows), cost = new Float32Array(cols * rows).fill(OFF);
  const mark = (x, y, ww, hh, fn) => {
    const c0 = Math.max(0, Math.floor(x * RES)), r0 = Math.max(0, Math.floor(y * RES));
    const c1 = Math.min(cols, Math.ceil((x + ww) * RES)), r1 = Math.min(rows, Math.ceil((y + hh) * RES));
    for (let r = r0; r < r1; r++) for (let c = c0; c < c1; c++) fn(r * cols + c);
  };
  for (const [x, y, ww, hh] of corridors) mark(x, y, ww, hh, (i) => { cost[i] = 1; });
  mark(0, 0, w, walls.top, (i) => { block[i] = 1; });
  mark(0, 0, walls.side, h, (i) => { block[i] = 1; });
  mark(w - walls.side, 0, walls.side, h, (i) => { block[i] = 1; });
  mark(0, h - walls.bottom, w, walls.bottom, (i) => { block[i] = 1; });
  // 가구 칸은 살짝 안쪽만 막는다 — 반 칸 격자에 걸친 모서리까지 막으면 가구 사이 좁은 틈이 닫힌다
  for (const [x, y, ww, hh] of rects) mark(x + 0.1, y + 0.1, Math.max(0, ww - 0.2), Math.max(0, hh - 0.2), (i) => { block[i] = 1; });
  return { cols, rows, block, cost, w, h };
}

const cellOf = (g, x, y) => [Math.min(g.cols - 1, Math.max(0, Math.floor(x * RES))), Math.min(g.rows - 1, Math.max(0, Math.floor(y * RES)))];
const free = (g, c, r) => c >= 0 && r >= 0 && c < g.cols && r < g.rows && !g.block[r * g.cols + c];

// 막힌 칸이면 가장 가까운 빈칸(자리가 탁자에 붙어 있다 — 길은 탁자 앞 빈칸까지, 마지막 한 걸음은 곧장)
export function nearestFree(g, c, r) {
  if (free(g, c, r)) return [c, r];
  for (let d = 1; d < Math.max(g.cols, g.rows); d++) {
    let best = null, bd = Infinity;
    for (let dr = -d; dr <= d; dr++) for (let dc = -d; dc <= d; dc++) {
      if (Math.max(Math.abs(dr), Math.abs(dc)) !== d || !free(g, c + dc, r + dr)) continue;
      const dd = dc * dc + dr * dr;
      if (dd < bd) { bd = dd; best = [c + dc, r + dr]; }
    }
    if (best) return best;
  }
  return null;
}

// 두 점 사이가 빈칸으로만 이어지나(곧게 펴기 · 마지막 걸음 확인)
export function clearLine(g, x0, y0, x1, y1) {
  const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * RES * 2) + 1;
  for (let i = 0; i <= n; i++) {
    const t = i / n, [c, r] = cellOf(g, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t);
    if (!free(g, c, r)) return false;
  }
  return true;
}
// 복도 위로만 지나는 직선인가 — 복도를 탄 길을 펼 때 복도 밖 지름길로 새지 않게
function sameCost(g, x0, y0, x1, y1) {
  const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * RES * 2) + 1;
  let maxc = 0;
  for (let i = 0; i <= n; i++) {
    const t = i / n, [c, r] = cellOf(g, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t);
    maxc = Math.max(maxc, g.cost[r * g.cols + c]);
  }
  return maxc;
}

// 길 — 방 안 타일 좌표의 점 목록(마지막 = 목표). 못 찾으면 목표 하나(예전처럼 곧장)
export function findPath(g, sx, sy, tx, ty) {
  const [sc0, sr0] = cellOf(g, sx, sy), [tc0, tr0] = cellOf(g, tx, ty);
  const s = nearestFree(g, sc0, sr0), t = nearestFree(g, tc0, tr0);
  if (!s || !t) return [[tx, ty]];
  if (clearLine(g, sx, sy, tx, ty) && sameCost(g, sx, sy, tx, ty) <= 1) return [[tx, ty]];
  const N = g.cols * g.rows, si = s[1] * g.cols + s[0], ti = t[1] * g.cols + t[0];
  const gs = new Float32Array(N).fill(Infinity), from = new Int32Array(N).fill(-1), done = new Uint8Array(N);
  const heap = [];                                    // [f, i] 최소 힙
  const push = (f, i) => { heap.push([f, i]); let k = heap.length - 1; while (k > 0) { const p = (k - 1) >> 1; if (heap[p][0] <= heap[k][0]) break; [heap[p], heap[k]] = [heap[k], heap[p]]; k = p; } };
  const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let k = 0; for (;;) { const l = 2 * k + 1, r = l + 1; let m = k; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === k) break; [heap[m], heap[k]] = [heap[k], heap[m]]; k = m; } } return top; };
  const hx = (i) => Math.hypot((i % g.cols) - t[0], Math.floor(i / g.cols) - t[1]);
  gs[si] = 0; push(hx(si), si);
  const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
  while (heap.length) {
    const [, i] = pop();
    if (done[i]) continue;
    done[i] = 1;
    if (i === ti) break;
    const c = i % g.cols, r = Math.floor(i / g.cols);
    for (const [dc, dr] of DIRS) {
      const nc = c + dc, nr = r + dr;
      if (!free(g, nc, nr)) continue;
      if (dc && dr && (!free(g, c + dc, r) || !free(g, c, r + dr))) continue;   // 모서리를 비스듬히 자르지 않는다
      const j = nr * g.cols + nc, step = (dc && dr ? Math.SQRT2 : 1) * (g.cost[i] + g.cost[j]) / 2;
      if (gs[i] + step < gs[j]) { gs[j] = gs[i] + step; from[j] = i; push(gs[j] + hx(j), j); }
    }
  }
  if (!done[ti]) return [[tx, ty]];
  const cells = [];
  for (let i = ti; i !== -1; i = from[i]) cells.push(i);
  cells.reverse();
  const pts = cells.map((i) => [(i % g.cols + 0.5) / RES, (Math.floor(i / g.cols) + 0.5) / RES]);
  const pc = cells.map((i) => g.cost[i]);
  pts.push([tx, ty]); pc.push(pc[pc.length - 1]);
  // 곧게 펴기 — 지금 점에서 보이는 가장 먼 점으로 건너뛴다. 단 그 직선이 원래 길보다 비싼 바닥(복도 밖)을 지나면 안 된다
  // (복도를 탄 길이 복도 밖으로 비스듬히 새지 않게). 마지막 점(자리)은 탁자에 붙어 있어 막힌 칸일 수 있다 — 바로 앞 점에서 곧장 간다
  const out = [];
  let cur = [sx, sy], k = 0;
  while (k < pts.length) {
    let far = k, worst = pc[k];
    for (let m = k; m < pts.length; m++) {
      worst = Math.max(worst, pc[m]);
      const last = m === pts.length - 1;
      if (m === k || (!last && clearLine(g, cur[0], cur[1], pts[m][0], pts[m][1]) && sameCost(g, cur[0], cur[1], pts[m][0], pts[m][1]) <= worst)) far = m;
      else if (!last) break;
    }
    if (far === pts.length - 2) far = pts.length - 1 > far && clearLine(g, cur[0], cur[1], tx, ty) ? pts.length - 1 : far;
    cur = pts[far];
    out.push(cur);
    k = far + 1;
  }
  if (out[out.length - 1] !== pts[pts.length - 1]) out.push([tx, ty]);
  return out;
}

// 가구 그림 → 바닥 자리(막는 사각형). 위에서 비스듬히 내려다본 그림이라 위쪽은 등판 · 윗면이 벽 쪽으로 솟은 부분 —
// 낮은 가구(≤ 1.5칸)는 거의 다, 키 큰 가구(책장)는 아래 1.5칸만 바닥을 차지한다. theme.json에서 foot: [dx, dy, w, h] · block: false로 바꾼다
export function footprint(d, wTiles, hTiles) {
  if (d.block === false) return null;
  if (d.foot) return [d.x + d.foot[0], d.y + d.foot[1], d.foot[2], d.foot[3]];
  const fh = hTiles <= 1.5 ? hTiles * 0.8 : hTiles <= 3 ? hTiles * 0.7 : 1.5;
  return [d.x, d.y + hTiles - fh, wTiles, fh];
}
