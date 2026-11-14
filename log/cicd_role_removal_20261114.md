# 세션 역할 cicd 빼기 (11-14, foreman-2)

사용자 지시(11-14): 「한 번도 안 썼고 앞으로도 쓸 일이 없다. 빌드와 배포는 브리지가 기계적으로 한다」

## 운영 DB에서 읽기만으로 센 값

| 칸 | cicd 줄 수 |
|---|---|
| `character_session.role` | 0 |
| `character.current_role` | 0 |
| `character.spawned_by` | 0 |
| `character.name` 에 「CI/CD」 | 0 |

참고로 세션 역할 분포는 coder 176 · scribe 39 · designer 24 · manager 10 · inspector 7 · helper 1. 그래서 멈추지 않고 진행했다.

## 뺀 곳

| 파일 | 뺀 것 |
|---|---|
| `bridge/models.py` | `Role.CICD` |
| `bridge/api/handoff.py` | `SessionRole` 의 cicd |
| `bridge/foreman.py` | `ROLES`, 계획 프롬프트의 역할 설명, `ROLE_KO` |
| `bridge/handoff.py` · `bridge/wake.py` | `ROLE_KO` 의 cicd |
| `config/models.toml` | `[defaults]` 의 `cicd = "sonnet"` |
| `bridge/static/js/render.js` | `ROLE_LABEL` · `SESSION_ROLES` · `ROLE_COLOR` |
| `bridge/static/js/modelpick.js` | `ROLE_PICK` |
| `bridge/static/js/office.js` | 주석의 역할 목록 |
| `bridge/static/themes/{office,magic,site,plain}/theme.json` | `roles.colors` 의 cicd 색(세션 역할 색이다. 출하 라인 · 배송 담당 그림에는 쓰이지 않는다. `courier`는 다른 칸) |
| `bridge/static/demo/stills.json` | 녹화된 모델 기본값의 cicd |
| 시험 | `tests/test_model_choice.py`(cicd 대신 scribe로 같은 동작 확인), `tests/js/theme.test.mjs`, `role_label.test.mjs`, `coder.test.mjs`(helper로 바꿈) |
| docs | README 2.3절(11-14 줄 추가) · 외형 설명 · 데이터 모델 표(`current_role` · `spawned_by`), `docs/11_foreman_dispatch.md` 계획 모양, `docs/12_scribe.md` 9줄, `docs/10_office_design.md` 148줄 |

## 남긴 것과 까닭

- 마이그레이션 0001 · 0017 의 주석 · 조건: 이미 적용된 기록이라 고치지 않았다. 새 마이그레이션도 만들지 않았다(칸은 VARCHAR)
- 파이프라인 구역(`bridge/pipeline.py`, Jenkins · ArgoCD 웹훅), 출하 라인 「배송 담당」(`courier`), `config/pipeline.toml` · `portfolio.toml` · `bridge/config.py` 의 `stage8_cicd_result.md` 참조: 세션 역할이 아니다
- README 의 포먼 일 설명(「CI/CD 결과 수신 후 후속 조치 판단」), 3.6절, 로드맵 표: 파이프라인 이야기라 그대로
- 모르는 역할이 오면: 이미 `SessionRole`(Literal)이 API에서 거부하고, `ROLE_KO.get` · `ROLE_LABEL[r] || null` 꼴로 읽어 지난 데이터에 cicd가 있어도 읽기가 깨지지 않는다(운영 DB에는 0줄)

## `docs/operations.md` · `docs/style_guide.md` 에 바꿀 줄

- 없음. `operations.md` 85줄의 「CI/CD」는 배포 · 시험 방식 이야기라 세션 역할과 무관하다

## 시험

- pytest 955 통과, `node --test tests/js/` 172 통과

## 규칙 위반

규칙 위반 없음
