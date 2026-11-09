"""세션 모델 고르기(11-05) — config/models.toml의 고를 수 있는 모델 · 역할별 기본값, 메시지의 모델 id를 화면 이름으로.

띄울 때는 `claude --model <id>`로 넘긴다. 실제로 쓴 모델은 트랜스크립트의 메시지마다 남으므로(DB message.model)
화면은 띄울 때 고른 값이 아니라 그것을 보인다(세션 안에서 /model로 바꿀 수 있다)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "models.toml"
_ID = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,39}$")   # 셸 명령에 그대로 들어가므로 좁게


class Models:
    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        raw: dict[str, Any] = {}
        try:
            raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        except OSError:
            pass
        self.choices = [c for c in raw.get("choices") or [] if _ID.match(str(c.get("id", "")))]
        self.defaults = {k: v for k, v in (raw.get("defaults") or {}).items() if self.valid(v)}
        self.tasks = {k: v for k, v in (raw.get("tasks") or {}).items() if self.valid(v)}

    def task(self, name: str, fallback: str = "sonnet") -> str:
        """세션이 아닌 `claude -p` 일감의 모델([tasks]). 없거나 목록에 없으면 fallback."""
        return self.tasks.get(name) or fallback

    def valid(self, model: str | None) -> bool:
        return bool(model) and any(c["id"] == model for c in self.choices)

    def default_for(self, role: str | None) -> str | None:
        return self.defaults.get(role or "coder")

    def pick(self, model: str | None, role: str | None) -> str | None:
        """고른 값이 목록에 있으면 그것, 아니면 역할 기본값(없으면 None — CC 설정을 따른다)."""
        return model if self.valid(model) else self.default_for(role)

    def view(self) -> dict[str, Any]:
        return {"choices": self.choices, "defaults": self.defaults}


def load_windows(path: str | Path = DEFAULT_PATH) -> dict[str, int]:
    """config/models.toml [windows] — family별 컨텍스트 창(토큰). 없는 파일 · 잘못된 값은 뺀다."""
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("windows") or {}
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool) and v > 0}


def window_of(windows: dict[str, int], model_id: str | None) -> int | None:
    """메시지의 모델 id → 창 크기. 모르는 모델이면 None(%를 보이지 않는다)."""
    return windows.get(family(model_id)) if model_id else None


def label(model_id: str | None) -> str:
    """메시지의 모델 id → 화면 이름. claude-opus-5-5 → Opus 5.5, claude-haiku-4-5-20251001 → Haiku 4.5."""
    if not model_id:
        return ""
    m = re.match(r"^claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?$", model_id)
    if not m:
        return model_id
    return f"{m[1].capitalize()} {m[2]}{'.' + m[3] if m[3] else ''}"


def family(model_id: str | None) -> str:
    """opus · sonnet · haiku · fable … — 색 · 묶음용. 모르면 other."""
    m = re.match(r"^claude-([a-z]+)-", model_id or "")
    return m[1] if m else ("other" if model_id else "")
