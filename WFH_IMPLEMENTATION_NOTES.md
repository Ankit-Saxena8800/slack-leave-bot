# WFH/On Duty Implementation Notes

## Problem Discovery

After extensive testing, we discovered that **WFH/On Duty records are NOT accessible via the Zoho People API**.

### What We Tested

1. **Forms API** - Checked all 19 available forms:
   - No "On Duty" or "WFH" form found
   - Available forms: employee, leave, asset, benefit, department, etc.

2. **Leave Records** - Analyzed 200 leave records:
   - Leave types found: Earned Leave, Flexi Leaves, Leave Without Pay, Maternity, Paternity
   - NO WFH or On Duty leave type exists

3. **Attendance Endpoints** - Tested 15+ different endpoints:
   - `/attendance/onduty` → 404
   - `/attendance/entry/onduty` → 404
   - `/attendance/log` → 404
   - `/attendance/checkin` → 404
   - All other variations → 404 or 401

### Root Cause

The Zoho People API we're using (`https://people.zoho.in/people/api/`) does not expose On Duty/WFH records. This appears to be a limitation of the Zoho People API itself, not our implementation.

The "Request On Duty" form visible in the Zoho web UI (at URL `#attendance/entry/onduty`) is a separate module that isn't accessible through the standard Forms API.

## Solution Implemented

Since we cannot verify WFH via API, the bot now:

1. **Detects WFH mentions** (using keywords: wfh, work from home, working from home, remote)
2. **Sends an acknowledgment message** with:
   - Recognition that the user is planning to WFH
   - Reminder to apply on Zoho People
   - Explanation that automatic verification isn't possible
3. **Skips Zoho verification** (to avoid false negatives)
4. **No reminders** (since we can't verify if they applied or not)

### Code Changes

**File: `slack_bot_polling.py`**

Added early return for WFH requests before Zoho verification:

```python
# IMPORTANT: WFH/On Duty verification is NOT supported via Zoho People API
if is_wfh:
    logger.info("WFH request detected - Zoho verification skipped (On Duty API not available)")
    # Send acknowledgment for WFH without verification
    formatted_dates = self._format_dates_for_display(leave_dates)
    message = (
        f"Hi <@{user_id}>, I see you're planning to WFH on {formatted_dates}. "
        f"Please ensure you've applied for On Duty (WFH) on Zoho People. "
        f"(Note: I can't automatically verify On Duty applications as they're not accessible via API)"
    )
    self._send_thread_reply(self.leave_channel_id, msg_ts, message)
    logger.info(f"Sent WFH acknowledgment to {user_name}")
    return  # Skip further processing for WFH
```

Added helper method for date formatting:

```python
def _format_dates_for_display(self, dates: List[datetime]) -> str:
    """Format a list of dates for display in messages"""
    if not dates:
        return "the requested dates"
    if len(dates) == 1:
        return dates[0].strftime("%b %d, %Y")
    elif len(dates) == 2:
        return f"{dates[0].strftime('%b %d')} and {dates[1].strftime('%b %d, %Y')}"
    else:
        sorted_dates = sorted(dates)
        first = sorted_dates[0].strftime("%b %d")
        last = sorted_dates[-1].strftime("%b %d, %Y")
        return f"{first} to {last}"
```

## Testing Results

### Test Scripts Created

1. `test_onduty_discovery.py` - Tested multiple endpoint variations
2. `list_all_forms.py` - Listed all 19 available Zoho forms
3. `test_attendance_endpoints.py` - Tested 15+ attendance endpoints
4. `check_wfh_in_leaves.py` - Checked if WFH is a leave type
5. `get_all_leaves.py` - Analyzed 200 leave records for WFH type

All tests confirmed: **WFH/On Duty is NOT accessible via API**

## Current Bot Behavior

### For Leave Requests (Regular Leaves)
✅ Detects leave mention
✅ Verifies in Zoho Leave Tracker
✅ Sends thank you OR reminder
✅ Tracks reminders and escalates

### For WFH Requests
✅ Detects WFH mention
✅ Extracts dates
⚠️  Sends acknowledgment (cannot verify)
❌ No Zoho verification (not possible)
❌ No reminders (cannot verify compliance)

## Alternative Solutions Considered

### Option 1: Manual API Discovery (Rejected)
- Would need access to Zoho Developer Console
- User would need to share exact form API names
- Already tried 50+ endpoint variations - none worked

### Option 2: Selenium/Web Scraping (Rejected)
- Would require browser automation
- Fragile (breaks with UI changes)
- Requires user credentials
- Against Zoho's terms of service

### Option 3: Treat WFH as Leave Type (Rejected)
- WFH is stored separately from leaves
- No WFH leave type exists in the system
- Would create confusion

### Option 4: Current Solution (Implemented)
- ✅ Transparent to users (explains limitation)
- ✅ Still provides value (acknowledgment + reminder)
- ✅ No false negatives
- ✅ Easy to revert if API becomes available

## Future Improvements

If Zoho adds On Duty API access:

1. Update `zoho_client.py` with correct endpoint
2. Remove the early return in `slack_bot_polling.py`
3. Enable full verification workflow for WFH

## User Communication

When a user mentions WFH, they now receive:

> Hi @user, I see you're planning to WFH on Feb 18, 2026. Please ensure you've applied for On Duty (WFH) on Zoho People. (Note: I can't automatically verify On Duty applications as they're not accessible via API)

This:
- ✅ Acknowledges their message (no silent failures)
- ✅ Reminds them to apply
- ✅ Explains the limitation transparently
- ✅ Sets correct expectations

## Summary

**Problem**: WFH/On Duty records not accessible via Zoho People API
**Solution**: Acknowledge WFH requests but skip verification
**Trade-off**: No automatic compliance tracking for WFH
**Benefit**: Bot still provides value and sets clear expectations

The bot now works correctly for:
- ✅ All leave types (Earned, Flexi, LWP, etc.)
- ✅ WFH mentions (with acknowledgment)
- ✅ Date parsing (including "Feb 12th" fix)
- ✅ Multi-date ranges
- ✅ Calendar year tracking

---

**Created**: 2026-02-11
**Last Updated**: 2026-02-11
