# Integration Checklist

Quick reference guide for integrating the enhanced features into the existing slack-leave-bot.

## Prerequisites

- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Dashboard dependencies installed (`cd dashboard && npm install`)
- [ ] Database initialized
- [ ] Environment variables configured

## Step-by-Step Integration

### Step 1: Initialize Database (5 minutes)

```bash
cd /Users/ankitsaxena/slack-leave-bot

# Initialize database
python3 << EOF
from database.db_manager import DatabaseManager
db = DatabaseManager('./bot_analytics.db')
if db.init_db():
    print("✅ Database initialized successfully")
else:
    print("❌ Database initialization failed")
EOF
```

**Verify:**
- [ ] `bot_analytics.db` file created
- [ ] File size is ~20-30KB (empty tables with schema)

### Step 2: Update .env File (5 minutes)

```bash
# Backup existing .env
cp .env .env.backup

# Add new variables to .env
cat >> .env << 'EOF'

# ===== ENHANCED FEATURES =====

# Analytics
ANALYTICS_ENABLED=true
ANALYTICS_DB_PATH=./bot_analytics.db

# Dashboard
DASHBOARD_PORT=3001
DASHBOARD_HOST=0.0.0.0

# Date Parsing
DATE_PARSER_MAX_RANGE_DAYS=90
DATE_PARSER_WORKING_DAYS_ONLY=true

# Templates
TEMPLATE_CONFIG_PATH=config/templates.yaml
NOTIFICATION_CONFIG_PATH=config/notification_config.yaml

# Verification Workflow
VERIFICATION_GRACE_PERIOD_MINUTES=30
VERIFICATION_RE_CHECK_INTERVALS=12,24,48
VERIFICATION_ESCALATION_HOURS=72

# Approval Workflow (Phase 5 - not yet implemented)
APPROVAL_WORKFLOW_ENABLED=false
ORG_HIERARCHY_FILE=config/org_hierarchy.json
HR_USER_IDS=

# Optional: Email notifications
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Optional: SMS notifications
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
EOF
```

**Verify:**
- [ ] `.env` has new variables
- [ ] Backup created at `.env.backup`

### Step 3: Update main.py (15 minutes)

**Location:** `/Users/ankitsaxena/slack-leave-bot/main.py`

Add this function before the `main()` function:

```python
def initialize_enhanced_components():
    """Initialize all enhanced components"""
    import os
    from database.db_manager import DatabaseManager, set_db_manager
    from analytics_collector import AnalyticsCollector, set_analytics_collector
    from template_engine import TemplateEngine, set_template_engine
    from notification_router import NotificationRouter, set_notification_router
    from verification_workflow import VerificationWorkflowManager, set_verification_manager
    from verification_storage import VerificationStorage

    logger.info("Initializing enhanced components...")

    try:
        # Database
        db_path = os.getenv('ANALYTICS_DB_PATH', './bot_analytics.db')
        db_manager = DatabaseManager(db_path)
        if db_manager.init_db():
            set_db_manager(db_manager)
            logger.info("✅ Database initialized")
        else:
            logger.warning("⚠️  Database initialization failed, analytics disabled")

        # Analytics Collector
        analytics_enabled = os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true'
        analytics = AnalyticsCollector(buffer_size=10, enabled=analytics_enabled)
        set_analytics_collector(analytics)
        logger.info(f"✅ Analytics collector initialized (enabled={analytics_enabled})")

        # Template Engine
        template_path = os.getenv('TEMPLATE_CONFIG_PATH', 'config/templates.yaml')
        template_engine = TemplateEngine(template_path)
        set_template_engine(template_engine)
        logger.info("✅ Template engine initialized")

        # Notification Router
        router = NotificationRouter()
        set_notification_router(router)
        logger.info("✅ Notification router initialized")

        # Verification Workflow
        storage = VerificationStorage()
        grace_period = int(os.getenv('VERIFICATION_GRACE_PERIOD_MINUTES', '30'))
        re_check_intervals_str = os.getenv('VERIFICATION_RE_CHECK_INTERVALS', '12,24,48')
        re_check_intervals = [int(x) for x in re_check_intervals_str.split(',')]
        verification_manager = VerificationWorkflowManager(
            storage=storage,
            grace_period_minutes=grace_period,
            re_check_intervals_hours=re_check_intervals
        )
        set_verification_manager(verification_manager)
        logger.info("✅ Verification workflow initialized")

        logger.info("All enhanced components initialized successfully!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize enhanced components: {e}", exc_info=True)
        logger.warning("Bot will continue with reduced functionality")
```

Then in the `main()` function, add the call right after imports and before starting the bot:

```python
def main():
    # ... existing code ...

    # Initialize enhanced components
    initialize_enhanced_components()

    # ... rest of existing code ...
```

**Verify:**
- [ ] Function added before `main()`
- [ ] Call added in `main()` function
- [ ] No syntax errors (`python3 -m py_compile main.py`)

### Step 4: Update slack_bot_polling.py - Part 1: Imports & Init (20 minutes)

**Location:** `/Users/ankitsaxena/slack-leave-bot/slack_bot_polling.py`

**A. Add imports at the top:**

```python
# Add after existing imports
from date_parsing_service import DateParsingService
from template_engine import render_template
from analytics_collector import get_analytics_collector
from notification_router import get_notification_router
from verification_workflow import get_verification_manager
```

**B. In `__init__` method (around line 50), add:**

```python
def __init__(self, slack_client, zoho_client):
    # ... existing code ...

    # Initialize enhanced components
    self.date_parser = DateParsingService()
    self.analytics = get_analytics_collector()
    self.notification_router = get_notification_router()
    self.verification_manager = get_verification_manager()

    logger.info("Enhanced components loaded")
```

**Verify:**
- [ ] No import errors
- [ ] Bot starts without errors
- [ ] Check logs for "Enhanced components loaded"

### Step 5: Update slack_bot_polling.py - Part 2: Date Parsing (10 minutes)

**Replace the `_extract_dates` method (lines 127-157):**

```python
def _extract_dates(self, text):
    """Extract dates from text using enhanced date parser"""
    try:
        result = self.date_parser.parse_dates(text)

        if result.dates:
            logger.info(f"Parsed {len(result.dates)} dates from text (confidence: {result.confidence})")
            if result.date_range:
                logger.info(f"Date range detected: {result.date_range.start_date} to {result.date_range.end_date}")

            return result.dates
        else:
            logger.debug("No dates parsed from text")
            return []

    except Exception as e:
        logger.error(f"Error parsing dates: {e}", exc_info=True)
        return []
```

**Verify:**
- [ ] Test with various date formats:
  ```python
  python3 << EOF
  from date_parsing_service import DateParsingService
  parser = DateParsingService()

  tests = [
      "I'll be on leave tomorrow",
      "Taking leave from 15th to 20th",
      "Half day next Monday",
      "WFH rest of the week"
  ]

  for test in tests:
      result = parser.parse_dates(test)
      print(f"{test} → {len(result.dates)} dates")
  EOF
  ```

### Step 6: Update slack_bot_polling.py - Part 3: Templates (15 minutes)

**Replace hardcoded messages:**

**Location A: Line ~329 (leave found message)**

Replace:
```python
reply = f"Thanks <@{user_id}> for applying on Zoho!"
```

With:
```python
reply = render_template('thread_reply.leave_found', {'user_id': user_id})
if not reply:
    reply = f"Thanks <@{user_id}> for applying on Zoho!"  # Fallback
```

**Location B: Line ~336 (leave not found message)**

Replace:
```python
reply = f"Hi <@{user_id}>, I couldn't find your leave/WFH application on Zoho for {dates_str}. Please apply on Zoho also."
```

With:
```python
reply = render_template('thread_reply.leave_not_found', {
    'user_id': user_id,
    'leave_dates': dates
})
if not reply:
    reply = f"Hi <@{user_id}>, please apply for leave/WFH on Zoho also."  # Fallback
```

**Verify:**
- [ ] Messages render correctly
- [ ] Fallback works if template engine fails
- [ ] User mentions appear correctly

### Step 7: Update slack_bot_polling.py - Part 4: Analytics (15 minutes)

**In `_process_message` method, after processing a message:**

```python
def _process_message(self, message_data, dates):
    # ... existing code ...

    # Record analytics
    if self.analytics:
        try:
            self.analytics.record_leave_mention(
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                event_type='leave_mentioned',  # or 'wfh_mentioned'
                message_ts=message_ts,
                leave_dates=dates,
                zoho_applied=leave_found
            )
        except Exception as e:
            logger.error(f"Failed to record analytics: {e}")
```

**In `_send_thread_reply` method:**

```python
def _send_thread_reply(self, channel_id, thread_ts, message):
    # ... existing code ...

    # Record analytics if Zoho check
    if self.analytics and 'Zoho' in message:
        try:
            # Extract user info and status from context
            # (you may need to pass these as parameters)
            self.analytics.record_zoho_check(
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                message_ts=thread_ts,
                leave_dates=dates,
                zoho_applied=applied
            )
        except Exception as e:
            logger.error(f"Failed to record Zoho check: {e}")
```

**Verify:**
- [ ] Analytics events recorded in database
- [ ] Check with: `sqlite3 bot_analytics.db "SELECT COUNT(*) FROM leave_events;"`
- [ ] Bot continues working if analytics fails

### Step 8: Update slack_bot_polling.py - Part 5: Multi-Level Reminders (20 minutes)

**Update `_check_due_reminders` method:**

```python
def _check_due_reminders(self):
    """Check and send due reminders with multi-level escalation"""
    from reminder_tracker import ReminderLevel

    due_reminders = self.reminder_tracker.get_due_reminders()

    for reminder, next_level in due_reminders:
        try:
            user_id = reminder['user_id']
            user_name = reminder['user_name']
            leave_dates = reminder['leave_dates']

            # Determine template and channels based on level
            if next_level == ReminderLevel.FIRST_FOLLOWUP:
                template_key = 'dm_reminder.first_followup'
                channels = ['dm']
            elif next_level == ReminderLevel.SECOND_ESCALATION:
                template_key = 'dm_reminder.second_escalation'
                channels = ['dm', 'thread']
            elif next_level == ReminderLevel.URGENT:
                template_key = 'dm_reminder.urgent'
                channels = ['dm', 'admin']
            else:
                continue

            # Render message
            message = render_template(template_key, {
                'user_name': user_name,
                'leave_dates': leave_dates,
                'user_id': user_id
            })

            if not message:
                logger.error(f"Failed to render template: {template_key}")
                continue

            # Send DM
            if 'dm' in channels:
                try:
                    dm_response = self.slack_client.conversations_open(users=[user_id])
                    if dm_response['ok']:
                        self.slack_client.chat_postMessage(
                            channel=dm_response['channel']['id'],
                            text=message
                        )
                        logger.info(f"Sent {next_level.name} DM to {user_name}")
                except Exception as e:
                    logger.error(f"Failed to send DM: {e}")

            # Send thread reply if needed
            if 'thread' in channels:
                try:
                    self._send_thread_reply(
                        reminder['channel_id'],
                        reminder['message_ts'],
                        message
                    )
                except Exception as e:
                    logger.error(f"Failed to send thread reply: {e}")

            # Notify admin if needed
            if 'admin' in channels:
                # TODO: Implement admin notification
                logger.warning(f"Admin notification needed for {user_name}")

            # Mark reminder sent
            self.reminder_tracker.mark_reminder_sent(
                user_id,
                reminder['message_ts'],
                next_level,
                f"sent_to_{','.join(channels)}"
            )

            # Record analytics
            if self.analytics:
                self.analytics.record_reminder(
                    user_id=user_id,
                    reminder_type=next_level.name,
                    message_ts=reminder['message_ts'],
                    action_taken=','.join(channels),
                    reminder_level=next_level.value
                )

        except Exception as e:
            logger.error(f"Error processing reminder: {e}", exc_info=True)
```

**Verify:**
- [ ] Reminders escalate properly
- [ ] Check reminder levels in `pending_reminders.json`
- [ ] DMs sent at correct times

### Step 9: Test Dashboard (10 minutes)

```bash
# Start dashboard
cd /Users/ankitsaxena/slack-leave-bot/dashboard
npm start
```

**Manual Testing:**
- [ ] Open http://localhost:3001
- [ ] Dashboard loads without errors
- [ ] Stats cards show data (or 0 if no data yet)
- [ ] Charts render
- [ ] No console errors in browser

**Generate Test Data (optional):**
```python
# Create some test events
python3 << EOF
from database.db_manager import DatabaseManager
from analytics_collector import AnalyticsCollector
from datetime import datetime

db = DatabaseManager('./bot_analytics.db')
db.init_db()

collector = AnalyticsCollector(enabled=True)

# Add test events
for i in range(10):
    collector.record_leave_mention(
        user_id=f'U{i}',
        user_email=f'user{i}@company.com',
        user_name=f'User {i}',
        event_type='leave_mentioned',
        message_ts=f'123456789{i}.000000',
        leave_dates=[datetime.now()],
        zoho_applied=i % 2 == 0
    )

# Wait for buffer flush
import time
time.sleep(2)

print("✅ Test data created")
EOF
```

- [ ] Dashboard shows test data
- [ ] Refresh button works
- [ ] Period selector works

### Step 10: Final Verification (10 minutes)

**Test Complete Flow:**

1. **Post a test message in Slack:**
   ```
   "I'll be on leave tomorrow"
   ```

2. **Check logs:**
   - [ ] Date parsed correctly
   - [ ] Analytics recorded
   - [ ] Template rendered
   - [ ] Message sent to Slack

3. **Check database:**
   ```bash
   sqlite3 bot_analytics.db << EOF
   SELECT COUNT(*) as leave_events FROM leave_events;
   SELECT COUNT(*) as reminder_events FROM reminder_events;
   SELECT * FROM leave_events ORDER BY created_at DESC LIMIT 1;
   EOF
   ```
   - [ ] Event recorded in database

4. **Check dashboard:**
   - [ ] New event appears in "Recent Events"
   - [ ] Stats updated

5. **Test date parsing:**
   - Post: "I'll be on leave from 15th to 20th"
   - [ ] Multiple dates parsed
   - [ ] Date range detected in logs

6. **Test reminders:**
   - Wait for reminder to be due (or manually adjust time in `pending_reminders.json`)
   - [ ] Reminder sent
   - [ ] Level escalates correctly

## Rollback Procedure

If something goes wrong:

```bash
# Stop all processes
pkill -f "python main.py"
pkill -f "node.*dashboard"

# Restore backups
cp .env.backup .env
cp slack_bot_polling.py.backup slack_bot_polling.py  # if you backed it up
cp main.py.backup main.py  # if you backed it up

# Remove new files (optional)
rm -f bot_analytics.db
rm -f verification_records.json

# Restart bot
python main.py
```

## Troubleshooting

### Issue: Database not initializing

```bash
# Check permissions
ls -la bot_analytics.db

# Reinitialize
rm bot_analytics.db
python3 -c "from database.db_manager import DatabaseManager; db = DatabaseManager('./bot_analytics.db'); db.init_db()"
```

### Issue: Dashboard not starting

```bash
# Check Node.js version
node --version  # Should be 16+

# Reinstall dependencies
cd dashboard
rm -rf node_modules package-lock.json
npm install

# Check for port conflict
lsof -i :3001
```

### Issue: Templates not loading

```bash
# Check file exists
ls -la config/templates.yaml

# Test template engine
python3 << EOF
from template_engine import TemplateEngine
engine = TemplateEngine('config/templates.yaml')
result = engine.render('thread_reply.leave_found', {'user_id': 'U123'})
print(result)
EOF
```

### Issue: Analytics not recording

```bash
# Check database connection
python3 << EOF
from database.db_manager import DatabaseManager
db = DatabaseManager('./bot_analytics.db')
print(f"Health check: {db.checkHealth()}")
EOF

# Check analytics collector
python3 << EOF
from analytics_collector import get_analytics_collector
collector = get_analytics_collector()
print(f"Enabled: {collector.enabled if collector else 'Not initialized'}")
EOF
```

## Success Criteria

All boxes checked = successful integration! 🎉

- [ ] Database initialized and accessible
- [ ] Dashboard running on port 3001
- [ ] Bot starts without errors
- [ ] Date parsing working with various formats
- [ ] Templates rendering correctly
- [ ] Analytics recording events
- [ ] Reminders escalating properly
- [ ] All tests passing
- [ ] No performance degradation

## Next Steps After Integration

1. Monitor logs for errors
2. Review dashboard daily
3. Adjust reminder timings if needed
4. Customize templates for your organization
5. Consider implementing approval workflow (Phase 5)
6. Add historical data backfill
7. Implement comprehensive test suite

## Support

See IMPLEMENTATION_GUIDE.md for:
- Detailed troubleshooting
- Advanced configuration
- Performance tuning
- Maintenance procedures

---

**Estimated Total Time:** 2-3 hours
**Difficulty:** Intermediate
**Rollback Risk:** Low (backward compatible)
