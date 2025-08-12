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
    
def _udp_probe_primary_ip(family: int) -> Optional[str]:
    """Tries to discover the primary local IP by opening a UDP socket to a public IP."""
    try:
        with socket.socket(family, socket.SOCK_DGRAM) as s:
            # We don't actually send anything; just connect to pick a route
            if family == socket.AF_INET:
                s.connect(("8.8.8.8", 80))
            else:
                s.connect(("2001:4860:4860::8888", 80))
            return s.getsockname()[0]
    except OSError:
        return None

def _cidr_to_netmask(prefix_len: int) -> str:
    """Converts IPv4 CIDR prefix length to dotted decimal subnet mask."""
    mask = (0xffffffff << (32 - prefix_len)) & 0xffffffff
    return ".".join(str((mask >> (8 * i)) & 0xff) for i in reversed(range(4)))

def _parse_ipconfig_windows(output: str) -> Dict[str, Optional[str]]:
    """Parses ipconfig output to find primary interface IPv4, IPv6, mask, and default gateway."""
    primary_ipv4: Optional[str] = None
    primary_ipv6: Optional[str] = None
    subnet_mask: Optional[str] = None
    gateway: Optional[str] = None
    gateway_v4: Optional[str] = None
    gateway_v6: Optional[str] = None

    current_has_gateway = False
    # ipconfig uses CRLF; normalize lines
    for line in output.splitlines():
        line = line.strip()
        if not line:
            # Section boundary; reset flag for next adapter block
            current_has_gateway = False
            continue

        # IPv4 Address line
        if "IPv4 Address" in line and ":" in line:
            try:
                value = line.split(":", 1)[1].strip()
                # Newer ipconfig shows IPv4 Address. . . . . . . . . . . : 192.168.1.10
                if value and value != "0.0.0.0" and primary_ipv4 is None:
                    primary_ipv4 = value
            except Exception:
                pass
        # Subnet Mask line
        elif line.startswith("Subnet Mask") and ":" in line and subnet_mask is None:
            try:
                value = line.split(":", 1)[1].strip()
                if value:
                    subnet_mask = value
            except Exception:
                pass
        # Default Gateway line
        elif line.startswith("Default Gateway") and ":" in line and (gateway_v4 is None or gateway_v6 is None):
            try:
                value = line.split(":", 1)[1].strip()
                # Sometimes the first Default Gateway line is blank and the next line has the value
                if value:
                    # Classify as IPv4 vs IPv6 and store separately
                    if ":" in value:
                        if gateway_v6 is None:
                            gateway_v6 = value
                    else:
                        if gateway_v4 is None:
                            gateway_v4 = value
                    current_has_gateway = True
                else:
                    current_has_gateway = True
            except Exception:
                pass
        elif current_has_gateway and (gateway_v4 is None or gateway_v6 is None):
            # The line immediately after a blank Default Gateway can contain the IP
            parts = line.split()
            if parts and re.match(r"^[0-9a-fA-F:.%]+$", parts[0]):
                val = parts[0]
                if ":" in val:
                    if gateway_v6 is None:
                        gateway_v6 = val
                else:
                    if gateway_v4 is None:
                        gateway_v4 = val
        # IPv6 Address lines
        elif ("IPv6 Address" in line or "Link-local IPv6 Address" in line) and ":" in line and primary_ipv6 is None:
            try:
                value = line.split(":", 1)[1].strip()
                # Remove possible (Preferred) suffix
                value = value.split(" ")[0]
                if value:
                    primary_ipv6 = value
            except Exception:
                pass

    # Prefer IPv4 gateway if available
    gateway = gateway_v4 or gateway_v6
    return {
        "primary_ipv4": primary_ipv4,
        "primary_ipv6": primary_ipv6,
        "subnet_mask": subnet_mask,
        "gateway": gateway,
    }

def _linux_network_info() -> Dict[str, Optional[str]]:
    primary_ipv4 = _udp_probe_primary_ip(socket.AF_INET)
    primary_ipv6 = _udp_probe_primary_ip(socket.AF_INET6)
    gateway = None
    subnet_mask = None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # default route
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True, creationflags=creationflags)
        m = re.search(r"default via (\S+).* dev (\S+)", out)
        if m:
            gateway = m.group(1)
            dev = m.group(2)
            # find cidr for that dev
            out4 = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "dev", dev], text=True, creationflags=creationflags)
            m4 = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", out4)
            if m4:
                if not primary_ipv4:
                    primary_ipv4 = m4.group(1)
                subnet_mask = _cidr_to_netmask(int(m4.group(2)))
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return {
        "primary_ipv4": primary_ipv4,
        "primary_ipv6": primary_ipv6,
        "subnet_mask": subnet_mask,
        "gateway": gateway,
    }

def _macos_network_info() -> Dict[str, Optional[str]]:
    primary_ipv4 = _udp_probe_primary_ip(socket.AF_INET)
    primary_ipv6 = _udp_probe_primary_ip(socket.AF_INET6)
    gateway = None
    subnet_mask = None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.check_output(["route", "-n", "get", "default"], text=True, creationflags=creationflags)
        m = re.search(r"gateway:\s+(\S+)", out)
        if m:
            gateway = m.group(1)
        m = re.search(r"interface:\s+(\S+)", out)
        if m:
            iface = m.group(1)
            try:
                out_if = subprocess.check_output(["ifconfig", iface], text=True, creationflags=creationflags)
                m4 = re.search(r"inet (\d+\.\d+\.\d+\.\d+) netmask 0x([0-9a-fA-F]+)", out_if)
                if m4:
                    if not primary_ipv4:
                        primary_ipv4 = m4.group(1)
                    mask_hex = int(m4.group(2), 16)
                    subnet_mask = ".".join(str((mask_hex >> (8 * i)) & 0xff) for i in reversed(range(4)))
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return {
        "primary_ipv4": primary_ipv4,
        "primary_ipv6": primary_ipv6,
        "subnet_mask": subnet_mask,
        "gateway": gateway,
    }

def get_network_info() -> Dict[str, Optional[str]]:
    """Returns basic network info: primary IPv4/IPv6, default gateway, subnet mask.

    This uses platform-specific commands when available and falls back to socket probes.
    """
    system = platform.system().lower()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if system == "windows":
        try:
            out = subprocess.check_output(["ipconfig"], text=True, creationflags=creationflags)
            info = _parse_ipconfig_windows(out)
            # Fallback primary IPs if missing
            info.setdefault("primary_ipv4", _udp_probe_primary_ip(socket.AF_INET))
            info.setdefault("primary_ipv6", _udp_probe_primary_ip(socket.AF_INET6))
            return info
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return {
            "primary_ipv4": _udp_probe_primary_ip(socket.AF_INET),
            "primary_ipv6": _udp_probe_primary_ip(socket.AF_INET6),
            "subnet_mask": None,
            "gateway": None,
        }
    if system == "linux":
        return _linux_network_info()
    if system == "darwin":
        return _macos_network_info()
    # Unknown OS fallback
    return {
        "primary_ipv4": _udp_probe_primary_ip(socket.AF_INET),
        "primary_ipv6": _udp_probe_primary_ip(socket.AF_INET6),
        "subnet_mask": None,
        "gateway": None,
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

_DNS_CACHE: Dict[str, Tuple[float, List[Tuple[int, str, int, int]]]] = {}
_DNS_TTL_SECONDS = 300  # cache DNS results for 5 minutes

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

    now = time.time()
    cached = _DNS_CACHE.get(host)
    if cached and now - cached[0] < _DNS_TTL_SECONDS:
        return cached[1]

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

    _DNS_CACHE[host] = (now, deduped)
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
