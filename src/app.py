# src/app.py

"""
Main application class for the TechRoute GUI.

This module defines the main application window, manages UI state,
and coordinates with the network module to run pinging operations.
"""

import ipaddress
import os
import platform
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional

from . import configuration, network
from .ui import AppUI

class TechRouteApp:
    """Manages the UI, pinging threads, and browser launching."""
    ui: AppUI
    
    def __init__(self, root: tk.Tk):
        """Initializes the application."""
        # Load configuration from YAML file
        self.config = configuration.load_or_create_config()
        
        self.root = root
        self.root.title("TechRoute - Machine Service Checker")

        # Set application icon
        try:
            # Use absolute paths for icons, assuming they are in the root directory
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            icon_path_ico = os.path.join(base_dir, "icon.ico")
            icon_path_png = os.path.join(base_dir, "icon.png")
            
            if os.path.exists(icon_path_ico):
                self.root.iconbitmap(icon_path_ico)
            elif os.path.exists(icon_path_png):
                # For other OSes or if .ico is not supported
                photo = tk.PhotoImage(file=icon_path_png)
                self.root.iconphoto(False, photo)
        except (tk.TclError, FileNotFoundError) as e:
            print(f"Warning: Could not load application icon. {e}")

        # --- State Variables ---
        self.is_pinging = False
        self.ping_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.web_ui_targets: Dict[str, Dict[str, Any]] = {} # {original_string: {'ip': ip, 'protocol': 'http'/'https'}}
        self.last_animation_time = 0.0

        # --- Browser Detection ---
        self.browser_command = network.find_browser_command(self.config['browser_preferences'])
        browser_name = self.browser_command['name'] if self.browser_command else "OS Default"
        
        # --- UI Setup ---
        self.ui = AppUI(self.root, self, browser_name)

        # --- Dynamic Initial Sizing ---
        self.initial_width = 550
        self.initial_height = 450 # Set a reasonable fixed initial height
        
        # Force Tkinter to compute the layout and widget sizes
        self.root.update_idletasks()

        # Set the initial size and the minimum size for the window.
        # This ensures the window launches at a reasonable size.
        self.root.geometry(f"{self.initial_width}x{self.initial_height}")
        self.root.minsize(self.initial_width, 400) # Set a reasonable minimum height

    def update_config(self, new_config: Dict[str, Any]):
        """Updates the application's config and saves it."""
        self.config = new_config
        configuration.save_config(self.config)
        messagebox.showinfo("Configuration Saved", "Your settings have been saved successfully.")

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
            
            default_ports = self.config.get('default_ports_to_check', [])
            
            if len(parts) > 1 and parts[1].strip():
                port_str = parts[1]
                try:
                    # Ports from the input line are added to the default ports
                    ports = [int(p.strip()) for p in port_str.split(',') if p.strip()]
                    if not all(0 < port < 65536 for port in ports):
                        raise ValueError("Port number out of range.")
                    target['ports'] = sorted(list(set(ports + default_ports)))
                except ValueError:
                    messagebox.showerror("Invalid Port", f"Invalid port for '{ip_str}'. Use comma-separated numbers (1-65535).")
                    return []
            else:
                target['ports'] = default_ports
                target['original_string'] = ip_str
            
            targets.append(target)
        return targets

    def toggle_ping_process(self):
        if self.is_pinging: self._stop_ping_process()
        else: self._start_ping_process()

    def update_ping_process(self):
        """Stops and restarts the pinging process with current settings."""
        if self.is_pinging:
            self._stop_ping_process()
            # Short delay to allow threads to terminate before restarting
            self.root.after(100, self._start_ping_process)
        else:
            # If not currently pinging, "Update" should just start it.
            self._start_ping_process()

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
        self.web_ui_targets.clear()
        self.ping_threads.clear()
        self.last_animation_time = 0.0 # Reset animation timer

        self.ui.start_stop_button.config(text="Stop Pinging")
        self.ui.ip_entry.config(state=tk.DISABLED)
        self.ui.update_status_bar("Pinging targets...")
        self.ui.setup_status_display(targets)
        # Adjust window size *after* populating the UI
        self.ui.start_blinking_animation()

        # Update polling rate from UI
        try:
            polling_rate_ms = int(self.ui.polling_rate_entry.get())
            self.config['ping_interval_seconds'] = polling_rate_ms / 1000.0
        except ValueError:
            messagebox.showwarning("Invalid Polling Rate", "Using default polling rate.")
            self.config['ping_interval_seconds'] = 3

        for target in targets:
            thread = threading.Thread(
                target=network.ping_worker,
                args=(
                    target,
                    self.stop_event,
                    self.update_queue,
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
        self.ui.launch_all_button.config(state=tk.DISABLED)
        self.ui.reset_status_indicator()
        # Clear status items and resize window back to initial state
        self.ui.setup_status_display([]) 

    def launch_all_web_uis(self):
        """Launches web UIs for all targets with open web ports."""
        if not self.web_ui_targets:
            messagebox.showinfo("No Targets", "No web UIs are available to launch.")
            return
        
        for target_details in self.web_ui_targets.values():
            url = f"{target_details['protocol']}://{target_details['ip']}"
            network.open_browser_with_url(url, self.browser_command)

    def launch_single_web_ui(self, original_string: str):
        """Launches the web UI for a single, specific target."""
        target_details = self.web_ui_targets.get(original_string)
        if target_details:
            url = f"{target_details['protocol']}://{target_details['ip']}"
            network.open_browser_with_url(url, self.browser_command)
        else:
            messagebox.showwarning("Unavailable", "This web UI is not currently available.")

    def launch_web_ui_for_port(self, original_string: str, port: int):
        """Launches a web UI for a specific IP and port."""
        ip = original_string.split(':', 1)[0]
        
        # Determine protocol based on port
        protocol = "https"
        if port == 80:
            protocol = "http"
        
        url = f"{protocol}://{ip}"
        network.open_browser_with_url(url, self.browser_command)

    def process_queue(self):
        """Processes messages from the update queue to safely update the GUI."""
        message = None
        try:
            # If there are messages, it means a new batch of pings has likely completed.
            # We only want to fire the animation once per batch.
            if not self.update_queue.empty():
                polling_rate_s = self.config.get('ping_interval_seconds', 3)
                if time.time() - self.last_animation_time >= polling_rate_s:
                    self.last_animation_time = time.time()
                    try:
                        polling_rate_ms = int(self.ui.polling_rate_entry.get())
                    except (ValueError, tk.TclError): # TclError if window is closing
                        polling_rate_ms = int(polling_rate_s * 1000)
                    
                    # This call also handles stopping the initial '???' blinking animation
                    self.ui.run_ping_animation(polling_rate_ms)

            # Process all available messages in the queue
            while not self.update_queue.empty():
                message = self.update_queue.get_nowait()

                # Unpack the main status update
                original_string, status, color, port_statuses, latency_str, web_port_open = message

                self.ui.update_status_in_gui(original_string, status, color, port_statuses, latency_str, web_port_open)

                if web_port_open:
                    ip = original_string.split(':', 1)[0]
                    if original_string not in self.web_ui_targets:
                        # Determine protocol based on common web ports
                        protocol = "https"
                        if any(p in [80, 8080] for p in (port_statuses or {})):
                            protocol = "http"
                        self.web_ui_targets[original_string] = {'ip': ip, 'protocol': protocol}
                        self.ui.launch_all_button.config(state=tk.NORMAL)

        except queue.Empty:
            # This is expected when the queue is empty, just ignore it.
            pass
        except (ValueError, IndexError) as e:
            # This can happen if a message is malformed.
            print(f"Error processing queue message: {message}. Error: {e}")

        finally:
            # Reschedule the next check
            if self.is_pinging:
                self.root.after(100, self.process_queue)
