"""
Main menu construction for the TechRoute application UI.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from .types import AppUIProtocol
from typing import Callable

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
        settings_menu.add_command(label=self._("Preferences"), underline=0, command=self._open_settings_dialog)

        # --- Language Sub-Menu ---
        self.language_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label=self._("Language"), menu=self.language_menu, underline=0)

        # --- Help Menu ---
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=self._("Help"), menu=help_menu, underline=0)
        help_menu.add_command(label=self._("Check for Updates"), underline=6)
        help_menu.add_separator()
        help_menu.add_command(label=self._("Github"), underline=0)
        help_menu.add_command(label=self._("About"), underline=0)
