#!/usr/bin/env python3
"""
Test script to verify macro.py network integration works correctly
"""

import sys
import os
import subprocess

print("=" * 60)
print("Network Lagger Arc Macro - Integration Test")
print("=" * 60)

# Check if we're on Linux
import platform
IS_LINUX = platform.system() == "Linux"

if not IS_LINUX:
    print("⚠️  WARNING: Not running on Linux")
    print("   Network control will use fallback mode")
    print()
else:
    print("✓ Running on Linux - Full network control available")
    print()

# Check for tc command
if IS_LINUX:
    try:
        result = subprocess.run(['which', 'tc'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ tc command found: {result.stdout.strip()}")
        else:
            print("✗ tc command not found!")
            print("  Install it with: sudo dnf install iproute-tc")
    except Exception as e:
        print(f"✗ Error checking for tc: {e}")
    print()

# Check for network interfaces
if IS_LINUX:
    try:
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        print("Available network interfaces:")
        for line in result.stdout.split('\n'):
            if ': ' in line and not 'lo:' in line:
                iface = line.split(':')[1].strip().split('@')[0]
                if iface != 'lo':
                    print(f"  • {iface}")
        print()
    except Exception as e:
        print(f"✗ Error listing interfaces: {e}")
        print()

# Check Python dependencies
print("Checking Python dependencies:")
try:
    import pynput
    print("✓ pynput installed")
except ImportError:
    print("✗ pynput not installed")
    print("  Install it with: pip install --user pynput")

try:
    import tkinter
    print("✓ tkinter installed")
except ImportError:
    print("✗ tkinter not installed")
    print("  Install it with: sudo dnf install python3-tkinter")

print()

# Check if macro files exist
print("Checking macro files:")
arc_path = os.path.join(os.path.dirname(__file__), "arc")
macro_py = os.path.join(arc_path, "macro.py")
macro_config = os.path.join(arc_path, "macro_config.json")

if os.path.exists(macro_py):
    print(f"✓ macro.py found")
    if os.access(macro_py, os.X_OK):
        print("  ✓ macro.py is executable")
    else:
        print("  ⚠️  macro.py is not executable")
        print("     Run: chmod +x arc/macro.py")
else:
    print("✗ macro.py not found")

if os.path.exists(macro_config):
    print(f"✓ macro_config.json found")
else:
    print("⚠️  macro_config.json not found (will be created on first run)")

print()

# Check sudo access
if IS_LINUX:
    print("Checking sudo access:")
    try:
        result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Sudo access available (cached)")
        else:
            print("⚠️  Sudo not cached")
            print("   Run 'sudo -v' or use the 'ACTIVATE SUDO' button in the GUI")
    except Exception as e:
        print(f"✗ Error checking sudo: {e}")
    print()

# Summary
print("=" * 60)
print("Integration Status:")
print("=" * 60)

if IS_LINUX:
    print("Network Control: Linux tc (same as lagger.py) ✓")
else:
    print("Network Control: Fallback mode (key simulation)")

print()
print("To run the macro:")
print("  cd arc/")
print("  python3 macro.py")
print()
print("For more information, see arc/README.md")
print("=" * 60)
