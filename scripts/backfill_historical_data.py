#!/usr/bin/env python3
"""
Historical Data Backfill Script
Parses bot.log to extract historical leave mentions and populate analytics database
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from database.db_manager import DatabaseManager, set_db_manager
from analytics_collector import AnalyticsCollector, set_analytics_collector

# Regex patterns to extract from logs
PATTERNS = {
    'leave_mention': re.compile(
        r'Processing leave message .* from user (\w+): (.+)'
    ),
    'user_info': re.compile(
        r'(\w+) has leave on Zoho|Sent reminder to (\w+)|Processing.*?(\w+@[\w.]+)'
    ),
    'zoho_found': re.compile(
        r'(\w+) has leave on Zoho'
    ),
    'zoho_not_found': re.compile(
        r'Sent reminder to (\w+)'
    ),
    'timestamp': re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
    ),
}


def parse_log_file(log_path: str, days_back: int = 90):
    """
    Parse bot.log to extract historical events

    Args:
        log_path: Path to bot.log file
        days_back: How many days back to parse (default 90)

    Returns:
        List of event dictionaries
    """
    print(f"\nParsing log file: {log_path}")
    print(f"Looking back: {days_back} days\n")

    if not os.path.exists(log_path):
        print(f"ERROR: Log file not found: {log_path}")
        return []

    events = []
    cutoff_date = datetime.now()
    cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_back)

    with open(log_path, 'r') as f:
        current_timestamp = None

        for line_num, line in enumerate(f, 1):
            # Extract timestamp
            ts_match = PATTERNS['timestamp'].search(line)
            if ts_match:
                try:
                    current_timestamp = datetime.strptime(ts_match.group(1), '%Y-%m-%d %H:%M:%S')
                except:
                    pass

            # Skip if too old
            if current_timestamp and current_timestamp < cutoff_date:
                continue

            # Check for leave mention
            leave_match = PATTERNS['leave_mention'].search(line)
            if leave_match and current_timestamp:
                user_id = leave_match.group(1)
                message = leave_match.group(2)

                event = {
                    'timestamp': current_timestamp,
                    'user_id': user_id,
                    'message': message,
                    'zoho_applied': None,
                    'line_number': line_num
                }
                events.append(event)

            # Check for Zoho found
            found_match = PATTERNS['zoho_found'].search(line)
            if found_match and events:
                # Update last event for this user
                user_name = found_match.group(1)
                for event in reversed(events):
                    if user_name in event.get('message', ''):
                        event['zoho_applied'] = True
                        break

            # Check for Zoho not found (reminder sent)
            not_found_match = PATTERNS['zoho_not_found'].search(line)
            if not_found_match and events:
                user_name = not_found_match.group(1)
                for event in reversed(events):
                    if user_name in event.get('message', ''):
                        event['zoho_applied'] = False
                        break

    print(f"✅ Found {len(events)} leave mention events")
    return events


def backfill_database(events):
    """
    Insert historical events into database

    Args:
        events: List of event dictionaries
    """
    print("\nInitializing database...")

    db_path = os.getenv('ANALYTICS_DB_PATH', './bot_analytics.db')
    db = DatabaseManager(db_path)

    if not db.init_db():
        print("❌ Failed to initialize database")
        return

    set_db_manager(db)
    print("✅ Database initialized")

    print("\nInitializing analytics collector...")
    analytics = AnalyticsCollector(buffer_size=10, enabled=True)
    set_analytics_collector(analytics)
    print("✅ Analytics collector initialized")

    print(f"\nBackfilling {len(events)} events...")

    inserted = 0
    skipped = 0

    for i, event in enumerate(events, 1):
        try:
            # Generate synthetic data for missing fields
            user_id = event['user_id']
            user_email = f"user_{user_id}@company.com"  # Synthetic
            user_name = f"User {user_id}"  # Synthetic
            message_ts = f"{int(event['timestamp'].timestamp())}.000000"

            # Estimate leave dates from timestamp
            leave_dates = [event['timestamp']]

            # Record event
            analytics.record_leave_mention(
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                event_type='leave_mentioned',
                message_ts=message_ts,
                leave_dates=leave_dates,
                zoho_applied=event['zoho_applied']
            )

            inserted += 1

            if i % 100 == 0:
                print(f"  Processed {i}/{len(events)} events...")

        except Exception as e:
            print(f"  ⚠️  Error processing event {i}: {e}")
            skipped += 1

    # Wait for buffer to flush
    print("\nWaiting for analytics buffer to flush...")
    import time
    time.sleep(5)

    print("\nShutting down analytics collector...")
    analytics.shutdown()

    print("\n" + "=" * 60)
    print("Backfill Complete!")
    print("=" * 60)
    print(f"Events inserted: {inserted}")
    print(f"Events skipped: {skipped}")
    print(f"Database: {db_path}")
    print("=" * 60)


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("Historical Data Backfill Script")
    print("=" * 60)

    # Find bot.log
    log_path = os.path.join(os.path.dirname(__file__), '..', 'bot.log')

    if not os.path.exists(log_path):
        print(f"\n❌ bot.log not found at: {log_path}")
        print("\nPlease ensure bot.log exists or specify the correct path.")
        sys.exit(1)

    # Parse logs
    events = parse_log_file(log_path, days_back=90)

    if not events:
        print("\n⚠️  No events found in log file")
        print("This could mean:")
        print("  - Log file is empty")
        print("  - No leave mentions in the last 90 days")
        print("  - Log format has changed")
        sys.exit(0)

    # Backfill
    backfill_database(events)

    print("\n✅ Historical data backfill completed successfully!")
    print("\nNext steps:")
    print("  1. Start dashboard: cd dashboard && node server.js")
    print("  2. Open browser: http://localhost:3001")
    print("  3. View historical analytics and trends")


if __name__ == '__main__':
    main()
