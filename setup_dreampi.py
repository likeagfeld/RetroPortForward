import subprocess
import sys
import os
import socket
from queue import Queue, Empty  # Add 'Empty' to the import
import threading
import time
from datetime import datetime
import re
import urllib3
import logging
from router_handlers import RouterHandlers 

urllib3.disable_warnings()

def log_message(message):
    """
    Log messages to both console and a log file.
    Creates log file in the script's directory or user's home directory.
    """
    # Determine the best location to create the log file
    try:
        # First try to create log in the script's directory
        log_dir = os.path.dirname(os.path.abspath(__file__))
    except:
        # Fallback to user's home directory
        log_dir = os.path.expanduser('~')

    # Ensure log directory exists
    log_path = os.path.join(log_dir, 'port_forward.log')

    # Create timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    # Print to console
    print(log_entry)

    # Append to log file
    try:
        with open(log_path, "a") as f:
            f.write(log_entry + "\n")
        
        # Confirm log file creation (for debugging)
        print(f"Log written to: {log_path}")
    except Exception as e:
        print(f"Could not write to log file: {e}")

def install_dependencies():
    try:
        log_message("Checking and installing required dependencies...")
        
        temp_dir = os.path.join(os.environ.get('TEMP', os.getcwd()), 'pip_temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Ensure pip is up to date
        def run_pip_command(command):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", command, "--upgrade"], 
                                      stdout=subprocess.DEVNULL, 
                                      stderr=subprocess.DEVNULL)
                return True
            except Exception as e:
                log_message(f"Pip {command} failed: {e}")
                return False

        # Upgrade pip
        run_pip_command("install")
        run_pip_command("setuptools")

        # Required packages with error handling
        required_packages = [
            'requests', 
            'netaddr', 
            'python-nmap', 
            'urllib3',
            'scapy'
        ]
        
        for package in required_packages:
            log_message(f"Installing {package}...")
            try:
                # Try multiple installation methods
                install_methods = [
                    # Method 1: Standard pip install
                    [sys.executable, "-m", "pip", "install", "--quiet", "--no-warn-script-location", package],
                    # Method 2: Alternative pip install
                    [sys.executable, "-m", "pip", "install", "--user", "--quiet", package],
                    # Method 3: Direct installation
                    [sys.executable, "-m", "pip", "install", package]
                ]

                installed = False
                for method in install_methods:
                    try:
                        subprocess.check_call(method, 
                                              stdout=subprocess.DEVNULL, 
                                              stderr=subprocess.DEVNULL)
                        log_message(f"{package} installed successfully")
                        installed = True
                        break
                    except Exception as e:
                        log_message(f"Installation method failed for {package}: {e}")
                
                if not installed:
                    raise Exception(f"Could not install {package}")

            except Exception as e:
                log_message(f"Failed to install {package}: {e}")
                # Continue trying other packages instead of failing completely
                continue

        # System-specific network library installation
        if os.name == 'nt':
            # Silent Npcap install for Windows
            try:
                import requests
                npcap_url = "https://nmap.org/npcap/dist/npcap-1.60.exe"
                npcap_installer = os.path.join(temp_dir, "npcap-installer.exe")
                
                # Download Npcap
                response = requests.get(npcap_url)
                with open(npcap_installer, 'wb') as f:
                    f.write(response.content)
                
                # Silent install of Npcap
                try:
                    subprocess.check_call([npcap_installer, "/silent"], 
                                          stdout=subprocess.DEVNULL, 
                                          stderr=subprocess.DEVNULL)
                    log_message("Npcap installed successfully")
                except Exception as npcap_err:
                    log_message(f"Could not install Npcap: {npcap_err}")
            except Exception as e:
                log_message(f"Npcap download failed: {e}")
        
        elif os.name == 'posix':
            # Silent libpcap install for Linux
            if os.path.exists('/usr/bin/apt'):
                try:
                    subprocess.check_call(['sudo', 'apt-get', 'install', '-y', 'libpcap-dev'], 
                                          stdout=subprocess.DEVNULL, 
                                          stderr=subprocess.DEVNULL)
                except Exception as e:
                    log_message(f"Could not install libpcap on Debian/Ubuntu: {e}")
            elif os.path.exists('/usr/bin/yum'):
                try:
                    subprocess.check_call(['sudo', 'yum', 'install', '-y', 'libpcap-devel'], 
                                          stdout=subprocess.DEVNULL, 
                                          stderr=subprocess.DEVNULL)
                except Exception as e:
                    log_message(f"Could not install libpcap on RHEL/CentOS: {e}")

        # Verify critical packages
        critical_packages = ['requests', 'scapy']
        for package in critical_packages:
            try:
                __import__(package)
            except ImportError:
                log_message(f"Critical package {package} not found after installation attempts")
                return False

        return True
    
    except Exception as e:
        log_message(f"Comprehensive dependency installation error: {e}")
        return False

try:
    import requests
except ImportError:
    log_message("Installing requests library...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"]) 
    except subprocess.CalledProcessError as e:
        log_message(f"Error installing requests: {e}")
        sys.exit(1)
    else:
        import requests

def get_router_subnet_ip():
    """Get the local IP address that's on the same subnet as the router."""
    try:
        # Get router IP
        if os.name == 'nt':  # Windows
            output = subprocess.check_output('ipconfig', text=True)
            gateways = re.findall(r'Default Gateway.*: ([\d.]+)', output)
            router_ip = gateways[0] if gateways else None
        else:  # Linux/Mac
            output = subprocess.check_output('ip route | grep default', shell=True, text=True)
            router_ip = output.split()[2]

        if not router_ip:
            log_message("Could not determine router IP address")
            return None

        # Get all non-VPN adapters
        output = subprocess.check_output('ipconfig /all', text=True) if os.name == 'nt' else \
                subprocess.check_output('ip addr show', shell=True, text=True)
        
        # Find adapter with matching subnet
        router_subnet = '.'.join(router_ip.split('.')[:3])  # Get first three octets
        vpn_patterns = ['vpn', 'tap-windows', 'tunnel', 'tun', 'tap']
        current_adapter = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Skip VPN adapters
            if any(pattern in line.lower() for pattern in vpn_patterns):
                current_adapter = None
                continue
                
            # Look for IPv4 addresses
            if os.name == 'nt':
                if line.endswith(':'):
                    current_adapter = line[:-1].strip()
                elif current_adapter and 'IPv4 Address' in line:
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if '.'.join(ip.split('.')[:3]) == router_subnet:
                            log_message(f"Found matching adapter: {current_adapter} with IP: {ip}")
                            return ip
            else:
                ip_match = re.search(r'inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                if ip_match:
                    ip = ip_match.group(1)
                    if '.'.join(ip.split('.')[:3]) == router_subnet:
                        return ip
        
        log_message("No matching subnet found")
        return None
    except Exception as e:
        log_message(f"Error getting router subnet IP: {str(e)}")
        return None
        
class RouterManager:
    def __init__(self, router_type=None):
        self.router_ip = None
        self.router_type = router_type
        self.handler = None
        self.session = requests.Session()
        self.session.verify = False
        
        if router_type:
            self.handler = RouterHandlers.get_handler(router_type)(self.session, self.router_ip)

    def find_router(self):
        """Find router IP address"""
        try:
            if os.name == 'nt':  # Windows
                output = subprocess.check_output('ipconfig', text=True)
                gateways = re.findall(r'Default Gateway.*: ([\d.]+)', output)
                if gateways:
                    self.router_ip = gateways[0]
            else:  # Linux/Mac
                output = subprocess.check_output('ip route | grep default', shell=True, text=True)
                self.router_ip = output.split()[2]

            if not self.router_ip:
                log_message("Could not determine router IP address")
                return False

            log_message(f"Found router at {self.router_ip}")
            
            # Update handler with router IP if we have one
            if self.handler:
                self.handler.router_ip = self.router_ip
                
            return True
        except subprocess.CalledProcessError as e:
            log_message(f"Error executing network commands: {str(e)}")
            return False
        except Exception as e:
            log_message(f"Error finding router: {str(e)}")
            return False

    def login_to_router(self, username=None, password=None):
        """Login to router with provided credentials"""
        if not self.handler:
            log_message("No router handler available")
            return False

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if self.handler.login(username, password):
                    log_message("Successfully logged into router")
                    return True
                
                log_message(f"Login failed. {max_attempts - attempt - 1} attempts remaining.")
            except Exception as e:
                log_message(f"Login error: {str(e)}")
                log_message(f"Login failed. {max_attempts - attempt - 1} attempts remaining.")
        
        return False

    def setup_port_forward(self, target_device, console_type):
        """Setup port forwarding for specified device and console"""
        if not self.handler:
            log_message("No router handler available")
            return False

        try:
            log_message("Setting up port forwarding rules...")
            
            # Get the appropriate port rules based on the console type
            port_rules = self.get_port_rules(console_type)
            
            success = self.handler.setup_port_forward(target_device, port_rules)
            
            if success:
                log_message("Successfully set up port forwarding rules")
                log_message("Rules have been configured as static port forwards and will persist")
            else:
                log_message("Failed to set up port forwarding rules")
                if self.router_type == "Generic":
                    log_message("For Generic router types, please configure port forwarding manually through your router's web interface")
                
            return success
        except Exception as e:
            log_message(f"Error setting up port forwarding: {str(e)}")
            return False

    def get_port_rules(self, console_type):
        """Get port forwarding rules for specified console type"""
        if console_type == 'dreamcast':
            return get_dreamcast_port_rules()
        elif console_type == 'saturn':
            return [
                {"protocol": "TCP", "external": 65432, "internal": 65432},
                {"protocol": "UDP", "external": 20001, "internal": 20001},
                {"protocol": "UDP", "external": 20002, "internal": 20002}
            ]
        else:
            return []

def scan_dreampi_ports(network_prefix):
    """Scan for hosts with DreamPi's specific ports open."""
    dreampi_ports = [65432, 20001, 20002]  # DreamPi's known ports
    total_ips = 252  # .2 to .253
    
    print(f"\rPort scan: 0% (0/{total_ips} IPs)", end="", flush=True)
    
    for i in range(2, 254):
        target_ip = f"{network_prefix}.{i}"
        progress = ((i - 1) / total_ips) * 100
        print(f"\rPort scan: {progress:.1f}% ({i-1}/{total_ips} IPs)", end="", flush=True)
        
        for port in dreampi_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)  # Very short timeout
                result = sock.connect_ex((target_ip, port))
                if result == 0:  # Port is open
                    # Found a potential DreamPi
                    print()  # New line after progress
                    log_message(f"Found potential DreamPi at {target_ip} (port {port} open)")
                    return target_ip
            except:
                pass
            finally:
                sock.close()
    
    print()  # New line after progress
    return None

def check_mac_pattern(network_prefix):
    """Look for specific MAC address patterns that might indicate a Raspberry Pi."""
    try:
        # Common Raspberry Pi MAC prefixes
        pi_mac_prefixes = [
            'B8:27:EB',  # Raspberry Pi 2, 3
            'DC:A6:32',  # Raspberry Pi 4
            'E4:5F:01'   # Raspberry Pi 4
        ]
        
        if os.name == 'nt':  # Windows
            arp_output = subprocess.check_output('arp -a', text=True)
            entries = arp_output.split('\n')
        else:  # Linux/Mac
            arp_output = subprocess.check_output('arp -n', shell=True, text=True)
            entries = arp_output.split('\n')
            
        total_entries = len(entries)
        print(f"\rMAC scan: 0% (0/{total_entries} entries)", end="", flush=True)
        
        for i, line in enumerate(entries):
            progress = ((i + 1) / total_entries) * 100
            print(f"\rMAC scan: {progress:.1f}% ({i+1}/{total_entries} entries)", end="", flush=True)
            
            for prefix in pi_mac_prefixes:
                if prefix.lower() in line.lower():
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if ip.startswith(network_prefix):
                            print()  # New line after progress
                            log_message(f"Found potential Raspberry Pi at {ip} (MAC match)")
                            return ip
        
        print()  # New line after progress
        return None
    except Exception as e:
        log_message(f"MAC scan error: {str(e)}")
        return None

def find_dreampi():
    """Find DreamPi using multiple detection methods."""
    try:
        # Get local IP on router's subnet
        local_ip = get_router_subnet_ip()
        if not local_ip:
            log_message("Could not determine local IP on router subnet")
            return None
            
        network_prefix = '.'.join(local_ip.split('.')[:3])
        log_message(f"Scanning router subnet: {network_prefix}.0/24...")
        print()  # Add blank line before progress starts

        # Expanded detection methods
        dreampi_hostname_patterns = [
            'dreampi', 
            'dream-pi', 
            'dream_pi', 
            'rpi', 
            'raspberrypi', 
            'raspberry-pi'
        ]

        pi_mac_prefixes = [
            'B8:27:EB',  # Older Raspberry Pi
            'DC:A6:32',  # Raspberry Pi 4
            'E4:5F:01',  # Raspberry Pi 4
            'D8:3A:DD',  # Raspberry Pi
            'B8:81:98',  # Raspberry Pi
        ]

        # Try Scapy for fast network scanning
        try:
            from scapy.all import ARP, Ether, srp
            import ipaddress

            # Generate IP list
            ip_list = [str(ip) for ip in ipaddress.IPv4Network(f'{network_prefix}.0/24', strict=False) 
                       if ip not in [ipaddress.IPv4Address(f'{network_prefix}.0'), 
                                     ipaddress.IPv4Address(f'{network_prefix}.255')]]
            
            # Remove network and broadcast addresses
            ip_list = [str(ip) for ip in ip_list if ip.split('.')[-1] not in ['0', '255']]

            print(f"Scanning {len(ip_list)} IP addresses...")

            # Progress tracking
            discovered_ips = []
            total_ips = len(ip_list)

            # Batch processing to show progress
            batch_size = 50
            for i in range(0, total_ips, batch_size):
                batch = ip_list[i:i+batch_size]
                
                # Prepare the ARP request packet
                arp_request = ARP(pdst=batch)
                ether_frame = Ether(dst="ff:ff:ff:ff:ff:ff")
                packet = ether_frame/arp_request

                # Send packet and receive responses
                result = srp(packet, timeout=1, verbose=0)[0]

                # Process results
                for sent, received in result:
                    ip = received.psrc
                    mac = received.hwsrc
                    
                    # Initial MAC prefix check
                    mac_match = any(mac.startswith(prefix) for prefix in pi_mac_prefixes)
                    
                    # Additional hostname and port checks
                    try:
                        # Try to get hostname
                        try:
                            hostname = socket.gethostbyaddr(ip)[0].lower()
                        except:
                            hostname = ""

                        # Hostname pattern match
                        hostname_match = any(pattern in hostname for pattern in dreampi_hostname_patterns)

                        # Port check for DreamPi specific ports
                        dreampi_ports = [65432, 20001, 20002]
                        port_match = False
                        for port in dreampi_ports:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(0.1)
                            result = sock.connect_ex((ip, port))
                            sock.close()
                            if result == 0:
                                port_match = True
                                break

                        # Combine detection methods
                        if mac_match or hostname_match or port_match:
                            log_message(f"Potential DreamPi found:")
                            log_message(f"  IP: {ip}")
                            log_message(f"  MAC: {mac}")
                            log_message(f"  Hostname: {hostname}")
                            log_message(f"  MAC Match: {mac_match}")
                            log_message(f"  Hostname Match: {hostname_match}")
                            log_message(f"  Port Match: {port_match}")
                            
                            discovered_ips.append(ip)

                    except Exception as e:
                        log_message(f"Error checking host {ip}: {e}")

                # Progress indication
                progress = min(((i + batch_size) / total_ips) * 100, 100)
                print(f"\rScanning progress: {progress:.1f}% ({min(i+batch_size, total_ips)}/{total_ips} IPs)", end="", flush=True)

            print()  # New line after progress

            # Process discovered IPs
            if discovered_ips:
                if len(discovered_ips) == 1:
                    return discovered_ips[0]
                else:
                    print("\nMultiple potential DreamPi devices found:")
                    for i, ip in enumerate(discovered_ips, 1):
                        print(f"{i}. {ip}")
                    
                    # Ask user to choose
                    while True:
                        try:
                            choice = input("Enter the number of your DreamPi (or 'q' to quit): ").strip()
                            if choice.lower() == 'q':
                                return None
                            
                            choice = int(choice)
                            if 1 <= choice <= len(discovered_ips):
                                return discovered_ips[choice - 1]
                            
                            print("Invalid selection. Please try again.")
                        except ValueError:
                            print("Please enter a valid number or 'q'.")

        except ImportError:
            log_message("Scapy not installed. Falling back to alternative methods.")
        except Exception as e:
            log_message(f"Network scanning error with Scapy: {e}")

        # Fallback to manual input if Scapy fails
        print("\nAutomatic DreamPi detection failed.")
        manual_input = input("Do you know your DreamPi's IP address? (Enter IP or press Enter to skip): ").strip()
        
        if manual_input:
            try:
                # Validate IP is in the correct subnet
                if manual_input.startswith(network_prefix):
                    log_message(f"Using manually provided DreamPi IP: {manual_input}")
                    return manual_input
                else:
                    log_message(f"Provided IP {manual_input} is not on the local network subnet {network_prefix}")
            except Exception as e:
                log_message(f"Error with manual IP input: {e}")

        # Final fallback
        log_message("Could not automatically find DreamPi on the network.")
        return None
        
    except Exception as e:
        log_message(f"Comprehensive error in DreamPi network discovery: {e}")
        return None

def get_local_ip():
    """Get local IP address on router's subnet."""
    return get_router_subnet_ip()

def get_dreampi_network_dreamcast_ip():
    """
    Find the Dreamcast IP on the DreamPi network.
    Assumes the Dreamcast is on the same subnet as the router.
    """
    try:
        local_ip = get_router_subnet_ip()
        if not local_ip:
            log_message("Could not determine local network subnet")
            return None
        
        # Split the local IP into its network parts
        network_parts = local_ip.split('.')
        
        # Replace the last octet with .98 while keeping the first three octets
        dreamcast_ip = f"{'.'.join(network_parts[:3])}.98"
        
        log_message(f"Determined Dreamcast IP: {dreamcast_ip}")
        return dreamcast_ip
    except Exception as e:
        log_message(f"Error determining Dreamcast IP: {str(e)}")
        return None

def get_dreamcast_port_rules():
    """Define port forwarding rules for Dreamcast online games."""
    return [
        # Alien Front Online
        {"protocol": "UDP", "external": 7980, "internal": 7980},
        
        # ChuChu Rocket!
        {"protocol": "UDP", "external": 9789, "internal": 9789},
        
        # ClassiCube
        {"protocol": "UDP", "external": 25565, "internal": 25565},
        
        # Daytona USA
        {"protocol": "UDP", "external": 20675, "internal": 20675},
        {"protocol": "UDP", "external": 12079, "internal": 12079},
        
        # Dee Dee Planet
        {"protocol": "UDP", "external": 9879, "internal": 9879},
        
        # Driving Strikers
        {"protocol": "UDP", "external": 30099, "internal": 30099},
        
        # Floigan Bros.
        {"protocol": "TCP", "external": 37001, "internal": 37001},
        
        # Golf Shiyouyo 2
        {"protocol": "UDP", "external": 20675, "internal": 20675},
        {"protocol": "UDP", "external": 12079, "internal": 12079},
        
        # Internet Game Pack
        {"protocol": "UDP", "external": 5656, "internal": 5656},
        {"protocol": "TCP", "external": 5011, "internal": 5011},
        {"protocol": "TCP", "external": 10500, "internal": 10500},
        {"protocol": "TCP", "external": 10501, "internal": 10501},
        {"protocol": "TCP", "external": 10502, "internal": 10502},
        {"protocol": "TCP", "external": 10503, "internal": 10503},
        
        # NBA/NFL/NCAA 2K Series
        {"protocol": "UDP", "external": 5502, "internal": 5502},
        {"protocol": "UDP", "external": 5503, "internal": 5503},
        {"protocol": "UDP", "external": 5656, "internal": 5656},
        {"protocol": "TCP", "external": 5011, "internal": 5011},
        {"protocol": "TCP", "external": 6666, "internal": 6666},
        
        # The Next Tetris: Online Edition
        {"protocol": "TCP", "external": 3512, "internal": 3512},
        {"protocol": "UDP", "external": 3512, "internal": 3512},
        
        # Ooga Booga
        {"protocol": "UDP", "external": 6001, "internal": 6001},
        
        # PBA Tour Bowling 2001 (Extensive port range)
        {"protocol": "TCP", "external": 2300, "internal": 2300},
        {"protocol": "UDP", "external": 2300, "internal": 2300},
        {"protocol": "TCP", "external": 2400, "internal": 2400},
        {"protocol": "UDP", "external": 2400, "internal": 2400},
        {"protocol": "UDP", "external": 6500, "internal": 6500},
        {"protocol": "TCP", "external": 47624, "internal": 47624},
        {"protocol": "UDP", "external": 13139, "internal": 13139},
        
        # Planet Ring
        {"protocol": "UDP", "external": 7648, "internal": 7648},
        {"protocol": "UDP", "external": 1285, "internal": 1285},
        {"protocol": "UDP", "external": 1028, "internal": 1028},
        
        # Sega Tetris
        {"protocol": "UDP", "external": 20675, "internal": 20675},
        {"protocol": "UDP", "external": 12079, "internal": 12079},
        
        # Starlancer (Extensive port range)
        {"protocol": "TCP", "external": 2300, "internal": 2300},
        {"protocol": "UDP", "external": 2300, "internal": 2300},
        {"protocol": "TCP", "external": 2400, "internal": 2400},
        {"protocol": "UDP", "external": 2400, "internal": 2400},
        {"protocol": "UDP", "external": 6500, "internal": 6500},
        {"protocol": "TCP", "external": 47624, "internal": 47624},
        
        # World Series Baseball 2K2
        {"protocol": "UDP", "external": 37171, "internal": 37171},
        {"protocol": "UDP", "external": 13713, "internal": 13713},
        
        # Worms World Party
        {"protocol": "TCP", "external": 17219, "internal": 17219}
    ]    
    
def main():
    log_message("Starting port forwarding setup...")
    
    if not install_dependencies():
        log_message("Failed to install required dependencies. Exiting...")
        return

    # Initial port forwarding goal selection
    while True:
        try:
            print("\nWhat would you like to configure port forwarding for?")
            goal_choice = input("1. Sega Saturn Online\n2. Sega Dreamcast Online\nEnter choice (1 or 2): ").strip()
            if goal_choice in ['1', '2']:
                break
            print("Please enter 1 or 2")
        except Exception as e:
            log_message(f"Error getting port forwarding goal: {str(e)}")
            return

    # Initialize router management
    router = RouterManager()
    if not router.find_router():
        log_message("Could not find router. Exiting...")
        return

    if not router.login_to_router():
        log_message("Could not log in to router. Exiting...")
        return

    # Define initial port rules
    if goal_choice == '1':
        # Saturn port rules
        port_rules = [
            {"protocol": "TCP", "external": 65432, "internal": 65432},
            {"protocol": "UDP", "external": 20001, "internal": 20001},
            {"protocol": "UDP", "external": 20002, "internal": 20002}
        ]

        # Saturn-specific port forwarding options
        while True:
            try:
                saturn_choice = input("\nWould you like to forward ports to:\n1. DreamPi\n2. This PC\nEnter choice (1 or 2): ").strip()
                if saturn_choice in ['1', '2']:
                    break
                print("Please enter 1 or 2")
            except Exception as e:
                log_message(f"Error getting Saturn port forwarding choice: {str(e)}")
                return

        if saturn_choice == '1':
            # Find DreamPi
            target_ip = find_dreampi()
            if not target_ip:
                log_message("Could not find DreamPi on the network. Exiting...")
                return
        else:
            # Use local PC's IP
            target_ip = get_local_ip()
            if not target_ip:
                log_message("Could not determine local PC's IP address. Exiting...")
                return
            log_message(f"Using local PC IP: {target_ip}")

    else:
        # Dreamcast port rules
        port_rules = get_dreamcast_port_rules()
        
        # Always forward to .98 IP for Dreamcast
        target_ip = get_dreampi_network_dreamcast_ip()
        if not target_ip:
            log_message("Could not determine Dreamcast IP. Exiting...")
            return
        
        log_message(f"Configuring port forwarding for Dreamcast Online Games on {target_ip}")

    # Setup static port forwarding
    if router.setup_port_forward(target_ip, port_rules):
        log_message("Port forwarding setup completed successfully!")
        log_message("These rules are configured as static port forwards and will persist")
    else:
        log_message("Failed to set up port forwarding rules")
        if router.router_type == "Generic":
            log_message("For Generic router types, please configure port forwarding manually through your router's web interface")
    
    log_message("Script completed. Press Enter to exit...")
    input()
    
if __name__ == "__main__":
    main()