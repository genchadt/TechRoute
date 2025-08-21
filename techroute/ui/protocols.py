"""
UI protocol definitions for TechRoute.
"""
from __future__ import annotations
from typing import Protocol, Dict, Any, Optional, List, TYPE_CHECKING, Callable
from tkinter import ttk

if TYPE_CHECKING:
    from ..controller import TechRouteController
    from ..events import AppActions


class AppUIProtocol(Protocol):
    """
    A formal interface describing the methods and properties that mixins
    and child widgets can expect from the main AppUI class.
    """
    root: Any  # tk.Tk
    status_widgets: Dict[str, Dict[str, Any]]
    group_frames: Dict[str, ttk.LabelFrame]
    status_indicator: Any  # ttk.Label
    status_bar_label: Any  # ttk.Label
    status_frame: Any  # ttk.Frame
    ping_animation_job: Optional[str]
    blinking_animation_job: Optional[str]
    menu_bar: Any  # tk.Menu
    animation_job: Optional[str]
    _is_blinking: bool
    _is_pinging: bool

    @property
    def config(self) -> Dict[str, Any]:
        """Application configuration dictionary."""
        ...
    
    actions: AppActions

    _: Callable[[str], str]

    def update_status_bar(self, message: str) -> None:
        ...

    def run_ping_animation(self, duration_ms: int) -> None:
        ...

    def reset_status_indicator(self) -> None:
        ...

    def start_blinking_animation(self) -> None:
        ...

    def stop_animation(self) -> None:
        ...

    def _blink(self) -> None:
        ...

    def _show_unsecure_browser_warning(self) -> bool:
        ...

    def launch_single_web_ui(self, original_string: str) -> None:
        ...
        
    def launch_web_ui_for_port(self, original_string: str, port: int) -> None:
        ...

    def refresh_ui(self) -> None:
        ...

    def toggle_ping_process(self) -> None:
        """Toggles the ping process on/off."""
        ...

    def stop_ping_process(self) -> None:
        """Stops the active ping process."""
        ...

    def get_web_ui_url(self, original_string: str, port: Optional[int] = None) -> Optional[str]:
        """Gets web UI URL for a target."""
        ...

    def get_all_web_ui_urls(self) -> List[str]:
        """Gets all available web UI URLs."""
        ...

    def add_target_row(self, target_info: Dict[str, Any]) -> None:
        """Adds a new target row to the status display."""
        ...

    def update_target_row(self, target_info: Dict[str, Any]) -> None:
        """Updates a target row in the status display."""
        ...

    def setup_status_display(self, targets: List[Dict[str, Any]]) -> None:
        """Creates or updates status widgets for all targets."""
        ...

    def refresh_status_rows_for_settings(self) -> None:
        """Updates existing rows after settings change."""
        ...

    def _open_settings_dialog(self, on_save: Callable[[Dict, Dict], None]) -> None:
        ...

    @property
    def main_app(self) -> Any:
        ...
