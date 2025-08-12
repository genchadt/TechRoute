# techroute/routing.py

"""
Handles OS-specific routing table and gateway lookups.

This is necessary because psutil's net_if_gateways() is not universally
reliable or available, especially on older versions or certain OS builds.
"""

import platform
import subprocess
import re
from typing import Optional, Tuple

def _get_windows_gateway() -> Optional[str]:
    """
    Uses PowerShell to get the default gateway for the active network connection on Windows.
    This is more reliable than parsing `ipconfig` as it is not dependent on string localization.
    It now explicitly selects the first available gateway to handle multi-homed systems.
    """
    try:
        # Command updated to select the first valid gateway from potentially multiple active adapters.
        command = "powershell -Command \"(Get-NetIPConfiguration | Where-Object { $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway -ne $null } | Select-Object -First 1).IPv4DefaultGateway.NextHop\""
        
        # Using CREATE_NO_WINDOW flag to prevent a console window from flashing.
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE

        output = subprocess.check_output(command, text=True, stderr=subprocess.PIPE, startupinfo=si)
        
        # The command might still return multiple lines if something is unusual. Take the first one.
        first_line = output.strip().splitlines()[0] if output.strip() else None
        
        if first_line and first_line != "0.0.0.0":
            return first_line
            
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        # IndexError is caught in case output is empty.
        return None
    return None

def _get_linux_gateway() -> Optional[str]:
    """
    Parses 'ip route' output to find the default gateway on Linux.
    """
    try:
        output = subprocess.check_output(["ip", "route"], text=True, stderr=subprocess.PIPE)
        # Look for the 'default via' line
        match = re.search(r"default via ([\d\.]+)", output)
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return None
    return None

def _get_macos_gateway() -> Optional[str]:
    """
    Parses 'netstat -nr' output to find the default gateway on macOS.
    """
    try:
        output = subprocess.check_output(["netstat", "-nr"], text=True, stderr=subprocess.PIPE)
        # Look for the 'default' line for the 'Internet' (IPv4) family
        match = re.search(r"^default\s+([\d\.]+)\s+.*$", output, re.MULTILINE)
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return None
    return None

def get_default_gateway() -> Optional[str]:
    """
    Returns the default gateway IP by calling the OS-specific function.
    """
    system = platform.system()
    if system == "Windows":
        return _get_windows_gateway()
    elif system == "Linux":
        return _get_linux_gateway()
    elif system == "Darwin":
        return _get_macos_gateway()
    return None
