# foreman-5 GIF 바뀐 곳만 담기와 README 머리글 덮기 검사 제외 (11-19)

관리자 410의 코더 일감, 작은 일 둘. 브랜치 `cc/foreman-5`.

## 1. GIF 바뀐 곳만 담기

한 일
- `tools/frames_to_gif.py`에 `--delta`와 `--delta-threshold N`(기본 120)을 더했다. 변환 부분은 `build_frames()`로 떼어 시험이 직접 부를 수 있게 했다. 옵션이 없으면 전과 같은 길을 탄다(같은 프레임 묶기, `optimize=True`, 투명 없음)
- `--delta`: 보이는 화면(앞 장들까지 그린 결과)과 새 프레임의 R, G, B 차의 합이 문턱 아래인 점을 투명(팔레트 255번)으로 두고, 문턱 이상 다른 점만 담는다. 바뀐 점이 하나도 없으면 앞 장의 머무는 시간만 늘린다. 팔레트는 지금처럼 여러 장에서 한 번 뽑는다. 투명 칸을 비우려고 색은 최대 255로 줄인다
- `tools/screen.py --record`에 같은 이름의 `--delta`, `--delta-threshold`를 더해 변환 도구에 넘긴다
- 시험 `tests/test_frames_to_gif.py`(도우미 `tests/data/gif_probe.py`): 옵션이 없을 때 전과 같은가, 문턱 120에서 작은 변화는 묶이고 바뀐 점만 담기는가(255칸 투명), 문턱 24와 300에서 결과가 달라지는가. 시스템 `python3`에 PIL이 없으면 건너뛴다
- 문서: `docs/13_demo_capture.md` 「녹화」 절 GIF 줄 바로 아래에 `--delta` 줄을 더했다

설계와 다르게 한 것, 판단 근거
- 디자이너 573의 스크래치 스크립트(`gifdelta.py`)는 읽지 못했다(log 6절 글만 읽음). 그 글의 설명(앞 장과 거의 같은 점을 투명, 문턱 120과 24, 팔레트 한 번)대로 새로 짰다. 같은 결과가 나오는지는 실제 마법학교 프레임으로 견주지 않았다
- 앞 장 원본이 아니라 보이는 화면과 견준다. 원본끼리 견주면 작은 변화가 장마다 쌓여도 문턱을 못 넘어 화면이 조금씩 어긋나기 때문이다(이 선택은 내가 했고 573의 스크립트도 그런지는 모른다)
- `--delta`에서는 `optimize`를 껐다. 팔레트를 다시 정렬하면 투명 칸 번호가 어긋날 수 있어서다. 켠 채 시험하지는 않았다
- 문턱은 세 색 차의 합을 255에서 잘라 쓰므로 255를 넘는 값은 「아무것도 안 바뀐 것」과 같다(`--help`와 docs에 적었다)

못 한 것
- 실제 마법학교 프레임으로 크기를 재지 않았다. 「한 장 200KB 아래」가 이 도구로 나오는지는 확인하지 못했다
- `docs/style_guide.md`에는 「FOREMAN 찍는 법」 절이 이 브랜치에 없어서 건드리지 않았다(아래 사람이 정할 것)

## 2. README 머리글 파일을 덮기 검사에서 저절로 빼기

한 일
- `bridge/doctext/check.py` 덮기 검사: `[readme]` 표가 켜져 있으면 `readme.GENERATED`와 함께 `[readme] header_file` 값도 대상에서 뺀다. 저장소가 `not_code`에 적을 필요가 없다. 표가 없으면 header_file이 있어도 빼지 않는다(표 없이는 쓰이지 않는 칸이라서)
- 시험 `tests/test_docs_check.py` `test_cover_skips_readme_header_file`: header_file을 안 적으면 그 `.md`가 「덮기 밖」으로 나오고, 적으면 빠지며, 다른 `.md`는 그대로 나온다
- `docs/12_scribe.md` 설정 칸 줄 두 곳(덮기 검사 설명, 머리글 설명)을 맞췄다

바뀌지 않은 것(코드를 건드리지 않았다)
- 근거 표시 검사: 머리글 파일은 원고 묶음 밖 글이라 본래 근거 표시 검사 대상이 아니다. 그대로다
- 줄표 검사(8번): 머리글은 README에 그대로 들어가 README 새 줄로 점검 8번을 받는다. 그대로다. 원본에서 고친다
- 거꾸로 찾기: 머리글 파일이 `.md`면 바뀔 때 `doc`으로 센다. 그대로다
- 머리글 파일은 `readme.GENERATED`에 넣지 않았다(사람이 쓰는 원본이라 `docs.py readme`가 쓰는 파일이 아니다)

## 점검 결과

줄표 고침과 덧붙임을 모두 마친 뒤 다시 돌렸다.
- `.venv/bin/python -m pytest -q`: 1478 통과(195초)
- `node --test tests/js/`: 244 통과, 실패 0
- `tools/docs.py check`: 틀린 것 0(처음에는 내 새 줄의 em dash 3건이 걸려 고쳤다)
- `tools/docs.py readme --dry`: README 차이 없음
- 거꾸로 찾기(`refs`): `check.py`, `screen.py`를 가리키는 노션 원고 세 곳(`notion/10_scribe/04_notion.md` 279줄, `notion/14_screen/01_store.md` 260줄, `notion/16_tests.md` 87줄)이 걸렸고, 모두 이번 바뀜과 맞는 문단이라 고치지 않았다. 덮기 검사 제외나 `--delta` 옵션을 다루는 문단이 아니다
- 실제 마법학교 프레임으로 GIF를 만들어 보지 않았다(위 「못 한 것」)

## 덧붙임: 덮기 밖 둘 (관리자 410 요청)

합치기 카드 문서 점검에서 「덮기 밖」 둘(`tests/data/gif_probe.py`, `tests/test_frames_to_gif.py`)이 나왔다. 내 처음 점검은 새 파일을 add하기 전에 돌려 이 둘을 놓쳤다.
- `notion/14_screen/05_check.md` 머리 「다루는 곳」에 두 파일을 더했다(`tools/frames_to_gif.py` 3-3절을 다루는 편이고 `tools/`는 이미 덮고 있었다)
- 같은 편 3-3절에 `--delta`를 설명하는 문단을 더했다(거꾸로 찾기가 이 줄을 걸었다). 크기는 재 보지 않아 숫자는 쓰지 않았다
- 다시 돌린 것: `tools/docs.py check` 틀린 것 0, 문서 점검과 GIF 시험 27개 통과. 전체 pytest는 이 덧붙임 전에 한 번 돌렸고 바뀐 것은 원고 한 편이라 다시 돌리지 않았다

## 규칙 위반

규칙 위반 있음. 둘, 둘 다 바로잡았다.
1. 11-19, 시험 파일 `tests/test_docs_check.py`의 경로 이름을 고치려고 Bash `sed -i`를 썼다(Edit로 했어야 한다). 바꾼 것은 시험 안의 `.foreman/`을 `top/`으로 한 줄 치환이었고, 결과는 시험 통과로 확인했다. 되돌리지 않았다(내용이 맞다)
2. 11-19, 시험이 왜 실패하는지 보려고 scratchpad에 빈 파일을 heredoc(`cat >`)으로 만들었다. 쓸모가 없어 바로 지웠다. 저장소 파일이 아니다

## 사람이 정할 것

- `docs/style_guide.md` 「FOREMAN 찍는 법」 절은 이 브랜치에 없다. 디자이너 573 브랜치(`cc/foreman-4`)가 합쳐진 뒤 그 절의 GIF 줄이 `--delta`를 가리키게 해야 한다(사람 승인 경로라 이 브랜치에서는 안 고쳤다). 지금 style_guide 57줄에는 GIF를 `tools/screen.py --record`로 찍는다는 말만 있다
- 마법학교 GIF를 이 도구로 다시 만들어 크기를 재 볼지(573의 결과와 견주기)
