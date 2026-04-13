"""
R1 - Webhook Handler
Webhook management and event processing
"""
import asyncio
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger("R1:webhooks")


class WebhookEvent(Enum):
    MESSAGE = "message"
    MESSAGE_CREATED = "message.created"
    MESSAGE_UPDATED = "message.updated"
    MESSAGE_DELETED = "message.deleted"
    TYPING_START = "typing.start"
    REACTION_ADDED = "reaction.added"
    REACTION_REMOVED = "reaction.removed"
    CHANNEL_CREATED = "channel.created"
    CHANNEL_DELETED = "channel.deleted"
    MEMBER_JOINED = "member.joined"
    MEMBER_LEFT = "member.left"
    CUSTOM = "custom"


class WebhookMethod(Enum):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"


@dataclass
class Webhook:
    id: str
    name: str
    url: str
    events: List[str] = field(default_factory=list)
    secret: Optional[str] = None
    enabled: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    method: WebhookMethod = WebhookMethod.POST
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    custom_payload: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    last_triggered: Optional[str] = None
    trigger_count: int = 0


@dataclass
class WebhookEventData:
    webhook_id: str
    event: str
    payload: Dict[str, Any]
    timestamp: str
    headers: Dict[str, str] = field(default_factory=dict)
    source: str = ""


class WebhookManager:
    def __init__(self, config_dir: Optional[str] = None):
        self.webhooks: Dict[str, Webhook] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
        self.config_dir = config_dir
        self._webhook_handler: Optional[Callable] = None
        
        if config_dir:
            from pathlib import Path
            self.webhooks_file = Path(config_dir) / "webhooks.json"
            self._load_webhooks()
    
    def _load_webhooks(self):
        if hasattr(self, 'webhooks_file') and self.webhooks_file.exists():
            try:
                data = json.loads(self.webhooks_file.read_text())
                for wh_data in data.get("webhooks", []):
                    webhook = Webhook(
                        id=wh_data["id"],
                        name=wh_data["name"],
                        url=wh_data["url"],
                        events=wh_data.get("events", []),
                        secret=wh_data.get("secret"),
                        enabled=wh_data.get("enabled", True),
                        headers=wh_data.get("headers", {}),
                        method=WebhookMethod(wh_data.get("method", "POST")),
                        timeout=wh_data.get("timeout", 30),
                        retry_count=wh_data.get("retry_count", 3),
                        retry_delay=wh_data.get("retry_delay", 1.0),
                        custom_payload=wh_data.get("custom_payload"),
                        filters=wh_data.get("filters", {}),
                        created_at=wh_data.get("created_at", ""),
                        last_triggered=wh_data.get("last_triggered"),
                        trigger_count=wh_data.get("trigger_count", 0),
                    )
                    self.webhooks[webhook.id] = webhook
                    
                    for event in webhook.events:
                        if event not in self.event_handlers:
                            self.event_handlers[event] = []
            except Exception as e:
                logger.error(f"Failed to load webhooks: {e}")
    
    def _save_webhooks(self):
        if hasattr(self, 'webhooks_file'):
            data = {
                "webhooks": [
                    {
                        "id": wh.id,
                        "name": wh.name,
                        "url": wh.url,
                        "events": wh.events,
                        "secret": wh.secret,
                        "enabled": wh.enabled,
                        "headers": wh.headers,
                        "method": wh.method.value,
                        "timeout": wh.timeout,
                        "retry_count": wh.retry_count,
                        "retry_delay": wh.retry_delay,
                        "custom_payload": wh.custom_payload,
                        "filters": wh.filters,
                        "created_at": wh.created_at,
                        "last_triggered": wh.last_triggered,
                        "trigger_count": wh.trigger_count,
                    }
                    for wh in self.webhooks.values()
                ]
            }
            self.webhooks_file.write_text(json.dumps(data, indent=2))
    
    def set_webhook_handler(self, handler: Callable):
        self._webhook_handler = handler
    
    def add_webhook(
        self,
        name: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        method: WebhookMethod = WebhookMethod.POST,
    ) -> Webhook:
        webhook_id = secrets.token_hex(8)
        
        webhook = Webhook(
            id=webhook_id,
            name=name,
            url=url,
            events=events,
            secret=secret or secrets.token_hex(16),
            headers=headers or {},
            method=method,
            created_at=datetime.now().isoformat(),
        )
        
        self.webhooks[webhook_id] = webhook
        
        for event in events:
            if event not in self.event_handlers:
                self.event_handlers[event] = []
        
        self._save_webhooks()
        logger.info(f"Added webhook: {name} ({webhook_id})")
        
        return webhook
    
    def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        return self.webhooks.get(webhook_id)
    
    def update_webhook(self, webhook_id: str, **kwargs) -> Optional[Webhook]:
        if webhook_id not in self.webhooks:
            return None
        
        webhook = self.webhooks[webhook_id]
        
        for key, value in kwargs.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        
        self._save_webhooks()
        return webhook
    
    def delete_webhook(self, webhook_id: str) -> bool:
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            self._save_webhooks()
            return True
        return False
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": wh.id,
                "name": wh.name,
                "url": wh.url,
                "events": wh.events,
                "enabled": wh.enabled,
                "created_at": wh.created_at,
                "last_triggered": wh.last_triggered,
                "trigger_count": wh.trigger_count,
            }
            for wh in self.webhooks.values()
        ]
    
    def register_event_handler(self, event: str, handler: Callable):
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    def register_global_handler(self, handler: Callable):
        self.global_handlers.append(handler)
    
    async def trigger(self, event: str, payload: Dict[str, Any], source: str = "") -> List[Dict[str, Any]]:
        results = []
        
        matching_webhooks = [
            wh for wh in self.webhooks.values()
            if wh.enabled and (event in wh.events or "*" in wh.events)
        ]
        
        for webhook in matching_webhooks:
            if not self._passes_filters(webhook.filters, payload):
                continue
            
            result = await self._send_webhook(webhook, event, payload, source)
            results.append(result)
            
            webhook.last_triggered = datetime.now().isoformat()
            webhook.trigger_count += 1
        
        for handler in self.global_handlers:
            try:
                event_data = WebhookEventData(
                    webhook_id="",
                    event=event,
                    payload=payload,
                    timestamp=datetime.now().isoformat(),
                    source=source,
                )
                await handler(event_data)
            except Exception as e:
                logger.error(f"Global handler error: {e}")
        
        for handlers in self.event_handlers.values():
            for handler in handlers:
                try:
                    event_data = WebhookEventData(
                        webhook_id="",
                        event=event,
                        payload=payload,
                        timestamp=datetime.now().isoformat(),
                        source=source,
                    )
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
        
        self._save_webhooks()
        return results
    
    async def _send_webhook(
        self,
        webhook: Webhook,
        event: str,
        payload: Dict[str, Any],
        source: str,
    ) -> Dict[str, Any]:
        import httpx
        
        headers = dict(webhook.headers)
        
        if webhook.secret:
            import json
            payload_str = json.dumps(payload)
            signature = hmac.new(
                webhook.secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        headers["X-Webhook-Event"] = event
        headers["X-Webhook-Timestamp"] = datetime.now().isoformat()
        headers["Content-Type"] = "application/json"
        
        body = webhook.custom_payload if webhook.custom_payload else json.dumps({
            "event": event,
            "payload": payload,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        })
        
        for attempt in range(webhook.retry_count):
            try:
                async with httpx.AsyncClient(timeout=webhook.timeout) as client:
                    response = await client.request(
                        method=webhook.method.value,
                        url=webhook.url,
                        content=body,
                        headers=headers,
                    )
                    
                    if response.status_code < 400:
                        return {
                            "webhook_id": webhook.id,
                            "success": True,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                        }
                    else:
                        logger.warning(f"Webhook {webhook.id} returned {response.status_code}")
                        
            except Exception as e:
                logger.error(f"Webhook {webhook.id} attempt {attempt + 1} failed: {e}")
            
            if attempt < webhook.retry_count - 1:
                await asyncio.sleep(webhook.retry_delay * (attempt + 1))
        
        return {
            "webhook_id": webhook.id,
            "success": False,
            "error": "All retry attempts failed",
            "attempt": webhook.retry_count,
        }
    
    def _passes_filters(self, filters: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        if not filters:
            return True
        
        for key, expected in filters.items():
            actual = payload.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False
        
        return True
    
    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        expected = "sha256=" + hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class WebhookTrigger:
    def __init__(self, webhook_manager: WebhookManager):
        self.webhook_manager = webhook_manager
    
    async def message_created(self, message: Dict[str, Any], source: str = ""):
        return await self.webhook_manager.trigger("message.created", message, source)
    
    async def message_updated(self, message: Dict[str, Any], source: str = ""):
        return await self.webhook_manager.trigger("message.updated", message, source)
    
    async def message_deleted(self, message_id: str, source: str = ""):
        return await self.webhook_manager.trigger("message.deleted", {"id": message_id}, source)
    
    async def typing_started(self, channel: str, user: str, source: str = ""):
        return await self.webhook_manager.trigger("typing.start", {
            "channel": channel,
            "user": user,
        }, source)
    
    async def custom_event(self, event_name: str, payload: Dict[str, Any], source: str = ""):
        return await self.webhook_manager.trigger(event_name, payload, source)
