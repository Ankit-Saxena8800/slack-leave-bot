"""
Multi-Level Reminder Tracker for Leave Bot
Tracks users who need follow-up reminders with escalation levels
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

TRACKER_FILE = os.path.join(os.path.dirname(__file__), 'pending_reminders.json')


class ReminderLevel(Enum):
    """Reminder escalation levels"""
    PENDING = 0  # Initial state (no reminder sent yet)
    FIRST_FOLLOWUP = 1  # 12hr reminder
    SECOND_ESCALATION = 2  # 48hr reminder
    URGENT = 3  # 72hr urgent reminder
    RESOLVED = 99  # User applied on Zoho


class ReminderTracker:
    """Tracks pending reminders with multi-level escalation"""

    def __init__(self):
        self.reminders = self._load()

        # Check if in test mode (fast reminders)
        test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'

        if test_mode:
            # FAST MODE FOR TESTING - Minutes instead of hours
            self.escalation_schedule = {
                ReminderLevel.FIRST_FOLLOWUP: 0.033,  # 2 minutes
                ReminderLevel.SECOND_ESCALATION: 0.067,  # 4 minutes
                ReminderLevel.URGENT: 0.1  # 6 minutes
            }
            logger.info("⚡ TEST MODE: Using fast reminder schedule (2/4/6 minutes)")
        else:
            # Production schedule (hours)
            self.escalation_schedule = {
                ReminderLevel.FIRST_FOLLOWUP: 12,
                ReminderLevel.SECOND_ESCALATION: 48,
                ReminderLevel.URGENT: 72
            }

    def _load(self) -> Dict:
        """Load reminders from file"""
        if os.path.exists(TRACKER_FILE):
            try:
                with open(TRACKER_FILE, 'r') as f:
                    data = json.load(f)
                    # Validate data structure
                    if not isinstance(data, dict):
                        logger.error(f"Invalid reminder data format, expected dict, got {type(data)}")
                        return {}
                    return data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse reminder file: {e}")
                return {}
            except Exception as e:
                logger.error(f"Failed to load reminders: {e}")
                return {}
        return {}

    def _save(self):
        """Save reminders to file"""
        try:
            # Write to temp file first, then rename atomically
            temp_file = f"{TRACKER_FILE}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.reminders, f, indent=2)
            os.replace(temp_file, TRACKER_FILE)
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")

    def add_reminder(self, user_id: str, user_email: str, user_name: str,
                     channel_id: str, message_ts: str, leave_dates: List[str],
                     initial_timestamp: Optional[datetime] = None):
        """
        Add a new reminder to track

        Args:
            user_id: Slack user ID
            user_email: User email
            user_name: User display name
            channel_id: Slack channel ID
            message_ts: Slack message timestamp
            leave_dates: List of leave dates (ISO format)
            initial_timestamp: Initial detection time (defaults to now)
        """
        reminder_key = f"{user_id}_{message_ts}"

        if initial_timestamp is None:
            initial_timestamp = datetime.now()

        self.reminders[reminder_key] = {
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "channel_id": channel_id,
            "message_ts": message_ts,
            "leave_dates": leave_dates,
            "created_at": initial_timestamp.isoformat(),
            "reminder_level": ReminderLevel.PENDING.value,
            "reminder_history": [],  # List of sent reminders with timestamps
            "next_reminder_due": self._calculate_next_reminder_due(
                initial_timestamp, ReminderLevel.PENDING
            ).isoformat(),
            "resolved": False
        }
        self._save()
        logger.info(f"Added multi-level reminder tracking for {user_name} ({user_email})")

    def _calculate_next_reminder_due(
        self,
        created_at: datetime,
        current_level: ReminderLevel
    ) -> datetime:
        """
        Calculate when the next reminder should be sent

        Args:
            created_at: Initial creation timestamp
            current_level: Current reminder level

        Returns:
            Next reminder due datetime
        """
        # Get next level
        if current_level == ReminderLevel.PENDING:
            next_level = ReminderLevel.FIRST_FOLLOWUP
        elif current_level == ReminderLevel.FIRST_FOLLOWUP:
            next_level = ReminderLevel.SECOND_ESCALATION
        elif current_level == ReminderLevel.SECOND_ESCALATION:
            next_level = ReminderLevel.URGENT
        else:
            # No more escalations
            return created_at + timedelta(days=365)

        hours_delay = self.escalation_schedule.get(next_level, 12)
        return created_at + timedelta(hours=hours_delay)

    def get_due_reminders(self) -> List[Tuple[Dict, ReminderLevel]]:
        """
        Get reminders that are due for follow-up

        Returns:
            List of tuples (reminder_dict, next_level)
        """
        due = []
        now = datetime.now()

        for key, reminder in self.reminders.items():
            if reminder.get("resolved"):
                continue

            current_level = ReminderLevel(reminder.get("reminder_level", 0))

            # Skip if already at max level
            if current_level == ReminderLevel.URGENT:
                # URGENT reminders should only be sent ONCE at 72 hours
                # Check if we've already sent an URGENT reminder
                reminder_history = reminder.get("reminder_history", [])
                urgent_already_sent = any(
                    h.get("level") == ReminderLevel.URGENT.value
                    for h in reminder_history
                )

                if urgent_already_sent:
                    # Already sent URGENT reminder - stop escalating
                    continue

                # Check if we need to escalate to admin
                created_at = datetime.fromisoformat(reminder["created_at"])
                hours_elapsed = (now - created_at).total_seconds() / 3600
                if hours_elapsed >= 72:
                    due.append((reminder, ReminderLevel.URGENT))
                continue

            next_reminder_due = datetime.fromisoformat(reminder["next_reminder_due"])
            if now >= next_reminder_due:
                # Determine next level
                if current_level == ReminderLevel.PENDING:
                    next_level = ReminderLevel.FIRST_FOLLOWUP
                elif current_level == ReminderLevel.FIRST_FOLLOWUP:
                    next_level = ReminderLevel.SECOND_ESCALATION
                elif current_level == ReminderLevel.SECOND_ESCALATION:
                    next_level = ReminderLevel.URGENT
                else:
                    continue

                due.append((reminder, next_level))

        return due

    def mark_reminder_sent(
        self,
        user_id: str,
        message_ts: str,
        reminder_level: ReminderLevel,
        action_taken: str = "reminder_sent"
    ):
        """
        Mark that a reminder was sent and update to next level

        Args:
            user_id: Slack user ID
            message_ts: Message timestamp
            reminder_level: Level of reminder that was sent
            action_taken: Description of action (e.g., 'dm_sent', 'admin_notified')
        """
        key = f"{user_id}_{message_ts}"
        if key in self.reminders:
            reminder = self.reminders[key]
            now = datetime.now()

            # Add to history
            reminder["reminder_history"].append({
                "level": reminder_level.value,
                "sent_at": now.isoformat(),
                "action": action_taken
            })

            # Update current level
            reminder["reminder_level"] = reminder_level.value

            # Calculate next reminder due time
            created_at = datetime.fromisoformat(reminder["created_at"])
            reminder["next_reminder_due"] = self._calculate_next_reminder_due(
                created_at, reminder_level
            ).isoformat()

            self._save()
            logger.info(f"Marked {reminder_level.name} reminder sent for {user_id}")

    def mark_followup_sent(self, user_id: str, message_ts: str):
        """
        Mark that follow-up was sent (backward compatibility)

        Args:
            user_id: Slack user ID
            message_ts: Message timestamp
        """
        self.mark_reminder_sent(
            user_id, message_ts,
            ReminderLevel.FIRST_FOLLOWUP,
            "followup_sent"
        )

    def mark_resolved(self, user_id: str, message_ts: str):
        """
        Mark reminder as resolved (user applied on Zoho)

        Args:
            user_id: Slack user ID
            message_ts: Message timestamp
        """
        key = f"{user_id}_{message_ts}"
        if key in self.reminders:
            self.reminders[key]["resolved"] = True
            self.reminders[key]["resolved_at"] = datetime.now().isoformat()
            self.reminders[key]["reminder_level"] = ReminderLevel.RESOLVED.value
            self._save()
            logger.info(f"Marked reminder resolved for {user_id}")

    def is_already_tracked(self, user_id: str, message_ts: str) -> bool:
        """Check if this message is already being tracked"""
        key = f"{user_id}_{message_ts}"
        return key in self.reminders

    def get_reminder_stats(self, user_id: str, message_ts: str) -> Optional[Dict]:
        """
        Get statistics for a specific reminder

        Args:
            user_id: Slack user ID
            message_ts: Message timestamp

        Returns:
            Dictionary with reminder statistics or None
        """
        key = f"{user_id}_{message_ts}"
        reminder = self.reminders.get(key)

        if not reminder:
            return None

        created_at = datetime.fromisoformat(reminder["created_at"])
        now = datetime.now()
        hours_elapsed = (now - created_at).total_seconds() / 3600

        return {
            "level": ReminderLevel(reminder["reminder_level"]).name,
            "reminders_sent": len(reminder["reminder_history"]),
            "hours_elapsed": round(hours_elapsed, 1),
            "resolved": reminder["resolved"],
            "history": reminder["reminder_history"]
        }

    def get_all_pending(self) -> List[Dict]:
        """
        Get all pending (unresolved) reminders

        Returns:
            List of pending reminder dicts
        """
        pending = []
        for key, reminder in self.reminders.items():
            if not reminder.get("resolved"):
                pending.append(reminder)
        return pending

    def cleanup_old(self, days: int = 7):
        """
        Remove reminders older than X days

        Args:
            days: Number of days to keep reminders
        """
        cutoff = datetime.now() - timedelta(days=days)
        to_remove = []

        for key, reminder in self.reminders.items():
            # Use created_at if available, fallback to first_reminder_sent for backward compatibility
            created_str = reminder.get("created_at") or reminder.get("first_reminder_sent")
            if not created_str:
                continue

            created_at = datetime.fromisoformat(created_str)
            if created_at < cutoff:
                to_remove.append(key)

        for key in to_remove:
            del self.reminders[key]

        if to_remove:
            self._save()
            logger.info(f"Cleaned up {len(to_remove)} old reminders")
