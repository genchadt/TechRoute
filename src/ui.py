# src/ui.py

"""
UI component for the PrintPing application.

This module defines the AppUI class, which is responsible for building
and managing all the Tkinter widgets for the main application window.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, Optional

class AppUI:
    """Manages the user interface of the PrintPing application."""

    def __init__(self, root: tk.Tk, app_controller, browser_name: str):
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

        self._setup_menu()
        self._setup_ui(browser_name)

    def _setup_menu(self):
        """Creates the main application menu bar."""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # --- File Menu ---
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu, underline=0)
        file_menu.add_command(label="New", underline=0)
        file_menu.add_command(label="Open", underline=0)
        file_menu.add_command(label="Save", underline=0)
        file_menu.add_command(label="Save As", underline=5)

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
        
        self.start_stop_button = ttk.Button(self.input_frame, text="Start Pinging", command=self.app_controller.toggle_ping_process, underline=0)
        self.start_stop_button.pack(pady=10)

        self.root.bind('<Control-Return>', lambda event: self.app_controller.toggle_ping_process())
        self.root.bind('<Alt-s>', lambda event: self.start_stop_button.invoke())

    def update_status_bar(self, message: str):
        """Updates the text in the status bar."""
        self.status_bar_label.config(text=message)

    def setup_status_display(self, targets: List[Dict[str, Any]]):
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
                    pass
            
            self.status_widgets[original_string] = {"label": label, "indicator": indicator, "port_widgets": port_widgets}

    def update_status_in_gui(self, original_string: str, status: str, color: str, launched_browser: bool, port_statuses: Optional[Dict[int, str]], latency_str: str):
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
                    pass
