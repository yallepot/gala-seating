#!/bin/bash

echo "========================================="
echo "GALA SEATING SYSTEM - QUICK START"
echo "========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.11 or higher"
    exit 1
fi

echo "✓ Python detected: $(python3 --version)"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

echo "✓ Virtual environment activated"
echo ""

# Install requirements
echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "✓ Dependencies installed"
echo ""

# Run the application
echo "========================================="
echo "Starting Gala Seating System..."
echo "========================================="
echo ""
echo "The application will be available at:"
echo "👉 http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python app.py
