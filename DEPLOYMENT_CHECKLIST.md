# Production Deployment Checklist

## Pre-Deployment Verification ✅

### Step 1: Run All Tests
```bash
cd /Users/ankitsaxena/slack-leave-bot
bash run_all_tests.sh
```

**Expected:** All 33 tests should pass

---

### Step 2: Configure Slack App for Interactive Components

**Required for Approval Workflow:**

1. **Go to:** https://api.slack.com/apps
2. **Select your app** (slack-leave-bot)
3. **Enable Socket Mode:**
   - Settings → Socket Mode → Enable
4. **Create App-Level Token:**
   - Basic Information → App-Level Tokens
   - Click "Generate Token and Scopes"
   - Name: `slack-leave-bot-socket`
   - Add scope: `connections:write`
   - Click "Generate"
   - **Copy the token** (starts with `xapp-`)
5. **Add to .env:**
   ```bash
   SLACK_APP_TOKEN=xapp-1-A0XXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXX
   ```

---

### Step 3: Configure Organizational Hierarchy

Edit the org hierarchy file with your real employees:

```bash
nano config/org_hierarchy.json
```

**Example:**
```json
{
  "employees": [
    {
      "email": "john.doe@company.com",
      "slack_user_id": "U123456",
      "name": "John Doe",
      "manager": "jane.manager@company.com",
      "department": "Engineering"
    },
    {
      "email": "alice.smith@company.com",
      "slack_user_id": "U234567",
      "name": "Alice Smith",
      "manager": "jane.manager@company.com",
      "department": "Engineering"
    }
  ],
  "approvers": [
    {
      "email": "jane.manager@company.com",
      "slack_user_id": "U345678",
      "name": "Jane Manager",
      "role": "manager",
      "department": "Engineering"
    }
  ],
  "hr_team": [
    {
      "email": "hr@company.com",
      "slack_user_id": "U456789",
      "name": "HR Team"
    }
  ]
}
```

**To get Slack user IDs:**
```bash
# In Slack, click user profile → More → Copy member ID
# Or use this API call:
curl -H "Authorization: Bearer YOUR_SLACK_BOT_TOKEN" \
  "https://slack.com/api/users.list" | jq '.members[] | {name: .real_name, id: .id, email: .profile.email}'
```

---

### Step 4: Configure Approval Rules

Edit `.env` to set your approval thresholds:

```bash
nano .env
```

**Configuration Examples:**

**Option A: All Leaves Require Approval**
```bash
# Regular leave
AUTO_APPROVE_DAYS=0          # No auto-approval
STANDARD_APPROVAL_DAYS=5     # Manager approval for 1-5 days
SENIOR_APPROVAL_DAYS=5       # Senior manager for 6+ days

# WFH
WFH_AUTO_APPROVE_DAYS=1      # Auto-approve 1-day WFH
WFH_REQUIRES_APPROVAL=true   # Enable WFH approval

# Approval workflow
APPROVAL_WORKFLOW_ENABLED=true
```

**Option B: Auto-Approve Short Leaves**
```bash
# Regular leave
AUTO_APPROVE_DAYS=2          # Auto-approve 1-2 day leaves
STANDARD_APPROVAL_DAYS=5     # Manager approval for 3-5 days
SENIOR_APPROVAL_DAYS=5       # Senior manager for 6+ days

# WFH
WFH_AUTO_APPROVE_DAYS=3      # Auto-approve WFH up to 3 days
WFH_REQUIRES_APPROVAL=true
```

---

### Step 5: Enable Approval Workflow

Ensure approval workflow is enabled:

```bash
# In .env
APPROVAL_WORKFLOW_ENABLED=true
```

---

### Step 6: Test Run (Dry Run)

Start the bot in test mode:

```bash
# Terminal 1: Start bot
python main.py

# Terminal 2: Start dashboard
cd dashboard
npm install  # First time only
node server.js

# Terminal 3: Watch logs
tail -f bot.log
```

**Verify:**
- ✅ Bot starts without errors
- ✅ Socket mode connects successfully
- ✅ Dashboard accessible at http://localhost:3001
- ✅ Database initialized

**Check logs for:**
```
✅ Bot initialized in POLLING mode
✅ Socket Mode handler started
✅ Approval workflow initialized
✅ Interactive handler initialized
✅ Org hierarchy loaded: 3 employees, 1 approvers
```

---

### Step 7: Test Messages

Post test messages in your Slack leave channel:

**Test 1: WFH Auto-Approve (1 day)**
```
WFH tomorrow
```
**Expected:**
- Bot detects WFH
- Auto-approves (if WFH_AUTO_APPROVE_DAYS >= 1)
- Sends thread reply confirming
- Checks Zoho for application

**Test 2: Leave Requires Approval (3 days)**
```
Taking leave Feb 15-17
```
**Expected:**
- Bot detects leave
- Sends approval request to manager
- Manager receives message with [Approve] [Reject] buttons
- Shows in dashboard: http://localhost:3001/api/approvals/pending

**Test 3: WFH Requires Approval (5 days)**
```
Working from home next week
```
**Expected:**
- Bot detects WFH
- Requires approval (5 days > WFH_AUTO_APPROVE_DAYS)
- Sends to manager with WFH label

---

### Step 8: Test Approval Flow

1. **Manager clicks "Approve" button**
   - Expected: Request marked as approved
   - Employee receives notification
   - Bot verifies in Zoho
   - Shows in dashboard: http://localhost:3001/api/approvals/stats

2. **Manager clicks "Reject" button**
   - Expected: Modal opens for rejection reason
   - Request marked as rejected
   - Employee notified with reason
   - HR notified (if configured)

---

### Step 9: Verify Dashboard

**Open dashboard:**
```bash
open http://localhost:3001
```

**Check endpoints:**
```bash
# Overall stats
curl http://localhost:3001/api/stats/overview?period=week

# Approval stats
curl http://localhost:3001/api/approvals/stats

# Pending approvals
curl http://localhost:3001/api/approvals/pending

# Recent approvals
curl http://localhost:3001/api/approvals/recent?limit=10

# Health check
curl http://localhost:3001/api/health/database
```

---

## Production Deployment

### Option 1: Run on Server (Recommended)

**1. Copy to production server:**
```bash
# On your local machine
tar -czf slack-leave-bot.tar.gz /Users/ankitsaxena/slack-leave-bot
scp slack-leave-bot.tar.gz user@your-server:/home/user/

# On server
ssh user@your-server
cd /home/user
tar -xzf slack-leave-bot.tar.gz
cd slack-leave-bot
```

**2. Install dependencies:**
```bash
# Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node.js (for dashboard)
cd dashboard
npm install
cd ..
```

**3. Configure environment:**
```bash
# Copy and edit .env
cp .env .env.production
nano .env.production
```

**4. Create systemd service for bot:**
```bash
sudo nano /etc/systemd/system/slack-leave-bot.service
```

**Content:**
```ini
[Unit]
Description=Slack Leave Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/user/slack-leave-bot
Environment="PATH=/home/user/slack-leave-bot/venv/bin"
ExecStart=/home/user/slack-leave-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**5. Create systemd service for dashboard:**
```bash
sudo nano /etc/systemd/system/slack-leave-dashboard.service
```

**Content:**
```ini
[Unit]
Description=Slack Leave Bot Dashboard
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/user/slack-leave-bot/dashboard
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**6. Start services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable slack-leave-bot
sudo systemctl enable slack-leave-dashboard
sudo systemctl start slack-leave-bot
sudo systemctl start slack-leave-dashboard
```

**7. Check status:**
```bash
sudo systemctl status slack-leave-bot
sudo systemctl status slack-leave-dashboard
```

**8. View logs:**
```bash
sudo journalctl -u slack-leave-bot -f
sudo journalctl -u slack-leave-dashboard -f
```

---

### Option 2: Run with Docker (Alternative)

**1. Create Dockerfile:**
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

**2. Create docker-compose.yml:**
```yaml
version: '3.8'
services:
  bot:
    build: .
    env_file: .env
    volumes:
      - ./bot.log:/app/bot.log
      - ./bot_analytics.db:/app/bot_analytics.db
    restart: unless-stopped

  dashboard:
    image: node:18-slim
    working_dir: /app
    volumes:
      - ./dashboard:/app
      - ./bot_analytics.db:/app/bot_analytics.db
    command: sh -c "npm install && node server.js"
    ports:
      - "3001:3001"
    restart: unless-stopped
```

**3. Run:**
```bash
docker-compose up -d
```

---

### Option 3: Run Locally (Development/Small Teams)

**1. Use screen or tmux:**
```bash
# Terminal 1: Bot
screen -S slack-bot
cd /Users/ankitsaxena/slack-leave-bot
python main.py
# Press Ctrl+A, D to detach

# Terminal 2: Dashboard
screen -S dashboard
cd /Users/ankitsaxena/slack-leave-bot/dashboard
node server.js
# Press Ctrl+A, D to detach
```

**2. Reattach to view:**
```bash
screen -r slack-bot
screen -r dashboard
```

---

## Post-Deployment Monitoring

### 1. Check Bot Health

```bash
# View logs
tail -f bot.log

# Check for errors
grep -i error bot.log

# Check approval activity
grep -E "(approval|WFH|Auto-approved)" bot.log | tail -20
```

### 2. Monitor Dashboard

```bash
# Health check
curl http://localhost:3001/api/health/database

# Stats
curl http://localhost:3001/api/stats/overview?period=today

# Pending approvals
curl http://localhost:3001/api/approvals/pending
```

### 3. Database Backup

```bash
# Backup analytics database
cp bot_analytics.db bot_analytics_backup_$(date +%Y%m%d).db

# Automated daily backup (add to crontab)
0 2 * * * cp /path/to/slack-leave-bot/bot_analytics.db /path/to/backups/bot_analytics_$(date +\%Y\%m\%d).db
```

---

## Troubleshooting

### Issue 1: Socket Mode Not Connecting

**Symptom:** "Failed to connect to Socket Mode"

**Solution:**
```bash
# Check SLACK_APP_TOKEN in .env
grep SLACK_APP_TOKEN .env

# Ensure it starts with xapp-
# Regenerate token if needed at https://api.slack.com/apps
```

### Issue 2: Approval Buttons Not Working

**Symptom:** Clicking approve/reject does nothing

**Solution:**
```bash
# Ensure Socket Mode handler is running
grep "Socket Mode handler" bot.log

# Check interactive handler initialized
grep "Interactive handler initialized" bot.log

# Verify APPROVAL_WORKFLOW_ENABLED=true
grep APPROVAL_WORKFLOW_ENABLED .env
```

### Issue 3: Manager Not Found

**Symptom:** "No manager found for employee"

**Solution:**
```bash
# Check org_hierarchy.json has correct mapping
cat config/org_hierarchy.json

# Ensure employee email matches Zoho email
# Ensure manager email is in approvers list
```

### Issue 4: Dashboard Not Loading

**Symptom:** Cannot access http://localhost:3001

**Solution:**
```bash
# Check if dashboard is running
ps aux | grep "node server.js"

# Check dashboard logs
tail -f dashboard/logs/dashboard.log

# Test manually
cd dashboard
node server.js
```

---

## Success Criteria

✅ **Bot Running:** `ps aux | grep "python main.py"` shows process
✅ **Socket Mode:** Logs show "Socket Mode handler started"
✅ **Dashboard:** http://localhost:3001 accessible
✅ **Approval Flow:** Manager receives approval requests with buttons
✅ **WFH Detection:** WFH messages auto-approved or route to approval
✅ **Zoho Verification:** Bot checks Zoho after approval
✅ **Analytics:** Dashboard shows stats and metrics

---

## What's Next After Deployment

### Week 1: Monitoring
- Watch bot.log for errors
- Monitor approval activity in dashboard
- Gather user feedback

### Week 2: Optimization
- Adjust AUTO_APPROVE_DAYS based on usage
- Tune WFH_AUTO_APPROVE_DAYS
- Add more employees to org_hierarchy.json

### Week 3+: Enhancements (Optional)
- Email notifications (configure SMTP in .env)
- SMS alerts (configure Twilio in .env)
- Custom message templates (edit config/templates.yaml)
- Historical data backfill (run scripts/backfill_historical_data.py)

---

## Quick Command Reference

```bash
# Start bot
python main.py

# Start dashboard
cd dashboard && node server.js

# Run tests
bash run_all_tests.sh

# View logs
tail -f bot.log

# Check approvals
curl http://localhost:3001/api/approvals/stats

# Restart services (if using systemd)
sudo systemctl restart slack-leave-bot
sudo systemctl restart slack-leave-dashboard
```

---

**Status:** Ready for Production Deployment ✅

**Next Action:** Choose deployment option and follow checklist above.
