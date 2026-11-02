# FOREMAN 8단계 — Harbor 프로젝트(runshoes · petmint)에 웹훅 정책 "foreman"을 만들거나 고친다.
# m-k8s에서 돈다: scripts/cicd-apply.sh harbor 가 맨 앞에 TOKEN = "…" 한 줄을 붙여 표준 입력으로 보낸다.
# admin 비밀번호는 Secret harbor/harbor-core(HARBOR_ADMIN_PASSWORD)에서 이 프로세스 안으로만 읽는다(화면 · 명령줄에 안 나온다).
# Harbor는 ingress VIP(192.168.122.240)에 Host 헤더로 http로 부른다(ssl-redirect false — platform/harbor/values.yaml).
import base64
import json
import subprocess
import urllib.error
import urllib.request

TOKEN = globals().get("TOKEN")  # noqa: F821 — 첫 줄이 넣는다
assert TOKEN and len(TOKEN) >= 32, "TOKEN 없음"
VIP, HOST = "http://192.168.122.240", "harbor.ronanlab.dev"
ENDPOINT = "http://192.168.122.1:8001/webhooks/harbor"
PROJECTS = ["runshoes", "petmint"]
EVENTS = ["PUSH_ARTIFACT", "SCANNING_FAILED", "QUOTA_EXCEED"]

pw = base64.b64decode(subprocess.check_output(
    ["kubectl", "-n", "harbor", "get", "secret", "harbor-core", "-o", "jsonpath={.data.HARBOR_ADMIN_PASSWORD}"])).decode()
AUTH = "Basic " + base64.b64encode(f"admin:{pw}".encode()).decode()
del pw


def call(method, path, body=None):
    req = urllib.request.Request(VIP + "/api/v2.0" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Host": HOST, "Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300]


for proj in PROJECTS:
    policy = {"name": "foreman", "description": "FOREMAN 인과 체인(8단계) — 이미지 push를 FOREMAN 브리지로",
              "enabled": True, "event_types": EVENTS,
              "targets": [{"type": "http", "address": ENDPOINT, "auth_header": "Bearer " + TOKEN,
                           "skip_cert_verify": True, "payload_format": "Default"}]}
    st, cur = call("GET", f"/projects/{proj}/webhook/policies")
    if st != 200:
        print(f"{proj}: 정책 목록 실패 HTTP {st}")
        continue
    old = next((p for p in cur or [] if p.get("name") == "foreman"), None)
    if old:
        st, out = call("PUT", f"/projects/{proj}/webhook/policies/{old['id']}", {**policy, "id": old["id"]})
        print(f"{proj}: 고침 HTTP {st}")
    else:
        st, out = call("POST", f"/projects/{proj}/webhook/policies", policy)
        print(f"{proj}: 만듦 HTTP {st}")
    if st >= 300:
        print("  ", out if isinstance(out, str) else "")
