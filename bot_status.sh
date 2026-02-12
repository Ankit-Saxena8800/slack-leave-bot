#!/bin/bash
# Check bot status

echo "🔍 Slack Leave Bot Status"
echo "=========================="

# Check for running instances
INSTANCES=$(ps aux | grep -E "[Pp]ython.*main.py" | grep -v grep)

if [ -z "$INSTANCES" ]; then
    echo "Status: ❌ NOT RUNNING"
    echo ""
    echo "To start: bash start_bot.sh"
else
    echo "Status: ✅ RUNNING"
    echo ""
    echo "Running instances:"
    echo "$INSTANCES" | awk '{print "  PID: " $2 "  Started: " $9 "  CPU: " $3 "%  Memory: " $4 "%"}'

    # Count instances
    COUNT=$(echo "$INSTANCES" | wc -l | tr -d ' ')
    echo ""
    if [ "$COUNT" -gt 1 ]; then
        echo "⚠️  WARNING: Multiple instances detected ($COUNT)"
        echo "   This will cause duplicate messages!"
        echo "   Run: bash stop_bot.sh && bash start_bot.sh"
    else
        echo "✅ Single instance running correctly"
    fi
fi

echo ""
echo "Recent activity (last 5 log lines):"
echo "-----------------------------------"
tail -5 bot.log 2>/dev/null || echo "  No log file found"

echo ""
echo "Quick commands:"
echo "  Start:  bash start_bot.sh"
echo "  Stop:   bash stop_bot.sh"
echo "  Logs:   tail -f bot.log"
echo "  Status: bash bot_status.sh"
