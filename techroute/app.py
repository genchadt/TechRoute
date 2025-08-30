"""
Main application class for the TechRoute GUI.

This module initializes the Tkinter root, the controller, and the UI,
then starts the application's main loop.
"""
import os
import platform
import tkinter as tk
import logging
from . import configuration
from .localization import LocalizationManager
from .controller import TechRouteController
from .ui.app_ui import AppUI
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
        
        localization_manager = LocalizationManager(
            configuration.load_or_create_config().get('language')
        )
        _ = localization_manager.translator
        self.root.title(_("TechRoute - Machine Service Checker"))

        # 1. Create the state, actions, and controller.
        self.state = AppStateModel()
        self.actions = AppActions()
        self.controller = TechRouteController(
            state=self.state,
            actions=self.actions,
            translator=_
        )

        # 2. Create the UI, providing it with actions, state, and the controller.
        self.ui = AppUI(
            root,
            self.actions,
            self.state,
            self.controller,
            _,
            localization_manager
        )

        # 3. Set the UI reference in the controller to complete the loop.
        self.controller.set_ui(self.ui)

        self._set_icon()

        if platform.system() == "Windows":
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)

        # Start the periodic queue processing
        self._process_controller_queue()



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
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Application starting up.")
    if platform.system() == "Windows":
        if ctypes:
            try:
                from ctypes import windll
                app_id = u'genchadt.techroute.1.0'
                windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            except (ImportError, AttributeError, OSError):
                print("Warning: Could not set AppUserModelID. Taskbar icon may not appear correctly.")

    root = tk.Tk()
    logging.info("Tk root created.")
    app = MainApp(root)
    logging.info("MainApp initialized.")
    root.mainloop()
