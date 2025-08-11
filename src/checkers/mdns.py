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
        # Help static type checkers
        assert Zeroconf is not None and ServiceBrowser is not None

        sys_is_linux = platform.system().lower() == "linux"
        effective_timeout = max(timeout, 2.0) if sys_is_linux else timeout

        # Try zeroconf browse: IPv4 first, then IPv6 on Linux
        browse_modes = ["v4"] + (["v6"] if sys_is_linux else [])
        for mode in browse_modes:
            try:
                zc_kwargs: dict[str, Any] = {}
                if IPVersion is not None:
                    try:
                        zc_kwargs["ip_version"] = IPVersion.V4Only if mode == "v4" else IPVersion.V6Only  # type: ignore[attr-defined]
                    except Exception:
                        pass
                ZC = cast(Any, Zeroconf)
                zc = ZC(**zc_kwargs)
                try:
                    listener = _AnyServiceListener()
                    SB = cast(Any, ServiceBrowser)
                    SB(zc, "_services._dns-sd._udp.local.", handlers=[listener.add_service, listener.update_service])  # noqa: F841
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
                pass

        # Fallback A: QU PTR query asking for unicast reply
        try:
            from .base import udp_send_receive

            def _enc_qname(name: str) -> bytes:
                out = bytearray()
                for p in [p for p in name.strip(".").split(".") if p]:
                    b = p.encode("utf-8")
                    out.append(len(b))
                    out.extend(b)
                out.append(0)
                return bytes(out)

            header = struct.pack(">HHHHHH", 0, 0x0000, 1, 0, 0, 0)
            question = _enc_qname("_services._dns-sd._udp.local.") + struct.pack(">HH", 12, 0x8001)
            payload = header + question

            # IPv4
            res_v4 = udp_send_receive("224.0.0.251", self.port, payload, timeout=effective_timeout, family_hint=socket.AF_INET)
            if res_v4.available:
                return CheckResult(True, info=res_v4.info)

            # IPv6 scoped per interface (Linux)
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
        except Exception as e:
            return CheckResult(False, error=str(e))

        # Fallback B (Linux): join multicast and listen briefly
        if sys_is_linux:
            def _multicast_query() -> bytes:
                header = struct.pack(">HHHHHH", 0, 0x0000, 1, 0, 0, 0)
                name = "_services._dns-sd._udp.local."
                out = bytearray()
                for p in [p for p in name.strip(".").split(".") if p]:
                    b = p.encode("utf-8")
                    out.append(len(b))
                    out.extend(b)
                out.append(0)
                question = bytes(out) + struct.pack(">HH", 12, 0x0001)
                return header + question

            query = _multicast_query()

            # IPv4 listen
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s4:
                    s4.settimeout(effective_timeout)
                    try:
                        s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    except OSError:
                        pass
                    try:
                        s4.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT", 15), 1)
                    except OSError:
                        pass
                    try:
                        s4.bind(("0.0.0.0", self.port))
                        mreq = socket.inet_aton("224.0.0.251") + socket.inet_aton("0.0.0.0")
                        s4.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                        try:
                            s4.sendto(query, ("224.0.0.251", self.port))
                        except OSError:
                            pass
                        try:
                            data, addr = s4.recvfrom(2048)
                            if data:
                                return CheckResult(True, info={"from": addr, "bytes": len(data)})
                        except socket.timeout:
                            pass
                    except OSError:
                        pass
            except OSError:
                pass

            # IPv6 listen
            try:
                with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s6:
                    s6.settimeout(effective_timeout)
                    try:
                        s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    except OSError:
                        pass
                    try:
                        s6.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT", 15), 1)
                    except OSError:
                        pass
                    try:
                        s6.bind(("::", self.port))
                    except OSError:
                        s6 = None  # type: ignore
                    if s6 is not None:
                        try:
                            ifaces: Iterable[tuple[int, str]] = socket.if_nameindex()
                        except OSError:
                            ifaces = []
                        group = socket.inet_pton(socket.AF_INET6, "ff02::fb")
                        for idx, name in ifaces:
                            try:
                                mreq6 = group + struct.pack("@I", idx)
                                s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq6)
                            except OSError:
                                continue
                        for idx, name in ifaces:
                            try:
                                s6.sendto(query, ("ff02::fb", self.port, 0, idx))
                            except OSError:
                                continue
                        try:
                            data, addr = s6.recvfrom(4096)
                            if data:
                                return CheckResult(True, info={"from": addr, "bytes": len(data)})
                        except socket.timeout:
                            pass
            except OSError:
                pass

        return CheckResult(False)
