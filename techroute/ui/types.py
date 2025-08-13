"""
Shared typing utilities for the TechRoute UI package.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TypeVar, TYPE_CHECKING, Protocol, Optional, Dict, Any, Callable

if TYPE_CHECKING:
    from .app_ui import AppUI
    from ..controller import TechRouteController
    from ..app import MainApp

AppUI_T = TypeVar("AppUI_T", bound="AppUI")

class AppUIProtocol(Protocol):
    """Protocol defining the interface that mixins expect from the main UI class."""
    root: tk.Tk
    config: Dict[str, Any]
    controller: Optional['TechRouteController']
    main_app: 'MainApp'
    status_indicator: ttk.Label
    status_bar_label: ttk.Label
    status_container: ttk.LabelFrame
    status_frame: ttk.Frame
    status_widgets: Dict[str, Dict[str, Any]]
    group_frames: Dict[str, ttk.LabelFrame]
    blinking_animation_job: Optional[str]
    ping_animation_job: Optional[str]
    
    def refresh_ui_for_settings_change(self) -> None: ...
    def update_status_bar(self, message: str) -> None: ...
    def _open_settings_dialog(self, on_save: Callable[[Dict, Dict], None]) -> None: ...

def create_indicator_button(parent: tk.Widget, text: str, is_open: bool = False, is_placeholder: bool = False, is_udp: bool = False) -> tk.Button:
    """Creates a standardized indicator button."""
    if is_placeholder:
        color = "#9E9E9E"  # Standard grey for placeholders
    else:
        if is_udp:
            color = "#2196F3" if is_open else "#FF9800"  # Blue/Orange for UDP
        else:
            color = "#4CAF50" if is_open else "#F44336"  # Green/Red for TCP
        
    return tk.Button(
        parent,
        text=text,
        bg=color,
        fg="white",
        disabledforeground="white",
        relief="raised",
        borderwidth=1,
        state=tk.DISABLED,
        padx=4,
        pady=1,
    )
