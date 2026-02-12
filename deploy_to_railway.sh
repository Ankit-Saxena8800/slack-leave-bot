#!/bin/bash
# Quick Deploy to Railway.app

echo "🚀 Railway.app Deployment Guide"
echo "================================"
echo ""
echo "✅ All files ready for deployment!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Go to: https://railway.app/"
echo "2. Click 'Start a New Project'"
echo "3. Select 'Deploy from GitHub repo'"
echo "4. Choose 'slack-leave-bot' repository"
echo ""
echo "5. Add Environment Variables in Railway:"
echo "   - Go to Variables tab"
echo "   - Copy from your .env file:"
echo ""
cat .env | grep -v "^#" | grep -v "^$" | grep -E "SLACK_BOT_TOKEN|LEAVE_CHANNEL|ADMIN_CHANNEL|ZOHO|POLL_INTERVAL" | sed 's/=.*/=***/'
echo ""
echo "6. Railway will auto-deploy!"
echo ""
echo "⏱️  Deployment takes ~2 minutes"
echo "📊 View logs in Railway dashboard"
echo "✅ Bot will run 24/7 forever!"
echo ""
echo "Press Enter to open Railway.app..."
read
open https://railway.app/
