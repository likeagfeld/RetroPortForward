import os
import subprocess
import sys
import platform
import site
from pathlib import Path

def check_dependencies():
    """Install required Python packages"""
    print("Checking dependencies...")
    required_packages = [
        'pywebview',
        'requests',
        'pyinstaller',
        'pillow'
    ]
    
    for package in required_packages:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package],
                check=True
            )
            print(f"Installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"Error installing {package}: {e}")
            sys.exit(1)

def find_webview2_loader():
    """Find WebView2Loader.dll in site-packages"""
    if platform.system() != 'Windows':
        return None
        
    possible_paths = [
        *[os.path.join(p, 'webview', 'lib', 'WebView2Loader.dll') 
          for p in site.getsitepackages()],
        os.path.join(site.getusersitepackages(), 'webview', 'lib', 'WebView2Loader.dll'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found WebView2Loader.dll at: {path}")
            return path
            
    return None

def build_frontend():
    """Build the React frontend"""
    print("Building frontend...")
    
    npm_cmd = 'npm.cmd' if platform.system() == 'Windows' else 'npm'
    
    try:
        # Install dependencies
        print("Installing npm dependencies...")
        subprocess.run([npm_cmd, 'install'], check=True)
        
        # Build the frontend
        print("Building frontend application...")
        subprocess.run([npm_cmd, 'run', 'build'], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Error during frontend build: {e}")
        sys.exit(1)

def create_executable():
    """Create executable using PyInstaller"""
    print("Creating executable...")
    
    # Get WebView2 path for Windows
    webview2_path = None
    if platform.system() == 'Windows':
        webview2_path = find_webview2_loader()
        if not webview2_path:
            print("Warning: Could not find WebView2Loader.dll")

    # Base PyInstaller command
    pyinstaller_command = [
        'pyinstaller',
        '--name=RetroPortForward',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        '--hidden-import=webview.platforms.edgechromium',
    ]

    # Add data files
    if platform.system() == 'Windows':
        pyinstaller_command.extend([
            '--add-data=dist/index.html;ui',
            '--add-data=dist/assets;assets'
        ])
    else:
        pyinstaller_command.extend([
            '--add-data=dist/index.html:ui',
            '--add-data=dist/assets:assets'
        ])

    # Add WebView2 for Windows
    if webview2_path:
        sep = ';' if platform.system() == 'Windows' else ':'
        pyinstaller_command.append(f'--add-binary={webview2_path}{sep}webview/lib')

    # Add the main script
    pyinstaller_command.append('main.py')

    try:
        subprocess.run(pyinstaller_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error creating executable: {e}")
        sys.exit(1)

def main():
    # Store the current directory
    start_dir = os.getcwd()
    print(f"Starting build process in: {start_dir}")
    
    try:
        # Check dependencies
        check_dependencies()
        
        # Clean previous builds
        print("Cleaning previous builds...")
        if os.path.exists('dist'):
            for item in os.listdir('dist'):
                item_path = os.path.join('dist', item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        os.rmdir(item_path)
                except Exception as e:
                    print(f"Error removing {item_path}: {e}")
                    
        if os.path.exists('build'):
            for item in os.listdir('build'):
                item_path = os.path.join('build', item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        os.rmdir(item_path)
                except Exception as e:
                    print(f"Error removing {item_path}: {e}")
        
        if os.path.exists('RetroPortForward.spec'):
            os.remove('RetroPortForward.spec')
        
        # Build frontend
        build_frontend()
        
        # Create executable
        create_executable()
        
        print("\nPackage created successfully!")
        if platform.system() == 'Windows':
            print("Executable is at: dist/RetroPortForward.exe")
        else:
            print("Executable is at: dist/RetroPortForward")
            
    except Exception as e:
        print(f"Error during packaging: {e}")
        sys.exit(1)
    finally:
        # Always return to starting directory
        os.chdir(start_dir)

if __name__ == '__main__':
    main()