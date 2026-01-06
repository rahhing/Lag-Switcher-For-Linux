#!/bin/bash
# Quick setup script for arc macro

echo "=================================================="
echo "Arc Macro - Quick Setup"
echo "=================================================="
echo ""

# Check if on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✓ Linux detected - Full support available"
    
    # Check for tc
    if command -v tc &> /dev/null; then
        echo "✓ tc (traffic control) is installed"
    else
        echo "✗ tc is not installed"
        echo "  Installing tc..."
        sudo dnf install iproute-tc -y || sudo apt install iproute2 -y
    fi
    
    # Check for pynput
    if python3 -c "import pynput" 2>/dev/null; then
        echo "✓ pynput is installed"
    else
        echo "✗ pynput is not installed"
        echo "  Installing pynput..."
        pip3 install --user pynput
    fi
    
    # Authenticate sudo
    echo ""
    echo "Authenticating sudo (will ask for password)..."
    sudo -v
    
    if [ $? -eq 0 ]; then
        echo "✓ Sudo authenticated"
    else
        echo "✗ Sudo authentication failed"
        exit 1
    fi
    
    echo ""
    echo "=================================================="
    echo "Setup complete!"
    echo "=================================================="
    echo ""
    echo "To run the macro:"
    echo "  cd arc/"
    echo "  python3 macro.py"
    echo ""
    echo "Network interfaces available:"
    ip link show | grep -E "^[0-9]+" | awk '{print "  • " $2}' | sed 's/:$//' | grep -v "lo"
    
else
    echo "⚠️  Not on Linux - Fallback mode will be used"
    echo "   Install pynput: pip3 install --user pynput"
fi

echo ""
echo "=================================================="
