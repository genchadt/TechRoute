"""
Status list creation and updates for TechRoute UI.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, TYPE_CHECKING, Callable

from .widgets.utils import create_indicator_button
from .styling import TCP_OPEN_COLOR, TCP_CLOSED_COLOR, UDP_OPEN_COLOR, UDP_CLOSED_COLOR

if TYPE_CHECKING:
    from .app_ui import AppUI
    from .dialog_manager import DialogManager
    from ..events import AppActions

class StatusViewManager:
    """Manages the status view widgets."""

    def __init__(self, root: tk.Tk, status_frame: ttk.Frame, actions: AppActions, dialog_manager: DialogManager, ui: AppUI, translator: Callable[[str], str]):
        self.root = root
        self.status_frame = status_frame
        self.actions = actions
        self.dialog_manager = dialog_manager
        self.ui = ui
        self._ = translator
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.group_frames: Dict[str, ttk.LabelFrame] = {}

    def setup_status_display(self, targets: List[Dict[str, Any]]):
        """Creates or updates status widgets for each target."""
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()
        self.group_frames.clear()

        if not targets:
            placeholder_frame = ttk.Frame(self.status_frame, height=60)
            placeholder_frame.pack(pady=10, padx=10, fill=tk.X, expand=True)
            placeholder_label = ttk.Label(placeholder_frame, text=self._("Waiting for targets..."), foreground="gray")
            placeholder_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            return

        for target_info in targets:
            self.add_target_row(target_info)

    def refresh_status_rows_for_settings(self):
        """Update existing rows after settings changed."""
        readability = self.actions.get_config().get('tcp_port_readability', 'Numbers')
        service_map = self.actions.get_config().get('port_service_map', {})

        for original_string, widgets in self.status_widgets.items():
            latest = None
            all_targets = self.actions.get_all_targets_with_status()
            for t in all_targets:
                if t.get('original_string') == original_string:
                    latest = t
                    break
            if latest:
                status = latest.get('status', widgets.get('status', ''))
                widgets['label'].config(text=f"{self.actions.extract_host(original_string)}: {status}")
                port_statuses = latest.get('port_statuses') or {}
                for port, btn in widgets.get('port_widgets', {}).items():
                    display_text = port
                    if readability == 'Simple':
                        display_text = service_map.get(str(port), str(port))
                    btn.config(text=display_text)
        if not self.status_widgets:
            for child in self.status_frame.winfo_children():
                if isinstance(child, ttk.Frame):
                    for lab in child.winfo_children():
                        if isinstance(lab, ttk.Label):
                            try:
                                lab.config(text=self._("Waiting for targets..."))
                            except Exception:
                                pass

    def add_target_row(self, target_info: Dict[str, Any]):
        """Creates a single row of widgets for a target."""
        parent = self.status_frame
        original_string = target_info['original_string']
        
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, expand=True, pady=2)

        ping_button = tk.Button(
            row_frame, text="PING", width=5, bg="gray", fg="white",
            disabledforeground="white", relief="raised", borderwidth=1,
            state=tk.DISABLED, cursor=""
        )
        ping_button.pack(side=tk.LEFT, padx=(0, 10))

        port_frame = ttk.Frame(row_frame)
        port_frame.pack(side=tk.RIGHT, padx=(5, 0))

        label = ttk.Label(row_frame, text=f"{self.actions.extract_host(original_string)}: {self._('Pinging...')}")
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

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
            "row_frame": row_frame, "label": label, "ping_button": ping_button,
            "port_widgets": port_widgets, "udp_widgets": udp_widgets,
            "group_frame": parent, "status": self._('Pinging...')
        }
        
        self.update_target_row(target_info)

    def _on_service_indicator_click(self, target: str, port_or_service: str, is_web_port: bool):
        """Handles clicks on any service indicator button."""
        if is_web_port:
            if self.dialog_manager.show_unsecure_browser_warning():
                try:
                    port = int(port_or_service)
                    self.ui.launch_web_ui_for_port(target, port)
                except (ValueError, TypeError):
                    pass
        else:
            messagebox.showinfo(
                "Service Information",
                f"Service '{port_or_service}' is responsive on {self.actions.extract_host(target)}, "
                "but it does not have a web interface to launch.",
                parent=self.root
            )

    def update_target_row(self, target_info: Dict[str, Any]):
        """Updates a single row of widgets for a target with new data."""
        original_string = target_info['original_string']
        widgets = self.status_widgets.get(original_string)
        if not widgets:
            return

        status = target_info.get('status', self._('Pinging...'))
        color = target_info.get('color', 'gray')
        latency_str = target_info.get('latency_str', '')
        web_port_open = target_info.get('web_port_open', False)
        port_statuses = target_info.get('port_statuses')
        udp_service_statuses = target_info.get('udp_service_statuses')

        ping_button_text = self._("PING")
        if status == self._("Online"):
            ping_button_text = latency_str
        elif status == self._("Offline"):
            ping_button_text = self._("FAIL")
        
        widgets['ping_button'].config(
            text=ping_button_text, bg=color,
            state=tk.NORMAL if web_port_open else tk.DISABLED,
            cursor="hand2" if web_port_open else ""
        )
        if web_port_open:
            widgets['ping_button'].config(
                command=lambda s=original_string: self._on_service_indicator_click(s, "80", is_web_port=True)
            )

        widgets['label'].config(text=f"{self.actions.extract_host(original_string)}: {status}")

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
                    
                    port_button.config(
                        text=display_text,
                        bg=TCP_OPEN_COLOR if is_open else TCP_CLOSED_COLOR,
                        state=tk.NORMAL if is_open else tk.DISABLED,
                        cursor="hand2" if is_open else ""
                    )
                    is_web_port = int(port) in [80, 443, 8080]
                    if is_open:
                        port_button.config(
                            command=lambda s=original_string, p=port, web=is_web_port: self._on_service_indicator_click(s, p, web)
                        )

        if udp_service_statuses:
            for svc_name, svc_status in udp_service_statuses.items():
                udp_btn = widgets['udp_widgets'].get(svc_name)
                if udp_btn:
                    is_open = (svc_status == "Open")
                    udp_btn.config(
                        bg=UDP_OPEN_COLOR if is_open else UDP_CLOSED_COLOR,
                        state=tk.NORMAL if is_open else tk.DISABLED,
                        cursor="hand2" if is_open else ""
                    )
                    if is_open:
                        udp_btn.config(
                            command=lambda s=original_string, svc=svc_name: self._on_service_indicator_click(s, svc, is_web_port=False)
                        )
