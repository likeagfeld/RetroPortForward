import os
import sys
import site
import subprocess
import platform
import shutil
from pathlib import Path

def install_dependencies():
    """Install required Python packages"""
    print("Installing dependencies...")
    packages = [
        'pywebview==4.4.1',
        'pyinstaller',
        'requests'
    ]
    
    for package in packages:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", package], check=True)

def find_webview2_loader():
    """Find or download WebView2Loader.dll"""
    print("Looking for WebView2Loader.dll...")
    
    # Common locations for WebView2Loader.dll
    possible_paths = []
    
    # Add site-packages paths
    for site_dir in site.getsitepackages():
        possible_paths.append(os.path.join(site_dir, 'webview', 'lib', 'WebView2Loader.dll'))
        possible_paths.append(os.path.join(site_dir, 'webview', 'WebView2Loader.dll'))
    
    # Add user site-packages
    user_site = site.getusersitepackages()
    possible_paths.append(os.path.join(user_site, 'webview', 'lib', 'WebView2Loader.dll'))
    possible_paths.append(os.path.join(user_site, 'webview', 'WebView2Loader.dll'))
    
    # Add direct Python paths
    possible_paths.append(os.path.join(sys.prefix, 'Lib', 'site-packages', 'webview', 'lib', 'WebView2Loader.dll'))
    
    # Check all possible paths
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found WebView2Loader.dll at: {path}")
            return path
    
    # If not found, create lib directory and copy from Windows
    print("WebView2Loader.dll not found in Python paths, checking Windows system...")
    
    windows_paths = [
        os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Microsoft', 'EdgeWebView', 'Application', 'WebView2Loader.dll'),
        os.path.join(os.environ.get('ProgramFiles', ''), 'Microsoft', 'EdgeWebView', 'Application', 'WebView2Loader.dll'),
        os.path.join(os.environ.get('SystemRoot', ''), 'System32', 'WebView2Loader.dll')
    ]
    
    for path in windows_paths:
        if os.path.exists(path):
            print(f"Found system WebView2Loader.dll at: {path}")
            # Create destination directory
            dest_dir = os.path.join(os.getcwd(), 'webview', 'lib')
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, 'WebView2Loader.dll')
            # Copy the file
            shutil.copy2(path, dest_path)
            print(f"Copied WebView2Loader.dll to: {dest_path}")
            return dest_path
    
    print("WebView2Loader.dll not found!")
    return None

def build_project():
    """Build the project"""
    print("Building project...")
    
    # Clean previous builds
    for path in ['dist', 'build', '__pycache__']:
        if os.path.exists(path):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
            except Exception as e:
                print(f"Error cleaning {path}: {e}")
    
    if os.path.exists('RetroPortForward.spec'):
        try:
            os.remove('RetroPortForward.spec')
        except Exception as e:
            print(f"Error removing spec file: {e}")
    
    # Build frontend
    print("Building frontend...")
    subprocess.run(['npm', 'install'], shell=True, check=True)
    subprocess.run(['npm', 'run', 'build'], shell=True, check=True)
    
    # Find WebView2Loader.dll
    webview2_path = find_webview2_loader()
    if not webview2_path:
        print("ERROR: WebView2Loader.dll not found! Please install Microsoft Edge WebView2 Runtime.")
        return
    
    # Prepare PyInstaller command
    pyinstaller_cmd = [
        'pyinstaller',
        '--name=RetroPortForward',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        '--hidden-import=webview.platforms.edgechromium',
        '--add-data=dist/index.html;ui',
        '--add-data=dist/assets;assets',
        f'--add-binary={webview2_path};webview/lib',
        'main.py'
    ]
    
    # Execute PyInstaller
    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("\nBuild completed successfully!")
        print("Executable is at: dist/RetroPortForward.exe")
    except subprocess.CalledProcessError as e:
        print(f"Error during PyInstaller build: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_dependencies()
    build_project()