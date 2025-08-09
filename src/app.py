# src/app.py

"""
Main application class for the PrintPing GUI.

This module defines the main application window, manages UI state,
and coordinates with the network module to run pinging operations.
"""

import ipaddress
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional

from . import configuration, network
from .ui import AppUI

class PrinterPingerApp:
    """Manages the UI, pinging threads, and browser launching."""
    ui: AppUI
    
    def __init__(self, root: tk.Tk):
        """Initializes the application."""
        # Load configuration from YAML file
        self.config = configuration.load_or_create_config()
        
        self.root = root
        self.root.title("PrintPing - Printer Pinger & Web UI Launcher")
        self.root.geometry("450x420")
        self.root.minsize(450, 420)

        # --- State Variables ---
        self.is_pinging = False
        self.ping_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.browser_opened = set()

        # --- Browser Detection ---
        self.browser_command = network.find_browser_command(self.config['browser_preferences'])
        browser_name = self.browser_command['name'] if self.browser_command else "OS Default"
        
        # --- UI Setup ---
        self.ui = AppUI(self.root, self, browser_name)

    def _parse_and_validate_targets(self, ip_string: str) -> List[Dict[str, Any]]:
        """
        Parses a string of IPs and ports, validating each.
        """
        targets = []
        lines = [line.strip() for line in ip_string.splitlines() if line.strip()]
        
        for line in lines:
            parts = line.split(':', 1)
            ip_str = parts[0].strip()
            
            try:
                ipaddress.ip_address(ip_str)
            except ValueError:
                messagebox.showerror("Invalid IP Address", f"The IP address '{ip_str}' is not valid.")
                return []

            target: Dict[str, Any] = {'ip': ip_str, 'ports': [], 'original_string': line}
            
            if len(parts) > 1 and parts[1].strip():
                port_str = parts[1]
                try:
                    ports = [int(p.strip()) for p in port_str.split(',') if p.strip()]
                    if not all(0 < port < 65536 for port in ports):
                        raise ValueError("Port number out of range.")
                    target['ports'] = sorted(list(set(ports)))
                except ValueError:
                    messagebox.showerror("Invalid Port", f"Invalid port for '{ip_str}'. Use comma-separated numbers (1-65535).")
                    return []
            else:
                target['ports'] = self.config['default_ports_to_check']
                target['original_string'] = ip_str
            
            targets.append(target)
        return targets

    def toggle_ping_process(self):
        if self.is_pinging: self._stop_ping_process()
        else: self._start_ping_process()

    def _start_ping_process(self):
        """Validates IPs and starts the pinging threads."""
        ip_string = self.ui.ip_entry.get("1.0", tk.END).strip()
        if not ip_string:
            messagebox.showwarning("Input Required", "Please enter at least one IP address.")
            return

        targets = self._parse_and_validate_targets(ip_string)
        if not targets: return

        self.is_pinging = True
        self.stop_event.clear()
        self.browser_opened.clear()
        self.ping_threads.clear()

        self.ui.start_stop_button.config(text="Stop Pinging")
        self.ui.ip_entry.config(state=tk.DISABLED)
        self.ui.update_status_bar("Pinging targets...")
        self.ui.setup_status_display(targets)

        for target in targets:
            thread = threading.Thread(
                target=network.ping_worker,
                args=(
                    target,
                    self.stop_event,
                    self.update_queue,
                    self.browser_opened,
                    self.browser_command,
                    self.config
                ),
                daemon=True
            )
            thread.start()
            self.ping_threads.append(thread)
        
        self.process_queue()

    def _stop_ping_process(self):
        """Stops the active pinging process."""
        self.is_pinging = False
        self.stop_event.set()
        self.ui.start_stop_button.config(text="Start Pinging")
        self.ui.ip_entry.config(state=tk.NORMAL)
        self.ui.update_status_bar("Pinging stopped.")

    def process_queue(self):
        """Processes messages from the update queue to safely update the GUI."""
        try:
            while not self.update_queue.empty():
                args = self.update_queue.get_nowait()
                self.ui.update_status_in_gui(*args)
        finally:
            if self.is_pinging:
                self.root.after(100, self.process_queue)