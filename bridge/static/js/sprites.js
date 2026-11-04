// 시트 테마(10d) — 원본 PNG를 그대로 받아 자르기 · 외곽선 · 색조를 브라우저에서 한다. 결과는 캔버스로 캐시.
// theme.sprites.defs: 이름 → [시트, x, y, w, h, 외곽선(1), 프레임 수, 초당 프레임]. 프레임은 오른쪽으로 w씩.
// 캐릭터(Ninja Adventure): Walk.png 64x64(열 = 아래 · 위 · 왼 · 오른, 행 = 프레임), Idle.png 64x16(열 = 방향).

const DIRS = { down: 0, up: 1, left: 2, right: 3 };

function loadImage(url) {
  return new Promise((ok, fail) => {
    const im = new Image();
    im.onload = () => ok(im);
    im.onerror = () => fail(new Error('스프라이트를 못 읽었다: ' + url));
    im.src = url;
  });
}

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

export async function loadSprites(theme, baseUrl) {
  const S = theme.sprites;
  const sheets = {};
  await Promise.all(Object.entries(S.sheets).map(async ([k, rel]) => { sheets[k] = await loadImage(new URL(rel, baseUrl)); }));
  const ch = S.chars || {};
  const names = new Set([...(ch.pool || []), ch.foreman, ...Object.values(ch.infra || {})].filter(Boolean));
  const chars = {};
  await Promise.all([...names].map(async (n) => {
    const dir = new URL(ch.dir + n + '/', baseUrl);
    chars[n] = { walk: await loadImage(new URL('Walk.png', dir)), idle: await loadImage(new URL('Idle.png', dir)) };
  }));
  return new Sprites(S, sheets, chars);
}

class Sprites {
  constructor(S, sheets, chars) {
    this.S = S; this.sheets = sheets; this.chars = chars;
    this.cache = new Map();
    this.outlineColor = hexRGBA(S.outline || '#1a1620');
  }

  has(name) { return !!this.S.defs[name]; }
  size(name) { const d = this.S.defs[name]; return d ? [d[3], d[4]] : [0, 0]; }

  // 이름 + 프레임 → 캔버스(외곽선이면 1px씩 넓다 — pad를 함께 돌려준다)
  frame(name, now = 0, fixed = null) {
    const d = this.S.defs[name];
    if (!d) return null;
    const [sh, x, y, w, h, ol, n, fps] = d;
    const f = n > 1 ? (fixed != null ? fixed % n : Math.floor((now / 1000) * (fps || 6)) % n) : 0;
    const key = `${name}#${f}`;
    let c = this.cache.get(key);
    if (!c) {
      const img = this.sheets[sh];
      const pad = ol ? 1 : 0;
      c = canvas(w + 2 * pad, h + 2 * pad);
      c.getContext('2d').drawImage(img, x + f * w, y, w, h, pad, pad, w, h);
      if (ol) outline(c, this.outlineColor);
      c.pad = pad;
      this.cache.set(key, c);
    }
    return c;
  }

  // 그리기 — (px, py)는 월드 px의 왼쪽 위. scale은 정수 배
  draw(ctx, name, px, py, now = 0, scale = 1, fixed = null) {
    const c = this.frame(name, now, fixed);
    if (!c) return;
    ctx.drawImage(c, Math.round(px) - c.pad * scale, Math.round(py) - c.pad * scale, c.width * scale, c.height * scale);
  }

  // 캐릭터 한 프레임 — mode: null · 'stone'(석화, 회색) · 'ghost'(유령, 푸른빛)
  // robe: 역할 색(#rrggbb) — 옷(채도 있고 너무 밝지 않은 픽셀)의 색상만 그 색으로 바꾼다(피부 · 외곽선은 그대로)
  charFrame(name, kind, dir, f, mode, robe = null) {
    const key = `c:${name}:${kind}:${dir}:${f}:${mode || ''}:${robe || ''}`;
    let c = this.cache.get(key);
    if (c) return c;
    const set = this.chars[name] || this.chars[Object.keys(this.chars)[0]];
    if (!set) return null;
    const col = DIRS[dir] ?? 0;
    c = canvas(16, 16);
    const g = c.getContext('2d');
    if (kind === 'walk') g.drawImage(set.walk, col * 16, (f % 4) * 16, 16, 16, 0, 0, 16, 16);
    else g.drawImage(set.idle, col * 16, 0, 16, 16, 0, 0, 16, 16);
    if (mode) tint(c, mode);
    else if (robe) recolor(c, robe);
    this.cache.set(key, c);
    return c;
  }
}

function rgb2hsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l];
  const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
  const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h / 6, s, l];
}
function hsl2rgb(h, s, l) {
  if (!s) return [l * 255, l * 255, l * 255];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
  const f = (t) => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
  return [f(h + 1 / 3) * 255, f(h) * 255, f(h - 1 / 3) * 255];
}

// 역할 색 — 옷 픽셀(채도 0.22 이상, 밝기 0.12~0.72)의 색상을 바꾼다. 피부(밝은 살구색)와 검은 외곽선은 남는다
export function recolor(c, hex) {
  const [tr, tg, tb] = hexRGBA(hex);
  const [th, ts] = rgb2hsl(tr, tg, tb);
  const g = c.getContext('2d');
  const d = g.getImageData(0, 0, c.width, c.height);
  for (let i = 0; i < d.data.length; i += 4) {
    if (!d.data[i + 3]) continue;
    const [, s, l] = rgb2hsl(d.data[i], d.data[i + 1], d.data[i + 2]);
    if (s < 0.22 || l < 0.12 || l > 0.72) continue;
    const [r, gg, b] = hsl2rgb(th, Math.max(0.35, Math.min(1, (s + ts) / 2)), l);
    d.data[i] = r; d.data[i + 1] = gg; d.data[i + 2] = b;
  }
  g.putImageData(d, 0, 0);
}

function hexRGBA(hex) {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 255];
}

// 바깥 1px 외곽선 — 투명 픽셀 중 불투명 픽셀과 4방향으로 닿은 것을 진한 색으로(Calciumtrice 가구를 Ninja · 0x72 화풍에 맞춘다)
export function outline(c, rgba) {
  const g = c.getContext('2d');
  const { width: w, height: h } = c;
  const src = g.getImageData(0, 0, w, h);
  const out = g.createImageData(w, h);
  out.data.set(src.data);
  const a = (x, y) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : src.data[(y * w + x) * 4 + 3]);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (a(x, y) > 0) continue;
    if (a(x + 1, y) > 128 || a(x - 1, y) > 128 || a(x, y + 1) > 128 || a(x, y - 1) > 128) {
      const i = (y * w + x) * 4;
      out.data[i] = rgba[0]; out.data[i + 1] = rgba[1]; out.data[i + 2] = rgba[2]; out.data[i + 3] = rgba[3];
    }
  }
  g.putImageData(out, 0, 0);
}

// 석화(회색 돌) · 유령(푸른빛) — 밝기만 남기고 색을 바꾼다
function tint(c, mode) {
  const g = c.getContext('2d');
  const d = g.getImageData(0, 0, c.width, c.height);
  for (let i = 0; i < d.data.length; i += 4) {
    if (!d.data[i + 3]) continue;
    const l = 0.3 * d.data[i] + 0.59 * d.data[i + 1] + 0.11 * d.data[i + 2];
    if (mode === 'stone') { const v = 70 + l * 0.6; d.data[i] = v; d.data[i + 1] = v; d.data[i + 2] = v + 6; }
    else if (mode === 'ghost') { d.data[i] = 120 + l * 0.35; d.data[i + 1] = 170 + l * 0.3; d.data[i + 2] = 255; }
  }
  g.putImageData(d, 0, 0);
}
