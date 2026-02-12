#!/usr/bin/env python3
"""
Create Test Data for Dashboard
Simulates leave mentions and reminders to populate the dashboard
"""
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager, set_db_manager
from analytics_collector import AnalyticsCollector, set_analytics_collector

print("\n" + "=" * 60)
print("Creating Test Data for Dashboard")
print("=" * 60 + "\n")

# Initialize components
print("1. Initializing database...")
db = DatabaseManager('./bot_analytics.db')
if db.init_db():
    set_db_manager(db)
    print("   ✅ Database initialized")
else:
    print("   ❌ Database initialization failed")
    sys.exit(1)

print("\n2. Initializing analytics collector...")
collector = AnalyticsCollector(buffer_size=5, enabled=True)
set_analytics_collector(collector)
print("   ✅ Analytics collector initialized")

print("\n3. Creating test leave events...")

# Create diverse test data
test_users = [
    {"id": "U001", "email": "alice@company.com", "name": "Alice Smith"},
    {"id": "U002", "email": "bob@company.com", "name": "Bob Johnson"},
    {"id": "U003", "email": "carol@company.com", "name": "Carol Williams"},
    {"id": "U004", "email": "david@company.com", "name": "David Brown"},
    {"id": "U005", "email": "eve@company.com", "name": "Eve Davis"},
]

now = datetime.now()

# Create leave events over the past 7 days
event_count = 0
for day_offset in range(7):
    event_date = now - timedelta(days=day_offset)

    for i, user in enumerate(test_users):
        # Not every user every day
        if (day_offset + i) % 2 == 0:
            # Alternate between compliant and non-compliant
            zoho_applied = (event_count % 3) != 0  # 2/3 compliant

            collector.record_leave_mention(
                user_id=user["id"],
                user_email=user["email"],
                user_name=user["name"],
                event_type='leave_mentioned',
                message_ts=f"{int(event_date.timestamp())}.{i:06d}",
                leave_dates=[event_date],
                zoho_applied=zoho_applied
            )

            event_count += 1
            print(f"   Added event {event_count}: {user['name']} - {'✅ Compliant' if zoho_applied else '❌ Non-compliant'}")

print(f"\n   Total events created: {event_count}")

print("\n4. Creating test reminder events...")

# Create reminders for non-compliant users
reminder_count = 0
for i, user in enumerate(test_users[:3]):  # First 3 users have reminders
    reminder_date = now - timedelta(hours=12 * (i + 1))

    collector.record_reminder(
        user_id=user["id"],
        reminder_type='FIRST_FOLLOWUP',
        message_ts=f"{int(reminder_date.timestamp())}.000000",
        action_taken='dm_sent',
        reminder_level=1,
        user_email=user["email"]
    )

    reminder_count += 1
    print(f"   Added reminder {reminder_count}: {user['name']} - FIRST_FOLLOWUP")

print(f"\n   Total reminders created: {reminder_count}")

print("\n5. Waiting for analytics buffer to flush...")
import time
time.sleep(3)
print("   ✅ Buffer flushed")

print("\n6. Verifying data in database...")
leave_count = db.get_table_count('leave_events')
reminder_count_db = db.get_table_count('reminder_events')

print(f"   Leave events in DB: {leave_count}")
print(f"   Reminder events in DB: {reminder_count_db}")

if leave_count > 0 and reminder_count_db > 0:
    print("   ✅ Data successfully recorded")
else:
    print("   ⚠️  Some data may not have been recorded")

print("\n7. Updating daily aggregates...")
from datetime import date
for day_offset in range(7):
    target_date = date.today() - timedelta(days=day_offset)
    collector.update_daily_aggregates(target_date)
    print(f"   Updated aggregates for {target_date}")

print("\n8. Final verification...")
aggregates_count = db.get_table_count('daily_aggregates')
print(f"   Daily aggregates: {aggregates_count}")

# Shutdown collector
print("\n9. Shutting down collector...")
collector.shutdown()
print("   ✅ Collector shutdown complete")

print("\n" + "=" * 60)
print("Test Data Creation Complete!")
print("=" * 60)
print("\n📊 Summary:")
print(f"   Leave Events: {leave_count}")
print(f"   Reminder Events: {reminder_count_db}")
print(f"   Daily Aggregates: {aggregates_count}")
print("\n💡 Next Steps:")
print("   1. Refresh the dashboard: http://localhost:3001")
print("   2. You should now see data in all charts and tables")
print("   3. Run: bash test_dashboard.sh to verify API responses")
print("\n✅ Dashboard should now show populated data!")
print()
