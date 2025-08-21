"""
UI component for the TechRoute application.

Defines the AppUI class, composed from mixins, responsible for building
and managing all Tkinter widgets for the main application window.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional, TYPE_CHECKING, List

from .menu import MenuMixin
from .dialogs import DialogsMixin
from .animations import AnimationsMixin
from .status_view import StatusViewMixin
from .widgets import NetworkInfoPanel, TargetInputPanel, StatusBar
from .types import AppState, StatusUpdatePayload, NetworkInfoPayload
from ..events import AppActions, AppStateModel
from ..network import open_browser_with_url

if TYPE_CHECKING:
    from typing import Callable


class AppUI(
    MenuMixin, 
    DialogsMixin, 
    AnimationsMixin, 
    StatusViewMixin
):
    """Manages the user interface of the TechRoute application."""

    def __init__(self, root: tk.Tk, actions: AppActions, state: AppStateModel, translator: Callable[[str], str]):
        """Initializes the UI and connects it to the controller."""
        super().__init__()
        self.root = root
        self.actions = actions
        self.state = state
        self._ = translator
        self._config = {} # Will be populated by controller state later
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.group_frames: Dict[str, ttk.LabelFrame] = {}
        self.blinking_animation_job: Optional[str] = None
        self.ping_animation_job: Optional[str] = None
        self.animation_job: Optional[str] = None
        self._is_blinking: bool = False
        self._is_pinging: bool = False
        
        self._create_widgets()
        self._setup_menu(translator)
        self._setup_ui_base()
        
        self._setup_ui_controller_dependent()

        self.setup_status_display([])
        self.root.update_idletasks()
        self.shrink_to_fit()
        self._periodic_network_update()
        
    def _create_widgets(self):
        """Create all the widgets for the UI."""
        self.main_frame = ttk.Frame(self.root)
        self.status_bar = StatusBar(self.root, self._)
        self.status_indicator = self.status_bar.status_indicator
        self.status_bar_label = self.status_bar.status_label
        self.controls_frame = ttk.Frame(self.main_frame)
        self.network_info_panel = NetworkInfoPanel(self.main_frame, self._)
        self.target_input_panel = TargetInputPanel(self.main_frame, self._)
        self.status_container = ttk.LabelFrame(self.main_frame, text=self._("Status"))
        self.status_canvas = tk.Canvas(self.status_container, borderwidth=0, highlightthickness=0)
        self.status_scrollbar = ttk.Scrollbar(self.status_container, orient="vertical", command=self.status_canvas.yview)
        self.status_frame = ttk.Frame(self.status_container)
        
        self.ip_entry = self.target_input_panel.ip_entry
        self.start_stop_button = self.target_input_panel.start_stop_button
        self.launch_all_button = self.target_input_panel.launch_all_button
        self.clear_statuses_button = self.target_input_panel.clear_statuses_button
        self.add_localhost_button = self.target_input_panel.add_localhost_button
        self.add_gateway_button = self.target_input_panel.add_gateway_button
        self.clear_field_button = self.target_input_panel.clear_field_button
        
        self.menu_bar = tk.Menu(self.root)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.theme_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.language_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.tcp_port_readability_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.theme_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self.tcp_port_readability_var = tk.StringVar()
        
        self.about_button = ttk.Button(self.help_menu)
        self.github_button = ttk.Button(self.help_menu)
        self.settings_button = ttk.Button(self.settings_menu)
        self.exit_button = ttk.Button(self.file_menu)

    # ------------------- Callback Handlers from Controller -------------------

    def on_state_change(self, new_state: AppState):
        """Reacts to application state changes from the controller."""
        self.target_input_panel.set_state("normal" if new_state == AppState.IDLE else "disabled")

        if new_state == AppState.IDLE:
            self.start_stop_button.config(text=self._("Start Pinging"))
            self.update_status_bar(self._("Pinging stopped."))
            self.reset_status_indicator()
            self.setup_status_display(self.actions.get_all_targets_with_status())
        elif new_state == AppState.CHECKING:
            self.start_stop_button.config(text=self._("Stop Pinging"))
            self.update_status_bar(self._("Checking targets..."))
            self.start_blinking_animation()
        elif new_state == AppState.PINGING:
            self.start_stop_button.config(text=self._("Stop Pinging"))
            self.update_status_bar(self._("Pinging targets..."))
            self.run_ping_animation(self.actions.get_polling_rate_ms())
        elif new_state == AppState.STOPPING:
            self.update_status_bar(self._("Stopping..."))

    def on_status_update(self, updates: List[StatusUpdatePayload]):
        """Handles status updates from the controller for multiple targets."""
        for target_info in updates:
            if target_info['original_string'] in self.status_widgets:
                self.update_target_row(target_info)
            else:
                self.add_target_row(target_info)
        
        if any(s.get('web_port_open') for s in self.actions.get_all_targets_with_status()):
            self.launch_all_button.config(state=tk.NORMAL)
        else:
            self.launch_all_button.config(state=tk.DISABLED)

    def on_initial_statuses_loaded(self, statuses: List[Dict[str, Any]]):
        """Receives the initial list of targets to display."""
        self.setup_status_display(statuses)

    def on_bulk_status_update(self, statuses: List[Dict[str, Any]]):
        """Handles a bulk update of all statuses, typically after a check."""
        self.setup_status_display(statuses)
        if any(s.get('web_port_open') for s in statuses):
            self.launch_all_button.config(state=tk.NORMAL)
        else:
            self.launch_all_button.config(state=tk.DISABLED)

    def on_network_info_update(self, info: NetworkInfoPayload):
        """Handles network information updates."""
        self.network_info_panel.update_info(info)

    # ------------------- UI Event Handlers -------------------

    def toggle_ping_process(self):
        """Sends a command to the controller to start or stop pinging."""
        try:
            polling_rate_ms = int(self.polling_rate_entry.get())
            ip_string = self.target_input_panel.get_text()
            
            if self.actions.get_state() == AppState.IDLE and not ip_string:
                messagebox.showerror(self._("Input Required"), self._("Please enter at least one IP address or hostname."))
                return

            self.actions.toggle_ping_process(ip_string, polling_rate_ms)
        except ValueError as e:
            messagebox.showerror(self._("Invalid Target"), str(e))

    def _update_ping_process(self):
        """Stops the current process and starts a new one."""
        if self.actions.get_state() != AppState.IDLE:
            self.stop_ping_process()
            self.root.after(150, self.toggle_ping_process)
        else:
            self.toggle_ping_process()

    def stop_ping_process(self):
        """Stops the active ping process."""
        self.actions.stop_ping_process()

    def _clear_statuses(self):
        """Stops any active process and clears the status display."""
        if self.actions.get_state() != AppState.IDLE:
            self.stop_ping_process()
            
        self.setup_status_display([])
        self.launch_all_button.config(state=tk.DISABLED)
        self.update_status_bar(self._("Statuses cleared."))
        self.reset_status_indicator()

    def launch_single_web_ui(self, original_string: str, port: Optional[int] = None):
        """Launches the web UI for a single, specific target.
        
        Note: This method does NOT show a security warning. The caller is
        responsible for that.
        """
        url = self.actions.get_web_ui_url(original_string, port)
        if url:
            open_browser_with_url(url, self.actions.get_browser_command())

    def launch_all_web_uis(self):
        """Launches web UIs for all targets with open web ports."""
        if not self._show_unsecure_browser_warning():
            return
        
        urls = self.actions.get_all_web_ui_urls()
        for url in urls:
            open_browser_with_url(url, self.actions.get_browser_command())

    def launch_web_ui_for_port(self, original_string: str, port: int):
        """Launches a web UI for a specific IP and port."""
        self.launch_single_web_ui(original_string, port)

    def get_web_ui_url(self, original_string: str, port: Optional[int] = None) -> Optional[str]:
        """Gets web UI URL for a target."""
        return self.actions.get_web_ui_url(original_string, port)

    def get_all_web_ui_urls(self) -> List[str]:
        """Gets all available web UI URLs."""
        return self.actions.get_all_web_ui_urls()

    # ------------------- Boilerplate and Helpers -------------------

    def _setup_ui_base(self):
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(3, weight=1)
        self.controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.controls_frame.columnconfigure(1, weight=1)
        self.network_info_panel.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.target_input_panel.grid(row=2, column=0, sticky="ew")
        self.status_container.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self.status_container.rowconfigure(0, weight=1)
        self.status_container.columnconfigure(0, weight=1)
        self.status_canvas.grid(row=0, column=0, sticky="nsew")
        self.status_scrollbar.grid(row=0, column=1, sticky="ns")
        self.status_canvas.config(yscrollcommand=self.status_scrollbar.set)
        self.status_frame_window = self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")
        self.status_scrollbar.grid_remove()
        self.status_frame.bind("<Configure>", self._on_status_frame_configure)
        self.status_canvas.bind("<Configure>", self._on_canvas_configure)

    def _setup_ui_controller_dependent(self):
        left_controls_frame = ttk.Frame(self.controls_frame)
        left_controls_frame.grid(row=0, column=0, sticky="w")
        
        ttk.Label(left_controls_frame, text=self._("Polling Rate (ms):")).pack(side=tk.LEFT, padx=(0, 5))
        self.polling_rate_entry = ttk.Entry(left_controls_frame, width=5)
        self.polling_rate_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.polling_rate_entry.insert(0, str(self.actions.get_polling_rate_ms()))
        
        self.ports_button = ttk.Button(left_controls_frame, text=self._("Ports..."), command=self._open_ports_dialog)
        self.ports_button.pack(side=tk.LEFT)
        
        self.services_button = ttk.Button(left_controls_frame, text=self._("UDP Services..."), command=self._open_udp_services_dialog)
        self.services_button.pack(side=tk.LEFT, padx=(8, 0))

        right_controls_frame = ttk.Frame(self.controls_frame)
        right_controls_frame.grid(row=0, column=2, sticky="e")
        
        self.update_button = ttk.Button(right_controls_frame, text=self._("Update"), command=self._update_ping_process)
        self.update_button.pack()

        self.config = self.actions.get_config()
        self.network_info_panel.setup_local_services(self.config)
        
        tip = self.target_input_panel
        tip.add_localhost_button.config(command=self._add_localhost_to_input)
        tip.add_gateway_button.config(command=self._add_gateway_to_input)
        tip.clear_field_button.config(command=self._clear_input_field)
        tip.start_stop_button.config(command=self.toggle_ping_process)
        tip.launch_all_button.config(command=self.launch_all_web_uis)
        tip.clear_statuses_button.config(command=self._clear_statuses)

    def _periodic_network_update(self):
        if self.actions:
            self.actions.process_network_updates()
        self.root.after(250, self._periodic_network_update)

    def _add_localhost_to_input(self):
        self._append_unique_line_to_ip_entry("127.0.0.1")

    def _add_gateway_to_input(self):
        gateway_ip = self.actions.get_gateway_ip()
        if gateway_ip:
            self._append_unique_line_to_ip_entry(gateway_ip)
        else:
            self.update_status_bar(self._("Gateway not detected."))

    def _clear_input_field(self):
        if self.target_input_panel.ip_entry.cget('state') != tk.NORMAL:
            return
        self.target_input_panel.clear()

    def _append_unique_line_to_ip_entry(self, value: str):
        if self.target_input_panel.ip_entry.cget('state') != tk.NORMAL:
            return
        
        content = self.target_input_panel.get_text()
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        
        # This is a temporary hack until the parser is available via an action
        # if any(self.actions.parser.extract_host(line) == value for line in lines):
        #     return
        
        self.target_input_panel.append_line(value)

    @property
    def config(self) -> Dict[str, Any]:
        """Application configuration dictionary."""
        return self._config

    @config.setter
    def config(self, value: Dict[str, Any]):
        """Sets the application configuration."""
        self._config = value
        self.refresh_ui()

    def refresh_ui(self):
        self.network_info_panel.refresh_for_settings_change(self._config)
        self.refresh_status_rows_for_settings()

    def _on_canvas_configure(self, event: tk.Event):
        self.status_canvas.itemconfig(self.status_frame_window, width=event.width)

    def _on_status_frame_configure(self, event: tk.Event):
        self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all"))
        self.root.after_idle(self._toggle_status_scrollbar)

    def update_status_bar(self, message: str):
        self.status_bar.update_status(message)

    def _toggle_status_scrollbar(self):
        self.status_frame.update_idletasks()
        frame_height = self.status_frame.winfo_reqheight()
        canvas_height = self.status_canvas.winfo_height()
        self.status_scrollbar.grid() if frame_height > canvas_height else self.status_scrollbar.grid_remove()

    def shrink_to_fit(self):
        self.root.update_idletasks()
        self.root.geometry(f"{self.root.winfo_reqwidth()}x{self.root.winfo_reqheight()}")

    @property
    def main_app(self) -> AppUI:
        """Returns the main application instance."""
        return self
