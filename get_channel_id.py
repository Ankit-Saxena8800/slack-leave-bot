#!/usr/bin/env python3
"""
List all channels to find test channel ID
"""

import os
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()

client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))

print("🔍 Searching for channels...\n")

try:
    # Get all channels
    response = client.conversations_list(types="public_channel,private_channel")
    channels = response.get('channels', [])

    print(f"Found {len(channels)} channels:\n")
    print(f"{'Channel Name':<30} {'Channel ID':<15} {'Members'}")
    print("=" * 60)

    # Filter for test/leave channels
    test_channels = []

    for channel in channels:
        name = channel.get('name', '')
        channel_id = channel.get('id', '')
        num_members = channel.get('num_members', 0)

        # Highlight test/leave channels
        if 'test' in name.lower() or 'leave' in name.lower():
            print(f"{name:<30} {channel_id:<15} {num_members}")
            test_channels.append((name, channel_id))

    if test_channels:
        print("\n" + "=" * 60)
        print("\n✅ Found test/leave channels:")
        for name, channel_id in test_channels:
            print(f"   #{name}: {channel_id}")
        print("\nCopy the Channel ID above and provide it to me!")
    else:
        print("\n❌ No test channels found")
        print("Please create a #test-leave-bot channel first")

except Exception as e:
    print(f"❌ Error: {e}")
    print("\nMake sure bot has 'channels:read' permission")
