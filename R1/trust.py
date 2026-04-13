"""
R1 - Trust Ladder System
5-level trust system with domain-specific scores and permission management
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum
import hashlib

logger = logging.getLogger("R1:trust")


class TrustLevel(Enum):
    """
    Trust levels from lowest to highest.
    Each level grants progressively more permissions.
    """
    STRANGER = "stranger"           # Level 0: Chat only
    ACQUAINTANCE = "acquaintance"   # Level 1: Browse web
    ASSOCIATE = "associate"         # Level 2: Shell commands (read-only)
    PARTNER = "partner"             # Level 3: Filesystem access
    OPERATOR = "operator"           # Level 4: Full access


# Permissions granted at each trust level
TRUST_PERMISSIONS = {
    TrustLevel.STRANGER: {
        "chat": True,
        "read_memory": True,
        "browse": False,
        "shell": False,
        "shell_write": False,
        "filesystem_read": False,
        "filesystem_write": False,
        "code_exec": False,
        "app_control": False,
        "full_access": False
    },
    TrustLevel.ACQUAINTANCE: {
        "chat": True,
        "read_memory": True,
        "browse": True,
        "shell": False,
        "shell_write": False,
        "filesystem_read": False,
        "filesystem_write": False,
        "code_exec": False,
        "app_control": False,
        "full_access": False
    },
    TrustLevel.ASSOCIATE: {
        "chat": True,
        "read_memory": True,
        "browse": True,
        "shell": True,           # Read-only commands
        "shell_write": False,
        "filesystem_read": False,
        "filesystem_write": False,
        "code_exec": True,       # Sandboxed only
        "app_control": False,
        "full_access": False
    },
    TrustLevel.PARTNER: {
        "chat": True,
        "read_memory": True,
        "browse": True,
        "shell": True,
        "shell_write": True,     # Can modify files via shell
        "filesystem_read": True,
        "filesystem_write": True,
        "code_exec": True,
        "app_control": True,
        "full_access": False
    },
    TrustLevel.OPERATOR: {
        "chat": True,
        "read_memory": True,
        "browse": True,
        "shell": True,
        "shell_write": True,
        "filesystem_read": True,
        "filesystem_write": True,
        "code_exec": True,
        "app_control": True,
        "full_access": True      # No restrictions
    }
}

# Trust score thresholds for each level
TRUST_THRESHOLDS = {
    TrustLevel.STRANGER: 0,
    TrustLevel.ACQUAINTANCE: 20,
    TrustLevel.ASSOCIATE: 40,
    TrustLevel.PARTNER: 60,
    TrustLevel.OPERATOR: 80
}


class TrustManager:
    """
    Manages trust levels and permissions for the R1 AI system.
    Tracks trust scores per domain and calculates overall trust level.
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / ".r1"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.trust_file = self.data_dir / "trust_data.json"
        self.history_file = self.data_dir / "trust_history.json"

        # Load or initialize trust data
        self.trust_data = self._load_trust_data()
        self.history = self._load_history()

        logger.info(f"TrustManager initialized: {self.get_current_level().value}")

    def _load_trust_data(self) -> Dict:
        """Load trust data from file"""
        if self.trust_file.exists():
            try:
                return json.loads(self.trust_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load trust data: {e}")

        # Default trust data
        return {
            "overall_score": 0,
            "domain_scores": {
                "coding": 0,
                "browsing": 0,
                "files": 0,
                "shell": 0,
                "general": 0
            },
            "current_level": TrustLevel.STRANGER.value,
            "last_interaction": None,
            "decay_rate": 0.1,  # Trust decay per day of inactivity
            "last_decay": datetime.now().isoformat()
        }

    def _load_history(self) -> List:
        """Load trust history"""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())[-500:]  # Last 500 entries
            except:
                pass
        return []

    def _save_trust_data(self):
        """Save trust data to file"""
        self.trust_file.write_text(json.dumps(self.trust_data, indent=2))

    def _save_history(self):
        """Save trust history"""
        self.history_file.write_text(json.dumps(self.history[-500:], indent=2))

    def _apply_decay(self):
        """Apply trust decay for inactivity"""
        try:
            last_decay = datetime.fromisoformat(self.trust_data["last_decay"])
            days_since_decay = (datetime.now() - last_decay).days

            if days_since_decay >= 1:  # Apply decay daily
                decay_amount = self.trust_data["decay_rate"] * days_since_decay

                # Decay each domain score
                for domain in self.trust_data["domain_scores"]:
                    self.trust_data["domain_scores"][domain] = max(
                        0,
                        self.trust_data["domain_scores"][domain] - decay_amount
                    )

                # Recalculate overall
                self.trust_data["overall_score"] = sum(
                    self.trust_data["domain_scores"].values()
                ) / len(self.trust_data["domain_scores"])

                self.trust_data["last_decay"] = datetime.now().isoformat()
                self._recalculate_level()
                self._save_trust_data()

                logger.info(f"Applied trust decay: -{decay_amount:.1f}")
        except Exception as e:
            logger.error(f"Failed to apply trust decay: {e}")

    def update_trust(self, domain: str, success: bool, magnitude: int = 1,
                     context: str = None) -> Dict:
        """
        Update trust score based on an interaction outcome.

        Args:
            domain: The domain of the action (coding, browsing, files, shell, general)
            success: Whether the action was successful
            magnitude: The magnitude of the trust change (1-10)
            context: Optional context about the action

        Returns:
            Dict with updated trust info
        """
        # Apply any pending decay first
        self._apply_decay()

        # Validate domain
        if domain not in self.trust_data["domain_scores"]:
            domain = "general"

        # Calculate delta
        delta = magnitude if success else -magnitude
        trust_cap = 100 if success else 0

        # Update domain score
        old_domain_score = self.trust_data["domain_scores"][domain]
        self.trust_data["domain_scores"][domain] = max(0, min(100,
            old_domain_score + delta
        ))

        # Update overall score (weighted average)
        old_overall = self.trust_data["overall_score"]
        self.trust_data["overall_score"] = sum(
            self.trust_data["domain_scores"].values()
        ) / len(self.trust_data["domain_scores"])

        # Record history
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "domain": domain,
            "success": success,
            "magnitude": magnitude,
            "delta": delta,
            "old_domain_score": old_domain_score,
            "new_domain_score": self.trust_data["domain_scores"][domain],
            "old_overall": old_overall,
            "new_overall": self.trust_data["overall_score"],
            "context": context
        }
        self.history.append(history_entry)

        # Recalculate level
        old_level = self.trust_data["current_level"]
        self._recalculate_level()
        level_changed = self.trust_data["current_level"] != old_level

        # Update last interaction time
        self.trust_data["last_interaction"] = datetime.now().isoformat()

        # Save
        self._save_trust_data()
        self._save_history()

        result = {
            "domain": domain,
            "domain_score": self.trust_data["domain_scores"][domain],
            "overall_score": self.trust_data["overall_score"],
            "old_level": old_level,
            "new_level": self.trust_data["current_level"],
            "level_changed": level_changed
        }

        if level_changed:
            logger.info(f"Trust level changed: {old_level} -> {self.trust_data['current_level']}")

        return result

    def _recalculate_level(self):
        """Recalculate trust level based on overall score"""
        score = self.trust_data["overall_score"]

        # Find highest level the user qualifies for
        for level in reversed(TrustLevel):
            if score >= TRUST_THRESHOLDS[level]:
                self.trust_data["current_level"] = level.value
                return

        self.trust_data["current_level"] = TrustLevel.STRANGER.value

    def get_current_level(self) -> TrustLevel:
        """Get current trust level"""
        return TrustLevel(self.trust_data["current_level"])

    def get_domain_score(self, domain: str) -> float:
        """Get trust score for a specific domain"""
        return self.trust_data["domain_scores"].get(domain, 0)

    def get_overall_score(self) -> float:
        """Get overall trust score"""
        return self.trust_data["overall_score"]

    def check_permission(self, permission: str) -> bool:
        """
        Check if a permission is granted at current trust level.

        Args:
            permission: The permission to check (e.g., 'shell', 'filesystem_write')

        Returns:
            True if the permission is granted
        """
        level = self.get_current_level()
        return TRUST_PERMISSIONS[level].get(permission, False)

    def get_permissions(self) -> Dict[str, bool]:
        """Get all permissions for current trust level"""
        level = self.get_current_level()
        return TRUST_PERMISSIONS[level].copy()

    def get_required_level(self, permission: str) -> Optional[TrustLevel]:
        """Get the minimum trust level required for a permission"""
        for level in TrustLevel:
            if TRUST_PERMISSIONS[level].get(permission, False):
                return level
        return None

    def get_trust_summary(self) -> Dict:
        """Get a summary of trust status"""
        return {
            "level": self.trust_data["current_level"],
            "overall_score": round(self.trust_data["overall_score"], 1),
            "domain_scores": {
                k: round(v, 1) for k, v in self.trust_data["domain_scores"].items()
            },
            "permissions": self.get_permissions(),
            "last_interaction": self.trust_data.get("last_interaction"),
            "history_count": len(self.history)
        }

    def get_recent_history(self, limit: int = 20) -> List[Dict]:
        """Get recent trust history"""
        return self.history[-limit:]

    def reset_trust(self, domain: str = None):
        """
        Reset trust scores.

        Args:
            domain: If provided, reset only that domain. Otherwise reset all.
        """
        if domain:
            if domain in self.trust_data["domain_scores"]:
                self.trust_data["domain_scores"][domain] = 0
                logger.info(f"Reset trust for domain: {domain}")
        else:
            self.trust_data["overall_score"] = 0
            for domain in self.trust_data["domain_scores"]:
                self.trust_data["domain_scores"][domain] = 0
            self.trust_data["current_level"] = TrustLevel.STRANGER.value
            logger.info("Reset all trust scores")

        self._recalculate_level()
        self._save_trust_data()

    def boost_trust(self, domain: str = None, amount: int = 10):
        """
        Manually boost trust scores (admin function).

        Args:
            domain: If provided, boost only that domain. Otherwise boost all.
            amount: Amount to boost (1-50)
        """
        amount = min(50, max(1, amount))  # Cap between 1-50

        if domain:
            if domain in self.trust_data["domain_scores"]:
                self.trust_data["domain_scores"][domain] = min(100,
                    self.trust_data["domain_scores"][domain] + amount
                )
        else:
            for d in self.trust_data["domain_scores"]:
                self.trust_data["domain_scores"][d] = min(100,
                    self.trust_data["domain_scores"][d] + amount
                )

        self.trust_data["overall_score"] = sum(
            self.trust_data["domain_scores"].values()
        ) / len(self.trust_data["domain_scores"])

        self._recalculate_level()
        self._save_trust_data()

        logger.info(f"Boosted trust by {amount}")


# Global instance
_trust_manager: Optional[TrustManager] = None


def get_trust_manager(data_dir: Path = None) -> TrustManager:
    global _trust_manager
    if _trust_manager is None:
        _trust_manager = TrustManager(data_dir)
    return _trust_manager


# ========== Decorators for Permission Checking ==========

def require_permission(permission: str):
    """
    Decorator to require a permission for a function.

    Usage:
        @require_permission('shell')
        async def run_command(cmd):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tm = get_trust_manager()
            if not tm.check_permission(permission):
                required_level = tm.get_required_level(permission)
                raise PermissionError(
                    f"Permission '{permission}' denied. "
                    f"Required trust level: {required_level.value}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_trust_level(level: TrustLevel):
    """
    Decorator to require a minimum trust level.

    Usage:
        @require_trust_level(TrustLevel.PARTNER)
        async def sensitive_operation():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tm = get_trust_manager()
            current_level = tm.get_current_level()
            trust_levels = list(TrustLevel)

            if trust_levels.index(current_level) < trust_levels.index(level):
                raise PermissionError(
                    f"Trust level {current_level.value} insufficient. "
                    f"Required: {level.value}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
