"""
Handles discovery of local network information.
"""
import socket
import ipaddress
import re
import subprocess
import logging
from typing import Dict, Optional, Tuple
import psutil
from ..routing import get_default_gateway

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cache for network information
_network_info_cache: Optional[Dict[str, Optional[str]]] = None

def _run_command(command: str) -> Optional[str]:
    """Executes a shell command and returns its output."""
    try:
        return subprocess.check_output(command, shell=True, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logging.warning(f"Command '{command}' failed: {e}")
        return None

def _parse_ip_addr_output(output: str, gateway: str) -> Optional[Tuple[str, str]]:
    """Parses the output of 'ip addr' to find the primary IP and netmask."""
    try:
        # Find the interface associated with the default gateway
        interface = None
        if gateway:
            route_output = _run_command(f"ip route get {gateway}")
            if route_output:
                match = re.search(r"dev\s+(\w+)", route_output)
                if match:
                    interface = match.group(1)

        if not interface:
            return None

        # Find the IPv4 address and netmask for that interface
        for line in output.splitlines():
            if interface in line and "inet " in line:
                parts = line.strip().split()
                ip_cidr = parts[1]
                ip, cidr = ip_cidr.split('/')
                netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{cidr}", strict=False).netmask)
                return ip, netmask
    except Exception as e:
        logging.error(f"Failed to parse 'ip addr' output: {e}")
    return None

def _parse_ifconfig_output(output: str) -> Optional[Tuple[str, str]]:
    """Parses the output of 'ifconfig' to find the primary IP and netmask."""
    try:
        # A simple regex to find IP and netmask, avoiding loopback
        matches = re.finditer(
            r"(\w+):\s+flags=.*?\n\s+inet\s+((?:\d{1,3}\.){3}\d{1,3}).*?netmask\s+((?:\d{1,3}\.){3}\d{1,3})",
            output,
            re.DOTALL
        )
        for match in matches:
            iface, ip, netmask = match.groups()
            if not iface.startswith("lo"):
                return ip, netmask
    except Exception as e:
        logging.error(f"Failed to parse 'ifconfig' output: {e}")
    return None

def _get_network_info_linux() -> Dict[str, Optional[str]]:
    """
    Linux-specific implementation to get network info using command-line tools.
    """
    gateway = get_default_gateway()
    primary_ipv4, subnet_mask = None, None

    # Try 'ip addr' first
    ip_addr_output = _run_command("ip addr")
    if ip_addr_output and gateway:
        result = _parse_ip_addr_output(ip_addr_output, gateway)
        if result:
            primary_ipv4, subnet_mask = result
            logging.info("Network info retrieved using 'ip addr'.")

    # Fallback to 'ifconfig'
    if not primary_ipv4:
        ifconfig_output = _run_command("ifconfig")
        if ifconfig_output:
            result = _parse_ifconfig_output(ifconfig_output)
            if result:
                primary_ipv4, subnet_mask = result
                logging.info("Network info retrieved using 'ifconfig'.")

    return {
        "primary_ipv4": primary_ipv4,
        "primary_ipv6": None,  # Simplified for now
        "subnet_mask": subnet_mask,
        "gateway": gateway,
    }

def get_network_info() -> Dict[str, Optional[str]]:
    """
    Returns basic network info with fallbacks for reliability.
    Caches the result to avoid repeated lookups.
    """
    global _network_info_cache
    if _network_info_cache is not None:
        return _network_info_cache

    info: Dict[str, Optional[str]] = {
        "primary_ipv4": None,
        "primary_ipv6": None,
        "subnet_mask": None,
        "gateway": None,
    }

    gateway = get_default_gateway()
    info["gateway"] = gateway

    try:
        # Primary method: psutil
        if gateway:
            addrs = psutil.net_if_addrs()
            for if_name, if_addrs in addrs.items():
                # Find the interface that contains the gateway
                if any(addr.family == socket.AF_INET and ipaddress.ip_address(gateway) in ipaddress.ip_network(f"{addr.address}/{addr.netmask}", strict=False) for addr in if_addrs if addr.family == socket.AF_INET and addr.netmask):
                    # Now get all IPs for that interface
                    for addr in if_addrs:
                        if addr.family == socket.AF_INET:
                            info["primary_ipv4"] = addr.address
                            info["subnet_mask"] = addr.netmask
                        elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80::"):
                            info["primary_ipv6"] = addr.address
                    
                    if info["primary_ipv4"]:
                        logging.info(f"Network info for interface '{if_name}' retrieved using psutil.")
                        _network_info_cache = info
                        return info
    except Exception as e:
        logging.warning(f"Could not retrieve network info using psutil: {e}. Trying fallbacks.")

    # Fallback for Linux if psutil fails to find an IP
    if psutil.LINUX and not info["primary_ipv4"]:
        logging.info("psutil failed to find network info. Attempting Linux command-line fallback.")
        linux_info = _get_network_info_linux()
        if linux_info["primary_ipv4"]:
            _network_info_cache = linux_info
            return linux_info

    if not info["primary_ipv4"]:
        logging.error("All methods to retrieve network information failed.")

    _network_info_cache = info
    return info

# To reset cache for testing or re-detection
def clear_network_info_cache():
    global _network_info_cache
    _network_info_cache = None
