// 모델 고르기(11-05) — [+ 세션] 창 · 포먼 계획 카드가 같이 쓴다. 목록 · 역할 기본값은 /api/spawn/options의 models(config/models.toml).
// 역할을 바꾸면 모델도 그 역할의 기본값으로 따라간다 — 사람이 모델을 직접 고른 뒤에는 따라가지 않는다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const ROLE_PICK = { coder: '코더 — 고치기 · 만들기', inspector: '점검 — 살펴보기 · 원인 찾기',  scribe: '서기 — 문서 · 회고', manager: '관리자 — 합치기 · 시험 · push · 기록', designer: '디자이너 — 화면 · 테마 · 캐릭터' };
// 11-09 scribe가 빠져 있어 교장이 서기 계획(role scribe)을 내도 계획 카드 칸이 첫 값(코더)으로 보였다 — 그대로 시작하면 코더로 떴다

export function modelOptions(models, cur, role) {
  const m = models || { choices: [], defaults: {} };
  const def = (m.defaults || {})[role || 'coder'];
  cur = (m.aliases || {})[cur] || cur;      // 11-14 전 계획 카드 값(opus 등 별칭)도 목록의 그 칸으로

  const opts = (m.choices || []).map((c) =>
    `<option value="${esc(c.id)}"${c.id === cur ? ' selected' : ''}${c.note ? ` title="${esc(c.label)} — ${esc(c.note)}"` : ''}>${esc(c.label)}${c.id === def ? ' (역할 기본)' : ''}</option>`);
  return `<option value=""${cur ? '' : ' selected'}>CC 설정 따르기</option>` + opts.join('');
}

// 메시지의 모델 id(claude-opus-5-5, 날짜 꼬리가 붙을 수 있다)가 목록의 id와 같은 모델인가(11-14 — 전에는 family로 맞춰 버전을 못 갈랐다)
export function sameModel(msgModel, id) {
  if (!msgModel || !id) return false;
  return msgModel === id || (msgModel.startsWith(id + '-') && /^\d{8}$/.test(msgModel.slice(id.length + 1)));
}

// 패널 머리줄 모델 창(「이 세션의 모델」, 11-05 · 11-14 사용자 글 고침). 화면 글에 가운뎃점을 쓰지 않는다.
// 속에서 어떻게 바꾸는지(/model · CC 확인 창에 대신 답함 · CC 기본값 되돌림)는 사람이 알 일이 아니라 적지 않는다
export function modelMenuHtml(models, model, busy) {
  const items = ((models && models.choices) || []).map((c) => {
    const cur = sameModel(model, c.id);
    return `<button type="button" data-id="${esc(c.id)}" data-label="${esc(c.label)}"${cur ? ' class="cur"' : ''}>`
      + `<span><b>${esc(c.label)}</b>${cur ? ' <span class="muted">(지금)</span>' : ''}</span>`
      + `${c.note ? `<span class="muted small">${esc(c.note)}</span>` : ''}</button>`;
  }).join('');
  return '<div class="mdl-head">이 세션의 모델</div>' + items
    + (busy ? '<div class="small warn">작업 중입니다. 대기열에 들어가 지금 작업이 끝난 뒤 바뀝니다.</div>' : '')
    + '<div class="small muted">대화가 쌓인 세션은 바꾼 뒤 첫 응답이 전체 대화를 다시 읽느라 느리고 토큰이 더 들 수 있습니다.</div>'
    + '<div class="small muted">이 세션만 바뀝니다. 브리지가 다시 떠도, 이 세션을 이어서 띄우거나 새 세션으로 옮겨도 바꾼 모델을 그대로 씁니다.</div>';
}

// role · model <select> 한 쌍을 묶는다. 역할이 바뀌면(사람이 모델을 안 건드렸을 때만) 기본값으로
export function bindRoleModel(roleSel, modelSel, models) {
  let touched = false;
  const fill = (cur) => { modelSel.innerHTML = modelOptions(models, cur, roleSel.value); };
  modelSel.addEventListener('change', () => { touched = true; });
  roleSel.addEventListener('change', () => {
    fill(touched ? modelSel.value : ((models && models.defaults) || {})[roleSel.value] || '');
  });
  return { fill, reset() { touched = false; fill(((models && models.defaults) || {})[roleSel.value] || ''); } };
}
