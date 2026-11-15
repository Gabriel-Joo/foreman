// 인계 2판 d [잃은 것 보기](11-06, docs/11_handoff_v2.md 3장) — 인계 칸 안의 한 묶음.
// 압축으로 사라지거나 약해진 지시 · 결정을 `claude -p`(설정: config/models.toml [tasks] losscheck)가 판정한다.
// 화면에는 사라짐 · 약해짐만 보인다. [옮길 것 뽑기에 넣기]로 문서로 옮기기(c)의 입력이 된다 — 되살리기 전 사람이 마지막 관문이다.

import { esc, ago, keep, pickedLabel, pickedFamily } from './render.js';
import { lossOutcome } from './moveflow.js';

// 11-15 포스트잇 #49 — 잊은 것 찾기 비용 안내는 여기 한 곳(손으로 정한 어림값이다. 실측(lc.cost_usd)에서 계산하지 않는다).
// 쓰는 곳: 이 파일 버튼 호버, handoff.js 확인 창 둘, opanel.js 띠 호버 · 확인 창. 값이 바뀌면 여기만 고친다
export const LOSS_COST = { prompts: 20, usd: 0.4, min: 1.5 };
export const lossCost = (sep = ', ') => `내가 보낸 말 ${LOSS_COST.prompts}개당 약 ${LOSS_COST.usd}달러${sep}${LOSS_COST.min}분`;
export const LOSS_CONFIRM = `압축으로 잊은 것을 찾습니다. 압축 구간마다 사람이 한 말을 뽑아 claude -p로 판정합니다. ${lossCost()}이 듭니다. 끝나면 알림이 갑니다.\n\n진행할까요?`;

const STATUS = { running: '도는 중…', done: '끝', failed: '실패', nothing: '찾을 것 없음' };
const OUT = { found: '끝', clean: '끝, 잊은 것 없음', nothing: '찾을 것 없음', partial: '일부만 끝', failed: '실패' };
// 11-14 사용자 — 「찾을 것 없음」 밑에 따로 있던 설명 줄을 그 글의 호버로 옮겼다
const OUT_TIP = { nothing: '찾을 것 없음 — 이 세션은 압축된 적이 없어 잊은 것이 생기지 않았습니다.' };

// 결과 수 한 줄(11-13 사용자 — 숫자 여섯이 한 줄에 붙어 한눈에 안 들어왔다). 사람이 볼 사라짐 · 약해짐만 크게,
// 살아 있음 · 뒤집힘 · 끝남 · 내가 보낸 말은 「그 밖 N개」 호버로
export function sumLine(lc, out = lossOutcome(lc)) {
  const c = lc.counts || {};
  const gone = c['사라짐'] || 0, weak = c['약해짐'] || 0;
  const rest = ['살아 있음', '뒤집힘', '끝남'].map((k) => [k, c[k] || 0]);
  const restN = rest.reduce((a, [, v]) => a + v, 0);
  const tip = `판정 내역 — 사람이 보낸 말 ${lc.prompts || 0}개를 다시 읽어 지시 · 결정마다 지금도 기억하는지 판정했습니다. 사라짐 · 약해짐 말고는 할 일이 없습니다.\n`
    + rest.map(([k, v]) => `${k} ${v}`).join('\n') + `\n내가 보낸 말 ${lc.prompts || 0}개`
    + (lc.groups_failed ? `\n실패한 묶음 ${lc.groups_failed}개` : '') + (lc.skipped ? `\n건너뛴 말 ${lc.skipped}개` : '');
  const head = out === 'clean' ? '<span class="small ok">✓ 끝까지 찾았고 잊은 것이 없습니다.</span>'
    : `<span class="loss-n gone" data-tip="사라짐 — 지금 세션이 아예 기억하지 못하는 지시 · 결정입니다.">사라짐 ${gone}</span>
      <span class="loss-n weak" data-tip="약해짐 — 남아 있지만 이유나 조건이 빠진 지시 · 결정입니다.">약해짐 ${weak}</span>`;
  return `<div class="loss-sum">${head}<span class="small muted loss-rest" data-tip="${esc(tip)}">그 밖 ${restN}개</span></div>`;
}

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
  const b = (act, label, on, tip, extra = '', cls = '') => `<button type="button" data-act="${act}" class="small${cls ? ` ${cls}` : ''}"${extra} title="${esc(tip)}"${on ? '' : ' disabled'}>${label}</button>`;
  // 11-06 이름 다시: 버튼 하나("잃은 것 찾기")로는 뭔지 몰랐다 — 이름 · 설명 줄 + 짧은 버튼
  // 11-14 사용자 — 평소에 너무 길다. 소제목 · 설명문을 빼고 이름을 버튼에, 설명은 버튼 호버로. 한 줄(버튼 + 상태)
  let head = b('loss-run', '압축으로 잊은 것 찾기', can,
    `압축으로 잊은 것 찾기 — 자동 압축 때마다 앞에서 정한 것이 빠집니다. 사람이 한 말을 다시 읽어 지금 세션이 아직 기억하는지 판정합니다. ${lossCost()}이 듭니다.`,
    '', 'docs-run');
  if (lc) {
    // 11-14 사용자 — 가운뎃점으로 잇지 않고 칸마다 따로(빈칸으로 띄움). 모델은 날 이름(claude-sonnet-5-5) 대신 패널 모델 칩과 같은 배지
    const o = lossOutcome(lc), tip = OUT_TIP[o];
    head += `<span class="small${o === 'failed' ? ' bad' : o === 'partial' ? ' warn' : ''}"${tip ? ` title="${esc(tip)}"` : ''}>${esc(OUT[o] || STATUS[lc.status] || lc.status)}</span>`;
    if (lc.status === 'running') head += `<span class="small">${lc.groups_done || 0}/${lc.groups_total || '?'} 진행</span>`;
    if (lc.cost_usd != null) head += `<span class="small">${lc.cost_usd.toFixed(2)}달러</span>`;
    head += `<span class="small">${ago(lc.updated_at || lc.created_at)}</span>`;
    if (lc.model) head += `<span class="mdl f-${esc(pickedFamily(lc.model))}" title="모델 — 이 찾기에 쓴 모델입니다.">${esc(pickedLabel(lc.model))}</span>`;
  } else {
    head += '<span class="small muted">아직 없습니다</span>';
  }
  let body = '';
  if (err) body += `<div class="small bad">✗ 찾기 칸을 불러오지 못했습니다. ${esc(err)}</div>`;
  const out = lossOutcome(lc);
  // 11-13 사용자 — 「없음」과 「실패」를 가른다. 실패가 조용히 「없음」으로 보이면 안 된다(bridge/losscheck.py outcome)
  if (out === 'failed') body += `<div class="small bad">✗ 찾기 실패: 잊은 것이 없는 것이 아니라 찾지 못했습니다.${lc.error ? ` ${esc(lc.error)}${/[.다]$/.test(lc.error) ? '' : '.'}` : ''} [다시 찾기]로 다시 돌릴 수 있습니다.</div>`;
  else if (out === 'partial') body += `<div class="small warn">⚠ 일부만 찾았습니다. ${esc(lc.error || '묶음 일부가 실패했습니다')}. 아래 수는 찾은 데까지이고, 0이어도 「없음」이 아닙니다.</div>`;
  if (lc && lc.status === 'done') {
    body += sumLine(lc, out);
    if (lc.lost_total) body += `<div class="hand-btns">${b('loss-use', '잊은 것으로 문서 후보 묻기', true, '잊은 것으로 문서 후보 묻기 — 찾은 잊은 것을 세션에게 넘겨, 아직 문서에 없는 것만 문서 후보로 받습니다. 후보는 아래 [대화에서만 정한 것 문서에 적기] 줄에 뜨고, 사람이 고른 것만 씁니다.', ` data-lc="${lc.id}"`, 'primary')}</div>`;
    body += '<div class="small muted">기계 판정입니다. 놓친 것이 있을 수 있고, 나중에 바뀐(뒤집힌) 결정이 섞일 수 있습니다. 문서에 넣기 전에 아래 [대화에서만 정한 것 문서에 적기] 줄에서 사람이 확인합니다.</div>';
    if (lc.lost && lc.lost.length) {
      body += `<details class="loss-list"${keep(`loss:${lc.id}:list`)}><summary class="small">잃은 것 ${lc.lost_total}${lc.lost_total > lc.lost.length ? `(앞 ${lc.lost.length}개)` : ''}</summary>${lc.lost.map(item).join('')}</details>`;
    }
  }
  return `<div class="hand-item"><div class="loss"><div class="hand-btns">${head}</div>${body}</div></div>`;
}
