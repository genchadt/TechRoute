"""
Core application controller for TechRoute.
"""
from __future__ import annotations
import json
import os
import threading
import logging
from queue import Queue, Empty
from typing import Dict, Any, List, Optional, Callable

from . import configuration
from .network import find_browser_command, get_network_info, open_browser_with_url, clear_network_info_cache
from .parsing import TargetParser
from .ping_manager import PingManager
from .checkers.base import ServiceCheckManager
from .checkers.mdns import MDNSChecker
from .checkers.slp import SLPChecker
from .checkers.wsdiscovery import WSDiscoveryChecker
from .checkers.snmp_checker import SNMPChecker
from .ui.types import AppState, ControllerCallbacks
from .events import AppActions, AppStateModel
from dataclasses import asdict
from .models import PingResult, TargetStatus, PortStatus

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TechRouteController:
    """Manages application state, network operations, and configuration."""
    parser: TargetParser
    web_ui_targets: Dict[str, Dict[str, str]]
    state: AppState

    def __init__(
        self,
        state: AppStateModel,
        actions: AppActions,
        translator: Callable[[str], str],
    ):
        """
        Initializes the controller.
        """
        self.ui = None  # Will be set by set_ui()
        self.state_model = state
        self.actions = actions
        self.config = configuration.load_or_create_config()
        self._ = translator
        self.state = AppState.IDLE
        
        tcp_ports = self.config.get('default_ports_to_check', configuration.TCP_PORTS)
        self.parser = TargetParser(default_ports=list(dict.fromkeys(tcp_ports)))

        self._load_port_service_mappings()

        # Initialize service checkers
        self.service_checker = ServiceCheckManager(
            checkers=[MDNSChecker(), SLPChecker(), WSDiscoveryChecker(), SNMPChecker()],
            cache_ttl=self.config.get("service_check_cache_ttl_seconds", 600)
        )

        self.ping_manager: Optional[PingManager] = None
        self._set_state(AppState.IDLE)

        # Connect controller methods to the actions object
        self.actions.toggle_ping_process = self.toggle_ping_process
        self.actions.stop_ping_process = self.stop_ping_process
        self.actions.get_state = self.get_state
        self.actions.get_polling_rate_ms = self.get_polling_rate_ms
        self.actions.get_gateway_ip = self.get_gateway_ip
        self.actions.get_web_ui_url = self.get_web_ui_url
        self.actions.get_all_web_ui_urls = self.get_all_web_ui_urls
        self.actions.process_network_updates = self.process_network_updates
        self.actions.process_queue = self.process_queue
        self.actions.update_config = self.update_config
        self.actions.get_browser_command = lambda: self.browser_command or {}
        self.actions.get_browser_name = self.get_browser_name
        self.actions.get_config = lambda: self.config
        self.actions.extract_host = self.parser.extract_host
        self.actions.get_service_checkers = lambda: self.service_checker.checkers
        self.actions.register_network_info_callback = self.register_network_info_callback

        self.web_ui_targets = {}
        self.targets: Dict[str, TargetStatus] = {}
        self.network_info = {}
        self._network_info_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.browser_command = find_browser_command(self.config.get('browser_preferences', []))
        self.network_info_queue: Queue[Dict[str, Any]] = Queue()

        self._network_thread_stop_event = threading.Event()
        threading.Thread(target=self._background_network_monitor, daemon=True).start()

    def set_ui(self, ui):
        """Sets the UI instance for the controller."""
        self.ui = ui
        self.actions.settings_changed = self.ui.handle_settings_change
        self._initialize_ping_manager()

    def register_network_info_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registers a callback for network information updates."""
        self._network_info_callback = callback

    def _initialize_ping_manager(self):
        """Creates the PingManager instance once the UI is available."""
        if not self.ui:
            return
        self.ping_manager = PingManager(
            app_config=self.config,
            on_checking_start=lambda: self._set_state(AppState.CHECKING),
            on_ping_stop=lambda: self._set_state(AppState.IDLE),
            on_initial_check_complete=lambda: self._set_state(AppState.PINGING)
        )

    def _set_state(self, new_state: AppState):
        """Sets the application state and notifies the UI."""
        self.state = new_state
        if self.ui:
            self.ui.on_state_change(new_state)

    def _load_port_service_mappings(self):
        """Loads port service mappings from the JSON file."""
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            mappings_path = os.path.join(base_dir, "techroute", "port_services.json")
            with open(mappings_path, 'r') as f:
                self.config['port_service_map'] = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logging.warning(f"Could not load port service mappings: {e}")
            self.config['port_service_map'] = {}

    def _background_network_monitor(self):
        """
        Periodically fetches network info and puts it in a queue for the main thread.
        """
        retry_interval = 5  # seconds
        while not self._network_thread_stop_event.is_set():
            clear_network_info_cache()  # Ensure fresh data
            info = get_network_info()
            
            logging.info(f"Background network monitor got info: {info}")
            
            if info and info.get("primary_ipv4"):
                logging.info(f"Putting network info in queue: {info}")
                self.network_info_queue.put(info)
                self._network_thread_stop_event.wait(60)
            else:
                logging.error("Failed to retrieve network info. Retrying in %d seconds.", retry_interval)
                self.network_info_queue.put({"error": "Detecting network..."})
                self._network_thread_stop_event.wait(retry_interval)

    def shutdown(self):
        """Shuts down background threads."""
        self._network_thread_stop_event.set()
        if self.ping_manager:
            self.ping_manager.stop()

    def get_browser_name(self) -> str:
        """Returns the name of the detected browser or a default."""
        self.browser_command = find_browser_command(self.config.get('browser_preferences', []))
        return self.browser_command['name'] if self.browser_command else "Unknown"

    def get_polling_rate_ms(self) -> int:
        """Gets the polling rate in milliseconds from the config."""
        return int(self.config.get("ping_interval_seconds", 3) * 1000)

    def get_gateway_ip(self) -> Optional[str]:
        """Returns the gateway IP address if available."""
        return self.network_info.get('gateway')

    def process_network_updates(self):
        """Processes network info updates from the queue."""
        try:
            info = self.network_info_queue.get_nowait()
            logging.info(f"Processing network update from queue: {info}")
            self.network_info = info
            if self._network_info_callback:
                logging.info(f"Calling network info callback with: {info}")
                self._network_info_callback(info)
            elif self.ui:
                # Fallback for older connections if any
                logging.info(f"Calling on_network_info_update with: {info}")
                self.ui.on_network_info_update(info)
            else:
                logging.warning("No network info callback registered")
        except Empty:
            pass

    def get_state(self) -> AppState:
        """Returns the current application state."""
        return self.state

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Updates the application's config, refreshes derived state, and saves it."""
        self.config = new_config
        tcp_ports = new_config.get('default_ports_to_check', configuration.TCP_PORTS)
        self.parser.default_ports = list(dict.fromkeys(tcp_ports))
        configuration.save_config(self.config)

    def process_queue(self):
        """Processes results from the ping manager's queue and updates state."""
        if not self.ping_manager or not self.ui:
            return

        results = self.ping_manager.process_queue()
        if not results:
            return

        for result in results:
            if result.original_string not in self.targets:
                continue
            
            target_status = self.targets[result.original_string]
            target_status.latency_ms = result.latency_ms
            
            web_port_was_open = target_status.web_port_open
            
            for port_status in result.port_statuses:
                target_status.port_statuses[port_status.port] = port_status
                if port_status.port in [80, 443, 8080] and port_status.status == 'Open':
                    target_status.web_port_open = True

            # Update web UI targets if a web port is newly discovered
            if target_status.web_port_open and not web_port_was_open:
                host = self.parser.extract_host(result.original_string)
                protocol = "https" if any(p.port in [443, 8443] and p.status == 'Open' for p in target_status.port_statuses.values()) else "http"
                self.web_ui_targets[result.original_string] = {'host': host, 'protocol': protocol}

        # Create UI update payloads from the canonical state
        update_payloads = []
        for original_string, target_status in self.targets.items():
            status_str = self._("Online") if target_status.latency_ms is not None else self._("Offline")
            color = "green" if target_status.latency_ms is not None else "red"
            latency_str = f"{target_status.latency_ms}ms" if target_status.latency_ms is not None else ""
            
            port_statuses_dict = {
                str(ps.port): ps.status 
                for ps in target_status.port_statuses.values() 
                if ps.protocol == "TCP"
            }
            udp_service_statuses_dict = {
                ps.service_name: ps.status 
                for ps in target_status.port_statuses.values() 
                if ps.protocol == "UDP" and ps.service_name
            }

            update_payloads.append({
                "original_string": original_string,
                "status": status_str,
                "color": color,
                "latency_str": latency_str,
                "port_statuses": port_statuses_dict,
                "web_port_open": target_status.web_port_open,
                "udp_service_statuses": udp_service_statuses_dict
            })
        
        if update_payloads:
            self.ui.on_status_update(update_payloads)
            
    def toggle_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Starts or stops the pinging process."""
        if self.state != AppState.IDLE:
            self.stop_ping_process()
        else:
            self.start_ping_process(ip_string, polling_rate_ms)

    def start_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Starts the target validation and pinging process in a background thread."""
        if not self.ping_manager or not self.ui:
            return

        if not ip_string.strip():
            logging.error("No targets provided.")
            raise ValueError("No targets provided.")

        # Start the validation and pinging process in a background thread
        # to avoid blocking the UI with DNS lookups.
        threading.Thread(
            target=self._validate_and_start_pinging,
            args=(ip_string, polling_rate_ms),
            daemon=True
        ).start()

    def _validate_and_start_pinging(self, ip_string: str, polling_rate_ms: int):
        """Parses targets, initializes state, and starts the ping manager."""
        if not self.ping_manager or not self.ui:
            return
        try:
            parsed_targets = self.parser.parse_and_validate_targets(ip_string)
            if not parsed_targets:
                self._set_state(AppState.IDLE)
                return

            self.web_ui_targets.clear()
            self.targets.clear()

            initial_statuses = []
            for t in parsed_targets:
                original_string = t['original_string']
                self.targets[original_string] = TargetStatus(
                    ip=t['ip'],
                    original_string=original_string
                )
                initial_statuses.append({'original_string': original_string})

            self.ui.on_initial_statuses_loaded(initial_statuses)

            self.ping_manager.start(parsed_targets, polling_rate_ms, self._)
        except (ValueError, AttributeError) as e:
            logging.error(f"Target validation failed: {e}")
            self._set_state(AppState.IDLE)

    def stop_ping_process(self):
        """Stops the active pinging process via the manager."""
        if not self.ping_manager:
            return
        self._set_state(AppState.STOPPING)
        self.ping_manager.stop()

    def get_web_ui_url(self, original_string: str, port: Optional[int] = None) -> Optional[str]:
        """Constructs a URL for a given target and optional port."""
        if port:
            host = self.parser.extract_host(original_string)
            protocol = "https" if port != 80 else "http"
            host_for_url = self.parser.format_host_for_url(host)
            return f"{protocol}://{host_for_url}:{port}"

        target_details = self.web_ui_targets.get(original_string)
        if not target_details:
            return None
            
        host_for_url = self.parser.format_host_for_url(target_details['host'])
        protocol = target_details.get('protocol', 'http')
        return f"{protocol}://{host_for_url}"

    def get_all_web_ui_urls(self) -> List[str]:
        """Returns a list of all available web UI URLs."""
        urls = []
        for original_string in self.web_ui_targets:
            url = self.get_web_ui_url(original_string)
            if url:
                urls.append(url)
        return urls
