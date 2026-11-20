# 원고 고침 한 번에 (관리자 410 서기 일감, 11-20)

> 규칙 위반 있음(하나). 시작한 main 커밋: `b2ba192`. 브랜치 `cc/foreman-4`, 커밋만 하고 push하지 않았다.
> 위반: 한국어 규칙. 11-20 이 일 시작 쪽(API 오류로 응답이 끊기기 전)에서 도구 호출 사이 진행 글 한 번이 영어였다. 훅이 두 번 알려 주어 그 뒤 모든 진행 글을 한국어로 돌렸다. 까닭은 도구 결과가 영어여서 그대로 이어 썼기 때문이다. 이 밖에 sed, heredoc, 리디렉션, `python -c`, `pgrep -f`는 쓰지 않았고 파일은 Edit, Write로만 고쳤다.

## 한 일

1. 다루는 곳 넣기: `03_keys`에 `bridge/config.py`, `03_promote`에 `handoff.js`와 `moveflow.js`, `01_room`에 `bridge/foreman.py`, `office.js`, `bridge/postit.py`. 본문이 그 파일의 동작을 설명하는지는 본문에서 해당 절을 찾아 맞댔다
2. `08_handoff.md` 다루는 곳에서 `docs/11_handoff.md`, `docs/11_handoff_v2.md`를 뺐다
3. `notion/` 모든 편의 다루는 곳에서 시험 파일을 뺐다(33편). `tests/` 아래, `test_*.py`, `*.test.mjs`, `conftest.py`, `tests/fixtures/`, 글롭 `tests/test_notion*.py`까지
   - `tools/docs.py check` 덮기 줄: 전 「519 가운데 519 덮음(다루는 곳 없이 덮은 것으로 친 시험 파일 2)」, 후 「519 가운데 519 덮음(… 시험 파일 174)」. 덮은 수는 그대로이고 시험 파일 172개가 「다루는 곳 없이 덮은 것」으로 옮겨 갔다
   - `notion/16_tests.md`는 다루는 곳이 시험 파일 위주였다. 시험이 아닌 `pyproject.toml`, `requirements.lock`, `deploy/systemd/foreman-bridge.service`만 남았다
4. 낡은 줄 둘
   - `notion/15_db.md`: hook은 파이프라인이 아니라 `bridge/api/hooks.py`가 조립기 `apply_hook`을 불러 넣는다(코드로 확인). `Store.insert_event`가 넣는 것은 셸, 웹훅, 승인, 입력 넣기, 디버그다. 이미 들어간 이벤트를 고치는 곳(조립기가 부 에이전트 이벤트 `turn_id`, `pipeline.py`가 `commit_sha`)을 한 문단 더했다. 읽은 커밋을 `b2ba192`로 올렸다(이 절만 코드와 맞댔지 편 전체를 다시 읽지는 않았다는 점은 아래 「사람이 정할 것」)
   - `docs/12_scribe.md`: 게시 경로가 한 함수(`DocSync.run_one`과 `sync`)라는 말이 「Publisher.publish가 쓴다」로 남아 있어 고쳤다. 잠금(프로젝트마다), 한 편 게시의 다시 잇기와 차례, 사람이 지운 페이지(`gone`)는 이미 같은 파일 다른 줄에 있었다. 낡았던 것은 다루는 곳 줄의 「시험 파일은 그 시험이 지키는 기능 편의 다루는 곳에 둔다」라서 11-20 결정으로 바꿨다
5. 갈래 옮기기
   - `05_roles/02_guards.md` 9절: 「미해결」 설명 줄과 표시를 지우고 「일부러 막지 않은 것」으로 썼다(까닭은 그대로 그림 넣기 헛걸림). 한계로 남긴다
   - `14_screen/05_check.md`: 6절 「알려진 한계」를 지우고 mp4 결정을 3-2절 본문으로 옮겼다. 6절에는 그 줄 하나뿐이어서 절째 없앴다. 「ffmpeg를 새로 깔지 않기로 한 까닭은 기록에 없다」를 적었다
   - `17_limits.md`는 이 둘을 가리키지 않아 고치지 않았다

## 점검

- `tools/docs.py check`: 틀린 것 0, 의심 207(전 208)
- `.venv/bin/python -m pytest -q`: 1583 passed

## 설계와 달랐던 점

- 일감은 「시험 파일 M으로 옮겨 가야 한다」고 했고 실제로 그랬다. 2에서 174로.
- 일감 4의 `docs/12_scribe.md`는 182줄 쪽 게시 줄 자체보다 같은 편의 다루는 곳 줄과 176줄 「같은 Publisher.publish」가 낡았다.

## 사람이 정할 것

- 읽은 커밋은 `15_db.md`만 올렸다. 다루는 곳을 더한 `03_keys`, `03_promote`, `01_room`과 갈래를 옮긴 `02_guards`, `05_check`는 편 전체를 코드와 다시 맞대 읽지 않아 올리지 않았다. 이 편들이 낡았는지 서기 「고쳐 쓰기」로 다시 읽게 할지 정해야 한다
- `15_db.md` 다루는 곳에 `bridge/store.py`, `bridge/api/hooks.py`를 넣을지(본문이 짧게 동작을 말한다)
