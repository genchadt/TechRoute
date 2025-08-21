from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Protocol, List
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class CheckResult:
    """
    Unified result for a service check.
    - available: whether the probe succeeded
    - info: optional dictionary with service-specific details
    - error: optional error string on failure
    - rtt: round-trip time in seconds, if successful
    """
    available: bool
    info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    rtt: Optional[float] = None

class BaseChecker(Protocol):
    """Protocol for service checkers."""
    name: str
    port: int

    def check(self, host: str, timeout: float = 1.0) -> CheckResult:
        ...

def udp_send_receive(
    host: str,
    port: int,
    payload: bytes,
    *,
    timeout: float = 1.0,
    family: int = socket.AF_UNSPEC,
) -> CheckResult:
    """
    A more robust UDP send/receive helper that tries both IPv6 and IPv4.
    """
    last_error = "Unknown failure"
    # Try IPv6 first, then IPv4
    for fam in (socket.AF_INET6, socket.AF_INET):
        if family != socket.AF_UNSPEC and fam != family:
            continue
        try:
            with socket.socket(fam, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                start_time = time.monotonic()
                s.sendto(payload, (host, port))
                data, addr = s.recvfrom(4096)
                rtt = time.monotonic() - start_time
                return CheckResult(True, info={"from": addr, "bytes": len(data)}, rtt=rtt)
        except socket.timeout:
            last_error = "Timeout"
            continue
        except socket.gaierror as e:
            last_error = f"DNS error: {e}"
            break  # No point trying other families if DNS fails
        except OSError as e:
            last_error = f"Socket error: {e}"
            continue
    
    return CheckResult(False, error=last_error)

@dataclass
class CacheEntry:
    """An entry in the service check cache."""
    result: CheckResult
    timestamp: float

@dataclass
class ServiceCheckManager:
    """
    Manages parallel execution of service checks.
    """
    checkers: List[BaseChecker]
    cache: Dict[str, CacheEntry] = field(default_factory=dict)
    cache_ttl: float = 60.0  # Cache results for 60 seconds

    def _is_cache_valid(self, key: str) -> bool:
        """Checks if a cached entry is still valid."""
        if key not in self.cache:
            return False
        entry = self.cache[key]
        return (time.monotonic() - entry.timestamp) < self.cache_ttl

    def run_checks(self, host: str, timeout: float = 2.0) -> Dict[str, CheckResult]:
        """
        Runs all registered service checks against a host in parallel and returns
        results in a predictable order.
        """
        unordered_results = {}
        futures = {}
        
        with ThreadPoolExecutor(max_workers=len(self.checkers)) as executor:
            for checker in self.checkers:
                cache_key = f"{checker.name}:{host}"
                if self._is_cache_valid(cache_key):
                    unordered_results[checker.name] = self.cache[cache_key].result
                    continue

                future = executor.submit(checker.check, host, timeout)
                futures[future] = checker.name

            for future in as_completed(futures):
                checker_name = futures[future]
                try:
                    result = future.result()
                    unordered_results[checker_name] = result
                    # Update cache
                    cache_key = f"{checker_name}:{host}"
                    self.cache[cache_key] = CacheEntry(result=result, timestamp=time.monotonic())
                except Exception as e:
                    logging.error(f"Checker '{checker_name}' failed with exception: {e}")
                    unordered_results[checker_name] = CheckResult(False, error=str(e))
        
        # Return results in the order the checkers were defined
        return {checker.name: unordered_results.get(checker.name, CheckResult(False, error="Not run")) for checker in self.checkers}

    def clear_cache(self):
        """Clears the entire cache."""
        self.cache.clear()
