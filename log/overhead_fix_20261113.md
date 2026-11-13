# 머리 위 표시 고치기 넷 — 2026-11-13 (코더 cc/foreman-2, 관리자 318 일감 A)

바탕은 `log/overhead_marks_20261113.md`(`580c6d7`). 사용자 결정 넷을 그대로 고쳤다.

## 한 일
1. **글자**: 관리자 머리 위 「사용자 보고 기다림」 → **「사용자에게 보고함」**. 「사용자 답 기다림」은 그대로
   - 바꾼 곳: `render.js`(말풍선 글 · 툴팁) · `bridge/api/dashboard.py`(escalate 응답 note · 주석 · docstring) · `store.js` · `opanel.js` 주석 · 시연 `overhead_marks.json` note · `tests/js/overhead_marks.test.mjs`
   - `managers.py`의 `escalate_hint`에는 이 글자가 없었다(「응답 글만으로는 사람 화면에 뜨지 않습니다」만) — 고칠 것 없음
   - `grep -rn "사용자 보고 기다림" bridge tests config docs README.md` → 0. **`log/`의 옛 기록 두 파일**(`overhead_marks_20261113.md` · `manager318_overhead_20261113.md`)은 그 시점 기록이라 그대로 뒀다 → 사용자 답(11-13): 기록 파일도 맞춰라 — 합친 뒤 관리자 318이 고침
2. **[전체] 지도 방 카드**: `office.js` 방 통계에 `userAsks`를 새로 두고, 관리자 escalate 물음은 `asks`에서 빼 「사용자 답 기다림 N」으로 따로 센다
   - 지도 카드 「멈춤 — 사용자 답 기다림 N」 · 카드 호버 · 방 머리줄(`badgeLines`)에 줄 추가, 방 경고 색(`siteState` alert)에도 포함
   - 세션이 사람에게 묻고 끝난 「답 기다림 N」은 그대로(우선순위는 그 아래)
3. **서브에이전트 「···」 머리 위에서 뺌**: `waitGlyph`가 뒤에서 도는 명령이 없으면 `null`을 돌려주고, 있으면 어두운 상자 · 파란 테두리 도는 막대만(서브에이전트가 같이 돌아도 「··|」 대신 막대 모양만). 멈춘 턴 빨간 「…」은 그대로. 호버 글은 「서브에이전트 N개 돎 — 둘레의 작은 캐릭터」, 시연 note도 맞춤
4. **`RELAY_GRACE` 150초 → 30초**(`bridge/api/dashboard.py`). 근거(잰 값)와 대가를 주석에 적었다 — 11-12 ~ 11-13 `session_action` mgr-relay 6건: 2.5초 ×3 · 17.4초 ×3, 실패 0(17.4초 = settle 2초 + `deliver(verify_s=15)` 대기열). 30초 = 최장 성공 17.4초 + 여유
   - 시험은 `RELAY_GRACE` 이름으로 참조해 기대값을 따라간다. 「넘기는 중」 케이스의 응답 시각만 20초 → 10초 전으로(30초 안에 여유 있게)

## 설계와 달랐던 점
- 일감은 「관리자 escalate 물음을 빼고 따로 센다」였는데, 별도 카드 줄이 없던 방 머리줄(`badgeLines`)에도 줄을 새로 넣었다 — 지도 카드만 갈리고 방 안에서는 안 보이면 같은 물음이 두 곳에서 다르게 보인다
- 서브에이전트만 돌 때 머리 위가 비는 것은 의도다(둘레의 작은 캐릭터가 대신 보인다). 호버 첫 줄에서 위치를 안내

## 확인
- `pytest` 796 통과(1 건너뜀) · `node --test tests/js/` 128 통과. 실제 `config/*.toml`을 읽는 시험은 새로 만들지 않았다
- 화면(미리보기 :8213, `tools/screen.py --demo overhead_marks --views foreman,ronanlab-infra,map --no-term`): 세 테마 × 3크기 × 좁게/넓게 18조합 모두 grid · layout · label · name · card · tip · prop 0건, 페이지 오류 0, 화면마다 `bubbleAudit()` 0(`audit(고정 안 됨)` 수는 이전과 같은 테마 그림 값)
- 사진: 마법학교 1024x700 넓게에서 「사용자에게 보고함」이 잘리지 않음, 오피스 1366에서 서브에이전트가 붙은 코더 머리 위는 비고 뒤 명령 코더는 어두운 상자의 「/」, 방 머리줄에 「사용자 답 기다림 1」

## 되돌리는 법
- 이 커밋을 `git revert`. 서버 쪽(`RELAY_GRACE` · escalate 응답 글)은 합친 뒤 원본 세션이 브리지를 다시 띄워야 돈다. 화면(JS)은 새로 고침
