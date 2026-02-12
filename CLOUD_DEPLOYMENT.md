# Deploy Slack Leave Bot to Cloud (24/7 Always Running)

## 🎯 Goal
Deploy bot to a cloud server so it runs **24/7 even when your Mac is off**.

---

## 🚀 Best Options (Easiest to Hardest)

### Option 1: Railway.app (RECOMMENDED - Easiest)
- ✅ **Free tier available**
- ✅ Automatic deployment from GitHub
- ✅ Built-in monitoring
- ✅ No server management needed
- ⏱️ **Setup time: 10 minutes**

### Option 2: AWS EC2 Free Tier
- ✅ Free for 1 year
- ✅ Full control
- ⚠️ Requires basic Linux knowledge
- ⏱️ **Setup time: 30 minutes**

### Option 3: DigitalOcean Droplet
- 💰 $6/month
- ✅ Very reliable
- ✅ Simple to use
- ⏱️ **Setup time: 20 minutes**

### Option 4: Google Cloud / Azure
- 💰 Pay as you go
- ✅ Enterprise grade
- ⏱️ **Setup time: 30-60 minutes**

---

## 🏆 RECOMMENDED: Railway.app Deployment

### Step 1: Prepare Your Code

1. Create a `requirements.txt`:
```bash
cd /Users/ankitsaxena/slack-leave-bot
cat > requirements.txt << 'EOF'
slack-sdk==3.23.0
python-dotenv==1.0.0
requests==2.31.0
dateparser==1.2.0
python-dateutil==2.8.2
EOF
```

2. Create a `Procfile`:
```bash
cat > Procfile << 'EOF'
worker: python main.py
EOF
```

3. Create a `railway.json`:
```bash
cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python main.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF
```

### Step 2: Push to GitHub (If Not Already)

```bash
# Initialize git if needed
git init
git add .
git commit -m "Deploy to Railway"

# Create repo on GitHub and push
# (or use existing repo)
```

### Step 3: Deploy to Railway

1. **Go to:** https://railway.app/
2. **Sign up** with GitHub
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Choose your `slack-leave-bot` repository
6. Railway will auto-detect Python and deploy

### Step 4: Add Environment Variables

In Railway dashboard:
1. Go to **"Variables"** tab
2. Add all variables from your `.env` file:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   LEAVE_CHANNEL_ID=C0AALBN04KW
   ADMIN_CHANNEL_ID=CL8CN59B2
   ZOHO_CLIENT_ID=...
   ZOHO_CLIENT_SECRET=...
   ZOHO_REFRESH_TOKEN=...
   ZOHO_DOMAIN=https://people.zoho.in
   POLL_INTERVAL=60
   ANALYTICS_ENABLED=false
   ```

### Step 5: Deploy!

Railway will automatically:
- ✅ Install dependencies
- ✅ Start your bot
- ✅ Keep it running 24/7
- ✅ Restart if it crashes
- ✅ Show logs in dashboard

**Done! Your bot is now running 24/7 in the cloud!**

---

## 🔧 Option 2: AWS EC2 Free Tier Deployment

### Step 1: Launch EC2 Instance

1. Go to AWS Console → EC2
2. Click **"Launch Instance"**
3. Choose **Ubuntu Server 22.04 LTS**
4. Select **t2.micro** (free tier)
5. Create or select key pair
6. Launch instance

### Step 2: Connect to Server

```bash
# Download your .pem key file
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### Step 3: Install Python and Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip git -y

# Clone your repository
git clone https://github.com/yourusername/slack-leave-bot.git
cd slack-leave-bot

# Install Python dependencies
pip3 install -r requirements.txt
```

### Step 4: Create .env File

```bash
nano .env
# Paste your environment variables
# Press Ctrl+X, Y, Enter to save
```

### Step 5: Create Systemd Service

```bash
sudo nano /etc/systemd/system/slackleavebot.service
```

Paste this:
```ini
[Unit]
Description=Slack Leave Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/slack-leave-bot
ExecStart=/usr/bin/python3 /home/ubuntu/slack-leave-bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 6: Start and Enable Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Start the bot
sudo systemctl start slackleavebot

# Enable auto-start on boot
sudo systemctl enable slackleavebot

# Check status
sudo systemctl status slackleavebot

# View logs
journalctl -u slackleavebot -f
```

**Done! Bot will run 24/7 and auto-start after server reboots!**

---

## 🐋 Option 3: Docker Deployment (Any Server)

### Step 1: Create Dockerfile

```bash
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run bot
CMD ["python", "main.py"]
EOF
```

### Step 2: Create docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  bot:
    build: .
    container_name: slack-leave-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./pending_reminders.json:/app/pending_reminders.json
      - ./bot.log:/app/bot.log
EOF
```

### Step 3: Deploy

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart
```

---

## 📊 Monitoring Your Cloud Bot

### Railway Dashboard
- View logs in real-time
- See resource usage
- Restart with one click
- Set up alerts

### AWS CloudWatch
```bash
# View logs
sudo journalctl -u slackleavebot -f

# Check process
systemctl status slackleavebot
```

### Docker
```bash
# Check status
docker ps

# View logs
docker logs -f slack-leave-bot

# Restart
docker restart slack-leave-bot
```

---

## 🔍 Verify Bot is Running in Cloud

### Test from Your Mac
```bash
# Check bot is responding in Slack
# Send a test message in the channel

# View logs from Railway/AWS dashboard
```

---

## 💰 Cost Comparison

| Service | Cost | Free Tier | Best For |
|---------|------|-----------|----------|
| **Railway** | Free → $5/mo | 500 hours/mo | Beginners |
| **AWS EC2** | Free → $8/mo | 1 year free | Learning AWS |
| **DigitalOcean** | $6/mo | $200 credit | Reliability |
| **Heroku** | $7/mo | No longer free | Legacy apps |
| **Fly.io** | Free → $2/mo | 3GB free | Small apps |

**Recommendation: Railway.app** - Easiest setup, generous free tier

---

## 🚨 Important Notes

### Before Deploying:
1. ✅ Push code to GitHub (Railway needs this)
2. ✅ Test bot locally first
3. ✅ Have all environment variables ready
4. ✅ Remove any local file paths from code

### Security:
- ✅ Never commit `.env` to GitHub
- ✅ Use environment variables in cloud
- ✅ Keep Slack/Zoho tokens secure
- ✅ Use SSH keys for server access

### Monitoring:
- ✅ Check logs daily (first week)
- ✅ Set up uptime monitoring (UptimeRobot.com - free)
- ✅ Get Slack notifications if bot goes down

---

## 🎯 Quick Start (Railway - 5 Steps)

```bash
# 1. Create required files
cat > requirements.txt << 'EOF'
slack-sdk==3.23.0
python-dotenv==1.0.0
requests==2.31.0
dateparser==1.2.0
python-dateutil==2.8.2
EOF

cat > Procfile << 'EOF'
worker: python main.py
EOF

# 2. Commit to git
git add .
git commit -m "Add Railway deployment files"
git push

# 3. Go to railway.app and sign up
# 4. Click "Deploy from GitHub"
# 5. Add environment variables

# Done! Bot running 24/7 in cloud!
```

---

## 📞 Need Help?

**Railway Issues:**
- Check logs in Railway dashboard
- Verify environment variables are set
- Ensure `Procfile` is correct

**AWS Issues:**
- Check systemd status: `sudo systemctl status slackleavebot`
- View logs: `journalctl -u slackleavebot -f`
- Restart: `sudo systemctl restart slackleavebot`

**Docker Issues:**
- Check container: `docker ps -a`
- View logs: `docker logs slack-leave-bot`
- Restart: `docker restart slack-leave-bot`

---

## ✅ Success Checklist

After deployment:
- [ ] Bot shows as online in cloud dashboard
- [ ] Bot responds to test message in Slack
- [ ] Logs show polling activity
- [ ] Zoho verification working
- [ ] Reminders being sent
- [ ] Bot survives server restart
- [ ] No errors in logs

**Your bot will now run 24/7 forever! 🎉**
