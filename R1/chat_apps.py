"""
R1 - Chat App Control Plane
Tracks configured chat integrations and exposes safe status metadata.
"""
import os
from typing import Dict, Any


class ChatAppsManager:
    def __init__(self):
        self.platforms = {
            "telegram": {
                "enabled": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
                "mode": "polling",
                "group_support": True,
            },
            "discord": {
                "enabled": bool(os.getenv("DISCORD_BOT_TOKEN")),
                "mode": "gateway",
                "group_support": True,
            },
            "whatsapp": {
                "enabled": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")),
                "mode": "twilio",
                "group_support": False,
            },
            "slack": {
                "enabled": bool(os.getenv("SLACK_BOT_TOKEN")),
                "mode": "events",
                "group_support": True,
            },
        }

    def get_status(self) -> Dict[str, Any]:
        configured = sum(1 for p in self.platforms.values() if p["enabled"])
        return {
            "configured": configured,
            "platforms": self.platforms,
            "private_by_default": True,
        }


chat_apps = ChatAppsManager()
