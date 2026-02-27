#!/bin/bash
# setup.sh - Initial setup for Club Kinawa Coding Lab

set -e

echo "🎮 Setting up Club Kinawa Coding Lab..."

# Check if running from correct directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: Must run from ck-coding-lab directory"
    exit 1
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p static/uploads
mkdir -p backups

# Install Python dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt --user

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "from database import init_db_full; init_db_full()"

# Check environment
echo "🔧 Checking environment..."
if [ -z "$SECRET_KEY" ]; then
    echo "⚠️  Warning: SECRET_KEY not set. Using default (change in production!)"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Set environment variables in ck-coding-lab.service"
echo "2. Copy ck-coding-lab.service to /etc/systemd/system/"
echo "3. Add nginx configuration from nginx-lab.conf"
echo "4. Start the service: sudo systemctl start ck-coding-lab"
echo "5. Test: https://clubkinawa.net/lab/login"