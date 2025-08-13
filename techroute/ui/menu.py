"""
Main menu construction for the TechRoute application UI.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, Callable
from .types import AppUIProtocol

class MenuMixin(AppUIProtocol):
    def _setup_menu(self, translator: Callable[[str], str]):
        """Creates the main application menu bar."""
        self._ = translator
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # --- File Menu ---
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=self._("File"), menu=file_menu, underline=0)
        file_menu.add_command(label=self._("New"), underline=0)
        file_menu.add_command(label=self._("Open..."), underline=0)
        file_menu.add_command(label=self._("Save List"), underline=0)
        file_menu.add_command(label=self._("Save List As..."), underline=5)

        # --- Edit Menu ---
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=self._("Edit"), menu=edit_menu, underline=0)
        edit_menu.add_command(label=self._("Clear"), underline=0)

        # --- View Menu ---
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=self._("View"), menu=view_menu, underline=0)
        view_menu.add_command(label=self._("Zoom In"), underline=5)
        view_menu.add_command(label=self._("Zoom Out"), underline=5)
        view_menu.add_separator()
        view_menu.add_checkbutton(label=self._("Show Menubar"), underline=5)
        view_menu.add_checkbutton(label=self._("Show Statusbar"), underline=5)

        # --- Settings Menu ---
        settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=self._("Settings"), menu=settings_menu, underline=0)
        settings_menu.add_command(
            label=self._("Preferences"), 
            underline=0, 
            command=lambda: self._open_settings_dialog(on_save=self.main_app.handle_settings_change)
        )

        # --- Help Menu ---
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=self._("Help"), menu=help_menu, underline=0)
        help_menu.add_command(label=self._("Check for Updates"), underline=6)
        help_menu.add_separator()
        help_menu.add_command(label=self._("Github"), underline=0)
        help_menu.add_command(label=self._("About"), underline=0)
