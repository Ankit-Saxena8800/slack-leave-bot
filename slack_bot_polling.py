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
from excluded_users_filter import get_filter as get_excluded_users_filter
from ai_classifier import get_ai_classifier

logger = logging.getLogger(__name__)

# File to persist processed messages across restarts
PROCESSED_MESSAGES_FILE = os.path.join(os.path.dirname(__file__), ".processed_messages.json")

# Leave/WFH keywords - respond to these patterns
LEAVE_KEYWORDS = [
    r'\b(on\s+)?leave\b',           # "on leave", "leave"
    r'\bwfh\b',                      # "WFH"
    r'\bwork\s*(ing)?\s*from\s*home\b',  # "working from home", "work from home"
    r'\bremote\b',                   # "remote"
    r'\bwork\s*remote(ly)?\b',       # "work remote", "work remotely"
    r'\bhome\s*office\b',            # "home office"
    r'\btelework\b',                 # "telework"

    # Absence/unavailability phrases
    r'\bday\s+off\b',                # "day off", "taking a day off"
    r'\bunavailable\b',              # "unavailable", "I am unavailable"
    r'\bwon\'?t\s+(be\s+)?(able\s+to\s+)?join\b',  # "won't be able to join", "won't join"
    r'\bcan\'?t\s+(be\s+)?(able\s+to\s+)?join\b',  # "can't join", "can't be able to join"
    r'\bnot\s+join(ing)?\b',         # "not joining"
    r'\bunable\s+to\s+join\b',       # "unable to join"

    # Sick leave phrases
    r'\b(not\s+)?feeling\s+(well|unwell)\b',  # "not feeling well", "feeling unwell"
    r'\b(down\s+with|caught)\s+(fever|cold|flu|covid|conjunctivitis)\b',  # "down with fever", "caught conjunctivitis"
    r'\bsick\b',                     # "sick", "feeling sick"
    r'\bill\b',                      # "ill", "feeling ill"
    r'\bunwell\b',                   # "unwell"

    # Medical appointments
    r'\bdoctor\s+(visit|appointment)\b',  # "doctor visit", "doctor appointment"
    r'\bmedical\s+(emergency|appointment)\b',  # "medical emergency"
]

# Patterns for partial day absences (don't require Zoho leave application)
# These are informational messages, not full leave days
PARTIAL_DAY_PATTERNS = [
    # Leaving early patterns
    r'\bleave\s+(the\s+)?(office|work)?\s*early\b',  # "leave early", "leaving early", "leave the office early"
    r'\bleaving\s+early\b',                           # "leaving early"
    r'\bgo(ing)?\s+early\b',                          # "going early"

    # Coming/Arriving late patterns
    r'\bcoming\s+late\b',                             # "coming late"
    r'\bwill\s+be\s+late\b',                          # "will be late"
    r'\brunning\s+late\b',                            # "running late"
    r'\bstarting\s+(a\s+)?(little\s+)?late\b',        # "starting late", "starting a little late"
    r'\blate\s+(today|tomorrow)\b',                   # "late today"
    r'\breaching\s+by\s+\d+',                         # "reaching by 11", "reaching by 10:30"
    r'\breach\s+(office|work|around|by|at)\s*\d*',   # "reach office", "reach by 11", "reach around 9:45"
    r'\bwill\s+reach\s+(by|at|around)?\s*\d*',        # "will reach by 11", "will reach around 10"
    r'\barriving\s+(at\s+)?(office|work)?\s*(by|at)?\s*\d*', # "arriving at office", "arriving by 12"
    r'\bjoin(ing)?\s+(late|by|at|around)\s*\d*',     # "joining late", "joining by 12", "will join around 10"
    r'\bin\s+(the\s+)?second\s+half\b',               # "in second half", "join in the second half"
    r'\bhalf\s+day\b',                                # "half day"

    # Temporary absence (not full leave)
    r'\bstep(ping)?\s+out\b',                         # "stepping out", "step out"
    r'\bout\s+for\s+\d+\s*(hour|min)',                # "out for 2 hours", "out for 30 mins"
    r'\b(be\s+)?back\s+(in|by)\s+\d+',                # "back in 2 hours", "back by 3pm"

    # Working from different office (not leave)
    r'\bgoing\s+to\s+(the\s+)?[A-Z]{2,}\s+office\b',  # "going to ROC office", "going to Noida office"
    r'\bworking\s+from\s+(the\s+)?[A-Z]{2,}\s+office\b', # "working from ROC office"
    r'\bat\s+(the\s+)?[A-Z]{2,}\s+office\b',          # "at ROC office"
]

# Patterns that indicate Zoho was already applied - skip reminder
ZOHO_APPLIED_PATTERNS = [
    r'applied.{0,50}zoho',                         # "applied on zoho", "applied for the same in zoho" (max 50 chars between)
    r'apply.{0,50}zoho',                           # "apply on zoho", "will apply in zoho"
    r'zoho\s+(done|applied|submitted|completed)',
    r'already\s+(been\s+)?(applied|submitted)',    # "already applied", "already been submitted"
    r'(applied|submitted)\s+already',
    r'(leave|request)\s+(has\s+)?(been\s+)?(applied|submitted)',  # "leave has been submitted", "request applied"
    r'leave\s+applied',
    r'(have|has)\s+applied',                       # "I have applied", "has applied"
    r'zoho\s+pe\s+apply',                          # Hindi
    r'zoho\s+par\s+apply',                         # Hindi
    r'zoho\s+mein\s+apply',                        # Hindi
    r'intimated\s+via\s+email',                    # "intimated via email"
    r'already\s+intimated',
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

        # Disable automatic retries to prevent duplicate messages
        # Our deduplication logic handles failures properly
        self.client = WebClient(token=self.token, retry_handlers=[])

        # Get bot's own user ID for duplicate detection
        try:
            auth_response = self.client.auth_test()
            self.bot_user_id = auth_response.get('user_id')
            logger.info(f"Bot user ID: {self.bot_user_id}")
        except Exception as e:
            logger.warning(f"Could not get bot user ID: {e}")
            self.bot_user_id = None

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
        self.ai_classifier = get_ai_classifier()  # AI-powered message classification

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
        """Save processed messages to file with atomic write"""
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

            # Write to temp file first, then rename atomically
            temp_file = f"{PROCESSED_MESSAGES_FILE}.tmp"
            with open(temp_file, 'w') as f:
                json.dump({"messages": messages, "updated": time.time()}, f, indent=2)
            os.replace(temp_file, PROCESSED_MESSAGES_FILE)
        except Exception as e:
            logger.error(f"Failed to save processed messages: {e}")

    def _is_leave_message(self, text: str, user_name: str = "User") -> bool:
        """
        Check if the message is about taking leave
        Uses AI classification if available, falls back to regex
        """
        # Try AI classification first (more accurate)
        if self.ai_classifier and self.ai_classifier.enabled:
            try:
                classification = self.ai_classifier.classify_message(text, user_name)
                if classification:
                    # Store classification for later use
                    if not hasattr(self, '_last_ai_classification'):
                        self._last_ai_classification = {}
                    self._last_ai_classification[text[:100]] = classification

                    logger.info(f"🤖 AI Classification: {classification.leave_type} (confidence: {classification.confidence:.2f})")
                    return classification.is_leave_message and classification.confidence >= 0.6
            except Exception as e:
                logger.warning(f"AI classification failed, falling back to regex: {e}")

        # Fallback to regex patterns
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

    def _is_partial_day_absence(self, text: str) -> bool:
        """
        Check if message is about partial day absence (leaving early, coming late)
        These don't require Zoho leave applications, so bot should not send reminders

        IMPORTANT: Skip partial day check if message has explicit WFH/Leave date lists
        (e.g., "WFH: 27 Feb, 2 March" or "Leave: 3 March")

        Returns:
            True if it's a partial day absence (skip Zoho reminder)
            False if it's a full leave day (needs Zoho application)
        """
        text_lower = text.lower()

        # Skip partial day check if message has explicit WFH/Leave date lists
        # These patterns indicate the user is listing specific dates, not just mentioning partial day
        if re.search(r'\b(wfh|work from home|leave)\s*:\s*\d', text_lower, re.IGNORECASE):
            logger.info(f"Message contains explicit WFH/Leave date list - NOT treating as partial day")
            return False

        for pattern in PARTIAL_DAY_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.info(f"Detected partial day absence: pattern '{pattern}' matched")
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

    def _get_user_real_name(self, user_id: str) -> str:
        """Get user's real/full name from Slack"""
        try:
            result = self.client.users_info(user=user_id)
            if result["ok"]:
                profile = result["user"]["profile"]
                return profile.get("real_name") or profile.get("display_name") or "Unknown"
        except SlackApiError as e:
            logger.error(f"Failed to get user real name: {e}")
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

    def _load_recent_messages(self):
        """Load recent messages cache from persistent storage (includes fingerprints)"""
        cache_file = ".recent_messages_cache.json"
        fingerprint_file = ".message_fingerprints.json"
        try:
            # Load legacy dedup cache
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    now = time.time()
                    self._recent_messages = {
                        k: v for k, v in data.items()
                        if now - v < 300
                    }
                    logger.info(f"Loaded {len(self._recent_messages)} recent message(s) from cache")
            else:
                self._recent_messages = {}

            # Load fingerprint cache (primary anti-duplicate mechanism)
            if os.path.exists(fingerprint_file):
                with open(fingerprint_file, 'r') as f:
                    data = json.load(f)
                    now = time.time()
                    self._message_fingerprints = {
                        k: v for k, v in data.items()
                        if now - v < 300
                    }
                    logger.info(f"Loaded {len(self._message_fingerprints)} message fingerprint(s) from cache")
            else:
                self._message_fingerprints = {}
        except Exception as e:
            logger.warning(f"Failed to load dedup caches: {e}")
            self._recent_messages = {}
            self._message_fingerprints = {}

    def _save_recent_messages(self):
        """Save recent messages cache to persistent storage (includes fingerprints)"""
        cache_file = ".recent_messages_cache.json"
        fingerprint_file = ".message_fingerprints.json"
        try:
            # Save legacy dedup cache
            temp_file = f"{cache_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self._recent_messages, f, indent=2)
            os.replace(temp_file, cache_file)

            # Save fingerprint cache (primary anti-duplicate mechanism)
            temp_fingerprint = f"{fingerprint_file}.tmp"
            with open(temp_fingerprint, 'w') as f:
                json.dump(self._message_fingerprints, f, indent=2)
            os.replace(temp_fingerprint, fingerprint_file)
        except Exception as e:
            logger.error(f"Failed to save dedup caches: {e}")

    def _send_thread_reply(self, channel: str, thread_ts: str, text: str):
        """Send a reply in a thread with comprehensive anti-duplicate protection"""
        import uuid
        import hashlib
        call_id = str(uuid.uuid4())[:8]

        if self.dry_run:
            logger.info(f"[DRY RUN] Would send thread reply: {text[:100]}...")
            return

        # MULTI-LAYER DEDUPLICATION STRATEGY
        # Layer 1: Content-based fingerprint (prevents identical messages)
        message_fingerprint = hashlib.md5(f"{channel}|{thread_ts}|{text}".encode()).hexdigest()

        # Layer 2: Time-based dedup key (backwards compatible)
        dedup_key = f"{channel}_{thread_ts}_{text[:100]}"

        if not hasattr(self, '_recent_messages'):
            self._load_recent_messages()
        if not hasattr(self, '_message_fingerprints'):
            self._message_fingerprints = {}

        now = time.time()
        dedup_window = 300  # 5 minutes

        logger.info(f"[{call_id}] _send_thread_reply called - channel={channel}, thread_ts={thread_ts}")
        logger.info(f"[{call_id}] Message fingerprint: {message_fingerprint}")

        # CHECK 1: Fingerprint-based dedup (exact content match)
        if message_fingerprint in self._message_fingerprints:
            last_sent = self._message_fingerprints[message_fingerprint]
            if now - last_sent < dedup_window:
                logger.error(f"[{call_id}] 🛑 DUPLICATE BLOCKED BY FINGERPRINT! (sent {now - last_sent:.1f}s ago)")
                logger.error(f"[{call_id}] This exact message was already sent - PREVENTING DUPLICATE")
                return

        # CHECK 2: Legacy dedup key check
        if dedup_key in self._recent_messages:
            last_sent = self._recent_messages[dedup_key]
            if now - last_sent < dedup_window:
                logger.warning(f"[{call_id}] 🛑 DEDUP BLOCKED: Skipping duplicate message (sent {now - last_sent:.1f}s ago)")
                return
            else:
                logger.info(f"[{call_id}] Dedup check passed (last sent {now - last_sent:.1f}s ago)")
        else:
            logger.info(f"[{call_id}] First time sending this message (no dedup entry)")

        try:
            logger.info(f"[{call_id}] ⚡ ABOUT TO SEND MESSAGE - ts={thread_ts}, text_preview={text[:80]}")

            # PRE-FLIGHT CHECK: One final check before API call
            # This catches race conditions where another thread started sending
            if message_fingerprint in self._message_fingerprints:
                last_sent = self._message_fingerprints[message_fingerprint]
                if now - last_sent < 30:  # 30 second window for race conditions
                    logger.error(f"[{call_id}] 🚨 RACE CONDITION DETECTED! Message send started {now - last_sent:.1f}s ago")
                    logger.error(f"[{call_id}] Aborting to prevent duplicate - another thread is sending this")
                    return

            logger.info(f"[{call_id}] Pre-flight check passed - calling Slack API...")

            # Generate unique client message ID for Slack deduplication
            # Slack uses this to prevent duplicate messages even if API is called twice
            client_msg_id = f"{message_fingerprint}-{int(now)}"
            logger.info(f"[{call_id}] Using client_msg_id: {client_msg_id}")

            # Call Slack API with client_msg_id for server-side deduplication
            response = self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text,
                client_msg_id=client_msg_id  # Slack deduplication key
            )

            response_ts = response.get('ts', 'unknown')
            logger.info(f"[{call_id}] ✅ chat_postMessage SUCCESS - response_ts={response_ts}, thread_ts={thread_ts}")
            logger.warning(f"[{call_id}] MESSAGE SENT SUCCESSFULLY - Slack response ts={response_ts}")

            # AGGRESSIVE DUPLICATE CLEANUP: Check thread and delete duplicates
            try:
                time.sleep(3.0)  # Wait 3s for Slack to fully process (duplicates can appear delayed)
                logger.info(f"[{call_id}] 🔍 Checking thread for duplicate messages...")

                thread_replies = self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=20  # Check last 20 messages in thread
                )

                bot_messages = []
                for msg in thread_replies.get('messages', []):
                    # Find messages from this bot with same text
                    if (msg.get('bot_id') or msg.get('user') == self.bot_user_id) and msg.get('text') == text:
                        bot_messages.append(msg)

                if len(bot_messages) > 1:
                    logger.error(f"[{call_id}] 🚨 DUPLICATE DETECTED! Found {len(bot_messages)} identical messages")
                    # Keep the first message, delete the rest
                    for duplicate in bot_messages[1:]:
                        dup_ts = duplicate.get('ts')
                        try:
                            self.client.chat_delete(channel=channel, ts=dup_ts)
                            logger.warning(f"[{call_id}] 🗑️  DELETED DUPLICATE message ts={dup_ts}")
                        except Exception as del_err:
                            logger.error(f"[{call_id}] Failed to delete duplicate: {del_err}")
                else:
                    logger.info(f"[{call_id}] ✅ No duplicates found - clean send!")

            except Exception as cleanup_err:
                logger.error(f"[{call_id}] Duplicate cleanup failed (non-critical): {cleanup_err}")

            # CRITICAL: Record BOTH fingerprint and dedup key to prevent duplicates
            self._message_fingerprints[message_fingerprint] = now
            self._recent_messages[dedup_key] = now
            logger.info(f"[{call_id}] ✅ Cached fingerprint + dedup key (5 min protection)")

            # Clean up old entries (keep last 10 minutes in cache)
            old_count = len(self._recent_messages)
            self._recent_messages = {
                k: v for k, v in self._recent_messages.items()
                if now - v < 600
            }
            self._message_fingerprints = {
                k: v for k, v in self._message_fingerprints.items()
                if now - v < 600
            }
            if len(self._recent_messages) < old_count:
                logger.info(f"[{call_id}] Cleaned {old_count - len(self._recent_messages)} expired entries")

            # Persist to disk to survive restarts
            self._save_recent_messages()
            logger.info(f"[{call_id}] ✅ Persisted dedup cache to disk")

        except SlackApiError as e:
            logger.error(f"[{call_id}] ❌ chat_postMessage FAILED: {e}")
            # DO NOT cache failed sends - allow retry

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

        # IMMEDIATELY mark as processing to prevent race conditions
        # If two polling cycles run simultaneously, only one will process this message
        logger.info(f"🔒 LOCKING message {msg_ts} for processing...")
        self.processed_messages.add(msg_ts)
        self._save_processed_messages()
        logger.info(f"✅ Message {msg_ts} marked as processing - race condition prevented")

        # Handle edited messages (message_changed subtype)
        subtype = message.get("subtype")
        if subtype == "message_changed":
            # Extract the edited message content
            edited_message = message.get("message", {})
            text = edited_message.get("text", "")
            user_id = edited_message.get("user")
            # Use the original message timestamp for tracking
            msg_ts = edited_message.get("ts", msg_ts)
            logger.info(f"Processing edited message {msg_ts}: {text[:50]}...")
        else:
            # Skip bot messages and other subtypes (but not message_changed)
            if message.get("bot_id") or subtype:
                self.processed_messages.add(msg_ts)  # Mark as processed
                return

            text = message.get("text", "")
            user_id = message.get("user")

        if not text or not user_id:
            return

        # Get user info early for AI classification and exclusion check
        user_name = self._get_user_name(user_id)
        user_real_name = self._get_user_real_name(user_id)

        # Check if this is a leave-related message (AI-powered or regex)
        if not self._is_leave_message(text, user_name):
            return

        logger.info(f"Processing leave message {msg_ts} from user {user_id}: {text[:50]}...")

        # Check if this is a partial day absence (leaving early, coming late)
        # These don't require Zoho leave applications, so skip reminders
        if self._is_partial_day_absence(text):
            logger.info(f"⏱️  Partial day absence detected (leaving early/coming late) - skipping Zoho reminder for {user_name}")
            # Acknowledge but don't send Zoho reminder
            try:
                acknowledgment = f"👋 Got it <@{user_id}>! No Zoho application needed for partial day absences."
                self._send_thread_reply(self.leave_channel_id, msg_ts, acknowledgment)
                logger.info(f"Sent acknowledgment for partial day absence to {user_name}")
            except Exception as e:
                logger.error(f"Failed to send partial day acknowledgment: {e}")
            return

        # Check if user is excluded (contractor/intern)
        excluded_filter = get_excluded_users_filter()
        if excluded_filter.is_excluded(user_name, user_real_name):
            logger.info(f"Skipping excluded user: {user_name} ({user_real_name})")
            self.processed_messages.add(msg_ts)
            self._save_processed_messages()
            return

        # Check if user already mentioned Zoho was applied - skip reminder
        if self._zoho_already_applied(text):
            logger.info(f"User mentioned Zoho already applied - skipping reminder")
            self.processed_messages.add(msg_ts)
            self._save_processed_messages()
            return

        # Get user email
        user_email = self._get_user_email(user_id)

        if not user_email:
            self._send_thread_reply(
                self.leave_channel_id, msg_ts,
                f"Hi <@{user_id}>, I couldn't find your email in Slack. "
                "Please ensure your email is set in your Slack profile."
            )
            self.processed_messages.add(msg_ts)
            self._save_processed_messages()
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

                            # Mark as processed - approval flow will handle next steps
                            self.processed_messages.add(msg_ts)
                            self._save_processed_messages()

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
        # For WFH, we skip Zoho verification but still track for reminder follow-ups
        if is_wfh:
            logger.info("WFH request detected - Zoho verification skipped (On Duty API not available)")
            # For WFH, leave_found remains False (can't verify via API)
            # Will send reminder to apply on Zoho and track for follow-ups

        if self.zoho_configured:
            try:
                # Use multi-date calendar year tracking
                zoho_result = self.zoho_client.check_leaves_applied_multi_date(
                    email=user_email,
                    leave_dates=leave_dates,
                    is_wfh=is_wfh
                )
                leave_found = zoho_result.get("found", False)
                missing_dates = zoho_result.get("missing_dates", [])

                if zoho_result.get("error"):
                    logger.warning(f"Zoho error: {zoho_result['error']}")

                # Log year coverage
                years_checked = zoho_result.get("years_checked", [])
                if years_checked:
                    logger.info(f"Checked Zoho for calendar year(s): {years_checked}")
            except Exception as e:
                logger.error(f"Zoho check failed: {e}")

        # ENHANCED LOGIC: Handle all/partial/none scenarios
        if leave_found:
            # All dates found in Zoho - Thank the user
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

        elif missing_dates and len(missing_dates) < len(leave_dates):
            # PARTIAL MATCH: Some dates found, some missing
            found_count = len(leave_dates) - len(missing_dates)
            missing_dates_str = ", ".join([d.strftime("%b %d, %Y") for d in missing_dates])

            message = f"Hi <@{user_id}>, I found {found_count} date(s) in Zoho, but these dates are still missing: *{missing_dates_str}*. Please apply for these dates on Zoho."

            self._send_thread_reply(self.leave_channel_id, msg_ts, message)
            logger.info(f"⚠️ Partial match for {user_name}: {found_count}/{len(leave_dates)} found, missing: {missing_dates_str}")

            # Record analytics (zoho_applied=False because incomplete)
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

            # Track for 12-hour follow-up reminder (only for missing dates)
            if not self.reminder_tracker.is_already_tracked(user_id, msg_ts):
                self.reminder_tracker.add_reminder(
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    channel_id=self.leave_channel_id,
                    message_ts=msg_ts,
                    leave_dates=[d.strftime("%Y-%m-%d") for d in missing_dates]  # Only missing dates
                )

        else:
            # NO dates found - remind to apply on Zoho
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

        # CRITICAL: Mark as processed ONLY after ALL processing complete
        # This ensures message is re-processed if bot crashes mid-processing
        self.processed_messages.add(msg_ts)
        self._save_processed_messages()
        logger.debug(f"Message {msg_ts} fully processed and marked")

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
                    missing_dates = zoho_result.get("missing_dates", [])

                    if zoho_result.get("error"):
                        logger.warning(f"Zoho error: {zoho_result['error']}")

                    # Log year coverage
                    years_checked = zoho_result.get("years_checked", [])
                    if years_checked:
                        logger.info(f"Checked Zoho for calendar year(s): {years_checked}")
                except Exception as e:
                    logger.error(f"Zoho check failed: {e}")

            if leave_found:
                # All dates found - send confirmation
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

            elif missing_dates and len(missing_dates) < len(leave_dates):
                # PARTIAL MATCH: Some dates found, some missing
                found_count = len(leave_dates) - len(missing_dates)
                missing_dates_str = ", ".join([d.strftime("%b %d, %Y") for d in missing_dates])

                message = f"Hi <@{user_id}>, your leave is approved! I found {found_count} date(s) in Zoho, but these dates are still missing: *{missing_dates_str}*. Please apply for these dates on Zoho."

                self._send_thread_reply(self.leave_channel_id, msg_ts, message)
                logger.info(f"⚠️ Partial match for approved leave - {user_name}: {found_count}/{len(leave_dates)} found, missing: {missing_dates_str}")

                # Record analytics (zoho_applied=False because incomplete)
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

            else:
                # NO dates found - remind to apply on Zoho
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

                missing_dates = zoho_result.get("missing_dates", [])

                if zoho_result.get("found"):
                    # All dates now found in Zoho - resolved!
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

                elif missing_dates and len(missing_dates) < len(leave_dates):
                    # PARTIAL MATCH: Some dates applied, some still missing
                    found_count = len(leave_dates) - len(missing_dates)
                    missing_dates_str = ", ".join([d.strftime("%b %d, %Y") for d in missing_dates])

                    # Update reminder to track only missing dates
                    self.reminder_tracker.update_leave_dates(
                        user_id=user_id,
                        message_ts=message_ts,
                        new_dates=[d.strftime("%Y-%m-%d") for d in missing_dates]
                    )

                    # Send partial resolution message
                    partial_msg = f"👍 Good progress <@{user_id}>! I found {found_count} date(s) in Zoho, but these dates are still missing: *{missing_dates_str}*. Please apply for these remaining dates."

                    try:
                        self._send_thread_reply(channel_id, message_ts, partial_msg)
                        logger.info(f"⚠️ Partial resolution for {user_name}: {found_count}/{len(leave_dates)} found, {len(missing_dates)} still missing")
                    except Exception as e:
                        logger.error(f"Failed to send partial resolution message: {e}")

                    # Don't mark as resolved, let reminder continue for missing dates
                    # But don't send escalation for this round since we already notified
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
            # Format with max 6 decimal places for Slack API compatibility
            oldest_timestamp = f"{float(self.last_timestamp) + 0.000001:.6f}"

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
