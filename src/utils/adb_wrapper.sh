#!/bin/bash
# ADB wrapper script to handle paths with spaces

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Execute ADB with all passed arguments
"$SCRIPT_DIR/adb" "$@"