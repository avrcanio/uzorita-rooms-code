from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

NEEDS_HUMAN_MESSAGE = (
    "Booking traži CAPTCHA ili provjeru (AWS WAF). "
    "Riješite zadatak u iframeu ispod, zatim kliknite Nastavi. "
    "Alternativa: RustDesk na bridge računalo i uvezite storage_state."
)


class ConnectOutcome(str, Enum):
    CONNECTED = "connected"
    NEEDS_2FA = "needs_2fa"
    NEEDS_HUMAN = "needs_human"


@dataclass(frozen=True)
class ConnectResult:
    outcome: ConnectOutcome
    storage_relative_path: str | None = None
