# 서기 일감: 원고 세 곳 고치기 (11-17)

## 한 일

1. 노션 원고 `notion/00_foreman.md` 6절 끝 문장: 인프라를 지켜보기의 예로 든 것을 사용자가 고른 문장으로 바꾸고, 인프라가 11-17에 묻기(enforce)로 올라간 사실을 같은 문단에 이어 적었다 [code:config/approval.toml] [c:12c07f6].
   - 함께 맞춘 곳(인프라를 observe로 적은 문장): `notion/04_approval.md`의 「프로젝트마다 observe와 enforce」 현재 값 줄과 인프라 설명 줄, `notion/04_approval/01_rules.md` 모드 문단, `notion/05_roles/02_guards.md` 승인 모드 문단
2. `notion/15_db.md`: 「이 편을 쓸 때」 세 곳(요약 표, 7절 보관 문단, 8절 백업 문단)에 `(11-15)`만 붙였다. 숫자는 그대로.
3. `portfolio/15_telegram.md` 머리 주석 「다루는 곳」 끝에 `scripts/foreman-bridge-alert.sh`, `deploy/systemd/foreman-bridge.service`를 더했다. 「읽은 커밋」은 그대로.

## 시험

`.venv/bin/python -m pytest -q`: 1241 passed.

## 규칙 위반 없음
