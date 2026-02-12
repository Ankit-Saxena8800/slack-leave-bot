"""
Slack Bot for Leave Intimation Monitoring
"""
import os
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from zoho_client import ZohoClient

logger = logging.getLogger(__name__)

# Leave-related keywords for message detection
LEAVE_KEYWORDS = [
    r'\b(leave|vacation|pto|time.?off|day.?off|sick|wfh|work.?from.?home|ooo|out.?of.?office)\b',
    r'\b(taking|applying|applied|on|going)\s+(a\s+)?(leave|vacation|pto|off)\b',
    r'\b(won\'?t|will\s+not|cannot|can\'?t)\s+(be\s+)?(available|coming|in.?office|working)\b',
    r'\b(half.?day|full.?day)\b',
    r'\b(tomorrow|today|monday|tuesday|wednesday|thursday|friday|next\s+week)\s+(off|leave)\b'
]

# Date patterns
DATE_PATTERNS = [
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # DD/MM/YYYY or MM/DD/YYYY
    r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+\d{2,4})?)',  # 15 January 2024
    r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{2,4})?)',  # January 15, 2024
    r'\b(today|tomorrow|day\s+after\s+tomorrow)\b',
    r'\b(this|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|week)\b',
]


class SlackLeaveBot:
    """Slack bot that monitors leave intimation channel and verifies Zoho applications"""

    def __init__(self):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.app_token = os.getenv("SLACK_APP_TOKEN")
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        self.leave_channel_id = os.getenv("LEAVE_CHANNEL_ID")
        self.admin_channel_id = os.getenv("ADMIN_CHANNEL_ID")
        self.hr_user_id = os.getenv("HR_USER_ID")
        self.days_range = int(os.getenv("CHECK_DAYS_RANGE", "7"))

        self.app = App(token=self.bot_token, signing_secret=self.signing_secret)
        self.client = WebClient(token=self.bot_token)
        self.zoho_client = ZohoClient()

        self._setup_event_handlers()

    def _setup_event_handlers(self):
        """Set up Slack event handlers"""

        @self.app.event("message")
        def handle_message(event, say):
            self._process_message(event, say)

        @self.app.event("app_mention")
        def handle_mention(event, say):
            say(
                text="Hi! I monitor this channel for leave messages and verify them against Zoho People. "
                     "Just post your leave intimation and I'll check if you've applied on Zoho!",
                thread_ts=event.get("thread_ts") or event["ts"]
            )

    def _is_leave_message(self, text: str) -> bool:
        """Check if the message is about taking leave"""
        text_lower = text.lower()

        for pattern in LEAVE_KEYWORDS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True

        return False

    def _extract_dates(self, text: str) -> List[datetime]:
        """Extract dates mentioned in the message"""
        dates = []
        text_lower = text.lower()

        # Check for relative dates
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if "today" in text_lower:
            dates.append(today)
        if "tomorrow" in text_lower:
            dates.append(today + timedelta(days=1))
        if "day after tomorrow" in text_lower:
            dates.append(today + timedelta(days=2))

        # Check for weekday mentions
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

        # Try to parse explicit dates
        for pattern in DATE_PATTERNS[:3]:  # First 3 patterns are for explicit dates
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                parsed = self._parse_date_string(match)
                if parsed:
                    dates.append(parsed)

        # If no dates found, assume today or near future
        if not dates:
            dates.append(today)

        return dates

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Try to parse a date string into datetime"""
        formats = [
            "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
            "%d/%m/%y", "%m/%d/%y", "%d-%m-%y", "%m-%d-%y",
            "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
            "%d %B", "%d %b", "%B %d", "%b %d"
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                # If no year specified, assume current year
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed
            except ValueError:
                continue

        return None

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

    def _send_thread_reply(self, channel: str, thread_ts: str, text: str):
        """Send a reply in a thread"""
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

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Missing Leave Application Alert"
                }
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
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Original Message:*\n> {original_message[:500]}"
                }
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

    def _process_message(self, event: dict, say):
        """Process incoming message and check for leave intimation"""
        # Ignore bot messages and messages from other channels
        if event.get("bot_id") or event.get("subtype"):
            return

        channel = event.get("channel")
        if self.leave_channel_id and channel != self.leave_channel_id:
            return

        text = event.get("text", "")
        user_id = event.get("user")
        message_ts = event.get("ts")

        if not text or not user_id:
            return

        # Check if this is a leave-related message
        if not self._is_leave_message(text):
            return

        logger.info(f"Detected leave message from user {user_id}")

        # Get user email
        user_email = self._get_user_email(user_id)
        user_name = self._get_user_name(user_id)

        if not user_email:
            self._send_thread_reply(
                channel, message_ts,
                f"Hi <@{user_id}>, I couldn't find your email in Slack. "
                "Please ensure your email is set in your Slack profile."
            )
            return

        # Extract dates from message
        leave_dates = self._extract_dates(text)

        # Check Zoho for leave application
        zoho_result = self.zoho_client.check_leave_applied(
            email=user_email,
            leave_date=leave_dates[0] if leave_dates else None,
            days_range=self.days_range
        )

        if zoho_result["error"]:
            if "not found" in zoho_result["error"].lower():
                self._send_thread_reply(
                    channel, message_ts,
                    f"Hi <@{user_id}>, I couldn't find you in Zoho People with email `{user_email}`. "
                    "Please check if your Zoho account uses a different email."
                )
            return

        if zoho_result["found"]:
            # Leave found in Zoho - all good!
            leaves = zoho_result["leaves"]
            leave_info = []
            for leave in leaves[:3]:  # Show up to 3 leaves
                from_date = leave.get("From", leave.get("from", "N/A"))
                to_date = leave.get("To", leave.get("to", "N/A"))
                status = leave.get("ApprovalStatus", leave.get("status", "N/A"))
                leave_type = leave.get("Leavetype", leave.get("leaveType", "Leave"))
                leave_info.append(f"- {leave_type}: {from_date} to {to_date} (Status: {status})")

            leave_details = "\n".join(leave_info)

            self._send_thread_reply(
                channel, message_ts,
                f"Thanks <@{user_id}>! I found your leave application in Zoho People:\n{leave_details}"
            )
        else:
            # Leave NOT found in Zoho
            dates_str = ", ".join([d.strftime("%d %b %Y") for d in leave_dates])

            # 1. Reply in thread
            self._send_thread_reply(
                channel, message_ts,
                f"Hi <@{user_id}>, I noticed you mentioned taking leave "
                f"(around {dates_str}), but I couldn't find a corresponding "
                "leave application in Zoho People.\n\n"
                "Please apply for leave on Zoho People to complete the process."
            )

            # 2. DM the user
            self._send_dm(
                user_id,
                f"Hi {user_name}!\n\n"
                f"I noticed your leave message in the leave intimation channel "
                f"for around {dates_str}, but I couldn't find a matching leave "
                "application in Zoho People.\n\n"
                "Please remember to apply for leave on Zoho People. "
                "This ensures proper attendance tracking and approval workflow.\n\n"
                "If you've already applied and believe this is an error, "
                "please check the dates on your Zoho application or contact HR."
            )

            # 3. Notify HR/Admin
            self._notify_admin(user_name, user_email, leave_dates, text)

            logger.info(f"Sent notifications for missing leave application by {user_name}")

    def start(self):
        """Start the bot"""
        handler = SocketModeHandler(self.app, self.app_token)
        logger.info("Starting Slack Leave Bot...")
        handler.start()
