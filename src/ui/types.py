"""
Shared typing utilities for the TechRoute UI package.

Defines a Protocol that captures the cross-mixin surface so static type
checkers understand the attributes/methods available on `self`.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import TechRouteApp


class UIContext(Protocol):
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

    # Inputs and buttons
    polling_rate_entry: ttk.Entry
    ports_button: ttk.Button
    update_button: ttk.Button
    ip_entry: tk.Text
    start_stop_button: ttk.Button
    launch_all_button: ttk.Button
    clear_statuses_button: ttk.Button | None

    # Cross-mixin methods referenced from other mixins
    def show_scrollbar(self) -> None: ...
    def hide_scrollbar(self) -> None: ...
    def setup_status_display(self, targets: List[Dict[str, Any]]) -> None: ...
    def _open_ports_dialog(self) -> None: ...
    def _open_settings_dialog(self) -> None: ...
    # Animation-related cross calls
    def stop_blinking_animation(self) -> None: ...
    def stop_ping_animation(self) -> None: ...
    def reset_status_indicator(self) -> None: ...
    def run_ping_animation(self, polling_rate_ms: int) -> None: ...
    def start_blinking_animation(self) -> None: ...
    def _blink(self) -> None: ...
    # Builder event handlers
    def _on_canvas_configure(self, event: tk.Event) -> None: ...
    def _on_status_frame_configure(self, event: tk.Event) -> None: ...
    # Network info updater
    def update_network_info(self, info: Dict[str, Any]) -> None: ...
    # Window sizing helper
    def shrink_to_fit(self) -> None: ...
    def lock_min_size_to_current(self) -> None: ...
    def _schedule_status_canvas_height_update(self) -> None: ...
    def _update_status_canvas_height(self) -> None: ...
