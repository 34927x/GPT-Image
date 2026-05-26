#!/bin/bash

echo "⚙️ Creating virtual environment (venv)..."
python3 -m venv venv

echo "📦 Activating venv and installing packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-local.txt

echo "🎭 Installing Playwright Chromium browser..."
playwright install chromium

echo "✅ Setup Complete!"
echo "To start the worker in this venv, run:"
echo "source venv/bin/activate"
echo "python3 local_worker.py"
