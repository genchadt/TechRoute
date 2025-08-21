"""
Defines the application's state model and the actions that can be dispatched.

This module provides the core components for a unidirectional data flow,
decoupling the UI from the controller.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable


@dataclass
class AppStateModel:
    """A dataclass holding the entire application state."""
    # Add state fields here as needed, e.g.:
    # current_state: AppState = AppState.IDLE
    # targets: List[Dict[str, Any]] = field(default_factory=list)
    pass


class AppActions:
    """Defines the actions the UI can dispatch."""

    def __init__(self):
        self.toggle_ping_process: Callable[[str, int], None] = lambda *args: None
        self.stop_ping_process: Callable[[], None] = lambda: None
        self.get_all_targets_with_status: Callable[[], List[Dict[str, Any]]] = lambda: []
        self.get_state: Callable[[], Any] = lambda: None
        self.get_polling_rate_ms: Callable[[], int] = lambda: 1000
        self.get_gateway_ip: Callable[[], Optional[str]] = lambda: None
        self.get_web_ui_url: Callable[[str, Optional[int]], Optional[str]] = lambda *args: None
        self.get_all_web_ui_urls: Callable[[], List[str]] = lambda: []
        self.process_network_updates: Callable[[], None] = lambda: None
        self.process_queue: Callable[[], None] = lambda: None
        self.update_config: Callable[[Dict[str, Any]], None] = lambda *args: None
        self.get_browser_command: Callable[[], Dict[str, Any]] = lambda: {}
        self.settings_changed: Callable[[Dict[str, Any], Dict[str, Any]], None] = lambda *args: None
        self.get_config: Callable[[], Dict[str, Any]] = lambda: {}
        self.extract_host: Callable[[str], str] = lambda s: s
        self.get_service_checkers: Callable[[], List[Any]] = lambda: []
