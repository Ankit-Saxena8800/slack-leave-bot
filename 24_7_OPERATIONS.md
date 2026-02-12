# Slack Leave Bot - 24/7 Operations Guide

## ✅ Current Status
- **Analytics:** DISABLED (no data storage, faster performance)
- **Dashboard:** STOPPED (not needed)
- **Bot Mode:** Core functionality only
- **Focus:** 100% uptime, fast responses

---

## 🚀 Quick Commands

### Start the Bot
```bash
cd /Users/ankitsaxena/slack-leave-bot
./start_bot.sh
```

### Stop the Bot
```bash
cd /Users/ankitsaxena/slack-leave-bot
./stop_bot.sh
```

### Check Bot Status
```bash
cd /Users/ankitsaxena/slack-leave-bot
./status_bot.sh
```

### View Live Logs
```bash
cd /Users/ankitsaxena/slack-leave-bot
tail -f bot.log
```

---

## 🔄 Keeping Bot Running 24/7

### Option 1: Manual Restart After Reboot
After Mac restart, simply run:
```bash
./start_bot.sh
```

### Option 2: Auto-Start on Mac Login (Recommended)
1. Open **System Preferences** → **Users & Groups**
2. Click **Login Items**
3. Click **+** and add `/Users/ankitsaxena/slack-leave-bot/start_bot.sh`

### Option 3: LaunchAgent (Always Running)
The bot will automatically restart if it crashes:

```bash
# Create LaunchAgent
cat > ~/Library/LaunchAgents/com.stage.slackleavebot.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stage.slackleavebot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/python3</string>
        <string>/Users/ankitsaxena/slack-leave-bot/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/ankitsaxena/slack-leave-bot</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/ankitsaxena/slack-leave-bot/bot.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ankitsaxena/slack-leave-bot/bot.log</string>
</dict>
</plist>
PLIST

# Load the service
launchctl load ~/Library/LaunchAgents/com.stage.slackleavebot.plist

# Start now
launchctl start com.stage.slackleavebot
```

To unload:
```bash
launchctl unload ~/Library/LaunchAgents/com.stage.slackleavebot.plist
```

---

## 📊 What the Bot Does (Core Only)

1. **Monitor Slack Channel** - Checks every 60 seconds
2. **Detect Leave Mentions** - "I'll be on leave", "taking leave", etc.
3. **Detect WFH Mentions** - "WFH", "working from home", etc.
4. **Verify with Zoho** - Checks if leave is applied in Zoho People
5. **Send Reminders** - If not found, sends follow-up reminders
6. **Track Reminders** - Stores in `pending_reminders.json`

**No analytics, no dashboard, no database - just pure bot functionality!**

---

## 🔍 Monitoring & Health

### Check if Bot is Working
```bash
# Quick check
ps aux | grep "python.*main.py" | grep -v grep

# Detailed check
./status_bot.sh
```

### View Recent Activity
```bash
tail -50 bot.log | grep -E "Processing|Found|reminder"
```

### Check Reminders
```bash
cat pending_reminders.json | python3 -m json.tool
```

---

## 🐛 Troubleshooting

### Bot Not Responding?
```bash
# Check if running
./status_bot.sh

# If not running, restart
./stop_bot.sh
./start_bot.sh
```

### Network Issues?
Bot has automatic retry logic for network failures. Just wait 1-2 minutes.

### Lock File Issues?
```bash
rm -f .bot.lock
./start_bot.sh
```

### Clear Old Reminders
```bash
# Edit pending_reminders.json to remove old entries
# Or delete and restart:
rm pending_reminders.json
./stop_bot.sh && ./start_bot.sh
```

---

## 📝 Configuration

All settings in `.env`:

### Core Settings
```bash
SLACK_BOT_TOKEN=your-token        # Slack bot token
LEAVE_CHANNEL_ID=C0AALBN04KW      # Channel to monitor
POLL_INTERVAL=60                   # Check every 60 seconds

ZOHO_CLIENT_ID=your-id            # Zoho credentials
ZOHO_CLIENT_SECRET=your-secret
ZOHO_REFRESH_TOKEN=your-token

ANALYTICS_ENABLED=false           # NO data storage
```

---

## ✅ Performance Optimizations

With analytics disabled:
- ✅ Faster response times (no database writes)
- ✅ Lower memory usage
- ✅ Simpler operation
- ✅ Fewer dependencies
- ✅ More reliable

---

## 🔒 Security Notes

- Bot token is in `.env` (keep secure, never commit to git)
- Process locking prevents duplicate instances
- 7-day message deduplication prevents reprocessing
- Automatic cleanup of old data

---

## 📞 Emergency Contacts

If bot fails:
1. Check logs: `tail -100 bot.log`
2. Restart: `./stop_bot.sh && ./start_bot.sh`
3. Verify Slack token hasn't expired
4. Check network connectivity
5. Verify Zoho credentials are valid

---

## 🎯 Current Status Summary

```
✅ Bot running: PID 70105
✅ Analytics: DISABLED
✅ Dashboard: STOPPED
✅ Mode: Core functionality only
✅ Uptime goal: 24/7
✅ Auto-recovery: Built-in retry logic
```

**Your bot is optimized for 24/7 operation with zero unnecessary overhead!**
