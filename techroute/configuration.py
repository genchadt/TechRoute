# techroute/configuration.py

"""
Configuration loader for TechRoute.

Handles loading settings from config.yaml. If the file doesn't exist,
it creates one with default values.
"""

import sys
import yaml
from typing import Dict, Any

# This dictionary holds the default structure and values for our config.
# It will be used to generate the initial config.yaml.
DEFAULT_CONFIG = {
    'ping_interval_seconds': 3,
    'port_check_timeout_seconds': 1,
    'default_ports_to_check': [80, 443, 631],
    'udp_services_to_check': [],
    # UI preferences
    'ui_theme': 'System',            # Options: System, Light, Dark
    'port_readability': 'Numbers',   # Options: Numbers, Simple
    # Users can edit, reorder, or remove browsers from the generated yaml.
    'browser_preferences': [
        {
            'name': 'Google Chrome',
            'exec': {
                'Windows': 'chrome', 
                'Linux': ['google-chrome', 'chromium-browser', 'chromium'], 
                'Darwin': 'Google Chrome'
            },
            'args': ['--ignore-certificate-errors', '--test-type']
        },
    ]
}

def get_config_path() -> str:
    """Returns the path to the config file."""
    return "config.yaml"

def save_config(config: Dict[str, Any]):
    """Saves the provided configuration dictionary to config.yaml."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            f.write("# TechRoute Configuration File\n")
            f.write("# You can edit these settings. The application will use them on next launch.\n\n")
            yaml.dump(config, f, sort_keys=False, default_flow_style=False, indent=2)
    except IOError as e:
        # In a GUI app, it's better to show an error dialog than print to stderr
        # For now, we'll print, but this could be improved.
        print(f"ERROR: Could not write config file to '{config_path}': {e}", file=sys.stderr)

def load_or_create_config() -> Dict[str, Any]:
    """
    Loads configuration from config.yaml.

    If the file doesn't exist, it creates it with default values.
    If the file is invalid, it reports the error and exits.
    """
    config_path = get_config_path()
    try:
        with open(config_path, 'r') as f:
            user_config = yaml.safe_load(f)
        
        # Merge user config with defaults to ensure all keys are present
        config = DEFAULT_CONFIG.copy()
        if user_config:
            # Deep update for nested structures like browser_preferences if needed,
            # but a simple update is fine for this structure.
            if isinstance(user_config, dict):
                config.update(user_config)
        return config

    except FileNotFoundError:
        print(f"Configuration file not found. Creating '{config_path}' with default settings.")
        try:
            with open(config_path, 'w') as f:
                # Add comments to the top of the file for user guidance
                f.write("# TechRoute Configuration File\n")
                f.write("# You can edit these settings. The application will use them on next launch.\n\n")
                yaml.dump(DEFAULT_CONFIG, f, sort_keys=False, default_flow_style=False, indent=2)
            return DEFAULT_CONFIG
        except IOError as e:
            print(f"FATAL: Could not write default config file to '{config_path}': {e}", file=sys.stderr)
            sys.exit(1)

    except yaml.YAMLError as e:
        print(f"FATAL: Error parsing '{config_path}': {e}", file=sys.stderr)
        sys.exit(1)
