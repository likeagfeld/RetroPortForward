import os
import subprocess
import shutil
import sys

def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous builds...")
    paths = ['dist', 'build', '__pycache__', 'RetroPortForward.spec']
    for path in paths:
        if os.path.exists(path):
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)

def build_frontend():
    """Build the React frontend"""
    print("Building frontend...")
    subprocess.run(['npm', 'install'], check=True, shell=True)
    subprocess.run(['npm', 'run', 'build'], check=True, shell=True)

def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable...")
    
    pyinstaller_cmd = [
        'pyinstaller',
        '--name=RetroPortForward',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        '--hidden-import=webview',
        '--hidden-import=webview.platforms.edgechromium',
        '--add-data=dist/index.html;ui',
        '--add-data=dist/assets;assets',
        'main.py'
    ]
    
    # Execute PyInstaller
    subprocess.run(pyinstaller_cmd, check=True)

def main():
    try:
        # Clean previous builds
        clean_build()
        
        # Build frontend
        build_frontend()
        
        # Build executable
        build_executable()
        
        print("\nBuild completed successfully!")
        print("Executable is at: dist/RetroPortForward.exe")
        
    except Exception as e:
        print(f"Error during build: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()