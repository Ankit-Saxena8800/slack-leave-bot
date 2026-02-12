"""
Approval Configuration
Defines approval rules, thresholds, timeouts, and escalation logic
"""

import os
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Approval request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class ApprovalAction(Enum):
    """Actions that can be taken on approval requests"""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFO = "request_info"
    ESCALATE = "escalate"
    HR_OVERRIDE_APPROVE = "hr_override_approve"
    HR_OVERRIDE_REJECT = "hr_override_reject"


@dataclass
class ApprovalRule:
    """Defines an approval rule"""
    min_days: int
    max_days: int
    requires_manager: bool
    requires_senior_manager: bool
    auto_approve: bool
    description: str

    def applies_to(self, leave_days: int) -> bool:
        """Check if rule applies to given leave duration"""
        return self.min_days <= leave_days <= self.max_days


class ApprovalConfig:
    """Configuration for approval workflow"""

    def __init__(self):
        """Initialize approval configuration from environment variables"""
        # Duration thresholds (in days)
        self.auto_approve_days = int(os.getenv('AUTO_APPROVE_DAYS', '2'))
        self.standard_approval_days = int(os.getenv('STANDARD_APPROVAL_DAYS', '5'))
        self.senior_approval_days = int(os.getenv('SENIOR_APPROVAL_DAYS', '5'))

        # Timeout settings (in hours)
        self.approval_timeout_hours = int(os.getenv('APPROVAL_TIMEOUT_HOURS', '48'))
        self.reminder_before_timeout_hours = int(os.getenv('REMINDER_BEFORE_TIMEOUT_HOURS', '12'))

        # Escalation settings
        self.escalation_enabled = os.getenv('ESCALATION_ENABLED', 'true').lower() == 'true'
        self.auto_escalate_on_timeout = os.getenv('AUTO_ESCALATE_ON_TIMEOUT', 'true').lower() == 'true'

        # Notification settings
        self.notify_employee_on_approval = True
        self.notify_employee_on_rejection = True
        self.notify_hr_on_rejection = True

        # HR override
        self.hr_can_override = True
        self.hr_user_ids = self._parse_hr_user_ids()

        # WFH-specific thresholds (optional)
        self.wfh_auto_approve_days = int(os.getenv('WFH_AUTO_APPROVE_DAYS', str(self.auto_approve_days)))
        self.wfh_requires_approval = os.getenv('WFH_REQUIRES_APPROVAL', 'true').lower() == 'true'

        # Define approval rules
        self.rules = self._define_rules()

        logger.info(f"Approval config initialized: auto_approve={self.auto_approve_days} days, "
                   f"timeout={self.approval_timeout_hours}hrs, escalation={self.escalation_enabled}")

    def _parse_hr_user_ids(self) -> List[str]:
        """Parse HR user IDs from environment"""
        hr_ids_str = os.getenv('HR_USER_IDS', '')
        if hr_ids_str:
            return [uid.strip() for uid in hr_ids_str.split(',') if uid.strip()]
        return []

    def _define_rules(self) -> List[ApprovalRule]:
        """Define approval rules based on leave duration"""
        return [
            ApprovalRule(
                min_days=0,
                max_days=self.auto_approve_days,
                requires_manager=False,
                requires_senior_manager=False,
                auto_approve=True,
                description=f"Auto-approve for leaves up to {self.auto_approve_days} days"
            ),
            ApprovalRule(
                min_days=self.auto_approve_days + 1,
                max_days=self.senior_approval_days,
                requires_manager=True,
                requires_senior_manager=False,
                auto_approve=False,
                description=f"Manager approval required for {self.auto_approve_days + 1}-{self.senior_approval_days} days"
            ),
            ApprovalRule(
                min_days=self.senior_approval_days + 1,
                max_days=999,  # No upper limit
                requires_manager=True,
                requires_senior_manager=True,
                auto_approve=False,
                description=f"Manager + Senior Manager approval required for {self.senior_approval_days + 1}+ days"
            )
        ]

    def get_applicable_rule(self, leave_days: int) -> ApprovalRule:
        """
        Get the applicable approval rule for given leave duration

        Args:
            leave_days: Number of leave days

        Returns:
            Applicable ApprovalRule
        """
        for rule in self.rules:
            if rule.applies_to(leave_days):
                return rule

        # Default to most restrictive rule
        return self.rules[-1]

    def requires_approval(self, leave_days: int, is_wfh: bool = False) -> bool:
        """
        Check if leave duration requires approval

        Args:
            leave_days: Number of leave days
            is_wfh: Whether this is a WFH request (uses WFH-specific rules)

        Returns:
            True if approval required
        """
        if is_wfh and self.wfh_requires_approval:
            # Use WFH-specific threshold
            if leave_days <= self.wfh_auto_approve_days:
                return False
            return True

        rule = self.get_applicable_rule(leave_days)
        return not rule.auto_approve

    def get_timeout_hours(self) -> int:
        """Get approval timeout in hours"""
        return self.approval_timeout_hours

    def get_reminder_threshold_hours(self) -> int:
        """Get hours before timeout to send reminder"""
        return self.reminder_before_timeout_hours

    def is_hr_user(self, user_id: str) -> bool:
        """
        Check if user is HR (can override)

        Args:
            user_id: Slack user ID

        Returns:
            True if user is HR
        """
        return user_id in self.hr_user_ids

    def can_auto_escalate(self) -> bool:
        """Check if auto-escalation is enabled"""
        return self.escalation_enabled and self.auto_escalate_on_timeout

    def get_escalation_config(self) -> Dict[str, Any]:
        """Get escalation configuration"""
        return {
            'enabled': self.escalation_enabled,
            'auto_escalate_on_timeout': self.auto_escalate_on_timeout,
            'timeout_hours': self.approval_timeout_hours,
            'reminder_hours': self.reminder_before_timeout_hours
        }

    def get_notification_config(self) -> Dict[str, bool]:
        """Get notification preferences"""
        return {
            'notify_employee_on_approval': self.notify_employee_on_approval,
            'notify_employee_on_rejection': self.notify_employee_on_rejection,
            'notify_hr_on_rejection': self.notify_hr_on_rejection
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            'auto_approve_days': self.auto_approve_days,
            'standard_approval_days': self.standard_approval_days,
            'senior_approval_days': self.senior_approval_days,
            'approval_timeout_hours': self.approval_timeout_hours,
            'reminder_before_timeout_hours': self.reminder_before_timeout_hours,
            'escalation_enabled': self.escalation_enabled,
            'auto_escalate_on_timeout': self.auto_escalate_on_timeout,
            'hr_can_override': self.hr_can_override,
            'rules': [
                {
                    'min_days': r.min_days,
                    'max_days': r.max_days,
                    'requires_manager': r.requires_manager,
                    'requires_senior_manager': r.requires_senior_manager,
                    'auto_approve': r.auto_approve,
                    'description': r.description
                }
                for r in self.rules
            ]
        }


# Global instance
_approval_config: Optional[ApprovalConfig] = None


def get_approval_config() -> ApprovalConfig:
    """Get or create global approval config instance"""
    global _approval_config
    if _approval_config is None:
        _approval_config = ApprovalConfig()
    return _approval_config


def set_approval_config(config: ApprovalConfig):
    """Set global approval config instance"""
    global _approval_config
    _approval_config = config
