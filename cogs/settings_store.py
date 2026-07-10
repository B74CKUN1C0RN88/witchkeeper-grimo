from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path(__file__).resolve().parent / "data" / "guild_settings.json"
_LOCK = asyncio.Lock()

DEFAULTS: dict[str, Any] = {
    "verify_role_id": None,
    "welcome_channel_id": None,
    "translation_enabled": True,
    "birthday_role_id": None,
    "birthday_channel_id": None,
    "moderation_log_channel_id": None,
    "morning_channel_id": None,
    "morning_enabled": False,
    "morning_time": "07:00",
    "morning_last_sent_date": None,
    "morning_last_message_index": None,
}


def _read_all() -> dict[str, dict[str, Any]]:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text("{}", encoding="utf-8")

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


async def get_guild_settings(guild_id: int) -> dict[str, Any]:
    async with _LOCK:
        data = _read_all()
        current = data.get(str(guild_id), {})
        return {**DEFAULTS, **current}


async def update_guild_settings(
    guild_id: int,
    **changes: Any,
) -> dict[str, Any]:
    async with _LOCK:
        data = _read_all()
        key = str(guild_id)
        current = {**DEFAULTS, **data.get(key, {})}
        current.update(changes)
        data[key] = current

        temp_file = SETTINGS_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_file.replace(SETTINGS_FILE)
        return current
