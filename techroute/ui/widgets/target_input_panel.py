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

        def create_button(parent, label, **kwargs):
            translated_label = self._(label)
            underline = translated_label.find('&')
            mnemonic = None
            if underline != -1:
                kwargs['text'] = translated_label.replace('&', '', 1)
                kwargs['underline'] = underline
                mnemonic = translated_label[underline + 1].lower()
            else:
                kwargs['text'] = translated_label
            
            button = ttk.Button(parent, **kwargs)
            return button, mnemonic

        def bind_mnemonic(widget, mnemonic):
            if mnemonic:
                self.winfo_toplevel().bind(f'<Alt-{mnemonic}>', lambda e, w=widget: w.invoke())

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
        self.add_localhost_button, localhost_mnemonic = create_button(left_quick_frame, "Add l&ocalhost")
        self.add_localhost_button.pack(side=tk.LEFT)
        bind_mnemonic(self.add_localhost_button, localhost_mnemonic)
        self.add_gateway_button, gateway_mnemonic = create_button(left_quick_frame, "Add &Gateway")
        self.add_gateway_button.pack(side=tk.LEFT, padx=(5, 0))
        bind_mnemonic(self.add_gateway_button, gateway_mnemonic)

        spacer = ttk.Frame(quick_row)
        spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        right_quick_frame = ttk.Frame(quick_row)
        right_quick_frame.pack(side=tk.RIGHT)
        self.clear_field_button, clear_field_mnemonic = create_button(right_quick_frame, "Clear F&ield")
        self.clear_field_button.pack()
        bind_mnemonic(self.clear_field_button, clear_field_mnemonic)

        button_frame = ttk.Frame(self.input_frame)
        button_frame.pack(pady=10, fill=tk.X)

        left_button_group = ttk.Frame(button_frame)
        left_button_group.pack(side=tk.LEFT)
        self.start_stop_button, start_stop_mnemonic = create_button(left_button_group, "&Start Pinging")
        self.start_stop_button.pack(side=tk.LEFT)
        bind_mnemonic(self.start_stop_button, start_stop_mnemonic)
        self.launch_all_button, launch_all_mnemonic = create_button(left_button_group, "&Launch Web UIs", state=tk.DISABLED)
        self.launch_all_button.pack(side=tk.LEFT, padx=(5, 0))
        bind_mnemonic(self.launch_all_button, launch_all_mnemonic)

        right_button_group = ttk.Frame(button_frame)
        right_button_group.pack(side=tk.RIGHT)
        self.clear_statuses_button, clear_statuses_mnemonic = create_button(right_button_group, "Cl&ear Statuses")
        self.clear_statuses_button.pack()
        bind_mnemonic(self.clear_statuses_button, clear_statuses_mnemonic)

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

    def update_browser_name(self, browser_name: str):
        """Updates the browser name in the frame's title."""
        self.input_frame.config(text=self._(f"Target Browser: {browser_name}"))

    def retranslate_ui(self, translator: Callable[[str], str]):
        """Retranslates the UI elements of the widget."""
        self._ = translator
        # The browser name will be updated by `update_browser_name`
        self.instruction_label.config(text=self._("Enter IPs or Hostnames, one per line"))
        self.add_localhost_button.config(text=self._("Add localhost"))
        self.add_gateway_button.config(text=self._("Add Gateway"))
        self.clear_field_button.config(text=self._("Clear Field"))
        self.start_stop_button.config(text=self._("Start Pinging"))
        self.launch_all_button.config(text=self._("Launch Web UIs"))
        self.clear_statuses_button.config(text=self._("Clear Statuses"))

    # --------------------------- Settings Refresh ---------------------------
    def refresh_for_settings_change(self):
        """Placeholder for future dynamic settings (no-op for now)."""
        pass
