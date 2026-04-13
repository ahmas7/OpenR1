"""
R1 v1 - Service Registry
"""
from typing import Any, Dict, Optional


class ServiceRegistry:
    def __init__(self):
        self._services: Dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        self._services[name] = service

    def get(self, name: str) -> Optional[Any]:
        return self._services.get(name)

    def list(self) -> Dict[str, Any]:
        return dict(self._services)


_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
