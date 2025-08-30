"""
Handles OS-specific routing table and gateway lookups.
Primary method uses 'netifaces', with a fallback to system commands for robustness.
"""
import logging
import platform
import re
import subprocess
from collections import namedtuple
from typing import Optional, List, Tuple
import ipaddress

import netifaces
import psutil


def _get_interface_name_for_gateway(gateway_ip: str) -> Optional[str]:
    """Finds the interface name associated with a given gateway IP."""
    try:
        gateway = ipaddress.ip_address(gateway_ip)
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family in (2, 23) and addr.netmask:  # AF_INET or AF_INET6
                    try:
                        network = ipaddress.ip_network(f"{addr.address}/{addr.netmask}", strict=False)
                        if gateway in network:
                            return iface
                    except ValueError:
                        continue
    except (ValueError, KeyError):
        pass
    return None


def _score_interface(iface_name: str) -> int:
    """Scores an interface based on its likelihood of being the 'real' physical one."""
    name = iface_name.lower()
    score = 100
    # Heavily penalize known virtual/VPN interfaces
    virtual_keywords = ['virtual', 'vmware', 'vbox', 'tailscale', 'vpn', 'loopback', 'teredo']
    for keyword in virtual_keywords:
        if keyword in name:
            score -= 50
    # Boost common physical interface names
    physical_keywords = ['ethernet', 'wi-fi', 'wlan', 'eth0', 'en0']
    for keyword in physical_keywords:
        if keyword in name:
            score += 20
    # Check if it's up
    try:
        stats = psutil.net_if_stats()
        # Create a dummy stats object for interfaces not returned by psutil.
        SNICStats = namedtuple('SNICStats', ['isup'])
        snicstats_default = SNICStats(isup=False)
        if stats.get(iface_name, snicstats_default).isup:
            score += 10
        else:
            score -= 100  # An interface that is down is useless
    except KeyError:
        return -1  # Interface disappeared
    return score


def _get_gateway_from_system_command() -> Optional[str]:
    """
    Parses system routing tables to find the best default gateway.
    It prefers gateways on interfaces that appear to be physical.
    """
    gateways: List[Tuple[str, str]] = [] # (gateway_ip, interface_name)
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(["route", "print", "-4"], capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if line.strip().startswith("0.0.0.0"):
                    parts = line.split()
                    if len(parts) >= 3:
                        gw_ip = parts[2]
                        iface = _get_interface_name_for_gateway(gw_ip)
                        if iface:
                            gateways.append((gw_ip, iface))
        elif system in ["Linux", "Darwin"]:
            result = subprocess.run(["ip", "route"], capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if line.strip().startswith("default"):
                    parts = line.split()
                    if len(parts) >= 3:
                        gw_ip = parts[2]
                        iface = parts[4] if len(parts) >= 5 else _get_interface_name_for_gateway(gw_ip)
                        if iface:
                            gateways.append((gw_ip, iface))
    except (FileNotFoundError, subprocess.CalledProcessError, IndexError) as e:
        logging.error(f"Failed to get gateway list from system command: {e}")
        return None

    logging.debug(f"Found potential gateways: {gateways}")
    if not gateways:
        logging.warning("System command returned no default gateways.")
        return None

    # Score and sort the gateways
    scored_gateways = sorted(
        gateways,
        key=lambda gw: _score_interface(gw[1]),
        reverse=True
    )
    
    logging.info(f"Scored gateways (IP, Interface, Score): {[(gw[0], gw[1], _score_interface(gw[1])) for gw in scored_gateways]}")
    best_gateway = scored_gateways[0][0]
    logging.info(f"Selected best gateway: {best_gateway}")
    return best_gateway


def get_default_gateway() -> Optional[str]:
    """
    Returns the default gateway IP.
    First, it tries netifaces for a fast lookup. If that fails, it falls back
    to parsing system routing tables, which is more robust.
    It prefers IPv4 but will return an IPv6 gateway if it's the only one found by netifaces.
    """
    # --- Primary Method: netifaces ---
    try:
        gateways = netifaces.gateways()
        logging.debug(f"Raw gateways from netifaces: {gateways}")
        if 'default' in gateways and netifaces.AF_INET in gateways['default']:
            gateway = gateways['default'][netifaces.AF_INET][0]
            logging.info(f"Found default gateway {gateway} via netifaces.")
            return gateway
        # Fallback to IPv6 if only that is available from netifaces
        if 'default' in gateways and netifaces.AF_INET6 in gateways['default']:
            gateway = gateways['default'][netifaces.AF_INET6][0]
            logging.warning(f"Found IPv6 default gateway {gateway} via netifaces (no IPv4).")
            return gateway
    except Exception as e:
        logging.warning(f"Could not determine default gateway using netifaces: {e}. Trying fallback.")

    # --- Fallback Method: System Command ---
    logging.info("Falling back to system command to find default gateway.")
    gateway = _get_gateway_from_system_command()
    if gateway:
        logging.info(f"Found default gateway {gateway} via system command.")
        return gateway

    logging.error("All methods to find the default gateway failed.")
    return None
