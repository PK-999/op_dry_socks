#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
if [ ! -f config.json ]; then
    cp config.json.example config.json
    chmod 600 config.json
fi

PYTHON_PATH="$DIR/.venv/bin/python3"
SCRIPT_PATH="$DIR/main.py"
PLIST_SRC="$DIR/com.varuna.daemon.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.varuna.daemon.plist"
mkdir -p "$HOME/Library/LaunchAgents"

echo "Generating plist..."
sed -e "s|{{PYTHON_PATH}}|$PYTHON_PATH|g" \
    -e "s|{{SCRIPT_PATH}}|$SCRIPT_PATH|g" \
    -e "s|{{WORKING_DIR}}|$DIR|g" \
    "$PLIST_SRC" > "$PLIST_DEST"

echo "Loading daemon..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Operation Dry Socks installed and running!"
