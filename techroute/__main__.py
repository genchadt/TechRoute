"""
Main entry point for the TechRoute application.
"""
from techroute.app import main
import os
import sys
import subprocess
import ctypes

def run_as_admin():
    """
    Checks for administrator privileges and re-launches the application
    if necessary.
    - On Windows, it uses ShellExecuteW with the 'runas' verb.
    - On Linux, it uses 'sudo' to re-run the script.
    """
    if os.name == 'nt':
        # Windows-specific check
        try:
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                print("Administrator privileges required. Attempting to re-launch...")
                
                # When running as a module (-m), __package__ is set.
                # We must re-launch using the module syntax.
                if __package__:
                    module_name = __package__
                    params = ' '.join([f'"{p}"' for p in sys.argv[1:]])
                    command = f'-m {module_name} {params}'
                else:
                    # Fallback for direct script execution
                    script = os.path.abspath(sys.argv[0])
                    params = ' '.join([f'"{p}"' for p in sys.argv[1:]])
                    command = f'"{script}" {params}'

                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, command, None, 1)
                sys.exit(0)
        except Exception as e:
            print(f"Failed to elevate privileges: {e}")
            sys.exit(1)
    
    elif os.name == 'posix':
        # Linux/macOS-specific check
        if os.geteuid() != 0:
            print("Root privileges are required for network scanning. Attempting to re-launch with sudo...")
            try:
                # Construct the command to re-run the script with sudo
                # This handles both direct script execution and module execution
                if __package__:
                    command = ['sudo', sys.executable, '-m', __package__] + sys.argv[1:]
                else:
                    command = ['sudo', sys.executable] + sys.argv

                # Execute the command
                result = subprocess.run(command)
                
                # Exit the original non-privileged process.
                # The exit code from the sudo process will be the result.
                sys.exit(result.returncode)

            except subprocess.CalledProcessError as e:
                print(f"Failed to acquire root privileges: {e}. Please run with sudo.")
                sys.exit(1)
            except FileNotFoundError:
                print("'sudo' command not found. Please run as root.")
                sys.exit(1)
            except Exception as e:
                print(f"An unexpected error occurred during privilege elevation: {e}")
                sys.exit(1)

def main_entry():
    """
    Main function to run the TechRoute application.
    """
    # Privilege check must be the very first thing
    run_as_admin()
    
    # Now, proceed with the application startup
    from techroute.app import main as app_main
    app_main()

if __name__ == "__main__":
    main_entry()
