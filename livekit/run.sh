#!/bin/bash
# LiveKit Server launcher — LAN-only standalone deployment
# Usage: ./run.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting LiveKit Server (LAN-only)..."
echo "  API:     http://localhost:7880"
echo "  RTC TCP: 7881"
echo "  RTC UDP: 50000-60000"
echo ""

exec ./livekit-server --config config.yaml
