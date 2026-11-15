"""붙여넣기 전 화면 가르기(11-13) — 입력 칸과 고르기 · 안내 창을 가른다(bridge/inject.screen_state).

화면 글은 CC 2.1.323을 tmux capture-pane으로 뜬 것을 줄였다(가로줄 · 테두리 길이, 긴 줄 끝). log/prompt_vs_dialog_20261113.md
"""

import pytest

import bridge.inject as inj

SID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
R = "─" * 120
B = "▔" * 120
HEAD = (" ▐▛███▛█   Claude Code v2.1.323\n▝▜██████▀  Sonnet 5.5 · Claude Max\n\n"
        "❯ /model\n  ⎿  Kept model as Sonnet 5.5\n\n❯ say ok only\n\n● ok\n\n✻ Churned for 2s · done 9:14 PM\n")

PROMPT = HEAD + f"\n{R}\n❯ \n{R}\n  ⏵⏵ auto mode on (shift+tab to cycle) · ← 1 agent\n"
PROMPT_DRAFT = HEAD + f"\n{R}\n❯ 첫 줄\n  둘째 줄\n{R}\n  ⏸ manual mode on · ? for shortcuts\n"

MODEL = HEAD + f"""{B}
   Select model
   Switch between Claude models. Your pick becomes the default for new sessions.

     1.  Default (recommended)  Opus 5.5 · Best for everyday, complex tasks
     2.  Opus 5.5               For complex work and everyday tasks
     3.  Fable 5.2              For your toughest challenges
   ❯ 4.  Sonnet 5.5 ✔           Most efficient for simpler tasks
     5.  Haiku 5.5              Fastest for quick answers

   Enter to set as default · s to use this session only · Esc to cancel
"""

CONFIG = "  ⎿  Kept model as Sonnet 5.5\n" + B[:-20] + """ ◐ medium · /effort ▔
   Settings  Status   Config   Usage   Stats

   ╭──────────────────────────────╮
   │ ⌕ Search settings…           │
   ╰──────────────────────────────╯
   ❯ Auto-compact                                    true
     Idle compaction                                 true
     ↓ 22 more

   Type to filter · Enter/↓ to select · ↑ to tabs · Esc to clear
"""

USAGE = "  ⎿  Kept model as Sonnet 5.5\n" + B + """
   Settings  Status   Config   Usage   Stats

   Session
   Total cost:            $0.0609
   Current session
   ██████████████████▌                                37% used
   11%  See what fills your context · run /context
"""

AUTOCOMPACT_CMD = HEAD + f"""{B}
   Auto-compact window

   Current setting for Sonnet 5.5: 1m tokens (default for this model)
   Select auto-compact window: auto

   ←/→ to adjust · Enter to apply · Esc to cancel
"""

TRUST = f"""{R}
 Accessing workspace:

 /tmp/scratchpad/dlgtest

 Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open source
 project, or work from your team). If not, take a moment to review what's in this folder first.

 ❯ No, exit
   Yes, I trust this folder

 Enter to confirm · Esc to cancel
"""

PERMISSION = HEAD + f"""
❯ Use the Bash tool to run exactly: touch probe.txt

● Creating empty probe.txt file
  ⎿  $ touch probe.txt

{R}
 Bash command

 Create empty probe.txt file
{"╌" * 120}
 touch probe.txt
{"╌" * 120}
 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and always allow access to /tmp/scratchpad/dlgtest from this project
   3. Yes, and switch to auto mode · auto mode handles these prompts for you
   4. No

 Esc to cancel · Tab to amend
"""

HELD = HEAD + f"""{R}
 Held message from another session — from uds:/tmp/cc-socks/1.sock [verified pid 1337218] (peer claims name: foreman-bridge)

 ❯ Deny
   Deliver this message to Claude

 Enter to confirm · Esc to cancel
"""

EXIT_CONFIRM = HEAD + f"""{B}
   Background work is running
   The following will stop when you exit:
   · Bash — npm run dev

   ❯ Exit anyway
     Stay

   Enter to confirm · Esc to cancel
"""

# 11-13 서기 세션에 뜬 자동 압축 권유 창 — 글은 관리자가 옮긴 것과 CC 코드(제목 Out · 안내 줄 Nut)에서. 테두리 꼴은 못 봤다
OFFER_BODY = """   We recommend compacting earlier

   Long conversations cost more and get less accurate. …

   ❯ Keep auto (1m tokens)
     Autocompact at ‹ 400k › tokens

   ↑/↓ choose · ←/→ change size · enter confirm · esc not now
"""
OFFER_BORDER = HEAD + B + "\n" + OFFER_BODY
OFFER_RULE = HEAD + R + "\n" + OFFER_BODY
OFFER_ABOVE_BOX = HEAD + OFFER_BODY + f"\n{R}\n❯ \n{R}\n  ⏵⏵ auto mode on\n"

UNKNOWN = HEAD + f"""{B}
   Something new

   ❯ Option A
     Option B

   Enter to pick · Esc to go back
"""


def old_prompt_showing(screen: str) -> bool:
    """11-13 전의 판단 — `❯`로 시작하는 줄이 하나라도 있으면 입력 줄."""
    return any(ln.lstrip().startswith("❯") for ln in screen.splitlines())


@pytest.mark.parametrize("screen,want", [
    (PROMPT, ("prompt", None)),
    (PROMPT_DRAFT, ("prompt", None)),
    (MODEL, ("dismiss", "모델 고르기(/model)")),
    (CONFIG, ("dismiss", "설정(/config · /usage · /status)")),
    (USAGE, ("dismiss", "설정(/config · /usage · /status)")),
    (AUTOCOMPACT_CMD, ("dismiss", "자동 압축 설정(/autocompact)")),
    (OFFER_BORDER, ("dismiss", "자동 압축 권유")),
    (OFFER_RULE, ("dismiss", "자동 압축 권유")),
    (OFFER_ABOVE_BOX, ("dismiss", "자동 압축 권유")),
    (TRUST, ("decision", "폴더 신뢰 확인")),
    (PERMISSION, ("decision", "도구 권한 묻기")),
    (HELD, ("decision", "보류된 세션 메시지 승인")),
    (EXIT_CONFIRM, ("decision", "끝내기 확인")),
    (UNKNOWN, ("unknown", None)),
])
def test_screen_state(screen, want):
    assert inj.screen_state(screen) == want


def test_old_rule_mistook_dialogs_for_prompt():
    """출발점 재현: 예전 판단은 대화가 있는 세션의 창을 모두 입력 줄로 봤다 — 지난 사용자 글(0칸 ❯)과 고르기 줄(들여 쓴 ❯) 때문.
    오늘의 권유 창도 그 길로 붙여넣기 · Enter를 받았다(Enter = 고른 「Keep auto」로 확정)."""
    for s in (MODEL, CONFIG, AUTOCOMPACT_CMD, OFFER_BORDER, OFFER_RULE, TRUST, PERMISSION, HELD, EXIT_CONFIRM):
        assert old_prompt_showing(s) is True
        assert inj.screen_state(s)[0] != "prompt"


def test_history_prompt_lines_are_not_the_box():
    """대화 영역의 지난 사용자 글(❯ /model)은 위가 가로줄이 아니라 입력 칸이 아니다."""
    assert inj._prompt_box(HEAD.splitlines()) is None


def _screens(monkeypatch, seq, *, busy=False):
    """capture-pane이 Esc 수에 따라 seq[Esc 수] 화면을 돌려준다(끝을 넘으면 마지막). 보낸 tmux 명령을 모은다."""
    t = inj.Target("/s", "%8", 1, SID)
    sent: list[tuple] = []

    async def fake_resolve(session_id, sessions_dir):
        return t, None, busy

    async def fake_tmux(socket, *args, **kw):
        if args[0] == "capture-pane":
            n = sum(1 for a in sent if a[-1] == "Escape")
            return seq[min(n, len(seq) - 1)]
        sent.append(args)
        return ""
    monkeypatch.setattr(inj, "resolve", fake_resolve)
    monkeypatch.setattr(inj, "tmux", fake_tmux)
    monkeypatch.setattr(inj, "ESC_WAIT_S", 0)
    return sent


def _kinds(sent):
    return [a[0] if a[0] != "send-keys" else a[-1] for a in sent]


async def test_offer_closed_with_esc_then_sent(monkeypatch):
    """오늘의 자동 압축 권유 창 — Esc(= 지금은 아님)로 닫고 입력 칸이 돌아온 뒤 넣는다. 결과에 창 이름."""
    sent = _screens(monkeypatch, [OFFER_BORDER, PROMPT])
    out = await inj.deliver(SID, "/exit", sessions_dir="/s", transcript=None, command=True)
    assert out["esc"] == 1 and out["dialog"] == "자동 압축 권유"
    assert _kinds(sent) == ["Escape", "load-buffer", "paste-buffer", "Enter"]


async def test_config_needs_two_escapes(monkeypatch):
    """/config은 첫 Esc가 검색만 지운다(실측) — 같은 창이 남아 있으면 한 번 더."""
    sent = _screens(monkeypatch, [CONFIG, CONFIG, PROMPT])
    out = await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
    assert out["esc"] == 2 and out["dialog"] == "설정(/config · /usage · /status)"
    assert _kinds(sent)[:3] == ["Escape", "Escape", "load-buffer"]


@pytest.mark.parametrize("screen,name", [(TRUST, "폴더 신뢰 확인"), (PERMISSION, "도구 권한 묻기"),
                                         (HELD, "보류된 세션 메시지 승인"), (EXIT_CONFIRM, "끝내기 확인")])
async def test_decision_dialog_refused_without_esc(monkeypatch, screen, name):
    """Esc가 결정이 되는 창 — Esc도 글도 보내지 않고 창 이름과 함께 거부."""
    sent = _screens(monkeypatch, [screen])
    with pytest.raises(inj.Refused, match=f"{name} 창이 떠 있어 넣지 못했습니다.*대화창에서 확인"):
        await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
    assert sent == []


async def test_unknown_dialog_refused_without_esc(monkeypatch):
    sent = _screens(monkeypatch, [UNKNOWN])
    with pytest.raises(inj.Refused, match="알 수 없는 창이 떠 있어 넣지 못했습니다"):
        await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
    assert sent == []


async def test_esc_reveals_decision_dialog_stops(monkeypatch):
    """Esc로 닫았더니 그 밑에 결정 창이 있었다 — 더 보내지 않는다."""
    sent = _screens(monkeypatch, [MODEL, PERMISSION])
    with pytest.raises(inj.Refused, match="도구 권한 묻기 창이 떠 있어"):
        await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
    assert _kinds(sent) == ["Escape"]


async def test_busy_with_dialog_no_esc(monkeypatch):
    sent = _screens(monkeypatch, [PERMISSION], busy=True)
    with pytest.raises(inj.Refused, match="도구 권한 묻기 창이 떠 있습니다. 작업 중이라 Esc를 보내지 않았습니다"):
        await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
    assert sent == []


async def test_left_in_box_reads_only_the_box(monkeypatch):
    """보낸 글이 대화 영역(지난 글)에만 있고 입력 칸이 비었으면 남은 게 아니다."""
    t = inj.Target("/s", "%1", 1, SID)

    async def fake_tmux(socket, *args, **kw):
        return HEAD + f"\n❯ 이미 들어가 있던 발볼 120켤레를 검증해라.\n\n{R}\n❯ \n{R}\n  ⏵⏵ auto mode on\n"
    monkeypatch.setattr(inj, "tmux", fake_tmux)
    assert await inj.left_in_box(t, "이미 들어가 있던 발볼 120켤레를 검증해라.") is False


# ── 입력 칸에 사람이 치던 글(11-14) — CC 화면 탭에서 사람이 반쯤 친 사이 브리지가 넣으면 두 글이 섞여 함께 제출된다 ──
G, E, DIM, INV = "\x1b[38;5;244m", "\x1b[39m", "\x1b[2m", "\x1b[7m"
NB = " "
# 실측 꼴(11-14 capture-pane -e): 가로줄은 회색, 빈 입력 칸은 「❯」 + NBSP(커서 칸)
PROMPT_EMPTY_COLOR = HEAD + f"\n{G}{R}\n{E}❯{NB}\n{G}{R}\n{E}  ⏵⏵ auto mode on\n"
PROMPT_TYPED_COLOR = HEAD + f"\n{G}{R}\n{E}❯ 이거 고쳐 줘 반쯤{INV} \x1b[27m\n{G}{R}\n{E}  ⏵⏵ auto mode on\n"
PROMPT_HINT_COLOR = HEAD + f'\n{G}{R}\n{E}❯ {INV}T\x1b[27m{DIM}ry "fix lint errors"\x1b[22m\n{G}{R}\n{E}  ⏵⏵ auto mode on\n'
PROMPT_GREY_HINT = HEAD + f"\n{G}{R}\n{E}❯ {G}press up to edit queued messages{E}\n{G}{R}\n{E}  ⏵⏵ auto mode on\n"


@pytest.mark.parametrize("screen,want", [
    (PROMPT, ""), (PROMPT_EMPTY_COLOR, ""), (PROMPT_HINT_COLOR, ""), (PROMPT_GREY_HINT, ""),
    (PROMPT_DRAFT, "첫 줄\n둘째 줄"), (PROMPT_TYPED_COLOR, "이거 고쳐 줘 반쯤"),
    (MODEL, ""), (HEAD, ""),
])
def test_typed_in_box(screen, want):
    assert inj.typed_in_box(screen) == want


def test_color_screen_still_reads_as_prompt():
    """색 포함 화면도 색을 벗기면 같은 판정(screen_state는 색 없는 글로 잰다)."""
    for s in (PROMPT_EMPTY_COLOR, PROMPT_TYPED_COLOR, PROMPT_HINT_COLOR):
        assert inj.screen_state(inj.plain(s)) == ("prompt", None)


@pytest.mark.parametrize("busy", [False, True])
async def test_typed_box_refused_nothing_sent(monkeypatch, busy):
    """입력 칸에 사람이 치던 글 — 일하는 중이든 아니든 붙여넣기 · Enter · Esc 어느 것도 보내지 않고 까닭을 돌려준다.
    11-14 전에는 거르지 않았다: screen_state가 「prompt」면 바로 붙여넣었다(PROMPT_DRAFT도 prompt)."""
    sent = _screens(monkeypatch, [PROMPT_TYPED_COLOR], busy=busy)
    with pytest.raises(inj.Refused, match="입력 칸에 사람이 치던 글이 있어 넣지 않았습니다. .*대화창"):
        await inj.deliver(SID, "관리자 중계 글", sessions_dir="/s", transcript=None)
    assert sent == []
    sent = _screens(monkeypatch, [PROMPT_DRAFT], busy=busy)
    with pytest.raises(inj.Refused, match="사람이 치던 글"):
        await inj.deliver(SID, "합치기 결과", sessions_dir="/s", transcript=None)
    assert sent == []


async def test_hint_text_is_not_typed(monkeypatch):
    """흐린 안내 · 제안 글만 있는 빈 칸에는 넣는다(거절하면 아무 때나 못 넣는다)."""
    for scr in (PROMPT_EMPTY_COLOR, PROMPT_HINT_COLOR, PROMPT_GREY_HINT):
        sent = _screens(monkeypatch, [scr])
        await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
        assert _kinds(sent) == ["load-buffer", "paste-buffer", "Enter"]


async def test_esc_closed_dialog_then_typed_box_refused(monkeypatch):
    """Esc로 안내 창을 닫았더니 입력 칸에 친 글이 있었다 — 넣지 않는다(닫은 Esc만 갔다)."""
    sent = _screens(monkeypatch, [MODEL, PROMPT_TYPED_COLOR])
    with pytest.raises(inj.Refused, match="사람이 치던 글"):
        await inj.deliver(SID, "글", sessions_dir="/s", transcript=None)
    assert _kinds(sent) == ["Escape"]
