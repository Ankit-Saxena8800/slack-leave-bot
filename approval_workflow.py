"""
Approval Workflow Engine
Manages leave approval requests, routing, and state transitions
"""

import os
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from approval_config import ApprovalStatus, ApprovalAction, get_approval_config
from approval_storage import get_approval_storage
from org_hierarchy import get_org_hierarchy, Employee

logger = logging.getLogger(__name__)


@dataclass
class ApprovalLevel:
    """Represents one level in the approval chain"""
    approver_email: str
    approver_name: str
    approver_slack_id: str
    level: int
    status: str = "pending"  # pending, approved, rejected
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ApprovalRequest:
    """Represents a leave approval request"""
    request_id: str
    employee_email: str
    employee_name: str
    employee_slack_id: str
    leave_dates: List[str]  # ISO format dates
    leave_days: int
    message_ts: str
    channel_id: str

    approval_chain: List[ApprovalLevel] = field(default_factory=list)
    current_level: int = 0
    status: str = "pending"  # pending, approved, rejected, escalated, expired, auto_approved

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None

    auto_approved: bool = False
    is_wfh: bool = False  # Track if this is WFH/On Duty request
    rejection_reason: Optional[str] = None
    escalated_to_hr: bool = False

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'request_id': self.request_id,
            'employee_email': self.employee_email,
            'employee_name': self.employee_name,
            'employee_slack_id': self.employee_slack_id,
            'leave_dates': self.leave_dates,
            'leave_days': self.leave_days,
            'message_ts': self.message_ts,
            'channel_id': self.channel_id,
            'approval_chain': [level.to_dict() for level in self.approval_chain],
            'current_level': self.current_level,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'approved_at': self.approved_at,
            'rejected_at': self.rejected_at,
            'auto_approved': self.auto_approved,
            'is_wfh': self.is_wfh,
            'rejection_reason': self.rejection_reason,
            'escalated_to_hr': self.escalated_to_hr,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApprovalRequest':
        """Create from dictionary"""
        # Reconstruct approval chain
        approval_chain = [
            ApprovalLevel(**level) for level in data.get('approval_chain', [])
        ]

        return cls(
            request_id=data['request_id'],
            employee_email=data['employee_email'],
            employee_name=data['employee_name'],
            employee_slack_id=data['employee_slack_id'],
            leave_dates=data['leave_dates'],
            leave_days=data['leave_days'],
            message_ts=data['message_ts'],
            channel_id=data['channel_id'],
            approval_chain=approval_chain,
            current_level=data.get('current_level', 0),
            status=data.get('status', 'pending'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            approved_at=data.get('approved_at'),
            rejected_at=data.get('rejected_at'),
            auto_approved=data.get('auto_approved', False),
            is_wfh=data.get('is_wfh', False),
            rejection_reason=data.get('rejection_reason'),
            escalated_to_hr=data.get('escalated_to_hr', False),
            metadata=data.get('metadata', {})
        )


class HROverride:
    """HR override functionality for approval requests"""

    def __init__(self, workflow_engine):
        """
        Initialize HR override

        Args:
            workflow_engine: ApprovalWorkflowEngine instance
        """
        self.engine = workflow_engine
        self.org_hierarchy = get_org_hierarchy()
        self.config = get_approval_config()

    def can_override(self, user_slack_id: str) -> bool:
        """
        Check if user can perform HR override

        Args:
            user_slack_id: Slack user ID

        Returns:
            True if user is HR
        """
        if not self.org_hierarchy:
            return self.config.is_hr_user(user_slack_id)

        employee = self.org_hierarchy.get_employee_by_slack_id(user_slack_id)
        if employee:
            return employee.is_hr

        return self.config.is_hr_user(user_slack_id)

    def approve_override(self, request_id: str, hr_user_id: str, reason: str = None) -> bool:
        """
        HR force approve a request

        Args:
            request_id: Request ID
            hr_user_id: HR user Slack ID
            reason: Optional override reason

        Returns:
            True if overridden successfully
        """
        if not self.can_override(hr_user_id):
            logger.warning(f"User {hr_user_id} attempted HR override without permission")
            return False

        storage = get_approval_storage()
        if not storage:
            return False

        request_data = storage.load_request(request_id)
        if not request_data:
            logger.error(f"Request not found for HR override: {request_id}")
            return False

        # Update request
        request_data['status'] = 'approved'
        request_data['approved_at'] = datetime.now().isoformat()
        request_data['metadata']['hr_override'] = True
        request_data['metadata']['hr_override_by'] = hr_user_id
        request_data['metadata']['hr_override_reason'] = reason or "HR override approval"
        request_data['metadata']['hr_override_at'] = datetime.now().isoformat()

        storage.save_request(request_data)
        logger.info(f"HR override approval: {request_id} by {hr_user_id}")

        return True

    def reject_override(self, request_id: str, hr_user_id: str, reason: str) -> bool:
        """
        HR force reject a request

        Args:
            request_id: Request ID
            hr_user_id: HR user Slack ID
            reason: Rejection reason

        Returns:
            True if overridden successfully
        """
        if not self.can_override(hr_user_id):
            logger.warning(f"User {hr_user_id} attempted HR override without permission")
            return False

        storage = get_approval_storage()
        if not storage:
            return False

        request_data = storage.load_request(request_id)
        if not request_data:
            logger.error(f"Request not found for HR override: {request_id}")
            return False

        # Update request
        request_data['status'] = 'rejected'
        request_data['rejected_at'] = datetime.now().isoformat()
        request_data['rejection_reason'] = reason
        request_data['metadata']['hr_override'] = True
        request_data['metadata']['hr_override_by'] = hr_user_id
        request_data['metadata']['hr_override_at'] = datetime.now().isoformat()

        storage.save_request(request_data)
        logger.info(f"HR override rejection: {request_id} by {hr_user_id}")

        return True

    def view_all_pending(self) -> List[Dict[str, Any]]:
        """
        Get all pending approval requests (HR view)

        Returns:
            List of pending requests
        """
        storage = get_approval_storage()
        if not storage:
            return []

        return storage.load_pending()


class ApprovalWorkflowEngine:
    """Manages approval workflow lifecycle"""

    def __init__(self):
        """Initialize approval workflow engine"""
        self.config = get_approval_config()
        self.org_hierarchy = get_org_hierarchy()
        self.storage = get_approval_storage()
        self.hr_override = HROverride(self)

        self.enabled = os.getenv('APPROVAL_WORKFLOW_ENABLED', 'false').lower() == 'true'

        if self.enabled:
            logger.info("Approval workflow engine initialized (enabled)")
        else:
            logger.info("Approval workflow engine initialized (disabled)")

    def create_approval_request(
        self,
        employee_slack_id: str,
        employee_email: str,
        employee_name: str,
        leave_dates: List[datetime],
        message_ts: str,
        channel_id: str,
        is_wfh: bool = False
    ) -> Optional[ApprovalRequest]:
        """
        Create a new approval request

        Args:
            employee_slack_id: Employee Slack ID
            employee_email: Employee email
            employee_name: Employee name
            leave_dates: List of leave dates
            message_ts: Slack message timestamp
            channel_id: Slack channel ID
            is_wfh: Whether this is a WFH request (uses WFH-specific rules)

        Returns:
            ApprovalRequest or None
        """
        if not self.enabled:
            logger.debug("Approval workflow disabled, skipping request creation")
            return None

        try:
            # Validate inputs
            if not employee_slack_id or not employee_email or not employee_name:
                logger.error("Invalid employee information: missing required fields")
                return None

            if not leave_dates or not isinstance(leave_dates, list):
                logger.error("Invalid leave_dates: must be a non-empty list")
                return None

            # Validate date range (must be within past 7 days to future 365 days)
            from datetime import datetime
            now = datetime.now()
            min_allowed_date = now - timedelta(days=7)
            max_allowed_date = now + timedelta(days=365)

            for leave_date in leave_dates:
                if leave_date < min_allowed_date:
                    logger.error(f"Leave date {leave_date.date()} is too far in the past (older than 7 days)")
                    return None
                if leave_date > max_allowed_date:
                    logger.error(f"Leave date {leave_date.date()} is too far in the future (more than 365 days ahead)")
                    return None

            # Calculate leave days
            leave_days = len(leave_dates)

            # Validate leave duration
            if leave_days < 1:
                logger.error("Leave duration must be at least 1 day")
                return None

            if leave_days > 365:
                logger.error(f"Leave duration ({leave_days} days) exceeds maximum allowed (365 days)")
                return None

            # Convert dates to ISO format
            date_strings = [d.date().isoformat() for d in leave_dates]

            # Generate request ID
            request_id = str(uuid.uuid4())

            # Create request
            request = ApprovalRequest(
                request_id=request_id,
                employee_email=employee_email,
                employee_name=employee_name,
                employee_slack_id=employee_slack_id,
                leave_dates=date_strings,
                leave_days=leave_days,
                message_ts=message_ts,
                channel_id=channel_id,
                created_at=datetime.now().isoformat()
            )

            # Check if auto-approve (use WFH-specific rules if applicable)
            if not self.config.requires_approval(leave_days, is_wfh=is_wfh):
                request.status = 'auto_approved'
                request.auto_approved = True
                request.approved_at = datetime.now().isoformat()
                request_type = "WFH" if is_wfh else "leave"
                logger.info(f"Auto-approved {request_type} request: {request_id} ({leave_days} days)")
            else:
                # Build approval chain
                approval_chain = self._build_approval_chain(employee_email, leave_days)
                request.approval_chain = approval_chain

                if not approval_chain:
                    logger.warning(f"No approval chain found for {employee_email}, auto-approving")
                    request.status = 'auto_approved'
                    request.auto_approved = True
                    request.approved_at = datetime.now().isoformat()
                else:
                    logger.info(f"Created approval request: {request_id} with {len(approval_chain)} level(s)")

            # Save request
            if self.storage:
                self.storage.save_request(request.to_dict())

            return request

        except Exception as e:
            logger.error(f"Failed to create approval request: {e}", exc_info=True)
            return None

    def _build_approval_chain(self, employee_email: str, leave_days: int) -> List[ApprovalLevel]:
        """
        Build approval chain for employee

        Args:
            employee_email: Employee email
            leave_days: Number of leave days

        Returns:
            List of ApprovalLevel objects
        """
        approval_chain = []

        if not self.org_hierarchy:
            logger.warning("Org hierarchy not available, cannot build approval chain")
            return approval_chain

        # Get approvers from org hierarchy
        approvers = self.org_hierarchy.get_approval_chain(employee_email, leave_days)

        for idx, approver in enumerate(approvers):
            level = ApprovalLevel(
                approver_email=approver.email,
                approver_name=approver.name,
                approver_slack_id=approver.slack_id,
                level=idx,
                status='pending'
            )
            approval_chain.append(level)

        return approval_chain

    def handle_approval_response(
        self,
        request_id: str,
        approver_slack_id: str,
        action: ApprovalAction,
        reason: str = None
    ) -> bool:
        """
        Handle approval/rejection response

        Args:
            request_id: Request ID
            approver_slack_id: Approver Slack ID
            action: Approval action
            reason: Optional reason for rejection

        Returns:
            True if handled successfully
        """
        if not self.storage:
            return False

        try:
            # Load request
            request_data = self.storage.load_request(request_id)
            if not request_data:
                logger.error(f"Request not found: {request_id}")
                return False

            request = ApprovalRequest.from_dict(request_data)

            # Check if request has expired (default timeout is 48 hours)
            if request.created_at:
                created_at = datetime.fromisoformat(request.created_at)
                timeout_hours = self.config.approval_timeout_hours if self.config else 48
                expiry_time = created_at + timedelta(hours=timeout_hours)

                if datetime.now() > expiry_time:
                    logger.warning(f"Approval request {request_id} has expired (created {created_at}, timeout {timeout_hours}h)")
                    # Mark as expired
                    request.status = "expired"
                    request.updated_at = datetime.now().isoformat()
                    self.storage.save_request(request.to_dict())
                    return False

            # Verify approver
            if request.current_level >= len(request.approval_chain):
                logger.error(f"Invalid approval level for request: {request_id}")
                return False

            current_approver = request.approval_chain[request.current_level]
            if current_approver.approver_slack_id != approver_slack_id:
                logger.warning(f"Approver mismatch: expected {current_approver.approver_slack_id}, got {approver_slack_id}")
                return False

            # Handle action
            if action == ApprovalAction.APPROVE:
                return self._handle_approve(request, current_approver)
            elif action == ApprovalAction.REJECT:
                return self._handle_reject(request, current_approver, reason)
            else:
                logger.warning(f"Unsupported action: {action}")
                return False

        except Exception as e:
            logger.error(f"Failed to handle approval response: {e}", exc_info=True)
            return False

    def _handle_approve(self, request: ApprovalRequest, approver: ApprovalLevel) -> bool:
        """
        Handle approval action

        Args:
            request: ApprovalRequest
            approver: Current approver level

        Returns:
            True if handled successfully
        """
        # Idempotency check: prevent double-approval (race condition protection)
        if approver.status == 'approved':
            logger.warning(f"Level {approver.level} already approved for request {request.request_id} - concurrent approval detected")
            return True  # Already approved, treat as success

        # Mark current level as approved
        approver.status = 'approved'
        approver.approved_at = datetime.now().isoformat()

        # Move to next level or complete
        request.current_level += 1

        if request.current_level >= len(request.approval_chain):
            # All approvals complete
            request.status = 'approved'
            request.approved_at = datetime.now().isoformat()
            logger.info(f"Request fully approved: {request.request_id}")
        else:
            # More approvals needed
            logger.info(f"Request {request.request_id} approved at level {approver.level}, moving to level {request.current_level}")

        # Save request
        if self.storage:
            self.storage.save_request(request.to_dict())

        return True

    def _handle_reject(self, request: ApprovalRequest, approver: ApprovalLevel, reason: str = None) -> bool:
        """
        Handle rejection action

        Args:
            request: ApprovalRequest
            approver: Current approver level
            reason: Rejection reason

        Returns:
            True if handled successfully
        """
        # Mark current level as rejected
        approver.status = 'rejected'
        approver.rejection_reason = reason or "No reason provided"

        # Mark request as rejected
        request.status = 'rejected'
        request.rejected_at = datetime.now().isoformat()
        request.rejection_reason = reason or "Rejected by approver"

        logger.info(f"Request rejected: {request.request_id} by {approver.approver_name}")

        # Save request
        if self.storage:
            self.storage.save_request(request.to_dict())

        return True

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        Get approval request by ID

        Args:
            request_id: Request ID

        Returns:
            ApprovalRequest or None
        """
        if not self.storage:
            return None

        request_data = self.storage.load_request(request_id)
        if request_data:
            return ApprovalRequest.from_dict(request_data)

        return None

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """
        Get all pending approval requests

        Returns:
            List of ApprovalRequest objects
        """
        if not self.storage:
            return []

        pending_data = self.storage.load_pending()
        return [ApprovalRequest.from_dict(data) for data in pending_data]

    def check_timeouts(self) -> List[ApprovalRequest]:
        """
        Check for expired approval requests

        Returns:
            List of expired requests
        """
        if not self.storage:
            return []

        timeout_hours = self.config.get_timeout_hours()
        expired_data = self.storage.load_expired(timeout_hours)

        expired_requests = []
        for data in expired_data:
            request = ApprovalRequest.from_dict(data)

            # Mark as expired
            request.status = 'expired'
            self.storage.save_request(request.to_dict())

            expired_requests.append(request)
            logger.warning(f"Approval request expired: {request.request_id}")

        return expired_requests

    def escalate_to_hr(self, request_id: str) -> bool:
        """
        Escalate request to HR

        Args:
            request_id: Request ID

        Returns:
            True if escalated successfully
        """
        if not self.storage:
            return False

        request_data = self.storage.load_request(request_id)
        if not request_data:
            return False

        request_data['status'] = 'escalated'
        request_data['escalated_to_hr'] = True
        request_data['metadata']['escalated_at'] = datetime.now().isoformat()

        self.storage.save_request(request_data)
        logger.info(f"Request escalated to HR: {request_id}")

        return True


# Global instance
_approval_workflow: Optional[ApprovalWorkflowEngine] = None


def get_approval_workflow() -> Optional[ApprovalWorkflowEngine]:
    """Get global approval workflow instance"""
    return _approval_workflow


def set_approval_workflow(workflow: ApprovalWorkflowEngine):
    """Set global approval workflow instance"""
    global _approval_workflow
    _approval_workflow = workflow
