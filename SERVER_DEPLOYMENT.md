# Self-Hosted Server Deployment Guide

## 🖥️ Option 1: Automated Deployment (Recommended)

### On Your Server:

```bash
# 1. Copy deploy.sh to your server
scp deploy.sh user@your-server:/tmp/

# 2. SSH to server
ssh user@your-server

# 3. Run deployment script
chmod +x /tmp/deploy.sh
/tmp/deploy.sh

# 4. Edit credentials
sudo nano /opt/slack-leave-bot/.env

# 5. Start the bot
sudo systemctl start slack-leave-bot
sudo systemctl enable slack-leave-bot

# 6. Check status
sudo systemctl status slack-leave-bot

# 7. View logs
sudo tail -f /var/log/slack-leave-bot/bot.log
```

---

## 🔧 Option 2: Manual Deployment

### 1. Install Dependencies

```bash
# Update system
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git

# Create directory
sudo mkdir -p /opt/slack-leave-bot
sudo chown $USER:$USER /opt/slack-leave-bot
cd /opt/slack-leave-bot
```

### 2. Get the Code

```bash
# Option A: Clone from GitHub
git clone https://github.com/Ankit-Saxena8800/slack-leave-bot.git .

# Option B: Copy from local machine
# On your Mac:
scp -r /Users/ankitsaxena/slack-leave-bot/* user@your-server:/opt/slack-leave-bot/
```

### 3. Setup Virtual Environment

```bash
cd /opt/slack-leave-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy .env template
cp .env.example .env  # or create new .env

# Edit with your credentials
nano .env
```

Add your actual credentials:
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
LEAVE_CHANNEL_ID=C03C4QAPABU
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

### 5. Test Run

```bash
# Test the bot works
source venv/bin/activate
python main.py

# Press Ctrl+C to stop after confirming it works
```

### 6. Create Systemd Service

```bash
sudo nano /etc/systemd/system/slack-leave-bot.service
```

Paste this configuration:
```ini
[Unit]
Description=Slack Leave Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/opt/slack-leave-bot
Environment="PATH=/opt/slack-leave-bot/venv/bin"
ExecStart=/opt/slack-leave-bot/venv/bin/python /opt/slack-leave-bot/main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/slack-leave-bot/bot.log
StandardError=append:/var/log/slack-leave-bot/error.log

[Install]
WantedBy=multi-user.target
```

**Replace YOUR_USERNAME** with your actual username!

### 7. Create Log Directory

```bash
sudo mkdir -p /var/log/slack-leave-bot
sudo chown $USER:$USER /var/log/slack-leave-bot
```

### 8. Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Start the bot
sudo systemctl start slack-leave-bot

# Enable auto-start on boot
sudo systemctl enable slack-leave-bot

# Check status
sudo systemctl status slack-leave-bot
```

---

## 📊 Management Commands

### Check Status
```bash
sudo systemctl status slack-leave-bot
```

### View Logs
```bash
# Live logs
sudo tail -f /var/log/slack-leave-bot/bot.log

# Error logs
sudo tail -f /var/log/slack-leave-bot/error.log

# Last 100 lines
sudo tail -n 100 /var/log/slack-leave-bot/bot.log
```

### Restart Bot
```bash
sudo systemctl restart slack-leave-bot
```

### Stop Bot
```bash
sudo systemctl stop slack-leave-bot
```

### Disable Auto-Start
```bash
sudo systemctl disable slack-leave-bot
```

---

## 🔄 Update Bot Code

```bash
cd /opt/slack-leave-bot

# Stop bot
sudo systemctl stop slack-leave-bot

# Pull latest code
git pull origin main

# Restart bot
sudo systemctl start slack-leave-bot

# Check it's working
sudo systemctl status slack-leave-bot
```

---

## 🔒 Security Best Practices

1. **Firewall**: Only expose necessary ports
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   ```

2. **Restrict .env permissions**:
   ```bash
   chmod 600 /opt/slack-leave-bot/.env
   ```

3. **Run as non-root user** (already configured in service)

4. **Regular updates**:
   ```bash
   sudo apt-get update && sudo apt-get upgrade
   ```

5. **Monitor logs** for suspicious activity

---

## 🐛 Troubleshooting

### Bot Won't Start
```bash
# Check logs
sudo journalctl -u slack-leave-bot -f

# Check if Python path is correct
which python3

# Check .env file exists
ls -la /opt/slack-leave-bot/.env
```

### Permission Issues
```bash
# Fix ownership
sudo chown -R $USER:$USER /opt/slack-leave-bot
sudo chown -R $USER:$USER /var/log/slack-leave-bot
```

### Bot Crashes
```bash
# Check error logs
sudo tail -f /var/log/slack-leave-bot/error.log

# Restart service
sudo systemctl restart slack-leave-bot
```

---

## 💰 Server Requirements

**Minimum:**
- 1 CPU core
- 512 MB RAM
- 2 GB disk space
- Ubuntu 20.04+ / Debian 11+ / CentOS 8+

**Recommended:**
- 1 CPU core
- 1 GB RAM
- 5 GB disk space
- Stable internet connection

---

## ✅ Success Checklist

After deployment:
- [ ] Bot service is running: `sudo systemctl status slack-leave-bot`
- [ ] Logs show polling: `sudo tail -f /var/log/slack-leave-bot/bot.log`
- [ ] Test message in Slack gets response
- [ ] Manager tagging works
- [ ] Bot auto-starts on server reboot

---

## 📞 Quick Reference

**Start:** `sudo systemctl start slack-leave-bot`
**Stop:** `sudo systemctl stop slack-leave-bot`
**Restart:** `sudo systemctl restart slack-leave-bot`
**Status:** `sudo systemctl status slack-leave-bot`
**Logs:** `sudo tail -f /var/log/slack-leave-bot/bot.log`
**Edit config:** `nano /opt/slack-leave-bot/.env`

---

Your bot will now run 24/7 on your server! 🎉
