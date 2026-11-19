# CLAUDE.md의 README 「나중에 할 일」 가리킴 고치기 (foreman-4, 11-19)

- 시작한 main 커밋: `c2457ab`
- 규칙 위반: 없음

## 한 일

- `CLAUDE.md` 관리자 예외 2: 「README 「나중에 할 일」 줄」을 「`docs/TODO.md` 줄(README는 생성물이라 할 일 절이 없다, 11-19 사용자)」로 고쳤다
- `notion/05_roles/01_roles.md` 같은 뜻의 줄을 「`docs/TODO.md`의 할 일 줄」로 고치고 머리 「읽은 커밋」을 `c2457ab`로 올렸다

## 조사 결과

- `CLAUDE.md` 45줄 「GitHub Actions 시험은 정해 두고 아직 안 만듦 — README 「나중에 할 일」」: `docs/TODO.md`에 그 할 일이 없다. CI, Actions, github 낱말로 찾은 항목은 foreman-7(CI/CD 체인 시작 실패), foreman-129(문서 점검을 pytest에 걸기, 다른 일), 468줄 설치 스크립트 항목뿐이다. 그래서 **고치지 않았다.** 「TODO에 없음」
- `CLAUDE.md` 44줄 「안 부르면 브리지 그물이 「확인 전」으로만 올린다」: `bridge/postit.py` `sweep`(미루자고 했는데 포스트잇이 없는 턴을 `confirmed` 0으로 올림), `add`(그물 줄을 관리자가 같은 턴으로 올리면 확인된 줄로 바꿈)와 맞다. 고치지 않았다. 같은 줄의 「나중에 할 일에 넣어라」는 사람이 하는 말이라 그대로 두었다
- 그 밖에 없어진 절을 가리키는 줄: 없다. 27줄 「`log/` 기록 · README 반영은 사용자가 시킬 때」는 절을 가리키지 않고 README 반영이라는 일을 말하므로 일감 밖이라 두었다(README가 생성물이라 낡았다고 볼 수도 있어 아래에 올린다)

## 사람이 정할 것

- 45줄의 GitHub Actions 시험이 `docs/TODO.md`에 없다. 항목으로 올릴지(관리자가 사용자에게 묻는다), 줄에서 「정해 두고 아직 안 만듦」 말을 뺄지 정한다
- 27줄의 「README 반영」을 지금 꼴에 맞게 고칠지(CLAUDE.md 정리 때)
