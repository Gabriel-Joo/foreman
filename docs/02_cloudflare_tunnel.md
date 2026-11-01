# BRIEF 02 — 외부 노출: Cloudflare Tunnel + Access

FOREMAN을 `foreman.ronanlab.dev`로 외부에 낸다.
기존 `ollama-tunnel` · `runshoes-tunnel`과 같은 GPU 서버에 세 번째 터널을 추가하는 작업이다.

> **선행 조건**: 브리지가 서버 PC `localhost:8000`에서 정상 동작하고, SSH 포워딩으로 접속해 기능 확인이 끝난 상태여야 한다.
> 개발 중에는 이 작업을 하지 않는다. **로드맵 6단계 이후에 실행한다.**

---

## 0 / 읽을 것

노션 문서 두 개를 먼저 읽는다. 같은 서버의 기존 터널 설정이므로 패턴을 그대로 따른다.

- 프로젝트 / Cloudflare Tunnel 세팅
- 프로젝트 / Cloudflare Tunnel 세팅 (트러블슈팅 기록)

→ **원하는 동작**: 기존 두 터널의 디렉토리 분리 방식, systemd 유닛 작성 방식, Access Application 설정 절차를 파악한다. 새로 발명하지 말고 기존 방식을 재사용한다.

**확인 체크리스트**

- [ ] `cloudflared tunnel login`은 이미 되어 있으므로 다시 하지 않는다
- [ ] 기존 터널 2개의 config 디렉토리가 어떻게 분리돼 있는지 확인했다
- [ ] 트러블슈팅 문서의 Host 헤더 / 도메인 프런팅 이슈를 이해했다

---

## 1 / 순서 엄수

이 작업은 순서를 바꾸면 보안 사고가 난다.

→ **원하는 동작**: 아래 순서를 반드시 지킨다.

```
터널 생성 → DNS 라우트 → Access Application 생성 및 정책 적용
→ 정책 동작 확인 → 그 다음에 터널 실행 → systemd 등록
```

기존 ollama-tunnel 세팅 때는 터널을 먼저 띄우고 나중에 Access를 걸었다. 그 사이 엔드포인트가 무인증 상태였고, 당시엔 모델 목록 조회 수준이라 감수할 만했다.

FOREMAN은 다르다. 이 엔드포인트는 서버에 명령을 주입하고 터미널에 접근한다. **무인증 구간이 1초라도 있으면 안 된다.**

**확인 체크리스트**

- [ ] Access 정책이 적용된 것을 확인하기 전에는 터널을 실행하지 않았다
- [ ] systemd 등록은 정책 확인 이후에 했다

---

## 2 / 터널 생성

→ **원하는 동작**: `foreman-tunnel`을 만들고 `foreman.ronanlab.dev`에 연결한다.

| 항목 | 값 |
|---|---|
| 터널 이름 | `foreman-tunnel` |
| 호스트명 | `foreman.ronanlab.dev` |
| config 디렉토리 | `~/.cloudflared-foreman/` (기존 두 개와 분리) |
| origin | `http://localhost:8000` (브리지) |

`route dns` 후 CNAME이 다른 터널을 가리키는 경우가 있다. 트러블슈팅 문서에 적힌 대로 대시보드에서 Target을 직접 확인한다.

**확인 체크리스트**

- [ ] 기존 두 터널의 config 파일을 건드리지 않았다
- [ ] `credentials-file` 경로가 새 터널의 UUID를 가리킨다
- [ ] DNS 레코드의 Target이 `<foreman-tunnel UUID>.cfargotunnel.com`이다
- [ ] 아직 터널을 실행하지 않았다

---

## 3 / Access Application — 사람 인증

기존 ollama는 Service Token(앱이 호출)이었다. FOREMAN은 사람이 브라우저로 접속하므로 방식이 다르다.

→ **원하는 동작**: Self-hosted 애플리케이션을 만들고, 단일 이메일만 허용한다.

- Access controls → Applications → Add an application
- Self-hosted and private → **Public DNS** 탭 (ollama 때 쓴 Service auth가 아님)
- Destinations: Subdomain `foreman`, Domain `ronanlab.dev`
- Policy:
  - Include → Emails → 사용자 본인 이메일 **하나만**
  - Action: **Allow**
- 세션 기간은 기본값보다 짧게 설정하는 것을 검토한다

### ⛔ 절대 하지 말 것

펫퍼민트는 시연용이라 "로그인한 누구나"로 열었다. FOREMAN에 같은 정책을 쓰면 안 된다. 이 UI는 서버 PC에 명령을 주입하고 터미널 세션에 접근한다. **뚫리면 GPU 서버 전체가 넘어간다.**

- Include를 도메인 전체(`@gmail.com` 등)로 열지 않는다
- Bypass 정책을 쓰지 않는다
- 테스트 목적으로도 일시적으로 열지 않는다

**확인 체크리스트**

- [ ] Include에 개별 이메일 주소만 들어 있다
- [ ] Action이 Allow이고 Bypass가 없다
- [ ] 정책을 저장했고 애플리케이션이 활성 상태다

---

## 4 / 정책 검증 (터널 실행 전)

→ **원하는 동작**: 터널을 켜기 전에 Access가 실제로 막는지 확인한다.

- 인증 없이 `https://foreman.ronanlab.dev` 접근 → Cloudflare 로그인 페이지로 가야 한다
- `curl`로 직접 호출 → 차단되어야 한다
- 허용 이메일로 로그인 → 통과해야 한다 (이 시점엔 origin이 없으므로 502/404가 정상)

**확인 체크리스트**

- [ ] 무인증 접근이 차단되는 것을 실제로 확인했다
- [ ] 허용 이메일 로그인이 통과하는 것을 확인했다
- [ ] 502 또는 404가 뜨는 것은 정상임을 이해했다 (origin 미실행)

---

## 5 / 터널 실행 및 WebSocket 검증

→ **원하는 동작**: 터널을 테스트 실행하고, 특히 WebSocket 연결을 확인한다.

FOREMAN은 WebSocket이 핵심이다. HTTP가 되더라도 WS가 안 되면 쓸 수 없다.

확인할 것:

- HTTP 응답 정상
- WS 핸드셰이크 성공 — 브리지의 WebSocket 엔드포인트에 브라우저로 붙어본다
- Access 쿠키(`CF_Authorization`)가 WS 핸드셰이크에도 실리는지
- 런슈즈 챗봇과 동일하게 HTTPS 페이지에서는 `wss://`를 써야 한다

프론트의 WS URL은 런슈즈 `src/api.ts`와 같은 방식으로 프로토콜을 동적 결정한다.

**확인 체크리스트**

- [ ] 브라우저에서 WS 연결이 수립되고 메시지가 오간다
- [ ] 개발 콘솔에 mixed content 경고가 없다
- [ ] 끊었다 다시 붙였을 때 재연결이 된다

---

## 6 / systemd 등록

→ **원하는 동작**: 기존 두 유닛과 같은 형식으로 `cloudflared-foreman.service`를 만든다.

- 기존 `cloudflared-ollama.service`, `cloudflared-runshoes.service`와 동일한 구조
- `User=kopo17`, `Restart=on-failure`
- enable + start 후 상태 확인

**확인 체크리스트**

- [ ] 세 서비스 모두 `active (running)`이다
- [ ] 터미널을 닫아도 터널이 유지된다
- [ ] 재부팅 후에도 자동 기동되는지 확인했거나, 확인 방법을 적었다

---

## 7 / 브리지 자체 인증

Access는 Cloudflare 앞단에서만 막는다. 터널을 거치지 않고 서버 내부나 학교망에서 `localhost:8000`에 직접 붙는 경로는 막지 못한다.

→ **원하는 동작**: 브리지에 자체 토큰 인증을 둔다.

- 환경변수로 토큰을 주입한다
- 모든 API와 WS 연결에서 토큰을 검증한다
- 토큰은 git에 커밋하지 않는다 (k8s Secret 패턴을 참고하되, 브리지는 호스트 프로세스이므로 환경변수 파일로)

**확인 체크리스트**

- [ ] 토큰 없이 `localhost:8000`에 붙으면 거부된다
- [ ] 토큰 값이 코드·git·로그에 평문으로 남지 않는다
- [ ] 토큰을 바꿨을 때 적용되는 절차를 적었다

---

## 8 / 노션 기록

→ **원하는 동작**: 기존 터널 문서와 같은 수준으로 기록을 남긴다.

- 프로젝트 / Cloudflare Tunnel 세팅 문서에 세 번째 터널 항목을 추가하거나, 별도 문서로 작성
- ollama(Service Token)와 FOREMAN(사람 인증)의 차이를 명시
- 순서를 지켜야 하는 이유를 기록

**확인 체크리스트**

- [ ] 왜 Service Token이 아닌 사람 인증인지 적었다
- [ ] 겪은 문제가 있으면 트러블슈팅 문서에 추가했다

---

## 출력 형식

각 단계 수행 후 결과를 보고한다. **실행 전 계획을 먼저 제시하고 승인을 받는다.**

## 하지 말 것

- 1번의 순서를 임의로 바꾸기
- 테스트 목적으로 Access 정책을 느슨하게 열기
- 기존 두 터널의 설정 파일·systemd 유닛 수정
- 토큰·Client Secret을 출력하거나 파일에 평문으로 남기기
