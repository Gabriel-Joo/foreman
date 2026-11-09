// 글씨 크기(11-08 사용자 요청 — "화면이 전체적으로 너무 작다, 그때그때 맞출 수 있게").
// 배율 하나가 옆 패널 전체(대화 · 탭 · 버튼 · 라벨 · 입력창 — CSS zoom)와 터미널 글씨(ttyd 안 xterm)를 함께 키운다.
// 픽셀 화면(캔버스)은 창 크기에 맞춰 스스로 맞추므로 여기서 건드리지 않는다.
// 이 브라우저에만 기억한다(localStorage — 못 쓰면 이 탭에서만).

const KEY = 'foremanUiScale';
// 11-09 사용자 — 120%부터 위로는 5씩(10씩 뛰면 한 번에 확 달라져 세밀하게 못 맞춘다)
export const STEPS = [0.9, 1, 1.1, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5, 1.55, 1.6];
const DEF = 1.2;                 // 1920 기준 — 11-08 전보다 한 단계 크게
const TERM_BASE = 14;            // 배율 1의 터미널 글씨(px). 처음 값 1.2면 17px(ttyd 기본 13)

function load() {
  let v = NaN;
  try { v = Number(localStorage.getItem(KEY)); } catch { /* 기억 못 함 */ }
  return STEPS.includes(v) ? v : DEF;
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

// 터미널(ttyd iframe, 같은 출처) — 안의 xterm이 window.term으로 있다. 글씨를 바꾸고 resize로 다시 맞춘다(행 · 열 수)
export function applyTermFont(frame) {
  try {
    const w = frame && frame.contentWindow, t = w && w.term;
    if (!t || !t.options) return false;
    if (t.options.fontSize !== termFont()) {
      t.options.fontSize = termFont();
      w.dispatchEvent(new Event('resize'));
    }
    return true;
  } catch { return false; }
}

document.addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('#oFontDn, #oFontUp');
  if (b) step(b.id === 'oFontUp' ? 1 : -1);
});
// 다른 탭에서 [가−][가+]를 누르면 이 탭도 따라간다(11-09 — 사용량 화면 /usage도 같은 배율을 쓴다)
addEventListener('storage', (e) => { if (e.key === KEY) { scale = load(); apply(); } });
apply();
new MutationObserver((_, ob) => { if (document.getElementById('oFontV')) { apply(); ob.disconnect(); } })
  .observe(document.documentElement, { childList: true, subtree: true });
