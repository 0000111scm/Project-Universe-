#!/bin/bash
# Setup script for Project Universe GPU Simulator
# Installs all dependencies for AMD RX 570 GPU acceleration

echo "============================================"
echo "Project Universe - GPU Simulator Setup"
echo "============================================"

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create/activate virtual environment if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate venv (Windows)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

# Activate venv (Unix/Linux/Mac)
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "Installing dependencies..."

# Install base requirements
pip install --upgrade pip
pip install -r requirements.txt

# Try installing PyOpenCL with AMD backend
echo ""
echo "Attempting to install PyOpenCL for AMD GPU..."

# On Windows, need to handle Visual Studio build tools
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "Windows detected. Installing PyOpenCL..."
    pip install pyopencl
else
    echo "Unix/Linux detected. Installing PyOpenCL..."
    pip install pyopencl
fi

echo ""
echo "============================================"
echo "Setup complete!"
echo ""
echo "To verify GPU setup, run:"
echo "  python -c \"import pyopencl as cl; print([d.name for p in cl.get_platforms() for d in p.get_devices()])\""
echo ""
echo "To run stress tests:"
echo "  python tests/stress_test.py"
echo ""
echo "============================================"
