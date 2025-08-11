# src/__main__.py

"""
Entry point for the TechRoute application.

Ensures Windows taskbar icon and grouping by setting AppUserModelID before
creating any windows, applies default window icons, shows a security warning,
and then starts the main loop.
"""

import os
import platform
import tkinter as tk
from tkinter import messagebox

from .app import TechRouteApp


def _set_windows_appusermodelid():
    """Sets the Windows AppUserModelID for proper taskbar icon/grouping."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes  # type: ignore
        app_id = "TechRoute.App"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)  # type: ignore[attr-defined]
    except Exception:
        # Best-effort; ignore if not available
        pass


def _apply_default_icons(root: tk.Tk) -> None:
    """Apply default icons for the application across all toplevels."""
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        icon_png = os.path.join(base_dir, "icon.png")
        icon_ico = os.path.join(base_dir, "icon.ico")

        # Prefer .ico on Windows for correct taskbar behavior
        if platform.system() == "Windows" and os.path.exists(icon_ico):
            try:
                root.iconbitmap(default=icon_ico)
            except tk.TclError:
                pass

        # Set a default iconphoto (propagates to dialogs/new toplevels when default=True)
        if os.path.exists(icon_png):
            try:
                photo = tk.PhotoImage(file=icon_png)
                root.iconphoto(True, photo)
            except tk.TclError:
                pass
    except Exception:
        pass


def main():
    """Main function to start the application."""
    # Ensure proper Windows taskbar icon/grouping before any windows are created
    _set_windows_appusermodelid()
    
    proceed = messagebox.askyesno(
        "Security Warning",
        "This application will open a web browser with DISABLED security features.\n\n"
        "Do NOT use this browser for normal web browsing!\n\n"
        "Do you want to continue?",
        icon="warning",
    )
    if not proceed:
        return
    
    try:
        root = tk.Tk()
        # Hide the main window while showing the initial warning dialog
        root.withdraw()
        _apply_default_icons(root)

        # On Linux, constrain window resizing behavior to meet UX requirements:
        # - Allow manual resizing with a minimum size set later by the app
        # - Cap the maximum size to 35% of screen width and full screen height
        try:
            if platform.system() == "Linux":
                screen_w = max(1, root.winfo_screenwidth())
                screen_h = max(1, root.winfo_screenheight())
                max_w = max(300, int(screen_w * 0.35))
                max_h = screen_h  # Full available height
                root.maxsize(max_w, max_h)
                # Ensure the window is user-resizable
                root.resizable(True, True)
            elif platform.system() == "Windows":
                # Ensure Windows can reach full screen height/width when maximized
                screen_w = max(1, root.winfo_screenwidth())
                screen_h = max(1, root.winfo_screenheight())
                root.maxsize(screen_w, screen_h)
                root.resizable(True, True)
        except Exception:
            # Best-effort: if querying screen size fails, proceed without hard caps
            pass



        # Show the main window and start the app
        root.deiconify()
        app = TechRouteApp(root)
        root.mainloop()
    except Exception as e:
        # If something fails before the root exists, fall back to a plain messagebox
        try:
            messagebox.showerror("Critical Error", f"A critical error occurred:\n{e}")
        except Exception:
            raise


if __name__ == "__main__":
    main()
