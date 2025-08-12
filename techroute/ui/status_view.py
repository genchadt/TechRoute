"""
Status list creation and updates for TechRoute UI.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, Optional, TYPE_CHECKING, cast
from .types import UIContext
from ..checkers import get_udp_service_registry

if TYPE_CHECKING:
    from ..app import TechRouteApp


class StatusViewMixin:
    app_controller: "TechRouteApp"

    def update_status_bar(self: UIContext, message: str):
        self.status_bar_label.config(text=message)

    def setup_status_display(self: UIContext, targets: List[Dict[str, Any]]):
        """
        Creates status widgets for each target or a placeholder if the list is empty.
        """
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()

        if not targets:
            # Add a simple label as a placeholder. The layout management will handle sizing.
            placeholder = ttk.Label(self.status_frame, text="Waiting for targets...", foreground="gray")
            placeholder.pack(pady=10, padx=10)
            return

        for target in targets:
            original_string, ports = target['original_string'], target['ports']

            # Use a Frame for each entry row
            row_frame = ttk.Frame(self.status_frame)
            row_frame.pack(fill=tk.X, expand=True, pady=2)
            row_frame.columnconfigure(1, weight=1)  # Allow the label to expand

            # This button will show ping status and be clickable to open the UI
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
                command=lambda s=original_string: self.app_controller.launch_single_web_ui(s),
            )
            ping_button.grid(row=0, column=0, padx=(0, 10), sticky='w')

            # Main label for the IP address and status
            label = ttk.Label(row_frame, text=f"{original_string}: Pinging...")
            label.grid(row=0, column=1, sticky='w')

            # Frame to hold TCP port status labels and UDP service labels
            port_frame = ttk.Frame(row_frame)
            port_frame.grid(row=0, column=2, sticky='e')

            port_widgets = {}
            if ports:
                readability = self.app_controller.config.get('port_readability', 'Numbers')
                service_map = self.app_controller.config.get('port_service_map', {})
                for port in ports:
                    display_text = str(port)
                    if readability == 'Simple':
                        display_text = service_map.get(str(port), str(port))
                    # Create a button for each port. It will be enabled/disabled based on status.
                    port_button = tk.Button(
                        port_frame,
                        text=display_text,
                        bg="gray",
                        fg="white",
                        disabledforeground="white",
                        relief="raised",
                        borderwidth=1,
                        state=tk.DISABLED,
                        padx=4,
                        pady=1,
                    )
                    port_button.pack(side=tk.LEFT, padx=2)

                    # Make relevant web ports (80, 443) clickable by assigning a command
                    if port in [80, 443]:
                        port_button.config(
                            command=lambda s=original_string, p=port: self.app_controller.launch_web_ui_for_port(s, p)
                        )

                    port_widgets[port] = port_button

            # UDP services: use service names as labels
            udp_widgets: Dict[str, tk.Button] = {}
            try:
                udp_ports_cfg = self.app_controller.config.get('udp_services_to_check', []) or []
                if udp_ports_cfg:
                    registry = get_udp_service_registry()
                    for udp_port in udp_ports_cfg:
                        entry = registry.get(int(udp_port))
                        if not entry:
                            continue
                        service_name, _checker = entry
                        udp_btn = tk.Button(
                            port_frame,
                            text=service_name,
                            bg="gray",
                            fg="white",
                            disabledforeground="white",
                            relief="raised",
                            borderwidth=1,
                            state=tk.DISABLED,
                            padx=4,
                            pady=1,
                        )
                        udp_btn.pack(side=tk.LEFT, padx=2)
                        udp_widgets[service_name] = udp_btn
            except Exception:
                pass

            self.status_widgets[original_string] = {
                "label": label,
                "ping_button": ping_button,  # Replaces 'indicator' and 'ui_button'
                "port_widgets": port_widgets,
                "udp_widgets": udp_widgets,
            }

    def update_status_in_gui(self: UIContext, original_string: str, status: str, color: str, port_statuses: Optional[Dict[int, str]], latency_str: str, web_port_open: bool, udp_service_statuses: Optional[Dict[str, str]] = None):
        """Updates the GUI widgets for a specific IP. Must be called from the main thread."""
        if original_string in self.status_widgets:
            widgets = self.status_widgets[original_string]
            ip_part = original_string.split(':', 1)[0]

            ping_button = widgets["ping_button"]
            ping_button.config(bg=color, text=latency_str if status == "Online" else "FAIL", fg="white")
            
            # The button is clickable only if a web port is open
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

                        # For relevant web ports, enable the button if the port is open
                        if port in [80, 443]:
                            # Tkinter state must be one of: tk.NORMAL, tk.ACTIVE, or tk.DISABLED
                            port_widget.config(
                                state=(tk.NORMAL if is_open else tk.DISABLED),
                                cursor=("hand2" if is_open else "")
                            )

            # Update UDP service widgets
            if udp_service_statuses:
                udp_widgets = widgets.get("udp_widgets", {})
                for svc_name, svc_status in udp_service_statuses.items():
                    btn = udp_widgets.get(svc_name)
                    if btn is not None:
                        is_open = (svc_status == "Open")
                        btn.config(bg=("green" if is_open else "red"), fg="white")

            # When pinging stops, clear port status text
            elif not self.app_controller.is_pinging:
                port_widgets = widgets.get("port_widgets", {})
                for port, widget in port_widgets.items():
                    widget.config(bg="gray", state=tk.DISABLED, cursor="", fg="white")

                # Reset UDP service widgets as well
                for _name, widget in widgets.get("udp_widgets", {}).items():
                    widget.config(bg="gray", state=tk.DISABLED, cursor="", fg="white")

                # Also reset the ping button explicitly to DISABLED
                ping_button.config(state=tk.DISABLED, bg="gray", text="", cursor="", fg="white")

        else:
            # This can happen if the UI is cleared while a thread is about to send an update.
            # It's safe to just ignore it.
            print(f"Warning: Received status update for '{original_string}' but its UI widget no longer exists.")
