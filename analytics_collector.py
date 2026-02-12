"""
Analytics Collector for Slack Leave Bot
Non-blocking metrics collection with buffered writes for performance
"""

import logging
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from queue import Queue, Empty
import threading
from dataclasses import dataclass, asdict

from database.db_manager import get_db_manager

logger = logging.getLogger(__name__)


@dataclass
class LeaveEvent:
    """Leave event data structure"""
    timestamp: str
    user_id: str
    user_email: str
    user_name: str
    event_type: str  # 'leave_mentioned', 'wfh_mentioned'
    message_ts: str
    leave_dates: Optional[List[str]] = None
    zoho_applied: Optional[bool] = None


@dataclass
class ReminderEvent:
    """Reminder event data structure"""
    timestamp: str
    user_id: str
    user_email: Optional[str]
    reminder_type: str  # 'first', 'followup_12hr', 'second_escalation', 'urgent', 'resolved'
    message_ts: str
    action_taken: Optional[str] = None  # 'thread_reply', 'dm_sent', 'admin_notified'
    reminder_level: int = 0


class AnalyticsCollector:
    """
    Collects and persists analytics events with non-blocking buffered writes
    """

    def __init__(self, buffer_size: int = 10, enabled: bool = True):
        """
        Initialize analytics collector

        Args:
            buffer_size: Number of events to buffer before batch insert
            enabled: Whether analytics collection is enabled
        """
        self.enabled = enabled
        self.buffer_size = buffer_size
        self._event_queue = Queue()
        self._shutdown = threading.Event()
        self._worker_thread = None

        if self.enabled:
            self._start_worker()

    def _start_worker(self):
        """Start background worker thread for processing events"""
        self._worker_thread = threading.Thread(
            target=self._process_events,
            daemon=True,
            name="AnalyticsWorker"
        )
        self._worker_thread.start()
        logger.info("Analytics collector worker started")

    def _process_events(self):
        """Background worker that processes events from queue"""
        buffer: List[Dict[str, Any]] = []

        while not self._shutdown.is_set():
            try:
                # Wait for event with timeout
                event = self._event_queue.get(timeout=1.0)
                buffer.append(event)

                # Flush buffer when full or on shutdown
                if len(buffer) >= self.buffer_size:
                    self._flush_buffer(buffer)
                    buffer = []

            except Empty:
                # Timeout - flush buffer if not empty
                if buffer:
                    self._flush_buffer(buffer)
                    buffer = []
                continue
            except Exception as e:
                logger.error(f"Error in analytics worker: {e}", exc_info=True)

        # Final flush on shutdown
        if buffer:
            self._flush_buffer(buffer)

    def _flush_buffer(self, buffer: List[Dict[str, Any]]):
        """
        Flush buffered events to database

        Args:
            buffer: List of events to flush
        """
        if not buffer:
            return

        try:
            db_manager = get_db_manager()
            if not db_manager:
                logger.warning("Database manager not available, skipping analytics flush")
                return

            # Separate by event type
            leave_events = []
            reminder_events = []
            approval_events = []

            for event in buffer:
                if event['type'] == 'leave':
                    leave_events.append(event['data'])
                elif event['type'] == 'reminder':
                    reminder_events.append(event['data'])
                elif event['type'] == 'approval_action':
                    # Store for future - not yet implemented in DB
                    approval_events.append(event['data'])
                    logger.debug(f"Approval event queued (not persisted): {event['data'].get('action')}")

            # Batch insert leave events
            if leave_events:
                query = """
                    INSERT INTO leave_events
                    (timestamp, user_id, user_email, user_name, event_type,
                     message_ts, leave_dates, zoho_applied)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = [
                    (
                        e['timestamp'],
                        e['user_id'],
                        e['user_email'],
                        e['user_name'],
                        e['event_type'],
                        e['message_ts'],
                        json.dumps(e.get('leave_dates')) if e.get('leave_dates') else None,
                        e.get('zoho_applied')
                    )
                    for e in leave_events
                ]
                db_manager.execute_many(query, params)

            # Batch insert reminder events
            if reminder_events:
                query = """
                    INSERT INTO reminder_events
                    (timestamp, user_id, user_email, reminder_type,
                     message_ts, action_taken, reminder_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                params = [
                    (
                        e['timestamp'],
                        e['user_id'],
                        e.get('user_email'),
                        e['reminder_type'],
                        e['message_ts'],
                        e.get('action_taken'),
                        e.get('reminder_level', 0)
                    )
                    for e in reminder_events
                ]
                db_manager.execute_many(query, params)

            logger.debug(f"Flushed {len(buffer)} events to database")

        except Exception as e:
            logger.error(f"Failed to flush analytics buffer: {e}", exc_info=True)

    def record_leave_mention(
        self,
        user_id: str,
        user_email: str,
        user_name: str,
        event_type: str,
        message_ts: str,
        leave_dates: Optional[List[datetime]] = None,
        zoho_applied: Optional[bool] = None
    ):
        """
        Record a leave mention event

        Args:
            user_id: Slack user ID
            user_email: User email address
            user_name: User display name
            event_type: 'leave_mentioned' or 'wfh_mentioned'
            message_ts: Slack message timestamp
            leave_dates: List of parsed leave dates
            zoho_applied: Whether leave was found in Zoho
        """
        if not self.enabled:
            return

        try:
            event = {
                'type': 'leave',
                'data': {
                    'timestamp': datetime.now().isoformat(),
                    'user_id': user_id,
                    'user_email': user_email,
                    'user_name': user_name,
                    'event_type': event_type,
                    'message_ts': message_ts,
                    'leave_dates': [d.isoformat() for d in leave_dates] if leave_dates else None,
                    'zoho_applied': zoho_applied
                }
            }
            self._event_queue.put_nowait(event)

        except Exception as e:
            logger.error(f"Failed to record leave mention: {e}")

    def record_reminder(
        self,
        user_id: str,
        reminder_type: str,
        message_ts: str,
        action_taken: Optional[str] = None,
        reminder_level: int = 0,
        user_email: Optional[str] = None
    ):
        """
        Record a reminder event

        Args:
            user_id: Slack user ID
            reminder_type: Type of reminder
            message_ts: Original message timestamp
            action_taken: Action taken for reminder
            reminder_level: Escalation level (0-3)
            user_email: User email (optional)
        """
        if not self.enabled:
            return

        try:
            event = {
                'type': 'reminder',
                'data': {
                    'timestamp': datetime.now().isoformat(),
                    'user_id': user_id,
                    'user_email': user_email,
                    'reminder_type': reminder_type,
                    'message_ts': message_ts,
                    'action_taken': action_taken,
                    'reminder_level': reminder_level
                }
            }
            self._event_queue.put_nowait(event)

        except Exception as e:
            logger.error(f"Failed to record reminder: {e}")

    def record_approval_action(
        self,
        request_id: str,
        action: str,
        approver_id: str,
        level: int = 0,
        reason: Optional[str] = None
    ):
        """
        Record an approval workflow action (Phase 5)

        Args:
            request_id: Approval request ID
            action: Action taken ('approved', 'rejected', 'escalated')
            approver_id: Approver Slack ID
            level: Approval level
            reason: Optional rejection/approval reason
        """
        if not self.enabled:
            return

        try:
            # Note: approval_action events are not yet handled by _flush_buffer
            # They should be added to the database schema and flush logic
            event = {
                'type': 'approval_action',
                'data': {
                    'timestamp': datetime.now().isoformat(),
                    'request_id': request_id,
                    'action': action,
                    'approver_id': approver_id,
                    'level': level,
                    'reason': reason
                }
            }
            # Queue the event even if not yet persisted - for future implementation
            self._event_queue.put_nowait(event)
            logger.debug(f"Approval action recorded (not yet persisted to DB): {action} for {request_id}")

        except Exception as e:
            logger.error(f"Failed to record approval action: {e}")

    def record_zoho_check(
        self,
        user_id: str,
        user_email: str,
        user_name: str,
        message_ts: str,
        leave_dates: Optional[List[datetime]],
        zoho_applied: bool
    ):
        """
        Record a Zoho verification check result

        Args:
            user_id: Slack user ID
            user_email: User email address
            user_name: User display name
            message_ts: Slack message timestamp
            leave_dates: List of leave dates checked
            zoho_applied: Whether leave was found in Zoho
        """
        # Update existing leave event or create new one
        self.record_leave_mention(
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            event_type='leave_mentioned',
            message_ts=message_ts,
            leave_dates=leave_dates,
            zoho_applied=zoho_applied
        )

    def update_daily_aggregates(self, target_date: Optional[date] = None):
        """
        Update daily aggregates for a specific date

        Args:
            target_date: Date to aggregate (defaults to today)
        """
        if not self.enabled:
            return

        try:
            db_manager = get_db_manager()
            if not db_manager:
                return

            target_date = target_date or date.today()
            date_str = target_date.isoformat()

            # Calculate aggregates
            query = """
                SELECT
                    COUNT(*) as total_leaves,
                    SUM(CASE WHEN zoho_applied = 1 THEN 1 ELSE 0 END) as compliant_count,
                    SUM(CASE WHEN zoho_applied = 0 THEN 1 ELSE 0 END) as non_compliant_count
                FROM leave_events
                WHERE DATE(timestamp) = ?
            """
            result = db_manager.execute_query(query, (date_str,), fetch='one')

            if result and result[0]['total_leaves'] > 0:
                stats = result[0]
                compliance_rate = (
                    stats['compliant_count'] / stats['total_leaves']
                    if stats['total_leaves'] > 0 else 0
                )

                # Count reminders sent
                reminder_query = """
                    SELECT COUNT(*) as count
                    FROM reminder_events
                    WHERE DATE(timestamp) = ?
                """
                reminder_result = db_manager.execute_query(
                    reminder_query, (date_str,), fetch='one'
                )
                reminders_sent = reminder_result[0]['count'] if reminder_result else 0

                # Upsert daily aggregate
                upsert_query = """
                    INSERT INTO daily_aggregates
                    (date, total_leaves, compliant_count, non_compliant_count,
                     reminders_sent, compliance_rate, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        total_leaves = excluded.total_leaves,
                        compliant_count = excluded.compliant_count,
                        non_compliant_count = excluded.non_compliant_count,
                        reminders_sent = excluded.reminders_sent,
                        compliance_rate = excluded.compliance_rate,
                        last_updated = excluded.last_updated
                """
                db_manager.execute_query(
                    upsert_query,
                    (
                        date_str,
                        stats['total_leaves'],
                        stats['compliant_count'],
                        stats['non_compliant_count'],
                        reminders_sent,
                        compliance_rate,
                        datetime.now().isoformat()
                    )
                )

                logger.debug(f"Updated daily aggregates for {date_str}")

        except Exception as e:
            logger.error(f"Failed to update daily aggregates: {e}", exc_info=True)

    def shutdown(self):
        """Shutdown analytics collector gracefully"""
        if not self.enabled:
            return

        logger.info("Shutting down analytics collector")
        self._shutdown.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        logger.info("Analytics collector shutdown complete")


# Global analytics collector instance
_analytics_collector: Optional[AnalyticsCollector] = None


def get_analytics_collector() -> Optional[AnalyticsCollector]:
    """Get global analytics collector instance"""
    return _analytics_collector


def set_analytics_collector(collector: AnalyticsCollector):
    """Set global analytics collector instance"""
    global _analytics_collector
    _analytics_collector = collector
