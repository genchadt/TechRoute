"""
A widget for displaying network information.
"""
import tkinter as tk
import time
from tkinter import ttk
from typing import Callable, Dict, Any, List

from ...checkers import get_udp_service_registry
from ...network import check_tcp_port
from .utils import create_indicator_button
from ..styling import TCP_OPEN_COLOR, TCP_CLOSED_COLOR, UDP_OPEN_COLOR, UDP_CLOSED_COLOR

class NetworkInfoPanel(ttk.Frame):
    """A frame that displays network information."""

    def __init__(self, parent: tk.Widget, translator: Callable[[str], str]):
        super().__init__(parent)
        self._ = translator
        self.local_service_indicators: Dict[int, tk.Button] = {}
        self._local_service_ports = [20, 21, 22, 445]
        # Cached network info for hysteresis (avoid reverting to Detecting...)
        self._cached_network_info = {}
        self._last_network_update = 0.0
        # Hysteresis state for local service statuses
        # port -> {state: 'Open'|'Closed'|'Unknown', open_streak:int, closed_streak:int}
        self._service_state = {}
        # Configuration for hysteresis thresholds
        self._close_confirm_threshold = 2  # require N consecutive Closed readings before showing Closed
        self._open_confirm_threshold = 1   # a single Open reading is enough

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
            btn = create_indicator_button(self.local_services_frame, display_text)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.local_service_indicators[p] = btn

        udp_ports_cfg = config.get('udp_services_to_check', [])
        # Add separator between TCP and UDP services
        if self._local_service_ports and udp_ports_cfg:
            sep = ttk.Separator(self.local_services_frame, orient=tk.VERTICAL)
            sep.pack(side=tk.LEFT, padx=5, fill=tk.Y)
        if udp_ports_cfg:
            registry = get_udp_service_registry()
            ordered_services = [
                ('mDNS', 5353),
                ('SNMP', 161),
                ('WS-Discovery', 3702),
                ('SLP', 427)
            ]
            
            for service_name, port in ordered_services:
                if port in udp_ports_cfg:
                    btn = create_indicator_button(self.local_services_frame, service_name)
                    btn.pack(side=tk.LEFT, padx=(0, 4))
                    self.local_service_indicators[port] = btn
        
        self.after(100, lambda: self.start_local_services_check(config))

    def start_local_services_check(self, config: Dict[str, Any]) -> None:
        """Kicks off a parallel check of local TCP and UDP ports."""
        import threading
        from collections import defaultdict

        if getattr(self, "_local_services_thread_running", False): return
        setattr(self, "_local_services_thread_running", True)

        def _worker():
            try:
                timeout = 0.2  # A shorter timeout for local checks is reasonable
                threads = []
                # A dict to hold results from threads, port -> list of statuses
                threaded_results = defaultdict(list)

                def _check_tcp(host, port):
                    try:
                        status = check_tcp_port(host, port, timeout)
                        threaded_results[port].append(status)
                    except Exception:
                        threaded_results[port].append("Closed")

                def _check_udp(host, port, checker):
                    try:
                        res = checker.check(host, timeout=timeout)
                        status = "Open" if res and res.available else "Closed"
                        threaded_results[port].append(status)
                    except Exception:
                        threaded_results[port].append("Closed")

                # --- TCP Checks ---
                for p in self._local_service_ports:
                    threads.append(threading.Thread(target=_check_tcp, args=("127.0.0.1", p)))
                    threads.append(threading.Thread(target=_check_tcp, args=("::1", p)))

                # --- UDP Checks ---
                udp_ports_cfg = config.get('udp_services_to_check', [])
                if udp_ports_cfg:
                    registry = get_udp_service_registry()
                    for udp_port in udp_ports_cfg:
                        entry = registry.get(int(udp_port))
                        if not entry: continue
                        _service_name, checker = entry
                        threads.append(threading.Thread(target=_check_udp, args=("127.0.0.1", udp_port, checker)))
                        threads.append(threading.Thread(target=_check_udp, args=("::1", udp_port, checker)))
                
                for t in threads: t.start()
                for t in threads: t.join()

                # --- Consolidate Results ---
                final_results = {}
                for port, statuses in threaded_results.items():
                    final_results[port] = "Open" if "Open" in statuses else "Closed"

                def _apply():
                    try:
                        from ...checkers import get_udp_service_registry
                        udp_ports = set(get_udp_service_registry().keys())
                        for p, measured_status in final_results.items():
                            btn = self.local_service_indicators.get(p)
                            if not btn: continue
                            
                            state_entry = self._service_state.setdefault(p, {"state": "Unknown", "open_streak": 0, "closed_streak": 0})
                            if measured_status == "Open":
                                state_entry["open_streak"] += 1
                                state_entry["closed_streak"] = 0
                                if state_entry["open_streak"] >= self._open_confirm_threshold:
                                    state_entry["state"] = "Open"
                            else:
                                state_entry["closed_streak"] += 1
                                state_entry["open_streak"] = 0
                                if state_entry["closed_streak"] >= self._close_confirm_threshold:
                                    state_entry["state"] = "Closed"

                            effective_state = state_entry["state"]
                            if effective_state == "Unknown":
                                continue
                            
                            is_open = effective_state == "Open"
                            color = (UDP_OPEN_COLOR if p in udp_ports else TCP_OPEN_COLOR) if is_open else \
                                    (UDP_CLOSED_COLOR if p in udp_ports else TCP_CLOSED_COLOR)
                            btn.config(bg=color)
                    except tk.TclError:
                        pass # Widget destroyed
                
                self.after(0, _apply)
            finally:
                setattr(self, "_local_services_thread_running", False)
                self.after(2000, lambda: self.start_local_services_check(config)) # Check more frequently

        threading.Thread(target=_worker, daemon=True).start()

    def update_info(self, info: Dict[str, Any]) -> None:
        """Updates labels with hysteresis: retain last good values on transient failures.

        We only overwrite a field if the new value looks valid (has a digit or ':').
        Otherwise, keep cached value to prevent flicker back to 'Detecting…'.
        """
        import logging
        logging.info(f"NetworkInfoPanel.update_info called with: {info}")
        try:
            def _is_valid(val: Any) -> bool:
                if not val or not isinstance(val, (str, int)):
                    return False
                s = str(val)
                if s.lower().startswith("detecting"):
                    return False
                return any(c.isdigit() for c in s)

            updated = False
            for key, label_attr, target_key in [
                ("primary_ipv4", "netinfo_v4", "primary_ipv4"),
                ("primary_ipv6", "netinfo_v6", "primary_ipv6"),
                ("gateway", "netinfo_gw", "gateway"),
                ("subnet_mask", "netinfo_mask", "subnet_mask"),
            ]:
                new_val = info.get(key)
                if _is_valid(new_val):
                    self._cached_network_info[target_key] = str(new_val)
                    updated = True

            if updated:
                self._last_network_update = time.time()

            # Apply cached (or placeholders if never set)
            v4 = self._cached_network_info.get("primary_ipv4", "n/a")
            v6 = self._cached_network_info.get("primary_ipv6", "n/a")
            gw = self._cached_network_info.get("gateway", "n/a")
            mask = self._cached_network_info.get("subnet_mask", "n/a")
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
        # Reapply cached values (prevents regress to placeholder on language change)
        if self._cached_network_info:
            try:
                self.netinfo_v4.config(text=self._cached_network_info.get("primary_ipv4", "n/a"))
                self.netinfo_v6.config(text=self._cached_network_info.get("primary_ipv6", "n/a"))
                self.netinfo_gw.config(text=self._cached_network_info.get("gateway", "n/a"))
                self.netinfo_mask.config(text=self._cached_network_info.get("subnet_mask", "n/a"))
            except tk.TclError:
                pass

    # --------------------------- Settings Refresh ---------------------------
    def refresh_for_settings_change(self, config: Dict[str, Any]):
        """Applies live settings adjustments without rebuilding the widget.

        Currently this only needs to handle TCP port readability changes.
        """
        try:
            readability = config.get('tcp_port_readability', 'Numbers')
            service_map = config.get('port_service_map', {})
            if not self.local_service_indicators:
                return
            for port in self._local_service_ports:
                btn = self.local_service_indicators.get(port)
                if not btn:
                    continue
                if readability == 'Simple':
                    btn.config(text=service_map.get(str(port), str(port)))
                else:
                    btn.config(text=str(port))
            # Re-apply cached network info (hysteresis) explicitly
            if self._cached_network_info:
                try:
                    self.netinfo_v4.config(text=self._cached_network_info.get("primary_ipv4", "n/a"))
                    self.netinfo_v6.config(text=self._cached_network_info.get("primary_ipv6", "n/a"))
                    self.netinfo_gw.config(text=self._cached_network_info.get("gateway", "n/a"))
                    self.netinfo_mask.config(text=self._cached_network_info.get("subnet_mask", "n/a"))
                except tk.TclError:
                    pass
        except Exception:
            pass
