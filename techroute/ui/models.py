from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class StatusUpdate:
    """
    A structured object for status updates from the ping manager.
    """
    original_string: str
    ip: str
    latency: Optional[float]
    port_statuses: Dict[int, str] = field(default_factory=dict)
    udp_service_statuses: Dict[str, str] = field(default_factory=dict)
    web_port_open: bool = False
    extra_info: Optional[Any] = None
