# FOREMAN 문서 점검을 pytest에 걸기 (foreman-5, 2026-11-17, 관리자 410 일감)

사용자 결정: 못 푸는 참조 넷이 풀린 뒤 pytest에 FOREMAN 자체 점검을 건다. 카드 한 줄은 보이게만 할 뿐이라 아무도 안 보면 조용히 낡는다. 깨지게 만드는 것은 시험뿐이다(`log/foreman-5_docs_check_20261117.md` 7절 2번).

## 1. 한 일

- 새 시험 `tests/test_docs_selfcheck.py` 1개(`test_foreman_docs_check_has_no_errors`). `tools/docs.py check`와 같은 함수(`bridge/doctext/check.py` `run`)를 이 저장소 작업 트리에 돌린다
  - 틀린 것이 하나라도 있으면 실패한다. 실패 글에 틀린 줄(파일:줄 또는 저장소 전체, 까닭) 처음 8개와 나머지 수가 나온다. 의심은 실패시키지 않는다
  - 작업 트리 판(`rev` 없음)이라 커밋 전 새 원고도 본다. add 하지 않은 새 파일은 편 점검에서는 보이지만 덮기 대상(git이 추적하는 파일) 수에는 add 뒤에 들어간다. 3단계 log 9절의 「아직 add 안 한 새 편」과 같은 동작이다
  - 점검할 묶음을 하나도 못 읽었으면(설정, 폴더 문제) 따로 실패한다. 조용히 0건으로 통과하지 않게 하려는 것이다
  - 다른 저장소는 점검하지 않는다(이 저장소 `ROOT`만)

## 2. 시간

- 이 시험 단독: **0.5초**(전체 0.69초). 목표 몇 초 안에 든다
- pytest 전체: **1330 통과**, 206.68초(3분 26초), 경고 1(전부터 있던 것). 이 시험이 더한 시간은 전체의 0.3% 아래다
- `node --test tests/js/`: 226 통과
- `tools/docs.py check`: 틀린 것 0, 의심 235(덮기 대상 494 가운데 494 덮음)

## 3. 고친 문서

- `docs/11_worktree.md` 「9.」: 「문서 점검은 pytest가 돈다」 항목
- `docs/operations.md`(사람 승인 카드가 된다): 문서 점검 명령 줄 뒤에 pytest가 같은 점검을 돈다는 말
- `notion/16_tests.md`: 시험 묶음 짜임에 문서 점검 문단(근거 표시 둘)
- `notion/10_scribe/03_evidence.md`: 점검 문단 끝에 한 문장, 머리 「다루는 곳」에 새 시험 파일(`16_tests`가 `tests/`를 통째로 덮지 않아 기능 편에 넣었다)
- `log/foreman-5_docs_check_20261117.md` 7절 2번 아래 「11-17 걸었다(커밋)」 한 줄
- 포트폴리오는 점검을 말하는 곳이 없어 고치지 않았다

## 4. 확인하지 못한 것

- 틀린 문서를 일부러 만들어 이 시험이 실패하는 것은 따로 해 보지 않았다. 판정이 `tools/docs.py check`와 같은 함수라 틀림을 잡는 쪽은 `tests/test_docs_check.py`(20개)가 이미 본다. 이 시험은 그 함수를 이 저장소에 거는 것만 맡는다

## 5. 규칙

규칙 위반 없음. 파일은 Edit, Write로만 고쳤다(`sed`, `>` 리디렉션, `python -c` 안 씀). `pgrep -f` 안 썼다. push와 브리지 다시 띄우기는 하지 않았다. 겹침: 코더 536이 고치는 `bridge/mergeprep.py`, `bridge/static/js/handoff.js`, `.foreman/docs.toml`, `bridge/doctext/config.py`는 건드리지 않았다.
