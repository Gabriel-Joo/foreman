# 덮기 검사가 not_code를 읽게 함 (foreman-6, 2026-11-17)

## 한 일

- `bridge/doctext/check.py` 덮기 대상 `target_files`에서 `not_code`에 드는 파일을 뺀다. 맞추는 함수는 거꾸로 찾기가 쓰던 `config.not_code_match`를 가져다 썼고 새로 짜지 않았다. 확장자, 경로, 글롭 셋 다 된다.
- 확장자 `.md`만은 뺀 목록에서 제외한다(아래 판단).
- 시험 `tests/test_docs_check.py::test_cover_skips_not_code`: 확장자, 경로, 글롭이 대상에서 빠지고 덮기 밖 틀림으로도 안 나온다. 안 든 파일과 `.md`는 그대로 덮기 밖으로 나온다.
- 문서: `docs/12_scribe.md` 점검 줄, `notion/10_scribe/03_evidence.md`.
- 런슈즈에 `records`로 사진 폴더를 넣는 우회는 쓰지 않았다.

## 덮기 수(대상, 덮음)

| 저장소 | 고치기 전 | 고친 뒤 | 줄어든 대상 |
|---|---|---|---|
| FOREMAN | 501, 501 | 496, 496 | 사진 0, md 0, 그 밖 5(`.gitignore`, `__init__.py` 넷) |
| 인프라 | 113, 113 | 113, 113 | 0(`not_code`가 기본 `.md`뿐) |
| 런슈즈(작업방 `docs/foreman-tool`) | 959, 825 | 830, 825 | 129 = 사진 117, md 0, 그 밖 12(잠금, 빌드와 도구 설정, `.claude/*`, `.foreman/*`) |

런슈즈 덮음이 사용자 말(822)과 825로 다른 것은 읽은 작업방 커밋 차이로 보인다(까닭은 확인하지 않았다). 런슈즈 `.foreman/docs.toml`은 `main`에 없고 작업방 `.claude/worktrees/foreman-tool`에만 있어 거기서 읽기만 했다. 고친 뒤 런슈즈의 틀림 134가 5로 줄었고, 남은 5는 덮기 밖이다.

## 판단이 갈리는 것: `.md`까지 뺄까

`not_code` 기본값 `[".md"]`를 그대로 빼면 문서 묶음 밖 md도 덮기 대상에서 빠진다. 줄어드는 수(지금 대상에 든 md): FOREMAN 5(`CLAUDE.md`, `README.md`, `LICENSES.md`, `.claude/agents/Explore.md`, 스프라이트 `README.md`), 인프라 22(`CLAUDE.md`, `README.md`, `apps/*/README.md`, 운영 절차서 `runbooks/*.md`), 런슈즈 5.

- 빼는 쪽: 덮기는 「코드와 설정 파일을 어느 편이 다루나」를 보는 검사이고, md는 코드가 아니다.
- 두는 쪽: 인프라 운영 절차서 22개는 어느 원고가 다루는지 보고 싶은 글이다. 빼면 안 다뤄도 조용히 넘어간다. 이 프로젝트의 조용한 고장을 막는 쪽이다.

사용자가 정할 일이라 `.md`는 빼지 않고 지금 동작을 두었다. 빼기로 하면 `check.py`의 `skip` 한 줄(`p != ".md"` 조건)만 지우면 된다.

## 시험

main(`b6aebf9`, 코더 546) 위로 rebase한 뒤 다시 돌렸다. 충돌은 `docs/12_scribe.md` 점검 줄 하나였고, main쪽 `readme` 줄과 `check` 줄을 두고 거기에 덮기 설명 문장만 다시 얹어 양쪽 고침을 모두 살렸다.

- pytest 전체 1403개 통과, `node --test tests/js/` 227개 통과
- `tools/docs.py check`: 틀린 것 0, 새 줄 줄표 0, 덮기 496 가운데 496
- `tools/docs.py readme --dry`: README.md와 같다(차이는 알림 한 줄뿐). 다시 만들 것 없음

## 규칙 위반 없음
