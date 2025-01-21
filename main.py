import os
import sys
import json
import logging
import platform
import traceback
import shutil
from pathlib import Path
import time

# Ensure the script can import modules from its directory
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import local modules
from setup_dreampi import (
    RouterManager, 
    get_dreamcast_port_rules, 
    get_router_subnet_ip, 
    find_dreampi,
    RouterHandlers,
    log_message
)

class Api:
    def __init__(self):
        self.router_manager = None
        logging.info("API Class Initialized")

    def echo(self, message):
        """Test method to verify API connectivity"""
        logging.info(f"Echo received: {message}")
        return f"Backend received: {message}"

    def start_port_forward(self, data):
        """Handle port forwarding setup"""
        logging.info(f">>> start_port_forward called with data: {json.dumps(data, indent=2)}")
        try:
            # Extract and validate data
            console_type = data.get('console')
            router_type = data.get('routerType')
            credentials = data.get('credentials', {})
            router_ip = data.get('routerIP')
            target_device = data.get('targetDevice')

            logging.info(f"Processing request for {router_type} router...")

            # Initialize router manager
            self.router_manager = RouterManager(router_type)
            
            # Set router IP if provided
            if router_ip:
                logging.info(f"Using provided router IP: {router_ip}")
                self.router_manager.router_ip = router_ip
            elif not self.router_manager.find_router():
                logging.error("Could not find router")
                return {'success': False, 'error': 'Could not find router'}

            # Extract credentials
            username = credentials.get('username', '')
            password = credentials.get('password', '')

            logging.info("Attempting router login...")
            if not self.router_manager.login_to_router(username, password):
                logging.error("Router login failed")
                return {'success': False, 'error': 'Router login failed'}
            logging.info("Router login successful")

            # Get target device IP
            if console_type == 'dreamcast':
                target_device = get_dreampi_network_dreamcast_ip()
                if not target_device:
                    return {'success': False, 'error': 'Could not determine Dreamcast IP'}
            elif target_device == 'dreampi':
                target_device = find_dreampi()
                if not target_device:
                    return {'success': False, 'error': 'Could not find DreamPi on network'}
            elif target_device == 'pc':
                target_device = get_local_ip()
                if not target_device:
                    return {'success': False, 'error': 'Could not determine local PC IP'}

            # Perform port forwarding setup
            if not self.router_manager.setup_port_forward(target_device, console_type):
                logging.error("Port forwarding setup failed")
                return {'success': False, 'error': 'Port forwarding setup failed'}
            
            # Gather port forwarding details
            port_rules = self.router_manager.get_port_rules(console_type)
            return {
                'success': True,
                'ip': target_device,
                'ports': [f"{rule['protocol']} {rule['external']}" for rule in port_rules]
            }

        except Exception as e:
            logging.error(f"Error in port forwarding: {str(e)}")
            logging.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

def setup_logging():
    """Set up logging configuration"""
    if getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'port_forward.log')
    
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        return log_path
    except Exception as e:
        print(f"Logging setup failed: {e}")
        return None

def get_resource_path(relative_path):
    """Get absolute path to resource"""
    try:
        if getattr(sys, '_MEIPASS', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(base_path, relative_path)
    except Exception as e:
        logging.error(f"Error getting resource path: {e}")
        return None

def initialize_webview():
    """Initialize webview with proper configuration"""
    try:
        import webview
        logging.info("WebView imported successfully")
        
        # Remove the platforms initialization that was causing the error
        # and use a simpler initialization approach
        if platform.system() == 'Windows':
            # For Windows, specify the gui renderer directly
            webview.gui = 'edgechromium'
        
        # Log which renderer is being used
        logging.info(f"WebView GUI toolkit: {webview.gui}")
        return webview
    except Exception as e:
        logging.error(f"Error initializing WebView: {e}")
        return None

def main():
    # Setup logging first
    log_file = setup_logging()
    logging.info("Starting application...")

    try:
        # Initialize WebView
        webview = initialize_webview()
        if not webview:
            logging.error("Failed to initialize WebView")
            input("Press Enter to exit...")
            return

        # Get HTML path
        html_path = get_resource_path(os.path.join('ui', 'index.html'))
        if not html_path or not os.path.exists(html_path):
            logging.error(f"UI file not found at expected path: {html_path}")
            input("Press Enter to exit...")
            return

        logging.info(f"Found UI at: {html_path}")

        # Create API instance
        api = Api()

        # Create window with API exposure
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

        # Start the application
        logging.info("Starting WebView application...")
        webview.start(debug=True)

    except Exception as e:
        logging.critical(f"Critical error: {str(e)}")
        logging.critical(traceback.format_exc())
        print(f"A critical error occurred. Check {log_file} for details.")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()