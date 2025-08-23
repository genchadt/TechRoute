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
from .models import StatusUpdate

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TechRouteController:
    """Manages application state, network operations, and configuration."""
    parser: TargetParser
    web_ui_targets: Dict[str, Dict[str, str]]
    state: AppState

    def __init__(
        self,
        main_app: Any,
        state: AppStateModel,
        actions: AppActions,
        translator: Callable[[str], str],
    ):
        """
        Initializes the controller.
        """
        self.main_app = main_app
        self.state_model = state
        self.actions = actions
        self.callbacks: Optional[ControllerCallbacks] = None
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
        self.actions.get_all_targets_with_status = self.get_all_targets_with_status
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
        self.actions.settings_changed = self.main_app.handle_settings_change
        self.actions.get_config = lambda: self.config
        self.actions.extract_host = self.parser.extract_host
        self.actions.get_service_checkers = lambda: self.service_checker.checkers
        self.actions.register_network_info_callback = self.register_network_info_callback

        self.web_ui_targets = {}
        self.network_info = {}
        self._network_info_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.browser_command = find_browser_command(self.config.get('browser_preferences', []))
        self.network_info_queue: Queue[Dict[str, Any]] = Queue()

        self._network_thread_stop_event = threading.Event()
        threading.Thread(target=self._background_network_monitor, daemon=True).start()

    def register_callbacks(self, callbacks: ControllerCallbacks):
        """Registers UI callbacks and initializes components that need them."""
        self.callbacks = callbacks
        self._initialize_ping_manager()

    def register_network_info_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registers a callback for network information updates."""
        self._network_info_callback = callback

    def _initialize_ping_manager(self):
        """Creates the PingManager instance once callbacks are available."""
        if not self.callbacks:
            return
        self.ping_manager = PingManager(
            app_config=self.config,
            on_status_update=self.callbacks.on_status_update,
            on_checking_start=lambda: self._set_state(AppState.CHECKING),
            on_pinging_start=lambda: self._set_state(AppState.PINGING),
            on_ping_stop=lambda: self._set_state(AppState.IDLE),
        )

    def _set_state(self, new_state: AppState):
        """Sets the application state and notifies the UI."""
        self.state = new_state
        if self.callbacks:
            self.callbacks.on_state_change(new_state)

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

    def get_all_targets_with_status(self) -> List[Dict[str, Any]]:
        """Returns all current targets with their last known status."""
        return self.ping_manager.get_all_targets_with_status() if self.ping_manager else []

    def process_network_updates(self):
        """Processes network info updates from the queue."""
        try:
            info = self.network_info_queue.get_nowait()
            logging.info(f"Processing network update from queue: {info}")
            self.network_info = info
            if self._network_info_callback:
                logging.info(f"Calling network info callback with: {info}")
                self._network_info_callback(info)
            elif self.callbacks:
                # Fallback for older connections if any
                logging.info(f"Calling on_network_info_update with: {info}")
                self.callbacks.on_network_info_update(info)
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
        """Processes messages from the ping manager's queue and updates state."""
        if not self.ping_manager or not self.callbacks:
            return
            
        messages = self.ping_manager.process_queue()
        if not messages:
            return

        for message in messages:
            if message.web_port_open:
                host = self.parser.extract_host(message.original_string)
                if message.original_string not in self.web_ui_targets:
                    protocol = "https" if any(p in [443, 8443] for p in (message.port_statuses or {})) else "http"
                    self.web_ui_targets[message.original_string] = {'host': host, 'protocol': protocol}
        
        update_payloads = [asdict(message) for message in messages]
        if update_payloads:
            self.callbacks.on_status_update(update_payloads)
            
    def toggle_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Starts or stops the pinging process."""
        if self.state != AppState.IDLE:
            self.stop_ping_process()
        else:
            self.start_ping_process(ip_string, polling_rate_ms)

    def start_ping_process(self, ip_string: str, polling_rate_ms: int):
        """Validates IPs and starts the pinging process via the manager."""
        if not self.ping_manager or not self.callbacks:
            return

        if not ip_string.strip():
            logging.error("No targets provided.")
            raise ValueError("No targets provided.")

        targets = self.parser.parse_and_validate_targets(ip_string)
        if not targets:
            return
        
        self.web_ui_targets.clear()
        
        initial_statuses = [{'original_string': t['original_string']} for t in targets]
        self.callbacks.on_initial_statuses_loaded(initial_statuses)

        self.ping_manager.start(targets, polling_rate_ms, self._)

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
