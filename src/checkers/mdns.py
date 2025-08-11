from __future__ import annotations

from typing import Optional

from .base import BaseChecker, CheckResult

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf  # type: ignore
except ImportError:
    ServiceBrowser = None  # type: ignore
    Zeroconf = None  # type: ignore

    class ServiceListener:  # type: ignore
        """Stub for ServiceListener."""

        def __init__(self) -> None:
            pass


class _AnyServiceListener(ServiceListener):
    def __init__(self) -> None:
        super().__init__()
        self.seen = False

    def add_service(self, zc: object, stype: str, name: str) -> None:  # pragma: no cover - callbacks
        self.seen = True

    def update_service(self, zc: object, stype: str, name: str) -> None:  # pragma: no cover - callbacks
        self.seen = True

    def remove_service(self, zc: object, stype: str, name: str) -> None:  # pragma: no cover - callbacks
        pass


class MDNSChecker(BaseChecker):
    """mDNS/Bonjour availability via zeroconf (UDP/5353)."""

    name = "mDNS"
    port = 5353

    def check(self, host: str, timeout: float = 1.5) -> CheckResult:
        if Zeroconf is None or ServiceBrowser is None:
            return CheckResult(False, error="zeroconf not installed")

        # Note: zeroconf primarily discovers on the local link. For a remote host,
        # this acts as a local availability probe rather than directed query.
        try:
            zc = Zeroconf()
            listener = _AnyServiceListener()
            # Browse a common service type; _services._dns-sd._udp.local. lists types
            ServiceBrowser(
                zc,
                "_services._dns-sd._udp.local.",
                handlers=[listener.add_service, listener.update_service],
            )  # noqa: F841
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
