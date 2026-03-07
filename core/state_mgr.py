import json
from pathlib import Path
from typing import Dict, Any

STATE_FILE = Path(__file__).resolve().parent.parent / "nexus-state.json"

def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_state(state: Dict[str, Any]):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def add_app_state(app_name: str, app_data: Dict[str, Any]):
    state = load_state()
    state[app_name] = app_data
    save_state(state)

def remove_app_state(app_name: str):
    state = load_state()
    if app_name in state:
        state.pop(app_name)
        save_state(state)

def get_app_state(app_name: str) -> Dict[str, Any] | None:
    state = load_state()
    return state.get(app_name)
