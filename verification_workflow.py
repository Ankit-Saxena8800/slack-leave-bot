"""
Verification Workflow for Slack Leave Bot
State machine for leave verification with grace periods and re-checks
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import os

from verification_storage import VerificationStorage

logger = logging.getLogger(__name__)


class LeaveVerificationState(Enum):
    """Leave verification states"""
    DETECTED = "detected"  # Initial detection
    GRACE_PERIOD = "grace_period"  # 30min grace before first check
    PENDING_VERIFICATION = "pending_verification"  # Waiting for Zoho check
    VERIFIED = "verified"  # Found in Zoho
    NOT_FOUND = "not_found"  # Not found in Zoho
    REMINDER_SENT = "reminder_sent"  # Reminder sent to user
    ESCALATED = "escalated"  # Escalated to admin
    RESOLVED = "resolved"  # User eventually applied


@dataclass
class VerificationRecord:
    """Verification record data structure"""
    id: str  # Unique identifier
    user_id: str
    user_email: str
    user_name: str
    channel_id: str
    message_ts: str
    leave_dates: List[str]  # ISO format dates
    state: str  # LeaveVerificationState value
    created_at: str  # ISO timestamp
    grace_period_until: Optional[str] = None  # ISO timestamp
    next_check_at: Optional[str] = None  # ISO timestamp
    checks_performed: int = 0
    check_history: List[Dict[str, Any]] = None
    last_state_change: Optional[str] = None  # ISO timestamp
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.check_history is None:
            self.check_history = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class VerificationResult:
    """Result of a verification check"""
    record_id: str
    success: bool
    found_in_zoho: bool
    new_state: LeaveVerificationState
    message: str
    next_check_at: Optional[datetime] = None


class VerificationWorkflowManager:
    """Manages verification workflow with grace periods and re-checks"""

    def __init__(
        self,
        storage: VerificationStorage,
        grace_period_minutes: int = 30,
        re_check_intervals_hours: List[int] = None,
        max_re_checks: int = 3
    ):
        """
        Initialize verification workflow manager

        Args:
            storage: VerificationStorage instance
            grace_period_minutes: Grace period before first check
            re_check_intervals_hours: List of intervals for re-checks
            max_re_checks: Maximum number of re-checks
        """
        self.storage = storage
        self.grace_period_minutes = grace_period_minutes
        self.re_check_intervals_hours = re_check_intervals_hours or [12, 24, 48]
        self.max_re_checks = max_re_checks

    def create_verification_record(
        self,
        user_id: str,
        user_email: str,
        user_name: str,
        channel_id: str,
        message_ts: str,
        leave_dates: List[datetime]
    ) -> VerificationRecord:
        """
        Create a new verification record

        Args:
            user_id: Slack user ID
            user_email: User email
            user_name: User display name
            channel_id: Slack channel ID
            message_ts: Slack message timestamp
            leave_dates: List of leave dates

        Returns:
            Created VerificationRecord
        """
        now = datetime.now()
        grace_period_until = now + timedelta(minutes=self.grace_period_minutes)

        # Generate unique ID
        record_id = f"{user_id}_{message_ts}_{int(now.timestamp())}"

        record = VerificationRecord(
            id=record_id,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            channel_id=channel_id,
            message_ts=message_ts,
            leave_dates=[d.date().isoformat() if isinstance(d, datetime) else d for d in leave_dates],
            state=LeaveVerificationState.GRACE_PERIOD.value,
            created_at=now.isoformat(),
            grace_period_until=grace_period_until.isoformat(),
            next_check_at=grace_period_until.isoformat(),
            last_state_change=now.isoformat()
        )

        self.storage.save_record(record)
        logger.info(f"Created verification record {record_id} for {user_name} with {self.grace_period_minutes}min grace period")

        return record

    def check_due_verifications(self) -> List[VerificationRecord]:
        """
        Get verification records that are due for checking

        Returns:
            List of VerificationRecord that need verification
        """
        now = datetime.now()
        due_records = []

        pending_records = self.storage.load_pending_records()

        for record in pending_records:
            # Skip if already verified or resolved
            if record.state in [
                LeaveVerificationState.VERIFIED.value,
                LeaveVerificationState.RESOLVED.value
            ]:
                continue

            # Check if next_check_at is due
            if record.next_check_at:
                next_check = datetime.fromisoformat(record.next_check_at)
                if now >= next_check:
                    due_records.append(record)

        logger.debug(f"Found {len(due_records)} verifications due for checking")
        return due_records

    def perform_verification(
        self,
        record: VerificationRecord,
        zoho_client
    ) -> VerificationResult:
        """
        Perform verification check using Zoho client

        Args:
            record: VerificationRecord to verify
            zoho_client: ZohoClient instance

        Returns:
            VerificationResult
        """
        try:
            # Parse leave dates
            from datetime import datetime as dt
            leave_dates = [
                dt.fromisoformat(d) if isinstance(d, str) else d
                for d in record.leave_dates
            ]

            # Check Zoho
            found_in_zoho = zoho_client.check_leave_applied(
                user_email=record.user_email,
                leave_dates=leave_dates
            )

            # Update record
            record.checks_performed += 1
            record.check_history.append({
                "checked_at": datetime.now().isoformat(),
                "found": found_in_zoho,
                "check_number": record.checks_performed
            })

            # Determine new state
            if found_in_zoho:
                new_state = LeaveVerificationState.VERIFIED
                next_check = None
                message = f"Leave verified in Zoho for {record.user_name}"
            else:
                # Not found - determine next action
                if record.checks_performed >= self.max_re_checks:
                    new_state = LeaveVerificationState.ESCALATED
                    next_check = None
                    message = f"Leave still not found after {record.checks_performed} checks - escalating"
                else:
                    new_state = LeaveVerificationState.NOT_FOUND
                    # Schedule next re-check
                    next_check = self._calculate_next_check(record)
                    message = f"Leave not found in Zoho - will re-check at {next_check.isoformat()}"

            # Transition state
            self.transition_state(record, new_state, message)

            if next_check:
                record.next_check_at = next_check.isoformat()
                self.storage.save_record(record)

            return VerificationResult(
                record_id=record.id,
                success=True,
                found_in_zoho=found_in_zoho,
                new_state=new_state,
                message=message,
                next_check_at=next_check
            )

        except Exception as e:
            logger.error(f"Verification failed for record {record.id}: {e}", exc_info=True)
            return VerificationResult(
                record_id=record.id,
                success=False,
                found_in_zoho=False,
                new_state=LeaveVerificationState(record.state),
                message=f"Verification check failed: {e}"
            )

    def _calculate_next_check(self, record: VerificationRecord) -> datetime:
        """
        Calculate next check time based on check history

        Args:
            record: VerificationRecord

        Returns:
            Next check datetime
        """
        created_at = datetime.fromisoformat(record.created_at)
        check_number = record.checks_performed

        if check_number <= len(self.re_check_intervals_hours):
            hours_offset = self.re_check_intervals_hours[check_number - 1]
        else:
            # Use last interval
            hours_offset = self.re_check_intervals_hours[-1]

        next_check = created_at + timedelta(hours=hours_offset)
        return next_check

    def transition_state(
        self,
        record: VerificationRecord,
        new_state: LeaveVerificationState,
        reason: str
    ):
        """
        Transition verification record to new state

        Args:
            record: VerificationRecord
            new_state: New LeaveVerificationState
            reason: Reason for transition
        """
        old_state = record.state
        record.state = new_state.value
        record.last_state_change = datetime.now().isoformat()

        # Add to metadata
        if 'state_history' not in record.metadata:
            record.metadata['state_history'] = []

        record.metadata['state_history'].append({
            'from_state': old_state,
            'to_state': new_state.value,
            'reason': reason,
            'timestamp': record.last_state_change
        })

        self.storage.save_record(record)
        logger.info(f"Record {record.id} transitioned from {old_state} to {new_state.value}: {reason}")

    def mark_resolved(self, record_id: str):
        """
        Mark verification record as resolved

        Args:
            record_id: Verification record ID
        """
        record = self.storage.load_record(record_id)
        if record:
            self.transition_state(
                record,
                LeaveVerificationState.RESOLVED,
                "User applied leave on Zoho"
            )

    def get_record_by_message(self, user_id: str, message_ts: str) -> Optional[VerificationRecord]:
        """
        Get verification record by user and message

        Args:
            user_id: Slack user ID
            message_ts: Message timestamp

        Returns:
            VerificationRecord or None
        """
        all_records = self.storage.load_pending_records()
        for record in all_records:
            if record.user_id == user_id and record.message_ts == message_ts:
                return record
        return None

    def get_pending_count(self) -> int:
        """
        Get count of pending verifications

        Returns:
            Number of pending verifications
        """
        pending = self.storage.load_pending_records()
        return len([r for r in pending if r.state not in [
            LeaveVerificationState.VERIFIED.value,
            LeaveVerificationState.RESOLVED.value
        ]])

    def cleanup_old_records(self, days: int = 30):
        """
        Clean up old verification records

        Args:
            days: Keep records from last N days
        """
        self.storage.cleanup_old(days)


# Global verification workflow manager instance
_verification_manager: Optional[VerificationWorkflowManager] = None


def get_verification_manager() -> Optional[VerificationWorkflowManager]:
    """Get global verification workflow manager"""
    return _verification_manager


def set_verification_manager(manager: VerificationWorkflowManager):
    """Set global verification workflow manager"""
    global _verification_manager
    _verification_manager = manager
