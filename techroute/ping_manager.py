"""
Manages the lifecycle of the network pinging process.
"""
from __future__ import annotations
import queue
import threading
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING

from .network import ping_worker
from .models import PingResult

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
        on_checking_start: Optional[Callable] = None,
        on_pinging_start: Optional[Callable] = None,
        on_ping_stop: Optional[Callable] = None,
        on_ping_update: Optional[Callable] = None,
        on_initial_check_complete: Optional[Callable] = None,
    ):
        self.config = app_config
        self.on_checking_start = on_checking_start
        self.on_pinging_start = on_pinging_start
        self.on_ping_stop = on_ping_stop
        self.on_initial_check_complete = on_initial_check_complete
        self.on_ping_update = on_ping_update

        self.state = PingState.IDLE
        self.ping_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.update_queue: queue.Queue[PingResult] = queue.Queue()

    def start(self, targets: List[Dict[str, Any]], polling_rate_ms: int, translator: Callable[[str], str]):
        """Starts the pinging process for the given targets."""
        if not targets:
            return

        self.state = PingState.PINGING
        self.stop_event.clear()
        self.ping_threads.clear()
        
        self.config['ping_interval_seconds'] = polling_rate_ms / 1000.0

        if self.on_checking_start:
            self.on_checking_start()

        # Create a shared event to signal when the first check is done
        first_check_done = threading.Event()

        # Define a callback that will be triggered by the ping_worker
        def _on_first_check_complete():
            if not first_check_done.is_set():
                if self.on_initial_check_complete:
                    self.on_initial_check_complete()
                first_check_done.set()

        for target in targets:
            thread = threading.Thread(
                target=ping_worker,
                args=(
                    target,
                    self.stop_event,
                    self.update_queue,
                    self.config,
                    translator,
                    _on_first_check_complete
                ),
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

    def process_queue(self) -> List[PingResult]:
        """
        Processes messages from the update queue and returns them.
        """
        if self.state == PingState.PINGING and not self.update_queue.empty():
            if self.on_ping_update:
                self.on_ping_update()
        
        messages = []
        try:
            while True:
                message = self.update_queue.get_nowait()
                messages.append(message)
        except queue.Empty:
            pass
        
        return messages
