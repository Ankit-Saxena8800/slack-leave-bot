"""
Approval Storage
JSON-based storage for approval requests with persistence and cleanup
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ApprovalStorage:
    """Manages persistence of approval requests to JSON file"""

    def __init__(self, storage_file: str = "approval_requests.json"):
        """
        Initialize approval storage

        Args:
            storage_file: Path to JSON storage file
        """
        self.storage_file = storage_file
        self.lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure storage file exists"""
        if not os.path.exists(self.storage_file):
            self._write_data({"approval_requests": [], "metadata": {"version": "1.0"}})
            logger.info(f"Created approval storage file: {self.storage_file}")

    def _read_data(self) -> Dict[str, Any]:
        """
        Read data from JSON file

        Returns:
            Data dictionary
        """
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read approval storage: {e}")
            return {"approval_requests": [], "metadata": {}}

    def _write_data(self, data: Dict[str, Any]):
        """
        Write data to JSON file

        Args:
            data: Data dictionary to write
        """
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to write approval storage: {e}")

    def save_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Save or update approval request

        Args:
            request_data: Approval request dictionary

        Returns:
            True if saved successfully
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                # Check if request already exists (by request_id)
                request_id = request_data.get("request_id")
                existing_idx = None
                for idx, req in enumerate(requests):
                    if req.get("request_id") == request_id:
                        existing_idx = idx
                        break

                # Update timestamp
                request_data["updated_at"] = datetime.now().isoformat()

                if existing_idx is not None:
                    # Update existing request
                    requests[existing_idx] = request_data
                    logger.debug(f"Updated approval request: {request_id}")
                else:
                    # Add new request
                    request_data["created_at"] = request_data.get("created_at", datetime.now().isoformat())
                    requests.append(request_data)
                    logger.debug(f"Created approval request: {request_id}")

                data["approval_requests"] = requests
                self._write_data(data)
                return True

            except Exception as e:
                logger.error(f"Failed to save approval request: {e}", exc_info=True)
                return False

    def load_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Load approval request by ID

        Args:
            request_id: Request ID

        Returns:
            Request data or None if not found
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                for req in requests:
                    if req.get("request_id") == request_id:
                        return req

                return None

            except Exception as e:
                logger.error(f"Failed to load approval request: {e}")
                return None

    def load_pending(self) -> List[Dict[str, Any]]:
        """
        Load all pending approval requests

        Returns:
            List of pending requests
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                # Filter pending requests
                pending = [
                    req for req in requests
                    if req.get("status") in ["pending", "escalated"]
                ]

                return pending

            except Exception as e:
                logger.error(f"Failed to load pending requests: {e}")
                return []

    def load_by_user(self, user_email: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load approval requests for a specific user

        Args:
            user_email: Employee email
            status: Optional status filter

        Returns:
            List of requests
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                # Filter by user
                user_requests = [
                    req for req in requests
                    if req.get("employee_email") == user_email
                ]

                # Apply status filter if provided
                if status:
                    user_requests = [req for req in user_requests if req.get("status") == status]

                return user_requests

            except Exception as e:
                logger.error(f"Failed to load user requests: {e}")
                return []

    def load_by_approver(self, approver_email: str, status: str = "pending") -> List[Dict[str, Any]]:
        """
        Load approval requests waiting for a specific approver

        Args:
            approver_email: Approver email
            status: Status filter (default: pending)

        Returns:
            List of requests
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                # Filter requests where this person is current approver
                approver_requests = []
                for req in requests:
                    if req.get("status") != status:
                        continue

                    approval_chain = req.get("approval_chain", [])
                    current_level = req.get("current_level", 0)

                    if current_level < len(approval_chain):
                        current_approver = approval_chain[current_level]
                        if current_approver.get("approver_email") == approver_email:
                            approver_requests.append(req)

                return approver_requests

            except Exception as e:
                logger.error(f"Failed to load approver requests: {e}")
                return []

    def load_expired(self, timeout_hours: int = 48) -> List[Dict[str, Any]]:
        """
        Load approval requests that have exceeded timeout

        Args:
            timeout_hours: Timeout threshold in hours

        Returns:
            List of expired requests
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                cutoff_time = datetime.now() - timedelta(hours=timeout_hours)
                expired = []

                for req in requests:
                    if req.get("status") != "pending":
                        continue

                    created_at_str = req.get("created_at")
                    if not created_at_str:
                        continue

                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if created_at < cutoff_time:
                            expired.append(req)
                    except:
                        continue

                return expired

            except Exception as e:
                logger.error(f"Failed to load expired requests: {e}")
                return []

    def cleanup_old(self, days: int = 90) -> int:
        """
        Remove old approval requests (completed/rejected older than specified days)

        Args:
            days: Age threshold in days

        Returns:
            Number of requests removed
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                cutoff_time = datetime.now() - timedelta(days=days)
                removed_count = 0

                # Keep only recent requests or pending/escalated requests
                filtered_requests = []
                for req in requests:
                    status = req.get("status")

                    # Always keep pending/escalated requests
                    if status in ["pending", "escalated"]:
                        filtered_requests.append(req)
                        continue

                    # Check age for completed/rejected requests
                    updated_at_str = req.get("updated_at") or req.get("created_at")
                    if not updated_at_str:
                        filtered_requests.append(req)
                        continue

                    try:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        if updated_at >= cutoff_time:
                            filtered_requests.append(req)
                        else:
                            removed_count += 1
                    except:
                        filtered_requests.append(req)

                if removed_count > 0:
                    data["approval_requests"] = filtered_requests
                    self._write_data(data)
                    logger.info(f"Cleaned up {removed_count} old approval requests")

                return removed_count

            except Exception as e:
                logger.error(f"Failed to cleanup old requests: {e}")
                return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics

        Returns:
            Statistics dictionary
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                stats = {
                    "total": len(requests),
                    "pending": 0,
                    "approved": 0,
                    "rejected": 0,
                    "expired": 0,
                    "escalated": 0,
                    "auto_approved": 0
                }

                for req in requests:
                    status = req.get("status", "unknown")
                    if status in stats:
                        stats[status] += 1

                return stats

            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                return {}

    def delete_request(self, request_id: str) -> bool:
        """
        Delete approval request

        Args:
            request_id: Request ID to delete

        Returns:
            True if deleted successfully
        """
        with self.lock:
            try:
                data = self._read_data()
                requests = data.get("approval_requests", [])

                # Filter out the request
                filtered = [req for req in requests if req.get("request_id") != request_id]

                if len(filtered) < len(requests):
                    data["approval_requests"] = filtered
                    self._write_data(data)
                    logger.info(f"Deleted approval request: {request_id}")
                    return True

                return False

            except Exception as e:
                logger.error(f"Failed to delete request: {e}")
                return False


# Global instance
_approval_storage: Optional[ApprovalStorage] = None


def get_approval_storage() -> Optional[ApprovalStorage]:
    """Get global approval storage instance"""
    return _approval_storage


def set_approval_storage(storage: ApprovalStorage):
    """Set global approval storage instance"""
    global _approval_storage
    _approval_storage = storage
