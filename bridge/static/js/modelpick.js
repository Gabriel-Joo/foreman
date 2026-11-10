// 모델 고르기(11-05) — [+ 세션] 창 · 포먼 계획 카드가 같이 쓴다. 목록 · 역할 기본값은 /api/spawn/options의 models(config/models.toml).
// 역할을 바꾸면 모델도 그 역할의 기본값으로 따라간다 — 사람이 모델을 직접 고른 뒤에는 따라가지 않는다.

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const ROLE_PICK = { coder: '코더 — 고치기 · 만들기', inspector: '점검 — 살펴보기 · 원인 찾기', cicd: 'CI/CD — 빌드 · 배포',
  scribe: '서기 — 문서 · 회고', manager: '관리자 — 합치기 · 시험 · push · 기록', designer: '디자이너 — 화면 · 테마 · 캐릭터' };
// 11-09 scribe가 빠져 있어 교장이 서기 계획(role scribe)을 내도 계획 카드 칸이 첫 값(코더)으로 보였다 — 그대로 시작하면 코더로 떴다

export function modelOptions(models, cur, role) {
  const m = models || { choices: [], defaults: {} };
  const def = (m.defaults || {})[role || 'coder'];
  const opts = (m.choices || []).map((c) =>
    `<option value="${esc(c.id)}"${c.id === cur ? ' selected' : ''}${c.note ? ` title="${esc(c.label)} — ${esc(c.note)}"` : ''}>${esc(c.label)}${c.id === def ? ' (역할 기본)' : ''}</option>`);
  return `<option value=""${cur ? '' : ' selected'}>CC 설정 따르기</option>` + opts.join('');
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
