"""Settings read from environment variables (GitHub Secrets / Variables)."""
import os
from dataclasses import dataclass

# Asia/Tashkent is UTC+5 all year (no daylight saving).
TZ_OFFSET_HOURS = 5

# slot -> (local post time, draft cron in UTC, publish cron in UTC)
# Drafts go out ~1h45m before the post so there is time to approve.
# Publish runs at :57 because GitHub starts scheduled jobs a few minutes late,
# and avoiding :00 sidesteps the busiest minute on GitHub's scheduler.
SLOTS = {
    "morning": ("08:00", "15 1 * * *", "57 2 * * *"),
    "noon":    ("12:00", "15 5 * * *", "57 6 * * *"),
    "evening": ("18:00", "15 11 * * *", "57 12 * * *"),
}

SLOT_NAMES_UZ = {
    "morning": "Ertalabki yangilik",
    "noon": "Kunduzgi qoʻllanma",
    "evening": "Kechki muhokama",
}


def slot_from_schedule(cron: str):
    """Map the cron string GitHub passes in back to (slot, stage)."""
    cron = (cron or "").strip()
    for slot, (_, draft_cron, publish_cron) in SLOTS.items():
        if cron == draft_cron:
            return slot, "draft"
        if cron == publish_cron:
            return slot, "publish"
    return None, None


@dataclass
class Config:
    bot_token: str
    channel_id: str
    admin_chat_id: str
    anthropic_key: str
    approval: bool
    writer_model: str
    checker_model: str


def _get(name: str, required: bool) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise SystemExit(f"Muhit o'zgaruvchisi yo'q: {name}")
    return value


def load(need_telegram: bool = True, need_claude: bool = True) -> Config:
    return Config(
        bot_token=_get("TELEGRAM_BOT_TOKEN", need_telegram),
        channel_id=_get("CHANNEL_ID", need_telegram),
        admin_chat_id=_get("ADMIN_CHAT_ID", need_telegram),
        anthropic_key=_get("ANTHROPIC_API_KEY", need_claude),
        approval=os.environ.get("APPROVAL", "1").strip() not in ("0", "false", "no", "off"),
        writer_model=os.environ.get("WRITER_MODEL", "").strip() or "claude-sonnet-5-5",
        checker_model=os.environ.get("CHECKER_MODEL", "").strip() or "claude-haiku-5-5",
    )
