# 서기 410 일감: 전체 대조 줄 1에서 남은 판단거리 셋 (11-20, foreman-4)

규칙 위반 없음

## 한 일

1. `notion/01_structure/01_placement.md` 다루는 곳에 `bridge/config.py`, `bridge/main.py`를 넣었다. 본문이 루프백 8000, 웹훅 귀(8001), ttyd 유닉스 소켓, 토큰, `debug_endpoints`(config.py)와 웹훅 귀 열기, `claude` 실행 파일 확인, 화면 파일 공개(main.py)를 설명한다.
2. `notion/09_dispatcher/02_note_wake.md` 다루는 곳에 `bridge/main.py`, `bridge/ingest_health.py`를 넣었다. 본문이 자동 기상이 켜지지 못해도 브리지가 뜨는 것, 뜰 때 `claude`를 못 찾으면 알리는 것(main.py), 기다리면 돌아오는 적재 막힘을 넘기지 않는 것(ingest_health.py)을 설명한다.
3. 머리 위 표시를 한 곳에 모았다.
   - 두 곳을 `render.js`의 `needMark`와 맞대 보았다. 차례(권한 거부, API 오류, 답 기다림, 사용자 답 기다림, 아직 안 본 물음, 합치기 기다림, 사용자에게 보고함, 보고 옴, 작업 세션 작은 두 표시)가 코드와 둘 다 같았다. 다른 점은 없었다.
   - `04_managers.md` 「머리 위 표시」의 표와 순서 글을 걷어 → 「픽셀 오피스와 테마」를 가리키는 한 줄로 줄였다.
   - 순서 글에만 있던 내용(권한 거부와 API 오류가 작업 세션에 그대로 뜨는 까닭, 작은 글씨와 회색 점, 보고가 이김)은 지우지 않고 `02_office.md` 표 아래로 옮겼다. 보고가 이기는 까닭은 04에 남겼다.
   - `02_office.md` 다루는 곳에 `bridge/static/js/render.js`를 넣었다.

## 읽은 커밋

네 편 모두 올리지 않았다. 해당 대목만 코드와 맞대 읽었고 편 전체를 읽지 않았다. 기술문서 전체 줄에서 다시 읽는다.

## 점검

`tools/docs.py check`, `pytest`는 아래 보고에 적는다.
