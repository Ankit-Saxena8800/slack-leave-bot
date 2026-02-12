# Slack Leave Bot Enhancement - Implementation Guide

## Overview

This guide covers the implementation of comprehensive enhancements to the slack-leave-bot including:
- Analytics & Dashboard
- Enhanced Date Parsing
- Multi-Level Reminders
- Template System
- Verification Workflow
- Approval System (Phase 5)

## Phase 1: Database & Analytics (COMPLETED)

### Files Created

1. **Database Layer**
   - `database/schema.sql` - SQLite schema with 3 tables
   - `database/db_manager.py` - Connection manager with WAL mode
   - Tables: `leave_events`, `reminder_events`, `daily_aggregates`

2. **Analytics Collector**
   - `analytics_collector.py` - Non-blocking metrics collection
   - Buffered writes (batch of 10 events)
   - Graceful degradation if DB unavailable

3. **Dashboard (Node.js + Express)**
   - `dashboard/server.js` - Express server on port 3001
   - `dashboard/database.js` - SQLite connection module
   - `dashboard/package.json` - Dependencies
   - `dashboard/public/index.html` - Main UI
   - `dashboard/public/css/styles.css` - Styling
   - `dashboard/public/js/api-client.js` - API client
   - `dashboard/public/js/dashboard.js` - Chart.js visualization

### Installation Steps

```bash
# Install Python dependencies
cd /Users/ankitsaxena/slack-leave-bot
pip install -r requirements.txt

# Install Dashboard dependencies
cd dashboard
npm install

# Initialize database
python3 -c "from database.db_manager import DatabaseManager; db = DatabaseManager('./bot_analytics.db'); db.init_db()"
```

### Running the Dashboard

```bash
# Terminal 1: Run the bot (with analytics enabled)
cd /Users/ankitsaxena/slack-leave-bot
python main.py

# Terminal 2: Run the dashboard
cd /Users/ankitsaxena/slack-leave-bot/dashboard
npm start
# Access at: http://localhost:3001
```

### Dashboard Features

- **Real-time Stats**: Today's leaves, compliance rate, pending reminders
- **Trend Chart**: 7/30/90-day leave mentions and compliance rate
- **Active Reminders**: Live list of pending reminders
- **Top Non-Compliant Users**: Users with most non-compliance
- **Recent Events**: Last 50 events with auto-refresh (30s)
- **System Health**: Bot status and database health

## Phase 2: Enhanced Date Parsing (COMPLETED)

### Files Created

1. **Date Parsing Service**
   - `date_parsing_service.py` - Advanced date parsing
   - Supports:
     - Date ranges: "15th to 20th", "Jan 15 to Jan 20"
     - Relative dates: "next week", "rest of week", "end of month"
     - Partial leaves: "half day", "morning only", "2pm to 5pm"
     - Fuzzy parsing with dateparser library

### Usage Example

```python
from date_parsing_service import DateParsingService

parser = DateParsingService()

# Parse various date formats
result = parser.parse_dates("I'll be on leave from 15th to 20th")
# result.dates = [datetime(2026, 2, 15), datetime(2026, 2, 16), ...]
# result.date_range = DateRange(start=..., end=..., days_count=6)

result = parser.parse_dates("Taking half day tomorrow morning")
# result.dates = [datetime(2026, 2, 6)]
# result.leave_type = LeaveType.HALF_DAY
```

### Integration (TODO - Task #5)

Replace `_extract_dates()` in `slack_bot_polling.py` (lines 127-157):

```python
from date_parsing_service import DateParsingService

class SlackLeaveBot:
    def __init__(self):
        # ... existing code ...
        self.date_parser = DateParsingService()

    def _extract_dates(self, text):
        """Use enhanced date parsing"""
        result = self.date_parser.parse_dates(text)
        return result.dates
```

## Phase 3: Template System (COMPLETED)

### Files Created

1. **Template Configuration**
   - `config/templates.yaml` - Message templates (multi-language ready)
   - `config/notification_config.yaml` - Reminder schedule & rules
   - `template_engine.py` - Template rendering with variable substitution

2. **Notification Router**
   - `notification_router.py` - Multi-channel routing
   - Channels: Slack DM, Thread, Admin, Email (optional), SMS (optional)

### Templates Structure

```yaml
templates:
  thread_reply:
    leave_found:
      en: "Thanks <@{user_id}> for applying on Zoho! ✅"
    leave_not_found:
      en: "Hi <@{user_id}>, please apply on Zoho for {leave_dates_formatted}."

  dm_reminder:
    first_followup:
      en: "Hi {user_name}! Friendly reminder to apply your leave..."
```

### Reminder Schedule (Multi-Level)

```yaml
reminder_schedule:
  levels:
    - name: "grace_period"
      delay_minutes: 30
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

### Usage Example

```python
from template_engine import render_template

# Render template
message = render_template(
    'thread_reply.leave_not_found',
    context={
        'user_id': 'U123456',
        'leave_dates': [datetime(2026, 2, 15)],
        'user_name': 'John Doe'
    }
)
```

### Integration (TODO - Task #9)

Replace hardcoded strings in `slack_bot_polling.py`:

```python
# Line 329 (leave found)
# OLD: f"Thanks <@{user_id}> for applying on Zoho!"
# NEW:
message = render_template('thread_reply.leave_found', {'user_id': user_id})

# Line 336 (leave not found)
# OLD: f"Hi <@{user_id}>, please apply for leave/WFH on Zoho also."
# NEW:
message = render_template('thread_reply.leave_not_found', {
    'user_id': user_id,
    'leave_dates': dates
})
```

## Phase 4: Reminder Enhancement (COMPLETED)

### Files Modified/Created

1. **Enhanced Reminder Tracker**
   - `reminder_tracker.py` - Enhanced with multi-level support
   - New enum: `ReminderLevel` (PENDING, FIRST_FOLLOWUP, SECOND_ESCALATION, URGENT, RESOLVED)
   - State progression tracking with history
   - Configurable escalation schedule

### Reminder Levels

| Level | Timing | Action |
|-------|--------|--------|
| PENDING | Initial detection | Thread acknowledgment |
| FIRST_FOLLOWUP | +12 hours | DM reminder |
| SECOND_ESCALATION | +48 hours | DM + Thread reply |
| URGENT | +72 hours | DM + Admin notification |

### New Methods

```python
# Add reminder with initial timestamp
tracker.add_reminder(user_id, email, name, channel, msg_ts, dates, initial_timestamp)

# Get due reminders (returns list of (reminder, next_level))
due_reminders = tracker.get_due_reminders()

# Mark reminder sent at specific level
tracker.mark_reminder_sent(user_id, msg_ts, ReminderLevel.FIRST_FOLLOWUP, "dm_sent")

# Get reminder statistics
stats = tracker.get_reminder_stats(user_id, msg_ts)
# Returns: level, reminders_sent, hours_elapsed, resolved, history
```

### Integration (TODO - Task #9)

Update `_check_due_reminders()` in `slack_bot_polling.py`:

```python
def _check_due_reminders(self):
    """Check and send due reminders with escalation"""
    due_reminders = self.reminder_tracker.get_due_reminders()

    for reminder, next_level in due_reminders:
        # Get template based on level
        if next_level == ReminderLevel.FIRST_FOLLOWUP:
            template_key = 'dm_reminder.first_followup'
            channels = ['dm']
        elif next_level == ReminderLevel.SECOND_ESCALATION:
            template_key = 'dm_reminder.second_escalation'
            channels = ['dm', 'thread']
        elif next_level == ReminderLevel.URGENT:
            template_key = 'dm_reminder.urgent'
            channels = ['dm', 'admin']

        # Render message
        message = render_template(template_key, {
            'user_name': reminder['user_name'],
            'leave_dates': reminder['leave_dates']
        })

        # Route to channels
        notification = NotificationMessage(
            recipient_id=reminder['user_id'],
            message=message
        )
        router.route_notification(channels, notification)

        # Mark sent
        self.reminder_tracker.mark_reminder_sent(
            reminder['user_id'],
            reminder['message_ts'],
            next_level
        )
```

## Phase 5: Verification Workflow (COMPLETED)

### Files Created

1. **Verification Workflow**
   - `verification_workflow.py` - State machine for leave verification
   - `verification_storage.py` - JSON-based storage

### Verification States

```
DETECTED → GRACE_PERIOD (30min) → PENDING_VERIFICATION → VERIFIED/NOT_FOUND
                                                           ↓
                                      REMINDER_SENT → Re-check at 12hr, 24hr, 48hr
                                                           ↓
                                      ESCALATED (after 3 re-checks)
```

### Timeline

- **T+0**: Message detected → GRACE_PERIOD (send acknowledgment)
- **T+30min**: First Zoho check → VERIFIED or NOT_FOUND
- **T+30min**: If not found → REMINDER_SENT
- **T+12hr**: Re-verification check #1
- **T+24hr**: Re-verification check #2
- **T+48hr**: Re-verification check #3
- **T+72hr**: If still not found → ESCALATED to HR

### Usage Example

```python
from verification_workflow import VerificationWorkflowManager, LeaveVerificationState
from verification_storage import VerificationStorage

# Initialize
storage = VerificationStorage()
manager = VerificationWorkflowManager(
    storage=storage,
    grace_period_minutes=30,
    re_check_intervals_hours=[12, 24, 48]
)

# Create verification record
record = manager.create_verification_record(
    user_id='U123',
    user_email='user@company.com',
    user_name='John Doe',
    channel_id='C123',
    message_ts='1234567890.123456',
    leave_dates=[datetime(2026, 2, 15)]
)

# Check due verifications
due_records = manager.check_due_verifications()

# Perform verification
for record in due_records:
    result = manager.perform_verification(record, zoho_client)
    if result.found_in_zoho:
        print(f"Verified: {record.user_name}")
    else:
        print(f"Not found, next check: {result.next_check_at}")
```

### Integration (TODO - Task #11)

Modify `_process_message()` in `slack_bot_polling.py`:

```python
def _process_message(self, message_data, dates):
    """Create verification record instead of immediate check"""

    # Send acknowledgment
    ack_message = render_template('thread_reply.grace_period_acknowledgment', {
        'user_id': user_id,
        'leave_dates': dates
    })
    self._send_thread_reply(channel_id, message_ts, ack_message)

    # Create verification record
    record = self.verification_manager.create_verification_record(
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        channel_id=channel_id,
        message_ts=message_ts,
        leave_dates=dates
    )

    # Analytics
    self.analytics.record_leave_mention(
        user_id, user_email, user_name,
        event_type='leave_mentioned',
        message_ts=message_ts,
        leave_dates=dates
    )
```

Update `_check_due_reminders()` to also check due verifications:

```python
def _check_due_reminders(self):
    """Check due reminders and verifications"""

    # Check due verifications
    due_verifications = self.verification_manager.check_due_verifications()
    for record in due_verifications:
        result = self.verification_manager.perform_verification(
            record, self.zoho_client
        )

        if result.found_in_zoho:
            # Send success message
            message = render_template('verification.verified_after_reminder', {
                'user_id': record.user_id,
                'leave_dates': record.leave_dates
            })
            self._send_thread_reply(record.channel_id, record.message_ts, message)

        # ... handle not found case

    # Check due reminders (existing logic)
    # ...
```

## Phase 6: Approval Workflow (TODO - Task #15, #16)

### Files to Create

1. **Organizational Hierarchy**
   - `config/org_hierarchy.json` - Employee-manager mapping
   - `org_hierarchy.py` - Hierarchy management

2. **Approval Engine**
   - `approval_workflow.py` - Approval request engine
   - `approval_config.py` - Approval rules
   - `approval_storage.py` - JSON storage
   - `interactive_handler.py` - Slack button handler

### Approval Flow

```
Leave Detected → Create Approval Request → Route to Manager
                                              ↓
                Manager receives Slack message with buttons
                                              ↓
                [Approve] [Reject] [Request Details]
                                              ↓
                Update request status → Apply to Zoho (if approved)
                                              ↓
                Notify employee
```

### Implementation Notes

**IMPORTANT**: Interactive buttons require Socket Mode or HTTP endpoint.

**Option A: Socket Mode (Recommended)**
- Modify `main.py` to use Socket Mode
- The `slack_bot.py` file exists with Socket Mode implementation
- Register interactive handlers

**Option B: Hybrid Approach**
- Keep polling for messages
- Add Flask/FastAPI endpoint for interactivity
- Register interactivity URL in Slack app settings

### Slack App Configuration Required

1. Enable Interactivity & Shortcuts
2. Set Request URL (for Option B) or enable Socket Mode
3. Add scopes: `commands`, `im:history`, `chat:write`

## Environment Configuration (TODO - Task #19)

Add to `.env`:

```bash
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
VERIFICATION_RE_CHECK_INTERVALS=720,1440,2880
VERIFICATION_ESCALATION_HOURS=72

# Approval Workflow (Phase 5)
APPROVAL_WORKFLOW_ENABLED=false
ORG_HIERARCHY_FILE=config/org_hierarchy.json
HR_USER_IDS=U123456,U234567

# Optional: Email notifications
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Optional: SMS notifications
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

## Main.py Integration (TODO - Task #17)

Add initialization in `main.py`:

```python
import os
from database.db_manager import DatabaseManager, set_db_manager
from analytics_collector import AnalyticsCollector, set_analytics_collector
from template_engine import TemplateEngine, set_template_engine
from notification_router import NotificationRouter, set_notification_router
from verification_workflow import VerificationWorkflowManager, set_verification_manager
from verification_storage import VerificationStorage

def initialize_components():
    """Initialize all new components"""

    # Database
    db_path = os.getenv('ANALYTICS_DB_PATH', './bot_analytics.db')
    db_manager = DatabaseManager(db_path)
    if db_manager.init_db():
        set_db_manager(db_manager)
        logger.info("Database initialized")

    # Analytics
    analytics_enabled = os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true'
    analytics = AnalyticsCollector(buffer_size=10, enabled=analytics_enabled)
    set_analytics_collector(analytics)
    logger.info(f"Analytics collector initialized (enabled={analytics_enabled})")

    # Template Engine
    template_path = os.getenv('TEMPLATE_CONFIG_PATH', 'config/templates.yaml')
    template_engine = TemplateEngine(template_path)
    set_template_engine(template_engine)
    logger.info("Template engine initialized")

    # Notification Router
    router = NotificationRouter()
    # Register channels (done in slack_bot_polling.py with slack_client)
    set_notification_router(router)
    logger.info("Notification router initialized")

    # Verification Workflow
    storage = VerificationStorage()
    grace_period = int(os.getenv('VERIFICATION_GRACE_PERIOD_MINUTES', '30'))
    re_check_intervals = [int(x) for x in os.getenv('VERIFICATION_RE_CHECK_INTERVALS', '12,24,48').split(',')]
    verification_manager = VerificationWorkflowManager(
        storage=storage,
        grace_period_minutes=grace_period,
        re_check_intervals_hours=re_check_intervals
    )
    set_verification_manager(verification_manager)
    logger.info("Verification workflow initialized")

# In main():
initialize_components()
```

## Testing Strategy

### Unit Tests (TODO - Task #20)

Create `tests/` directory:

```bash
tests/
├── test_date_parsing.py
├── test_template_engine.py
├── test_verification_workflow.py
├── test_reminder_tracker.py
├── test_analytics_collector.py
└── test_notification_router.py
```

### Integration Testing

```python
# Test end-to-end flow
def test_leave_mention_flow():
    """Test full flow from message to analytics"""
    # 1. Simulate leave mention
    # 2. Verify verification record created
    # 3. Wait for grace period
    # 4. Check Zoho verification
    # 5. Verify analytics recorded
    # 6. Check reminder scheduled if not found
```

### Performance Testing

```python
# Test analytics overhead
def test_analytics_performance():
    """Ensure analytics adds <1% overhead"""
    import time

    # Measure without analytics
    start = time.time()
    for i in range(1000):
        process_message_without_analytics(msg)
    baseline = time.time() - start

    # Measure with analytics
    start = time.time()
    for i in range(1000):
        process_message_with_analytics(msg)
    with_analytics = time.time() - start

    overhead = (with_analytics - baseline) / baseline * 100
    assert overhead < 1.0, f"Analytics overhead too high: {overhead}%"
```

## Deployment Checklist

### Prerequisites

- [ ] Python 3.8+
- [ ] Node.js 16+
- [ ] SQLite 3
- [ ] Slack Bot Token with required scopes

### Installation

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Dashboard Dependencies**
   ```bash
   cd dashboard && npm install
   ```

3. **Initialize Database**
   ```bash
   python3 -c "from database.db_manager import DatabaseManager; db = DatabaseManager('./bot_analytics.db'); db.init_db()"
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Test Configuration**
   ```bash
   # Test date parsing
   python3 -c "from date_parsing_service import DateParsingService; parser = DateParsingService(); print(parser.parse_dates('next week'))"

   # Test template engine
   python3 -c "from template_engine import TemplateEngine; engine = TemplateEngine('config/templates.yaml'); print(engine.render('thread_reply.leave_found', {'user_id': 'U123'}))"
   ```

### Running

1. **Start Bot**
   ```bash
   python main.py
   ```

2. **Start Dashboard** (separate terminal)
   ```bash
   cd dashboard && npm start
   ```

3. **Access Dashboard**
   ```
   http://localhost:3001
   ```

### Verification

- [ ] Bot starts without errors
- [ ] Dashboard accessible
- [ ] Database file created (`bot_analytics.db`)
- [ ] Leave mention triggers analytics
- [ ] Dashboard shows real-time data
- [ ] Date parsing handles various formats
- [ ] Templates render correctly
- [ ] Reminders escalate properly
- [ ] Verification workflow operates with grace period

## Monitoring & Maintenance

### Log Files

- `bot.log` - Main bot log
- `bot_analytics.db` - Analytics database
- `pending_reminders.json` - Active reminders
- `verification_records.json` - Verification records

### Cleanup Tasks

```python
# Run daily
reminder_tracker.cleanup_old(days=7)
verification_manager.cleanup_old_records(days=30)
analytics.update_daily_aggregates()
```

### Database Maintenance

```bash
# Vacuum database weekly
python3 -c "from database.db_manager import DatabaseManager; db = DatabaseManager('./bot_analytics.db'); db.vacuum()"

# Check database size
du -h bot_analytics.db
```

## Troubleshooting

### Dashboard Not Loading

```bash
# Check if database exists
ls -lh bot_analytics.db

# Check dashboard logs
cd dashboard && npm start

# Test database connection
node -e "const db = require('./dashboard/database.js'); db.initDatabase('../bot_analytics.db'); console.log(db.checkHealth());"
```

### Analytics Not Recording

```python
# Check analytics collector
from analytics_collector import get_analytics_collector
collector = get_analytics_collector()
print(f"Enabled: {collector.enabled}")
print(f"Queue size: {collector._event_queue.qsize()}")
```

### Date Parsing Issues

```python
# Test date parser
from date_parsing_service import DateParsingService
parser = DateParsingService()

test_texts = [
    "I'll be on leave tomorrow",
    "Taking leave from 15th to 20th",
    "Half day next Monday",
    "WFH rest of the week"
]

for text in test_texts:
    result = parser.parse_dates(text)
    print(f"{text} → {result.dates}")
```

## Future Enhancements

### Planned Features

1. **Machine Learning**
   - Predict non-compliance risk
   - Smart reminder timing based on user patterns

2. **Mobile App**
   - React Native dashboard
   - Push notifications

3. **Integrations**
   - Google Calendar sync
   - Microsoft Teams support
   - JIRA time-off sync

4. **Advanced Analytics**
   - Team-level compliance reports
   - Department comparisons
   - Seasonal trend analysis

5. **Automation**
   - Auto-approve based on rules
   - Bulk import from calendar
   - End-of-month compliance reports

## Support

For issues or questions:
1. Check logs in `bot.log`
2. Review this guide
3. Check GitHub issues
4. Contact maintainer

## Version History

- **v1.0** - Initial enhanced implementation
  - Analytics & Dashboard
  - Enhanced date parsing
  - Multi-level reminders
  - Template system
  - Verification workflow
  - Foundation for approval system
