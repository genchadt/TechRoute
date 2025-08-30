"""
Main menu construction for the TechRoute application UI.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .dialog_manager import DialogManager
    from ..events import AppActions

class MenuManager:
    """Creates and manages the main application menu bar."""

    def __init__(self, root: tk.Tk, actions: AppActions, dialog_manager: DialogManager, translator: Callable[[str], str]):
        self.root = root
        self.actions = actions
        self.dialog_manager = dialog_manager
        self._ = translator

    def setup(self):
        """Creates the main application menu bar."""
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        def add_menu_item(parent_menu, item_type, label, **kwargs):
            translated_label = self._(label)
            underline = translated_label.find('&')
            if underline != -1:
                kwargs['label'] = translated_label.replace('&', '', 1)
                kwargs['underline'] = underline
            else:
                kwargs['label'] = translated_label

            if item_type == 'cascade':
                parent_menu.add_cascade(**kwargs)
            elif item_type == 'command':
                parent_menu.add_command(**kwargs)
            elif item_type == 'checkbutton':
                parent_menu.add_checkbutton(**kwargs)

        # --- File Menu ---
        file_menu = tk.Menu(menu_bar, tearoff=0)
        add_menu_item(menu_bar, 'cascade', "&File", menu=file_menu)
        add_menu_item(file_menu, 'command', "&New", accelerator="Ctrl+N")
        add_menu_item(file_menu, 'command', "&Open...", accelerator="Ctrl+O")
        add_menu_item(file_menu, 'command', "&Save List", accelerator="Ctrl+S")
        add_menu_item(file_menu, 'command', "Save List &As...", accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        add_menu_item(file_menu, 'command', "E&xit", command=self.root.destroy)

        # --- Edit Menu ---
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        add_menu_item(menu_bar, 'cascade', "&Edit", menu=edit_menu)
        add_menu_item(edit_menu, 'command', "&Clear All Statuses", command=self.actions.clear_statuses)

        # --- View Menu ---
        view_menu = tk.Menu(menu_bar, tearoff=0)
        add_menu_item(menu_bar, 'cascade', "&View", menu=view_menu)
        add_menu_item(view_menu, 'command', "Zoom &In", accelerator="Ctrl++")
        add_menu_item(view_menu, 'command', "Zoom &Out", accelerator="Ctrl+-")
        view_menu.add_separator()
        add_menu_item(view_menu, 'checkbutton', "Show &Menubar")
        add_menu_item(view_menu, 'checkbutton', "Show S&tatusbar")

        # --- Settings Menu ---
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        add_menu_item(menu_bar, 'cascade', "&Settings", menu=settings_menu)
        add_menu_item(settings_menu, 'command', "&Preferences...", command=lambda: self.dialog_manager.open_settings_dialog(on_save=self.actions.settings_changed))

        # --- Help Menu ---
        help_menu = tk.Menu(menu_bar, tearoff=0)
        add_menu_item(menu_bar, 'cascade', "&Help", menu=help_menu)
        add_menu_item(help_menu, 'command', "Check for &Updates...")
        help_menu.add_separator()
        add_menu_item(help_menu, 'command', "&Github", command=self.actions.open_github)
        add_menu_item(help_menu, 'command', "&About", command=self.dialog_manager.show_about_dialog)
