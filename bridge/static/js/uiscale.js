// 글씨 크기(11-08 사용자 요청 — "화면이 전체적으로 너무 작다, 그때그때 맞출 수 있게").
// 배율 하나가 옆 패널 전체(대화 · 탭 · 버튼 · 라벨 · 입력창 — CSS zoom)와 터미널 글씨(ttyd 안 xterm)를 함께 키운다.
// 픽셀 화면(캔버스)은 창 크기에 맞춰 스스로 맞추므로 여기서 건드리지 않는다.
// 이 브라우저에만 기억한다(localStorage — 못 쓰면 이 탭에서만).

const KEY = 'foremanUiScale';
// 11-10 사용자 — 전에는 브라우저 70%로 봐서 160%까지 키울 수 있게 했다. 이제 브라우저 100%에서 90%가 보기 좋아 그 둘레 80~110%, 5씩.
// 글씨 배율이 들어가는 곳(패널 · 머리말 · 툴팁 · 새 세션 창 · 사용량 화면 · 픽셀 화면 글씨 · 터미널)은 모두 이 STEPS · DEF를 쓴다.
// CSS의 처음 값(--ui-zoom, JS가 뜨기 전)은 panel.css · usage.html의 :root 한 줄 — DEF와 같은지 tests/js/uiscale_range.test.mjs가 본다
export const STEPS = [0.8, 0.85, 0.9, 0.95, 1, 1.05, 1.1];
export const DEF = 0.9;
const TERM_BASE = 14;            // 배율 1의 터미널 글씨(px) — 90%면 13px(ttyd 기본과 같다), 80~110%는 11~15px

// 저장된 값을 계단에 맞춘다 — 범위 밖(옛 120% 등)이거나 계단에 없으면 가장 가까운 계단, 없거나 숫자가 아니면 DEF
export function snapScale(raw) {
  if (raw === null || raw === undefined || String(raw).trim() === '') return DEF;
  const v = Number(raw);
  if (!Number.isFinite(v) || v <= 0) return DEF;
  return STEPS.reduce((best, s) => (Math.abs(s - v) < Math.abs(best - v) - 1e-9 ? s : best), STEPS[0]);
}
function load() {
  let raw = null;
  try { raw = localStorage.getItem(KEY); } catch { /* 기억 못 함 */ }
  return snapScale(raw);
}
let scale = load();

export const uiScale = () => scale;
export const termFont = () => Math.round(TERM_BASE * scale);

function apply() {
  document.documentElement.style.setProperty('--ui-zoom', String(scale));
  const v = document.getElementById('oFontV');
  if (v) v.textContent = `${Math.round(scale * 100)}%`;
  const dn = document.getElementById('oFontDn'), up = document.getElementById('oFontUp');
  if (dn) dn.disabled = scale <= STEPS[0];
  if (up) up.disabled = scale >= STEPS[STEPS.length - 1];
  window.dispatchEvent(new CustomEvent('foreman-uiscale', { detail: scale }));
}

export function step(d) {
  const i = Math.max(0, Math.min(STEPS.length - 1, STEPS.indexOf(scale) + d));
  scale = STEPS[i];
  try { localStorage.setItem(KEY, String(scale)); } catch { /* 이 탭에서만 */ }
  apply();
}

// xterm 칸 폭 보정(11-10 사용자 — 왼쪽이 잘려 "it push", 커서가 줄 끝이 아니라 `chatbot`의 `b` 자리).
// xterm은 장치 칸 폭 = floor(글자 폭 × dpr) + round(letterSpacing)(letterSpacing은 장치 px — dpr을 곱하지 않는다, 헤드리스로 잼)
// → 글자 폭(0.6em)이 장치 px로 정수가 아닌 크기(13 · 14 · 18px, 브라우저 확대 70% …)에서 칸이 글자보다 좁았다(14px: 칸 8 · 글자 8.4).
// 모자란 1 장치 px를 letterSpacing으로 채워 칸 ≥ 글자(장치 px 올림)가 되게 한다. 글씨 크기는 그대로(배율 5% 단위 세밀함 유지)
export function cellSpacing(glyphCss, dpr = 1) {
  const g = glyphCss * dpr;
  if (!(g > 0)) return 0;
  return Math.max(0, Math.ceil(g - 0.02) - Math.floor(g + 1e-6));   // 0.02 — 측정 소수 오차로 정수 크기(10 · 15 · 20px)에 1을 더하지 않게
}
function glyphWidth(w, t) {                  // xterm이 재는 것과 같은 값(캔버스 measureText — 헤드리스에서 _charSizeService.width와 같았다)
  const cv = w.document.createElement('canvas').getContext('2d');
  cv.font = `${t.options.fontSize}px ${t.options.fontFamily}`;
  return cv.measureText('W'.repeat(50)).width / 50;
}

// 터미널(ttyd iframe, 같은 출처) — 안의 xterm이 window.term으로 있다. 글씨 · 칸 폭을 바꾸고 resize로 다시 맞춘다(행 · 열 수)
export function applyTermFont(frame) {
  try {
    const w = frame && frame.contentWindow, t = w && w.term;
    if (!t || !t.options) return false;
    let changed = false;
    if (t.options.fontSize !== termFont()) { t.options.fontSize = termFont(); changed = true; }
    const ls = cellSpacing(glyphWidth(w, t), w.devicePixelRatio || 1);
    if ((t.options.letterSpacing || 0) !== ls) { t.options.letterSpacing = ls; changed = true; }
    if (changed) w.dispatchEvent(new Event('resize'));
    return true;
  } catch { return false; }
}

// 브라우저 확대(dpr)가 바뀌면 — 칸 폭 내림이 달라져 다시 맞춰야 한다(xterm은 스스로 칸을 다시 재지만 letterSpacing은 그대로 둔다)
export function onDprChange(cb) {
  if (typeof matchMedia !== 'function') return;
  const mq = matchMedia(`(resolution: ${devicePixelRatio}dppx)`);
  mq.addEventListener('change', () => { cb(); onDprChange(cb); }, { once: true });
}

if (typeof document !== 'undefined') {     // node 시험(snapScale · STEPS · cellSpacing)에서 불러도 되게
  document.addEventListener('click', (e) => {
    const b = e.target.closest && e.target.closest('#oFontDn, #oFontUp');
    if (b) step(b.id === 'oFontUp' ? 1 : -1);
  });
  // 다른 탭에서 [가−][가+]를 누르면 이 탭도 따라간다(11-09 — 사용량 화면 /usage도 같은 배율을 쓴다)
  addEventListener('storage', (e) => { if (e.key === KEY) { scale = load(); apply(); } });
  apply();
  new MutationObserver((_, ob) => { if (document.getElementById('oFontV')) { apply(); ob.disconnect(); } })
    .observe(document.documentElement, { childList: true, subtree: true });
}
