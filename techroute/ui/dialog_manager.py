"""
Dialog manager for the TechRoute UI.
"""
from __future__ import annotations
import os
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, Callable, Dict

from .. import configuration

if TYPE_CHECKING:
    from ..controller import TechRouteController
    from .app_ui import AppUI

class DialogManager:
    """Handles the creation and management of UI dialogs."""

    def __init__(self, root: tk.Tk, controller: "TechRouteController", ui: "AppUI"):
        self.root = root
        self.controller = controller
        self.ui = ui

    def _set_dialog_icon(self, dialog: tk.Toplevel):
        """Sets the icon for a dialog window."""
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            icon_path_ico = os.path.join(base_dir, "icon.ico")
            icon_path_png = os.path.join(base_dir, "icon.png")

            if platform.system() == "Windows":
                if os.path.exists(icon_path_ico):
                    dialog.iconbitmap(icon_path_ico)
            elif os.path.exists(icon_path_png):
                photo = tk.PhotoImage(file=icon_path_png)
                dialog.iconphoto(False, photo)
        except (tk.TclError, FileNotFoundError):
            pass

    def show_about_dialog(self):
        """Shows the About dialog."""
        messagebox.showinfo(
            "About TechRoute",
            "TechRoute - Machine Service Checker\n\n"
            "Version: 1.0.0\n"
            "A simple tool to check machine statuses and services.",
            parent=self.root
        )

    def show_unsecure_browser_warning(self) -> bool:
        """
        Shows a warning about opening an unsecure browser instance.
        Returns True if the user proceeds, False otherwise.
        """
        title = "Unsecure Browser Warning"
        message = (
            "You are about to open a web browser instance directly from this application. "
            "This browser instance is intended for accessing device configuration pages and "
            "is NOT a secure, fully-featured browser.\n\n"
            "Please DO NOT use it for general web browsing, logging into accounts, "
            "or handling sensitive data.\n\n"
            "Do you want to continue?"
        )
        return messagebox.askokcancel(title, message, parent=self.root, icon='warning')

    def _center_dialog(self, dialog: tk.Toplevel, width: int, height: int):
        """Centers the dialog on the main window."""
        dialog.withdraw()
        self.root.update_idletasks()
        
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()

        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)
        
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.deiconify()

    def open_ports_dialog(self):
        """Opens a dialog to edit the default ports."""
        dialog = tk.Toplevel(self.root)
        self._set_dialog_icon(dialog)
        dialog.title("Default Ports")
        width, height = 300, 250
        if platform.system() == "Linux":
            width = int(width * 1.25)
            height = int(height * 1.15)
        self._center_dialog(dialog, width, height)
        dialog.transient(self.root)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        dialog.rowconfigure(0, weight=1)
        dialog.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)
        content.columnconfigure(0, weight=1)

        ttk.Label(content, text="Default ports to check (one per line):").grid(row=0, column=0, sticky='w')

        quick_add_frame = ttk.Frame(content)
        quick_add_frame.grid(row=1, column=0, sticky='w', pady=(2, 5))

        def add_port_if_missing(port: int):
            content = port_text.get("1.0", tk.END).strip()
            ports = {line.strip() for line in content.splitlines() if line.strip()}
            if str(port) not in ports:
                if content:
                    port_text.insert(tk.END, f"\n{port}")
                else:
                    port_text.insert(tk.END, str(port))
                port_text.see(tk.END)

        ttk.Button(quick_add_frame, text="Add LPD (515)", command=lambda: add_port_if_missing(515)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_add_frame, text="Add RAW (9100)", command=lambda: add_port_if_missing(9100)).pack(side=tk.LEFT)

        text_frame = ttk.Frame(content)
        text_frame.grid(row=2, column=0, sticky='nsew')
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        port_text = tk.Text(text_frame, width=20, height=8)
        port_text.grid(row=0, column=0, sticky='nsew')

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=port_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        port_text.config(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(content)
        button_frame.grid(row=3, column=0, pady=(10, 0))

        current_ports = self.controller.config.get('default_ports_to_check', [])
        port_text.insert(tk.END, "\n".join(map(str, current_ports)))

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
            
            new_config = self.controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(new_ports)))
            self.controller.update_config(new_config)
            dialog.destroy()

        def reset_to_default():
            default_ports = configuration.DEFAULT_CONFIG.get('default_ports_to_check', [])
            new_config = self.controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(default_ports)))
            self.controller.update_config(new_config)
            
            current_ports = self.controller.config.get('default_ports_to_check', [])
            port_text.delete("1.0", tk.END)
            port_text.insert(tk.END, "\n".join(map(str, current_ports)))

        ttk.Button(button_frame, text="Save", command=save_ports).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Default", command=reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

    def open_settings_dialog(self, on_save: Callable[[Dict, Dict], None]):
        """Opens the Settings dialog."""
        dialog = tk.Toplevel(self.root)
        self._set_dialog_icon(dialog)
        dialog.title("Settings")
        
        width, height = 380, 240
        if platform.system() == "Linux":
            width = int(width * 1.25)
            height = int(height * 1.25)
        self._center_dialog(dialog, width, height)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.rowconfigure(0, weight=1)
        dialog.columnconfigure(0, weight=1)

        content = ttk.Frame(dialog, padding=10)
        content.grid(row=0, column=0, sticky='nsew')

        ttk.Label(content, text="Theme:").grid(row=0, column=0, sticky='w', pady=(0, 8))
        theme_values = ["System", "Light", "Dark"]
        theme_var = tk.StringVar(value=self.controller.config.get('ui_theme', 'System'))
        theme_combo = ttk.Combobox(content, textvariable=theme_var, values=theme_values, state='readonly', width=20)
        theme_combo.grid(row=0, column=1, sticky='w', pady=(0, 8), padx=(8, 0))

        view_frame = ttk.LabelFrame(content, text="View", padding=5)
        view_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))

        ttk.Label(view_frame, text="Language:").grid(row=0, column=0, sticky='w', pady=(0, 8))
        
        available_languages = ['System', 'en', 'zh_CN']
        
        language_var = tk.StringVar(value=self.controller.config.get('language', 'System'))
        language_combo = ttk.Combobox(view_frame, textvariable=language_var, values=available_languages, state='readonly', width=20)
        language_combo.grid(row=0, column=1, sticky='w', pady=(0, 8), padx=(8, 0))

        ttk.Label(view_frame, text="TCP Port Readability:").grid(row=1, column=0, sticky='w', pady=(0, 8))
        port_readability_var = tk.StringVar(value=self.controller.config.get('tcp_port_readability', 'Numbers'))
        
        readability_radios = ttk.Frame(view_frame)
        readability_radios.grid(row=1, column=1, sticky='w', pady=(0, 8), padx=(8, 0))
        simple_radio = ttk.Radiobutton(readability_radios, text="Simple (e.g., HTTP, FTP)", variable=port_readability_var, value="Simple")
        simple_radio.pack(anchor='w')
        numbers_radio = ttk.Radiobutton(readability_radios, text="Numbers (e.g., 80, 21)", variable=port_readability_var, value="Numbers")
        numbers_radio.pack(anchor='w')

        btns = ttk.Frame(content)
        btns.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        def save_settings():
            old_config = self.controller.config.copy()
            new_config = old_config.copy()
            new_config['ui_theme'] = theme_var.get()
            new_config['tcp_port_readability'] = port_readability_var.get()
            new_config['language'] = language_var.get()
            
            self.controller.update_config(new_config)

            language_changed = new_config.get('language') != old_config.get('language')
            if on_save:
                on_save(old_config, new_config)

            if not language_changed:
                self.ui.refresh_ui()
            
            dialog.destroy()

        ttk.Button(btns, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        content.columnconfigure(1, weight=1)
        self.root.wait_window(dialog)

    def open_udp_services_dialog(self):
        """Opens a dialog to select UDP services to check."""
        import webbrowser
        dialog = tk.Toplevel(self.root)
        self._set_dialog_icon(dialog)
        dialog.title("UDP Services")
        width, height = 360, 300
        if platform.system() == "Linux":
            width = int(width * 1.25)
            height = int(height * 1.25)
            
        self._center_dialog(dialog, width, height)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.rowconfigure(0, weight=1)
        dialog.columnconfigure(0, weight=1)

        content = ttk.Frame(dialog, padding=10)
        content.grid(row=0, column=0, sticky='nsew')
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        group = ttk.LabelFrame(content, text="UDP Services", padding=10)
        group.grid(row=0, column=0, sticky='nsew')

        services = [
            (427, "SLP"),
            (5353, "mDNS"),
            (3702, "WS-Discovery"),
            (161, "SNMP"),
        ]

        vars_map: dict[int, tk.BooleanVar] = {}
        selected_existing = set(self.controller.config.get('udp_services_to_check', []))
        for idx, (port, name) in enumerate(services):
            var = tk.BooleanVar(value=(int(port) in selected_existing))
            vars_map[port] = var
            cb = ttk.Checkbutton(group, text=f"{name} ({port})", variable=var)
            cb.grid(row=idx, column=0, sticky="w", pady=(0, 2))

        select_all_var = tk.BooleanVar(value=False)
        def toggle_all():
            val = select_all_var.get()
            for v in vars_map.values():
                v.set(val)
        ttk.Checkbutton(group, text="Select All", variable=select_all_var, command=toggle_all).grid(row=len(services), column=0, sticky="w", pady=(6, 0))

        accreditation_frame = ttk.Frame(content)
        accreditation_frame.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        
        desc = ttk.Label(accreditation_frame, text="UDP detection powered by nmap (planned).")
        desc.pack(anchor="w")

        link_frame = ttk.Frame(accreditation_frame)
        link_frame.pack(anchor="w")

        def open_link(event=None):
            try:
                webbrowser.open_new_tab("https://nmap.org")
            except Exception:
                pass
        
        learn_more_label = ttk.Label(link_frame, text="Learn more: ")
        learn_more_label.pack(side=tk.LEFT)
        
        link = ttk.Label(link_frame, text="nmap.org", foreground="blue", cursor="hand2")
        link.pack(side=tk.LEFT)
        link.bind("<Button-1>", open_link)

        btns = ttk.Frame(content)
        btns.grid(row=2, column=0, pady=(10, 0))

        def save_services():
            selected_ports = sorted(int(p) for p, v in vars_map.items() if v.get())
            new_config = self.controller.config.copy()
            new_config['udp_services_to_check'] = selected_ports
            self.controller.update_config(new_config)
            dialog.destroy()
            
        def reset_to_default():
            default_services = configuration.DEFAULT_CONFIG.get('udp_services_to_check', [])
            new_config = self.controller.config.copy()
            new_config['udp_services_to_check'] = sorted(list(set(default_services)))
            self.controller.update_config(new_config)
            
            selected_existing = set(new_config.get('udp_services_to_check', []))
            for port, var in vars_map.items():
                var.set(int(port) in selected_existing)

        ttk.Button(btns, text="Save", command=save_services).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Reset to Default", command=reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)
