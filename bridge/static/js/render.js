// FOREMAN 대시보드 — 그리는 쪽(6단계, 실용 화면). store.js의 state만 본다.
// 10단계 테마 렌더러는 이 파일 대신 같은 state를 받아 캐릭터로 그리면 된다(createRenderer(root, store)만 맞추면 된다).
// 영역(conn · approvals · grid · panel)마다 state.ver가 바뀐 것만 다시 그린다. 입력 칸 · 스크롤은 다시 그려도 유지한다.

const STATE_LABEL = { ACTIVE: '작업 중', IDLE: '대기', SUSPENDED: '정지', DORMANT: '종료' };
const ORIGIN_LABEL = { human: '나', task_notification: '완료 알림', subagent_message: '서브에이전트 결과', agent_message: '다른 세션', meta: '시스템' };
const END_LABEL = { stop: '끝남', stop_failure: 'API 오류', interrupted: '중단', session_end: '세션 종료', process_lost: '프로세스 사라짐', merged: '다음 입력에 합쳐짐', no_signal: '신호 없음', abandoned: '끝 신호 없이 버려짐' };

import { stuckTurn } from './store.js';

const ROLE_LABEL = { coder: '코더', foreman: '포먼', cicd: 'CI/CD', inspector: '점검', helper: '도우미', infra: '인프라' };

// 세션을 알아보는 이름 — CC가 붙인 제목 → CC 세션 이름 → 짧은 id. 캐릭터 이름은 아래 줄에(한 캐릭터에 세션 여럿)
export function sessionName(s) { return s.title || s.cc_name || s.short; }
function sessionSub(s) {
  return [s.character, ROLE_LABEL[s.role] || s.role, s.short, s.tmux_pane].filter(Boolean).join(' · ');
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function ago(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
  if (s < 60) return `${s}초 전`;
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
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
function promptText(p) {
  if (!p) return '';
  return p.replace(/^\s*<pasted_content id="[0-9a-f]+">\s*/, '').replace(/\s*<\/pasted_content id="[0-9a-f]+">\s*$/, '').trim();
}
function oneLine(s, n) {
  s = promptText(s).replace(/\s+/g, ' ');
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}
function why(s) {
  if (!s.pid) return '프로세스가 없다';
  if (s.proc === 'T') return '정지(SUSPENDED) — 입력이 셸 명령으로 실행된다';
  if (!s.tmux_pane) return 'tmux 밖 세션 — 주입할 pane이 없다';
  return '';
}

// ── 8단계 파이프라인 — 프로젝트마다 인프라 캐릭터와 최근 체인(커밋 → Jenkins → Harbor → ArgoCD), 깨진 곳은 붉게 ──
const PIPE_STAGES = [['jenkins', 'Jenkins'], ['harbor', 'Harbor'], ['argocd', 'ArgoCD']];
const PIPE_MARK = { success: '✓', failed: '✗', running: '…', waiting: '⏸ Sync 대기' };   // waiting — 수동 Sync 앱, 실패 아님(11-03)
const INFRA_LABEL = { IDLE: '응답', ACTIVE: '일하는 중', STALE: '응답 없음' };
function pipeBlock(pp) {
  if (!pp) return '';
  const infra = pp.infra.filter((c) => !c.retired);
  if (!infra.length && !pp.chains.length && !pp.waiting.length && !pp.watch && !pp.webhook_broken) return '';
  // 빠진 알림 찾기(11-03): push 뒤 시작 알림이 없으면 3분에 노란색, 17분에 빨간색(텔레그램도)
  const w = pp.watch;
  const watch = w && w.state !== 'ok'
    ? `<div class="small ${w.state === 'missing' ? 'bad' : 'warn'}">${w.state === 'missing' ? '빌드 알림 없음 — Jenkins 확인' : '빌드 시작 알림 없음 — 폴링 안전망 대기'}: push <code class="sha">${esc(w.short)}</code> ${esc(oneLine(w.subject || '', 60))} · ${ago(w.since)}</div>`
    : (w ? `<div class="small muted">빌드 기다리는 중: push <code class="sha">${esc(w.short)}</code> · ${ago(w.since)}</div>` : '');
  const hook = pp.webhook_broken ? '<div class="small bad">웹훅 끊김 의심 — 최근 빌드가 폴링으로 시작</div>' : '';
  const chips = infra.map((c) => `<span class="pill infra ${c.status === 'STALE' ? 'warn' : ''}" title="${esc(INFRA_LABEL[c.status] || c.status)} · 마지막 응답 ${esc(ago(c.last_seen_at))}">${esc(c.name)}${c.status === 'STALE' ? ' ⚠' : ''}</span>`).join('');
  const who = (c) => c.title || c.character || (c.session_id ? '세션' : '사람');
  const chains = pp.chains.slice(0, 4).map((ch) => {
    const commits = ch.commits.length ? ch.commits : [{ short: ch.short, subject: '' }];
    const head = commits.find((c) => c.sha === ch.head) || commits[0];
    const extra = commits.length > 1 ? ` <span class="muted">+${commits.length - 1}커밋</span>` : '';
    const steps = PIPE_STAGES.map(([k, label]) => {
      const x = ch.stages[k];
      const cls = x ? `ps-${x.status}` : 'ps-none';
      const tip = x ? `${label} ${x.status}${x.step ? ' · ' + x.step : ''}${x.message ? '\n' + x.message : ''}` : `${label} 아직`;
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
    <div id="down" class="down" role="alert" aria-live="assertive"><div class="box">
      <h2>서버 연결 끊김</h2><p id="downWhy"></p><p id="downNext"></p>
      <button id="retryNow">지금 다시 연결</button>
    </div></div>
    <div id="tokDlg" class="down"><form class="box" id="tokForm">
      <h2 class="plain">API 토큰</h2>
      <p class="muted small">.env.bridge의 FOREMAN_API_TOKEN 값. 이 브라우저에만 저장한다.</p>
      <input id="tokInput" type="password" autocomplete="new-password" placeholder="FOREMAN_API_TOKEN 값">
      <p><button type="submit">연결</button> <span id="tokLen" class="small muted"></span></p>
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
  $('approvals').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-aid]');
    if (!b) return;
    const aid = Number(b.dataset.aid);
    if (b.dataset.act === 'allow') store.decide(aid, 'allow');
    else if (b.dataset.act === 'deny') {
      const m = prompt('거부 이유(모델에게 전달된다)', '사용자가 거부');
      if (m !== null) store.decide(aid, 'deny', m);
    } else if (b.dataset.act === 'open') store.select(Number(b.dataset.sid));
  });
  // 승인 이력(11-03) — 무엇이 몇 번 걸렸고 다 승인했는지. 늘 Yes만 누르는 규칙은 손볼 후보로 표시
  let histDays = 1, histTimer = null;
  const OUT = { approved: ['승인', 'ok'], denied: ['거부', 'bad'], unknown: ['모름', 'muted'] };
  async function loadHist() {
    try {
      const r = await fetch(`/api/approvals/history?days=${histDays}`, { headers: store.headers() });
      if (!r.ok) { $('apprHistBody').textContent = `불러오지 못함(${r.status})`; return; }
      const h = await r.json();
      const t = h.total;
      $('apprHistHead').textContent = `— ${histDays === 1 ? '오늘' : histDays + '일'} ${t.n}건 · 승인 ${t.approved} · 거부 ${t.denied}${t.unknown ? ' · 모름 ' + t.unknown : ''}`;
      const yes = h.by_rule.filter((b) => b.always_yes);
      const rules = h.by_rule.map((b) => `<tr${b.always_yes ? ' class="warn"' : ''}><td>${esc(b.rule)}</td><td>${b.n}</td><td>${b.approved}</td><td>${b.denied}</td><td>${b.unknown}</td><td>${b.always_yes ? '늘 Yes — 규칙 손볼 후보' : ''}</td></tr>`).join('');
      const items = h.items.slice(0, 30).map((x) => `<li><span class="${OUT[x.outcome][1]}">${OUT[x.outcome][0]}</span> <span class="muted">${ago(x.at)} · ${esc(x.project || '미분류')} · ${esc(x.rule)}</span> ${esc(oneLine(x.summary || '', 140))}</li>`).join('');
      const obs = h.observe.length ? `<div class="muted">관찰 모드(창을 띄우지 않음)에서 걸렸을 것: ${h.observe.map((o) => `${esc(o.project)} ${esc(o.rule)} ${o.n}`).join(' · ')}</div>` : '';
      $('apprHistBody').innerHTML = `
        <div class="row"><button class="ghost small" data-days="1">오늘</button><button class="ghost small" data-days="7">7일</button><button class="ghost small" data-days="30">30일</button></div>
        ${yes.length ? `<div class="warn">늘 Yes: ${yes.map((b) => `${esc(b.rule)} ${b.n}번`).join(' · ')} — 묻는 의미가 없으면 규칙을 고친다</div>` : ''}
        ${rules ? `<table class="hist"><tr><th>규칙</th><th>걸림</th><th>승인</th><th>거부</th><th>모름</th><th></th></tr>${rules}</table>` : '<div class="muted">걸린 것 없음</div>'}
        ${obs}<ul class="hist-items">${items}</ul>`;
    } catch (e) { $('apprHistBody').textContent = '불러오지 못함'; }
  }
  $('apprHist').addEventListener('toggle', () => {
    clearInterval(histTimer);
    if ($('apprHist').open) { loadHist(); histTimer = setInterval(loadHist, 60000); }
  });
  $('apprHistBody').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-days]');
    if (b) { histDays = Number(b.dataset.days); loadHist(); }
  });
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
      $('downWhy').textContent = `${c.reason || '브리지와 연락이 없다'} — ${new Date(c.since).toLocaleTimeString()}부터`;
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
    const ingest = !ig ? '' : (ig.stalled ? `<span class="bad" title="트랜스크립트 감시 루프가 ${ig.tick_age_s}초째 돌지 않는다">⚠ 와처 멈춤</span>`
      : (ig.stuck && ig.stuck.length ? `<span class="bad" title="${esc(ig.stuck.map((x) => `${x.session} ${x.minutes}분 · ${x.failures}번 — ${x.error}`).join('\n'))}">⚠ 적재 막힘 ${ig.stuck.length}개 세션 · ${Math.max(...ig.stuck.map((x) => x.minutes))}분</span>`
      : (ig.skips && ig.skips.length ? `<span class="warn" title="${esc(ig.skips.map((x) => `${x.session} ${x.kind === 'chunk' ? '덩어리' : '줄'} ${x.count} — ${x.reason}`).join('\n'))}">적재 중 버린 줄 있음(24시간)</span>` : '')));
    $('summary').innerHTML = ingest +
      `<span>작업 중 <b>${active}</b>/${live}</span>` +
      (subs ? `<span>서브에이전트 <b>${subs}</b></span>` : '') +
      (pending ? `<span class="warn">승인 대기 <b>${pending}</b></span>` : '') +
      `<span class="muted">오늘 출력 ${tok(outToday)}</span>`;
  }

  function drawApprovals(st) {
    const list = [...st.approvals.values()].sort((a, b) => a.id - b.id);
    $('approvals').innerHTML = list.map((a) => {
      const done = a.status !== 'pending';
      const label = (st.projects.find((p) => p.name === a.project) || {}).label || a.project || '미분류';
      return `<div class="appr ${done ? 'done' : ''}">
        <div class="appr-main">
          <div><b>🔐 ${esc(label)}</b> · ${esc(a.tool)} <span class="muted small">#${a.id} · ${esc(a.rule)}</span></div>
          ${a.summary ? `<div class="appr-sum">▶ ${esc(a.summary)}</div>` : ''}
          ${a.summary ? `<details class="small"><summary class="muted">명령 전체</summary><code>${esc(a.target)}</code></details>` : `<code>${esc(a.target)}</code>`}
          <div class="small muted">${esc(a.reason || '')}${a.error ? ` · <span class="bad">${esc(a.error)}</span>` : ''}</div>
        </div>
        <div class="appr-act">${done ? `<span class="small">${esc(a.status)}${a.decided_by ? ' · ' + esc(a.decided_by) : ''}</span>` :
          `<button data-aid="${a.id}" data-act="allow">승인</button><button data-aid="${a.id}" data-act="deny" class="ghost">거부</button>`}
          ${a.session_id ? `<button data-aid="${a.id}" data-sid="${a.session_id}" data-act="open" class="ghost small">세션</button>` : ''}</div>
      </div>`;
    }).join('');
  }

  function card(s, st) {
    const a = s.activity;
    const pend = [...st.approvals.values()].filter((x) => x.session_id === s.id && x.status === 'pending').length;
    const doing = s.state === 'ACTIVE' && a ? `<div class="doing"><b>${esc(a.tool)}</b>${a.subagent ? ' <span class="muted">(서브)</span>' : ''} ${esc(oneLine(a.target, 90))} <span class="muted small">${ago(a.ts)}</span></div>` : '';
    const stuck = stuckTurn(s);
    const turn = s.open_turn ? `<div class="turn small${stuck ? ' warn' : ''}">${stuck ? '⚠ 끝 신호 없는 턴' : '▶'} ${esc(ORIGIN_LABEL[s.open_turn.origin] || '')} ${esc(oneLine(s.open_turn.prompt || '', 80))} <span class="muted">${since(s.open_turn.started_at)}</span></div>` : '';
    const reply = s.replyPreview && s.state === 'ACTIVE' ? `<div class="reply small">${esc(oneLine(s.replyPreview, 100))}</div>` : '';
    return `<article class="card st-${s.state}${st.selected === s.id ? ' sel' : ''}" data-sid="${s.id}" tabindex="0" aria-label="${esc(sessionName(s))} ${STATE_LABEL[s.state]}">
      <div class="card-top">
        <span class="badge st-${s.state}">${s.state}</span>
        <b class="title" title="${esc(sessionName(s))}">${esc(sessionName(s))}</b>
        <span class="right small muted">${s.state === 'DORMANT' ? ago(s.last_ts) : STATE_LABEL[s.state]}</span>
      </div>
      <div class="sub small muted">${esc(sessionSub(s))}</div>
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
        ${dormant.length ? `<details class="dormant"><summary class="small muted">종료된 세션 ${dormant.length}개</summary>${dormant.map((s) => card(s, st)).join('')}</details>` : ''}
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
    const t = s.tokens;
    $('panelHead').innerHTML = `<span class="badge st-${s.state}">${s.state}</span> <b>${esc(sessionName(s))}</b><div class="muted small">${esc(sessionSub(s))} · ${esc((s.cwd || '').replace(/^\/home\/[^/]+/, '~'))}</div>`;
    $('panelInfo').innerHTML = `<div class="small kv">
      <span>프로세스</span><span>${s.pid ? `${s.pid} (${esc(s.proc)}) · CC ${esc(s.cc_status || '?')}` : '없음'}${s.tmux_pane ? ' · tmux ' + esc(s.tmux_pane) : ''}</span>
      <span>지금</span><span>${s.activity && s.state === 'ACTIVE' ? `${esc(s.activity.tool)} ${esc(oneLine(s.activity.target, 120))} (${ago(s.activity.ts)})` : (s.state === 'ACTIVE' ? '생각 중' : STATE_LABEL[s.state])}</span>
      <span>서브에이전트</span><span>${s.subagents_running ? `${s.subagents_running}개 — ${esc((s.subagent_descs || []).join(', '))}` : '없음'}</span>
      <span>토큰</span><span>입력(캐시 포함) ${tok(t.input)} · 출력 ${tok(t.output)} · 오늘 입력 ${tok(t.today_input)} · 출력 ${tok(t.today_output)}<br><span class="muted">서브에이전트 입력 ${tok(t.subagent_input)} · 출력 ${tok(t.subagent_output)}(추정)</span></span>
    </div>`;
    const c = st.convo.get(s.id);
    const convo = $('convo');
    const atBottom = convo.scrollHeight - convo.scrollTop - convo.clientHeight < 40 || lastSel !== s.id;
    convo.innerHTML = !c ? '' : (c.error ? `<p class="bad small">${esc(c.error)}</p>` : '') + (c.turns || []).map((x) => `
      <div class="msg in o-${esc(x.origin)}"><div class="who small muted">${esc(ORIGIN_LABEL[x.origin] || x.origin)} · ${ago(x.started_at)}</div><div class="txt">${esc(promptText(x.prompt)).slice(0, 3000)}</div></div>
      ${x.reply ? `<div class="msg out"><div class="who small muted">CC${x.end_reason ? ' · ' + esc(END_LABEL[x.end_reason] || x.end_reason) : ' · 진행 중'}${x.tools ? ` · 도구 ${x.tools}` : ''}${x.subagents ? ` · 서브 ${x.subagents}` : ''}</div><div class="txt">${esc(x.reply)}</div></div>`
        : (x.end_reason ? `<div class="msg out small muted">${esc(END_LABEL[x.end_reason] || x.end_reason)}${x.tools ? ` · 도구 ${x.tools}` : ''}</div>` : '')}`).join('') + (c && c.loading ? '<p class="small muted">불러오는 중…</p>' : '');
    if (atBottom) convo.scrollTop = convo.scrollHeight;
    $('feed').innerHTML = s.feed.slice().reverse().map((f) => `<div class="f f-${f.kind}"><span class="muted">${new Date(f.ts).toLocaleTimeString()}</span> ${esc(f.text)}</div>`).join('') || '<p class="small muted">이 화면을 연 뒤의 활동이 여기에 쌓인다</p>';
    $('inputForm').hidden = false;
    const blocked = !s.injectable;
    $('inputText').disabled = blocked; $('sendBtn').disabled = blocked;
    $('inputWhy').textContent = blocked ? `보낼 수 없음 — ${why(s)}` : (s.state === 'ACTIVE' ? '일하는 중 — 대기열로 들어간다' : '');
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
