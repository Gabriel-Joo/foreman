// FOREMAN 대시보드 — 그리는 쪽(6단계, 실용 화면). store.js의 state만 본다.
// 10단계 테마 렌더러는 이 파일 대신 같은 state를 받아 캐릭터로 그리면 된다(createRenderer(root, store)만 맞추면 된다).
// 영역(conn · approvals · grid · panel)마다 state.ver가 바뀐 것만 다시 그린다. 입력 칸 · 스크롤은 다시 그려도 유지한다.

// 10b: 승인 카드 · 대화 · 활동 · 세션 정보 · 파이프라인 HTML은 함수로 내보낸다 — 픽셀 화면 옆 패널(opanel.js)도 같은 것을 쓴다.

export const STATE_LABEL = { ACTIVE: '작업 중', IDLE: '대기', SUSPENDED: '정지', DORMANT: '종료' };
export const ORIGIN_LABEL = { human: '나', task_notification: '완료 알림', subagent_message: '서브에이전트 결과', agent_message: '다른 세션', meta: '자동 메시지', handoff: '옮기기 요약 요청(FOREMAN)', handoff_in: '옮겨 온 요약(FOREMAN)', manager_ask: '관리자 부탁', relay: '작업 세션 보고' };
const END_LABEL = { stop: '끝남', stop_failure: 'API 오류', interrupted: '중단', session_end: '세션 종료', process_lost: '프로세스 사라짐', merged: '다음 입력에 합쳐짐', no_signal: '신호 없음', abandoned: '끝 신호 없이 버려짐' };

import { stuckTurn } from './store.js';
import { renderMarkdown } from './md.js';

// 역할 화면 이름(11-09 — scribe · manager 보탬). foreman은 감독실 캐릭터 몫(테마 이름 팀장 · 교장 · 소장)이라 세션 역할로 고를 수 없다
// 11-10 designer(디자이너 — 화면 담당) 보탬
export const ROLE_LABEL = { coder: '코더', designer: '디자이너', manager: '관리자', scribe: '서기', inspector: '점검', cicd: 'CI/CD', foreman: '감독', helper: '도우미', infra: '인프라' };
// 세션 역할로 고를 수 있는 것 — bridge/api/handoff.py SessionRole과 같다
export const SESSION_ROLES = ['coder', 'designer', 'manager', 'scribe', 'inspector', 'cicd'];
export const roleLabel = (r) => ROLE_LABEL[r] || null;
// 역할 색 — 한 곳(11-13 사용자 「발밑 역할 색은 역할 배지와 같게」). 패널 배지(.rolebadge.role-*)와 픽셀 화면 발밑 색 원(office.js drawAura)이
// 모두 이 값을 쓴다. 배지 CSS는 아래 roleColorCss()가 문서에 넣는다(panel.css에는 색이 없고 역할 없음 · 기본 회색만 있다).
// 테마 옷 색(theme.json roles.colors — 로브 · 사원증 끈 · 안전모)은 그림에 맞춘 다른 값이라 따로 둔다
export const ROLE_COLOR = { coder: '#5b9be6', manager: '#e0604f', scribe: '#d08b4f', inspector: '#3fbf85', cicd: '#b07ad0', designer: '#e8619f', foreman: '#c9a227' };
export const roleColorCss = () => Object.entries(ROLE_COLOR).map(([r, c]) => `.rolebadge.role-${r} { --rc:${c}; }`).join('\n');
if (typeof document !== 'undefined' && !document.getElementById('roleColors')) {
  const st = document.createElement('style');
  st.id = 'roleColors';
  st.textContent = roleColorCss();
  document.head.appendChild(st);
}
// 제목 앞 역할 배지 글(11-09 사용자 — "서기인지 코더인지 모르고 지나쳤다"). 역할은 제목 글자가 아니라 따로 — 제목을 고쳐도 남는다
export const roleTag = (r) => `[${roleLabel(r) || '역할?'}]`;
export const ROLE_UNKNOWN_TIP = '역할? — 이 세션의 역할을 알 수 없습니다. 머리줄 역할을 눌러 정합니다.';
// 패널 머리줄 배지(11-10 사용자 — "코더 패널에도 서기 패널에도 [디자이너]"): 배지는 그 캐릭터의 역할이다.
// 세션 패널은 그 세션의 role, 세션 없는 캐릭터(서기실 · 코더 자리 · 감독)는 자기 역할. 파이프라인 캐릭터 · 빈 패널은 배지 없음(null)
const TARGET_ROLE = { scribe: 'scribe', coder: 'coder', foreman: 'foreman' };
export function panelRole(target, s) {
  if (!target) return null;
  if (target.kind === 'session') {
    // 11-13 사용자 — 코더 상주 · 임시 구분을 없앴다(모든 코더 세션이 같은 모양). 배지는 역할만
    const l = s ? roleLabel(s.role) : null;
    const tip = l ? `${l} — 이 세션이 맡은 역할입니다. 눌러서 바꿉니다. 제목을 고쳐도 역할은 그대로입니다.` : ROLE_UNKNOWN_TIP;
    return { role: l ? s.role : 'none', label: l || '역할?', editable: !!s, tip };
  }
  const r = TARGET_ROLE[target.kind];
  return r ? { role: r, label: roleLabel(r), editable: false, tip: `${roleLabel(r)} — 이 캐릭터의 역할입니다.` } : null;
}
export function roleBadge(s) {
  const l = roleLabel(s.role);
  const tip = l ? `${l} — 이 세션이 맡은 역할입니다. 제목을 고쳐도 그대로입니다.` : ROLE_UNKNOWN_TIP;
  return `<span class="rolebadge role-${esc(s.role || 'none')}" title="${esc(tip)}">${esc(l || '역할?')}</span>`;
}

// 세션을 알아보는 이름 — CC가 붙인 제목 → CC 세션 이름 → 짧은 id. 캐릭터 이름은 아래 줄에(한 캐릭터에 세션 여럿)
// 11-09 사람이 해야 풀리는 대기 — "대기"(쉼)와 따로. 무엇을 어디서 하는지 호버에(사용자: 사람 답을 기다리는 상태는 쉼이 아니다)
export function humanNeed(s) {
  if (!s || s.state === 'DORMANT') return null;
  if (s.denied) {
    const who = s.denied.subagent ? '서브에이전트의 ' : '';
    return { label: '권한 거부', tip: `권한 거부 — CC 자체 권한 검사(auto mode)가 ${who}${s.denied.tool || '도구'}를 막았습니다${s.denied.reason ? '(' + s.denied.reason + ')' : ''}. FOREMAN 승인 카드로는 오지 않습니다. 그 세션에 허용 · 다른 방법을 지시하거나 settings에 허용 규칙을 넣어야 풀립니다.` };
  }
  if (s.api_stop) return { label: 'API 오류로 멈춤', tip: apiStopTip(s.api_stop) };
  if (s.asks) return { label: '답 기다림', tip: '답 기다림 — 마지막 응답이 사람에게 묻고 끝났습니다. 패널 입력 칸이나 그 세션 대화창에서 답하면 풀립니다.' };
  if (s.escalate && s.escalate.question) return { label: '사용자 답 기다림', tip: ESC_TIP.question(s.escalate.question) };
  return null;
}
// 11-13 API 오류로 멈춤(브리지 dashboard.py api_stops) — 마지막 턴이 API 오류로 끝났고 새 턴이 없다. 서버 상태는 쉼(IDLE)이라
// 따로 가르지 않으면 쉬는 세션과 똑같다(11-12 코더 311). 종류 · 할 일은 대화 패널 턴 끝 이름표와 같은 bridge/api_error.py
export function apiStopTip(a) {
  const named = a.label && a.label !== 'API 오류' ? a.label : '';     // 모르는 종류(unknown)는 「API 오류」 그대로
  const kind = [named + (a.detail ? ` [${a.detail}]` : ''), a.reset ? `${a.reset}에 풀림` : ''].filter((x) => x.trim()).join(' · ');
  return `API 오류로 멈춤 — 마지막 턴이 API 오류${kind ? `(${kind})` : ''}로 끝났고 그 뒤 새 입력이 없습니다. 할 일: ${a.action || '그 세션 대화창에서 오류 글을 보고 다시 보냅니다'}.`
    + `${a.request_id ? ` (${a.request_id})` : ''} 다시 보내면 풀립니다. 30분 넘게 그대로면 텔레그램으로 한 번 더 알립니다.`;
}
// 11-13(사용자) — 사람이 볼 것은 관리자 머리 위에만. 관리자가 POST /api/sessions/{sid}/escalate로 올린 것만 뜬다
const ESC_TIP = {
  // 11-13 사람 승인 합치기 카드는 브리지가 관리자 머리 위로 올린다(merge_sid) — 답이 아니라 [합치기]를 눌러야 풀린다
  question: (e) => (e && e.merge_sid != null
    ? `사용자 답 기다림 — 세션 ${e.merge_sid}의 합치기 카드가 사람 승인을 기다립니다. 말풍선을 누르면 그 세션 패널의 「세션」 탭에서 합치거나 나중으로 미룹니다. 합치거나 미루면 사라집니다.${e.text ? `\n${e.text}` : ''}`
    : `사용자 답 기다림 — 관리자가 사람에게 물었습니다. 패널 입력 칸에 답하면 풀립니다.${e && e.text ? `\n${e.text}` : ''}`),
  report: (e) => `사용자에게 보고함 —관리자가 사람에게 보고했습니다. 누르면 대화가 열리고, 읽으면 사라집니다.${e && e.text ? `\n${e.text}` : ''}`,
};
// 캐릭터 머리 위 말풍선(11-11 사용자 — 답 기다림 · 보고가 캐릭터에 안 보였다). 답 기다림은 노랑(warn), 보고 옴은 초록(ok)으로 갈라
// 「답해야 하는 것」과 「읽기만 하면 되는 것」을 한눈에. 보고 옴은 그 세션 패널을 열면 사라진다(opanel → store.reportRead)
export function needMark(s) {
  if (!s || s.state === 'DORMANT') return null;
  if (s.denied) return { text: '권한 거부', tone: 'warn', tip: humanNeed(s).tip };
  // 11-13 API 오류로 멈춤 — 세션이 막혔다는 뜻이라 권한 거부처럼 작업 세션에도 사람용으로, 빨강(bad). 권한 거부 다음(둘 다 막힘이고
  // 권한 거부는 그 전부터 있던 순서), 답 기다림 위(묻는 말은 오류 전 응답일 수 있다 — 지금 막힌 것은 오류다)
  if (s.api_stop) return { text: 'API 오류로 멈춤', tone: 'bad', tip: apiStopTip(s.api_stop) };
  if (s.asks) return { text: '답 기다림', tone: 'warn', tip: humanNeed(s).tip };
  const e = s.escalate || {};
  if (e.question) return { text: '사용자 답 기다림', tone: 'warn', tip: ESC_TIP.question(e.question), mergeSid: e.question.merge_sid ?? null };
  // 겹치면(11-11): 권한 거부 > 답 기다림 > 합치기 기다림 > 보고 옴. 앞의 둘은 세션이 막혀 있어 지금 사람 손이 먼저 필요하고,
  // 합치기는 사람이 눌러야 끝나는 일이라 읽기만 하면 되는 보고보다 위다(합치기 카드가 떠 있으면 그 응답은 보고이기도 하다)
  // 11-13(사용자): 관리자 머리 위로 올렸으면(to_manager) 여기에는 안 띄운다 — 관리자가 없거나 못 올렸을 때만 남는다
  if (s.merge_wait && !s.merge_wait.to_manager) return { text: '합치기 기다림', tone: 'merge', tip: '합치기 기다림 — 일을 마친 따로 작업의 합치기 카드가 승인을 기다립니다. 누르면 그 세션 패널의 「세션」 탭에서 합치거나 나중으로 미룹니다.' + (s.merge_wait.esc_error ? ` 관리자 머리 위로 올리지 못해 여기 띄웠습니다(${s.merge_wait.esc_error}).` : ''), mergeSid: s.id };
  if (e.report) return { text: '사용자에게 보고함', tone: 'ok', tip: ESC_TIP.report(e.report) };
  if (s.report) return { text: '보고 옴', tone: 'ok', tip: '보고 옴 — 묻지 않고 일을 마친 응답이 왔습니다. 누르면 대화가 열리고, 읽으면 사라집니다.' };
  return workerMark(s);
}
// 11-13 작업 세션이 관리자에게 넘긴 것 — 사람 몫이 아니라 작게(quiet). 넘기지 못했으면 서버가 위 asks · report로 낸다.
// 11-13 사용자(관리자 318 전달): 「관리자 답 기다림」은 남긴다(코더가 관리자 답을 기다리느라 멈춰 있다). 같은 턴을 보고로도 · 물음으로도
// 넘겼으면(kinds) 「관리자에게 보고함」이 이긴다 — 보고한 뒤에는 관리자가 답을 주든 말든 코더는 할 일이 없다
function workerMark(s) {
  if (!s.relayed) return null;
  const kinds = s.relayed.kinds || [s.relayed.kind];
  return !kinds.includes('report') && kinds.includes('question')
    ? { text: '관리자 답 기다림', tone: 'quiet', tip: '관리자 답 기다림 — 이 세션의 물음을 관리자에게 넘겼습니다. 관리자가 모아 사람에게 올립니다.' }
    : { text: '관리자에게 보고함', tone: 'quiet', tip: '관리자에게 보고함 — 이 세션의 보고를 관리자에게 넘겼습니다. 사람은 읽지 않아도 됩니다.' };
}
// 합치기 기다림 세션을 가장 오래된 카드부터(승인 막대 건수 · 누르면 열 세션)
export function mergeWaits(sessions) {
  return [...sessions].filter((s) => s && s.merge_wait).sort((a, b) => Date.parse(a.merge_wait.since) - Date.parse(b.merge_wait.since) || a.id - b.id);
}
// 멈춤(11-11, 브리지 bridge/stallwatch.py가 1분마다 잼) — 작업 중 끊김 · 응답 없음 · 맴돎 · 끝내기 확인 창 · 긴 작업
export function stallChip(s) {
  const list = (s && s.stall) || [];
  if (!list.length) return '';
  return list.map((f) => `<span class="${f.kind === 'long' ? 'muted' : 'warn'}" title="${esc(`${f.label} — ${f.detail}${f.kind === 'long' ? '' : ' 텔레그램으로도 알립니다.'}`)}">⏸ ${esc(f.label)}</span>`).join(' ') + ' ';
}
export function stateBadge(s) {
  const n = humanNeed(s);
  return n ? `<span class="badge st-NEED" title="${esc(n.tip)}">${esc(n.label)}</span>`
    : `<span class="badge st-${s.state}">${esc(STATE_LABEL[s.state] || s.state)}</span>`;
}
export function sessionName(s) { return s.custom_title || s.title || s.cc_name || s.short; }   // 사람이 붙인 이름이 먼저(11-05)
export function sessionSub(s) {
  // 역할은 제목 앞 배지(roleBadge)가 맡는다(11-09). 여기는 캐릭터 이름에서 역할 이름을 뗀 나머지만 —
  // "코더 foreman-3" → "따로 작업 foreman-3", "코더" → 없음. 역할 캐릭터가 아닌 이름(떠돌이 등)은 그대로
  const c = s.character || '';
  for (const l of Object.values(ROLE_LABEL)) {
    if (c === l) return '';
    if (c.startsWith(l + ' ')) return `따로 작업 ${c.slice(l.length + 1)}`;
  }
  return c;
}
// 호버용 — 세션 짧은 id · tmux 창
export function sessionIds(s) {
  return [s.short ? `세션 ${s.short}` : '', s.tmux_pane ? `tmux 창 ${s.tmux_pane}` : ''].filter(Boolean).join(' · ');
}

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function ago(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
  if (s < 60) return `${s}초 전`;
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}
// 대화의 시각은 "n분 전"이 아니라 시계 — 10초마다 글이 바뀌면 대화를 다시 그려야 해서 읽던 자리 · 고른 글자가 날아간다
export function clock(ts) {
  if (!ts) return '';
  const d = new Date(ts), now = new Date();
  const hm = d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
  return d.toDateString() === now.toDateString() ? hm : `${d.getMonth() + 1}/${d.getDate()} ${hm}`;
}
function since(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
  return s < 60 ? `${s}초째` : s < 3600 ? `${Math.floor(s / 60)}분째` : `${Math.floor(s / 3600)}시간 ${Math.floor((s % 3600) / 60)}분째`;
}
export function tok(n) {
  n = n || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return String(n);
}
export function promptText(p) {
  if (!p) return '';
  const s = p.replace(/^\s*<pasted_content id="[0-9a-f]+">\s*/, '').replace(/\s*<\/pasted_content id="[0-9a-f]+">\s*$/, '').trim();
  return unwrapAgent(s);
}

// CC 내부 포장을 벗긴다(11-05) — 서브에이전트 · 다른 세션 결과는
//   [Another Claude session sent a message:] <agent-message from="…">\n[Subagent hand-back] …The report follows:\n  (두 칸 들여 쓴 본문)\n</agent-message>
// 완료 알림은 <task-notification>…<status>…<summary>…[<result>…] — 요약 · 결과만
export function unwrapAgent(s) {
  // 여러 개가 한 입력에 붙어 오거나(대기열이 합쳐짐) 길이 제한으로 닫는 태그가 잘려 올 수 있다 — 하나씩, 닫는 태그가 없으면 끝까지
  if (s.includes('<agent-message from=')) {
    const re = /(?:Another Claude session sent a message:\s*)?<agent-message from="[^"]*">[ \t]*\n?([\s\S]*?)(?:<\/agent-message>|$)/g;
    const one = (body) => {
      const f = body.indexOf('The report follows:');
      if (/^\s*\[[^\]]*hand-back\]/i.test(body) && f >= 0) body = body.slice(f + 'The report follows:'.length);
      return body.replace(/^\n/, '').split('\n').map((ln) => ln.replace(/^  /, '')).join('\n').trim();
    };
    return s.replace(re, (_, body) => `${one(body)}\n\n`).replace(/\n{3,}/g, '\n\n').trim();
  }
  if (/^\s*<task-notification>/.test(s)) {
    const tag = (k) => { const x = new RegExp(`<${k}>([\\s\\S]*?)</${k}>`).exec(s); return x ? x[1].trim() : ''; };
    const st = tag('status'), sum = tag('summary'), res = tag('result');
    return [`[${st || '알림'}] ${sum}`.trim(), res].filter(Boolean).join('\n\n') || s;
  }
  return s;
}

// 가벼운 마크다운 — 터미널처럼 굵게 · 제목 · 코드가 보이게. 먼저 이스케이프하고 그다음 바꾼다(HTML을 통과시키지 않는다)
// 11-05 — 표 · 목록 · 들여 쓴 코드블록을 못 읽어 깨지던 것을 블록 단위 파서(md.js)로 바꿈
export function mdLite(s) { return renderMarkdown(s); }

// 긴 글은 앞부분만 보이고 [전체 보기] — 패널 안에 스크롤을 또 만들지 않는다. 펼친 것은 다시 그려도 펼친 채로
const OPEN_MSG = new Set();
const CLAMP_LINES = 100, CLAMP_CHARS = 12000;   // 11-05 — 기본은 펼침, 아주 긴 것(100줄 넘는 것)만 접는다(전에는 14줄)
export function longText(key, text_) {
  const t = String(text_ || '');
  const long = t.split('\n').length > CLAMP_LINES || t.length > CLAMP_CHARS;
  if (!long) return `<div class="txt md">${mdLite(t)}</div>`;
  const open = OPEN_MSG.has(key);
  return `<div class="txt md clamp${open ? ' open' : ''}" data-mk="${esc(key)}">${mdLite(t)}</div>
    <button class="more ghost small" data-mk="${esc(key)}">${open ? '접기' : `전체 보기 (${t.length.toLocaleString()}자)`}</button>`;
}
if (typeof document !== 'undefined') {
  document.addEventListener('click', (ev) => {
    const b = ev.target.closest && ev.target.closest('button.more[data-mk]');
    if (!b) return;
    const k = b.dataset.mk, box = b.previousElementSibling;
    if (OPEN_MSG.has(k)) OPEN_MSG.delete(k); else OPEN_MSG.add(k);
    const open = OPEN_MSG.has(k);
    if (box) box.classList.toggle('open', open);
    b.textContent = open ? '접기' : `전체 보기 (${(box ? box.textContent.length : 0).toLocaleString()}자)`;
  });
  document.addEventListener('toggle', (ev) => {        // "중간 글" 펼침도 다시 그릴 때 유지(toggle은 버블링하지 않아 capture로)
    const d = ev.target;
    if (d && d.dataset && d.dataset.mid) { if (d.open) OPEN_MSG.add(d.dataset.mid); else OPEN_MSG.delete(d.dataset.mid); }
    if (d && d.dataset && d.dataset.keep) DETAILS.set(d.dataset.keep, d.open);
  }, true);
}

// 접고 펴는 칸(<details>)의 상태 기억(11-06) — 패널은 몇 초마다 · 이벤트마다 innerHTML로 다시 그려서, 사람이 접은 칸이
// 처음값(open)으로 되돌아갔다(서기실 창 · 요약 고치기). 칸마다 이름(key)을 주면 사람이 바꾼 상태로 다시 그린다.
// 쓰는 법: `<details class="hand"${keep('scribe:todo', true)}>` — 처음값은 dflt, 사람이 한 번 바꾸면 그 뒤로는 그 상태
const DETAILS = new Map();
export function keep(key, dflt = false) {
  const open = DETAILS.has(key) ? DETAILS.get(key) : dflt;
  return ` data-keep="${esc(key)}"${open ? ' open' : ''}`;
}
export function oneLine(s, n) {
  s = promptText(s).replace(/\s+/g, ' ');
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}
export function why(s) {
  if (!s.pid) return '세션이 끝났습니다(프로세스가 없습니다).';
  if (s.proc === 'T') return '멈춘 세션입니다. 지금 보내면 셸 명령으로 실행되므로 막았습니다.';
  if (!s.tmux_pane) return 'tmux 밖에서 도는 세션이라 화면에서 보낼 수 없습니다.';
  return '';
}

// ── 두 화면이 같이 쓰는 조각(10b) ──────────────────────────
export function projectLabel(st, name) { return (st.projects.find((p) => p.name === name) || {}).label || name || '미분류'; }

// 처리된 승인 카드의 상태(11-06 — "allowed · browser"처럼 DB 값이 그대로 보였다). [글, 색]
const APPR_DONE = { allowed: ['허용했습니다', 'ok'], denied: ['거부했습니다', 'bad'], timeout: ['시간 초과 — CC가 기본값대로 정했습니다', 'warn'],
  terminal: ['터미널에서 답했습니다', ''], abandoned: ['브리지가 다시 떠서 정리했습니다', 'muted'], pending: ['기다리는 중입니다', 'warn'] };
const APPR_BY = { browser: '화면에서', terminal: '터미널에서', bridge: '브리지가' };
// ── 카드가 어디에 뜨나(11-10 사용자 — 받은 할 일 #5 · #11) ──────────────────────────
// 전에는 패널 맨 위에 모든 세션의 카드가 떠서, FOREMAN 질문이 [런슈즈]에서 · 런슈즈 승인이 라운지에서 보였고 그 자리에서 답할 수 있었다.
// 이제: 답하는 카드는 그 세션 패널에만(mine). 다른 세션 것은 한 줄로 보이기만 하고 [세션 열기]로 간다(peek — 답 버튼 없음).
// 답한 카드는 그 세션 패널에서 한 줄로 접힌다(folded). 세션을 모르는 것(session_id 없음)만 어디서나 답할 수 있게 둔다 — 갈 패널이 없다
export function apprPlace(list, sid) {
  const out = { mine: [], peek: [], folded: [] };
  for (const a of list) {
    const own = a.session_id == null || (sid != null && a.session_id === sid);
    if (a.status === 'pending') (own ? out.mine : out.peek).push(a);
    else if (own && a.session_id != null) out.folded.push(a);
  }
  return out;
}
// 어느 세션 것인지 — 「프로젝트 · [역할] 세션 N」(카드 머리 · 한 줄 모두)
export function apprWho(a, st) {
  const s = a.session_id != null ? st.sessions.get(a.session_id) : null;
  const sess = a.session_id == null ? '세션 모름' : `${s ? roleTag(s.role) + ' ' : ''}세션 ${a.session_id}`;
  return `${projectLabel(st, a.project)} · ${sess}`;
}
const firstQ = (a) => (Array.isArray(a.questions) && a.questions[0] ? a.questions[0].question : '') || a.summary || a.target || '';
// 답한 것 — 이 화면에서 고른 답(PICKS · NOTES), 없으면 브리지가 보낸 message("질문 → 답; … · 글: …")에서 질문을 뗀 것
export function apprAnswer(a) {
  const p = PICKS.get(a.id), note = (NOTES.get(a.id) || '').trim();
  if (p && Object.values(p).some((v) => v && v.length)) return Object.values(p).map((v) => (v || []).join(', ')).filter(Boolean).join(' · ') + (note ? ` · 글: ${note}` : '');
  if (!a.message) return note ? `글: ${note}` : '';
  return a.message.split('; ').map((x) => { const i = x.indexOf(' → '); return i < 0 ? x : x.slice(i + 3); }).join(' · ');
}
const FOLD_HEAD = { allowed: ['✓', 'ok'], denied: ['✕', 'bad'], timeout: ['⏰', 'warn'], terminal: ['✓', ''], abandoned: ['·', 'muted'] };
// 접힌 한 줄 — 누르면 펼침(EXPANDED), 끝 [×]는 치우기(store.dismissApproval)
export const EXPANDED = new Set();
export function apprFoldLine(a, st) {
  const q = a.tool === 'AskUserQuestion';
  const [mark, cls] = FOLD_HEAD[a.status] || ['·', 'muted'];
  const verb = q ? ({ allowed: '답함', terminal: '터미널에서 답함', timeout: '시간 초과', abandoned: '정리됨', denied: '거부함' }[a.status] || a.status)
    : ({ allowed: '허용함', denied: '거부함', terminal: '터미널에서 답함', timeout: '시간 초과', abandoned: '정리됨' }[a.status] || a.status);
  const ans = apprAnswer(a);
  const what = q ? `「${oneLine(firstQ(a), 60)}」` : `▶ ${oneLine(a.summary || a.target || a.tool, 60)}`;
  const open = EXPANDED.has(a.id);
  return `<div class="appr-fold${open ? ' open' : ''}">
    <button class="appr-fold-b" data-aid="${a.id}" data-act="fold" aria-expanded="${open}"
      data-tip="${esc(`${q ? '답한 질문' : '처리한 승인'} — 누르면 ${open ? '접습니다' : '펼쳐 전체를 봅니다'}. ${apprWho(a, st)}`)}"><span class="${cls}">${mark} ${esc(verb)}</span> — ${esc(what)}${ans ? ` → <b>${esc(oneLine(ans, 80))}</b>` : ''}</button>
    <button class="ghost small appr-x" data-aid="${a.id}" data-act="dismiss" data-tip="치우기 — 이 줄을 지웁니다. 답은 [세션] 탭 승인 기록에 남습니다." aria-label="치우기">×</button>
  </div>${open ? approvalCard(a, st) : ''}`;
}
// 다른 세션 것 — 보이기만(답 버튼 없음). [세션 열기]로 그 세션 패널에 가서 답한다
export function apprPeekLine(a, st) {
  const q = a.tool === 'AskUserQuestion';
  const what = q ? `「${oneLine(firstQ(a), 50)}」` : `▶ ${oneLine(a.summary || a.target || a.tool, 50)}`;
  return `<div class="appr-peek">
    <span class="appr-peek-t" data-tip="${esc(`${q ? '다른 세션의 질문' : '다른 세션의 승인 요청'} — ${apprWho(a, st)}. 답은 그 세션 패널에서 합니다.\n${q ? firstQ(a) : (a.summary || a.target || '')}`)}"><span class="warn">${q ? '❓' : '🔐'}</span> <b>${esc(apprWho(a, st))}</b> ${esc(what)}</span>
    <button class="ghost small" data-aid="${a.id}" data-sid="${a.session_id}" data-act="open" data-tip="세션 열기 — 이 ${q ? '질문' : '승인'}을 한 세션의 패널을 엽니다. 답은 거기서 합니다.">세션 열기</button>
  </div>`;
}

export function approvalCard(a, st) {      // 버튼은 data-aid · data-act(allow · deny · open) — 누르면 handleApprovalClick
  const done = a.status !== 'pending';
  // 질문(AskUserQuestion)은 승인이 아니다 — 선택지를 버튼으로, 누르면 그 답이 세션에 바로 들어간다(11-09 사용자)
  if (a.tool === 'AskUserQuestion') return questionCard(a, st, done);
  return `<div class="appr ${done ? 'done' : ''}">
    <div class="appr-main">
      <div><b>🔐 ${esc(apprWho(a, st))}</b> · <span title="${esc(a.tool)} — 승인 #${a.id} · 걸린 규칙 ${esc(a.rule)}">${esc(a.tool)}</span></div>
      ${a.summary ? `<div class="appr-sum">▶ ${esc(a.summary)}</div>` : ''}
      ${a.summary ? `<details class="small"${keep(`appr:${a.id}:cmd`)}><summary class="muted">명령 전체</summary><code>${esc(a.target)}</code></details>` : `<code>${esc(a.target)}</code>`}
      <div class="small muted">${esc(a.reason || '')}${a.error ? ` · <span class="bad">${esc(a.error)}</span>` : ''}</div>
    </div>
    <div class="appr-act">${done ? `<span class="small ${(APPR_DONE[a.status] || [])[1] || ''}">${esc((APPR_DONE[a.status] || [a.status])[0])}${
        (a.status === 'allowed' || a.status === 'denied') && APPR_BY[a.decided_by] ? ' · ' + APPR_BY[a.decided_by] : ''}</span>` :
      `<button data-aid="${a.id}" data-act="allow">승인</button><button data-aid="${a.id}" data-act="deny" class="ghost">거부</button>`}
      ${a.session_id ? `<button data-aid="${a.id}" data-sid="${a.session_id}" data-act="open" class="ghost small">세션</button>` : ''}</div>
  </div>`;
}
// 질문 카드 — 고른 것은 다시 그려도 남게 여기에(aid → 질문 번호 → 고른 선택지 이름들)
const PICKS = new Map();
// 답과 함께 보낼 글(11-10, 받은 할 일 #2) — aid → 글. 카드를 다시 그려도 남게 여기에(칸 값은 그린 뒤 opanel이 되살린다)
export const NOTES = new Map();
function questionCard(a, st, done) {
  const qs = !done && Array.isArray(a.questions) ? a.questions : null;
  const picks = PICKS.get(a.id) || {};
  // 질문이 하나 · 하나만 고름이면 누르는 즉시 보낸다(적어 둔 글도 같이). 여럿이거나 여러 개 고름이면 고른 뒤 [답 보내기]
  const instant = qs && qs.length === 1 && !qs[0].multi;
  const ready = qs && qs.every((q, i) => (picks[i] || []).length);
  const note = qs ? `<textarea class="appr-note" data-note-aid="${a.id}" rows="2" placeholder="답과 함께 보낼 글(없어도 됩니다)"
      data-tip="글 — 고른 답과 함께 세션에 갑니다. 고르지 않고 글만 보내도 됩니다(아래 [글만 보내기])."></textarea>` : '';
  const body = qs ? qs.map((q, i) => `<div class="appr-qq">
        <div class="appr-sum">${q.header ? `<span class="muted">[${esc(q.header)}]</span> ` : ''}${esc(q.question)}${q.multi ? ' <span class="small muted">(여러 개 고를 수 있습니다)</span>' : ''}</div>
        ${q.options.map((o, j) => `<button class="appr-opt ${(picks[i] || []).includes(o.label) ? 'on' : ''}" data-aid="${a.id}" data-act="pick" data-qi="${i}" data-oi="${j}"
          title="${esc(o.label)} — ${instant ? '누르면 이 답을 세션에 바로 넣습니다.' : '고른 뒤 [답 보내기]를 누릅니다.'}"><b>${esc(o.label)}</b>${o.description ? `<small>${esc(o.description)}</small>` : ''}</button>`).join('')}
      </div>`).join('')
    : `<div class="appr-q">${esc(a.target)}</div>`;
  const doneTxt = a.status === 'allowed' ? '답했습니다 · 화면에서' : a.status === 'terminal' ? '답했습니다 · 터미널에서' : (APPR_DONE[a.status] || [a.status])[0];
  return `<div class="appr appr-ask ${done ? 'done' : ''}">
    <div class="appr-main">
      <div><b>❓ ${esc(apprWho(a, st))}</b> · <span title="세션의 질문 — 세션이 고를 것을 묻고 답을 기다립니다. 선택지를 누르면 그 답이 세션에 바로 들어갑니다. 대화창에서 답해도 됩니다.">세션이 묻습니다</span></div>
      ${body}
      ${note}
      ${a.error ? `<div class="small bad">${esc(a.error)}</div>` : ''}
    </div>
    <div class="appr-act">${done ? `<span class="small ${(APPR_DONE[a.status] || [])[1] || ''}">${esc(doneTxt)}</span>`
      : qs ? `${instant ? '' : `<button data-aid="${a.id}" data-act="answer" class="primary" ${ready ? '' : 'disabled'} title="답 보내기 — 고른 답을 적은 글과 함께 세션에 넣습니다.">답 보내기</button>`}<button data-aid="${a.id}" data-act="note" class="ghost small" ${(NOTES.get(a.id) || '').trim() ? '' : 'disabled'} title="글만 보내기 — 고르지 않고 적은 글만 답으로 보냅니다. 고른 것이 있으면 같이 갑니다.">글만 보내기</button>`
        : '<span class="small warn" title="대화창에서 답합니다 — 브리지가 다시 떠서 이 질문의 선택지를 잃었습니다.">대화창에서 답합니다</span>'}
      ${a.session_id ? `<button data-aid="${a.id}" data-sid="${a.session_id}" data-act="open" class="ghost small" title="세션 — 이 질문을 한 세션의 패널을 엽니다.">세션</button>` : ''}</div>
  </div>`;
}
function sendAnswer(store, a, picks) {
  const out = {};
  a.questions.forEach((q, i) => { out[q.question] = picks[i] || []; });
  store.answer(a.id, out, (NOTES.get(a.id) || '').trim() || null);
}
// 글 칸 — 친 글을 NOTES에 두고 [글만 보내기]를 켜고 끈다(카드를 다시 그리지 않는다 — 치는 중 칸이 날아가지 않게)
export function handleApprovalInput(ev) {
  const t = ev.target.closest('textarea[data-note-aid]');
  if (!t) return;
  NOTES.set(Number(t.dataset.noteAid), t.value);
  const b = t.closest('.appr').querySelector('button[data-act="note"]');
  if (b) b.disabled = !t.value.trim();
}
// 다시 그린 뒤 글 칸 값을 되살린다
export function restoreNotes(root) {
  for (const t of root.querySelectorAll('textarea[data-note-aid]')) t.value = NOTES.get(Number(t.dataset.noteAid)) || '';
}

export function handleApprovalClick(ev, store, openSession) {
  const b = ev.target.closest('button[data-aid]');
  if (!b) return;
  const aid = Number(b.dataset.aid);
  if (b.dataset.act === 'fold') {
    if (EXPANDED.has(aid)) EXPANDED.delete(aid); else EXPANDED.add(aid);
    store.touch('approvals');
    return;
  }
  if (b.dataset.act === 'dismiss') { EXPANDED.delete(aid); store.dismissApproval(aid); return; }
  if (b.dataset.act === 'note') {
    const a = store.state.approvals.get(aid);
    if (a && Array.isArray(a.questions) && (NOTES.get(aid) || '').trim()) sendAnswer(store, a, PICKS.get(aid) || {});
    return;
  }
  if (b.dataset.act === 'pick' || b.dataset.act === 'answer') {
    const a = store.state.approvals.get(aid);
    if (!a || !Array.isArray(a.questions)) return;
    const picks = PICKS.get(aid) || {};
    if (b.dataset.act === 'pick') {
      const qi = Number(b.dataset.qi), q = a.questions[qi], label = q.options[Number(b.dataset.oi)].label, cur = picks[qi] || [];
      picks[qi] = q.multi ? (cur.includes(label) ? cur.filter((x) => x !== label) : [...cur, label]) : [label];
      PICKS.set(aid, picks);
      if (a.questions.length === 1 && !q.multi) { sendAnswer(store, a, picks); return; }
      store.touch('approvals');
      return;
    }
    sendAnswer(store, a, picks);
    return;
  }
  if (b.dataset.act === 'allow') store.decide(aid, 'allow');
  else if (b.dataset.act === 'deny') {
    const m = prompt('거부 이유를 적어 주세요. 모델에게 그대로 전달됩니다.', '사용자가 거부했습니다');
    if (m !== null) store.decide(aid, 'deny', m);
  } else if (b.dataset.act === 'open') openSession(Number(b.dataset.sid));
}

export function sessionKv(s, pend) {
  const t = s.tokens || {};
  return `<div class="small kv">
      <span>상태</span><span title="${esc(procTip(s))}">${procLabel(s)}</span>
      <span>지금</span><span>${s.activity && s.state === 'ACTIVE' ? `${esc(s.activity.tool)} ${esc(oneLine(s.activity.target, 120))} (${ago(s.activity.ts)})` : (s.state === 'ACTIVE' ? '생각 중' : STATE_LABEL[s.state])}</span>
      <span>서브에이전트</span><span>${s.subagents_running ? `${s.subagents_running}개 — ${esc((s.subagent_descs || []).join(', '))}` : '없음'}</span>
      <span>모델</span><span>${modelChip(s, pend) || '<span class="muted">아직 응답 없음</span>'}${s.model_req ? ` <span class="muted">· 띄울 때 고른 것 ${esc(s.model_req)}</span>` : ''}</span>
      <span>토큰</span><span><span title="입력(캐시 포함) — 대화가 이어질 때마다 앞 대화를 다시 읽는 몫(캐시)까지 더한 양입니다. 캐시는 싸게 매겨집니다.">입력(캐시 포함) ${tok(t.input)}</span> · 출력 ${tok(t.output)} · 오늘 입력 ${tok(t.today_input)} · 출력 ${tok(t.today_output)}<br><span class="muted" title="서브에이전트 토큰(추정) — 서브에이전트 기록에서 셈한 값이라 실제와 조금 다를 수 있습니다.">서브에이전트 입력 ${tok(t.subagent_input)} · 출력 ${tok(t.subagent_output)}(추정)</span></span>
      ${(t.by_model || []).length ? `<span>모델별</span><span>${byModelTable(t.by_model)}</span>` : ''}
    </div>`;
}
// 세션 정보 「상태」 칸(11-09) — 겉은 쉬운 말, pid · 상태 문자 · CC 상태 · tmux 창은 호버로
const PROC_KO = { R: '실행', S: '대기(잠듦)', D: '디스크 대기', T: '멈춤(Ctrl+Z)', Z: '좀비', I: '유휴' };
function procLabel(s) {
  if (!s.pid) return '꺼짐';
  if (s.proc === 'T') return '켜짐 · 멈춰 둠';
  return `켜짐 · ${s.cc_status === 'busy' ? '일하는 중' : s.cc_status ? '쉬는 중' : '상태 모름'}`;
}
function procTip(s) {
  if (!s.pid) return '꺼짐 — 이 세션의 프로세스가 없습니다.';
  return `상태 — 프로세스 ${s.pid} (${s.proc || '?'}${PROC_KO[s.proc] ? ' ' + PROC_KO[s.proc] : ''}) · CC ${s.cc_status || '?'}${s.tmux_pane ? ` · tmux 창 ${s.tmux_pane}` : ''}`;
}

// 모델(11-05) — 지금 쓰는 모델(마지막 응답). Opus는 비싸서 색으로 구분한다
// pend: /model을 보냈지만 아직 응답 모델이 안 바뀐 것({ model, label, queued }). button이면 눌러서 고르는 칸(패널 머리줄)
export function modelChip(s, pend, button) {
  if (!s.model && !pend && !button) return '';
  const now = s.model ? esc(s.model_label) : '모델';
  const to = pend ? ` → <b>${esc(pend.label)}</b>${pend.queued ? ' <span class="muted">(대기열)</span>' : ''}` : '';
  const tip = button
    ? `모델 — 눌러서 이 세션의 모델을 바꿉니다(/model). 지금 ${s.model ? esc(s.model) : '응답 없음'}${pend ? `, ${esc(pend.label)}(으)로 바꾸는 중` : ''}.`
    : `모델 — 이 세션이 마지막 응답에 쓴 모델입니다(${esc(s.model || '')}).`;
  return button
    ? `<button type="button" class="mdl mdl-btn f-${esc(s.model_family || '')}" data-mdl="1" data-tip="${tip}">${now}${to} ▾</button>`
    : `<span class="mdl f-${esc(s.model_family)}" title="${tip}">${now}${to}</span>`;
}
// 세션의 모델별 토큰 — 서브에이전트 · CC 내부 호출(제목 붙이기 등)도 각자의 모델로 들어간다
function byModelTable(rows) {
  return `<table class="bym small">${rows.map((m) => `<tr><td><span class="mdl f-${esc(m.family)}">${esc(m.label)}</span></td>
    <td class="n">출력 ${tok(m.output)}</td><td class="n muted">입력 ${tok(m.input)}</td><td class="n">오늘 출력 ${tok(m.today_output)}</td></tr>`).join('')}</table>`;
}

// 작업 중에 보낸 입력(대기열로 열린 턴에 끼어든 것, 11-05) — 내 글이면 내 말풍선으로, 서브에이전트 결과 · 완료 알림이면 곁가지로
function queuedHtml(x) {
  return (x.queued || []).map((q, i) => {
    const raw = promptText(q.text);
    const o = /^\s*(<task-notification|<agent-message|Another Claude session)/.test(q.text.replace(/^\s*<pasted_content[^>]*>\s*/, ''))
      ? (/<task-notification/.test(q.text) ? 'task_notification' : 'subagent_message') : 'human';
    const who = o === 'human' ? '나 · 작업 중에 보냄' : `${ORIGIN_LABEL[o]} · 작업 중에 옴`;
    return `<div class="msg in o-${o} o-queued"><div class="who small muted">${esc(who)} · ${clock(q.ts)}</div>${longText(`${x.id}q${i}`, raw)}</div>`;
  }).join('');
}
// 턴 끝 이유 — API 오류면 종류(분류기 거부 · 한도 · 과부하 …)를 글자로, 할 일 · request id는 호버(11-11, bridge/api_error.py)
export function endLabel(x) {
  const base = END_LABEL[x.end_reason] || x.end_reason;
  const e = x.end_reason === 'stop_failure' ? x.api_error : null;
  if (!e) return esc(base);
  const name = e.kind === 'unknown' ? base : `${base} — ${e.label}${e.detail ? ` [${e.detail}]` : ''}`;
  const tip = `${e.label} — ${e.action}.${e.reset ? ` ${e.reset}에 풀립니다.` : ''}${e.request_id ? ` 요청 번호는 ${e.request_id}입니다.` : ''}`;
  return `<span class="warn" title="${esc(tip)}">${esc(name)}</span>`;
}
export function convoHtml(c) {
  if (!c) return '';
  return (c.error ? `<p class="bad small">${esc(c.error)}</p>` : '') + (c.turns || []).map((x) => `
      <div class="msg in o-${esc(x.origin)}"><div class="who small muted">${esc(ORIGIN_LABEL[x.origin] || x.origin)} · ${clock(x.started_at)}</div>${longText(`${x.id}i`, promptText(x.prompt))}</div>${queuedHtml(x)}
      ${x.reply ? `<div class="msg out"><div class="who small muted">CC${x.end_reason ? ' · ' + endLabel(x) : ' · 진행 중'}${x.tools ? ` · 도구 ${x.tools}` : ''}${x.subagents ? ` · 서브 ${x.subagents}` : ''}</div>${
        x.mid && x.mid.length ? `<details class="mid"${OPEN_MSG.has(`${x.id}m`) ? ' open' : ''} data-mid="${x.id}m"><summary class="small muted">중간 글 ${x.mid.length}</summary>${x.mid.map((m, i) => `<div class="mid-one">${longText(`${x.id}m${i}`, m)}</div>`).join('')}</details>` : ''}${longText(`${x.id}o`, x.reply)}</div>`
        : (x.end_reason ? `<div class="msg out small muted">${endLabel(x)}${x.tools ? ` · 도구 ${x.tools}` : ''}</div>` : '')}`).join('') + (c.loading ? '<p class="small muted">불러오는 중…</p>' : '');
}

// 승인 이력(11-03) — 무엇이 몇 번 걸렸고 다 승인했는지. 늘 Yes만 누르는 규칙은 손볼 후보로 표시. <details>를 열 때만 읽는다
export function mountApprovalHistory(det, head, body, store) {
  let histDays = 1, histTimer = null;
  const OUT = { approved: ['승인', 'ok'], denied: ['거부', 'bad'], unknown: ['모름', 'muted'] };
  async function loadHist() {
    try {
      const r = await fetch(`/api/approvals/history?days=${histDays}`, { headers: store.headers() });
      if (!r.ok) { body.textContent = `불러오지 못함(${r.status})`; return; }
      const h = await r.json();
      const t = h.total;
      head.textContent = `— ${histDays === 1 ? '오늘' : histDays + '일'} ${t.n}건 · 승인 ${t.approved} · 거부 ${t.denied}${t.unknown ? ' · 답 확인 못 함 ' + t.unknown : ''}`;
      head.title = '답 확인 못 함 — 대화창에서 직접 답했거나 시간이 지나, 어떻게 됐는지 FOREMAN이 알 수 없는 것입니다.';
      const yes = h.by_rule.filter((b) => b.always_yes);
      const rules = h.by_rule.map((b) => `<tr${b.always_yes ? ' class="warn"' : ''}><td>${esc(b.rule)}</td><td>${b.n}</td><td>${b.approved}</td><td>${b.denied}</td><td>${b.unknown}</td><td>${b.always_yes ? '늘 허락함 — 묻지 않게 바꿀 후보' :''}</td></tr>`).join('');
      // 질문은 고른 답(DB message)까지 — 답한 질문 줄을 치운 뒤 다시 보는 곳(11-10)
      const items = h.items.slice(0, 30).map((x) => `<li><span class="${OUT[x.outcome][1]}">${x.tool === 'AskUserQuestion' ? (x.message ? '답함' : '질문') : OUT[x.outcome][0]}</span> <span class="muted">${ago(x.at)} · ${esc(x.project || '미분류')}${x.session_id ? ` · 세션 ${x.session_id}` : ''} · ${esc(x.rule)}</span> ${esc(oneLine(x.summary || '', 140))}${
        x.tool === 'AskUserQuestion' && x.message ? ` <b>→ ${esc(oneLine(x.message, 160))}</b>` : ''}</li>`).join('');
      const obs = h.observe.length ? `<div class="muted" title="묻지 않고 지켜보기만 한 것 — 관찰 모드인 규칙입니다. 승인 창을 띄우지 않고, 창을 띄웠다면 걸렸을 것만 셉니다.">묻지 않고 지켜보기만 한 것:${h.observe.map((o) => `${esc(o.project)} ${esc(o.rule)} ${o.n}`).join(' · ')}</div>` : '';
      body.innerHTML = `
        <div class="row"><button class="ghost small" data-days="1">오늘</button><button class="ghost small" data-days="7">7일</button><button class="ghost small" data-days="30">30일</button></div>
        ${yes.length ? `<div class="warn" title="늘 허락함 — 매번 허락한 규칙입니다. 묻지 않게 바꾸면 번거로움이 줄어듭니다(config/approval.toml).">늘 허락함: ${yes.map((b) => `${esc(b.rule)} ${b.n}번`).join(' · ')} — 묻는 의미가 없으면 규칙을 고칩니다</div>` : ''}
        ${rules ? `<table class="hist"><tr><th title="규칙 — 승인 창을 띄운 규칙의 이름입니다(config/approval.toml).">규칙</th><th>걸림</th><th>승인</th><th>거부</th><th>모름</th><th></th></tr>${rules}</table>` : '<div class="muted">걸린 것 없음</div>'}
        ${obs}<ul class="hist-items">${items}</ul>`;
    } catch (e) { body.textContent = '불러오지 못함'; }
  }
  det.addEventListener('toggle', () => {
    clearInterval(histTimer);
    if (det.open) { loadHist(); histTimer = setInterval(loadHist, 60000); }
  });
  body.addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-days]');
    if (b) { histDays = Number(b.dataset.days); loadHist(); }
  });
}

// 활동 줄 — 도구 줄을 누르면 그 호출의 입력 전체 · 결과 본문을 트랜스크립트에서 읽어 바로 아래 펼친다(11-05).
// 본문은 DB에 없다. 받은 것은 이 탭에만 둔다(FEED_DETAIL), 펼친 줄은 다시 그려도 펼친 채로(FEED_OPEN)
export const FEED_DETAIL = new Map();     // eid → {loading} | {error} | 응답
export const FEED_OPEN = new Set();
export function feedHtml(s) {
  return s.feed.slice().reverse().map((f) => {
    const open = f.eid && FEED_OPEN.has(f.eid);
    return `<div class="f f-${f.kind}${f.eid ? ' f-click' : ''}${open ? ' f-open' : ''}"${f.eid ? ` data-eid="${f.eid}" title="눌러서 입력 · 결과 보기"` : ''}><span class="muted">${new Date(f.ts).toLocaleTimeString()}</span> ${f.eid ? `<span class="f-tw">${open ? '▾' : '▸'}</span>` : ''}${esc(f.text)}</div>${open ? toolDetailHtml(FEED_DETAIL.get(f.eid)) : ''}`;
  }).join('') || '<p class="small muted">활동이 아직 없습니다.</p>';
}

function inputHtml(tool, inp) {
  if (inp == null) return '<div class="small muted">입력을 트랜스크립트에서 찾지 못했습니다.</div>';
  const pre = (t, cls = '') => `<pre class="fd-pre${cls}">${esc(t)}</pre>`;
  const kv = (k) => (inp[k] != null && inp[k] !== '' ? `<div class="small"><span class="muted">${esc(k)}</span> ${esc(String(inp[k]))}</div>` : '');
  switch (tool) {
    case 'Bash': return (inp.description ? `<div class="small muted">${esc(inp.description)}</div>` : '') + pre('$ ' + (inp.command || ''));
    case 'Read': return kv('file_path') + kv('offset') + kv('limit') + kv('pages');
    case 'Write': return kv('file_path') + pre(inp.content || '');
    case 'Edit': return kv('file_path') + (inp.replace_all ? '<div class="small muted">replace_all</div>' : '') +
      pre(String(inp.old_string || '').split('\n').map((l) => '- ' + l).join('\n'), ' fd-del') +
      pre(String(inp.new_string || '').split('\n').map((l) => '+ ' + l).join('\n'), ' fd-add');
    case 'Grep': case 'Glob': return kv('pattern') + kv('path') + kv('glob') + kv('output_mode');
    case 'WebFetch': return kv('url') + (inp.prompt ? pre(inp.prompt) : '');
    case 'WebSearch': return kv('query');
    case 'Agent': case 'Task': return kv('description') + kv('subagent_type') + (inp.prompt ? pre(inp.prompt) : '');
    default: return pre(JSON.stringify(inp, null, 2));
  }
}
export function toolDetailHtml(d) {
  if (!d || d.loading) return '<div class="fdet small muted">트랜스크립트에서 읽는 중…</div>';
  if (d.error) return `<div class="fdet small bad">못 읽음 — ${esc(d.error)}</div>`;
  const ex = d.extra || {};
  const res = d.result == null
    ? `<div class="small muted">${d.found && d.found.result ? '결과 글 없음' : '결과가 아직 없다(도는 중이거나 기록 전)'}</div>`
    : `<pre class="fd-pre fd-out${d.is_error ? ' fd-err' : ''}">${esc(d.result || '(빈 출력)')}</pre>`;
  return `<div class="fdet">
    <div class="fd-h small"><b>${esc(d.tool || '')}</b> 입력</div>${inputHtml(d.tool, d.input)}
    <div class="fd-h small"><b>결과</b>${d.is_error ? ' <span class="bad">오류</span>' : ''}${d.result_chars ? ` <span class="muted">${d.result_chars.toLocaleString()}자</span>` : ''}${
      ex.interrupted ? ' <span class="warn">중단됨</span>' : ''}${ex.backgroundTaskId ? ` <span class="muted">백그라운드 ${esc(ex.backgroundTaskId)}</span>` : ''}${
      ex.file ? ` <span class="muted">${esc(ex.file.filePath || '')} ${ex.file.startLine || 1}~ (${ex.file.numLines || '?'}/${ex.file.totalLines || '?'}줄)</span>` : ''}${
      d.other_blocks && d.other_blocks.length ? ` <span class="muted">+${esc(d.other_blocks.join(', '))}</span>` : ''}</div>
    ${res}${ex.stderr ? `<div class="fd-h small bad">stderr</div><pre class="fd-pre fd-err">${esc(ex.stderr)}</pre>` : ''}
    <div class="small muted">${esc(d.file || '')} · ${d.ms}ms · 비밀값은 가림</div></div>`;
}

// ── 8단계 파이프라인 — 프로젝트마다 인프라 캐릭터와 최근 체인(커밋 → Jenkins → Harbor → ArgoCD), 깨진 곳은 붉게 ──
const PIPE_STAGES = [['jenkins', 'Jenkins'], ['harbor', 'Harbor'], ['argocd', 'ArgoCD']];
const PIPE_MARK = { success: '✓', failed: '✗', running: '…', waiting: '⏸ ArgoCD Sync 대기', stale: '– 나중 배포로 대체' };   // waiting — 수동 Sync 앱, 실패 아님(11-03). stale — 끝 알림 없이 남았던 것(11-05)
const INFRA_LABEL = { IDLE: '응답', ACTIVE: '일하는 중', STALE: '응답 없음' };
export function pipeBlock(pp) {
  if (!pp) return '';
  const infra = pp.infra.filter((c) => !c.retired);
  if (!infra.length && !pp.chains.length && !pp.waiting.length && !pp.watch && !pp.webhook_broken) return '';
  // 빠진 알림 찾기(11-03): push 뒤 시작 알림이 없으면 3분에 노란색, 17분에 빨간색(텔레그램도)
  const w = pp.watch;
  const watch = w && w.state !== 'ok'
    ? `<div class="small ${w.state === 'missing' ? 'bad' : 'warn'}"${w.state === 'missing' ? '' : ' title="빌드 시작 알림 없음 — Jenkins가 push 알림(웹훅)을 못 받은 것 같습니다. 몇 분마다 저장소를 직접 확인하는 폴링이 대신 빌드를 시작하길 기다립니다."'}>${w.state === 'missing' ? '빌드 알림 없음 — Jenkins 확인' : '빌드 시작 알림 없음 — Jenkins가 스스로 확인하길 기다리는 중'}: push <code class="sha">${esc(w.short)}</code> ${esc(oneLine(w.subject || '', 60))} · ${ago(w.since)}</div>`
    : (w ? `<div class="small muted">빌드 기다리는 중: push <code class="sha">${esc(w.short)}</code> · ${ago(w.since)}</div>` : '');
  const hook = pp.webhook_broken ? '<div class="small bad" title="빌드 알림 끊김 의심 — push 때 Jenkins로 가는 알림(웹훅)이 끊긴 것 같습니다. 최근 빌드가 웹훅이 아니라 폴링(주기적 확인)으로 시작했습니다.">빌드 알림 끊김 의심 — 최근 빌드가 늦게 시작했습니다</div>' : '';
  const chips = infra.map((c) => `<span class="pill infra ${c.status === 'STALE' ? 'warn' : ''}" title="${esc(INFRA_LABEL[c.status] || c.status)} · 마지막 응답 ${esc(ago(c.last_seen_at))}">${esc(c.name)}${c.status === 'STALE' ? ' ⚠' : ''}</span>`).join('');
  const who = (c) => c.title || c.character || (c.session_id ? '세션' : '사람');
  const chains = pp.chains.slice(0, 4).map((ch) => {
    const commits = ch.commits.length ? ch.commits : [{ short: ch.short, subject: '' }];
    const head = commits.find((c) => c.sha === ch.head) || commits[0];
    const extra = commits.length > 1 ? ` <span class="muted">+${commits.length - 1}커밋</span>` : '';
    const skip = ch.stages.jenkins && ch.stages.jenkins.skipped;   // 문서만 바뀐 빌드(11-09) — 이미지 · 배포 없음이 정상
    const steps = PIPE_STAGES.map(([k, label]) => {
      const x = ch.stages[k];
      if (!x && skip && k !== 'jenkins') return `<span class="ps ps-none muted" title="${esc(label)} 건너뜀 — 문서만 바뀐 빌드라 이미지 · 배포를 하지 않았습니다. 정상입니다.">${label} –</span>`;
      const cls = x ? `ps-${x.status}` : 'ps-none';
      const tip = x ? `${label} ${x.status}${x.step ? ' · ' + x.step : ''}${x.status === 'waiting' ? '\nArgoCD Sync 대기 — 수동 Sync 앱이라 ArgoCD 화면에서 Sync를 눌러야 올라갑니다. FOREMAN에는 누를 곳이 없습니다. 누르면 ArgoCD가 열립니다.' : ''}${x.message ? '\n' + x.message : ''}` : `${label} 아직`;
      const inner = `${label} ${x ? PIPE_MARK[x.status] || '' : '·'}${x && x.step && x.status === 'failed' ? ` <b>${esc(x.step)}</b>` : ''}`;
      return x && x.url ? `<a class="ps ${cls}" href="${esc(x.url)}" target="_blank" rel="noopener" title="${esc(tip)}">${inner}</a>`
        : `<span class="ps ${cls}" title="${esc(tip)}">${inner}</span>`;
    }).join('<span class="ps-arrow">→</span>');
    return `<div class="chain ${ch.broke ? 'broke' : ''}" title="${esc(commits.map((c) => `${c.short} ${c.subject || ''} — ${who(c)}`).join('\n'))}">
      <div class="chain-commit small"><code class="sha">${esc(head.short)}</code> ${esc(oneLine(head.subject || '', 60))}${extra} <span class="muted">· ${esc(who(head))} · ${ago(ch.at)}</span></div>
      <div class="chain-steps small">${steps}</div>
      ${ch.broke ? `<div class="small bad">여기서 깨짐: ${esc(PIPE_STAGES.find(([k]) => k === ch.broke)[1])}${ch.stages[ch.broke].step ? ' · ' + esc(ch.stages[ch.broke].step) : ''}${ch.stages[ch.broke].message ? ' — ' + esc(oneLine(ch.stages[ch.broke].message, 140)) : ''}</div>` : ''}
    </div>`;
  }).join('');
  const waiting = pp.waiting.length ? `<div class="small muted">빌드 전 커밋: ${pp.waiting.map((w) => `<code class="sha">${esc(w.short)}</code>${w.pushed ? '' : '(push 전)'}`).join(' ')}</div>` : '';
  return `<div class="pipe"><div class="pipe-head small"><b>파이프라인</b> ${chips}</div>${hook}${watch}${waiting}${chains}</div>`;
}

export function createRenderer(root, store) {
  root.innerHTML = `
    <header class="top">
      <div class="brand">FOREMAN</div>
      <div id="summary" class="summary"></div>
      <a class="small" href="/" title="픽셀 화면(마지막에 본 테마)">픽셀 화면</a>
      <div id="conn" class="conn"></div>
      <button id="tokBtn" class="ghost" title="API 토큰">토큰</button>
    </header>
    <section id="approvals" class="approvals" aria-label="승인 대기"></section>
    <details id="apprHist" class="appr-hist"><summary class="small">승인 이력 <span id="apprHistHead" class="muted"></span></summary><div id="apprHistBody" class="small"></div></details>
    <main class="layout">
      <section id="grid" class="grid" aria-label="세션"></section>
      <aside id="panel" class="panel" aria-label="선택한 세션">
        <div class="panel-head"><button id="back" class="ghost back">← 목록</button><div id="panelHead"></div></div>
        <div id="panelBody" class="panel-body">
          <div id="panelInfo"></div>
          <h3>최근 대화</h3>
          <div id="convo" class="convo"></div>
          <h3>최근 활동</h3>
          <div id="feed" class="feed"></div>
        </div>
        <form id="inputForm" class="input">
          <textarea id="inputText" rows="3" placeholder="이 세션에 보낼 입력 — Ctrl+Enter로 보내기"></textarea>
          <div class="row">
            <label class="small"><input id="cmd" type="checkbox"> '/'를 슬래시 명령으로</label>
            <span id="inputWhy" class="small muted"></span>
            <button id="sendBtn" type="submit">보내기</button>
          </div>
          <div id="inputResult" class="small"></div>
        </form>
      </aside>
    </main>
    <div id="down" class="overlay" role="alert" aria-live="assertive"><div class="box">
      <h2>서버 연결 끊김</h2><p id="downWhy"></p><p id="downNext"></p>
      <button id="retryNow" class="primary">지금 다시 연결</button>
    </div></div>
    <div id="tokDlg" class="overlay"><form class="box" id="tokForm">
      <h2 class="plain">API 토큰</h2>
      <p class="muted small">.env.bridge의 FOREMAN_API_TOKEN 값입니다. 이 브라우저에만 저장합니다.</p>
      <input id="tokInput" type="password" autocomplete="new-password" placeholder="FOREMAN_API_TOKEN 값">
      <p><button type="submit" class="primary">연결</button> <span id="tokLen" class="small muted"></span></p>
    </form></div>`;

  const $ = (id) => root.querySelector('#' + id);
  const seen = { conn: -1, approvals: -1, grid: -1, panel: -1, pipe: -1 };
  let lastSel = undefined;

  // ── 동작 연결 ──────────────────────────────────────────
  $('grid').addEventListener('click', (ev) => {
    const card = ev.target.closest('[data-sid]');
    if (card) store.select(Number(card.dataset.sid));
  });
  $('grid').addEventListener('keydown', (ev) => {
    const card = ev.target.closest('[data-sid]');
    if (card && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); store.select(Number(card.dataset.sid)); }
  });
  $('back').onclick = () => store.select(null);
  $('approvals').addEventListener('click', (ev) => handleApprovalClick(ev, store, (sid) => store.select(sid)));
  $('approvals').addEventListener('input', handleApprovalInput);
  mountApprovalHistory($('apprHist'), $('apprHistHead'), $('apprHistBody'), store);
  $('inputForm').onsubmit = async (ev) => {
    ev.preventDefault();
    const id = store.state.selected, text = $('inputText').value;
    if (!id || !text.trim()) return;
    $('sendBtn').disabled = true;
    const r = await store.sendInput(id, text, $('cmd').checked);
    $('sendBtn').disabled = false;
    if (r.ok) $('inputText').value = '';
  };
  $('inputText').addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) $('inputForm').requestSubmit(); });
  $('retryNow').onclick = () => store.retryNow();
  $('tokBtn').onclick = () => { $('tokDlg').classList.add('on'); $('tokInput').focus(); };
  $('tokInput').oninput = () => { const n = $('tokInput').value.trim().replace(/^FOREMAN_API_TOKEN=/, '').length; $('tokLen').textContent = n ? `길이 ${n}` : ''; };
  $('tokForm').onsubmit = (ev) => {
    ev.preventDefault();
    store.token = $('tokInput').value;
    $('tokInput').value = '';
    $('tokDlg').classList.remove('on');
    store.start();
  };

  // ── 영역별 그리기 ───────────────────────────────────────
  function drawConn(st) {
    const c = st.conn;
    const label = { idle: '연결 전', connecting: '연결 중…', up: '연결됨', down: '끊김', auth: '토큰 확인 필요' }[c.status];
    $('conn').className = 'conn ' + c.status;
    $('conn').textContent = label;
    const down = c.status === 'down';
    $('down').classList.toggle('on', down);
    if (down) {
      $('downWhy').textContent = `${c.reason || '브리지와 연락이 없습니다'} — ${new Date(c.since).toLocaleTimeString()}부터`;
      $('downNext').textContent = c.nextIn ? `${c.nextIn}초 뒤 다시 연결 (시도 ${c.attempt})` : `연결 중… (시도 ${c.attempt})`;
    }
    if (c.status === 'auth') $('tokDlg').classList.add('on');
  }

  function drawSummary(st) {
    let active = 0, live = 0, outToday = 0, subs = 0;
    for (const s of st.sessions.values()) {
      if (s.state === 'ACTIVE') active++;
      if (s.state !== 'DORMANT') live++;
      outToday += s.tokens ? s.tokens.today_output : 0;
      subs += s.subagents_running || 0;
    }
    const pending = [...st.approvals.values()].filter((a) => a.status === 'pending').length;
    // 적재(수집기)가 막히면 맨 앞에 — 이 화면이 보여 주는 기록 자체가 멈춘 것이다(11-03)
    const ig = st.ingest;
    const ingest = !ig ? '' : (ig.stalled ? `<span class="bad" title="트랜스크립트 감시가 ${ig.tick_age_s}초째 멈춰 있습니다">⚠ 와처 멈춤</span>`
      : (ig.stuck && ig.stuck.length ? `<span class="bad" title="${esc(ig.stuck.map((x) => `${x.session} ${x.minutes}분 · ${x.failures}번 — ${x.error}`).join('\n'))}">⚠ 적재 막힘 ${ig.stuck.length}개 세션 · ${Math.max(...ig.stuck.map((x) => x.minutes))}분</span>`
      : (ig.skips && ig.skips.length ? `<span class="warn" title="${esc(ig.skips.map((x) => `${x.session} ${x.kind === 'chunk' ? '덩어리' : '줄'} ${x.count} — ${x.reason}`).join('\n'))}">적재 중 버린 줄 있음(24시간)</span>` : '')));
    $('summary').innerHTML = ingest +
      `<span>작업 중 <b>${active}</b>/${live}</span>` +
      (subs ? `<span>서브에이전트 <b>${subs}</b></span>` : '') +
      (pending ? `<span class="warn">승인 대기 <b>${pending}</b></span>` : '') +
      `<span class="muted">오늘 출력 ${tok(outToday)}</span>`;
  }

  let lastApprHtml = '';
  function drawApprovals(st) {
    const list = [...st.approvals.values()].sort((a, b) => a.id - b.id);
    // 클래식은 모든 세션을 한 곳에서 보는 확인 페이지라 답 카드를 다 띄운다. 답한 것은 한 줄로 접는다(11-10)
    const html = list.map((a) => (a.status === 'pending' ? approvalCard(a, st) : apprFoldLine(a, st))).join('');
    if (lastApprHtml !== html) { lastApprHtml = html; $('approvals').innerHTML = html; restoreNotes($('approvals')); }
  }

  function card(s, st) {
    const a = s.activity;
    const pend = [...st.approvals.values()].filter((x) => x.session_id === s.id && x.status === 'pending').length;
    const doing = s.state === 'ACTIVE' && a ? `<div class="doing"><b>${esc(a.tool)}</b>${a.subagent ? ' <span class="muted">(서브)</span>' : ''} ${esc(oneLine(a.target, 90))} <span class="muted small">${ago(a.ts)}</span></div>` : '';
    const stuck = stuckTurn(s);
    const turn = s.open_turn ? `<div class="turn small${stuck ? ' warn' : ''}">${stuck ? '⚠ 끝났는지 모름' : '▶'} ${esc(ORIGIN_LABEL[s.open_turn.origin] || '')} ${esc(oneLine(s.open_turn.prompt || '', 80))} <span class="muted">${since(s.open_turn.started_at)}</span></div>` : '';
    const reply = s.replyPreview && s.state === 'ACTIVE' ? `<div class="reply small">${esc(oneLine(s.replyPreview, 100))}</div>` : '';
    return `<article class="card st-${s.state}${st.selected === s.id ? ' sel' : ''}" data-sid="${s.id}" tabindex="0" aria-label="${esc(sessionName(s))} ${STATE_LABEL[s.state]}">
      <div class="card-top">
        <span class="badge st-${s.state}">${s.state}</span>
        ${roleBadge(s)}<b class="title" title="${esc(sessionName(s))}">${esc(sessionName(s))}</b>
        <span class="right small muted">${s.state === 'DORMANT' ? ago(s.last_ts) : STATE_LABEL[s.state]}</span>
      </div>
      <div class="sub small muted" title="${esc(sessionIds(s))}">${esc(sessionSub(s))}</div>
      ${turn}${doing}${reply}
      <div class="meta small">
        ${s.subagents_running ? `<span class="pill">서브에이전트 ${s.subagents_running}</span>` : ''}
        ${pend ? `<span class="pill warn">승인 대기 ${pend}</span>` : ''}
        <span class="muted">출력 ${tok(s.tokens.output)} · 오늘 ${tok(s.tokens.today_output)}</span>
      </div>
    </article>`;
  }

  function drawGrid(st) {
    const html = st.projects.map((p) => {
      const ss = p.sessionIds.map((id) => st.sessions.get(id)).filter(Boolean);
      const live = ss.filter((s) => s.state !== 'DORMANT');
      const dormant = ss.filter((s) => s.state === 'DORMANT');
      return `<section class="proj">
        <h2>${esc(p.label)} <span class="muted small">${live.length}개 살아 있음</span></h2>
        ${pipeBlock(st.pipeline.get(p.name))}
        ${live.map((s) => card(s, st)).join('')}
        ${dormant.length ? `<details class="dormant"${keep(`classic:${p.name}:dormant`)}><summary class="small muted">종료된 세션 ${dormant.length}개</summary>${dormant.map((s) => card(s, st)).join('')}</details>` : ''}
      </section>`;
    }).join('');
    const open = new Set([...$('grid').querySelectorAll('details[open]')].map((d) => d.parentElement.querySelector('h2').textContent));
    $('grid').innerHTML = html + (st.hiddenDormant ? `<p class="small muted">48시간 넘게 활동 없는 세션 ${st.hiddenDormant}개는 숨김</p>` : '');
    for (const d of $('grid').querySelectorAll('details')) if (open.has(d.parentElement.querySelector('h2').textContent)) d.open = true;
  }

  function drawPanel(st) {
    const s = st.selected != null ? st.sessions.get(st.selected) : null;
    root.classList.toggle('has-sel', !!s);
    if (!s) {
      $('panelHead').innerHTML = '<span class="muted">세션을 고르세요</span>';
      $('panelInfo').innerHTML = ''; $('convo').innerHTML = ''; $('feed').innerHTML = '';
      $('inputForm').hidden = true;
      return;
    }
    $('panelHead').innerHTML = `<span class="badge st-${s.state}">${s.state}</span> ${roleBadge(s)} <b>${esc(sessionName(s))}</b><div class="muted small" title="${esc(sessionIds(s))}">${esc([sessionSub(s), (s.cwd || '').replace(/^\/home\/[^/]+/, '~')].filter(Boolean).join(' · '))}</div>`;
    $('panelInfo').innerHTML = sessionKv(s);
    const convo = $('convo');
    const atBottom = convo.scrollHeight - convo.scrollTop - convo.clientHeight < 40 || lastSel !== s.id;
    convo.innerHTML = convoHtml(st.convo.get(s.id));
    if (atBottom) convo.scrollTop = convo.scrollHeight;
    $('feed').innerHTML = feedHtml(s);
    $('inputForm').hidden = false;
    const blocked = !s.injectable;
    $('inputText').disabled = blocked; $('sendBtn').disabled = blocked;
    $('inputWhy').textContent = blocked ? `보낼 수 없음 — ${why(s)}` : (s.state === 'ACTIVE' ? '작업 중 — 끝나면 전달' : '');
    const li = st.lastInput && st.lastInput.sessionId === s.id ? st.lastInput : null;
    $('inputResult').innerHTML = li ? `<span class="${li.ok ? 'ok' : 'bad'}">${esc(li.msg)}${li.guarded ? ' (첫 글자 보호)' : ''}</span>` : '';
    if (lastSel !== s.id) { $('inputText').value = ''; lastSel = s.id; }
  }

  store.subscribe((st) => {
    if (seen.conn !== st.ver.conn) { seen.conn = st.ver.conn; drawConn(st); }
    if (seen.approvals !== st.ver.approvals) { seen.approvals = st.ver.approvals; drawApprovals(st); }
    if (seen.grid !== st.ver.grid || seen.pipe !== st.ver.pipe) {
      seen.grid = st.ver.grid; seen.pipe = st.ver.pipe; drawGrid(st); drawSummary(st);
    }
    if (seen.panel !== st.ver.panel) { seen.panel = st.ver.panel; drawPanel(st); }
  });
  // "n초 전" · "n분째" 같은 시간 표시만 갱신
  setInterval(() => store.touch('grid', 'panel'), 10000);
}
