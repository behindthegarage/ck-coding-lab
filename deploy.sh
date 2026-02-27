#!/bin/bash
# deploy.sh - Deploy Club Kinawa Coding Lab to production

set -e

echo "🚀 Deploying Club Kinawa Coding Lab..."

# Configuration
SERVICE_NAME="ck-coding-lab"
NGINX_CONF="/etc/nginx/sites-available/hariclaw.com"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Check if running as root for system commands
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Some operations require root privileges."
        echo "   Run with sudo if needed for system commands."
    fi
}

# Copy systemd service
echo "📋 Installing systemd service..."
if [ -f "${SERVICE_NAME}.service" ]; then
    sudo cp "${SERVICE_NAME}.service" "$SERVICE_FILE"
    sudo systemctl daemon-reload
    echo "✅ Service file installed"
else
    echo "❌ Service file not found: ${SERVICE_NAME}.service"
    exit 1
fi

# Check nginx config
echo "🌐 Checking nginx configuration..."
if [ -f "$NGINX_CONF" ]; then
    echo "✅ Nginx config exists at $NGINX_CONF"
    echo ""
    echo "⚠️  MANUAL STEP REQUIRED:"
    echo "   Add the contents of nginx-lab.conf to your nginx server block"
    echo "   Then run: sudo nginx -t && sudo systemctl reload nginx"
else
    echo "⚠️  Nginx config not found at expected location"
    echo "   You'll need to manually configure nginx for clubkinawa.net/lab"
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --user

# Initialize/update database
echo "🗄️  Initializing database..."
export CKCL_DB_PATH="/home/openclaw/ck-coding-lab/ckcl.db"
python3 -c "from database import init_db_full; init_db_full()"

# Create first staff user
echo ""
echo "👤 Create first staff user:"
read -p "Enter username for admin: " admin_user
read -sp "Enter 4-digit PIN: " admin_pin
echo ""

python3 << EOF
import sys
sys.path.insert(0, '/home/openclaw/ck-coding-lab')
from database import get_db
from auth import hash_pin

with get_db() as db:
    try:
        db.execute(
            "INSERT INTO users (username, pin_hash, is_active) VALUES (?, ?, 1)",
            ("$admin_user", hash_pin("$admin_pin"))
        )
        print(f"✅ User '$admin_user' created successfully")
    except Exception as e:
        print(f"⚠️  Error creating user: {e}")
EOF

# Start service
echo ""
echo "🚀 Starting service..."
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"
sleep 2

# Check status
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service is running"
    echo ""
    echo "🎮 Club Kinawa Coding Lab deployed!"
    echo ""
    echo "Access: https://clubkinawa.net/lab/login"
    echo ""
    echo "Useful commands:"
    echo "  Check status: sudo systemctl status $SERVICE_NAME"
    echo "  View logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "  Restart: sudo systemctl restart $SERVICE_NAME"
else
    echo "❌ Service failed to start"
    echo "Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi