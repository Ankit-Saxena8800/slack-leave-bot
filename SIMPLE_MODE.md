# Simple Bot Mode - Active ✅

## How It Works

### Step 1: User Posts Leave/WFH
User posts in Slack leave channel:
```
"Taking leave tomorrow"
"WFH on Friday"
"On leave next week"
```

### Step 2: Bot Checks Zoho
Bot immediately checks Zoho People to see if leave/WFH is applied.

### Step 3: Bot Responds

**If FOUND in Zoho:**
```
Thank you @user for informing and applying on Zoho! ✅
Your leave/WFH is noted.
```

**If NOT FOUND in Zoho:**
```
Hi @user, I couldn't find your leave/WFH application on Zoho for Feb 13, 2026.
Please apply on Zoho as well. I'll check again in 24 hours. 📋
```

### Step 4: 24-Hour Reminder
If still not applied after 24 hours, bot sends a DM:
```
Hi User Name! 👋

This is a reminder that you haven't applied for leave/WFH on Zoho yet.

*Dates:* Feb 13, 2026

Please apply on Zoho at your earliest convenience.
```

---

## Configuration

**Current Settings:**
- ✅ Simple Zoho verification (no approval workflow)
- ✅ Immediate Zoho check (no grace period)
- ✅ 24-hour reminder if not applied
- ✅ Single reminder (no multi-level escalation)
- ✅ Friendly HR-style messages
- ❌ No approval buttons needed
- ❌ No multi-level reminders
- ❌ No escalation to admin

**Reminder Schedule:**
- T+0: User posts → Bot checks Zoho → Bot replies
- T+24hrs: If not found → Bot sends DM reminder

---

## Example Flow

### Example 1: User Applied on Zoho ✅

```
User: "WFH tomorrow"
  ↓
Bot checks Zoho
  ↓
✅ FOUND in Zoho
  ↓
Bot: "Thank you @user for informing and applying on Zoho! ✅"
  ↓
Done! No reminder needed.
```

### Example 2: User Did NOT Apply ⚠️

```
User: "Taking leave Monday"
  ↓
Bot checks Zoho
  ↓
❌ NOT FOUND in Zoho
  ↓
Bot: "Hi @user, please apply on Zoho. I'll check again in 24 hours."
  ↓
Wait 24 hours...
  ↓
Bot checks Zoho again
  ↓
Still not found?
  ↓
Bot sends DM: "Reminder to apply on Zoho"
```

---

## Messages

### Thread Reply (Applied)
> Thank you @user for informing and applying on Zoho! ✅ Your leave/WFH is noted.

### Thread Reply (Not Applied)
> Hi @user, I couldn't find your leave/WFH application on Zoho for Feb 13, 2026. Please apply on Zoho as well. I'll check again in 24 hours. 📋

### DM Reminder (After 24 hours)
> Hi User Name! 👋
>
> This is a reminder that you haven't applied for leave/WFH on Zoho yet.
>
> *Dates:* Feb 13, 2026
>
> Please apply on Zoho at your earliest convenience.

---

## Testing

**Test 1: Post a leave message**
```
Post in Slack: "Taking leave tomorrow"
Expected: Bot checks Zoho and replies in thread
```

**Test 2: Check if applied**
- If you applied on Zoho: Get "Thank you" message
- If NOT applied: Get "Please apply" message

**Test 3: Wait 24 hours**
- If still not applied: Get DM reminder

---

## Bot Status

**Running:**
```
✅ Bot PID: 44164
✅ Mode: Simple Zoho Verification
✅ Channel: C0AALBN04KW
✅ Polling: Every 60 seconds
✅ Reminder: After 24 hours
```

**Features:**
- ✅ Leave detection (20+ patterns)
- ✅ WFH detection (8 patterns)
- ✅ Zoho verification
- ✅ 24-hour reminder
- ✅ Duplicate message fix
- ✅ Analytics tracking

---

## Quick Commands

```bash
# Check bot status
ps aux | grep "python3 main.py"

# View logs
tail -f bot.log

# Restart bot
pkill -f "python3 main.py" && rm -f .bot.lock && python3 main.py &

# Check reminders
grep "reminder" bot.log | tail -20
```

---

**Status:** ✅ ACTIVE - Simple Mode
**Last Updated:** Feb 10, 2026 14:28
**Ready for Production:** Yes
