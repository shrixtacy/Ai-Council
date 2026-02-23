#!/usr/bin/env python3
"""
AI Council PyPI Publishing Script
=================================
This script helps publish AI Council to PyPI (Python Package Index).
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def run_command(cmd_list, description):
    """Run a command safely using a list to avoid shell parsing issues."""
    print(f"\n🔄 {description}...")
    # shell=True hata diya gaya hai (CodeRabbit Fix)
    result = subprocess.run(cmd_list, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error: {description} failed\n{result.stderr}")
        return False
    print(f"✅ {description} completed successfully")
    return True

def check_prerequisites():
    print("🔍 Checking prerequisites...")
    try:
        import build, twine
        print("✅ Build tools available")
        return True
    except ImportError:
        return run_command([sys.executable, "-m", "pip", "install", "build", "twine"], "Installing tools")

def validate_package():
    print("\n🔍 Validating configuration...")
    # project_root fixed hone ki wajah se ye files ab mil jayengi
    for f in ['pyproject.toml', 'README.md', 'LICENSE']:
        if not Path(f).exists():
            print(f"❌ Missing: {f}")
            return False
    return True

def build_package():
    print("\n🏗️ Building package...")
    for folder in ['dist', 'build']:
        if os.path.exists(folder):
            shutil.rmtree(folder) # Cross-platform cleanup
    return run_command([sys.executable, "-m", "build"], "Building package")

def upload_to_pypi(test=True):
    # Unused 'repository' variable removed (CodeRabbit Fix)
    cmd = [sys.executable, "-m", "twine", "upload"]
    if test: cmd += ["--repository", "testpypi"]
    cmd.append("dist/*")
    return run_command(cmd, f"Uploading to {'Test PyPI' if test else 'PyPI'}")

def main():
    print("🚀 AI Council PyPI Publishing Script")
    # Path logic fixed to point to repo root (CodeRabbit Fix)
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)
    
    if not (check_prerequisites() and validate_package() and build_package()):
        sys.exit(1)
    
    print("\n📦 Build Success! 1. TestPyPI, 2. Production, 3. Skip")
    choice = input("Choice: ").strip()
    if choice == "1": upload_to_pypi(test=True)
    elif choice == "2" and input("Confirm? (y/n): ").lower() == 'y':
        upload_to_pypi(test=False)

if __name__ == "__main__":
    main()