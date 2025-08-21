from __future__ import annotations

from typing import Optional, Iterable, Any, cast, Dict
import platform
import struct
import socket
import threading
import time
import logging

from .base import BaseChecker, CheckResult

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf  # type: ignore
    try:
        # Optional extras; not all versions expose these
        from zeroconf import IPVersion  # type: ignore
    except Exception:  # pragma: no cover - optional
        IPVersion = None  # type: ignore
except ImportError:
    ServiceBrowser = None  # type: ignore
    Zeroconf = None  # type: ignore
    IPVersion = None  # type: ignore

    class ServiceListener:  # type: ignore
        """Stub for ServiceListener."""

        def __init__(self) -> None:
            pass

# Optional: use Avahi via D-Bus when available (Linux)
try:
    import dbus  # type: ignore
except Exception:
    dbus = None  # type: ignore


class _AnyServiceListener(ServiceListener):
    def __init__(self, event: threading.Event) -> None:
        super().__init__()
        self._event = event

    def add_service(self, *args, **kwargs) -> None:  # pragma: no cover - callbacks
        self._event.set()

    def update_service(self, *args, **kwargs) -> None:  # pragma: no cover - callbacks
        self._event.set()

    def remove_service(self, *args, **kwargs) -> None:  # pragma: no cover - callbacks
        pass


class _MDNSMonitor:
    """Persistent, shared Zeroconf browser that records recent mDNS activity.

    We treat *any* service add/update callback on the meta-service browser
    as proof that mDNS traffic is flowing on the link. This avoids creating
    a Zeroconf instance for every availability probe and dramatically
    reduces flapping caused by narrow observation windows.
    """

    _FRESHNESS_WINDOW = 60.0  # Seconds since last event to consider 'fresh'
    _STALE_ACTIVE_PROBE_INTERVAL = 120.0  # How often (s) we allow an active probe when stale
    _GRACE_AFTER_SUCCESS = 300.0  # Still report available (optimistic) within this after last success unless explicit failures

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_event: float = 0.0
        self._last_success_return: float = 0.0  # last time we actually returned available
        self._last_active_probe: float = 0.0
        self._zc: Any = None
        self._started = False
        self._active_probe_failures: int = 0
        self._logger = logging.getLogger("techroute.mdns")
        self._logger.addHandler(logging.NullHandler())

    def _ensure_started(self) -> None:
        if self._started:
            return
        if Zeroconf is None or ServiceBrowser is None:
            return
        try:
            ZC = cast(Any, Zeroconf)
            self._zc = ZC()  # Single shared instance
            listener = self._Listener(self)
            SB = cast(Any, ServiceBrowser)
            SB(self._zc, "_services._dns-sd._udp.local.", listener)
            self._started = True
            self._logger.debug("Started persistent Zeroconf mDNS monitor")
        except Exception as e:  # pragma: no cover - startup edge
            self._zc = None
            self._logger.debug("Failed to start Zeroconf monitor: %s", e)

    class _Listener(ServiceListener):  # type: ignore[misc]
        def __init__(self, outer: '_MDNSMonitor') -> None:  # noqa: F821
            super().__init__()
            self._outer = outer

        def add_service(self, *args, **kwargs) -> None:  # pragma: no cover - callback
            self._mark()
        def update_service(self, *args, **kwargs) -> None:  # pragma: no cover - callback
            self._mark()
        def _mark(self) -> None:
            with self._outer._lock:
                self._outer._last_event = time.monotonic()
                self._outer._active_probe_failures = 0

    # Active probe (unicast PTR query) only when stale, to gently re-confirm
    def _active_probe(self, timeout: float) -> bool:
        now = time.monotonic()
        if (now - self._last_active_probe) < self._STALE_ACTIVE_PROBE_INTERVAL:
            return False
        self._last_active_probe = now
        try:
            return self._send_qu_ptr(timeout)
        except Exception as e:  # pragma: no cover - diagnostics
            self._logger.debug("Active mDNS probe error: %s", e)
            return False

    def _send_qu_ptr(self, timeout: float) -> bool:
        from .base import udp_send_receive

        def _enc_qname(name: str) -> bytes:
            out = bytearray()
            for part in [p for p in name.strip('.').split('.') if p]:
                b = part.encode('utf-8')
                out.append(len(b))
                out.extend(b)
            out.append(0)
            return bytes(out)

        header = struct.pack(">HHHHHH", 0, 0x0000, 1, 0, 0, 0)
        question = _enc_qname("_services._dns-sd._udp.local.") + struct.pack(">HH", 12, 0x8001)
        payload = header + question
        # IPv4 first
        res_v4 = udp_send_receive("224.0.0.251", 5353, payload, timeout=timeout, family=socket.AF_INET)
        if res_v4.available:
            with self._lock:
                self._last_event = time.monotonic()
            return True
        # IPv6 (best effort)
        if platform.system().lower() == 'linux':
            try:
                ifaces: Iterable[tuple[int, str]] = socket.if_nameindex()
            except OSError:
                ifaces = []
            for _, name in ifaces:
                addr = f"ff02::fb%{name}"
                res_v6 = udp_send_receive(addr, 5353, payload, timeout=timeout, family=socket.AF_INET6)
                if res_v6.available:
                    with self._lock:
                        self._last_event = time.monotonic()
                    return True
        return False

    def availability_snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            last_event = self._last_event
            last_success = self._last_success_return
        age = now - last_event if last_event else float('inf')
        return {
            "last_event_age_sec": age,
            "had_success": last_success > 0.0,
        }

    def is_available(self, timeout: float) -> CheckResult:
        self._ensure_started()
        now = time.monotonic()
        with self._lock:
            last_event = self._last_event
            last_success = self._last_success_return

        # Fast path: fresh passive event
        if last_event and (now - last_event) <= self._FRESHNESS_WINDOW:
            with self._lock:
                self._last_success_return = now
            return CheckResult(True, info={"method": "passive", "age": now - last_event})

        # If we had past success, remain optimistic within grace while we try an active probe occasionally
        optimistic_window = (last_success > 0.0) and ((now - last_success) <= self._GRACE_AFTER_SUCCESS)

        did_probe = False
        if self._active_probe(timeout):
            did_probe = True
            with self._lock:
                self._last_success_return = now
            return CheckResult(True, info={"method": "active-probe", "age": now - self._last_event})

        if optimistic_window:
            # Still report available, but include stale flag
            return CheckResult(True, info={"method": "stale-passive", "stale": True, "age": (now - last_event) if last_event else None})

        # Linux: try Avahi as a last resort before declaring failure
        avahi_res = MDNSChecker._avahi_dbus_check_static()
        if avahi_res is not None and avahi_res.available:
            with self._lock:
                self._last_success_return = now
                if self._last_event == 0.0:
                    self._last_event = now  # Seed
            return avahi_res

        return CheckResult(False, info={"method": "none", "probe_attempted": did_probe})


_monitor: Optional[_MDNSMonitor] = None


def _get_monitor() -> _MDNSMonitor:
    global _monitor
    if _monitor is None:
        _monitor = _MDNSMonitor()
    return _monitor


class MDNSChecker(BaseChecker):
    """mDNS/Bonjour availability via persistent monitoring + light active probes.

    The `host` parameter is ignored (mDNS is link-scope); we retain it to satisfy
    the BaseChecker protocol.
    """

    name = "mDNS"
    port = 5353

    @staticmethod
    def _avahi_dbus_check_static() -> CheckResult | None:
        if dbus is None or platform.system().lower() != "linux":
            return None
        try:
            bus = dbus.SystemBus()  # type: ignore[assignment]
            server_obj = bus.get_object("org.freedesktop.Avahi", "/")  # type: ignore[attr-defined]
            server = dbus.Interface(server_obj, "org.freedesktop.Avahi.Server")  # type: ignore[attr-defined]
            _ = server.GetVersionString()  # type: ignore[attr-defined]
            state = int(server.GetState())  # type: ignore[attr-defined]
            return CheckResult(True, info={"method": "avahi-dbus", "state": state})
        except Exception as e:  # pragma: no cover - system integration
            return CheckResult(False, error=f"Avahi D-Bus: {e}")

    # Backwards-compatible instance method for any older references
    def _avahi_dbus_check(self) -> CheckResult | None:  # pragma: no cover - delegate
        return self._avahi_dbus_check_static()

    def check(self, host: str, timeout: float = 1.5) -> CheckResult:  # noqa: D401
        # timeout influences active probe upper bound; we internally cap / extend as needed
        bounded = max(0.5, min(timeout, 5.0))
        mon = _get_monitor()
        return mon.is_available(timeout=bounded)

