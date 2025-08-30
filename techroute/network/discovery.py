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
from ..routing import _score_interface

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cache for network information
_network_info_cache: Optional[Dict[str, Optional[str]]] = None

def get_network_info() -> Dict[str, Optional[str]]:
    """
    Returns basic network info using psutil.
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

    try:
        # Get the default gateway
        gateway = get_default_gateway()
        if gateway:
            info["gateway"] = gateway
        else:
            logging.error("Could not determine default gateway.")

        # Find the interface associated with the default gateway or find the best one
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        
        best_iface = None
        if gateway:
            for iface, iface_addrs in addrs.items():
                if iface in stats and stats[iface].isup and not iface.startswith('lo'):
                    for addr in iface_addrs:
                        if addr.family == socket.AF_INET and addr.netmask:
                            try:
                                network = ipaddress.ip_network(f"{addr.address}/{addr.netmask}", strict=False)
                                if ipaddress.ip_address(gateway) in network:
                                    best_iface = iface
                                    break
                            except ValueError:
                                continue
                if best_iface:
                    break
        
        if best_iface:
            logging.info(f"Found best interface '{best_iface}' for gateway {gateway} using psutil.")
            for addr in addrs[best_iface]:
                if addr.family == socket.AF_INET:
                    info["primary_ipv4"] = addr.address
                    info["subnet_mask"] = addr.netmask
                elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80::"):
                    info["primary_ipv6"] = addr.address
        else:
            logging.warning("Could not find a gateway-associated interface. Scoring all interfaces.")
            scored_ifaces = []
            for iface, iface_addrs in addrs.items():
                if iface in stats and stats[iface].isup and not iface.startswith('lo'):
                    for addr in iface_addrs:
                        if addr.family == socket.AF_INET:
                            score = _score_interface(iface)
                            scored_ifaces.append((score, iface, iface_addrs))
                            break
            
            if scored_ifaces:
                scored_ifaces.sort(key=lambda x: x[0], reverse=True)
                best_iface_fallback, best_addrs_fallback = scored_ifaces[0][1], scored_ifaces[0][2]
                logging.info(f"Using best-scored fallback interface '{best_iface_fallback}' as primary.")
                
                for addr in best_addrs_fallback:
                    if addr.family == socket.AF_INET:
                        info["primary_ipv4"] = addr.address
                        info["subnet_mask"] = addr.netmask
                    elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80::"):
                        info["primary_ipv6"] = addr.address

    except Exception as e:
        logging.error(f"An error occurred while retrieving network info with psutil: {e}")

    if not info["primary_ipv4"]:
        logging.error("Failed to retrieve primary IPv4 address using any method.")

    _network_info_cache = info
    return info

# To reset cache for testing or re-detection
def clear_network_info_cache():
    global _network_info_cache
    _network_info_cache = None
