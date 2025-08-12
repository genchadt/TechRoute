import os
import platform
import tkinter as tk
from tkinter import messagebox
import logging

from .app import TechRouteApp

# --- Configuration Constants ---
APP_USER_MODEL_ID = "TechRoute.App"
ICON_PNG_NAME = "icon.png"
ICON_ICO_NAME = "icon.ico"

# --- Logging Setup ---
# Configure logging to show WARNINGs and above by default.
# This helps in debugging non-critical issues without being too verbose.
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

# --- Helper Functions ---
def _set_windows_appusermdelid() -> None:
    """
    Sets the Windows AppUserModelID for proper taskbar icon and grouping.
    This must be called before any Tkinter windows are created on Windows.
    Errors are logged but do not prevent application startup.
    """
    if platform.system() != "Windows":
        return

    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception as e:
        # This is a best-effort feature. Log the error but don't crash.
        logging.warning("Failed to set AppUserModelID '%s': %s", APP_USER_MODEL_ID, e)


def _apply_default_icons(root: tk.Tk) -> None:
    """
    Applies default icons for the application across all toplevels.
    Prefers .ico on Windows for better taskbar integration.
    Errors are logged but do not prevent application startup.
    """
    try:
        # Calculate the base directory relative to this script
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        icon_png_path = os.path.join(base_dir, ICON_PNG_NAME)
        icon_ico_path = os.path.join(base_dir, ICON_ICO_NAME)

        # Prefer .ico on Windows for correct taskbar behavior and multi-resolution support
        if platform.system() == "Windows" and os.path.exists(icon_ico_path):
            try:
                root.iconbitmap(default=icon_ico_path)
            except tk.TclError as e:
                logging.warning("Failed to set .ico icon '%s' (Tkinter error): %s", icon_ico_path, e)
            except Exception as e:
                logging.warning("An unexpected error occurred while setting .ico icon '%s': %s", icon_ico_path, e)

        # Set a default iconphoto (propagates to dialogs/new toplevels when default=True)
        # This is generally more cross-platform for title bar icons.
        if os.path.exists(icon_png_path):
            try:
                photo = tk.PhotoImage(file=icon_png_path)
                root.iconphoto(True, photo) # 'True' makes it apply to all future toplevels
            except tk.TclError as e:
                logging.warning("Failed to set .png iconphoto '%s' (Tkinter error): %s", icon_png_path, e)
            except Exception as e:
                logging.warning("An unexpected error occurred while setting .png iconphoto '%s': %s", icon_png_path, e)
    except Exception as e:
        logging.warning("An general error occurred during default icon application: %s", e)


def _apply_platform_window_constraints(root: tk.Tk) -> None:
    """
    Applies platform-specific window sizing/resizing constraints.
    Ensures the window can be maximized to full screen dimensions and is resizable
    on all platforms. Errors are logged but do not prevent application startup.
    """
    try:
        screen_w = max(1, root.winfo_screenwidth())
        screen_h = max(1, root.winfo_screenheight())

        # By default, allow the window to be maximized to full screen dimensions
        # and be user-resizable on all platforms.
        root.maxsize(screen_w, screen_h)
        root.resizable(True, True)

        # Specific platform logic can be added here if behaviors needed to diverge,
        # e.g., if Linux or Windows required different default resizable states.
        # Currently, the desired behavior is consistent across platforms.

    except Exception as e:
        logging.warning("Failed to apply platform window constraints: %s", e)


# --- Main Application Entry Point ---
def main() -> None:
    """
    Main function to start the TechRoute application.
    Handles initial setup, security warning, and main loop execution.
    """
    # 1. Ensure proper Windows taskbar icon/grouping before any windows are created
    _set_windows_appusermodelid()

    # 2. Create the root Tkinter window (hidden initially)
    root = tk.Tk()
    root.withdraw() # Hide the main window immediately

    # 3. Apply default icons and window constraints to the hidden root window
    _apply_default_icons(root)
    _apply_platform_window_constraints(root)

    # 4. Show a critical security warning before proceeding
    proceed = messagebox.askyesno(
        "Security Warning",
        "This application will open a web browser with DISABLED security features.\n\n"
        "Do NOT use this browser for normal web browsing!\n\n"
        "Do you want to continue?",
        icon="warning",
        parent=root,  # Associate dialog with the root window
    )

    if not proceed:
        logging.info("User declined security warning. Exiting application.")
        root.destroy() # Destroy the hidden root window
        return

    # 5. If the user proceeds, show the main window and start the application
    try:
        root.deiconify() # Make the main window visible
        app = TechRouteApp(root) # Initialize the main application logic
        root.mainloop() # Start the Tkinter event loop
    except Exception as e:
        # Log the full traceback for critical errors during runtime
        logging.exception("A critical error occurred during application runtime.")
        try:
            # Attempt to show a user-friendly error message
            messagebox.showerror("Critical Error", f"A critical error occurred:\n{e}", parent=root)
        except Exception:
            # If even the error messagebox fails (e.g., Tkinter context completely broken),
            # re-raise the original exception to allow standard crash reporting/debugging.
            logging.critical("Failed to display critical error messagebox. Re-raising original exception.")
            raise # Re-raise the original exception


if __name__ == "__main__":
    main()
