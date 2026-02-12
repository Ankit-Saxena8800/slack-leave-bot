#!/bin/bash
# Stop test bot and restore production config

echo "🛑 STOPPING TEST BOT"
echo "===================="
echo ""

# Stop test bot
pkill -f "python3.*main.py"
rm -f .bot.lock
echo "✅ Test bot stopped"

# Restore production .env
if [ -f .env.backup ]; then
    mv .env.backup .env
    echo "✅ Restored production configuration"
fi

echo ""
echo "To start production bot:"
echo "  python3 main.py > bot.log 2>&1 &"
