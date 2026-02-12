#!/bin/bash
# Stop Slack Leave Bot

echo "🛑 Stopping Slack Leave Bot..."

if pgrep -f "python.*main.py" > /dev/null; then
    pkill -f "python.*main.py"
    rm -f .bot.lock
    sleep 2
    
    if pgrep -f "python.*main.py" > /dev/null; then
        echo "❌ Bot still running. Force killing..."
        pkill -9 -f "python.*main.py"
        rm -f .bot.lock
    fi
    
    echo "✅ Bot stopped"
else
    echo "ℹ️  Bot was not running"
fi
