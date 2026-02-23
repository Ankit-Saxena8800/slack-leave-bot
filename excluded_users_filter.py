"""
Excluded Users Filter
Manages list of contractors and interns who should be excluded from bot monitoring
"""

import os
import csv
import logging
from typing import Set, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class ExcludedUsersFilter:
    """Filter to exclude contractors and interns from bot monitoring"""

    def __init__(self, csv_path: str = None):
        """
        Initialize excluded users filter

        Args:
            csv_path: Path to CSV file with excluded users
        """
        if csv_path is None:
            # Default to config/excluded_users.csv
            csv_path = os.path.join(
                os.path.dirname(__file__),
                "config",
                "excluded_users.csv"
            )

        self.csv_path = csv_path
        self.excluded_names: Set[str] = set()
        self.excluded_users: List[Dict] = []
        self._load_excluded_users()

    def _load_excluded_users(self):
        """Load excluded users from CSV file"""
        if not os.path.exists(self.csv_path):
            logger.warning(f"Excluded users file not found: {self.csv_path}")
            return

        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    full_name = row.get('full_name', '').strip()
                    if full_name:
                        # Store original name
                        self.excluded_users.append(row)

                        # Add normalized versions for matching
                        self.excluded_names.add(full_name.lower())

                        # Also add first name only for partial matching
                        first_name = full_name.split()[0].lower()
                        self.excluded_names.add(first_name)

            logger.info(f"Loaded {len(self.excluded_users)} excluded users ({len(self.excluded_names)} name variations)")

        except Exception as e:
            logger.error(f"Failed to load excluded users: {e}")

    def is_excluded(self, user_name: str, user_real_name: str = None) -> bool:
        """
        Check if a user should be excluded from bot monitoring

        Args:
            user_name: Slack display name or username
            user_real_name: Slack real name (full name)

        Returns:
            True if user should be excluded, False otherwise
        """
        if not self.excluded_names:
            return False

        # Normalize names for comparison
        names_to_check = []

        if user_name:
            names_to_check.append(user_name.lower().strip())

        if user_real_name:
            names_to_check.append(user_real_name.lower().strip())
            # Also check first name from real name
            first_name = user_real_name.split()[0].lower().strip()
            names_to_check.append(first_name)

        # Check if any name variation matches
        for name in names_to_check:
            if name in self.excluded_names:
                logger.info(f"User '{user_name}' ({user_real_name}) is excluded (matched: {name})")
                return True

        return False

    def get_excluded_users(self) -> List[Dict]:
        """Get list of all excluded users"""
        return self.excluded_users

    def reload(self):
        """Reload excluded users from CSV file"""
        self.excluded_names.clear()
        self.excluded_users.clear()
        self._load_excluded_users()
        logger.info("Reloaded excluded users list")


# Singleton instance
_filter_instance = None


def get_filter() -> ExcludedUsersFilter:
    """Get singleton instance of excluded users filter"""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = ExcludedUsersFilter()
    return _filter_instance
