# src/ui.py

"""
UI component for the TechRoute application.

This module defines the AppUI class, which is responsible for building
and managing all the Tkinter widgets for the main application window.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, messagebox, simpledialog
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from . import configuration

if TYPE_CHECKING:
    from .app import TechRouteApp


class AppUI:
    """Manages the user interface of the TechRoute application."""

    def __init__(self, root: tk.Tk, app_controller: 'TechRouteApp', browser_name: str):
        """
        Initializes the UI.

        Args:
            root: The root Tkinter window.
            app_controller: The main application controller instance.
            browser_name: The name of the detected browser to display.
        """
        self.root = root
        self.app_controller = app_controller
        self.status_widgets: Dict[str, Dict[str, Any]] = {}
        self.blinking_animation_job: Optional[str] = None
        self.ping_animation_job: Optional[str] = None

        self._setup_menu()
        self._setup_ui(browser_name)

    def show_scrollbar(self):
        """Makes the status frame scrollbar visible."""
        self.status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_canvas.config(yscrollcommand=self.status_scrollbar.set)

    def hide_scrollbar(self):
        """Hides the status frame scrollbar."""
        self.status_scrollbar.pack_forget()
        # Unset the scroll command to prevent the canvas from trying to use a hidden scrollbar
        self.status_canvas.config(yscrollcommand="")

    def _setup_menu(self):
        """Creates the main application menu bar."""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # --- File Menu ---
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu, underline=0)
        file_menu.add_command(label="New", underline=0)
        file_menu.add_command(label="Open...", underline=0)
        file_menu.add_command(label="Save List", underline=0)
        file_menu.add_command(label="Save List As...", underline=5)

        # --- Edit Menu ---
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Edit", menu=edit_menu, underline=0)
        edit_menu.add_command(label="Clear", underline=0)

        # --- View Menu ---
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="View", menu=view_menu, underline=0)
        view_menu.add_command(label="Zoom In", underline=5)
        view_menu.add_command(label="Zoom Out", underline=5)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show Menubar", underline=5)
        view_menu.add_checkbutton(label="Show Statusbar", underline=5)

        # --- Settings Menu ---
        settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Settings", menu=settings_menu, underline=0)
        settings_menu.add_command(label="Preferences", underline=0)

        # --- Help Menu ---
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=help_menu, underline=0)
        help_menu.add_command(label="Check for Updates", underline=6)
        help_menu.add_separator()
        help_menu.add_command(label="Github", underline=0)
        help_menu.add_command(label="About", underline=0)

    def _open_ports_dialog(self):
        """Opens a dialog to edit the default ports."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Default Ports")
        dialog.geometry("300x250")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Default ports to check (one per line):").pack(pady=5, padx=10, anchor='w')

        text_frame = ttk.Frame(dialog)
        text_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        port_text = tk.Text(text_frame, width=20, height=8)
        port_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=port_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        port_text.config(yscrollcommand=scrollbar.set)

        current_ports = self.app_controller.config.get('default_ports_to_check', [])
        port_text.insert(tk.END, "\n".join(map(str, current_ports)))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        def save_ports():
            new_ports_str = port_text.get("1.0", tk.END).strip()
            if not new_ports_str:
                new_ports = []
            else:
                try:
                    new_ports = [int(p.strip()) for p in new_ports_str.splitlines() if p.strip()]
                    if not all(0 < port < 65536 for port in new_ports):
                        raise ValueError("Port number out of range.")
                except ValueError:
                    messagebox.showerror("Invalid Ports", "Please enter valid port numbers (1-65535), one per line.", parent=dialog)
                    return
            
            new_config = self.app_controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(new_ports)))
            self.app_controller.update_config(new_config)
            dialog.destroy()

        def reset_to_default():
            default_ports = configuration.DEFAULT_CONFIG.get('default_ports_to_check', [])
            new_config = self.app_controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(default_ports)))
            self.app_controller.update_config(new_config)
            dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_ports).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Default", command=reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

    def _setup_ui(self, browser_name: str):
        """Creates and configures the UI elements."""
        # --- Status Bar ---
        self.status_bar_frame = ttk.Frame(self.root)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_bar_label = ttk.Label(self.status_bar_frame, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, padding=2)
        self.status_bar_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Use a monospace font for the indicator to prevent width changes during animation
        mono_font = tkfont.Font(family="Courier", size=10)
        self.status_indicator = ttk.Label(self.status_bar_frame, text="💻 ? ? ? ? ? 📠", relief=tk.SUNKEN, width=15, anchor=tk.CENTER, padding=(5,2), font=mono_font)
        self.status_indicator.pack(side=tk.RIGHT)

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Configure grid layout ---
        # DO NOT give row 2 weight, as this prevents the window from shrinking to fit content.
        # The window resizing will be handled manually in the App class.
        self.main_frame.columnconfigure(0, weight=1)

        # --- Top Controls Frame ---
        self.controls_frame = ttk.Frame(self.main_frame, padding=(0, 0, 0, 10))
        self.controls_frame.grid(row=0, column=0, sticky="ew")
        self.controls_frame.columnconfigure(1, weight=1) # Make space between left and right buttons

        left_controls_frame = ttk.Frame(self.controls_frame)
        left_controls_frame.grid(row=0, column=0, sticky='w')
        
        ttk.Label(left_controls_frame, text="Polling Rate (ms):").pack(side=tk.LEFT, padx=(0, 5))
        self.polling_rate_entry = ttk.Entry(left_controls_frame, width=5)
        self.polling_rate_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.polling_rate_entry.insert(0, str(int(self.app_controller.config.get('ping_interval_seconds', 3) * 1000)))

        self.ports_button = ttk.Button(left_controls_frame, text="Ports...", command=self._open_ports_dialog)
        self.ports_button.pack(side=tk.LEFT)

        right_controls_frame = ttk.Frame(self.controls_frame)
        right_controls_frame.grid(row=0, column=2, sticky='e')

        self.update_button = ttk.Button(right_controls_frame, text="Update", command=self.app_controller.update_ping_process)
        self.update_button.pack()

        self.input_frame = ttk.LabelFrame(self.main_frame, text=f"Target Browser: {browser_name}", padding="10")
        self.input_frame.grid(row=1, column=0, sticky="ew")
        
        # --- Status Area with optional Scrollbar ---
        self.status_container = ttk.Frame(self.main_frame)
        self.status_container.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.status_container.rowconfigure(0, weight=1)
        self.status_container.columnconfigure(0, weight=1)

        self.status_canvas = tk.Canvas(self.status_container, borderwidth=0, highlightthickness=0)
        self.status_scrollbar = ttk.Scrollbar(self.status_container, orient="vertical", command=self.status_canvas.yview)
        
        # This frame will contain the actual status widgets
        self.status_frame = ttk.LabelFrame(self.status_canvas, text="Status", padding="10")

        self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")
        self.status_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Initially hide the scrollbar
        self.hide_scrollbar()

        self.status_frame.bind("<Configure>", lambda e: self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all")))


        ttk.Label(self.input_frame, text="Enter IPs, one per line (e.g., 192.168.1.50:80,443):").pack(pady=5)

        text_frame = ttk.Frame(self.input_frame)
        text_frame.pack(pady=5, fill=tk.X, expand=True)

        self.ip_entry = tk.Text(text_frame, width=40, height=6)
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=scrollbar.set)
        
        # --- Button Frame ---
        button_frame = ttk.Frame(self.input_frame)
        button_frame.pack(pady=10)

        self.start_stop_button = ttk.Button(button_frame, text="Start Pinging", command=self.app_controller.toggle_ping_process, underline=0)
        self.start_stop_button.pack(side=tk.LEFT, padx=5)

        self.launch_all_button = ttk.Button(button_frame, text="Launch Web UIs", command=self.app_controller.launch_all_web_uis, state=tk.DISABLED)
        self.launch_all_button.pack(side=tk.LEFT, padx=5)

        self.root.bind('<Control-Return>', lambda event: self.app_controller.toggle_ping_process())
        self.root.bind('<Alt-s>', lambda event: self.start_stop_button.invoke())

    def start_blinking_animation(self):
        """Starts a blinking animation with question marks."""
        self.stop_ping_animation()  # Ensure ping animation is stopped
        if self.blinking_animation_job:
            self.root.after_cancel(self.blinking_animation_job)

        self._blink()

    def _blink(self):
        """Helper function for the blinking animation."""
        current_text = self.status_indicator.cget("text")
        if "?" in current_text:
            new_text = "💻           📠"
        else:
            new_text = "💻 ? ? ? ? ? 📠"
        self.status_indicator.config(text=new_text)
        self.blinking_animation_job = self.root.after(500, self._blink)

    def stop_blinking_animation(self):
        """Stops the blinking animation."""
        if self.blinking_animation_job:
            self.root.after_cancel(self.blinking_animation_job)
            self.blinking_animation_job = None
        self.status_indicator.config(text="💻 . . . . . 📠")

    def stop_ping_animation(self):
        """Stops any in-progress ping animation."""
        if self.ping_animation_job:
            self.root.after_cancel(self.ping_animation_job)
            self.ping_animation_job = None

    def reset_status_indicator(self):
        """Resets the status indicator to its initial state."""
        self.stop_blinking_animation()
        self.stop_ping_animation()
        self.status_indicator.config(text="💻 ? ? ? ? ? 📠")

    def run_ping_animation(self, polling_rate_ms: int):
        """Fires a one-shot animation of an arrow, scaled by the polling rate."""
        self.stop_ping_animation()  # Cancel any previous animation
        self.stop_blinking_animation()  # Ensure the '???' animation is stopped

        frames = [
            "💻 → . . . . 📠",
            "💻 . → . . . 📠",
            "💻 . . → . . 📠",
            "💻 . . . → . 📠",
            "💻 . . . . → 📠",
        ]
        num_frames = len(frames)

        # Lower polling rate -> faster animation.
        # Map polling rate to a total animation duration, clamped to a sensible range.
        total_duration_ms = polling_rate_ms / 5.0
        total_duration_ms = max(150, min(total_duration_ms, 600))

        frame_delay = int(total_duration_ms / num_frames)

        def update_frame(frame_index):
            if frame_index < num_frames:
                self.status_indicator.config(text=frames[frame_index])
                next_frame_index = frame_index + 1
                self.ping_animation_job = self.root.after(frame_delay, update_frame, next_frame_index)
            else:
                # Animation finished, reset to idle state.
                self.status_indicator.config(text="💻 . . . . . 📠")
                self.ping_animation_job = None
        
        update_frame(0)

    def update_status_bar(self, message: str):
        self.status_bar_label.config(text=message)

    def setup_status_display(self, targets: List[Dict[str, Any]]):
        """Creates the initial status widgets for each IP address."""
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()

        for target in targets:
            original_string, ports = target['original_string'], target['ports']
            
            # Use a Frame for each entry row
            row_frame = ttk.Frame(self.status_frame)
            row_frame.pack(fill=tk.X, expand=True, pady=2)
            row_frame.columnconfigure(1, weight=1) # Allow the label to expand

            # This button will show ping status and be clickable to open the UI
            ping_button = tk.Button(row_frame, text="", width=5, bg="gray", fg="white",
                                    disabledforeground="white",
                                    relief="raised", borderwidth=1, state=tk.DISABLED,
                                    command=lambda s=original_string: self.app_controller.launch_single_web_ui(s))
            ping_button.grid(row=0, column=0, padx=(0, 10), sticky='w')

            # Main label for the IP address and status
            label = ttk.Label(row_frame, text=f"{original_string}: Pinging...")
            label.grid(row=0, column=1, sticky='w')
            
            # Frame to hold port status labels
            port_frame = ttk.Frame(row_frame)
            port_frame.grid(row=0, column=2, sticky='e')

            port_widgets = {}
            if ports:
                for port in ports:
                    # Create a button for each port. It will be enabled/disabled based on status.
                    port_button = tk.Button(port_frame, text=f"{port}", bg="gray", fg="white", 
                                            disabledforeground="white",
                                            relief="raised", borderwidth=1, state=tk.DISABLED,
                                            padx=4, pady=1)
                    port_button.pack(side=tk.LEFT, padx=2)

                    # Make relevant web ports (80, 443) clickable by assigning a command
                    if port in [80, 443]:
                        port_button.config(command=lambda s=original_string, p=port: self.app_controller.launch_web_ui_for_port(s, p))
                    
                    port_widgets[port] = port_button
            
            self.status_widgets[original_string] = {
                "label": label, 
                "ping_button": ping_button, # Replaces 'indicator' and 'ui_button'
                "port_widgets": port_widgets
            }

    def update_status_in_gui(self, original_string: str, status: str, color: str, port_statuses: Optional[Dict[int, str]], latency_str: str, web_port_open: bool):
        """Updates the GUI widgets for a specific IP. Must be called from the main thread."""
        if original_string in self.status_widgets:
            widgets = self.status_widgets[original_string]
            ip_part = original_string.split(':', 1)[0]

            ping_button = widgets["ping_button"]
            ping_button.config(bg=color, text=latency_str if status == "Online" else "FAIL", fg="white")
            
            # The button is clickable only if a web port is open
            is_launchable = web_port_open
            ping_button.config(state=tk.NORMAL if is_launchable else tk.DISABLED, 
                               cursor="hand2" if is_launchable else "")

            widgets["label"].config(text=f"{ip_part}: {status}")
            
            if port_statuses:
                port_widgets = widgets.get("port_widgets", {})
                for port, port_status in port_statuses.items():
                    if port in port_widgets:
                        port_widget = port_widgets[port]
                        is_open = (port_status == "Open")
                        port_color = "green" if is_open else "red"
                        port_widget.config(bg=port_color, fg="white")

                        # For relevant web ports, enable the button if the port is open
                        if port in [80, 443]:
                            port_widget.config(state=tk.NORMAL if is_open else "",
                                               cursor="hand2" if is_open else "")

            # When pinging stops, clear port status text
            elif not self.app_controller.is_pinging:
                port_widgets = widgets.get("port_widgets", {})
                for port, widget in port_widgets.items():
                    widget.config(bg="gray", state=tk.DISABLED, cursor="", fg="white")
                
                # Also reset the ping button
                ping_button.config(state=tk.DISABLED, bg="gray", text="", cursor="", fg="white")

        else:
            # This can happen if the UI is cleared while a thread is about to send an update.
            # It's safe to just ignore it.
            print(f"Warning: Received status update for '{original_string}' but its UI widget no longer exists.")
