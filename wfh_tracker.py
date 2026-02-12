#!/usr/bin/env python3
"""
Manual WFH tracking system
Users can confirm WFH application via Slack reactions or commands
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

WFH_TRACKING_FILE = Path(__file__).parent / "wfh_applications.json"


class WFHTracker:
    """Track WFH applications manually"""

    def __init__(self):
        self.wfh_records = self._load_records()

    def _load_records(self) -> Dict:
        """Load WFH tracking records"""
        try:
            if WFH_TRACKING_FILE.exists():
                with open(WFH_TRACKING_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load WFH records: {e}")
        return {"pending": [], "confirmed": [], "updated": datetime.now().isoformat()}

    def _save_records(self):
        """Save WFH tracking records"""
        try:
            self.wfh_records["updated"] = datetime.now().isoformat()
            with open(WFH_TRACKING_FILE, 'w') as f:
                json.dump(self.wfh_records, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save WFH records: {e}")

    def add_pending_wfh(self, user_id: str, user_email: str, user_name: str,
                        dates: List[datetime], message_ts: str) -> str:
        """Add a pending WFH request"""
        record = {
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "dates": [d.isoformat() for d in dates],
            "message_ts": message_ts,
            "detected_at": datetime.now().isoformat(),
            "status": "pending"
        }

        self.wfh_records["pending"].append(record)
        self._save_records()

        logger.info(f"Added pending WFH for {user_name}: {len(dates)} dates")
        return record.get("message_ts")

    def confirm_wfh(self, message_ts: str, confirmed_by: str = "user") -> bool:
        """Mark WFH as confirmed (applied on Zoho)"""
        # Find in pending
        for i, record in enumerate(self.wfh_records["pending"]):
            if record["message_ts"] == message_ts:
                record["status"] = "confirmed"
                record["confirmed_at"] = datetime.now().isoformat()
                record["confirmed_by"] = confirmed_by

                # Move to confirmed
                self.wfh_records["confirmed"].append(record)
                self.wfh_records["pending"].pop(i)
                self._save_records()

                logger.info(f"WFH confirmed: {record['user_name']}")
                return True

        return False

    def is_wfh_confirmed(self, user_email: str, date: datetime) -> bool:
        """Check if user has confirmed WFH for a specific date"""
        date_str = date.date().isoformat()

        for record in self.wfh_records["confirmed"]:
            if record["user_email"] == user_email:
                for record_date in record["dates"]:
                    if record_date.startswith(date_str):
                        return True
        return False

    def get_pending_wfh(self, user_email: Optional[str] = None) -> List[Dict]:
        """Get pending WFH requests"""
        pending = self.wfh_records["pending"]

        if user_email:
            return [r for r in pending if r["user_email"] == user_email]

        return pending

    def get_overdue_wfh(self, hours: int = 12) -> List[Dict]:
        """Get WFH requests pending for more than X hours"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=hours)
        overdue = []

        for record in self.wfh_records["pending"]:
            detected_at = datetime.fromisoformat(record["detected_at"])
            if detected_at < cutoff:
                overdue.append(record)

        return overdue


# Integration functions for slack_bot_polling.py

def handle_wfh_confirmation_reaction(tracker: WFHTracker, message_ts: str,
                                     user_id: str) -> bool:
    """
    Handle when user adds a checkmark reaction to confirm WFH application

    Usage in slack_bot_polling.py:
    - Listen for reaction_added event
    - If reaction is :white_check_mark: or :heavy_check_mark:
    - Call this function
    """
    return tracker.confirm_wfh(message_ts, confirmed_by=user_id)


def get_wfh_status_message(tracker: WFHTracker, user_email: str,
                           dates: List[datetime]) -> str:
    """
    Get status message for WFH request

    Returns: String indicating if WFH is confirmed or pending
    """
    all_confirmed = all(tracker.is_wfh_confirmed(user_email, date) for date in dates)

    if all_confirmed:
        return "✅ WFH application confirmed"

    pending_count = len(tracker.get_pending_wfh(user_email))
    if pending_count > 0:
        return f"⏳ {pending_count} WFH request(s) pending confirmation"

    return "❓ WFH status unknown"
