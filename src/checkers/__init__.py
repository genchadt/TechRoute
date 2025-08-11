"""
UDP service checkers package.

Provides a common BaseChecker and concrete checkers for:
- SLP (UDP/427)
- mDNS (UDP/5353)
- WS-Discovery (UDP/3702)
- SNMP (UDP/161)

Each checker exposes a simple `check(host: str, timeout: float) -> bool | dict` API
that returns True/False for availability or a small dict with basic info.

These checkers are kept decoupled from the GUI; the main app can integrate them later.
"""

from .base import BaseChecker, CheckResult
from .slp import SLPChecker
from .mdns import MDNSChecker
from .wsdiscovery import WSDiscoveryChecker
from .snmp_checker import SNMPChecker

__all__ = [
    "BaseChecker",
    "CheckResult",
    "SLPChecker",
    "MDNSChecker",
    "WSDiscoveryChecker",
    "SNMPChecker",
]
