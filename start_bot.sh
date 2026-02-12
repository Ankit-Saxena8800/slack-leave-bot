#!/bin/bash
# Start Slack Leave Bot for 24/7 Operation

cd /Users/ankitsaxena/slack-leave-bot

# Check if bot is already running
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Bot is already running"
    ps aux | grep "python.*main.py" | grep -v grep
    exit 0
fi

# Start the bot
echo "🚀 Starting Slack Leave Bot..."
nohup python3 main.py >> bot.log 2>&1 &

# Wait and verify
sleep 3

if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Bot started successfully!"
    ps aux | grep "python.*main.py" | grep -v grep
else
    echo "❌ Bot failed to start. Check bot.log"
    tail -20 bot.log
    exit 1
fi
