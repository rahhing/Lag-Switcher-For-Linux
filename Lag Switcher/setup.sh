#!/bin/bash
# Setup script for Network Lagger on Fedora Linux

echo "==================================="
echo "Network Lagger Setup"
echo "==================================="
echo ""

# Check if running on Fedora
if ! command -v dnf &> /dev/null; then
    echo "Warning: This script is designed for Fedora Linux"
    echo "You may need to install packages manually on your distribution"
    echo ""
fi

# Install system dependencies
echo "Installing system dependencies..."
sudo dnf install -y iproute-tc python3-tkinter python3-pip python3-devel

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install --user -r requirements.txt

# Make the script executable
echo ""
echo "Making lagger.py executable..."
chmod +x lagger.py

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "To run the application:"
echo "  ./lagger.py"
echo ""
echo "IMPORTANT: Before using, set your network interface:"
echo "  1. Find your interface: ip link show"
echo "  2. Update in the GUI (e.g., eth0, enp0s3, wlan0)"
echo ""
