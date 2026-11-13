// 발밑 역할 색 원(11-13 사용자) — 이름표를 안 봐도 역할이 한눈에 보이게 캐릭터 발밑에 역할 색을 깐다.
// 「딱딱한 동그라미가 아니라 마법 문양처럼 퍼지는 꼴 · 가운데가 짙고 바깥으로 옅어지는 번짐 · 테마에 맞게 · 늘 켜 두되 쉴 때는 옅게 ·
//  색은 역할 배지와 같게 · 걸을 때도 따라온다」. 색은 render.js ROLE_COLOR 한 곳. 그리는 차례는 office.js(바닥 다음 · 가구와 사람 앞)
import { ROLE_COLOR } from './render.js';

// 세기 — 일할 때 1, 쉴 때 옅게(사용자). 멈춤 · 끝남은 더 옅게(그래도 역할은 보이게 — 늘 켜 둔다)
export const AURA_REST = 0.6, AURA_OFF = 0.4;

// 이 캐릭터의 발밑 원 — { color, k(세기), s(크기 배율) } 또는 null(역할이 없는 캐릭터).
// 붙이는 것: 세션(역할이 있을 때) · 서브에이전트(부모 역할, 작게) · 감독실 캐릭터(감독) · 세션 없는 서기 · 쉬는/돌아가는 코더.
// 안 붙이는 것: 배송 담당 · 인프라(역할 배지가 없는 파이프라인 캐릭터), 역할을 모르는 세션(배지 「역할?」 — 경고색 원은 경고로 읽힌다)
export function auraOf(a, miniScale = 0.6) {
  if (!a) return null;
  const color = ROLE_COLOR[a.role];
  if (!color) return null;
  if (a.kind === 'mini') return { color, k: 1, s: miniScale };           // 서브에이전트는 늘 일하는 중
  if (a.kind === 'session') {
    const st = a.s && a.s.state;
    return { color, k: st === 'ACTIVE' ? 1 : st === 'IDLE' ? AURA_REST : AURA_OFF, s: 1 };
  }
  if (a.kind === 'foreman') return { color, k: a.fm && a.fm.running ? 1 : AURA_REST, s: 1 };
  if (a.kind === 'scribe' || a.kind === 'coder') return { color, k: AURA_REST, s: 1 };   // 세션 없는 캐릭터 — 쉬는 중
  return null;
}

// 테마마다 고를 수 있는 꼴(안). 첫째가 그 테마 기본(theme.json aura.style이 없을 때) — 견준 사진 · 고른 까닭은 log/role_aura_20261113.md
export const AURA_STYLES = {
  magic: ['star', 'rune', 'glow'],
  office: ['mat', 'spot', 'glow'],
  site: ['hazard', 'tape', 'glow'],
  plain: ['glow'],
};
export function auraStyle(themeName, themeAura, override) {
  const list = AURA_STYLES[themeName] || ['glow'];
  if (override && (list.includes(override) || override === 'off')) return override;
  if (themeAura && themeAura.style && list.includes(themeAura.style)) return themeAura.style;
  return list[0];
}

// 크기 — 발 점 기준 가로 반지름(칸 단위)과 납작함. 이름표가 발밑(발 점 2px 아래)에 서서 원 아래 절반을 덮는다 —
// 그래서 원을 이름표보다 넓게(가로 지름 약 2칸) 잡아 양옆이 이름표 밖으로 보이고, 가운데를 발 점보다 조금 위에 둔다
export const AURA_RX = 1.15, AURA_FLAT = 0.45, AURA_LIFT = 0.16;

const hexA = (hex, a) => {                 // '#rrggbb' + 알파 → rgba()
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
};
const mix = (hex, to, t) => {              // 색을 to(0 = 검정 · 255 = 흰색) 쪽으로 t만큼
  const n = parseInt(hex.slice(1), 16), f = (c) => Math.round(c + (to - c) * t);
  return `#${[(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => f(c).toString(16).padStart(2, '0')).join('')}`;
};

// 그리기 — 월드 px(x, y = 발 점), T = 한 칸 px, t = 초. ctx 상태는 되돌려 놓는다
export function drawAura(ctx, style, x, y, T, au, t) {
  if (!au || style === 'off') return;
  const rx = AURA_RX * T * au.s, ry = rx * AURA_FLAT, cy = y - AURA_LIFT * T * au.s, k = au.k, c = au.color;
  const spin = k >= 1 ? t * 0.5 : 0;                  // 일할 때만 천천히 돈다(쉴 때는 멈춘 문양)
  ctx.save();
  ctx.translate(x, cy);
  ctx.scale(1, AURA_FLAT);                            // 원을 납작하게 — 바닥에 깔린 것처럼(아래 r은 가로 반지름 기준)
  const r = rx;
  // 1) 바깥 그늘 — 바닥이 같은 색(오피스 파란 타일 · 코더 파랑)이어도 테두리가 보이게, 원 바깥쪽을 살짝 어둡게
  let g = ctx.createRadialGradient(0, 0, r * 0.55, 0, 0, r * 1.08);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.55, `rgba(0,0,0,${(0.28 * k).toFixed(3)})`); g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r * 1.08, 0, Math.PI * 2); ctx.fill();
  // 2) 번짐 — 가운데가 짙고 바깥으로 옅어진다(사용자)
  g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
  g.addColorStop(0, hexA(mix(c, 255, 0.25), 0.85 * k)); g.addColorStop(0.35, hexA(c, 0.6 * k)); g.addColorStop(1, hexA(c, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fill();
  const lw = Math.max(0.8, T / 16);
  const ring = (rr, a, w = lw, col = mix(c, 255, 0.35)) => { ctx.strokeStyle = hexA(col, a * k); ctx.lineWidth = w / AURA_FLAT * 0.55; ctx.beginPath(); ctx.arc(0, 0, rr, 0, Math.PI * 2); ctx.stroke(); };
  if (style === 'rune') {
    // 마법진 — 바깥 고리 · 안 고리, 그 사이에 룬 눈금 8개(돈다)
    ring(r * 0.86, 0.85); ring(r * 0.62, 0.6);
    ctx.save(); ctx.rotate(spin);
    ctx.fillStyle = hexA(mix(c, 255, 0.55), 0.95 * k);
    for (let i = 0; i < 8; i++) {
      const th = (i / 8) * Math.PI * 2, mx = Math.cos(th) * r * 0.74, my = Math.sin(th) * r * 0.74;
      ctx.save(); ctx.translate(mx, my); ctx.rotate(th);
      ctx.fillRect(-lw * 0.6, -lw * (i % 2 ? 1.6 : 2.6), lw * 1.2, lw * (i % 2 ? 3.2 : 5.2));   // 길고 짧은 눈금이 번갈아
      ctx.restore();
    }
    ctx.restore();
  } else if (style === 'star') {
    // 육망성 — 두 삼각형(돈다) + 바깥 고리
    ring(r * 0.86, 0.8);
    ctx.save(); ctx.rotate(spin);
    ctx.strokeStyle = hexA(mix(c, 255, 0.45), 0.85 * k); ctx.lineWidth = lw / AURA_FLAT * 0.5;
    for (const o of [0, Math.PI / 3]) {
      ctx.beginPath();
      for (let i = 0; i <= 3; i++) { const th = o + i * Math.PI * 2 / 3 - Math.PI / 2; ctx.lineTo(Math.cos(th) * r * 0.84, Math.sin(th) * r * 0.84); }
      ctx.stroke();
    }
    ctx.restore();
  } else if (style === 'spot') {
    // 오피스 — 천장 조명이 바닥에 떨어진 빛 웅덩이: 가운데 흰빛 한 겹 + 얇은 가장자리
    g = ctx.createRadialGradient(0, 0, 0, 0, 0, r * 0.45);
    g.addColorStop(0, `rgba(255,255,255,${(0.35 * k).toFixed(3)})`); g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r * 0.45, 0, Math.PI * 2); ctx.fill();
    ring(r * 0.9, 0.55, lw * 0.8, c);
  } else if (style === 'mat') {
    // 오피스 — 둥근 러그: 짙은 가장자리 띠 + 안쪽 실선
    ring(r * 0.84, 0.9, lw * 2.2, mix(c, 0, 0.15)); ring(r * 0.66, 0.5, lw * 0.8);
  } else if (style === 'hazard') {
    // 현장 — 작업 구역 표시: 끊긴 고리(돈다, 역할 색과 어두운 틈이 번갈아)
    ctx.save(); ctx.rotate(spin * 0.6);
    const n = 12;
    for (let i = 0; i < n; i++) {
      ctx.strokeStyle = i % 2 ? hexA('#1d1f22', 0.55 * k) : hexA(mix(c, 255, 0.3), 0.95 * k);
      ctx.lineWidth = lw * 2 / AURA_FLAT * 0.55;
      ctx.beginPath(); ctx.arc(0, 0, r * 0.82, (i / n) * Math.PI * 2, ((i + 1) / n) * Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  } else if (style === 'tape') {
    // 현장 — 바닥 테이프 네 모서리(ㄱ자)
    ctx.strokeStyle = hexA(mix(c, 255, 0.25), 0.95 * k); ctx.lineWidth = lw * 1.6 / AURA_FLAT * 0.55;
    const e = r * 0.78, l = r * 0.32;
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      ctx.beginPath(); ctx.moveTo(sx * e, sy * (e - l)); ctx.lineTo(sx * e, sy * e); ctx.lineTo(sx * (e - l), sy * e); ctx.stroke();
    }
  }
  ctx.restore();
}
