"""
Dialogs for the TechRoute UI.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING
from .types import UIContext

from .. import configuration

if TYPE_CHECKING:
    from ..app import TechRouteApp


class DialogsMixin:
    root: tk.Tk
    app_controller: "TechRouteApp"

    def _open_ports_dialog(self: UIContext):
        """Opens a dialog to edit the default ports."""
        import platform
        dialog = tk.Toplevel(self.root)
        dialog.title("Default Ports")
        # Default size
        width, height = 300, 250
        if platform.system() == "Linux":
            width = int(width * 1.15)
            height = int(height * 1.15)
        dialog.geometry(f"{width}x{height}")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Default ports to check (one per line):").pack(pady=5, padx=10, anchor='w')

        text_frame = ttk.Frame(dialog)
        text_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        port_text = tk.Text(text_frame, width=20, height=8)
        port_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=port_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        port_text.config(yscrollcommand=scrollbar.set)

        current_ports = self.app_controller.config.get('default_ports_to_check', [])
        port_text.insert(tk.END, "\n".join(map(str, current_ports)))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        def save_ports():
            new_ports_str = port_text.get("1.0", tk.END).strip()
            if not new_ports_str:
                new_ports = []
            else:
                try:
                    new_ports = [int(p.strip()) for p in new_ports_str.splitlines() if p.strip()]
                    if not all(0 < port < 65536 for port in new_ports):
                        raise ValueError("Port number out of range.")
                except ValueError:
                    messagebox.showerror("Invalid Ports", "Please enter valid port numbers (1-65535), one per line.", parent=dialog)
                    return
            
            new_config = self.app_controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(new_ports)))
            self.app_controller.update_config(new_config)
            dialog.destroy()

        def reset_to_default():
            default_ports = configuration.DEFAULT_CONFIG.get('default_ports_to_check', [])
            new_config = self.app_controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(default_ports)))
            self.app_controller.update_config(new_config)
            dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_ports).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Default", command=reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

    def _open_settings_dialog(self: UIContext):
        """Opens the Settings dialog (form only)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("380x220")
        dialog.transient(self.root)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Theme
        ttk.Label(content, text="Theme:").grid(row=0, column=0, sticky='w', pady=(0, 8))
        theme_values = ["System", "Light", "Dark"]
        theme_var = tk.StringVar(value=self.app_controller.config.get('ui_theme', 'System'))
        theme_combo = ttk.Combobox(content, textvariable=theme_var, values=theme_values, state='readonly', width=20)
        theme_combo.grid(row=0, column=1, sticky='w', pady=(0, 8), padx=(8, 0))

        # Port readability as a simple switch (Checkbutton): checked = Simple, unchecked = Numbers
        port_simple_default = self.app_controller.config.get('port_readability', 'Numbers') == 'Simple'
        port_simple_var = tk.BooleanVar(value=port_simple_default)
        port_switch = ttk.Checkbutton(content, text="Port readability: Simple", variable=port_simple_var)
        port_switch.grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))

        # Note/explanation
        note = ttk.Label(content, text="Simple shows names (FTP, HTTP, HTTPS), Numbers shows raw port numbers.", foreground='gray')
        note.grid(row=2, column=0, columnspan=2, sticky='w', pady=(0, 8))

        # Buttons
        btns = ttk.Frame(content)
        btns.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        def save_settings():
            new_config = self.app_controller.config.copy()
            new_config['ui_theme'] = theme_var.get()
            new_config['port_readability'] = 'Simple' if port_simple_var.get() else 'Numbers'
            self.app_controller.update_config(new_config)  # save only; applying behavior is future work
            dialog.destroy()

        ttk.Button(btns, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Make layout a bit nicer
        content.columnconfigure(1, weight=1)
        self.root.wait_window(dialog)
