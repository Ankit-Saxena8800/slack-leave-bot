# Slack Leave Bot - Complete Workflow Guide

## 🎯 Overview

The Slack Leave Bot monitors your #leaves channel and automatically verifies leave applications on Zoho People, sending reminders to users who haven't applied.

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SLACK #LEAVES CHANNEL                   │
│  Users post: "I'll be on leave Feb 12th"                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   SLACK LEAVE BOT (Polling)                  │
│  - Polls every 60 seconds                                    │
│  - Detects leave/WFH mentions                                │
│  - Parses dates and extracts user info                       │
└────────────┬───────────────────────┬────────────────────────┘
             │                       │
    ┌────────┴────────┐    ┌────────┴────────┐
    │ Regular Leave   │    │  WFH Request    │
    └────────┬────────┘    └────────┬────────┘
             │                       │
             ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│  ZOHO PEOPLE API        │  │  ACKNOWLEDGMENT ONLY    │
│  - Verify application   │  │  (API not available)    │
│  - Check status         │  │                         │
└────────┬────────────────┘  └─────────────────────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐  ┌────────────────┐
│ FOUND  │  │  NOT FOUND     │
└───┬────┘  └───┬────────────┘
    │           │
    ▼           ▼
┌────────┐  ┌─────────────────────┐
│ THANK  │  │  REMINDER SYSTEM    │
│ USER   │  │  - 12hr: First DM   │
└────────┘  │  - 48hr: Escalation │
            │  - 72hr: Admin      │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  ANALYTICS DATABASE │
            │  - Track all events │
            │  - Generate reports │
            └─────────────────────┘
```

---

## 🔄 Complete Workflow (Step-by-Step)

### **Step 1: Message Detection** (0-60 seconds)

```
User Action:
├─ Posts in #leaves: "I'll be on leave Feb 12th"
└─ Or: "I'll be doing wfh on 18th"

Bot Action:
├─ Polls channel every 60 seconds
├─ Detects new message (within 60s)
├─ Checks against processed messages (deduplication)
└─ If new → Process message

Deduplication:
├─ Stores message timestamps in .processed_messages.json
├─ Keeps last 7 days of messages
└─ Prevents duplicate processing
```

**Keywords Detected:**
- **Leave**: leave, leaves, pto, vacation, absent, day off, sick leave
- **WFH**: wfh, work from home, working from home, remote work

---

### **Step 2: Message Analysis** (Immediate)

```
Parse User Info:
├─ User ID: U123456
├─ User Name: Ankit Saxena
└─ User Email: ankit.s@company.com (via Slack API)

Detect Type:
├─ IF contains WFH keywords → WFH Request
└─ ELSE → Regular Leave

Parse Dates:
├─ Enhanced Date Parser (date_parsing_service.py)
├─ Patterns supported:
│   ├─ Single dates: "Feb 12th", "March 5"
│   ├─ Ranges: "15th to 20th", "from Jan 15 to Jan 20"
│   ├─ Relative: "today", "tomorrow", "next Monday"
│   ├─ Weekdays: "Monday", "next Friday"
│   └─ Partial: "half day", "morning only"
│
└─ Output: List of datetime objects

Example Outputs:
├─ "Feb 12th" → [2026-02-12]
├─ "15th to 20th" → [2026-02-15, 2026-02-16, ..., 2026-02-20]
└─ "next Monday" → [2026-02-17]
```

---

### **Step 3A: Regular Leave Processing**

#### **3A.1: Grace Period** (30 minutes)

```
Why Grace Period?
├─ User might be applying right now
├─ Prevents immediate "not found" message
└─ Better user experience

Implementation:
├─ Record detected at: T+0
├─ First Zoho check: T+30min
└─ Stored in: verification_records.json
```

#### **3A.2: Zoho Verification** (T+30min)

```
API Call:
GET https://people.zoho.in/people/api/forms/leave/getRecords

Parameters:
├─ searchField: EmailID
├─ searchOperator: Contains
├─ searchText: user@company.com

Calendar Year Tracking:
├─ If dates span multiple years (e.g., Dec 2026 + Jan 2027)
├─ Query each year separately:
│   ├─ Year 2026: Jan 1, 2026 - Dec 31, 2026
│   └─ Year 2027: Jan 1, 2027 - Dec 31, 2027
└─ Combine results

Date Matching:
├─ Parse Zoho dates: "12-Feb-2026" → 2026-02-12
├─ Compare with requested dates
├─ Match if any requested date found
└─ Check ApprovalStatus: Approved, Pending, Cancelled

Result:
├─ IF ALL dates found → leave_found = True
├─ IF PARTIAL match → leave_found = False (missing dates)
└─ IF NONE found → leave_found = False
```

#### **3A.3: Response Generation**

```
IF leave_found = True:
├─ Template: 'thread_reply.leave_found'
├─ Message: "Thanks @user for applying on Zoho!"
├─ Action: Post in thread
├─ Analytics: Record as "leave_compliant"
└─ END (no reminders)

IF leave_found = False:
├─ Template: 'thread_reply.leave_not_found'
├─ Message: "Hi @user, please apply for leave/WFH on Zoho also."
├─ Action: Post in thread
├─ Analytics: Record as "leave_non_compliant"
├─ Create reminder record:
│   ├─ user_id, user_email, user_name
│   ├─ leave_dates
│   ├─ message_ts (for threading)
│   ├─ detected_at: current timestamp
│   ├─ next_reminder_due: now + 12 hours
│   └─ reminder_level: 0
└─ Save to: pending_reminders.json
```

---

### **Step 3B: WFH Processing** (Current Implementation)

```
Detection:
├─ Keywords: wfh, work from home, working from home, remote
└─ is_wfh = True

Processing:
├─ Parse dates (same as regular leave)
├─ Format dates for display:
│   ├─ Single: "Feb 18, 2026"
│   ├─ Two: "Feb 18 and Feb 19, 2026"
│   └─ Multiple: "Feb 18 to Feb 22, 2026"
│
├─ Send acknowledgment message:
│   └─ "Hi @user, I see you're planning to WFH on {dates}.
│       Please ensure you've applied for On Duty (WFH) on Zoho People.
│       (Note: I can't automatically verify On Duty applications
│       as they're not accessible via API)"
│
├─ Track in wfh_tracker (if manual tracking enabled)
└─ END (no Zoho verification, no automatic reminders)

Why No Verification?
├─ Zoho People API doesn't expose On Duty records
├─ Tested 50+ endpoints - all returned 404
├─ No "On Duty" form in API
└─ Solution: Acknowledge + inform user of limitation
```

---

### **Step 4: Reminder System**

#### **4.1: Reminder Check Loop** (Every 1 hour)

```
Cron Job:
├─ Runs every 60 minutes
├─ Reads: pending_reminders.json
└─ Processes each pending reminder

For Each Reminder:
├─ Check if next_reminder_due <= now
├─ IF YES:
│   ├─ Re-verify in Zoho (check if now applied)
│   │   ├─ IF NOW FOUND:
│   │   │   ├─ Send: "Thanks for applying!"
│   │   │   ├─ Remove from pending
│   │   │   └─ Record resolution
│   │   └─ IF STILL NOT FOUND:
│   │       └─ Send next level reminder ↓
│   │
│   └─ Escalation levels
└─ IF NO: Skip (not yet due)

Cleanup:
├─ Remove reminders older than 7 days
└─ Remove resolved reminders
```

#### **4.2: Reminder Levels**

```
Level 0 → Level 1 (T+12 hours):
├─ Channel: DM (Direct Message)
├─ Template: 'dm_reminder.first_followup'
├─ Message: "Hi {user}, friendly reminder to apply your leave on Zoho."
├─ Also: Post in thread (thread_ts preserved)
└─ Update: next_reminder_due = now + 36 hours (total 48hr)

Level 1 → Level 2 (T+48 hours):
├─ Channel: DM + Thread
├─ Template: 'dm_reminder.second_escalation'
├─ Message: "Hi {user}, please ensure you apply by end of day.
│            Dates: {leave_dates}"
├─ Tone: More urgent
└─ Update: next_reminder_due = now + 24 hours (total 72hr)

Level 2 → Level 3 (T+72 hours):
├─ Channel: DM + Thread + Admin
├─ Template: 'dm_reminder.urgent'
├─ Message: "URGENT: {user}, please apply immediately for {dates}"
├─ Admin Notification:
│   ├─ Channel: #hr or admin DM
│   └─ Message: "User {user} hasn't applied after 72 hours"
│
└─ Final action: Can mark as escalated, continue reminders, or close
```

#### **4.3: Re-verification Logic**

```
At Each Reminder Level:
├─ Before sending reminder, check Zoho again
├─ Reason: User might have applied since last check
│
└─ IF found:
    ├─ Send: "Thanks for applying! No further reminders."
    ├─ Remove from pending_reminders.json
    └─ Record in analytics as "resolved_at_Xhr"

Example:
User applies at T+20hr (between 12hr and 48hr checks)
├─ First reminder sent at T+12hr: "Please apply"
├─ User applies at T+20hr
├─ Second check at T+48hr: RE-VERIFY
│   └─ NOW FOUND in Zoho
└─ Action: Thank user, stop reminders
```

---

### **Step 5: Analytics Collection**

#### **5.1: Events Tracked**

```
Leave Events (leave_events table):
├─ timestamp: When event occurred
├─ user_id, user_email, user_name
├─ event_type: 'leave_mentioned' or 'wfh_mentioned'
├─ message_ts: Slack message timestamp
├─ leave_dates: JSON array of dates
├─ zoho_applied: Boolean (found in Zoho?)
└─ created_at: Record creation time

Reminder Events (reminder_events table):
├─ timestamp: When reminder sent
├─ user_id
├─ reminder_type: 'first', 'followup_12hr', 'followup_48hr', 'resolved'
├─ message_ts: Original leave message
├─ action_taken: 'thread_reply', 'dm_sent', 'admin_notified'
└─ created_at

Daily Aggregates (daily_aggregates table):
├─ date: Aggregation date
├─ total_leaves: Count of leave mentions
├─ compliant_count: Found on Zoho
├─ non_compliant_count: Not found on Zoho
├─ reminders_sent: Total reminders
└─ compliance_rate: compliant / total
```

#### **5.2: Collection Process**

```
Non-blocking Collection:
├─ Analytics collector runs in separate thread
├─ Events buffered in memory queue
├─ Batch insert every 10 events or 60 seconds
└─ If analytics fails → Bot continues working

Data Retention:
├─ Keep detailed events: 90 days
├─ Keep daily aggregates: Forever
└─ Cleanup job runs weekly
```

---

## 📈 Dashboard (localhost:3005)

### **Available Now:**

```
Overview Page:
├─ Today's Stats
│   ├─ Total leaves mentioned
│   ├─ Compliance rate
│   ├─ Pending reminders
│   └─ Active users
│
├─ Charts
│   ├─ Leave mentions trend (30 days)
│   ├─ Compliance rate over time
│   └─ Reminder distribution
│
├─ Active Reminders List
│   ├─ User name
│   ├─ Dates
│   ├─ Time remaining
│   └─ Reminder level
│
└─ Recent Events Feed
    ├─ Last 50 events
    ├─ Real-time updates (30s refresh)
    └─ Filter by: leave/wfh/reminder
```

**Access:** http://localhost:3005

---

## 🎯 Example Scenarios

### **Scenario 1: Compliant User**

```
T+0min:  User posts: "I'll be on leave Feb 12th"
T+1min:  Bot detects message
T+30min: Bot checks Zoho → FOUND ✅
T+30min: Bot posts: "Thanks @user for applying on Zoho!"
         Analytics: Record as compliant
         END
```

### **Scenario 2: Non-Compliant User (Applies Later)**

```
T+0min:   User posts: "On leave Feb 15th"
T+1min:   Bot detects message
T+30min:  Bot checks Zoho → NOT FOUND ❌
T+30min:  Bot posts: "Hi @user, please apply on Zoho"
T+12hr:   Bot re-checks → STILL NOT FOUND
T+12hr:   Bot sends DM: "Friendly reminder to apply"
T+20hr:   User applies on Zoho
T+48hr:   Bot re-checks → NOW FOUND ✅
T+48hr:   Bot posts: "Thanks for applying! (Verified)"
          Analytics: Record as "resolved_at_48hr"
          END
```

### **Scenario 3: Non-Compliant User (Never Applies)**

```
T+0min:   User posts: "I'll be absent Feb 18th"
T+30min:  Bot checks → NOT FOUND ❌
T+30min:  Reminder Level 0 set
T+12hr:   Bot checks → NOT FOUND
T+12hr:   Level 1: DM sent
T+48hr:   Bot checks → NOT FOUND
T+48hr:   Level 2: Urgent DM + Thread
T+72hr:   Bot checks → NOT FOUND
T+72hr:   Level 3: Admin notified
          Continue or escalate
```

### **Scenario 4: WFH Request**

```
T+0min:  User posts: "I'll be doing wfh on 18th"
T+1min:  Bot detects: is_wfh = True
T+1min:  Bot posts: "Hi @user, please ensure you've applied
                     for On Duty (WFH) on Zoho People.
                     (Note: Can't verify via API)"
         Analytics: Record as "wfh_mentioned"
         END (no verification, no reminders)
```

---

## 🔧 Configuration

### **Environment Variables (.env)**

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token
LEAVE_CHANNEL_ID=C0AALBN04KW

# Zoho Configuration
ZOHO_CLIENT_ID=your-client-id
ZOHO_CLIENT_SECRET=your-secret
ZOHO_REFRESH_TOKEN=your-token
ZOHO_DOMAIN=https://people.zoho.in

# Bot Behavior
POLL_INTERVAL=60                    # Seconds between polls
GRACE_PERIOD_MINUTES=30            # Before first Zoho check
REMINDER_INTERVALS=720,2880,4320   # 12hr, 48hr, 72hr (minutes)

# Analytics
ANALYTICS_ENABLED=true
ANALYTICS_DB_PATH=./bot_analytics.db
DASHBOARD_PORT=3005

# Templates
TEMPLATE_CONFIG_PATH=config/templates.yaml
NOTIFICATION_CONFIG_PATH=config/notification_config.yaml
```

### **Reminder Customization**

Edit `config/notification_config.yaml`:

```yaml
reminder_schedule:
  levels:
    - name: "first_followup"
      delay_hours: 12
      channels: ["dm"]

    - name: "second_escalation"
      delay_hours: 48
      channels: ["dm", "thread"]

    - name: "urgent_escalation"
      delay_hours: 72
      channels: ["dm", "admin"]
```

### **Message Templates**

Edit `config/templates.yaml`:

```yaml
templates:
  thread_reply:
    leave_found:
      en: "Thanks <@{user_id}> for applying on Zoho!"

    leave_not_found:
      en: "Hi <@{user_id}>, please apply for leave/WFH on Zoho also."

  dm_reminder:
    first_followup:
      en: "Hi {user_name}, friendly reminder to apply your leave on Zoho."
```

---

## 📊 Monitoring & Logs

### **Log Files**

```bash
# Bot main log
tail -f bot.log

# Dashboard log
tail -f dashboard/dashboard.log

# Analytics collector log
grep "analytics_collector" bot.log
```

### **Check Bot Status**

```bash
# Is bot running?
pgrep -f main.py

# Check recent activity
tail -20 bot.log | grep "Polling channel"

# Check pending reminders
cat pending_reminders.json | jq

# Check processed messages
cat .processed_messages.json | jq
```

### **Database Queries**

```bash
# Connect to analytics DB
sqlite3 bot_analytics.db

# Today's stats
SELECT COUNT(*) as total_leaves,
       SUM(CASE WHEN zoho_applied THEN 1 ELSE 0 END) as compliant
FROM leave_events
WHERE DATE(timestamp) = DATE('now');

# Compliance rate
SELECT date, compliance_rate
FROM daily_aggregates
ORDER BY date DESC
LIMIT 30;

# Recent events
SELECT timestamp, user_name, event_type, zoho_applied
FROM leave_events
ORDER BY timestamp DESC
LIMIT 10;
```

---

## 🚀 Summary

**The bot is a 5-phase system:**

1. **Detection** (60s) → Polls Slack, detects leave messages
2. **Analysis** (instant) → Parses dates, identifies type
3. **Verification** (30min+) → Checks Zoho for application
4. **Reminders** (12hr/48hr/72hr) → Escalating notifications
5. **Analytics** (continuous) → Tracks everything in DB

**Current Status:**
- ✅ Regular leaves: Fully automated
- ⚠️  WFH: Acknowledgment only (API limitation)
- ✅ Dashboard: http://localhost:3005

**Want automated WFH verification?**
See: `AUTOMATED_WFH_SOLUTIONS.md` for 5 solutions
