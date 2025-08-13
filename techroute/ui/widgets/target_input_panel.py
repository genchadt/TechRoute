"""
A widget for handling target input.
"""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Literal

class TargetInputPanel(ttk.Frame):
    """A frame that contains the target input field and related buttons."""

    def __init__(self, parent: tk.Widget, translator: Callable[[str], str]):
        super().__init__(parent)
        self._ = translator

        self.input_frame = ttk.LabelFrame(self, text=self._("Target Browser: Unknown"), padding="10")
        self.input_frame.pack(fill=tk.X, expand=True)

        self.instruction_label = ttk.Label(self.input_frame, text=self._("Enter IPs or Hostnames, one per line"))
        self.instruction_label.pack(pady=5)

        text_frame = ttk.Frame(self.input_frame)
        text_frame.pack(pady=5, fill=tk.X, expand=True)
        self.ip_entry = tk.Text(text_frame, width=60, height=6, wrap="word")
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()
        vscrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=vscrollbar.set)

        quick_row = ttk.Frame(self.input_frame)
        quick_row.pack(pady=(0, 5), fill=tk.X)
        
        left_quick_frame = ttk.Frame(quick_row)
        left_quick_frame.pack(side=tk.LEFT)
        self.add_localhost_button = ttk.Button(left_quick_frame, text=self._("Add localhost"), underline=0)
        self.add_localhost_button.pack(side=tk.LEFT)
        self.add_gateway_button = ttk.Button(left_quick_frame, text=self._("Add Gateway"), underline=4)
        self.add_gateway_button.pack(side=tk.LEFT, padx=(5, 0))

        spacer = ttk.Frame(quick_row)
        spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        right_quick_frame = ttk.Frame(quick_row)
        right_quick_frame.pack(side=tk.RIGHT)
        self.clear_field_button = ttk.Button(right_quick_frame, text=self._("Clear Field"), underline=0)
        self.clear_field_button.pack()

        button_frame = ttk.Frame(self.input_frame)
        button_frame.pack(pady=10, fill=tk.X)

        left_button_group = ttk.Frame(button_frame)
        left_button_group.pack(side=tk.LEFT)
        self.start_stop_button = ttk.Button(left_button_group, text=self._("Start Pinging"), underline=0)
        self.start_stop_button.pack(side=tk.LEFT)
        self.launch_all_button = ttk.Button(left_button_group, text=self._("Launch Web UIs"), underline=0, state=tk.DISABLED)
        self.launch_all_button.pack(side=tk.LEFT, padx=(5, 0))

        right_button_group = ttk.Frame(button_frame)
        right_button_group.pack(side=tk.RIGHT)
        self.clear_statuses_button = ttk.Button(right_button_group, text=self._("Clear Statuses"), underline=0)
        self.clear_statuses_button.pack()

    def get_text(self) -> str:
        return self.ip_entry.get("1.0", tk.END).strip()

    def set_state(self, state: Literal['normal', 'disabled']):
        self.ip_entry.config(state=state)

    def clear(self):
        self.ip_entry.delete("1.0", tk.END)

    def append_line(self, text: str):
        content = self.ip_entry.get("1.0", "end-1c")
        prefix = "\n" if content and not content.endswith("\n") else ""
        self.ip_entry.insert("end", prefix + text + "\n")
        self.ip_entry.see("end")

    def retranslate_ui(self, translator: Callable[[str], str]):
        """Retranslates the UI elements of the widget."""
        self._ = translator
        self.input_frame.config(text=self._("Target Browser: Unknown"))
        self.instruction_label.config(text=self._("Enter IPs or Hostnames, one per line"))
        self.add_localhost_button.config(text=self._("Add localhost"))
        self.add_gateway_button.config(text=self._("Add Gateway"))
        self.clear_field_button.config(text=self._("Clear Field"))
        self.start_stop_button.config(text=self._("Start Pinging"))
        self.launch_all_button.config(text=self._("Launch Web UIs"))
        self.clear_statuses_button.config(text=self._("Clear Statuses"))
