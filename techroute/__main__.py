"""
Main entry point for the TechRoute application.
"""
import sys
from . import privileges
from .app import main

def main_entry():
    """
    Checks for administrator privileges and runs the main application if granted.
    If not, it requests elevation and exits.
    """
    if not privileges.is_admin():
        print("Administrator privileges are required. Attempting to re-launch...")
        privileges.request_elevation()
        sys.exit(0)
    
    # If we have admin rights, proceed to launch the app.
    main()

if __name__ == "__main__":
    main_entry()
