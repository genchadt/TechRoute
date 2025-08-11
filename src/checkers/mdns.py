from __future__ import annotations

from typing import Optional, Iterable, Any, cast
import platform
import struct
import socket

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


class _AnyServiceListener(ServiceListener):
    def __init__(self) -> None:
        super().__init__()
        self.seen = False

    def add_service(self, *args, **kwargs) -> None:  # pragma: no cover - callbacks
        # Accept both positional and keyword styles from zeroconf
        self.seen = True

    def update_service(self, *args, **kwargs) -> None:  # pragma: no cover - callbacks
        self.seen = True

    def remove_service(self, *args, **kwargs) -> None:  # pragma: no cover - callbacks
        pass


class MDNSChecker(BaseChecker):
    """mDNS/Bonjour availability via zeroconf (UDP/5353)."""

    name = "mDNS"
    port = 5353

    def check(self, host: str, timeout: float = 1.5) -> CheckResult:
        if Zeroconf is None or ServiceBrowser is None:
            return CheckResult(False, error="zeroconf not installed")
        # Help static type checkers: from here on, these are available
        assert Zeroconf is not None and ServiceBrowser is not None
        # Note: zeroconf primarily discovers on the local link. For a remote host,
        # this acts as a local availability probe rather than a directed query.
        # On some Linux systems IPv6-only stacks or interface selection can prevent
        # discovery; prefer IPv4 which is most widely permitted by firewalls.
        sys_is_linux = platform.system().lower() == "linux"
        effective_timeout = max(timeout, 2.0) if sys_is_linux else timeout

        # Prefer IPv4 browse first, then try IPv6 on Linux where many stacks run v6-only mDNS
        modes = ["v4"]
        if sys_is_linux:
            modes.append("v6")
        for ip_mode in modes:
            try:
                zc_kwargs = {}
                if IPVersion is not None:
                    try:
                        if ip_mode == "v4":
                            zc_kwargs["ip_version"] = IPVersion.V4Only  # type: ignore[attr-defined]
                        else:
                            zc_kwargs["ip_version"] = IPVersion.V6Only  # type: ignore[attr-defined]
                    except Exception:
                        pass
                ZC = cast(Any, Zeroconf)
                zc = ZC(**zc_kwargs)
                try:
                    listener = _AnyServiceListener()
                    SB = cast(Any, ServiceBrowser)
                    SB(
                        zc,
                        "_services._dns-sd._udp.local.",
                        handlers=[listener.add_service, listener.update_service],
                    )  # noqa: F841
                    import time
                    end = time.time() + effective_timeout
                    while time.time() < end:
                        if listener.seen:
                            return CheckResult(True)
                        time.sleep(0.05)
                finally:
                    try:
                        zc.close()
                    except Exception:
                        pass
            except Exception:
                # If IPv4 browse fails, try IPv6 (on Linux); otherwise fall through
                pass

        # Fallback: craft QU PTR query to multicast and expect a unicast reply
        # Try IPv4 first, then IPv6 (probing common interfaces) on Linux.
        try:
            from .base import udp_send_receive

            def _encode_qname(name: str) -> bytes:
                parts = [p for p in name.strip(".").split(".") if p]
                out = bytearray()
                for p in parts:
                    b = p.encode("utf-8")
                    out.append(len(b))
                    out.extend(b)
                out.append(0)
                return bytes(out)

            # DNS header: id=0, flags=0x0000 (query), QDCOUNT=1
            header = struct.pack(
                ">HHHHHH",
                0,
                0x0000,
                1,  # QD
                0,  # AN
                0,  # NS
                0,  # AR
            )
            qname = _encode_qname("_services._dns-sd._udp.local.")
            qtype = 12  # PTR
            qclass = 0x8001  # IN with QU bit set to request unicast reply
            question = qname + struct.pack(">HH", qtype, qclass)
            payload = header + question

            # IPv4 multicast first
            res_v4 = udp_send_receive("224.0.0.251", self.port, payload, timeout=effective_timeout, family_hint=socket.AF_INET)
            if res_v4.available:
                return CheckResult(True, info=res_v4.info)

            # On Linux, also try IPv6 across available interfaces using scoped ff02::fb%iface
            if sys_is_linux:
                try:
                    ifaces: Iterable[tuple[int, str]] = socket.if_nameindex()
                except OSError:
                    ifaces = []
                for idx, name in ifaces:
                    addr = f"ff02::fb%{name}"
                    res_v6 = udp_send_receive(addr, self.port, payload, timeout=effective_timeout, family_hint=socket.AF_INET6)
                    if res_v6.available:
                        return CheckResult(True, info=res_v6.info)
            return CheckResult(False)
        except Exception as e:  # pragma: no cover - conservative fallback
            return CheckResult(False, error=str(e))
