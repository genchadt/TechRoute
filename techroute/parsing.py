"""
Handles parsing and validation of network targets.
"""
from __future__ import annotations
import ipaddress
from typing import Dict, Any, List, Tuple

class TargetParser:
    """Parses and validates target strings."""

    def __init__(self, default_ports: List[int]):
        self.default_ports = default_ports

    def parse_and_validate_targets(self, ip_string: str) -> List[Dict[str, Any]]:
        """
        Parses a string of IPs/hostnames and ports, validating each and removing duplicates.
        """
        targets = []
        processed_hosts = set()
        lines = [line.strip() for line in ip_string.splitlines() if line.strip()]
        
        for line in lines:
            host, ports_list = self._parse_target_line(line)
            
            normalized_host = '127.0.0.1' if host == 'localhost' else host
            
            if normalized_host in processed_hosts:
                continue

            self._validate_host(host)
            
            all_ports = sorted(list(set(ports_list + self.default_ports)))
            
            target: Dict[str, Any] = {
                'ip': host, 
                'ports': all_ports, 
                'original_string': line
            }
            targets.append(target)
            processed_hosts.add(normalized_host)
            
        return targets

    def _parse_target_line(self, line: str) -> Tuple[str, List[int]]:
        """Parses a single line of target input into a host and a list of ports."""
        s = line.strip()
        if s.startswith('['):
            end = s.find(']')
            if end == -1:
                raise ValueError(f"Missing closing ']' in '{s}'. For IPv6 with ports use: [fe80::1]:80,443")
            host = s[1:end]
            rest = s[end+1:].strip()
            if rest.startswith(':'):
                port_str = rest[1:].strip()
                if port_str:
                    return host, self._parse_ports(port_str, s)
            elif rest:
                raise ValueError(f"Unexpected text after ']': '{rest}'.")
            return host, []
        else:
            try:
                ipaddress.ip_address(s)
                return s, []
            except ValueError:
                if ':' in s:
                    # This logic is tricky. A colon could be an IPv6 address or a port separator.
                    # We'll assume if it doesn't validate as an IP, it's host:port.
                    # This might fail for bare IPv6 addresses, but they should be bracketed.
                    parts = s.rsplit(':', 1)
                    host, port_str = parts[0].strip(), parts[1].strip()
                    if host and port_str:
                        return host, self._parse_ports(port_str, s)
                return s, []

    def _parse_ports(self, port_str: str, original_line: str) -> List[int]:
        """Parses a comma-separated string of ports into a list of integers."""
        try:
            ports = [int(p.strip()) for p in port_str.split(',') if p.strip()]
            if not all(0 < port < 65536 for port in ports):
                raise ValueError
            return ports
        except (ValueError, TypeError):
            raise ValueError(f"Invalid port list in '{original_line}'. Use comma-separated numbers (1-65535).")

    def _validate_host(self, host: str) -> None:
        """Validates a hostname or IP address."""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not host or len(host) > 253:
                raise ValueError(f"The hostname '{host}' is not valid.")
            labels = host.split('.')
            if not all(labels):
                raise ValueError(f"The hostname '{host}' contains empty labels.")
            for lbl in labels:
                if not (1 <= len(lbl) <= 63):
                    raise ValueError(f"The hostname '{host}' has an invalid label length.")
                if lbl.startswith('-') or lbl.endswith('-'):
                    raise ValueError(f"The hostname '{host}' has a label starting/ending with '-'.")
                if not all(c.isalnum() or c == '-' for c in lbl):
                    raise ValueError(f"The hostname '{host}' contains invalid characters.")

    @staticmethod
    def extract_host(value: str) -> str:
        """Extracts the host from an input line that may include ports and/or IPv6 brackets."""
        s = value.strip()
        if s.startswith('['):
            end = s.find(']')
            if end != -1:
                return s[1:end]
        try:
            ipaddress.ip_address(s)
            return s
        except ValueError:
            pass
        if ':' in s:
            # Check if it's a hostname with a port
            if '.' in s.split(':', 1)[0]:
                return s.split(':', 1)[0].strip()
            # It could be an unbracketed IPv6, so we can't just split.
            # However, for the purpose of this app, we assume hostnames are FQDNs or simple names.
            # A simple split is likely sufficient for the intended use case.
            return s.split(':', 1)[0].strip()
        return s

    @staticmethod
    def format_host_for_url(host: str) -> str:
        """Wrap IPv6 literal hosts in brackets for URL building."""
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.version == 6:
                return f"[{host}]"
        except ValueError:
            pass
        return host
