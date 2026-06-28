#!/bin/bash

echo "Stopping iPhone Photo Manager services..."

# Kill any process listening on the backend port 8000
echo "Freeing port 8000..."
fuser -k 8000/tcp 2>/dev/null || true

# Kill any lingering python processes running the app
echo "Killing python processes for server/app.py..."
pkill -f "python3 server/app.py" 2>/dev/null || true

echo "All services have been stopped successfully."
