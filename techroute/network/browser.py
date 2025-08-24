"""
Handles finding and launching web browsers.
"""
import os
import platform
import shutil
import subprocess
import tempfile
import webbrowser
import logging
from tkinter import messagebox
from typing import Dict, Any, List, Optional

def find_browser_command(browser_preferences: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Finds the first available Chrome/Chromium browser from the preference list.

    On Windows, it specifically searches for Chrome/Chromium in common installation directories
    to avoid accidentally picking up Chrome-based browsers like Edge.
    
    Returns:
        A dictionary with browser details if found, otherwise None.
    """
    system = platform.system()
    for browser in browser_preferences:
        if 'chrome' not in browser['name'].lower() and 'chromium' not in browser['name'].lower():
            continue

        exec_names = browser['exec'].get(system)
        if not exec_names:
            continue

        if isinstance(exec_names, str):
            exec_names = [exec_names]

        path: Optional[str] = None
        is_mac_app = False

        if system == 'Windows':
            possible_paths = [
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(os.environ.get("LocalAppData", ""), "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(os.environ.get("LocalAppData", ""), "Chromium\\Application\\chrome.exe")
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    path = p
                    break
            
            if not path:
                for name in exec_names:
                    found_path = shutil.which(name)
                    if found_path: 
                        path = found_path
                        break
        elif system == 'Darwin':
            for app_name in ['Google Chrome', 'Chromium']:
                mac_path = f"/Applications/{app_name}.app"
                if os.path.isdir(mac_path):
                    path = mac_path
                    is_mac_app = True
                    browser['name'] = app_name
                    break
        elif system == 'Linux':
            # First try shutil.which for the configured executable names
            for name in exec_names:
                found_path = shutil.which(name)
                if found_path:
                    path = found_path
                    break
            
            # If not found, check common installation paths
            if not path:
                possible_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable',
                    '/usr/bin/chromium-browser',
                    '/usr/bin/chromium',
                    '/usr/bin/chromium-browser-stable',
                    '/snap/bin/chromium',
                    '/snap/bin/google-chrome',
                    '/var/lib/flatpak/exports/bin/com.google.Chrome',
                    '/var/lib/flatpak/exports/bin/org.chromium.Chromium',
                    '/opt/google/chrome/google-chrome',
                    '/usr/lib/chromium-browser/chromium-browser',
                    '/usr/lib/chromium/chromium'
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        path = p
                        break
            
            # If still not found, try to find any chromium or chrome executable
            if not path:
                for name in ['chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable', 'chrome']:
                    found_path = shutil.which(name)
                    if found_path:
                        path = found_path
                        break

        if path:
            return {'name': browser['name'], 'path': path, 'args': browser['args'], 'is_mac_app': is_mac_app}
    return None

def open_browser_with_url(url: str, browser_command: Optional[Dict[str, Any]]) -> None:
    """
    Opens a URL using the detected browser or falls back to the default.
    
    Returns:
        None if successful, otherwise an error message string.
    """
    if not browser_command:
        logging.info(f"No preferred browser found. Falling back to OS default to open {url}")
        try:
            webbrowser.open(url)
            return
        except Exception as e:
            logging.error(f"Failed to open URL in default browser: {e}")
            raise RuntimeError(f"Failed to open URL in default browser: {e}")

    try:
        command: List[str] = []
        use_shell = False
        system = platform.system()

        if system == 'Darwin' and browser_command.get('is_mac_app'):
            command.extend(['open', '-a', browser_command['path']])
            if browser_command['args']:
                command.extend(['--args'] + browser_command['args'])
            command.append(url)
        else:
            command.append(browser_command['path'])
            command.extend(browser_command['args'])
            command.append(url)
            if system == 'Windows':
                use_shell = True
        
        logging.info(f"Executing browser command: {' '.join(command)}")

        env = os.environ.copy()
        preexec_fn = None
        if system == 'Linux':
            try:
                # This block is Linux-specific because it deals with privilege dropping
                # for running browsers as root, which is a common issue on Linux.
                # These functions (geteuid, setgid, etc.) do not exist on Windows,
                # so we wrap this in a try...except to avoid AttributeError.
                if os.geteuid() == 0: # type: ignore
                    original_user = os.environ.get('SUDO_USER')
                    if original_user:
                        import pwd
                        user_info = pwd.getpwnam(original_user) # type: ignore
                        uid = user_info.pw_uid
                        gid = user_info.pw_gid
                        home = user_info.pw_dir
                        
                        env['HOME'] = home
                        env['LOGNAME'] = original_user
                        env['USER'] = original_user
                        
                        # Attempt to get DISPLAY and XAUTHORITY from the original user's environment
                        try:
                            user_env_cmd = ['sudo', '-u', original_user, 'env']
                            user_env_proc = subprocess.run(user_env_cmd, capture_output=True, text=True, check=True)
                            for line in user_env_proc.stdout.splitlines():
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    if key in ['DISPLAY', 'XAUTHORITY']:
                                        env[key] = value
                        except (subprocess.CalledProcessError, FileNotFoundError) as e:
                            logging.warning(f"Could not get original user's environment: {e}")

                        def demote():
                            os.setgid(gid) # type: ignore
                            os.setuid(uid) # type: ignore
                        preexec_fn = demote
            except AttributeError:
                # This will be raised on non-Linux systems where os.geteuid doesn't exist.
                # We can safely ignore it as this logic is only for Linux.
                pass
        
        log_path = os.path.join(tempfile.gettempdir(), "browser_launch.log")
        with open(log_path, "w") as log_file:
            # On Windows, preexec_fn is not supported
            popen_kwargs = {'stdout': log_file, 'stderr': log_file, 'shell': use_shell, 'env': env}
            if system != 'Windows':
                popen_kwargs['preexec_fn'] = preexec_fn
            
            subprocess.Popen(command, **popen_kwargs)
    except (OSError, FileNotFoundError) as e:
        logging.error(f"Error launching preferred browser: {e}. The browser might not be installed correctly.")
        raise RuntimeError(f"Error launching preferred browser: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while launching the browser: {e}")
        raise RuntimeError(f"An unexpected error occurred: {e}")

def open_browser_with_error_handling(url: str, browser_command: Optional[Dict[str, Any]]):
    """
    Opens a URL and shows a messagebox on failure.
    """
    try:
        open_browser_with_url(url, browser_command)
    except Exception as e:
        messagebox.showerror(
            "Browser Launch Error",
            f"Failed to launch the web browser.\n\nDetails: {e}"
        )
