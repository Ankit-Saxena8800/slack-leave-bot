# Thread Reminders with Manager Tagging - Active ✅

## Overview

Bot now sends all reminders in the SAME THREAD where the user posted, and tags the manager.

---

## Complete Flow

### Step 1: User Posts Leave/WFH
```
User: "WFH on Friday"
```

### Step 2: Bot Checks Zoho & Replies in Thread
**If FOUND in Zoho:**
```
✅ Thank you @user for informing and applying on Zoho! Your leave/WFH is noted.
```

**If NOT FOUND in Zoho:**
```
Hi @user, I couldn't find your leave/WFH application on Zoho for Feb 14, 2026.
Please apply on Zoho as well. I'll check again in 24 hours. 📋
```

### Step 3: After 24 Hours (if still not applied)
**Bot posts in SAME THREAD:**
```
⚠️ Reminder: @user, your leave/WFH for Feb 14, 2026 is still not applied on Zoho.
Please apply as soon as possible. CC: @manager
```

**Features:**
- ✅ Posted in same thread (not DM)
- ✅ Tags the user
- ✅ Tags the manager
- ✅ Shows the dates

### Step 4: When User Finally Applies
**Bot detects and posts in SAME THREAD:**
```
✅ Great! @user has now applied the leave/WFH on Zoho. Thank you!
```

---

## Example Thread

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User @ankit
Feb 10, 2:30 PM
"WFH on Friday"

  LeaveBot APP
  Just now
  Hi @ankit, I couldn't find your leave/WFH application on Zoho for Feb 14, 2026.
  Please apply on Zoho as well. I'll check again in 24 hours. 📋

  [24 hours pass - user doesn't apply]

  LeaveBot APP
  Feb 11, 2:30 PM
  ⚠️ Reminder: @ankit, your leave/WFH for Feb 14, 2026 is still not applied on Zoho.
  Please apply as soon as possible. CC: @jane.manager

  [User applies on Zoho]

  LeaveBot APP
  Feb 11, 3:15 PM
  ✅ Great! @ankit has now applied the leave/WFH on Zoho. Thank you!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Manager Configuration

**Update your team in:** `config/org_hierarchy.json`

```json
{
  "employees": [
    {
      "email": "employee@company.com",
      "name": "Employee Name",
      "slack_id": "U123456",
      "manager": "manager@company.com"
    }
  ],
  "employees": [
    {
      "email": "manager@company.com",
      "name": "Manager Name",
      "slack_id": "U234567",
      "role": "manager"
    }
  ]
}
```

**How to get Slack IDs:**
1. Click on user in Slack
2. View profile
3. Click ⋯ (More)
4. Copy member ID

---

## Configuration Summary

**Reminder Settings:**
- ⏰ Reminder after: 24 hours
- 📍 Reminder location: Same thread
- 👥 Tags: User + Manager
- 📧 DM: Disabled
- 🔔 Multi-level: Disabled

**Messages:**
- Thread reply (not found): Friendly "Please apply on Zoho"
- Thread reminder (24hr): Warning with manager tag
- Thread resolution: Thank you message

---

## Bot Status

```
✅ Bot Running (PID: 44413)
✅ Mode: Simple + Thread Reminders
✅ DM Reminders: Disabled
✅ Thread Reminders: Enabled (24hr)
✅ Manager Tagging: Enabled
📡 Channel: C0AALBN04KW
```

---

## Testing

### Test 1: Post Leave Message
```
Post: "Taking leave tomorrow"
Expected: Thread reply from bot
```

### Test 2: Don't Apply on Zoho
```
Wait: 24 hours (or modify code to 2 minutes for testing)
Expected: Reminder in same thread with manager tag
```

### Test 3: Apply on Zoho
```
Action: Apply leave on Zoho
Expected: Bot posts "Great! User has now applied" in thread
```

---

## Features

✅ **No DMs** - Everything in thread
✅ **Manager Tagging** - Manager gets notified in thread
✅ **Single Thread** - All messages in one conversation
✅ **24-Hour Check** - Automatic re-verification
✅ **Resolution Confirmation** - Thanks message when applied
✅ **Clean & Simple** - No complex escalation

---

## Customization

### Change Reminder Time (Testing)

To test with shorter reminder time:

```bash
nano config/notification_config.yaml

# Change line 13:
delay_hours: 24   →   delay_minutes: 2  # For 2-minute testing
```

Then restart bot:
```bash
pkill -f "python3 main.py" && rm .bot.lock && python3 main.py &
```

### Change Messages

Edit: `config/templates.yaml`

```yaml
thread_reminder:
  first_followup:
    en: "Your custom reminder message here @{user_id} CC: @{manager_slack_id}"
```

---

## Ready to Test! 🚀

**Current Status:**
- ✅ Thread reminders enabled
- ✅ Manager tagging enabled
- ✅ DM reminders disabled
- ✅ Bot running

**Post a test message in Slack and see it work!**
