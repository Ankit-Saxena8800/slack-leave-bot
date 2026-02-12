"""
Socket Mode Handler
Handles Slack Socket Mode connections for interactive components
"""

import os
import logging
from typing import Optional
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk import WebClient

from interactive_handler import get_interactive_handler, InteractiveHandler

logger = logging.getLogger(__name__)


class SocketModeHandler:
    """Manages Socket Mode connection and routing"""

    def __init__(self, app_token: str, bot_token: str):
        """
        Initialize Socket Mode handler

        Args:
            app_token: Slack app token (xapp-...)
            bot_token: Bot token (xoxb-...)
        """
        self.app_token = app_token
        self.bot_token = bot_token

        # Initialize clients
        self.web_client = WebClient(token=bot_token)
        self.socket_client = None
        self.interactive_handler = None

        self.enabled = bool(app_token and app_token.startswith('xapp-'))

        if self.enabled:
            logger.info("Socket Mode handler initialized (enabled)")
        else:
            logger.info("Socket Mode handler initialized (disabled - no valid app token)")

    def start(self):
        """Start Socket Mode connection"""
        if not self.enabled:
            logger.warning("Socket Mode disabled, cannot start")
            return False

        try:
            # Initialize interactive handler
            self.interactive_handler = get_interactive_handler()
            if not self.interactive_handler:
                from interactive_handler import InteractiveHandler, set_interactive_handler
                self.interactive_handler = InteractiveHandler(self.web_client)
                set_interactive_handler(self.interactive_handler)

            # Create Socket Mode client
            self.socket_client = SocketModeClient(
                app_token=self.app_token,
                web_client=self.web_client
            )

            # Register event listeners
            self.socket_client.socket_mode_request_listeners.append(self._handle_socket_mode_request)

            # Connect
            logger.info("Starting Socket Mode connection...")
            self.socket_client.connect()
            logger.info("Socket Mode connected successfully")

            return True

        except Exception as e:
            logger.error(f"Failed to start Socket Mode: {e}", exc_info=True)
            return False

    def _handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest):
        """
        Handle Socket Mode request

        Args:
            client: SocketModeClient instance
            req: SocketModeRequest
        """
        try:
            logger.debug(f"Received Socket Mode request: {req.type}")

            # Acknowledge immediately
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # Route to appropriate handler
            if req.type == "interactive":
                self._handle_interactive(req)
            elif req.type == "slash_commands":
                self._handle_slash_command(req)
            elif req.type == "events_api":
                self._handle_event(req)
            else:
                logger.debug(f"Unhandled request type: {req.type}")

        except Exception as e:
            logger.error(f"Error handling Socket Mode request: {e}", exc_info=True)

    def _handle_interactive(self, req: SocketModeRequest):
        """
        Handle interactive component (buttons, modals)

        Args:
            req: SocketModeRequest
        """
        if not self.interactive_handler:
            logger.error("Interactive handler not initialized")
            return

        payload = req.payload
        self.interactive_handler.handle_interaction(payload)

    def _handle_slash_command(self, req: SocketModeRequest):
        """
        Handle slash command

        Args:
            req: SocketModeRequest
        """
        payload = req.payload
        command = payload.get('command')
        logger.info(f"Received slash command: {command}")

        # TODO: Implement slash command handlers
        # Example: /leave-status, /approve-pending, etc.

    def _handle_event(self, req: SocketModeRequest):
        """
        Handle Events API event

        Args:
            req: SocketModeRequest
        """
        payload = req.payload
        event = payload.get('event', {})
        event_type = event.get('type')

        logger.debug(f"Received event: {event_type}")

        # Events are handled by the main polling bot
        # Socket Mode is primarily for interactive components

    def stop(self):
        """Stop Socket Mode connection"""
        if self.socket_client:
            try:
                logger.info("Stopping Socket Mode connection...")
                self.socket_client.close()
                logger.info("Socket Mode connection closed")
            except Exception as e:
                logger.error(f"Error stopping Socket Mode: {e}")

    def is_connected(self) -> bool:
        """Check if Socket Mode is connected"""
        if not self.socket_client:
            return False
        return self.socket_client.is_connected()


# Global instance
_socket_mode_handler: Optional[SocketModeHandler] = None


def get_socket_mode_handler() -> Optional[SocketModeHandler]:
    """Get global Socket Mode handler instance"""
    return _socket_mode_handler


def set_socket_mode_handler(handler: SocketModeHandler):
    """Set global Socket Mode handler instance"""
    global _socket_mode_handler
    _socket_mode_handler = handler


def initialize_socket_mode(app_token: str = None, bot_token: str = None) -> Optional[SocketModeHandler]:
    """
    Initialize Socket Mode handler

    Args:
        app_token: Slack app token (optional, from env if not provided)
        bot_token: Bot token (optional, from env if not provided)

    Returns:
        SocketModeHandler instance or None
    """
    if app_token is None:
        app_token = os.getenv('SLACK_APP_TOKEN', '')

    if bot_token is None:
        bot_token = os.getenv('SLACK_BOT_TOKEN', '')

    if not app_token or not app_token.startswith('xapp-'):
        logger.info("Socket Mode disabled: No valid SLACK_APP_TOKEN")
        return None

    handler = SocketModeHandler(app_token, bot_token)
    set_socket_mode_handler(handler)

    # Start Socket Mode
    if handler.enabled:
        handler.start()

    return handler
