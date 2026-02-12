# Slack Configuration Status

## Current Status

| Component | Status | Value |
|-----------|--------|-------|
| SLACK_BOT_TOKEN | ✅ Configured | xoxb-475622235234-... |
| SLACK_SIGNING_SECRET | ✅ Configured | 18e756e77d4fc2c7... |
| LEAVE_CHANNEL_ID | ✅ Configured | C0AALBN04KW |
| ADMIN_CHANNEL_ID | ✅ Configured | CL8CN59B2 |
| SLACK_APP_TOKEN | ❌ **MISSING** | **(Empty)** |

---

## Critical Issue: SLACK_APP_TOKEN Missing

**The approval buttons won't work without this token!**

### What Works Without It:
- ✅ Bot can detect leave messages
- ✅ Bot can send thread replies
- ✅ Bot can verify in Zoho
- ✅ Bot can send DMs

### What DOESN'T Work:
- ❌ Interactive approval buttons ([Approve] [Reject])
- ❌ Socket Mode connection
- ❌ Real-time button clicks
- ❌ Manager approval workflow UI

---

## How to Fix (5 Minutes)

### Step 1: Get the Token

1. **Go to:** https://api.slack.com/apps
2. **Select your app:** slack-leave-bot
3. **Enable Socket Mode:**
   - Go to: **Settings** → **Socket Mode**
   - Toggle **ON** if not already enabled
4. **Create App-Level Token:**
   - Go to: **Basic Information** → **App-Level Tokens**
   - Click **"Generate Token and Scopes"**
   - Token Name: `slack-leave-bot-socket`
   - Add Scope: `connections:write`
   - Click **Generate**
   - **COPY THE TOKEN** (starts with `xapp-1-`)

### Step 2: Add to .env

```bash
nano .env
```

Find line 71 and add your token:
```bash
SLACK_APP_TOKEN=xapp-1-A0XXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Save and exit (Ctrl+O, Enter, Ctrl+X)

---

## Alternative: Test Without Approval Buttons First

You can still test basic functionality without the app token:

### What You Can Test:
1. ✅ Leave message detection
2. ✅ Thread replies
3. ✅ Zoho verification
4. ✅ DM reminders

### To Disable Approval Workflow Temporarily:
```bash
# Edit .env
APPROVAL_WORKFLOW_ENABLED=false
```

Then the bot will work in basic mode:
- Detects leave messages
- Checks Zoho immediately
- Sends thread reply
- No approval buttons needed

---

## Recommendation

**Option 1: Get SLACK_APP_TOKEN (5 min) - RECOMMENDED**
- Full approval workflow with buttons
- Complete feature set
- Production-ready

**Option 2: Test Basic Mode First**
- Disable approval workflow temporarily
- Test leave detection and Zoho verification
- Add app token later for approval features

---

## Next Steps

Choose your path:

### Path A: Full Setup (Approval Workflow)
```bash
# 1. Get SLACK_APP_TOKEN from Slack
# 2. Add to .env line 71
# 3. Start bot
python main.py
# 4. Test approval flow with buttons
```

### Path B: Basic Testing First
```bash
# 1. Disable approval workflow
nano .env
# Set: APPROVAL_WORKFLOW_ENABLED=false

# 2. Start bot
python main.py

# 3. Test leave detection
# Post in Slack: "Taking leave tomorrow"
# Bot will check Zoho directly (no approval)
```

---

**Which path do you prefer?**
