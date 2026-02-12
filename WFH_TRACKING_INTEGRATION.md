# WFH Tracking Integration Guide

Since Zoho People API doesn't expose On Duty/WFH records, here are multiple solutions to add WFH checking:

---

## ✅ Option 1: Configure WFH as Leave Type (RECOMMENDED)

**Easiest solution - No code changes needed!**

### Setup in Zoho People:

1. Go to **Settings** → **Leave** → **Leave Types**
2. Click **"Add Leave Type"**
3. Configure:
   ```
   Name: Work From Home
   Short Name: WFH
   Unit: Days/Hours (as needed)

   Advanced Settings:
   ☑️ Does not affect leave balance
   ☑️ Can be applied for partial days
   ☐ Weekend considered

   Approval:
   - Auto-approve OR require manager approval
   ```
4. Save

### Result:
- ✅ Bot automatically detects WFH (it's now a leave type)
- ✅ Full verification works
- ✅ Reminders work
- ✅ Analytics work
- ✅ No code changes needed

### Ask Users To:
Going forward, apply WFH using the "Work From Home" leave type instead of "Request On Duty"

---

## Option 2: Manual Tracking with Slack Reactions

Users confirm WFH application by reacting to bot's message with ✅

### Integration Steps:

**1. Add WFH Tracker to bot:**

Edit `slack_bot_polling.py`, add at top:
```python
from wfh_tracker import WFHTracker, handle_wfh_confirmation_reaction

class SlackLeaveBot:
    def __init__(self, ...):
        # ... existing code ...
        self.wfh_tracker = WFHTracker()
```

**2. Modify WFH handling** (replace lines 493-500):
```python
if is_wfh:
    logger.info("WFH request detected")
    formatted_dates = self._format_dates_for_display(leave_dates)

    # Track WFH request
    msg_ts = self.wfh_tracker.add_pending_wfh(
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        dates=leave_dates,
        message_ts=msg_ts
    )

    # Send message with instructions
    message = (
        f"Hi <@{user_id}>, I see you're planning to WFH on {formatted_dates}.\n\n"
        f"Please apply for On Duty (WFH) on Zoho People, then:\n"
        f"• React to this message with ✅ to confirm you've applied\n"
        f"• I'll send a reminder in 12 hours if not confirmed"
    )

    response = self._send_thread_reply(self.leave_channel_id, msg_ts, message)

    # Add checkmark reaction as hint
    try:
        self.client.reactions_add(
            channel=self.leave_channel_id,
            timestamp=msg_ts,
            name="white_check_mark"
        )
    except Exception as e:
        logger.error(f"Failed to add reaction: {e}")

    return
```

**3. Add reaction handler** (add new method to SlackLeaveBot class):
```python
def _handle_reaction_added(self, event: Dict):
    """Handle when user adds reaction to message"""
    try:
        reaction = event.get("reaction", "")
        message_ts = event.get("item", {}).get("ts")
        user_id = event.get("user")

        # Check if it's a confirmation reaction
        if reaction in ["white_check_mark", "heavy_check_mark", "ballot_box_with_check"]:
            # Try to confirm WFH
            if self.wfh_tracker.confirm_wfh(message_ts, confirmed_by=user_id):
                # Send confirmation
                self.client.chat_postMessage(
                    channel=self.leave_channel_id,
                    thread_ts=message_ts,
                    text=f"✅ Thanks <@{user_id}>! WFH application confirmed."
                )
                logger.info(f"WFH confirmed by {user_id}")
    except Exception as e:
        logger.error(f"Error handling reaction: {e}")
```

**4. Subscribe to reaction events** (in `start()` method):
```python
def start(self):
    # ... existing polling code ...

    # Also check for reactions (if using RTM/Socket mode)
    # OR poll reactions API periodically
```

**5. Add reminder checking** (in `_check_due_reminders()`):
```python
# Check for overdue WFH confirmations
overdue_wfh = self.wfh_tracker.get_overdue_wfh(hours=12)
for wfh_record in overdue_wfh:
    message_ts = wfh_record["message_ts"]
    user_id = wfh_record["user_id"]

    # Send reminder
    self.client.chat_postMessage(
        channel=self.leave_channel_id,
        thread_ts=message_ts,
        text=f"<@{user_id}> Friendly reminder: Please confirm your WFH application by reacting with ✅"
    )
```

### User Experience:
1. User posts: "I'll be doing wfh on 18th"
2. Bot replies: "Please apply on Zoho, then react with ✅"
3. User applies on Zoho
4. User clicks ✅ on bot's message
5. Bot confirms: "✅ Thanks! WFH application confirmed"

---

## Option 3: Slash Command Confirmation

Users confirm via `/wfh-applied` command

### Implementation:

**1. Create slash command handler:**

Create `slash_commands.py`:
```python
from flask import Flask, request, jsonify
from wfh_tracker import WFHTracker

app = Flask(__name__)
tracker = WFHTracker()

@app.route('/slack/commands/wfh-applied', methods=['POST'])
def wfh_applied_command():
    """Handle /wfh-applied command"""
    # Verify Slack signature
    # ... signature verification code ...

    user_id = request.form.get('user_id')
    user_name = request.form.get('user_name')

    # Get user's pending WFH
    user_email = get_user_email(user_id)  # You'll need to implement this
    pending = tracker.get_pending_wfh(user_email)

    if not pending:
        return jsonify({
            "response_type": "ephemeral",
            "text": "No pending WFH requests found."
        })

    # Confirm all pending WFH for this user
    for record in pending:
        tracker.confirm_wfh(record["message_ts"], confirmed_by=user_id)

    return jsonify({
        "response_type": "ephemeral",
        "text": f"✅ Confirmed {len(pending)} WFH application(s)!"
    })

if __name__ == '__main__':
    app.run(port=3002)
```

**2. Configure in Slack:**
- Go to api.slack.com/apps
- Select your app
- Go to "Slash Commands"
- Create new command: `/wfh-applied`
- Request URL: `https://your-server.com/slack/commands/wfh-applied`
- Save

**3. Update bot message:**
```python
message = (
    f"Hi <@{user_id}>, I see you're planning to WFH on {formatted_dates}.\n\n"
    f"After applying on Zoho People, type `/wfh-applied` to confirm."
)
```

---

## Option 4: Web Scraping (Not Recommended ⚠️)

Use Selenium to scrape Zoho People UI and check On Duty records.

### Why NOT Recommended:
- ❌ Fragile (breaks with UI changes)
- ❌ Requires browser automation
- ❌ Slow and resource-intensive
- ❌ May violate Zoho's terms of service
- ❌ Security risk (needs credentials)

### If You Must:

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def check_wfh_via_scraping(email, date):
    """NOT RECOMMENDED - Use only as last resort"""
    driver = webdriver.Chrome()

    try:
        # Login to Zoho
        driver.get("https://people.zoho.in/")
        # ... login steps ...

        # Navigate to On Duty
        driver.get("https://people.zoho.in/zp#attendance/entry/onduty")

        # Search for employee
        # ... scraping logic ...

        # Check if WFH exists for date
        # ... more scraping ...

        return found
    finally:
        driver.quit()
```

**Problems:**
- Needs to run in foreground (can't run on server)
- Requires Chrome/Firefox installed
- Login credentials in code (security risk)
- Breaks when Zoho changes UI

---

## Option 5: Contact Zoho Support

Request API access for On Duty module.

### Steps:

1. **Email Zoho Support:**
   ```
   To: support@zohopeopleplus.com
   Subject: API Access Request for On Duty Module

   Hello,

   We use Zoho People API for leave tracking automation.
   We need to verify "On Duty" (Work From Home) applications via API.

   Current issue:
   - /forms API doesn't list On Duty form
   - /attendance endpoints return 404
   - On Duty data not in leave records

   Request:
   - API endpoint to query On Duty records
   - Or documentation on accessing On Duty via API

   Our use case: Slack bot that verifies leave/WFH compliance

   Thank you!
   ```

2. **Wait for response** (may take 3-5 business days)

3. **If they provide endpoint:**
   - Update `zoho_client.py` with correct endpoint
   - Remove early return in `slack_bot_polling.py`
   - Enable full WFH verification

---

## Comparison Table

| Option | Difficulty | Code Changes | User Action | Reliability |
|--------|-----------|--------------|-------------|-------------|
| **1. WFH as Leave Type** | ⭐ Easy | None | Apply via "WFH" leave type | ⭐⭐⭐⭐⭐ High |
| **2. Reaction Confirmation** | ⭐⭐ Medium | Moderate | Click ✅ reaction | ⭐⭐⭐⭐ Good |
| **3. Slash Command** | ⭐⭐⭐ Hard | Significant | Type `/wfh-applied` | ⭐⭐⭐ Fair |
| **4. Web Scraping** | ⭐⭐⭐⭐ Very Hard | Complex | None | ⭐ Poor |
| **5. Contact Zoho** | ⭐ Easy | None (wait) | None | ⭐⭐⭐⭐⭐ High (if granted) |

---

## Recommended Approach

**Best solution for most cases:**

1. **Immediate**: Implement **Option 2 (Reaction Confirmation)**
   - Quick to implement
   - Good user experience
   - Reliable tracking

2. **Long-term**: Configure **Option 1 (WFH as Leave Type)**
   - Cleanest solution
   - No code changes needed
   - Full bot functionality

3. **Parallel**: Contact Zoho (**Option 5**)
   - If they provide API, switch to that
   - Best long-term solution

---

## Quick Start - Reaction Confirmation

Want to implement Option 2 right now? Here's the minimal code:

```bash
# 1. The wfh_tracker.py is already created
# 2. Add these lines to slack_bot_polling.py:

# At top:
from wfh_tracker import WFHTracker

# In __init__:
self.wfh_tracker = WFHTracker()

# Replace WFH handling (lines 493-500):
# [Use code from Option 2 above]

# Restart bot:
pkill -9 -f main.py && rm -f .bot.lock && python3 main.py > bot.log 2>&1 &
```

Done! Users can now confirm WFH by clicking ✅

---

## Questions?

- **Q: Can we auto-confirm WFH after 24 hours?**
  - A: Yes, add auto-confirm logic in `_check_due_reminders()`

- **Q: Can we send email reminders?**
  - A: Yes, integrate SMTP in notification_router.py

- **Q: Can managers confirm for team members?**
  - A: Yes, check user role before confirming

- **Q: Can we track partial WFH (half day)?**
  - A: Yes, store hours in WFH record

---

**Created**: 2026-02-11
**Recommendation**: Use Option 1 (WFH as Leave Type) for zero-code solution
