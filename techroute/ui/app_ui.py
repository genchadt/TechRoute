"""
UI component for the TechRoute application.

Defines the AppUI class, composed from mixins, responsible for building
and managing all Tkinter widgets for the main application window.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, TYPE_CHECKING, Callable

from .menu import MenuMixin
from .dialogs import DialogsMixin
from .animations import AnimationsMixin
from .builder import BuilderMixin
from .status_view import StatusViewMixin

if TYPE_CHECKING:
    from ..app import TechRouteApp


class AppUI(MenuMixin, DialogsMixin, AnimationsMixin, BuilderMixin, StatusViewMixin):
    """Manages the user interface of the TechRoute application."""
    # Core objects
    root: tk.Tk
    app_controller: "TechRouteApp"

    # Status bar widgets / animation state
    menu_bar: tk.Menu
    status_bar_frame: ttk.Frame
    status_indicator: ttk.Label
    status_bar_label: ttk.Label
    blinking_animation_job: Optional[str]
    ping_animation_job: Optional[str]
    _ping_anim_gen: Optional[int]

    # Status list container
    main_frame: ttk.Frame
    controls_frame: ttk.Frame
    input_frame: ttk.LabelFrame
    status_container: ttk.Frame
    status_scrollbar: ttk.Scrollbar
    status_canvas: tk.Canvas
    status_frame_window: int
    status_frame: ttk.LabelFrame
    status_widgets: Dict[str, Dict[str, Any]]

    # Network information group widgets
    network_frame: ttk.LabelFrame
    netinfo_v4: ttk.Label
    netinfo_v6: ttk.Label
    netinfo_gw: ttk.Label
    netinfo_mask: ttk.Label

    # Local services indicators (by port number)
    local_service_indicators: Dict[int, tk.Button]
    _local_service_ports: list[int]

    # Inputs and buttons
    polling_rate_entry: ttk.Entry
    ports_button: ttk.Button
    services_button: ttk.Button
    update_button: ttk.Button
    ip_entry: tk.Text
    start_stop_button: ttk.Button
    launch_all_button: ttk.Button
    clear_statuses_button: Optional[ttk.Button]
    clear_field_button: Optional[ttk.Button]

    # Builder internal state for resize debounce/perf
    _resizing_active: bool
    _resize_debounce_job: Optional[str]
    _last_canvas_width: Optional[int]


    def __init__(self, root: tk.Tk, app_controller: 'TechRouteApp', browser_name: str):
        """Initializes the UI."""
        self.root = root
        self.app_controller = app_controller
        self.status_widgets = {}
        self.blinking_animation_job = None
        self.ping_animation_job = None
        # Optional buttons created in builder; may not be set in all contexts
        self.clear_statuses_button = None
        self.clear_field_button = None

        self._setup_menu()
        self._setup_ui(browser_name)

    def lock_min_size_to_current(self) -> None:
        """Locks the window's minimum size to its current size."""
        super().lock_min_size_to_current()

    def shrink_to_fit(self) -> None:
        """Resizes the window to fit its content, with a 10% width increase."""
        super().shrink_to_fit()

    def refresh_ui_for_settings_change(self) -> None:
        """Refreshes UI elements that depend on configuration settings."""
        # Update local service indicators
        readability = self.app_controller.config.get('port_readability', 'Numbers')
        service_map = self.app_controller.config.get('port_service_map', {})
        for port, button in self.local_service_indicators.items():
            display_text = str(port)
            if readability == 'Simple':
                display_text = service_map.get(str(port), str(port))
            button.config(text=display_text)

        # If there are active statuses, redraw them to reflect the new setting
        if self.status_widgets:
            # Get the current list of targets from the status_widgets keys
            targets = [{'original_string': s, 'ports': list(w.get('port_widgets', {}).keys())} for s, w in self.status_widgets.items()]
            self.setup_status_display(targets)
            
            # After redrawing, we need to re-apply the last known status to each widget
            # This is a simplified re-application; a more robust solution might store
            # the last full status update message and re-run it.
            for original_string, widgets in self.status_widgets.items():
                # This is a visual refresh of names, not a full status update.
                # The next ping cycle will bring the correct colors and states.
                pass
