# 🚀 Quick Start Guide - Slack Leave Bot

## Ready to Use in 5 Minutes!

### Prerequisites

- Python 3.8+
- Node.js 14+
- Slack workspace admin access
- Zoho People account (optional)

---

## Step 1: Configure Slack App (2 minutes)

### Enable Socket Mode

1. Go to https://api.slack.com/apps
2. Select your Slack app
3. Navigate to **Settings → Socket Mode**
4. Toggle **Enable Socket Mode** to ON
5. Click **Generate Token and Scopes**
   - Name: `socket-token`
   - Scope: `connections:write`
   - Click **Generate**
   - **Copy the token** (starts with `xapp-`)

### Enable Interactivity

1. Go to **Features → Interactivity & Shortcuts**
2. Toggle **Interactivity** to ON
3. (Socket Mode handles the URL automatically)
4. Click **Save Changes**

### Reinstall App (if prompted)

---

## Step 2: Update Configuration (1 minute)

### Edit `.env` File

```bash
# Enable approval workflow
APPROVAL_WORKFLOW_ENABLED=true

# Paste your Socket Mode token from Step 1
SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXXXX

# Add HR user IDs (find in Slack → View Profile → ... → Copy member ID)
HR_USER_IDS=U12345ABCDE,U67890FGHIJ
```

### Edit `config/org_hierarchy.json`

Replace example data with your real employees:

```json
{
  "organization": {
    "name": "Your Company",
    "employees": [
      {
        "email": "john.doe@yourcompany.com",
        "name": "John Doe",
        "slack_id": "U01234ABCDE",  // Get from Slack profile
        "department": "eng",
        "manager": "jane.smith@yourcompany.com",
        "position": "Software Engineer",
        "employee_id": "EMP001"
      },
      {
        "email": "jane.smith@yourcompany.com",
        "name": "Jane Smith",
        "slack_id": "U04567DEFGH",
        "department": "eng",
        "manager": null,
        "position": "Engineering Manager",
        "employee_id": "MGR001"
      }
    ]
  }
}
```

**Note:** Leave `manager: null` for top-level managers

---

## Step 3: Install Dependencies (1 minute)

### Python Dependencies

```bash
pip3 install --break-system-packages \
  slack-sdk \
  python-dotenv \
  requests \
  dateparser \
  python-dateutil \
  pyyaml
```

### Node.js Dependencies

```bash
cd dashboard
npm install
cd ..
```

---

## Step 4: Start the Bot (30 seconds)

### Terminal 1: Start Bot

```bash
python main.py
```

**Expected Output:**
```
✅ Database initialized
✅ Analytics collector initialized (enabled=True)
✅ Template engine initialized
✅ Notification router initialized
✅ Verification workflow initialized (grace period: 30min)
✅ Organizational hierarchy loaded
✅ Approval workflow engine initialized
✅ Socket Mode initialized for interactive components
Bot initialized successfully
```

### Terminal 2: Start Dashboard

```bash
cd dashboard
node server.js
```

**Expected Output:**
```
Database connected: /path/to/bot_analytics.db
Dashboard server running on http://localhost:3001
```

---

## Step 5: Test It! (30 seconds)

### Test 1: Auto-Approve (1-2 days)

Post in your Slack leave channel:
```
I'll be on leave tomorrow
```

**Expected:**
- ✅ Bot processes message
- ✅ Auto-approved (1 day ≤ 2 days)
- ✅ Checks Zoho
- ✅ Sends confirmation or reminder

### Test 2: Manager Approval (3+ days)

Post in your Slack leave channel:
```
Taking leave from Feb 15 to Feb 19
```

**Expected:**
- ✅ Bot detects 5 days
- ✅ Requires approval
- ✅ Manager receives message with buttons:

```
┌─────────────────────────────────────┐
│ 📝 Leave Approval Request           │
├─────────────────────────────────────┤
│ Your Name has requested leave       │
│ Dates: 2026-02-15 to 2026-02-19    │
│ Duration: 5 days                    │
│ Your approval level: 1/1            │
├─────────────────────────────────────┤
│ [✅ Approve] [❌ Reject] [ℹ️ Info]  │
└─────────────────────────────────────┘
```

- ✅ Manager clicks **Approve**
- ✅ Employee notified
- ✅ Bot checks Zoho
- ✅ Sends confirmation or reminder

### Test 3: Check Dashboard

Open browser: http://localhost:3001

**You should see:**
- 📊 Total Leaves
- ✅ Compliant Count
- ⚠️ Non-Compliant Count
- 🔔 Pending Reminders
- 📈 Compliance Rate
- 📉 Trend Chart
- 📋 Recent Events

---

## Common Issues & Solutions

### Issue 1: Socket Mode Not Connecting

**Error:** `Socket Mode disabled: No valid SLACK_APP_TOKEN`

**Solution:**
1. Check `.env` has `SLACK_APP_TOKEN=xapp-...`
2. Verify token starts with `xapp-`
3. Ensure no spaces or quotes around token
4. Restart bot

### Issue 2: Interactive Buttons Not Working

**Error:** Buttons appear but nothing happens when clicked

**Solution:**
1. Verify Socket Mode is **enabled** in Slack app settings
2. Check bot logs show: "Socket Mode connected successfully"
3. Ensure Interactivity is **enabled** in app settings
4. Restart bot and dashboard

### Issue 3: Employee Not Found

**Error:** `Employee not found in org hierarchy`

**Solution:**
1. Edit `config/org_hierarchy.json`
2. Add employee with correct email and Slack ID
3. Get Slack ID: Profile → ... → Copy member ID
4. Restart bot (reloads org hierarchy)

### Issue 4: Dashboard Shows No Data

**Solution:**
```bash
# Create test data
python create_test_data.py

# Refresh dashboard
# http://localhost:3001
```

### Issue 5: Approval Workflow Not Triggering

**Check:**
```bash
# Verify in .env
APPROVAL_WORKFLOW_ENABLED=true  # Must be 'true'

# Check bot logs
# Should show: "Approval Workflow: ENABLED"
```

---

## Quick Reference

### Approval Tiers

| Leave Duration | Approval Required          |
|----------------|----------------------------|
| 1-2 days       | ❌ Auto-approved           |
| 3-5 days       | ✅ Manager approval        |
| 6+ days        | ✅ Manager + Senior Manager|

### Reminder Levels

| Time After     | Action                     |
|----------------|----------------------------|
| 12 hours       | First followup (DM)        |
| 48 hours       | Second escalation (DM + Thread) |
| 72 hours       | Urgent (DM + Admin)        |

### Dashboard Endpoints

| Endpoint                      | Purpose                    |
|-------------------------------|----------------------------|
| http://localhost:3001         | Main dashboard UI          |
| /api/stats/overview           | Overview statistics        |
| /api/health/database          | Database health check      |
| /api/events/recent            | Recent leave events        |
| /api/reminders/active         | Active reminders           |

### Useful Commands

```bash
# Check if bot is running
ps aux | grep "python main.py"

# Check if dashboard is running
lsof -ti:3001

# Stop dashboard
lsof -ti:3001 | xargs kill

# View bot logs
tail -f bot.log

# Check database
sqlite3 bot_analytics.db "SELECT COUNT(*) FROM leave_events;"

# Restart everything
# Kill processes, then:
python main.py
cd dashboard && node server.js
```

---

## Advanced Configuration

### Customize Auto-Approve Threshold

Edit `.env`:
```bash
AUTO_APPROVE_DAYS=3  # Change from 2 to 3 days
```

### Customize Approval Timeout

Edit `.env`:
```bash
APPROVAL_TIMEOUT_HOURS=24  # Change from 48 to 24 hours
```

### Customize Reminder Intervals

Edit `.env`:
```bash
VERIFICATION_RE_CHECK_INTERVALS=6,12,24  # 6hr, 12hr, 24hr
```

### Add More Employees

Edit `config/org_hierarchy.json`:
```json
{
  "email": "new.employee@company.com",
  "name": "New Employee",
  "slack_id": "U09876ZYXWV",  // Get from Slack
  "department": "eng",
  "manager": "manager@company.com",
  "position": "Engineer",
  "employee_id": "EMP999"
}
```

### Mark as Senior Manager

Add to employee in `org_hierarchy.json`:
```json
{
  "email": "senior@company.com",
  ...
  "is_senior_manager": true  // Add this line
}
```

### Mark as HR

Add to employee in `org_hierarchy.json`:
```json
{
  "email": "hr@company.com",
  ...
  "is_hr": true  // Add this line
}
```

---

## Getting Help

### Log Files

```bash
# Bot logs
cat bot.log

# Last 50 lines
tail -50 bot.log

# Follow in real-time
tail -f bot.log
```

### Validation Scripts

```bash
# Test bot initialization
python test_initialization.py

# Validate environment
python validate_env.py

# Create test data
python create_test_data.py

# Verify dashboard data
python verify_dashboard_data.py
```

### Documentation

- `FINAL_SUMMARY.md` - Complete project summary
- `PHASE_5_COMPLETE.md` - Approval workflow details
- `CODE_REVIEW_REPORT.md` - Code quality report
- `STEP_*_COMPLETE.md` - Integration steps

---

## Production Deployment Tips

### Run in Background

```bash
# Bot
nohup python main.py > bot.log 2>&1 &

# Dashboard
cd dashboard
nohup node server.js > dashboard.log 2>&1 &
```

### Use Process Manager

```bash
# Install PM2
npm install -g pm2

# Start bot
pm2 start main.py --name slack-bot

# Start dashboard
cd dashboard
pm2 start server.js --name dashboard

# Monitor
pm2 status
pm2 logs

# Auto-restart on reboot
pm2 startup
pm2 save
```

### Database Backup

```bash
# Backup database
cp bot_analytics.db bot_analytics_$(date +%Y%m%d).db

# Automated daily backup
crontab -e
# Add: 0 2 * * * cp /path/to/bot_analytics.db /backups/bot_analytics_$(date +\%Y\%m\%d).db
```

---

## Success! 🎉

Your Slack Leave Bot is now running with:

- ✅ Advanced date parsing
- ✅ Manager approval workflow
- ✅ Interactive Slack buttons
- ✅ Multi-level reminders
- ✅ Real-time analytics
- ✅ Live dashboard
- ✅ HR override capabilities

**Enjoy your enhanced leave management system!**

For detailed information, see `FINAL_SUMMARY.md`
