# Fully Automated WFH Verification Solutions

All solutions below require **ZERO manual user actions** - completely automated.

---

## ✅ Solution 1: Zoho Webhooks (RECOMMENDED)

**How it works**: Zoho sends real-time notification when On Duty is applied → Bot auto-confirms

### Setup Steps:

#### 1. Start Webhook Server

```bash
# Install Flask if not installed
pip install flask

# Start webhook server
python3 zoho_webhook_server.py
```

Server runs on port 3002 by default.

#### 2. Expose Server to Internet

**Option A: Use ngrok (for testing)**
```bash
# Install ngrok
brew install ngrok  # or download from ngrok.com

# Expose webhook server
ngrok http 3002

# You'll get URL like: https://abc123.ngrok.io
```

**Option B: Deploy to server (for production)**
- Deploy to AWS/GCP/Heroku
- Use your domain: https://yourdomain.com/webhooks/zoho/onduty

#### 3. Configure in Zoho People

1. Go to Zoho People → **Settings** → **Developer Space** → **Webhooks**

2. Click **"Create Webhook"**

3. Configure:
   ```
   Webhook Name: On Duty Application Notification
   Module: Attendance (or Custom Forms)
   Form: On Duty / Request On Duty
   Trigger Event: On Create, On Update

   Webhook URL: https://your-ngrok-url.ngrok.io/webhooks/zoho/onduty

   Method: POST
   Format: JSON

   Include Fields:
   ☑️ Employee_ID
   ☑️ Employee_Email
   ☑️ Type (On Duty Type)
   ☑️ From / Period
   ☑️ To
   ☑️ Status / ApprovalStatus
   ☑️ All other fields
   ```

4. **Test webhook**:
   - Use test URL: https://your-url.com/webhooks/zoho/test
   - Send test notification
   - Check logs

5. **Activate webhook**

#### 4. Integration with Bot

Add to `.env`:
```bash
WEBHOOK_PORT=3002
WEBHOOK_ENABLED=true
```

#### 5. Test End-to-End

1. User posts in Slack: "I'll be doing wfh on 18th"
2. Bot responds: "Please apply on Zoho" (marks as pending)
3. User applies On Duty on Zoho
4. **Zoho sends webhook → Bot auto-confirms ✅**
5. Bot posts in Slack thread: "✅ WFH application confirmed on Zoho!"

### Advantages:
- ✅ **Fully automated** - zero user action
- ✅ Real-time verification (instant)
- ✅ Official Zoho feature (supported)
- ✅ No API limitations
- ✅ Reliable

### Requirements:
- Zoho People must support webhooks for On Duty form
- Server with public URL (ngrok for testing)

---

## ✅ Solution 2: Zoho Deluge Custom Function

Create custom script in Zoho that pushes On Duty data to your bot.

### Setup Steps:

#### 1. Create Deluge Function in Zoho

Go to Zoho People → **Settings** → **Developer Space** → **Functions**

Create new function: `NotifySlackBot`

```javascript
// Zoho Deluge Script
void NotifySlackBot(string employeeId, string employeeEmail, string onDutyType,
                    string fromDate, string toDate, string status)
{
    // Your bot webhook URL
    webhookUrl = "https://your-server.com/webhooks/zoho/onduty";

    // Prepare payload
    payload = Map();
    payload.put("Employee_ID", employeeId);
    payload.put("Employee_Email", employeeEmail);
    payload.put("Type", onDutyType);
    payload.put("From", fromDate);
    payload.put("To", toDate);
    payload.put("Status", status);
    payload.put("Source", "deluge_function");

    // Send to bot
    response = invokeurl
    [
        url: webhookUrl
        type: POST
        parameters: payload.toString()
        headers: {"Content-Type": "application/json"}
    ];

    info "Notification sent: " + response;
}
```

#### 2. Create Workflow Rule

Go to **Settings** → **Automation** → **Workflow Rules**

Create rule for "On Duty" form:
```
Trigger: On Create, On Update
Condition: Type contains "Work From Home"

Action: Call Function → NotifySlackBot
Parameters:
  - ${On_Duty.Employee_ID}
  - ${On_Duty.Employee_Email}
  - ${On_Duty.Type}
  - ${On_Duty.From}
  - ${On_Duty.To}
  - ${On_Duty.Status}
```

#### 3. Test

Apply On Duty → Deluge function runs → Bot receives notification → Auto-confirms

### Advantages:
- ✅ Fully automated
- ✅ No webhook configuration needed (uses function URL)
- ✅ More control over when to notify
- ✅ Can add custom logic in Deluge

---

## ✅ Solution 3: Zoho Analytics Integration

If On Duty data is in Zoho Analytics, query it directly.

### Setup:

#### 1. Check if On Duty data is in Analytics

Go to Zoho Analytics → Check if "On Duty" or "Attendance" reports exist

#### 2. Get Analytics API credentials

Settings → Developer Hub → Create API credentials

#### 3. Query via Analytics API

```python
import requests

def check_wfh_via_analytics(employee_email, date):
    """Query On Duty via Zoho Analytics API"""

    analytics_api_url = "https://analyticsapi.zoho.in/api/{owner_name}/{workspace_name}"

    # SQL query
    sql = f"""
    SELECT * FROM OnDuty
    WHERE Employee_Email = '{employee_email}'
    AND Period = '{date}'
    AND Type = 'Work From Home'
    """

    params = {
        "ZOHO_ACTION": "EXPORT",
        "ZOHO_OUTPUT_FORMAT": "JSON",
        "ZOHO_ERROR_FORMAT": "JSON",
        "ZOHO_API_VERSION": "1.0",
        "ZOHO_SQLQUERY": sql
    }

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    response = requests.get(analytics_api_url, params=params, headers=headers)
    data = response.json()

    return len(data.get("data", [])) > 0
```

#### 4. Update bot to use Analytics API

Modify `slack_bot_polling.py`:
```python
if is_wfh:
    # Check via Analytics instead of regular API
    leave_found = check_wfh_via_analytics(user_email, leave_dates[0])

    if leave_found:
        self._send_thread_reply(self.leave_channel_id, msg_ts,
            f"Thanks <@{user_id}> for applying WFH on Zoho!")
    else:
        # Send reminder
        self._send_thread_reply(self.leave_channel_id, msg_ts,
            f"Hi <@{user_id}>, please apply for WFH on Zoho.")
```

### Advantages:
- ✅ Fully automated
- ✅ Direct data access
- ✅ Can query historical data

### Disadvantages:
- ⚠️ Only if On Duty syncs to Analytics
- ⚠️ May have data lag (not real-time)

---

## ✅ Solution 4: Headless Browser Automation

Use Selenium/Playwright to automatically check Zoho UI.

### Implementation:

```python
# automated_zoho_checker.py
from playwright.sync_api import sync_playwright
import os

class AutomatedZohoChecker:
    def __init__(self):
        self.zoho_email = os.getenv('ZOHO_USER_EMAIL')
        self.zoho_password = os.getenv('ZOHO_USER_PASSWORD')

    def check_wfh_exists(self, employee_name, date):
        """Automatically check if WFH exists in Zoho UI"""
        with sync_playwright() as p:
            # Launch browser (headless)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                # Login to Zoho
                page.goto('https://people.zoho.in/')
                page.fill('input[name="email"]', self.zoho_email)
                page.fill('input[name="password"]', self.zoho_password)
                page.click('button[type="submit"]')
                page.wait_for_timeout(3000)

                # Navigate to On Duty page
                page.goto('https://people.zoho.in/zp#attendance/entry/onduty')
                page.wait_for_timeout(2000)

                # Search for employee
                page.fill('input[placeholder*="Search"]', employee_name)
                page.wait_for_timeout(2000)

                # Check if date exists in results
                content = page.content()
                date_str = date.strftime('%d-%b-%Y')

                found = date_str in content and 'Work from home' in content

                browser.close()
                return found

            except Exception as e:
                browser.close()
                raise e
```

### Run as Background Service:

```python
# Schedule checks every 5 minutes
import schedule
import time

checker = AutomatedZohoChecker()

def check_pending_wfh():
    """Check all pending WFH requests"""
    pending = wfh_tracker.get_pending_wfh()

    for record in pending:
        employee_name = record['user_name']
        dates = [datetime.fromisoformat(d) for d in record['dates']]

        for date in dates:
            found = checker.check_wfh_exists(employee_name, date)

            if found:
                # Auto-confirm
                wfh_tracker.confirm_wfh(record['message_ts'],
                                       confirmed_by='auto_checker')
                # Notify in Slack
                slack_client.chat_postMessage(
                    channel=LEAVE_CHANNEL_ID,
                    thread_ts=record['message_ts'],
                    text=f"✅ WFH application verified on Zoho!"
                )

# Run every 5 minutes
schedule.every(5).minutes.do(check_pending_wfh)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Advantages:
- ✅ Fully automated
- ✅ Works even without API
- ✅ Can see exactly what users see

### Disadvantages:
- ⚠️ Requires credentials
- ⚠️ Fragile (breaks if UI changes)
- ⚠️ Resource intensive
- ⚠️ Slower (5-10 second checks)
- ⚠️ May violate Zoho ToS

### Setup:
```bash
# Install Playwright
pip install playwright
playwright install chromium

# Add to .env
ZOHO_USER_EMAIL=your-email@company.com
ZOHO_USER_PASSWORD=your-password

# Run checker
python3 automated_zoho_checker.py
```

---

## ✅ Solution 5: Zoho People API v3 / Custom API

Try newer API versions or custom endpoints.

### Investigation Steps:

```python
# Test different API versions
import requests

base_urls = [
    "https://people.zoho.in/people/api",      # v1 (current)
    "https://people.zoho.in/people/api/v2",   # v2
    "https://people.zoho.in/people/api/v3",   # v3
    "https://people.zoho.in/api/v1",          # Alternative
    "https://peopleapi.zoho.in/api",          # Different subdomain
]

endpoints = [
    "/attendance/onduty",
    "/onduty/records",
    "/forms/OnDuty/getRecords",
    "/custom/onduty",
    "/timetracker/onduty",
]

for base_url in base_urls:
    for endpoint in endpoints:
        url = base_url + endpoint
        try:
            response = requests.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
            if response.status_code != 404:
                print(f"✓ FOUND: {url} → {response.status_code}")
        except:
            pass
```

---

## 🏆 Comparison & Recommendation

| Solution | Automation | Reliability | Setup | Recommendation |
|----------|-----------|-------------|-------|----------------|
| **Webhooks** | 100% | ⭐⭐⭐⭐⭐ | Medium | ✅ **BEST** |
| **Deluge Function** | 100% | ⭐⭐⭐⭐⭐ | Medium | ✅ **BEST** |
| **Analytics API** | 100% | ⭐⭐⭐⭐ | Easy | ✅ Good |
| **Headless Browser** | 100% | ⭐⭐ | Hard | ⚠️ Last Resort |
| **API v2/v3** | 100% | ⭐⭐⭐⭐⭐ | Easy | ✅ If exists |

---

## 🚀 Recommended Implementation Plan

### Step 1: Try Webhooks (1 hour)
1. Start webhook server
2. Check if Zoho People has webhooks for On Duty
3. If YES → Configure webhook → **DONE!**
4. If NO → Go to Step 2

### Step 2: Try Deluge Function (1 hour)
1. Create Deluge function
2. Create workflow rule
3. Test → **DONE!**

### Step 3: Try Analytics API (30 mins)
1. Check if On Duty in Analytics
2. If YES → Use Analytics API → **DONE!**
3. If NO → Go to Step 4

### Step 4: API Discovery (30 mins)
1. Run API version discovery script
2. If found → Update bot → **DONE!**
3. If not found → Go to Step 5

### Step 5: Headless Automation (Last Resort)
1. Implement Playwright checker
2. Run as background service
3. Accept limitations

---

## 📋 Quick Start - Webhooks

Want to try webhooks right now?

```bash
# 1. Start webhook server
python3 zoho_webhook_server.py

# 2. In another terminal, expose via ngrok
ngrok http 3002

# 3. Copy the ngrok URL (e.g., https://abc123.ngrok.io)

# 4. Go to Zoho People → Settings → Developer Space → Webhooks
#    - Create webhook for On Duty form
#    - URL: https://abc123.ngrok.io/webhooks/zoho/onduty
#    - Test it

# 5. Apply On Duty in Zoho → Check if webhook received
tail -f webhook.log
```

---

## ❓ Which Solution Should I Use?

**Answer these questions:**

1. **Does Zoho People have webhooks for On Duty?**
   - YES → Use **Webhooks** (Solution 1)
   - NO → Go to Q2

2. **Can you create Deluge functions?**
   - YES → Use **Deluge** (Solution 2)
   - NO → Go to Q3

3. **Is On Duty data in Zoho Analytics?**
   - YES → Use **Analytics API** (Solution 3)
   - NO → Go to Q4

4. **Okay with headless browser automation?**
   - YES → Use **Playwright** (Solution 4)
   - NO → Contact Zoho support

---

**Files Created:**
- `zoho_webhook_server.py` - Webhook server ready to use
- `AUTOMATED_WFH_SOLUTIONS.md` - This guide

**Need help implementing? Let me know which solution you want to try first!**
