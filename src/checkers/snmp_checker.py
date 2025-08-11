from __future__ import annotations

from typing import Optional

from .base import BaseChecker, CheckResult
import importlib


class SNMPChecker:
    """SNMP availability check using pysnmp (UDP/161).

    Performs a quick GET for sysDescr.0 on public community by default.
    """

    name = "SNMP"
    port = 161

    def __init__(self, community: str = "public"):
        self.community = community

    def check(self, host: str, timeout: float = 1.0) -> CheckResult:
        try:
            hlapi = importlib.import_module("pysnmp.hlapi")
            SnmpEngine = getattr(hlapi, "SnmpEngine")
            CommunityData = getattr(hlapi, "CommunityData")
            UdpTransportTarget = getattr(hlapi, "UdpTransportTarget")
            ContextData = getattr(hlapi, "ContextData")
            ObjectType = getattr(hlapi, "ObjectType")
            ObjectIdentity = getattr(hlapi, "ObjectIdentity")
            getCmd = getattr(hlapi, "getCmd")
        except Exception:
            return CheckResult(False, error="pysnmp not installed")
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community, mpModel=1),  # v2c
                UdpTransportTarget((host, self.port), timeout=timeout, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")),  # sysDescr.0
            )
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            if errorIndication:
                return CheckResult(False, error=str(errorIndication))
            if errorStatus:
                return CheckResult(False, error=f"SNMP error: {errorStatus.prettyPrint()}")
            # If we got here, target responded to SNMP
            info = {"oid": "1.3.6.1.2.1.1.1.0", "value": str(varBinds[0][1]) if varBinds else ""}
            return CheckResult(True, info=info)
        except StopIteration:
            return CheckResult(False)
        except Exception as e:
            return CheckResult(False, error=str(e))
