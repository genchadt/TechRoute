"""
Core application controller for TechRoute.
"""
from __future__ import annotations
import json
import os
import threading
import time
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING

from . import configuration
from .network import find_browser_command, get_network_info, open_browser_with_url
from .parsing import TargetParser
from .ping_manager import PingManager, PingState

if TYPE_CHECKING:
    from .ui.app_ui import AppUI


class TechRouteController:
    """Manages application state, network operations, and configuration."""
    parser: TargetParser
    web_ui_targets: Dict[str, Dict[str, str]]
    on_checking_start: Optional[Callable]
    on_pinging_start: Optional[Callable]
    on_ping_stop: Optional[Callable]
    on_ping_update: Optional[Callable]

    def __init__(
        self,
        on_status_update: Callable,
        on_network_info_update: Callable,
        translator: Callable[[str], str],
    ):
        """
        Initializes the controller.
        """
        self.ui: Optional[AppUI] = None
        self.config = configuration.load_or_create_config()
        self._ = translator
        self.on_checking_start = None
        self.on_pinging_start = None
        self.on_ping_stop = None
        self.on_ping_update = None

        # Default TCP ports for parser come from config; UDP handled separately
        tcp_ports = self.config.get('default_ports_to_check', configuration.TCP_PORTS)
        self.parser = TargetParser(default_ports=list(dict.fromkeys(tcp_ports)))

        self._load_port_service_mappings()

        self.ping_manager = PingManager(
            app_config=self.config,
            on_status_update=on_status_update,
            on_checking_start=lambda: self.on_checking_start() if self.on_checking_start else None,
            on_pinging_start=lambda: self.on_pinging_start() if self.on_pinging_start else None,
            on_ping_stop=lambda: self.on_ping_stop() if self.on_ping_stop else None,
            on_ping_update=lambda: self.on_ping_update() if self.on_ping_update else None,
        )

        self.web_ui_targets = {}
        self.network_info = {}
        self.browser_command = find_browser_command(self.config.get('browser_preferences', []))
        self.on_status_update = on_status_update
        self.on_network_info_update = on_network_info_update

        threading.Thread(target=self._background_fetch_network_info, daemon=True).start()

    def set_ui(self, ui: AppUI):
        """Links the UI to the controller after initialization."""
        self.ui = ui

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
        info = get_network_info()
        self.network_info = info or {}
        self.on_network_info_update(self.network_info)

    def get_browser_name(self) -> str:
        """Returns the name of the detected browser or a default."""
        return self.browser_command['name'] if self.browser_command else "OS Default"

    def get_polling_rate_ms(self) -> int:
        """Gets the polling rate in milliseconds from the config."""
        return int(self.config.get("ping_interval_seconds", 3) * 1000)

    def get_gateway_ip(self) -> Optional[str]:
        """Returns the gateway IP address if available."""
        return self.network_info.get('gateway')

    def get_all_targets_with_status(self) -> List[Dict[str, Any]]:
        """Returns all current targets with their last known status."""
        return self.ping_manager.get_all_targets_with_status()

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """DEPRECATED: Returns all current targets with their last known status."""
        return self.ping_manager.get_all_targets_with_status()
        
    def get_state(self) -> PingState:
        """Returns the current pinging state from the manager."""
        return self.ping_manager.state

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Updates the application's config, refreshes derived state, and saves it."""
        self.config = new_config
        # Refresh default TCP ports used by the parser
        tcp_ports = new_config.get('default_ports_to_check', configuration.TCP_PORTS)
        self.parser.default_ports = list(dict.fromkeys(tcp_ports))
        configuration.save_config(self.config)

    def process_queue(self):
        """Processes messages from the ping manager's queue and updates state."""
        messages = self.ping_manager.process_queue()
        if messages:  # Only update if there are actual messages
            for message in messages:
                # Process web UI targets
                original_string, _, _, port_statuses, _, web_port_open, _ = message
                if web_port_open:
                    host = self.parser.extract_host(original_string)
                    if original_string not in self.web_ui_targets:
                        protocol = "https"
                        if any(p in [80, 8080] for p in (port_statuses or {})):
                            protocol = "http"
                        self.web_ui_targets[original_string] = {'host': host, 'protocol': protocol}
            
            # Trigger UI update for each message
            for message in messages:
                self.on_status_update(message)

    def toggle_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Starts or stops the pinging process."""
        if self.ping_manager.state != PingState.IDLE:
            self.stop_ping_process()
        else:
            self.start_ping_process(ip_string, polling_rate_ms)

    def start_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Validates IPs and starts the pinging process via the manager."""
        if not ip_string.strip():
            print("Error: No targets provided.")
            return

        try:
            targets = self.parser.parse_and_validate_targets(ip_string)
        except ValueError as e:
            raise e

        if not targets:
            return

        self.web_ui_targets.clear()
        self.ping_manager.start(targets, polling_rate_ms, self._)

    def stop_ping_process(self):
        """Stops the active pinging process via the manager."""
        self.ping_manager.stop()


    def launch_all_web_uis(self):
        """Launches web UIs for all targets with open web ports."""
        if not self.web_ui_targets or not self.ui or not self.ui._show_unsecure_browser_warning():
            return False

        for target_details in self.web_ui_targets.values():
            host_for_url = self.parser.format_host_for_url(target_details['host'])
            url = f"{target_details['protocol']}://{host_for_url}"
            open_browser_with_url(url, self.browser_command)
        return True

    def launch_single_web_ui(self, original_string: str):
        """Launches the web UI for a single, specific target."""
        target_details = self.web_ui_targets.get(original_string)
        if not target_details or not self.ui or not self.ui._show_unsecure_browser_warning():
            return
            
        host_for_url = self.parser.format_host_for_url(target_details['host'])
        protocol = target_details.get('protocol', 'http')
        url = f"{protocol}://{host_for_url}"
        open_browser_with_url(url, self.browser_command)

    def launch_web_ui_for_port(self, original_string: str, port: int):
        """Launches a web UI for a specific IP and port."""
        if not self.ui or not self.ui._show_unsecure_browser_warning():
            return

        host = self.parser.extract_host(original_string)
        protocol = "https" if port != 80 else "http"
        host_for_url = self.parser.format_host_for_url(host)
        url = f"{protocol}://{host_for_url}:{port}"
        open_browser_with_url(url, self.browser_command)
