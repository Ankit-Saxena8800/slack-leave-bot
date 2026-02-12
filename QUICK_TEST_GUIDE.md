# Quick Workflow Test Guide

## ⚡ TEST MODE ACTIVE!

Bot is now configured for **SUPER FAST testing**:

### Fast Settings:
- ✅ **Polling:** Every 10 seconds (not 60)
- ✅ **1st Reminder:** 2 minutes (not 12 hours)
- ✅ **2nd Reminder:** 4 minutes (not 48 hours)
- ✅ **Urgent Alert:** 6 minutes (not 72 hours)

---

## 🧪 Quick Test Steps

### 1. Send Test Message (Right Now!)
Go to **#test-leave-bot** and send:
```
I'll be doing WFH on March 15th
```

### 2. Bot Response (Within 10 seconds)
Bot will reply:
```
Hi @You, I couldn't find your leave/WFH application on Zoho for Mar 15, 2026. 
Please apply on Zoho as well. I'll check again in 24 hours.
```

### 3. First Reminder (2 minutes later)
Bot will send:
```
⚠️ Reminder: @You, your leave/WFH for Mar 15, 2026 is still not applied on Zoho. 
Please apply as soon as possible. CC: @YourManager
```
✅ **Check if your REAL manager is tagged!**

### 4. Second Reminder (4 minutes total)
```
⚠️ URGENT: @You, please apply your leave immediately for Mar 15, 2026. 
CC: @YourManager
```

### 5. Final Alert (6 minutes total)
Admin gets notified + manager tagged again

---

## ⏱️ Complete Timeline

```
0:00 - Send "I'll be WFH on March 15th"
0:10 - Bot detects and responds
2:00 - 1st Reminder (with manager tag)
4:00 - 2nd Reminder (urgent)
6:00 - Final alert to admin
```

**Total test time: 6 minutes!** (vs 72 hours in production)

---

## 🔍 Watch Live Logs

In terminal, run:
```bash
tail -f bot.log | grep -E "Processing|Found|manager|Reminder"
```

You'll see:
- Message detected
- Manager lookup
- Zoho verification
- Reminder scheduling
- Manager tagging

---

## ✅ What to Verify

1. **Initial Response:**
   - [ ] Bot replies within 10 seconds
   - [ ] Mentions you correctly
   - [ ] Shows correct date

2. **Manager Tagging (2min):**
   - [ ] Actual manager name appears (not "@manager")
   - [ ] Manager gets Slack notification
   - [ ] Can click manager name

3. **Reminder Progression:**
   - [ ] 1st reminder at ~2 minutes
   - [ ] 2nd reminder at ~4 minutes
   - [ ] Admin notified at ~6 minutes

4. **Zoho Integration:**
   - [ ] Bot correctly identifies leave not in Zoho
   - [ ] If you apply on Zoho, bot stops reminders

---

## 🛑 Stop Test After Verification

Once you've verified everything works:

```bash
# Disable test mode
sed -i '' 's/TEST_MODE=true/TEST_MODE=false/' .env

# Restore normal polling
sed -i '' 's/POLL_INTERVAL=10/POLL_INTERVAL=60/' .env

# Restart bot
./stop_bot.sh && ./start_bot.sh
```

This will restore:
- ✅ Polling every 60 seconds
- ✅ 12/48/72 hour reminder schedule
- ✅ Production mode

---

## 📊 Current Bot Status

```
✅ Test Mode: ENABLED
✅ Polling: Every 10 seconds
✅ Channel: #test-leave-bot (C0AALBN04KW)
✅ Reminders: 2/4/6 minutes
✅ Manager tagging: FROM ZOHO
✅ Bot PID: 72641
```

---

## 🎯 Ready to Test!

**Send this message NOW in #test-leave-bot:**
```
I'll be doing WFH on March 15th
```

Then watch for:
1. Immediate bot response
2. Manager tag in 2 minutes
3. Full workflow in 6 minutes!

**Let's verify the manager tagging works! 🚀**
