from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class PortStatus:
    """Represents the status of a single port."""
    port: int
    protocol: str  # "TCP" or "UDP"
    status: str    # "Open" or "Closed"
    service_name: Optional[str] = None

@dataclass
class PingResult:
    """Represents the result of a single ping and port scan operation from a worker."""
    original_string: str
    ip: str
    latency_ms: Optional[float]
    port_statuses: List[PortStatus] = field(default_factory=list)

@dataclass
class TargetStatus:
    """Represents the complete, canonical status of a single target."""
    ip: str
    original_string: str
    hostname: Optional[str] = None
    latency_ms: Optional[float] = None
    # Use a dictionary for fast lookups by port number
    port_statuses: Dict[int, PortStatus] = field(default_factory=dict)
    web_port_open: bool = False
