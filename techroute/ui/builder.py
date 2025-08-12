"""
UI layout builder and wiring for TechRoute.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from typing import Dict, Any
from .types import UIContext


class BuilderMixin:
    root: tk.Tk

    # Expected attributes:
    # app_controller, status_widgets, blinking_animation_job, ping_animation_job

    def _on_canvas_configure(self: UIContext, event: tk.Event) -> None:
        # When the canvas is configured (e.g., resized), update the width of the frame inside.
        # This ensures the content frame always fills the canvas horizontally.
        canvas_width = event.width
        self.status_canvas.itemconfig(self.status_frame_window, width=canvas_width)

    def _on_status_frame_configure(self: UIContext, event: tk.Event) -> None:
        # When the content frame's size changes, update the canvas's scroll region.
        # This makes the scrollbar aware of the full content height.
        self.status_canvas.configure(scrollregion=self.status_canvas.bbox("all"))

    def _setup_ui(self: UIContext, browser_name: str) -> None:
        # Status Bar
        self.status_bar_frame = ttk.Frame(self.root)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar_label = ttk.Label(self.status_bar_frame, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, padding=(2, 5))
        self.status_bar_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        mono_font = tkfont.Font(family="Courier", size=10)
        self.status_indicator = ttk.Label(self.status_bar_frame, text="💻 ? ? ? ? ? 📠", relief=tk.SUNKEN, width=15, anchor=tk.CENTER, padding=(5, 5), font=mono_font)
        self.status_indicator.pack(side=tk.RIGHT)

        # Main Frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(3, weight=1)

        # Top Controls Frame
        self.controls_frame = ttk.Frame(self.main_frame, padding=(0, 0, 0, 10))
        self.controls_frame.grid(row=0, column=0, sticky="ew")
        self.controls_frame.columnconfigure(1, weight=1)

        # Left controls
        left_controls_frame = ttk.Frame(self.controls_frame)
        left_controls_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(left_controls_frame, text="Polling Rate (ms):", underline=0).pack(side=tk.LEFT, padx=(0, 5))
        self.polling_rate_entry = ttk.Entry(left_controls_frame, width=5)
        self.polling_rate_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.polling_rate_entry.insert(0, str(int(self.app_controller.config.get("ping_interval_seconds", 3) * 1000)))
        self.ports_button = ttk.Button(left_controls_frame, text="Ports...", underline=1, command=self._open_ports_dialog)
        self.ports_button.pack(side=tk.LEFT)
        self.services_button = ttk.Button(left_controls_frame, text="UDP Services...", underline=0, command=self._open_udp_services_dialog)
        self.services_button.pack(side=tk.LEFT, padx=(8, 0))

        # Right controls
        right_controls_frame = ttk.Frame(self.controls_frame)
        right_controls_frame.grid(row=0, column=2, sticky="e")
        self.update_button = ttk.Button(right_controls_frame, text="Update", underline=0, command=self.app_controller.update_ping_process)
        self.update_button.pack()

        # Network Information Group
        self.network_frame = ttk.LabelFrame(self.main_frame, text="Network Information", padding="10")
        self.network_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        netgrid = self.network_frame
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

        # Local services indicators (use identical indicator buttons as in status rows)
        ttk.Label(netgrid, text="Local Services:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        local_services_frame = ttk.Frame(netgrid)
        local_services_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=(6, 0), pady=(4, 0))
        # Ports to check on localhost
        self._local_service_ports = [20, 21, 22, 139, 445]
        self.local_service_indicators = {}
        for p in self._local_service_ports:
            btn = tk.Button(
                local_services_frame,
                text=f"{p}",
                bg="gray",
                fg="white",
                disabledforeground="white",
                relief="raised",
                borderwidth=1,
                state=tk.DISABLED,
                padx=4,
                pady=1,
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.local_service_indicators[p] = btn
        # Start a background update after network info loads
        try:
            self.root.after(100, getattr(self, "_start_local_services_check"))
        except Exception:
            pass

        # Targets Input Group
        self.input_frame = ttk.LabelFrame(self.main_frame, text=f"Target Browser: {browser_name}", padding="10")
        self.input_frame.grid(row=2, column=0, sticky="ew")
        ttk.Label(self.input_frame, text="Enter IPs or Hostnames, one per line").pack(pady=5)

        quick_row = ttk.Frame(self.input_frame)
        quick_row.pack(pady=(0, 5), fill=tk.X)
        
        # Left-aligned buttons
        left_quick_frame = ttk.Frame(quick_row)
        left_quick_frame.pack(side=tk.LEFT)
        ttk.Button(left_quick_frame, text="Add localhost", underline=0, command=self.app_controller.add_localhost_to_input).pack(side=tk.LEFT)
        ttk.Button(left_quick_frame, text="Add Gateway", underline=4, command=self.app_controller.add_gateway_to_input).pack(side=tk.LEFT, padx=(5, 0))

        # Spacer to push the next button to the right
        spacer = ttk.Frame(quick_row)
        spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Right-aligned button
        right_quick_frame = ttk.Frame(quick_row)
        right_quick_frame.pack(side=tk.RIGHT)
        self.clear_field_button = ttk.Button(right_quick_frame, text="Clear Field", underline=0, command=self.app_controller.clear_input_field)
        self.clear_field_button.pack()

        # Input text area with scrollbars
        text_frame = ttk.Frame(self.input_frame)
        text_frame.pack(pady=5, fill=tk.X, expand=True)
        self.ip_entry = tk.Text(text_frame, width=60, height=6, wrap="none")
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()
        vscrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=vscrollbar.set)
        hscrollbar = ttk.Scrollbar(self.input_frame, orient=tk.HORIZONTAL, command=self.ip_entry.xview)
        hscrollbar.pack(fill=tk.X)
        self.ip_entry.config(xscrollcommand=hscrollbar.set)

        # Status Area with optional Scrollbar
        self.status_container = ttk.Frame(self.main_frame)
        self.status_container.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self.status_canvas = tk.Canvas(self.status_container, borderwidth=0, highlightthickness=0)
        self.status_scrollbar = ttk.Scrollbar(self.status_container, orient="vertical", command=self.status_canvas.yview)
        self.status_frame = ttk.LabelFrame(self.status_canvas, text="Status", padding="10")

        self.status_frame_window = self.status_canvas.create_window((0, 0), window=self.status_frame, anchor="nw")

        # Layout: Canvas fills the area, Scrollbar is on the right
        self.status_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_canvas.config(yscrollcommand=self.status_scrollbar.set)

        # Bind events for resizing
        self.status_frame.bind("<Configure>", self._on_status_frame_configure)
        self.status_canvas.bind("<Configure>", self._on_canvas_configure)

        self.setup_status_display([])

        # Button Row
        button_frame = ttk.Frame(self.input_frame)
        button_frame.pack(pady=10, fill=tk.X)
        button_frame.columnconfigure(1, weight=1)
        left_button_group = ttk.Frame(button_frame)
        left_button_group.grid(row=0, column=0, sticky="w")
        self.start_stop_button = ttk.Button(left_button_group, text="Start Pinging", underline=0, command=self.app_controller.toggle_ping_process)
        self.start_stop_button.pack(side=tk.LEFT, padx=5)
        self.launch_all_button = ttk.Button(left_button_group, text="Launch Web UIs", underline=0, command=self.app_controller.launch_all_web_uis, state=tk.DISABLED)
        self.launch_all_button.pack(side=tk.LEFT, padx=5)
        right_button_group = ttk.Frame(button_frame)
        right_button_group.grid(row=0, column=2, sticky="e")
        clear_statuses_button = ttk.Button(right_button_group, text="Clear Statuses", underline=0, command=self.app_controller.clear_statuses)
        clear_statuses_button.pack(side=tk.RIGHT)
        try:
            self.clear_statuses_button = clear_statuses_button
        except Exception:
            pass

        # Key bindings and mnemonics
        self.root.bind("<Control-Return>", lambda event: self.app_controller.toggle_ping_process())
        self.root.bind("<Alt-s>", lambda event: self.start_stop_button.invoke())
        self.root.bind("<Alt-l>", lambda event: self.launch_all_button.invoke())
        self.root.bind("<Alt-o>", lambda event: self.ports_button.invoke())
        self.root.bind("<Alt-n>", lambda event: self.services_button.invoke())
        self.root.bind("<Alt-u>", lambda event: self.update_button.invoke())
        self.root.bind("<Alt-c>", lambda event: self.app_controller.clear_statuses())
        self.root.bind("<Alt-a>", lambda event: self.app_controller.add_localhost_to_input())
        self.root.bind("<Alt-g>", lambda event: self.app_controller.add_gateway_to_input())
        self.root.bind("<Alt-f>", lambda event: self.clear_field_button.invoke() if self.clear_field_button else None)
        self.root.bind("<Alt-p>", lambda event: self.polling_rate_entry.focus_set())
        self.root.bind("<Alt-i>", lambda event: self.ip_entry.focus_set())

    def lock_min_size_to_current(self: UIContext) -> None:
        try:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            self.root.minsize(w, h)
        except Exception:
            pass

    def shrink_to_fit(self: UIContext) -> None:
        try:
            self.root.update_idletasks()
            req_w = self.root.winfo_reqwidth()
            req_h = self.root.winfo_reqheight()
            # Only grow the window if needed; don't shrink below current size
            cur_w = max(1, self.root.winfo_width())
            cur_h = max(1, self.root.winfo_height())
            new_w = max(cur_w, req_w)
            new_h = max(cur_h, req_h)

            # On Linux, set both geometry and minsize when not actively dragging
            try:
                import platform as _platform
                if _platform.system() == "Linux":
                    if not getattr(self, "_resizing_active", False):
                        self.root.geometry(f"{new_w}x{new_h}")
                    self.root.minsize(new_w, new_h)
                    return
            except Exception:
                pass

            self.root.geometry(f"{new_w}x{new_h}")
        except Exception:
            pass

    def update_network_info(self: UIContext, info: Dict[str, Any]) -> None:
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
            pass

    # --- Local Services (localhost) checker ---
    def _start_local_services_check(self: UIContext) -> None:
        """Kick off an asynchronous check of local TCP ports and schedule periodic refreshes."""
        try:
            import threading
            if getattr(self, "_local_services_thread_running", False):
                return
            setattr(self, "_local_services_thread_running", True)

            def _worker():
                try:
                    from .. import network as _net
                    ports = getattr(self, "_local_service_ports", [20, 21, 22, 139, 445])
                    timeout = 0.5
                    results: Dict[int, str] = {}
                    # Check both IPv4 and IPv6 loopback; consider Open if either responds
                    host_v4 = "127.0.0.1"
                    host_v6 = "::1"
                    for p in ports:
                        try:
                            status_v4 = _net.check_tcp_port(host_v4, p, timeout)
                        except Exception:
                            status_v4 = "Closed"
                        try:
                            status_v6 = _net.check_tcp_port(host_v6, p, timeout)
                        except Exception:
                            status_v6 = "Closed"
                        results[p] = ("Open" if (status_v4 == "Open" or status_v6 == "Open") else "Closed")

                    def _apply():
                        try:
                            for p, status in results.items():
                                btn = self.local_service_indicators.get(p)
                                if not btn:
                                    continue
                                is_open = (status == "Open")
                                btn.config(bg=("green" if is_open else "red"), fg="white")
                        except Exception:
                            pass
                    try:
                        self.root.after(0, _apply)
                    except Exception:
                        pass
                finally:
                    setattr(self, "_local_services_thread_running", False)
                    # Schedule next refresh in background (every ~5 seconds)
                    try:
                        self.root.after(5000, getattr(self, "_start_local_services_check"))
                    except Exception:
                        pass

            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            # If anything goes wrong, try again later quietly
            try:
                self.root.after(5000, getattr(self, "_start_local_services_check"))
            except Exception:
                pass
