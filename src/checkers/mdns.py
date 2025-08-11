from __future__ import annotations

from typing import Optional

from .base import BaseChecker, CheckResult


class _AnyServiceListener:
    def __init__(self):
        self.seen = False

    def add_service(self, zc, stype, name):  # pragma: no cover - callbacks
        self.seen = True

    def update_service(self, zc, stype, name):  # pragma: no cover - callbacks
        self.seen = True

    def remove_service(self, zc, stype, name):  # pragma: no cover - callbacks
        pass


class MDNSChecker:
    """mDNS/Bonjour availability via zeroconf (UDP/5353)."""

    name = "mDNS"
    port = 5353

    def check(self, host: str, timeout: float = 1.5) -> CheckResult:
        try:
            from zeroconf import Zeroconf, ServiceBrowser  # type: ignore
        except Exception:
            return CheckResult(False, error="zeroconf not installed")

        # Note: zeroconf primarily discovers on the local link. For a remote host,
        # this acts as a local availability probe rather than directed query.
        try:
            zc = Zeroconf()
            listener = _AnyServiceListener()
            # Browse a common service type; _services._dns-sd._udp.local. lists types
            ServiceBrowser(zc, "_services._dns-sd._udp.local.", listener)  # noqa: F841
            # Wait briefly for any service
            import time
            end = time.time() + timeout
            while time.time() < end:
                if listener.seen:
                    break
                time.sleep(0.05)
            zc.close()
            return CheckResult(listener.seen)
        except Exception as e:
            return CheckResult(False, error=str(e))
