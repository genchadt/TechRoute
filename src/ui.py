# src/ui.py

"""
UI component for the TechRoute application.

This module defines the AppUI class, which is responsible for building
and managing all the Tkinter widgets for the main application window.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, Optional

class AppUI:
    """Manages the user interface of the TechRoute application."""

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

    def _on_frame_configure(self, event=None):
        """Reset the scroll region to encompass the inner frame."""
        self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        """Adjust the width of the inner frame to match the canvas."""
        self.status_canvas.itemconfig(self.canvas_window, width=event.width)

    def _setup_ui(self, browser_name: str):
        """Creates and configures the UI elements."""
        self.status_bar_label = ttk.Label(self.root, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, padding=2)
        self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Configure grid layout to ensure status_frame expands ---
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        self.input_frame = ttk.LabelFrame(self.main_frame, text=f"Target Browser: {browser_name}", padding="10")
        self.input_frame.grid(row=0, column=0, sticky="ew")
        
        # --- Scrollable Status Frame ---
        # Container for the canvas and scrollbar
        status_container = ttk.LabelFrame(self.main_frame, text="Status", padding=(10, 5))
        status_container.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        status_container.rowconfigure(0, weight=1)
        status_container.columnconfigure(0, weight=1)

        # Canvas to hold the scrollable content
        self.status_canvas = tk.Canvas(status_container, borderwidth=0, highlightthickness=0)
        self.status_scrollbar = ttk.Scrollbar(status_container, orient="vertical", command=self.status_canvas.yview)
        self.status_canvas.configure(yscrollcommand=self.status_scrollbar.set)

        # This frame will hold the actual status widgets
        self.status_frame = ttk.Frame(self.status_canvas)
        self.canvas_window = self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")

        # Place canvas and scrollbar
        self.status_canvas.grid(row=0, column=0, sticky="nsew")
        self.status_scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind events for resizing
        self.status_frame.bind("<Configure>", self._on_frame_configure)
        self.status_canvas.bind("<Configure>", self._on_canvas_configure)

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
            
            # Use a Frame for each entry row
            row_frame = ttk.Frame(self.status_frame)
            row_frame.pack(fill=tk.X, expand=True, pady=2)
            row_frame.columnconfigure(1, weight=1) # Allow the label/port frame to expand

            indicator = tk.Label(row_frame, text="", width=5, bg="gray", fg="white", padx=4, pady=1, relief="raised", borderwidth=1)
            indicator.grid(row=0, column=0, padx=(0, 10), sticky='n')

            # Frame to hold the main label and the port statuses
            details_frame = ttk.Frame(row_frame)
            details_frame.grid(row=0, column=1, sticky='ew')

            label = ttk.Label(details_frame, text=f"{original_string}: Pinging...")
            label.pack(side=tk.LEFT, pady=2, anchor='w')
            
            port_frame = ttk.Frame(details_frame)
            port_frame.pack(side=tk.LEFT, padx=(10, 0), anchor='w', fill=tk.X, expand=True)

            port_widgets = {}
            if ports:
                for port in ports:
                    port_label = tk.Label(
                        port_frame,
                        text=f"{port}",
                        font=("Segoe UI", 7, "bold"),
                        bg="gray",
                        fg="white",
                        padx=3,
                        pady=1,
                        relief="raised",
                        borderwidth=1
                    )
                    port_label.pack(side=tk.LEFT, padx=2)
                    port_widgets[port] = port_label
            
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
                    if port in port_widgets:
                        port_widget = port_widgets[port]
                        port_color = "#0078D4" if port_status == "Open" else "#F7630C"  # Win10 Blue/Orange
                        port_widget.config(bg=port_color)
                    
        else:
            # This can happen if the UI is cleared while a thread is about to send an update.
            # It's safe to just ignore it.
            print(f"Warning: Received status update for '{original_string}' but its UI widget no longer exists.")
