"""
A widget for displaying network information.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Any, List

from ...checkers import get_udp_service_registry
from ..types import create_indicator_button
from ...network import check_tcp_port

class NetworkInfoPanel(ttk.Frame):
    """A frame that displays network information."""

    def __init__(self, parent: tk.Widget, translator: Callable[[str], str]):
        super().__init__(parent)
        self._ = translator
        self.local_service_indicators: Dict[int, tk.Button] = {}
        self._local_service_ports = [20, 21, 22, 445]

        self.network_frame = ttk.LabelFrame(self, text=self._("Network Information"), padding="10")
        self.network_frame.pack(fill=tk.X, expand=True)

        netgrid = self.network_frame
        self.ipv4_label = ttk.Label(netgrid, text=self._("IPv4:"))
        self.ipv4_label.grid(row=0, column=0, sticky="w")
        self.netinfo_v4 = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_v4.grid(row=0, column=1, sticky="w", padx=(6, 0))
        
        self.ipv6_label = ttk.Label(netgrid, text=self._("IPv6:"))
        self.ipv6_label.grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.netinfo_v6 = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_v6.grid(row=0, column=3, sticky="w", padx=(6, 0))

        self.gateway_label = ttk.Label(netgrid, text=self._("Gateway:"))
        self.gateway_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.netinfo_gw = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_gw.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(4, 0))

        self.subnet_label = ttk.Label(netgrid, text=self._("Subnet Mask:"))
        self.subnet_label.grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(4, 0))
        self.netinfo_mask = ttk.Label(netgrid, text=self._("Detecting…"))
        self.netinfo_mask.grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(4, 0))

        self.local_services_label = ttk.Label(netgrid, text=self._("Local Services:"))
        self.local_services_label.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.local_services_frame = ttk.Frame(netgrid)
        self.local_services_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=(6, 0), pady=(4, 0))

    def setup_local_services(self, config: Dict[str, Any]):
        """Creates the local service indicator buttons."""
        readability = config.get('tcp_port_readability', 'Numbers')
        service_map = config.get('port_service_map', {})

        for p in self._local_service_ports:
            display_text = str(p)
            if readability == 'Simple':
                display_text = service_map.get(str(p), str(p))
            btn = create_indicator_button(self.local_services_frame, display_text, is_placeholder=True)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.local_service_indicators[p] = btn

        udp_ports_cfg = config.get('udp_services_to_check', [])
        if udp_ports_cfg:
            registry = get_udp_service_registry()
            for udp_port in udp_ports_cfg:
                entry = registry.get(int(udp_port))
                if not entry: continue
                service_name, _checker = entry
                btn = create_indicator_button(self.local_services_frame, service_name, is_placeholder=True)
                btn.pack(side=tk.LEFT, padx=(0, 4))
                self.local_service_indicators[udp_port] = btn
        
        self.after(100, lambda: self.start_local_services_check(config))

    def start_local_services_check(self, config: Dict[str, Any]) -> None:
        """Kicks off an asynchronous check of local TCP ports."""
        import threading
        if getattr(self, "_local_services_thread_running", False): return
        setattr(self, "_local_services_thread_running", True)

        def _worker():
            try:
                timeout, results = 0.5, {}
                host_v4, host_v6 = "127.0.0.1", "::1"
                for p in self._local_service_ports:
                    try: status_v4 = check_tcp_port(host_v4, p, timeout)
                    except Exception: status_v4 = "Closed"
                    try: status_v6 = check_tcp_port(host_v6, p, timeout)
                    except Exception: status_v6 = "Closed"
                    results[p] = "Open" if (status_v4 == "Open" or status_v6 == "Open") else "Closed"
                
                udp_ports_cfg = config.get('udp_services_to_check', [])
                if udp_ports_cfg:
                    registry = get_udp_service_registry()
                    for udp_port in udp_ports_cfg:
                        entry = registry.get(int(udp_port))
                        if not entry: continue
                        _service_name, checker = entry
                        status = "Closed"
                        try:
                            res_v4 = checker.check(host_v4, timeout=timeout)
                            res_v6 = checker.check(host_v6, timeout=timeout)
                            if (res_v4 and res_v4.available) or (res_v6 and res_v6.available):
                                status = "Open"
                        except Exception: status = "Closed"
                        results[udp_port] = status
                
                def _apply():
                    try:
                        from ...checkers import get_udp_service_registry
                        udp_ports = get_udp_service_registry().keys()

                        for p, status in results.items():
                            btn = self.local_service_indicators.get(p)
                            if not btn: continue
                            
                            is_open = status == "Open"
                            
                            if p in udp_ports:
                                color = "#2196F3" if is_open else "#FF9800"
                            else:  # TCP
                                color = "#4CAF50" if is_open else "#F44336"
                            
                            btn.config(bg=color, fg="white")
                    except tk.TclError: pass
                self.after(0, _apply)
            finally:
                setattr(self, "_local_services_thread_running", False)
                self.after(5000, lambda: self.start_local_services_check(config))
        
        threading.Thread(target=_worker, daemon=True).start()

    def update_info(self, info: Dict[str, Any]) -> None:
        """Updates the labels with new network information."""
        try:
            v4 = info.get("primary_ipv4") or "n/a"
            v6 = info.get("primary_ipv6") or "n/a"
            gw = info.get("gateway") or "n/a"
            mask = info.get("subnet_mask") or "n/a"
            self.netinfo_v4.config(text=str(v4))
            self.netinfo_v6.config(text=str(v6))
            self.netinfo_gw.config(text=str(gw))
            self.netinfo_mask.config(text=str(mask))
        except tk.TclError:
            pass

    def retranslate_ui(self, translator: Callable[[str], str]):
        """Retranslates the UI elements of the widget."""
        self._ = translator
        self.network_frame.config(text=self._("Network Information"))
        self.ipv4_label.config(text=self._("IPv4:"))
        self.ipv6_label.config(text=self._("IPv6:"))
        self.gateway_label.config(text=self._("Gateway:"))
        self.subnet_label.config(text=self._("Subnet Mask:"))
        self.local_services_label.config(text=self._("Local Services:"))
        
        # Retranslate "Detecting..." if it's currently displayed
        if self.netinfo_v4.cget("text") != "n/a" and not any(char.isdigit() for char in self.netinfo_v4.cget("text")):
            self.netinfo_v4.config(text=self._("Detecting…"))
        if self.netinfo_v6.cget("text") != "n/a" and not any(char.isdigit() for char in self.netinfo_v6.cget("text")):
            self.netinfo_v6.config(text=self._("Detecting…"))
        if self.netinfo_gw.cget("text") != "n/a" and not any(char.isdigit() for char in self.netinfo_gw.cget("text")):
            self.netinfo_gw.config(text=self._("Detecting…"))
        if self.netinfo_mask.cget("text") != "n/a" and not any(char.isdigit() for char in self.netinfo_mask.cget("text")):
            self.netinfo_mask.config(text=self._("Detecting…"))
