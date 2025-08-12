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
        self._is_ping_animation_running = False
        self._stop_ping_animation_requested = False

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
        """Requests a graceful stop of any in-progress ping animation."""
        if self._is_ping_animation_running:
            self._stop_ping_animation_requested = True
        if self.ping_animation_job:
            self.root.after_cancel(self.ping_animation_job)
            self.ping_animation_job = None
        # If no animation is running, ensure the indicator is in a neutral state
        if not self._is_ping_animation_running:
            self.status_indicator.config(text="💻 . . . . . 📠")

    def reset_status_indicator(self):
        """Resets the status indicator to its initial state."""
        self.stop_blinking_animation()
        self.stop_ping_animation()
        self.status_indicator.config(text="💻 ? ? ? ? ? 📠")

    def run_ping_animation(self, polling_rate_ms: int):
        """Fires a one-shot animation of a moving dot, scaled by the polling rate."""
        if self._is_ping_animation_running:
            return  # Don't start a new animation if one is already running

        self.stop_blinking_animation()
        self._is_ping_animation_running = True
        self._stop_ping_animation_requested = False

        frames = [
            "💻 • . . . . 📠",
            "💻 . • . . . 📠",
            "💻 . . • . . 📠",
            "💻 . . . • . 📠",
            "💻 . . . . • 📠",
            "💻 . . . • . 📠",
            "💻 . . • . . 📠",
            "💻 . • . . . 📠",
            "💻 • . . . . 📠",
        ]
        num_frames = len(frames)
        
        # Animation should complete slightly before the next ping cycle for smoothness.
        # Total duration is the polling rate minus a 200ms buffer.
        # We ensure a minimum duration to keep the animation visible on very fast polls.
        total_duration_ms = max(50, polling_rate_ms - 200)
        frame_delay = max(1, int(total_duration_ms / num_frames))

        def update_frame(frame_index: int):
            if self._stop_ping_animation_requested:
                self.status_indicator.config(text="💻 . . . . . 📠")
                self._is_ping_animation_running = False
                self._stop_ping_animation_requested = False
                self.ping_animation_job = None
                return

            if frame_index < num_frames:
                self.status_indicator.config(text=frames[frame_index])
                next_frame_index = frame_index + 1
                self.ping_animation_job = self.root.after(frame_delay, update_frame, next_frame_index)
            else:
                # Animation finished, reset state
                self.status_indicator.config(text="💻 . . . . . 📠")
                self._is_ping_animation_running = False
                self.ping_animation_job = None

        # Start the animation
        self.status_indicator.config(text=frames[0])
        self.ping_animation_job = self.root.after(frame_delay, update_frame, 1)
