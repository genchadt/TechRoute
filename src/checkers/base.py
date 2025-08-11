from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Protocol
import socket


@dataclass
class CheckResult:
    """
    Unified result for a UDP service check.

    - available: whether basic availability probe succeeded
    - info: optional small dictionary with service-specific details
    - error: optional error string when the check failed in an exceptional way
    """
    available: bool
    info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseChecker(Protocol):
    """Protocol for service checkers."""

    name: str
    port: int

    def check(self, host: str, timeout: float = 1.0) -> CheckResult:  # pragma: no cover - protocol
        ...


def udp_send_receive(
    host: str,
    port: int,
    payload: bytes,
    *,
    timeout: float = 1.0,
    family_hint: Optional[int] = None,
    bind_multicast: Optional[str] = None,
) -> CheckResult:
    """
    Lightweight UDP send/receive helper supporting IPv4/IPv6 and optional multicast binding.

    - host: destination hostname/IP
    - port: destination UDP port
    - payload: bytes to send
    - timeout: seconds to wait for a response
    - family_hint: optionally force AF_INET/AF_INET6
    - bind_multicast: optional local address to bind for multicast (e.g., "224.0.0.251" or "ff02::fb")
    """
    try:
        # Resolve host
        infos = socket.getaddrinfo(host, port, family_hint or 0, socket.SOCK_DGRAM)
        if not infos:
            return CheckResult(False, error="Resolution failed")

        for family, socktype, proto, canonname, sockaddr in infos:
            try:
                with socket.socket(family, socket.SOCK_DGRAM, proto) as s:
                    s.settimeout(timeout)
                    # Allow reuse for multicast scenarios
                    try:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    except OSError:
                        pass

                    # Optional bind if checking multicast groups
                    if bind_multicast:
                        try:
                            if family == socket.AF_INET:
                                s.bind((bind_multicast, 0))
                            elif family == socket.AF_INET6:
                                s.bind((bind_multicast, 0, 0, 0))
                        except OSError:
                            # If bind fails, continue without it
                            pass

                    s.sendto(payload, sockaddr)
                    try:
                        data, addr = s.recvfrom(2048)
                        return CheckResult(True, info={"from": addr, "bytes": len(data)})
                    except socket.timeout:
                        continue
            except OSError:
                continue
        return CheckResult(False)
    except socket.gaierror as e:
        return CheckResult(False, error=str(e))
