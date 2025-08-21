from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class StatusUpdate:
    """Represents a single status update for a target."""
    original_string: str
    status: str
    color: str
    latency_str: str
    port_statuses: Optional[Dict[str, str]]
    web_port_open: bool
    udp_service_statuses: Optional[Dict[str, str]]
