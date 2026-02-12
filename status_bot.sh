#!/bin/bash
# Check Slack Leave Bot Status

if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Bot is RUNNING"
    echo ""
    ps aux | grep "python.*main.py" | grep -v grep
    echo ""
    echo "Last 10 log entries:"
    tail -10 bot.log
else
    echo "❌ Bot is NOT running"
    echo ""
    echo "Last 10 log entries:"
    tail -10 bot.log
fi
