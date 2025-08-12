"""
Core application controller for TechRoute.
"""
from __future__ import annotations
import ipaddress
import json
import os
import queue
import threading
import time
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Tuple, Callable, TYPE_CHECKING

from . import configuration, network

if TYPE_CHECKING:
    from .ui.app_ui import AppUI


class PingState(Enum):
    """Represents the pinging state of the application."""
    IDLE = auto()
    CHECKING = auto()
    PINGING = auto()


class TechRouteController:
    """Manages application state, network operations, and configuration."""

    def __init__(
        self,
        ui: AppUI,
        on_status_update: Callable,
        on_network_info_update: Callable,
        on_checking_start: Callable,
        on_pinging_start: Callable,
        on_ping_stop: Callable,
        on_ping_update: Callable,
    ):
        """
        Initializes the controller.

        Args:
            ui: The main UI instance.
            on_status_update: Callback to send status updates to the UI.
            on_network_info_update: Callback to send network info to the UI.
            on_checking_start: Callback for when the initial check begins.
            on_pinging_start: Callback for when continuous pinging begins.
            on_ping_stop: Callback to trigger UI changes when pinging stops.
            on_ping_update: Callback to trigger UI animations on each ping cycle.
        """
        self.ui = ui
        self.config = configuration.load_or_create_config()
        self._load_port_service_mappings()

        self.on_status_update = on_status_update
        self.on_network_info_update = on_network_info_update
        self.on_checking_start = on_checking_start
        self.on_pinging_start = on_pinging_start
        self.on_ping_stop = on_ping_stop
        self.on_ping_update = on_ping_update

        # --- State Variables ---
        self.state = PingState.IDLE
        self.initial_target_count = 0
        self.initial_responses_received = 0
        self.ping_threads = []
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.web_ui_targets: Dict[str, Dict[str, str]] = {}
        self.network_info: Dict[str, Any] = {}
        self.browser_command = network.find_browser_command(self.config.get('browser_preferences', []))

        # --- Background Initialization ---
        threading.Thread(target=self._background_fetch_network_info, daemon=True).start()

    def _load_port_service_mappings(self):
        """Loads port service mappings from the JSON file."""
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            mappings_path = os.path.join(base_dir, "techroute", "port_services.json")
            with open(mappings_path, 'r') as f:
                self.config['port_service_map'] = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load port service mappings. {e}")
            self.config['port_service_map'] = {}

    def _background_fetch_network_info(self):
        """Fetches network info and updates the UI via callback."""
        info = network.get_network_info()
        self.network_info = info or {}
        self.on_network_info_update(self.network_info)

    def get_browser_name(self) -> str:
        """Returns the name of the detected browser or a default."""
        return self.browser_command['name'] if self.browser_command else "OS Default"

    def get_polling_rate_ms(self) -> int:
        """Gets the polling rate in milliseconds from the config."""
        return int(self.config.get("ping_interval_seconds", 3) * 1000)

    def update_polling_rate_ms(self, rate_ms: int):
        """Updates the polling rate from the UI."""
        self.config['ping_interval_seconds'] = max(50, rate_ms) / 1000.0

    def get_gateway_ip(self) -> Optional[str]:
        """Returns the gateway IP address if available."""
        return self.network_info.get('gateway')

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Updates the application's config and saves it."""
        self.config = new_config
        configuration.save_config(self.config)

    def toggle_ping_process(self, ip_string: str, polling_rate_ms: int):
        if self.state != PingState.IDLE:
            self.stop_ping_process()
        else:
            self.start_ping_process(ip_string, polling_rate_ms)

    def start_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Validates IPs and starts the pinging threads."""
        if not ip_string.strip():
            # This should be handled by the UI, but as a safeguard:
            print("Error: No targets provided.")
            return

        try:
            targets = self.parse_and_validate_targets(ip_string)
        except ValueError as e:
            # Propagate error to be shown in the UI
            raise e

        if not targets:
            return

        self.state = PingState.CHECKING
        self.initial_target_count = len(targets)
        self.initial_responses_received = 0
        self.stop_event.clear()
        self.web_ui_targets.clear()
        self.ping_threads.clear()
        self.update_polling_rate_ms(polling_rate_ms)
        self.on_checking_start()

        for target in targets:
            thread = threading.Thread(
                target=network.ping_worker,
                args=(target, self.stop_event, self.update_queue, self.config),
                daemon=True
            )
            thread.start()
            self.ping_threads.append(thread)

    def stop_ping_process(self):
        """Stops the active pinging process."""
        if self.state == PingState.IDLE:
            return
        self.state = PingState.IDLE
        self.stop_event.set()
        self.on_ping_stop()
        # We don't join the threads here to avoid blocking the UI.
        # The daemon threads will exit. The stop_event ensures they stop work.

    def process_queue(self):
        """Processes messages from the update queue to safely update the GUI."""
        if self.state == PingState.PINGING and not self.update_queue.empty():
            self.on_ping_update()

        try:
            while True:
                message = self.update_queue.get_nowait()

                if self.state == PingState.CHECKING:
                    self.initial_responses_received += 1
                    if self.initial_responses_received >= self.initial_target_count:
                        self.state = PingState.PINGING
                        self.on_pinging_start()

                self.on_status_update(message)

                # Unpack for web UI logic
                original_string, _, _, port_statuses, _, web_port_open, _ = message
                if web_port_open:
                    host = self._extract_host(original_string)
                    if original_string not in self.web_ui_targets:
                        protocol = "https"
                        if any(p in [80, 8080] for p in (port_statuses or {})):
                            protocol = "http"
                        self.web_ui_targets[original_string] = {'host': host, 'protocol': protocol}
        except queue.Empty:
            pass  # Expected when the queue is empty

    def launch_all_web_uis(self):
        """Launches web UIs for all targets with open web ports after showing a warning."""
        if not self.web_ui_targets:
            return False
        
        if not self.ui._show_unsecure_browser_warning():
            return False

        for target_details in self.web_ui_targets.values():
            host_for_url = self._format_host_for_url(target_details['host'])
            url = f"{target_details['protocol']}://{host_for_url}"
            network.open_browser_with_url(url, self.browser_command)
        return True

    def launch_single_web_ui(self, original_string: str):
        """Launches the web UI for a single, specific target after showing a warning."""
        target_details = self.web_ui_targets.get(original_string)
        if not target_details:
            return

        if not self.ui._show_unsecure_browser_warning():
            return
            
        host_for_url = self._format_host_for_url(target_details['host'])
        protocol = target_details.get('protocol', 'http')
        url = f"{protocol}://{host_for_url}"
        network.open_browser_with_url(url, self.browser_command)

    def launch_web_ui_for_port(self, original_string: str, port: int):
        """Launches a web UI for a specific IP and port after showing a warning."""
        if not self.ui._show_unsecure_browser_warning():
            return

        host = self._extract_host(original_string)
        protocol = "https" if port != 80 else "http"
        host_for_url = self._format_host_for_url(host)
        url = f"{protocol}://{host_for_url}:{port}"
        network.open_browser_with_url(url, self.browser_command)

    def parse_and_validate_targets(self, ip_string: str) -> List[Dict[str, Any]]:
        """
        Parses a string of IPs/hostnames and ports, validating each and removing duplicates.
        """
        targets = []
        processed_hosts = set()
        lines = [line.strip() for line in ip_string.splitlines() if line.strip()]
        
        for line in lines:
            host, ports_list = self._parse_target_line(line)
            
            # Normalize host to avoid trivial duplicates like 'localhost' vs '127.0.0.1'
            # This is a simple check; more complex normalization could be done if needed.
            normalized_host = '127.0.0.1' if host == 'localhost' else host
            
            if normalized_host in processed_hosts:
                continue

            self._validate_host(host)
            default_ports = self.config.get('default_ports_to_check', [])
            
            # Combine and deduplicate ports
            all_ports = sorted(list(set(ports_list + default_ports)))
            
            target: Dict[str, Any] = {
                'ip': host, 
                'ports': all_ports, 
                'original_string': line
            }
            targets.append(target)
            processed_hosts.add(normalized_host)
            
        return targets

    def _parse_target_line(self, line: str) -> Tuple[str, List[int]]:
        """Parses a single line of target input into a host and a list of ports."""
        s = line.strip()
        if s.startswith('['):
            end = s.find(']')
            if end == -1:
                raise ValueError(f"Missing closing ']' in '{s}'. For IPv6 with ports use: [fe80::1]:80,443")
            host = s[1:end]
            rest = s[end+1:].strip()
            if rest.startswith(':'):
                port_str = rest[1:].strip()
                if port_str:
                    return host, self._parse_ports(port_str, s)
            elif rest:
                raise ValueError(f"Unexpected text after ']': '{rest}'.")
            return host, []
        else:
            try:
                ipaddress.ip_address(s)
                return s, []
            except ValueError:
                if ':' in s:
                    host, port_str = s.split(':', 1)
                    host = host.strip()
                    port_str = port_str.strip()
                    if port_str:
                        return host, self._parse_ports(port_str, s)
                return s, []

    def _parse_ports(self, port_str: str, original_line: str) -> List[int]:
        """Parses a comma-separated string of ports into a list of integers."""
        try:
            ports = [int(p.strip()) for p in port_str.split(',') if p.strip()]
            if not all(0 < port < 65536 for port in ports):
                raise ValueError
            return ports
        except (ValueError, TypeError):
            raise ValueError(f"Invalid port list in '{original_line}'. Use comma-separated numbers (1-65535).")

    def _validate_host(self, host: str) -> None:
        """Validates a hostname or IP address."""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not host or len(host) > 253:
                raise ValueError(f"The hostname '{host}' is not valid.")
            labels = host.split('.')
            if not all(labels): # Check for empty labels from ".."
                raise ValueError(f"The hostname '{host}' contains empty labels.")
            for lbl in labels:
                if not (1 <= len(lbl) <= 63):
                    raise ValueError(f"The hostname '{host}' has an invalid label length.")
                if lbl.startswith('-') or lbl.endswith('-'):
                    raise ValueError(f"The hostname '{host}' has a label starting/ending with '-'.")
                if not all(c.isalnum() or c == '-' for c in lbl):
                    raise ValueError(f"The hostname '{host}' contains invalid characters.")

    def _extract_host(self, value: str) -> str:
        """Extracts the host from an input line that may include ports and/or IPv6 brackets."""
        s = value.strip()
        if s.startswith('['):
            end = s.find(']')
            if end != -1:
                return s[1:end]
        try:
            ipaddress.ip_address(s)
            return s
        except ValueError:
            pass
        if ':' in s:
            return s.split(':', 1)[0].strip()
        return s

    def _format_host_for_url(self, host: str) -> str:
        """Wrap IPv6 literal hosts in brackets for URL building."""
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.version == 6:
                return f"[{host}]"
        except ValueError:
            pass
        return host
