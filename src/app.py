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

class PrinterPingerApp:
    """Manages the UI, pinging threads, and browser launching."""
    
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
        self._setup_ui(browser_name)

    def _setup_ui(self, browser_name: str):
        """Creates and configures the UI elements."""
        self.status_bar_label = ttk.Label(self.root, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, padding=2)
        self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.input_frame = ttk.LabelFrame(self.main_frame, text=f"Target Browser: {browser_name}", padding="10")
        self.input_frame.pack(fill=tk.X)
        
        self.status_frame = ttk.LabelFrame(self.main_frame, text="Status", padding="10")
        self.status_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        ttk.Label(self.input_frame, text="Enter IPs, one per line (e.g., 192.168.1.50:80,443):").pack(pady=5)

        text_frame = ttk.Frame(self.input_frame)
        text_frame.pack(pady=5, fill=tk.X, expand=True)

        self.ip_entry = tk.Text(text_frame, width=40, height=8)
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=scrollbar.set)
        
        self.start_stop_button = ttk.Button(self.input_frame, text="Start Pinging", command=self.toggle_ping_process, underline=0)
        self.start_stop_button.pack(pady=10)

        self.status_widgets: Dict[str, Dict[str, Any]] = {}

        self.root.bind('<Control-Return>', lambda event: self.toggle_ping_process())
        self.root.bind('<Alt-s>', lambda event: self.start_stop_button.invoke())

    def _update_status_bar(self, message: str):
        self.status_bar_label.config(text=message)

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
        ip_string = self.ip_entry.get("1.0", tk.END).strip()
        if not ip_string:
            messagebox.showwarning("Input Required", "Please enter at least one IP address.")
            return

        targets = self._parse_and_validate_targets(ip_string)
        if not targets: return

        self.is_pinging = True
        self.stop_event.clear()
        self.browser_opened.clear()
        self.ping_threads.clear()

        self.start_stop_button.config(text="Stop Pinging")
        self.ip_entry.config(state=tk.DISABLED)
        self._update_status_bar("Pinging targets...")
        self._setup_status_display(targets)

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
        self.start_stop_button.config(text="Start Pinging")
        self.ip_entry.config(state=tk.NORMAL)
        self._update_status_bar("Pinging stopped.")

    def _setup_status_display(self, targets: List[Dict[str, Any]]):
        """Creates the initial status widgets for each IP address."""
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()

        for target in targets:
            original_string, ports = target['original_string'], target['ports']
            frame = ttk.Frame(self.status_frame)
            frame.pack(fill=tk.X, pady=2, anchor='w')
            
            ping_frame = ttk.Frame(frame)
            ping_frame.pack(side=tk.LEFT, anchor='n')

            indicator = tk.Label(ping_frame, text="", width=5, bg="gray", fg="white", padx=4, pady=1, relief="raised", borderwidth=1)
            indicator.pack(side=tk.LEFT, padx=(0, 10))

            label = ttk.Label(ping_frame, text=f"{original_string}: Pinging...")
            label.pack(side=tk.LEFT, pady=2)
            
            port_frame = ttk.Frame(frame)
            port_frame.pack(side=tk.LEFT, padx=(10, 0), anchor='n')

            port_widgets = {}
            if ports:
                for port in ports:
                    port_button = tk.Label(port_frame, text=str(port), bg="gray", fg="white", padx=4, pady=1, relief="raised", borderwidth=1)
                    port_button.pack(side=tk.LEFT, padx=2)
                    port_widgets[port] = port_button
            
            self.status_widgets[original_string] = {"label": label, "indicator": indicator, "port_widgets": port_widgets}

    def process_queue(self):
        """Processes messages from the update queue to safely update the GUI."""
        try:
            while not self.update_queue.empty():
                args = self.update_queue.get_nowait()
                self._update_status_in_gui(*args)
        finally:
            if self.is_pinging:
                self.root.after(100, self.process_queue)

    def _update_status_in_gui(self, original_string: str, status: str, color: str, launched_browser: bool, port_statuses: Optional[Dict[int, str]], latency_str: str):
        """Updates the GUI widgets for a specific IP. Must be called from the main thread."""
        if original_string in self.status_widgets:
            widgets = self.status_widgets[original_string]
            ip_part = original_string.split(':', 1)[0]

            widgets["indicator"].config(bg=color, text=latency_str if status == "Online" else "FAIL")

            current_text = widgets["label"].cget("text")
            new_text = f"{ip_part}: {status}"

            if launched_browser or "Launched" in current_text:
                new_text += " - Web UI Launched"
            widgets["label"].config(text=new_text)
            
            if port_statuses:
                port_widgets = widgets.get("port_widgets", {})
                for port, port_status in port_statuses.items():
                    if port in port_widgets:
                        button = port_widgets[port]
                        port_color = {"Open": "#007bff", "Closed": "#fd7e14"}.get(port_status, "#dc3545")
                        button.config(bg=port_color)