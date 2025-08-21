"""
Shared utility functions for UI widgets.
"""
from __future__ import annotations
from typing import Any
import tkinter as tk


def create_indicator_button(parent: Any, text: str) -> Any:
    """Creates a styled tk.Button for use as a status indicator."""
    return tk.Button(
        parent,
        text=text,
        width=len(text) + 1,
        bg="gray",
        fg="white",
        disabledforeground="white",
        relief="raised",
        borderwidth=1,
        state=tk.DISABLED,
        cursor=""
    )
