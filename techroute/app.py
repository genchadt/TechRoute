# techroute/app.py

"""
Main application class for the TechRoute GUI.

This module initializes the Tkinter root, the controller, and the UI,
then starts the application's main loop.
"""

import os
import platform
import tkinter as tk
from tkinter import messagebox
from .localization import LocalizationManager
try:
    import ctypes
except ImportError:
    ctypes = None

from .controller import TechRouteController
from .ui.app_ui import AppUI

class MainApp:
    """The main application runner."""

    def __init__(self, root: tk.Tk):
        """Initializes the application components."""
        self.root = root
        
        # The controller must be created before the UI to access config
        self.controller = TechRouteController(
            on_status_update=self._handle_status_update,
            on_network_info_update=self._handle_network_info_update,
        )

        # Setup localization
        self.localization_manager = LocalizationManager(self.controller.config.get('language'))
        _ = self.localization_manager.translator
        self.root.title(_("TechRoute - Machine Service Checker"))

        self._set_icon()

        # Force taskbar icon update on Windows
        if platform.system() == "Windows":
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)

        # The UI must be created with a translator
        self.ui = AppUI(root, self, _)
        
        # Now link the UI and controller
        self.controller.set_ui(self.ui)
        self.ui.set_controller(self.controller)

        # Set controller callbacks that might depend on the UI
        self.controller.on_checking_start = self.ui.start_blinking_animation
        self.controller.on_pinging_start = self.ui.stop_blinking_animation
        self.controller.on_ping_stop = self.ui.reset_status_indicator
        self.controller.on_ping_update = lambda: self.ui.run_ping_animation(self.controller.get_polling_rate_ms())

        # Start the periodic queue processing
        self._process_controller_queue()

    def retranslate_ui(self):
        """Retranslates the entire UI."""
        _ = self.localization_manager.translator
        self.root.title(_("TechRoute - Machine Service Checker"))
        self.ui.retranslate_ui(_)

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
                # For other OSes like Linux
                photo = tk.PhotoImage(file=icon_path_png)
                self.root.iconphoto(False, photo)
        except (tk.TclError, FileNotFoundError) as e:
            print(f"Warning: Could not load application icon. {e}")

    def _handle_status_update(self, message: tuple):
        """Callback for the controller to send status updates to the UI."""
        try:
            self.ui.process_status_update(message)
        except tk.TclError:
            # Window is likely closing
            pass

    def _handle_network_info_update(self, info: dict):
        """Callback for the controller to send network info to the UI."""
        try:
            self.ui.update_network_info(info)
            # Now that network info is loaded, lock the minimum window size
            self.root.update_idletasks()
            req_w = self.root.winfo_reqwidth()
            req_h = self.root.winfo_reqheight()
            self.root.minsize(req_w, req_h)
        except (tk.TclError, AttributeError):
             # Window is likely closing, or UI is not fully initialized
            pass

    def _process_controller_queue(self):
        """Periodically tells the controller to process its event queue."""
        self.controller.process_queue()
        self.root.after(100, self._process_controller_queue)

def main():
    """The main entry point for the application."""
    # Set the AppUserModelID on Windows to ensure the custom icon is used on the taskbar.
    # This must be done BEFORE the main window is created.
    if platform.system() == "Windows":
        if ctypes:
            try:
                from ctypes import windll
                app_id = u'genchadt.techroute.1.0'  # Unique ID for the application
                windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            except (ImportError, AttributeError, OSError):
                # This can fail on some minimal Windows environments.
                print("Warning: Could not set AppUserModelID. Taskbar icon may not appear correctly.")

    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
