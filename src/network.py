# src/network.py

"""
Network utilities for PrintPing.

This module handles all network operations, including ICMP pings, TCP port checks,
and system-specific browser detection and launching.
"""

import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import threading
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
        # We only care about Chrome/Chromium for this application's purpose
        if 'chrome' not in browser['name'].lower() and 'chromium' not in browser['name'].lower():
            continue

        exec_names = browser['exec'].get(system)
        if not exec_names:
            continue

        # Ensure exec_names is a list for consistent processing
        if isinstance(exec_names, str):
            exec_names = [exec_names]

        path: Optional[str] = None
        is_mac_app = False

        if system == 'Windows':
            # Prioritize explicit paths to avoid finding Edge's chrome.exe stub
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
            
            # If not found in explicit paths, check PATH, but be wary of stubs.
            if not path:
                for name in exec_names:
                    found_path = shutil.which(name)
                    # A simple heuristic to avoid Edge's compatibility stub
                    if found_path and ('google' in found_path.lower() or 'chromium' in found_path.lower()): 
                        path = found_path
                        break
        elif system == 'Darwin':
            # On macOS, check for both standard Chrome and Chromium app names
            for app_name in ['Google Chrome', 'Chromium']:
                mac_path = f"/Applications/{app_name}.app"
                if os.path.isdir(mac_path):
                    path = mac_path
                    is_mac_app = True
                    # Update browser name to what was actually found
                    browser['name'] = app_name
                    break
        else:  # Linux
            for name in exec_names:
                found_path = shutil.which(name)
                if found_path:
                    path = found_path
                    break

        if path:
            return {'name': browser['name'], 'path': path, 'args': browser['args'], 'is_mac_app': is_mac_app}
    return None

def open_browser_with_url(url: str, browser_command: Optional[Dict[str, Any]]):
    """Opens a URL using the detected browser or falls back to the default."""
    if not browser_command:
        # If no preferred browser is found, fall back to the OS default.
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
        else:  # Windows and Linux
            command.append(browser_command['path'])
            command.extend(browser_command['args'])
            command.append(url)
            if system == 'Windows':
                use_shell = True
            
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=use_shell)
    except (OSError, FileNotFoundError) as e:
        print(f"Error launching preferred browser: {e}. The browser might not be installed correctly.")
        # No fallback to webbrowser.open() here, as the fallback is handled at the start.
    
def _parse_latency(ping_output: str, is_windows: bool) -> str:
    """Parses latency from the ping command's stdout."""
    try:
        if is_windows:
            match = re.search(r"Average\s?=\s?(\d+)ms", ping_output)
            if match: return f"{match.group(1)}ms"
        else:  # Linux/macOS
            # Handle both "avg" and "durchschnitt" for English and German locales
            match = re.search(r"rtt min/(avg|durchschnitt)/max/mdev = [\d.]+/([\d.]+)/", ping_output)
            if match: return f"{int(float(match.group(2)))}ms"
    except (IndexError, ValueError):
        pass
    return ""

def _check_port(ip: str, port: int, timeout: float) -> str:
    """Checks if a TCP port is open on a given IP."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            if sock.connect_ex((ip, port)) == 0:
                return "Open"
            return "Closed"
        except socket.gaierror:
            return "Hostname Error"
        except socket.error:
            return "Conn Error"

def ping_worker(
    target: Dict[str, Any], 
    stop_event: threading.Event, 
    update_queue: queue.Queue, 
    browser_opened: set, 
    browser_command: Optional[Dict[str, Any]],
    app_config: Dict[str, Any]
):
    """
    Worker thread function to ping an IP, check ports, and queue GUI updates.
    """
    ip = target['ip']
    ports = target['ports']
    original_string = target['original_string']
    
    ping_interval = app_config['ping_interval_seconds']
    port_timeout = app_config['port_check_timeout_seconds']
    
    is_windows = platform.system().lower() == 'windows'
    command = ['ping', '-n' if is_windows else '-c', '1', '-w' if is_windows else '-W', '1000' if is_windows else '1', ip]

    while not stop_event.is_set():
        launched_browser = False
        port_statuses: Optional[Dict[int, str]] = None
        latency_str = ""
        
        try:
            startupinfo = None
            if is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            response = subprocess.run(
                command, check=True, capture_output=True, text=True, startupinfo=startupinfo
            )
            
            if response.returncode == 0 or (not is_windows and response.returncode == 1 and "1 received" in response.stdout):
                status, color = "Online", "green"
                latency_str = _parse_latency(response.stdout, is_windows)
                
                if ports:
                    port_statuses = {port: _check_port(ip, port, port_timeout) for port in ports}
                    if not any(s == "Open" for s in port_statuses.values()):
                        color = "orange"
                
                if ip not in browser_opened:
                    open_browser_with_url(f"https://{ip}", browser_command)
                    browser_opened.add(ip)
                    launched_browser = True
            else:
                status, color = "Offline", "red"

        except (subprocess.CalledProcessError, FileNotFoundError):
            status, color = "Offline", "red"
        
        update_queue.put((original_string, status, color, launched_browser, port_statuses, latency_str))
        stop_event.wait(timeout=ping_interval)