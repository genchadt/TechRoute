"""
UI component for the TechRoute application.

Defines the AppUI class, composed from mixins, responsible for building
and managing all Tkinter widgets for the main application window.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, TYPE_CHECKING

from .menu import MenuMixin
from .dialogs import DialogsMixin
from .animations import AnimationsMixin
from .builder import BuilderMixin
from .status_view import StatusViewMixin

if TYPE_CHECKING:
    from ..app import TechRouteApp


class AppUI(MenuMixin, DialogsMixin, AnimationsMixin, BuilderMixin, StatusViewMixin):
    """Manages the user interface of the TechRoute application."""
    clear_statuses_button: Optional[ttk.Button]
    # Local service indicators (created in BuilderMixin._setup_ui)
    local_http_indicator: tk.Button
    local_https_indicator: tk.Button
    local_rdp_indicator: tk.Button

    def __init__(self, root: tk.Tk, app_controller: 'TechRouteApp', browser_name: str):
        """Initializes the UI."""
        self.root = root
        self.app_controller = app_controller
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.blinking_animation_job: Optional[str] = None
        self.ping_animation_job: Optional[str] = None
        # For UIContext protocol compliance
        self._resizing_active: bool = False
        self._resize_debounce_job: Optional[str] = None
        self._last_canvas_width: Optional[int] = None
        # Optional button created in builder; may not be set in all contexts
        self.clear_statuses_button = None

        self._setup_menu()
        self._setup_ui(browser_name)
