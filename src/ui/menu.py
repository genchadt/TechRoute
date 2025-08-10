"""
Main menu construction for the TechRoute application UI.
"""
from __future__ import annotations
import tkinter as tk
from .types import UIContext


class MenuMixin:
    root: tk.Tk

    def _setup_menu(self: UIContext):
        """Creates the main application menu bar."""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # --- File Menu ---
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu, underline=0)
        file_menu.add_command(label="New", underline=0)
        file_menu.add_command(label="Open...", underline=0)
        file_menu.add_command(label="Save List", underline=0)
        file_menu.add_command(label="Save List As...", underline=5)

        # --- Edit Menu ---
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Edit", menu=edit_menu, underline=0)
        edit_menu.add_command(label="Clear", underline=0)

        # --- View Menu ---
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="View", menu=view_menu, underline=0)
        view_menu.add_command(label="Zoom In", underline=5)
        view_menu.add_command(label="Zoom Out", underline=5)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show Menubar", underline=5)
        view_menu.add_checkbutton(label="Show Statusbar", underline=5)

        # --- Settings Menu ---
        settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Settings", menu=settings_menu, underline=0)
        settings_menu.add_command(label="Preferences", underline=0, command=self._open_settings_dialog)

        # --- Help Menu ---
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=help_menu, underline=0)
        help_menu.add_command(label="Check for Updates", underline=6)
        help_menu.add_separator()
        help_menu.add_command(label="Github", underline=0)
        help_menu.add_command(label="About", underline=0)
