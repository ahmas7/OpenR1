"""
R1 - Integrations
Multi-channel messaging support
"""
from R1.integrations.discord import DiscordClient, DiscordConfig, DiscordMessage, DiscordNotifier, DMPolicy as DiscordDMPolicy
from R1.integrations.slack import SlackClient, SlackConfig, SlackMessage, SlackNotifier, DMPolicy as SlackDMPolicy
from R1.integrations.telegram import TelegramClient, TelegramConfig, TelegramMessage, TelegramNotifier, DMPolicy as TelegramDMPolicy

__all__ = [
    "DiscordClient",
    "DiscordConfig", 
    "DiscordMessage",
    "DiscordNotifier",
    "DiscordDMPolicy",
    "SlackClient",
    "SlackConfig",
    "SlackMessage",
    "SlackNotifier",
    "SlackDMPolicy",
    "TelegramClient",
    "TelegramConfig",
    "TelegramMessage",
    "TelegramNotifier",
    "TelegramDMPolicy",
]
