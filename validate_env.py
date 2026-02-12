#!/usr/bin/env python3
"""
Environment Variables Validation Script
Checks that all required and optional environment variables are properly configured
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_env():
    """Validate environment configuration"""
    print("\n" + "=" * 70)
    print("Environment Variables Validation")
    print("=" * 70 + "\n")

    # Required variables (bot won't work without these)
    required = {
        'SLACK_BOT_TOKEN': 'Slack Bot Token',
        'LEAVE_CHANNEL_ID': 'Leave Channel ID',
    }

    # Enhanced features variables (new)
    enhanced = {
        'ANALYTICS_ENABLED': 'Analytics Enabled',
        'ANALYTICS_DB_PATH': 'Analytics Database Path',
        'DASHBOARD_PORT': 'Dashboard Port',
        'TEMPLATE_CONFIG_PATH': 'Template Config Path',
        'NOTIFICATION_CONFIG_PATH': 'Notification Config Path',
        'VERIFICATION_GRACE_PERIOD_MINUTES': 'Verification Grace Period',
        'VERIFICATION_RE_CHECK_INTERVALS': 'Verification Re-check Intervals',
    }

    # Zoho variables (optional but recommended)
    zoho = {
        'ZOHO_CLIENT_ID': 'Zoho Client ID',
        'ZOHO_CLIENT_SECRET': 'Zoho Client Secret',
        'ZOHO_REFRESH_TOKEN': 'Zoho Refresh Token',
        'ZOHO_DOMAIN': 'Zoho Domain',
    }

    # Optional variables
    optional = {
        'ADMIN_CHANNEL_ID': 'Admin Channel ID',
        'POLL_INTERVAL': 'Poll Interval',
        'CHECK_DAYS_RANGE': 'Check Days Range',
        'DATE_PARSER_MAX_RANGE_DAYS': 'Date Parser Max Range',
        'DATE_PARSER_WORKING_DAYS_ONLY': 'Date Parser Working Days Only',
        'VERIFICATION_ESCALATION_HOURS': 'Verification Escalation Hours',
        'APPROVAL_WORKFLOW_ENABLED': 'Approval Workflow Enabled',
        'HR_USER_IDS': 'HR User IDs',
    }

    results = {
        'required': [],
        'enhanced': [],
        'zoho': [],
        'optional': [],
        'missing': []
    }

    # Check required variables
    print("📋 REQUIRED VARIABLES")
    print("-" * 70)
    for key, desc in required.items():
        value = os.getenv(key)
        if value:
            masked = value[:10] + '...' if len(value) > 10 else value
            print(f"✅ {desc:.<45} SET ({masked})")
            results['required'].append(key)
        else:
            print(f"❌ {desc:.<45} MISSING")
            results['missing'].append(key)

    # Check enhanced features variables
    print("\n🚀 ENHANCED FEATURES VARIABLES")
    print("-" * 70)
    for key, desc in enhanced.items():
        value = os.getenv(key)
        if value:
            print(f"✅ {desc:.<45} {value}")
            results['enhanced'].append(key)
        else:
            print(f"⚠️  {desc:.<45} NOT SET (using default)")

    # Check Zoho variables
    print("\n🔗 ZOHO INTEGRATION")
    print("-" * 70)
    zoho_configured = True
    for key, desc in zoho.items():
        value = os.getenv(key)
        if value:
            masked = value[:15] + '...' if len(value) > 15 else value
            print(f"✅ {desc:.<45} SET ({masked})")
            results['zoho'].append(key)
        else:
            print(f"⚠️  {desc:.<45} NOT SET")
            zoho_configured = False

    if zoho_configured:
        print("\n   ✅ Zoho integration fully configured")
    else:
        print("\n   ⚠️  Zoho integration incomplete - bot will run but cannot verify leaves")

    # Check optional variables
    print("\n⚙️  OPTIONAL CONFIGURATION")
    print("-" * 70)
    for key, desc in optional.items():
        value = os.getenv(key)
        if value:
            print(f"✅ {desc:.<45} {value}")
            results['optional'].append(key)
        else:
            print(f"⚪ {desc:.<45} NOT SET (using default)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Required Variables............ {len(results['required'])}/{len(required)}")
    print(f"Enhanced Features Variables... {len(results['enhanced'])}/{len(enhanced)}")
    print(f"Zoho Variables................ {len(results['zoho'])}/{len(zoho)}")
    print(f"Optional Variables............ {len(results['optional'])}/{len(optional)}")

    if results['missing']:
        print(f"\n❌ Missing Required Variables: {', '.join(results['missing'])}")
        print("   Bot will NOT start without these!")
        print("=" * 70 + "\n")
        return False
    else:
        print("\n✅ All required variables are set!")
        print("✅ Enhanced features are configured!")
        if zoho_configured:
            print("✅ Zoho integration is configured!")
        print("=" * 70 + "\n")
        return True

    # Test specific configurations
    print("\n🧪 CONFIGURATION TESTS")
    print("-" * 70)

    # Test analytics enabled
    analytics_enabled = os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true'
    print(f"Analytics {'ENABLED' if analytics_enabled else 'DISABLED'}")

    # Test verification intervals
    try:
        intervals = os.getenv('VERIFICATION_RE_CHECK_INTERVALS', '12,24,48')
        parsed = [int(x.strip()) for x in intervals.split(',')]
        print(f"Verification intervals: {parsed} hours")
    except:
        print("⚠️  Invalid verification intervals format")

    # Test dashboard port
    try:
        port = int(os.getenv('DASHBOARD_PORT', '3001'))
        print(f"Dashboard will run on port: {port}")
    except:
        print("⚠️  Invalid dashboard port")

    print("=" * 70 + "\n")

if __name__ == "__main__":
    import sys
    success = check_env()
    sys.exit(0 if success else 1)
