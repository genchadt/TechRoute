"""
Dialogs for the TechRoute UI.
"""
from __future__ import annotations
import os
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, Callable, Dict

from .. import configuration
from .types import AppUIProtocol

class DialogsMixin(AppUIProtocol):
    def _set_dialog_icon(self, dialog: tk.Toplevel):
        """Sets the icon for a dialog window."""
        try:
            # Correctly determine the base directory relative to this file
            # The script is in techroute/ui/, so we need to go up two levels
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
            # If the icon fails to load, we don't want to crash the dialog.
            # The main app will have already printed a warning.
            pass
    def _show_unsecure_browser_warning(self) -> bool:
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
        return messagebox.askokcancel(title, message, parent=self.root)

    def _center_dialog(self, dialog: tk.Toplevel, width: int, height: int):
        """Centers the dialog on the main window."""
        dialog.withdraw() # Hide the window until it's ready
        self.root.update_idletasks()
        
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()

        # Calculate the position for the dialog to be centered
        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)
        
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.deiconify() # Show the window now that it's centered

    def _open_ports_dialog(self):
        """Opens a dialog to edit the default ports."""
        if not self.controller:
            return
        dialog = tk.Toplevel(self.root)
        self._set_dialog_icon(dialog)
        dialog.title("Default Ports")
        # Default size
        width, height = 300, 250
        if platform.system() == "Linux":
            width = int(width * 1.25)
            height = int(height * 1.15)
        self._center_dialog(dialog, width, height)
        dialog.transient(self.root)
        dialog.grab_set()


        ttk.Label(dialog, text="Default ports to check (one per line):").pack(pady=5, padx=10, anchor='w')

        # --- Quick-add row for LPD and RAW ---
        quick_add_frame = ttk.Frame(dialog)
        quick_add_frame.pack(pady=(0, 2), padx=10, anchor='w')

        def add_port_if_missing(port: int):
            # Get all lines, but do not strip trailing whitespace from the text area
            content = port_text.get("1.0", tk.END)
            lines = [l.rstrip() for l in content.splitlines()]
            ports = set(l for l in lines if l)
            if str(port) not in ports:
                # Remove any trailing empty lines
                while lines and not lines[-1]:
                    lines.pop()
                # Rebuild the text area with no trailing blanks
                port_text.delete("1.0", tk.END)
                port_text.insert("1.0", "\n".join(lines) + ("\n" if lines else ""))
                # Now add the new port
                if lines:
                    port_text.insert(tk.END, str(port) + "\n")
                else:
                    port_text.insert("1.0", str(port) + "\n")
                port_text.see(tk.END)

        ttk.Button(quick_add_frame, text="Add LPD (515)", command=lambda: add_port_if_missing(515)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_add_frame, text="Add RAW (9100)", command=lambda: add_port_if_missing(9100)).pack(side=tk.LEFT)

        text_frame = ttk.Frame(dialog)
        text_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)

        port_text = tk.Text(text_frame, width=20, height=8)
        port_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=port_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        port_text.config(yscrollcommand=scrollbar.set)

        if self.controller:
            current_ports = self.controller.config.get('default_ports_to_check', [])
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
            
            if self.controller:
                new_config = self.controller.config.copy()
                new_config['default_ports_to_check'] = sorted(list(set(new_ports)))
                self.controller.update_config(new_config)
            dialog.destroy()

        def reset_to_default():
            if not self.controller:
                return
            default_ports = configuration.DEFAULT_CONFIG.get('default_ports_to_check', [])
            new_config = self.controller.config.copy()
            new_config['default_ports_to_check'] = sorted(list(set(default_ports)))
            self.controller.update_config(new_config)
            dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_ports).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Default", command=reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

    def _open_settings_dialog(self, on_save: Callable[[Dict, Dict], None]):
        """Opens the Settings dialog (form only)."""
        if not self.controller:
            return
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

        content = ttk.Frame(dialog, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Theme
        ttk.Label(content, text="Theme:").grid(row=0, column=0, sticky='w', pady=(0, 8))
        theme_values = ["System", "Light", "Dark"]
        theme_var = tk.StringVar(value=self.controller.config.get('ui_theme', 'System') if self.controller else 'System')
        theme_combo = ttk.Combobox(content, textvariable=theme_var, values=theme_values, state='readonly', width=20)
        theme_combo.grid(row=0, column=1, sticky='w', pady=(0, 8), padx=(8, 0))

        # --- View Group ---
        view_frame = ttk.LabelFrame(content, text="View", padding=5)
        view_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))

        # Language
        ttk.Label(view_frame, text="Language:").grid(row=0, column=0, sticky='w', pady=(0, 8))
        
        # Get available languages, ensuring zh_CN is present for the demo
        available_languages = ['System']
        if self.main_app and self.main_app.localization_manager:
            available_languages.extend(self.main_app.localization_manager.available_languages)
        if 'zh_CN' not in available_languages:
            available_languages.append('zh_CN')
        
        language_var = tk.StringVar(value=self.controller.config.get('language', 'System') if self.controller else 'System')
        language_combo = ttk.Combobox(view_frame, textvariable=language_var, values=available_languages, state='readonly', width=20)
        language_combo.grid(row=0, column=1, sticky='w', pady=(0, 8), padx=(8, 0))

        # Port Readability
        ttk.Label(view_frame, text="TCP Port Readability:").grid(row=1, column=0, sticky='w', pady=(0, 8))
        port_readability_var = tk.StringVar(value=self.controller.config.get('tcp_port_readability', 'Numbers') if self.controller else 'Numbers')
        
        readability_radios = ttk.Frame(view_frame)
        readability_radios.grid(row=1, column=1, sticky='w', pady=(0, 8), padx=(8, 0))
        simple_radio = ttk.Radiobutton(readability_radios, text="Simple (e.g., HTTP, FTP)", variable=port_readability_var, value="Simple")
        simple_radio.pack(anchor='w')
        numbers_radio = ttk.Radiobutton(readability_radios, text="Numbers (e.g., 80, 21)", variable=port_readability_var, value="Numbers")
        numbers_radio.pack(anchor='w')

        # Buttons
        btns = ttk.Frame(content)
        btns.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        def save_settings():
            if not self.controller:
                return

            old_config = self.controller.config.copy()
            new_config = old_config.copy()
            new_config['ui_theme'] = theme_var.get()
            new_config['tcp_port_readability'] = port_readability_var.get()
            new_config['language'] = language_var.get()
            
            self.controller.update_config(new_config)
            
            if on_save:
                on_save(old_config, new_config)

            # Trigger a UI refresh to apply other settings live
            self.refresh_ui_for_settings_change()
            
            dialog.destroy()

        ttk.Button(btns, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Make layout a bit nicer
        content.columnconfigure(1, weight=1)
        self.root.wait_window(dialog)

    def _open_udp_services_dialog(self):
        """Opens a dialog to select UDP services to check (future feature)."""
        if not self.controller:
            return
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

        content = ttk.Frame(dialog, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Groupbox for UDP Services
        group = ttk.LabelFrame(content, text="UDP Services", padding=10)
        group.pack(fill=tk.BOTH, expand=True)

        # Service list with ports and names
        services = [
            (427, "SLP"),
            (5353, "mDNS"),
            (3702, "WS-Discovery"),
            (161, "SNMP"),
        ]

        # Build checkboxes
        vars_map: dict[int, tk.BooleanVar] = {}
        selected_existing = set(self.controller.config.get('udp_services_to_check', []) or []) if self.controller else set()
        for idx, (port, name) in enumerate(services):
            var = tk.BooleanVar(value=(int(port) in selected_existing))
            vars_map[port] = var
            # Example label: "SLP (427)"
            cb = ttk.Checkbutton(group, text=f"{name} ({port})", variable=var)
            cb.grid(row=idx, column=0, sticky="w", pady=(0, 2))

        # Select All
        select_all_var = tk.BooleanVar(value=False)
        def toggle_all():
            val = select_all_var.get()
            for v in vars_map.values():
                v.set(val)
        ttk.Checkbutton(group, text="Select All", variable=select_all_var, command=toggle_all).grid(row=len(services), column=0, sticky="w", pady=(6, 0))

        # Accreditation / link area
        accreditation_frame = ttk.Frame(content)
        accreditation_frame.pack(fill=tk.X, pady=(8, 0))
        
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

        # Buttons
        btns = ttk.Frame(content)
        btns.pack(pady=(10, 0))

        def save_services():
            if not self.controller:
                return
            # Persist chosen UDP service ports into config under 'udp_services_to_check'
            selected_ports = sorted(int(p) for p, v in vars_map.items() if v.get())
            new_config = self.controller.config.copy()
            new_config['udp_services_to_check'] = selected_ports
            self.controller.update_config(new_config)
            dialog.destroy()

        ttk.Button(btns, text="Save", command=save_services).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)
