# Quick Start - NO Auto-Approval Mode

## Configuration: ALL Requests Require Approval ✅

The bot is now configured so **every leave and WFH request requires manager approval**.

---

## Current Settings

```bash
# .env configuration
APPROVAL_WORKFLOW_ENABLED=true
AUTO_APPROVE_DAYS=0              # No auto-approval for leave
WFH_AUTO_APPROVE_DAYS=0          # No auto-approval for WFH
WFH_REQUIRES_APPROVAL=true
```

---

## Setup Steps (Required)

### Step 1: Configure Slack App Token ⚠️ REQUIRED

**Interactive buttons won't work without this!**

1. **Go to:** https://api.slack.com/apps
2. **Select your app:** slack-leave-bot
3. **Enable Socket Mode:**
   - Settings → Socket Mode → Toggle ON
4. **Create App-Level Token:**
   - Basic Information → App-Level Tokens
   - Click "Generate Token and Scopes"
   - Name: `slack-leave-bot-socket`
   - Add scope: `connections:write`
   - Click "Generate"
   - **COPY THE TOKEN** (starts with `xapp-`)

5. **Add to .env:**
   ```bash
   nano .env
   # Find line 71 and add your token:
   SLACK_APP_TOKEN=xapp-1-A0XXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXX
   ```

---

### Step 2: Configure Org Hierarchy

Edit the organizational structure with your team:

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

**To get Slack User IDs:**
- Click user in Slack → View profile → More → Copy member ID
- Or: Slack profile → ⋯ → Copy member ID

---

### Step 3: Start the Bot

```bash
# Terminal 1: Start bot
cd /Users/ankitsaxena/slack-leave-bot
python main.py

# Terminal 2: Start dashboard (optional but recommended)
cd /Users/ankitsaxena/slack-leave-bot/dashboard
npm install  # First time only
node server.js

# Terminal 3: Watch logs
tail -f bot.log
```

**Expected logs:**
```
✅ Bot initialized in POLLING mode
✅ Socket Mode handler started
✅ Approval workflow initialized (enabled=True)
✅ Interactive handler initialized
✅ Org hierarchy loaded: X employees, Y approvers
```

---

## Testing

### Test 1: Regular Leave Request

**In Slack leave channel, post:**
```
Taking leave tomorrow
```

**Expected behavior:**
1. Bot detects leave (1 day)
2. **NO auto-approval** (AUTO_APPROVE_DAYS=0)
3. Sends approval request to manager
4. Manager receives message:
   ```
   🔔 Leave Approval Request

   Employee: @john.doe
   Leave Dates: Feb 11, 2026
   Duration: 1 day

   [Approve] [Reject] [Request Details]
   ```
5. Manager clicks [Approve]
6. Bot verifies in Zoho
7. Employee gets notification

---

### Test 2: WFH Request

**In Slack leave channel, post:**
```
WFH Friday
```

**Expected behavior:**
1. Bot detects WFH (1 day)
2. **NO auto-approval** (WFH_AUTO_APPROVE_DAYS=0)
3. Sends approval request to manager
4. Manager receives WFH approval request
5. Manager approves
6. Bot verifies in Zoho

---

### Test 3: Multi-Day Leave

**In Slack leave channel, post:**
```
Taking leave Feb 15-19
```

**Expected behavior:**
1. Bot detects leave (5 days)
2. Requires manager approval (5 days <= STANDARD_APPROVAL_DAYS)
3. Manager approves
4. Bot verifies in Zoho

---

### Test 4: Long Leave (Multi-Level)

**In Slack leave channel, post:**
```
Taking leave Feb 15-21
```

**Expected behavior:**
1. Bot detects leave (7 days)
2. Requires multi-level approval (7 days > SENIOR_APPROVAL_DAYS)
3. Goes to manager first
4. After manager approves, goes to senior manager
5. After senior manager approves, verifies in Zoho

---

## Approval Flow Examples

### Example 1: 1-Day Leave (Manager Approval)

```
Employee: "Taking leave tomorrow"
    ↓
Bot: No auto-approval
    ↓
Manager: Receives approval request with buttons
    ↓
Manager: Clicks [Approve]
    ↓
Bot: Checks Zoho
    ↓
Employee: Gets approval notification
```

### Example 2: 1-Day WFH (Manager Approval)

```
Employee: "WFH tomorrow"
    ↓
Bot: Detects WFH, no auto-approval
    ↓
Manager: Receives WFH approval request
    ↓
Manager: Clicks [Approve]
    ↓
Bot: Checks Zoho
```

### Example 3: Rejection Flow

```
Employee: "Taking leave next week"
    ↓
Manager: Receives approval request
    ↓
Manager: Clicks [Reject]
    ↓
Manager: Modal opens, enters reason
    ↓
Bot: Marks as rejected
    ↓
Employee: Gets rejection with reason
    ↓
HR: Gets notification (optional)
```

---

## Dashboard Monitoring

**Open dashboard:**
```bash
open http://localhost:3001
```

**Check approval stats:**
```bash
curl http://localhost:3001/api/approvals/stats
```

**Sample output:**
```json
{
  "total": 25,
  "pending": 3,
  "approved": 20,
  "rejected": 2,
  "auto_approved": 0,        ← Should be 0 (no auto-approval)
  "average_approval_time_hours": 2.5
}
```

**Check pending approvals:**
```bash
curl http://localhost:3001/api/approvals/pending
```

---

## Approval Rules Summary

| Leave Type | Duration | Auto-Approve? | Approval Required |
|------------|----------|---------------|-------------------|
| Regular Leave | 1 day | ❌ NO | ✅ Manager |
| Regular Leave | 2-5 days | ❌ NO | ✅ Manager |
| Regular Leave | 6+ days | ❌ NO | ✅ Manager + Senior Manager |
| WFH | 1 day | ❌ NO | ✅ Manager |
| WFH | 2+ days | ❌ NO | ✅ Manager |

**Key Point:** AUTO_APPROVE_DAYS=0 and WFH_AUTO_APPROVE_DAYS=0 means **nothing is auto-approved**.

---

## Troubleshooting

### Issue: Approval buttons don't work

**Symptom:** Manager clicks [Approve] but nothing happens

**Solution:**
```bash
# 1. Check SLACK_APP_TOKEN is set
grep SLACK_APP_TOKEN .env

# 2. Ensure Socket Mode is enabled in Slack app settings
# Go to: https://api.slack.com/apps → Your App → Socket Mode

# 3. Check logs for Socket Mode connection
grep "Socket Mode" bot.log

# Expected: "Socket Mode handler started"
```

---

### Issue: No manager found

**Symptom:** "No manager found for employee"

**Solution:**
```bash
# Check org_hierarchy.json
cat config/org_hierarchy.json

# Ensure:
# 1. Employee email matches their Slack profile email
# 2. Manager email is listed in "approvers" section
# 3. Slack user IDs are correct
```

---

### Issue: Bot not detecting messages

**Symptom:** Bot doesn't respond to leave messages

**Solution:**
```bash
# 1. Check LEAVE_CHANNEL_ID in .env
grep LEAVE_CHANNEL_ID .env

# 2. Ensure bot is in the channel
# In Slack: /invite @slack-leave-bot

# 3. Check logs
tail -f bot.log | grep "Processing message"
```

---

## Verification Checklist

Before production use:

- [ ] APPROVAL_WORKFLOW_ENABLED=true ✅
- [ ] AUTO_APPROVE_DAYS=0 ✅
- [ ] WFH_AUTO_APPROVE_DAYS=0 ✅
- [ ] SLACK_APP_TOKEN configured ⚠️
- [ ] config/org_hierarchy.json populated with team
- [ ] Bot running: `ps aux | grep "python main.py"`
- [ ] Socket Mode connected: `grep "Socket Mode" bot.log`
- [ ] Test message sent and approval request received
- [ ] Manager can see approve/reject buttons
- [ ] Clicking approve works and verifies Zoho
- [ ] Dashboard accessible: http://localhost:3001

---

## Next Steps

1. **Configure SLACK_APP_TOKEN** (required for buttons)
2. **Update org_hierarchy.json** with your team
3. **Start bot:** `python main.py`
4. **Test with real message**
5. **Monitor logs:** `tail -f bot.log`
6. **Check dashboard:** http://localhost:3001

---

## Quick Command Reference

```bash
# Start bot
python main.py

# Start dashboard
cd dashboard && node server.js

# View logs
tail -f bot.log

# Check approvals
curl http://localhost:3001/api/approvals/stats

# Check pending
curl http://localhost:3001/api/approvals/pending

# Test health
curl http://localhost:3001/api/health/database
```

---

**Status:** Configured for NO Auto-Approval ✅

**All requests require manager approval!**
