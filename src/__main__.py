# src/__main__.py

"""
Entry point for the TechRoute application.

This script initializes and runs the Tkinter main loop.
It also displays the initial security warning.
"""

import tkinter as tk
from tkinter import messagebox
from .app import TechRouteApp

def main():
    """Main function to start the application."""
    if not messagebox.askyesno(
        "Security Warning",
        "This application will open a web browser with DISABLED security features.\n\n"
        "Do NOT use this browser for normal web Browse!\n\n"
        "Do you want to continue?",
        icon='warning'
    ):
        return
    
    try:
        root = tk.Tk()
        app = TechRouteApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Critical Error", f"A critical error occurred:\n{e}")

if __name__ == "__main__":
    main()
