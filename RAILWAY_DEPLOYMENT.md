# Deploy to Railway.app - Step by Step

## ✅ All Files Ready!

Your bot is ready to deploy with:
- ✅ requirements.txt - Python dependencies
- ✅ Procfile - Start command
- ✅ railway.json - Auto-restart config
- ✅ Dockerfile - Container setup
- ✅ .gitignore - Excludes secrets

---

## 🚀 Deployment Steps

### Step 1: Push to GitHub (5 minutes)

```bash
# Initialize git (if not already)
cd /Users/ankitsaxena/slack-leave-bot
git init

# Add files
git add .
git commit -m "Deploy Slack Leave Bot to Railway"

# Create GitHub repo and push
# Go to: https://github.com/new
# Create repo named: slack-leave-bot
# Then run:
git remote add origin https://github.com/YOUR_USERNAME/slack-leave-bot.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Railway (3 minutes)

1. **Go to:** https://railway.app/
2. **Sign up/Login** with GitHub
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Choose **"slack-leave-bot"**
6. Railway will detect Python and auto-deploy!

### Step 3: Add Environment Variables (2 minutes)

In Railway dashboard:
1. Click on your project
2. Go to **"Variables"** tab
3. Click **"+ New Variable"**
4. Add these variables one by one:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
LEAVE_CHANNEL_ID=C0AALBN04KW
ADMIN_CHANNEL_ID=CL8CN59B2
POLL_INTERVAL=60
ZOHO_CLIENT_ID=your-zoho-client-id
ZOHO_CLIENT_SECRET=your-zoho-client-secret
ZOHO_REFRESH_TOKEN=your-zoho-refresh-token
ZOHO_DOMAIN=https://people.zoho.in
CHECK_DAYS_RANGE=7
DRY_RUN=false
TEST_MODE=false
ANALYTICS_ENABLED=false
```

**Important:** Copy these from your `.env` file!

### Step 4: Deploy & Verify (2 minutes)

1. Railway will auto-deploy after adding variables
2. Go to **"Deployments"** tab
3. Click on latest deployment
4. Check **"Logs"** - you should see:
   ```
   Starting Slack Leave Bot...
   Polling channel C0AALBN04KW every 60s
   ```

---

## ✅ Success Checklist

After deployment:
- [ ] Railway shows deployment as "Active"
- [ ] Logs show bot polling
- [ ] Send test message in Slack
- [ ] Bot responds within 60 seconds
- [ ] Manager tag works (@Nisha)

---

## 📊 Railway Dashboard Features

**View Logs:**
- Click **"View Logs"** to see real-time bot activity
- See every message processed
- Monitor manager lookups
- Check Zoho verifications

**Monitor Usage:**
- Free tier: 500 hours/month (enough for 24/7!)
- Shows CPU and memory usage
- Alerts if bot crashes

**Restart Bot:**
- Click **"Restart"** button if needed
- Bot auto-restarts on crash

---

## 🔧 Update Bot After Deployment

To update code after changes:

```bash
# Make your changes locally
# Test them

# Commit and push
git add .
git commit -m "Update bot code"
git push

# Railway auto-deploys!
```

---

## 💰 Cost

**Railway Free Tier:**
- ✅ 500 execution hours/month (20+ days of 24/7)
- ✅ Plenty for your bot
- ✅ $0/month

**After Free Tier:**
- $5/month for unlimited
- Still very cheap!

---

## 🐛 Troubleshooting

**Bot not starting?**
- Check Railway logs for errors
- Verify all environment variables are set
- Make sure SLACK_BOT_TOKEN is correct

**Bot not responding?**
- Check logs - is it polling?
- Verify LEAVE_CHANNEL_ID is correct
- Test Slack token is valid

**Manager tag not working?**
- Check logs for "Found manager" messages
- Verify manager exists in Zoho People
- Ensure manager is in Slack workspace

---

## 📞 After Deployment

**Stop Local Bot:**
```bash
cd /Users/ankitsaxena/slack-leave-bot
./stop_bot.sh
```

Your bot is now running in the cloud 24/7! 🎉

**Monitor it:**
- Railway dashboard: https://railway.app/dashboard
- Slack notifications: Bot will continue working
- Check logs anytime from Railway

---

**Deployment time: ~10 minutes total**
**Your bot will run forever in the cloud! 🚀**
