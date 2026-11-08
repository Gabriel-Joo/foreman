// 인계 2판 d [잃은 것 보기](11-06, docs/11_handoff_v2.md 3장) — 인계 칸 안의 한 묶음.
// 압축으로 사라지거나 약해진 지시 · 결정을 `claude -p`(설정: config/models.toml [tasks] losscheck)가 판정한다.
// 화면에는 사라짐 · 약해짐만 보인다. [옮길 것 뽑기에 넣기]로 문서로 옮기기(c)의 입력이 된다 — 되살리기 전 사람이 마지막 관문이다.

import { esc, ago, keep } from './render.js';

const STATUS = { running: '도는 중…', done: '끝', failed: '실패' };

function item(x) {
  return `<div class="loss-item loss-${x.status === '사라짐' ? 'gone' : 'weak'}">
    <div class="small" title="${esc(x.status)} — 종류 ${esc(x.kind)} · 번호 ${esc(x.id)}"><b>${esc(x.status)}</b> ${esc(x.gist)}</div>
    ${x.quote ? `<div class="small muted">원문: “${esc(x.quote)}”</div>` : ''}
    ${x.where ? `<div class="small muted">있는 곳: ${esc(x.where)}</div>` : ''}
    ${x.status === '약해짐' && x.missing ? `<div class="small muted">빠진 것: ${esc(x.missing)}</div>` : ''}
    ${x.dropped_at ? `<div class="small muted">빠진 요약: ${esc(x.dropped_at)}</div>` : ''}
  </div>`;
}

// lc = 마지막 점검(없으면 null), can = 시작 가능, err = 표를 못 읽은 사유
export function lossGroup(lc, can, err) {
  const b = (act, label, on, tip, extra = '') => `<button type="button" data-act="${act}" class="small"${extra} title="${esc(tip)}"${on ? '' : ' disabled'}>${label}</button>`;
  // 11-06 이름 다시: 버튼 하나("잃은 것 찾기")로는 뭔지 몰랐다 — 이름 · 설명 줄 + 짧은 버튼
  let head = b('loss-run', lc ? '다시 찾기' : '찾기', can,
    '압축으로 잊은 지시 · 결정 찾기 — 사람이 한 말을 다시 읽어 지금 세션이 아직 기억하는지 판정합니다. 내가 보낸 말 20개당 약 0.4달러 · 1.5분이 듭니다.');
  if (lc) {
    const prog = lc.status === 'running' ? ` · ${lc.groups_done || 0}/${lc.groups_total || '?'} 진행` : '';
    const cost = lc.cost_usd != null ? ` · ${lc.cost_usd.toFixed(2)}달러` : '';
    head += `<span class="small">${esc(STATUS[lc.status] || lc.status)}${prog}${cost} · ${ago(lc.updated_at || lc.created_at)}${lc.model ? ` · ${esc(lc.model)}` : ''}</span>`;
  } else {
    head += '<span class="small muted">아직 없습니다.</span>';
  }
  let body = '';
  if (err) body += `<div class="small bad">${esc(err)}</div>`;
  if (lc && lc.error) body += `<div class="small ${lc.status === 'failed' ? 'bad' : 'warn'}">${esc(lc.error)}</div>`;
  if (lc && lc.status === 'done') {
    const c = lc.counts || {};
    body += `<div class="small">사라짐 ${c['사라짐'] || 0} · 약해짐 ${c['약해짐'] || 0} <span class="muted">(살아 있음 ${c['살아 있음'] || 0} · 뒤집힘 ${c['뒤집힘'] || 0} · 끝남 ${c['끝남'] || 0}, 내가 보낸 말 ${lc.prompts || 0}개)</span>
      ${lc.lost_total ? b('loss-use', '문서에 적기로 넘기기', true, '문서에 적기로 넘기기 — 이 목록을 아래 「대화에서 정한 것 문서에 적기」에 같이 넣습니다. 세션이 아직 문서에 없는 것만 고르고, 사람이 승인한 것만 씁니다.', ` data-lc="${lc.id}"`) : ''}</div>`;
    body += '<div class="small muted">기계 판정입니다 — 놓친 것이 있을 수 있고, 나중에 바뀐(뒤집힌) 결정이 섞일 수 있습니다. 문서에 넣기 전에 아래 「대화에서 정한 것 문서에 적기」에서 사람이 확인합니다.</div>';
    if (lc.lost && lc.lost.length) {
      body += `<details class="loss-list"${keep(`loss:${lc.id}:list`)}><summary class="small">잃은 것 ${lc.lost_total}${lc.lost_total > lc.lost.length ? `(앞 ${lc.lost.length}개)` : ''}</summary>${lc.lost.map(item).join('')}</details>`;
    }
  }
  return `<div class="hand-item"><div class="hand-item-h"><b>압축으로 잊은 지시 · 결정 찾기</b> <span class="small muted">자동 압축 때마다 앞에서 정한 것이 빠집니다. 무엇이 빠졌는지 찾습니다.</span></div>
    <div class="loss"><div class="hand-btns">${head}</div>${body}</div></div>`;
}
