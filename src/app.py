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
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            icon_path_png = os.path.join(base_dir, "icon.png")

            # Using PhotoImage is more portable, especially for Linux.
            if os.path.exists(icon_path_png):
                photo = tk.PhotoImage(file=icon_path_png)
                self.root.iconphoto(False, photo)
            # Fallback to .ico for Windows if .png is not found
            elif platform.system() == "Windows":
                icon_path_ico = os.path.join(base_dir, "icon.ico")
                if os.path.exists(icon_path_ico):
                    self.root.iconbitmap(icon_path_ico)
        except (tk.TclError, FileNotFoundError) as e:
            print(f"Warning: Could not load application icon. {e}")

        # --- State Variables ---
        self.is_pinging = False
        self.ping_threads = []
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.web_ui_targets = {}  # {original_string: {'ip': ip, 'protocol': 'http'/'https'}}
        self.last_animation_time = 0.0
        self.network_info = {}

        # --- Browser Detection ---
        self.browser_command = network.find_browser_command(self.config['browser_preferences'])
        browser_name = self.browser_command['name'] if self.browser_command else "OS Default"

        # --- UI Setup ---
        self.ui = AppUI(self.root, self, browser_name)

        # --- Initial sizing: shrink window to fit contents ---
        # Let the UI compute its requested size and then size the window to match.
        self.root.update_idletasks()
        try:
            # Delegate to UI helper to size to requested width/height
            self.ui.shrink_to_fit()
            # Lock current size as the minimum so the window can't be shrunk too far
            self.ui.lock_min_size_to_current()
        except Exception:
            pass

        # Fetch basic network info in background after UI is drawn
        threading.Thread(target=self._background_fetch_network_info, daemon=True).start()

    def _background_fetch_network_info(self):
        info = network.get_network_info()
        # Store and reflect in the Network Information group on the main thread
        def _apply():
            self.network_info = info or {}
            self.ui.update_network_info(self.network_info)
        try:
            self.root.after(0, _apply)
        except tk.TclError:
            # Window likely closing; ignore
            pass

    def _append_unique_line_to_ip_entry(self, value: str) -> None:
        """Appends a value as a new unique line to the IP entry if editable."""
        try:
            if str(self.ui.ip_entry.cget('state')) != str(tk.NORMAL):
                self.ui.update_status_bar("Input disabled while pinging.")
                return
        except tk.TclError:
            return
        # Exclude the trailing implicit newline Tkinter keeps at the end
        content = self.ui.ip_entry.get("1.0", "end-1c")
        lines = [l.rstrip() for l in content.splitlines() if l.strip()]
        if value in lines:
            self.ui.update_status_bar(f"'{value}' already in list.")
            return
        # Always append to the end and ensure a newline before the new value if needed
        insert_at = "end-1c"
        needs_leading_nl = bool(content) and not content.endswith("\n")
        prefix = "\n" if needs_leading_nl else ""
        self.ui.ip_entry.insert(insert_at, prefix + value + "\n")
        self.ui.ip_entry.see("end")

    def add_localhost_to_input(self):
        """Adds localhost to the targets list (IPv4)."""
        self._append_unique_line_to_ip_entry("127.0.0.1")

    def add_gateway_to_input(self):
        """Adds the default gateway to the targets list if known."""
        gw = None
        info = self.network_info or {}
        # Prefer IPv4 gateway if both available
        gw_candidate = info.get('gateway')
        if gw_candidate:
            gw = gw_candidate
        # Fallback: try to refetch quickly if not known yet
        if not gw:
            try:
                fresh = network.get_network_info()
                gw = fresh.get('gateway') if fresh else None
                if fresh:
                    self.network_info = fresh
            except Exception:
                gw = None
        if gw:
            self._append_unique_line_to_ip_entry(str(gw))
        else:
            self.ui.update_status_bar("Gateway not detected.")

    def update_config(self, new_config: Dict[str, Any]):
        """Updates the application's config and saves it."""
        self.config = new_config
        configuration.save_config(self.config)
        messagebox.showinfo("Configuration Saved", "Your settings have been saved successfully.")

    def _parse_and_validate_targets(self, ip_string: str) -> List[Dict[str, Any]]:
        """
        Parses a string of IPs/hostnames and ports, validating each.
        Accepts IPv4/IPv6 literals or DNS hostnames. Ports are optional and
        can be a comma-separated list after a colon.
        """
        targets = []
        lines = [line.strip() for line in ip_string.splitlines() if line.strip()]
        
        for line in lines:
            host: str
            ports_list: List[int] = []

            default_ports = self.config.get('default_ports_to_check', [])

            s = line.strip()
            # Case 1: Bracketed IPv6 or hostname with ports: [host]:p1,p2
            if s.startswith('['):
                end = s.find(']')
                if end == -1:
                    messagebox.showerror("Invalid Target", f"Missing closing ']' in '{s}'. For IPv6 with ports use: [fe80::1]:80,443")
                    return []
                host = s[1:end]
                rest = s[end+1:].strip()
                if rest.startswith(':'):
                    port_str = rest[1:].strip()
                    if port_str:
                        try:
                            ports_list = [int(p.strip()) for p in port_str.split(',') if p.strip()]
                            if not all(0 < port < 65536 for port in ports_list):
                                raise ValueError
                        except ValueError:
                            messagebox.showerror("Invalid Port", f"Invalid port list in '{s}'. Use comma-separated numbers (1-65535).")
                            return []
                elif rest:
                    messagebox.showerror("Invalid Target", f"Unexpected text after ']': '{rest}'.")
                    return []
            else:
                # Case 2: Whole string may be an IP literal (v4 or v6) without ports
                try:
                    ipaddress.ip_address(s)
                    host = s
                except ValueError:
                    # Case 3: hostname or IPv4 with ports: host:ports
                    if ':' in s:
                        host, port_str = s.split(':', 1)
                        host = host.strip()
                        port_str = port_str.strip()
                        if port_str:
                            try:
                                ports_list = [int(p.strip()) for p in port_str.split(',') if p.strip()]
                                if not all(0 < port < 65536 for port in ports_list):
                                    raise ValueError
                            except ValueError:
                                messagebox.showerror("Invalid Port", f"Invalid port list in '{s}'. Use comma-separated numbers (1-65535).")
                                return []
                    else:
                        host = s

            # Validate hostname if not an IP literal
            try:
                ipaddress.ip_address(host)
                is_ip_literal = True
            except ValueError:
                is_ip_literal = False

            if not is_ip_literal:
                hostname = host
                if len(hostname) > 253 or len(hostname) == 0:
                    messagebox.showerror("Invalid Hostname", f"The hostname '{hostname}' is not valid.")
                    return []
                labels = hostname.split('.')
                for lbl in labels:
                    if not (1 <= len(lbl) <= 63):
                        messagebox.showerror("Invalid Hostname", f"The hostname '{hostname}' has an invalid label length.")
                        return []
                    if lbl.startswith('-') or lbl.endswith('-'):
                        messagebox.showerror("Invalid Hostname", f"The hostname '{hostname}' has a label starting/ending with '-'.")
                        return []
                    for ch in lbl:
                        if not (ch.isalnum() or ch == '-'):
                            messagebox.showerror("Invalid Hostname", f"The hostname '{hostname}' contains invalid character '{ch}'.")
                            return []

            # Build target
            target: Dict[str, Any] = {'ip': host, 'ports': sorted(list(set((ports_list or []) + default_ports))), 'original_string': line}
            targets.append(target)
        return targets

    def _extract_host(self, value: str) -> str:
        """Extracts the host from an input line that may include ports and/or IPv6 brackets."""
        s = value.strip()
        if s.startswith('['):
            end = s.find(']')
            if end != -1:
                return s[1:end]
        # If it's a pure IP literal
        try:
            ipaddress.ip_address(s)
            return s
        except ValueError:
            pass
        # Otherwise, split host:ports
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
            messagebox.showwarning("Input Required", "Please enter at least one IP address or hostname.")
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
    # Do not clear status items on stop; leave last results visible.

    def launch_all_web_uis(self):
        """Launches web UIs for all targets with open web ports."""
        if not self.web_ui_targets:
            messagebox.showinfo("No Targets", "No web UIs are available to launch.")
            return
        
        for target_details in self.web_ui_targets.values():
            host_for_url = self._format_host_for_url(target_details['host'])
            url = f"{target_details['protocol']}://{host_for_url}"
            network.open_browser_with_url(url, self.browser_command)

    def launch_single_web_ui(self, original_string: str):
        """Launches the web UI for a single, specific target."""
        target_details = self.web_ui_targets.get(original_string)
        if target_details:
            host_for_url = self._format_host_for_url(target_details['host'])
            url = f"{target_details['protocol']}://{host_for_url}"
            network.open_browser_with_url(url, self.browser_command)
        else:
            messagebox.showwarning("Unavailable", "This web UI is not currently available.")

    def launch_web_ui_for_port(self, original_string: str, port: int):
        """Launches a web UI for a specific IP and port."""
        host = self._extract_host(original_string)
        
        # Determine protocol based on port
        protocol = "https"
        if port == 80:
            protocol = "http"
        host_for_url = self._format_host_for_url(host)
        url = f"{protocol}://{host_for_url}"
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
                    host = self._extract_host(original_string)
                    if original_string not in self.web_ui_targets:
                        # Determine protocol based on common web ports
                        protocol = "https"
                        if any(p in [80, 8080] for p in (port_statuses or {})):
                            protocol = "http"
                        self.web_ui_targets[original_string] = {'host': host, 'protocol': protocol}
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

    def clear_statuses(self):
        """Clears the status list and related launch state."""
        # Clear the status display UI
        self.ui.setup_status_display([])
        # Clear any tracked web UI targets and disable the launch-all button
        self.web_ui_targets.clear()
        self.ui.launch_all_button.config(state=tk.DISABLED)
        # Update the status bar for user feedback
        self.ui.update_status_bar("Statuses cleared.")
