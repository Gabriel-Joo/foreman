// 출하 라인 Harbor 칸의 상태(11-17). DOM을 모른다(node --test로 시험, tests/js/shipstate.test.mjs).
// Harbor는 따로 알림을 받지 않는다. 이미지를 올리는 일은 Jenkins의 「빌드·push」 단계 안이라 Jenkins 행에서 미루어 그린다.
// 기준은 하나다: 그 빌드의 이미지가 실제로 올라갔는가. 올라가지 않았으면 ✓로 그리지 않는다.
export const PUSH_STEP = /push|harbor|이미지/i;              // 이미지를 올리는 단계
export const AFTER_PUSH_STEP = /매니페스트|manifest|배포|deploy/i;   // push 뒤 단계(이 단계에서 실패했으면 이미지는 이미 올라갔다)

// stages = 체인의 단계들({ jenkins, harbor, argocd }). 돌려주는 값은 칸 상태(running · success · failed · waiting · stale · none)
export function harborStatus(stages) {
  const s = stages || {}, j = s.jenkins;
  if (s.harbor && s.harbor.status) return s.harbor.status;          // Harbor가 직접 알려 온 것이 있으면 그대로
  if (!j) return 'none';
  if (j.skipped) return 'none';                                     // 문서만 바뀐 빌드 — 이미지 없음(정상)
  if (j.status === 'failed') {
    const step = j.step || '';
    if (PUSH_STEP.test(step)) return 'failed';                      // push에서 실패 — 이미지가 올라가지 않았다
    if (AFTER_PUSH_STEP.test(step)) return 'success';               // push 뒤에서 실패 — 이미지는 올라갔다
    return 'none';                                                  // push 앞(태그 · 시험 등)이거나 모르는 단계 — 올라갔다고 말하지 않는다
  }
  return j.status || 'none';
}
