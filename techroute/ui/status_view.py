"""
Status list creation and updates for TechRoute UI.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, Optional, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..controller import TechRouteController

from .types import create_indicator_button, AppUIProtocol
from ..checkers import get_udp_service_registry

class StatusViewMixin(AppUIProtocol):
    def __init__(self):
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.group_frames: Dict[str, ttk.LabelFrame] = {}
        # This will be properly initialized by AppUI
        self._: Callable[[str], str] = lambda s: s
        self.controller: Optional['TechRouteController'] = None
        super().__init__()

    def update_status_bar(self, message: str):
        self.status_bar_label.config(text=message)

    def setup_status_display(self, targets: List[Dict[str, Any]]):
        """
        Creates or updates status widgets for each target, grouped by status.
        """
        if not self.controller:
            return

        # Clear existing widgets
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()
        self.group_frames.clear()

        if not targets:
            # Display a placeholder if there are no targets
            placeholder_frame = ttk.Frame(self.status_frame, height=60)
            placeholder_frame.pack(pady=10, padx=10, fill=tk.X, expand=True)
            placeholder_label = ttk.Label(placeholder_frame, text=self._("Waiting for targets..."), foreground="gray")
            placeholder_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            return

        # Create UI elements for each target directly in the main status frame
        for target_info in targets:
            self._create_target_row(self.status_frame, target_info)

    def _create_target_row(self, parent: ttk.Frame, target_info: Dict[str, Any]):
        """Creates a single row of widgets for a target."""
        if not self.controller:
            return

        original_string = target_info['original_string']
        
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, expand=True, pady=2)

        # Ping button (latency/status indicator)
        ping_button = tk.Button(
            row_frame, text="PING", width=5, bg="gray", fg="white",
            disabledforeground="white", relief="raised", borderwidth=1,
            state=tk.DISABLED, cursor=""
        )
        ping_button.pack(side=tk.LEFT, padx=(0, 10))

        # Port/Service indicators frame
        port_frame = ttk.Frame(row_frame)
        port_frame.pack(side=tk.RIGHT, padx=(5, 0))

        # Main label
        label = ttk.Label(row_frame, text=f"{self.controller.parser.extract_host(original_string)}: {self._('Pinging...')}")
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create placeholders for all potential ports
        port_widgets = {}
        udp_widgets = {}
        readability = self.controller.config.get('tcp_port_readability', 'Numbers')
        service_map = self.controller.config.get('port_service_map', {})
        all_tcp_ports = self.controller.parser.default_ports
        
        for port in all_tcp_ports:
            display_text = str(port)
            if readability == 'Simple':
                display_text = service_map.get(str(port), str(port))
            port_button = create_indicator_button(port_frame, display_text, False, is_placeholder=True)
            port_button.pack(side=tk.LEFT, padx=2)
            port_widgets[str(port)] = port_button

        if self.controller and self.controller.service_checker.checkers:
            # Add a separator if there are also TCP ports
            if all_tcp_ports:
                sep = ttk.Separator(port_frame, orient=tk.VERTICAL)
                sep.pack(side=tk.LEFT, padx=5, fill=tk.Y)

            # Sort checkers in desired order: mDNS, SNMP, WS-Discovery, SLP
            sorted_checkers = sorted(
                self.controller.service_checker.checkers,
                key=lambda c: ["mDNS", "SNMP", "WS-Discovery", "SLP"].index(c.name)
            )
            for checker in sorted_checkers:
                udp_btn = create_indicator_button(port_frame, checker.name, False, is_placeholder=True, is_udp=True)
                udp_btn.pack(side=tk.LEFT, padx=2)
                udp_widgets[checker.name] = udp_btn

        self.status_widgets[original_string] = {
            "row_frame": row_frame,
            "label": label,
            "ping_button": ping_button,
            "port_widgets": port_widgets,
            "udp_widgets": udp_widgets,
            "group_frame": parent,
            "status": self._('Pinging...')
        }
        
        # Immediately update the row with the actual initial data
        self.update_target_row(target_info)

    def update_target_row(self, target_info: Dict[str, Any]):
        """Updates a single row of widgets for a target with new data."""
        if not self.controller:
            return

        original_string = target_info['original_string']
        widgets = self.status_widgets.get(original_string)
        if not widgets:
            return  # Should not happen if rows are created correctly

        status = target_info.get('status', self._('Pinging...'))
        color = target_info.get('color', 'gray')
        latency_str = target_info.get('latency_str', '')
        web_port_open = target_info.get('web_port_open', False)
        port_statuses = target_info.get('port_statuses')
        udp_service_statuses = target_info.get('udp_service_statuses')

        # Update Ping Button
        if status == self._("Online"):
            ping_button_text = latency_str
        elif status == self._("Offline"):
            ping_button_text = self._("FAIL")
        else:
            ping_button_text = self._("PING")
        widgets['ping_button'].config(
            text=ping_button_text, bg=color,
            state=tk.NORMAL if web_port_open else tk.DISABLED,
            cursor="hand2" if web_port_open else "",
            command=lambda s=original_string: self.controller.launch_single_web_ui(s) if self.controller else None
        )

        # Update Main Label
        widgets['label'].config(text=f"{self.controller.parser.extract_host(original_string)}: {status}")

        # Update TCP Port Buttons
        if port_statuses:
            readability = self.controller.config.get('tcp_port_readability', 'Numbers')
            service_map = self.controller.config.get('port_service_map', {})
            for port, port_status in port_statuses.items():
                port_button = widgets['port_widgets'].get(str(port))
                if port_button:
                    is_open = (port_status == "Open")
                    display_text = str(port)
                    if readability == 'Simple':
                        display_text = service_map.get(str(port), str(port))
                    
                    port_button.config(text=display_text, bg="#4CAF50" if is_open else "#F44336", state=tk.NORMAL)
                    if int(port) in [80, 443, 8080]:
                        port_button.config(
                            state=tk.NORMAL if is_open else tk.DISABLED,
                            cursor="hand2" if is_open else "",
                            command=lambda s=original_string, p=int(port): self.controller.launch_web_ui_for_port(s, p) if self.controller else None
                        )

        # Update UDP Service Buttons
        if udp_service_statuses and self.controller:
            for checker in self.controller.service_checker.checkers:
                svc_name = checker.name
                udp_btn = widgets['udp_widgets'].get(svc_name)
                if udp_btn:
                    svc_status = udp_service_statuses.get(svc_name)
                    if svc_status:
                        is_open = (svc_status == "Open")
                        udp_btn.config(bg="#2196F3" if is_open else "#FF9800", state=tk.NORMAL)
                    else:
                        udp_btn.config(bg="gray", state=tk.DISABLED)
