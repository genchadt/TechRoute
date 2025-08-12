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

    # Local services indicators (by port number)
    local_service_indicators: Dict[int, tk.Button]
    _local_service_ports: List[int]

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

    # Cross-mixin methods referenced from other mixins
    def update_status_bar(self, message: str) -> None: ...
    def setup_status_display(self, targets: List[Dict[str, Any]]) -> None: ...
    def _open_ports_dialog(self) -> None: ...
    def _open_udp_services_dialog(self) -> None: ...
    def _open_settings_dialog(self) -> None: ...
    def _center_dialog(self, dialog: tk.Toplevel, width: int, height: int) -> None: ...
    def update_status_in_gui(self, original_string: str, status: str, color: str, port_statuses: Optional[Dict[int, str]], latency_str: str, web_port_open: bool, udp_service_statuses: Optional[Dict[str, str]]) -> None: ...

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
    def _toggle_status_scrollbar(self) -> None: ...
    # Network info updater
    def update_network_info(self, info: Dict[str, Any]) -> None: ...
    # Window sizing helper
    def shrink_to_fit(self) -> None: ...
    def lock_min_size_to_current(self) -> None: ...
    def refresh_ui_for_settings_change(self) -> None: ...


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
