#!/usr/bin/env python3
"""
Interactive Setup Script for Slack Leave Verification Bot
Guides you through obtaining all required credentials
"""
import os
import webbrowser
import time

ENV_FILE = os.path.join(os.path.dirname(__file__), '.env')

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_step(num, text):
    print(f"\n[Step {num}] {text}")
    print("-" * 40)

def wait_for_enter(msg="Press Enter when done..."):
    input(f"\n>>> {msg}")

def main():
    print_header("SLACK LEAVE BOT - SETUP WIZARD")
    print("\nThis wizard will help you get all required credentials.")
    print("It will open browser tabs and guide you step by step.")

    config = {}

    # ==================== SLACK SETUP ====================
    print_header("PART 1: SLACK APP SETUP")

    print_step(1, "Create a Slack App")
    print("I'll open the Slack API page. Create a new app:")
    print("  - Click 'Create New App' > 'From scratch'")
    print("  - Name: 'Leave Verification Bot'")
    print("  - Select your workspace")

    wait_for_enter("Press Enter to open Slack API page...")
    webbrowser.open("https://api.slack.com/apps")
    wait_for_enter("Press Enter after creating the app...")

    print_step(2, "Configure Bot Permissions")
    print("In your new app, go to 'OAuth & Permissions' and add these Bot Token Scopes:")
    print("  - channels:history")
    print("  - channels:read")
    print("  - chat:write")
    print("  - im:write")
    print("  - users:read")
    print("  - users:read.email")
    wait_for_enter()

    print_step(3, "Enable Socket Mode")
    print("Go to 'Socket Mode' in the sidebar:")
    print("  - Enable Socket Mode")
    print("  - Create an App-Level Token")
    print("  - Name it 'socket-token'")
    print("  - Add scope: connections:write")
    print("  - Copy the token (starts with xapp-)")
    wait_for_enter()
    config['SLACK_APP_TOKEN'] = input("Paste your App-Level Token (xapp-...): ").strip()

    print_step(4, "Enable Events")
    print("Go to 'Event Subscriptions':")
    print("  - Enable Events")
    print("  - Under 'Subscribe to bot events', add:")
    print("    - message.channels")
    print("    - app_mention")
    print("  - Save Changes")
    wait_for_enter()

    print_step(5, "Install App & Get Bot Token")
    print("Go to 'Install App':")
    print("  - Click 'Install to Workspace'")
    print("  - Authorize the app")
    print("  - Copy the 'Bot User OAuth Token' (starts with xoxb-)")
    wait_for_enter()
    config['SLACK_BOT_TOKEN'] = input("Paste your Bot Token (xoxb-...): ").strip()

    print_step(6, "Get Signing Secret")
    print("Go to 'Basic Information':")
    print("  - Scroll to 'App Credentials'")
    print("  - Copy the 'Signing Secret'")
    config['SLACK_SIGNING_SECRET'] = input("Paste your Signing Secret: ").strip()

    print_step(7, "Get Channel IDs")
    print("In Slack, right-click on your leave channel > 'View channel details'")
    print("Scroll down to find the Channel ID (starts with C)")
    config['LEAVE_CHANNEL_ID'] = input("Paste Leave Channel ID: ").strip()

    print("Now do the same for your HR/Admin notification channel:")
    config['ADMIN_CHANNEL_ID'] = input("Paste Admin Channel ID (or press Enter to skip): ").strip()

    # ==================== ZOHO SETUP ====================
    print_header("PART 2: ZOHO PEOPLE API SETUP")

    print_step(8, "Create Zoho API Client")
    print("I'll open Zoho API Console. You need to:")
    print("  - Sign in with your Zoho admin account")
    print("  - Click 'Add Client' > 'Self Client'")

    wait_for_enter("Press Enter to open Zoho API Console...")
    webbrowser.open("https://api-console.zoho.com/")
    wait_for_enter("Press Enter after creating the Self Client...")

    print_step(9, "Get Client Credentials")
    print("In your Self Client, copy the Client ID and Client Secret")
    config['ZOHO_CLIENT_ID'] = input("Paste Client ID: ").strip()
    config['ZOHO_CLIENT_SECRET'] = input("Paste Client Secret: ").strip()

    print_step(10, "Generate Authorization Code")
    print("In the Self Client page:")
    print("  - Click 'Generate Code'")
    print("  - Enter these scopes (copy exactly):")
    print("    ZohoPeople.forms.READ,ZohoPeople.leave.READ,ZohoPeople.employee.READ")
    print("  - Set duration to 10 minutes")
    print("  - Click 'Create'")
    print("  - Copy the generated code")
    wait_for_enter()
    auth_code = input("Paste the Authorization Code: ").strip()

    print_step(11, "Exchange Code for Refresh Token")
    print("Generating refresh token...")

    import requests
    token_url = "https://accounts.zoho.com/oauth/v2/token"
    payload = {
        "code": auth_code,
        "client_id": config['ZOHO_CLIENT_ID'],
        "client_secret": config['ZOHO_CLIENT_SECRET'],
        "grant_type": "authorization_code"
    }

    try:
        response = requests.post(token_url, data=payload)
        data = response.json()

        if "refresh_token" in data:
            config['ZOHO_REFRESH_TOKEN'] = data['refresh_token']
            print("SUCCESS! Got refresh token.")
        else:
            print(f"Error: {data}")
            print("You may need to regenerate the authorization code and try again.")
            config['ZOHO_REFRESH_TOKEN'] = input("Manually paste refresh token (or leave blank): ").strip()
    except Exception as e:
        print(f"Error: {e}")
        config['ZOHO_REFRESH_TOKEN'] = input("Manually paste refresh token: ").strip()

    # Zoho domain
    print("\nSelect your Zoho region:")
    print("  1. Global (zoho.com)")
    print("  2. India (zoho.in)")
    print("  3. Europe (zoho.eu)")
    region = input("Enter 1, 2, or 3 [default: 1]: ").strip() or "1"
    domains = {"1": "https://people.zoho.com", "2": "https://people.zoho.in", "3": "https://people.zoho.eu"}
    config['ZOHO_DOMAIN'] = domains.get(region, domains["1"])

    # ==================== SAVE CONFIG ====================
    print_header("SAVING CONFIGURATION")

    # Build .env content
    env_content = f"""# Slack Configuration
SLACK_BOT_TOKEN={config.get('SLACK_BOT_TOKEN', '')}
SLACK_APP_TOKEN={config.get('SLACK_APP_TOKEN', '')}
SLACK_SIGNING_SECRET={config.get('SLACK_SIGNING_SECRET', '')}
LEAVE_CHANNEL_ID={config.get('LEAVE_CHANNEL_ID', '')}
ADMIN_CHANNEL_ID={config.get('ADMIN_CHANNEL_ID', '')}
HR_USER_ID=

# Zoho People Configuration
ZOHO_CLIENT_ID={config.get('ZOHO_CLIENT_ID', '')}
ZOHO_CLIENT_SECRET={config.get('ZOHO_CLIENT_SECRET', '')}
ZOHO_REFRESH_TOKEN={config.get('ZOHO_REFRESH_TOKEN', '')}
ZOHO_ORGANIZATION_ID=
ZOHO_DOMAIN={config.get('ZOHO_DOMAIN', 'https://people.zoho.com')}

# Bot Configuration
CHECK_DAYS_RANGE=7
"""

    with open(ENV_FILE, 'w') as f:
        f.write(env_content)

    print(f"Configuration saved to: {ENV_FILE}")

    print_header("SETUP COMPLETE!")
    print("\nFinal steps:")
    print("1. In Slack, invite the bot to your leave channel:")
    print(f"   Type: /invite @Leave Verification Bot")
    print("2. Also invite to admin channel if configured")
    print("\nTo start the bot, run:")
    print("   cd ~/slack-leave-bot")
    print("   source venv/bin/activate")
    print("   python main.py")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
