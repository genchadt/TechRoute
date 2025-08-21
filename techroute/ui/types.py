"""
Shared typing information for the UI layer.
"""
from __future__ import annotations
from typing import Protocol, Dict, Any, Callable, List, Optional, Tuple, TYPE_CHECKING
from tkinter import ttk
from enum import Enum, auto
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..controller import TechRouteController

# ------------------- Data Structures for State Transfer -------------------

class AppState(Enum):
    """Defines the possible operational states of the application."""
    IDLE = auto()
    CHECKING = auto()
    PINGING = auto()
    STOPPING = auto()

StatusUpdatePayload = Dict[str, Any]
NetworkInfoPayload = Dict[str, Any]

# ------------------- Protocols for Decoupling -------------------

@dataclass
class ControllerCallbacks:
    """
    A container for all callback functions the controller uses to communicate with the UI.
    This ensures the controller remains UI-agnostic.
    """
    on_state_change: Callable[[AppState], None]
    on_status_update: Callable[[List[StatusUpdatePayload]], None]
    on_initial_statuses_loaded: Callable[[List[Dict[str, Any]]], None]
    on_network_info_update: Callable[[NetworkInfoPayload], None]

    def __init__(self, on_state_change: Callable[[AppState], None],
                 on_status_update: Callable[[List[StatusUpdatePayload]], None],
                 on_initial_statuses_loaded: Callable[[List[Dict[str, Any]]], None],
                 on_network_info_update: Callable[[NetworkInfoPayload], None]):
        self.on_state_change = on_state_change
        self.on_status_update = on_status_update
        self.on_initial_statuses_loaded = on_initial_statuses_loaded
        self.on_network_info_update = on_network_info_update
