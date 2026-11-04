#!/usr/bin/env bash
# One command to start the website on Mac / Linux:   bash run.sh
cd "$(dirname "$0")"
if [ ! -d venv ]; then
  echo "First time setup: creating a private Python environment..."
  python3 -m venv venv || { echo "Python 3 is required: https://www.python.org/downloads/"; exit 1; }
  ./venv/bin/pip install --upgrade pip
  ./venv/bin/pip install -r requirements.txt || echo "Some packages failed - the site may run in demo mode."
fi
echo "Starting DEEPFACE-ASD at http://127.0.0.1:5000  (press Ctrl+C to stop)"
./venv/bin/python app.py
