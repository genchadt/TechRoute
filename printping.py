import tkinter as tk
from tkinter import ttk, messagebox
import ipaddress
import subprocess
import webbrowser
import threading
import time
import platform
import shutil
import os
import queue
import socket
import re
from typing import Dict, Any, List, Optional, Tuple

# ! DO NOT USE BROWSER WINDOWS OPENED BY THIS SCRIPT FOR NORMAL BROWSING !
# !!! YOU HAVE BEEN WARNED !!!

# --- Browser Configuration ---
# The script will try to find and use these browsers in the specified order.
# Arguments are tailored per browser to handle certificate errors and other pop-ups.
# It is HIGHLY recommended to use Chromium based browsers as they support
# more appropriate command-line arguments
BROWSER_PREFERENCES = [
    {
        'name': 'Google Chrome',
        'exec': {
            'Windows': 'chrome',
            'Linux': 'google-chrome',
            'Darwin': 'Google Chrome' # macOS application name
        },
        'args': ['--ignore-certificate-errors', '--test-type']
        # --ignore-certificate-errors is used to bypass SSL errors
        # --test-type is used to run the browser without warnings
        # ! As the above suggests, this browser is UNSAFE for regular browsing use !
        # ! ALL security features of the browser are DISABLED to make control panel use simpler. !
        # ! Open another, normal instance for safe browsing !
    },
    {
        'name': 'Microsoft Edge',
        'exec': {
            'Windows': 'msedge',
            'Linux': 'microsoft-edge',
            'Darwin': 'Microsoft Edge'
        },
        'args': ['--ignore-certificate-errors']
    },
    {
        'name': 'Mozilla Firefox',
        'exec': {
            'Windows': 'firefox',
            'Linux': 'firefox',
            'Darwin': 'Firefox'
        },
        'args': []
    }
]

PING_INTERVAL_SECONDS = 3 # Pings every 3 seconds
DEFAULT_PORTS_TO_CHECK = [21, 80, 161, 443] # FTP, HTTP, SNMP, HTTPS


class PrinterPingerApp:
    """
    Main application class for the Printer Pinger GUI.
    Manages the UI, pinging threads, and browser launching.
    """
    def __init__(self, root: tk.Tk):
        """
        Initializes the application.
        """
        
        self.root = root
        self.root.title("Printer Pinger & Web UI Launcher")
        self.root.geometry("450x420") # Increased height for status bar
        self.root.minsize(450, 420)

        # --- State Variables ---
        self.is_pinging = False
        self.ping_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.browser_opened = set()

        # --- Browser Detection ---
        self.browser_command = self._find_browser_command()
        browser_name = self.browser_command['name'] if self.browser_command else "OS Default"
        
        # --- UI Setup ---
        self._setup_ui(browser_name)

    def _setup_ui(self, browser_name: str):
        """Creates and configures the UI elements."""
        # Status Bar (created before main_frame to be at the bottom)
        self.status_bar_label = ttk.Label(self.root, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, padding=2)
        self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.input_frame = ttk.LabelFrame(self.main_frame, text=f"Target Browser: {browser_name}", padding="10")
        self.input_frame.pack(fill=tk.X)
        
        self.status_frame = ttk.LabelFrame(self.main_frame, text="Status", padding="10")
        self.status_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Tells user to enter IPS one per line
        self.ip_label = ttk.Label(self.input_frame, text="Enter IPs, one per line:")
        self.ip_label.pack(pady=5)

        self.text_frame = ttk.Frame(self.input_frame)
        self.text_frame.pack(pady=5, fill=tk.X, expand=True)

        self.ip_entry = tk.Text(self.text_frame, width=40, height=8)
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ip_entry.focus()

        self.scrollbar = ttk.Scrollbar(self.text_frame, orient=tk.VERTICAL, command=self.ip_entry.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ip_entry.config(yscrollcommand=self.scrollbar.set)
        
        self.start_stop_button = ttk.Button(self.input_frame, text="Start Pinging", command=self.toggle_ping_process, underline=0)
        self.start_stop_button.pack(pady=10)

        self.status_widgets: Dict[str, Dict[str, Any]] = {}

        # --- Keyboard Shortcuts ---
        self.root.bind('<Control-Return>', lambda event: self.toggle_ping_process())
        self.root.bind('<Alt-s>', lambda event: self.start_stop_button.invoke())

    def _update_status_bar(self, message: str):
        """Updates the text in the status bar."""
        self.status_bar_label.config(text=message)

    def _find_browser_command(self) -> Optional[Dict[str, Any]]:
        """
        Finds the first available browser from BROWSER_PREFERENCES.
        On Windows, it specifically searches for Chrome in common installation directories.
        
        Returns:
            A dictionary with browser details if found, otherwise None.
        """
        system = platform.system()
        for browser in BROWSER_PREFERENCES:
            exec_name = browser['exec'].get(system)
            if not exec_name:
                continue

            path: Optional[str] = None
            is_mac_app = False

            if system == 'Windows' and browser['name'] == 'Google Chrome':
                # Special handling for Chrome on Windows to find the absolute path
                possible_paths = [
                    os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google\\Chrome\\Application\\chrome.exe"),
                    os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google\\Chrome\\Application\\chrome.exe"),
                    os.path.join(os.environ.get("LocalAppData", ""), "Google\\Chrome\\Application\\chrome.exe"),
                    os.path.join(os.environ.get("LocalAppData", ""), "Chromium\\Application\\chrome.exe")
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        path = p
                        break
                if not path: # Fallback to shutil.which if our specific search fails
                    path = shutil.which(exec_name)
            elif system == 'Darwin':
                mac_path = f"/Applications/{exec_name}.app"
                if os.path.isdir(mac_path):
                    path = mac_path
                    is_mac_app = True
            else: # Linux or other browsers on Windows
                path = shutil.which(exec_name)

            if path:
                return {'name': browser['name'], 'path': path, 'args': browser['args'], 'is_mac_app': is_mac_app}
        return None

    def open_browser_with_url(self, url: str):
        """
        Opens a URL using the detected browser or falls back to the default.
        """
        if self.browser_command:
            try:
                command: Any = []
                use_shell = False
                system = platform.system()

                if system == 'Darwin' and self.browser_command.get('is_mac_app'):
                    command.extend(['open', '-a', self.browser_command['path']])
                    if self.browser_command['args']:
                        command.extend(['--args'] + self.browser_command['args'])
                    command.append(url)
                else: # Windows and Linux
                    command.append(self.browser_command['path'])
                    command.extend(self.browser_command['args'])
                    command.append(url)
                    # On Windows, shell=True can be more reliable for launching GUI apps
                    # with arguments from a non-console script.
                    if system == 'Windows':
                        use_shell = True

                subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=use_shell)
            except (OSError, FileNotFoundError) as e:
                print(f"Error launching preferred browser: {e}. Falling back to default.")
                webbrowser.open(url)
        else:
            # Fallback for when no preferred browser is found
            webbrowser.open(url)

    def _parse_and_validate_targets(self, ip_string: str) -> List[Dict[str, Any]]:
        """
        Parses a string of IPs and ports, validating each.
        If no ports are specified for an IP, default ports are used.
        
        Returns:
            A list of target dictionaries, each with an IP and a list of ports.
        """
        targets = []
        lines = [line.strip() for line in ip_string.splitlines() if line.strip()]
        
        for line in lines:
            parts = line.split(':', 1)
            ip_str = parts[0].strip()
            
            try:
                ipaddress.ip_address(ip_str)
            except ValueError:
                messagebox.showerror("Invalid IP Address", f"The IP address '{ip_str}' is not valid.")
                return []

            target: Dict[str, Any] = {'ip': ip_str, 'ports': [], 'original_string': line}
            
            if len(parts) > 1 and parts[1].strip():
                port_str = parts[1]
                try:
                    ports = [int(p.strip()) for p in port_str.split(',') if p.strip()]
                    if not all(0 < port < 65536 for port in ports):
                        raise ValueError("Port number out of range.")
                    target['ports'] = sorted(list(set(ports))) # Remove duplicates and sort
                except ValueError:
                    messagebox.showerror("Invalid Port", f"Invalid port specification for '{ip_str}'. Please use comma-separated numbers (1-65535).")
                    return []
            else:
                # If no ports are specified, use the default list
                target['ports'] = DEFAULT_PORTS_TO_CHECK
                target['original_string'] = ip_str # Use just the IP as the key
            
            targets.append(target)
            
        return targets

    def toggle_ping_process(self):
        """Toggles the pinging process between start and stop."""
        if self.is_pinging:
            self._stop_ping_process()
        else:
            self._start_ping_process()

    def _start_ping_process(self):
        """
        Validates IPs and starts the pinging threads.
        """
        ip_string = self.ip_entry.get("1.0", tk.END).strip()
        if not ip_string:
            messagebox.showwarning("Input Required", "Please enter at least one IP address.")
            return

        targets = self._parse_and_validate_targets(ip_string)
        
        if not targets:
            return

        self.is_pinging = True
        self.stop_event.clear()
        self.browser_opened.clear()
        self.ping_threads.clear()

        self.start_stop_button.config(text="Stop Pinging")
        self.ip_entry.config(state=tk.DISABLED)
        self._update_status_bar("Pinging targets...")
        self._setup_status_display(targets)

        for target in targets:
            thread = threading.Thread(target=self.ping_worker, args=(target, self.stop_event), daemon=True)
            thread.start()
            self.ping_threads.append(thread)
        
        # Start the queue processor
        self.process_queue()

    def _stop_ping_process(self):
        """Stops the active pinging process."""
        self.is_pinging = False
        self.stop_event.set() # Signal all threads to stop
        self.start_stop_button.config(text="Start Pinging")
        self.ip_entry.config(state=tk.NORMAL)
        self._update_status_bar("Pinging stopped.")

    def _setup_status_display(self, targets: List[Dict[str, Any]]):
        """
        Creates the initial status widgets for each IP address.
        """
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_widgets.clear()

        for target in targets:
            original_string = target['original_string']
            ports = target['ports']

            # Main frame for this target
            frame = ttk.Frame(self.status_frame)
            frame.pack(fill=tk.X, pady=2, anchor='w')
            
            # Frame for the ping status (indicator + label)
            ping_frame = ttk.Frame(frame)
            ping_frame.pack(side=tk.LEFT, anchor='n')

            indicator = tk.Label(ping_frame, text="", width=5, bg="gray", fg="white", padx=4, pady=1, relief="raised", borderwidth=1)
            indicator.pack(side=tk.LEFT, padx=(0, 10))

            label = ttk.Label(ping_frame, text=f"{original_string}: Pinging...")
            label.pack(side=tk.LEFT, pady=2) # Add padding to align vertically
            
            # Frame to hold port buttons
            port_frame = ttk.Frame(frame)
            port_frame.pack(side=tk.LEFT, padx=(10, 0), anchor='n')

            port_widgets = {}
            if ports:
                for port in ports:
                    # Using tk.Label to easily control color and appearance
                    port_button = tk.Label(port_frame, text=str(port), bg="gray", fg="white", padx=4, pady=1, relief="raised", borderwidth=1)
                    port_button.pack(side=tk.LEFT, padx=2)
                    port_widgets[port] = port_button
            
            self.status_widgets[original_string] = {
                "label": label, 
                "indicator": indicator,
                "port_widgets": port_widgets
            }

    def _parse_latency(self, ping_output: str, is_windows: bool) -> str:
        """Parses latency from the ping command's stdout."""
        try:
            if is_windows:
                # Look for "Average = Xms" or "Average =Xms"
                match = re.search(r"Average\s?=\s?(\d+)ms", ping_output)
                if match:
                    return f"{match.group(1)}ms"
            else: # Linux/macOS
                # Look for "rtt min/avg/max/mdev = .../.../X/... ms"
                match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", ping_output)
                if match:
                    return f"{int(float(match.group(1)))}ms"
        except (IndexError, ValueError):
            pass # Could fail if regex changes or output is unexpected
        return ""

    def _check_port(self, ip: str, port: int, timeout: float = 1.0) -> str:
        """Checks if a TCP port is open on a given IP."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            try:
                if sock.connect_ex((ip, port)) == 0:
                    return "Open"
                else:
                    return "Closed"
            except socket.gaierror:
                return "Hostname Error"
            except socket.error:
                return "Conn Error"

    def ping_worker(self, target: Dict[str, Any], stop_event: threading.Event):
        """
        Pings a single IP address periodically and puts updates in the queue.
        If ports are specified, it checks them.
        This function is executed in a separate thread.
        """
        ip = target['ip']
        ports = target['ports']
        original_string = target['original_string']
        
        is_windows = platform.system().lower() == 'windows'
        # Construct the appropriate ping command once per thread
        if is_windows:
            command = ['ping', '-n', '1', '-w', '1000', ip]
        else:  # For Linux and macOS
            command = ['ping', '-c', '1', '-W', '1', ip]

        while not stop_event.is_set():
            launched_browser = False
            port_statuses: Optional[Dict[int, str]] = None
            latency_str = ""
            
            try:
                # On Windows, prevent the console window from appearing
                startupinfo = None
                if is_windows:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                response = subprocess.run(
                    command, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    startupinfo=startupinfo
                )
                
                if response.returncode == 0:
                    status, color = "Online", "green"
                    latency_str = self._parse_latency(response.stdout, is_windows)
                    
                    if ports:
                        port_statuses = {port: self._check_port(ip, port) for port in ports}
                        # If any port is open, the status is green.
                        if not any(s == "Open" for s in port_statuses.values()):
                            color = "orange" # Online but specified ports are closed
                    
                    if ip not in self.browser_opened:
                        self.open_browser_with_url(f"https://{ip}")
                        self.browser_opened.add(ip)
                        launched_browser = True
                else: # Should not happen with check=True, but for safety
                    status, color = "Offline", "red"

            except (subprocess.CalledProcessError, FileNotFoundError):
                status, color = "Offline", "red"
            
            # Put the result into the thread-safe queue for the main thread to process
            self.update_queue.put((original_string, status, color, launched_browser, port_statuses, latency_str))
            
            # Wait for the interval or until the stop event is set.
            # This is more efficient than a busy-wait sleep loop.
            stop_event.wait(timeout=PING_INTERVAL_SECONDS)

    def process_queue(self):
        """
        Processes messages from the update queue to safely update the GUI.
        """
        try:
            while not self.update_queue.empty():
                original_string, status, color, launched_browser, port_statuses, latency_str = self.update_queue.get_nowait()
                self._update_status_in_gui(original_string, status, color, launched_browser, port_statuses, latency_str)
        finally:
            # Reschedule itself to run again if pinging is active
            if self.is_pinging:
                self.root.after(100, self.process_queue)

    def _update_status_in_gui(self, original_string: str, status: str, color: str, launched_browser: bool, port_statuses: Optional[Dict[int, str]], latency_str: str):
        """
        Updates the GUI widgets for a specific IP. Must be called from the main thread.
        """
        if original_string in self.status_widgets:
            widgets = self.status_widgets[original_string]
            ip_part = original_string.split(':', 1)[0]

            # Update ping status indicator
            widgets["indicator"].config(bg=color, text=latency_str if status == "Online" else "FAIL")

            current_text = widgets["label"].cget("text")
            
            # Build the new status text for the main label (without port info)
            new_text = f"{ip_part}: {status}"

            if launched_browser:
                # Append launched message, but avoid duplicating it
                if "Launched" not in current_text:
                     new_text += " - Web UI Launched"
            elif "Launched" in current_text:
                # Preserve the launched message if it was already there
                new_text += " - Web UI Launched"

            widgets["label"].config(text=new_text)
            
            # Update port status "buttons"
            if port_statuses:
                port_widgets = widgets.get("port_widgets", {})
                for port, port_status in port_statuses.items():
                    if port in port_widgets:
                        button = port_widgets[port]
                        port_color = "gray" # Default/initial color
                        if port_status == "Open":
                            port_color = "#007bff" # Blue
                        elif port_status == "Closed":
                            port_color = "#fd7e14" # Orange
                        elif "Error" in port_status:
                            port_color = "#dc3545" # Red for errors
                        
                        button.config(bg=port_color)


def main():
    if messagebox.askyesno("Security Warning",
        "This application will open a web browser with DISABLED security features.\n\n"
        "Do NOT use this browser for normal web browsing!\n\n"
        "Do you want to continue?",
        icon='warning') == False:
        return
    
    try:
        root = tk.Tk()
        app = PrinterPingerApp(root)
        root.mainloop()
    except Exception as e:
        # Fallback for logging any unexpected critical errors.
        print(f"An unexpected error occurred: {e}")
        messagebox.showerror("Critical Error", f"A critical error occurred:\n{e}")

if __name__ == "__main__":
    main()