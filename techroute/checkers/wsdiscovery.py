from __future__ import annotations

from .base import BaseChecker, CheckResult, udp_send_receive


class WSDiscoveryChecker:
    """WS-Discovery probe (UDP/3702) using a minimal Probe packet.

    This broadcasts a Probe (multicast address is typically 239.255.255.250 or FF02::C).
    For simplicity and firewall-friendliness, send unicast to host but allow multicast bind.
    """

    name = "WS-Discovery"
    port = 3702

    def check(self, host: str, timeout: float = 1.0) -> CheckResult:
        # Minimal SOAP-over-UDP Probe request, not fully spec-compliant but widely answered
        # XML body kept intentionally short; many devices reply with ProbeMatches.
        xml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<e:Envelope xmlns:e='http://www.w3.org/2003/05/soap-envelope'"
            " xmlns:w='http://schemas.xmlsoap.org/ws/2004/08/addressing'"
            " xmlns:d='http://schemas.xmlsoap.org/ws/2005/04/discovery'>"
            "<e:Header>"
            "<w:MessageID>uuid:00000000-0000-0000-0000-000000000000</w:MessageID>"
            "<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>"
            "<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>"
            "</e:Header>"
            "<e:Body>"
            "<d:Probe/>"
            "</e:Body>"
            "</e:Envelope>"
        ).encode("utf-8")
        # Bind to IPv4 multicast group for potential responses
        return udp_send_receive(host, self.port, xml, timeout=timeout, bind_multicast="239.255.255.250")
