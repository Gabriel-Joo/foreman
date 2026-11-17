# 포스트잇을 받은 편지함 겸 TODO 보는 창으로 (문서 정리 E, cc/foreman-4, 2026-11-17)

관리자 410 일감. 사용자는 자리를 비웠고, 판단이 필요한 것은 고치지 않고 맨 끝 「아침에 사람이 정할 것」에 모았다.

## 1. 한 일

| 커밋 | 무엇 |
|---|---|
| `d27ed20` feat | `bridge/todofile.py`: 저장소 `docs/TODO.md`를 HEAD 판으로 읽고(FOREMAN 꼴, 인프라 꼴), 다음 번호로 더하고, 지우고, 커밋 메시지의 `(todo:번호)`를 읽는다. 시험 `tests/test_todofile.py` |
| `79acf9c` feat | `bridge/postit.py` `to_todo`, `to_limit`, `todo_remove`, `todo_view`, `pieces_of`. API 넷(`GET /api/postit/pieces`, `POST /api/postit/{id}/todo`, `POST /api/postit/limit`, `POST /api/postit/todo/remove`). 옛 [→](`close limit`)는 409. 서기 「알려진 한계 쓰기」 재료와 지시문을 편, 까닭, TODO 지우기에 맞춤 |
| `c9770fb` feat | `postit.js` 세 묶음, [TODO로] [한계로] [x], [한계로] 칸(까닭이 비면 [보내기] 꺼짐), 할 일 줄의 「커밋 abc가 끝냄」과 [지우기], 머리 탭 호버와 주황. css 몇 줄. 화면 말 목록 두 줄 |
| `7f2eecc` docs | `docs/12_scribe.md` 「11.」(11-8 새 절), `notion/10_scribe/02_postit.md`, `portfolio/11_postit.md` |
| (rebase 뒤) fix | 관리자 덧붙임대로 세 묶음, 줄마다 펼침, 「끝낸 것」을 `render.js` `keep`으로(555 `5a5031e`와 같은 길). 세 묶음은 접는 칸(처음값 펼침) |

시험: `.venv/bin/python -m pytest -q` 1427 통과, `node --test tests/js/` 239 통과, `tools/docs.py check` 틀린 것 0(새 줄 줄표 0), `tools/docs.py readme` 이미 같음. main(`82f0c90`)으로 rebase했고 `git merge-tree`로 먼저 본 충돌은 없었다.

화면: 미리보기(포트 8217, 끝낸 뒤 껐다)와 `tools/screen.py --themes magic,office,space --sizes 1600x1000`로 포스트잇 창을 열어 찍었다. 세 테마 모두 점검 문제 0건, 세 묶음이 펼쳐진 채 그려진다. 미리보기의 API는 도는 브리지(main 코드)라 「할 일」은 「docs/TODO.md를 읽지 못했습니다」로 보였다(0으로 보이지 않는 것까지만 확인). 할 일 줄, [한계로] 칸, [지우기]가 실제 데이터로 그려지는 모습은 합친 뒤 브리지를 다시 띄워야 볼 수 있고, 보지 못했다.

## 2. 동작 요약

- 「아직 안 보낸 것」 = 열린 포스트잇(new, taking, merged). 적는 칸이 묶음 머리 바로 밑. 적는 것은 DB에만
- 「할 일」 = HEAD의 `docs/TODO.md` 번호와 한 줄 제목, 올린 날. 내용은 복사하지 않는다. 30일 넘은 항목은 「30일 넘은 것」으로만 간다
- [TODO로]: 브리지가 원본 폴더에서 다음 번호(지금 파일과 `git log -p` 기록의 최대 + 1)로 그 저장소 꼴대로 「## 포스트잇에서 보낸 것」 절 끝에 더하고 `git commit --only -- docs/TODO.md`. push 안 함. 막는 때: HEAD 떼어짐, 합치기나 rebase 중, `docs/TODO.md`에 커밋 안 된 변경, 커밋 실패(파일을 HEAD로 되돌림). 포스트잇은 `closed_reason todo`, `closed_note`에 번호와 커밋
- [한계로]: 편(기술문서, 포트폴리오 묶음 HEAD의 .md) 고르기와 까닭. 까닭이 비면 화면이 막고 서버도 409. 포스트잇은 `limit`, `closed_note`는 `TODO:`(TODO에서 보냈을 때), `편:`, `까닭:` 줄. TODO 항목에서 보내면 닫힌 `todomd` 줄을 새로 만든다. 서기 「알려진 한계 쓰기」가 편에 쓰고, TODO에서 온 줄은 같은 커밋에서 항목을 지우고 메시지에 `(todo:번호)`
- `(todo:번호)`: 최근 커밋 500개를 HEAD가 바뀔 때만 다시 읽는다. 항목에 칩과 [지우기], 머리 탭 주황. 저절로 지우지 않는다(일감의 「가장 덜 위험한 쪽」)
- 스키마는 바꾸지 않았다(스키마 잠금 안 걸림). `source` VARCHAR(8)에 `todomd`, `closed_reason` VARCHAR(8)에 `todo`가 들어간다

## 3. 옛 포스트잇이 어디에 보이나

마이그레이션 없이 표시 규칙으로 정했다: 열린 상태(new, taking, merged)는 모두 「아직 안 보낸 것」. 11-17 DB를 읽기만 해서 센 값: foreman new 43, done 19, drop 2 / runshoes new 4, drop 3 / ronanlab-infra new 12 / petmint-rag-chatbot new 1. 옛 [→](limit) 줄은 0장이라, 편과 까닭 없는 옛 한계 줄을 따로 다룰 일이 없다(재료에 「편 없음, 쓰지 말고 알려라」 갈래만 남겼다). 끝난 것으로 보이는 5장, 일부 끝난 2장, [갱신] 안 받은 18장은 건드리지 않았다.

## 4. 조사 결과, 설계와 달랐던 점

- TODO.md 꼴이 넷이다: FOREMAN `- **foreman-N** 제목 (날)` + 들여 쓴 내용(123개), 인프라 `- infra-N (날) 할 일 → 나온 곳`(43개), 런슈즈 `- [ ]` 체크 목록(번호 없음), 펫퍼민트 표(번호 없음). 번호 없는 둘은 「번호 붙은 항목이 없습니다」로 보이고 [TODO로]는 거부한다
- 인프라 항목 제목이 한 문장 전체라 길다. 화면은 90자에서 자른다
- 「알려진 한계 쓰기」의 맡을 파일을 원고 폴더 통째로 적으면 열린 포트폴리오, 기술문서 일과 늘 겹쳐 막혀서, 정적 값은 `README.md`, `docs/TODO.md`로 두고 띄울 때 고른 편 파일을 더하게 했다(`blocked`의 `extra`, dispatch 기록에도). 그 대신 `docs/` 통째로 맡는 「CLAUDE.md 정리」와는 `docs/TODO.md`로 겹쳐 막힌다(시험 기대값을 바꿨다)
- 옛 README 생성물 거부(`LIMIT_GONE`, `readme_generated`)와 그 시험은 없앴다. [갱신]의 README 「알려진 한계」 뺄 줄 길은 README에 그 절이 있는 저장소에서 그대로 돈다
- 브리지 커밋은 세션 도구 호출을 거르는 `reposcope`를 거치지 않는다. 대신 사람 단추로만, 그 파일 하나만, push 없이 하고, 프로젝트 토큰은 새 API에 닿지 않는다(`scopetoken`에 길을 더하지 않음)
- 거꾸로 찾기(`tools/docs.py refs`)의 「모름」 문단(`docs/15_usage.md`, `notion/01_structure.md`, `notion/08_handoff/03_promote.md` 등)은 읽어 보니 지금 코드와 맞아 그대로 두었다

## 5. 규칙 위반

- 진행 글 한 줄을 영어로 썼다(「Now wiring the form state…」, [한계로] 칸 상태를 잇던 때). 브리지 훅이 알려 다음 글부터 한국어로 썼다
- 새 코드 주석과 시험 주석 25곳에 em dash와 가운뎃점을 넣었다(일감 「새 문서 글은 em dash와 가운뎃점 없이」, `docs/manuscript_rules.md` 1절). 전체 pytest의 줄표 시험이 잡아 커밋 전에 모두 쉼표, 마침표로 고쳤다
- 뜻 없는 `cat > /dev/null <<'X'` 명령을 한 번 쳤다(파일을 고치지 않았지만 heredoc 리디렉션 꼴이다). 그 뒤로 쓰지 않았다
- 위반은 아니지만 적는다: 런슈즈 저장소에 `git -C … symbolic-ref`(읽기)를 쳤다가 다른 저장소 막음에 거부됐다. 그 뒤로 다른 저장소는 `ls`, `head`로만 읽었다

## 6. 아침에 사람이 정할 것

1. **브리지가 다른 저장소 원본 폴더에 커밋해도 되나.** 지금 코드는 인프라, 런슈즈, 펫퍼민트 방에서도 사람이 [TODO로], [지우기]를 누르면 그 저장소 `docs/TODO.md`만 담아 커밋한다(push 없음). 다른 저장소 막음(`reposcope`)은 세션용이라 걸리지 않는다. 막아야 하면 프로젝트별 설정 한 칸으로 끄게 하는 일이 남는다
2. **push.** 브리지 커밋은 push하지 않는다. FOREMAN은 관리자가, 인프라는 `[repo_scope.manager_push]` 길로 관리자가 push한다고 보았다. 런슈즈, 펫퍼민트는 그 저장소 관리자 몫
3. **브리지 커밋의 Co-Authored-By.** 사람 단추로 코드가 만든 커밋이라 Claude 줄을 붙이지 않았다. 저장소 커밋 규칙에 맞는지
4. **런슈즈, 펫퍼민트 TODO.md 번호 꼴.** 지금은 「번호가 없습니다」로만 보이고 [TODO로]를 거부한다. 번호 꼴로 바꿀지는 그 저장소 일
5. **새 항목을 넣는 자리.** FOREMAN은 「## 1. …」 ~ 「## 9. …」 번호 절인데 [TODO로]는 파일 끝 「## 포스트잇에서 보낸 것」에 넣는다. 절을 고르게 할지, 서기가 옮길지
6. **30일 넘은 것.** 「할 일」에서 빼고 「30일 넘은 것」에만 보이게 했다(겹쳐 보이지 않게). 두 묶음 모두에 보이길 원하면 한 줄 고침
7. **`(todo:번호)` 알림의 세기.** 지금은 화면(칩, [지우기], 머리 탭 주황)뿐이고 텔레그램은 없다
8. **「알려진 한계 쓰기」와 「CLAUDE.md 정리」가 `docs/TODO.md`로 겹쳐 동시에 못 돈다.** 보수적으로 막았다
9. **포트폴리오 사진.** `portfolio/img/11_postit*.png`는 옛 화면([→] 단추)이다. 글은 고쳤고 사진은 합치고 브리지를 다시 띄운 뒤 다시 찍어야 한다
10. 합친 뒤 브리지를 다시 띄워야 새 API가 돈다. 그 전에는 창이 「할 일」을 「읽지 못했습니다」로 보인다
