# 호버 잘림 · 줄바꿈(툴팁 전체) + tipAudit, 추가 사용은 CC 한도 글로 판정 (2026-11-09 오후, 원본 폴더)

앞 기록: [credits_and_middle_number_20261109.md](credits_and_middle_number_20261109.md)

## 1. 호버 — 두 호버만이 아니라 툴팁 전체 문제였다

- 잘림: `.tip-n > div { white-space:nowrap; overflow:hidden; text-overflow:ellipsis }` — 숫자 줄(구분선 아래)은 **모든 툴팁에서** 줄을 바꾸지 않고 …로 잘랐다(사용량 호버 "11월 10일 …"). 이제 줄을 바꾸고 이어지는 줄은 들여 쓴다
- 이상한 줄바꿈: 설명이 긴 한 문단이라 폭이 차는 곳에서 끊겼다("넘쳐 쓸 / 크레딧이"). 이제 설명은 **문장마다 줄**(`splitSentences`), 문장 안은 낱말 단위(keep-all) + `text-wrap: pretty`. 띄어쓰기 없는 긴 글(경로 · 명령 · 주소)은 `/ _ - . = , : ?` 뒤에서만 끊게 `<wbr>`(`softEsc` — 패널 경로, 캐릭터 호버의 명령)
- 크기 제한: 폭만 `min(440px × 글씨 배율, 화면 폭 − 16px)` — 한 줄이 너무 길면 읽기 어려워서 남겼다. 높이 제한은 없다. 화면보다 높으면 폭을 화면 폭까지 넓힌다(`fit`)
- **점검 `window.office.tipAudit()`**: 지금 화면의 모든 호버 글(버튼 · 패널 data-tip/title · 캔버스 칸 · 캐릭터)을 실제 툴팁 상자에 넣어 넘침 · 낱말 끊김(끊을 자리 없이 줄 폭보다 긴 낱말) · 화면보다 큼을 센다. `tools/screen.py`가 화면마다 기본으로 센다
  - 처음 돌림: 39건 — 캐릭터 호버의 긴 명령(`S=/tmp/…`) · 패널 작업 폴더 경로. `<wbr>` 뒤 0건
  - 옛 CSS(nowrap + …)를 잠시 되돌려 돌리면 "넘침 oUsage"를 잡는다(점검이 그 문제를 본다)
  - 세 테마 × 1920 · 1366 · 1024 × **125%** × [⌂] · [전체] · 펫퍼민트 · 런슈즈: 호버 250개 0건

## 2. 추가 사용(크레딧) — 사람이 넣은 값이 아니라 CC가 남긴 한도 글로

- 다른 경로: claude.ai 설정 > 사용량은 공개 API가 없다(로그인한 브라우저 화면). CC의 /usage(대화형 · `-p` 둘 다)에는 잔액이 없고 대화형은 "Usage credits are off"
- **찾은 것**: CC는 한도에 닿으면 모델 응답 대신 오류 글을 남긴다(트랜스크립트 `isApiErrorMessage`, `error: rate_limit`, `apiError: usage_limit_reached`, 모델 `<synthetic>` — 적재기는 event type `error`). 11-09 실제:
  - 13:10 KST "You've hit your 5-hour limit · resets 2:10pm (Asia/Seoul)"
  - 13:13 ~ 13:32 실제 Opus 응답이 이어짐(리셋 14:10 전 — 추가 사용으로 이어 씀)
  - 13:32 · 13:55 "You've hit your **monthly spend limit** · raise it at https://claude.ai/settings/usage?from=cc_cli_limit_message · your 5-hour limit resets 2:10pm"
  - 금액(잔액 · 월 한도 · 쓴 돈)은 글에 없다
- `usage.credit_signal`: 이번 달(KST) 마지막 한도 글 하나로 — monthly spend limit → **막힘**, 그냥 한도 → 그 한도 리셋 전에 실제 응답이 1분 뒤로 이어졌으면 **이어 씀**, 아니면 **막힘**, 이번 달 근거 없음 → **모름**. 같은 때 StopFailure 훅 이벤트(글 없음)도 error로 30ms 뒤에 들어와 처음엔 그것을 골라 글을 못 읽었다(16:36 ~ 16:39 화면에 "이어 씀"이 잘못 떴다) → 글 있는 행만
- 화면 칩: "⛔ 추가 사용 막힘 · 오늘 13:55"(빨강) · "추가 사용으로 이어 씀 · 시각"(노랑) · "추가 사용 확인 필요"(근거 없음). 칩에 근거 시각, 호버에 CC 글 원문. "한도를 올렸다면 다음에 한도에 닿을 때 다시 판정합니다"
- 사람이 넣은 값(`[credits]`)은 **판정에 쓰지 않고**(근거가 없을 때만) 호버의 금액 참고로만. **넣은 지 3일**이 지나거나 달이 바뀌면 숫자를 감춘다 — 월 사용액은 쓰는 날마다 늘고 충전 · 한도는 아무 때나 바뀐다
- 90% 알림의 "막힘"도 같은 판정(근거 시각 · 까닭을 글에)

## 확인

- 파이썬 512 + `test_credit_signal_from_cc_limit_messages`(5시간 한도 → 이어 씀 → 월 지출 한도 → 훅 행 · 리셋 뒤 응답에도 막힘 → 다음 달 모름) · JS 53
- 브리지 16:36:41 · 16:39:01 다시 띄움(승인 대기 0 뒤). 실제 칩 "⛔ 추가 사용 막힘 · 오늘 13:55"
