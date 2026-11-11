-- 0030 한 계획에 여러 세션 · 맡을 파일 · 모든 띄우기 기록(11-11 교장 ① · ④ · 일곱, log/plan_structure_20261111.md 「1물결 — C1」)
-- 11-09 「둘 띄워줘」가 하나만 됐다(dispatch 132 · 133 → 세션 231만) — 계획(dispatch) 하나에 세션 여럿을 담는다.
-- 세션마다 역할 · 모델 · 맡을 파일 · 합칠 순서 · 띄운 결과를 한 줄씩. 계획 JSON(dispatch.plan · edited)의 sessions[]와 같은 것을
-- 시작할 때 이 표에 옮긴다(살아 있는 세션의 맡을 파일을 찾으려고 — JSON을 매번 풀지 않게).
--   status      started(띄움) · failed(띄우기 실패 — error) · off(사람이 계획 카드에서 끔)
--   files       맡을 파일(저장소 기준 경로 · 폴더는 끝에 / · 글롭 *) — JSON 배열
--   merge_order 합칠 순서(1부터, 작은 것 먼저). 없으면 계획 안 순서
-- dispatch.origin에 값 둘을 더한다(칼럼은 VARCHAR(10) 그대로): spawn(/api/spawn 직접 — + 새 세션 창 · 관리자) · move(새 세션으로 옮기기)
-- 더하기만 — 되돌리기: DROP TABLE dispatch_session;  (0029 코드는 이 표를 모른다 — 지워도 돈다. origin 'spawn' · 'move' 행은 그대로 둬도 된다)
CREATE TABLE dispatch_session (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  dispatch_id  BIGINT UNSIGNED NOT NULL,
  idx          SMALLINT UNSIGNED NOT NULL,
  role         VARCHAR(16) NULL,
  model        VARCHAR(40) NULL,
  title        VARCHAR(255) NULL,
  files        JSON NULL,
  merge_order  SMALLINT UNSIGNED NULL,
  status       VARCHAR(10) NOT NULL,
  session_id   BIGINT UNSIGNED NULL,
  cwd          VARCHAR(1024) NULL,
  error        VARCHAR(500) NULL,
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY ux_dsess (dispatch_id, idx),
  KEY ix_dsess_session (session_id)
) ENGINE=InnoDB;
