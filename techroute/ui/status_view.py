"""
Status list creation and updates for TechRoute UI.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from .types import create_indicator_button, AppUIProtocol
from ..checkers import get_udp_service_registry

class StatusViewMixin(AppUIProtocol):
    def update_status_bar(self, message: str):
        self.status_bar_label.config(text=message)

    def setup_status_display(self, targets: List[Dict[str, Any]]):
        """
        Creates status widgets for each target or a placeholder if the list is empty.
        """
        if not self.controller:
            return

        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()

        if not targets:
            placeholder = ttk.Label(self.status_frame, text="Waiting for targets...", foreground="gray")
            placeholder.pack(pady=10, padx=10)
            return

        for target in targets:
            original_string, ports = target['original_string'], target['ports']

            row_frame = ttk.Frame(self.status_frame)
            row_frame.pack(fill=tk.X, expand=True, pady=2)
            row_frame.columnconfigure(1, weight=1)

            ping_button = tk.Button(
                row_frame,
                text="",
                width=5,
                bg="gray",
                fg="white",
                disabledforeground="white",
                relief="raised",
                borderwidth=1,
                state=tk.DISABLED,
                command=lambda s=original_string: self.controller.launch_single_web_ui(s) if self.controller else None,
            )
            ping_button.grid(row=0, column=0, padx=(0, 10), sticky='w')

            label = ttk.Label(row_frame, text=f"{original_string}: Pinging...")
            label.grid(row=0, column=1, sticky='w')

            port_frame = ttk.Frame(row_frame)
            port_frame.grid(row=0, column=2, sticky='e')

            port_widgets = {}
            if ports:
                readability = self.controller.config.get('tcp_port_readability', 'Numbers')
                service_map = self.controller.config.get('port_service_map', {})
                for port in ports:
                    display_text = str(port)
                    if readability == 'Simple':
                        display_text = service_map.get(str(port), str(port))
                    port_button = create_indicator_button(port_frame, display_text)
                    port_button.pack(side=tk.LEFT, padx=2)

                    if port in [80, 443]:
                        port_button.config(
                            command=lambda s=original_string, p=port: self.controller.launch_web_ui_for_port(s, p) if self.controller else None
                        )
                    port_widgets[port] = port_button

            udp_widgets: Dict[str, tk.Button] = {}
            try:
                udp_ports_cfg = self.controller.config.get('udp_services_to_check', []) or []
                if udp_ports_cfg:
                    registry = get_udp_service_registry()
                    for udp_port in udp_ports_cfg:
                        entry = registry.get(int(udp_port))
                        if not entry:
                            continue
                        service_name, _checker = entry
                        # UDP services are always displayed by name, not port number
                        udp_btn = create_indicator_button(port_frame, service_name)
                        udp_btn.pack(side=tk.LEFT, padx=2)
                        udp_widgets[service_name] = udp_btn
            except Exception:
                pass

            self.status_widgets[original_string] = {
                "label": label,
                "ping_button": ping_button,
                "port_widgets": port_widgets,
                "udp_widgets": udp_widgets,
            }
