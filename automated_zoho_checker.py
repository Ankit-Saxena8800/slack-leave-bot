#!/usr/bin/env python3
"""
Automated Zoho On Duty Checker using Headless Browser
Periodically checks Zoho UI for WFH applications (fully automated)
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
import schedule

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Playwright not installed")
    print("Install with: pip install playwright && playwright install chromium")
    sys.exit(1)

from wfh_tracker import WFHTracker
from slack_sdk import WebClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zoho_checker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutomatedZohoChecker:
    """Automated checker for WFH applications in Zoho using headless browser"""

    def __init__(self):
        self.zoho_email = os.getenv('ZOHO_USER_EMAIL')
        self.zoho_password = os.getenv('ZOHO_USER_PASSWORD')
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID', '60022591660')  # From your URL

        if not self.zoho_email or not self.zoho_password:
            raise ValueError("ZOHO_USER_EMAIL and ZOHO_USER_PASSWORD must be set in .env")

        self.wfh_tracker = WFHTracker()
        self.slack_client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        self.leave_channel_id = os.getenv('LEAVE_CHANNEL_ID')

        # Rate limiting
        self.last_check_time = None
        self.min_check_interval = 60  # seconds

    def check_wfh_exists(self, employee_email: str, employee_name: str, date: datetime) -> bool:
        """
        Check if WFH application exists for given employee and date

        Args:
            employee_email: Employee's email
            employee_name: Employee's name
            date: Date to check

        Returns:
            True if WFH application found, False otherwise
        """
        # Rate limiting
        if self.last_check_time:
            elapsed = (datetime.now() - self.last_check_time).total_seconds()
            if elapsed < self.min_check_interval:
                wait_time = self.min_check_interval - elapsed
                logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                time.sleep(wait_time)

        logger.info(f"Checking WFH for {employee_name} ({employee_email}) on {date.date()}")

        with sync_playwright() as p:
            browser = None
            try:
                # Launch browser in headless mode
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )

                # Create context with viewport
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )

                page = context.new_page()

                # Set timeout
                page.set_default_timeout(30000)

                # Step 1: Login to Zoho
                logger.info("Logging in to Zoho People...")
                page.goto('https://accounts.zoho.in/signin?servicename=ZohoPeople&signupurl=https://www.zoho.com/people/signup.html')

                # Wait for login form
                page.wait_for_selector('input#login_id', timeout=10000)

                # Enter email
                page.fill('input#login_id', self.zoho_email)
                page.click('button#nextbtn')

                # Wait for password field
                page.wait_for_selector('input#password', timeout=10000)

                # Enter password
                page.fill('input#password', self.zoho_password)
                page.click('button#nextbtn')

                # Wait for redirect to People
                logger.info("Waiting for login redirect...")
                page.wait_for_timeout(5000)

                # Check if login successful
                if 'signin' in page.url.lower():
                    logger.error("Login failed - still on signin page")
                    return False

                # Step 2: Navigate to On Duty page
                logger.info("Navigating to On Duty page...")
                on_duty_url = f'https://peopleplus.zoho.in/{self.zoho_org_id}/zp#attendance/entry/onduty'
                page.goto(on_duty_url)

                # Wait for page to load
                page.wait_for_timeout(3000)

                # Step 3: Search for employee
                logger.info(f"Searching for employee: {employee_name}")

                # Try multiple search selectors
                search_selectors = [
                    'input[placeholder*="Search"]',
                    'input[type="search"]',
                    'input.search-input',
                    '#searchBox'
                ]

                search_input = None
                for selector in search_selectors:
                    try:
                        search_input = page.query_selector(selector)
                        if search_input:
                            break
                    except:
                        continue

                if search_input:
                    page.fill(selector, employee_name)
                    page.wait_for_timeout(2000)
                else:
                    logger.warning("Could not find search input - checking all records")

                # Step 4: Check if WFH exists for the date
                date_str = date.strftime('%d-%b-%Y')  # e.g., "18-Feb-2026"
                alt_date_str = date.strftime('%d/%m/%Y')  # e.g., "18/02/2026"

                # Get page content
                content = page.content()

                # Look for date and WFH indicators
                found = False

                # Check if date exists
                if date_str in content or alt_date_str in content:
                    logger.info(f"Found date {date_str} in page")

                    # Check if it's WFH type
                    if any(indicator in content.lower() for indicator in
                           ['work from home', 'wfh', 'working from home']):
                        logger.info("Found WFH indicator")

                        # Additional check: look for employee name near the date
                        if employee_name.split()[0] in content:  # First name
                            found = True
                            logger.info(f"✓ WFH application FOUND for {employee_name} on {date_str}")
                        else:
                            logger.info("Date and WFH found but not for this employee")
                    else:
                        logger.info("Date found but not WFH type")
                else:
                    logger.info(f"Date {date_str} not found in page")

                # Take screenshot for debugging (if enabled)
                if os.getenv('DEBUG_SCREENSHOTS') == 'true':
                    screenshot_path = f'debug_screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    page.screenshot(path=screenshot_path)
                    logger.info(f"Screenshot saved: {screenshot_path}")

                self.last_check_time = datetime.now()
                return found

            except PlaywrightTimeout as e:
                logger.error(f"Timeout error: {e}")
                return False

            except Exception as e:
                logger.error(f"Error checking WFH: {e}", exc_info=True)
                return False

            finally:
                if browser:
                    browser.close()

    def check_pending_wfh_requests(self):
        """Check all pending WFH requests"""
        logger.info("Checking pending WFH requests...")

        pending = self.wfh_tracker.get_pending_wfh()
        logger.info(f"Found {len(pending)} pending WFH request(s)")

        for record in pending:
            try:
                employee_email = record['user_email']
                employee_name = record['user_name']
                dates = [datetime.fromisoformat(d) for d in record['dates']]
                message_ts = record['message_ts']

                logger.info(f"Checking WFH for {employee_name}: {len(dates)} date(s)")

                # Check each date
                all_found = True
                found_dates = []

                for date in dates:
                    found = self.check_wfh_exists(employee_email, employee_name, date)
                    if found:
                        found_dates.append(date)
                    else:
                        all_found = False

                    # Small delay between checks
                    time.sleep(2)

                # If all dates found, auto-confirm
                if all_found and len(dates) > 0:
                    logger.info(f"All dates found! Auto-confirming WFH for {employee_name}")

                    # Confirm in tracker
                    self.wfh_tracker.confirm_wfh(message_ts, confirmed_by='auto_checker')

                    # Send Slack notification
                    try:
                        self.slack_client.chat_postMessage(
                            channel=self.leave_channel_id,
                            thread_ts=message_ts,
                            text=f"✅ WFH application verified on Zoho! (Checked: {len(dates)} date(s))"
                        )
                        logger.info("Slack notification sent")
                    except Exception as e:
                        logger.error(f"Failed to send Slack notification: {e}")

                elif len(found_dates) > 0:
                    # PARTIAL MATCH: Some dates found, some missing
                    missing_dates = [d for d in dates if d not in found_dates]
                    missing_dates_str = ", ".join([d.strftime("%b %d, %Y") for d in missing_dates])

                    logger.info(f"⚠️ Partial match: {len(found_dates)}/{len(dates)} dates found for {employee_name}, missing: {missing_dates_str}")

                    # Send Slack notification about partial match
                    try:
                        self.slack_client.chat_postMessage(
                            channel=self.leave_channel_id,
                            thread_ts=message_ts,
                            text=f"⚠️ Partial match for {employee_name}: Found {len(found_dates)} date(s) in Zoho, but these dates are still missing: *{missing_dates_str}*. Please apply for these dates."
                        )
                        logger.info("Partial match notification sent")
                    except Exception as e:
                        logger.error(f"Failed to send partial match notification: {e}")

                else:
                    logger.info(f"WFH not found yet for {employee_name}")

            except Exception as e:
                logger.error(f"Error processing record: {e}", exc_info=True)

    def run_continuous(self, interval_minutes: int = 5):
        """
        Run checker continuously

        Args:
            interval_minutes: Check interval in minutes
        """
        logger.info(f"Starting automated WFH checker (interval: {interval_minutes} min)")

        # Schedule checks
        schedule.every(interval_minutes).minutes.do(self.check_pending_wfh_requests)

        # Run first check immediately
        self.check_pending_wfh_requests()

        # Keep running
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("Checker stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)


def main():
    """Main entry point"""
    try:
        # Check environment variables
        required_vars = ['ZOHO_USER_EMAIL', 'ZOHO_USER_PASSWORD', 'SLACK_BOT_TOKEN', 'LEAVE_CHANNEL_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            sys.exit(1)

        # Create checker
        checker = AutomatedZohoChecker()

        # Get check interval from env (default 5 minutes)
        interval = int(os.getenv('WFH_CHECK_INTERVAL_MINUTES', '5'))

        # Run
        checker.run_continuous(interval_minutes=interval)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
