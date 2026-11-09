# 펫퍼민트 docs → Notion — 옵션 · 짝 등록 · 모의 실행: 20쪽 모두 멈춤이라 켜지 않음 (2026-11-09 오후, 원본 폴더)

앞 기록: [screen_mismatch_waits_20261109.md](screen_mismatch_waits_20261109.md) 「펫퍼민트 docs 자동 반영」

## 한 일

- 게시기 프로젝트 옵션(`config/notion.toml` 칸, 없으면 지금 동작 그대로 — 런슈즈 · FOREMAN 영향 없음)
  - `create = false` — 짝(doc_publish)이 없거나 범위 밖이면 만들지 않고 실패(새 페이지 0 보장)
  - `title = "keep"` — 제목을 건드리지 않음("00. 모델 준비" — 사이드바 순서). `order = "keep"` — 옮기기 · 차례 바꾸기 없음
  - `header = "footer"` — 맨 위 사본 상자 대신 맨 아래 회색 한 줄 "마지막 갱신 — 커밋 · 시각"(Notion API엔 글자 크기가 없어 회색)
  - `keep_notion = ["inline_code", "image"]` — 글(plain)이 같고 꾸밈만 다르면 Notion 글 그대로, 저장소 그림 자리는 Notion 그림 블록과 차례로 짝지어 그대로(다시 올리지 않음). 사람 수정으로도 안 잡힌다(`adopt_notion_shape`)
  - `skip` — 대상 아닌 docs 파일(README · next_rebuild)
- **하위 페이지를 지우지 않게**(모든 프로젝트): 맞추기가 child_page · child_database 블록을 보지도 지우지도 않는다. 펫퍼민트 18쪽은 「02. 파이프라인 설계」(pipeline.md)의 하위 페이지라, 전에는 pipeline.md를 맞출 때 18쪽이 휴지통으로 갈 수 있었다
- 짝 20개를 `doc_publish`에 등록(제목 · 부모 · url은 Notion에서 읽은 그대로, content_hash 비움). `docs`는 아직 `"off"` — 아무것도 돌지 않는다
- 20쪽 모두 git(origin/main `8e6da41`)에 있고 범위(펫퍼민트 root) 안, 2쪽은 [기술문서] 바로 아래, 18쪽은 pipeline 아래

## 모의 실행(쓰기를 막은 클라이언트, DB 기록 안 고침)

- 새 페이지 0 · 쓰기 0 · **20쪽 모두 HumanEdited(멈춤)**
- 원인 1 — 제목 단계가 체계적으로 하나씩 낮다: 같은 글의 제목이 우리 변환 heading_2 ↔ Notion heading_3 161건, heading_3 ↔ heading_4 173건, heading_1 ↔ heading_2 4건. 결정된 예외 두 가지에 없다
- 원인 2 — 글이 실제로 다른 블록: 변환 블록 1,826개 중 236개(13%)는 같은 글이 Notion에 없다(꾸밈은 빼고 견줌). 예: 16 「순서는 등록부 `app/services/code_rules.py`의 `RULES` 목록이…」 ↔ Notion 「…RULES가 정한다…」. 펫퍼민트 세션의 "차이 0"은 글 단위 검증이었다(그 세션도 그렇게 적었다)
- 그래서 켜지 않았다 — 켜면 20쪽이 다 멈추고 알림 20통, 덮는 것은 0

## 정할 것(사용자)

1. 제목 단계 차이를 세 번째 "Notion 모양 기준" 예외로 둘지(두면 단계만 다른 제목은 멈추지 않고 Notion 단계 그대로)
2. 글이 다른 236블록 — git에 옮길지(펫퍼민트 세션), Notion을 git으로 덮을지([Notion 수정 버리고 덮기]), 파일마다 정할지

## 확인

- 파이썬 491(새 `test_sync_never_deletes_subpages` · `test_adopt_notion_shape_inline_code_and_image`)
