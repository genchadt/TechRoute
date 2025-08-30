"""
UI animations for the TechRoute status indicator.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

class Animator:
    """Manages animations for the status indicator widget."""

    def __init__(self, root: tk.Tk, status_indicator: ttk.Label):
        self.root = root
        self.status_indicator = status_indicator
        self.animation_job = None
        self._is_blinking = False
        self._is_pinging = False

    def start_blinking_animation(self):
        """Starts a blinking animation with question marks."""
        if self._is_blinking:
            return
        self.stop_animation()
        self._is_blinking = True
        self._blink()

    def _blink(self):
        """Helper function for the blinking animation."""
        if not self._is_blinking:
            return
        try:
            current_text = self.status_indicator.cget("text")
            new_text = "💻           📠" if "?" in current_text else "💻 ? ? ? ? ? 📠"
            self.status_indicator.config(text=new_text)
            self.animation_job = self.root.after(500, self._blink)
        except tk.TclError:
            self.animation_job = None
            self._is_blinking = False

    def stop_animation(self):
        """Stops any running animation."""
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
            self.animation_job = None
        self._is_blinking = False
        self._is_pinging = False
        try:
            # Set a neutral state when stopping, not a specific animation frame
            self.status_indicator.config(text="💻 . . . . . 📠")
        except tk.TclError:
            pass

    def reset_status_indicator(self):
        """Resets the status indicator to its initial state."""
        self.stop_animation()
        try:
            self.status_indicator.config(text="💻 ? ? ? ? ? 📠")
        except tk.TclError:
            pass

    def run_ping_animation(self, duration_ms: int):
        """Starts a continuous ping animation loop scaled by the polling rate."""
        if self._is_pinging:
            return
        
        self.stop_animation()
        self._is_pinging = True
        self._ping_loop(duration_ms)

    def _ping_loop(self, duration_ms: int):
        """The core loop for the ping animation."""
        if not self._is_pinging:
            self.reset_status_indicator()
            return

        frames = [
            "💻 • . . . . 📠", "💻 . • . . . 📠", "💻 . . • . . 📠",
            "💻 . . . • . 📠", "💻 . . . . • 📠", "💻 . . . • . 📠",
            "💻 . . • . . 📠", "💻 . • . . . 📠", "💻 • . . . . 📠",
        ]
        
        animation_duration = max(500, duration_ms - 500)
        frame_delay = animation_duration // len(frames)
        
        def update_frame(frame_index: int):
            if not self._is_pinging:
                self.reset_status_indicator()
                return

            try:
                if frame_index < len(frames):
                    self.status_indicator.config(text=frames[frame_index])
                    self.animation_job = self.root.after(frame_delay, update_frame, frame_index + 1)
                else:
                    # Animation cycle finished, prepare for the next one
                    self.status_indicator.config(text="💻 . . . . . 📠")
                    wait_time = max(100, duration_ms - animation_duration)
                    self.animation_job = self.root.after(wait_time, self._ping_loop, duration_ms)
            except tk.TclError:
                self._is_pinging = False
                self.animation_job = None

        update_frame(0)
