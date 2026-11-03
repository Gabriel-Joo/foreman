-- 0013 승인 요약 (11-03 사용자 요청)
-- 승인 창에 명령이 통째로 나와서 읽기 힘들었다 — "무엇을 대상으로" 하는지를 한 줄로(bridge/approval_summary.py).
-- 예: "rm -rf → /tmp/claude-1000/…/tmp.x (이 명령에서 mktemp로 만든 것)", "kubectl delete → pod/jenkins-0 (jenkins 네임스페이스)"
-- 텔레그램 · 대시보드 승인 카드 · CC 승인 창(permissionDecisionReason) · 승인 이력에 같은 줄을 쓴다
ALTER TABLE approval
  ADD COLUMN summary VARCHAR(512) NULL AFTER reason;
