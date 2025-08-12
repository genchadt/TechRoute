"""
Shared typing utilities for the TechRoute UI package.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import TypeVar, TYPE_CHECKING, Protocol, Optional, Dict, Any

if TYPE_CHECKING:
    from .app_ui import AppUI
    from ..controller import TechRouteController

AppUI_T = TypeVar("AppUI_T", bound="AppUI")

class AppUIProtocol(Protocol):
    """Protocol defining the interface that mixins expect from the main UI class."""
    root: tk.Tk
    controller: Optional['TechRouteController']
    status_indicator: ttk.Label
    status_bar_label: ttk.Label
    status_frame: ttk.LabelFrame
    status_widgets: Dict[str, Dict[str, Any]]
    blinking_animation_job: Optional[str]
    ping_animation_job: Optional[str]
    
    def refresh_ui_for_settings_change(self) -> None: ...
    def update_status_bar(self, message: str) -> None: ...
    def _open_settings_dialog(self) -> None: ...

def create_indicator_button(parent: tk.Widget, text: str) -> tk.Button:
    """Creates a standardized indicator button."""
    return tk.Button(
        parent,
        text=text,
        bg="gray",
        fg="white",
        disabledforeground="white",
        relief="raised",
        borderwidth=1,
        state=tk.DISABLED,
        padx=4,
        pady=1,
    )
