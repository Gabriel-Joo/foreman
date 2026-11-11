# 낡은 문서 둘 다시 맞춤 — 10_office_design · operations (11-11, 서기 foreman-2 · cc/foreman-2)

앞 기록: [docs_four_sync_20261111.md](docs_four_sync_20261111.md). 292가 문서를 맞추던 사이 합쳐진 291 · 290 · 297 때문에 낡은 곳만 고쳤다. 코드 · 설정 · 시험 · README · CLAUDE.md는 건드리지 않았다.

## 고친 곳 (커밋은 문서마다)

| 문서 | 고친 곳 | 맞춘 근거 |
|---|---|---|
| `docs/10_office_design.md` 149줄 | 막대를 누르면 「세션」 탭으로 연다고 | `bridge/static/js/office.js:3335~3339`(`#oMerge` → `panel.showTab('sess')`, 캐릭터는 마지막 탭) · `log/merge_bar_discard_tab_20261111.md` ④⑤ |
| 같은 문서 151줄 | 「실제로는 대화 탭」 → 처음 본 어긋남이었고 고쳐졌다(세션 탭). 「버려도 최대 1분」 → 버리면 바로 사라진다. 승인 뒤 열린 화면이 늦게 따라오는 것과 브리지 재시작 뒤 「오래됨」 시각이 바뀌는 것은 **고친 것이 아니라 남은 것**으로 그대로 | `bridge/handoff.py:1258~1259`(`mergeprep.worktree_gone`) · 기록 「라이브 여섯 가지」 ①②③⑥. 다른 곳에 같은 뜻의 낡은 문장은 없었다(`grep` 「대화 탭」 · 「1분」 · 「훑」) |
| `docs/operations.md` 28줄 시험 줄 | 공용 `foreman_test` · "동시에 돌리지 않는다" → 세션마다 시험 DB. `test_app_db`가 운영 DB에 대고 띄운다는 말도 세션 DB로 | `log/test_db_per_session_20261111.md` · `tests/test_app_db.py:37`에 `losscheck_recover: False`가 아직 있음을 확인 |
| 같은 문서 「3. 돌리기 · 확인」 | 새 항목 「시험 DB는 세션마다 따로다」: 이름 규칙 · 시작 머리글 · 끝나면 지움 · 죽은 것은 다음 pytest가 치움 · 공용으로 떨어지는 경고 · 손 명령 · 새 시험 쓰는 법 · 토큰 헤더 · 운영 DB에 쓰는 시험 둘 · 권한. "기다린다 / 혼자 돌린다" 안내는 이 항목으로 대체(그 밖에 operations에 그런 안내는 없었다. `pgrep -f` 함정 설명은 그대로) | 290 기록의 「문서에 옮길 것」 · `tests/conftest.py:27,38,48,73`(경고 · 머리글) · `tests/testdb.py`(`--clean`) |
| 같은 문서 39줄 | CC 세션 tmux | 아래 |

## tmux · systemd — 직접 본 것 (11-11 19:10)

- `tmux ls`: `cc-foreman` · `cc-foreman-2` · `cc-petmint` · `cc-petmint-rag-chatbot` · `cc-petmint-rag-chatbot-2` · `cc-ronanlab-infra` · `cc-runshoes` · `cc-runshoes-3` · `foreman-bridge`(창 1) · `foreman-shell`(창 4)
- `tmux list-panes -a -F '#{session_name} #{pane_pid} #{pane_current_command}'`: `foreman-bridge`는 `bash` 하나뿐. `cc-*`는 `claude`, 다만 **`cc-petmint` · `cc-runshoes`는 `bash`**(그 안에서 CC가 따로 도는지는 확인 못 함)
- `XDG_RUNTIME_DIR=/run/user/1000 systemctl --user status foreman-bridge`: `active (running)`, 19:07:38 시작, 메인 `python -m bridge` + 자식 `ttyd`(foreman-shell). `enabled`
- 그래서 "서기 세션은 아직 tmux 세션 `foreman-bridge` 안에 있다 · 이름 변경 보류 · 펫퍼민트는 tmux 밖(pts/7)"은 낡았다. 지금 문서: 세션은 `cc-<프로젝트>[-N]`, `foreman-bridge`는 빈 bash, 브리지는 systemd. 런슈즈 `cc-runshoes`가 "정전 뒤 사라졌다"도 지금은 틀려서 뺐다
- 코드에서 `cc-<프로젝트>-N` 이름 규칙을 읽어 확인한 것은 아니다. 목록의 이름 모양에서 적었다

## 확인하지 못한 것

- `-N`이 정확히 무엇인지(같은 프로젝트의 몇 번째 세션인지)는 이름 모양만 보고 적었다
- 시험 DB 항목의 `<자리>` 규칙(소문자 · 24자)은 `tests/testdb.py:29~34`와 대조했다. 이 문서의 시험 DB 동작은 **합쳐진 코드를 이 worktree에서 돌려 본 것이 아니라** 기록과 코드 일부(conftest · testdb 함수 이름)를 보고 적었다

## 관리자에게 넘길 것

- `CLAUDE.md` 48줄 「브리지(tmux `foreman-bridge`)는 승인 대기가 없는지 본 뒤 다시 띄운다」는 낡았다 → 「브리지(systemd `foreman-bridge`)」. `docs/operations.md` 「3.」과 같게. (이 세션은 CLAUDE.md를 고치지 않았다)
- 작업 규칙 속 "시험 동시에 돌리지 않는다" 류 지시문 문구가 있다면 합친 뒤에 맞게 뺀다(290 기록 「관리자가 지시문에서 뺄 문구」)

## 체크리스트

- [x] 10_office_design: 「대화 탭」 → 「세션 탭」
- [x] 10_office_design: 「버려도 최대 1분 남음」 → 「버리면 바로 사라짐」
- [x] operations: 시험 줄을 세션마다 시험 DB로(290 기록대로)
- [x] tmux · systemd 실제로 보고 맞춤(위 명령과 결과)
- [x] 문서마다 커밋(`cf91746` 10_office_design · `cc2498d` operations · 이 기록은 따로)
- [x] 고친 곳마다 근거(위 표)
