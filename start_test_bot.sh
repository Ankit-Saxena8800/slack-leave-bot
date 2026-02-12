#!/bin/bash
# Start bot in TEST mode

echo "🧪 STARTING BOT IN TEST MODE"
echo "=============================="
echo ""

# Check if test channel ID is set
if grep -q "C_TEST_CHANNEL_ID" .env.test; then
    echo "⚠️  Please configure your test channel ID first!"
    echo ""
    echo "Steps:"
    echo "1. Create #test-leave-bot channel in Slack (or use existing test channel)"
    echo "2. Get the channel ID:"
    echo "   - Right-click channel → View channel details"
    echo "   - Copy channel ID from bottom of details"
    echo "3. Update .env.test:"
    echo "   - Replace C_TEST_CHANNEL_ID with your channel ID"
    echo ""
    read -p "Press Enter after you've updated .env.test, or Ctrl+C to cancel..."
fi

# Stop production bot
echo "Stopping production bot..."
pkill -f "python3.*main.py"
rm -f .bot.lock
sleep 2

# Backup current .env
if [ -f .env ]; then
    cp .env .env.backup
    echo "✅ Backed up production .env"
fi

# Use test .env
cp .env.test .env
echo "✅ Using test configuration"

# Start bot in test mode
echo ""
echo "Starting test bot..."
nohup python3 main.py > test_bot.log 2>&1 &
TEST_BOT_PID=$!

sleep 3

# Check if started
if ps -p $TEST_BOT_PID > /dev/null; then
    echo "✅ Test bot started (PID: $TEST_BOT_PID)"
    echo ""
    echo "📝 Test bot is now monitoring your test channel"
    echo "📊 Logs: tail -f test_bot.log"
    echo "🛑 Stop: ./stop_test_bot.sh"
    echo ""
    echo "🧪 POST A TEST MESSAGE:"
    echo "   Go to your test channel and post:"
    echo "   'I'll be on leave tomorrow'"
    echo ""

    # Start monitoring
    echo "Starting log monitor..."
    ./test_monitor.sh
else
    echo "❌ Failed to start test bot"
    echo "Check test_bot.log for errors"
fi
