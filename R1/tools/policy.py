"""
R1 v1 - Tool Safety Policy
"""
from dataclasses import dataclass
from typing import Tuple

from .base import SafetyLevel
from ..config.settings import settings


@dataclass
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


def evaluate_policy(safety: SafetyLevel) -> PolicyDecision:
    policy = settings.tool_policy.lower().strip()

    if policy == "allow":
        return PolicyDecision(allowed=True)

    if policy == "deny":
        if safety == SafetyLevel.DANGEROUS:
            return PolicyDecision(allowed=False, reason="Dangerous tools are denied by policy.")
        return PolicyDecision(allowed=True)

    # default: confirm
    if safety == SafetyLevel.DANGEROUS:
        return PolicyDecision(
            allowed=False,
            requires_confirmation=True,
            reason="Dangerous tool requires confirmation."
        )

    return PolicyDecision(allowed=True)
