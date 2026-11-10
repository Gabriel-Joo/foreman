// FOREMAN 픽셀 오피스 — 테마 렌더러(10단계). store.js(데이터)는 그대로, 이 파일은 그리기만.
// 10a: 지도 ↔ 방 줌, 도형 캐릭터, 상태별 모습, 방 배지(작업 · 승인 · 파이프라인 · 토큰). 동작은 theme.json이 정한다(theme.js).
// 좌표: 월드는 타일 단위로 정하고 px = 타일 × layout.tile. 카메라가 월드 → 화면.

import { resolveAction, infraAction, groupSubagents, tokenRate, viewState } from './theme.js';
import { loadSprites } from './sprites.js';
import { createSidePanel } from './opanel.js';
import { mountNewSession } from './newsession.js';
import { mountTodoInbox } from './todoinbox.js';
import { coderJobs, coderBubble, isCoder, REST_DAYS } from './coder.js';
import { roleTag } from './render.js';
import { showTip, hideTip, themeTips, attachDomTips, textTip, softEsc, tipAudit as tipAuditOf } from './tip.js';
import { buildGrid, findPath, footprint, nearestFree, RES } from './walk.js';
import { uiScale } from './uiscale.js';
import { wrapWords } from './wrap.js';
import { applyGrid, INFRA_STAGES, gridProblems } from './grid.js';

// 픽셀 화면 글씨(화면 좌표로 그리는 것 — 구역 · 캐릭터 이름표, 말풍선, 방 카드, 단계 이름) 배율(11-09 사용자:
// "130%로 보는데 맨 윗줄 탭 글씨 정도면 좋겠다", [가+ · 가−]도 따라가게). 탭은 17px × 배율 — 이름표 14px × 배율 × 1.2가 그쯤.
// 1.2는 기본 배율이 아니라 이름표 ↔ 탭 글씨 비율이다 — 범위 · 처음 값은 uiscale.js STEPS · DEF 하나(11-10 80~110%, 처음 90%)
// 11-10 모눈: 방 하나를 볼 때 방 안 글씨(방 이름표 · 캐릭터 이름 · 말풍선)는 글씨 배율이 아니라 방 배율을 따른다(createOffice 안 tpx · labelFont).
// fpx는 경고 배너 · [전체] 카드 · 감독실 글씨에 남는다
const FZ = () => uiScale() * 1.2;
const fpx = (n) => Math.round(n * FZ());
const MIN_CARD = () => fpx(80);           // [전체] 현장 카드 최소 폭(px) — "FOREMAN" · "(떠돌이)"가 한 줄에 들어가는 폭(11-09)
const sizeFont = (f) => String(f).replace(/(\d+(?:\.\d+)?)px/, (m, n) => `${fpx(+n)}px`);

const KNOWN = [['runshoes', '런슈즈'], ['petmint-rag-chatbot', '펫퍼민트'], ['foreman', 'FOREMAN']];
const RATE_WIN = 10 * 60 * 1000;          // 토큰 속도 창 — 최근 10분
const SPEED = 3.2;                         // 걷는 속도(타일/초)
// 역할 고정 자리(11-09 관리자 · 11-10 디자이너) — 테마 layout.zones.<역할>.seats에 서고, 일할 때도 그 자리. 작업 책상 수 · "+N"에 들지 않는다
export const FIXED_SEAT_ROLES = ['manager', 'designer'];

export async function createOffice(root, store, themeUrl = '/static/themes/office/theme.json') {
  const theme = await (await fetch(themeUrl, { cache: 'no-cache' })).json();
  // 방 모눈(11-10) — 세 테마가 한 벌(themes/_shared/grid.json)을 쓴다. 방 칸 · 복도 · 출하 단계를 받고 방 안 좌표(in)를 방 좌표로
  if (theme.layout && theme.layout.grid) {
    const g = await (await fetch(new URL(theme.layout.grid, new URL(themeUrl, location.href)), { cache: 'no-cache' })).json();
    applyGrid(theme, g);
  }
  const L = theme.layout, T = L.tile, P = theme.palette;
  const GRIDDEF = theme.grid || null;
  // 10d: 시트 테마면 원본 PNG를 받아 둔다(자르기 · 외곽선 · 색조는 sprites.js). 도형 테마(office)는 그대로
  const SP = theme.sprites.kind === 'sheets' ? await loadSprites(theme, new URL(themeUrl, location.href)) : null;
  const CH = (SP && theme.sprites.chars) || {};

  root.innerHTML = `
    <header class="otop">
      <!-- 11-08 두 줄(사용자): 1줄 어디로 갈지 · 2줄 상태와 설정. 테마 이름 글은 뺐다(2줄 테마 버튼이 눌린 모양으로 보인다) -->
      <div class="otop-row">
        <span class="brand" title="FOREMAN — 지금 테마: ${esc(theme.label)}">FOREMAN</span>
        <button id="oMap" class="ghost" title="${esc((theme.hq && theme.hq.label) || '감독실')} — 현장 전체를 보는 감독실로 갑니다. Esc로도 갑니다.">⌂</button>
        <button id="oAll" class="ghost" title="전체 — 모든 현장을 한 화면에 봅니다.">전체</button>
        <nav id="oProj" class="oproj" aria-label="프로젝트"></nav>
        <button id="oNew" class="ghost onew" title="새 세션 — 프로젝트나 폴더를 골라 새 세션을 띄웁니다.">＋ 세션</button>
        <button id="oTodo" class="ghost onew" title="할 일 — 세션을 띄우지 않고 할 일을 적어 둡니다. 서기 정리로 주면 README 표로, 코더에게 주면 그 방 코더의 맡길 일로 갑니다.">＋ 할 일</button>
        <span id="oAlerts" class="oalerts"></span>
      </div>
      <div class="otop-row otop-sub">
        <span id="oStat" class="ostat"></span>
        <a id="oUsage" class="ghost ousage" href="/usage" data-tip="한도 — 구독 사용 한도입니다. 누르면 사용량 화면에서 어디서 나가는지 봅니다.">한도</a>
        <a id="oCredit" class="ghost ousage" href="/usage" hidden></a>
        <!-- 11-08 도형 · 클래식은 머리말에서 뺐다(사용자 — 안 쓴다). 주소 /?theme=plain · /classic으로는 그대로 열린다 -->
        <span class="otheme" role="group" aria-label="테마">${[['office', '오피스'], ['magic', '마법학교'], ['site', '현장']].map(([k, v]) => k === theme.name
          ? `<span class="oproj-b on" aria-current="true" title="${v} — 지금 테마입니다.">${v}</span>` : `<a class="oproj-b" href="/?theme=${k}" title="${v} — 이 테마로 바꿉니다.">${v}</a>`).join('')}</span>
        <span class="ofont" role="group" aria-label="글씨 크기"><button id="oFontDn" class="ghost" title="글씨 작게 — 머리말 · 옆 패널 · 터미널 글씨를 한 단계 줄입니다.">가−</button><span id="oFontV" class="muted"></span><button id="oFontUp" class="ghost" title="글씨 크게 — 머리말 · 옆 패널 · 터미널 글씨를 한 단계 키웁니다.">가+</button></span>
        <span id="oConn" class="conn"></span>
        <button id="oTok" class="ghost" title="접속 키 — 이 화면이 브리지에 접속할 때 쓰는 열쇠(API 토큰)를 다시 넣습니다.">접속 키</button>
      </div>
    </header>
    <div class="obody">
      <div id="oStage" class="ostage"><canvas id="oCv"></canvas>
        <div id="oDown" class="odown" role="alert" aria-live="assertive" hidden>
          <b>⚠ 서버 연결 끊김</b> <span id="oDownWhy" class="small"></span> <span id="oDownNext" class="small muted"></span>
          <button id="oRetry" class="small primary">지금 다시 연결</button>
          <div class="small muted">화면의 캐릭터는 끊기기 전 상태입니다. 다시 연결되면 맞춥니다.</div>
        </div>
      </div>
    </div>
    <div id="tokDlg" class="overlay"><form class="box" id="tokForm">
      <h2 class="plain">접속 키</h2>
      <p class="muted small">이 화면이 브리지에 접속할 때 쓰는 열쇠(API 토큰)입니다. .env.bridge의 FOREMAN_API_TOKEN 값을 넣습니다. 이 브라우저에만 저장합니다(클래식 화면과 같이 씁니다).</p>
      <input id="tokInput" type="password" autocomplete="new-password" placeholder="FOREMAN_API_TOKEN 값">
      <p><button type="submit" class="primary">연결</button> <button type="button" id="tokCancel" class="ghost">닫기</button> <span id="tokLen" class="small muted"></span></p>
    </form></div>`;
  const $ = (id) => root.querySelector('#' + id);
  const cv = $('oCv'), ctx = cv.getContext('2d');
  // 10b: 옆 패널(승인 · 대화 · 입력). 캔버스를 덮지 않고 옆에 붙는다 — 패널을 펴고 접으면 캔버스 크기가 바뀌고 카메라가 다시 맞춘다
  const panel = createSidePanel(root.querySelector('.obody'), store, { onSelectSession: (sid) => openSession(sid), onClear: () => { selected = null; } });

  // ── 상태 ───────────────────────────────────────────
  let world = { rooms: [], lounge: null, w: 0, h: 0 };
  const actors = new Map();            // key → actor
  // 서기 머리 위 "할 일 N"(12a) — 방(프로젝트) → {items:[{kind, title, why}]}. 브리지가 LLM 없이 센다(/api/scribe/todo)
  const scribeTodo = new Map();
  async function loadScribeTodo() {
    try {
      const r = await fetch('/api/scribe/todo', { headers: store.headers() });
      if (!r.ok) return;
      const j = await r.json();
      scribeTodo.clear();
      for (const [k, v] of Object.entries(j.projects || {})) scribeTodo.set(k, v);
    } catch { /* 못 읽으면 배지만 안 뜬다 */ }
  }
  loadScribeTodo();
  setInterval(loadScribeTodo, 60000);
  // 코더 상주(11-09) — 방 → {inbox(코더에게 받은 할 일), rested(쉬게 한 일)}. 나머지 맡길 일은 store 값으로 센다(coder.js coderJobs)
  const coderTodo = new Map();
  async function loadCoderTodo() {
    try {
      const r = await fetch('/api/coder/todo', { headers: store.headers() });
      if (!r.ok) return;
      const j = await r.json();
      coderTodo.clear();
      for (const [k, v] of Object.entries(j.projects || {})) coderTodo.set(k, v);
      rebuild(store.state);
    } catch { /* 못 읽으면 기계로 센 신호만 */ }
  }
  setTimeout(loadCoderTodo, 400);
  setInterval(loadCoderTodo, 60000);
  // 스키마 잠금(11-09 사용자 — "설계는 사람이 푼다인데 누를 곳이 없다") — 방 배너에 누가 · 언제부터 · 무엇으로, 막힌 세션, 일찍 푼 것.
  // 줄을 누르면 확인 창 뒤 [풀기](DELETE /api/schema-lock/{project})
  let schemaBoard = { locks: {}, released: {} }, lockTip = '';
  async function loadSchemaBoard() {
    try {
      const r = await fetch('/api/schema-lock/board', { headers: store.headers() });
      if (r.ok) schemaBoard = await r.json();
    } catch { /* 못 읽으면 줄이 안 뜬다 */ }
  }
  setTimeout(loadSchemaBoard, 600);
  setInterval(loadSchemaBoard, 30000);
  const hmOf = (iso) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? '' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
  function schemaLines(name) {
    const out = [], lk = schemaBoard.locks && schemaBoard.locks[name], rel = schemaBoard.released && schemaBoard.released[name];
    if (lk && lk.held) {
      const who = lk.session_id ? `세션 ${lk.session_id}` : `세션 ${lk.cc}`, where = lk.wt ? `worktree ${lk.wt}` : '원본 폴더';
      const b = lk.blocked;
      // 겉은 짧게(한 줄), 쥔 곳 · 무엇으로는 호버(BANNER_LOCK tip) — 11-09 두 줄로 넘쳐 방이 줄고 이름이 겹쳤다
      if (b) out.push([`🔒 멈춤 — ${b.session_id ? `세션 ${b.session_id}` : `세션 ${b.cc}`}이 스키마 잠금에 막혔습니다(쥔 ${who}) — 눌러서 풉니다`, P.warn, 'bold 15px', true, 'schemalock']);
      else out.push([`🔒 DB 구조 잠금 — ${who}이 ${hmOf(lk.since)}부터 쥐고 있습니다 — 눌러서 풉니다`, P.muted, '15px', true, 'schemalock']);
      lockTip = `스키마 잠금 풀기 — ${who}(${where})이 ${hmOf(lk.since)}부터 쥐고 있습니다(${lk.what || '?'}).${b ? ` 세션 ${b.session_id || b.cc}이 ${hmOf(b.at)}에 ${b.what || '?'}를 하려다 막혔습니다.` : ''} 쥔 세션이 스키마 일을 끝냈으면 누르고 확인해 풉니다.`;
    }
    if (rel && Date.now() - Date.parse(rel.at) < 10 * 60000) out.push([`🔓 잠금을 풀었습니다 — ${rel.why}`, P.ok || P.act, '15px', true]);
    return out;
  }
  // 감독실 캐릭터 = 디스패처의 얼굴(11-08). 세션은 없고, 디스패처가 하는 일이 여기 보인다:
  // 계획을 세우는 중(claude -p가 도는 동안) → 책상에서 일하는 동작, [시작]을 기다리는 자동 제안 → 머리 위 "제안 N"
  const FM_NAME = (theme.foreman && theme.foreman.name) || '감독';
  let fmState = { running: [], pending: [] };
  async function loadForeman() {
    try {
      const r = await fetch('/api/foreman/state', { headers: store.headers() });
      if (!r.ok) return;
      const j = await r.json();                 // 시연 재생은 대본의 "api"에 있으면 그 응답, 없으면 404(서 있기만)
      fmState = { running: Array.isArray(j.running) ? j.running : [], pending: Array.isArray(j.pending) ? j.pending : [] };
      rebuild(store.state);
    } catch { /* 못 읽으면 캐릭터가 서 있기만 한다 */ }
  }
  const fmOf = (room) => ({                      // room null = 감독실(전체)
    running: fmState.running.some((x) => room == null || x.project === room || x.project == null),
    pending: fmState.pending.filter((x) => room == null || x.project === room),
  });
  window.addEventListener('foreman-state', () => loadForeman());
  setTimeout(loadForeman, 500);
  setInterval(loadForeman, 60000);
  // 사용량(11-08, docs/15) — 머리 칩 "5h 42% · 주 91%", 지난 30분 환산액 상위 셋의 열기, 한도 90% 넘으면 현황판 경고등.
  // 못 읽으면 칩이 "⚠ 사용량"으로 바뀐다(조용히 옛 숫자를 보이지 않게)
  let usage = null;                              // /api/usage/brief
  const hotOf = new Map();                       // 세션 id → 달러/시간
  async function loadUsage() {
    try {
      const r = await fetch('/api/usage/brief', { headers: store.headers() });
      if (!r.ok) throw new Error(String(r.status));
      usage = await r.json();
    } catch (e) { usage = { failed: String(e.message || e) }; }
    hotOf.clear();
    for (const h of (usage && usage.hot) || []) hotOf.set(h.session_id, h.usd_h);
    usageChip();
  }
  let usageTipRows = { lines: [], why: '' };
  // 추가 사용(크레딧) 칩(11-09 사용자) — 판정은 CC가 한도에 닿을 때 남긴 글(서버 credit_signal): 막힘 · 이어 씀 · 모름.
  // 사람이 넣은 값(config/usage.toml [credits])은 넣은 지 3일 안일 때만 호버에 금액으로 — 지나면 숫자를 감추고 "확인 필요"
  function creditChip(cv) {
    const el = document.getElementById('oCredit');
    if (!el) return;
    el.hidden = !cv;
    if (!cv) return;
    const sig = cv.signal || {}, m = cv.manual;
    const usd = (v) => `US$${Number(v).toFixed(2).replace(/\.00$/, '')}`;
    const when = (iso) => {
      const d = new Date(iso), now = new Date(), hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      return d.toDateString() === now.toDateString() ? `오늘 ${hm}` : `${d.getMonth() + 1}월 ${d.getDate()}일 ${hm}`;
    };
    const money = m && cv.manual_fresh
      ? [`크레딧 ${usd(m.balance_usd)} · 월간 한도 ${m.monthly_cap_usd != null ? usd(m.monthly_cap_usd) : '없음'} 중 ${usd(m.monthly_used_usd)} 사용`,
        `자동 충전 ${m.auto_reload ? '켜짐' : '꺼짐'} — ${m.as_of} 직접 넣은 값(3일 지나면 감춤)`]
      : [m ? `직접 넣은 금액은 ${m.as_of || '날짜 없음'} 값이라 감췄습니다 — 설정 > 사용량에서 보고 고치면 3일 보입니다` : '금액은 FOREMAN이 읽을 수 없습니다(설정 > 사용량에만 있음)'];
    const seen = sig.at ? [`근거: ${when(sig.at)} CC가 남긴 글 — ${sig.text || ''}`] : [];
    let cls = 'ghost ousage', label, tip;
    if (sig.state === 'blocked') {
      cls += ' bad'; label = `⛔ 추가 사용 막힘 · ${when(sig.at)}`;
      tip = `추가 사용 막힘 — ${sig.why === 'spend' ? '월 지출 한도에 닿아 한도를 넘겨 이어 쓰지 못했습니다.' : '한도에 닿은 뒤 리셋까지 이어 쓴 응답이 없었습니다.'} 5시간 · 주간 한도에 닿으면 리셋까지 세션이 멈춥니다. 한도를 올렸다면 다음에 한도에 닿을 때 다시 판정합니다.`;
    } else if (sig.state === 'flowing') {
      cls += ' warn'; label = `추가 사용으로 이어 씀 · ${when(sig.since)}`;
      tip = '추가 사용으로 이어 씀 — 한도에 닿은 뒤에도 응답이 이어졌습니다. 크레딧이 나가고 있을 수 있습니다.';
    } else if (cv.blocked) {
      cls += ' bad'; label = '⛔ 추가 사용 막힘(넣은 값)';
      tip = '추가 사용 막힘 — 이번 달 한도에 닿은 적이 없어 직접 넣은 값으로 판정했습니다. 5시간 · 주간 한도에 닿으면 리셋까지 세션이 멈춥니다.';
    } else {
      label = '추가 사용 확인 필요';
      tip = '추가 사용 확인 필요 — 이번 달 한도에 닿은 적이 없어 크레딧으로 이어 쓸 수 있는지 아직 모릅니다. 처음 한도에 닿을 때 FOREMAN이 판정합니다.';
    }
    el.className = cls; el.textContent = label;
    el.dataset.tip = [tip, ...seen, ...money].join('\n');
  }
  const usagePct = (l) => (l.est_pct ?? l.measured_pct);
  const usageMax = () => Math.max(0, ...((usage && usage.limits) || []).map((l) => usagePct(l) ?? 0));
  function usageChip() {
    const el = document.getElementById('oUsage');
    if (!el || !usage) return;
    const ls = usage.limits || [], rd = usage.reading || {};
    // 11-09 "5h"를 몰랐다 — 5시간 · 주간, 추정이면 "약"
    const short = { session_5h: '5시간', weekly_all: '주간', weekly_fable: 'Fable 주간' };
    // 11-09 사용자 — "이 속도면 언제 바닥나나"(설정 화면의 "수요일 밤에 소진"). 리셋 전에 100%가 될 때만, 요일 · 시각으로
    const etaKo = (iso) => {
      const d = new Date(iso), now = new Date(), hh = String(d.getHours()).padStart(2, '0');
      return d.toDateString() === now.toDateString() ? `오늘 ${hh}:${String(d.getMinutes()).padStart(2, '0')}` : `${'일월화수목금토'[d.getDay()]} ${hh}시`;
    };
    const parts = ls.filter((l) => usagePct(l) != null && (l.key !== 'weekly_fable' || usagePct(l) >= 1))
      .map((l) => `${short[l.key] || l.label} ${(l.est_pct != null && l.measured_pct != null && Math.abs(l.est_pct - l.measured_pct) >= 0.5) ? '약 ' : ''}${Math.round(usagePct(l))}%`
        + (l.eta_before_reset && l.eta_100 ? ` · ${etaKo(l.eta_100)} 소진 예상` : ''));
    const bad = usage.failed || !rd.ok;
    const max = usageMax();
    el.className = 'ghost ousage' + (bad ? ' bad' : max >= 95 ? ' bad' : max >= 80 ? ' warn' : '');
    // 11-09 이름 나누기 — 계정 사용 한도는 "한도", 세션 대화가 창을 채운 비율은 패널 머리줄 "쌓인 대화 N%"(같은 %라 헷갈렸다)
    el.textContent = usage.failed ? '⚠ 한도' : (bad ? '⚠ ' : '') + (parts.length ? `한도: ${parts.join(' · ')}` : '한도');
    // 11-09 숫자 줄: "5시간 51% — 02:10 리셋" · "주간 5% — 11월 15일 22:00 리셋"(오늘이면 시각만)
    const resetKo = (iso) => {
      if (!iso) return '';
      const d = new Date(iso), now = new Date(), hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      return d.toDateString() === now.toDateString() ? hm : `${d.getMonth() + 1}월 ${d.getDate()}일 ${hm}`;
    };
    const lines = ls.filter((l) => l.key !== 'weekly_fable' || (usagePct(l) || 0) >= 1).map((l) =>
      `${short[l.key] || l.label} ${usagePct(l) == null ? '—' : Math.round(usagePct(l)) + '%'}${l.reset_at ? ` — ${resetKo(l.reset_at)} 리셋` : ''}${l.eta_before_reset ? ` (이 속도면 ${l.eta_100 ? resetKo(l.eta_100) + '에 ' : '리셋 전에 '}100%)` : ''}`);
    const why = usage.failed ? ` 지금은 불러오지 못했습니다(${usage.failed}).` : !rd.ok ? ` 지금은 /usage를 읽지 못하고 있습니다(${rd.error || '오래됐습니다'}).` : '';
    // 11-09 사용자 — /usage "What's contributing"(CC 추정: 대략 · 이 기기 세션만 · 비중끼리 겹침). 서브에이전트 · MCP 비중, 제안 줄
    const span = { '24h': '24시간', '7d': '7일' };
    const contrib = (usage.contributing || []).flatMap((b) => {
      const name = span[b.span] || b.span;
      const top = [b.subagents && `서브에이전트 ${b.subagents}`, b.mcp && `MCP ${b.mcp}`].filter(Boolean).join(' · ');
      return [top && `지난 ${name} — ${top}`, ...(b.span === '24h' ? b.tips.map((t) => `CC 제안 ${t.pct}% — ${t.text}`) : [])].filter(Boolean);
    });
    if (contrib.length) lines.push('CC가 본 비중 — 대략 · 이 기기 세션만 · 비중끼리 겹침(합이 100%가 아님)', ...contrib);
    usageTipRows = { lines, why };                     // 감독실 경고등 호버도 같은 줄을 쓴다(11-09)
    creditChip(usage.credits);
    el.dataset.tip =`한도 — 구독 사용 한도를 몇 % 썼는지입니다. 세션마다 쌓인 대화 %(패널 머리줄)와는 다릅니다. "약"은 마지막으로 읽은 뒤 FOREMAN이 더해 본 추정입니다. 누르면 어디서 나가는지 봅니다.${why}\n${lines.join('\n')}`;
  }
  if (new URLSearchParams(location.search).get('demo')) {   // 시연 재생은 /api를 막는다 — 칩을 숨긴다(⚠로 찍히지 않게)
    setTimeout(() => { for (const id of ['oUsage', 'oCredit']) { const el = document.getElementById(id); if (el) el.hidden = true; } }, 0);
  } else {
    setTimeout(loadUsage, 800);
    setInterval(loadUsage, 60000);                  // 읽기 사이 추정 %가 오르는 것 · 이벤트를 놓친 때
    window.addEventListener('foreman-usage', () => setTimeout(loadUsage, 300));   // 브리지가 /usage를 새로 읽은 순간
  }
  const tokHist = new Map();           // 방 이름 → [{t, v, o}]
  let lastSnap = null;
  let view = 'hq';                     // 'hq'(감독실, 1단) | 'map'(전체) | 방 이름(현장, 2단) | '_lounge'
  let selected = null;                 // actor key
  const cam = { x: 0, y: 0, s: 1 }, camT = { x: 0, y: 0, s: 1 };
  // 방 안 글씨(캐릭터 이름 · 말풍선, 11-10 모눈) — 방 배율을 따른다(사용자: "화면 안의 글씨도 그 배율을 따른다, 글씨 크기에 흔들리지 않게").
  // 배율 3에서 글씨 배율 기준(90%)과 같은 크기, 화면 9px 밑으로는 줄이지 않는다. 머리말 · 경고 배너 · [전체] 카드 · 감독실은 그대로 fpx(글씨 배율)
  const inRoom = () => view !== 'hq' && view !== 'map';
  const tpx = (n) => (inRoom() ? Math.max(9, Math.round(n * cam.s / 3)) : fpx(n));
  let W = 0, H = 0, dpr = 1, last = performance.now(), running = true;

  // ── 월드 만들기(store가 바뀔 때마다) ─────────────────
  function rooms(st) {
    const byName = new Map(st.projects.map((p) => [p.name, p]));
    const names = [...KNOWN.map(([n]) => n), ...st.projects.map((p) => p.name).filter((n) => n && !KNOWN.some(([k]) => k === n))];
    const out = [];
    names.forEach((name, i) => {
      const p = byName.get(name);
      const label = (p && p.label) || (KNOWN.find(([k]) => k === name) || [])[1] || name;
      out.push({ name, label, x: i * (L.room.w + L.gap), y: 0, w: L.room.w, h: L.room.h,
                 sessionIds: p ? p.sessionIds : [] });
    });
    const lp = byName.get(null);
    const lx = out.length * (L.room.w + L.gap);
    const lounge = { name: null, label: '라운지(떠돌이)', x: lx, y: 0, w: L.lounge.w, h: L.lounge.h,
                     sessionIds: lp ? lp.sessionIds : [], lounge: true };
    // 감독실(1단) — 현장들 위쪽에 따로 선 방. 벽의 현황판에 현장마다 표시(촛불 · 모니터 · 자석 — 테마가 정한다)
    const hs = (theme.hq && theme.hq.size) || { w: 28, h: 16 };
    const hq = { name: '_hq', label: (theme.hq && theme.hq.label) || '감독실', x: Math.max(0, (lx + L.lounge.w - hs.w) / 2),
                 y: -(hs.h + 8), w: hs.w, h: hs.h, hq: true };
    return { rooms: out, lounge, hq, w: lx + L.lounge.w, h: L.room.h };
  }

  // 구역 자리 — theme.json의 seats([x, y, 방향?] 목록) · stand(한 점). 자리보다 사람이 많으면 옆으로 조금씩 비켜 선다
  function zoneSeat(room, name, k) {
    const z = L.zones[name];
    if (!z) return null;
    if (z.seats && z.seats.length) {
      const s = z.seats[k % z.seats.length], extra = Math.floor(k / z.seats.length);
      return [room.x + s[0] + extra * 0.45, room.y + s[1] + extra * 0.2, s[2] || z.face];
    }
    if (z.stand) return [room.x + z.stand[0], room.y + z.stand[1], z.face];
    return null;
  }
  function seat(room, k) {
    if (room.lounge) {
      const z = L.zones.lounge_seats;
      return [room.x + z.x + (k % z.cols) * z.dx, room.y + z.y + Math.floor(k / z.cols) * z.dy + 1, 'down'];
    }
    const z = L.zones.desks;
    if (z.seats) return zoneSeat(room, 'desks', k);
    return [room.x + z.x + (k % z.cols) * z.dx + 1, room.y + z.y + Math.floor(k / z.cols) * z.dy + 2];
  }
  function seatCount(room) {
    const z = room.lounge ? L.zones.lounge_seats : L.zones.desks;
    return z.seats ? z.seats.length : z.cols * z.rows;
  }
  function spot(room, go, deskXY, k) {
    if (room.lounge || go === 'desk') return deskXY;
    return zoneSeat(room, go, k) || deskXY;
  }

  // ── 출하 라인 — 배송 담당 한 명(11-05) ─────────────────
  // 평소엔 라인 맨 앞 자기 자리. 새 빌드가 보이면 그 커밋을 한 세션 캐릭터가 걸어와 일감을 넘기고(6초), 배송 담당이
  // ① 빌드 → ② 이미지 → ③ 배포 중 지금 단계 앞으로 걸어간다. 끝나면(성공) 배포 앞에 잠깐 있다가 제자리, 실패면 그 단계에 30분.
  // 한 방에 빌드가 여럿이면 가장 오래된 진행 중인 것을 맡고 나머지는 자기 자리 옆 "대기 n". 방마다 따로.
  const COURIER = { seen: new Set(), primed: false, handoff: new Map(), timers: new Map() };
  const HANDOFF_MS = 6000, DONE_LINGER_MS = 25000, FAIL_STAY_MS = 30 * 60000;
  function chainStage(ch) {
    const s = ch.stages || {}, j = s.jenkins || {}, a = s.argocd || {};
    const pushy = /push|harbor|이미지/i.test(j.step || '');
    if (a.status === 'running' || a.status === 'waiting') return { k: 'argocd', st: a.status, active: true };
    if (a.status === 'failed') return { k: 'argocd', st: 'failed', end: Date.parse(a.ended_at || ch.at) };
    if (a.status === 'success') return { k: 'argocd', st: 'success', end: Date.parse(a.ended_at || ch.at) };
    if (j.status === 'running') return { k: pushy ? 'harbor' : 'jenkins', st: 'running', active: true };
    if (j.status === 'failed') return { k: pushy ? 'harbor' : 'jenkins', st: 'failed', end: Date.parse(j.ended_at || ch.at) };
    // 문서만 바뀐 빌드(11-09, foremanNotify "skipped") — 이미지 · 배포가 없는 게 정상이다. 빌드에서 끝난다
    if (j.status === 'success' && j.skipped) return { k: 'jenkins', st: 'success', end: Date.parse(j.ended_at || ch.at) };
    if (j.status === 'success') {                          // 이미지가 올라갔고 배포를 기다린다 — 30분까지는 진행 중으로 본다
      const end = Date.parse(j.ended_at || ch.at);
      return Date.now() - end < FAIL_STAY_MS ? { k: 'harbor', st: 'running', active: true } : { k: 'harbor', st: 'success', end };
    }
    return null;
  }
  function courierPlan(room, pp) {
    const chains = (pp && pp.chains) || [], now = Date.now();
    for (const ch of chains) {
      if (COURIER.seen.has(ch.head)) continue;
      COURIER.seen.add(ch.head);
      const sid = ch.commits && ch.commits[0] && ch.commits[0].session_id;
      if (COURIER.primed && sid) {                         // 새 빌드 — 커밋한 세션이 일감을 넘기러 온다
        COURIER.handoff.set(room.name, { sid, until: now + HANDOFF_MS });
        laterRebuild(room.name, HANDOFF_MS + 50);
      }
    }
    const staged = chains.map((ch) => ({ ch, s: chainStage(ch) })).filter((x) => x.s);
    // 진행 중으로 보는 것 — 2시간 안에 시작했고, 더 새 빌드(chains는 최신이 앞)가 그 단계를 아직 끝내지 않은 것만.
    // 끝 알림이 영영 안 온 옛 행이 "배포 진행 중"으로 남아 담당을 붙잡던 것(11-05)을 화면에서도 막는다
    const STALE_MS = 2 * 3600000;
    const active = staged.filter((x, i) => {
      if (!x.s.active) return false;
      const st = (x.ch.stages || {})[x.s.k === 'harbor' ? 'jenkins' : x.s.k] || {};
      if (Date.now() - Date.parse(st.started_at || x.ch.at || 0) > STALE_MS) return false;
      return !staged.slice(0, i).some((y) => y.s.k === x.s.k && !y.s.active);
    });
    const ho = COURIER.handoff.get(room.name);
    const handing = ho && now < ho.until ? ho : null;
    let at = null, st = 'none', ch = null;
    if (active.length) { const x = active[active.length - 1]; at = x.s.k; st = x.s.st; ch = x.ch; }   // chains는 최신이 앞 — 가장 오래된 것
    else if (staged.length) {
      const x = staged[0];
      if (x.s.st === 'failed' && now - x.s.end < FAIL_STAY_MS) { at = x.s.k; st = 'failed'; ch = x.ch; laterRebuild(room.name, FAIL_STAY_MS - (now - x.s.end) + 50); }
      else if (x.s.st === 'success' && now - x.s.end < DONE_LINGER_MS) { at = x.s.k; st = 'success'; ch = x.ch; laterRebuild(room.name, DONE_LINGER_MS - (now - x.s.end) + 50); }
    }
    if (handing) at = null;                                // 일감을 받는 동안은 제자리
    return { at, st, ch, handing, queue: active.slice(0, -1).map((x) => x.ch) };
  }
  const STAGE_KO = { jenkins: '① 빌드', harbor: '② 이미지', argocd: '③ 배포' };
  function courierNow(p) {
    if (!p) return '쉬는 중';
    if (p.handing) return '일감 받는 중';
    if (!p.at) return '쉬는 중 — 진행 중인 빌드 없음';
    return `${STAGE_KO[p.at]} ${({ running: '진행 중', waiting: 'ArgoCD Sync 대기', success: '✓ 끝', failed: '✗ 실패' })[p.st] || ''}`;
  }
  function laterRebuild(key, ms) {
    clearTimeout(COURIER.timers.get(key));
    COURIER.timers.set(key, setTimeout(() => store.touch('grid'), Math.min(ms, 2 ** 31 - 1)));
  }
  // 출하 라인 전용 자리(11-05) — 구조물 바로 앞(발밑보다 아래)에 못 박은 칸. theme.layout.zones.infra.stands(방 좌표):
  // { jenkins:[x,y], harbor:[x,y], argocd:[x,y], home:[x,y] }. 그 칸엔 가구를 두지 않는다(window.office.audit()가 확인)
  const HANDOFF_DX = 1.3;
  function stageStand(room, k) {
    const z = L.zones.infra, s = z.stands && z.stands[k];
    return s ? [room.x + s[0], room.y + s[1]] : [room.x + z[k].x + 3, room.y + z.y + 2];
  }
  function courierHome(room) {
    const z = L.zones.infra, s = z.stands && z.stands.home;
    return s ? [room.x + s[0], room.y + s[1]] : [room.x + Math.max(0.8, z.jenkins.x - 0.6), room.y + z.y + 2.3];
  }

  // 코더 상주(11-09) — 상주 코더의 그림 · 색, 임시 일꾼의 비침(사용자 11-09 골랐다: 반투명 + "임시" 이름표)
  const CODER_HUE = 205, TEMP_ALPHA = 0.6;
  const coderChar = () => CH.coder || (CH.pool && CH.pool[0]) || null;
  const coderLast = new Map();          // 방 → 상주 코더의 몸을 쓰던 세션 캐릭터 키(끝나면 그 자리에서 걸어 돌아오게)

  const DORMANT_SHOW_MS = 3 * 60000;
  function dormantGone(s, roomName) {
    if (s.state !== 'DORMANT') return false;
    const end = Date.parse(s.detached_at || s.last_ts || 0) || 0;
    const left = end + DORMANT_SHOW_MS - Date.now();
    if (left > 0) laterRebuild('dormant:' + roomName + ':' + s.id, left + 100);   // 3분이 지나면 다시 그려 지운다
    return left <= 0;
  }

  function rebuild(st) {
    world = rooms(st);
    // 승인 대기와 질문(AskUserQuestion)은 따로 센다(11-09 사용자: 질문은 승인이 아니다). 둘 다 사람을 기다리니 경고는 같다
    const pending = new Map(), asking = new Map();
    for (const a of st.approvals.values()) {
      if (a.status !== 'pending' || a.session_id == null) continue;
      const m = a.tool === 'AskUserQuestion' ? asking : pending;
      m.set(a.session_id, (m.get(a.session_id) || 0) + 1);
    }
    const seen = new Set();
    for (const room of [...world.rooms, world.lounge]) {
      const plan = !room.lounge && L.zones.infra ? courierPlan(room, st.pipeline.get(room.name)) : null;
      room.courier = plan;
      // 세션 — 깨어 있는 것 먼저 자리를 준다. 자리가 모자라면 배지에 "+N"
      const ss = room.sessionIds.map((id) => st.sessions.get(id)).filter(Boolean);
      ss.sort((a, b) => (a.state === 'DORMANT') - (b.state === 'DORMANT') || a.id - b.id);
      const cap = seatCount(room);
      let scribeN = 0;                 // 이 방의 서기 세션 수 — 둘이면 두 번째는 다음 자리(같은 자리에 겹치지 않게, 11-06)
      // 관리자(11-09 사용자) — 감독실 안 옆자리(theme manager 구역)에 선다. 일할 때도 그 자리(도구 따라 구역으로 가지 않는다).
      // 작업 책상 수에 들지 않는다. 상주가 아니라 세션이 있을 때만 보인다.
      // 디자이너(11-10 사용자)도 같은 규칙 — 자리만 작업 책상 옆(theme designer 구역, 코더 책상과 나란히 · 책상 5자리와 따로)
      const fixedN = {};
      const mgrOf = (s) => { const r = roleOf(s); return !room.lounge && FIXED_SEAT_ROLES.includes(r) && !!(L.zones[r] && L.zones[r].seats) ? r : null; };
      // 코더 상주(11-09) — 방마다 코더가 늘 있다. 살아 있는 코더 세션 중 가장 먼저 뜬 것이 상주 코더의 몸을 쓰고(책상으로 걸어가 일하고
      // 끝나면 자리로 돌아온다), 둘째부터는 임시 일꾼(반투명 · "임시" 이름표, 세션이 끝나면 사라진다). 끝난 코더 세션은 남기지 않는다
      const homed = !room.lounge && !!(L.zones.coder_home && L.zones.coder_home.seat);
      const coderOf = (s) => homed && isCoder({ role: roleOf(s) });
      const liveCoders = ss.filter((s) => coderOf(s) && s.state !== 'DORMANT');
      const residentSid = liveCoders.length ? liveCoders[0].id : null;
      room.coders = liveCoders.length;
      // 끝난 세션(DORMANT)은 끝나고 3분 동안만 흐리게 자리에 남았다가 화면에서 사라진다(11-05 사용자 요청).
      // 패널 세션 목록의 "종료된 세션"에는 그대로 있다 — 거기서 골라 [새로 띄우기]. 멈춘 세션(SUSPENDED)은 그대로 보인다
      const shown = ss.filter((s) => !dormantGone(s, room.name));
      room.overflow = Math.max(0, shown.filter((s) => !mgrOf(s)).length - cap);
      room.stats = { ACTIVE: 0, IDLE: 0, SUSPENDED: 0, DORMANT: 0, pending: 0, question: 0, denied: 0, asks: 0, subs: 0, tin: 0, tout: 0, opus_out: 0, all_out: 0 };
      let slot = 0;
      ss.forEach((s) => {
        // 기다림(IDLE + 자식 일)은 작업으로 센다 — 현장이 "쉼"으로 보이면 돌고 있는 일을 놓친다(11-06)
        const vs = viewState(s) === 'WAITING' ? 'ACTIVE' : s.state;
        room.stats[vs] = (room.stats[vs] || 0) + 1;
        room.stats.pending += pending.get(s.id) || 0;
        room.stats.question += asking.get(s.id) || 0;
        // 11-09 사람이 해야 풀리는 대기(브리지 /api/dashboard denied · asks) — 쉼으로 세지 않고 따로
        if (s.state !== 'DORMANT' && s.denied) room.stats.denied += 1;          // 종료된 세션의 옛 물음은 세지 않는다
        else if (s.state !== 'DORMANT' && s.asks) room.stats.asks += 1;
        room.stats.subs += s.subagents_running || 0;
        room.stats.tin += (s.tokens && s.tokens.today_input) || 0;
        room.stats.tout += (s.tokens && s.tokens.today_output) || 0;
        // 모델별은 서브에이전트까지 센다(위 tout은 본 대화만) — 비율은 모델별 합끼리 낸다
        for (const m of (s.tokens && s.tokens.by_model) || []) {
          room.stats.all_out += m.today_output || 0;
          if (m.family === 'opus') room.stats.opus_out += m.today_output || 0;
        }
        if (dormantGone(s, room.name)) return;
        if (coderOf(s) && s.state === 'DORMANT') return;          // 코더 세션이 끝나면 상주 코더는 자리로, 임시 일꾼은 사라진다
        const mgr = mgrOf(s);
        const k = mgr ? 0 : slot++;
        if (!mgr && k >= cap) return;
        let act = resolveAction(theme, { state: viewState(s), role: roleOf(s), tool: s.activity && s.activity.tool, target: s.activity && s.activity.target,
                                         flags: { approval_pending: pending.has(s.id) || asking.has(s.id), stuck_turn: !!s.stuck_turn } });
        // 쉬는 모습은 사람마다 다르게(마법학교: 엎드려 자기 · 먹기 · 책) — 플래그가 덮은 동작은 그대로
        if (act.variants && !act.flag) act = { ...act, anim: act.variants[s.id % act.variants.length] };
        // 서기(12a) — 서기실 안에서만 움직인다. 일할 때 도구에 따라 쓰기(Edit · Write) · 서가(Read · Grep) · 대조대(Bash),
        // 쉬거나 기다릴 때는 쓰기 자리. 승인 대기 같은 플래그는 그대로 둔다
        let seatK = k;
        const sz = L.zones.scribe;
        if (roleOf(s) === 'scribe' && sz && !act.flag) {
          const vs = viewState(s);
          if (vs === 'ACTIVE') {
            const t = (s.activity && s.activity.tool) || '';
            seatK = /^(Read|Grep|Glob|WebFetch|WebSearch)$/.test(t) ? 1 : /^(Bash|Monitor)$/.test(t) ? 2 : 0;
            act = { ...act, go: 'scribe', anim: ['type', 'read', 'think'][seatK] };
          } else if (vs === 'IDLE' || vs === 'WAITING') {
            seatK = 0;
            act = { ...act, go: 'scribe', anim: vs === 'WAITING' ? 'wait' : 'read' };
            delete act.variants;
          }
          if (act.go === 'scribe') seatK = (seatK + scribeN++) % sz.seats.length;
        }
        if (mgr) {                     // 승인 대기 같은 플래그의 모습(손 들기)은 그대로, 자리만 그 역할 구역(감독실 · 작업 책상 옆)
          act = { ...act, go: mgr };
          seatK = fixedN[mgr] || 0;
          fixedN[mgr] = seatK + 1;
        }
        const desk = mgr ? null : seat(room, k);
        let [tx, ty, face] = spot(room, act.go, desk, act.go === 'scribe' || mgr ? seatK : k);
        if (plan && plan.handing && plan.handing.sid === s.id) {      // 새 빌드 — 배송 담당에게 일감을 넘기러 간다
          const [hx, hy] = courierHome(room);
          tx = hx + HANDOFF_DX; ty = hy; face = 'left';
          act = { ...act, anim: 'idle', handoff: true };
        }
        const key = 's:' + s.id;
        const resident = s.id === residentSid, temp = coderOf(s) && !resident;
        const char = resident ? coderChar() : CH.pool ? CH.pool[s.id % CH.pool.length] : null;
        if (temp && act.alpha == null) act = { ...act, alpha: TEMP_ALPHA };
        const born = !actors.has(key);
        upsert(key, { kind: 'session', room: room.name, tx, ty, face, act, desk, s, hue: resident ? CODER_HUE : hueOf(s.id), char, role: roleOf(s),
                      name: s.custom_title || s.title || s.cc_name || ('세션 ' + s.id), resident, temp, coders: liveCoders.length });
        // 상주 코더가 일을 받으면 자기 자리에서 책상으로 걸어간다(그 자리에서 나타나지 않게)
        const home = actors.get('k:' + room.name);
        if (born && resident && home) { const a = actors.get(key); a.x = home.x; a.y = home.y; }
        if (resident) coderLast.set(room.name, key);
        seen.add(key);
        // 서브에이전트 — 부모의 축소판. 10명까지 보이고 나머지는 +N(10c). 새로 생기면 원탁방 마법진에서 소환, 끝나면 연기
        const n = s.subagents_running || 0;
        const g = groupSubagents(s.subagent_descs || [], MINI_CAP);
        const shown = Math.min(n, MINI_CAP);
        for (let i = 0; i < shown; i++) {
          const mk = `m:${s.id}:${i}`;
          const born = !actors.has(mk);
          const from = born ? summonPoint(room, tx, ty) : null;
          upsert(mk, { kind: 'mini', room: room.name, parent: key, idx: i, of: shown, char, hue: hueOf(s.id), role: roleOf(s),
                       act: { anim: 'walk' }, name: g.shown[i] || g.label || '서브에이전트', tx: from ? from[0] : tx, ty: from ? from[1] : ty });
          if (born) {
            const a = actors.get(mk);
            a.x = from[0]; a.y = from[1]; a.bornAt = performance.now() + i * 180;   // 하나씩 차례로 나온다
            summons.push({ x: from[0], y: from[1], t0: a.bornAt });
          }
          seen.add(mk);
        }
        const self = actors.get(key);
        self.subHidden = Math.max(0, n - shown);
        self.subLabel = g.label;
      });
      if (!room.lounge) {
        // 감독실 캐릭터(팀장 · 교장 · 소장) — 디스패처의 얼굴. 세션은 없다. 방마다 있는 것은 같은 디스패처의 그 프로젝트 창구(11-08)
        const f = L.zones.foreman_office;
        const key = 'f:' + room.name, fs = fmOf(room.name);
        upsert(key, { kind: 'foreman', room: room.name, tx: room.x + f.seat[0], ty: room.y + f.seat[1], face: 'down',
                      act: fs.running ? { anim: 'type' } : { anim: 'stand' }, hue: 45, name: FM_NAME, char: CH.foreman || null,
                      role: 'foreman', fm: fs });
        seen.add(key);
        // 서기(12a) — 서기실에 늘 있다. 그 방에 살아 있는 서기 세션이 있으면 그 세션 캐릭터가 대신 선다(일 → 끝나면 다시 서기실)
        const sz = L.zones.scribe;
        if (sz && sz.seats && !ss.some((s) => roleOf(s) === 'scribe' && s.state !== 'DORMANT')) {
          const p = sz.seats[0], wkey = 'w:' + room.name;
          upsert(wkey, { kind: 'scribe', room: room.name, tx: room.x + p[0], ty: room.y + p[1], face: p[2] || 'down',
                         act: { anim: 'read', go: 'scribe' }, hue: 25, name: '서기', char: (CH.pool && CH.pool[3 % CH.pool.length]) || null,
                         role: 'scribe', todo: scribeTodo.get(room.name) || null });
          seen.add(wkey);
        }
        // 코더 상주(11-09) — 살아 있는 코더 세션이 없으면 자기 자리(theme coder_home)에서 그 테마의 쉬는 동작. 머리 위 "맡길 일 N"
        if (homed) {
          const jobs = coderJobs(room.name, coderTodo.get(room.name) || null, st);
          room.coderJobs = jobs;
          const ckey = 'k:' + room.name;
          if (!liveCoders.length) {
            const z = L.zones.coder_home, p = z.seat, bornK = !actors.has(ckey);
            upsert(ckey, { kind: 'coder', room: room.name, tx: room.x + p[0], ty: room.y + p[1], face: p[2] || 'down',
                           act: { anim: z.anim || 'idle', go: 'coder_home' }, hue: CODER_HUE, name: '코더', char: coderChar(), role: 'coder', jobs });
            // 방금 일을 마친 상주 코더 — 책상에서 자리로 걸어 돌아온다
            const last = coderLast.get(room.name), la = last && actors.get(last);
            if (bornK && la) { const a = actors.get(ckey); a.x = la.x; a.y = la.y; }
            coderLast.delete(room.name);
            seen.add(ckey);
          } else {
            const ra = actors.get('s:' + residentSid);
            if (ra) ra.jobs = jobs;
          }
        }
        // 출하 라인 — 단계 이름표의 상태는 배송 담당이 맡은 빌드(없으면 마지막 빌드) 것.
        // 단계마다 서 있던 Jenkins · Harbor · ArgoCD 캐릭터 대신 배송 담당 한 명이 돌아다닌다(11-05 사용자 요청)
        const pp = st.pipeline.get(room.name);
        room.pipe = pp || null;
        const chain = (plan && plan.ch) || (pp && pp.chains && pp.chains[0]);
        const stages = (chain && chain.stages) || {};
        for (const kind of ['jenkins', 'harbor', 'argocd']) {
          let status = stages[kind] && stages[kind].status;
          if (kind === 'harbor' && !status && stages.jenkins && stages.jenkins.skipped) status = 'none';   // 문서만 — 이미지 없음(정상)
          else if (kind === 'harbor' && !status && stages.jenkins) status = stages.jenkins.status === 'failed' && stages.jenkins.step !== '빌드·push' ? 'success' : stages.jenkins.status;
          room['st_' + kind] = status || 'none';
        }
        if (plan) {
          const z = L.zones.infra, key = `c:${room.name}`;
          const [hx, hy] = courierHome(room);
          const at = plan.at;
          const [tx, ty] = at ? stageStand(room, at) : [hx, hy];
          const c = theme.courier || {};
          upsert(key, { kind: 'courier', room: room.name, tx, ty, face: 'down',
                        char: c.char || (CH.infra && (CH.infra.courier || CH.infra.jenkins)) || null,
                        act: plan.handing ? { anim: 'idle', status: 'handoff' } : at ? infraAction(theme, plan.st) : { anim: 'idle', status: 'idle' },
                        hue: 30, name: c.name || '배송 담당', plan });
          seen.add(key);
        }
      }
    }
    // 감독실의 팀장(교장 · 소장) — 늘 자리에 있다. 어느 프로젝트든 계획을 세우면 일하고, 제안은 모두 센다
    const hz = (theme.hq && theme.hq.seat) || [14, 8.6], hs = fmOf(null);
    upsert('f:_hq', { kind: 'foreman', room: '_hq', tx: world.hq.x + hz[0], ty: world.hq.y + hz[1], face: 'down',
                      act: hs.running ? { anim: 'type' } : { anim: 'stand' }, hue: 45, name: FM_NAME, char: CH.foreman || null,
                      role: 'foreman', fm: hs });
    seen.add('f:_hq');
    for (const k of [...actors.keys()]) if (!seen.has(k)) vanish(k);
    if (selected && !actors.has(selected)) selected = null;
    // 토큰 이력 — 스냅샷이 새로 올 때마다 방별 누적(오늘)을 적는다
    if (st.generatedAt && st.generatedAt !== lastSnap) {
      lastSnap = st.generatedAt;
      const now = Date.now();
      for (const room of [...world.rooms, world.lounge]) {
        const k = room.name || '_lounge';
        const h = tokHist.get(k) || [];
        h.push({ t: now, v: room.stats.tin + room.stats.tout, o: room.stats.tout });
        while (h.length && now - h[0].t > RATE_WIN * 1.5) h.shift();
        tokHist.set(k, h);
      }
    }
    for (const room of [...world.rooms, world.lounge]) {
      const h = tokHist.get(room.name || '_lounge') || [];
      room.rate = tokenRate(h, Date.now(), RATE_WIN);
      room.rateOut = tokenRate(h.map((x) => ({ t: x.t, v: x.o })), Date.now(), RATE_WIN);
      room.rateSpan = h.length > 1 ? h[h.length - 1].t - h[0].t : 0;     // 화면을 연 지 얼마 안 되면 아직 잴 수 없다
    }
    if (view !== 'map' && view !== 'hq' && !world.rooms.concat(world.lounge).some((r) => (r.name || '_lounge') === view)) view = 'hq';
    aim();
    header(st);
    const sa = selected && actors.get(selected);
    if (sa && (sa.kind === 'infra' || sa.kind === 'courier')) info();          // 인프라 상태가 바뀌었으면 패널 제목 줄도 바꾼다(세션은 패널이 store를 직접 본다)
    COURIER.primed = true;                        // 첫 그리기 뒤부터 새로 보이는 빌드만 "일감 넘기기"
    if (store.state.selected == null && sa && (sa.kind === 'session' || sa.kind === 'mini')) selected = null;   // 패널에서 ✕
  }

  // 역할(로브 · 사원증 끈 · 안전모 색) — 세션의 role(DB character_session.role: foreman coder inspector cicd helper).
  // 11-05 전에는 테마 이름(lead builder …)이 DB와 달라 실제 세션 색이 한 번도 맞지 않았다. 미리 보기: /office?roles=demo
  const ROLES = (theme.roles && theme.roles.colors) || {};
  const ROLE_MODE = (theme.roles && theme.roles.mode) || 'robe';   // robe(옷 색) · lanyard(사원증 끈) · helmet(안전모)
  const DEMO_ROLES = new URLSearchParams(location.search).get('roles') === 'demo' ? Object.keys(ROLES) : null;
  function roleOf(s) { return s.role || (DEMO_ROLES && DEMO_ROLES.length ? DEMO_ROLES[s.id % DEMO_ROLES.length] : null); }
  // 역할이 없을 때의 색(현장: 노란 안전모), 포먼(감독)의 색 — 테마가 정한다. 없으면 표시 안 함
  function roleColor(role) {
    const R = theme.roles || {};
    if (role === 'foreman') return R.foreman || null;
    return (role && ROLES[role]) || R.default || null;
  }

  // 서브에이전트(10c) — 소환 자리: 그 방에 마법진(circle 구역)이 있으면 그 가운데, 없으면 부모 자리
  const MINI_CAP = 10;
  const MINI = theme.sprites.mini_scale || 0.6;
  const summons = [];
  function summonPoint(room, px, py) {
    const z = L.zones.circle || L.zones[(theme.spawn && theme.spawn.zone) || ''];
    if (!z || room.lounge) return [px, py];
    return [room.x + z.x + z.w / 2, room.y + z.y + z.h / 2];
  }
  // 작은 일꾼은 부모 둘레를 천천히 돈다 — 목표를 매 프레임 다시 정한다
  function miniTarget(a, now) {
    const p = actors.get(a.parent);
    if (!p) return [a.tx, a.ty];
    const ang = (a.idx / Math.max(1, a.of)) * Math.PI * 2 + now / 6000 + (a.idx % 2) * 0.4;
    const rx = 1.1 + 0.25 * (a.idx % 3), ry = 0.55;
    return [p.x + Math.cos(ang) * rx, p.y + 0.35 + Math.sin(ang) * ry];
  }

  // 사라지기 — 서브에이전트(작은 일꾼)는 연기로 흩어진다(10c). 나머지는 그냥 지운다
  const puffs = [];
  function vanish(k) {
    const a = actors.get(k);
    if (a && (a.kind === 'mini' || a.temp)) puffs.push({ x: a.x, y: a.y, t0: performance.now() });   // 임시 일꾼도 연기로(11-09)
    actors.delete(k);
  }

  function upsert(key, a) {
    const cur = actors.get(key);
    if (cur) { Object.assign(cur, a); return; }
    actors.set(key, { ...a, key, x: a.tx, y: a.ty, phase: Math.random() * 6 });
  }

  // ── 걷기(11-05) — 가구를 피해 ㅗ자 복도로. 방마다 배치가 같아 격자는 현장 방 하나 · 라운지 하나(방 안 좌표) ──
  const WALK_DEBUG = new URLSearchParams(location.search).get('walk') === '1';
  const CORRIDORS = L.corridors || [];
  function sizeT(d) { const [w, h] = SP.size(d.s); const sc = d.scale || 1; return [w * sc / T, h * sc / T]; }
  function obstacles() {
    const out = [];
    const add = (d, ox, oy) => {
      if (d.fx === 'glasswall') {
        // 유리벽 — 옆 · 아래 테두리만 벽, 아래 가운데에 문(서버룸처럼 안에 자리가 있다). 위는 원래 벽
        const x = ox + d.x, y = oy + d.y, w = d.w || 1, h = d.h || 1, door = d.door ?? 1.5, th = 0.35;
        out.push([x, y, th, h], [x + w - th, y, th, h],
                 [x, y + h - th, (w - door) / 2, th], [x + (w + door) / 2, y + h - th, (w - door) / 2, th]);
        return;
      }
      if (!d.s || d.fx || d.z === 'wall' || d.z === 'floor' || d.z === 'top') return;
      const [w, h] = sizeT(d);
      for (let i = 0; i < (d.n || 1); i++) {
        const f = footprint({ ...d, x: ox + d.x + i * (d.dx || 1), y: oy + d.y }, w, h);
        if (f) out.push(f);
      }
    };
    for (const d of theme.sprites.decor || []) add(d, 0, 0);
    const iz = L.zones.infra;
    for (const kind of ['jenkins', 'harbor', 'argocd']) for (const d of (theme.sprites.infra_decor || {})[kind] || []) add(d, iz[kind].x, iz.y);
    return out;
  }
  // 라운지는 의자(앉는 자리)뿐이라 막을 가구가 없다 — 벽만
  const GRID = SP ? { room: buildGrid(L.room.w, L.room.h, obstacles(), CORRIDORS), lounge: buildGrid(L.lounge.w, L.lounge.h, []) } : null;
  function roomOf(a) {
    if (a.room === '_hq') return null;
    return a.room == null ? world.lounge : world.rooms.find((r) => r.name === a.room);
  }
  // 목표가 바뀌면 길을 새로 찾는다(월드 좌표 점 목록). 작은 일꾼(서브에이전트)은 부모 둘레를 날아다녀 길을 찾지 않는다
  function routeOf(a) {
    const key = a.tx + ',' + a.ty;
    if (a.routeKey === key) return a.route;
    a.routeKey = key;
    const r = GRID && a.kind !== 'mini' ? roomOf(a) : null;
    if (!r) { a.route = [[a.tx, a.ty]]; return a.route; }
    const g = r.lounge ? GRID.lounge : GRID.room;
    a.route = findPath(g, a.x - r.x, a.y - r.y, a.tx - r.x, a.ty - r.y).map(([x, y]) => [x + r.x, y + r.y]);
    return a.route;
  }
  function drawWalkDebug() {
    if (!WALK_DEBUG || !GRID) return;
    for (const r of [...world.rooms, world.lounge]) {
      if (!r) continue;
      const g = r.lounge ? GRID.lounge : GRID.room;
      for (let i = 0; i < g.cols * g.rows; i++) {
        const c = i % g.cols, rr = Math.floor(i / g.cols);
        if (g.block[i]) ctx.fillStyle = '#ff303055';
        else if (g.cost[i] <= 1) ctx.fillStyle = '#30a0ff33';
        else continue;
        ctx.fillRect((r.x + c / RES) * T, (r.y + rr / RES) * T, T / RES, T / RES);
      }
    }
    ctx.strokeStyle = '#ffee00'; ctx.lineWidth = 1;
    for (const a of actors.values()) {
      if (!a.route || a.kind === 'mini') continue;
      ctx.beginPath(); ctx.moveTo(a.x * T, a.y * T);
      for (const [x, y] of a.route) ctx.lineTo(x * T, y * T);
      ctx.stroke();
    }
  }

  // ── 카메라 ──────────────────────────────────────────
  function roomByView() { return [...world.rooms, world.lounge].find((r) => (r.name || '_lounge') === view); }
  // 한 방(감독실 포함)을 볼 때 카메라가 맞추는 사각형(월드 타일). 전체(map)면 null — 그리기도 이 사각형 밖은 자른다(frame)
  function focusRect() {
    const q = view === 'hq' ? world.hq : view === 'map' ? null : roomByView();
    if (!q) return null;
    // 11-08 위 2.5 → 0.5칸(방 위 카드를 평소엔 빼서 — drawBadge) · 아래 0.4(사용자 — 여백이 많다). 11-09 0.4 → 0.2칸(사용자: 최대한)
    // 감독실 현장 카드는 11-09 [전체]로 옮겼다(사용자: 감독실도 방 — 그 방만 보인다)
    return q.hq ? { x: q.x - 0.3, y: q.y - 0.3, w: q.w + 0.6, h: q.h + 0.6 } : { x: q.x - 0.2, y: q.y - 0.3, w: q.w + 0.4, h: q.h + 0.6 };
  }
  function aim() {
    const f = focusRect();
    const r = f || { x: -1, y: -3, w: world.w + 2, h: world.h + 4 };
    // 11-09 한 방: 경고 배너(캔버스 맨 위) 높이만큼 아래 칸에 맞춘다. [전체]: 아래 MAP_H px를 현장 카드에 비운다 — 둘 다 겹쳐 그리지 않는다.
    // 위에 붙인다(배너 밑, 없으면 탭 줄 밑) — 세로가 남으면 남는 자리는 아래로(전엔 가운데라 위에 빈 띠가 생겼다)
    const bh = f && view !== 'hq' ? BANNER_H : 0, below = f ? 0 : MAP_H + 10;
    const room = f && !f.hq && view !== 'hq';
    // 한 방은 계단 배율(roomViewScale, 11-10 모눈) — 패널 좁게 · 넓게 두 값에 하나씩. [전체] · 감독실은 전처럼 맞춘다
    const fit = () => (room ? roomViewScale() : Math.min(W / (r.w * T), (H - bh - below) / (r.h * T)) * 0.99);
    if (!f && world.lounge && W > 0) {
      // [전체] 맨 오른쪽 라운지는 좁다 — 그 카드(최소 폭 MIN_CARD)가 옆 카드와 겹치거나 화면 밖으로 나가지 않게 오른쪽에 자리를 더 둔다.
      // 넓히면 배율이 줄어 카드가 차지하는 타일 수가 늘어난다 — 몇 번 번갈아 맞춘다
      for (let i = 0; i < 4; i++) {
        const need = world.lounge.x + (MIN_CARD() + 8) / (fit() * T) - r.x;
        if (need <= r.w) break;
        r.w = need;
      }
    }
    const s = fit();
    camT.s = s; camT.x = (r.x + r.w / 2) * T;
    // 한 방은 위에 붙이고, [전체]는 카드 자리를 뺀 칸의 가운데(위로 남는 자리에 감독실이 보인다 — 위에 붙이면 잘려 나갔다)
    camT.y = f ? r.y * T + (H / 2 - bh) / s : (r.y + r.h / 2) * T + below / (2 * s);
    // 계단 배율로 방이 세로로 조금 넘치면(위 벽 한 칸까지 — roomViewScale) 아래를 맞추고 위 벽을 자른다. 방 칸(위 벽 아래)은 늘 보인다
    if (room && r.h * T * s > H - bh) camT.y = (r.y + r.h) * T - H / (2 * s);
  }
  // 방 하나를 볼 때의 카메라 배율(11-10 모눈) — 0.25 계단(한 칸 = 4px 단위). 연속값이면 창 · 패널 · 글씨 배율이 바뀔 때마다 방이 조금씩
  // 다른 크기가 됐다(1366 좁게: 글씨 80 · 90%는 2.0, 110%는 머리말이 커져 1.77). 이제 폭으로 정하고, 높이는 위 벽 한 칸까지 잘려도 된다고 본다
  // — 잰 크기(1920 · 1366 · 1024 × 패널 좁게 · 넓게 × 글씨 80~110%)에서 글씨 배율이 바뀌어도 계단이 같다(log/designer_grid_20261110.md 「4.」).
  // 넓은 쪽(패널 좁게)은 좁은 쪽을 통째로 키운 것 — 방 배치는 같고 배율만 다르다. 경고 배너가 뜨면 그 높이를 빼고 맞춘다
  const SCALE_STEP = 0.25, WALL_CROP = 1.0;
  function roomViewScale() {
    const q = L.room || { w: 28, h: 18 };
    const sw = W / ((q.w + 0.4) * T), sh = (H - BANNER_H) / ((q.h + 0.6 - WALL_CROP) * T);
    return Math.max(SCALE_STEP * 2, Math.floor(Math.min(sw, sh) / SCALE_STEP + 1e-6) * SCALE_STEP);
  }

  // ── 한 방 볼 때의 경고 배너(11-09 사용자) ──────────────
  // 탭 줄 바로 밑(캔버스 맨 위)에 폭 전체로 붙이고, 방은 그 아래에서 시작한다(aim이 BANNER_H를 뺀 칸에 맞춘다).
  // 전에는 방 윗벽 위 빈칸에 그리려다 모자라면 방 위에 겹쳤다. 글이 폭을 넘으면 자르지 않고 낱말 단위로 줄을 바꾸고, 그만큼 방이 내려간다
  let BANNER = null, BANNER_H = 0, MAP_H = 0, BANNER_LINK = null, BANNER_LOCK = null;
  const wrapText = (t, maxW) => wrapWords(t, maxW, (s) => ctx.measureText(s).width);
  function bannerLayout(r) {
    const src = cardLines(r, true);
    if (!src.length) return null;
    const lines = [];
    for (const [t, c, f, , link] of src) {
      ctx.font = `${sizeFont(f)} system-ui, sans-serif`;
      for (const s of wrapText(t, W - 12)) lines.push([s, c, f, link]);
    }
    return { lines, h: lines.length * cardLH() + 8, border: badgeLines(r).border, argocd: r.pipe && r.pipe.argocd_url, room: r.name };
  }
  // 프레임마다 — 경고가 생기거나 사라지거나 줄 수가 바뀌면 카메라를 다시 맞춘다(방이 부드럽게 내려가고 올라붙는다)
  function syncBanner() {
    const room = view === 'hq' || view === 'map' ? null : roomByView();
    BANNER = room ? bannerLayout(room) : null;
    if (!BANNER) BANNER_LINK = BANNER_LOCK = null;
    const h = BANNER ? BANNER.h : 0;
    MAPC = view === 'map' ? mapLayout() : null;
    const mh = MAPC ? MAPC.h : 0;
    if (h !== BANNER_H || mh !== MAP_H) { BANNER_H = h; MAP_H = mh; aim(); }
  }
  function drawBanner(b) {
    ctx.fillStyle = '#0d0f14'; ctx.fillRect(0, 0, W, b.h);
    ctx.strokeStyle = b.border; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, b.h - 1); ctx.lineTo(W, b.h - 1); ctx.stroke();
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    BANNER_LINK = null; BANNER_LOCK = null;
    b.lines.forEach(([t, c, f, link], i) => {
      ctx.font = `${sizeFont(f)} system-ui, sans-serif`; ctx.fillStyle = c; ctx.fillText(t, 6, 5 + i * cardLH());
      if (link === 'schemalock' && b.room) {           // 스키마 잠금 줄(11-09) — 밑줄 · 누르면 확인 창 뒤 풀기
        const w = ctx.measureText(t).width, y = 5 + i * cardLH();
        ctx.fillRect(6, y + fpx(15) + 1, w, 1);
        const box = { x: 0, y: y - 2, w: w + 12, h: cardLH(), project: b.room };
        BANNER_LOCK = BANNER_LOCK ? { ...BANNER_LOCK, h: box.y + box.h - BANNER_LOCK.y, w: Math.max(BANNER_LOCK.w, box.w) } : box;
      }
      if (link === 'argocd' && b.argocd) {             // 배포 대기 줄 — 밑줄 · 누르면 ArgoCD 앱 화면(새 탭)
        const w = ctx.measureText(t).width, y = 5 + i * cardLH();
        ctx.fillRect(6, y + fpx(15) + 1, w, 1);
        const box = { x: 0, y: y - 2, w: w + 12, h: cardLH(), url: b.argocd };
        BANNER_LINK = BANNER_LINK && BANNER_LINK.url === box.url ? { ...BANNER_LINK, h: box.y + box.h - BANNER_LINK.y, w: Math.max(BANNER_LINK.w, box.w) } : box;
      }
    });
    if (BANNER_LINK) HITS.push({ ...BANNER_LINK, tip: textTip('ArgoCD Sync 대기 — 수동 Sync 앱이라 ArgoCD 화면에서 Sync를 눌러야 올라갑니다. FOREMAN에는 누를 곳이 없습니다. 누르면 ArgoCD가 새 탭으로 열립니다.') });
    if (BANNER_LOCK) HITS.push({ ...BANNER_LOCK, tip: textTip(lockTip || '스키마 잠금 풀기 — 한 프로젝트의 DB 구조(마이그레이션)는 한 세션만 바꿉니다. 쥔 세션이 스키마 일을 끝냈으면 누르고 확인해 풉니다.') });
    return { x: 0, y: 0, w: W, h: b.h };
  }
  // 점검(tools/screen.py --eval) — 배너 높이와 방 윗벽의 화면 y. 방이 배너 밑에서 시작하면 roomTop >= h
  function bannerAudit() {
    const q = view === 'hq' || view === 'map' ? null : roomByView();
    return { h: BANNER_H, lines: BANNER ? BANNER.lines.map((l) => l[0]) : [], roomTop: q ? Math.round(toScreen(0, q.y * T)[1]) : null };
  }
  function toWorld(px, py) { return [(px - W / 2) / cam.s + cam.x, (py - H / 2) / cam.s + cam.y]; }
  function toScreen(wx, wy) { return [(wx - cam.x) * cam.s + W / 2, (wy - cam.y) * cam.s + H / 2]; }

  function resize() {
    const r = $('oStage').getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    W = r.width; H = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    aim();
    if (!cam.init) { Object.assign(cam, camT); cam.init = true; }
  }

  // ── 그리기 ──────────────────────────────────────────
  function frame(now) {
    if (!running) return;
    // rAF 시각은 그 프레임의 시작이라 앞서 잰 performance.now()보다 이를 수 있다 — 음수 dt면 제자리(d = 0)에서 0/0 = NaN이 됐다
    const dt = Math.max(0, Math.min(0.1, (now - last) / 1000));
    last = now;
    syncBanner();
    const k = Math.min(1, dt * 6);
    cam.x += (camT.x - cam.x) * k; cam.y += (camT.y - cam.y) * k; cam.s += (camT.s - cam.s) * k;
    for (const a of actors.values()) {
      if (a.kind === 'mini') {
        if (a.bornAt && now < a.bornAt) continue;              // 아직 소환 중 — 마법진 가운데서 기다린다
        [a.tx, a.ty] = miniTarget(a, now);
      }
      // 길(점 목록)의 다음 점으로 걷는다 — 점에 닿으면 다음 점, 남은 걸음은 이어서 쓴다
      const route = routeOf(a);
      let step = SPEED * dt * (a.kind === 'mini' ? 0.8 : 1);
      a.moving = false;
      while (route.length && step > 0) {
        const [px, py] = route[0];
        const dx = px - a.x, dy = py - a.y, d = Math.hypot(dx, dy);
        if (d > 0.05) { a.moving = true; a.dir = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up'); }
        if (d <= step) { a.x = px; a.y = py; step -= d; if (route.length > 1) route.shift(); else break; }
        else { a.x += dx / d * step; a.y += dy / d * step; step = 0; }
      }
      a.phase += dt * (a.moving ? 10 : 4);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#15171c';
    ctx.fillRect(0, 0, W, H);
    ctx.setTransform(cam.s * dpr, 0, 0, cam.s * dpr, (W / 2 - cam.x * cam.s) * dpr, (H / 2 - cam.y * cam.s) * dpr);
    ctx.imageSmoothingEnabled = false;
    // 11-09 한 방을 볼 때는 그 방 사각형 밖을 그리지 않는다 — 감독실 아래로 다른 방 선반이 잘린 채 비어져 나왔다(사용자). 밖은 배경색
    const fr = focusRect();
    ctx.save();
    if (fr) { ctx.beginPath(); ctx.rect(fr.x * T, fr.y * T, fr.w * T, fr.h * T); ctx.clip(); }
    const list = [...actors.values()].sort((a, b) => a.y - b.y);
    BODIES.clear();
    if (SP) {
      // 시트 테마 — 바닥 · 벽은 먼저, 가구와 사람은 발밑(아래 끝) 순서로 함께 그린다: 탁자 뒤에 앉은 사람은 다리가 가려진다(앉기 흉내)
      const sorted = [];
      drawHQS(now, sorted);
      for (const r of world.rooms) drawRoomS(r, now, sorted);
      if (world.lounge) drawLoungeS(world.lounge, now, sorted);
      for (const a of list) {
        if (a.bornAt && now < a.bornAt) continue;
        // 소파 · 침대 같은 "위에 앉는" 가구에 자리 잡은 사람은 그 가구 바로 다음(가구 위에). 걸어가는 동안은 발 위치 순서
        const onIt = !a.moving && Math.abs(a.x - a.tx) < 0.05 && Math.abs(a.y - a.ty) < 0.05 && seatFurniture(a);
        sorted.push({ y: onIt ? Math.max(a.y, onIt.key) : a.y, draw: () => drawActorS(a, now) });
        const prop = propOf(a);
        if (prop) {                                                         // 그 동작의 소품 — 앞 탁자 위나 발치에 놓는다
          const tbl = Math.abs(a.x - a.tx) < 0.05 && Math.abs(a.y - a.ty) < 0.05 ? sleepTable(a) : null;
          sorted.push({ y: tbl ? tbl.key + 0.002 : (onIt ? Math.max(a.y, onIt.key) : a.y) + 0.001, draw: () => drawPropS(a, prop, tbl, now) });
        }
        const tbl = !a.moving && a.act && a.act.anim === 'sleep' && sleepTable(a);
        if (tbl) sorted.push({ y: tbl.key, draw: () => {                   // 엎드린 머리를 탁자 위에
          ctx.save(); ctx.beginPath();
          ctx.rect((a.x - 1.5) * T, (a.y - 4) * T, 3 * T, (tbl.clipBottom - a.y + 4) * T); ctx.clip();   // 11-09 캐릭터 1.5배 — 칸도 넓게
          drawActorS(a, now); ctx.restore();
        } });
      }
      sorted.sort((p, q) => p.y - q.y);
      for (const it of sorted) it.draw();
      for (const r of world.rooms) overTopItems(r, list, now);       // 탁자 위 소품이 사람 앞에 그려진 자리만 사람을 덧그린다
      if (world.hq) overTopItems(world.hq, list, now, 'hq');        // 감독실(교장실 · 팀장실 · 감독 컨테이너) 탁자도
      BUBBLES.clear();
      for (const a of list) drawOverlay(a, now);
    } else {
      drawHQShapes(now);
      for (const r of world.rooms) drawRoom(r, now);
      if (world.lounge) drawLounge(world.lounge);
      for (const a of list) if (!(a.bornAt && now < a.bornAt)) drawActor(a, now);
    }
    drawSummonsPuffs(now);
    drawWalkDebug();
    ctx.restore();                                  // 한 방 자르기(focusRect) 끝
    // 글자는 화면 좌표로(선명하게)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    HITS = []; NAMES = []; MAP_BOXES = []; BOARD_NAMES = []; LABELS = [];
    if (LAMP) {                                     // 경고등 호버(11-09) — 왜 켜졌는지
      const [lx, ly] = toScreen(LAMP.x, LAMP.y), rr = Math.max(10, 8 * cam.s);
      const head = LAMP.max >= 90 ? `사용량 경고등 — 구독 한도를 ${Math.round(LAMP.max)}% 썼습니다. 100%가 되면 리셋까지 모든 세션이 멈춥니다.`
        : `사용량 경고등 — 사용량을 읽지 못하고 있습니다. 한도 %가 낡았을 수 있습니다.${usageTipRows.why}`;
      HITS.push({ x: lx - rr, y: ly - rr, w: 2 * rr, h: 2 * rr, soft: true, tip: textTip([head, ...usageTipRows.lines].join('\n')) });
    }
    const zoomedIn = view !== 'map';
    for (const r of [...world.rooms, world.lounge]) drawBadge(r, zoomedIn);
    if (view === 'hq') {
      drawHQCards();
      const hqName = (theme.hq && theme.hq.label) || '감독실';
      drawTag(world.hq.x + 0.3, world.hq.y + 2.2, hqName, true, null, null,
        `<div class="tip-h">${esc(hqName)}</div><div class="tip-b">감독실</div><div>현장마다 지금 상태를 한눈에 보는 곳입니다.</div>`);
      for (const a of list) if (a.room === '_hq') drawName(a);
    } else if (zoomedIn) {
      const room = roomByView();
      if (room && !room.lounge) { drawZoneTags(room); if (SP) overTags(room, list, now); }
      const here = list.filter((a) => a.room === (view === '_lounge' ? null : view));
      markCrowd(here);
      for (const a of here) drawName(a);
    }
    requestAnimationFrame(frame);
  }

  function rect(x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(x * T, y * T, w * T, h * T); }

  function drawRoom(r, now) {
    const z = L.zones;
    for (let i = 0; i < r.w; i++) for (let j = 0; j < r.h; j++) rect(r.x + i, r.y + j, 1, 1, (i + j) % 2 ? P.floor : P.floorAlt);
    // 벽
    ctx.strokeStyle = P.wallTop; ctx.lineWidth = 3;
    ctx.strokeRect(r.x * T, r.y * T, r.w * T, r.h * T);
    // 포먼 사무실(구석, 유리벽)
    const f = z.foreman_office;
    rect(r.x + f.x, r.y + f.y, f.w, f.h, P.office);
    ctx.strokeStyle = P.officeGlass; ctx.lineWidth = 2;
    ctx.strokeRect((r.x + f.x) * T, (r.y + f.y) * T, f.w * T, f.h * T);
    rect(r.x + f.x + 1, r.y + f.y + 1, 3, 1, P.deskTop);
    // 책상
    const d = z.desks;
    for (let k = 0; k < d.cols * d.rows; k++) {
      const sx = r.x + d.x + (k % d.cols) * d.dx, sy = r.y + d.y + Math.floor(k / d.cols) * d.dy;
      rect(sx, sy, 2, 1, P.deskTop); rect(sx, sy + 1, 2, 0.25, P.desk);
      rect(sx + 0.6, sy - 0.1, 0.8, 0.5, '#1b1f27');      // 모니터
    }
    // 서버랙 · 창 · 전화
    const s = z.server_rack;
    rect(r.x + s.x, r.y + s.y, s.w, s.h, P.rack);
    for (let i = 0; i < 6; i++) if (Math.sin(now / 300 + i * 1.7) > 0) rect(r.x + s.x + 0.4 + (i % 3) * 0.8, r.y + s.y + 0.5 + Math.floor(i / 3) * 1.2, 0.3, 0.2, P.rackLed);
    const w = z.window;
    rect(r.x + w.x, r.y + w.y, w.w, w.h, P.window);
    rect(r.x + z.phone.x, r.y + z.phone.y, 1, 1, '#c9a227');
    // 파이프라인 구역
    const iz = z.infra;
    rect(r.x + 1, r.y + iz.y, r.w - 2, iz.h, P.infraFloor);
    for (const kind of ['jenkins', 'harbor', 'argocd']) {
      const st = r['st_' + kind] || 'none';
      const c = { running: P.act, success: P.ok, failed: P.bad, waiting: P.warn, none: P.muted }[st] || P.muted;
      rect(r.x + iz[kind].x, r.y + iz.y + 0.5, 4, 2, '#1f252c');
      ctx.strokeStyle = c; ctx.lineWidth = 2;
      ctx.strokeRect((r.x + iz[kind].x) * T, (r.y + iz.y + 0.5) * T, 4 * T, 2 * T);
      if (kind !== 'argocd') { ctx.fillStyle = P.muted; ctx.fillRect((r.x + iz[kind].x + 4.3) * T, (r.y + iz.y + 1.4) * T, 4.4 * T, 2); }
      if (st === 'waiting') drawSign(r.x + iz[kind].x + 2, r.y + iz.y + 0.1, '⏸');
      if (st === 'failed') drawSmoke(r.x + iz[kind].x + 2, r.y + iz.y + 0.4, now);
    }
  }

  function drawLounge(r) {
    for (let i = 0; i < r.w; i++) for (let j = 0; j < r.h; j++) rect(r.x + i, r.y + j, 1, 1, (i + j) % 2 ? P.lounge : '#332d34');
    ctx.strokeStyle = '#6b5f6e'; ctx.lineWidth = 3; ctx.setLineDash([6, 4]);
    ctx.strokeRect(r.x * T, r.y * T, r.w * T, r.h * T); ctx.setLineDash([]);
    const z = L.zones.lounge_seats;
    for (let k = 0; k < z.cols * z.rows; k++) rect(r.x + z.x + (k % z.cols) * z.dx - 0.5, r.y + z.y + Math.floor(k / z.cols) * z.dy + 1.5, 2, 0.6, '#5a4a5e');
  }

  function drawActor(a, now) {
    const sp = theme.sprites.person, act = a.act || {};
    if (a.kind === 'mini') {                                  // 도형 테마의 축소판
      const s = MINI, x = a.x * T, yb = a.y * T, h = sp.h * s, w = sp.w * s, bob = Math.abs(Math.sin(a.phase)) * 1.5;
      ctx.fillStyle = roleColor(a.role) || `hsl(${a.hue} 55% 55%)`; ctx.fillRect(x - w / 2, yb - h * 0.7 - bob, w, h * 0.7);
      ctx.fillStyle = '#f1c9a5'; ctx.beginPath(); ctx.arc(x, yb - h * 0.8 - bob, sp.head * s, 0, Math.PI * 2); ctx.fill();
      return;
    }
    const x = a.x * T, yBase = a.y * T;
    const anim = a.moving ? 'walk' : (act.anim || 'stand');
    const sit = !a.moving && (anim === 'sit' || anim === 'type' || anim === 'read' || anim === 'think' || anim === 'call');
    const bob = anim === 'walk' ? Math.abs(Math.sin(a.phase)) * 2 : (anim === 'work' ? Math.abs(Math.sin(a.phase)) : 0);
    const h = sit ? sp.h - 4 : sp.h;
    const y = yBase - h - bob;
    ctx.globalAlpha = act.alpha != null ? act.alpha : 1;
    const body = act.fx === 'frozen' ? P.frozen : `hsl(${a.hue} 55% ${a.kind === 'foreman' ? 45 : 55}%)`;
    // 몸 · 머리
    ctx.fillStyle = body; ctx.fillRect(x - sp.w / 2, y + sp.head * 1.6, sp.w, h - sp.head * 1.6);
    ctx.fillStyle = act.fx === 'frozen' ? '#dff3ff' : '#f1c9a5';
    ctx.beginPath(); ctx.arc(x, y + sp.head, sp.head, 0, Math.PI * 2); ctx.fill();
    if (a.kind === 'foreman') { ctx.fillStyle = '#f2c14e'; ctx.fillRect(x - 5, y - 1, 10, 2); }       // 포먼 표시(모자 띠)
    if (a.kind === 'infra' || a.kind === 'courier') { ctx.fillStyle = '#ff9f1c'; ctx.fillRect(x - 6, y - 1, 12, 3); }           // 안전모
    // 손 · 소품
    ctx.fillStyle = body;
    if (anim === 'type' && !a.moving) { const j = Math.sin(a.phase * 3) > 0 ? 1 : 0; ctx.fillRect(x - 6, y + 9 + j, 3, 2); ctx.fillRect(x + 3, y + 9 + (1 - j), 3, 2); }
    if (anim === 'read' && !a.moving) { ctx.fillStyle = '#e8e0c8'; ctx.fillRect(x - 5, y + 8, 10, 4); }
    if (anim === 'raise_hand') { ctx.fillRect(x + 4, y - 4, 2, 9); }
    if (anim === 'talk' || anim === 'call') { ctx.fillStyle = '#c9a227'; ctx.fillRect(x + 4, y + 2, 3, 5); }
    if (act.fx === 'frozen') { ctx.strokeStyle = '#bfe8ff'; ctx.lineWidth = 1; ctx.strokeRect(x - sp.w / 2 - 2, y - 2, sp.w + 4, h + 4); }
    ctx.globalAlpha = 1;
    drawHeat(a, now);
    if (act.fx === 'smoke') drawSmoke(a.x, a.y - 1.4, now);
    if (act.bubble) drawBubble(x, y - 6, act.bubble, act.flag === 'approval_pending' ? P.warn : '#e8e8f0');
    else if (anim === 'wait' && !act.flag) drawBubble(x, y - 6, '·'.repeat(1 + Math.floor(now / 500) % 3).padEnd(3, ' '), P.act, 7);   // 기다림
    else if (a.kind === 'scribe' && scribeBubble(a)) drawBubble(x, y - 6, scribeBubble(a), P.warn, todoPx() / cam.s);
    else if (coderBubbleOf(a)) drawBubble(x, y - 6, coderBubbleOf(a), P.warn, todoPx() / cam.s);
    else if (a.kind === 'foreman' && a.fm && a.fm.pending.length) drawBubble(x, y - 6, `시작할 일 ${a.fm.pending.length}`, P.warn, todoPx() / cam.s);
    if (a.subHidden) drawBubble(x + 10, y + 2, `+${a.subHidden}`, P.act, 7);              // 10명 넘는 서브에이전트는 접는다
    drawCompactMark(a, x + 8, y - 4);
    const rc = roleColor(a.role);
    if (rc) { ctx.fillStyle = rc; ctx.fillRect(x - 1, y + sp.head * 1.6, 2, h - sp.head * 1.6 - 2); }   // 역할 — 사원증 끈 색
    if (a.key === selected) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - 9, y - 3, 18, h + 6); }
  }

  // ── 시트 테마 그리기(10d) ────────────────────────────
  const RS = (SP && theme.sprites.room) || {};
  function tileHash(i, j) { return ((i * 73856093) ^ (j * 19349663)) >>> 0; }

  function spriteBottom(name, y) { const [, h] = SP.size(name); return y + h / T; }

  // ── 자리 점검(11-05, 디버그) — 캐릭터가 서는 모든 자리에서 가구가 사람 윗몸(머리 · 가슴)을 덮는지, 자리가 가구 발밑 안인지.
  // 화면 시험이 window.office.audit()으로 부른다. 앉은 자리에서 책상이 다리를 가리는 것은 정상(윗몸만 본다)
  function standSpots() {
    const out = [], z = L.zones;
    for (const [name, zz] of Object.entries(z)) {
      if (!zz || name === 'infra' || name === 'lounge_seats') continue;
      if (zz.seats) zz.seats.forEach((s, i) => out.push({ where: `${name}#${i}`, x: s[0], y: s[1] }));
      if (zz.stand) out.push({ where: `${name}.stand`, x: zz.stand[0], y: zz.stand[1] });
      if (zz.seat) out.push({ where: `${name}.seat`, x: zz.seat[0], y: zz.seat[1] });
    }
    if (z.infra) {
      for (const k of ['jenkins', 'harbor', 'argocd']) { const [x, y] = stageStand({ x: 0, y: 0 }, k); out.push({ where: `infra.${k}`, x, y }); }
      const [hx, hy] = courierHome({ x: 0, y: 0 });
      out.push({ where: 'infra.home', x: hx, y: hy }, { where: 'infra.handoff', x: hx + HANDOFF_DX, y: hy });
    }
    return out;
  }
  // where: 'room'(방 가구 + 출하 라인, 방 좌표) · 'hq'(감독실 가구, 감독실 좌표)
  function decorRects(where = 'room') {
    const out = [], iz = L.zones.infra;
    const add = (d, ox, oy, src) => {
      if (!d.s || d.fx || d.z === 'wall' || d.z === 'floor') return;
      const [w, h] = sizeT(d);
      for (let i = 0; i < (d.n || 1); i++) {
        const x = ox + d.x + i * (d.dx || 1), y = oy + d.y;
        const top = d.z === 'top';
        const key = top ? oy + topKey(d) : y + h - 0.01;
        out.push({ s: d.s, src, d, ox, oy, x, y, w, h, key, top, host: top ? d._host : null,
                   hostTop: top && d._hostTop != null ? oy + d._hostTop : null,
                   foot: top ? null : footprint({ ...d, x, y }, w, h) });
      }
    };
    if (where === 'hq') { for (const d of HQ.decor || []) add(d, 0, 0, 'hq'); return out; }
    for (const d of theme.sprites.decor || []) add(d, 0, 0, 'decor');
    if (iz) for (const k of ['jenkins', 'harbor', 'argocd']) for (const d of (theme.sprites.infra_decor || {})[k] || []) add(d, iz[k].x, iz.y, 'infra.' + k);
    return out;
  }
  // 한 점(방 좌표)에 사람이 서면 — 윗몸 · 머리가 가려지는 비율, 가구 발밑 안인가. 자리를 고를 때 쓴다
  function probe(x, y) {
    const rects = decorRects();
    let body = 0, head = 0, inFoot = false;
    for (const r of rects) {
      const f = r.foot;
      if (f && x > f[0] - 0.15 && x < f[0] + f[2] + 0.15 && y > f[1] - 0.1 && y < f[1] + f[3] + 0.1) inFoot = true;
      if (r.key <= y) continue;
      const cov = (bx, by, bw, bh) => Math.max(0, Math.min(bx + bw, r.x + r.w) - Math.max(bx, r.x)) * Math.max(0, Math.min(by + bh, r.y + r.h) - Math.max(by, r.y)) / (bw * bh);
      body = Math.max(body, cov(x - 0.4, y - 1.6, 0.8, 0.85));
      head = Math.max(head, cov(x - 0.35, y - 1.6, 0.7, 0.5));
    }
    return { body: +body.toFixed(2), head: +head.toFixed(2), inFoot };
  }
  // 소품이 사람 앞에 그려지는 부분 — 소품 칸 ∩ 사람 몸 ∩ 받침 윗면 선 위쪽(아래쪽은 원래 탁자가 사람을 가린다). [x, y, w, h] | null
  function topOverlap(r, px, py) {
    const x0 = Math.max(px - 0.45, r.x), x1 = Math.min(px + 0.45, r.x + r.w);
    const y0 = Math.max(py - 1.6, r.y), y1 = Math.min(py, r.y + r.h, r.hostTop != null ? r.hostTop : Infinity);
    return x1 - x0 > 0.05 && y1 - y0 > 0.05 ? [x0, y0, x1 - x0, y1 - y0] : null;
  }
  function audit() {
    const issues = [];
    const check = (spots, rects) => {
      for (const p of spots) {
        const body = [p.x - 0.4, p.y - 1.6, 0.8, 0.85];               // 윗몸(머리 · 가슴)
        for (const r of rects) {
          if (r.top) continue;                                        // 소품은 아래에서 따로
          const ix = Math.min(body[0] + body[2], r.x + r.w) - Math.max(body[0], r.x);
          const iy = Math.min(body[1] + body[3], r.y + r.h) - Math.max(body[1], r.y);
          if (r.key > p.y && ix > 0.15 && iy > 0.15) issues.push({ where: p.where, at: [p.x, p.y], kind: '가림', by: r.s, src: r.src, overlap: +(ix * iy / (body[2] * body[3])).toFixed(2) });
        }
        for (const r of rects) {
          const f = r.foot;
          if (f && p.x > f[0] && p.x < f[0] + f[2] && p.y > f[1] && p.y < f[1] + f[3]) issues.push({ where: p.where, at: [p.x, p.y], kind: '가구 안', by: r.s, src: r.src });
        }
        // 탁자 위 소품(z: top)이 사람 앞에 — 받침 윗면 위로 보이는 몸과 겹치고 사람보다 나중에 그려지는 것.
        // 그림 단계의 덧그리기(overTopItems)가 그 칸만 사람을 다시 그린다(fixed: true)
        for (const r of rects) {
          if (!r.top || r.key <= p.y) continue;
          const o = topOverlap(r, p.x, p.y);
          if (o) issues.push({ where: p.where, at: [p.x, p.y], kind: '소품 앞', by: r.s, src: r.src, overlap: +(o[2] * o[3] / (0.9 * 1.6)).toFixed(2), fixed: true });
        }
      }
      for (const r of rects) if (r.top && !r.host) issues.push({ where: r.src, at: [r.x, r.y], kind: '받침 없음', by: r.s, src: r.src });
    };
    check(standSpots(), decorRects('room'));
    if (HQ.seat) check([{ where: 'hq.seat', x: HQ.seat[0], y: HQ.seat[1] }], decorRects('hq'));
    return issues;
  }

  // ── 자리 배치 점검 · 다시 짜기(11-05 사용자 요청: 겹침을 하나씩 고치지 말고 근본적으로) ─────────────
  // 사람 자리를 먼저 본다 — 모든 자리에 캐릭터를 세워 머리 · 몸통(몸 위쪽 60%)을 무엇이 가리는지: 나중에 그려지는 가구,
  // 탁자 위 소품(받침 윗면 위로 솟은 부분), 구역 이름표(몸 전체). 머리만 보이는 것도 가려짐이다.
  // 괜찮은 것: 앉은 자리에서 탁자가 다리(아래 40%)를 가리는 것, "위에 앉는" 가구(소파 · 침대 — 사람보다 먼저 그린다).
  function bodySize() {
    if (bodySize._v) return bodySize._v;
    let w = 0.9, h = 1.5;
    for (const ch of (CH.pool || []).slice(0, 8)) {
      const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
      if (c) { w = Math.max(w, c.width / T); h = Math.max(h, c.height / T); }
    }
    const k = (theme.sprites && theme.sprites.char_scale) ?? 1.5;    // 캐릭터 배율(11-09) — 상한도 같이
    return (bodySize._v = [Math.min(w, 1.3 * k), Math.min(h, 2.4 * k)]);
  }
  // ── 방 이름표(11-10 모눈) — 방 왼쪽 위 칸에 고정한다 ─────────────────────────────
  // 전에는 가구 · 사람 자리를 먼저 잡고 이름표가 빈 데를 찾아갔다(11-05 tagPlace → 11-10 tagLayout 한꺼번에 놓기 — 겹침 378 → 3건).
  // 겹치지 않게는 됐지만 이름표가 제각각 떠서 어수선했고(사용자), 화면 너비가 연속값이라 모든 중간 너비에서 자리를 골라야 했다.
  // 이제 자리 고르기가 없다: 방 왼쪽 위 + pad. 그 칸은 테마 배치가 비운다(가구 · 사람 머리 — gridAudit이 본다).
  // 글씨는 월드 크기(grid.json label.font, 월드 px) — 방 배율을 따라 함께 커지고 작아진다. 글씨 배율(가− · 가+)은 패널 · 머리말 몫이고
  // 방 안 이름표에는 들어가지 않는다(11-10 사용자 — "브라우저 글씨 크기에 흔들리지 않게"). 화면 8px 밑으로는 줄이지 않는다(1024 · 패널 넓게 =
  // 배율 1에서 이름표 1.45배 — 판 바닥이 방 위에서 1.04칸. 9px로 했더니 1.64배 · 1.16칸이 되어 단계 그림 · 바로 밑 자리에 걸렸다)
  // 이름은 짧게 — 하는 일은 호버(「① 빌드 모니터 · Jenkins 빌드」 → 이름표 「빌드 모니터」, 호버 「Jenkins 빌드」). ① ② ③은 바닥 화살표 쪽
  const GL = (GRIDDEF && GRIDDEF.label) || { font: 6.5, h: 0.75, pad: 0.1 };
  const LABEL_MIN_PX = 8;
  // s = 월드 px 하나의 화면 px(cam.s). 키우는 배수는 1.45(배율 1 — 1024 패널 넓게)에서 멈춘다: 터미널을 열어 방이 그보다 작아지면(배율 0.75 등)
  // 글씨도 8px 밑으로 함께 작아진다 — 이름표 판이 비워 둔 칸(방 위 1.1칸)을 넘지 않게
  const LABEL_K_MAX = 1.45;
  const labelK = (s) => Math.min(LABEL_K_MAX, Math.max(1, LABEL_MIN_PX / (GL.font * s)));
  const labelFont = (s) => TAG0.font.replace(/(\d+(?:\.\d+)?)px/, `${(GL.font * s * labelK(s)).toFixed(2)}px`);
  const STAGE_DOT = { running: 'act', success: 'ok', failed: 'bad', waiting: 'warn' };
  const STAGE_SYM = { running: '…', success: '✓', failed: '✗', waiting: '⏸' };     // 이름표엔 기호만, 말은 호버(STATUS_KO)
  const stageName = (k) => {
    const v = ((theme.tags && theme.tags.infra) || {})[k], iz = L.zones.infra;
    if (Array.isArray(v)) return { name: v[0], what: v[1] || '' };
    const s = String(v || (iz[k] && iz[k].label) || k);
    return { name: s.split(' · ')[0], what: s.split(' · ')[1] || '' };
  };
  // 방 하나의 이름표 목록(방 좌표 타일) — 구역 열 + 출하장 + 세 단계. room을 주면 단계 상태(점 · 기호)까지
  function roomLabels(room = null) {
    const out = [];
    const names = (theme.tags && theme.tags.zones) || {}, roles = (theme.tags && theme.tags.roles) || {};
    for (const [key, v] of Object.entries(names)) {
      const z = L.zones[key];
      if (!z || z.x == null) continue;
      const [label] = Array.isArray(v) ? v : [v];
      out.push({ zone: key, text: label, x: z.x, y: z.y, role: roles[key] });
    }
    const iz = L.zones.infra, it = (theme.tags && theme.tags.infra) || {};
    if (iz && iz.jenkins) {
      // 모눈이 없는 테마(도형 plain)는 출하 라인 위 한 줄에
      if (it.title) out.push({ zone: 'infra', text: it.title, x: GRIDDEF ? iz.x : 1, y: GRIDDEF ? iz.y : iz.y - 0.9, role: 'ship' });
      INFRA_STAGES.forEach((k, i) => {
        const st = (room && room['st_' + k]) || 'none', { name, what } = stageName(k);
        out.push({ zone: 'infra:' + k, stage: k, i, st, what, text: name + (STAGE_SYM[st] ? ' ' + STAGE_SYM[st] : ''), dot: STAGE_DOT[st] ? P[STAGE_DOT[st]] : null,
                   x: iz[k].x, y: iz.y });
      });
    }
    return out;
  }
  // 이름표 칸(방 좌표 타일, [x, y, w, h]) — 왼쪽 위 + pad. s = 그릴 때의 배율(재기는 방 하나를 보는 배율)
  function labelBox(l, s = roomViewScale()) {
    const k = labelK(s), pad = GL.pad * T * k;                                     // 월드 px
    ctx.save(); ctx.font = labelFont(s); const tw = ctx.measureText(l.text).width / s; ctx.restore();
    const dot = l.dot ? GL.font * k : 0;
    return [l.x + GL.pad, l.y + GL.pad, (tw + dot + 2 * pad) / T, GL.h * k];
  }
  // 이름표 칸 목록 — layoutAudit(사람 자리 ↔ 이름표) · gridAudit(왼쪽 위 칸 · 가구) · layoutPlan이 쓴다
  function tagRects(where = 'room') {
    if (where === 'hq') {                                                           // 감독실 이름표는 그대로(화면 크기 — 감독실은 모눈 밖)
      const s = roomViewScale() * T, padL = TAG.kind === 'hazard' ? 9 : TAG.kind === 'sign' ? 7 : 6, fontPx = +((TAG.font.match(/(\d+)px/) || [0, 10])[1]);
      ctx.save(); ctx.font = TAG.font.replace(/(\d+)px/, (m, n) => `${+n + 3}px`);
      const label = HQ.label || '감독실', w = (padL + ctx.measureText(label).width + 6) / s;
      ctx.restore();
      return [{ zone: 'hq', label, x: 0.3, y: 2.2, w, h: (fontPx + 10) / s }];
    }
    return roomLabels().map((l) => { const [x, y, w, h] = labelBox(l); return { zone: l.zone, label: l.text, x, y, w, h }; });
  }
  const areaOf = (a, b) => Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) *
                           Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));
  function spotProblems(p, rects, tags) {
    const [bw, bh] = bodySize();
    const up = [p.x - bw / 2 + 0.05, p.y - bh, bw - 0.1, bh * 0.6], full = [p.x - bw / 2 + 0.05, p.y - bh, bw - 0.1, bh];
    const out = [];
    for (const r of rects) {
      if (r.key <= p.y) continue;                                                  // 사람보다 먼저 그려진다
      if (!r.top && SIT_ON.test(r.s) && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h) continue;   // 위에 앉은 가구
      const box = r.top && r.hostTop != null ? [r.x, r.y, r.w, Math.max(0, Math.min(r.y + r.h, r.hostTop) - r.y)] : [r.x, r.y, r.w, r.h];
      const c = areaOf(up, box) / (up[2] * up[3]);
      if (c > 0.02) out.push({ kind: r.top ? '소품' : '가구', by: r.s, r, cover: +c.toFixed(2) });
    }
    for (const t of tags) {
      const c = areaOf(full, [t.x, t.y, t.w, t.h]) / (full[2] * full[3]);
      if (c > 0.02) out.push({ kind: '이름표', by: t.label, t, cover: +c.toFixed(2) });
    }
    return out;
  }
  // 자리 점검 — 모든 자리(구역 좌석 · 책상 · 감독 자리 · 출하 라인 · 대기 · 일감 넘기기 · 감독실)
  // labels:false면 좌석 점검만(이름표 점검 labelAudit은 지금 화면 그대로라 screen.py가 화면마다 따로 센다, 11-10)
  function layoutAudit({ labels = true } = {}) {
    const out = labels ? labelAudit() : [], rects = decorRects('room'), tags = tagRects('room');
    for (const p of standSpots()) { const pr = spotProblems(p, rects, tags); if (pr.length) out.push({ where: p.where, at: [p.x, p.y], problems: pr.map(({ kind, by, cover }) => ({ kind, by, cover })) }); }
    if (HQ.seat) {
      const p = { where: 'hq.seat', x: HQ.seat[0], y: HQ.seat[1] }, pr = spotProblems(p, decorRects('hq'), tagRects('hq'));
      if (pr.length) out.push({ where: p.where, at: [p.x, p.y], problems: pr.map(({ kind, by, cover }) => ({ kind, by, cover })) });
    }
    return out;
  }
  // 자리 다시 짜기 — ② 소품이 가리면 소품을 받침 탁자 위에서 옆으로 ③ 그래도 가리면 사람 자리를 가장 가까운 깨끗한 곳으로
  // (원래 가구 칸 안에 있던 자리는 그 가구 곁에서, 빈 바닥 자리는 걸을 수 있는 칸에서). ① 이름표 옮기기는 11-10 모눈에서 뺐다(이름표는 방 왼쪽 위 고정).
  // 이 페이지 안의 테마 값을 바꿔 가며 풀고, 바뀐 값만 돌려준다 — theme.json에 옮겨 적는다(모눈 테마는 방 왼쪽 위 기준으로 바꿔 적는다)
  function layoutPlan() {
    const before = layoutAudit({ labels: false });
    const spots = () => standSpots();
    const blocked = (x, y) => { const g = GRID && GRID.room; if (!g) return false; const c = Math.floor(x * RES), r = Math.floor(y * RES); return c < 0 || r < 0 || c >= g.cols || r >= g.rows || !!g.block[r * g.cols + c]; };
    const changes = { items: [], seats: {}, stands: {}, unsolved: [] };
    // ② 소품
    for (const r of decorRects('room').filter((x) => x.top && x.d._hostSpan)) {
      const covering = () => spots().filter((p) => spotProblems(p, [r], []).length);
      if (!covering().length) continue;
      const [s0, s1] = r.d._hostSpan, x0 = r.d.x;
      let best = null;
      for (let nx = s0; nx <= s1 - r.w + 1e-9; nx += 0.05) {
        r.d.x = nx; r.x = r.ox + nx;
        if (!covering().length && (!best || Math.abs(nx - x0) < Math.abs(best - x0))) best = nx;
      }
      r.d.x = best != null ? +best.toFixed(2) : x0; r.x = r.ox + r.d.x;
      if (best != null) changes.items.push({ s: r.s, src: r.src, from: [x0, r.d.y], to: [r.d.x, r.d.y] });
    }
    // ③ 사람 자리
    const rects = decorRects('room'), tags = tagRects('room');
    for (const p of spots()) {
      if (!spotProblems(p, rects, tags).length) continue;
      const [zone, idx] = p.where.split(/[#.]/);
      const host = rects.find((r) => !r.top && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h);
      const sameZone = spots().filter((o) => o.where !== p.where && o.where.split(/[#.]/)[0] === zone);
      let best = null;
      for (let ny = p.y - 0.6; ny <= p.y + 1.0 + 1e-9; ny += 0.05) for (let nx = p.x - 1.2; nx <= p.x + 1.2 + 1e-9; nx += 0.05) {
        const d = Math.hypot(nx - p.x, (ny - p.y) * 1.2);
        if (best && d >= best.d) continue;
        if (host ? !(nx >= host.x - 0.3 && nx <= host.x + host.w + 0.3 && ny >= host.y - 0.3 && ny <= host.y + host.h + 0.3) : blocked(nx, ny)) continue;
        if (sameZone.some((o) => Math.hypot(o.x - nx, o.y - ny) < 0.75)) continue;
        if (spotProblems({ x: nx, y: ny }, rects, tags).length) continue;
        best = { d, x: +nx.toFixed(2), y: +ny.toFixed(2) };
      }
      if (!best) { changes.unsolved.push({ spot: p.where, at: [p.x, p.y], problems: spotProblems(p, rects, tags).map(({ kind, by, cover }) => ({ kind, by, cover })) }); continue; }
      if (zone === 'infra') {
        const z = L.zones.infra; z.stands = z.stands || {};
        if (idx === 'handoff') { changes.unsolved.push({ spot: p.where, note: '일감 넘기는 자리는 대기 자리 + 1.3칸 — 대기 자리를 옮겨야 한다' }); continue; }
        z.stands[idx] = [best.x, best.y]; changes.stands[idx] = [best.x, best.y];
      } else if (idx === 'seat') { L.zones[zone].seat = [best.x, best.y]; changes.seats[zone + '.seat'] = [best.x, best.y]; }
      else if (idx === 'stand') { L.zones[zone].stand = [best.x, best.y]; changes.seats[zone + '.stand'] = [best.x, best.y]; }
      else {
        const s = L.zones[zone].seats[+idx];
        s[0] = best.x; s[1] = best.y;
        changes.seats[zone] = L.zones[zone].seats.map((q) => q.slice());
      }
    }
    TOP_RECTS.room = null;
    return { before, changes, after: layoutAudit({ labels: false }) };
  }

  // 탁자 위 소품 덧그리기(11-05) — 탁자 뒤에 앉은 사람은 탁자보다 먼저 그려져야 다리가 가려지는데, 그러면 탁자 위 소품
  // (책 · 머그 · 촛대)이 사람 몸 위로 그려진다. 한 줄 정렬로는 둘 다 만족할 수 없어서, 다 그린 뒤 소품과 겹치는 사람만
  // 소품 자리 안에서 한 번 더 그린다 — 탁자는 다리를 가리고, 소품은 사람 뒤로 간다
  // 구역 이름표 위로 사람을 덧그린다(11-05) — 이름표는 화면에 같은 크기라 화면이 좁을수록(패널을 넓히면) 방 안에서 커져서,
  // 이름표 자리를 옮기는 것만으로는 모든 배율에서 사람 자리를 피할 수 없다. 이름표를 그린 뒤 이름표 칸 안의 사람만 한 번 더 —
  // 이름표는 읽히고, 사람은 어떤 배율에서도 이름표에 가리지 않는다
  function overTags(room, list, now) {
    const tags = HITS.filter((h) => h.zone);
    if (!tags.length) return;
    const toW = (sx, sy) => [((sx - W / 2) / cam.s + cam.x), ((sy - H / 2) / cam.s + cam.y)];   // 화면 → 월드 픽셀
    const boxes = tags.map((h) => { const [x0, y0] = toW(h.x, h.y), [x1, y1] = toW(h.x + h.w, h.y + h.h); return [x0, y0, x1 - x0, y1 - y0]; });
    const [bw, bh] = bodySize();
    ctx.save();
    ctx.setTransform(cam.s * dpr, 0, 0, cam.s * dpr, (W / 2 - cam.x * cam.s) * dpr, (H / 2 - cam.y * cam.s) * dpr);
    for (const a of list) {
      if (a.room !== room.name || (a.bornAt && now < a.bornAt)) continue;
      const body = [(a.x - bw / 2) * T, (a.y - bh) * T, bw * T, bh * T];
      const hit = boxes.filter((b) => areaOf(body, b) > 0);
      if (!hit.length) continue;
      ctx.save(); ctx.beginPath();
      for (const b of hit) ctx.rect(b[0], b[1], b[2], b[3]);
      ctx.clip(); drawActorS(a, now); ctx.restore();
    }
    ctx.restore();
  }

  const TOP_RECTS = {};
  function overTopItems(room, list, now, where = 'room') {
    if (!TOP_RECTS[where]) TOP_RECTS[where] = decorRects(where).filter((r) => r.top);
    const rects = TOP_RECTS[where];
    if (!rects.length || window.__noTopFix) return;      // __noTopFix — 화면 시험에서 고치기 전 모습과 견줄 때만
    for (const a of list) {
      if (a.room !== room.name || (a.bornAt && now < a.bornAt)) continue;
      const ax = a.x - room.x, ay = a.y - room.y;          // 방(감독실) 좌표
      const parts = rects.filter((r) => r.key > ay).map((r) => topOverlap(r, ax, ay)).filter(Boolean);
      if (!parts.length) continue;
      ctx.save();
      ctx.beginPath();
      for (const [x, y, w, h] of parts) ctx.rect((room.x + x) * T, (room.y + y) * T, w * T, h * T);
      ctx.clip();
      drawActorS(a, now);
      ctx.restore();
    }
  }

  // 탁자 위 소품의 그리는 순서 — 소품 가운데가 들어 있는 받침(같은 목록의 가구) 중 발밑이 가장 아래인 것 바로 다음.
  // 전에는 y + 3(어림)이라 받침 앞(아래)에 선 사람보다 늦게 그려져 사람 머리 위로 소품이 덮였다(11-05)
  function topKey(d) {
    if (d._k != null) return d._k;
    // 소품이 들어 있는 목록 — 방 가구 · 출하 라인 · 감독실(theme.hq.decor). 감독실을 빠뜨려서 그 탁자 위 책 · 두루마리가
    // 받침을 못 찾고 어림값(y + h + 0.3)으로 떨어져 탁자에 앉은 포먼 위로 그려졌다(11-05 사용자 보고)
    const lists = [theme.sprites.decor || [], ...Object.values(theme.sprites.infra_decor || {}), (theme.hq && theme.hq.decor) || []];
    const list = lists.find((l) => l.includes(d)) || [];
    // 받침을 가운데가 아니라 소품의 밑동(아래쪽)으로 찾는다 — 모니터 · PC처럼 키 큰 소품은 가운데가 탁자 윗면보다 위라 못 찾았다
    const [w, h] = sizeT(d), cx = d.x + w / 2, cy = d.y + h * 0.85;
    let best = null, bestTop = null, span = null;
    const pieces = [];
    for (const b of list) {
      if (!b.s || b.fx || b.z) continue;
      const [bw, bh] = sizeT(b);
      for (let i = 0; i < (b.n || 1); i++) {
        const bx = b.x + i * (b.dx || 1);
        pieces.push([bx, bx + bw, b.y]);
        if (cx >= bx && cx <= bx + bw && cy >= b.y && cy <= b.y + bh && (best == null || b.y + bh > best)) { best = b.y + bh; bestTop = b.y; span = [bx, bx + bw]; }
      }
    }
    // 받침 탁자의 좌우 끝 — 이어 붙인 조각(왼끝 · 가운데 · 오른끝)까지. 자리 다시 짜기(layoutPlan)가 소품을 이 안에서만 옮긴다
    if (span) for (let grew = true; grew;) {
      grew = false;
      for (const [a0, a1, ay] of pieces) {
        if (Math.abs(ay - bestTop) > 0.05) continue;
        if (a1 >= span[0] - 0.06 && a0 < span[0] - 0.01) { span[0] = a0; grew = true; }
        if (a0 <= span[1] + 0.06 && a1 > span[1] + 0.01) { span[1] = a1; grew = true; }
      }
    }
    // 받침보다 0.005 뒤 = 받침 발밑(-0.01)보다 뒤, 받침 앞 사람보다 앞. 받침을 못 찾으면 제 발밑(audit()이 "받침 없음"으로 알린다)
    d._host = best != null;
    d._hostSpan = span;
    d._hostTop = bestTop;                                // 받침 윗면 선 — 덧그리기는 이 선 위쪽만(아래는 탁자가 사람을 가리는 자리)
    d._k = best != null ? best - 0.005 : d.y + h - 0.01;
    return d._k;
  }

  // 장식 하나 — z: wall · floor는 바로, top(탁자 위)은 탁자 바로 뒤, 그 밖은 발밑 순서로
  function placeDecor(d, ox, oy, now, sorted) {
    const n = d.n || 1;
    for (let i = 0; i < n; i++) {
      const x = ox + d.x + i * (d.dx || 1), y = oy + d.y;
      if (d.fx === 'glasswall') { sorted.push({ y: y + (d.h || 1) + 0.05, draw: () => drawFx(d.fx, x, y, now, d) }); continue; }   // 유리벽은 그 구역 앞에
      if (d.fx) { sorted.push({ y: y + 0.1, draw: () => drawFx(d.fx, x, y, now, d) }); continue; }
      const scale = d.scale || 1;
      const draw = () => {
        if (d.alpha != null) ctx.globalAlpha = d.alpha * (d.pulse ? 0.65 + 0.35 * Math.sin(now / 700) : 1);
        SP.draw(ctx, d.s, x * T, y * T, now, scale, d.frame != null ? d.frame : null);
        ctx.globalAlpha = 1;
      };
      if (d.z === 'wall' || d.z === 'floor') draw();
      else if (d.z === 'top') sorted.push({ y: oy + topKey(d), draw });       // 탁자 · 선반 위 — 받침 바로 다음(받침 앞에 선 사람보다는 먼저)
      else sorted.push({ y: spriteBottom(d.s, y) * 1 - 0.01, draw });
    }
  }

  // 바닥 — 시트 타일이거나(room.floor 이름 목록) 테마 색으로 그린 타일(room.proc.floor: 오피스 파란 타일 · 현장 콘크리트)
  function drawFloor(x0, y0, w, h, spec, salt = 0) {
    if (spec && typeof spec === 'object' && !Array.isArray(spec)) {
      const tw = spec.tile || 1, th = spec.tileH || tw;
      ctx.save();
      ctx.beginPath(); ctx.rect(x0 * T, y0 * T, w * T, h * T); ctx.clip();   // 엇갈린 타일이 구역 밖으로 넘치지 않게
      ctx.fillStyle = spec.a; ctx.fillRect(x0 * T, y0 * T, w * T, h * T);
      for (let j = 0; j < h / th; j++) for (let i = 0; i <= w / tw; i++) {
        const hsh = tileHash(i + salt, j);
        const off = spec.stagger && j % 2 ? tw / 2 : 0;
        const px0 = (x0 + i * tw - off) * T, py0 = (y0 + j * th) * T;
        if (spec.b && hsh % 3 === 0) { ctx.fillStyle = spec.b; ctx.fillRect(Math.max(px0, x0 * T), py0, tw * T, th * T); }
        if (spec.spot && hsh % 7 === 0) { ctx.fillStyle = spec.spot; ctx.fillRect(px0 + (hsh % 11), py0 + ((hsh >>> 4) % 11), 2, 2); }
        ctx.fillStyle = spec.grout || '#0003';
        ctx.fillRect(Math.max(px0, x0 * T), py0, tw * T, 1); ctx.fillRect(px0, py0, 1, th * T);
      }
      ctx.restore();
      return;
    }
    const fl = Array.isArray(spec) ? spec : [spec];
    for (let i = 0; i < w; i++) for (let j = 0; j < h; j++) SP.draw(ctx, fl[tileHash(x0 + i + salt, y0 + j) % fl.length], (x0 + i) * T, (y0 + j) * T);
  }
  const FLOOR = (RS.proc && RS.proc.floor) || RS.floor || ['floor_1'];

  function drawRoomS(r, now, sorted) {
    const z = L.zones;
    drawFloor(r.x + 1, r.y + 2, r.w - 2, r.h - 3, FLOOR);
    for (const zz of Object.values(z)) {
      if (!zz || !zz.floor) continue;
      drawFloor(r.x + zz.x, r.y + zz.y, zz.w, zz.h, (RS.proc && RS.proc[zz.floor]) || zz.floor, 3);
    }
    // 출하 라인 바닥은 조금 어둡게(모눈이면 출하장 칸만 — 왼쪽은 출하 접수대 방)
    const iz = z.infra;
    ctx.fillStyle = P.infraFloor;
    if (GRIDDEF) ctx.fillRect((r.x + iz.x) * T, (r.y + iz.y) * T, iz.w * T, iz.h * T);
    else ctx.fillRect((r.x + 1) * T, (r.y + iz.y) * T, (r.w - 2) * T, iz.h * T);
    drawCorridors(r);
    drawRoomBounds(r);
    if (GRIDDEF) drawShipArrows(r);
    drawWalls(r);
    const b = RS.banners;
    if (b) for (let i = b.from, k = 0; i < r.w - 1; i += b.every, k++) SP.draw(ctx, b.s[(k + r.x) % b.s.length], (r.x + i) * T, (r.y + 1) * T);
    for (const d of theme.sprites.decor || []) if (d.s || d.fx) placeDecor(d, r.x, r.y, now, sorted);
    // 출하 라인 — 구역마다 가구 + 상태 테두리(실패 연기 · Sync 대기 표지)
    for (const kind of ['jenkins', 'harbor', 'argocd']) {
      const ox = r.x + iz[kind].x, oy = r.y + iz.y;
      for (const d of (theme.sprites.infra_decor || {})[kind] || []) placeDecor(d, ox, oy, now, sorted);
      const st = r['st_' + kind] || 'none';
      const c = { running: P.act, success: P.ok, failed: P.bad, waiting: P.warn, none: P.muted }[st] || P.muted;
      ctx.strokeStyle = c; ctx.globalAlpha = st === 'none' ? 0.35 : 0.9; ctx.lineWidth = 1;
      // 단계 칸 — 모눈이면 이름표 줄(위 0.85칸) 아래부터 출하장 바닥까지
      const sb = GRIDDEF ? [0, 0.85, iz.stageW || 4.5, iz.h - 1.0] : [0, 0.2, 4.5, 2.6];
      ctx.strokeRect((ox + sb[0]) * T + 0.5, (oy + sb[1]) * T + 0.5, sb[2] * T, sb[3] * T);
      ctx.globalAlpha = 1;
      if (st === 'waiting') sorted.push({ y: oy + 3, draw: () => drawSign(ox + 2.2, oy + sb[1] + 0.1, '⏸') });
      if (st === 'failed') sorted.push({ y: oy + 3, draw: () => drawSmokeS(ox + 2, oy + sb[1] + 1.0, now) });
    }
  }

  // 방 경계(11-10 모눈 — 사용자: "팀장실만 바닥색이 달라 나머지는 어디가 방인지 읽히지 않는다").
  // 방마다 흐린 선, 이웃한 방은 바닥을 번갈아 조금 밝게. 선 색은 방 이름 색(테마의 팀장 · 교장 색)과 같다
  const ROOM_INK = (theme.roles && ((theme.roles.colors && theme.roles.colors.foreman) || theme.roles.foreman)) || P.label;
  function gridRooms() {
    if (!GRIDDEF) return [];
    const roles = (theme.tags && theme.tags.roles) || {};
    const out = Object.entries(roles).filter(([k]) => L.zones[k] && L.zones[k].w).map(([k, role]) => ({ key: k, role, x: L.zones[k].x, y: L.zones[k].y, w: L.zones[k].w, h: L.zones[k].h }));
    const iz = L.zones.infra;
    if (iz && iz.w) out.push({ key: 'infra', role: 'ship', x: iz.x, y: iz.y, w: iz.w, h: iz.h });
    return out;
  }
  function drawRoomBounds(r) {
    const rs = gridRooms();
    if (!rs.length) return;
    rs.forEach((q, i) => {
      if ((Math.floor(q.x / 4) + Math.floor(q.y / 5)) % 2 === 0) {          // 이웃한 방끼리 밝기가 엇갈리게(칸 자리로 정해 테마가 바뀌어도 같다)
        ctx.fillStyle = '#ffffff0d'; ctx.fillRect((r.x + q.x) * T, (r.y + q.y) * T, q.w * T, q.h * T);
      }
      ctx.save();
      ctx.strokeStyle = ROOM_INK; ctx.globalAlpha = 0.38; ctx.lineWidth = 1;
      ctx.setLineDash([3, 2]);
      ctx.strokeRect((r.x + q.x) * T + 1.5, (r.y + q.y) * T + 1.5, q.w * T - 3, q.h * T - 3);
      ctx.restore();
    });
  }
  // 출하장 바닥 화살표(11-10) — 출하 접수대 → ① · ① → ② · ② → ③. 번호는 화살표 쪽(이름표에서 뺐다)
  function shipArrows() {
    const iz = L.zones.infra, g = GRIDDEF;
    if (!iz || !g) return [];
    const y = iz.y + 1.6, w = iz.stageW || 4.5, out = [];
    let from = iz.x + 0.2;
    INFRA_STAGES.forEach((k, i) => {
      out.push({ i, x0: from, x1: iz[k].x - 0.15, y });
      from = iz[k].x + w + 0.15;
    });
    return out;
  }
  function drawShipArrows(r) {
    ctx.save();
    for (const a of shipArrows()) {
      const X0 = (r.x + a.x0) * T, X1 = (r.x + a.x1) * T, Y = (r.y + a.y) * T;
      if (X1 - X0 < 10) continue;
      ctx.globalAlpha = 0.85;
      ctx.strokeStyle = ROOM_INK; ctx.lineWidth = 2; ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(X0, Y); ctx.lineTo(X1 - 5, Y); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = ROOM_INK; ctx.beginPath(); ctx.moveTo(X1, Y); ctx.lineTo(X1 - 6, Y - 4); ctx.lineTo(X1 - 6, Y + 4); ctx.closePath(); ctx.fill();
      // 번호 — 화살표 가운데 위에 원 숫자(월드 px라 방 배율을 따른다)
      const cx = (X0 + X1) / 2, cy = Y - 6;
      ctx.fillStyle = '#000000aa'; ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = ROOM_INK; ctx.font = 'bold 8px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('①②③'[a.i], cx, cy + 0.5);
    }
    ctx.restore();
  }

  // ㅗ자 복도 — 바닥에 깐 길(마법학교 붉은 융단 · 오피스 회색 카펫 · 현장 초록 보행로 + 노란 선). 사각형이 겹친 곳은 테두리 없이 이어진다
  function drawCorridors(r) {
    const cs = RS.corridor;
    if (!cs || !CORRIDORS.length) return;
    const px = (v) => v * T, e = 1.5;
    ctx.fillStyle = cs.a;
    for (const [x, y, w, h] of CORRIDORS) ctx.fillRect(px(r.x + x), px(r.y + y), px(w), px(h));
    if (cs.b) {                                            // 결 — 융단 · 카펫은 가로 줄무늬, 보행로는 빗금
      ctx.fillStyle = cs.b;
      for (const [x, y, w, h] of CORRIDORS) {
        ctx.save(); ctx.beginPath(); ctx.rect(px(r.x + x), px(r.y + y), px(w), px(h)); ctx.clip();
        if (cs.kind === 'walkway') for (let k = -h; k < w; k += 1) { ctx.beginPath(); ctx.moveTo(px(r.x + x + k), px(r.y + y + h)); ctx.lineTo(px(r.x + x + k + h), px(r.y + y)); ctx.lineTo(px(r.x + x + k + h + 0.3), px(r.y + y)); ctx.lineTo(px(r.x + x + k + 0.3), px(r.y + y + h)); ctx.fill(); }
        else for (let k = 0.25; k < Math.max(w, h); k += 0.5) w >= h ? ctx.fillRect(px(r.x + x), px(r.y + y + (k % h)), px(w), 1) : ctx.fillRect(px(r.x + x + (k % w)), px(r.y + y), 1, px(h));
        ctx.restore();
      }
    }
    ctx.fillStyle = cs.edge;
    for (const [x, y, w, h, side] of CORRIDOR_EDGES) {   // 바깥 테두리만(사각형이 맞닿은 곳은 이어진다)
      const X = px(r.x + x), Y = px(r.y + y);
      if (side === 't') ctx.fillRect(X, Y, px(w), e); else if (side === 'b') ctx.fillRect(X, Y - e, px(w), e);
      else if (side === 'l') ctx.fillRect(X, Y, e, px(h)); else ctx.fillRect(X - e, Y, e, px(h));
    }
  }
  // 복도 바깥 테두리 — 사각형 변을 잘게 나눠 바깥쪽이 다른 복도가 아닌 구간만 남긴다(한 번만 계산)
  const CORRIDOR_EDGES = (() => {
    const inAny = (x, y) => CORRIDORS.some(([a, b, w, h]) => x > a && x < a + w && y > b && y < b + h);
    const out = [], S = 0.05, o = 0.02;
    for (const [x, y, w, h] of CORRIDORS) {
      const sides = [['t', x, y, w, 0, 0, -o], ['b', x, y + h, w, 0, 0, o], ['l', x, y, 0, h, -o, 0], ['r', x + w, y, 0, h, o, 0]];
      for (const [side, sx, sy, lw, lh, ox, oy] of sides) {
        const len = lw || lh;
        let start = null;
        for (let t = 0; t <= len + 1e-9; t += S) {
          const qx = sx + (lw ? t : 0), qy = sy + (lh ? t : 0);
          const edge = t < len && !inAny(qx + (lw ? S / 2 : 0) + ox, qy + (lh ? S / 2 : 0) + oy);
          if (edge && start == null) start = t;
          if ((!edge || t + S > len + 1e-9) && start != null) {
            const end = edge ? len : t;
            out.push(lw ? [sx + start, sy, end - start, 0, side] : [sx, sy + start, 0, end - start, side]);
            start = null;
          }
        }
      }
    }
    return out;
  })();

  // 벽 — 위 두 줄은 시트(머리 · 면), 옆 · 아래 테두리는 어두운 두께(위에서 내려다본 벽 윗면)
  function drawWalls(r) {
    const pw = RS.proc && RS.proc.wall;
    if (pw) {
      // 색으로 그린 벽 — 위 띠 + 면 + 가로줄(2dPig 벽 · 현장 철판 벽)
      ctx.fillStyle = pw.top; ctx.fillRect(r.x * T, r.y * T, r.w * T, T * 0.5);
      ctx.fillStyle = pw.face; ctx.fillRect(r.x * T, (r.y + 0.5) * T, r.w * T, T * 1.5);
      ctx.fillStyle = pw.stripe;
      for (let k = 0; k < (pw.stripes || 3); k++) ctx.fillRect(r.x * T, (r.y + 0.75 + k * 0.4) * T, r.w * T, 1);
      if (pw.rivet) { ctx.fillStyle = pw.rivet; for (let i = 0; i < r.w; i += 2) ctx.fillRect((r.x + i + 0.5) * T, (r.y + 0.6) * T, 2, 2); }
      ctx.fillStyle = pw.base || '#0004'; ctx.fillRect(r.x * T, (r.y + 2) * T - 2, r.w * T, 2);
    } else for (let i = 0; i < r.w; i++) {
      SP.draw(ctx, RS.wall_top, (r.x + i) * T, r.y * T);
      SP.draw(ctx, RS.wall, (r.x + i) * T, (r.y + 1) * T);
    }
    ctx.fillStyle = P.wallCap || '#1c1820';
    ctx.fillRect(r.x * T, (r.y + 1) * T, T * 0.6, (r.h - 1) * T);
    ctx.fillRect((r.x + r.w - 0.6) * T, (r.y + 1) * T, T * 0.6, (r.h - 1) * T);
    ctx.fillRect(r.x * T, (r.y + r.h - 0.6) * T, r.w * T, T * 0.6);
    ctx.fillStyle = P.wallEdge || '#4a4150';
    ctx.fillRect((r.x + 0.6) * T, (r.y + 2) * T, 1, (r.h - 2.6) * T);
    ctx.fillRect((r.x + r.w - 0.6) * T - 1, (r.y + 2) * T, 1, (r.h - 2.6) * T);
    ctx.fillRect((r.x + 0.6) * T, (r.y + r.h - 0.6) * T - 1, (r.w - 1.2) * T, 1);
  }

  function drawLoungeS(r, now, sorted) {
    drawFloor(r.x + 1, r.y + 2, r.w - 2, r.h - 3, FLOOR, 7);
    ctx.fillStyle = P.lounge + '88'; ctx.fillRect((r.x + 1) * T, (r.y + 2) * T, (r.w - 2) * T, (r.h - 3) * T);
    drawWalls(r);
    const z = L.zones.lounge_seats;
    for (let k = 0; k < z.cols * z.rows; k++) {
      const sx = r.x + z.x + (k % z.cols) * z.dx, sy = r.y + z.y + Math.floor(k / z.cols) * z.dy + 1;
      sorted.push({ y: sy + 0.6, draw: () => SP.draw(ctx, 'stool', (sx - 0.5) * T, (sy - 0.4) * T) });
    }
  }

  // 엔진이 그리는 빛 — 수정구 · 스테인드글라스 · 촛불(에셋에 없는 것)
  function drawFx(kind, x, y, now, d = {}) {
    const t = now / 1000;
    if (kind === 'stripes') {
      // 안전 줄무늬 — 노랑 · 검정 빗금 띠
      const w = (d.w || 1) * T, h = (d.h || 0.3) * T;
      ctx.save(); ctx.beginPath(); ctx.rect(x * T, y * T, w, h); ctx.clip();
      ctx.fillStyle = P.stripeA || '#f2c14e'; ctx.fillRect(x * T, y * T, w, h);
      ctx.fillStyle = P.stripeB || '#2b2f3a';
      for (let k = -h; k < w; k += 8) { ctx.beginPath(); ctx.moveTo(x * T + k, y * T + h); ctx.lineTo(x * T + k + 4, y * T + h); ctx.lineTo(x * T + k + 4 + h, y * T); ctx.lineTo(x * T + k + h, y * T); ctx.fill(); }
      ctx.restore();
      return;
    }
    if (kind === 'glasswall') {
      // 유리벽 — 옅은 하늘색 면 + 밝은 테두리, 위쪽 반사광(사람이 비쳐 보인다)
      const w = (d.w || 1) * T, h = (d.h || 1) * T, c = P.glassWall || '#bfe8ff';
      const door = (d.door ?? 1.5) * T, dl = x * T + (w - door) / 2;   // 아래 가운데 문(걷기 격자와 같은 자리 — 사람이 여기로 드나든다)
      ctx.globalAlpha = 0.10; ctx.fillStyle = c; ctx.fillRect(x * T, y * T, w, h);
      ctx.globalAlpha = 0.7; ctx.strokeStyle = c; ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(dl, y * T + h - 0.5); ctx.lineTo(x * T + 0.5, y * T + h - 0.5); ctx.lineTo(x * T + 0.5, y * T + 0.5);
      ctx.lineTo(x * T + w - 0.5, y * T + 0.5); ctx.lineTo(x * T + w - 0.5, y * T + h - 0.5); ctx.lineTo(dl + door, y * T + h - 0.5);
      ctx.stroke();
      ctx.fillStyle = c; ctx.fillRect(dl - 1, y * T + h - 4, 2, 4); ctx.fillRect(dl + door - 1, y * T + h - 4, 2, 4);   // 문설주
      ctx.globalAlpha = 0.35; ctx.beginPath(); ctx.moveTo(x * T + 4, y * T + h - 4); ctx.lineTo(x * T + 14, y * T + h - 14); ctx.stroke();
      ctx.globalAlpha = 1;
      return;
    }
    if (kind === 'orb') {
      const p = 0.6 + 0.4 * Math.sin(t * 2.2);
      glow(x * T, y * T, 10 + p * 4, P.orb, 0.35 * p);
      ctx.fillStyle = '#d8f6ff'; ctx.beginPath(); ctx.arc(x * T, y * T, 3, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = P.orb; ctx.beginPath(); ctx.arc(x * T - 1, y * T - 1, 1.2, 0, Math.PI * 2); ctx.fill();
    } else if (kind === 'glass') {
      const cols = [P.glass1, P.glass2, P.glass3];
      for (let i = 0; i < 3; i++) {
        ctx.globalAlpha = 0.16 + 0.06 * Math.sin(t + i);
        ctx.fillStyle = cols[i]; ctx.fillRect((x - 0.6 + i * 0.4) * T, y * T, 0.4 * T, 1.4 * T);
      }
      ctx.globalAlpha = 1;
    } else if (kind === 'candle') {
      const f = Math.sin(t * 9 + x * 3) > 0 ? 1 : 0;
      glow(x * T, (y - 0.15) * T, 9, P.candle, 0.28);
      ctx.fillStyle = '#efe6cf'; ctx.fillRect(Math.round(x * T) - 1, Math.round(y * T) - 2, 2, 4);
      ctx.fillStyle = P.candle; ctx.fillRect(Math.round(x * T) - 1, Math.round(y * T) - 4 - f, 2, 2);
    }
  }
  function glow(px, py, rad, color, alpha) {
    const g = ctx.createRadialGradient(px, py, 0, px, py, rad);
    g.addColorStop(0, color); g.addColorStop(1, color + '00');
    ctx.globalAlpha = alpha; ctx.fillStyle = g; ctx.fillRect(px - rad, py - rad, rad * 2, rad * 2); ctx.globalAlpha = 1;
  }
  function drawSmokeS(tx, ty, now) {
    if (SP.has('fx_smoke')) SP.draw(ctx, 'fx_smoke', tx * T - 16, ty * T - 30, now);
    else drawSmoke(tx, ty, now);
  }

  // 사람 — Ninja 시트. 걷기는 진짜 프레임, 앉기는 탁자가 가리고, 자기 · 들기 · 석화 · 유령은 엔진 흉내
  // 소환(마법진이 밝아지고 불꽃) · 퇴장(연기) — 10c
  function drawSummonsPuffs(now) {
    for (let i = summons.length - 1; i >= 0; i--) {
      const s = summons[i], e = now - s.t0;
      if (e > 500) { summons.splice(i, 1); continue; }
      if (e < -600) continue;
      const k = 1 - Math.abs(e + 50) / 550;
      if (SP && SP.has('fx_circle')) {
        ctx.globalAlpha = Math.max(0, k);
        SP.draw(ctx, 'fx_circle', s.x * T - 16, s.y * T - 16, now);
        if (SP.has('fx_spark')) SP.draw(ctx, 'fx_spark', s.x * T - 15, s.y * T - 30, now);
        ctx.globalAlpha = 1;
      } else {
        ctx.strokeStyle = P.act; ctx.globalAlpha = Math.max(0, k); ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(s.x * T, s.y * T, 6 + (1 - k) * 10, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1;
      }
    }
    for (let i = puffs.length - 1; i >= 0; i--) {
      const p = puffs[i], e = now - p.t0;
      if (e > 600) { puffs.splice(i, 1); continue; }
      if (e < 0) continue;
      if (SP && SP.has('fx_smoke')) SP.draw(ctx, 'fx_smoke', p.x * T - 16, p.y * T - 26, now, 1, Math.floor(e / 100));
      else drawSmoke(p.x, p.y - 0.3, now);
    }
  }

  // "위에 앉거나 눕는" 가구 — 소파 · 빈백 · 간이침대 · 벤치 · 그루터기 · 의자. 자리 점이 이 가구 칸 안이면 사람은 그 가구
  // 바로 다음에 그린다(가구 위에 앉은/누운 모습). 탁자 · 책상 · 작업대는 아니다 — 거기선 탁자가 다리를 가리는 지금 모습이 맞다.
  // (11-05 — 발 위치 순서로는 소파 · 침대 · 의자 등받이가 나중에 그려져 사람이 뒤로 숨었다: 오피스 라운지 소파, 현장 함바 간이침대,
  //  마법학교 책상 · 대강당 아래 줄 — 등을 보이고 의자에 앉은 사람의 몸 절반을 등받이가 가렸다)
  const SIT_ON = /(^|_)(sofa|couch|bean|cot|bed|bench|stump|stool|hammock|futon|chair)(_|\d|$)/i;   // 낱말 단위 — workbench(작업대)는 아니다
  function seatFurniture(a) {
    const key = `${a.room}:${a.tx}:${a.ty}`;
    if (a._bedKey === key) return a._bed;
    a._bedKey = key;
    const room = world.rooms.find((r) => r.name === a.room);
    a._bed = null;
    if (!room) return null;
    const px = a.tx - room.x, py = a.ty - room.y;
    for (const r of decorRects('room')) {
      if (r.top || !SIT_ON.test(r.s) || px < r.x || px > r.x + r.w || py < r.y || py > r.y + r.h) continue;
      if (!a._bed || r.key > a._bed.key - room.y) a._bed = { s: r.s, lx: room.x + r.x, cx: room.x + r.x + r.w / 2, cy: room.y + r.y + r.h * 0.5, key: room.y + r.key + 0.002 };
    }
    return a._bed;
  }
  const lieBed = seatFurniture;
  // 엎드려 자기(sleep) — 탁자 뒤에 앉아 머리를 탁자 위에 댄다. 탁자가 나중에 그려져 머리까지 가렸다(11-05 마법학교 대강당).
  // 앞의 탁자를 찾아, 탁자를 그린 뒤 머리 쪽(탁자 윗면 + 0.55칸 위쪽)만 한 번 더 그린다
  function sleepTable(a) {
    const key = `s:${a.room}:${a.tx}:${a.ty}`;
    if (a._tblKey === key) return a._tbl;
    a._tblKey = key; a._tbl = null;
    const room = world.rooms.find((r) => r.name === a.room);
    if (!room) return null;
    const t = tableAt(a.tx - room.x, a.ty - room.y);
    if (t) a._tbl = { key: room.y + t.key + 0.003, top: room.y + t.y, clipBottom: room.y + t.y + 0.55,
                      lx: room.x + t.x, rx: room.x + t.x + t.w, h: t.h };
    return a._tbl;
  }
  // 자리(방 좌표) 바로 앞 탁자 — 자는 사람 머리 · 놓는 소품이 올라간다. 위에 앉는 가구 · 탁자 위 소품은 아니다
  function tableAt(px, py) {
    let best = null;
    for (const r of decorRects('room')) {
      if (r.top || SIT_ON.test(r.s) || px < r.x || px > r.x + r.w || r.y < py - 0.8 || r.y > py + 0.6) continue;
      if (!best || r.y < best.y) best = r;
    }
    return best;
  }
  function drawActorS(a, now) {
    if (a.kind === 'mini') {                                  // 부모의 축소판 — 늘 걷는 그림(돌아다닌다)
      const dir = a.dir || 'down';
      const c = SP.charFrame(a.char, 'walk', dir, Math.floor(a.phase * 0.8) % 4, null, ROLE_MODE === 'robe' ? roleColor(a.role) : null);
      if (!c) return;
      const w = Math.round(c.width * MINI), h = Math.round(c.height * MINI);
      const bob = c.static ? Math.round(Math.abs(Math.sin(a.phase * 1.3)) * 1.5) : 0;
      ctx.drawImage(c.img, Math.round(a.x * T - w / 2), Math.round(a.y * T - h) - bob, w, h);
      return;
    }
    const act = a.act || {};
    const anim = a.moving ? 'walk' : (act.anim || 'stand');
    const dir = a.moving ? (a.dir || 'down') : (a.face || 'down');
    const mode = act.fx === 'stone' || act.fx === 'frozen' ? 'stone' : act.fx === 'ghost' ? 'ghost' : null;
    const walking = a.moving || anim === 'work';
    const f = walking && !mode ? Math.floor(a.phase * 0.8) % 4 : 0;
    const c = SP.charFrame(a.char, walking ? 'walk' : 'idle', dir, f, mode, mode || ROLE_MODE !== 'robe' ? null : roleColor(a.role));
    if (!c) return;
    const K = c.scale || 1;                                                      // 캐릭터 배율(11-09, sprites.js charFrame) — 흔들림 · 표시도 같이
    let px = Math.round(a.x * T - c.width / 2), py = Math.round(a.y * T - c.height);
    a.drawH = c.height;
    if (c.static && walking && !mode) py -= Math.round(Math.abs(Math.sin(a.phase * 1.3)) * 2 * K);   // 정면 한 장 — 출렁여서 걷는 흉내
    if (anim === 'sleep') py += Math.round(4 * K);                               // 엎드려 잔다 — 머리를 탁자 위로
    if (mode === 'ghost') py += Math.round((Math.sin(a.phase * 0.6) * 1.5 - 2) * K);  // 유령은 떠 있다
    ctx.globalAlpha = act.alpha != null ? act.alpha : 1;
    if (anim === 'lie' && !a.moving) {
      // 간이침대에 눕기 — 그림을 왼쪽으로 90도 눕힌다(머리가 왼쪽 = 베개 쪽). 자리 점이 아니라 그 아래 침대의 가운데에
      // 몸을 맞춘다(11-05 — 전에는 자리 점에 그려 몸이 침대 오른쪽 · 위로 반쯤 벗어났다). 그리는 순서는 lieBed().key
      const bed = lieBed(a);
      // 누우면 그림 높이가 가로 길이 — 머리(왼쪽 끝)가 베개(침대 왼쪽 끝 + 0.25칸)에 닿게
      const cx = bed ? Math.min(bed.cx, bed.lx + 0.25 + c.height / T / 2) : a.x, cy = bed ? bed.cy : a.y - 5 / T;
      ctx.save();
      ctx.translate(Math.round(cx * T), Math.round(cy * T));
      ctx.rotate(-Math.PI / 2);
      ctx.drawImage(c.img, -c.width / 2, -c.height / 2, c.width, c.height);
      ctx.restore();
      ctx.globalAlpha = 1;
      a.drawH = Math.round(10 * K);
      return;
    }
    ctx.drawImage(c.img, px, py, c.width, c.height);
    if (!a.moving) BODIES.set(a.key, { a, box: [px, py, c.width, c.height] });   // 이름표가 사람을 덮나(labelAudit · drawName, 11-10)
    // 역할 표시 — 오피스는 사원증 끈, 현장은 안전모 색(마법학교는 위에서 로브 색을 바꿨다). 원본 픽셀 단위로 그리고 K배
    const rc = !mode && roleColor(a.role);
    if (rc && ROLE_MODE === 'lanyard') {
      ctx.save(); ctx.translate(Math.round(a.x * T), py + Math.round(c.height * 0.42)); ctx.scale(K, K);
      ctx.fillStyle = rc;
      for (let k = 0; k < 4; k++) { ctx.fillRect(-3 + Math.floor(k / 1.4), k, 1, 1); ctx.fillRect(2 - Math.floor(k / 1.4), k, 1, 1); }
      ctx.fillStyle = '#ffffff'; ctx.fillRect(-1, 4, 3, 3); ctx.fillStyle = rc; ctx.fillRect(-1, 4, 3, 1);
      ctx.restore();
    } else if (rc && ROLE_MODE === 'helmet') {
      const bw = c.width / K;                                                    // 원본 폭
      const hw = Math.round(bw * 0.62);
      ctx.save(); ctx.translate(Math.round(a.x * T), py); ctx.scale(K, K);
      ctx.fillStyle = rc; ctx.fillRect(-hw / 2, -1, hw, 3); ctx.fillRect(-hw / 2 - 1, 2, hw + 2, 1);
      ctx.fillStyle = '#ffffff55'; ctx.fillRect(-hw / 2 + 1, -1, 2, 1);
      ctx.restore();
    }
    ctx.globalAlpha = 1;
  }

  // ── 소품은 들지 않고 놓는다(11-05 사용자 지시) ─────────────────────────────────────────────
  // 전에는 테마마다 발밑 기준 dx · dy와 원래 크기로 손에 들려, 16px 캐릭터 앞에 16px 책 · 깃펜 · 플라스크가 얼굴 높이에 얹혀
  // 사람이 안 보였다(마법학교 서고). 이제 사람은 서 있거나 앉아 있기만 하고, 그 동작의 소품은 곁에 놓는다:
  //  · 앞에 탁자가 있으면(tableAt — 자는 사람 머리를 얹는 그 탁자) 탁자 윗면, 사람 손 쪽으로 조금
  //  · 없으면 사람 옆 바닥(손 쪽 발치)
  //  · 크기: 폭 ≤ 캐릭터 폭의 절반, 높이 ≤ 캐릭터 키의 55%(16px 캐릭터 → 8 × 9px). 비율은 지킨다
  //  · 얼굴 칸(그림 위쪽 FACE_H, 가운데 FACE_W 폭)과 겹치면 손 쪽 바깥으로 민다 — 얼굴은 늘 보인다
  // 테마 props에는 그림(s) · 손 쪽(dx 부호, 양수 오른쪽) · shake(플라스크 흔들기 등) · fx(소품 위 효과)만 둔다
  const FACE_H = 0.5, FACE_W = 0.64;
  function faceBox(cw, ch, cx, foot) {
    const top = foot - ch;
    return [cx - Math.ceil(cw * FACE_W / 2), top, Math.ceil(cw * FACE_W), Math.ceil(ch * FACE_H)];
  }
  // tbl: { top(px, 탁자 그림 위 끝), h(px), lx, rx(px) } | null. 돌려주는 값은 px 칸 + 어디에 놓였는지
  function placeProp(prop, cw, ch, cx, foot, tbl, shake = 0) {
    const [sw, sh] = SP.size(prop.s);
    const k = Math.min(1, Math.floor(cw * 0.5) / sw, Math.floor(ch * 0.55) / sh);
    const w = Math.max(2, Math.round(sw * k)), h = Math.max(2, Math.round(sh * k));
    const side = (prop.dx || 0) < 0 ? -1 : 1;
    let x, y, on;
    if (tbl) {
      on = 'table';
      x = cx - Math.round(w / 2) + side * Math.round(cw * 0.35);
      x = Math.max(tbl.lx + 1, Math.min(x, tbl.rx - w - 1));              // 탁자 밖으로 삐져나가지 않게
      y = tbl.top + Math.min(6, Math.round(tbl.h * 0.45)) - h;            // 바닥이 윗면 위에 닿게
    } else {
      on = 'floor';
      x = side > 0 ? cx + Math.floor(cw / 2) - 1 : cx - Math.ceil(cw / 2) - w + 1;   // 발치 옆
      y = foot - h;
    }
    x += shake;                                                            // 흔들기를 먼저 — 그다음 얼굴 검사
    const [fx, fy, fw, fh] = faceBox(cw, ch, cx, foot);
    if (areaOf([x, y, w, h], [fx, fy, fw, fh]) > 0) x = side > 0 ? fx + fw : fx - w;   // 얼굴을 덮으면 옆으로
    return { x, y, w, h, on, k: +k.toFixed(2) };
  }
  function propOf(a) {
    if (a.kind === 'mini' || a.moving) return null;
    const act = a.act || {};
    if (act.fx === 'stone' || act.fx === 'frozen' || act.fx === 'ghost') return null;
    return (theme.sprites.props || {})[act.anim] || null;
  }
  // 놓인 소품 그리기 — 그리기 목록에서 탁자 위면 그 탁자 바로 다음, 바닥이면 사람 바로 다음 순서
  function drawPropS(a, prop, tbl, now) {
    const c = SP.charFrame(a.char, 'idle', a.face || 'down', 0, null, null);
    if (!c) return;
    const sh = prop.shake ? Math.round(Math.sin(a.phase * 6) * prop.shake) : 0;
    const t = tbl && { top: tbl.top * T, h: tbl.h * T, lx: tbl.lx * T, rx: tbl.rx * T };
    const r = placeProp(prop, c.width, c.height, Math.round(a.x * T), Math.round(a.y * T), t, sh);
    ctx.globalAlpha = (a.act && a.act.alpha != null) ? a.act.alpha : 1;
    const pc = SP.scaled(prop.s, r.w, r.h, now);
    if (pc) ctx.drawImage(pc, r.x - pc.pad, r.y - pc.pad);
    if (prop.fx) { const [fw, fh] = SP.size(prop.fx); SP.draw(ctx, prop.fx, r.x + r.w / 2 - fw / 2, r.y - fh / 2 - 2, now); }
    ctx.globalAlpha = 1;
  }
  // 소품 점검 — ① 모든 테마 캐릭터 × 모든 소품을 바닥 · 탁자(tableAt이 잡는 가장 높은 탁자) 두 경우로 놓아 얼굴 칸과 겹치는지 · 너무 큰지
  // ② 모든 자리(standSpots)의 실제 앞 탁자 위에 놓아 얼굴 칸과 겹치는지, 자리마다 어디에 놓이는지(탁자 / 바닥).
  // 화면 시험이 window.office.propAudit()으로 부른다. issues가 빈 배열이면 통과
  function propAudit() {
    const issues = [], props = theme.sprites.props || {};
    const chars = [...new Set([...(CH.pool || []), CH.foreman, ...Object.values(CH.infra || {})].filter(Boolean))];
    for (const ch of chars) {
      const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
      if (!c) { issues.push({ char: ch, problem: '캐릭터 그림 없음' }); continue; }
      const face = faceBox(c.width, c.height, 0, c.height);
      const high = { top: c.height - Math.round(0.8 * T), h: T, lx: -T, rx: T };       // tableAt이 잡는 가장 높은 탁자
      for (const [anim, prop] of Object.entries(props)) {
        if (anim.startsWith('_')) continue;
        if (!SP.has(prop.s)) { issues.push({ char: ch, anim, problem: '소품 그림 없음', s: prop.s }); continue; }
        for (const tbl of [null, high]) for (const sh of [-(prop.shake || 0), prop.shake || 0]) {
          const r = placeProp(prop, c.width, c.height, 0, c.height, tbl, sh);
          const ov = areaOf([r.x, r.y, r.w, r.h], face);
          if (ov > 0) issues.push({ char: ch, anim, s: prop.s, on: r.on, problem: '얼굴 가림', px: ov });
          if (r.w > c.width / 2 + 0.5 || r.h > c.height * 0.55 + 0.5) issues.push({ char: ch, anim, s: prop.s, problem: '너무 큼', size: [r.w, r.h], char_size: [c.width, c.height] });
        }
      }
    }
    // 실제 자리 — 앞 탁자가 잡히는 자리마다 모든 캐릭터 × 소품을 그 탁자 위에 놓아 본다
    const spots = standSpots().map((p) => ({ ...p, t: tableAt(p.x, p.y) }));
    for (const p of spots) {
      if (!p.t) continue;
      const tb = { top: p.t.y * T, h: p.t.h * T, lx: p.t.x * T, rx: (p.t.x + p.t.w) * T };
      for (const ch of chars) {
        const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
        if (!c) continue;
        const cx = Math.round(p.x * T), foot = Math.round(p.y * T), face = faceBox(c.width, c.height, cx, foot);
        for (const [anim, prop] of Object.entries(props)) {
          if (anim.startsWith('_') || !SP.has(prop.s)) continue;
          const r = placeProp(prop, c.width, c.height, cx, foot, tb);
          const ov = areaOf([r.x, r.y, r.w, r.h], face);
          if (ov > 0) issues.push({ where: p.where, char: ch, anim, s: prop.s, on: 'table', problem: '얼굴 가림', px: ov });
        }
      }
    }
    return { issues: issues.filter((x, i, a) => a.findIndex((y) => JSON.stringify(y) === JSON.stringify(x)) === i),
             spots: spots.map((p) => ({ where: p.where, on: p.t ? 'table' : 'floor', by: p.t ? p.t.s : null })) };
  }
  // 소품 견본(디버그) — 줄 = 소품 동작, 칸 = 캐릭터. 실제 그리기와 같은 placeProp · scaled로 그려 PNG data URL을 돌려준다.
  // 칸마다 왼쪽은 바닥에 놓은 것, 오른쪽은 앞 탁자(회색 띠) 위에 놓은 것. 얼굴 칸은 빨간 테두리(showFace)
  function propSheet(zoom = 6, showFace = true) {
    const props = Object.entries(theme.sprites.props || {}).filter(([k]) => !k.startsWith('_'));
    const chars = [...new Set([...(CH.pool || []), CH.foreman].filter(Boolean))].slice(0, 6);
    const cell = 56, lab = 46;
    const cv = document.createElement('canvas');
    cv.width = (lab + chars.length * cell) * zoom; cv.height = props.length * cell * zoom;
    const g = cv.getContext('2d');
    g.imageSmoothingEnabled = false; g.fillStyle = '#d8d4c8'; g.fillRect(0, 0, cv.width, cv.height);
    g.scale(zoom, zoom);
    props.forEach(([anim, prop], r) => {
      g.fillStyle = '#222'; g.font = '6px monospace'; g.textBaseline = 'middle'; g.fillText(anim, 2, r * cell + cell / 2);
      chars.forEach((ch, i) => {
        const c = SP.charFrame(ch, 'idle', 'down', 0, null, null);
        if (!c) return;
        const foot = r * cell + cell - 6;
        for (const [j, withTbl] of [[0, false], [1, true]]) {
          const cx = Math.round(lab + i * cell + 14 + j * 26);
          g.drawImage(c.img, Math.round(cx - c.width / 2), foot - c.height, c.width, c.height);
          let tbl = null;
          if (withTbl) {                                                  // 사람 바로 앞 탁자 — 윗면이 몸 아래 40%(layoutAudit이 허용하는 높이). 사람보다 나중에
            tbl = { top: foot - Math.round(c.height * 0.4), h: T, lx: cx - 12, rx: cx + 12 };
            g.fillStyle = '#8a7a66'; g.fillRect(tbl.lx, tbl.top, 24, T);
            g.fillStyle = '#a8977f'; g.fillRect(tbl.lx, tbl.top, 24, 6);
          }
          const pr = placeProp(prop, c.width, c.height, cx, foot, tbl);
          const pc = SP.scaled(prop.s, pr.w, pr.h, 0);
          if (pc) g.drawImage(pc, pr.x - pc.pad, pr.y - pc.pad);
          if (showFace) { const f = faceBox(c.width, c.height, cx, foot); g.strokeStyle = '#e0303088'; g.lineWidth = 1 / zoom; g.strokeRect(f[0], f[1], f[2], f[3]); }
        }
      });
    });
    return cv.toDataURL('image/png');
  }

  // 압축 알림(11-05) — 2번째 압축부터 머리 오른쪽에 📦(4번째부터 빨간 테두리). 패널 띠의 [나중에]로 숨긴 것은 같이 숨긴다
  function drawCompactMark(a, x, y) {
    const c = a.kind === 'session' && a.s && a.s.compact;
    if (!c || !c.level) return;
    if (window.foremanCompactSnoozed && window.foremanCompactSnoozed(a.s.id, c.count)) return;
    if (c.level === 'late') { ctx.fillStyle = P.bad; ctx.beginPath(); ctx.arc(x + 4, y - 3, 6, 0, Math.PI * 2); ctx.fill(); }
    ctx.font = '8px "Noto Color Emoji", "Apple Color Emoji", sans-serif'; ctx.textAlign = 'left';
    ctx.fillText('📦', x, y);
  }

  // 사람 위에 뜨는 것 — 말풍선(이모트) · 연기 · 자는 Zz · 일꾼 수 · 선택 표시(가구에 가리지 않게 마지막에)
  function drawOverlay(a, now) {
    const act = a.act || {};
    const x = a.x * T, top = a.y * T - (a.drawH || 16);
    drawHeat(a, now);
    if (act.fx === 'smoke') drawSmokeS(a.x, a.y - 0.6, now);
    drawCompactMark(a, x + 7, top + 4);
    if (act.bubble) {
      const e = 'e_' + act.bubble;
      if (SP.has(e)) SP.draw(ctx, e, x - 7, top - 13 - Math.round(Math.abs(Math.sin(now / 300)) * 2), now);
      else drawBubble(x, top - 4, act.bubble, P.warn);
    }
    if (!a.moving && act.anim === 'sleep' && !act.flag) {
      const t = (now / 1400 + (a.phase % 1)) % 1;
      ctx.globalAlpha = 1 - t; ctx.fillStyle = P.zz; ctx.font = 'bold 7px ui-monospace, monospace'; ctx.textAlign = 'left';
      ctx.fillText('z', x + 5 + t * 4, top + 2 - t * 8); ctx.globalAlpha = 1;
    }
    if (!a.moving && act.anim === 'wait' && !act.flag) {                       // 기다림 — 책상에 서서 "…"이 차오른다
      drawBubble(x, top - 3, '·'.repeat(1 + Math.floor(now / 500) % 3).padEnd(3, ' '), P.act, 7);
    }
    if (a.kind === 'scribe' && scribeBubble(a)) {                                // 서기 — 할 일 N(누르면 목록), 쌓이면 "정리할까요?"
      placeBubble(a, x, top, scribeBubble(a), P.warn, todoPx() / cam.s);
    }
    if (coderBubbleOf(a) && !(act.anim === 'wait' && !act.flag) && !act.bubble) {   // 코더 — 맡길 일 N · 합치기 기다림(누르면 목록)
      placeBubble(a, x, top, coderBubbleOf(a), P.warn, todoPx() / cam.s);
    }
    if (a.kind === 'foreman' && a.fm && a.fm.pending.length) {                   // 디스패처 — [시작]을 기다리는 자동 제안(누르면 그 계획)
      placeBubble(a, x, top, `시작할 일 ${a.fm.pending.length}`, P.warn, todoPx() / cam.s);
    }
    if (a.kind === 'courier') {                                                  // 출하 대기 N(11-10 — 전엔 이름표 칸을 따로 골랐다. 호버는 drawZoneTags)
      const rm = world.rooms.find((q) => q.name === a.room), q = rm && rm.courier && rm.courier.queue;
      if (q && q.length) placeBubble(a, x, top, `대기 ${q.length}`, P.warn, todoPx() / cam.s);
    }
    if (a.subHidden) drawBubble(x + 11, top + 4, `+${a.subHidden}`, P.act, 7);      // 10명 넘는 서브에이전트는 접는다
    if (a.key === selected) { const h = (a.drawH || 16) + 4, w = Math.round(h * 0.9); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - w / 2, top - 2, w, h); }
  }

  // 이름표를 피하는 말풍선(11-06 — 서기실에서 "할 일 2"가 구역 이름표를 덮었다). 이름표는 사람 위 글보다 나중에 화면 좌표로 그려서,
  // 지난 프레임의 이름표 칸(HITS)을 월드 픽셀로 바꿔 머리 위 → 오른쪽 → 왼쪽 → 발밑 순으로 안 겹치는 첫 자리에 둔다(없으면 가장 덜 겹치는 곳)
  const BUBBLES = new Map();
  // 서기 "할 일 N"은 화면 px로 고정(11-06 — 월드 8px이 줌 2.5~3배로 20px 넘게 커져 다른 글씨보다 훨씬 컸다)
  const todoPx = () => tpx(12);                  // 11-10 방 안에서는 방 배율을 따른다(감독실은 글씨 배율)
  // 서기 말풍선(11-09) — 받은 할 일이 쌓이면(config/scribe.toml [nudge]) "정리할까요?" — 누르면 「나중에 할 일 정리」를 고른 창(세션은 사람이)
  const scribeBubble = (a) => (a.todo && a.todo.nudge ? '정리할까요?' : a.todo && a.todo.items && a.todo.items.length ? `문서 할 일 ${a.todo.items.length}` : null);
  // 코더 말풍선(11-09) — 쉬는 상주 코더, 또는 상주 코더의 몸을 쓰는 세션. 임시 일꾼에는 띄우지 않는다
  const coderBubbleOf = (a) => ((a.kind === 'coder' || (a.kind === 'session' && a.resident)) ? coderBubble(a.jobs) : null);
  function tagBoxesW() {
    const toW = (sx, sy) => [((sx - W / 2) / cam.s + cam.x), ((sy - H / 2) / cam.s + cam.y)];
    return HITS.filter((h) => h.zone).map((h) => { const [x0, y0] = toW(h.x, h.y), [x1, y1] = toW(h.x + h.w, h.y + h.h); return [x0, y0, x1 - x0, y1 - y0]; });
  }
  function placeBubble(a, x, top, text, color, size) {
    ctx.font = `bold ${size}px ui-monospace, monospace`;
    const pad = size * 0.25, w = Math.max(size, ctx.measureText(text).width + size * 0.7), h = size + 2 * pad, feet = a.y * T;
    // 11-10 옆 자리를 실제 몸 폭으로(전에는 ±8px — 1.5배 캐릭터는 몸 반폭이 그보다 커서 옆 말풍선이 몸을 덮었다), 사람 몸 · 이름도 피한다
    const ob = BODIES.get(a.key), half = ob ? ob.box[2] * 0.35 : 8;
    const spots = [[x, top - 3], [x, top - 3 - h - 2], [x + half + 3 + w / 2, top + 8], [x - half - 3 - w / 2, top + 8], [x, feet + size + 5]];
    const toW = (r) => [(r[0] - W / 2) / cam.s + cam.x, (r[1] - H / 2) / cam.s + cam.y, r[2] / cam.s, r[3] / cam.s];
    const boxes = [...tagBoxesW(), ...[...BODIES.values()].map(({ box: b }) => [b[0] + b[2] * 0.15, b[1] + b[3] * 0.04, b[2] * 0.7, b[3] * 0.94]),
                   ...NAMES.filter((m) => m.key !== a.key).map((m) => toW(m.rect))];
    let best = null;
    for (const [bx, by] of spots) {
      const r = [bx - w / 2, by - size - pad, w, h], cover = boxes.reduce((s, b) => s + areaOf(r, b), 0);
      if (!best || cover < best.cover) best = { bx, by, r, cover };
      if (!cover) break;
    }
    BUBBLES.set(a.key, { room: a.room, text, rect: best.r.map((v) => Math.round(v)), cover: Math.round(best.cover) });
    drawBubble(best.bx, best.by, text, color, size);
  }
  function bubbleAudit() {                       // 이름표에 걸친 말풍선 — tools/screen.py --eval 'window.office.bubbleAudit()'
    return [...BUBBLES.entries()].filter(([k, b]) => b.cover > 0 && actors.has(k)).map(([key, b]) => ({ key, ...b }));
  }
  // size는 월드 px(줌만큼 커진다). 여백은 글씨에 비례 — size 9에서 예전(위아래 2 · 좌우 3)과 같다
  function drawBubble(x, y, text, color, size = 9) {
    ctx.font = `bold ${size}px ui-monospace, monospace`;
    const pad = size * 0.25, w = Math.max(size, ctx.measureText(text).width + size * 0.7);
    ctx.fillStyle = color; ctx.fillRect(x - w / 2, y - size - pad, w, size + 2 * pad);
    ctx.fillStyle = '#111'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y - size / 2);
  }
  function drawSign(tx, ty, ch) { drawBubble(tx * T, ty * T, ch, P.warn, 10); }
  // 사용량 열기(11-08, docs/15 6절) — 지난 30분 환산액 상위 셋. 세기는 달러/시간에 비례($20/시간이면 가득).
  // 오피스: 노트북에서 김 · 마법학교: 마력 오라 · 현장: 엔진 아지랑이 · 도형: 주황 고리. 실패 연기(회색)와 섞이지 않게 색을 따로 쓴다
  function drawHeat(a, now) {
    if (a.kind !== 'session' || !a.s) return;
    const r = hotOf.get(a.s.id);
    if (!r) return;
    // 세기 0.6~1 — 0.3에서는 바닥색에 묻혀 보이지 않았다(11-08 확대 사진). 효과는 몸통 둘레 · 머리 위(발밑은 이름표가 가린다)
    const k = Math.max(0.6, Math.min(1, r / 20)), x = a.x * T, mid = a.y * T - 9, head = a.y * T - 18, t = now / 1000;
    const kind = theme.name;
    if (kind === 'magic') {
      glow(x, mid, 16 + 4 * Math.sin(t * 3), '#a87bff', 0.35 * k);
      for (let i = 0; i < 2; i++) {                               // 몸을 감싸며 퍼지는 마력 고리
        const p = (t * 0.8 + i / 2) % 1;
        ctx.globalAlpha = 0.8 * k * (1 - p); ctx.strokeStyle = '#c9a6ff'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.ellipse(x, mid, 8 + p * 7, 11 + p * 7, 0, 0, Math.PI * 2); ctx.stroke();
      }
      for (let i = 0; i < 4; i++) {                               // 위로 오르는 빛 알갱이
        const p = (t * 0.7 + i / 4) % 1;
        ctx.globalAlpha = k * (1 - p); ctx.fillStyle = '#efe4ff';
        ctx.fillRect(x - 8 + i * 5 + Math.sin(p * 6 + i) * 2, head - p * 18, 2, 2);
      }
    } else if (kind === 'site') {
      glow(x, head + 2, 14, '#ff8a1f', 0.3 * k);
      ctx.strokeStyle = '#ffb04a'; ctx.lineWidth = 1.6;
      for (let i = 0; i < 3; i++) {                               // 엔진 아지랑이 — 머리 위로 일렁이는 선
        const p = (t * 0.9 + i / 3) % 1, yy = head - 2 - p * 16;
        ctx.globalAlpha = 0.9 * k * (1 - p);
        ctx.beginPath();
        for (let j = -7; j <= 7; j += 2) ctx.lineTo(x + j, yy + Math.sin(j * 0.9 + t * 8 + i) * 1.8);
        ctx.stroke();
      }
    } else if (kind === 'office') {
      for (let i = 0; i < 4; i++) {                               // 노트북 김 — 머리 옆으로 오르는 김(어두운 테두리로 밝은 바닥에서도 보이게)
        const p = (t * 0.7 + i / 4) % 1, px = x + 7 + Math.sin(p * 6 + i) * 3, py = head + 4 - p * 20, rad = 2 + p * 4;
        ctx.globalAlpha = 0.85 * k * (1 - p);
        ctx.fillStyle = '#f4f6fa'; ctx.strokeStyle = '#5b6170'; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.arc(px, py, rad, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
    } else {
      const p = (t * 1.2) % 1;
      ctx.globalAlpha = 0.8 * k * (1 - p); ctx.strokeStyle = '#ff9f1c'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, mid, 10 + p * 7, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  // 현황판 경고등 — 한도(추정) 90% 넘으면 판 오른쪽 위에서 붉게 깜빡(95% 넘으면 빠르게). 못 읽으면 노란 등
  // 감독실 현황판 오른쪽 위 경고등 — 빨강: 사용량 90% 이상, 노랑: 사용량을 못 읽음. 호버 이유는 화면 좌표 단계에서(LAMP → HITS)
  let LAMP = null;
  function drawUsageLamp(now) {
    LAMP = null;
    if (!usage) return;
    const max = usageMax(), bad = usage.failed || (usage.reading && !usage.reading.ok);
    if (max < 90 && !bad) return;
    const b = HQ.board || {}, q = world.hq;
    const x = (q.x + (b.x ?? 3) + (b.w ?? 22) - 0.5) * T, y = (q.y + (b.y ?? 0.4) - 0.05) * T;
    LAMP = { x, y, max, bad: !!bad };
    const col = max >= 90 ? '#ff3b30' : '#ffcc00';
    const on = 0.55 + 0.45 * Math.sin(now / (max >= 95 ? 150 : 400));
    glow(x, y, 30 * on, col, 0.6 * on);
    ctx.fillStyle = col; ctx.globalAlpha = 0.6 + 0.4 * on;
    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = '#222'; ctx.fillRect(x - 4.5, y + 4.5, 9, 3);
  }
  function drawSmoke(tx, ty, now) {
    for (let i = 0; i < 3; i++) {
      const t = ((now / 900) + i / 3) % 1;
      ctx.globalAlpha = 0.6 * (1 - t);
      ctx.fillStyle = '#8a8f99';
      ctx.beginPath(); ctx.arc(tx * T + Math.sin(t * 6 + i) * 3, ty * T - t * 18, 3 + t * 5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // ── 구역 이름표(화면 좌표 — 줌과 상관없이 작고 선명하게) ─────
  const TAG0 = (theme.tags && theme.tags.style) || { bg: '#000000cc', fg: '#ffffff', border: '#ffffff55', font: '600 14px system-ui, sans-serif', kind: 'sign' };
  // font는 읽을 때마다 글씨 배율을 곱한다(11-09) — 이름표 그리기 · 폭 재기 · 자리 점검이 모두 같은 크기를 본다
  const TAG = { ...TAG0, get font() { return sizeFont(TAG0.font); } };
  themeTips(theme.tags && theme.tags.style);     // 툴팁 색 · 글꼴도 이름표를 따른다(양피지 · 사인판 · 안전 표지판). 구조 · 크기 · 지연은 같다
  attachDomTips();
  // (wx, wy) 월드 타일 → 그 자리에 이름표 하나. big: 감독실 이름처럼 조금 크게. dot: 앞에 붙는 상태 색
  function drawTag(wx, wy, text, big = false, dot = null, sub = null, tip = null) {
    const box = drawTagBox(wx, wy, text, big, dot, sub);
    if (tip) HITS.push({ ...box, tip });
    return box;
  }
  function drawTagBox(wx, wy, text, big, dot, sub) {
    const [sx, sy] = toScreen(wx * T, wy * T);
    const font = big ? TAG.font.replace(/(\d+)px/, (m, n) => `${+n + 3}px`) : TAG.font;
    ctx.font = font; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    const fs = +(font.match(/(\d+)px/) || [0, 10])[1];
    const tw = ctx.measureText(text).width;
    ctx.font = TAG.font;
    const sw = sub ? ctx.measureText(sub).width + 8 : 0;
    const padL = TAG.kind === 'hazard' ? 9 : TAG.kind === 'sign' ? 7 : 6;
    const w = Math.ceil(padL + (dot ? 9 : 0) + tw + 6 + sw), h = fs + 7;
    const x = Math.round(sx), y = Math.round(sy);
    LABELS.push({ text, rect: [x, y, w, h] });
    ctx.fillStyle = TAG.bg; ctx.fillRect(x, y, w, h);
    if (TAG.kind === 'hazard') {                                     // 안전 표지판 — 왼쪽에 검정 · 노랑 빗금, 검정 테두리
      ctx.save(); ctx.beginPath(); ctx.rect(x, y, 6, h); ctx.clip();
      ctx.fillStyle = TAG.border; ctx.fillRect(x, y, 6, h);
      ctx.fillStyle = TAG.bg; for (let k = -h; k < 6; k += 5) { ctx.beginPath(); ctx.moveTo(x + k, y + h); ctx.lineTo(x + k + 2, y + h); ctx.lineTo(x + k + 2 + h, y); ctx.lineTo(x + k + h, y); ctx.fill(); }
      ctx.restore();
      ctx.strokeStyle = TAG.border; ctx.lineWidth = 1.5; ctx.strokeRect(x + 0.75, y + 0.75, w - 1.5, h - 1.5);
    } else if (TAG.kind === 'sign') {                                // 사인판 — 왼쪽 색 띠
      ctx.fillStyle = TAG.border; ctx.fillRect(x, y, 3, h);
      ctx.strokeStyle = '#00000022'; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
    } else {                                                         // 양피지 — 테두리 + 모서리 말림
      ctx.strokeStyle = TAG.border; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
      ctx.fillStyle = TAG.border; ctx.beginPath(); ctx.moveTo(x + w - 5, y + h); ctx.lineTo(x + w, y + h - 5); ctx.lineTo(x + w, y + h); ctx.fill();
      ctx.fillStyle = '#c9b282'; ctx.fillRect(x + 1, y + h - 2, w - 7, 1);
    }
    let cx = x + padL;
    if (dot) { ctx.fillStyle = dot; ctx.beginPath(); ctx.arc(cx + 3, y + h / 2, 3, 0, Math.PI * 2); ctx.fill(); cx += 9; }
    ctx.font = font; ctx.fillStyle = TAG.fg; ctx.fillText(text, cx, y + h / 2 + 0.5);
    if (sub) {                                                       // 상태 — 이름표 바탕 위에서 읽히게 글자색, 앞에 구분선
      ctx.fillStyle = TAG.fg; ctx.globalAlpha = 0.35; ctx.fillRect(cx + tw + 4, y + 3, 1, h - 6); ctx.globalAlpha = 1;
      // 실패는 빨강 글자(✗), 그 밖은 이름표 글자색 — 성공 ✓ 은 앞의 초록 점이 이미 말한다
      ctx.font = TAG.font.replace(/^(italic )?\d*\s*/, 'bold '); ctx.fillStyle = sub.startsWith('✗') ? '#d23b3b' : TAG.fg;
      ctx.fillText(sub, cx + tw + 8, y + h / 2 + 0.5);
    }
    return { x, y, w, h };
  }

  const WAIT_TIP = 'ArgoCD에서 Sync를 눌러야 올라갑니다.';
  const STATUS_KO = { running: '진행 중', success: '성공', failed: '실패', waiting: 'ArgoCD Sync 대기', stale: '나중 배포로 대체', none: '기록 없음' };
  // 구역이 하는 일 — 테마마다 이름(비유)은 달라도 설명은 같다(theme.tags.roles: 구역 → 아래 열쇠). 이름표에 마우스를 올리면 뜬다(11-05)
  // 툴팁 글은 짧게 — "무엇" 한 마디 + 한 줄 설명. 화면 글은 "~습니다"로(11-05 사용자 요청: 도구 목록 · 판별 명령은 넣지 않는다)
  const ZONE_ROLE = {
    hq:   { what: '계획 세우는 자리', desc: '뭘 할지 말하면 어느 프로젝트에서, 새 세션으로 할지 기존 세션에 붙일지 계획을 세워줍니다.' },
    read: { what: '파일 읽기', desc: '코드와 문서를 읽고 찾는 곳입니다.' },
    edit: { what: '코드 수정', desc: '파일을 고치거나 새로 쓰는 곳입니다.' },
    bash: { what: '명령 실행', desc: '셸 명령을 돌리는 곳입니다.' },
    test: { what: '테스트 실행', desc: '테스트를 돌리는 곳입니다.' },
    git:  { what: 'git 작업', desc: '커밋하고 푸시하는 곳입니다.' },
    web:  { what: '웹 검색', desc: '밖에서 정보를 찾는 곳입니다.' },
    sub:  { what: '보조 호출', desc: '서브에이전트에게 일을 나눠 맡기는 곳입니다.' },
    idle: { what: '대기 중', desc: '할 일이 없을 때 쉬는 곳입니다.' },
    scribe: { what: '서기실', desc: '서기가 늘 머무는 곳입니다. 서기를 누르면 문서 일을 맡길 수 있습니다.' },
  };
  const INFRA_ROLE = {
    jenkins: { what: '빌드', desc: '커밋을 빌드하고 테스트하는 곳입니다.' },
    harbor:  { what: '이미지 저장', desc: '빌드한 이미지를 보관하는 곳입니다.' },
    argocd:  { what: '배포', desc: '새 이미지를 서버에 내보내는 곳입니다.' },
  };
  const tipOf = (r) => r && `<div class="tip-b">${r.what}</div><div>${r.desc}</div>`;
  let HITS = [];                     // 이번 프레임에 그린 이름표 자리(화면 좌표) — 마우스를 올리면 설명
  // 방 이름표 그리기(11-10 모눈) — 방 왼쪽 위 칸 고정(roomLabels · labelBox), 글씨 · 칸은 방 배율(cam.s)을 따른다.
  // 글자색은 테마의 팀장(교장 · 소장) 색(ROOM_INK — 하드코딩하지 않는다), 바탕은 어두운 판 — 어느 바닥에서도 읽힌다. 하는 일은 호버
  function labelTip(l) {
    if (l.stage) {
      const st = l.st;
      return `<div class="tip-h">${'①②③'[l.i]} ${esc(stageName(l.stage).name)}</div><div class="tip-b">${esc(l.what || INFRA_ROLE[l.stage].what)}</div><div>${INFRA_ROLE[l.stage].desc}</div>` +
        (st !== 'none' ? `<div class="tip-s">${esc(STATUS_KO[st] || st)}${st === 'waiting' ? ' — ' + WAIT_TIP : ''}</div>` : '');
    }
    if (l.zone === 'infra') return `<div class="tip-h">${esc(l.text)}</div><div class="tip-b">출하 라인</div><div>커밋이 빌드 → 이미지 → 배포 순서로 나가는 곳입니다. 바닥 화살표 ① ② ③이 그 순서입니다.</div>`;
    const role = ZONE_ROLE[l.role];
    return `<div class="tip-h">${esc(l.text)}</div>${role ? tipOf(role) : ''}`;
  }
  function drawZoneTags(r) {
    const s = cam.s, k = labelK(s), fs = GL.font * s * k, pad = GL.pad * T * k * s;
    ctx.save();
    for (const l of roomLabels(r)) {
      const [bx, by, bw, bh] = labelBox(l, s);
      const [x0, y0] = toScreen((r.x + bx) * T, (r.y + by) * T);
      const x = Math.round(x0), y = Math.round(y0), w = Math.round(bw * T * s), h = Math.round(bh * T * s);
      ctx.fillStyle = '#000000b8'; ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = ROOM_INK; ctx.globalAlpha = 0.5; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1); ctx.globalAlpha = 1;
      let cx = x + pad;
      if (l.dot) { ctx.fillStyle = l.dot; ctx.beginPath(); ctx.arc(cx + fs * 0.4, y + h / 2, fs * 0.3, 0, Math.PI * 2); ctx.fill(); cx += fs; }
      ctx.font = labelFont(s); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillStyle = l.st === 'failed' ? P.bad : ROOM_INK;
      ctx.fillText(l.text, cx, y + h / 2 + 0.5);
      HITS.push({ x, y, w, h, zone: l.zone, tip: labelTip(l) });                       // overTags · 호버
      LABELS.push({ text: l.text, rect: [x, y, w, h], zone: l.zone });
    }
    ctx.restore();
    // 출하 대기(한 방에 빌드가 여럿 — 담당은 가장 오래된 것을 맡고 나머지는 줄 선다) — 담당 머리 위 말풍선(drawOverlay)의 호버
    const q = r.courier && r.courier.queue;
    const ca = q && q.length ? [...actors.values()].find((a) => a.kind === 'courier' && a.room === r.name) : null;
    const b = ca && BUBBLES.get(ca.key);
    if (b) {
      const [x, y, w, h] = toScr(b.rect);
      HITS.push({ x, y, w, h, tip: `<div class="tip-h">출하 대기</div><div class="tip-b">대기 ${q.length}개</div><div>먼저 온 빌드가 끝나기를 기다리고 있습니다.</div>${q.map((ch) => {
        const c = ch.commits && ch.commits[0];
        return `<div class="tip-t">${esc(ch.short)} ${esc(short((c && c.subject) || '', 60))}</div>`;
      }).join('')}` });
    }
  }

  // 붐비는 사람(11-06) — 발밑 기본 자리끼리 겹치면 둘 다 이름의 끝부분만 쓴다(「서기 — 포트폴리오 쓰기: 포먼 디스패처」 → 「포먼 디스패처」).
  // 먼저 그린 사람이 긴 이름으로 자리를 다 차지해 둘째가 갈 데가 없었다(오피스 1024 필사실)
  const nameTail = (s) => { const m = String(s || '').split(/:\s|\s—\s/); return m[m.length - 1] || s; };
  // 세션 캐릭터 · 쉬는 상주 코더 · 서기의 이름표는 역할만(11-09 사용자 — 제목이 들어가 "임시 · 세션 역할 관리자(man…"처럼 잘렸다).
  // 제목 · 세션 번호는 호버와 패널 머리줄에. 임시 일꾼이면 "임시"만 덧붙인다
  const roleNamed = (a) => a.kind === 'session' || a.kind === 'coder' || a.kind === 'scribe';
  const roleName = (a) => roleTag(a.role) + (a.temp ? ' 임시' : '');
  function markCrowd(as) {
    ctx.font = `${tpx(15)}px system-ui, sans-serif`;
    const bx = as.filter((a) => !(a.kind === 'mini' && a.key !== selected)).map((a) => {
      const [sx, sy] = toScreen(a.x * T, a.y * T), w = ctx.measureText(roleNamed(a) ? roleName(a) : short(a.name, 18)).width + 6;
      a.crowd = false;
      return [a, [sx - w / 2, sy + 2, w, tpx(15) + 3]];
    });
    for (let i = 0; i < bx.length; i++) for (let j = i + 1; j < bx.length; j++) {
      if (areaOf(bx[i][1], bx[j][1]) > 0) bx[i][0].crowd = bx[j][0].crowd = true;
    }
  }
  function drawName(a) {
    if (a.kind === 'mini' && a.key !== selected) return;     // 작은 일꾼 이름은 누른 것만(묶음 이름은 부모 밑에)
    const [sx, sy] = toScreen(a.x * T, a.y * T);
    // 끝난 세션(DORMANT)과 멈춘 세션(SUSPENDED)이 그림만으로는 헷갈렸다(11-05) — 이름 뒤에 글로 붙인다
    const suffix = a.kind === 'session' && a.s ? ({ DORMANT: ' · 끝남', SUSPENDED: ' · 멈춤' }[a.s.state] || '') : '';
    const text = roleNamed(a) ? roleName(a) + suffix : short(a.name, 30) + suffix;   // 임시 일꾼은 테두리도 점선(11-09)
    // 11-06 글씨 키움(11 → 15px, 두 번) — 줄 높이 NH, 줄 사이 1px
    const NH = tpx(15) + 3;                                  // 11-10 방 안은 방 배율(배율 3에서 15px · 18), 감독실은 글씨 배율
    ctx.font = `${tpx(15)}px system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const lines = [[text, a.kind === 'foreman' ? P.warn : P.label]];
    const n = a.kind === 'session' && a.s ? a.s.subagents_running || 0 : 0;
    // 11-10 사용자(받은 할 일 #9) — 캐릭터 아래는 수만("뒤에서 도는 일 2"). 무슨 일인지는 호버(세션 호버에 하나씩 적는다).
    // 전에는 "· 세 테마 × 세 폭 × 다섯 화면 다시…"처럼 설명이 붙어 이름표가 길게 깔렸다
    if (n) lines.push([`서브에이전트 ${n}`, P.act]);
    // 백그라운드 Bash · Monitor — "IDLE + 백그라운드 n개"(README 3.11). 일꾼 줄이 있으면 그 아래
    const bg = a.kind === 'session' && a.s ? a.s.background || [] : [];
    if (bg.length) lines.push([`뒤에서 도는 일 ${bg.length}`, P.act]);
    // 구역 이름표 · 앞서 그린 이름과 겹치면 비켜 그린다(11-06 — 글씨를 키우자 오피스 1024에서 서버룸 사람 이름이 「서버룸」을 덮었다).
    // 후보: 발밑(기본) → 겹친 칸의 아래 · 왼쪽 · 오른쪽. 사람에게서 멀어지지 않게 두 줄 높이 · 이름 폭 안에서만.
    // 그래도 겹치면 이름을 앞 10자로 줄여 한 번 더(나란히 앉은 서기 둘의 긴 이름)
    // 11-10 사람 몸도 피한다(자기 몸 포함) — 전에는 이름표 · 앞 이름만 피해서, 발밑 자리가 막히면 「[서기]」가 머리 위로 가며
    // 머리를 덮고(머리 위 자리를 1.9칸으로 잡았는데 1.5배 캐릭터는 그보다 크다), 「[코더]」가 아래에 앉은 사람을 덮었다
    const bodyList = bodyRects(), bodies = bodyList.map((b) => b.r);
    const ownR = (bodyList.find((b) => b.key === a.key) || {}).r || null;
    const others = [...HITS.filter((h) => !h.soft).map((h) => [h.x, h.y, h.w, h.h]), ...NAMES.map((m) => m.rect), ...bodies,
                    ...[...BUBBLES.entries()].filter(([k]) => actors.has(k)).map(([, b]) => toScr(b.rect))];   // soft = 호버만(그림 위 넓은 칸)
    const place = (ls) => {
      const ws = ls.map(([t]) => ctx.measureText(t).width + 6), mw = Math.max(...ws), bh = ls.length * (NH + 1) - 1;
      const cover = (cx, top) => others.reduce((s, o) => s + areaOf([cx - mw / 2, top, mw, bh], o), 0);
      let best = { cx: sx, top: sy + 2, c: cover(sx, sy + 2), ws, mw, bh, ls };
      if (!best.c) return best;
      // 좌우 한 이름 폭 · 아래 두 줄 · 머리 위 · 몸 양옆을 8px 격자로 훑는다. 안 겹치는 자리가 있으면 그중 가장 가까운 곳,
      // 없으면 겹친 넓이×2 + 거리가 가장 작은 곳(넓이만 보면 조금 덜 겹치려고 머리 위 왼쪽 끝까지 갔다)
      const bodyTop = ownR ? ownR[1] : sy - Math.round(2.4 * T * cam.s);
      const head = bodyTop - bh - 2;
      const tops = [sy + 2, sy + 2 + (NH + 1), sy + 2 + 2 * (NH + 1), head, head - (NH + 1)];
      const score = (c, cx, top) => (c ? 100000 + 2 * c : 0) + Math.hypot(cx - sx, top - sy - 2);
      const cands = [];
      for (const top of tops) for (let dx = -mw; dx <= mw; dx += 8) cands.push([sx + dx, top]);
      if (ownR) {                        // 몸 양옆(허리 높이부터 발까지)
        for (let top = ownR[1] + ownR[3] * 0.3; top <= sy + 2; top += 6) {
          cands.push([ownR[0] - mw / 2 - 3, top], [ownR[0] + ownR[2] + mw / 2 + 3, top]);
        }
      }
      for (const o of others) {          // 겹친 칸의 바로 아래 · 왼쪽 · 오른쪽(격자가 놓치는 딱 맞는 자리)
        if (!areaOf([sx - mw / 2, sy + 2, mw, bh], o)) continue;
        cands.push([sx, o[1] + o[3] + 2], [o[0] - mw / 2 - 2, sy + 2], [o[0] + o[2] + mw / 2 + 2, sy + 2]);
      }
      let bs = score(best.c, best.cx, best.top);
      for (const [cx, top] of cands) {
        if (Math.abs(cx - sx) > mw + (ownR ? ownR[2] / 2 + 4 : 0) || (top > sy && top - (sy + 2) > NH * 2 + 4)) continue;
        const c = cover(cx, top), s = score(c, cx, top);
        if (s < bs) { best = { ...best, cx, top, c }; bs = s; }
      }
      return best;
    };
    let best = place(lines);
    if (best.c && text.length > 11 && !roleNamed(a)) {
      const alt = place([[short(nameTail(a.name), 10) + suffix, lines[0][1]], ...lines.slice(1)]);
      if (alt.c < best.c) best = alt;
    }
    const { ws, mw, bh } = best;
    best.cx = Math.max(mw / 2 + 2, Math.min(W - mw / 2 - 2, best.cx));   // 화면 밖으로 잘리지 않게(11-09 — 1024에서 방 밖 「출하 반장」)
    best.ls.forEach(([t, col], i) => {
      const y = best.top + i * (NH + 1);
      ctx.fillStyle = '#000a'; ctx.fillRect(best.cx - ws[i] / 2, y, ws[i], NH);
      if (a.temp && i === 0) {                                   // 임시 일꾼 — 점선 테두리(11-09)
        ctx.save(); ctx.setLineDash([3, 2]); ctx.strokeStyle = P.label; ctx.lineWidth = 1;
        ctx.strokeRect(Math.round(best.cx - ws[i] / 2) + 0.5, y + 0.5, Math.round(ws[i]) - 1, NH - 1); ctx.restore();
      }
      ctx.fillStyle = col; ctx.fillText(t, best.cx, y + 1);
    });
    NAMES.push({ key: a.key, name: best.ls[0][0], rect: [best.cx - mw / 2, best.top, mw, bh].map(Math.round), cover: Math.round(best.c) });
  }
  // 이름이 구역 이름표 · 다른 이름과 겹친 것(비켜도 남은 것) — tools/screen.py가 세 테마 × 세 크기로 센다(11-06)
  let NAMES = [];
  function nameAudit() { return NAMES.filter((m) => m.cover > 0); }
  // ── 이름표 점검(11-10 사용자 — "구역 이름표가 가구 위에, 캐릭터 이름표가 캐릭터를 덮는다. 점검은 0건인데 실제로는 겹친다") ──
  // layoutAudit은 좌석(자리 점)의 윗몸을 가구 · 소품 · 구역 이름표가 덮나만, nameAudit은 캐릭터 이름 ↔ 구역 이름표 · 앞 이름만 쟀다.
  // 이름표 ↔ 가구, 이름표 ↔ 실제로 그린 사람 몸, 이름표끼리(구역 이름표 · 출하 라인 · 말풍선 포함)는 아무도 재지 않았다.
  // 이 점검은 지금 화면에 그린 그대로(화면 px)를 잰다 — LABELS(drawTagBox) · NAMES · BUBBLES · BODIES(drawActorS)
  let LABELS = [];
  const BODIES = new Map();
  const toScr = (r) => { const [x, y] = toScreen(r[0], r[1]); return [x, y, r[2] * cam.s, r[3] * cam.s]; };   // 월드 px → 화면 px
  // 사람 몸의 화면 칸 — 그림 칸에서 옆 여백(투명)을 조금 뺀다
  function bodyRects() {
    return [...BODIES.values()].map(({ a, box }) => {
      const [x, y, w, h] = toScr(box);
      return { key: a.key, name: a.name || a.key, r: [x + w * 0.15, y + h * 0.04, w * 0.7, h * 0.94] };
    });
  }
  // 그림의 불투명 범위(0~1 비율 [왼, 위, 오른, 아래]) — 그림 칸에는 투명 여백이 있어(아치 윗부분 등) 칸으로만 재면 안 덮는 것을 덮었다고 셌다
  const OPAQ = new Map();
  function opaqueBox(name) {
    if (OPAQ.has(name)) return OPAQ.get(name);
    let r = [0, 0, 1, 1];
    if (!SP) return r;                       // 그림이 아직 안 떴다 — 저장하지 않는다
    try {
      const c = SP && SP.frame(name, 0, 0);
      if (c && c.width && c.height) {
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
        for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
          if (d[(y * c.width + x) * 4 + 3] > 40) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
        }
        if (x1 >= 0) r = [x0 / c.width, y0 / c.height, (x1 + 1) / c.width, (y1 + 1) / c.height];
      }
    } catch { /* 읽지 못하면 그림 칸 그대로 */ }
    OPAQ.set(name, r);
    return r;
  }
  // 이름표가 피해야 할 가구 · 소품(벽에 붙은 선반 · 창 포함, 바닥 깔개는 뺀다) — 방 좌표 [x, y, w, h], 그림의 불투명 범위만
  function furnRects(where = 'room') {
    const out = [];
    const add = (d, ox, oy) => {
      if (!d.s || d.fx || d.z === 'floor') return;
      const [w, h] = sizeT(d), [l, t, rr, b] = opaqueBox(d.s);
      for (let i = 0; i < (d.n || 1); i++) out.push({ s: d.s, x: ox + d.x + i * (d.dx || 1) + l * w, y: oy + d.y + t * h, w: (rr - l) * w, h: (b - t) * h });
    };
    if (where === 'hq') { for (const d of HQ.decor || []) add(d, 0, 0); return out; }
    for (const d of theme.sprites.decor || []) add(d, 0, 0);
    const iz = L.zones.infra;
    if (iz) for (const k of ['jenkins', 'harbor', 'argocd']) for (const d of (theme.sprites.infra_decor || {})[k] || []) add(d, iz[k].x, iz.y);
    return out;
  }
  // ── 모눈 점검(11-10 — 「화면 모눈으로 다시 짜기」) ─────────────────────────────
  // 테마 · 창 크기와 상관없는 배치 점검(방 좌표). tools/screen.py가 테마마다 부르고, ⑤ 테마 셋의 방 자리가 같은지는 rooms를 견준다.
  // ① 두 방이 같은 칸 · ② 복도가 끊김 · 복도에 안 닿는 방 — grid.js gridProblems(grid.json만)
  // ② 걸어서 못 가는 자리 — 실제 걷기 격자(가구가 막은 칸)에서 복도에서 모든 자리(좌석 · 출하 담당 자리)까지 이어지나
  // ③ 가구가 방 밖으로 — 그림의 불투명 범위가 제 방(in) 안인가. 위 벽에 붙은 방은 위 벽(y 0~)까지, 출하 단계 그림은 그 단계 칸 안. 자리도 제 방 안
  // ④ 이름표가 방 왼쪽 위 칸에 — 왼쪽 위 + pad에 있고 방 안이며, 가구(불투명) · 자리의 몸과 겹치지 않는가. 가장 작은 배율(배율 1 — 이름표가 가장 크다)과 지금 배율 둘 다
  function gridAudit() {
    if (!GRIDDEF) return { problems: [], rooms: null };
    const out = gridProblems(GRIDDEF).map((t) => ({ kind: '모눈', text: t }));
    const rooms = gridRooms(), byKey = Object.fromEntries(rooms.map((q) => [q.key, q]));
    const roleRect = Object.fromEntries(rooms.map((q) => [q.role, [q.x, q.y, q.w, q.h]]));
    const inside = (r, q, top = q.y) => r[0] >= q.x - 0.01 && r[1] >= top - 0.01 && r[0] + r[2] <= q.x + q.w + 0.01 && r[1] + r[3] <= q.y + q.h + 0.01;
    const fmtR = (r) => r.map((v) => +v.toFixed(2)).join(',');
    // ③ 가구
    const iz = L.zones.infra;
    const opq = (d, ox, oy) => {
      if (d.fx === 'glasswall') return [[ox + d.x, oy + d.y, d.w || 1, d.h || 1]];
      if (d.fx) return [[ox + d.x, oy + d.y, 0, 0]];                                   // 빛 · 촛불 — 점
      const [w, h] = sizeT(d), [l, t, rr, b] = opaqueBox(d.s), list = [];
      for (let i = 0; i < (d.n || 1); i++) list.push([ox + d.x + i * (d.dx || 1) + l * w, oy + d.y + t * h, (rr - l) * w, (b - t) * h]);
      return list;
    };
    for (const d of theme.sprites.decor || []) {
      if (!d.s && !d.fx) continue;
      const q = byKey[d.in];
      if (!q) { out.push({ kind: '가구 방 없음', text: `${d.s || d.fx} — in(방)이 없습니다` }); continue; }
      const top = q.y <= INNER_TOP ? 0 : q.y;                                         // 위 벽에 붙은 방은 벽에 건 것까지
      for (const r of opq(d, 0, 0)) if (!inside(r, q, top)) out.push({ kind: '가구 방 밖', text: `${d.s || d.fx}(${d.in}) [${fmtR(r)}] — 방 [${fmtR([q.x, q.y, q.w, q.h])}]` });
    }
    if (iz) for (const k of INFRA_STAGES) {
      const q = { x: iz[k].x, y: iz.y, w: iz.stageW || 4.5, h: iz.h };
      for (const d of (theme.sprites.infra_decor || {})[k] || []) for (const r of opq(d, iz[k].x, iz.y)) {
        if (!inside(r, q)) out.push({ kind: '가구 방 밖', text: `${d.s}(출하 ${k}) [${fmtR(r)}] — 단계 칸 [${fmtR([q.x, q.y, q.w, q.h])}]` });
      }
    }
    // 자리도 제 방 안(관리자 · 디자이너 · 상주 코더는 in의 방)
    const spotRoom = (where) => {
      const name = where.split(/[#.]/)[0];
      if (name === 'infra') return byKey.infra;
      const z = L.zones[name];
      return z && byKey[z.in || name];
    };
    const spots = standSpots();
    for (const p of spots) {
      const q = spotRoom(p.where);
      if (q && !inside([p.x, p.y, 0, 0], q)) out.push({ kind: '자리 방 밖', text: `${p.where} (${p.x}, ${p.y}) — 방 [${fmtR([q.x, q.y, q.w, q.h])}]` });
    }
    // ② 걸어서 닿는가 — 복도 첫 칸 가운데에서 걷기 격자를 훑는다
    const g = GRID && GRID.room;
    if (g) {
      const c0 = GRIDDEF.corridors[0], start = nearestFree(g, Math.floor((c0[0] + 0.5) * RES), Math.floor((c0[1] + 0.5) * RES));
      const seen = new Uint8Array(g.cols * g.rows);
      if (start) {
        const q = [start[1] * g.cols + start[0]]; seen[q[0]] = 1;
        while (q.length) {
          const i = q.pop(), c = i % g.cols, r = Math.floor(i / g.cols);
          for (const [dc, dr] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
            const cc = c + dc, rr = r + dr, j = rr * g.cols + cc;
            if (cc < 0 || rr < 0 || cc >= g.cols || rr >= g.rows || seen[j] || g.block[j]) continue;
            seen[j] = 1; q.push(j);
          }
        }
      }
      for (const p of spots) {
        const f = nearestFree(g, Math.floor(p.x * RES), Math.floor(p.y * RES));
        if (!f || !seen[f[1] * g.cols + f[0]]) out.push({ kind: '못 가는 자리', text: `${p.where} (${p.x}, ${p.y}) — 복도에서 걸어서 닿지 않습니다` });
      }
    }
    // ④ 이름표 — 가장 큰 꼴(배율 1)과 지금 방 배율
    const [bw, bh] = bodySize();
    const furn = furnRects('room').map((f) => [f.x, f.y, f.w, f.h, f.s]);
    for (const s of [...new Set([1, roomViewScale()])]) {
      for (const l of roomLabels()) {
        const q = l.stage ? { x: iz[l.stage].x, y: iz.y, w: iz.stageW || 4.5, h: iz.h } : byKey[l.zone];
        if (!q) continue;
        const b = labelBox(l, s), tag = `이름표 「${l.text}」(배율 ${s})`;
        if (Math.abs(b[0] - (q.x + GL.pad)) > 0.01 || Math.abs(b[1] - (q.y + GL.pad)) > 0.01) out.push({ kind: '이름표 자리', text: `${tag} [${fmtR(b)}] — 방 왼쪽 위가 아닙니다` });
        if (!inside(b, q)) out.push({ kind: '이름표 방 밖', text: `${tag} [${fmtR(b)}] — 방 [${fmtR([q.x, q.y, q.w, q.h])}]` });
        for (const f of furn) {
          const a = areaOf(b, f);
          if (a > 0.02) out.push({ kind: '이름표↔가구', text: `${tag} ↔ ${f[4]} ${a.toFixed(2)}칸²` });
        }
        for (const p of spots) {
          const body = [p.x - bw / 2 + 0.05, p.y - bh, bw - 0.1, bh], a = areaOf(b, body);
          if (a > 0.02) out.push({ kind: '이름표↔자리', text: `${tag} ↔ ${p.where} 몸 ${a.toFixed(2)}칸²` });
        }
      }
    }
    return { problems: out, rooms: roleRect };
  }
  const INNER_TOP = 2;                                                             // 위 벽 아래 첫 줄(grid.js INNER.y0)

  function labelAudit() {
    const out = [];
    const bub = [...BUBBLES.entries()].filter(([k]) => actors.has(k)).map(([, b]) => ({ kind: '말풍선', text: b.text, r: toScr(b.rect) }));
    const labels = [...LABELS.map((l) => ({ kind: l.zone ? '구역 이름표' : '이름표', text: l.text, r: l.rect })),
                    ...NAMES.map((m) => ({ kind: '캐릭터 이름표', text: m.name, r: m.rect })), ...bub];
    // ① 이름표 ↔ 사람 몸
    for (const b of bodyRects()) for (const l of labels) {
      const c = areaOf(l.r, b.r) / (b.r[2] * b.r[3]);
      if (c > 0.03) out.push({ where: 'label', kind: '이름표↔몸', label: `${l.kind} ${l.text}`, by: b.name, cover: +c.toFixed(2),
                               at: l.r.map(Math.round), body: b.r.map(Math.round) });
    }
    // ② 이름표끼리
    for (let i = 0; i < labels.length; i++) for (let j = i + 1; j < labels.length; j++) {
      const s = areaOf(labels[i].r, labels[j].r);
      if (s > 6) out.push({ where: 'label', kind: '이름표↔이름표', label: `${labels[i].kind} ${labels[i].text}`, by: `${labels[j].kind} ${labels[j].text}`, px: Math.round(s) });
    }
    // ③ 구역 이름표 · 출하 라인 이름표 ↔ 가구(지금 보이는 방 · 감독실)
    const rooms = view === 'hq' ? [] : view === 'map' ? world.rooms : world.rooms.filter((r) => r.name === view);
    const furn = rooms.flatMap((r) => furnRects('room').map((f) => ({ s: f.s, r: [(r.x + f.x) * T, (r.y + f.y) * T, f.w * T, f.h * T] })));
    if (view === 'hq' && world.hq) furn.push(...furnRects('hq').map((f) => ({ s: f.s, r: [(world.hq.x + f.x) * T, (world.hq.y + f.y) * T, f.w * T, f.h * T] })));
    for (const f of furn) {
      const fr = toScr(f.r);
      for (const l of labels) {
        if (l.kind !== '구역 이름표' && l.kind !== '이름표') continue;
        const c = areaOf(l.r, fr) / (l.r[2] * l.r[3]);
        if (c > 0.05) out.push({ where: 'label', kind: '이름표↔가구', label: `${l.kind} ${l.text}`, by: f.s, cover: +c.toFixed(2),
                                 at: l.r.map(Math.round), furn: fr.map(Math.round) });
      }
    }
    return out;
  }

  function fmt(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(n); }

  // 현장 상태 하나 — 감독실 표시(촛불 · 모니터 · 자석)와 카드 테두리가 같은 판단을 쓴다
  function siteState(r) {
    const st = r.stats || {}, pp = r.pipe;
    const broke = pp && pp.chains && pp.chains[0] && pp.chains[0].broke;
    if (broke || (pp && pp.webhook_broken) || (pp && pp.watch && pp.watch.state === 'missing')) return 'fail';
    if (st.pending || st.question || st.denied || st.asks) return 'alert';
    if (st.ACTIVE) return 'busy';
    if ((st.IDLE || 0) + (st.SUSPENDED || 0) + (st.DORMANT || 0)) return 'idle';
    return 'empty';
  }

  // 현장 카드 글씨(11-06 키움 두 번: 11 → 15px, 제목 13 → 17px, 줄 간격 15 → cardLH())
  const cardLH = () => fpx(20);                  // 11-09 글씨 배율을 따른다
  function badgeLines(r) {
    const st = r.stats || {};
    const lines = [];
    lines.push([`${r.label}`, P.label, 'bold 17px']);
    lines.push([`작업 ${st.ACTIVE || 0} · 쉼 ${st.IDLE || 0}${st.SUSPENDED ? ' · 멈춤 ' + st.SUSPENDED : ''}${st.subs ? ' · 서브에이전트 ' + st.subs : ''}${r.overflow ? ' · 책상 없음 +' + r.overflow : ''}`, P.muted, '15px']);
    // 넷째 칸 true = 경고 줄 — 한 방을 볼 때는 이 줄만 카드로 띄운다(11-08, 나머지는 머리말과 겹친다)
    if (st.pending) lines.push([`❗ 승인 대기 ${st.pending}`, P.warn, 'bold 16px', true]);
    if (st.question) lines.push([`❓ 질문 ${st.question} — 패널에서 답합니다`, P.warn, 'bold 16px', true]);
    // 11-09 FOREMAN 승인 카드로 오지 않는 것 — 무엇을 어디서 해야 풀리는지 글에 넣는다
    if (st.denied) lines.push([`✋ 권한 거부 ${st.denied} — CC 자체 검사가 막았습니다. 그 세션에 허용하거나 다른 방법을 지시합니다`, P.warn, 'bold 16px', true]);
    if (st.asks) lines.push([`💬 답 기다림 ${st.asks} — 묻고 끝났습니다. 패널 입력 칸이나 터미널에서 답합니다`, P.warn, 'bold 16px', true]);
    if (r.name) lines.push(...schemaLines(r.name));                // 스키마 잠금(11-09)
    const pp = r.pipe;
    const broke = pp && pp.chains && pp.chains[0] && pp.chains[0].broke;
    if (broke) lines.push([`🔥 파이프라인 실패 · ${broke}`, P.bad, 'bold 15px', true]);
    // 11-09 "배포 승인 기다림"은 FOREMAN 안에서 승인할 것처럼 읽혔다 — 푸는 곳(ArgoCD)을 말에 넣는다. 배너에서 누르면 ArgoCD 앱 화면
    else if (r.st_argocd === 'waiting') lines.push([`⏸ 배포 대기 — ArgoCD에서 Sync를 눌러야 올라갑니다${pp && pp.argocd_url ? ' ↗' : ''}`, P.warn, '15px', true, 'argocd']);
    if (pp && pp.webhook_broken) lines.push(['⚠ 빌드 알림 끊김 의심', P.bad, '15px', true]);
    if (pp && pp.watch && pp.watch.state !== 'ok') lines.push([`⚠ 빌드 알림 ${pp.watch.state === 'missing' ? '없음' : '늦음'}`, pp.watch.state === 'missing' ? P.bad : P.warn, '15px', true]);
    // 토큰 — 지금 어느 방이 쓰고 있나(사용자 요청 11-03). 오늘 누적 + 최근 10분 증가
    const hot = r.rate > 2e6 ? P.bad : r.rate > 3e5 ? P.warn : r.rate > 0 ? P.act : P.muted;
    lines.push([`토큰 오늘 출력 ${fmt(st.tout || 0)} · 입력 ${fmt(st.tin || 0)}`, P.muted, '15px']);
    // 그중 Opus(11-05 사용자 요청 — 비싼 모델을 어디서 쓰나). 다른 모델이 하나도 없으면 줄이 같아 생략
    if (st.opus_out && st.opus_out < st.all_out) lines.push([`Opus 출력 ${fmt(st.opus_out)} (서브에이전트 포함 ${Math.round(100 * st.opus_out / st.all_out)}%)`, P.muted, '15px']);
    else if (st.opus_out) lines.push(['오늘은 전부 Opus', P.muted, '15px']);
    const span = Math.round((r.rateSpan || 0) / 60000);
    lines.push([r.rate ? `최근 ${Math.max(1, Math.min(10, span))}분 ${fmt(r.rate)} 토큰 씀 (출력 ${fmt(r.rateOut)})`
      : (r.rateSpan || 0) < 60000 ? '최근 사용량 재는 중…(화면을 연 뒤부터)' : `최근 ${Math.min(10, span)}분 사용 없음`,
      hot, r.rate ? 'bold 15px' : '15px']);
    const border = st.pending || st.question || broke ? P.warn : hot;
    return { lines, border, thick: r.rate > 3e5 || st.pending || st.question };
  }

  // 줄 수가 넘치면 뒤에서부터 덜 중요한 줄(Opus · 최근 사용량)을 뺀다 — 11-06 글씨를 키우자 마법학교 1366에서 카드가 방 윗벽을 덮었다
  function fitLines(lines, maxLines) {
    const out = [...lines];
    const OPT = /^(Opus 출력|오늘은 전부 Opus|최근 )/;
    for (let i = out.length - 1; out.length > maxLines && i >= 0; i--) if (OPT.test(out[i][0])) out.splice(i, 1);
    return out;
  }
  function cardLines(r, alertsOnly) {
    const all = badgeLines(r).lines;
    return alertsOnly ? (all.some((l) => l[3]) ? [all[0], ...all.filter((l) => l[3])] : []) : all;
  }
  function drawCard(r, bx, by, w, minW = 210, maxW = 400, maxLines = 99, alertsOnly = false) {
    const b = badgeLines(r), { border, thick } = b, lines = fitLines(cardLines(r, alertsOnly), maxLines);
    w = Math.max(minW * FZ(), Math.min(w, maxW * FZ()));             // 폭도 글씨 배율만큼(11-09)
    const h = lines.length * cardLH() + 8;
    ctx.fillStyle = '#0d0f14e6'; ctx.fillRect(bx, by, w, h);
    ctx.strokeStyle = border; ctx.lineWidth = thick ? 2 : 1;
    ctx.strokeRect(bx + 0.5, by + 0.5, w - 1, h - 1);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    // 11-08 — 글자 수(8.5px/자)로 자르던 것을 실제 폭으로. 한글은 한 자가 그보다 넓어 감독실 카드(현장 1600)에서 글이 카드 밖으로 넘쳤다
    lines.forEach(([t, c, f], i) => { ctx.font = `${sizeFont(f)} system-ui, sans-serif`; ctx.fillStyle = c; ctx.fillText(fitText(t, w - 12), bx + 6, by + 5 + i * cardLH()); });
    return { x: bx, y: by, w, h };
  }
  // 지금 글꼴로 maxW px 안에 들어가게 — 넘치면 뒤를 줄이고 …
  function fitText(t, maxW) {
    t = String(t);
    if (ctx.measureText(t).width <= maxW) return t;
    let lo = 0, hi = t.length;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (ctx.measureText(t.slice(0, m) + '…').width <= maxW) lo = m; else hi = m - 1; }
    return t.slice(0, lo) + '…';
  }

  function drawBadge(r, zoomedIn) {
    if (view === 'hq' || (zoomedIn && (r.name || '_lounge') !== view)) { r.badge = null; return; }   // 안 그린 배지는 클릭도 안 받는다
    const [sx, sy] = toScreen(r.x * T, r.y * T);
    const [ex] = toScreen((r.x + r.w) * T, 0);
    // 11-08 한 방을 볼 때는 경고(승인 대기 · 파이프라인 · 웹훅 · 빌드 알림)가 있을 때만 그 줄만 — 작업 수 · 토큰은 머리말
    // (프로젝트 버튼 · 툴팁)과 겹쳐 뺐고, 그만큼 방을 키웠다(aim). 11-09 경고는 맨 위 배너로(syncBanner · drawBanner — 방 위에 겹치지 않는다)
    if (zoomedIn) { r.badge = BANNER ? drawBanner(BANNER) : null; return; }
    // 11-09 [전체] 카드 — 방 위에 다섯 줄로 겹쳐 그리던 것(감독실 그림을 덮고 …로 잘림)을 방 아래 두 줄로(사용자)
    r.badge = drawMapCard(r);
  }

  // ── 감독실(1단) ────────────────────────────────────
  const HQ = theme.hq || {};
  function sites() { return [...world.rooms, world.lounge].filter(Boolean); }
  // 현황판 위 현장 자리(월드 타일) — 판을 현장 수로 나눈다
  function boardSlots() {
    const b = HQ.board || { x: 3, y: 0.4, w: 22, h: 5.4 };
    const ss = sites(), q = world.hq;
    return ss.map((r, i) => ({ r, x: q.x + b.x + (b.w / ss.length) * i, y: q.y + b.y, w: b.w / ss.length, h: b.h }));
  }

  // 현장 카드 — 감독실 아래에 현장마다(화면 좌표, 선명하게). 누르면 그 현장으로
  // 11-09 사용자: [전체] 카드가 방을 덮고 다섯 줄이 잘렸다 → 방 아래로 떼고(aim이 MAP_H만큼 비운다) 두 줄 — 이름 · 지금 상태.
  // 토큰 · Opus · 최근 사용량은 호버로. 폭을 넘으면 자르지 않고 줄을 바꾸고, 네 칸 높이는 가장 긴 카드에 맞춘다
  function hqCardLines(r) {
    const st = r.stats || {}, pp = r.pipe;
    const broke = pp && pp.chains && pp.chains[0] && pp.chains[0].broke;
    let state;
    if (broke) state = [`멈춤 — 파이프라인 실패(${broke})`, P.bad, 'bold 16px'];
    else if (st.pending) state = [`멈춤 — 승인 대기 ${st.pending}`, P.warn, 'bold 16px'];
    else if (st.question) state = [`멈춤 — 질문 ${st.question}`, P.warn, 'bold 16px'];
    else if (st.denied) state = [`멈춤 — 권한 거부 ${st.denied}`, P.warn, 'bold 16px'];
    else if (st.asks) state = [`멈춤 — 답 기다림 ${st.asks}`, P.warn, 'bold 16px'];
    else if (st.ACTIVE) state = [`작업 중 ${st.ACTIVE}`, P.act, '16px'];
    else if ((st.IDLE || 0) + (st.SUSPENDED || 0) + (st.DORMANT || 0)) state = ['쉼', P.muted, '16px'];
    else state = ['세션 없음', P.muted, '16px'];
    const s = siteState(r);
    return [[r.label, s === 'fail' ? P.bad : s === 'alert' ? P.warn : P.label, 'bold 17px'], state];
  }
  function hqCardTip(r, head = null) {
    const st = r.stats || {}, pp = r.pipe;
    const span = Math.round((r.rateSpan || 0) / 60000);
    const rows = [
      `작업 ${st.ACTIVE || 0} · 쉼 ${st.IDLE || 0}${st.SUSPENDED ? ' · 멈춰 둠 ' + st.SUSPENDED : ''}${st.subs ? ' · 서브에이전트 ' + st.subs : ''}${r.overflow ? ' · 책상 없음 +' + r.overflow : ''}`,
      ...(st.pending || st.question ? [`승인 대기 ${st.pending || 0} · 질문 ${st.question || 0} — 패널 카드에서 답합니다`] : []),
      ...(st.denied ? [`권한 거부 ${st.denied} — CC 자체 검사, 그 세션에 허용 · 다른 방법 지시`] : []),
      ...(st.asks ? [`답 기다림 ${st.asks} — 패널 입력 칸이나 터미널에서 답합니다`] : []),
      ...(r.st_argocd === 'waiting' ? ['배포 대기 — ArgoCD에서 Sync를 눌러야 올라갑니다'] : []),
      ...(pp && pp.webhook_broken ? ['빌드 알림 끊김 의심'] : []),
      ...(pp && pp.watch && pp.watch.state !== 'ok' ? [`빌드 알림 ${pp.watch.state === 'missing' ? '없음' : '늦음'}`] : []),
      `토큰 오늘 출력 ${fmt(st.tout || 0)} · 입력 ${fmt(st.tin || 0)}`,
      ...(st.opus_out && st.opus_out < st.all_out ? [`Opus 출력 ${fmt(st.opus_out)} (서브에이전트 포함 ${Math.round(100 * st.opus_out / st.all_out)}%)`]
        : st.opus_out ? ['오늘은 전부 Opus'] : []),
      r.rate ? `최근 ${Math.max(1, Math.min(10, span))}분 ${fmt(r.rate)} 토큰 씀 (출력 ${fmt(r.rateOut)})`
        : (r.rateSpan || 0) < 60000 ? '최근 사용량 재는 중(화면을 연 뒤부터)' : `최근 ${Math.min(10, span)}분 사용 없음`,
    ];
    return textTip([head || `${r.label} — 현장 상태입니다. 누르면 그 현장으로 갑니다.`, ...rows].join('\n'));
  }
  // 감독실 현황판 칸 호버(11-09 사용자 — 빨간 표시가 왜 켜졌는지). 표시 종류는 테마마다 다르고 판단은 siteState 하나다:
  //   ❗(이름 뒤) · 붉은 촛불(마법학교) · 노란 모니터 띠 · 테두리 깜빡 + "!"(오피스) · 빨간 자석(현장, 칸 오른쪽 위) = 사람이 풀어야 하는 대기
  //   🔥 · 꺼진 촛불 + 연기 · 빨간 모니터 + "✕" · 빨간 자석 = 파이프라인 실패 · 웹훅 끊김 의심 · 빌드 알림 없음
  //   현장 테마 아래 줄의 작은 빨간 자석 = 승인 대기 한 건에 하나(최대 4)
  function boardTip(r) {
    const s = siteState(r);
    const head = s === 'alert' ? `${r.label} — 빨간 표시: 사람이 풀어야 하는 대기가 있습니다. 아래 줄이 무엇을 어디서 푸는지입니다. 누르면 그 현장으로 갑니다.`
      : s === 'fail' ? `${r.label} — 빨간 표시: 파이프라인이 깨졌거나 빌드 알림이 끊겼습니다. 누르면 그 현장으로 갑니다.` : null;
    return hqCardTip(r, head);
  }
  // [전체] 현장 카드 — 방마다 그 방 바로 아래, 한 줄(같은 y · 같은 높이). 폭은 그 방 폭(목표 배율 camT.s로 재서 흔들리지 않게)
  let MAPC = null;                               // 이번 프레임의 카드 줄 · 높이(syncBanner가 잰다, 높이는 MAP_H)
  // 카드가 쓸 수 있는 폭(타일) — 그 방 왼쪽 끝부터 다음 방 왼쪽 끝까지(방 사이 틈 포함). 맨 끝(라운지)은 방 폭
  function colW(r) {
    const ss = sites(), i = ss.indexOf(r);
    return i >= 0 && i < ss.length - 1 ? ss[i + 1].x - r.x : r.w;
  }
  function mapLayout() {
    const cards = new Map();
    for (const r of sites()) {
      const cw = Math.max(MIN_CARD(), colW(r) * T * camT.s - 6);
      const lines = [];
      for (const [t, c, f] of hqCardLines(r)) { ctx.font = `${sizeFont(f)} system-ui, sans-serif`; for (const x of wrapText(t, cw - 12)) lines.push([x, c, f]); }
      cards.set(r, lines);
    }
    const n = Math.max(2, ...[...cards.values()].map((l) => l.length));
    return { cards, h: n * cardLH() + 8 };
  }
  function drawMapCard(r) {
    const M = MAPC || mapLayout();
    const lines = M.cards.get(r);
    if (!lines) return null;
    const bottom = Math.max(...sites().map((s) => toScreen(0, (s.y + s.h) * T)[1]));
    const [x0, ] = toScreen(r.x * T, 0), [x1] = toScreen((r.x + colW(r)) * T, 0);
    const w = Math.min(W - 8, Math.max(MIN_CARD(), x1 - x0 - 6)), y = Math.round(bottom + 8);
    const x = Math.round(Math.max(4, Math.min(x0, W - 4 - w)));         // 화면 밖으로 나가지 않게(좁은 창에서 라운지가 오른쪽 끝)
    const { border, thick } = badgeLines(r);
    ctx.fillStyle = '#0d0f14'; ctx.fillRect(x, y, w, M.h);
    ctx.strokeStyle = border; ctx.lineWidth = thick ? 2 : 1;
    ctx.strokeRect(x + 0.5, y + 0.5, w - 1, M.h - 1);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    lines.forEach(([t, c, f], k) => { ctx.font = `${sizeFont(f)} system-ui, sans-serif`; ctx.fillStyle = c; ctx.fillText(t, x + 6, y + 5 + k * cardLH()); });
    const box = { x, y, w, h: M.h };
    HITS.push({ ...box, tip: hqCardTip(r) });
    MAP_BOXES.push({ ...box, label: r.label, lines: lines.map((l) => l[0]) });
    return box;
  }
  // 점검(tools/screen.py --eval) — [전체] 카드끼리 겹침 · 화면 밖 · 방(감독실 포함) 그림과 겹침 · 높이가 다름 · 잘림(…)
  let MAP_BOXES = [];
  function cardAudit() {
    const bs = MAP_BOXES, out = [];
    const hit = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
    const pics = [...sites(), world.hq].filter(Boolean).map((r) => {
      const [x0, y0] = toScreen(r.x * T, r.y * T), [x1, y1] = toScreen((r.x + r.w) * T, (r.y + r.h) * T);
      return { x: x0, y: y0, w: x1 - x0, h: y1 - y0, label: r.label };
    });
    bs.forEach((a, i) => {
      bs.slice(i + 1).forEach((b) => { if (hit(a, b)) out.push(`카드 겹침 ${a.label} · ${b.label}`); });
      pics.forEach((p) => { if (hit(a, p)) out.push(`그림 덮음 ${a.label} → ${p.label}`); });
      if (a.x < 0 || a.x + a.w > W || a.y + a.h > H) out.push(`화면 밖 ${a.label}`);
      if (a.h !== bs[0].h || a.y !== bs[0].y) out.push(`줄 안 맞음 ${a.label}`);
      if (a.lines.some((t) => t.endsWith('…'))) out.push(`잘림 ${a.label}`);
    });
    // [⌂] 현황판 이름 · 표시(11-09) — 다른 칸 이름과 겹침 · 칸 밖으로 나감 · 낱말 가운데서 끊김
    const bn = BOARD_NAMES;
    const box = ([x, y, w, h]) => ({ x, y, w, h });
    bn.forEach((a, i) => {
      bn.slice(i + 1).forEach((b) => {
        if (a.rects.some((ra) => b.rects.some((rb) => hit(box(ra), box(rb))))) out.push(`현황판 이름 겹침 ${a.label} · ${b.label}`);
      });
      if (a.rects.some(([x, , w]) => x < a.slot[0] || x + w > a.slot[1])) out.push(`현황판 이름 칸 밖 ${a.label}`);
      if (a.lines.some((t, k) => k && !/^[(（]/.test(t) && !a.label.includes(a.lines[k - 1] + ' ' + t))) out.push(`현황판 이름 낱말 끊김 ${a.label}`);
    });
    return { n: bs.length, lines: bs.map((b) => b.lines.length), board: bn.length, problems: out };
  }
  // 호버 잘림 점검(11-09 사용자) — 지금 화면의 모든 호버 글: 버튼 · 패널(data-tip · title) · 캔버스 칸(HITS) · 캐릭터
  function tipAudit() {
    const items = [];
    for (const n of document.querySelectorAll('[data-tip], [title]')) {
      const t = n.dataset.tip || n.getAttribute('title');
      if (t) items.push({ name: (n.id || n.textContent || '').trim().slice(0, 30) || n.tagName, html: textTip(t) });
    }
    for (const h of HITS) if (h.tip) items.push({ name: `칸 ${Math.round(h.x)},${Math.round(h.y)}`, html: h.tip });
    for (const a of actors.values()) items.push({ name: `캐릭터 ${a.name || a.key}`, html: actorTip(a) });
    return { n: items.length, problems: tipAuditOf(items) };
  }
  // 감독실 — 현황판 위 현장 이름만(11-09 카드는 [전체]로 — 감독실도 그 방만 보인다)
  // 11-09 사용자: ❗가 붙으면 이름이 밀려 잘렸다 — 바탕 상자는 이름 폭만 쟀는데 글은 "이름 ❗"를 가운데에 그려 이름이 왼쪽 상자 밖으로
  // 나갔고, 1024에서는 옆 칸 이름과 겹쳤다. 이제 이름은 표시와 상관없이 늘 칸 가운데 — 칸 폭에 들어갈 때까지 글씨를 줄이고(12px까지),
  // 그래도 넘치면 자르지 않고 줄을 바꾼다("라운지" / "(떠돌이)"). 표시(❗ · 🔥)는 이름 오른쪽에 자리가 있으면 거기, 없으면 이름 아래
  let BOARD_NAMES = [];
  function drawHQCards() {
    for (const s of boardSlots()) {
      const [x0, y0] = toScreen(s.x * T, s.y * T), [x1, y1] = toScreen((s.x + s.w) * T, (s.y + s.h) * T);
      const [lx, ly] = toScreen((s.x + s.w / 2) * T, (s.y + 0.35) * T);
      const st = siteState(s.r);
      const mark = st === 'alert' ? '❗' : st === 'fail' ? '🔥' : '';
      const room = x1 - x0 - 6;                                    // 옆 칸과 3px씩 띄운다
      let px = fpx(17);
      for (; px > fpx(12); px--) {
        ctx.font = `bold ${px}px system-ui, sans-serif`;
        if (ctx.measureText(s.r.label).width + 10 <= room) break;
      }
      ctx.font = `bold ${px}px system-ui, sans-serif`;
      const lines = wrapText(s.r.label, room - 10), LH = px + 5;
      const nw = Math.max(...lines.map((t) => ctx.measureText(t).width)) + 10, mw = ctx.measureText('❗').width + 6;
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      lines.forEach((t, i) => {
        ctx.fillStyle = '#000000aa'; ctx.fillRect(lx - nw / 2, ly + i * LH, nw, LH);
        ctx.fillStyle = st === 'fail' ? P.bad : st === 'alert' ? P.warn : P.label;
        ctx.fillText(t, lx, ly + i * LH + 2);
      });
      const rects = [[lx - nw / 2, ly, nw, lines.length * LH]];
      if (mark) {
        const right = lx + nw / 2 + mw <= x1 - 3;
        const mx = right ? lx + nw / 2 : lx - mw / 2, my = right ? ly : ly + lines.length * LH;
        ctx.fillStyle = '#000000aa'; ctx.fillRect(mx, my, mw, LH);
        ctx.fillText(mark, mx + mw / 2, my + 2);
        rects.push([mx, my, mw, LH]);
      }
      BOARD_NAMES.push({ label: s.r.label, lines, slot: [x0, x1], rects: rects.map((r) => r.map(Math.round)) });
      HITS.push({ x: x0, y: y0, w: x1 - x0, h: y1 - y0, soft: true, tip: boardTip(s.r) });
    }
  }

  // 현황판 — 마법학교: 거대한 양피지 지도 + 현장마다 촛불(작업중 밝게 · 승인 대기 붉게 맥박 · 실패면 꺼지고 연기 · 쉼 작게 · 없음 꺼짐)
  function drawBoard(now) {
    const b = HQ.board || {}, q = world.hq;
    const bx = q.x + (b.x ?? 3), by = q.y + (b.y ?? 0.4), bw = b.w ?? 22, bh = b.h ?? 5.4;
    const style = b.style || 'map';
    if (style === 'map') {
      rect(bx - 0.15, by - 0.15, bw + 0.3, bh + 0.3, '#3b2a1c');
      rect(bx, by, bw, bh, '#d8c49a');
      ctx.fillStyle = '#c4ab7a';
      for (let i = 0; i < 60; i++) { const h = tileHash(i, 3); ctx.fillRect((bx + (h % 1000) / 1000 * bw) * T, (by + ((h >>> 10) % 1000) / 1000 * bh) * T, 2, 2); }
    } else {
      rect(bx - 0.15, by - 0.15, bw + 0.3, bh + 0.3, style === 'monitors' ? '#11141a' : '#8a8f99');
      rect(bx, by, bw, bh, style === 'monitors' ? '#1b2230' : '#eef1f4');
    }
    boardSlots().forEach((s, i) => {
      const state = siteState(s.r);
      const cx = s.x + s.w / 2, top = s.y;
      if (style === 'map') {
        // 땅 모양 — 현장마다 다른 섬(해시로 정한 울퉁불퉁한 다각형) + 길
        ctx.fillStyle = ['#a9b97a', '#c9a46a', '#9fb0b8', '#b59ac0'][i % 4];
        ctx.beginPath();
        for (let k = 0; k < 12; k++) {
          const ang = (k / 12) * Math.PI * 2, rr = 0.75 + ((tileHash(i, k) % 100) / 100) * 0.35;
          const px = (cx + Math.cos(ang) * rr * s.w * 0.36) * T, py = (top + 2.3 + Math.sin(ang) * rr * 1.5) * T;
          k ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
        }
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = '#6b4f33'; ctx.lineWidth = 1; ctx.stroke();
        if (i) { ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo((s.x - s.w * 0.15) * T, (top + 2.3) * T); ctx.lineTo((s.x + s.w * 0.15) * T, (top + 2.3) * T); ctx.stroke(); ctx.setLineDash([]); }
        drawSiteCandle(cx, top + 3.3, state, now, i);
      } else if (style === 'monitors') {
        // 모니터 하나 — 어두운 화면, 위 띠가 상태 색(이상이면 깜빡), 안에 작업중 칸 · 토큰 막대 · 아이콘
        const c = { fail: P.bad, alert: P.warn, busy: P.act, idle: P.ok, empty: '#3a4356' }[state];
        const st = s.r.stats || {};
        rect(s.x + 0.4, top + 0.5, s.w - 0.8, bh - 1.4, '#0c0f15');
        rect(s.x + 0.6, top + 0.7, s.w - 1.2, bh - 1.8, state === 'empty' ? '#121722' : '#0f1a2a');
        ctx.globalAlpha = state === 'alert' || state === 'fail' ? 0.55 + 0.45 * Math.sin(now / 250) : 1;
        rect(s.x + 0.6, top + 0.7, s.w - 1.2, 0.35, c);
        if (state === 'alert' || state === 'fail') { ctx.strokeStyle = c; ctx.lineWidth = 2; ctx.strokeRect((s.x + 0.6) * T, (top + 0.7) * T, (s.w - 1.2) * T, (bh - 1.8) * T); }
        ctx.globalAlpha = 1;
        if (state !== 'empty') {
          for (let k = 0; k < Math.min(8, (st.ACTIVE || 0) + (st.IDLE || 0)); k++)   // 사람 칸 — 작업중은 밝게, 쉼은 어둡게
            rect(s.x + 0.9 + k * 0.55, top + 1.5, 0.4, 0.4, k < (st.ACTIVE || 0) ? P.act : '#3a4a66');
          const tok = Math.min(1, Math.log10(1 + (st.tout || 0)) / 6);
          rect(s.x + 0.9, top + 2.3, (s.w - 1.8) * tok, 0.25, '#5dd39e');                // 오늘 출력 토큰(로그 눈금)
          ctx.fillStyle = '#5dd39e55';
          for (let k = 0; k < 10; k++) { const v = (tileHash(k, i) % 100) / 100; ctx.fillRect((s.x + 0.9 + k * (s.w - 1.8) / 10) * T, (top + bh - 1.2 - v * 1.2) * T, 2, v * 1.2 * T); }
          if (state === 'alert') { ctx.fillStyle = P.warn; ctx.font = 'bold 12px ui-monospace, monospace'; ctx.textAlign = 'right'; ctx.fillText('!', (s.x + s.w - 0.9) * T, (top + 1.9) * T); }
          if (state === 'fail') { ctx.fillStyle = P.bad; ctx.font = 'bold 12px ui-monospace, monospace'; ctx.textAlign = 'right'; ctx.fillText('✕', (s.x + s.w - 0.9) * T, (top + 1.9) * T); }
        }
      } else {
        // 화이트보드 + 자석(현장마다) — 이상이면 빨간 자석
        const c = { fail: '#e03b2f', alert: '#e03b2f', busy: '#2f7de0', idle: '#2fae5a', empty: '#9aa0a8' }[state];
        ctx.strokeStyle = '#7d8590'; ctx.lineWidth = 1;
        for (let k = 0; k < 4; k++) { ctx.beginPath(); ctx.moveTo((s.x + 0.4) * T, (top + 1 + k) * T); ctx.lineTo((s.x + s.w - 0.4) * T, (top + 1 + k) * T); ctx.stroke(); }
        // 공정 막대(현장마다 고정 모양) — 손으로 그린 공정표 느낌
        for (let k = 0; k < 3; k++) {
          const hsh = tileHash(i * 5 + k, 9), len = 0.3 + (hsh % 60) / 100, st0 = ((hsh >>> 8) % 30) / 100;
          ctx.fillStyle = ['#7fb7ff', '#f2c14e', '#9fd8a8'][k] + 'cc';
          ctx.fillRect((s.x + 0.5 + st0 * (s.w - 1)) * T, (top + 1.15 + k) * T, len * (s.w - 1.6) * T, 5);
        }
        ctx.fillStyle = c; ctx.beginPath(); ctx.arc((s.x + s.w - 0.9) * T, (top + 1.4) * T, 5 + (state === 'alert' ? Math.sin(now / 200) * 1.5 : 0), 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#333'; ctx.stroke();
        // 사람마다 자석 — 작업중 파랑 · 쉼 초록 · 멈춤 회색, 승인 대기는 빨강
        const st = s.r.stats || {};
        const mags = [...Array(Math.min(st.pending || 0, 4)).fill('#e03b2f'), ...Array(st.ACTIVE || 0).fill('#2f7de0'), ...Array(st.IDLE || 0).fill('#2fae5a'),
                      ...Array((st.SUSPENDED || 0) + (st.DORMANT || 0)).fill('#9aa0a8')].slice(0, 10);
        mags.forEach((mc, k) => { ctx.fillStyle = mc; ctx.beginPath(); ctx.arc((s.x + 0.8 + k * 0.6) * T, (top + 4.2) * T, 3.5, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = '#0006'; ctx.stroke(); });
      }
      s.hit = { x: s.x, y: s.y, w: s.w, h: bh };
    });
  }

  function drawSiteCandle(x, y, state, now, i) {
    const t = now / 1000;
    // 촛대 · 초
    ctx.fillStyle = '#7a5a2e'; ctx.fillRect(x * T - 5, y * T + 6, 10, 2);
    ctx.fillStyle = state === 'fail' ? '#9a948a' : '#efe6cf'; ctx.fillRect(x * T - 2, y * T - 2, 4, 8);
    if (state === 'empty') return;                                   // 아무도 없다 — 꺼져 있다
    if (state === 'fail') {                                          // 꺼졌다 — 연기 한 줄
      for (let k = 0; k < 3; k++) {
        const p = ((t * 0.6) + k / 3) % 1;
        ctx.globalAlpha = 0.5 * (1 - p); ctx.fillStyle = '#5b5560';
        ctx.beginPath(); ctx.arc(x * T + Math.sin(p * 7 + i) * 2, y * T - 4 - p * 14, 1.5 + p * 2.5, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;
      return;
    }
    const red = state === 'alert';
    const big = state === 'busy' || red;
    const flick = Math.sin(t * 11 + i * 2) * 0.5 + Math.sin(t * 17 + i) * 0.3;
    const size = big ? 1 : 0.55;
    const col = red ? '#ff4b3a' : '#ffb347';
    glow(x * T, (y - 0.35) * T, (big ? 26 : 12) * (red ? 0.9 + 0.25 * Math.sin(t * 5) : 1), col, big ? 0.45 : 0.25);
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.ellipse(x * T, y * T - 5 * size - 2, 2.2 * size + 0.6, (5 + flick) * size, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = red ? '#ffd0c8' : '#fff3c0';
    ctx.beginPath(); ctx.ellipse(x * T, y * T - 3 * size - 2, 1 * size, 2.5 * size, 0, 0, Math.PI * 2); ctx.fill();
  }

  function drawHQS(now, sorted) {
    const q = world.hq;
    drawFloor(q.x + 1, q.y + 2, q.w - 2, q.h - 3, (HQ.floor && ((RS.proc && RS.proc[HQ.floor]) || HQ.floor)) || FLOOR, 5);
    drawWalls(q);
    for (const d of HQ.decor || []) if (d.s || d.fx) placeDecor(d, q.x, q.y, now, sorted);
    drawBoard(now);
    drawUsageLamp(now);
  }

  function drawHQShapes(now) {
    const q = world.hq;
    for (let i = 0; i < q.w; i++) for (let j = 0; j < q.h; j++) rect(q.x + i, q.y + j, 1, 1, (i + j) % 2 ? P.office : '#3f3a56');
    ctx.strokeStyle = P.officeGlass; ctx.lineWidth = 3; ctx.strokeRect(q.x * T, q.y * T, q.w * T, q.h * T);
    rect(q.x + 11, q.y + 9, 6, 1.2, P.deskTop); rect(q.x + 11, q.y + 10.2, 6, 0.3, P.desk);
    rect(q.x + 12.3, q.y + 8.4, 1.2, 0.8, '#1b1f27'); rect(q.x + 14.5, q.y + 8.4, 1.2, 0.8, '#1b1f27');   // 듀얼 모니터
    drawBoard(now);
    drawUsageLamp(now);
  }

  // ── 머리말 · 정보 패널 ──────────────────────────────
  // 머리말 프로젝트 줄(11-05) — 감독실에 나갔다 오지 않고 바로 다른 방으로. 지금 방은 눌린 모양.
  // 숫자: 작업 중 n · 승인 대기 n. 점: 승인 대기(노랑 깜빡) · 안 본 새 답(파랑) — 그 방을 보면 지워진다
  const seenAt = new Map();                 // 방 → 마지막으로 본 때(이 화면을 연 때부터 센다)
  const openedAt = Date.now();
  function drawProjects(st) {
    if (!world) return;
    const rooms = [...world.rooms, ...(world.lounge && world.lounge.sessionIds && world.lounge.sessionIds.length ? [world.lounge] : [])];
    const now = Date.now();
    const html = rooms.map((r) => {
      const key = r.name || '_lounge';
      if (view === key) seenAt.set(key, now);
      const ss = (r.sessionIds || []).map((id) => st.sessions.get(id)).filter(Boolean);
      const act = ss.filter((s) => s.state === 'ACTIVE' || viewState(s) === 'WAITING').length;
      const pend = (r.stats && r.stats.pending) || 0, ques = (r.stats && r.stats.question) || 0;
      const lastReply = Math.max(0, ...ss.map((s) => s.replyAt || 0));
      const unseen = lastReply > Math.max(openedAt, seenAt.get(key) || 0);
      const dot = pend || ques ? '<i class="pdot warn"></i>' : unseen ? '<i class="pdot new"></i>' : '';
      const nums = [act ? `<span class="pn">작업 ${act}</span>` : '', pend ? `<span class="pn warn">승인 ${pend}</span>` : '',
        ques ? `<span class="pn warn">질문 ${ques}</span>` : ''].join('');
      const rs = r.stats || {};
      // 11-09 툴팁 모양(제목 — 설명 / 숫자 한 줄에 하나). "출력 74k · Opus 출력 94k"가 헷갈렸다 — 앞은 본 대화만, 뒤는
      // 서브에이전트 포함이었다. 출력은 서브에이전트 포함 하나로, Opus는 그중 %로
      const allOut = rs.all_out || rs.tout || 0;
      const tip = `${r.label} — 이 방으로 가서 주요 세션 대화를 엽니다.`
        + (act || pend || ques ? `\n작업 중 ${act}${pend ? ` · 승인 대기 ${pend}` : ''}${ques ? ` · 질문 ${ques}` : ''}` : '') + (unseen ? '\n안 본 새 답 있음' : '')
        + `\n오늘 쓴 글 ${fmt(allOut)} 토큰${rs.opus_out && allOut ? ` (그중 Opus ${Math.round(100 * rs.opus_out / allOut)}%)` : ''}`
        + `\n오늘 읽은 양 ${fmt(rs.tin || 0)} 토큰 (대화 다시 읽기 포함)`;
      return `<button class="ghost oproj-b${view === key ? ' on' : ''}${pend || ques ? ' pend' : ''}" data-room="${esc(key)}" data-tip="${esc(tip)}" aria-pressed="${view === key}">${dot}${esc(r.label)}${nums}</button>`;
    }).join('');
    if ($('oProj').innerHTML !== html) $('oProj').innerHTML = html;
  }
  function header(st) {
    const c = st.conn;
    $('oConn').className = 'conn ' + c.status;
    $('oConn').textContent = { up: '연결됨', down: '끊김', connecting: '연결 중', auth: '토큰 필요', idle: '연결 전' }[c.status] || c.status;
    const pl = [...st.approvals.values()].filter((a) => a.status === 'pending');
    const ques = pl.filter((a) => a.tool === 'AskUserQuestion').length, pend = pl.length - ques;
    const ig = st.ingest;
    // 전체 요약(클래식 머리말과 같은 숫자) + 적재가 막히면 무엇이 막혔는지(마우스를 올리면)
    let active = 0, live = 0, outToday = 0, subs = 0;
    for (const s of st.sessions.values()) {
      if (s.state === 'ACTIVE' || viewState(s) === 'WAITING') active++;
      if (s.state !== 'DORMANT') live++;
      outToday += (s.tokens && s.tokens.today_output) || 0;
      subs += s.subagents_running || 0;
    }
    const igWhy = !ig ? '' : ig.stalled ? `화면 갱신 멈춤 — 세션 기록을 읽어 화면을 바꾸는 감시가 멈췄습니다.\n트랜스크립트 감시가 ${ig.tick_age_s}초째 멈춰 있습니다`
      : '기록 못 읽는 세션 — 브리지가 이 세션들의 대화 기록을 읽지 못해 화면이 늦습니다.\n' + (ig.stuck || []).map((x) => `${x.session} ${x.minutes}분 · ${x.failures}번 — ${x.error}`).join('\n');
    $('oAlerts').innerHTML = (pend ? `<button id="oPend" class="ghost warn" title="승인 대기 — 누르면 그 세션 패널을 엽니다. 거기서 승인하거나 거부합니다.">❗ 승인 대기 ${pend}</button>` : '') +
      (ques ? `<button id="oAsk" class="ghost warn" title="질문 — 세션이 고를 것을 묻고 있습니다. 누르면 그 세션 패널을 엽니다. 선택지를 누르면 답이 들어갑니다.">❓ 질문 ${ques}</button>` : '') +
      (ig && !ig.ok ? `<span class="bad" title="${esc(igWhy)}">⚠ ${ig.stalled ? '화면 갱신 멈춤' : `기록 못 읽는 세션 ${(ig.stuck || []).length}`}</span>` : '');
    const stat = `작업 중 <b>${active}</b>/${live}${subs ? ` · 서브에이전트 ${subs}` : ''} · 출력 토큰 ${fmt(outToday)}`;
    if ($('oStat').innerHTML !== stat) $('oStat').innerHTML = stat;
    // data-tip으로 바로(11-09 — title을 매번 다시 붙여 기본 툴팁과 둘이 떴다)
    $('oStat').dataset.tip = `지금 상태 — 일하는 세션 수와 오늘 쓴 양입니다. 출력 토큰은 CC가 쓴 글의 양입니다.`
      + `\n작업 중 ${active} / 켜진 세션 ${live}${subs ? `\n서브에이전트 ${subs}` : ''}\n오늘 출력 ${fmt(outToday)} 토큰`;
    $('oMap').disabled = view === 'hq';
    $('oAll').disabled = view === 'map';
    drawProjects(st);
    // 연결 끊김 — 캔버스를 가리지 않는 띠 + 캔버스를 흐리게(보이는 모습이 끊기기 전 것이라는 표시)
    const down = c.status === 'down';
    $('oDown').hidden = !down;
    $('oStage').classList.toggle('offline', down || c.status === 'auth');
    if (down) {
      $('oDownWhy').textContent = `${c.reason || '브리지와 연락이 없습니다'} — ${new Date(c.since).toLocaleTimeString()}부터`;
      $('oDownNext').textContent = c.nextIn ? `${c.nextIn}초 뒤 다시 연결합니다 (시도 ${c.attempt})` : `연결하는 중입니다… (시도 ${c.attempt})`;
    }
    if (c.status === 'auth') $('tokDlg').classList.add('on');
  }

  // 고른 캐릭터를 패널에 알린다 — 세션은 store.select(대화를 불러온다), 서브에이전트는 부모 세션, 인프라 · 포먼은 파이프라인 · 세션 목록
  function info() {
    const a = selected && actors.get(selected);
    if (!a) return;
    const owner = a.kind === 'mini' ? actors.get(a.parent) : a;
    if (owner && owner.kind === 'session') {
      if (store.state.selected !== owner.s.id) store.select(owner.s.id);
      remember(owner.s.id);
      panel.show({ kind: 'session' });
    } else if (a.kind === 'infra') {
      const r = world.rooms.find((q) => q.name === a.room), st = r ? r['st_' + a.infra] : 'none';
      panel.show({ kind: 'infra', room: a.room, infra: a.infra, name: a.name, status: STATUS_KO[st] || st });
    } else if (a.kind === 'courier') {
      panel.show({ kind: 'infra', room: a.room, infra: 'courier', name: a.name, status: courierNow(a.plan) });
    } else if (a.kind === 'foreman') {
      // 11-08 — 세션 목록 대신: 패널엔 그 프로젝트 노트, 가운데엔 말하기 창(제안이 있으면 그 계획)
      const room = a.room === '_hq' ? null : a.room;
      panel.show({ kind: 'foreman', room, name: a.name });
      const pend = a.fm && a.fm.pending[0];
      if (window.foremanChat) (pend ? window.foremanChat.openDispatch(pend.dispatch_id) : window.foremanChat.open(room));
    } else if (a.kind === 'scribe') {
      // 서기실 — 무엇을 시킬지 고르는 창 · 할 일 · Notion 게시. "정리할까요?"가 떠 있으면 「나중에 할 일 정리」를 고른 채(누르는 것은 사람)
      panel.show({ kind: 'scribe', room: a.room, pick: a.todo && a.todo.nudge ? 'later' : null });
    } else if (a.kind === 'coder') {
      panel.show({ kind: 'coder', room: a.room });            // 코더 — 맡길 일 · 지금 일(11-09)
    }
  }
  // 패널(승인 카드의 "세션" · 세션 목록)에서 고르면 그 현장으로 가서 캐릭터를 고른다
  function openSession(sid) {
    const key = 's:' + sid, a = actors.get(key);
    if (a && view !== a.room) { view = a.room || '_lounge'; aim(); header(store.state); }
    selected = a ? key : null;
    store.select(sid);
    remember(sid);
    panel.show({ kind: 'session' });
  }

  // 방마다 마지막으로 본 세션(11-08 사용자 — 프로젝트를 오갈 때마다 캐릭터를 눌러야 대화가 떴다). 이 브라우저에만
  const LAST_KEY = 'foremanLastSess:';
  function remember(sid, room) {
    const a = actors.get('s:' + sid);
    const key = a ? (a.room || '_lounge') : room;              // 끝난 세션은 캐릭터가 없다 — 머리말에서 고른 방으로
    if (!key) return;
    try { localStorage.setItem(LAST_KEY + key, String(sid)); } catch { /* 이번만 */ }
  }
  // 머리말에서 방을 누르면 열 세션: 작업 중(승인 대기 포함)이 있으면 그중 가장 최근에 움직인 것,
  // 다 쉬면 마지막으로 본 것(그 방에 아직 있으면), 그것도 없으면 가장 최근에 움직인 것
  function pickSession(key) {
    const r = [...world.rooms, world.lounge].find((q) => q && (q.name || '_lounge') === key);
    const ss = ((r && r.sessionIds) || []).map((id) => store.state.sessions.get(id)).filter(Boolean);
    if (!ss.length) return null;
    const moved = (s) => Date.parse(s.last_ts || 0) || 0;
    const latest = (xs) => xs.reduce((b, s) => (moved(s) > moved(b) ? s : b));
    const busy = ss.filter((s) => s.state === 'ACTIVE' || viewState(s) === 'WAITING');
    if (busy.length) return latest(busy).id;
    let last = null;
    try { last = Number(localStorage.getItem(LAST_KEY + key)); } catch { /* 기억 없음 */ }
    if (last && ss.some((s) => s.id === last)) return last;
    const live = ss.filter((s) => s.state !== 'DORMANT');
    return latest(live.length ? live : ss).id;
  }
  function goRoom(key) {
    go(key);
    const sid = pickSession(key);
    if (sid != null) { openSession(sid); remember(sid, key); }
  }

  // 스키마 잠금 풀기(11-09) — 사람이 확인한 뒤에만. 실패하면 까닭을 띄운다
  async function unlockSchema(project) {
    const lk = schemaBoard.locks && schemaBoard.locks[project];
    if (!lk) return;
    const label = (store.state.projects.find((p) => p.name === project) || {}).label || project;
    const who = lk.session_id ? `세션 ${lk.session_id}` : `세션 ${lk.cc}`;
    if (!confirm(`${label}의 DB 구조 잠금을 풉니다. 지금은 ${who}(${lk.wt ? `worktree ${lk.wt}` : '원본 폴더'})이 ${hmOf(lk.since)}부터 쥐고 있습니다. 그 세션이 아직 마이그레이션을 쓰는 중이면 두 세션의 스키마가 겹칠 수 있습니다. 풀까요?`)) return;
    try {
      const r = await fetch(`/api/schema-lock/${encodeURIComponent(project)}`, { method: 'DELETE', headers: store.headers() });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.released) alert(`잠금을 풀지 못했습니다 — ${j.refused || j.detail || (r.ok ? '이미 풀려 있습니다' : `HTTP ${r.status}`)}`);
    } catch (e) { alert(`잠금을 풀지 못했습니다 — ${e.message}`); }
    await loadSchemaBoard();
  }

  // ── 입력 ───────────────────────────────────────────
  cv.addEventListener('click', (ev) => {
    const r = cv.getBoundingClientRect();
    const px = ev.clientX - r.left, py = ev.clientY - r.top;
    for (const room of [...world.rooms, world.lounge]) {
      const b = room.badge;
      const k = BANNER_LINK;
      if (k && view !== 'hq' && view !== 'map' && px >= k.x && px <= k.x + k.w && py >= k.y && py <= k.y + k.h) { window.open(k.url, '_blank', 'noopener'); return; }
      const lk = BANNER_LOCK;
      if (lk && view !== 'hq' && view !== 'map' && px >= lk.x && px <= lk.x + lk.w && py >= lk.y && py <= lk.y + lk.h) { unlockSchema(lk.project); return; }
      if (b && px >= b.x && px <= b.x + b.w && py >= b.y && py <= b.y + b.h) { go(room.name || '_lounge'); return; }
    }
    const [wx, wy] = toWorld(px, py);
    if (view === 'hq') {                                   // 현황판의 현장 자리를 눌러도 들어간다
      const s = boardSlots().find((b) => wx >= b.x * T && wx <= (b.x + b.w) * T && wy >= b.y * T && wy <= (b.y + b.h) * T);
      if (s) { go(s.r.name || '_lounge'); return; }
    }
    if (view === 'map') {
      const room = [...world.rooms, world.lounge].find((q) => wx >= q.x * T && wx <= (q.x + q.w) * T && wy >= q.y * T && wy <= (q.y + q.h) * T);
      if (room) go(room.name || '_lounge');
      return;
    }
    // 일하는 상주 코더의 말풍선(맡길 일)을 누르면 코더 목록(11-09) — 캐릭터를 누르면 세션이 열린다
    for (const [k, b] of BUBBLES) {
      const a = actors.get(k);
      if (!a || !a.resident || !b.rect) continue;
      const [x, y, w, h] = b.rect;
      if (wx >= x && wx <= x + w && wy >= y && wy <= y + h) { panel.show({ kind: 'coder', room: a.room }); return; }
    }
    let best = null, bd = 1.4 * T;
    for (const [k, a] of actors) {
      const d = Math.hypot(a.x * T - wx, a.y * T - 8 - wy);
      if (d < bd) { bd = d; best = k; }
    }
    if (!best) return;                   // 빈 바닥을 눌러도 패널은 그대로(입력하던 것을 잃지 않게). 해제는 패널의 ✕
    selected = best;
    info();
  });
  // ── 마우스를 올리면(11-05) — 이름표는 그 구역이 하는 일, 캐릭터는 이름 · 지금 하는 일. 누르지 않아도 보인다 ──
  function actorAt(wx, wy) {
    let best = null, bd = 1.4 * T;
    for (const [k, a] of actors) {
      if (view !== 'map' && a.room !== (view === '_lounge' ? null : view) && !(view === 'hq' && a.room === '_hq')) continue;
      const d = Math.hypot(a.x * T - wx, a.y * T - 8 - wy);
      if (d < bd) { bd = d; best = a; }
    }
    return best;
  }
  // 코더 맡길 일 호버 줄(11-09) — 몇 개 · 앞의 셋
  function coderJobsTip(jobs) {
    if (!jobs || !jobs.length) return '';
    const line = (j) => (j.kind === 'rested' ? `합치기 기다림 — ${j.title}${j.days >= REST_DAYS ? ` · ${j.days}일째` : ''}` : j.title);
    return `<div>맡길 일 ${jobs.length} — 코더에게 받은 할 일과 브리지가 이미 아는 신호입니다.${jobs.slice(0, 3).map((j) => `<div class="tip-s">· ${esc(short(line(j), 60))}</div>`).join('')}${jobs.length > 3 ? `<div class="tip-s">… ${jobs.length - 3}개 더</div>` : ''}</div>`;
  }
  function actorTip(a) {
    const roleKey = (r) => ((theme.tags && theme.tags.roles) || {})[r];
    const zoneName = (go) => {                     // 지금 가 있는 구역의 이름표 · 하는 일
      const key = go === 'desk' ? 'desks' : go;
      const v = ((theme.tags && theme.tags.zones) || {})[key];
      const nm = Array.isArray(v) ? v[0] : v;
      const role = ZONE_ROLE[roleKey(key)];
      return nm ? `${esc(nm)}${role ? ` — ${esc(role.what)}` : ''}` : '';
    };
    if (a.kind === 'session' && a.s) {
      const s = a.s;
      const now = s.state === 'ACTIVE' ? (s.activity ? `${esc(s.activity.tool)} ${softEsc(short(s.activity.target || '', 70))}` : '생각 중') : '';
      const vs = viewState(s), bg = s.background || [];
      // 코더 상주(11-09) — 상주 코더의 몸을 쓰는 세션은 "코더 · 일 N", 임시 일꾼은 어느 세션 · 무슨 일인지
      const who = a.resident ? `<div class="tip-s">코더 · 일 ${a.coders || 1} — 이 방 코더가 맡은 세션입니다.${a.coders > 1 ? ` 나머지 ${a.coders - 1}개는 임시 일꾼이 합니다.` : ''}</div>${coderJobsTip(a.jobs)}${a.jobs && a.jobs.length ? '<div class="tip-t">머리 위 말풍선을 누르면 맡길 일 목록이 열립니다.</div>' : ''}`
        : a.temp ? `<div class="tip-s">임시 일꾼 — 이 방에 코더 세션이 둘 이상이라 세션 ${s.id}을 맡았습니다. 세션이 끝나면 사라집니다.</div>` : '';
      // 11-09 사용자 — 이름표는 역할만이라 호버 첫 줄에 역할 · 세션 번호 · 제목("237 합쳐라"를 듣고 어느 세션인지 찾게)
      return `<div class="tip-h">${esc(roleTag(roleOf(s)))} 세션 ${s.id}${a.temp ? ' · 임시' : ''}</div><div class="tip-b">${esc(a.name)}</div>${who}<div class="tip-b">${esc({ ACTIVE: '작업 중', IDLE: '쉬는 중', WAITING: '기다리는 중', SUSPENDED: '멈춤', DORMANT: '종료' }[vs] || vs)}${
        a.act && a.act.go ? ` · ${zoneName(a.act.go)}` : ''}</div>${now ? `<div>${now}</div>` : ''}${
        s.subagents_running ? `<div>서브에이전트 ${s.subagents_running}개 돎${(s.subagent_descs || []).map((d) => `<div class="tip-s">· ${esc(short(d, 50))}</div>`).join('')}</div>` : ''}${
        bg.length ? `<div>뒤에서 도는 일 ${bg.length}개(백그라운드 명령)${bg.map((x) => `<div class="tip-s">· ${esc(x.tool)} ${esc(short(x.description || x.task, 50))}</div>`).join('')}</div>` : ''}${
        a.act && a.act.flag ? `<div class="tip-s">${esc({ approval_pending: '승인 대기', stuck_turn: '끝났는지 모름 — 끝 신호가 오지 않았습니다' }[a.act.flag] || a.act.flag)}</div>` : ''}${
        a.subHidden ? `<div class="tip-s">+${a.subHidden} — 서브에이전트가 많아 화면에 다 그리지 않고 접은 수입니다.</div>` : ''}${
        s.compact && s.compact.level ? `<div class="tip-s">📦 대화 자동 요약 ${s.compact.count}번(대화가 길어 앞부분을 요약해 줄였습니다. 줄일수록 처음에 정한 것을 잊습니다) —${s.compact.level === 'late' ? '늦었습니다' : '새 세션으로 넘어갈 때입니다'}</div>` : ''}
        <div class="tip-t">누르면 대화가 열립니다.</div>`;
    }
    if (a.kind === 'mini') return `<div class="tip-h">서브에이전트</div><div>${esc(a.name)}</div><div class="tip-t">누르면 부모 세션이 열립니다.</div>`;
    if (a.kind === 'infra') {
      const r = world.rooms.find((q) => q.name === a.room), st = r ? r['st_' + a.infra] : 'none';
      return `<div class="tip-h">${esc(a.name)}</div>${tipOf(INFRA_ROLE[a.infra])}<div class="tip-s">지금: ${esc(STATUS_KO[st] || st)}${st === 'waiting' ? ' — ' + WAIT_TIP : ''}</div>`;
    }
    if (a.kind === 'courier') {
      const ch = a.plan && a.plan.ch, c = ch && ch.commits && ch.commits[0];
      return `<div class="tip-h">${esc(a.name)}</div><div class="tip-b">출하 라인 담당</div><div>커밋을 받아 단계마다 옮기는 사람입니다.</div>
        <div class="tip-s">${esc(courierNow(a.plan))}${a.plan && a.plan.st === 'waiting' ? ' — ' + WAIT_TIP : ''}</div>${c ? `<div class="tip-t">${esc(c.short)} ${esc(short(c.subject || '', 70))}</div>` : ''}${
        a.plan && a.plan.queue.length ? `<div class="tip-t">대기 ${a.plan.queue.length}개</div>` : ''}<div class="tip-t">누르면 파이프라인이 열립니다.</div>`;
    }
    if (a.kind === 'foreman') {
      const fm = a.fm || { running: false, pending: [] };
      const now_ = fm.running ? '지금 계획을 세우는 중입니다.' : fm.pending.length ? `시작할 일 ${fm.pending.length} — 세워 둔 계획 중 [시작]을 기다리는 것입니다.` : '기다리는 중입니다.';
      return `<div class="tip-h">${esc(a.name)}</div>${tipOf(ZONE_ROLE.hq)}<div class="tip-s">${now_}</div>${
        fm.pending.slice(0, 2).map((x) => `<div class="tip-t">· ${esc(short(x.title || x.why || '', 60))}</div>`).join('')}<div class="tip-t">누르면 말하기 창이 열립니다. 세션은 없습니다.</div>`;
    }
    if (a.kind === 'scribe') {
      const t = a.todo;
      return `<div class="tip-h">서기</div><div class="tip-b">문서 담당 — 회고 · 문서 점검 · README · CLAUDE.md · 나중에 할 일 · Notion 게시</div>${
        t && t.nudge ? `<div class="tip-s">정리할까요? — 서기 몫 받은 할 일이 쌓였습니다(${esc(t.nudge.why)}). 누르면 「나중에 할 일 정리」를 고른 창이 열립니다. [시키기]를 눌러야 세션이 뜹니다.</div>` : ''}${
        t && t.items && t.items.length ? `<div>문서 할 일 ${t.items.length} — README가 낡은 것처럼 브리지가 찾은 문서 정리 거리입니다. 누르면 서기에게 맡깁니다.${t.items.slice(0, 3).map((x) => `<div class="tip-s">· ${esc(x.title)}</div>`).join('')}</div>` : ''}
        <div class="tip-t">누르면 일을 고르는 창이 열립니다.</div>`;
    }
    if (a.kind === 'coder') {
      return `<div class="tip-h">코더</div><div class="tip-b">코딩 담당 — 지금은 세션이 없어 자리에서 쉽니다. 코더 세션이 뜨면 책상으로 가서 일합니다.</div>${coderJobsTip(a.jobs)}
        <div class="tip-t">누르면 맡길 일 목록이 열립니다.</div>`;
    }
    return `<div class="tip-h">${esc(a.name || '')}</div>`;
  }
  // 툴팁은 화면 전체가 하나(tip.js) — 이름표 · 캐릭터 · 버튼이 같은 모양 · 같은 지연으로 뜬다(11-05)
  cv.addEventListener('mousemove', (ev) => {
    const r = cv.getBoundingClientRect();
    const px = ev.clientX - r.left, py = ev.clientY - r.top;
    const hit = HITS.find((h) => px >= h.x && px <= h.x + h.w && py >= h.y && py <= h.y + h.h);
    let html = hit ? hit.tip : null, key = hit ? 'tag:' + hit.x + ':' + hit.y : null, onActor = false;
    if (!html && view !== 'map') {
      const [wx, wy] = toWorld(px, py);
      const a = actorAt(wx, wy);
      if (a) { html = actorTip(a); key = 'actor:' + a.key; onActor = true; }
    }
    cv.style.cursor = onActor ? 'pointer' : '';
    if (!html) { hideTip(); return; }
    showTip(html, ev.clientX, ev.clientY, key);
  });
  cv.addEventListener('mouseleave', () => { hideTip(); cv.style.cursor = ''; });
  // 현장을 옮겨도 고른 세션 · 패널은 그대로 둔다
  function go(v) { view = v; aim(); header(store.state); }
  $('oMap').onclick = () => go('hq');
  $('oAll').onclick = () => go('map');
  $('oProj').addEventListener('click', (ev) => { const b = ev.target.closest('[data-room]'); if (b) goRoom(b.dataset.room); });
  // + 새 세션(11-05) — 지금 보고 있는 현장을 기본 프로젝트로. 띄우면 그 세션을 골라 패널에 연다
  const newSession = mountNewSession(store, { onCreated: (sid) => setTimeout(() => openSession(sid), 300) });
  $('oNew').onclick = () => newSession.open(view !== 'hq' && view !== 'map' && view !== '_lounge' ? view : null);
  // 11-09 [＋ 할 일] — 받는 함에 적는다(세션 없음). 적으면 서기 머리 위 "할 일 N"을 다시 센다
  const todoInbox = mountTodoInbox(store, { onSaved: () => { loadScribeTodo(); loadCoderTodo(); } });
  $('oTodo').onclick = () => todoInbox.open(view !== 'hq' && view !== 'map' && view !== '_lounge' ? view : null);
  window.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    if (ev.target.closest && ev.target.closest('input, textarea, select')) return;   // 입력 칸에서 친 Esc는 칸이 처리
    if ($('tokDlg').classList.contains('on')) { $('tokDlg').classList.remove('on'); return; }
    go('hq');
  });
  // 11-10 답은 그 세션 패널에서만 — 누르면 기다리는 것 중 가장 오래된 것의 세션 패널을 연다(세션을 모르면 패널만)
  $('oAlerts').addEventListener('click', (ev) => {
    const b = ev.target.closest('#oPend, #oAsk');
    if (!b) return;
    const ask = b.id === 'oAsk';
    const a = [...store.state.approvals.values()].filter((x) => x.status === 'pending' && (x.tool === 'AskUserQuestion') === ask)
      .sort((x, y) => x.id - y.id).find((x) => x.session_id != null);
    if (a) openSession(a.session_id);
    panel.setOpen(true);
  });
  $('oRetry').onclick = () => store.retryNow();
  $('oTok').onclick = () => { $('tokDlg').classList.add('on'); $('tokInput').focus(); };
  $('tokCancel').onclick = () => $('tokDlg').classList.remove('on');
  $('tokInput').oninput = () => { const n = $('tokInput').value.trim().replace(/^FOREMAN_API_TOKEN=/, '').length; $('tokLen').textContent = n ? `길이 ${n}` : ''; };
  $('tokForm').onsubmit = (ev) => {
    ev.preventDefault();
    store.token = $('tokInput').value;
    $('tokInput').value = '';
    $('tokDlg').classList.remove('on');
    store.start();
  };
  // 패널 · 터미널이 펴지고 접히면 무대 크기가 바뀐다 — 창 크기만 보지 않고 무대를 직접 본다
  new ResizeObserver(() => resize()).observe($('oStage'));
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    running = !document.hidden;
    if (running) { last = performance.now(); requestAnimationFrame(frame); }
  });

  resize();
  store.subscribe(rebuild);
  requestAnimationFrame(frame);
  return { go, theme, openSession, panel, actors, newSession: (p) => newSession.open(p), openTodo: (p, to) => todoInbox.open(p, to), foremanName: FM_NAME,
           audit: () => audit(), propAudit: () => propAudit(), propSheet: (z, f) => propSheet(z, f), probe: (x, y) => probe(x, y), rects: (w) => decorRects(w), layoutAudit: (o) => layoutAudit(o), labelAudit: () => labelAudit(), gridAudit: () => gridAudit(), camScale: () => ({ cam: cam.s, room: roomViewScale() }), roomLabels: (name) => roomLabels(world.rooms.find((r) => r.name === name) || null).map((l) => ({ ...l, box: labelBox(l) })),furnRects: (w) => furnRects(w), standSpots: () => standSpots(), bannerAudit: () => bannerAudit(), cardAudit: () => cardAudit(), tipAudit: () => tipAudit(), tagRects: (w) => tagRects(w), bodySize: () => bodySize(), bubbleAudit: () => bubbleAudit(), nameAudit: () => nameAudit(), names: () => NAMES.slice(),
           // 터미널을 열 때 고를 프로젝트(11-10) — 보고 있는 현장, 없으면(감독실 · 지도 · 라운지) 고른 세션의 프로젝트, 그것도 없으면 null
           currentProject: () => (world.rooms.some((r) => r.name === view) ? view
             : ((store.state.sessions.get(store.state.selected) || {}).project || null)),
           hits: () => HITS.filter((h) => !h.soft).map((h) => ({ rect: [h.x, h.y, h.w, h.h].map(Math.round), zone: h.zone || null })),
    // 시연 사진(13) — 이름표 자리(캔버스 기준 화면 좌표)와 캐릭터 발밑 화면 좌표. 툴팁을 띄워 찍을 때 마우스를 그 자리로 보낸다
    hits: () => HITS.map((h) => ({ x: h.x, y: h.y, w: h.w, h: h.h, zone: h.zone || null })),
    actorScreen: (key) => { const a = actors.get(key); return a ? toScreen(a.x * T, a.y * T) : null; }, layoutPlan: () => layoutPlan(), debug: () => [...actors.values()].map((a) => ({ key: a.key, room: a.room, x: String(a.x), y: String(a.y), tx: a.tx, ty: a.ty,
                                                                       anim: a.act && a.act.anim, go: a.act && a.act.go, face: a.face, dir: a.dir, char: a.char })) };
}

function hueOf(id) { return (id * 47) % 360; }
function short(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
