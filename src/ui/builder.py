"""
UI layout builder and wiring for TechRoute.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from typing import Dict, Any, List, cast
from .types import UIContext


class BuilderMixin:
    root: tk.Tk

    # Expected attributes:
    # app_controller, status_widgets, blinking_animation_job, ping_animation_job

    def show_scrollbar(self: UIContext) -> None:
        """Makes the status frame scrollbar visible."""
        self.status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_canvas.config(yscrollcommand=self.status_scrollbar.set)

    def hide_scrollbar(self: UIContext) -> None:
        """Hides the status frame scrollbar."""
        self.status_scrollbar.pack_forget()
        # Unset the scroll command to prevent the canvas from trying to use a hidden scrollbar
        self.status_canvas.config(yscrollcommand="")

    def _on_canvas_configure(self: UIContext, event: tk.Event) -> None:
        """When the canvas is resized, update the width of the frame inside it."""
        canvas_width = event.width
        self.status_canvas.itemconfig(self.status_frame_window, width=canvas_width)

    def _on_status_frame_configure(self: UIContext, event: tk.Event) -> None:
        """When the frame's content changes size, update the canvas scroll region."""
        self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all"))
        # Also resize the canvas height to snugly fit its contents
        try:
            self._schedule_status_canvas_height_update()
        except Exception:
            pass

    def _setup_ui(self: UIContext, browser_name: str) -> None:
        """Creates and configures the UI elements."""
        # --- Status Bar ---
        self.status_bar_frame = ttk.Frame(self.root)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_bar_label = ttk.Label(
            self.status_bar_frame,
            text="Ready.",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(2, 5),
        )
        self.status_bar_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Use a monospace font for the indicator to prevent width changes during animation
        mono_font = tkfont.Font(family="Courier", size=10)
        self.status_indicator = ttk.Label(
            self.status_bar_frame,
            text="💻 ? ? ? ? ? 📠",
            relief=tk.SUNKEN,
            width=15,
            anchor=tk.CENTER,
            padding=(5, 5),
            font=mono_font,
        )
        self.status_indicator.pack(side=tk.RIGHT)

        self.main_frame = ttk.Frame(self.root, padding="10")
        # Do not force the main frame to expand vertically; let content dictate size
        self.main_frame.pack(fill=tk.X, expand=False)

        # --- Configure grid layout ---
        # Avoid forcing vertical expansion; shrink to fit contents
        # self.main_frame.rowconfigure(3, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        # --- Top Controls Frame ---
        self.controls_frame = ttk.Frame(self.main_frame, padding=(0, 0, 0, 10))
        self.controls_frame.grid(row=0, column=0, sticky="ew")
        self.controls_frame.columnconfigure(1, weight=1)  # Space between left and right groups

        left_controls_frame = ttk.Frame(self.controls_frame)
        left_controls_frame.grid(row=0, column=0, sticky="w")

        ttk.Label(left_controls_frame, text="Polling Rate (ms):").pack(side=tk.LEFT, padx=(0, 5))
        self.polling_rate_entry = ttk.Entry(left_controls_frame, width=5)
        self.polling_rate_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.polling_rate_entry.insert(0, str(int(self.app_controller.config.get("ping_interval_seconds", 3) * 1000)))

        self.ports_button = ttk.Button(left_controls_frame, text="Ports...", command=self._open_ports_dialog)
        self.ports_button.pack(side=tk.LEFT)

        right_controls_frame = ttk.Frame(self.controls_frame)
        right_controls_frame.grid(row=0, column=2, sticky="e")

        self.update_button = ttk.Button(right_controls_frame, text="Update", command=self.app_controller.update_ping_process)
        self.update_button.pack()

        # --- Network Information Group ---
        self.network_frame = ttk.LabelFrame(self.main_frame, text="Network Information", padding="10")
        self.network_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        netgrid = self.network_frame
        # Labels: IPv4, IPv6, Gateway, Subnet Mask
        ttk.Label(netgrid, text="IPv4:").grid(row=0, column=0, sticky="w")
        self.netinfo_v4 = ttk.Label(netgrid, text="Detecting…")
        self.netinfo_v4.grid(row=0, column=1, sticky="w", padx=(6, 0))

        ttk.Label(netgrid, text="IPv6:").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.netinfo_v6 = ttk.Label(netgrid, text="Detecting…")
        self.netinfo_v6.grid(row=0, column=3, sticky="w", padx=(6, 0))

        ttk.Label(netgrid, text="Gateway:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.netinfo_gw = ttk.Label(netgrid, text="Detecting…")
        self.netinfo_gw.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(4, 0))

        ttk.Label(netgrid, text="Subnet Mask:").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(4, 0))
        self.netinfo_mask = ttk.Label(netgrid, text="Detecting…")
        self.netinfo_mask.grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(4, 0))

        # --- Targets Input Group ---
        self.input_frame = ttk.LabelFrame(self.main_frame, text=f"Target Browser: {browser_name}", padding="10")
        self.input_frame.grid(row=2, column=0, sticky="ew")

        # --- Status Area with optional Scrollbar ---
        self.status_container = ttk.Frame(self.main_frame)
        self.status_container.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        # Don't give extra weight; let the canvas height follow content

        self.status_canvas = tk.Canvas(self.status_container, borderwidth=0, highlightthickness=0)
        self.status_scrollbar = ttk.Scrollbar(self.status_container, orient="vertical", command=self.status_canvas.yview)

        # This frame will contain the actual status widgets
        self.status_frame = ttk.LabelFrame(self.status_canvas, text="Status", padding="10")

        self.status_frame_window = self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")
        # Fill horizontally so borders align; don't force vertical expansion
        self.status_canvas.pack(side=tk.LEFT, fill=tk.X, expand=False)

        # Initially hide the scrollbar
        self.hide_scrollbar()

        # Bind events to handle resizing of the frame within the canvas
        self.status_frame.bind("<Configure>", self._on_status_frame_configure)
        self.status_canvas.bind("<Configure>", self._on_canvas_configure)

        # Set up the initial empty state
        self.setup_status_display([])

        ttk.Label(
            self.input_frame,
            text="Enter IPs or Hostnames, one per line"
        ).pack(pady=5)
        # Quick insert buttons row (beneath label, above text field)
        quick_row = ttk.Frame(self.input_frame)
        quick_row.pack(pady=(0, 5), fill=tk.X)
        ttk.Button(quick_row, text="Add localhost", command=self.app_controller.add_localhost_to_input).pack(side=tk.LEFT)
        ttk.Button(quick_row, text="Add Gateway", command=self.app_controller.add_gateway_to_input).pack(side=tk.LEFT, padx=(5, 0))

        text_frame = ttk.Frame(self.input_frame)
        text_frame.pack(pady=5, fill=tk.X, expand=True)

        self.ip_entry = tk.Text(text_frame, width=40, height=6)
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=scrollbar.set)

        # --- Button Row: left-aligned Start/Launch, right-aligned Clear ---
        button_frame = ttk.Frame(self.input_frame)
        button_frame.pack(pady=10, fill=tk.X)
        # Create a stretchy middle column to push right group to the edge
        button_frame.columnconfigure(1, weight=1)

        left_button_group = ttk.Frame(button_frame)
        left_button_group.grid(row=0, column=0, sticky="w")

        self.start_stop_button = ttk.Button(
            left_button_group,
            text="Start Pinging",
            command=self.app_controller.toggle_ping_process,
            underline=0,
        )
        self.start_stop_button.pack(side=tk.LEFT, padx=5)

        self.launch_all_button = ttk.Button(
            left_button_group,
            text="Launch Web UIs",
            command=self.app_controller.launch_all_web_uis,
            state=tk.DISABLED,
        )
        self.launch_all_button.pack(side=tk.LEFT, padx=5)

        right_button_group = ttk.Frame(button_frame)
        right_button_group.grid(row=0, column=2, sticky="e")

        clear_statuses_button = ttk.Button(
            right_button_group,
            text="Clear Statuses",
            command=self.app_controller.clear_statuses,
        )
        clear_statuses_button.pack(side=tk.RIGHT)

        # Key bindings
        self.root.bind("<Control-Return>", lambda event: self.app_controller.toggle_ping_process())
        self.root.bind("<Alt-s>", lambda event: self.start_stop_button.invoke())
        # Ensure initial geometry wraps content tightly
        try:
            self._schedule_status_canvas_height_update()
        except Exception:
            pass

    def _schedule_status_canvas_height_update(self: UIContext) -> None:
        """Schedule a canvas height recalculation after idle to coalesce rapid changes."""
        job_attr = "_status_canvas_height_job"
        # Cancel any pending job to avoid redundant resizes
        job_id = getattr(self, job_attr, None)
        if job_id:
            try:
                self.root.after_cancel(job_id)
            except Exception:
                pass
        def _do():
            try:
                # Call the private helper safely
                self._update_status_canvas_height()
            except Exception:
                pass
        setattr(self, job_attr, self.root.after_idle(_do))

    def _update_status_canvas_height(self: UIContext) -> None:
        """Resize the status canvas height to tightly wrap its content when scrollbar is hidden."""
        try:
            self.root.update_idletasks()
            # Compute required height of the LabelFrame inside the canvas
            req_h = max(1, self.status_frame.winfo_reqheight())
            # If scrollbar is visible, keep the current canvas height to allow scrolling
            scrollbar_visible = bool(self.status_scrollbar.winfo_ismapped())
            if not scrollbar_visible:
                self.status_canvas.configure(height=req_h)
        except Exception:
            pass

    def lock_min_size_to_current(self: UIContext) -> None:
        """Lock the window's minimum size to its current width/height to prevent over-shrinking."""
        try:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            # Use minsize to prevent shrinking below the current footprint, while still allowing growth
            self.root.minsize(w, h)
        except Exception:
            pass

    def shrink_to_fit(self: UIContext) -> None:
        """Resize the root window to the requested size of its contents."""
        try:
            self.root.update_idletasks()
            req_w = self.root.winfo_reqwidth()
            req_h = self.root.winfo_reqheight()
            # geometry accepts widthxheight; top-left position left unchanged
            self.root.geometry(f"{req_w}x{req_h}")
        except Exception:
            pass

    def update_network_info(self: UIContext, info: Dict[str, Any]) -> None:
        """Update the Network Information group labels."""
        try:
            v4 = info.get("primary_ipv4") or "n/a"
            v6 = info.get("primary_ipv6") or "n/a"
            gw = info.get("gateway") or "n/a"
            mask = info.get("subnet_mask") or "n/a"
            self.netinfo_v4.config(text=str(v4))
            self.netinfo_v6.config(text=str(v6))
            self.netinfo_gw.config(text=str(gw))
            self.netinfo_mask.config(text=str(mask))
        except Exception:
            # If labels are not yet created or window closing, ignore
            pass
