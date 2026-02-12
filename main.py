#!/usr/bin/env python3
"""
Slack Leave Verification Bot (Polling Mode)
Monitors Slack leave intimation channel and verifies against Zoho People
"""
import os
import sys
import fcntl
import atexit
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Lock file to prevent multiple instances
LOCK_FILE = os.path.join(os.path.dirname(__file__), '.bot.lock')
lock_file_handle = None


def acquire_lock():
    """Acquire exclusive lock to prevent multiple instances"""
    global lock_file_handle
    lock_file_handle = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file_handle.write(str(os.getpid()))
        lock_file_handle.flush()
        return True
    except (IOError, OSError):
        logger.error("Another instance of the bot is already running!")
        logger.error("Kill the other instance first or delete .bot.lock file")
        return False


def release_lock():
    """Release the lock on exit"""
    global lock_file_handle
    if lock_file_handle:
        try:
            fcntl.flock(lock_file_handle, fcntl.LOCK_UN)
            lock_file_handle.close()
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception as e:
            logger.warning(f"Error releasing lock: {e}")


def validate_config():
    """Validate required environment variables"""
    required_vars = ["SLACK_BOT_TOKEN"]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please set SLACK_BOT_TOKEN in .env file")
        sys.exit(1)

    # Check Zoho config
    zoho_vars = ["ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN"]
    missing_zoho = [var for var in zoho_vars if not os.getenv(var)]

    if missing_zoho:
        logger.warning(f"Zoho not configured ({', '.join(missing_zoho)})")
        logger.warning("Bot will run but cannot verify leaves against Zoho")

    if not os.getenv("LEAVE_CHANNEL_ID"):
        logger.warning("LEAVE_CHANNEL_ID not set - will try to auto-detect")


def initialize_enhanced_components():
    """Initialize all enhanced components (analytics, templates, verification, etc.)"""
    logger.info("Initializing enhanced components...")

    try:
        # Import enhanced modules
        from database.db_manager import DatabaseManager, set_db_manager
        from analytics_collector import AnalyticsCollector, set_analytics_collector
        from template_engine import TemplateEngine, set_template_engine
        from notification_router import NotificationRouter, set_notification_router
        from verification_workflow import VerificationWorkflowManager, set_verification_manager
        from verification_storage import VerificationStorage

        # 1. Database Manager
        try:
            db_path = os.getenv('ANALYTICS_DB_PATH', './bot_analytics.db')
            db_manager = DatabaseManager(db_path)
            if db_manager.init_db():
                set_db_manager(db_manager)
                logger.info("✅ Database initialized")
            else:
                logger.warning("⚠️  Database initialization failed, analytics will be disabled")
        except Exception as e:
            logger.warning(f"⚠️  Database setup failed: {e}, analytics will be disabled")

        # 2. Analytics Collector
        try:
            analytics_enabled = os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true'
            analytics = AnalyticsCollector(buffer_size=10, enabled=analytics_enabled)
            set_analytics_collector(analytics)
            logger.info(f"✅ Analytics collector initialized (enabled={analytics_enabled})")
        except Exception as e:
            logger.warning(f"⚠️  Analytics collector setup failed: {e}")

        # 3. Template Engine
        try:
            template_path = os.getenv('TEMPLATE_CONFIG_PATH', 'config/templates.yaml')
            template_engine = TemplateEngine(template_path)
            set_template_engine(template_engine)
            logger.info("✅ Template engine initialized")
        except Exception as e:
            logger.warning(f"⚠️  Template engine setup failed: {e}, will use hardcoded messages")

        # 4. Notification Router
        try:
            router = NotificationRouter()
            set_notification_router(router)
            logger.info("✅ Notification router initialized")
        except Exception as e:
            logger.warning(f"⚠️  Notification router setup failed: {e}")

        # 5. Verification Workflow
        try:
            storage = VerificationStorage()
            grace_period = int(os.getenv('VERIFICATION_GRACE_PERIOD_MINUTES', '30'))
            re_check_intervals_str = os.getenv('VERIFICATION_RE_CHECK_INTERVALS', '12,24,48')
            re_check_intervals = [int(x.strip()) for x in re_check_intervals_str.split(',')]
            verification_manager = VerificationWorkflowManager(
                storage=storage,
                grace_period_minutes=grace_period,
                re_check_intervals_hours=re_check_intervals
            )
            set_verification_manager(verification_manager)
            logger.info(f"✅ Verification workflow initialized (grace period: {grace_period}min)")
        except Exception as e:
            logger.warning(f"⚠️  Verification workflow setup failed: {e}")

        # 6. Approval Workflow Components (Phase 5)
        try:
            approval_enabled = os.getenv('APPROVAL_WORKFLOW_ENABLED', 'false').lower() == 'true'

            if approval_enabled:
                from org_hierarchy import OrgHierarchy, set_org_hierarchy
                from approval_config import ApprovalConfig, set_approval_config
                from approval_storage import ApprovalStorage, set_approval_storage
                from approval_workflow import ApprovalWorkflowEngine, set_approval_workflow

                # Load org hierarchy
                org_file = os.getenv('ORG_HIERARCHY_FILE', 'config/org_hierarchy.json')
                org_hierarchy = OrgHierarchy(org_file)
                set_org_hierarchy(org_hierarchy)
                logger.info("✅ Organizational hierarchy loaded")

                # Initialize approval config
                approval_config = ApprovalConfig()
                set_approval_config(approval_config)
                logger.info("✅ Approval config initialized")

                # Initialize approval storage
                approval_storage = ApprovalStorage()
                set_approval_storage(approval_storage)
                logger.info("✅ Approval storage initialized")

                # Initialize approval workflow engine
                approval_workflow = ApprovalWorkflowEngine()
                set_approval_workflow(approval_workflow)
                logger.info("✅ Approval workflow engine initialized")
            else:
                logger.info("ℹ️  Approval workflow disabled (APPROVAL_WORKFLOW_ENABLED=false)")
        except Exception as e:
            logger.warning(f"⚠️  Approval workflow setup failed: {e}")

        logger.info("Enhanced components initialization complete!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize enhanced components: {e}", exc_info=True)
        logger.warning("Bot will continue with reduced functionality (basic mode)")


def main():
    """Main entry point"""
    # CRITICAL: Acquire lock to prevent multiple instances
    if not acquire_lock():
        sys.exit(1)
    atexit.register(release_lock)

    logger.info("=" * 50)
    logger.info("Slack Leave Verification Bot Starting...")
    logger.info(f"PID: {os.getpid()}")
    logger.info("=" * 50)

    # Validate configuration
    validate_config()

    # Initialize enhanced components
    initialize_enhanced_components()

    # Initialize Socket Mode for interactive components (if enabled)
    socket_mode = None
    try:
        approval_enabled = os.getenv('APPROVAL_WORKFLOW_ENABLED', 'false').lower() == 'true'
        if approval_enabled:
            from socket_mode_handler import initialize_socket_mode
            socket_mode = initialize_socket_mode()
            if socket_mode and socket_mode.enabled:
                logger.info("✅ Socket Mode initialized for interactive components")
    except Exception as e:
        logger.warning(f"⚠️  Socket Mode initialization failed: {e}")
        logger.warning("Approval workflow will not have interactive buttons")

    # Import and start the bot
    from slack_bot_polling import SlackLeaveBotPolling

    try:
        bot = SlackLeaveBotPolling()
        logger.info("Bot initialized successfully")
        logger.info(f"Monitoring channel: {os.getenv('LEAVE_CHANNEL_ID', 'AUTO-DETECT')}")
        logger.info(f"Poll interval: {os.getenv('POLL_INTERVAL', '10')} seconds")
        logger.info("Press Ctrl+C to stop")
        logger.info("-" * 50)
        bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Graceful shutdown of enhanced components
        try:
            # Shutdown analytics
            from analytics_collector import get_analytics_collector
            analytics = get_analytics_collector()
            if analytics:
                logger.info("Shutting down analytics collector...")
                analytics.shutdown()

            # Shutdown Socket Mode
            if socket_mode:
                logger.info("Stopping Socket Mode...")
                socket_mode.stop()
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")


if __name__ == "__main__":
    main()
