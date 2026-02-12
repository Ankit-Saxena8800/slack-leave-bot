"""
Interactive Handler for Slack Block Kit Components
Handles button clicks, modal submissions, and interactive messages
"""

import os
import logging
import json
from typing import Optional, Dict, Any, Callable
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from approval_workflow import get_approval_workflow, ApprovalAction
from approval_config import get_approval_config
from template_engine import render_template
from analytics_collector import get_analytics_collector

logger = logging.getLogger(__name__)


class InteractiveHandler:
    """Handles Slack interactive components"""

    def __init__(self, slack_client: WebClient, on_approval_complete: Optional[Callable] = None):
        """
        Initialize interactive handler

        Args:
            slack_client: Slack WebClient instance
            on_approval_complete: Optional callback function(approval_request) called when fully approved
        """
        self.client = slack_client
        self.approval_workflow = get_approval_workflow()
        self.config = get_approval_config()
        self.analytics = get_analytics_collector()
        self.on_approval_complete = on_approval_complete

        # Register action handlers
        self.action_handlers = {
            'approve_leave': self._handle_approve,
            'reject_leave': self._handle_reject,
            'request_info': self._handle_request_info
        }

    def handle_interaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main interaction handler

        Args:
            payload: Slack interaction payload

        Returns:
            Response dictionary
        """
        try:
            interaction_type = payload.get('type')

            if interaction_type == 'block_actions':
                return self._handle_block_actions(payload)
            elif interaction_type == 'view_submission':
                return self._handle_view_submission(payload)
            elif interaction_type == 'view_closed':
                return self._handle_view_closed(payload)
            else:
                logger.warning(f"Unsupported interaction type: {interaction_type}")
                return {"response_action": "errors", "errors": {"error": "Unsupported interaction"}}

        except Exception as e:
            logger.error(f"Failed to handle interaction: {e}", exc_info=True)
            return {"response_action": "errors", "errors": {"error": str(e)}}

    def _handle_block_actions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle block actions (button clicks)

        Args:
            payload: Payload from Slack

        Returns:
            Response dictionary
        """
        actions = payload.get('actions', [])
        if not actions:
            return {}

        action = actions[0]
        action_id = action.get('action_id')
        value = action.get('value')  # Contains request_id

        user = payload.get('user', {})
        user_id = user.get('id')

        # Get handler for this action
        handler = self.action_handlers.get(action_id)
        if handler:
            return handler(value, user_id, payload)

        logger.warning(f"No handler for action: {action_id}")
        return {}

    def _handle_approve(self, request_id: str, approver_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle approve button click

        Args:
            request_id: Approval request ID
            approver_id: Approver Slack ID
            payload: Full payload

        Returns:
            Response dictionary
        """
        if not self.approval_workflow:
            logger.error("Approval workflow not initialized")
            return {}

        # Process approval
        success = self.approval_workflow.handle_approval_response(
            request_id=request_id,
            approver_slack_id=approver_id,
            action=ApprovalAction.APPROVE
        )

        if success:
            # Get request details
            request = self.approval_workflow.get_request(request_id)

            # Update message
            message = payload.get('message', {})
            self._update_approval_message(
                channel=payload.get('channel', {}).get('id'),
                ts=message.get('ts'),
                request=request,
                action='approved',
                approver_id=approver_id
            )

            # Notify employee if fully approved
            if request and request.status == 'approved':
                self._notify_employee_approval(request)

                # CRITICAL: Trigger Zoho verification after full approval
                if self.on_approval_complete:
                    try:
                        logger.info(f"Leave fully approved for {request.employee_email}, proceeding to Zoho verification")
                        self.on_approval_complete(request)
                    except Exception as e:
                        logger.error(f"Error in approval completion callback: {e}", exc_info=True)
                        logger.warning("Employee notified but Zoho verification may not have been triggered")
                else:
                    logger.warning("No approval completion callback registered - Zoho verification skipped")

            # Record analytics
            if self.analytics:
                self.analytics.record_approval_action(
                    request_id=request_id,
                    action='approved',
                    approver_id=approver_id,
                    level=request.current_level - 1 if request else 0
                )

            logger.info(f"Approval processed: {request_id} by {approver_id}")

        return {}

    def _handle_reject(self, request_id: str, approver_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle reject button click - opens modal for reason

        Args:
            request_id: Approval request ID
            approver_id: Approver Slack ID
            payload: Full payload

        Returns:
            Response dictionary
        """
        # Open modal to collect rejection reason
        trigger_id = payload.get('trigger_id')
        if not trigger_id:
            logger.error("No trigger_id in payload")
            return {}

        try:
            self.client.views_open(
                trigger_id=trigger_id,
                view={
                    "type": "modal",
                    "callback_id": f"reject_modal_{request_id}",
                    "title": {"type": "plain_text", "text": "Reject Leave Request"},
                    "submit": {"type": "plain_text", "text": "Submit"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "rejection_reason",
                            "label": {"type": "plain_text", "text": "Reason for rejection"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "reason_input",
                                "multiline": True,
                                "placeholder": {"type": "plain_text", "text": "Please provide a reason..."}
                            }
                        }
                    ],
                    "private_metadata": json.dumps({
                        "request_id": request_id,
                        "approver_id": approver_id,
                        "message_ts": payload.get('message', {}).get('ts'),
                        "channel_id": payload.get('channel', {}).get('id')
                    })
                }
            )
        except SlackApiError as e:
            logger.error(f"Failed to open rejection modal: {e}")

        return {}

    def _handle_request_info(self, request_id: str, approver_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle request info button click

        Args:
            request_id: Approval request ID
            approver_id: Approver Slack ID
            payload: Full payload

        Returns:
            Response dictionary
        """
        if not self.approval_workflow:
            return {}

        request = self.approval_workflow.get_request(request_id)
        if not request:
            return {}

        # Send ephemeral message with details
        try:
            details = self._format_request_details(request)
            self.client.chat_postEphemeral(
                channel=payload.get('channel', {}).get('id'),
                user=approver_id,
                text=details
            )
        except SlackApiError as e:
            logger.error(f"Failed to send request details: {e}")

        return {}

    def _handle_view_submission(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle modal submission

        Args:
            payload: Payload from Slack

        Returns:
            Response dictionary
        """
        view = payload.get('view', {})
        callback_id = view.get('callback_id', '')

        if callback_id.startswith('reject_modal_'):
            return self._handle_reject_submission(payload)

        return {}

    def _handle_reject_submission(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle rejection modal submission

        Args:
            payload: Payload from Slack

        Returns:
            Response dictionary
        """
        if not self.approval_workflow:
            return {}

        view = payload.get('view', {})
        values = view.get('state', {}).get('values', {})
        private_metadata = json.loads(view.get('private_metadata', '{}'))

        request_id = private_metadata.get('request_id')
        approver_id = private_metadata.get('approver_id')
        message_ts = private_metadata.get('message_ts')
        channel_id = private_metadata.get('channel_id')

        # Extract rejection reason
        reason_block = values.get('rejection_reason', {})
        reason_input = reason_block.get('reason_input', {})
        reason = reason_input.get('value', 'No reason provided')

        # Process rejection
        success = self.approval_workflow.handle_approval_response(
            request_id=request_id,
            approver_slack_id=approver_id,
            action=ApprovalAction.REJECT,
            reason=reason
        )

        if success:
            # Get request details
            request = self.approval_workflow.get_request(request_id)

            # Update message
            self._update_approval_message(
                channel=channel_id,
                ts=message_ts,
                request=request,
                action='rejected',
                approver_id=approver_id,
                reason=reason
            )

            # Notify employee
            if request:
                self._notify_employee_rejection(request, reason)

            # Record analytics
            if self.analytics:
                self.analytics.record_approval_action(
                    request_id=request_id,
                    action='rejected',
                    approver_id=approver_id,
                    level=request.current_level if request else 0,
                    reason=reason
                )

            logger.info(f"Rejection processed: {request_id} by {approver_id}")

        return {}

    def _handle_view_closed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle modal closed"""
        return {}

    def _update_approval_message(
        self,
        channel: str,
        ts: str,
        request: Any,
        action: str,
        approver_id: str,
        reason: str = None
    ):
        """
        Update the approval request message

        Args:
            channel: Channel ID
            ts: Message timestamp
            request: ApprovalRequest object
            action: 'approved' or 'rejected'
            approver_id: Approver Slack ID
            reason: Optional rejection reason
        """
        try:
            if action == 'approved':
                if request.status == 'approved':
                    # Fully approved
                    text = f"✅ Leave request *APPROVED* by <@{approver_id}>\n"
                    text += f"All approvals complete. Employee can now apply on Zoho."
                else:
                    # Partially approved, waiting for next level
                    text = f"✅ Approved by <@{approver_id}>\n"
                    text += f"Waiting for approval from next level ({request.current_level + 1}/{len(request.approval_chain)})"

                color = "good"
            else:
                # Rejected
                text = f"❌ Leave request *REJECTED* by <@{approver_id}>\n"
                if reason:
                    text += f"Reason: {reason}"
                color = "danger"

            # Update message
            self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                attachments=[{
                    "color": color,
                    "text": text
                }]
            )

        except SlackApiError as e:
            logger.error(f"Failed to update approval message: {e}")

    def _notify_employee_approval(self, request: Any):
        """
        Notify employee that leave is approved

        Args:
            request: ApprovalRequest object
        """
        try:
            message = render_template('approval.approved', {
                'user_name': request.employee_name,
                'leave_dates': ', '.join(request.leave_dates),
                'approvers': ', '.join([a.approver_name for a in request.approval_chain])
            })

            if not message:
                message = f"✅ Your leave request for {', '.join(request.leave_dates)} has been approved! Please apply on Zoho."

            # Open DM conversation first
            dm_response = self.client.conversations_open(users=[request.employee_slack_id])
            if dm_response['ok']:
                channel_id = dm_response['channel']['id']
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=message
                )
                logger.info(f"Notified employee of approval: {request.employee_email}")
            else:
                logger.error(f"Failed to open DM conversation with employee: {dm_response}")

        except SlackApiError as e:
            logger.error(f"Failed to notify employee of approval: {e}")

    def _notify_employee_rejection(self, request: Any, reason: str):
        """
        Notify employee that leave is rejected

        Args:
            request: ApprovalRequest object
            reason: Rejection reason
        """
        try:
            message = render_template('approval.rejected', {
                'user_name': request.employee_name,
                'leave_dates': ', '.join(request.leave_dates),
                'reason': reason
            })

            if not message:
                message = f"❌ Your leave request for {', '.join(request.leave_dates)} has been rejected.\nReason: {reason}"

            # Open DM conversation first
            dm_response = self.client.conversations_open(users=[request.employee_slack_id])
            if dm_response['ok']:
                channel_id = dm_response['channel']['id']
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=message
                )
                logger.info(f"Notified employee of rejection: {request.employee_email}")
            else:
                logger.error(f"Failed to open DM conversation with employee: {dm_response}")

        except SlackApiError as e:
            logger.error(f"Failed to notify employee of rejection: {e}")

    def _format_request_details(self, request: Any) -> str:
        """
        Format request details for display

        Args:
            request: ApprovalRequest object

        Returns:
            Formatted details string
        """
        details = f"*Leave Request Details*\n\n"
        details += f"Employee: {request.employee_name}\n"
        details += f"Dates: {', '.join(request.leave_dates)}\n"
        details += f"Duration: {request.leave_days} day(s)\n"
        details += f"Status: {request.status}\n\n"

        if request.approval_chain:
            details += f"*Approval Chain:*\n"
            for level in request.approval_chain:
                status_icon = "✅" if level.status == "approved" else "⏳" if level.status == "pending" else "❌"
                details += f"{status_icon} {level.approver_name} ({level.approver_email})\n"

        return details

    def send_approval_request_message(
        self,
        request: Any,
        approver_slack_id: str
    ) -> bool:
        """
        Send approval request message to approver

        Args:
            request: ApprovalRequest object
            approver_slack_id: Approver Slack ID

        Returns:
            True if sent successfully
        """
        try:
            current_level = request.approval_chain[request.current_level]

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📝 Leave Approval Request"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{request.employee_name}* has requested leave approval.\n\n"
                                f"*Dates:* {', '.join(request.leave_dates)}\n"
                                f"*Duration:* {request.leave_days} day(s)\n"
                                f"*Your approval level:* {current_level.level + 1}/{len(request.approval_chain)}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve"},
                            "style": "primary",
                            "action_id": "approve_leave",
                            "value": request.request_id
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject"},
                            "style": "danger",
                            "action_id": "reject_leave",
                            "value": request.request_id
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "ℹ️ Request Info"},
                            "action_id": "request_info",
                            "value": request.request_id
                        }
                    ]
                }
            ]

            self.client.chat_postMessage(
                channel=approver_slack_id,
                text=f"Leave approval request from {request.employee_name}",
                blocks=blocks
            )

            logger.info(f"Sent approval request to {approver_slack_id} for request {request.request_id}")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to send approval request message: {e}")
            return False


# Global instance
_interactive_handler: Optional[InteractiveHandler] = None


def get_interactive_handler() -> Optional[InteractiveHandler]:
    """Get global interactive handler instance"""
    return _interactive_handler


def set_interactive_handler(handler: InteractiveHandler):
    """Set global interactive handler instance"""
    global _interactive_handler
    _interactive_handler = handler
