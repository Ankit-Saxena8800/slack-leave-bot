#!/bin/bash
# Live test monitoring script

echo "🔍 MONITORING BOT ACTIVITY"
echo "=========================="
echo ""
echo "Watching logs for bot responses..."
echo "Press Ctrl+C to stop"
echo ""

# Get current log size
CURRENT_SIZE=$(wc -l < bot.log)

# Monitor for 2 minutes
END_TIME=$(($(date +%s) + 120))

while [ $(date +%s) -lt $END_TIME ]; do
    # Get new log lines
    NEW_SIZE=$(wc -l < bot.log)

    if [ $NEW_SIZE -gt $CURRENT_SIZE ]; then
        # Show new lines
        tail -n +$((CURRENT_SIZE + 1)) bot.log | while read line; do
            # Highlight important events
            if echo "$line" | grep -q "Processing message"; then
                echo "🔵 $line"
            elif echo "$line" | grep -q "Leave message detected\|WFH request detected"; then
                echo "🟢 $line"
            elif echo "$line" | grep -q "Thanks\|please apply"; then
                echo "✅ $line"
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "✅ BOT RESPONDED! Check Slack now!"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
            elif echo "$line" | grep -q "ERROR"; then
                echo "❌ $line"
            else
                echo "   $line"
            fi
        done

        CURRENT_SIZE=$NEW_SIZE
    fi

    sleep 2
done

echo ""
echo "Monitoring completed."
echo ""
echo "To check bot status:"
echo "  tail -20 bot.log"
