// 툴팁 하나(11-05) — 구역 이름표 · 캐릭터 · 출하 라인(캔버스)과 버튼 · 패널(DOM)이 같은 모양 · 같은 속도로 뜬다.
// 구조: .tip-h(작은 머리 — 무엇) · .tip-b(굵게 — 하는 일) · 본문 · .tip-s(지금 상태) · .tip-t(덧붙임).
// 색 · 글꼴은 테마 이름표(theme.tags.style — 양피지 · 사인판 · 안전 표지판)를 따르고, 크기 · 여백 · 위치 · 지연은 같다.
// DOM은 data-tip(HTML 아님, 글자)이나 title을 읽는다 — title은 브라우저 기본 툴팁이 따로 뜨지 않게 data-tip으로 옮긴다.

const DELAY = 350;          // 올리고 이만큼 머물면 뜬다(지나가는 마우스에 깜빡이지 않게)
let el = null, timer = null, shownFor = null;

function ensure() {
  if (el) return el;
  el = document.createElement('div');
  el.className = 'tip';
  el.setAttribute('role', 'tooltip');
  el.hidden = true;
  document.body.appendChild(el);
  return el;
}

function place(x, y) {
  const w = el.offsetWidth, h = el.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
  let left = x + 14, top = y + 18;
  if (left + w > vw - 6) left = Math.max(6, x - w - 10);
  if (top + h > vh - 6) top = Math.max(6, y - h - 10);
  el.style.left = left + 'px'; el.style.top = top + 'px';
}

// 캔버스 · 코드에서 — html은 호출하는 쪽이 이스케이프한다. key가 같으면 다시 기다리지 않고 따라만 간다
export function showTip(html, x, y, key = html) {
  ensure();
  if (shownFor === key && !el.hidden) { place(x, y); return; }
  clearTimeout(timer);
  shownFor = key;
  window.__tipPending = html;          // 화면 시험(헤드리스)이 무엇이 뜰지 본다 — 지연 때문에 바로는 안 보인다
  timer = setTimeout(() => {
    if (shownFor !== key) return;
    el.innerHTML = html;
    el.hidden = false;
    place(x, y);
  }, el.hidden ? DELAY : 60);          // 이미 떠 있으면(옆 대상으로 옮김) 거의 바로
}
export function hideTip() { clearTimeout(timer); shownFor = null; if (el) el.hidden = true; }

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// "머리 — 본문" 한 줄짜리 title도 같은 구조로: 첫 " — " 앞을 굵게
export function textTip(t) {
  const i = t.indexOf(' — ');
  return i > 0 ? `<div class="tip-b">${esc(t.slice(0, i))}</div><div>${esc(t.slice(i + 3))}</div>` : `<div>${esc(t)}</div>`;
}

// 테마 이름표 색 · 글꼴을 툴팁에(theme.tags.style). 없으면(도형 · 클래식) 기본 카드 색
export function themeTips(style) {
  const r = document.documentElement.style;
  if (!style) return;
  r.setProperty('--tip-bg', style.bg.length > 7 ? style.bg.slice(0, 7) : style.bg);
  r.setProperty('--tip-fg', style.fg);
  r.setProperty('--tip-border', style.border.length > 7 ? style.border.slice(0, 7) : style.border);
  r.setProperty('--tip-font', style.font.replace(/(\d+)px/, '14px').replace(/\b(600|bold)\b/, '400'));
  document.documentElement.dataset.tipKind = style.kind || 'sign';
}

// DOM — data-tip · title이 달린 것에 마우스를 올리면
export function attachDomTips(root = document) {
  let cur = null;
  root.addEventListener('mouseover', (ev) => {
    const t = ev.target.closest && ev.target.closest('[data-tip], [title]');
    if (!t || t === cur) return;
    if (t.hasAttribute('title')) { if (t.title) t.dataset.tip = t.title; t.removeAttribute('title'); }
    if (!t.dataset.tip) return;
    cur = t;
    const r = t.getBoundingClientRect();
    showTip(textTip(t.dataset.tip), r.left + Math.min(r.width / 2, 40), r.bottom - 10, t);
  });
  root.addEventListener('mouseout', (ev) => {
    if (!cur) return;
    if (ev.relatedTarget && cur.contains(ev.relatedTarget)) return;
    cur = null; hideTip();
  });
  root.addEventListener('mousedown', () => { cur = null; hideTip(); }, true);
}
