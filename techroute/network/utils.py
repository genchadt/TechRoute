"""
Core network utility functions.
"""
import socket
from functools import lru_cache
from typing import List, Optional, Tuple, cast

@lru_cache(maxsize=128)
def _is_ip_literal(host: str) -> Tuple[bool, Optional[int]]:
    """Checks if a string is a valid IP literal."""
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
    """Resolves a hostname to a list of addresses, caching the result."""
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
