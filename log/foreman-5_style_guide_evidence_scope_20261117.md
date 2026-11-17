# 근거 범위 규칙을 style_guide에 넣음 (11-17, foreman-5)

관리자 410의 서기 일감(사용자 지시 19의 3번).

## 한 일

- `docs/style_guide.md` 「4. 문체」의 「근거를 바로 단다」 목록 끝에 한 줄을 더했다. 「브리지가 표시가 실제로 있는지 확인한다」 줄 바로 아래다
- 사용자 문장 네 개를 그대로 넣었고, 날짜 `(11-17 사용자)`와 까닭 한 줄, 두 log 가리킴(`[log:foreman-5_notion_evidence_scope_20261117.md]`, `[log:foreman-6_portfolio_scope_check_20261117.md]`)을 달았다. 이 절의 다른 줄과 같은 꼴(굵은 규칙, 괄호 날짜, 끝에 `[log:]`)이다
- 다른 절, 다른 파일, 원고(`notion/`, `portfolio/`)는 고치지 않았다. 두 log가 찾은 원고와 글의 어긋남도 고치지 않았다(사용자가 보고만 하라고 했다)

## 시험

- `.venv/bin/python -m pytest -q`: 1176 passed (알려진 `test_digest_send_failure_and_late_are_reported`도 이번에는 통과, 시각 때문에 실패하는 시험이라 시간대에 따라 다르다)
- `node --test tests/js/`: 210 pass, 0 fail

## 규칙 위반 없음
