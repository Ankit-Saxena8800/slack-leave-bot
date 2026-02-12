#!/usr/bin/env python3
"""
Zoho Webhook Server for On Duty Applications
Receives real-time notifications when users apply for On Duty/WFH
"""

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
from wfh_tracker import WFHTracker
from slack_sdk import WebClient
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
tracker = WFHTracker()
slack_client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
LEAVE_CHANNEL_ID = os.getenv('LEAVE_CHANNEL_ID')


@app.route('/webhooks/zoho/onduty', methods=['POST'])
def zoho_onduty_webhook():
    """
    Receive webhook from Zoho when On Duty is applied

    To configure in Zoho People:
    1. Go to Settings → Developer Space → Webhooks
    2. Create new webhook for "On Duty" form
    3. Trigger: On Create
    4. URL: https://your-server.com/webhooks/zoho/onduty
    5. Include all fields
    """
    try:
        # Get webhook data
        data = request.json
        logger.info(f"Received Zoho webhook: {json.dumps(data, indent=2)}")

        # Extract On Duty information
        employee_email = data.get('Employee_Email') or data.get('EmailID')
        employee_id = data.get('Employee_ID')
        on_duty_type = data.get('Type') or data.get('OnDutyType')
        period_from = data.get('From') or data.get('Period')
        period_to = data.get('To') or period_from
        status = data.get('Status') or data.get('ApprovalStatus')

        # Check if it's a WFH request
        if on_duty_type and 'work from home' in on_duty_type.lower():
            logger.info(f"WFH application detected: {employee_email} - {period_from} to {period_to}")

            # Parse dates
            dates = parse_zoho_dates(period_from, period_to)

            # Check if we have pending WFH request for this user
            pending_wfh = tracker.get_pending_wfh(employee_email)

            if pending_wfh:
                # Match dates and auto-confirm
                for pending in pending_wfh:
                    if dates_match(pending['dates'], dates):
                        # Confirm WFH
                        tracker.confirm_wfh(pending['message_ts'], confirmed_by='zoho_webhook')

                        # Send Slack notification
                        slack_client.chat_postMessage(
                            channel=LEAVE_CHANNEL_ID,
                            thread_ts=pending['message_ts'],
                            text=f"✅ WFH application confirmed on Zoho! Status: {status}"
                        )

                        logger.info(f"Auto-confirmed WFH for {employee_email}")
                        break
            else:
                logger.info(f"No pending WFH request found for {employee_email}")

        return jsonify({"status": "success", "message": "Webhook processed"}), 200

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/webhooks/zoho/test', methods=['GET', 'POST'])
def test_webhook():
    """Test endpoint to verify webhook configuration"""
    logger.info(f"Test webhook called: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Data: {request.get_data()}")

    return jsonify({
        "status": "ok",
        "message": "Webhook endpoint is working",
        "timestamp": datetime.now().isoformat()
    }), 200


def parse_zoho_dates(from_str, to_str):
    """Parse Zoho date strings to datetime objects"""
    dates = []
    try:
        # Try multiple date formats
        for fmt in ["%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                from_date = datetime.strptime(from_str, fmt)
                to_date = datetime.strptime(to_str, fmt) if to_str else from_date

                # Generate all dates in range
                current = from_date
                while current <= to_date:
                    dates.append(current.isoformat())
                    current += timedelta(days=1)
                break
            except:
                continue
    except Exception as e:
        logger.error(f"Date parsing error: {e}")

    return dates


def dates_match(pending_dates, webhook_dates, tolerance_days=1):
    """Check if dates match (with tolerance for minor differences)"""
    from datetime import timedelta

    pending_set = set(d[:10] for d in pending_dates)  # Just date part
    webhook_set = set(d[:10] for d in webhook_dates)

    # Exact match
    if pending_set == webhook_set:
        return True

    # Allow for tolerance (e.g., user said "18th" but applied for "17th-18th")
    if len(webhook_set.intersection(pending_set)) > 0:
        return True

    return False


if __name__ == '__main__':
    # Run webhook server
    port = int(os.getenv('WEBHOOK_PORT', 3002))
    app.run(host='0.0.0.0', port=port, debug=False)
