# Club Kinawa Coding Lab

A vibe coding workspace where kids build games and interactive projects through natural language conversation.

## Quick Start

```bash
cd /home/openclaw/ck-coding-lab
./setup.sh          # Install dependencies, init database
./deploy.sh         # Deploy to production (requires sudo)
```

Access: `https://clubkinawa.net/lab/login`

## Architecture

```
Kid (Browser)
    ↓ HTTPS
Nginx (clubkinawa.net/lab)
    ↓ Proxy to
Gunicorn (Flask App on :5006)
    ↓ SQLite
Database (ckcl.db)
    ↓ AI Gateway
OpenClaw API (Kimi K2.5 / Codex)
```

## File Structure

```
ck-coding-lab/
├── app.py                  # Flask app factory
├── database.py             # SQLite schema & migrations
├── auth.py                 # Authentication (PIN-based)
├── routes.py               # Auth API endpoints
├── project_routes.py       # Project & chat API
├── ai_client.py            # AI model integration
├── sandbox.py              # Code validation
├── static/
│   ├── css/style.css       # Dark theme UI
│   └── js/
│       ├── auth.js         # Login/logout
│       ├── projects.js     # Project gallery
│       ├── workspace.js    # Chat/Code/Preview tabs
│       └── sandbox.js      # Secure code execution
├── templates/
│   ├── login.html          # Kid login page
│   ├── projects.html       # Project list
│   └── workspace.html      # Coding workspace
├── requirements.txt        # Python deps
├── setup.sh                # Initial setup
├── deploy.sh               # Production deployment
├── ck-coding-lab.service   # systemd service
└── nginx-lab.conf          # Nginx configuration
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `dev-secret-key-change-in-production` |
| `CKCL_DB_PATH` | SQLite database path | `ckcl.db` |
| `OPENCLAW_GATEWAY_URL` | OpenClaw API gateway | `http://localhost:18789` |

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with username/PIN
- `POST /api/auth/logout` - Logout
- `POST /api/auth/register` - Create user (staff)
- `GET /api/auth/me` - Get current user

### Projects
- `GET /api/projects` - List user's projects
- `POST /api/projects` - Create new project
- `GET /api/projects/<id>` - Get project with chat history
- `PUT /api/projects/<id>` - Update project
- `DELETE /api/projects/<id>` - Delete project

### Chat & AI
- `POST /api/projects/<id>/chat` - Send message to AI
- `POST /api/projects/<id>/validate` - Validate code safety

### Versions
- `GET /api/projects/<id>/versions` - List saved versions
- `POST /api/projects/<id>/versions` - Save current version
- `GET /api/projects/<id>/versions/<vid>` - Get specific version

## Security

- PIN-based authentication (4 digits, bcrypt hashed)
- Session tokens with 24-hour expiry
- Code validation blocks dangerous patterns (eval, fetch, etc.)
- iframe sandbox with frame limit protection
- No network access from sandbox
- Parameterized SQL queries

## Deployment

### 1. Initial Setup

```bash
cd /home/openclaw/ck-coding-lab
./setup.sh
```

### 2. Configure Environment

```bash
export SECRET_KEY="your-secret-key-here"
export OPENCLAW_GATEWAY_URL="http://localhost:18789"
```

Or edit `ck-coding-lab.service` to set them permanently.

### 3. Deploy

```bash
./deploy.sh
```

### 4. Manual Nginx Step

Add contents of `nginx-lab.conf` to your nginx server block:

```bash
sudo nano /etc/nginx/sites-available/hariclaw.com
# Paste contents from nginx-lab.conf inside server block
sudo nginx -t
sudo systemctl reload nginx
```

## Management Commands

```bash
# Check service status
sudo systemctl status ck-coding-lab

# View logs
sudo journalctl -u ck-coding-lab -f

# Restart service
sudo systemctl restart ck-coding-lab

# Database backup
cp ckcl.db backups/ckcl-$(date +%Y%m%d).db

# Create admin user (interactive)
python3 -c "
from database import get_db
from auth import hash_pin, create_user
import sys

username = input('Username: ')
pin = input('4-digit PIN: ')

try:
    user = create_user(username, pin)
    print(f'Created user: {user[\"username\"]}')
except Exception as e:
    print(f'Error: {e}')
"
```

## Development

```bash
# Run locally (port 5000)
python app.py

# Run tests
python test_auth.py
python test_sandbox.py

# Test API
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "pin": "1234"}'
```

## Troubleshooting

**Service won't start:**
- Check logs: `sudo journalctl -u ck-coding-lab -n 50`
- Verify port 5006 not in use: `lsof -i :5006`
- Check permissions on ckcl.db

**Nginx 502 error:**
- Verify service is running: `systemctl status ck-coding-lab`
- Check SELinux: `sudo setsebool -P httpd_can_network_connect 1`

**AI not responding:**
- Verify OpenClaw gateway is running: `openclaw gateway status`
- Check environment variable: `echo $OPENCLAW_GATEWAY_URL`

## License

MIT - For Club Kinawa use

---
*Built with Flask, p5.js, and AI*