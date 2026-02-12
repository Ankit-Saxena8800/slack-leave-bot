"""
Verification Storage for Slack Leave Bot
JSON-based storage for verification records
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
from dataclasses import asdict
import threading

logger = logging.getLogger(__name__)


class VerificationStorage:
    """Manages persistence of verification records"""

    def __init__(self, storage_file: str = None):
        """
        Initialize verification storage

        Args:
            storage_file: Path to JSON storage file
        """
        if storage_file is None:
            storage_file = os.path.join(
                os.path.dirname(__file__),
                'verification_records.json'
            )

        self.storage_file = storage_file
        self._lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure storage file exists"""
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w') as f:
                json.dump({"records": []}, f, indent=2)
            logger.info(f"Created verification storage file: {self.storage_file}")

    def _load_data(self) -> dict:
        """Load data from storage file"""
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load verification data: {e}")
            return {"records": []}

    def _save_data(self, data: dict):
        """Save data to storage file"""
        try:
            # Write to temp file first, then rename (atomic operation)
            temp_file = f"{self.storage_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            os.replace(temp_file, self.storage_file)

        except Exception as e:
            logger.error(f"Failed to save verification data: {e}", exc_info=True)

    def save_record(self, record) -> bool:
        """
        Save or update verification record

        Args:
            record: VerificationRecord instance

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                data = self._load_data()
                records = data.get("records", [])

                # Convert record to dict
                record_dict = asdict(record)

                # Check if record exists
                existing_idx = None
                for idx, existing_record in enumerate(records):
                    if existing_record.get("id") == record.id:
                        existing_idx = idx
                        break

                if existing_idx is not None:
                    # Update existing
                    records[existing_idx] = record_dict
                    logger.debug(f"Updated verification record {record.id}")
                else:
                    # Add new
                    records.append(record_dict)
                    logger.debug(f"Added new verification record {record.id}")

                data["records"] = records
                self._save_data(data)
                return True

            except Exception as e:
                logger.error(f"Failed to save record: {e}", exc_info=True)
                return False

    def load_record(self, record_id: str):
        """
        Load verification record by ID

        Args:
            record_id: Record ID

        Returns:
            VerificationRecord or None
        """
        from verification_workflow import VerificationRecord

        with self._lock:
            try:
                data = self._load_data()
                records = data.get("records", [])

                for record_dict in records:
                    if record_dict.get("id") == record_id:
                        return VerificationRecord(**record_dict)

                return None

            except Exception as e:
                logger.error(f"Failed to load record {record_id}: {e}")
                return None

    def load_pending_records(self) -> List:
        """
        Load all pending (non-verified) verification records

        Returns:
            List of VerificationRecord instances
        """
        from verification_workflow import VerificationRecord, LeaveVerificationState

        with self._lock:
            try:
                data = self._load_data()
                records = data.get("records", [])

                pending = []
                for record_dict in records:
                    # Include records that are not verified or resolved
                    state = record_dict.get("state")
                    if state not in [
                        LeaveVerificationState.VERIFIED.value,
                        LeaveVerificationState.RESOLVED.value
                    ]:
                        pending.append(VerificationRecord(**record_dict))

                return pending

            except Exception as e:
                logger.error(f"Failed to load pending records: {e}", exc_info=True)
                return []

    def load_all_records(self) -> List:
        """
        Load all verification records

        Returns:
            List of VerificationRecord instances
        """
        from verification_workflow import VerificationRecord

        with self._lock:
            try:
                data = self._load_data()
                records = data.get("records", [])

                return [VerificationRecord(**r) for r in records]

            except Exception as e:
                logger.error(f"Failed to load all records: {e}")
                return []

    def delete_record(self, record_id: str) -> bool:
        """
        Delete verification record

        Args:
            record_id: Record ID

        Returns:
            True if deleted, False otherwise
        """
        with self._lock:
            try:
                data = self._load_data()
                records = data.get("records", [])

                # Filter out the record
                new_records = [r for r in records if r.get("id") != record_id]

                if len(new_records) < len(records):
                    data["records"] = new_records
                    self._save_data(data)
                    logger.info(f"Deleted verification record {record_id}")
                    return True
                else:
                    logger.warning(f"Record {record_id} not found for deletion")
                    return False

            except Exception as e:
                logger.error(f"Failed to delete record: {e}")
                return False

    def cleanup_old(self, days: int = 30):
        """
        Remove verification records older than specified days

        Args:
            days: Number of days to keep records
        """
        with self._lock:
            try:
                cutoff = datetime.now() - timedelta(days=days)
                data = self._load_data()
                records = data.get("records", [])

                # Filter out old records
                new_records = []
                removed_count = 0

                for record in records:
                    created_at_str = record.get("created_at")
                    if created_at_str:
                        created_at = datetime.fromisoformat(created_at_str)
                        if created_at >= cutoff:
                            new_records.append(record)
                        else:
                            removed_count += 1
                    else:
                        # Keep records without timestamp
                        new_records.append(record)

                if removed_count > 0:
                    data["records"] = new_records
                    self._save_data(data)
                    logger.info(f"Cleaned up {removed_count} old verification records")

            except Exception as e:
                logger.error(f"Failed to cleanup old records: {e}", exc_info=True)

    def get_statistics(self) -> dict:
        """
        Get storage statistics

        Returns:
            Dictionary with statistics
        """
        from verification_workflow import LeaveVerificationState

        with self._lock:
            try:
                data = self._load_data()
                records = data.get("records", [])

                stats = {
                    "total": len(records),
                    "by_state": {}
                }

                for record in records:
                    state = record.get("state", "unknown")
                    stats["by_state"][state] = stats["by_state"].get(state, 0) + 1

                return stats

            except Exception as e:
                logger.error(f"Failed to get statistics: {e}")
                return {"total": 0, "by_state": {}}
