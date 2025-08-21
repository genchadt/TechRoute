"""
Handles finding and launching web browsers.
"""
import os
import platform
import shutil
import subprocess
import webbrowser
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
                    if found_path and ('google' in found_path.lower() or 'chromium' in found_path.lower()): 
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
            for name in exec_names:
                found_path = shutil.which(name)
                if found_path:
                    path = found_path
                    break
            
            if not path:
                possible_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/chromium-browser',
                    '/usr/bin/chromium'
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        path = p
                        break

        if path:
            return {'name': browser['name'], 'path': path, 'args': browser['args'], 'is_mac_app': is_mac_app}
    return None

def open_browser_with_url(url: str, browser_command: Optional[Dict[str, Any]]):
    """Opens a URL using the detected browser or falls back to the default."""
    if not browser_command:
        print(f"No preferred browser found or configured. Falling back to OS default to open {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Failed to open URL in default browser: {e}")
        return

    try:
        command: Any = []
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
            
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=use_shell)
    except (OSError, FileNotFoundError) as e:
        print(f"Error launching preferred browser: {e}. The browser might not be installed correctly.")
