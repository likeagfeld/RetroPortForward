# router_handlers.py

import re
import json
import base64
import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import quote
from requests.auth import HTTPBasicAuth

class RouterHandlers:
    @staticmethod
    def get_handler(router_type):
        handlers = {
            "ASUS": ASUSHandler,
            "TP-Link": TPLinkHandler,
            "Netgear": NetgearHandler,
            "Linksys": LinksysHandler,
            "D-Link": DLinkHandler,
            "Cisco": CiscoHandler,
            "Belkin": BelkinHandler,
            "Buffalo": BuffaloHandler,
            "Zyxel": ZyxelHandler,
            "Huawei": HuaweiHandler,
            "Ubiquiti": UbiquitiHandler,
            "MikroTik": MikroTikHandler,
            "NETIS": NETISHandler,
            "Tenda": TendaHandler,
            "EnGenius": EnGeniusHandler,
            "Actiontec": ActiontecHandler,
            "AirTies": AirTiesHandler,
            "Arris": ArrisHandler,
            "Motorola": MotorolaHandler,
            "Sagemcom": SagemcomHandler,
            "Thomson": ThomsonHandler,
            "Technicolor": TechnicolorHandler,
            "Zoom": ZoomHandler,
            "Billion": BillionHandler,
            "SmartRG": SmartRGHandler,
            "Edimax": EdimaxHandler,
            "Comtrend": ComtrendHandler,
            "Pace": PaceHandler,
            "Xiaomi": XiaomiHandler,
            "Fios-G1100": FiosG1100Handler,
            "OpenWrt": OpenWrtHandler
        }
        return handlers.get(router_type, GenericHandler)

class RouterHandler:
    def __init__(self, session, router_ip):
        self.session = session
        self.router_ip = router_ip
        self.token = None
        
        # Configure session defaults
        self.session.verify = False  # Skip SSL verification
        self.session.timeout = 10    # Set reasonable timeout
        
        # Set common headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })

    def test_connection(self):
        """Test if the router is reachable"""
        try:
            response = self.session.get(f"http://{self.router_ip}/", timeout=5)
            return response.status_code < 400
        except Exception as e:
            logging.error(f"Router connection test failed: {str(e)}")
            return False

    def login(self, username, password):
        raise NotImplementedError()

    def setup_port_forward(self, client_ip, port_rules):
        raise NotImplementedError()

class ASUSHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.cgi"
            data = {
                "login_username": username,
                "login_passwd": password
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("asus_token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            rules_data = {
                "action_mode": "apply",
                "current_page": "Advanced_VirtualServer_Content.asp",
                "next_page": "Advanced_VirtualServer_Content.asp",
                "modified": "0",
                "action_script": "restart_firewall",
                "vts_enable_x": "1",
            }
            
            for i, rule in enumerate(port_rules):
                rules_data.update({
                    f"vts_desc_x_{i}": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    f"vts_port_x_{i}": str(rule['external']),
                    f"vts_ipaddr_x_{i}": client_ip,
                    f"vts_proto_x_{i}": rule['protocol'],
                    f"vts_protono_x_{i}": "0",
                })
            
            response = self.session.post(
                f"http://{self.router_ip}/start_apply.htm",
                data=rules_data,
                headers={"Cookie": f"asus_token={self.token}"}
            )
            return response.status_code == 200
        except Exception:
            return False

class FiosG1100Handler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"https://{self.router_ip}"
            auth = HTTPBasicAuth(username, password)
            response = self.session.get(login_url, auth=auth)
            if response.status_code == 200:
                self.session.auth = auth
                return True
            return False
        except Exception as e:
            print(f"Login error: {str(e)}")
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "destination_ip": client_ip,
                    "destination_port": str(rule['internal']),
                    "source_port": str(rule['external']),
                    "enabled": True
                }
                response = self.session.post(
                    f"https://{self.router_ip}/api/firewall/portforwarding",
                    json=data
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False     
            
class TPLinkHandler(RouterHandler):
    def login(self, username, password):
        try:
            # Modern TP-Link routers
            login_url = f"http://{self.router_ip}/cgi-bin/luci/;stok=/login?form=login"
            data = {
                "username": username,
                "password": self._encrypt_password(password)
            }
            response = self.session.post(login_url, json=data)
            if response.status_code == 200:
                self.token = response.json().get('data', {}).get('stok')
                return bool(self.token)
                
            # Legacy TP-Link routers
            login_url = f"http://{self.router_ip}/userRpm/LoginRpm.htm"
            auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
            self.session.headers.update({"Authorization": f"Basic {auth_string}"})
            response = self.session.get(login_url)
            return "Main" in response.text
        except Exception:
            return False

    def _encrypt_password(self, password):
        return hashlib.md5(password.encode()).hexdigest()

    def setup_port_forward(self, client_ip, port_rules):
        try:
            # Modern TP-Link routers
            if self.token:
                for rule in port_rules:
                    data = {
                        "protocol": rule['protocol'],
                        "externalPort": str(rule['external']),
                        "internalPort": str(rule['internal']),
                        "internalIP": client_ip,
                        "description": f"DreamPi_{rule['protocol']}_{rule['external']}"
                    }
                    response = self.session.post(
                        f"http://{self.router_ip}/cgi-bin/luci/;stok={self.token}/admin/port_forward/add",
                        json=data
                    )
                    if response.status_code != 200:
                        return False
                return True
                
            # Legacy TP-Link routers
            rules_str = ""
            for i, rule in enumerate(port_rules):
                rules_str += f"{rule['external']} {rule['external']} {rule['protocol']} {client_ip} Enabled DreamPi_{rule['protocol']}_{rule['external']},"
            
            data = {
                "port_forward_rules": rules_str,
                "Save": "Save"
            }
            response = self.session.post(
                f"http://{self.router_ip}/userRpm/VirtualServerRpm.htm",
                data=data
            )
            return "Settings saved" in response.text
        except Exception:
            return False

class NetgearHandler(RouterHandler):
    def login(self, username, password):
        try:
            # Modern Netgear routers use SOAP API
            login_url = f"http://{self.router_ip}/soap/server_sa"
            soap_data = f'''<?xml version="1.0" encoding="utf-8" standalone="no"?>
            <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
                <SOAP-ENV:Header>
                    <SessionID>A7D88AE69687E58D9A00</SessionID>
                </SOAP-ENV:Header>
                <SOAP-ENV:Body>
                    <Authenticate>
                        <Username>{username}</Username>
                        <Password>{password}</Password>
                    </Authenticate>
                </SOAP-ENV:Body>
            </SOAP-ENV:Envelope>'''
            
            headers = {
                'Content-Type': 'text/xml',
                'SOAPAction': 'http://purenetworks.com/HNAP1/Login'
            }
            
            response = self.session.post(login_url, data=soap_data, headers=headers)
            if response.status_code == 200:
                self.token = re.search(r'<SessionID>(.*?)</SessionID>', response.text).group(1)
                return bool(self.token)
            
            # Legacy Netgear routers
            login_url = f"http://{self.router_ip}/start.htm"
            auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
            self.session.headers.update({"Authorization": f"Basic {auth_string}"})
            response = self.session.get(login_url)
            return response.status_code == 200
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            if self.token:  # Modern Netgear
                for rule in port_rules:
                    soap_data = f'''<?xml version="1.0" encoding="utf-8" standalone="no"?>
                    <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
                        <SOAP-ENV:Header>
                            <SessionID>{self.token}</SessionID>
                        </SOAP-ENV:Header>
                        <SOAP-ENV:Body>
                            <AddPortMapping>
                                <PortMappingDescription>DreamPi_{rule['protocol']}_{rule['external']}</PortMappingDescription>
                                <InternalClient>{client_ip}</InternalClient>
                                <PortMappingProtocol>{rule['protocol']}</PortMappingProtocol>
                                <ExternalPort>{rule['external']}</ExternalPort>
                                <InternalPort>{rule['internal']}</InternalPort>
                            </AddPortMapping>
                        </SOAP-ENV:Body>
                    </SOAP-ENV:Envelope>'''
                    
                    response = self.session.post(
                        f"http://{self.router_ip}/soap/server_sa",
                        data=soap_data,
                        headers={'Content-Type': 'text/xml'}
                    )
                    if response.status_code != 200:
                        return False
                return True
            
            # Legacy Netgear
            for rule in port_rules:
                data = {
                    "protocol": rule['protocol'],
                    "external_port": rule['external'],
                    "internal_port": rule['internal'],
                    "internal_ip": client_ip,
                    "desc": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "apply": "Apply"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/forwarding.cgi",
                    data=data
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class LinksysHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/admin/login.cgi"
            data = {
                "username": username,
                "password": password
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("PHPSESSID")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "single_port": "1",
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "ext_port": str(rule['external']),
                    "int_port": str(rule['internal']),
                    "protocol": rule['protocol'],
                    "int_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/admin/forward.cgi",
                    data=data,
                    cookies={"PHPSESSID": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class DLinkHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.cgi"
            data = {
                "username": username,
                "password": base64.b64encode(password.encode()).decode()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("uid")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "public_port": str(rule['external']),
                    "private_port": str(rule['internal']),
                    "protocol": rule['protocol'],
                    "local_ip": client_ip,
                    "enabled": "1",
                    "schedule": "Always"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/portforward.cgi",
                    data=data,
                    cookies={"uid": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class CiscoHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login"
            data = {
                "username": username,
                "password": password,
                "submit": "Login"
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionid")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "protocol": rule['protocol'],
                    "internal_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/firewall/portforward/add",
                    data=data,
                    cookies={"sessionid": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class BelkinHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.php"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("session")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "internalPort": str(rule['internal']),
                    "externalPort": str(rule['external']),
                    "protocol": rule['protocol'],
                    "internalClient": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/forward.php",
                    data=data,
                    cookies={"session": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class BuffaloHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/admin.cgi"
            auth = HTTPBasicAuth(username, password)
            response = self.session.get(login_url, auth=auth)
            if response.status_code == 200:
                self.session.auth = auth
                return True
            return False
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/port_forward.cgi",
                    data=data
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class ZyxelHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.cgi"
            data = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sid")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "start_port": str(rule['external']),
                    "end_port": str(rule['external']),
                    "server_ip": client_ip,
                    "protocol": rule['protocol'],
                    "enable": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/nat-port-forward.cgi",
                    data=data,
                    cookies={"sid": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class HuaweiHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/api/system/user_login"
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            data = {
                "Username": username,
                "Password": password_hash
            }
            response = self.session.post(login_url, json=data)
            self.token = response.headers.get("Set-Cookie")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "Name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "Protocol": rule['protocol'],
                    "ExternalPort": str(rule['external']),
                    "InternalPort": str(rule['internal']),
                    "InternalClient": client_ip,
                    "Enable": 1
                }
                response = self.session.post(
                    f"http://{self.router_ip}/api/security/virtual_server",
                    json=data,
                    headers={"Cookie": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class UbiquitiHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"https://{self.router_ip}/api/auth/login"
            data = {
                "username": username,
                "password": password
            }
            response = self.session.post(login_url, json=data)
            self.token = response.json().get("token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "proto": rule['protocol'],
                    "src_port": str(rule['external']),
                    "dst_port": str(rule['internal']),
                    "dst_addr": client_ip,
                    "enabled": True
                }
                response = self.session.post(
                    f"https://{self.router_ip}/api/s/default/rest/portforward",
                    json=data,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class MikroTikHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/rest/system/user/login"
            data = {
                "name": username,
                "password": password
            }
            response = self.session.post(login_url, json=data)
            self.token = response.cookies.get("jwt")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "comment": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'].lower(),
                    "dst-port": str(rule['external']),
                    "to-ports": str(rule['internal']),
                    "to-addresses": client_ip,
                    "action": "dst-nat",
                    "chain": "dstnat",
                    "disabled": "false"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/rest/ip/firewall/nat",
                    json=data,
                    cookies={"jwt": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class NETISHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.php"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("NETIS_SESSION")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/port_forward.php",
                    data=data,
                    cookies={"NETIS_SESSION": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class TendaHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login/Auth"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, json=data)
            self.token = response.cookies.get("SESSIONID")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "outPort": str(rule['external']),
                    "inPort": str(rule['internal']),
                    "ipAddr": client_ip,
                    "enable": 1
                }
                response = self.session.post(
                    f"http://{self.router_ip}/goform/virtualServer",
                    json=data,
                    cookies={"SESSIONID": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class EnGeniusHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/cgi-bin/auth.cgi"
            data = {
                "username": username,
                "password": base64.b64encode(password.encode()).decode()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("session_id")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "public_port": str(rule['external']),
                    "private_port": str(rule['internal']),
                    "server_ip": client_ip,
                    "enable": "on"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/cgi-bin/port_forwarding.cgi",
                    data=data,
                    cookies={"session_id": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class ActiontecHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.cgi"
            data = {
                "username": username,
                "password": password
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionKey")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_client": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/port_forwarding.cgi",
                    data=data,
                    cookies={"sessionKey": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class AirTiesHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login"
            data = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, json=data)
            self.token = response.headers.get("X-Session-Token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": True
                }
                response = self.session.post(
                    f"http://{self.router_ip}/api/port_forward",
                    json=data,
                    headers={"X-Session-Token": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class ArrisHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("session")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "dest_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/port_forward.asp",
                    data=data,
                    cookies={"session": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class MotorolaHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/goform/login"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionid")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "public_port": str(rule['external']),
                    "private_port": str(rule['internal']),
                    "local_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/goform/PortForwarding",
                    data=data,
                    cookies={"sessionid": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class SagemcomHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/api/v1/login"
            data = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, json=data)
            self.token = response.json().get("token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "externalPort": str(rule['external']),
                    "internalPort": str(rule['internal']),
                    "destinationIp": client_ip,
                    "enabled": True
                }
                response = self.session.post(
                    f"http://{self.router_ip}/api/v1/nat/portforwarding",
                    json=data,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class ThomsonHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/cgi/login"
            data = {
                "user": username,
                "pwd": base64.b64encode(password.encode()).decode()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionid")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/cgi/portforwarding",
                    data=data,
                    cookies={"sessionid": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class TechnicolorHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("session")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "label": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "destination": client_ip,
                    "enable": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/portforward",
                    data=data,
                    cookies={"session": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class ZoomHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/goform/login"
            data = {
                "userName": username,
                "userPwd": hashlib.sha256(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionKey")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "ruleName": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "publicPort": str(rule['external']),
                    "privatePort": str(rule['internal']),
                    "localIP": client_ip,
                    "enable": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/goform/PortMapping",
                    data=data,
                    cookies={"sessionKey": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class BillionHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.cgi"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionid")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/portforward.cgi",
                    data=data,
                    cookies={"sessionid": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class SmartRGHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/api/v1/session"
            data = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, json=data)
            self.token = response.json().get("token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "wan_port": str(rule['external']),
                    "lan_port": str(rule['internal']),
                    "lan_ip": client_ip,
                    "enabled": True
                }
                response = self.session.post(
                    f"http://{self.router_ip}/api/v1/nat/port-forward",
                    json=data,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class EdimaxHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/cgi-bin/login.cgi"
            data = {
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("session_id")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "public_port": str(rule['external']),
                    "private_port": str(rule['internal']),
                    "ip_addr": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/cgi-bin/port_forwarding.cgi",
                    data=data,
                    cookies={"session_id": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class ComtrendHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login.cgi"
            data = {
                "username": username,
                "password": base64.b64encode(password.encode()).decode()
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sessionKey")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_client": client_ip,
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/nat/portforward.cgi",
                    data=data,
                    cookies={"sessionKey": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class PaceHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/login"
            data = {
                "username": username,
                "password": hashlib.sha256(password.encode()).hexdigest()
            }
            response = self.session.post(login_url, json=data)
            self.token = response.json().get("access_token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "description": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "protocol": rule['protocol'],
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": True
                }
                response = self.session.post(
                    f"http://{self.router_ip}/api/port-forwarding",
                    json=data,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class XiaomiHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/cgi-bin/luci/api/xqsystem/login"
            nonce = self.session.get(f"http://{self.router_ip}/cgi-bin/luci/api/xqsystem/nonce").json().get("nonce")
            password_hash = hashlib.sha1(f"{password}{nonce}".encode()).hexdigest()
            data = {
                "username": username,
                "password": password_hash,
                "nonce": nonce
            }
            response = self.session.post(login_url, json=data)
            self.token = response.json().get("token")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "proto": rule['protocol'].lower(),
                    "external_port": str(rule['external']),
                    "internal_port": str(rule['internal']),
                    "internal_ip": client_ip,
                    "enabled": True
                }
                response = self.session.post(
                    f"http://{self.router_ip}/cgi-bin/luci/api/xqsystem/port_forward",
                    json=data,
                    headers={"Authorization": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class OpenWrtHandler(RouterHandler):
    def login(self, username, password):
        try:
            login_url = f"http://{self.router_ip}/cgi-bin/luci/admin/login"
            data = {
                "luci_username": username,
                "luci_password": password
            }
            response = self.session.post(login_url, data=data)
            self.token = response.cookies.get("sysauth")
            return bool(self.token)
        except Exception:
            return False

    def setup_port_forward(self, client_ip, port_rules):
        try:
            for rule in port_rules:
                data = {
                    "name": f"DreamPi_{rule['protocol']}_{rule['external']}",
                    "proto": rule['protocol'].lower(),
                    "src_port": str(rule['external']),
                    "dest_port": str(rule['internal']),
                    "dest_ip": client_ip,
                    "target": "DNAT",
                    "enabled": "1"
                }
                response = self.session.post(
                    f"http://{self.router_ip}/cgi-bin/luci/admin/network/firewall/forwards",
                    data=data,
                    cookies={"sysauth": self.token}
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception:
            return False

class GenericHandler(RouterHandler):
    def login(self, username, password):
        try:
            # Try multiple common authentication methods
            auth_methods = [
                self._try_basic_auth,
                self._try_form_auth,
                self._try_digest_auth
            ]
            
            for method in auth_methods:
                if method(username, password):
                    return True
            
            return False
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            return False

    def _try_basic_auth(self, username, password):
        try:
            # Set basic auth
            self.session.auth = (username, password)
            
            # Try to access router's homepage
            response = self.session.get(f"http://{self.router_ip}/", timeout=5)
            
            # Check if auth was successful (no 401/403 status)
            if response.status_code < 400:
                logging.info("Basic auth successful")
                return True
                
            return False
        except Exception as e:
            logging.debug(f"Basic auth failed: {str(e)}")
            return False

    def _try_form_auth(self, username, password):
        try:
            # Common form login endpoints
            login_paths = [
                '/login.cgi',
                '/login.asp',
                '/login.htm',
                '/login',
                '/cgi-bin/login'
            ]
            
            # Try each login path
            for path in login_paths:
                try:
                    # Common form data patterns
                    form_data_variants = [
                        {'username': username, 'password': password},
                        {'user': username, 'pass': password},
                        {'login': username, 'password': password},
                        {'admin_name': username, 'admin_pwd': password}
                    ]
                    
                    for form_data in form_data_variants:
                        response = self.session.post(
                            f"http://{self.router_ip}{path}",
                            data=form_data,
                            timeout=5,
                            allow_redirects=True
                        )
                        
                        # Check if login was successful
                        if response.status_code < 400:
                            logging.info(f"Form auth successful using {path}")
                            return True
                            
                except Exception as e:
                    logging.debug(f"Form auth attempt failed for {path}: {str(e)}")
                    continue
            
            return False
        except Exception as e:
            logging.debug(f"Form auth failed: {str(e)}")
            return False

    def _try_digest_auth(self, username, password):
        try:
            from requests.auth import HTTPDigestAuth
            
            # Try digest authentication
            digest_auth = HTTPDigestAuth(username, password)
            response = self.session.get(
                f"http://{self.router_ip}/",
                auth=digest_auth,
                timeout=5
            )
            
            if response.status_code < 400:
                logging.info("Digest auth successful")
                self.session.auth = digest_auth
                return True
                
            return False
        except Exception as e:
            logging.debug(f"Digest auth failed: {str(e)}")
            return False

    def setup_port_forward(self, client_ip, port_rules):
        """
        For generic routers, we just provide instructions
        """
        # Generate port forwarding instructions
        instructions = []
        for rule in port_rules:
            instructions.append(
                f"- Forward {rule['protocol']} port {rule['external']} to {client_ip}:{rule['internal']}"
            )
        
        # Log the instructions
        logging.info("Generic router - manual configuration required")
        logging.info("Port forwarding instructions:")
        for instruction in instructions:
            logging.info(instruction)
        
        return False  # Return False to trigger manual instructions in the UI

# Export all handlers
__all__ = [
    'RouterHandlers',
    'RouterHandler',
    'GenericHandler',
    'ASUSHandler',
    'TPLinkHandler',
    'NetgearHandler',
    'LinksysHandler',
    'DLinkHandler',
    'CiscoHandler',
    'BelkinHandler',
    'BuffaloHandler',
    'ZyxelHandler',
    'HuaweiHandler',
    'UbiquitiHandler',
    'MikroTikHandler',
    'NETISHandler',
    'TendaHandler',
    'EnGeniusHandler',
    'ActiontecHandler',
    'AirTiesHandler',
    'ArrisHandler',
    'MotorolaHandler',
    'SagemcomHandler',
    'ThomsonHandler',
    'TechnicolorHandler',
    'ZoomHandler',
    'BillionHandler',
    'SmartRGHandler',
    'EdimaxHandler',
    'ComtrendHandler',
    'PaceHandler',
    'XiaomiHandler',
    'OpenWrtHandler'
]