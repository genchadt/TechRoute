"""
A widget for the application's status bar.
"""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from typing import Callable

class StatusBar(ttk.Frame):
    """The application's status bar."""

    def __init__(self, parent: tk.Misc, translator: Callable[[str], str]):
        super().__init__(parent)
        self._ = translator

        self.status_label = ttk.Label(self, text=self._("Ready."), relief=tk.SUNKEN, anchor=tk.W, padding=(2, 5))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        mono_font = tkfont.Font(family="Courier", size=10)
        self.status_indicator = ttk.Label(self, text="💻 ? ? ? ? ? 📠", relief=tk.SUNKEN, width=15, anchor=tk.CENTER, padding=(5, 5), font=mono_font)
        self.status_indicator.pack(side=tk.RIGHT)

    def update_status(self, text: str):
        """Updates the main status label."""
        self.status_label.config(text=text)

    def set_indicator_text(self, text: str):
        """Sets the text of the status indicator."""
        self.status_indicator.config(text=text)

    def retranslate_ui(self, translator: Callable[[str], str]):
        """Retranslates the UI elements of the widget."""
        self._ = translator
        self.status_label.config(text=self._("Ready."))
