# TechRoute

**TechRoute** is a simple cross-platform GUI tool for network administrators and IT technicians. It continuously pings a list of printers (or any network device), checks for open web service ports, and automatically launches their web UI in a dedicated, security-relaxed browser instance for easy access.

## Features

* **Continuous Monitoring**: Pings multiple IP addresses simultaneously at a configurable interval and displays their online/offline status in real-time.
* **Latency Display**: Shows the average ping latency for online devices.
* **Port Checking**: Scans for common TCP ports to confirm service availability including 80 & 443 (HTTP/HTTPS), 161 & 162 (SNMP).
* **UDP Service Discovery**: Modular checkers for SLP (427), mDNS (5353), WS-Discovery (3702), and SNMP (161) let you probe for UDP-based services and device presence.
* **Auto Web UI Launch**: Automatically opens the web interface of a printer as soon as it comes online.
* **Smart Browser Detection**: Finds Chrome or Edge first to use command-line flags that bypass SSL certificate errors. Falls back to the system's default browser if needed.
* **Fully Configurable**: All settings can be changed in a user-friendly `config.yaml` file.

---

## ⚠️ Security Warning

This application is designed to launch a web browser with key security features **DISABLED** (e.g., `--ignore-certificate-errors`). This is necessary to streamline access to printer web panels that use self-signed SSL certificates.

**DO NOT** use the browser windows opened by this tool for any general web browsing. They are not secure.

---

## Installation & Usage


This tool requires Python 3 and the following libraries:

- `PyYAML`
- `python-nmap`
- `zeroconf` (for mDNS/Bonjour UDP checks)
- `pysnmp` (for SNMP UDP checks)

1. **Clone or Download**: Get the project files onto your local machine.
2. **Navigate to Directory**: Open a terminal or command prompt and `cd` into the `TechRoute` directory.
3. **Install Dependencies**:


    ```bash
    pip install -r requirements.txt
    ```

4. **Run the application**:

    ```bash
    python -m techroute
    ```

5. **Configure (First Run)**: The first time you run the app, it will create a `config.yaml` file in the same directory. You can open this file in a text editor to change settings.
6. **Enter IPs or Hostnames**: In the application window, enter one IP or hostname per line.
    * To use default ports: `192.168.1.50`, `printer.local`, or `fe80::1`
    * To specify custom ports: `192.168.1.51:80,443,8000` or `[fe80::1]:80,443`
7. **Start Pinging**: Click the "Start Pinging" button or use the `Ctrl+Enter` shortcut.

---

## Configuration

You can customize the application's behavior by editing the **`config.yaml`** file that is created on the first run.

* **`browser_preferences`**: Change the order of preferred browsers or add a new one.
* **`ping_interval_seconds`**: Adjust how often the application pings the targets.
* **`default_ports_to_check`**: Modify the list of TCP ports that are checked by default.

---

## Project Structure

The project is organized into several files to separate concerns:

```plaintext
TechRoute/
├── techroute/
│   ├── __main__.py         # Main script entry point
│   ├── app.py              # Contains the Tkinter GUI class
│   ├── configuration.py    # Manages loading config.yaml
│   └── network.py          # Network logic (ping, port scan, etc.)
│   └── checkers/           # Modular UDP service checkers (SLP, mDNS, WS-Discovery, SNMP)
│       ├── base.py         # BaseChecker protocol, CheckResult, and UDP helper
│       ├── slp.py          # SLPChecker: Service Location Protocol (UDP/427)
│       ├── mdns.py         # MDNSChecker: mDNS/Bonjour (UDP/5353) using zeroconf
│       ├── wsdiscovery.py  # WSDiscoveryChecker: WS-Discovery (UDP/3702)
│       ├── snmp_checker.py # SNMPChecker: SNMP sysDescr.0 GET (UDP/161) using pysnmp
│       └── __init__.py     # Exports all checkers for easy import
├── config.yaml             # User-editable settings (created on first run)
├── requirements.txt        # Project dependencies
└── README.md               # This documentation file
```

---

## UDP Service Checkers (Extending/Using)

The `techroute/checkers` package provides a modular way to check for UDP-based services and device presence. Each checker exposes a simple API:

```python
from techroute.checkers import SLPChecker, MDNSChecker, WSDiscoveryChecker, SNMPChecker

result = SLPChecker().check("192.168.1.100")
print(result.available, result.info, result.error)

result = MDNSChecker().check("192.168.1.100")
print(result.available)

result = WSDiscoveryChecker().check("192.168.1.100")
print(result.available)

result = SNMPChecker().check("192.168.1.100")
print(result.available, result.info)
```

- All checkers return a `CheckResult` dataclass: `.available` (bool), `.info` (dict or None), `.error` (str or None).
- mDNS and SNMP checkers require `zeroconf` and `pysnmp` respectively; if not installed, `.error` will explain.
- These checkers are decoupled from the GUI and can be used in scripts, tests, or integrated into the main app.

---
