"""
Handles OS-specific routing table and gateway lookups using the 'netifaces' library.
"""
import logging
from typing import Optional
import netifaces

def get_default_gateway() -> Optional[str]:
    """
    Returns the default gateway IP by querying netifaces.
    It prefers IPv4 but will return an IPv6 gateway if it's the only one found.
    """
    try:
        gateways = netifaces.gateways()
        if 'default' in gateways and netifaces.AF_INET in gateways['default']:
            return gateways['default'][netifaces.AF_INET][0]
        elif 'default' in gateways and netifaces.AF_INET6 in gateways['default']:
            logging.warning("Could not find IPv4 default gateway, falling back to IPv6.")
            return gateways['default'][netifaces.AF_INET6][0]
    except Exception as e:
        logging.error(f"Could not determine default gateway using netifaces: {e}")
    
    logging.error("All methods to find the default gateway failed.")
    return None
