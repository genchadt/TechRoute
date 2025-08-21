"""
Handles privilege checking and elevation requests for the application.
"""
import os
import sys
import platform
import ctypes

def is_admin() -> bool:
    """
    Checks if the application is running with administrator or root privileges.

    Returns:
        bool: True if running with elevated privileges, False otherwise.
    """
    try:
        if platform.system() == "Windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        elif hasattr(os, 'geteuid'):
            # On POSIX systems, UID 0 is root.
            # Ignore linter/type-checker warnings about os.geteuid on Windows;
            # this attribute only exists on POSIX platforms.
            return os.geteuid() == 0  # type: ignore[attr-defined]  # pylint: disable=no-member
        return False # Default to False if none of the above checks work
    except AttributeError:
        # If ctypes is not available or geteuid doesn't exist, assume not admin.
        return False

def request_elevation():
    """
    Restarts the application with a request for elevated privileges.
    """
    if platform.system() == "Windows":
        try:
            if __package__:
                # Executed as a module, e.g., python -m techroute
                params = f'-m {__package__} {" ".join(sys.argv[1:])}'
            else:
                # Executed as a script
                params = f'"{sys.argv[0]}" {" ".join(sys.argv[1:])}'

            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                params,
                None,
                1
            )
        except Exception as e:
            print(f"Failed to elevate privileges: {e}")
    else:
        # For Linux/macOS, there's no universal way to request elevation.
        # The standard is to instruct the user to use sudo.
        print("This application requires root privileges to function correctly.")
        print("Please run it with 'sudo'.")
