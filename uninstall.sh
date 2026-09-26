#!/bin/bash

PLIST_DEST="$HOME/Library/LaunchAgents/com.varuna.daemon.plist"

echo "Unloading daemon..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true

echo "Removing plist..."
rm -f "$PLIST_DEST"

echo "Uninstall complete."
