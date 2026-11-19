# 포스트잇이 다른 저장소에 커밋할 때의 막음과 기록 (E1, cc/foreman-4, 2026-11-19)

관리자 410 일감. 사용자 결정(11-19): 사람이 포스트잇에서 [TODO로], [지우기]를 누르면 브리지가 다른 저장소(인프라, 런슈즈, 펫퍼민트) 원본 폴더에 직접 커밋해도 된다. 조건은 TODO.md 하나만, push 없음, 커밋 안 된 변경이 하나라도 있으면 거부하고 까닭을 포스트잇에 남김, 누른 것마다 무엇을 어느 저장소에 넣었는지 포스트잇에 남김.

## 1. 한 일

- `bridge/todofile.py`: `dirty_files(repo)`를 더했다. `git status --porcelain -z --untracked-files=normal`로 저장소 전체(추적 파일의 고침, 스테이지, 추적 안 하는 새 파일)를 본다. `_commit_sync`가 하나라도 있으면 `TodoError`로 거부한다. 까닭에 걸린 파일(앞 다섯 개와 나머지 개수)을 적는다. 커밋은 그대로 `git commit --only -- docs/TODO.md`다(가 조건 한 겹 더)
- 새 표 `postit_repo_log`(`migrations/0034_postit_repo_log.sql`): 열린 포스트잇에는 메모나 이력 칸이 없고(`closed_note`는 닫을 때만 쓰인다), 거부된 포스트잇은 닫히지 않으므로 새 표를 두었다. 칸은 project, repo, postit_id, action(add, remove), ok, todo_id, commit, note, created_at. 스키마 잠금은 걸리지 않았다
- `bridge/postit.py`: `to_todo`와 `todo_remove`가 성공과 거부 모두 `log_repo`로 한 줄 남긴다(기록을 못 남겨도 결과 보고는 막지 않고 로그만). 성공한 [TODO로]의 `closed_note`에 `저장소:`와 `docs/TODO.md에 더함, push 안 함` 줄을 더했다. `repo_log()`가 화면용 읽기
- `bridge/api/postit.py`: `GET /api/postit` 응답에 `repo_log`(최근 20줄)와 열린 줄마다 `repo_refused`(마지막 거부 까닭, 그 뒤 성공해 닫히면 열린 줄에서 사라진다)를 더했다
- `bridge/static/js/postit.js`: 못 넣은 줄 밑에 빨간 거부 까닭, 맨 아래 「저장소에 넣은 기록 N」 접는 칸(시각, 성공은 흐리게, 거부는 「못 함:」). 완료 알림에 어느 저장소인지 넣었다
- 시험: `tests/test_todofile.py`(고침, 스테이지, 추적 안 하는 새 파일 각각 거부와 아무것도 안 건드림, 한글 이름과 이름 바꾸기, 무시한 파일은 변경이 아님, 막음을 끄고도 다른 스테이지가 안 섞여 커밋이 TODO.md 하나뿐인 것), `tests/test_stage2_db.py`(더러운 저장소에서 [TODO로] 거부, 기록 줄, 화면 응답의 `repo_refused`, 정리 뒤 성공과 기록, `closed_note` 정확한 내용, [지우기] 거부와 성공 기록), `tests/js/postit.test.mjs`(거부 까닭과 기록 칸). 임시 저장소에서만 돌렸고 실제 저장소에는 커밋하지 않았다
- 문서: `docs/12_scribe.md` 11-1, 11-8, `notion/10_scribe/02_postit.md`, `notion/15_db.md`, `notion/15_db/01_tables.md`(새 표 절과 표 개수), `notion/15_db/02_migrate.md`, `portfolio/11_postit.md`. 화면 말 목록(`tests/data/screen_words.toml`)에 바뀐 거부 글 한 줄

시험: `.venv/bin/python -m pytest -q` 1432 통과, `node --test tests/js/` 240 통과, `tools/docs.py check` 틀린 것 0(새 줄표 0), `tools/docs.py readme` 이미 같음. 화면은 직접 띄워 보지 않았다(JS는 문자열 시험만).

## 2. 조사 결과, 설계와 달랐던 점

- **한글 파일 이름 문제를 시험이 잡았다.** `git status --porcelain`은 한글 이름을 따옴표와 8진수(`"\353\202…"`)로 보인다. `-z` 출력으로 바꾸고 이름 바꾸기(R, C)의 옛 이름 칸을 건너뛰게 했다
- 일감의 [한계로]와 [TODO에서 온 것 지우기]는 브리지가 저장소에 직접 커밋하지 않는다. [한계로]는 포스트잇 DB에 닫힌 줄을 만들 뿐이고, TODO.md 항목 지우기는 서기 세션이 자기 worktree에서 같은 커밋으로 한다. 그래서 브리지의 직접 커밋은 [TODO로]와 [지우기] 둘이고, 이 둘에 막음과 기록을 걸었다. [한계로]의 기록은 이미 `closed_note`(편, 까닭, TODO 번호)에 남는다
- [지우기]는 눌린 포스트잇이 없다(TODO 항목에서 누른다). 그래서 그 기록은 포스트잇 줄이 아니라 창 아래 「저장소에 넣은 기록」에 남는다. 열린 포스트잇에서 눌리는 [TODO로]만 줄 밑에 거부 까닭이 붙는다
- 다른 저장소 상태는 읽지 않았다(시험은 임시 저장소). 인프라, 런슈즈, 펫퍼민트 원본 폴더에 지금 커밋 안 된 변경이 있는지는 모른다

## 3. FOREMAN 자기 저장소에도 걸리는가

걸린다. 이 세션 중 원본 폴더 `git status`(읽기만)에 관리자가 고치는 `log/manager410_overhead_20261115.md`가 커밋 안 된 채 있었다. 그때 FOREMAN 방에서 [TODO로]를 누르면 거부됐을 것이다. `.worktrees/`와 `.run/`은 무시되어 걸리지 않는다. 관리자가 원본 폴더에서 `log/`를 쓰고 합치고 하는 시간이 길어서 거부가 잦을 수 있다. 막는 쪽이 맞다고 보고 FOREMAN만의 예외는 짜지 않았다.

## 4. 규칙 위반

- 진행 글 몇 줄을 영어로 썼다(「Now update the existing test…」, 「Apply doc edits…」 등 훅이 네 번 알렸다). 알림을 받은 뒤 한국어로 썼다. 같은 실수를 되풀이했으니 쓰기 전에 한국어인지 본다
- 의미 없는 `sed -i 's/x/x/' /dev/null`을 한 번 쳤다. 파일을 고치지 않았고(실제로 `/dev/null`이라 실패했다) 이후 쓰지 않았다. 파일은 모두 Edit, Write로 고쳤다
- 그 밖에 `pgrep`, heredoc, `python -c` 파일 고치기 없음. 다른 저장소 폴더에 커밋하거나 상태를 읽지 않았다

## 5. 사람이 정할 것

1. **추적 안 하는 새 파일(`??`)도 막는 쪽으로 짰다.** 일감대로 막았다. 부작용: 저장소에 임시 파일이나 메모가 하나만 있어도 [TODO로]가 거부된다. 풀려면 `dirty_files`에서 `??`를 빼면 된다(한 줄). 무시하기로 한 파일(`.gitignore`)은 이미 걸리지 않는다
2. **FOREMAN 자기 저장소.** 위 3절대로 관리자가 원본 폴더에서 일하는 동안 거부된다. 막는 쪽이 맞다고 보아 예외를 짜지 않았다. 관리자가 일을 마칠 때 `log/` 등을 커밋하는 습관이면 문제가 적고, 아니면 FOREMAN만 「`log/` 변경은 무시」 같은 예외를 두는 안이 있다. 정하면 한 줄 일이다
3. **「저장소에 넣은 기록」은 20줄만 화면에 보인다**(DB에는 모두 남는다). 더 보려면 창에 더 보기를 더한다. 지금은 고치지 않았다
4. **기록이 DB에만 있다.** 저장소 쪽(커밋 메시지 본문)에는 포스트잇 번호가 이미 들어 있다. 다른 곳(텔레그램 등)에 알릴지는 정하지 않았다
5. 합친 뒤 마이그레이션 0034를 올리고 브리지를 다시 띄워야 새 기록이 돈다. 마이그레이션 없이 새 코드만 뜨면 막음은 돌지만 기록은 못 남기고 브리지 로그에만 남는다. 옛 브리지는 옛 규칙(`docs/TODO.md`만 봄)으로 돈다

## 6. 사용자 답 뒤 되돌림 (11-19, 같은 브랜치)

사용자 답(관리자 410 전달): 조건 「다」를 저장소 전체로 넓힌 것은 과했다. 거부는 둘뿐이다. (1) `docs/TODO.md`가 더러울 때(고침, 스테이지), (2) rebase, merge, cherry-pick, revert 중이거나 HEAD가 떼어졌을 때. 다른 파일이 더러운 것과 추적 안 하는 새 파일은 보지 않는다(커밋에 안 들어간다). 커밋은 `--only -- docs/TODO.md`. FOREMAN 예외는 짜지 않는다. 라(기록), 화면 기록 칸 20줄, 마이그레이션 0034는 그대로 둔다.

바꾼 것:
- `bridge/todofile.py`: `dirty_files`를 지웠다(쓰는 곳이 없어졌다). `_commit_sync`는 `git status --porcelain -- docs/TODO.md`만 보고 거부 글도 원래대로 「docs/TODO.md에 커밋 안 된 변경이 있어 건드리지 않았습니다. 다른 세션이 고치는 중일 수 있습니다」다. HEAD 떼어짐과 합치기, rebase, cherry-pick, revert 거부는 그대로다. `screen_words.toml`에 더했던 바뀐 글 한 줄도 뺐다(글이 원래로 돌아와서)
- 시험: 저장소 전체 거부 시험(고침, 스테이지, `??` 각각)과 `dirty_files` 시험, 검사를 끄는 시험을 지우고 다음으로 바꿨다. 다른 파일의 고침, 스테이지 뒤 또 고침, 추적 안 하는 새 파일, 한글 이름이 있어도 [TODO로]와 [지우기]가 커밋되고 커밋에 TODO.md만 들며 남의 변경은 그대로인 것, TODO.md가 스테이지에 올라 있으면 거부, 합치기, cherry-pick, revert, rebase 표시가 있으면 거부. DB 시험은 더러운 파일을 `docs/TODO.md`로 바꿔 거부와 기록(까닭에 「docs/TODO.md에 커밋 안 된 변경」)을 보고, 추적 안 하는 새 파일이 있어도 성공하는 것을 본다
- 문서: `docs/12_scribe.md` 11-8, `notion/10_scribe/02_postit.md`, `portfolio/11_postit.md`, 주석
- 위 1절의 `dirty_files`, 한글 이름 `-z` 처리, 3절(FOREMAN 원본 폴더가 더러우면 거부됨), 5절 1번과 2번은 이 되돌림으로 없어졌다. 3절의 관찰(관리자가 `log/`를 고치는 중)은 이제 [TODO로]를 막지 않는다

되돌림 중 규칙 위반: 의미 없는 `cat > /dev/null <<< ""` 명령을 한 번 쳤다(파일은 고치지 않았고 `/dev/null`로 보냈을 뿐이다). 그 밖에 없다. 진행 글은 한국어로 썼다.
