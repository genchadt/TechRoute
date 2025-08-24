"""
Main application class for the TechRoute GUI.

This module initializes the Tkinter root, the controller, and the UI,
then starts the application's main loop.
"""
import os
import platform
import tkinter as tk
from . import configuration
from .localization import LocalizationManager
from .controller import TechRouteController
from .ui.app_ui import AppUI
from .ui.types import ControllerCallbacks
from .events import AppActions, AppStateModel

try:
    import ctypes
except ImportError:
    ctypes = None

class MainApp:
    """The main application runner."""

    def __init__(self, root: tk.Tk):
        """Initializes the application components."""
        self.root = root
        
        self.localization_manager = LocalizationManager(
            configuration.load_or_create_config().get('language')
        )
        _ = self.localization_manager.translator
        self.root.title(_("TechRoute - Machine Service Checker"))

        # 1. Create the state, actions, and controller.
        self.state = AppStateModel()
        self.actions = AppActions()
        self.controller = TechRouteController(
            main_app=self,
            state=self.state,
            actions=self.actions,
            translator=_
        )

        # 2. Create the UI, providing it with actions and the initial state.
        self.ui = AppUI(
            root,
            self.actions,
            self.state,
            self.controller,
            _,
            on_ui_ready=self._initial_ui_load
        )

        # 3. Set up callbacks for the controller to update the UI.
        callbacks = ControllerCallbacks(
            on_state_change=self.ui.on_state_change,
            on_status_update=self.ui.on_status_update,
            on_initial_statuses_loaded=self.ui.on_initial_statuses_loaded,
            on_network_info_update=self.ui.on_network_info_update,
        )
        self.controller.register_callbacks(callbacks)
        
        self._set_icon()

        if platform.system() == "Windows":
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)

        # Start the periodic queue processing
        self._process_controller_queue()

    def _initial_ui_load(self):
        """Performs the initial loading of data into the UI."""
        # This is where you can now safely interact with both the controller
        # and the UI, knowing they are both fully initialized.
        pass

    def handle_settings_change(self, old_config, new_config):
        """Handles logic for applying settings changes."""
        should_retranslate = new_config.get('language') != old_config.get('language')
        if should_retranslate:
            self.localization_manager.set_language(new_config.get('language'))
            self.retranslate_ui()

    def retranslate_ui(self):
        """Retranslates the entire UI."""
        _ = self.localization_manager.translator
        self.root.title(_("TechRoute - Machine Service Checker"))
        # self.ui.retranslate_ui(_) 
        if self.actions:
            self.actions.update_config(self.actions.get_config())

    def _set_icon(self):
        """Sets the application icon based on the OS."""
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            icon_path_ico = os.path.join(base_dir, "icon.ico")
            icon_path_png = os.path.join(base_dir, "icon.png")

            if platform.system() == "Windows":
                if os.path.exists(icon_path_ico):
                    self.root.iconbitmap(icon_path_ico)
            elif os.path.exists(icon_path_png):
                photo = tk.PhotoImage(file=icon_path_png)
                self.root.iconphoto(False, photo)
        except (tk.TclError, FileNotFoundError) as e:
            print(f"Warning: Could not load application icon. {e}")

    def _process_controller_queue(self):
        """Periodically tells the controller to process its event queue."""
        if self.actions:
            self.actions.process_queue()
        self.root.after(100, self._process_controller_queue)

def main():
    """The main entry point for the application."""
    if platform.system() == "Windows":
        if ctypes:
            try:
                from ctypes import windll
                app_id = u'genchadt.techroute.1.0'
                windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            except (ImportError, AttributeError, OSError):
                print("Warning: Could not set AppUserModelID. Taskbar icon may not appear correctly.")

    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
