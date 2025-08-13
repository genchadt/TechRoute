"""
UI animations for the TechRoute status indicator.

Provides a mixin with small, self-contained animation methods.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from .types import AppUIProtocol

class AnimationsMixin(AppUIProtocol):
    """Animation helpers for the AppUI status indicator."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def run_ping_animation(self, polling_rate_ms: int):
        """Fires a one-shot animation of a moving dot, scaled by the polling rate."""
        if self._is_pinging:
            return
        
        self.stop_animation()
        self._is_pinging = True

        frames = [
            "💻 • . . . . 📠", "💻 . • . . . 📠", "💻 . . • . . 📠",
            "💻 . . . • . 📠", "💻 . . . . • 📠", "💻 . . . • . 📠",
            "💻 . . • . . 📠", "💻 . • . . . 📠", "💻 • . . . . 📠",
        ]
        
        # Use polling_rate_ms to determine frame delay, making animation speed responsive
        # Ensure frame_delay is not too fast or slow
        frame_delay = max(50, min(200, polling_rate_ms // len(frames)))

        def update_frame(frame_index: int):
            if not self._is_pinging:
                self.reset_status_indicator()
                return

            try:
                if frame_index < len(frames):
                    self.status_indicator.config(text=frames[frame_index])
                    self.animation_job = self.root.after(frame_delay, update_frame, frame_index + 1)
                else:
                    # When animation completes, it should be ready for the next run
                    self._is_pinging = False
                    self.status_indicator.config(text="💻 . . . . . 📠")
            except tk.TclError:
                self._is_pinging = False
                self.animation_job = None

        update_frame(0)
