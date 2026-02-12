# Bot Branding Guide - HR Team

## 🎯 Goal
Change bot name to "HR Team" and add STAGE logo as profile picture.

## ⚡ Quick Start

**File to upload:** `stage_logo_square_centered.png` (already created - properly centered, no stretching!)

**Steps:**
1. Go to https://api.slack.com/apps
2. Select your bot app
3. **Basic Information** → Update "App Name" to **"HR Team"**
4. **App Home** → Update "Display Name" to **"HR Team"** and "Default Username" to **"hrteam"**
5. **Basic Information** → Upload **`stage_logo_square_centered.png`**
6. Save changes and verify in Slack

---

## 📝 Step-by-Step Instructions

### **Step 1: Access Slack App Settings**

1. Go to: **https://api.slack.com/apps**
2. Sign in with your Slack workspace credentials
3. Find and click on your bot app (currently "LeaveBot" or similar)

---

### **Step 2: Update Display Name**

1. In the left sidebar, click **"Basic Information"**
2. Scroll to **"Display Information"** section
3. Update the following:

   ```
   App Name: HR Team
   Short Description: Leave tracking and verification assistant
   Long Description: Automated leave verification bot that checks
                     Zoho People and sends reminders for compliance
   ```

4. Click **"Save Changes"**

---

### **Step 3: Update Bot User Name**

1. In the left sidebar, click **"App Home"**
2. Under **"Your App's Presence in Slack"** section
3. Click **"Edit"** next to the bot user
4. Update:
   ```
   Display Name: HR Team
   Default Username: hrteam
   ```
5. **Save**

---

### **Step 4: Upload STAGE Logo**

#### **Use the Prepared Logo:**

**File to upload:** `stage_logo_square_centered.png`
- This is a properly centered square version (1024x1024)
- Maintains aspect ratio without stretching
- White background with STAGE logo centered

#### **Uploading:**

1. In **"Basic Information"** → **"Display Information"**
2. Under **"App Icon & Preview"**
3. Click **"Upload an image"** or **"Add App Icon"**
4. Select **`stage_logo_square_centered.png`**
5. Crop/adjust if needed
6. Click **"Save"**

---

### **Step 5: Update Background Color (Optional)**

1. Still in **"Display Information"**
2. Set **"Background Color"** to match STAGE branding
   - Example: `#1a1a1a` (dark) or `#ffffff` (white)
   - Or use STAGE's brand color

---

### **Step 6: Verify Changes**

1. Go to your Slack workspace
2. Find the bot in any channel
3. Check that:
   - ✅ Name shows as "HR Team"
   - ✅ STAGE logo appears as profile picture
   - ✅ Bot messages look professional

---

## 🎨 STAGE Logo Options

### **Option A: Extract from Website**

If STAGE has a website with the logo:
1. Right-click the logo → "Save image as"
2. Save as `stage_logo.png`
3. Upload to Slack as described above

### **Option B: Request from Design Team**

Ask your design/marketing team for:
- STAGE logo in PNG format
- 1024x1024 pixels
- Transparent background preferred

### **Option C: Use Existing File**

If you already have the logo:
1. Make sure it's at least 512x512 pixels
2. Convert to PNG if needed
3. Upload to Slack

---

## 🔧 Alternative: Update via Slack API (Advanced)

If you want to automate this, you can use the Slack API:

```bash
# Update bot profile picture
curl -F file=@stage_logo.png \
     -F token=YOUR_BOT_TOKEN \
     https://slack.com/api/users.setPhoto

# Update bot name
curl -X POST https://slack.com/api/users.profile.set \
     -H "Authorization: Bearer YOUR_BOT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "profile": {
         "display_name": "HR Team",
         "status_text": "Helping with leave tracking",
         "status_emoji": ":calendar:"
       }
     }'
```

---

## ✅ Verification Checklist

After updating, verify:

- [ ] Bot display name is "HR Team"
- [ ] STAGE logo appears as bot avatar
- [ ] Bot username is @hrteam or similar
- [ ] Logo is clear and not pixelated
- [ ] Background color matches STAGE branding
- [ ] Bot appears professional in messages

---

## 🎯 Expected Result

**Before:**
```
LeaveBot [4:55 PM]
Hi @user, I see you're planning to WFH...
```

**After:**
```
HR Team [4:55 PM]
Hi @user, I see you're planning to WFH...
```

With STAGE logo as the profile picture!

---

## ❓ Troubleshooting

**Q: Changes don't appear in Slack?**
- Wait 5-10 minutes for Slack to refresh
- Try reloading Slack (Cmd+R on Mac, Ctrl+R on Windows)
- Reinstall the app to the workspace if needed

**Q: Logo looks blurry?**
- Upload a higher resolution image (1024x1024)
- Make sure the original is sharp and clear

**Q: Can't find the bot app settings?**
- Make sure you're logged in as a workspace admin
- Check that you have permission to edit the app

---

## 📞 Need Help?

If you need assistance:
1. Provide your STAGE logo file
2. I can help resize/optimize it
3. I can guide you through the upload process

---

**Created:** 2026-02-11
**Bot Version:** Production v2.0
