# 끝내기가 CC의 다른 화면(/usage 등)에 막힌 건 — Esc로 닫고 /exit (11-08)

`log/ui_input_overlay_20261108.md`의 짝이다. 입력은 거부하도록 고쳤지만, 끝내기도 같은 이유(입력 줄 ❯ 없음)로 안 됐다(세션 210, 사용자가 [끝내기]를 눌렀는데 안 끝남).

## 고친 것

- `bridge/handoff.py` 끝내기(`act == "exit"`): 입력 줄이 안 보이면 Esc를 최대 3번(0.6초 간격) 보내고 `/exit`를 보낸다. 작업 중이 아닐 때만 여기 오므로 Esc가 작업을 끊지 않는다. 그래도 입력 줄이 안 돌아오면 `deliver()`가 입력 거부 사유로 막는다 — 말없이 실패하지 않는다
- **앞 세션이 쓴 고침에 버그가 있었다**: `prompt_showing`을 `bridge.inject`에서 가져오지 않아, 그대로 띄웠으면 끝내기마다 `NameError`가 났다. 가져오기 줄에 넣었다

## 실제 확인

- 세션 210은 이 세션이 시작할 때 이미 끝나 있었다(`cc-foreman`에 셸만 남음, `claude --resume ad5179ab…` 안내) → 시험 세션으로 같은 상황을 만들었다
- 브리지 재기동(승인 대기 0건 확인 후, 새 PID 562154) → `/api/spawn`으로 Haiku 세션 213(`cc-foreman-4`) → `/usage`를 쳐서 ❯ 0개 확인 → `/api/sessions/213/action {"action":"exit"}` → `{"ok":true,"tmux_closed":true}`, CC 프로세스 · tmux 창 사라짐. 모델 호출은 없었다
- 213은 `hidden_reason='test'`로 숨겼다
- `pytest -k "handoff or exit or inject"` 30 통과(끝내기 Esc 경로 자체의 단위 시험은 없다 — 실제 확인으로 대신)

## 이 서버에서 알아둘 것

- 이 CC 세션 셸에서 `systemctl --user`가 `Process org.freedesktop.systemd1 exited with status 1`로 실패했다. 세션 환경의 `DBUS_SESSION_BUS_ADDRESS`가 VNC 쪽 `/tmp/dbus-…`를 가리키고 `XDG_RUNTIME_DIR`가 비어 있어서다. `XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`를 붙이면 된다
- `/usage` 화면 머리에 "Your login expires in 1 day · run /login to renew"가 떠 있었다(11-08 09:2x)
