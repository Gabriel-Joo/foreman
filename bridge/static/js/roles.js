// 역할 — 화면 쪽 한 곳(11-15, 454 제안 1 · 2 · 3, docs/roles.md). 파이썬 쪽 한 곳은 bridge/roles.py이고
// tests/test_roles_agree.py가 둘이 한 역할도 어긋나지 않는지(목록 · 이름 · 설명 · 색) 본다. 새 역할 순서는 docs/roles.md 「3.」.
// 서버가 내려주지 않고 JS에 두는 까닭: 배지 색 CSS · 픽셀 화면 · 미리보기(브리지 없는 시연 페이지) · node 시험이 모듈을 읽자마자 쓴다.

// 세션으로 고를 수 있는 역할(순서 = 역할 고르기 칸 순서, 첫째가 기본값) — bridge/roles.py SESSION_ROLES와 같다
export const SESSION_ROLES = ['coder', 'designer', 'manager', 'scribe', 'inspector'];
// 화면 이름. foreman(감독) · helper · infra는 캐릭터 몫이라 이름만 있다(고를 수 없다)
export const ROLE_LABEL = { coder: '코더', designer: '디자이너', manager: '관리자', scribe: '서기', inspector: '조사', foreman: '감독', helper: '도우미', infra: '인프라' };
// 한 줄 설명 — bridge/roles.py ROLE_DESC와 같은 글(CLAUDE.md 「역할을 가르는 기준」). 역할 고르기 칸 · 교장 지시문
export const ROLE_DESC = {
  coder: '코드를 고치거나 만듭니다',
  designer: '화면을 고칩니다. js, css, 테마, 캐릭터, 호버 글',
  manager: '합치고 시험하고 push하고 기록합니다',
  scribe: '문서를 쓰고 맞춥니다',
  inspector: '읽고 알아봅니다. 고치지 않고 결과 log만 씁니다. 조사와 제안은 모두 여기입니다',
};

// ── 색 한 표 ─────────────────────────────────────────
// ROLE_COLOR — 배지 · 발밑 원 · 이름표 글자(11-13 사용자 「발밑 역할 색은 역할 배지와 같게」)
export const ROLE_COLOR = { coder: '#5b9be6', manager: '#e0604f', scribe: '#d08b4f', inspector: '#3fbf85', designer: '#e8619f', foreman: '#c9a227' };
// ROLE_CLOTH — 테마 옷 색(로브 · 사원증 끈 · 안전모). 그림에 맞춰 배지보다 어둡다(11-15 전에는 theme.json 네 곳에 같은 값이 따로 적혀 있었다).
// 테마는 다른 값이 필요한 역할만 theme.json roles.colors에 적어 덮는다(현장: 코더 #2f6fb0 · 감독 흰 안전모 #f4f4f4).
// 키 순서는 ?roles=demo가 세션에 역할을 돌려 주는 순서다. 여기도 테마에도 없는 역할은 ROLE_COLOR로 떨어진다(clothColor)
export const ROLE_CLOTH = { foreman: '#d4a72c', coder: '#3f7fd0', inspector: '#2e9e6a', scribe: '#b0713a', manager: '#c0392b', designer: '#d6408a', helper: '#8a8f98' };
export const ROLE_NONE_COLOR = '#e0b040', ROLE_OTHER_COLOR = '#8a8f98';   // panel.css .rolebadge.role-none(역할?) · .rolebadge 기본 회색과 같은 값

// 테마의 역할 → 옷 색 표(공통 ROLE_CLOTH 위에 테마가 적은 값)
export const themeCloth = (theme) => ({ ...ROLE_CLOTH, ...((theme && theme.roles && theme.roles.colors) || {}) });
// 옷 색 하나 — 테마 표 → 배지 색 순. 없으면 null(역할 없음 · 테마 기본은 부르는 쪽이 정한다)
export const clothColor = (cloth, role) => (role && (cloth[role] || ROLE_COLOR[role])) || null;
