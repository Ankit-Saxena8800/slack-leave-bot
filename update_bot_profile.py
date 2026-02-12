#!/usr/bin/env python3
"""
Update Slack bot profile with STAGE logo and HR Team name
"""

import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

def update_bot_profile():
    """Update bot display name and profile picture"""

    client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))

    print("🎨 Updating Bot Profile")
    print("=" * 50)
    print()

    try:
        # 1. Update bot name and status
        print("1. Updating display name to 'HR Team'...")

        response = client.users_profile_set(
            profile={
                "display_name": "HR Team",
                "status_text": "Leave tracking assistant",
                "status_emoji": ":calendar:"
            }
        )

        if response["ok"]:
            print("   ✅ Display name updated")
        else:
            print(f"   ⚠️  Could not update name: {response}")

        print()

        # 2. Update profile picture
        print("2. Uploading STAGE logo as profile picture...")

        logo_path = "stage_logo_square.png"

        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as image_file:
                response = client.users_setPhoto(
                    image=image_file.read()
                )

            if response["ok"]:
                print("   ✅ Profile picture updated")
                print("   ✅ STAGE logo is now the bot avatar!")
            else:
                print(f"   ⚠️  Could not update picture: {response}")
        else:
            print(f"   ❌ Logo file not found: {logo_path}")

        print()
        print("=" * 50)
        print("✅ Bot Profile Update Complete!")
        print()
        print("Check your Slack workspace:")
        print("  - Bot name should be: HR Team")
        print("  - Bot avatar should be: STAGE logo")
        print("  - Status should be: Leave tracking assistant")

    except SlackApiError as e:
        print(f"❌ Error: {e.response['error']}")
        print()
        if e.response['error'] == 'missing_scope':
            print("⚠️  Missing Permissions!")
            print()
            print("Your bot needs these OAuth scopes:")
            print("  - users.profile:write")
            print("  - users:write")
            print()
            print("To add these:")
            print("1. Go to: https://api.slack.com/apps")
            print("2. Select your bot")
            print("3. Go to: OAuth & Permissions")
            print("4. Add scopes: users.profile:write, users:write")
            print("5. Reinstall the app to your workspace")
            print("6. Run this script again")
        else:
            print("Try manual upload method instead:")
            print("1. Go to: https://api.slack.com/apps")
            print("2. Select your bot → Basic Information")
            print("3. Upload stage_logo_square.png manually")

if __name__ == "__main__":
    update_bot_profile()
