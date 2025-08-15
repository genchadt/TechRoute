"""
UI component for the TechRoute application.

Defines the AppUI class, composed from mixins, responsible for building
and managing all Tkinter widgets for the main application window.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional, TYPE_CHECKING

from .menu import MenuMixin
from .dialogs import DialogsMixin
from .animations import AnimationsMixin
from .status_view import StatusViewMixin
from ..ping_manager import PingState
from .widgets import NetworkInfoPanel, TargetInputPanel, StatusBar

if TYPE_CHECKING:
    from ..controller import TechRouteController
    from ..app import MainApp
    from typing import Callable


class AppUI(
    MenuMixin, 
    DialogsMixin, 
    AnimationsMixin, 
    StatusViewMixin
):
    """Manages the user interface of the TechRoute application."""

    def __init__(self, root: tk.Tk, main_app_instance: 'MainApp', translator: Callable[[str], str]):
        """Initializes the UI, waiting for the controller to be set."""
        super().__init__()
        self.root = root
        self.main_app = main_app_instance
        self.controller: Optional['TechRouteController'] = None
        self._ = translator
        self.config = {}
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.group_frames: Dict[str, ttk.LabelFrame] = {}
        self.blinking_animation_job = None
        self.ping_animation_job = None
        
        self._create_widgets()
        self._setup_menu(translator)
        self._setup_ui_base()
        
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
        
        # Convenience references
        self.ip_entry = self.target_input_panel.ip_entry
        self.start_stop_button = self.target_input_panel.start_stop_button
        self.launch_all_button = self.target_input_panel.launch_all_button
        self.clear_statuses_button = self.target_input_panel.clear_statuses_button
        self.add_localhost_button = self.target_input_panel.add_localhost_button
        self.add_gateway_button = self.target_input_panel.add_gateway_button
        self.clear_field_button = self.target_input_panel.clear_field_button
        
        # Menu-related widgets
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
        
        # These are buttons within menus, so they don't need a direct parent
        self.about_button = ttk.Button(self.help_menu)
        self.github_button = ttk.Button(self.help_menu)
        self.settings_button = ttk.Button(self.settings_menu)
        self.exit_button = ttk.Button(self.file_menu)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        canvas_width = event.width
        if self.status_frame_window is not None:
            self.status_canvas.itemconfig(self.status_frame_window, width=canvas_width)

    def _on_status_frame_configure(self, event: tk.Event) -> None:
        self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all"))
        self.root.after_idle(self._toggle_status_scrollbar)

    def retranslate_ui(self, translator: Callable[[str], str]):
        """Retranslates all the widgets in the UI."""
        self._ = translator
        
        # Preserve the current targets if they exist
        current_targets = self.controller.get_all_targets_with_status() if self.controller else []

        # Destroy old widgets
        self.main_frame.destroy()
        self.status_bar.destroy()
        
        # Recreate all the widgets
        self._create_widgets()
        self._setup_menu(translator)
        self._setup_ui_base()
        
        if self.controller:
            self._setup_ui_controller_dependent()
            # Restore the status display with the preserved targets
            self.setup_status_display(current_targets)
            self.process_status_update()

    def set_controller(self, controller: 'TechRouteController'):
        """Sets the controller and finalizes UI setup."""
        self.controller = controller
        self.config = controller.config
        
        # Set up callbacks for ping state changes
        self.controller.on_pinging_start = self.on_pinging_start
        self.controller.on_ping_stop = self.on_ping_stop
        self.controller.on_ping_update = self.on_ping_update
        
        self._setup_ui_controller_dependent()
        # Initialize the status display now that we have a controller
        self.setup_status_display([])
        self.root.update_idletasks()
        self.shrink_to_fit()
        self._periodic_network_update()

    def _setup_ui_base(self):
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.main_frame.config(padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(3, weight=1)

        self.controls_frame.config(padding=(0, 0, 0, 10))
        self.controls_frame.grid(row=0, column=0, sticky="ew")
        self.controls_frame.columnconfigure(1, weight=1)

        self.network_info_panel.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.target_input_panel.grid(row=2, column=0, sticky="ew")

        # Grid the scrollable status area using a canvas + scrollbar
        self.status_container.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self.status_container.config(text=self._("Status"), padding="10")
        self.status_container.rowconfigure(0, weight=1)
        self.status_container.columnconfigure(0, weight=1)
        self.status_canvas.config(borderwidth=0, highlightthickness=0)
        self.status_scrollbar.config(orient="vertical", command=self.status_canvas.yview)
        self.status_frame_window = self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")
        self.status_canvas.grid(row=0, column=0, sticky="nsew")
        self.status_scrollbar.grid(row=0, column=1, sticky="ns")
        self.status_canvas.config(yscrollcommand=self.status_scrollbar.set)
        self.status_scrollbar.grid_remove()
        self.status_frame.bind("<Configure>", self._on_status_frame_configure)
        self.status_canvas.bind("<Configure>", self._on_canvas_configure)

        # Build initial placeholder only if controller is set
        if self.controller:
            self.setup_status_display([])

    def _setup_ui_controller_dependent(self):
        if not self.controller: return

        # Clear any existing widgets in the controls_frame
        for widget in self.controls_frame.winfo_children():
            widget.destroy()

        left_controls_frame = ttk.Frame(self.controls_frame)
        left_controls_frame.grid(row=0, column=0, sticky="w")
        
        ttk.Label(left_controls_frame, text=self._("Polling Rate (ms):"), underline=0).pack(side=tk.LEFT, padx=(0, 5))
        self.polling_rate_entry = ttk.Entry(left_controls_frame, width=5)
        self.polling_rate_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.polling_rate_entry.insert(0, str(self.controller.get_polling_rate_ms()))
        
        self.ports_button = ttk.Button(left_controls_frame, text=self._("Ports..."), underline=1, command=self._open_ports_dialog)
        self.ports_button.pack(side=tk.LEFT)
        
        # underline=1 highlights the 'D' in "UDP Services..." so Alt-d can be used.
        self.services_button = ttk.Button(left_controls_frame, text=self._("UDP Services..."), underline=1, command=self._open_udp_services_dialog)
        self.services_button.pack(side=tk.LEFT, padx=(8, 0))

        right_controls_frame = ttk.Frame(self.controls_frame)
        right_controls_frame.grid(row=0, column=2, sticky="e")
        
        self.update_button = ttk.Button(right_controls_frame, text=self._("Update"), underline=0, command=self._update_ping_process)
        self.update_button.pack()

        self.network_info_panel.setup_local_services(self.controller.config)
        
        tip = self.target_input_panel
        tip.add_localhost_button.config(command=self._add_localhost_to_input)
        tip.add_gateway_button.config(command=self._add_gateway_to_input)
        tip.clear_field_button.config(command=self._clear_input_field)
        tip.start_stop_button.config(command=self._toggle_ping_process)
        tip.launch_all_button.config(command=self.controller.launch_all_web_uis)
        tip.clear_statuses_button.config(command=self._clear_statuses)

        self.root.bind("<Control-Return>", lambda event: self._toggle_ping_process())
        self.root.bind("<Alt-s>", lambda event: tip.start_stop_button.invoke())
        self.root.bind("<Alt-l>", lambda event: tip.launch_all_button.invoke())
        self.root.bind("<Alt-o>", lambda e, btn=self.ports_button: btn.invoke())
        self.root.bind("<Alt-d>", lambda e, btn=self.services_button: btn.invoke())
        self.root.bind("<Alt-u>", lambda e, btn=self.update_button: btn.invoke())
        self.root.bind("<Alt-c>", lambda event: tip.clear_statuses_button.invoke())
        self.root.bind("<Alt-a>", lambda event: self._add_localhost_to_input())
        self.root.bind("<Alt-g>", lambda event: self._add_gateway_to_input())
        self.root.bind("<Alt-f>", lambda event: tip.clear_field_button.invoke())
        self.root.bind("<Alt-p>", lambda e, entry=self.polling_rate_entry: entry.focus_set())
        self.root.bind("<Alt-i>", lambda event: tip.ip_entry.focus_set())

    def process_status_update(self, data: Optional[Any] = None):
        """
        Handles status updates from the controller.
        It can process a single update (tuple) or a list of initial targets.
        """
        if not self.controller or not data:
            return

        if isinstance(data, list):
            # Initial setup of all targets
            self.setup_status_display(data)
            return
        
        if isinstance(data, tuple):
            # Unpack a single update message into a dictionary
            keys = ['original_string', 'status', 'color', 'port_statuses', 'latency_str', 'web_port_open', 'udp_service_statuses']
            target_info = dict(zip(keys, data))
            original_string = target_info['original_string']

            if original_string in self.status_widgets:
                self.update_target_row(target_info)
            else:
                # This case might occur if an update arrives before the UI is fully built.
                # A full refresh is a safe fallback.
                all_statuses = self.controller.get_all_targets_with_status()
                self.setup_status_display(all_statuses)

        # Update the "Launch All" button state
        all_statuses = self.controller.get_all_targets_with_status()
        if any(s.get('web_port_open') for s in all_statuses):
            self.target_input_panel.launch_all_button.config(state=tk.NORMAL)
        else:
            self.target_input_panel.launch_all_button.config(state=tk.DISABLED)

    def on_pinging_start(self):
        """Callback for when the ping manager transitions to continuous pinging."""
        self.target_input_panel.start_stop_button.config(text=self._("Stop Pinging"))
        self.target_input_panel.set_state("disabled")
        self.update_status_bar(self._("Pinging targets..."))
        self.on_ping_update() # Start the first ping animation immediately

    def on_ping_stop(self):
        """Callback for when the ping manager stops."""
        self.target_input_panel.start_stop_button.config(text=self._("Start Pinging"))
        self.target_input_panel.set_state("normal")
        self.update_status_bar(self._("Pinging stopped."))
        self.reset_status_indicator()
        # Refresh display to show final state
        if self.controller:
            self.setup_status_display(self.controller.get_all_targets_with_status())

    def on_ping_update(self):
        """Callback for each ping update to re-trigger the animation."""
        if self.controller:
            polling_rate_ms = self.controller.get_polling_rate_ms()
            self.run_ping_animation(polling_rate_ms)

    def _toggle_ping_process(self):
        if not self.controller: return
        
        if self.controller.get_state() != PingState.IDLE:
            self.controller.stop_ping_process()
        else:
            ip_string = self.target_input_panel.get_text()
            if not ip_string:
                messagebox.showerror(self._("Input Required"), self._("Please enter at least one IP address or hostname."))
                return
            try:
                polling_rate_ms = int(self.polling_rate_entry.get())
            except ValueError:
                messagebox.showerror(self._("Invalid Polling Rate"), self._("Polling rate must be a number."))
                return
            
            try:
                self.controller.start_ping_process(ip_string, polling_rate_ms)
            except ValueError as e:
                messagebox.showerror(self._("Invalid Target"), str(e))

    def _update_ping_process(self):
        if not self.controller: return
        if self.controller.get_state() != PingState.IDLE:
            self.controller.stop_ping_process()
            self.root.after(120, self._toggle_ping_process)
        else:
            self._toggle_ping_process()

    def _clear_statuses(self):
        if not self.controller: return
        # Stop any pinging before clearing statuses
        if self.controller.get_state() != PingState.IDLE:
            self.controller.stop_ping_process()
            
        self.setup_status_display([])
        self.controller.web_ui_targets.clear()
        self.target_input_panel.launch_all_button.config(state=tk.DISABLED)
        self.update_status_bar(self._("Statuses cleared."))
        self.reset_status_indicator()

    def _add_localhost_to_input(self):
        self._append_unique_line_to_ip_entry("127.0.0.1")

    def _add_gateway_to_input(self):
        if not self.controller: return
        gateway_ip = self.controller.get_gateway_ip()
        if gateway_ip:
            self._append_unique_line_to_ip_entry(gateway_ip)
        else:
            self.update_status_bar(self._("Gateway not detected."))

    def _clear_input_field(self):
        if self.target_input_panel.ip_entry.cget('state') != tk.NORMAL:
            self.update_status_bar(self._("Input disabled while pinging."))
            return
        self.target_input_panel.clear()
        self.update_status_bar(self._("Input field cleared."))

    def _append_unique_line_to_ip_entry(self, value: str):
        if not self.controller or self.target_input_panel.ip_entry.cget('state') != tk.NORMAL:
            self.update_status_bar(self._("Input disabled while pinging."))
            return
        
        content = self.target_input_panel.get_text()
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        
        normalized_value = '127.0.0.1' if value == 'localhost' else value
        
        for line in lines:
            existing_host = self.controller.parser.extract_host(line)
            normalized_existing = '127.0.0.1' if existing_host == 'localhost' else existing_host
            
            if normalized_value == normalized_existing:
                self.update_status_bar(self._(f"'{value}' is already in the list."))
                return
        
        self.target_input_panel.append_line(value)

    def refresh_ui_for_settings_change(self) -> None:
        if not self.controller: return
        pass

    def _periodic_network_update(self):
        """Periodically checks for network updates from the controller."""
        if self.controller:
            self.controller.process_network_updates()
        self.root.after(250, self._periodic_network_update)

    def update_network_info(self, info: Dict[str, Any]) -> None:
        self.network_info_panel.update_info(info)

    def update_status_bar(self, message: str):
        self.status_bar.update_status(message)

    def _toggle_status_scrollbar(self) -> None:
        try:
            self.status_frame.update_idletasks()
            frame_height, canvas_height = self.status_frame.winfo_reqheight(), self.status_canvas.winfo_height()
            if frame_height > canvas_height: self.status_scrollbar.grid()
            else: self.status_scrollbar.grid_remove()
        except Exception: pass

    def lock_min_size_to_current(self) -> None:
        try:
            self.root.update_idletasks()
            self.root.minsize(self.root.winfo_width(), self.root.winfo_height())
        except Exception: pass

    def shrink_to_fit(self) -> None:
        try:
            self.root.update_idletasks()
            req_w, req_h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
            cur_w, cur_h = max(1, self.root.winfo_width()), max(1, self.root.winfo_height())
            width_percentage = self.controller.config.get('window_settings', {}).get('width_percentage', 100) if self.controller else 100
            width_multiplier = max(50, width_percentage) / 100.0
            new_w, new_h = max(cur_w, int(req_w * width_multiplier)), max(cur_h, req_h)
            try:
                import platform as _platform
                if _platform.system() == "Linux" and not getattr(self, "_resizing_active", False):
                    self.root.geometry(f"{new_w}x{new_h}")
                    self.root.minsize(new_w, new_h)
                    return
            except Exception: pass
            self.root.geometry(f"{new_w}x{new_h}")
        except Exception: pass
