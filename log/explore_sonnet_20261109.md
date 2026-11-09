# FOREMAN 기본 제공 Explore를 sonnet으로 (2026-11-09)

사용자 지시: 런슈즈 `57420bd`와 같은 방식으로 FOREMAN에도. worktree `foreman-3`(브랜치 `cc/foreman-3`).

## 한 일

- `.claude/agents/Explore.md` 새로 — 런슈즈 것과 같은 frontmatter(`name: Explore`, `disallowedTools: Agent · Edit · Write · NotebookEdit · ExitPlanMode · Artifact · ArtifactComments · ArtifactData · ArtifactCheck`, `model: sonnet`)와 읽기 전용 본문(끝에 "답은 한국어로")
- `.gitignore`에는 `.claude`를 빼는 줄이 없고 `.claude/settings.json`이 이미 추적 중 → 새 파일도 그대로 커밋된다
- CLAUDE.md 「작업 규칙」에 한 줄: 덮어썼다는 것 · FOREMAN은 `CLAUDE_CODE_SUBAGENT_MODEL`을 쓰지 않아 다른 서브에이전트는 그대로(부모 모델)

## 확인 (같은 찾기 일: operations.md에서 "worktree"가 나오는 줄 3개, `model` 인자 없이)

| | 세션 | 서브에이전트 메타 | `"model"` 센 결과 |
|---|---|---|---|
| 이 worktree 안 | `5ae6f0f1` | `isBuiltIn: false` (덮어쓴 정의) | assistant 응답 **sonnet 2** (파일 전체 grep 시 sonnet 4 + 메타 줄 opus 1) |
| 저장소 밖(임시 폴더) | `fd1c3240` | `isBuiltIn: true` | **opus 8** |

- 둘 다 답은 줄 25 · 56 · 70으로 같았다
- 저장소 안 jsonl에서 센 opus 1줄은 응답이 아니라 요청 쪽 기록(메타의 `pickedEffortModel`이 `claude-opus-5-5`)이다. 응답을 낸 모델은 assistant 줄의 `message.model`이 sonnet 둘뿐이다 (런슈즈 기록의 "opus 1줄"과 같은 종류)
- 저장소 밖에서 쓴 임시 폴더는 지움. FOREMAN 세션이 아니라 `claude -p` 시험이므로 세션 숨김(`hidden_reason='test'`)은 해당 없음

## 남은 것

- 떠 있는 기존 세션은 시작할 때 에이전트 정의를 읽으므로, 이 덮어쓰기는 **합친 뒤 새로 뜨는 세션**부터 먹는다(이번 확인도 새 `claude -p`로 했다)
- 브리지 코드 변경 없음 → 다시 띄울 일 없음. 커밋만, push 안 함
