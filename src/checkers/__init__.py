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

# Registry of known UDP services: port -> (display name, checker instance)
_UDP_SERVICE_REGISTRY: dict[int, tuple[str, BaseChecker]] | None = None


def get_udp_service_registry() -> dict[int, tuple[str, BaseChecker]]:
    """
    Returns a mapping of UDP service port to a tuple of (service name, checker instance).

    Ports covered:
    - 427: SLP
    - 5353: mDNS
    - 3702: WS-Discovery
    - 161: SNMP
    """
    global _UDP_SERVICE_REGISTRY
    if _UDP_SERVICE_REGISTRY is None:
        _UDP_SERVICE_REGISTRY = {
            427: ("SLP", SLPChecker()),
            5353: ("mDNS", MDNSChecker()),
            3702: ("WS-Discovery", WSDiscoveryChecker()),
            161: ("SNMP", SNMPChecker()),
        }
    return _UDP_SERVICE_REGISTRY

__all__ = [
    "BaseChecker",
    "CheckResult",
    "SLPChecker",
    "MDNSChecker",
    "WSDiscoveryChecker",
    "SNMPChecker",
    "get_udp_service_registry",
]
