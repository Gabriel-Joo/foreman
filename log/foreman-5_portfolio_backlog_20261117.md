# 밀린 포트폴리오 한 번 밀어내기 (foreman-5 서기, 2026-11-17)

관리자 410이 넘긴 사용자 지시. 517 전에 쌓인 서기실 「코드가 바뀐 편」만, 편 전체가 아니라 읽은 커밋 뒤 바뀐 코드에 걸리는 문단만 고쳤다. 편 목록(16편)은 그대로다.

## 1. 대상

서기실 셈법(머리 주석 「읽은 커밋」..main 사이에 「다루는 곳」을 바꾼 feat, fix 커밋)으로 센 8편. 걸린 커밋은 셋뿐이었다.

| 편 | 걸린 커밋 |
|---|---|
| 01_pixel_office | fb7121b(517 문서 밀림 사슬 끊기, `roles.js`) |
| 06_handoff | fb7121b, afcad6b(514 실패 알림 바로, Fable 가격 비우기) |
| 07_merge | fb7121b |
| 08_foreman_plan | fb7121b |
| 09_new_session | fb7121b, afcad6b |
| 10_scribe_room | 5adb03a(513 포트폴리오 패널 프로젝트별) |
| 14_usage | afcad6b |
| 15_telegram | afcad6b |

고친 뒤 같은 셈법으로 다시 세어 0편이다. 8편 모두 읽은 커밋을 fb7121b(main)로 바꿨다. 「다루는 곳」은 바꾸지 않았다.

나눈 방법: 10편과 14, 15편은 서브에이전트 둘에게 맡기고(병렬), 01, 06, 07, 08, 09편은 이 세션이 고쳤다. 서브에이전트 결과는 diff와 코드로 다시 확인했다.

## 2. 고친 문장과 근거

| 편:줄 | 무엇을 | 근거 |
|---|---|---|
| 01 | 읽은 커밋만. 53줄 「코드를 고치는 코더」는 짧게 줄인 말이라 지금도 맞음 | `bridge/static/js/roles.js` |
| 06:54 | 요약 문단 끝에 더함: 요약이 꼴 없이 끝남, 기다리는 중 세션 끝남, 시간 초과면 ⚠를 단 텔레그램 알림이 바로 가고 묶음을 켠 프로젝트여도 미루지 않음 | `bridge/handoff.py` `_notify(fail=True)`, `bridge/notify.py` `direct_decision`, afcad6b, `log/foreman-5_fail_now_unpriced_20261117.md` |
| 07 | 읽은 커밋만. 517이 「📄 걸리는 문서」 줄을 이미 넣었고, 30줄 「관리자 세션에 카드를 알리지 못하면 바로 알림」은 지금 코드(`later=False`)와 맞음 | `bridge/mergeprep.py` `_tell_manager_card`, fb7121b |
| 08:49 | 교장이 코드 고친 뒤 문서만 맞추는 서기 세션을 따로 내지 않고, 규칙은 브리지가 코더 첫 글 끝에 붙인다는 두 문장 | `bridge/foreman.py` INSTRUCTIONS 「coder」 줄, `bridge/handoff.py` `_finish_spawn`, fb7121b |
| 09:34 | 역할 표 아래 새 문단: 코더로 띄우면 첫 입력 끝에 문서도 함께 고치라는 규칙과 거꾸로 찾는 도구 안내가 붙고, 요약 넣고 시작할 때도 붙으며 디자이너, 조사에는 없음 | `bridge/docrefs.py` `prompt_block`, `bridge/roles.py` `CODER_DOCS_RULE`, `DOCS_RULE_ROLES`, `bridge/handoff.py` `inject(rule=)` |
| 10:48 | 게시 사진 캡션을 새 사진에 맞춰 다시 씀(게시됨 16, 바뀜 2, 휴지통 줄) | 새로 찍은 사진, `bridge/static/js/scribe.js` |
| 10:52 | 새 문단: 게시 칸이 서기실을 연 프로젝트의 목록을 읽고 게시, 다시 게시, 내리기, 원본 없는 페이지 내리기를 그 프로젝트로 보냄. portfolio 폴더 없으면 「아직 없음」, 커밋 못 읽으면 읽지 못했다고, Notion 자리 없으면 버튼이 까닭과 함께 막히고 서버도 거절 | 5adb03a, `bridge/static/js/scribe.js` `portPubBlock`, `bridge/notion.py` `portfolio_place`, `bridge/api/publish.py`, `log/foreman-4_portfolio_per_project_20261117.md` |
| 14:19 | Fable 가격 칸을 출처가 없어 비웠고 그 토큰은 「모름」, 화면 띠 「환산이 일부 빠졌습니다.」와 카드 「+ 모름」 | afcad6b, `config/usage.toml`, `bridge/usage.py`, `bridge/static/usage.html` |
| 14:21 | 가격 없는 Fable 사용이 빠져 한도 하한이 그만큼 작게 나옴 | `bridge/static/usage.html` 띠 글, `bridge/usage.py` `limit_status` |
| 14:37 | 모델별 표에서 환산 못 한 줄에 「+ 모름」, 호버로 빠진 토큰 수 | `bridge/static/usage.html` `usdRow` |
| 15:38-40 | 바로 가는 알림 표에 세 줄: 🛡 붙은 「⑂ 합치기 준비됨」, 관리자에게 못 전한 「… 텔레그램으로 남깁니다」, ⚠ 인계 요약 실패 | `bridge/mergeprep.py` `rule_urgent`, 1335줄 글, `bridge/handoff.py`, afcad6b |
| 15:48 | 바로 가는 것 문단에 합치기 카드 예외와 인계 요약 실패를 더함 | `config/notify.toml`, `bridge/notify.py` `direct_decision` |

사진: `portfolio/img/10_scribe_room_publish.png`만 지금 화면으로 다시 찍음(마법학교, `tools/screen.py --eval --clip`, 263KB). 열어 보고 비밀값, 토큰, 다른 프로젝트 글이 없음을 확인했다.

## 3. 그대로 둔 것

- 판단 19건(`log/foreman-6_portfolio_scope_check_20261117.md`, `log/foreman-7_portfolio_scope_fix_20261117.md` 「6.」)은 고치지 않았다. 10편 10, 34, 50줄은 원문을 두고 513 동작만 아래 새 문단으로 더했다. 15편 표(판단 `15:27-37`)에는 514와 합치기 카드의 바로 가는 줄만 더했고, 승인 쪽 🛡 규칙 파일 알림(rulefile), 압축, 맥락, 겹침, 응답 없음 줄은 판단 항목이 묻는 것이라 더하지 않았다. 사람이 정할 때 참고: 서브에이전트가 돌고 있는 브리지에서 읽어 보니 인프라 방도 「포트폴리오 게시 게시됨 12」라, 10편 판단 항목이 전제한 「포트폴리오는 FOREMAN만」은 지금 사실이 아니다.
- 「5. 다시 찍을 것」의 사진(01, 00, 02, 10_scribe_room.png, 10_scribe_room_panel.png)은 다시 찍지 않았다. 10편 나머지 두 장은 513이 바꾼 곳이 접힌 게시 머리줄뿐이라 그대로 두었다.
- 14편 11줄 사진은 Fable 가격을 비우기 전 화면이다(다시 찍지 않음).

## 4. 확인 못 한 것

- 「주간 Fable」 카드 한도 하한이 지금 실제로 비어 보이는지(14일 안 옛 관찰 기록이 남으면 아직 뜰 수 있다). 그래서 「그만큼 더 작게」까지만 썼다.
- Notion 자리가 없는 프로젝트의 실제 화면(지금 네 프로젝트 모두 자리가 있다). 코드와 log로만 확인.

## 5. 확인한 것

- 새로 쓴 줄의 줄표, 가운뎃점: 10편 캡션의 「게시됨 16 · 바뀜 2」 하나뿐이고, 화면 글을 글자 그대로 옮긴 것이다.
- `tests/screen_words.py` 걸린 것 없음, `pytest tests/test_screen_words.py` 17 통과.

## 6. 규칙

규칙 위반 없음. 파일 고치기는 Edit, Write로만 했다(서브에이전트도 같다고 보고, 사진은 `cp`로 덮어씀).
