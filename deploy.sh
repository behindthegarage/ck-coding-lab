#!/bin/bash
# deploy.sh - Deploy Club Kinawa Coding Lab to production

set -euo pipefail

echo "🚀 Deploying Club Kinawa Coding Lab..."

# Configuration
SERVICE_NAME="ck-coding-lab"
NGINX_CONF="/etc/nginx/sites-available/kinawa"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${APP_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"

if [ ! -x "$PYTHON_BIN" ] || [ ! -x "$PIP_BIN" ]; then
    echo "❌ Virtualenv not found at ${VENV_DIR}"
    echo "   Create it first: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Sync latest code before doing the rest of the deploy
if git -C "$APP_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    BRANCH="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
    if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
        BRANCH="main"
    fi

    if ! git -C "$APP_DIR" diff --quiet || ! git -C "$APP_DIR" diff --cached --quiet; then
        echo "❌ Refusing to deploy with uncommitted tracked changes in ${APP_DIR}"
        echo "   Commit or stash them first so git pull can fast-forward safely."
        git -C "$APP_DIR" status --short
        exit 1
    fi

    echo "🔄 Syncing latest code from origin/${BRANCH}..."
    git -C "$APP_DIR" fetch origin "$BRANCH"
    LOCAL_SHA="$(git -C "$APP_DIR" rev-parse HEAD)"
    REMOTE_SHA="$(git -C "$APP_DIR" rev-parse "origin/${BRANCH}")"

    if [ "$LOCAL_SHA" != "$REMOTE_SHA" ]; then
        git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
        echo "✅ Updated repo to $(git -C "$APP_DIR" rev-parse --short HEAD)"
    else
        echo "✅ Repo already up to date at $(git -C "$APP_DIR" rev-parse --short HEAD)"
    fi
else
    echo "⚠️  ${APP_DIR} is not a git checkout; skipping code sync"
fi

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
else
    echo "⚠️  Nginx config not found at expected location"
    echo "   You'll need to manually configure nginx for clubkinawa.net/lab"
fi

# Install dependencies into the app virtualenv
echo "📦 Installing Python dependencies into ${VENV_DIR}..."
"$PIP_BIN" install -r requirements.txt

# Initialize/update database
echo "🗄️  Initializing database..."
export CKCL_DB_PATH="/home/openclaw/ck-coding-lab/ckcl.db"
"$PYTHON_BIN" -c "from database import init_db_full; init_db_full()"

# Optionally create first admin user on a fresh install only
if [ -t 0 ]; then
    user_count=$("$PYTHON_BIN" - <<'PY'
import os
import sqlite3

db_path = os.environ['CKCL_DB_PATH']
conn = sqlite3.connect(db_path)
try:
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    print(cur.fetchone()[0])
finally:
    conn.close()
PY
)

    if [ "$user_count" = "0" ]; then
        echo ""
        echo "👤 No users found. Create first admin user:"
        read -r -p "Enter username for admin: " admin_user
        read -r -s -p "Enter 4-digit PIN: " admin_pin
        echo ""

        ADMIN_USER="$admin_user" ADMIN_PIN="$admin_pin" "$PYTHON_BIN" <<'PY'
import os
import sys
sys.path.insert(0, '/home/openclaw/ck-coding-lab')
from database import get_db
from auth import hash_pin

with get_db() as db:
    db.execute(
        "INSERT INTO users (username, pin_hash, role, is_active) VALUES (?, ?, 'admin', 1)",
        (os.environ['ADMIN_USER'], hash_pin(os.environ['ADMIN_PIN']))
    )
    print(f"✅ User '{os.environ['ADMIN_USER']}' created successfully")
PY
    else
        echo "👤 Existing users found (${user_count}); skipping admin bootstrap prompt"
    fi
else
    echo "👤 Non-interactive deploy; skipping admin bootstrap prompt"
fi

# Restart service
echo ""
echo "🚀 Restarting service..."
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
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
