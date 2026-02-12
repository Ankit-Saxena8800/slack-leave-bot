"""
Notification Router for Slack Leave Bot
Routes notifications to different channels (DM, Thread, Admin, Email, SMS)
"""

import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """Represents a notification message"""
    recipient_id: str  # User ID, email, or phone number
    message: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class NotificationChannel(ABC):
    """Abstract base class for notification channels"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @abstractmethod
    def send(self, message: NotificationMessage) -> bool:
        """
        Send notification through this channel

        Args:
            message: NotificationMessage to send

        Returns:
            True if successful, False otherwise
        """
        pass

    def is_enabled(self) -> bool:
        """Check if channel is enabled"""
        return self.enabled


class SlackDMChannel(NotificationChannel):
    """Slack Direct Message channel"""

    def __init__(self, slack_client, enabled: bool = True):
        """
        Initialize Slack DM channel

        Args:
            slack_client: Slack WebClient instance
            enabled: Whether channel is enabled
        """
        super().__init__(enabled)
        self.slack_client = slack_client

    def send(self, message: NotificationMessage) -> bool:
        """Send DM to Slack user"""
        if not self.enabled:
            logger.debug("Slack DM channel is disabled")
            return False

        try:
            # Open DM conversation
            response = self.slack_client.conversations_open(users=[message.recipient_id])
            if not response['ok']:
                logger.error(f"Failed to open DM conversation: {response}")
                return False

            channel_id = response['channel']['id']

            # Send message
            result = self.slack_client.chat_postMessage(
                channel=channel_id,
                text=message.message,
                blocks=message.metadata.get('blocks')
            )

            if result['ok']:
                logger.info(f"Sent DM to user {message.recipient_id}")
                return True
            else:
                logger.error(f"Failed to send DM: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending Slack DM: {e}", exc_info=True)
            return False


class SlackThreadChannel(NotificationChannel):
    """Slack Thread Reply channel"""

    def __init__(self, slack_client, enabled: bool = True):
        """
        Initialize Slack Thread channel

        Args:
            slack_client: Slack WebClient instance
            enabled: Whether channel is enabled
        """
        super().__init__(enabled)
        self.slack_client = slack_client

    def send(self, message: NotificationMessage) -> bool:
        """Send thread reply in Slack"""
        if not self.enabled:
            logger.debug("Slack Thread channel is disabled")
            return False

        try:
            channel_id = message.metadata.get('channel_id')
            thread_ts = message.metadata.get('thread_ts')

            if not channel_id or not thread_ts:
                logger.error("Missing channel_id or thread_ts for thread reply")
                return False

            result = self.slack_client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=message.message,
                blocks=message.metadata.get('blocks')
            )

            if result['ok']:
                logger.info(f"Sent thread reply in {channel_id}")
                return True
            else:
                logger.error(f"Failed to send thread reply: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending Slack thread reply: {e}", exc_info=True)
            return False


class SlackAdminChannel(NotificationChannel):
    """Slack Admin notification channel"""

    def __init__(self, slack_client, admin_channel_id: str = None, hr_user_ids: List[str] = None, enabled: bool = True):
        """
        Initialize Slack Admin channel

        Args:
            slack_client: Slack WebClient instance
            admin_channel_id: Admin/HR channel ID
            hr_user_ids: List of HR user IDs to mention
            enabled: Whether channel is enabled
        """
        super().__init__(enabled)
        self.slack_client = slack_client
        self.admin_channel_id = admin_channel_id
        self.hr_user_ids = hr_user_ids or []

    def send(self, message: NotificationMessage) -> bool:
        """Send notification to admin channel"""
        if not self.enabled or not self.admin_channel_id:
            logger.debug("Slack Admin channel is disabled or not configured")
            return False

        try:
            # Add HR mentions if configured
            mentions = " ".join([f"<@{user_id}>" for user_id in self.hr_user_ids])
            full_message = f"{mentions}\n\n{message.message}" if mentions else message.message

            result = self.slack_client.chat_postMessage(
                channel=self.admin_channel_id,
                text=full_message,
                blocks=message.metadata.get('blocks')
            )

            if result['ok']:
                logger.info(f"Sent admin notification to {self.admin_channel_id}")
                return True
            else:
                logger.error(f"Failed to send admin notification: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending admin notification: {e}", exc_info=True)
            return False


class EmailChannel(NotificationChannel):
    """Email notification channel"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_address: str,
        enabled: bool = False
    ):
        """
        Initialize Email channel

        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_address: From email address
            enabled: Whether channel is enabled
        """
        super().__init__(enabled)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address

    def send(self, message: NotificationMessage) -> bool:
        """Send email notification"""
        if not self.enabled:
            logger.debug("Email channel is disabled")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message.metadata.get('subject', 'Leave Bot Notification')
            msg['From'] = self.from_address
            msg['To'] = message.recipient_id  # Should be email address

            # Add text part
            text_part = MIMEText(message.message, 'plain')
            msg.attach(text_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Sent email to {message.recipient_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return False


class SMSChannel(NotificationChannel):
    """SMS notification channel (Twilio)"""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        enabled: bool = False
    ):
        """
        Initialize SMS channel

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: From phone number
            enabled: Whether channel is enabled
        """
        super().__init__(enabled)
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self._client = None

    def _get_client(self):
        """Lazy load Twilio client"""
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.error("Twilio library not installed. Install with: pip install twilio")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                self.enabled = False
        return self._client

    def send(self, message: NotificationMessage) -> bool:
        """Send SMS notification"""
        if not self.enabled:
            logger.debug("SMS channel is disabled")
            return False

        try:
            client = self._get_client()
            if not client:
                return False

            # Send SMS
            message_obj = client.messages.create(
                body=message.message,
                from_=self.from_number,
                to=message.recipient_id  # Should be phone number
            )

            logger.info(f"Sent SMS to {message.recipient_id}, SID: {message_obj.sid}")
            return True

        except Exception as e:
            logger.error(f"Error sending SMS: {e}", exc_info=True)
            return False


class NotificationRouter:
    """Routes notifications to appropriate channels"""

    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}

    def register_channel(self, name: str, channel: NotificationChannel):
        """
        Register a notification channel

        Args:
            name: Channel name (e.g., 'dm', 'thread', 'admin', 'email', 'sms')
            channel: NotificationChannel instance
        """
        self.channels[name] = channel
        logger.info(f"Registered notification channel: {name}")

    def route_notification(
        self,
        channel_names: List[str],
        message: NotificationMessage
    ) -> Dict[str, bool]:
        """
        Route notification to multiple channels

        Args:
            channel_names: List of channel names to use
            message: NotificationMessage to send

        Returns:
            Dict mapping channel name to success status
        """
        results = {}

        for channel_name in channel_names:
            channel = self.channels.get(channel_name)
            if channel:
                if channel.is_enabled():
                    success = channel.send(message)
                    results[channel_name] = success
                else:
                    logger.debug(f"Channel '{channel_name}' is disabled")
                    results[channel_name] = False
            else:
                logger.warning(f"Channel '{channel_name}' not registered")
                results[channel_name] = False

        return results

    def send_to_channel(
        self,
        channel_name: str,
        message: NotificationMessage
    ) -> bool:
        """
        Send notification to a single channel

        Args:
            channel_name: Channel name
            message: NotificationMessage to send

        Returns:
            True if successful, False otherwise
        """
        channel = self.channels.get(channel_name)
        if not channel:
            logger.warning(f"Channel '{channel_name}' not registered")
            return False

        if not channel.is_enabled():
            logger.debug(f"Channel '{channel_name}' is disabled")
            return False

        return channel.send(message)


# Global notification router instance
_notification_router: Optional[NotificationRouter] = None


def get_notification_router() -> Optional[NotificationRouter]:
    """Get global notification router instance"""
    return _notification_router


def set_notification_router(router: NotificationRouter):
    """Set global notification router instance"""
    global _notification_router
    _notification_router = router
