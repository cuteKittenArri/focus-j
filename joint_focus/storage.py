import json
import os
from pathlib import Path
from typing import Any, Dict

APP_DIR = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "joint-focus"
STATE_FILE = APP_DIR / "state.json"

DEFAULT_STATE: Dict[str, Any] = {
    "joints": 0,
    "sessions_completed": 0,
    "minutes_focused": 0,
    "joints_redeemed": 0,
    "custom_minutes": 45,
}


def load_state() -> Dict[str, Any]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        state = DEFAULT_STATE.copy()
        for key, default_value in DEFAULT_STATE.items():
            state[key] = data.get(key, default_value)
        return state
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return DEFAULT_STATE.copy()


def save_state(state: Dict[str, Any]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = STATE_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp_file.replace(STATE_FILE)


def add_joint(state: Dict[str, Any], minutes: int) -> Dict[str, Any]:
    state["joints"] += 1
    state["sessions_completed"] += 1
    state["minutes_focused"] += minutes
    save_state(state)
    return state


def redeem_joint(state: Dict[str, Any]) -> bool:
    if state["joints"] > 0:
        state["joints"] -= 1
        state["joints_redeemed"] += 1
        save_state(state)
        return True
    return False


def set_custom_minutes(state: Dict[str, Any], minutes: int) -> None:
    if state.get("custom_minutes") != minutes:
        state["custom_minutes"] = minutes
        save_state(state)
