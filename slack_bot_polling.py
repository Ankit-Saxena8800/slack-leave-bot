"""
Slack Bot for Leave Intimation Monitoring (Polling Mode)
Works with a single Slack token - no Socket Mode required
"""
import os
import re
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Set
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from zoho_client import ZohoClient
from reminder_tracker import ReminderTracker, ReminderLevel

# Enhanced features imports
from date_parsing_service import DateParsingService
from template_engine import render_template
from analytics_collector import get_analytics_collector
from notification_router import get_notification_router, NotificationMessage
from verification_workflow import get_verification_manager
from approval_workflow import get_approval_workflow
from interactive_handler import get_interactive_handler
from org_hierarchy import get_org_hierarchy

logger = logging.getLogger(__name__)

# File to persist processed messages across restarts
PROCESSED_MESSAGES_FILE = os.path.join(os.path.dirname(__file__), ".processed_messages.json")

# Leave/WFH keywords - only respond to these two cases
LEAVE_KEYWORDS = [
    r'\b(on\s+)?leave\b',           # "on leave", "leave"
    r'\bwfh\b',                      # "WFH"
    r'\bwork\s*(ing)?\s*from\s*home\b',  # "working from home", "work from home"
    r'\bremote\b',                   # "remote"
    r'\bwork\s*remote\b',            # "work remote"
    r'\bhome\s*office\b',            # "home office"
    r'\btelework\b',                 # "telework"
]

# Patterns that indicate Zoho was already applied - skip reminder
ZOHO_APPLIED_PATTERNS = [
    r'applied\s+(on\s+)?zoho',
    r'zoho\s+(done|applied|submitted|completed)',
    r'already\s+applied',
    r'applied\s+already',
    r'leave\s+applied',
    r'applied\s+leave\s+(on\s+)?zoho',
    r'zoho\s+pe\s+apply',
    r'zoho\s+par\s+apply',
    r'zoho\s+mein\s+apply',
]


class SlackLeaveBotPolling:
    """Slack bot that monitors leave channel using polling"""

    def __init__(self):
        self.token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_TOKEN")
        self.leave_channel_id = os.getenv("LEAVE_CHANNEL_ID")
        self.admin_channel_id = os.getenv("ADMIN_CHANNEL_ID")
        self.hr_user_id = os.getenv("HR_USER_ID")
        self.days_range = int(os.getenv("CHECK_DAYS_RANGE", "7"))
        self.poll_interval = int(os.getenv("POLL_INTERVAL", "10"))  # seconds

        # DRY RUN MODE - logs only, no Slack messages
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

        self.client = WebClient(token=self.token)

        # Check if Zoho is configured
        self.zoho_configured = all([
            os.getenv("ZOHO_CLIENT_ID"),
            os.getenv("ZOHO_CLIENT_SECRET"),
            os.getenv("ZOHO_REFRESH_TOKEN")
        ])
        self.zoho_client = ZohoClient() if self.zoho_configured else None

        # 24-hour reminder tracker
        self.reminder_tracker = ReminderTracker()

        # Enhanced components (initialized in main.py)
        self.date_parser = DateParsingService()
        self.analytics = get_analytics_collector()
        self.notification_router = get_notification_router()
        self.verification_manager = get_verification_manager()
        self.approval_workflow = get_approval_workflow()

        # Initialize or configure interactive handler with callback
        self.interactive_handler = get_interactive_handler()
        if self.interactive_handler:
            # Set the approval completion callback
            self.interactive_handler.on_approval_complete = self.process_approved_leave
            logger.info("  - Interactive Handler: Configured with approval callback")
        else:
            # Create interactive handler with callback if not already created
            from interactive_handler import InteractiveHandler, set_interactive_handler
            try:
                self.interactive_handler = InteractiveHandler(
                    slack_client=self.client,
                    on_approval_complete=self.process_approved_leave
                )
                set_interactive_handler(self.interactive_handler)
                logger.info("  - Interactive Handler: Created with approval callback")
            except Exception as e:
                logger.warning(f"Could not create interactive handler: {e}")
                self.interactive_handler = None

        logger.info("Enhanced components loaded")
        if self.analytics:
            logger.info("  - Analytics: ENABLED")
        if self.date_parser:
            logger.info("  - Date Parser: ENABLED")
        if self.verification_manager:
            logger.info("  - Verification Workflow: ENABLED")
        if self.approval_workflow:
            logger.info(f"  - Approval Workflow: {'ENABLED' if self.approval_workflow.enabled else 'DISABLED'}")

        # Load processed messages from file (persists across restarts)
        self.processed_messages: Set[str] = self._load_processed_messages()
        self.startup_timestamp = time.time()  # Track when bot started

        # In test mode, look back 10 minutes to catch recent test messages
        # In production, start from current time
        test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        if test_mode:
            lookback_seconds = 600  # 10 minutes
            self.last_timestamp = str(time.time() - lookback_seconds)
            logger.info(f"⚡ TEST MODE: Looking back {lookback_seconds/60} minutes for messages")
        else:
            self.last_timestamp = str(time.time())
            logger.info("Production mode: Processing only new messages from now")

        # Rate limit backoff
        self.backoff_seconds = 0
        self.max_backoff = 300  # 5 minutes max backoff

        # Counter for periodic reminder checks (every 5 min = 10 polls at 30s interval)
        self.reminder_check_interval = 10
        self.poll_counter = 0

    def _load_processed_messages(self) -> Set[str]:
        """Load processed messages from file"""
        try:
            if os.path.exists(PROCESSED_MESSAGES_FILE):
                with open(PROCESSED_MESSAGES_FILE, 'r') as f:
                    data = json.load(f)
                    # Only keep messages from last 7 days
                    cutoff = time.time() - (7 * 24 * 60 * 60)
                    messages = set()
                    for ts in data.get("messages", []):
                        try:
                            # Safely parse timestamp
                            ts_float = float(ts.split('.')[0]) if '.' in ts else float(ts)
                            if ts_float > cutoff:
                                messages.add(ts)
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Invalid timestamp format: {ts}, error: {e}")
                    logger.info(f"Loaded {len(messages)} processed messages from file")
                    return messages
        except Exception as e:
            logger.error(f"Failed to load processed messages: {e}")
        return set()

    def _save_processed_messages(self):
        """Save processed messages to file"""
        try:
            # Only keep messages from last 7 days
            cutoff = time.time() - (7 * 24 * 60 * 60)
            messages = []
            for ts in self.processed_messages:
                try:
                    # Safely parse timestamp
                    ts_float = float(ts.split('.')[0]) if '.' in ts else float(ts)
                    if ts_float > cutoff:
                        messages.append(ts)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid timestamp format during save: {ts}, error: {e}")
            with open(PROCESSED_MESSAGES_FILE, 'w') as f:
                json.dump({"messages": messages, "updated": time.time()}, f)
        except Exception as e:
            logger.error(f"Failed to save processed messages: {e}")

    def _is_leave_message(self, text: str) -> bool:
        """Check if the message is about taking leave"""
        text_lower = text.lower()
        for pattern in LEAVE_KEYWORDS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    def _is_wfh_request(self, text: str) -> bool:
        """Check if the message is specifically about WFH/remote work"""
        text_lower = text.lower()
        wfh_patterns = [
            r'\bwfh\b',
            r'\bwork\s*(ing)?\s*from\s*home\b',
            r'\bremote\b',
            r'\bwork\s*remote\b',
            r'\bhome\s*office\b',
            r'\btelework\b',
        ]
        for pattern in wfh_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    def _zoho_already_applied(self, text: str) -> bool:
        """Check if message indicates Zoho leave was already applied"""
        text_lower = text.lower()
        for pattern in ZOHO_APPLIED_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    def _extract_dates(self, text: str) -> List[datetime]:
        """Extract dates mentioned in the message using enhanced date parser"""
        try:
            # Use enhanced date parser if available
            if self.date_parser:
                result = self.date_parser.parse_dates(text)

                if result.dates:
                    logger.info(f"Parsed {len(result.dates)} dates from text (confidence: {result.confidence})")
                    if result.date_range:
                        logger.info(f"Date range: {result.date_range.start_date.date()} to {result.date_range.end_date.date()}")
                    if result.leave_type.value != 'full_day':
                        logger.info(f"Leave type: {result.leave_type.value}")
                    return result.dates
                else:
                    logger.debug("No dates parsed, using fallback")

            # Fallback to basic parsing if enhanced parser not available or finds nothing
            dates = []
            text_lower = text.lower()
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            if "today" in text_lower:
                dates.append(today)
            if "tomorrow" in text_lower:
                dates.append(today + timedelta(days=1))
            if "day after tomorrow" in text_lower:
                dates.append(today + timedelta(days=2))

            weekdays = {
                "monday": 0, "tuesday": 1, "wednesday": 2,
                "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
            }

            for day_name, day_num in weekdays.items():
                if day_name in text_lower:
                    days_ahead = day_num - today.weekday()
                    if "next" in text_lower:
                        days_ahead += 7
                    if days_ahead <= 0:
                        days_ahead += 7
                    dates.append(today + timedelta(days=days_ahead))

            if not dates:
                dates.append(today)

            return dates

        except Exception as e:
            logger.error(f"Error in date extraction: {e}", exc_info=True)
            # Return today as fallback
            return [datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)]

    def _format_dates_for_display(self, dates: List[datetime]) -> str:
        """Format a list of dates for display in messages"""
        if not dates:
            return "the requested dates"

        if len(dates) == 1:
            return dates[0].strftime("%b %d, %Y")
        elif len(dates) == 2:
            return f"{dates[0].strftime('%b %d')} and {dates[1].strftime('%b %d, %Y')}"
        else:
            # For 3+ dates, show range or list
            sorted_dates = sorted(dates)
            first = sorted_dates[0].strftime("%b %d")
            last = sorted_dates[-1].strftime("%b %d, %Y")
            return f"{first} to {last}"

    def _get_user_email(self, user_id: str) -> Optional[str]:
        """Get user's email from Slack"""
        try:
            result = self.client.users_info(user=user_id)
            if result["ok"]:
                return result["user"]["profile"].get("email")
        except SlackApiError as e:
            logger.error(f"Failed to get user info: {e}")
        return None

    def _get_user_name(self, user_id: str) -> str:
        """Get user's display name from Slack"""
        try:
            result = self.client.users_info(user=user_id)
            if result["ok"]:
                profile = result["user"]["profile"]
                return profile.get("display_name") or profile.get("real_name") or "Unknown"
        except SlackApiError as e:
            logger.error(f"Failed to get user name: {e}")
        return "Unknown"

    def _get_user_id_by_email(self, email: str) -> Optional[str]:
        """Get Slack user ID from email address"""
        if not email:
            return None
        try:
            result = self.client.users_lookupByEmail(email=email)
            if result["ok"]:
                return result["user"]["id"]
        except SlackApiError as e:
            logger.debug(f"Failed to find Slack user by email {email}: {e}")
        except Exception as e:
            logger.debug(f"Error looking up user by email: {e}")
        return None

    def _send_thread_reply(self, channel: str, thread_ts: str, text: str):
        """Send a reply in a thread"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would send thread reply: {text[:100]}...")
            return
        try:
            self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text
            )
        except SlackApiError as e:
            logger.error(f"Failed to send thread reply: {e}")

    def _send_dm(self, user_id: str, text: str):
        """Send a direct message to a user"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would send DM to {user_id}: {text[:100]}...")
            return
        try:
            result = self.client.conversations_open(users=[user_id])
            if result["ok"]:
                dm_channel = result["channel"]["id"]
                self.client.chat_postMessage(
                    channel=dm_channel,
                    text=text
                )
        except SlackApiError as e:
            logger.error(f"Failed to send DM: {e}")

    def _notify_admin(self, user_name: str, user_email: str, leave_dates: List[datetime], original_message: str):
        """Notify HR/Admin about missing leave application"""
        if not self.admin_channel_id:
            return

        dates_str = ", ".join([d.strftime("%d %b %Y") for d in leave_dates])

        if self.dry_run:
            logger.info(f"[DRY RUN] Would notify admin about {user_name} ({user_email}) - dates: {dates_str}")
            return

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Missing Leave Application Alert"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Employee:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{user_email}"}
                ]
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Mentioned Dates:*\n{dates_str}"},
                    {"type": "mrkdwn", "text": "*Status:*\nNot found in Zoho People"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Original Message:*\n> {original_message[:500]}"}
            }
        ]

        try:
            self.client.chat_postMessage(
                channel=self.admin_channel_id,
                text=f"Missing leave application alert for {user_name}",
                blocks=blocks
            )
        except SlackApiError as e:
            logger.error(f"Failed to notify admin: {e}")

    def _process_message(self, message: dict):
        """Process a single message"""
        msg_ts = message.get("ts")

        if not msg_ts:
            return

        # CRITICAL: Skip if already processed (check FIRST)
        if msg_ts in self.processed_messages:
            logger.debug(f"Skipping already processed message: {msg_ts}")
            return

        # Skip bot messages
        if message.get("bot_id") or message.get("subtype"):
            self.processed_messages.add(msg_ts)  # Mark as processed
            return

        text = message.get("text", "")
        user_id = message.get("user")

        if not text or not user_id:
            return

        # Check if this is a leave-related message
        if not self._is_leave_message(text):
            return

        # CRITICAL: Mark as processed IMMEDIATELY before any other action
        # This prevents duplicate processing even if bot restarts
        self.processed_messages.add(msg_ts)
        self._save_processed_messages()
        logger.info(f"Processing leave message {msg_ts} from user {user_id}: {text[:50]}...")

        # Check if user already mentioned Zoho was applied - skip reminder
        if self._zoho_already_applied(text):
            logger.info(f"User mentioned Zoho already applied - skipping reminder")
            return

        # Get user info
        user_email = self._get_user_email(user_id)
        user_name = self._get_user_name(user_id)

        if not user_email:
            self._send_thread_reply(
                self.leave_channel_id, msg_ts,
                f"Hi <@{user_id}>, I couldn't find your email in Slack. "
                "Please ensure your email is set in your Slack profile."
            )
            return

        # Extract dates from message
        leave_dates = self._extract_dates(text)

        # Detect if this is a WFH request (needed for Zoho verification)
        is_wfh = self._is_wfh_request(text)

        # ============================================================
        # PHASE 5: APPROVAL WORKFLOW
        # Check if manager approval is required before Zoho verification
        # ============================================================
        if self.approval_workflow and self.approval_workflow.enabled:
            try:
                # Use previously detected is_wfh flag

                # Create approval request
                approval_request = self.approval_workflow.create_approval_request(
                    employee_slack_id=user_id,
                    employee_email=user_email,
                    employee_name=user_name,
                    leave_dates=leave_dates,
                    message_ts=msg_ts,
                    channel_id=self.leave_channel_id,
                    is_wfh=is_wfh
                )

                if approval_request:
                    # Check if auto-approved or requires approval
                    if approval_request.auto_approved:
                        logger.info(f"Leave auto-approved for {user_name} ({len(leave_dates)} days)")
                        # Continue to Zoho verification below
                    else:
                        # Send approval request to approver(s)
                        if approval_request.approval_chain and self.interactive_handler:
                            current_level = approval_request.approval_chain[0]
                            self.interactive_handler.send_approval_request_message(
                                request=approval_request,
                                approver_slack_id=current_level.approver_slack_id
                            )
                            logger.info(f"Approval request sent to {current_level.approver_name} for {user_name}")

                            # Notify employee that approval is pending
                            self._send_dm(
                                user_id,
                                f"Your leave request for {len(leave_dates)} day(s) has been sent to your manager for approval. "
                                "You'll be notified once it's approved."
                            )

                            # Record analytics
                            if self.analytics:
                                try:
                                    self.analytics.record_leave_mention(
                                        user_id=user_id,
                                        user_email=user_email,
                                        user_name=user_name,
                                        event_type='leave_mentioned',
                                        message_ts=msg_ts,
                                        leave_dates=leave_dates,
                                        zoho_applied=None  # Pending approval
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to record analytics: {e}")

                            # RETURN - wait for approval via interactive handler
                            return
                        else:
                            logger.warning("Approval required but no approval chain or interactive handler - proceeding to Zoho")

            except Exception as e:
                logger.error(f"Approval workflow error: {e}", exc_info=True)
                logger.warning("Proceeding to Zoho verification despite approval workflow error")

        # ============================================================
        # ZOHO VERIFICATION (Executed after approval or if approval disabled)
        # ============================================================

        # Check Zoho for leave application (default to not found if Zoho not configured)
        leave_found = False
        zoho_result = None

        # IMPORTANT: WFH/On Duty verification is NOT supported via Zoho People API
        # The On Duty form is not accessible through the API endpoints we have access to
        if is_wfh:
            logger.info("WFH request detected - Zoho verification skipped (On Duty API not available)")
            # Send acknowledgment for WFH without verification
            formatted_dates = self._format_dates_for_display(leave_dates)
            message = (
                f"Hi <@{user_id}>, I see you're planning to WFH on {formatted_dates}. "
                f"Please ensure you've applied for On Duty (WFH) on Zoho People."
            )
            self._send_thread_reply(self.leave_channel_id, msg_ts, message)
            logger.info(f"Sent WFH acknowledgment to {user_name}")
            return  # Skip further processing for WFH

        if self.zoho_configured:
            try:
                # Use multi-date calendar year tracking
                zoho_result = self.zoho_client.check_leaves_applied_multi_date(
                    email=user_email,
                    leave_dates=leave_dates,
                    is_wfh=is_wfh
                )
                leave_found = zoho_result.get("found", False)
                if zoho_result.get("error"):
                    logger.warning(f"Zoho error: {zoho_result['error']}")

                # Log year coverage
                years_checked = zoho_result.get("years_checked", [])
                if years_checked:
                    logger.info(f"Checked Zoho for calendar year(s): {years_checked}")
            except Exception as e:
                logger.error(f"Zoho check failed: {e}")

        # SIMPLE LOGIC: Only two possible responses
        if leave_found:
            # Leave found in Zoho - Thank the user
            message = render_template('thread_reply.leave_found', {'user_id': user_id})
            if not message:
                # Fallback if template fails
                message = f"Thanks <@{user_id}> for applying on Zoho!"

            self._send_thread_reply(self.leave_channel_id, msg_ts, message)
            logger.info(f"{user_name} has leave on Zoho - thanked")

            # Record analytics
            if self.analytics:
                try:
                    self.analytics.record_leave_mention(
                        user_id=user_id,
                        user_email=user_email,
                        user_name=user_name,
                        event_type='leave_mentioned',
                        message_ts=msg_ts,
                        leave_dates=leave_dates,
                        zoho_applied=True
                    )
                except Exception as e:
                    logger.error(f"Failed to record analytics: {e}")

        else:
            # Leave NOT found - remind to apply on Zoho
            message = render_template('thread_reply.leave_not_found', {
                'user_id': user_id,
                'leave_dates': leave_dates
            })
            if not message:
                # Fallback if template fails
                message = f"Hi <@{user_id}>, please apply for leave/WFH on Zoho also."

            self._send_thread_reply(self.leave_channel_id, msg_ts, message)
            logger.info(f"Sent reminder to {user_name} to apply on Zoho")

            # Record analytics
            if self.analytics:
                try:
                    self.analytics.record_leave_mention(
                        user_id=user_id,
                        user_email=user_email,
                        user_name=user_name,
                        event_type='leave_mentioned',
                        message_ts=msg_ts,
                        leave_dates=leave_dates,
                        zoho_applied=False
                    )
                except Exception as e:
                    logger.error(f"Failed to record analytics: {e}")

            # Track for 12-hour follow-up reminder
            if not self.reminder_tracker.is_already_tracked(user_id, msg_ts):
                self.reminder_tracker.add_reminder(
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    channel_id=self.leave_channel_id,
                    message_ts=msg_ts,
                    leave_dates=[d.strftime("%Y-%m-%d") for d in leave_dates]
                )

    def process_approved_leave(self, approval_request):
        """
        Process leave after approval is granted (Phase 5)
        Called by interactive handler after approval

        Args:
            approval_request: ApprovalRequest object that was approved
        """
        try:
            user_id = approval_request.employee_slack_id
            user_email = approval_request.employee_email
            user_name = approval_request.employee_name
            msg_ts = approval_request.message_ts

            # Convert leave dates from ISO strings back to datetime
            leave_dates = [datetime.fromisoformat(d) for d in approval_request.leave_dates]

            # Get WFH flag from approval request
            is_wfh = approval_request.is_wfh

            logger.info(f"Processing approved {'WFH' if is_wfh else 'leave'} for {user_name}")

            # Check Zoho for leave application
            leave_found = False

            if self.zoho_configured:
                try:
                    # Use multi-date calendar year tracking
                    zoho_result = self.zoho_client.check_leaves_applied_multi_date(
                        email=user_email,
                        leave_dates=leave_dates,
                        is_wfh=is_wfh
                    )
                    leave_found = zoho_result.get("found", False)
                    if zoho_result.get("error"):
                        logger.warning(f"Zoho error: {zoho_result['error']}")

                    # Log year coverage
                    years_checked = zoho_result.get("years_checked", [])
                    if years_checked:
                        logger.info(f"Checked Zoho for calendar year(s): {years_checked}")
                except Exception as e:
                    logger.error(f"Zoho check failed: {e}")

            if leave_found:
                # Leave found - send confirmation
                message = render_template('thread_reply.leave_found', {'user_id': user_id})
                if not message:
                    message = f"Thanks <@{user_id}>! Your leave is approved and found in Zoho."

                self._send_thread_reply(self.leave_channel_id, msg_ts, message)
                logger.info(f"{user_name} has leave on Zoho - confirmed")

                # Record analytics
                if self.analytics:
                    try:
                        self.analytics.record_leave_mention(
                            user_id=user_id,
                            user_email=user_email,
                            user_name=user_name,
                            event_type='leave_mentioned',
                            message_ts=msg_ts,
                            leave_dates=leave_dates,
                            zoho_applied=True
                        )
                    except Exception as e:
                        logger.error(f"Failed to record analytics: {e}")
            else:
                # Leave NOT found - remind to apply on Zoho
                message = render_template('thread_reply.leave_not_found', {
                    'user_id': user_id,
                    'leave_dates': leave_dates
                })
                if not message:
                    message = f"Hi <@{user_id}>, your leave is approved. Please apply on Zoho also."

                self._send_thread_reply(self.leave_channel_id, msg_ts, message)
                logger.info(f"Approved leave for {user_name} - reminded to apply on Zoho")

                # Record analytics
                if self.analytics:
                    try:
                        self.analytics.record_leave_mention(
                            user_id=user_id,
                            user_email=user_email,
                            user_name=user_name,
                            event_type='leave_mentioned',
                            message_ts=msg_ts,
                            leave_dates=leave_dates,
                            zoho_applied=False
                        )
                    except Exception as e:
                        logger.error(f"Failed to record analytics: {e}")

                # Track for follow-up reminder
                if not self.reminder_tracker.is_already_tracked(user_id, msg_ts):
                    self.reminder_tracker.add_reminder(
                        user_id=user_id,
                        user_email=user_email,
                        user_name=user_name,
                        channel_id=self.leave_channel_id,
                        message_ts=msg_ts,
                        leave_dates=[d.strftime("%Y-%m-%d") for d in leave_dates]
                    )

        except Exception as e:
            logger.error(f"Error processing approved leave: {e}", exc_info=True)

    def _check_due_reminders(self):
        """Check reminders that are due with multi-level escalation"""
        if not self.zoho_configured:
            return

        due_reminders = self.reminder_tracker.get_due_reminders()

        for reminder, next_level in due_reminders:
            try:
                user_id = reminder["user_id"]
                user_email = reminder.get("user_email", "")
                user_name = reminder.get("user_name", "User")
                message_ts = reminder["message_ts"]
                leave_dates_str = reminder.get("leave_dates", [])
                channel_id = reminder.get("channel_id", self.leave_channel_id)

                logger.info(f"Processing {next_level.name} reminder for {user_name} ({user_email})")

                # Parse leave dates
                leave_dates = []
                for d in leave_dates_str:
                    try:
                        leave_dates.append(datetime.strptime(d, "%Y-%m-%d"))
                    except:
                        pass

                # Re-check Zoho before sending reminder (multi-date calendar year tracking)
                # Check both leave and on-duty records (is_wfh=True checks both)
                zoho_result = self.zoho_client.check_leaves_applied_multi_date(
                    email=user_email,
                    leave_dates=leave_dates,
                    is_wfh=True  # Check both leave and on-duty for reminders
                )

                if zoho_result.get("found"):
                    # Leave now found in Zoho - resolved!
                    self.reminder_tracker.mark_resolved(user_id, message_ts)
                    logger.info(f"{user_name} has now applied on Zoho - resolved")

                    # Send thanks message in thread
                    thanks_msg = f"✅ Great! <@{user_id}> has now applied the leave/WFH on Zoho. Thank you!"

                    try:
                        self._send_thread_reply(channel_id, message_ts, thanks_msg)
                        logger.info(f"Sent resolution confirmation in thread for {user_name}")
                    except Exception as e:
                        logger.error(f"Failed to send resolution message: {e}")

                    # Record analytics
                    if self.analytics:
                        try:
                            self.analytics.record_reminder(
                                user_id=user_id,
                                reminder_type='resolved',
                                message_ts=message_ts,
                                action_taken='leave_found',
                                reminder_level=next_level.value,
                                user_email=user_email
                            )
                        except Exception as e:
                            logger.error(f"Failed to record analytics: {e}")

                    continue

                # Get manager info from Zoho People
                logger.info(f"DEBUG: Attempting to get manager for {user_email}")
                manager_slack_id = None
                try:
                    manager_info = self.zoho_client.get_manager_info(user_email)
                    logger.info(f"DEBUG: Manager info from Zoho: {manager_info}")
                    if manager_info and manager_info.get('email'):
                        # Map manager email to Slack user ID
                        logger.info(f"DEBUG: Looking up Slack user for manager email: {manager_info['email']}")
                        manager_slack_id = self._get_user_id_by_email(manager_info['email'])
                        logger.info(f"DEBUG: Manager Slack ID: {manager_slack_id}")
                        if manager_slack_id:
                            logger.info(f"✅ Found manager for {user_name}: {manager_info.get('name', 'Unknown')} (Slack ID: {manager_slack_id})")
                        else:
                            logger.warning(f"⚠️ Manager {manager_info.get('name')} ({manager_info['email']}) not found in Slack")
                    else:
                        logger.warning(f"⚠️ No manager info found in Zoho for {user_email}")
                except Exception as e:
                    logger.error(f"❌ Error getting manager for {user_email}: {e}", exc_info=True)

                # Simplified: Always use thread reminder (24-hour follow-up)
                template_key = 'thread_reminder.first_followup'
                channels = ['thread']

                # Format leave dates for template
                leave_dates_formatted = self._format_dates_for_display(leave_dates)

                # Render message with manager tag
                logger.info(f"DEBUG: Rendering template with manager_slack_id={manager_slack_id}")
                message = render_template(template_key, {
                    'user_name': user_name,
                    'leave_dates': leave_dates,
                    'leave_dates_formatted': leave_dates_formatted,
                    'user_id': user_id,
                    'manager_slack_id': manager_slack_id or 'manager'  # Fallback if no manager found
                })

                logger.info(f"DEBUG: Template returned: {message[:100] if message else 'None'}")

                if not message:
                    # Fallback message with manager tag
                    logger.info("DEBUG: Using fallback message")
                    if manager_slack_id:
                        message = f"⚠️ Reminder: <@{user_id}>, your leave/WFH is still not applied on Zoho. Please apply as soon as possible. CC: <@{manager_slack_id}>"
                    else:
                        message = f"⚠️ Reminder: <@{user_id}>, your leave/WFH is still not applied on Zoho. Please apply as soon as possible."

                # Send thread reply only (no DM)
                sent_channels = []
                if 'thread' in channels:
                    try:
                        self._send_thread_reply(channel_id, message_ts, message)
                        sent_channels.append('thread')
                        logger.info(f"Sent 24-hour reminder in thread for {user_name}")
                    except Exception as e:
                        logger.error(f"Failed to send thread reply: {e}")

                # Notify admin if needed
                if 'admin' in channels and self.admin_channel_id:
                    try:
                        admin_msg = f"⚠️ *Non-Compliance Alert*\n\n"
                        admin_msg += f"User: <@{user_id}> ({user_email})\n"
                        admin_msg += f"Level: {next_level.name}\n"
                        admin_msg += f"Leave dates: {', '.join(leave_dates_str)}\n"
                        admin_msg += f"User has not applied leave on Zoho after multiple reminders."

                        # Use client.chat_postMessage instead of non-existent _send_message
                        self.client.chat_postMessage(
                            channel=self.admin_channel_id,
                            text=admin_msg
                        )
                        sent_channels.append('admin')
                        logger.warning(f"Escalated {user_name} to admin")
                    except Exception as e:
                        logger.error(f"Failed to notify admin: {e}")

                # Mark reminder sent
                self.reminder_tracker.mark_reminder_sent(
                    user_id,
                    message_ts,
                    next_level,
                    f"sent_to_{','.join(sent_channels)}"
                )

                # Record analytics
                if self.analytics:
                    try:
                        self.analytics.record_reminder(
                            user_id=user_id,
                            reminder_type=next_level.name,
                            message_ts=message_ts,
                            action_taken=','.join(sent_channels),
                            reminder_level=next_level.value,
                            user_email=user_email
                        )
                    except Exception as e:
                        logger.error(f"Failed to record analytics: {e}")

            except Exception as e:
                logger.error(f"Error processing reminder: {e}", exc_info=True)

        # Cleanup old reminders (older than 7 days)
        self.reminder_tracker.cleanup_old(days=7)

    def _fetch_channel_id(self) -> Optional[str]:
        """Try to find the leave channel if not specified"""
        if self.leave_channel_id:
            return self.leave_channel_id

        try:
            # Look for common leave channel names
            result = self.client.conversations_list(types="public_channel,private_channel")
            if result["ok"]:
                for channel in result["channels"]:
                    name = channel["name"].lower()
                    if any(x in name for x in ["leave", "pto", "time-off", "timeoff", "absence"]):
                        logger.info(f"Found leave channel: #{channel['name']} ({channel['id']})")
                        return channel["id"]
        except SlackApiError as e:
            logger.error(f"Failed to list channels: {e}")

        return None

    def _poll_messages(self) -> bool:
        """Poll for new messages in the leave channel. Returns False if rate limited."""
        try:
            # Add tiny amount to last_timestamp to make it exclusive (avoid re-fetching same message)
            oldest_timestamp = str(float(self.last_timestamp) + 0.000001)

            result = self.client.conversations_history(
                channel=self.leave_channel_id,
                oldest=oldest_timestamp,
                limit=10  # Reduced to minimize API usage
            )

            if result["ok"]:
                # Reset backoff on successful request
                self.backoff_seconds = 0

                messages = result.get("messages", [])
                logger.info(f"DEBUG: Slack API returned {len(messages)} messages (oldest={oldest_timestamp})")
                if messages:
                    for msg in messages:
                        logger.info(f"DEBUG: Message TS={msg.get('ts')}, User={msg.get('user')}, Text={msg.get('text', '')[:50]}...")

                # Process oldest first
                for message in reversed(messages):
                    # Update last timestamp BEFORE processing to prevent re-fetching
                    msg_ts = message.get("ts")
                    if msg_ts and float(msg_ts) > float(self.last_timestamp):
                        self.last_timestamp = msg_ts

                    self._process_message(message)
                return True

        except SlackApiError as e:
            error_str = str(e)
            if "ratelimited" in error_str:
                # Exponential backoff for rate limiting
                self.backoff_seconds = min(self.backoff_seconds * 2 + 60, self.max_backoff)
                logger.warning(f"Rate limited. Backing off for {self.backoff_seconds}s")
                return False
            elif "not_in_channel" in error_str:
                logger.error(f"Bot is not in channel {self.leave_channel_id}. Please invite the bot.")
            elif "channel_not_found" in error_str:
                logger.error(f"Channel {self.leave_channel_id} not found. Check the channel ID.")
            else:
                logger.error(f"Failed to fetch messages: {e}")
        return True

    def start(self):
        """Start polling for messages"""
        # Try to find channel if not specified
        if not self.leave_channel_id:
            self.leave_channel_id = self._fetch_channel_id()

        if not self.leave_channel_id:
            logger.error("No leave channel configured. Set LEAVE_CHANNEL_ID in .env")
            return

        logger.info(f"Starting to poll channel {self.leave_channel_id} every {self.poll_interval}s")
        logger.info(f"Loaded {len(self.processed_messages)} previously processed messages")

        while True:
            try:
                logger.info("Polling channel for new messages...")
                # Apply backoff if rate limited
                if self.backoff_seconds > 0:
                    logger.info(f"Rate limit backoff: waiting {self.backoff_seconds}s")
                    time.sleep(self.backoff_seconds)

                success = self._poll_messages()

                # Only check reminders if not rate limited
                if success:
                    self.poll_counter += 1
                    if self.poll_counter >= self.reminder_check_interval:
                        self.poll_counter = 0
                        try:
                            self._check_due_reminders()
                        except Exception as e:
                            logger.error(f"Error checking due reminders: {e}")

            except Exception as e:
                logger.error(f"Error during polling: {e}")

            time.sleep(self.poll_interval)
