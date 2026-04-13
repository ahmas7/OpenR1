"""
R1 - Chat Integrations
Telegram, Discord, WhatsApp, Slack, Signal
"""
import os
import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, Optional


class ChatPlatform(ABC):
    @abstractmethod
    async def start(self): pass
    
    @abstractmethod
    async def stop(self): pass
    
    @abstractmethod
    async def send_message(self, chat_id: str, text: str): pass


class TelegramBot(ChatPlatform):
    def __init__(self, token: str, on_message: Callable):
        self.token = token
        self.on_message = on_message
        self.running = False
        self.offset = 0
    
    async def start(self):
        self.running = True
        while self.running:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"https://api.telegram.org/bot{self.token}/getUpdates",
                        params={"offset": self.offset, "timeout": 60}
                    )
                    for update in r.json().get("result", []):
                        self.offset = update["update_id"] + 1
                        if "message" in update and update["message"].get("text"):
                            msg = update["message"]
                            await self.on_message({
                                "platform": "telegram",
                                "chat_id": str(msg["chat"]["id"]),
                                "user_id": str(msg["from"]["id"]),
                                "text": msg["text"]
                            })
            except Exception as e:
                print(f"Telegram error: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        self.running = False
    
    async def send_message(self, chat_id: str, text: str):
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )


class DiscordBot(ChatPlatform):
    def __init__(self, token: str, on_message: Callable):
        self.token = token
        self.on_message = on_message
        self.running = False
        self.ws = None
    
    async def start(self):
        import httpx
        import websockets
        import json
        
        self.running = True
        async with httpx.AsyncClient() as client:
            r = await client.get("https://discord.com/api/v10/gateway")
            url = r.json()["url"] + "?v=10&encoding=json"
        
        while self.running:
            try:
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if data.get("op") == 10:
                            asyncio.create_task(self._heartbeat(data["d"]["heartbeat_interval"] / 1000))
                            await self._identify()
                        
                        elif data.get("op") == 0 and data.get("t") == "MESSAGE_CREATE":
                            msg_data = data["d"]
                            if not msg_data.get("author", {}).get("bot"):
                                await self.on_message({
                                    "platform": "discord",
                                    "channel_id": msg_data["channel_id"],
                                    "user_id": msg_data["author"]["id"],
                                    "text": msg_data.get("content", "")
                                })
            except Exception as e:
                print(f"Discord error: {e}")
                await asyncio.sleep(5)
    
    async def _identify(self):
        import json
        await self.ws.send(json.dumps({
            "op": 2, "d": {
                "token": self.token,
                "intents": 513,
                "properties": {"os": "windows", "browser": "r1", "device": "r1"}
            }
        }))
    
    async def _heartbeat(self, interval: float):
        import json
        while self.running:
            await asyncio.sleep(interval)
            await self.ws.send(json.dumps({"op": 1, "d": None}))
    
    async def stop(self):
        self.running = False
    
    async def send_message(self, channel_id: str, text: str):
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {self.token}"},
                json={"content": text}
            )


class WhatsAppBot(ChatPlatform):
    def __init__(self, account_sid: str, auth_token: str, from_number: str, on_message: Callable):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.on_message = on_message
        self.running = False
    
    async def start(self):
        self.running = True
        print("WhatsApp bot ready - configure webhook in Twilio console")
    
    async def stop(self):
        self.running = False
    
    async def send_message(self, to: str, text: str):
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                auth=(self.account_sid, self.auth_token),
                data={
                    "To": f"whatsapp:{to}",
                    "From": f"whatsapp:{self.from_number}",
                    "Body": text
                }
            )


class SlackBot(ChatPlatform):
    def __init__(self, token: str, on_message: Callable):
        self.token = token
        self.on_message = on_message
        self.running = False
    
    async def start(self):
        self.running = True
        print("Slack bot ready - configure events webhook")
    
    async def stop(self):
        self.running = False
    
    async def send_message(self, channel: str, text: str):
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"channel": channel, "text": text}
            )


class ChatManager:
    def __init__(self, on_message: Callable):
        self.on_message = on_message
        self.platforms: Dict[str, ChatPlatform] = {}
    
    def add_telegram(self, token: str):
        self.platforms["telegram"] = TelegramBot(token, self.on_message)
        return self
    
    def add_discord(self, token: str):
        self.platforms["discord"] = DiscordBot(token, self.on_message)
        return self
    
    def add_whatsapp(self, account_sid: str, auth_token: str, from_number: str):
        self.platforms["whatsapp"] = WhatsAppBot(account_sid, auth_token, from_number, self.on_message)
        return self
    
    def add_slack(self, token: str):
        self.platforms["slack"] = SlackBot(token, self.on_message)
        return self
    
    async def start_all(self):
        for platform in self.platforms.values():
            await platform.start()
    
    async def stop_all(self):
        for platform in self.platforms.values():
            await platform.stop()
    
    async def send(self, platform: str, chat_id: str, text: str):
        if platform in self.platforms:
            await self.platforms[platform].send_message(chat_id, text)
