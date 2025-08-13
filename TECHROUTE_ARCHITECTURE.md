# TechRoute Architecture Documentation

## Overview
TechRoute is a network discovery and monitoring tool that:
- Discovers devices on the local network
- Checks TCP/UDP service availability
- Provides a GUI for monitoring status

## Core Components

### 1. Controller (techroute/controller.py)
Main application coordinator that:
- Manages network discovery processes
- Handles configuration
- Coordinates between UI and backend services

Key Functions:
- `__init__()` - Initializes all components
- `process_queue()` - Handles status updates
- `start_ping_process()` - Starts network scanning
- `launch_web_ui_for_port()` - Opens web interfaces

### 2. Network Discovery (techroute/network/)
#### discovery.py
- Discovers local network information
- Gets IP addresses, subnet masks, gateways
- Uses both system tools (ip/ifconfig) and psutil

Key Functions:
- `get_network_info()` - Main interface for network info
- `_get_network_info_linux()` - Linux-specific implementation

#### ping.py
- Performs actual ping and port checks
- Runs in worker threads

Key Functions:
- `ping_worker()` - Main worker function
- `_check_port()` - Checks TCP port status
- `_parse_latency()` - Extracts ping times

### 3. Service Checkers (techroute/checkers/)
#### base.py
- Defines base interfaces for service checking
- Provides common UDP helper functions

Key Components:
- `CheckResult` dataclass - Standard result format
- `ServiceCheckManager` - Coordinates parallel checks

#### Protocol Checkers (mdns.py, slp.py, etc.)
- Implement protocol-specific discovery
- All follow BaseChecker interface

### 4. UI Components (techroute/ui/)
#### app_ui.py
- Main application window
- Handles theme/language settings

#### status_view.py
- Displays target status information
- Shows ping results and port statuses

Key Functions:
- `update_target_row()` - Updates UI for a target
- `_create_target_row()` - Creates status widgets

### 5. Configuration (techroute/configuration.py)
- Manages application settings
- Handles config file loading/saving

Key Functions:
- `load_or_create_config()` - Main config loader
- `save_config()` - Saves changes

## Data Flow
1. User initiates scan via UI
2. Controller creates ping workers
3. Workers perform checks and queue results
4. Controller processes queue and updates UI
5. UI renders status changes

## Key Data Structures
- `target_info` dict - Contains all status info for a target
- `port_statuses` dict - Maps ports to status ("Open"/"Closed")
- `udp_service_statuses` dict - Maps service names to status

## Important Patterns
- Observer pattern for status updates
- Worker thread pattern for parallel checks
- Protocol interface pattern for service checkers
