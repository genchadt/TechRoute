"""
UI component for the TechRoute application.

Defines the AppUI class, composed from mixins, responsible for building
and managing all Tkinter widgets for the main application window.
"""
from __future__ import annotations
import ipaddress
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional, TYPE_CHECKING

from .menu import MenuMixin
from .dialogs import DialogsMixin
from .animations import AnimationsMixin
import tkinter.font as tkfont
from .types import create_indicator_button
from ..checkers import get_udp_service_registry
from .status_view import StatusViewMixin
from ..controller import PingState

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

    def _on_canvas_configure(self, event: tk.Event) -> None:
        # When the canvas is configured (e.g., resized), update the width of the frame inside.
        # This ensures the content frame always fills the canvas horizontally.
        canvas_width = event.width
        self.status_canvas.itemconfig(self.status_frame_window, width=canvas_width)

    def _on_status_frame_configure(self, event: tk.Event) -> None:
        # When the content frame's size changes, update the canvas's scroll region.
        # This makes the scrollbar aware of the full content height.
        self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all"))
        # Defer the check to avoid race conditions on widget creation/destruction
        self.root.after_idle(self._toggle_status_scrollbar)
    root: tk.Tk
    status_widgets: Dict[str, Dict[str, Any]]

    blinking_animation_job: Optional[str]
    ping_animation_job: Optional[str]
    clear_statuses_button: Optional[ttk.Button]
    clear_field_button: Optional[ttk.Button]

    def __init__(self, root: tk.Tk, main_app_instance: 'MainApp', translator: Callable[[str], str]):
        """Initializes the UI, waiting for the controller to be set."""
        super().__init__()
        self.root = root
        self.main_app = main_app_instance
        self.controller: Optional['TechRouteController'] = None
        self.status_widgets = {}
        self.blinking_animation_job = None
        self.ping_animation_job = None
        self.clear_statuses_button = None
        self.clear_field_button = None
        self._last_animation_time = 0.0
        self._ = translator

        self._setup_menu(translator)
        self._setup_ui_base()

    def retranslate_ui(self, translator: Callable[[str], str]):
        """Retranslates all the widgets in the UI."""
        self._ = translator
        self._setup_menu(translator)
        self._build_language_menu()
        self._setup_ui_base()
        if self.controller:
            self._setup_ui_controller_dependent()

    def _build_language_menu(self):
        """Builds the language selection menu."""
        if not self.controller:
            return
        self.language_var = tk.StringVar(value=self.controller.config.get('language', 'System'))
        
        # Add "System Default" option
        self.language_menu.add_radiobutton(
            label=self._("System Default"),
            variable=self.language_var,
            value='System',
            command=self._on_language_select
        )
        self.language_menu.add_separator()

        # Add other available languages
        if self.main_app and self.main_app.localization_manager:
            for lang_code in self.main_app.localization_manager.available_languages:
                self.language_menu.add_radiobutton(
                    label=lang_code.upper(), # Replace with full name later
                    variable=self.language_var,
                    value=lang_code,
                    command=self._on_language_select
                )

    def _on_language_select(self):
        """Handles language change and triggers a UI refresh."""
        new_lang = self.language_var.get()
        if self.controller and self.main_app.localization_manager:
            # Update config
            self.controller.config['language'] = new_lang
            self.controller.update_config(self.controller.config)
            
            # Update translator
            self.main_app.localization_manager.set_language(new_lang)
            
            # Retranslate UI
            self.main_app.retranslate_ui()

    def set_controller(self, controller: 'TechRouteController'):
        """Sets the controller and finalizes UI setup."""
        self.controller = controller
        self._setup_ui_controller_dependent()
        self.root.update_idletasks()
        self.shrink_to_fit()

    def _setup_ui_base(self):
        # Status Bar
        self.status_bar_frame = ttk.Frame(self.root)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar_label = ttk.Label(self.status_bar_frame, text=self._("Ready."), relief=tk.SUNKEN, anchor=tk.W, padding=(2, 5))
        self.status_bar_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        mono_font = tkfont.Font(family="Courier", size=10)
        self.status_indicator = ttk.Label(self.status_bar_frame, text="💻 ? ? ? ? ? 📠", relief=tk.SUNKEN, width=15, anchor=tk.CENTER, padding=(5, 5), font=mono_font)
        self.status_indicator.pack(side=tk.RIGHT)

        # Main Frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(3, weight=1)

        # Top Controls Frame
        self.controls_frame = ttk.Frame(self.main_frame, padding=(0, 0, 0, 10))
        self.controls_frame.grid(row=0, column=0, sticky="ew")
        self.controls_frame.columnconfigure(1, weight=1)

        # Network Information Group
        self.network_frame = ttk.LabelFrame(self.main_frame, text=self._("Network Information"), padding="10")
        self.network_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        netgrid = self.network_frame
        ttk.Label(netgrid, text=self._("IPv4:")).grid(row=0, column=0, sticky="w")
        self.netinfo_v4 = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_v4.grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Label(netgrid, text=self._("IPv6:")).grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.netinfo_v6 = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_v6.grid(row=0, column=3, sticky="w", padx=(6, 0))
        ttk.Label(netgrid, text=self._("Gateway:")).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.netinfo_gw = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_gw.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(4, 0))
        ttk.Label(netgrid, text=self._("Subnet Mask:")).grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(4, 0))
        self.netinfo_mask = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_mask.grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(4, 0))

        # Targets Input Group
        self.input_frame = ttk.LabelFrame(self.main_frame, text=self._("Target Browser: Unknown"), padding="10")
        self.input_frame.grid(row=2, column=0, sticky="ew")
        ttk.Label(self.input_frame, text=self._("Enter IPs or Hostnames, one per line")).pack(pady=5)

        # Input text area with scrollbars
        text_frame = ttk.Frame(self.input_frame)
        text_frame.pack(pady=5, fill=tk.X, expand=True)
        self.ip_entry = tk.Text(text_frame, width=60, height=6, wrap="word")
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()
        vscrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=vscrollbar.set)

        # Status Area with optional Scrollbar
        self.status_container = ttk.Frame(self.main_frame)
        self.status_container.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self.status_canvas = tk.Canvas(self.status_container, borderwidth=0, highlightthickness=0)
        self.status_scrollbar = ttk.Scrollbar(self.status_container, orient="vertical", command=self.status_canvas.yview)
        self.status_frame = ttk.LabelFrame(self.status_canvas, text=self._("Status"), padding="10")

        self.status_frame_window = self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")

        # Layout: Use grid to manage canvas and scrollbar
        self.status_container.rowconfigure(0, weight=1)
        self.status_container.columnconfigure(0, weight=1)
        self.status_canvas.grid(row=0, column=0, sticky="nsew")
        self.status_scrollbar.grid(row=0, column=1, sticky="ns")
        self.status_canvas.config(yscrollcommand=self.status_scrollbar.set)

        # Initially hide the scrollbar. It will be shown as needed by _toggle_status_scrollbar
        self.status_scrollbar.grid_remove()

        # Bind events for resizing
        self.status_frame.bind("<Configure>", self._on_status_frame_configure)
        self.status_canvas.bind("<Configure>", self._on_canvas_configure)

        self.setup_status_display([])

    def _setup_ui_controller_dependent(self):
        # Left controls
        left_controls_frame = ttk.Frame(self.controls_frame)
        left_controls_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(left_controls_frame, text=self._("Polling Rate (ms):"), underline=0).pack(side=tk.LEFT, padx=(0, 5))
        self.polling_rate_entry = ttk.Entry(left_controls_frame, width=5)
        self.polling_rate_entry.pack(side=tk.LEFT, padx=(0, 15))
        if self.controller:
            self.polling_rate_entry.insert(0, str(self.controller.get_polling_rate_ms()))
        self.ports_button = ttk.Button(left_controls_frame, text=self._("Ports..."), underline=1, command=self._open_ports_dialog)
        self.ports_button.pack(side=tk.LEFT)
        self.services_button = ttk.Button(left_controls_frame, text=self._("UDP Services..."), underline=0, command=self._open_udp_services_dialog)
        self.services_button.pack(side=tk.LEFT, padx=(8, 0))

        # Right controls
        right_controls_frame = ttk.Frame(self.controls_frame)
        right_controls_frame.grid(row=0, column=2, sticky="e")
        self.update_button = ttk.Button(right_controls_frame, text=self._("Update"), underline=0, command=self._update_ping_process)
        self.update_button.pack()

        # Local services indicators
        ttk.Label(self.network_frame, text=self._("Local Services:")).grid(row=2, column=0, sticky="w", pady=(4, 0))
        local_services_frame = ttk.Frame(self.network_frame)
        local_services_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=(6, 0), pady=(4, 0))
        self._local_service_ports = [20, 21, 22, 445]
        self.local_service_indicators = {}
        
        readability = self.controller.config.get('tcp_port_readability', 'Numbers') if self.controller else 'Numbers'
        service_map = self.controller.config.get('port_service_map', {}) if self.controller else {}

        for p in self._local_service_ports:
            display_text = str(p)
            if readability == 'Simple':
                display_text = service_map.get(str(p), str(p))

            btn = create_indicator_button(local_services_frame, display_text)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.local_service_indicators[p] = btn

        # Add UDP services from config
        udp_ports_cfg = self.controller.config.get('udp_services_to_check', []) if self.controller else []
        if udp_ports_cfg:
            registry = get_udp_service_registry()
            for udp_port in udp_ports_cfg:
                entry = registry.get(int(udp_port))
                if not entry:
                    continue
                service_name, _checker = entry
                btn = create_indicator_button(local_services_frame, service_name)
                btn.pack(side=tk.LEFT, padx=(0, 4))
                self.local_service_indicators[udp_port] = btn
        
        self.root.after(100, self._start_local_services_check)

        # Quick action buttons for input
        quick_row = ttk.Frame(self.input_frame)
        quick_row.pack(pady=(0, 5), fill=tk.X)
        
        left_quick_frame = ttk.Frame(quick_row)
        left_quick_frame.pack(side=tk.LEFT)
        ttk.Button(left_quick_frame, text=self._("Add localhost"), underline=0, command=self._add_localhost_to_input).pack(side=tk.LEFT)
        ttk.Button(left_quick_frame, text=self._("Add Gateway"), underline=4, command=self._add_gateway_to_input).pack(side=tk.LEFT, padx=(5, 0))

        spacer = ttk.Frame(quick_row)
        spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        right_quick_frame = ttk.Frame(quick_row)
        right_quick_frame.pack(side=tk.RIGHT)
        self.clear_field_button = ttk.Button(right_quick_frame, text=self._("Clear Field"), underline=0, command=self._clear_input_field)
        self.clear_field_button.pack()

        # Button Row
        button_frame = ttk.Frame(self.input_frame)
        button_frame.pack(pady=10, fill=tk.X)

        left_button_group = ttk.Frame(button_frame)
        left_button_group.pack(side=tk.LEFT)
        self.start_stop_button = ttk.Button(left_button_group, text=self._("Start Pinging"), underline=0, command=self._toggle_ping_process)
        self.start_stop_button.pack(side=tk.LEFT)
        self.launch_all_button = ttk.Button(left_button_group, text=self._("Launch Web UIs"), underline=0, command=lambda: self.controller.launch_all_web_uis() if self.controller else None, state=tk.DISABLED)
        self.launch_all_button.pack(side=tk.LEFT, padx=(5, 0))

        right_button_group = ttk.Frame(button_frame)
        right_button_group.pack(side=tk.RIGHT)
        clear_statuses_button = ttk.Button(right_button_group, text=self._("Clear Statuses"), underline=0, command=self._clear_statuses)
        clear_statuses_button.pack()
        self.clear_statuses_button = clear_statuses_button

        # Key bindings and mnemonics
        self.root.bind("<Control-Return>", lambda event: self._toggle_ping_process())
        self.root.bind("<Alt-s>", lambda event: self.start_stop_button.invoke())
        self.root.bind("<Alt-l>", lambda event: self.launch_all_button.invoke())
        self.root.bind("<Alt-o>", lambda event: self.ports_button.invoke())
        self.root.bind("<Alt-n>", lambda event: self.services_button.invoke())
        self.root.bind("<Alt-u>", lambda event: self.update_button.invoke())
        self.root.bind("<Alt-c>", lambda event: self._clear_statuses())
        self.root.bind("<Alt-a>", lambda event: self._add_localhost_to_input())
        self.root.bind("<Alt-g>", lambda event: self._add_gateway_to_input())
        self.root.bind("<Alt-f>", lambda event: self.clear_field_button.invoke() if self.clear_field_button else None)
        self.root.bind("<Alt-p>", lambda event: self.polling_rate_entry.focus_set())
        self.root.bind("<Alt-i>", lambda event: self.ip_entry.focus_set())

    def process_status_update(self, message: tuple):
        """Receives a status update message from the controller and updates the UI."""
        if not self.controller:
            return

        # Unpack and update the status row
        original_string, status, color, port_statuses, latency_str, web_port_open, udp_service_statuses = message
        self.update_status_in_gui(
            original_string, status, color, port_statuses, latency_str, web_port_open, udp_service_statuses
        )

        # Enable launch button if a web UI is found
        if web_port_open:
            self.launch_all_button.config(state=tk.NORMAL)

    def update_status_in_gui(self: 'AppUI', original_string: str, status: str, color: str, port_statuses: Optional[Dict[int, str]], latency_str: str, web_port_open: bool, udp_service_statuses: Optional[Dict[str, str]] = None):
        """Updates the GUI widgets for a specific IP. Must be called from the main thread."""
        if not self.controller:
            return

        if original_string in self.status_widgets:
            widgets = self.status_widgets[original_string]
            ip_part = original_string.split(':', 1)[0]

            ping_button = widgets["ping_button"]
            ping_button.config(bg=color, text=latency_str if status == self._("Online") else self._("FAIL"), fg="white")
            
            is_launchable = web_port_open
            ping_button.config(state=tk.NORMAL if is_launchable else tk.DISABLED, 
                               cursor="hand2" if is_launchable else "")

            widgets["label"].config(text=f"{ip_part}: {status}")
            
            if port_statuses:
                port_widgets = widgets.get("port_widgets", {})
                for port, port_status in port_statuses.items():
                    if port in port_widgets:
                        port_widget = port_widgets[port]
                        is_open = (port_status == "Open")
                        port_color = "green" if is_open else "red"
                        port_widget.config(bg=port_color, fg="white")

                        if port in [80, 443]:
                            port_widget.config(
                                state=(tk.NORMAL if is_open else tk.DISABLED),
                                cursor=("hand2" if is_open else "")
                            )

            if udp_service_statuses:
                udp_widgets = widgets.get("udp_widgets", {})
                for svc_name, svc_status in udp_service_statuses.items():
                    btn = udp_widgets.get(svc_name)
                    if btn is not None:
                        is_open = (svc_status == "Open")
                        btn.config(bg=("green" if is_open else "red"), fg="white")

            elif self.controller.state == PingState.IDLE:
                port_widgets = widgets.get("port_widgets", {})
                for port, widget in port_widgets.items():
                    widget.config(bg="gray", state=tk.DISABLED, cursor="", fg="white")

                for _name, widget in widgets.get("udp_widgets", {}).items():
                    widget.config(bg="gray", state=tk.DISABLED, cursor="", fg="white")

                ping_button.config(state=tk.DISABLED, bg="gray", text="", cursor="", fg="white")
        else:
            print(f"Warning: Received status update for '{original_string}' but its UI widget no longer exists.")

    def _toggle_ping_process(self):
        """Handles the Start/Stop button click."""
        if not self.controller:
            return

        if self.controller.state != PingState.IDLE:
            self.controller.stop_ping_process()
            self.start_stop_button.config(text=self._("Start Pinging"), underline=0)
            self.launch_all_button.config(state=tk.DISABLED)
            self.ip_entry.config(state=tk.NORMAL)
            self.update_status_bar(self._("Pinging stopped."))
        else:
            ip_string = self.ip_entry.get("1.0", tk.END).strip()
            if not ip_string:
                messagebox.showerror(self._("Input Required"), self._("Please enter at least one IP address or hostname."))
                return

            try:
                polling_rate_ms = int(self.polling_rate_entry.get())
            except ValueError:
                messagebox.showerror(self._("Invalid Polling Rate"), self._("Polling rate must be a number."))
                return

            try:
                targets = self.controller.parse_and_validate_targets(ip_string) if self.controller else []
                if not targets:
                    return

                self.setup_status_display(targets)
                self.controller.start_ping_process(ip_string, polling_rate_ms)
                self.start_stop_button.config(text=self._("Stop Pinging"), underline=0)
                self.ip_entry.config(state=tk.DISABLED)
                self.update_status_bar(self._("Pinging targets..."))
                
            except ValueError as e:
                messagebox.showerror(self._("Invalid Target"), str(e))

    def _update_ping_process(self):
        """Stops and restarts the pinging process with current settings."""
        if not self.controller:
            return
            
        if self.controller.state != PingState.IDLE:
            # The stop call will trigger a UI update via its callback
            self.controller.stop_ping_process()
            # Schedule a restart
            self.root.after(120, self._toggle_ping_process)
        else:
            self._toggle_ping_process()

    def _clear_statuses(self):
        """Clears the status list and related state."""
        if not self.controller:
            return
        self.setup_status_display([])
        self.controller.web_ui_targets.clear()
        self.launch_all_button.config(state=tk.DISABLED)
        self.update_status_bar(self._("Statuses cleared."))

    def _add_localhost_to_input(self):
        self._append_unique_line_to_ip_entry("127.0.0.1")

    def _add_gateway_to_input(self):
        if not self.controller:
            return
        gateway_ip = self.controller.get_gateway_ip()
        if gateway_ip:
            self._append_unique_line_to_ip_entry(gateway_ip)
        else:
            self.update_status_bar(self._("Gateway not detected."))

    def _clear_input_field(self):
        if str(self.ip_entry.cget('state')) != str(tk.NORMAL):
            self.update_status_bar(self._("Input disabled while pinging."))
            return
        self.ip_entry.delete("1.0", tk.END)
        self.update_status_bar(self._("Input field cleared."))

    def _extract_host_from_line(self, line: str) -> str:
        """Extracts the host from a line, correctly handling IPv4, IPv6, and hostnames."""
        s = line.strip()
        # Case 1: IPv6 with ports, e.g., [fe80::1]:8080
        if s.startswith('[') and ']' in s:
            return s[1:s.find(']')]
        
        # Case 2: Raw IP address (v4 or v6) without ports
        try:
            ipaddress.ip_address(s)
            return s
        except ValueError:
            pass  # Not a raw IP, proceed to next check

        # Case 3: Hostname or IP with ports, e.g., example.com:80 or 192.168.1.1:80
        # This is tricky for raw IPv6, which is why it's handled above.
        # For IPv4 and hostnames, this is safe.
        if ':' in s and '.' in s.split(':', 1)[0]: # Likely IPv4 or FQDN with port
             return s.split(':', 1)[0]
        elif ':' not in s: # No colon, must be a hostname
            return s
        
        # If we're here, it could be a hostname with a colon (unlikely for this app's purpose)
        # or an unbracketed IPv6 with a port. The controller would catch the invalid format,
        # but for UI-side deduplication, we take the part before the first colon.
        return s.split(':', 1)[0]

    def _append_unique_line_to_ip_entry(self, value: str):
        """
        Appends a value as a new unique line to the IP entry, checking for host duplicates.
        """
        if str(self.ip_entry.cget('state')) != str(tk.NORMAL):
            self.update_status_bar(self._("Input disabled while pinging."))
            return
        
        content = self.ip_entry.get("1.0", "end-1c")
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        
        # The value to be added is always a clean host/IP, no need to extract.
        # Normalize it for comparison.
        normalized_value = '127.0.0.1' if value == 'localhost' else value
        
        for line in lines:
            existing_host = self._extract_host_from_line(line)
            normalized_existing = '127.0.0.1' if existing_host == 'localhost' else existing_host
            
            if normalized_value == normalized_existing:
                self.update_status_bar(self._(f"'{value}' is already in the list."))
                return
        
        prefix = "\n" if content and not content.endswith("\n") else ""
        self.ip_entry.insert("end", prefix + value + "\n")
        self.ip_entry.see("end")

    def refresh_ui_for_settings_change(self) -> None:
        """Refreshes UI elements that depend on configuration settings."""
        if not self.controller:
            return
            
        readability = self.controller.config.get('tcp_port_readability', 'Numbers')
        service_map = self.controller.config.get('port_service_map', {})
        for port, button in self.local_service_indicators.items():
            display_text = str(port)
            if readability == 'Simple':
                display_text = service_map.get(str(port), str(port))
            button.config(text=display_text)

        if self.status_widgets:
            targets = [{'original_string': s, 'ports': list(w.get('port_widgets', {}).keys())} for s, w in self.status_widgets.items()]
            self.setup_status_display(targets)

    def update_network_info(self, info: Dict[str, Any]) -> None:
        try:
            v4 = info.get("primary_ipv4") or "n/a"
            v6 = info.get("primary_ipv6") or "n/a"
            gw = info.get("gateway") or "n/a"
            mask = info.get("subnet_mask") or "n/a"
            self.netinfo_v4.config(text=str(v4))
            self.netinfo_v6.config(text=str(v6))
            self.netinfo_gw.config(text=str(gw))
            self.netinfo_mask.config(text=str(mask))
        except Exception:
            pass

    def _toggle_status_scrollbar(self) -> None:
        """Shows or hides the status view scrollbar based on content height."""
        try:
            self.status_frame.update_idletasks()
            frame_height = self.status_frame.winfo_reqheight()
            canvas_height = self.status_canvas.winfo_height()
            if frame_height > canvas_height:
                self.status_scrollbar.grid()
            else:
                self.status_scrollbar.grid_remove()
        except Exception:
            pass

    def lock_min_size_to_current(self) -> None:
        try:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            self.root.minsize(w, h)
        except Exception:
            pass

    def shrink_to_fit(self) -> None:
        try:
            self.root.update_idletasks()
            req_w = self.root.winfo_reqwidth()
            req_h = self.root.winfo_reqheight()
            cur_w = max(1, self.root.winfo_width())
            cur_h = max(1, self.root.winfo_height())
            
            width_percentage = self.controller.config.get('window_settings', {}).get('width_percentage', 100) if self.controller else 100
            width_multiplier = max(50, width_percentage) / 100.0

            new_w = max(cur_w, int(req_w * width_multiplier))
            new_h = max(cur_h, req_h)

            try:
                import platform as _platform
                if _platform.system() == "Linux":
                    if not getattr(self, "_resizing_active", False):
                        self.root.geometry(f"{new_w}x{new_h}")
                    self.root.minsize(new_w, new_h)
                    return
            except Exception:
                pass

            self.root.geometry(f"{new_w}x{new_h}")
        except Exception:
            pass

    def _start_local_services_check(self) -> None:
        """Kick off an asynchronous check of local TCP ports and schedule periodic refreshes."""
        try:
            import threading
            if getattr(self, "_local_services_thread_running", False):
                return
            setattr(self, "_local_services_thread_running", True)

            def _worker():
                try:
                    from .. import network as _net
                    ports = getattr(self, "_local_service_ports", [20, 21, 22, 139, 445])
                    timeout = 0.5
                    results: Dict[int, str] = {}
                    host_v4 = "127.0.0.1"
                    host_v6 = "::1"
                    for p in ports:
                        try:
                            status_v4 = _net.check_tcp_port(host_v4, p, timeout)
                        except Exception:
                            status_v4 = "Closed"
                        try:
                            status_v6 = _net.check_tcp_port(host_v6, p, timeout)
                        except Exception:
                            status_v6 = "Closed"
                        results[p] = ("Open" if (status_v4 == "Open" or status_v6 == "Open") else "Closed")

                    udp_ports_cfg = self.controller.config.get('udp_services_to_check', []) if self.controller else []
                    if udp_ports_cfg:
                        registry = get_udp_service_registry()
                        for udp_port in udp_ports_cfg:
                            entry = registry.get(int(udp_port))
                            if not entry:
                                continue
                            _service_name, checker = entry
                            status = "Closed"
                            try:
                                res_v4 = checker.check(host_v4, timeout=timeout)
                                res_v6 = checker.check(host_v6, timeout=timeout)
                                if (res_v4 and res_v4.available) or (res_v6 and res_v6.available):
                                    status = "Open"
                            except Exception:
                                status = "Closed"
                            results[udp_port] = status

                    def _apply():
                        try:
                            for p, status in results.items():
                                btn = self.local_service_indicators.get(p)
                                if not btn:
                                    continue
                                is_open = (status == "Open")
                                btn.config(bg=("green" if is_open else "red"), fg="white")
                        except Exception:
                            pass
                    try:
                        self.root.after(0, _apply)
                    except Exception:
                        pass
                finally:
                    setattr(self, "_local_services_thread_running", False)
                    try:
                        self.root.after(5000, getattr(self, "_start_local_services_check"))
                    except Exception:
                        pass

            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            try:
                self.root.after(5000, getattr(self, "_start_local_services_check"))
            except Exception:
                pass
