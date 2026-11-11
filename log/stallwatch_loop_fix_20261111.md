# 멈춤 감시 「맴돎」 오판 고치기 (2026-11-11, worktree foreman-3, 코더)

앞 기록: 관리자 244의 지시(11-11 11:32:29 브리지 로그 `멈춤 알림: 세션 273 loop — 30분 안에 Bash S=/tmp/…/650c05를 8번 했습니다`)

## 조사 결과

- 뿌리: `samples()`가 `GROUP BY tool, LEFT(target, 160)`으로 「같은 명령」을 갈랐다. 273(디자이너)은 Bash마다 `S=<스크래치 경로>;`를 붙였고 그 경로가 앞 160자 대부분을 채워, `for t in … shot.py` · `ls $S/…` · `cat > $S/click.js` 같은 다른 명령이 하나로 묶였다
- 지난 DB 전체(10-12~11-11, 도구 쓴 턴 1,751개)에 옛 판정을 대 보니 **맴돎 27턴** — 하나하나 보니 **모두 거짓**이었다. 꼴은 셋:
  1. Bash 앞 160자만 같음(21건): 대부분 앞머리 — `S=… ;` · `SP=…;` · `W=…` · `cd <스크래치> &&` · `D=…; cd $D;` · `cd ~/foreman; set -a; . ./.env.db …` · `node --check … && SP=… &&`. 나머지는 같은 꼴의 heredoc 스크립트(`python3 - <<'EOF'` 뒤 앞부분이 같은 도우미 함수, 본문이 다름)
  2. **병렬 서브에이전트**(5건): 에이전트 7~9개가 저마다 `ToolSearch select:WebSearch`를 한두 번씩(런슈즈 156, 4건), 여섯이 저마다 `notion-fetch <스펙>`(펫퍼민트 223, 11-09) — 한 턴 안의 event라 합쳐 셌다
  3. **문서 고치기**(1건): 인프라 265가 Notion 페이지 여럿을 고치며 `notion-update-page` 같은 쪽을 6번(11-10) — Edit과 같은 진행
- 실패 횟수(30분 8번)도 같은 뿌리: 걸린 3턴 중 2턴(런슈즈 156 · 221)은 병렬 에이전트 여럿의 실패를 합친 것(한 에이전트당 3~4번)
- 진짜 맴돈 사례(같은 명령을 고치지 않고 되풀이)는 지난 DB에 **없었다** — 새 판정으로 4번 이상 되풀이한 것도 1턴뿐(같은 문서를 WebFetch로 4번, 질문이 다름)

## 고친 판정 (`bridge/stallwatch.py`)

- `same_key(tool, target)` — Bash는 맨 바깥의 `;` · `&&` · 줄바꿈으로 이어진 **앞 조각 중 자리 잡기만 하는 것**을 뺀다: 변수 지정(`S=…` · `T=$(…)` · `A=1 B=2`) · `export` · `unset` · `cd` · `pushd` · `set -e…` · `umask` · `source …activate` · 주석 줄. 한 명령 안의 앞머리 `A=B cmd` · `env` · `timeout N` · `nice` · `time` · `command` · `stdbuf`도 뺀다. 파이프 앞 조각은 빼지 않는다(명령의 일부). 쪼개기는 승인 판정과 같은 `approval._seg_spans`(따옴표 · `$( )` 안 구분자 무시). 남은 **명령 전체**(1,024자 넘으면 `payload.target_full`)로 비교 — 앞 몇 글자로 자르지 않는다
- `most_repeated(events)` — 파이썬에서 센다(SQL `GROUP BY` 대신):
  - 서브에이전트(`event.subagent_id`)마다 따로
  - 그 에이전트가 고치면(Edit · MultiEdit · Write · NotebookEdit · `mcp__…(update|create|edit|write|append|insert|replace|move|delete)`) 그때까지 센 것을 0으로 — **고치고 다시 돌리기는 맴돎이 아니다**. 읽기 · 찾기(Read · Grep)만 끼면 여전히 맴돎
- 실패 횟수도 `GROUP BY subagent_id`의 가장 많은 것
- 문턱(`LOOP_SAME` 6 · `LOOP_ERRORS` 8 · 30분)은 그대로

## 실제 DB에 대 본 숫자 (턴마다 도구를 쓴 매 순간 30분 창으로)

| | 옛 판정 | 새 판정 |
|---|---|---|
| 같은 것 되풀이(맴돎) | 27턴 (모두 거짓) | **0턴** |
| 실패 8번 | 3턴 | **1턴** |
| 273의 11-11 턴(6551) | 걸림(8번) | 안 걸림 |

- 남은 1턴: 인프라 265(11-10 12:24, 본 세션) — 30분에 서로 다른 인프라 명령(vagrant ssh · kubectl · git commit) 8개가 실패. 「같은 자리」는 아니지만 실패가 잦았던 것은 사실이라 그대로 두었다. 이것도 울리지 않게 하려면 실패 판정을 「같은 명령의 실패」로 좁히면 된다 — 사용자 판단 몫
- 진짜 맴돎이 지난 DB에 없어 「여전히 잡힌다」는 시험으로만 확인: 앞머리가 달라도 같은 `pytest` 6번 → 잡음, 그 사이에 Read · Grep만 끼어도 잡음, 한 서브에이전트 혼자 6번 → 잡음(다른 에이전트의 Edit은 그 셈을 지우지 않음)

## 시험

- `tests/test_stallwatch.py`: `test_same_key_strips_prefixes` · `test_loop_prefix_only_same_is_not_loop` · `test_loop_true_repeat_is_caught` · `test_loop_fix_and_rerun_is_progress` · `test_loop_counts_per_subagent`, DB 시험에 「앞머리만 같은 Bash 8개 → 화면에 안 뜸」(실제 SQL 길)
- 전체 pytest **610 통과 · 1 건너뜀**. ruff · mypy는 이 venv에 없어 못 돌림

## 273의 잘못된 「맴돎」 표시

- 화면의 `stall`은 브리지 메모리 스냅숏이고 1분마다 통째로 다시 만든다. 273의 그 턴(6551)은 02:37 UTC(11:37)에 끝나, 열린 턴이 없으니 옛 판정으로도 이미 빠졌다 — **지울 것 없음**
- `notification` 1614(`stall:loop:273:202611110219`)는 「같은 멈춤은 한 번」 막음용 줄이고 화면에 뜨지 않는다. 키가 그 턴 시작 시각이라 끝난 턴에만 걸린다 — 남겨 두어도 된다. 이미 나간 텔레그램은 거둘 수 없다
- 라이브 :8000 · 라이브 DB는 건드리지 않았다(읽기만)

## 합친 뒤 관리자가 할 일

1. 승인 대기 0을 본 뒤 **브리지 다시 띄우기**(`bridge/stallwatch.py` 변경)
2. 다시 띄운 뒤 첫 재기(1분 뒤) 브리지 로그에 `멈춤 알림: … loop`이 헛나오지 않는지
3. (선택) 남은 「실패 8번」 판정을 좁힐지 사용자에게 — 위 인프라 265 사례
