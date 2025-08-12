# techroute/network.py

"""
Network utilities for TechRoute.

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
from typing import Dict, Any, List, Optional, Tuple, cast
import sys
import time
import random
import psutil
from functools import lru_cache
import ipaddress
from .routing import get_default_gateway

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
        elif system == 'Linux':
            # First, try to find the browser in the system's PATH
            for name in exec_names:
                found_path = shutil.which(name)
                if found_path:
                    path = found_path
                    break
            
            # If not found, check some common hardcoded paths as a fallback
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

def get_network_info() -> Dict[str, Optional[str]]:
    """
    Returns basic network info using psutil for cross-platform reliability.
    """
    primary_ipv4: Optional[str] = None
    primary_ipv6: Optional[str] = None
    subnet_mask: Optional[str] = None
    gateway: Optional[str] = None

    try:
        # Get all network interfaces
        addrs = psutil.net_if_addrs()
        gateway = get_default_gateway()

        # Find the interface associated with the gateway to get other network info
        default_interface = None
        if gateway:
            for if_name, if_addrs in addrs.items():
                for addr in if_addrs:
                    if addr.family == socket.AF_INET and addr.netmask:
                        # A simple heuristic: if an interface's network contains the gateway,
                        # it's likely the right one. This is not foolproof.
                        try:
                            ip_net = ipaddress.ip_network(f"{addr.address}/{addr.netmask}", strict=False)
                            if ipaddress.ip_address(gateway) in ip_net:
                                default_interface = if_name
                                break
                        except (ValueError, TypeError):
                            continue
                if default_interface:
                    break
        
        if default_interface and default_interface in addrs:
            # Prioritize the default interface for finding the primary IP
            for addr in addrs[default_interface]:
                if addr.family == socket.AF_INET:
                    primary_ipv4 = addr.address
                    subnet_mask = addr.netmask
                elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80::"):
                    if primary_ipv6 is None: # Take the first non-link-local IPv6
                        primary_ipv6 = addr.address

        # Fallback if default interface logic fails: iterate all interfaces
        if not primary_ipv4:
            for if_name, if_addrs in addrs.items():
                # Skip loopback interfaces
                if if_name.lower().startswith('lo') or 'loopback' in if_name.lower():
                    continue
                for addr in if_addrs:
                    if addr.family == socket.AF_INET:
                        if primary_ipv4 is None:
                            primary_ipv4 = addr.address
                            subnet_mask = addr.netmask
                    elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80::"):
                        if primary_ipv6 is None:
                            primary_ipv6 = addr.address
    except Exception as e:
        print(f"Could not retrieve network info using psutil: {e}")

    return {
        "primary_ipv4": primary_ipv4,
        "primary_ipv6": primary_ipv6,
        "subnet_mask": subnet_mask,
        "gateway": gateway,
    }

def _parse_latency(ping_output: str, is_windows: bool) -> str:
    """Parses latency from the ping command's stdout."""
    try:
        if is_windows:
            match = re.search(r"Average\s?=\s?(\d+)ms", ping_output)
            if match: return f"{match.group(1)}ms"
        else:  # Linux/macOS
            # Handle common Unix ping summaries
            # Linux:  rtt min/avg/max/mdev = 10.123/12.345/...
            m = re.search(r"rtt min/(avg|durchschnitt)/max/(mdev|stddev) = [\d.]+/([\d.]+)/", ping_output)
            if m:
                return f"{int(float(m.group(3)))}ms"
            # macOS: round-trip min/avg/max/stddev = 10.123/12.345/...
            m = re.search(r"round-trip min/(avg|durchschnitt)/max/(mdev|stddev) = [\d.]+/([\d.]+)/", ping_output)
            if m:
                return f"{int(float(m.group(2)))}ms"
    except (IndexError, ValueError):
        pass
    return ""

@lru_cache(maxsize=128)
def _is_ip_literal(host: str) -> Tuple[bool, Optional[int]]:
    try:
        ip_obj = socket.inet_pton(socket.AF_INET, host)
        return True, socket.AF_INET
    except OSError:
        pass
    try:
        ip_obj = socket.inet_pton(socket.AF_INET6, host.split('%')[0])  # strip scope if present
        return True, socket.AF_INET6
    except OSError:
        return False, None

@lru_cache(maxsize=128)
def _cached_resolve_host(host: str) -> List[Tuple[int, str, int, int]]:
    """Resolve hostname to a list of addresses with basic TTL cache.

    Returns list of tuples: (family, ip, flowinfo, scopeid)
    For IPv4, flowinfo and scopeid are 0.
    If host is already an IP literal, returns a single-entry list immediately.
    """
    is_ip, family = _is_ip_literal(host)
    if is_ip:
        if family == socket.AF_INET:
            return [(socket.AF_INET, host, 0, 0)]
        else:
            # Extract optional scope id like fe80::1%eth0
            ip_only, _, scope = host.partition('%')
            scopeid = 0
            try:
                # Best-effort: convert interface name to index if provided
                if scope:
                    scopeid = socket.if_nametoindex(scope)
            except OSError:
                # Not an interface name or not available
                scopeid = 0
            return [(socket.AF_INET6, ip_only, 0, scopeid)]

    results: List[Tuple[int, str, int, int]] = []
    try:
        # Resolve without port to avoid duplicating per-port lookups
        infos = socket.getaddrinfo(host, None)
        for family, socktype, proto, canonname, sockaddr in infos:
            if family == socket.AF_INET:
                if isinstance(sockaddr, tuple) and len(sockaddr) >= 2 and isinstance(sockaddr[0], (str, bytes)):
                    ip = cast(str, sockaddr[0] if isinstance(sockaddr[0], str) else sockaddr[0].decode('ascii', 'ignore'))
                    results.append((family, ip, 0, 0))
            elif family == socket.AF_INET6:
                if isinstance(sockaddr, tuple):
                    if len(sockaddr) == 4:
                        ip6 = cast(str, sockaddr[0])
                        flowinfo = cast(int, sockaddr[2])
                        scopeid = cast(int, sockaddr[3])
                        results.append((family, ip6, flowinfo, scopeid))
                    elif len(sockaddr) >= 2:
                        ip6 = cast(str, sockaddr[0])
                        results.append((family, ip6, 0, 0))
    except socket.gaierror:
        results = []

    # De-duplicate while preserving order
    seen = set()
    deduped: List[Tuple[int, str, int, int]] = []
    for rec in results:
        key = (rec[0], rec[1], rec[3])
        if key not in seen:
            seen.add(key)
            deduped.append(rec)

    return deduped

def _select_ping_target(host: str) -> Tuple[str, bool]:
    """Choose a concrete IP address to ping and whether to use IPv6 option.

    Preference: if any IPv6 addresses exist, prefer IPv6 (keeping prior behavior);
    otherwise use IPv4. Returns (ip_string, use_ipv6).
    """
    addrs = _cached_resolve_host(host)
    v6 = [a for a in addrs if a[0] == socket.AF_INET6]
    v4 = [a for a in addrs if a[0] == socket.AF_INET]
    if v6:
        ip, flow, scope = v6[0][1], v6[0][2], v6[0][3]
        # Re-attach scope if applicable
        ip_with_scope = f"{ip}%{scope}" if scope else ip
        return ip_with_scope, True
    if v4:
        return v4[0][1], False
    # Fallback to original host; let ping decide
    return host, False

def _check_port(host: str, port: int, timeout: float) -> str:
    """Checks if a TCP port is open on a given host (IPv4/IPv6/hostname)."""
    addrs = _cached_resolve_host(host)
    if not addrs:
        return "Hostname Error"

    for family, ip, flowinfo, scopeid in addrs:
        try:
            with socket.socket(family, socket.SOCK_STREAM, 0) as sock:
                sock.settimeout(timeout)
                if family == socket.AF_INET:
                    sockaddr = (ip, port)
                else:
                    sockaddr = (ip, port, flowinfo, scopeid)
                if sock.connect_ex(sockaddr) == 0:
                    return "Open"
        except socket.timeout:
            continue
        except OSError:
            continue
    return "Closed"

def check_tcp_port(host: str, port: int, timeout: float) -> str:
    """Public helper to check a TCP port.

    Returns one of: "Open", "Closed", or "Hostname Error".
    """
    return _check_port(host, port, timeout)

def ping_worker(
    target: Dict[str, Any], 
    stop_event: threading.Event, 
    update_queue: queue.Queue,
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
    # Resolve a concrete target to avoid repeated DNS inside ping and prefer IPv6 when available
    concrete_ip, use_ipv6 = _select_ping_target(ip)

    # Build ping command; pass numeric/quiet flags to avoid reverse DNS and reduce output noise
    command: List[str] = ['ping']
    if is_windows:
        if use_ipv6:
            command.append('-6')
        # -n 1 (count), -w 1000 (timeout ms)
        command.extend(['-n', '1', '-w', '1000', concrete_ip])
    else:
        if use_ipv6:
            command.append('-6')
        # -n: no DNS lookups, -q: quiet summary, -c 1: count, -W 1: timeout (s)
        command.extend(['-n', '-q', '-c', '1', '-W', '1', concrete_ip])

    # Add a tiny initial jitter so many threads don't synchronize and spike the CPU at once
    if ping_interval > 0:
        stop_event.wait(timeout=random.uniform(0, min(0.3, ping_interval * 0.25)))

    while not stop_event.is_set():
        port_statuses: Optional[Dict[int, str]] = None
        udp_service_statuses: Optional[Dict[str, str]] = None
        latency_str = ""
        web_port_open = False
        
        try:
            # --- ICMP Ping ---
            ping_output = subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0
            )
            status = "Online"
            color = "green"
            latency_str = _parse_latency(ping_output, is_windows)

            # --- TCP Port Check ---
            if ports:
                port_statuses = {}
                for port in ports:
                    port_status = _check_port(ip, port, port_timeout)
                    port_statuses[port] = port_status
                    if port_status == 'Open' and port in [80, 443, 8080]:
                        web_port_open = True
            # --- UDP Service Checks (optional) ---
            try:
                udp_ports = app_config.get('udp_services_to_check', []) or []
                if udp_ports:
                    # Local import to avoid heavy deps on module import
                    from .checkers import get_udp_service_registry  # type: ignore
                    registry = get_udp_service_registry()
                    udp_service_statuses = {}
                    for udp_port in udp_ports:
                        entry = registry.get(int(udp_port))
                        if not entry:
                            continue
                        service_name, checker = entry
                        try:
                            res = checker.check(ip, timeout=max(0.5, min(2.0, port_timeout)))
                            udp_service_statuses[service_name] = "Open" if res.available else "Closed"
                        except Exception:
                            udp_service_statuses[service_name] = "Closed"
            except Exception:
                # If anything goes wrong, skip UDP checks quietly
                pass
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            status = "Offline"
            color = "red"

        # Queue result for UI
        update_queue.put((
            original_string,
            status,
            color,
            port_statuses,
            latency_str,
            web_port_open,
            udp_service_statuses,
        ))
        stop_event.wait(timeout=ping_interval)
