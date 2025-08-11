from __future__ import annotations

from .base import BaseChecker, CheckResult, udp_send_receive


class SLPChecker:
    """Basic Service Location Protocol check (UDP/427).

    Sends a minimal SrvRqst and waits for any reply.
    This is a very light availability probe, not a full SLP implementation.
    """

    name = "SLP"
    port = 427

    def check(self, host: str, timeout: float = 1.0) -> CheckResult:
        # Minimal SLPv2 UA SrvRqst (not fully spec-compliant; enough for availability)
        # Using a generic packet with empty service type to solicit DA/SA reply.
        # Format is simplified; many devices reply anyway.
        payload = bytes.fromhex(
            "0201"  # ver=2, function=SrvRqst
            "0000"  # length (ignored by many stacks in UDP)
            "0000"  # flags
            "00000000"  # ext offset
            "0000"  # xid
            "0000"  # langtag len
            # prlist len + prlist omitted (0)
            "0000"  # prlist len
            # prev responders omitted
            # service type len + empty
            "0000"
            # scope list len + empty
            "0000"
            # predicate len + empty
            "0000"
            # slp spi len + empty
            "0000"
        )
        return udp_send_receive(host, self.port, payload, timeout=timeout)
