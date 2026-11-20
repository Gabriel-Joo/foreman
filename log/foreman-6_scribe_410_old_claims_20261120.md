# 서기 일감 410: 옛 설명과 약한 근거 맞추기 (2026-11-20)

시작한 main 커밋: `b89b3b6`. 규칙 위반: 없음.

## 한 일

1. `docs/00_design.md`
   - 수신 웹훅: 브리지가 받는 길은 `/webhooks/jenkins`, `harbor`, `argocd` 셋이다(`bridge/api/webhooks.py`). GitLab 길은 없어서 줄에서 뺐다. Harbor는 받는 곳만 있고 보내는 정책을 건 기록은 없다(`notion/12_pipeline.md` 5-2절이 적고 있다. 이 줄에는 넣지 않았다).
   - 「캐릭터가 파이프라인 구역으로 걸어간다」: 지금 화면은 세션 캐릭터가 출하 라인에 걸어와 일감을 넘기고(6초) 배송 담당 한 명이 단계 앞으로 걸어간다. 성공하면 25초, 실패하면 그 단계 앞에 30분 선다(`office.js` 370~372줄). 그 문단과 2.5절의 「파이프라인 구역(3.6)」을 이대로 고쳤다. 출하 라인은 런슈즈와 펫퍼민트 방에만 있다.
2. `docs/11_foreman_dispatch.md`: 교장 작업 폴더는 `~/.foreman/dispatch`(`ForemanDispatcher.workdir`). 코드는 처음 만든 커밋 `98b4e23`부터 이 폴더였다. 문서만 저장소라고 적었고, 달라진 까닭은 기록에 없다고 적었다.
3. 약한 근거 좁히기
   - `notion/04_approval.md` `git-이력파괴`: 기록(`design_history_20261117.md`)에 있는 것은 펫퍼민트 세션의 `filter-branch`, `reflog expire`, `gc --prune`이 observe 기록에 남고 어느 규칙에도 안 걸렸다는 것까지다. `git-기록파괴`는 `15e5b1d` 전에 이미 있었고 그 커밋이 `git-이력파괴`로 이름을 바꾸며 `reset --hard`, `clean -f`를 더했다. 그래서 「그 사건으로 새로 만들었다」를 빼고 「처음 만든 까닭은 기록에 없다」로 좁혔다.
   - `notion/07_merge/01_card.md` 「2,454」: 「기록에는 2,454개로 적혀 있고」 꼴로 좁혔다(세는 법은 기록에 없다). 지금 다시 센 수는 그대로 뒀다.
   - `notion/10_scribe/03_evidence.md`: 인프라(`b587fe9`)와 런슈즈(`606b730`)의 기준 커밋은 `log/foreman-5_dashdot_moved_lines_20261117.md`에 있어 그것만 근거로 걸었다. 펫퍼민트 값은 FOREMAN 기록에 없어 「FOREMAN 기록에는 없다」로 적었다. 세 저장소 설정 파일에 칸이 있는 것은 읽기만 해서 확인했고, 다른 저장소 파일은 고치지 않았다.
4. `notion/14_screen.md` 7, 96줄: 관리자 410의 사용자 결정(11-20)대로 `[code:CLAUDE.md]`를 `[docs:CLAUDE.md]`로 바꿨다.
5. 고친 네 편의 「읽은 커밋」을 `b89b3b6`으로 맞췄다. 고친 줄만 코드와 대조했고 편 전체를 다시 읽지는 않았다.

## 되돌림 (같은 날, 관리자 410 지시)

`notion/14_screen.md` 7, 96줄의 `[docs:CLAUDE.md]`는 점검이 `docs/CLAUDE.md`로 풀어 틀림 2였다. 두 줄을 `[code:CLAUDE.md]`로 되돌려 `tools/docs.py check` 틀린 것 0을 봤다. 맨 위 문서를 가리키는 표시 꼴은 나중에 코더가 점검 규칙과 00, 06, 08, 09, 14, 16편을 한 번에 바꾼다. 아래 「걸린 것」의 첫 항목과 4번은 이 되돌림 앞의 상태다.

## 걸린 것

- `tools/docs.py check`가 틀림 2를 낸다: `notion/14_screen.md:7`, `:96`에서 `docs/CLAUDE.md 파일이 없습니다`. `[docs:]`는 docs 묶음 폴더 기준이라 저장소 맨 위 CLAUDE.md를 못 푼다. 사용자가 점검 고치기는 코더 몫이라고 해서 두었다. 다른 편(`00_foreman`, `05_roles`, `06_sessions` 등)의 `[code:CLAUDE.md]` 열 곳 남짓은 이 일감 밖이라 두었다.
- 기준 `docs/manuscript_rules.md`와 `docs/style_guide.md`에는 규칙 문서(저장소 맨 위 CLAUDE.md)를 가리키는 근거 표시 종류가 없다. 이번에 `[docs:CLAUDE.md]`로 정했으나 기준에는 적히지 않았다.
- `notion/12_pipeline.md` 307줄이 `00_design.md`의 옛 문장을 인용한다. 지금 문장이 바뀌었으니 같은 편을 맡은 세션이 한 번 봐야 한다(고치지 않았다).
- `log/design_history_20261117.md`는 규칙 이름을 `git-기록파괴`로, 지금 설정은 `git-이력파괴`로 적는다(기록이라 두었다).

## 시험

- `tools/docs.py check`: 틀린 것 2(위), 의심 326
- pytest: 1521 passed, 1 warning

## 사람이 정할 것

- `[docs:CLAUDE.md]` 점검 수정을 코더에게 맡길 때, `[code:CLAUDE.md]`가 남은 다른 편 열 곳 남짓을 함께 바꿀지
- 기준 문서에 규칙 문서 근거 표시 종류를 적을지(사람 승인 문서)
