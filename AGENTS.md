# AGENTS.md - Club Kinawa Coding Lab

## Project Overview

**Name:** Club Kinawa Coding Lab  
**Purpose:** Vibe coding workspace where kids build games through natural language AI conversation  
**Category:** A (Application code - local authoring, VPS runtime)  
**URL:** https://clubkinawa.net/lab  

## Canonical Hosts

| Environment | Host | Path |
|-------------|------|------|
| **Local Dev** | terminus-OptiPlex-7050 | `~/ck-coding-lab-local/` |
| **VPS Runtime** | p5gHxcyh7WDx (162.212.153.134) | `/home/openclaw/ck-coding-lab/` |
| **Version Control** | GitHub | `behindthegarage/ck-coding-lab` |

## Setup Commands

```bash
# Clone (one-time)
git clone https://github.com/behindthegarage/ck-coding-lab.git ck-coding-lab-local
cd ck-coding-lab-local

# Install dependencies
pip install -r requirements.txt

# Create local dev database (do NOT copy production)
python3 -c "
import sqlite3, bcrypt
import os
os.remove('ckcl.db') if os.path.exists('ckcl.db') else None
db = sqlite3.connect('ckcl.db')
# Run migrations
db.executescript(open('database_migrations.py').read())
# Add test admin
db.execute('INSERT INTO users (username, pin_hash, role, is_active) VALUES (?, ?, ?, ?)',
    ('admin', bcrypt.hashpw(b'0303', bcrypt.gensalt()).decode(), 'admin', 1))
db.commit()
"
```

## Dev Commands

```bash
# Start local dev server
flask --app app run --port 5006 --debug

# Or with gunicorn (production-like)
gunicorn -w 2 -b 127.0.0.1:5006 --timeout 180 "app:create_app()"

# Run tests
python3 -m pytest test_auth.py test_sandbox.py -v

# Check health
curl http://localhost:5006/health
```

## Deployment

**Model:** Controlled VPS pull (manual deploy after GitHub push)

```bash
# 1. Edit locally, test
flask --app app run --port 5006

# 2. Commit and push
git add .
git commit -m "Description of changes"
git push origin main

# 3. SSH to VPS and deploy
ssh openclaw@162.212.153.134
cd /home/openclaw/ck-coding-lab
./deploy.sh  # Pulls latest, restarts service

# 4. Verify
curl https://clubkinawa.net/lab/health
```

## Service Map

| Service | Type | Details |
|---------|------|---------|
| **App Server** | systemd | `ck-coding-lab.service` (gunicorn, port 5006) |
| **Database** | SQLite | `ckcl.db` (production - do not touch) |
| **Reverse Proxy** | nginx | `/etc/nginx/sites-enabled/kinawa` (location /lab) |
| **Logs** | files | `/home/openclaw/ck-coding-lab/logs/` |

## Environment / Secrets

**Local dev:** Uses `ckcl.db` (created fresh, test data only)  
**VPS prod:** Uses `/home/openclaw/ck-coding-lab/ckcl.db` (real kid accounts - NEVER copy locally)

**Secrets handled on VPS only:**
- Kimi API key (in `ai_client.py` or env var)
- No local `.env` file (all config in code for simplicity)

## Verification Checklist

Before pushing:
- [ ] Local server starts without errors
- [ ] `/health` returns 200
- [ ] Can log in with test admin (admin/0303)
- [ ] No hardcoded localhost:18789 (OpenClaw gateway) references

After deploy:
- [ ] `curl https://clubkinawa.net/lab/health` returns 200
- [ ] Can log in on production
- [ ] AI chat works (test with simple prompt)

## Known Traps

| Trap | Why | Prevention |
|------|-----|------------|
| Copying prod DB locally | Contains real kid PINs | Always create fresh local DB |
| Calling OpenClaw gateway | Returns 405, breaks AI | Use direct Kimi API only |
| Forgetting to restart service | Changes not live | Always run `./deploy.sh` on VPS |
| SQLite lock conflicts | Multiple processes | Use `timeout` in connection, avoid long transactions |
| Caching old JS | Browser cache | Add `?v=N` cache-bust to script tags when changing JS |

## Docs Sync Rule

Update this file when:
- New routes added
- Database schema changes
- Deploy process changes
- New environment variables needed

## Rollback

```bash
# On VPS - quick rollback to previous commit
ssh openclaw@162.212.153.134
cd /home/openclaw/ck-coding-lab
git log --oneline -5  # find previous commit
git checkout <commit-hash>
sudo systemctl restart ck-coding-lab.service
```

## Local Authoring Workflow

1. **Edit** locally in `~/ck-coding-lab-local/`
2. **Test** locally with `flask --app app run`
3. **Commit** locally
4. **Push** to GitHub
5. **Deploy** via SSH + `./deploy.sh`
6. **Verify** production

**Emergency VPS edit:** If you must edit on VPS, run:
```bash
# On VPS after hotfix
git add . && git commit -m "HOTFIX: description"
git push origin main
# Then IMMEDIATELY on local:
cd ~/ck-coding-lab-local && git pull
```
