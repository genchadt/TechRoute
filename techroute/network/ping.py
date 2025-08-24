"""
Handles the core network pinging and port checking operations.
"""
import os
import platform
import queue
import re
import socket
import struct
import select
import subprocess
import threading
import time
import random
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass

from ..models import StatusUpdate
from .utils import _cached_resolve_host, check_tcp_port

@dataclass
class ICMPPacket:
    type: int
    code: int
    checksum: int
    identifier: int
    sequence: int
    payload: bytes

    def pack(self) -> bytes:
        header = struct.pack('!BBHHH', self.type, self.code, 0, self.identifier, self.sequence)
        checksum = self._calculate_checksum(header + self.payload)
        header = struct.pack('!BBHHH', self.type, self.code, checksum, self.identifier, self.sequence)
        return header + self.payload

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        if len(data) % 2:
            data += b'\x00'
        res = sum(struct.unpack('!%dH' % (len(data) // 2), data))
        res = (res >> 16) + (res & 0xffff)
        res += res >> 16
        return ~res & 0xffff

class ICMPPinger:
    """Handles ICMP echo requests using raw sockets."""
    
    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout
        self.sequence = random.randint(0, 0xffff)
        self.identifier = random.randint(0, 0xffff)
        
    def ping(self, host: str) -> Tuple[bool, float]:
        """Send ICMP echo request and measure round-trip time."""
        try:
            is_ipv6 = ':' in host
            sock_type = socket.AF_INET6 if is_ipv6 else socket.AF_INET
            sock_proto = socket.IPPROTO_ICMPV6 if is_ipv6 else socket.IPPROTO_ICMP
            
            with socket.socket(sock_type, socket.SOCK_RAW, sock_proto) as sock:
                sock.settimeout(self.timeout)
                
                # Create ICMP packet
                packet = ICMPPacket(
                    type=128 if is_ipv6 else 8,  # Echo request
                    code=0,
                    checksum=0,
                    identifier=self.identifier,
                    sequence=self.sequence,
                    payload=struct.pack('d', time.time())
                )
                
                # Send packet
                dest_addr = host.split('%')[0]  # Remove scope from IPv6
                sock.sendto(packet.pack(), (dest_addr, 0))
                
                # Wait for response
                start_time = time.time()
                ready = select.select([sock], [], [], self.timeout)
                if ready[0]:
                    data, addr = sock.recvfrom(1024)
                    elapsed = (time.time() - start_time) * 1000  # Convert to ms
                    return True, round(elapsed, 1)
        except (socket.error, socket.timeout):
            pass
        return False, 0.0

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

def ping_worker(
    target: Dict[str, Any],
    stop_event: threading.Event,
    update_queue: queue.Queue,
    app_config: Dict[str, Any],
    translator: Callable[[str], str],
    on_first_check_done: Optional[Callable[[], None]] = None
):
    """Worker thread function to ping an IP, check ports, and queue GUI updates."""
    ip, ports, original_string = target['ip'], target['ports'], target['original_string']
    ping_interval = app_config['ping_interval_seconds']
    port_timeout = app_config['port_check_timeout_seconds']
    is_windows = platform.system().lower() == 'windows'
    concrete_ip, use_ipv6 = _select_ping_target(ip)

    pinger = ICMPPinger(timeout=1.0)

    def _perform_check() -> StatusUpdate:
        """Performs all checks (ping, TCP, UDP) and returns a status tuple."""
        port_statuses: Optional[Dict[str, str]] = None
        udp_service_statuses: Optional[Dict[str, str]] = None
        latency_str, web_port_open = "", False

        success, latency_ms = pinger.ping(concrete_ip)
        if success:
            status, color = translator("Online"), "green"
            latency_str = f"{latency_ms}ms"
        else:
            status, color = translator("Offline"), "red"

        # Always check ports, even if ping fails
        if ports:
            port_statuses = {str(port): check_tcp_port(ip, port, port_timeout) for port in ports}
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
        
        return StatusUpdate(
            original_string=original_string,
            status=status,
            color=color,
            port_statuses=port_statuses,
            latency_str=latency_str,
            web_port_open=web_port_open,
            udp_service_statuses=udp_service_statuses
        )

    # Perform an initial check immediately
    update_queue.put(_perform_check())

    if on_first_check_done:
        on_first_check_done()

    while not stop_event.is_set():
        if ping_interval > 0:
            stop_event.wait(timeout=ping_interval)
        
        if stop_event.is_set():
            break

        update_queue.put(_perform_check())
