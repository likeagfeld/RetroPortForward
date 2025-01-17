import os
import sys
import json
import logging
import platform
import traceback
import shutil

# Ensure the script can import modules from its directory
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Attempt to import required libraries
try:
    import webview
    import requests
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Import local modules
from setup_dreampi import (
    RouterManager, 
    get_dreamcast_port_rules, 
    get_router_subnet_ip, 
    find_dreampi, 
    log_message
)

def setup_comprehensive_logging():
    """Set up detailed logging for debugging"""
    # Determine log file path
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        log_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        log_dir = os.path.dirname(os.path.abspath(__file__))

    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'port_forward_launch.log')
    
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()  # Also output to console
            ]
        )

        # Log system and environment information
        logging.info("Application Launch Attempt")
        logging.info(f"Python Version: {sys.version}")
        logging.info(f"Platform: {platform.platform()}")
        logging.info(f"Executable Path: {sys.executable}")
        logging.info(f"Current Working Directory: {os.getcwd()}")
        logging.info(f"Script Location: {os.path.abspath(__file__)}")
        logging.info(f"Sys.frozen: {getattr(sys, 'frozen', False)}")
        
        return log_path
    except Exception as e:
        print(f"Logging setup failed: {e}")
        traceback.print_exc()
        return None

def find_and_copy_html_file():
    """Find and copy the HTML file to the correct location"""
    try:
        # Determine base directory
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        # Possible locations for the HTML file
        possible_locations = [
            os.path.join(base_dir, 'index.html'),
            os.path.join(base_dir, 'ui', 'index.html'),
            os.path.join(base_dir, 'dist', 'index.html'),
            os.path.join(base_dir, 'build', 'index.html'),
            os.path.join(os.path.dirname(base_dir), 'dist', 'index.html'),
            os.path.join(os.path.dirname(base_dir), 'index.html')
        ]

        # Find the HTML file
        html_path = None
        for location in possible_locations:
            if os.path.exists(location):
                logging.info(f"Found HTML file at: {location}")
                html_path = location
                break

        if not html_path:
            logging.error("Could not find index.html")
            return None

        # Create ui directory next to the executable/script
        dest_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd(), 'ui')
        os.makedirs(dest_dir, exist_ok=True)

        # Copy the HTML file
        dest_path = os.path.join(dest_dir, 'index.html')
        shutil.copy2(html_path, dest_path)  # Use copy2 to preserve metadata

        # Also copy assets if they exist
        assets_src = os.path.join(os.path.dirname(html_path), 'assets')
        if os.path.exists(assets_src):
            assets_dest = os.path.join(os.path.dirname(dest_path), 'assets')
            if os.path.exists(assets_dest):
                shutil.rmtree(assets_dest)
            shutil.copytree(assets_src, assets_dest)
            logging.info(f"Copied assets from {assets_src} to {assets_dest}")

        logging.info(f"Copied HTML from {html_path} to {dest_path}")
        return dest_path

    except Exception as e:
        logging.error(f"Error finding/copying HTML file: {e}")
        traceback.print_exc()
        return None

class Api:
    def __init__(self):
        self.router_manager = None
        self.window = None
        logging.info("API Class Initialized")

    def set_window(self, window):
        """Set the webview window reference"""
        self.window = window
        logging.info("Window reference set")

    def start_port_forward(self, data):
        """
        Main method to handle port forwarding configuration
        """
        try:
            # Log the received configuration for debugging
            logging.info(f"Starting port forwarding with data: {json.dumps(data, indent=2)}")

            # Validate required parameters
            if not data or not all(key in data for key in ['console', 'routerType', 'credentials']):
                logging.error("Missing required configuration parameters")
                return {
                    'success': False, 
                    'error': 'Invalid configuration: Missing required parameters'
                }

            # Extract configuration parameters
            console_type = data.get('console')
            router_type = data.get('routerType')
            router_ip = data.get('routerIP')
            credentials = data.get('credentials', {})
            target_device = data.get('targetDevice')

            # Validate credentials
            if not credentials.get('username') or not credentials.get('password'):
                logging.error("Invalid or missing credentials")
                return {
                    'success': False, 
                    'error': 'Invalid credentials: Username and password are required'
                }

            # Initialize router manager
            self.router_manager = RouterManager()
            
            # Set router IP if provided
            if router_ip:
                logging.info(f"Using manual router IP: {router_ip}")
                self.router_manager.router_ip = router_ip
            
            # Attempt to find router if IP not manually specified
            elif not self.router_manager.find_router():
                logging.error("Could not find router")
                return {
                    'success': False,
                    'error': 'Unable to locate router on the network'
                }
            
            # Set router type
            self.router_manager.router_type = router_type
            logging.info(f"Router type set to: {router_type}")

            # Attempt to log in to router
            self.router_manager.session.auth = (credentials['username'], credentials['password'])
            
            if not self.router_manager.login_to_router():
                logging.error("Router login failed")
                return {
                    'success': False,
                    'error': 'Router login failed. Check your credentials.'
                }
            
            # Determine target IP based on console type
            if console_type == 'dreamcast':
                logging.info("Processing Dreamcast configuration...")
                port_rules = get_dreamcast_port_rules()
                
                # Always use .98 IP for Dreamcast
                subnet_parts = self.router_manager.router_ip.split('.')[:3]
                target_ip = f"{'.'.join(subnet_parts)}.98"
                logging.info(f"Using Dreamcast IP: {target_ip}")
            
            elif console_type == 'saturn':
                logging.info("Processing Saturn configuration...")
                port_rules = [
                    {"protocol": "TCP", "external": 65432, "internal": 65432},
                    {"protocol": "UDP", "external": 20001, "internal": 20001},
                    {"protocol": "UDP", "external": 20002, "internal": 20002}
                ]
                
                # Determine target IP for Saturn
                if target_device == 'dreampi':
                    logging.info("Looking for DreamPi...")
                    target_ip = find_dreampi()
                    if not target_ip:
                        logging.error("Could not find DreamPi")
                        return {
                            'success': False,
                            'error': 'Could not find DreamPi on the network'
                        }
                    logging.info(f"Found DreamPi at: {target_ip}")
                
                else:  # target_device == 'pc'
                    logging.info("Getting local PC IP...")
                    target_ip = get_router_subnet_ip()
                    if not target_ip:
                        logging.error("Could not determine local PC IP")
                        return {
                            'success': False,
                            'error': 'Could not determine local PC IP'
                        }
                    logging.info(f"Using local PC IP: {target_ip}")
            
            else:
                logging.error(f"Invalid console type: {console_type}")
                return {
                    'success': False,
                    'error': 'Invalid console type'
                }

            # Setup port forwarding
            logging.info(f"Setting up port forwarding to {target_ip}...")
            if self.router_manager.setup_port_forward(target_ip, port_rules):
                logging.info("Port forwarding setup successful")
                return {
                    'success': True,
                    'ip': target_ip,
                    'ports': [f"{rule['protocol']} {rule['external']}" for rule in port_rules]
                }
            else:
                # Fallback for generic routers
                if router_type == "Generic":
                    logging.info("Generic router - providing manual configuration steps")
                    port_info = "\n".join([
                        f"- {rule['protocol']} Port {rule['external']} -> {target_ip}:{rule['internal']}"
                        for rule in port_rules
                    ])
                    return {
                        'success': False,
                        'error': f'Please configure these ports manually:\n{port_info}'
                    }
                
                logging.error("Port forwarding setup failed")
                return {
                    'success': False,
                    'error': 'Failed to configure port forwarding'
                }

        except Exception as e:
            logging.error(f"Unexpected error in port forwarding: {str(e)}")
            logging.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }

def main():
    # Setup comprehensive logging first
    log_file = setup_comprehensive_logging()
    
    try:
        # Create API instance
        api = Api()
        
        # Find and copy HTML file
        html_path = find_and_copy_html_file()
        
        if not html_path or not os.path.exists(html_path):
            logging.error("Could not find or copy HTML file")
            input("Press Enter to exit...")
            return

        logging.info(f"Using HTML path: {html_path}")

        # Set debug mode for development
        debug = not getattr(sys, 'frozen', False)

        # Create the main application window
        window = webview.create_window(
            'Retro Console Port Forward Setup',
            html_path,
            js_api=api,
            width=800,
            height=800,
            resizable=True,
            text_select=True,
            min_size=(600, 600)
        )
        
        # Set the window reference in the API
        api.set_window(window)
        
        # Start the webview application
        logging.info("Starting webview application")
        if platform.system() == "Windows":
            try:
                webview.start(gui="edgechromium", debug=debug)
            except Exception as e:
                logging.error(f"Failed to start with edgechromium: {e}")
                logging.info("Trying alternate WebView backend...")
                webview.start(debug=debug)
        else:
            webview.start(debug=debug)
    
    except Exception as e:
        logging.critical(f"Failed to start application: {str(e)}")
        logging.critical(traceback.format_exc())
        print(f"Critical error: {str(e)}")
        print("Check log file for more details.")
        input("Press Enter to exit...")

if __name__ == '__main__':
    main()