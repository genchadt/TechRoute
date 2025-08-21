"""
Manages the lifecycle of the network pinging process.
"""
from __future__ import annotations
import queue
import threading
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING

from .network import ping_worker
from .models import StatusUpdate

if TYPE_CHECKING:
    from .ui.app_ui import AppUI

class PingState(Enum):
    """Represents the pinging state of the application."""
    IDLE = auto()
    PINGING = auto()

class PingManager:
    """Manages the state and execution of pinging threads."""

    def __init__(
        self,
        app_config: Dict[str, Any],
        on_status_update: Callable,
        on_checking_start: Optional[Callable] = None,
        on_pinging_start: Optional[Callable] = None,
        on_ping_stop: Optional[Callable] = None,
        on_ping_update: Optional[Callable] = None,
    ):
        self.config = app_config
        self.on_status_update = on_status_update
        self.on_checking_start = on_checking_start
        self.on_pinging_start = on_pinging_start
        self.on_ping_stop = on_ping_stop
        self.on_ping_update = on_ping_update

        self.state = PingState.IDLE
        self.ping_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.update_queue: queue.Queue = queue.Queue()
        self.targets: Dict[str, Dict[str, Any]] = {}

    def get_all_targets_with_status(self) -> List[Dict[str, Any]]:
        """Returns all current targets with their last known status."""
        return list(self.targets.values())

    def start(self, targets: List[Dict[str, Any]], polling_rate_ms: int, translator: Callable[[str], str]):
        """Starts the pinging process for the given targets."""
        if not targets:
            return

        self.state = PingState.PINGING
        self.stop_event.clear()
        self.ping_threads.clear()
        self.targets.clear()
        for target in targets:
            # Set initial values for ALL fields
            target.update({
                'status': translator('Pinging...'),
                'color': 'gray',
                'latency_str': '',
                'port_statuses': None,
                'web_port_open': False,
                'udp_service_statuses': None
            })
            self.targets[target['original_string']] = target
        
        self.config['ping_interval_seconds'] = max(50, polling_rate_ms) / 1000.0
        
        # Immediately trigger a UI update to show the initial state
        self.on_status_update(list(self.targets.values()))

        if self.on_checking_start:
            self.on_checking_start()

        # Delay the start of the pinging animation to allow the "checking" animation to play
        threading.Timer(1.0, self._start_ping_threads, args=[targets, translator]).start()

    def _start_ping_threads(self, targets: List[Dict[str, Any]], translator: Callable[[str], str]):
        """Starts the ping worker threads."""
        if self.state != PingState.PINGING:
            return

        if self.on_pinging_start:
            self.on_pinging_start()

        for target in targets:
            thread = threading.Thread(
                target=ping_worker,
                args=(target, self.stop_event, self.update_queue, self.config, translator),
                daemon=True
            )
            thread.start()
            self.ping_threads.append(thread)

    def stop(self):
        """Stops the active pinging process."""
        if self.state == PingState.IDLE:
            return
        self.state = PingState.IDLE
        self.stop_event.set()
        if self.on_ping_stop:
            self.on_ping_stop()

    def process_queue(self) -> List[Any]:
        """
        Processes messages from the update queue and returns them.
        """
        if self.state == PingState.PINGING and not self.update_queue.empty():
            if self.on_ping_update:
                self.on_ping_update()
        
        messages = []
        try:
            while True:
                message: StatusUpdate = self.update_queue.get_nowait()
                messages.append(message)
                
                if message.original_string in self.targets:
                    # Update ALL fields, not just status
                    self.targets[message.original_string].update({
                        'status': message.status,
                        'color': message.color,
                        'port_statuses': message.port_statuses,
                        'latency_str': message.latency_str,
                        'web_port_open': message.web_port_open,
                        'udp_service_statuses': message.udp_service_statuses
                    })
        except queue.Empty:
            pass
        
        return messages
