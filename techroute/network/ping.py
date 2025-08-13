"""
Handles the core network pinging and port checking operations.
"""
import os
import platform
import queue
import re
import socket
import subprocess
import threading
import time
import random
from functools import lru_cache
import ipaddress
from typing import Dict, Any, List, Optional, Tuple, cast, Callable

def _parse_latency(ping_output: str, is_windows: bool) -> str:
    """Parses latency from the ping command's stdout."""
    try:
        if is_windows:
            match = re.search(r"Average\s?=\s?(\d+)ms", ping_output)
            if match: return f"{match.group(1)}ms"
        else:
            m = re.search(r"rtt min/(avg|durchschnitt)/max/(mdev|stddev) = [\d.]+/([\d.]+)/", ping_output)
            if m:
                return f"{int(float(m.group(3)))}ms"
            m = re.search(r"round-trip min/(avg|durchschnitt)/max/(mdev|stddev) = [\d.]+/([\d.]+)/", ping_output)
            if m:
                return f"{int(float(m.group(2)))}ms"
    except (IndexError, ValueError):
        pass
    return ""

@lru_cache(maxsize=128)
def _is_ip_literal(host: str) -> Tuple[bool, Optional[int]]:
    try:
        socket.inet_pton(socket.AF_INET, host)
        return True, socket.AF_INET
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, host.split('%')[0])
        return True, socket.AF_INET6
    except OSError:
        return False, None

@lru_cache(maxsize=128)
def _cached_resolve_host(host: str) -> List[Tuple[int, str, int, int]]:
    """Resolve hostname to a list of addresses."""
    is_ip, family = _is_ip_literal(host)
    if is_ip:
        if family == socket.AF_INET:
            return [(socket.AF_INET, host, 0, 0)]
        else:
            ip_only, _, scope = host.partition('%')
            scopeid = 0
            try:
                if scope:
                    scopeid = socket.if_nametoindex(scope)
            except OSError:
                scopeid = 0
            return [(socket.AF_INET6, ip_only, 0, scopeid)]

    results: List[Tuple[int, str, int, int]] = []
    try:
        infos = socket.getaddrinfo(host, None)
        for family, socktype, proto, canonname, sockaddr in infos:
            if family == socket.AF_INET:
                if isinstance(sockaddr, tuple) and len(sockaddr) >= 2:
                    ip = cast(str, sockaddr[0])
                    results.append((family, ip, 0, 0))
            elif family == socket.AF_INET6:
                if isinstance(sockaddr, tuple) and len(sockaddr) == 4:
                    ip6, flowinfo, scopeid = cast(str, sockaddr[0]), cast(int, sockaddr[2]), cast(int, sockaddr[3])
                    results.append((family, ip6, flowinfo, scopeid))
    except socket.gaierror:
        results = []

    seen = set()
    deduped: List[Tuple[int, str, int, int]] = []
    for rec in results:
        key = (rec[0], rec[1], rec[3])
        if key not in seen:
            seen.add(key)
            deduped.append(rec)
    return deduped

def _select_ping_target(host: str) -> Tuple[str, bool]:
    """Choose a concrete IP address to ping."""
    addrs = _cached_resolve_host(host)
    v6 = [a for a in addrs if a[0] == socket.AF_INET6]
    v4 = [a for a in addrs if a[0] == socket.AF_INET]
    if v6:
        ip, _, scope = v6[0][1], v6[0][2], v6[0][3]
        return f"{ip}%{scope}" if scope else ip, True
    if v4:
        return v4[0][1], False
    return host, False

def _check_port(host: str, port: int, timeout: float) -> str:
    """Checks if a TCP port is open on a given host."""
    addrs = _cached_resolve_host(host)
    if not addrs:
        return "Hostname Error"

    for family, ip, flowinfo, scopeid in addrs:
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sockaddr = (ip, port) if family == socket.AF_INET else (ip, port, flowinfo, scopeid)
                if sock.connect_ex(sockaddr) == 0:
                    return "Open"
        except (socket.timeout, OSError):
            continue
    return "Closed"

def check_tcp_port(host: str, port: int, timeout: float) -> str:
    """Public helper to check a TCP port."""
    return _check_port(host, port, timeout)

def ping_worker(
    target: Dict[str, Any],
    stop_event: threading.Event,
    update_queue: queue.Queue,
    app_config: Dict[str, Any],
    translator: Callable[[str], str]
):
    """Worker thread function to ping an IP, check ports, and queue GUI updates."""
    ip, ports, original_string = target['ip'], target['ports'], target['original_string']
    ping_interval = app_config['ping_interval_seconds']
    port_timeout = app_config['port_check_timeout_seconds']
    is_windows = platform.system().lower() == 'windows'
    concrete_ip, use_ipv6 = _select_ping_target(ip)

    command: List[str] = ['ping']
    if is_windows:
        command.extend(['-n', '1', '-w', '1000'])
        if use_ipv6: command.append('-6')
        command.append(concrete_ip)
    else:
        command.extend(['-n', '-q', '-c', '1', '-W', '1'])
        if use_ipv6: command.append('-6')
        command.append(concrete_ip)

    def _perform_check():
        """Performs all checks (ping, TCP, UDP) and returns a status tuple."""
        port_statuses: Optional[Dict[str, str]] = None
        udp_service_statuses: Optional[Dict[str, str]] = None
        latency_str, web_port_open = "", False

        try:
            ping_output = subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0
            )
            status, color = translator("Online"), "green"
            latency_str = _parse_latency(ping_output, is_windows)
        except (subprocess.CalledProcessError, FileNotFoundError):
            status, color = translator("Offline"), "red"

        # Always check ports, even if ping fails
        if ports:
            port_statuses = {str(port): _check_port(ip, port, port_timeout) for port in ports}
            if any(port_statuses.get(str(p)) == 'Open' for p in [80, 443, 8080]):
                web_port_open = True

        udp_ports_to_check = app_config.get('udp_services_to_check', [])
        if udp_ports_to_check:
            from ..checkers import get_udp_service_registry
            registry = get_udp_service_registry()
            udp_service_statuses = {}
            for port in udp_ports_to_check:
                if port not in registry:
                    continue
                
                service_name, checker = registry[port]
                try:
                    res = checker.check(ip, timeout=max(0.5, min(2.0, port_timeout)))
                    udp_service_statuses[service_name] = "Open" if res and res.available else "Closed"
                except Exception:
                    udp_service_statuses[service_name] = "Closed"
        
        return (
            original_string, status, color, port_statuses, latency_str,
            web_port_open, udp_service_statuses
        )

    # Perform an initial check immediately
    update_queue.put(_perform_check())

    while not stop_event.is_set():
        if ping_interval > 0:
            stop_event.wait(timeout=ping_interval)
        
        if stop_event.is_set():
            break

        update_queue.put(_perform_check())
