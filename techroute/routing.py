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
    Parses 'ipconfig' output to find the default gateway on Windows.
    """
    try:
        output = subprocess.check_output(["ipconfig"], text=True, stderr=subprocess.PIPE)
        # Regex to find the Default Gateway line, which may have a link-local IPv6
        # gateway listed first. We prioritize the IPv4 gateway.
        # The pattern looks for "Default Gateway" followed by lines of IPs.
        gateway_pattern = re.compile(r"Default Gateway[.\s]*:\s*([^\s\n]+(?:\n\s+[^\s\n]+)*)")
        
        matches = gateway_pattern.findall(output)
        
        for match in matches:
            # The match might contain multiple lines if both IPv6 and IPv4 gateways are present.
            # We split by newline and strip whitespace to get individual IPs.
            gateways = [gw.strip() for gw in match.strip().split('\n')]
            for gw in gateways:
                # A simple check for an IPv4 address format.
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw):
                    return gw
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
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
