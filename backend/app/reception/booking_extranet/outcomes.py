from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

NEEDS_HUMAN_MESSAGE = (
    "Booking traži CAPTCHA ili provjeru (AWS WAF). "
    "Riješite zadatak u iframeu ispod, zatim kliknite Nastavi. "
    "Alternativa: uvezite storage_state (JSON) u Postavke → Booking."
)

NEEDS_2FA_MESSAGE = (
    "Booking traži SMS kod. Prijava s IP-a servera (Hetzner) često aktivira "
    "dodatne provjere."
)

NEEDS_2FA_SMS_LIMIT_MESSAGE = (
    "Booking više ne šalje SMS (previše pokušaja s servera). "
    "Pričekajte 24–48 h ili se prijavite na laptopu i uvezite sesiju (JSON). "
    "Ne pokrećite ponovno „Pokreni prijavu (VNC)”."
)


class ConnectOutcome(str, Enum):
    CONNECTED = "connected"
    NEEDS_2FA = "needs_2fa"
    NEEDS_HUMAN = "needs_human"


@dataclass(frozen=True)
class ConnectResult:
    outcome: ConnectOutcome
    storage_relative_path: str | None = None
