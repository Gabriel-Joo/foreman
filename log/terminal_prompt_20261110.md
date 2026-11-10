# 터미널 프롬프트 줄이기 · 막대 안내 줄 없애기 (11-10, 관리자 세션 244 지시)

## 한 일
1. `deploy/shell/foreman-bashrc` — PS1에서 `사용자@호스트:`만 뺐다(`~/.bashrc`는 그대로). `__foreman_short_ps1`가 색 있는 모양 · 없는 모양 둘 다 지운 뒤 `[창 이름] `을 맨 앞에 붙인다. 창 이름 · `(llm_env)` · 폴더 · 색 · `\[ \]` 감싸기는 그대로.
   - 가상환경이 conda가 아니라 venv다(`~/.bashrc` 120줄 `source ~/llm_env/bin/activate`). venv의 `deactivate`는 `_OLD_VIRTUAL_PS1`로 되돌리므로 그것도 같이 줄인다 → deactivate 뒤에 사용자@호스트가 돌아오지 않는다. conda는 이 서버에 없어 `CONDA_PROMPT_MODIFIER`는 보지 않았다.
2. `bridge/static/js/terminal.js`의 `term-note` 안내 줄과 `panel.css`의 `.term-note` 두 줄을 지웠다. 다른 곳(screen.py · 시험 · docs)에는 이 글 · 클래스가 없었다.

## 잰 값 (시험 tmux, 폭 134에서 시작, `cd ~/AI_programming/petmint-rag-chatbot` 뒤 커서 칸)
| 경우 | 프롬프트 | 전 → 후 |
|---|---|---|
| 변경 전, 134→90→134 | 104칸 | 104 → 99 (어긋남) |
| 변경 후, 134→90→134 | 70칸 | 70 → 70 |
| 변경 후, 134→80→134 | 70칸 | 70 → 70 |
| 변경 후, 134→60→134 | 70칸 | 70 → 65 (어긋남) |

- 프롬프트(70칸)보다 좁아지는 폭(60)에서는 같은 5칸 어긋남이 남는다(고치지 않음, 지시대로).

## 가상환경 표시
- 시작: `[petmint-rag-chatbot] (llm_env) ~/AI_programming/petmint-rag-chatbot$`
- `deactivate` 뒤: `[petmint-rag-chatbot] ~/AI_programming/petmint-rag-chatbot$` (사용자@호스트 안 돌아옴)
- 다시 `source ~/llm_env/bin/activate` 뒤: `(llm_env) [petmint-rag-chatbot] ~/...$` — 순서가 `(가상환경)`이 `[창 이름]` 앞으로 바뀐다(activate가 PS1 맨 앞에 붙이므로). 길이는 같고 표시만 다르다. 맞추려면 activate 뒤 PS1을 다시 만드는 훅이 필요해 하지 않았다.

## 시험
pytest 551 통과 · 1 건너뜀. 시험 tmux는 /tmp 짧은 소켓(`/tmp/fsh-t.sock`)으로 띄워 끄고 지웠다. 라이브 셸(`foreman-shell`)은 건드리지 않았다. 브리지 파이썬은 안 바꿨다.

## 합친 뒤
- **이미 열린 셸 창은 새 셸부터 적용된다 — 창을 새로 띄워야 보인다.**
- 막대 안내 줄은 화면 파일이라 브리지를 다시 띄우지 않아도 된다(새로 고침).

## 남은 것
- 60칸 아래 패널의 커서 어긋남(위).
- activate를 다시 했을 때 `(가상환경)`과 `[창 이름]` 순서.
