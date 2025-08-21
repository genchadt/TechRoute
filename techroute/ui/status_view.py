"""
Status list creation and updates for TechRoute UI.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, TYPE_CHECKING, Callable, Optional

from .widgets.utils import create_indicator_button
from .styling import TCP_OPEN_COLOR, TCP_CLOSED_COLOR, UDP_OPEN_COLOR, UDP_CLOSED_COLOR, DEFAULT_INDICATOR_COLOR

if TYPE_CHECKING:
    from .protocols import AppUIProtocol


class StatusViewMixin:
    def __init__(self: 'AppUIProtocol', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.group_frames: Dict[str, ttk.LabelFrame] = {}
        self._: Callable[[str], str] = lambda s: s

    def update_status_bar(self: 'AppUIProtocol', message: str):
        self.status_bar_label.config(text=message)

    def setup_status_display(self: 'AppUIProtocol', targets: List[Dict[str, Any]]):
        """
        Creates or updates status widgets for each target, grouped by status.
        """
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
            self.add_target_row(target_info)

    # --------------------------- Settings Refresh ---------------------------
    def refresh_status_rows_for_settings(self: 'AppUIProtocol'):
        """Update existing rows after settings (readability/language) changed.

        Avoids discarding current status by re-deriving label/port texts.
        """
        readability = self.actions.get_config().get('tcp_port_readability', 'Numbers')
        service_map = self.actions.get_config().get('port_service_map', {})

        for original_string, widgets in self.status_widgets.items():
            # Re-translate status text (widgets['status'] stores last raw status string)
            # We use controller data if available to get up-to-date info.
            # Acquire latest record from ping manager
            latest = None
            all_targets = self.actions.get_all_targets_with_status()
            for t in all_targets:
                if t.get('original_string') == original_string:
                    latest = t
                    break
            if latest:
                status = latest.get('status', widgets.get('status', ''))
                widgets['label'].config(text=f"{self.actions.extract_host(original_string)}: {status}")
                # Update TCP port buttons readability preserving color/background
                port_statuses = latest.get('port_statuses') or {}
                for port, btn in widgets.get('port_widgets', {}).items():
                    display_text = port
                    if readability == 'Simple':
                        display_text = service_map.get(str(port), str(port))
                    btn.config(text=display_text)
                # UDP services keep their names; nothing to change
        # Also update placeholder frame (if any) translation
        if not self.status_widgets:
            for child in self.status_frame.winfo_children():
                if isinstance(child, ttk.Frame):
                    for lab in child.winfo_children():
                        if isinstance(lab, ttk.Label):
                            try:
                                lab.config(text=self._("Waiting for targets..."))
                            except Exception:
                                pass

    def add_target_row(self: 'AppUIProtocol', target_info: Dict[str, Any]):
        """Creates a single row of widgets for a target."""
        parent = self.status_frame

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
        label = ttk.Label(row_frame, text=f"{self.actions.extract_host(original_string)}: {self._('Pinging...')}")
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create placeholders for all potential ports
        port_widgets = {}
        udp_widgets = {}
        readability = self.actions.get_config().get('tcp_port_readability', 'Numbers')
        service_map = self.actions.get_config().get('port_service_map', {})
        all_tcp_ports = self.actions.get_config().get('default_ports_to_check', [])
        
        for port in all_tcp_ports:
            display_text = str(port)
            if readability == 'Simple':
                display_text = service_map.get(str(port), str(port))
            port_button = create_indicator_button(port_frame, display_text)
            port_button.pack(side=tk.LEFT, padx=1)
            port_widgets[str(port)] = port_button

        if self.actions and self.actions.get_service_checkers():
            if all_tcp_ports:
                sep = ttk.Separator(port_frame, orient=tk.VERTICAL)
                sep.pack(side=tk.LEFT, padx=5, fill=tk.Y)

            sorted_checkers = sorted(
                self.actions.get_service_checkers(),
                key=lambda c: ["mDNS", "SNMP", "WS-Discovery", "SLP"].index(c.name)
            )
            for checker in sorted_checkers:
                udp_btn = create_indicator_button(port_frame, checker.name)
                udp_btn.pack(side=tk.LEFT, padx=1)
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

    def update_target_row(self: 'AppUIProtocol', target_info: Dict[str, Any]):
        """Updates a single row of widgets for a target with new data."""
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
            command=lambda s=original_string: self.launch_single_web_ui(s)
        )

        # Update Main Label
        widgets['label'].config(text=f"{self.actions.extract_host(original_string)}: {status}")

        # Update TCP Port Buttons
        if port_statuses:
            readability = self.actions.get_config().get('tcp_port_readability', 'Numbers')
            service_map = self.actions.get_config().get('port_service_map', {})
            for port, port_status in port_statuses.items():
                port_button = widgets['port_widgets'].get(str(port))
                if port_button:
                    is_open = (port_status == "Open")
                    display_text = str(port)
                    if readability == 'Simple':
                        display_text = service_map.get(str(port), str(port))
                    
                    port_button.config(text=display_text, bg=TCP_OPEN_COLOR if is_open else TCP_CLOSED_COLOR, state=tk.NORMAL)
                    if int(port) in [80, 443, 8080]:
                        port_button.config(
                            state=tk.NORMAL if is_open else tk.DISABLED,
                            cursor="hand2" if is_open else "",
                            command=lambda s=original_string, p=int(port): self.launch_web_ui_for_port(s, p)
                        )

        # Update UDP Service Buttons
        if udp_service_statuses:
            for checker in self.actions.get_service_checkers():
                svc_name = checker.name
                udp_btn = widgets['udp_widgets'].get(svc_name)
                if udp_btn:
                    svc_status = udp_service_statuses.get(svc_name)
                    if svc_status:
                        is_open = (svc_status == "Open")
                        # Use a different color scheme for UDP services
                        udp_btn.config(bg=UDP_OPEN_COLOR if is_open else UDP_CLOSED_COLOR, state=tk.NORMAL)
                    else:
                        udp_btn.config(bg=DEFAULT_INDICATOR_COLOR, state=tk.DISABLED)
