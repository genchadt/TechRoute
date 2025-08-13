"""
Handles discovery of local network information.
"""
import socket
import ipaddress
from typing import Dict, Optional
import psutil
from ..routing import get_default_gateway

def get_network_info() -> Dict[str, Optional[str]]:
    """
    Returns basic network info using psutil for cross-platform reliability.
    """
    primary_ipv4: Optional[str] = None
    primary_ipv6: Optional[str] = None
    subnet_mask: Optional[str] = None
    gateway: Optional[str] = None

    try:
        addrs = psutil.net_if_addrs()
        gateway = get_default_gateway()

        default_interface = None
        if gateway:
            for if_name, if_addrs in addrs.items():
                for addr in if_addrs:
                    if addr.family == socket.AF_INET and addr.netmask:
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
            for addr in addrs[default_interface]:
                if addr.family == socket.AF_INET:
                    primary_ipv4 = addr.address
                    subnet_mask = addr.netmask
                elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80::"):
                    if primary_ipv6 is None:
                        primary_ipv6 = addr.address

        if not primary_ipv4:
            for if_name, if_addrs in addrs.items():
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
