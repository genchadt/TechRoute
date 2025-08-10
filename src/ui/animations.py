"""
UI animations for the TechRoute status indicator.

Provides a mixin with small, self-contained animation methods.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, cast
from .types import UIContext


class AnimationsMixin:
    """Animation helpers for the AppUI status indicator."""

    root: tk.Tk

    # The following attributes are expected on the concrete class:
    # - status_indicator: ttk.Label
    # - blinking_animation_job: str | None
    # - ping_animation_job: str | None

    def start_blinking_animation(self: UIContext):
        """Starts a blinking animation with question marks."""
        self.stop_ping_animation()  # Ensure ping animation is stopped
        if self.blinking_animation_job:
            self.root.after_cancel(self.blinking_animation_job)

        self._blink()

    def _blink(self: UIContext):
        """Helper function for the blinking animation."""
        current_text = self.status_indicator.cget("text")
        if "?" in current_text:
            new_text = "💻           📠"
        else:
            new_text = "💻 ? ? ? ? ? 📠"
        self.status_indicator.config(text=new_text)
        self.blinking_animation_job = self.root.after(500, self._blink)

    def stop_blinking_animation(self: UIContext):
        """Stops the blinking animation."""
        if self.blinking_animation_job:
            self.root.after_cancel(self.blinking_animation_job)
            self.blinking_animation_job = None
        self.status_indicator.config(text="💻 . . . . . 📠")

    def stop_ping_animation(self: UIContext):
        """Stops any in-progress ping animation."""
        # Invalidate any in-flight animation frames by advancing a generation token
        try:
            self._ping_anim_gen = getattr(self, "_ping_anim_gen", 0) + 1
            setattr(self, "_ping_anim_gen", self._ping_anim_gen)
        except Exception:
            pass
        if self.ping_animation_job:
            self.root.after_cancel(self.ping_animation_job)
            self.ping_animation_job = None

    def reset_status_indicator(self: UIContext):
        """Resets the status indicator to its initial state."""
        self.stop_blinking_animation()
        self.stop_ping_animation()
        self.status_indicator.config(text="💻 ? ? ? ? ? 📠")

    def run_ping_animation(self: UIContext, polling_rate_ms: int):
        """Fires a one-shot animation of an arrow, scaled by the polling rate."""
        self.stop_ping_animation()  # Cancel any previous animation
        self.stop_blinking_animation()  # Ensure the '???' animation is stopped

        # Establish a new generation for this animation run
        self._ping_anim_gen = (getattr(self, "_ping_anim_gen", 0) or 0) + 1
        current_gen = self._ping_anim_gen

        frames = [
            "💻 • . . . . 📠",
            "💻 . • . . . 📠",
            "💻 . . • . . 📠",
            "💻 . . . • . 📠",
            "💻 . . . . • 📠",
        ]
        num_frames = len(frames)

        # Animation speed rules:
        # - Normally, run at (poll rate - 200ms).
        # - If poll rate < 1200ms, detach from ping cadence and run at 1200ms.
        if polling_rate_ms < 1200:
            total_duration_ms = 1200
        else:
            total_duration_ms = max(200, polling_rate_ms - 200)

        frame_delay = max(1, int(total_duration_ms / num_frames))

        # Start from the first frame deterministically to avoid mid-sequence starts
        self.status_indicator.config(text=frames[0])

        def update_frame(frame_index: int):
            # If a newer animation started, abandon this sequence
            if getattr(self, "_ping_anim_gen", current_gen) != current_gen:
                return
            if frame_index < num_frames:
                self.status_indicator.config(text=frames[frame_index])
                next_frame_index = frame_index + 1
                self.ping_animation_job = self.root.after(frame_delay, update_frame, next_frame_index)
            else:
                # Animation finished, reset to idle state if still current
                if getattr(self, "_ping_anim_gen", current_gen) == current_gen:
                    self.status_indicator.config(text="💻 . . . . . 📠")
                    self.ping_animation_job = None

        # Schedule from the second frame to maintain total duration alignment
        self.ping_animation_job = self.root.after(frame_delay, update_frame, 1)
