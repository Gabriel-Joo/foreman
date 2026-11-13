// 머리 위 표시 쌓기(11-13 사용자) — 캐릭터 위에 쌓는다. 캐릭터를 덮지 않고, 하나만 떠도 위로(옆 · 발밑으로 비키지 않는다).
// 아래(머리 바로 위) = 글씨 카드(관리자에게 보고함 · 사용자 답 기다림 · 문서 할 일 · 맡길 일 …),
// 위 = 동작 카드(멈춘 턴 「…」 · 뒤에서 도는 일 막대 · 테마 「?」 「!」). 그리기 · 글씨 폭 재기는 office.js, 여기는 자리 계산만.
// 좌표는 월드 px [x, y, w, h], y는 아래로 커진다. base = 덩어리 아래 끝(머리 위 끝 바로 위)
export const STACK_GAP = 1;

export const areaOf = (a, b) => Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) *
  Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));

// 한 줄로 쌓기 — cards[0]이 맨 아래(머리 바로 위). 가운데 x = 0 기준
export function column(cards, base, gap = STACK_GAP) {
  let yb = base;
  return cards.map((c) => { const r = [-c.w / 2, yb - c.h, c.w, c.h]; yb = r[1] - gap; return r; });
}

// 위 칸으로 넘칠 때 — 글씨 카드는 그대로 쌓고 동작 카드를 맨 아래 글씨 카드 옆(dir 1 오른쪽 · -1 왼쪽)에 붙인다.
// 둘 다 머리 위 높이라 캐릭터를 덮지 않는다. 덩어리 전체를 머리 가운데에 맞춘다
export function side(texts, acts, base, dir, gap = STACK_GAP) {
  const tr = column(texts, base, gap), t0 = tr[0];
  let edge = dir > 0 ? t0[0] + t0[2] + gap : t0[0] - gap;
  const ar = acts.map((c) => {
    const r = [dir > 0 ? edge : edge - c.w, base - c.h, c.w, c.h];
    edge = dir > 0 ? r[0] + r[2] + gap : r[0] - gap;
    return r;
  });
  const all = [...tr, ...ar];
  const lo = Math.min(...all.map((r) => r[0])), hi = Math.max(...all.map((r) => r[0] + r[2])), sh = -(lo + hi) / 2;
  return all.map((r) => [r[0] + sh, r[1], r[2], r[3]]);
}

// 후보 — 앞일수록 먼저 고른다: 원래 크기 한 줄(가운데 → 옆으로 조금씩 → 조금씩 들어 올림) → 동작 카드 옆에 붙임 → 글씨를 줄여 같은 차례.
// 옆으로 미는 폭은 덩어리가 자기 머리(가운데 x ± reach) 위에 걸쳐 있는 만큼까지 — 누구 표시인지 갈리게.
// 들어 올리는 높이는 raise까지(붐비는 자리에서 이웃 머리 · 이름표 위로) — 아래(몸 쪽)로는 내리지 않는다.
// sized(k) = { texts, acts } (k배 크기로 잰 카드, 각 { w, h })
// lifts = 덩어리 아래 끝을 막는 칸 바로 위에 맞추는 높이들(걸음 step이 좁은 틈 — 복도 띠 등 — 을 건너뛰지 않게, liftsOver)
export function stackCandidates(sized, x, base, { gap = STACK_GAP, step = 3, shrinks = [1, 0.85, 'dot'], reach = 0, raise = 0, lifts = [] } = {}) {
  const out = [];
  for (const k of shrinks) {
    const { texts, acts } = sized(k);
    const shapes = [{ shape: 'column', rects: column([...texts, ...acts], base, gap) }];
    if (texts.length && acts.length) {
      shapes.push({ shape: 'side-right', rects: side(texts, acts, base, 1, gap) }, { shape: 'side-left', rects: side(texts, acts, base, -1, gap) });
    }
    for (const s of shapes) {
      const lo = Math.min(...s.rects.map((r) => r[0])), hi = Math.max(...s.rects.map((r) => r[0] + r[2]));
      const lim = Math.max(0, Math.min(-lo, hi) + reach - 3);
      const dxs = [0], up = [];
      for (let d = step; d <= lim; d += step) dxs.push(d, -d);
      for (let d = step; d <= raise; d += step) up.push(d);
      const dys = [0, ...[...new Set([...up, ...lifts.filter((d) => d > 0 && d <= raise)])].sort((p, q) => p - q)];
      for (const dy of dys) for (const dx of dxs) {
        out.push({ shape: s.shape, k, dx, dy, rects: s.rects.map((r) => [x + r[0] + dx, r[1] - dy, r[2], r[3]]) });
      }
    }
  }
  return out;
}

// 들어 올릴 높이 후보 — 머리 위 덩어리 폭(x ± half) 안에서 머리보다 위에 걸친 칸마다, 덩어리 아래 끝(base)이 그 칸 위 끝 바로 위에 오는 높이
export const liftsOver = (boxes, x, half, base, gap = STACK_GAP) => boxes
  .filter((b) => b[0] < x + half && b[0] + b[2] > x - half && b[1] < base)
  .map((b) => Math.ceil(base - (b[1] - gap)));

// 선 y(월드 px)보다 위로 넘어간 넓이. y가 없으면 0
export const overTop = (rects, y) => (y == null ? 0
  : rects.reduce((s, r) => s + Math.max(0, Math.min(r[3], y - r[1])) * r[2], 0));

// 덩어리 아래 끝과 base(자기 머리 위) 사이 띠가 others(다른 사람 몸 · 다른 표시)와 겹친 넓이 — 들어 올리지 않았으면 0
export function leapOver(rects, base, others) {
  const lo = Math.min(...rects.map((r) => r[0])), hi = Math.max(...rects.map((r) => r[0] + r[2]));
  const bot = Math.max(...rects.map((r) => r[1] + r[3]));
  return bot >= base - 0.5 ? 0 : others.reduce((s, b) => s + areaOf([lo, bot, hi - lo, base - bot], b), 0);
}

// 덮으면 안 되는 넓이: 막는 칸(이름표 · 사람 몸 — 자기 몸 포함 · 다른 표시)과 겹친 넓이 + 보이는 칸(view — 캔버스 ∩ 방 화면 자르기) 밖 넓이
export function stackCover(rects, { boxes = [], view = null } = {}) {
  let c = 0;
  for (const r of rects) {
    for (const b of boxes) c += areaOf(r, b);
    if (view) c += r[2] * r[3] - areaOf(r, view);
  }
  return c;
}

// 고르는 층(앞일수록 무겁다, 넓이 px²마다) — cover: 사람 몸 · 이름표 · 다른 카드 · 화면/방 밖(잘림) ≫ room: 복도 너머 위 방 ≫
// 글씨 줄임(k < 1, 한 번에 SHRINK — 위 방 1px²보다 가볍게: 오피스 넓게에서 「/」를 0.85배로 줄이면 위아래 줄 사이에 들어가는데 위 방까지 떴다) ≫
// spot: 뒤에 놓일 이웃 덩어리의 제자리 · 다른 이름표 ≫ soft: 선 칸 위 끝을 넘어 복도로 나간 넓이.
// 줄여도 글씨 카드는 화면 9px 아래로 안 간다(sizeCard). 0.5px² 아래는 0(반올림 틈)
// 들어 올림은 높이(월드 px)마다 RAISE — 덮음을 피하려면 얼마든지 올리되, 이름표 · 이웃 제자리(spot)를 조금 덜 덮자고 멀리 뜨지는 않게
// (11-13 — 공짜였을 때 아래 줄 코더의 「/」가 위 줄 코더의 이름표를 피해 위 줄 코더 머리 위 복도까지 갔다)
// leap: 덩어리와 자기 머리 사이에 낀 다른 사람 몸 · 다른 표시 넓이(건너뜀) — 누구 표시인지 헷갈린다. 100px² 넘게 건너뛰느니 점(DOT)으로
// (11-13 현장 1024: 위 줄 코더 바로 아래 코더의 「API 오류로 멈춤」이 위 줄 코더의 「합치기 기다림」 옆 위로 올라갔다)
export const TIER = { cover: 1e6, room: 1e3, leap: 100, spot: 10, soft: 1 };
// 점(k = 'dot') — 글씨 카드를 [전체] 지도처럼 색 점으로(글은 캐릭터 호버 · 방 머리줄에 남는다). 줄여도(화면 9px) 들어갈 틈이 없을 때 —
// 위 방 10px² · 건너뜀 100px²보다 무겁게. 11-13 오피스 넓게 · 1024의 작은 라운지에서 위 줄 코더 바로 아래 코더의 「API 오류로 멈춤」이
// 덮지 않으려고 위 방(팀장실)까지 떴고, 현장 1024에서는 위 줄 코더의 카드 옆 위로 건너뛰어 누구 것인지 헷갈렸다
export const SHRINK = 500, DOT = 1e4, RAISE = 30;
// tiers = { cover: fn(rects), room: fn, leap: fn, spot: fn, soft: fn } — 없는 층은 0
// 층은 모두 0 이상이라, 더하는 도중 이미 지금 최선 이상이면 그 후보는 나머지 층을 재지 않는다(붐비는 자리에서 후보가 수천 개)
export function pickStack(cands, tiers) {
  let best = null;
  for (const c of cands) {
    const v = {}, n = (x) => (x > 0.5 ? x : 0);
    let score = (c.k === 'dot' ? DOT : c.k < 1 ? SHRINK : 0) + (c.dy || 0) * RAISE, cut = false;
    for (const [name, w] of Object.entries(TIER)) {
      if (best && score >= best.score) { cut = true; break; }
      v[name] = tiers[name] ? tiers[name](c.rects) : 0; score += n(v[name]) * w;
    }
    if (cut) continue;
    if (!best || score < best.score) best = { ...c, ...v, score };
    if (!score) break;
  }
  return best;
}

// 자리 말풍선의 주인(11-13 사용자 — 「맡길 일」 · 「문서 할 일」은 자리에 늘): 그 방에서 자리(x, y 타일) near칸 안에 멈춰 선 사람 중
// 가장 가까운 사람. 걷는 사람 · 아직 안 나타난 사람(bornAt) · 서브에이전트(mini)는 주인이 아니다. 없으면 null(자리의 보이지 않는 몸 위에)
export function seatHost(list, seat, near, now) {
  let best = null, bd = near;
  for (const a of list) {
    if (a.room !== seat.room || a.kind === 'mini' || a.moving || (a.bornAt && now < a.bornAt)) continue;
    const d = Math.hypot(a.x - seat.x, a.y - seat.y);
    if (d < bd) { bd = d; best = a; }
  }
  return best;
}

// 덩어리 후보가 닿을 수 있는 칸(x ± half, base - up ~ base)에 걸친 것만 — 세상 전체의 몸 · 이름표 · 카드를 후보마다 훑지 않게
export const nearBoxes = (boxes, x, half, base, up) => boxes.filter((b) => b[0] < x + half && b[0] + b[2] > x - half && b[1] < base + 1 && b[1] + b[3] > base - up);
