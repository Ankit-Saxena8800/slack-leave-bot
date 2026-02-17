# AWS EC2 Deployment Guide

## 🚀 Quick Deployment (5 Minutes)

### Prerequisites

1. **AWS Account** with EC2 access
2. **AWS CLI** installed and configured:
   ```bash
   # Install AWS CLI (if not installed)
   brew install awscli  # macOS
   # or
   pip install awscli

   # Configure AWS CLI
   aws configure
   # Enter: Access Key, Secret Key, Region (ap-south-1), Output format (json)
   ```

3. **Verify AWS CLI**:
   ```bash
   aws sts get-caller-identity
   # Should show your AWS account info
   ```

---

## 📋 Automated Deployment

### Run the Deployment Script

```bash
cd /Users/ankitsaxena/slack-leave-bot

# Run deployment script
./deploy-aws-ec2.sh
```

**The script will:**
- ✅ Create SSH key pair (`slack-bot-key.pem`)
- ✅ Create security group (allows SSH access)
- ✅ Launch Ubuntu EC2 instance (t3.micro - free tier)
- ✅ Install Python, dependencies, and bot code
- ✅ Set up systemd service for auto-start
- ✅ Configure logging

**Takes ~3-5 minutes**

---

## 🔧 Post-Deployment Configuration

After the script completes, you'll see the instance IP address.

### 1. SSH to Your EC2 Instance

```bash
ssh -i slack-bot-key.pem ubuntu@<PUBLIC_IP>
```

### 2. Configure Bot Credentials

```bash
sudo nano /opt/slack-leave-bot/.env
```

Update with your actual credentials:
```bash
SLACK_BOT_TOKEN=xoxb-your-actual-token
LEAVE_CHANNEL_ID=C03C4QAPABU
ADMIN_CHANNEL_ID=CL8CN59B2
POLL_INTERVAL=60
ZOHO_CLIENT_ID=your-actual-client-id
ZOHO_CLIENT_SECRET=your-actual-client-secret
ZOHO_REFRESH_TOKEN=your-actual-refresh-token
ZOHO_DOMAIN=https://people.zoho.in
CHECK_DAYS_RANGE=7
DRY_RUN=false
TEST_MODE=false
ANALYTICS_ENABLED=false
```

Save and exit (Ctrl+X, Y, Enter)

### 3. Start the Bot

```bash
sudo systemctl start slack-leave-bot
sudo systemctl status slack-leave-bot
```

Should show **"active (running)"**

### 4. Verify Bot is Working

```bash
# View logs
sudo tail -f /var/log/slack-leave-bot/bot.log

# Should show:
# ✅ Starting Slack Leave Bot...
# ✅ Monitoring channel: C03C4QAPABU
# ✅ Polling every 60s
```

---

## 📊 Instance Details

**Specifications:**
- **Instance Type:** t3.micro (1 vCPU, 1GB RAM)
- **Region:** ap-south-1 (Mumbai)
- **OS:** Ubuntu 22.04 LTS
- **Storage:** 8GB EBS
- **Cost:** ~$8-10/month (or free tier for first year)

**Networking:**
- **SSH:** Port 22 (open to 0.0.0.0/0)
- **Security Group:** slack-leave-bot-sg

---

## 🔒 Security Best Practices

### 1. Restrict SSH Access

```bash
# Update security group to only allow your IP
MY_IP=$(curl -s ifconfig.me)

aws ec2 revoke-security-group-ingress \
  --group-name slack-leave-bot-sg \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region ap-south-1

aws ec2 authorize-security-group-ingress \
  --group-name slack-leave-bot-sg \
  --protocol tcp \
  --port 22 \
  --cidr $MY_IP/32 \
  --region ap-south-1
```

### 2. Use Systems Manager (No SSH)

```bash
# Install SSM agent (already included in Ubuntu AMI)
# Access instance without SSH:
aws ssm start-session --target <instance-id> --region ap-south-1
```

### 3. Enable CloudWatch Monitoring

```bash
# View logs from CloudWatch
aws logs tail /aws/ec2/slack-leave-bot --follow --region ap-south-1
```

---

## 🔄 Management Commands

### From Local Machine

```bash
# Get instance status
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=slack-leave-bot" \
  --region ap-south-1 \
  --query 'Reservations[0].Instances[0].[InstanceId,State.Name,PublicIpAddress]' \
  --output table

# Stop instance (to save costs when not needed)
aws ec2 stop-instances --instance-ids <instance-id> --region ap-south-1

# Start instance
aws ec2 start-instances --instance-ids <instance-id> --region ap-south-1

# Terminate instance (DELETE - cannot undo!)
aws ec2 terminate-instances --instance-ids <instance-id> --region ap-south-1
```

### From EC2 Instance (via SSH)

```bash
# Start bot
sudo systemctl start slack-leave-bot

# Stop bot
sudo systemctl stop slack-leave-bot

# Restart bot
sudo systemctl restart slack-leave-bot

# Check status
sudo systemctl status slack-leave-bot

# View logs
sudo tail -f /var/log/slack-leave-bot/bot.log
sudo tail -f /var/log/slack-leave-bot/error.log

# View service logs
sudo journalctl -u slack-leave-bot -f
```

---

## 🔄 Update Bot Code

### Method 1: Git Pull (Recommended)

```bash
ssh -i slack-bot-key.pem ubuntu@<PUBLIC_IP>

cd /opt/slack-leave-bot
sudo systemctl stop slack-leave-bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start slack-leave-bot
```

### Method 2: Deploy New Instance

```bash
# Terminate old instance
aws ec2 terminate-instances --instance-ids <old-instance-id> --region ap-south-1

# Run deployment script again
./deploy-aws-ec2.sh
```

---

## 💰 Cost Optimization

### Free Tier (First 12 Months)

If you're within AWS free tier:
- ✅ t3.micro: 750 hours/month free
- ✅ 30 GB EBS storage free
- ✅ **Total cost: $0/month**

### After Free Tier

**Monthly costs in ap-south-1:**
- t3.micro instance: ~$8/month (24/7)
- EBS storage (8GB): ~$1/month
- Data transfer: ~$0.50/month
- **Total: ~$9-10/month**

### Cost Savings

**Option 1: Stop instance when not needed**
```bash
# Stop at night (if bot not needed 24/7)
aws ec2 stop-instances --instance-ids <instance-id> --region ap-south-1
# Cost: ~$3-5/month (12 hrs/day)
```

**Option 2: Use Spot Instances** (70% cheaper)
```bash
# Modify deploy script to use spot instances
# Risk: Can be terminated with 2-minute notice
# Cost: ~$2-3/month
```

**Option 3: Switch to Lambda** (cheapest)
```bash
# Serverless, pay-per-invocation
# Cost: ~$1-2/month
# Requires refactoring for Lambda
```

---

## 📊 Monitoring & Alerts

### Enable CloudWatch Monitoring

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name SlackLeaveBot \
  --dashboard-body file://cloudwatch-dashboard.json \
  --region ap-south-1
```

### Set Up Alarms

```bash
# Alert if instance stops
aws cloudwatch put-metric-alarm \
  --alarm-name slack-bot-instance-down \
  --alarm-description "Alert when bot instance is not running" \
  --metric-name StatusCheckFailed \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=InstanceId,Value=<instance-id> \
  --alarm-actions <sns-topic-arn> \
  --region ap-south-1
```

---

## 🐛 Troubleshooting

### Bot Not Starting

```bash
# Check service status
sudo systemctl status slack-leave-bot

# Check logs
sudo journalctl -u slack-leave-bot -n 50

# Common issues:
# 1. .env file not configured
# 2. Invalid credentials
# 3. Network connectivity
```

### Cannot SSH

```bash
# 1. Check security group allows your IP
aws ec2 describe-security-groups \
  --group-names slack-leave-bot-sg \
  --region ap-south-1

# 2. Check instance is running
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=slack-leave-bot" \
  --region ap-south-1 \
  --query 'Reservations[0].Instances[0].State.Name'

# 3. Use correct key file
ssh -i slack-bot-key.pem ubuntu@<PUBLIC_IP>
```

### High Costs

```bash
# Check instance type
aws ec2 describe-instances \
  --instance-ids <instance-id> \
  --region ap-south-1 \
  --query 'Reservations[0].Instances[0].InstanceType'

# Check if running when not needed
# Consider stopping at night or using Lambda
```

---

## 🔐 Backup & Disaster Recovery

### Backup Strategy

```bash
# Create AMI (snapshot)
aws ec2 create-image \
  --instance-id <instance-id> \
  --name "slack-bot-backup-$(date +%Y%m%d)" \
  --description "Slack Leave Bot backup" \
  --region ap-south-1

# List backups
aws ec2 describe-images \
  --owners self \
  --filters "Name=name,Values=slack-bot-backup-*" \
  --region ap-south-1
```

### Restore from Backup

```bash
# Launch instance from AMI
aws ec2 run-instances \
  --image-id <ami-id> \
  --instance-type t3.micro \
  --key-name slack-bot-key \
  --security-group-ids <sg-id> \
  --region ap-south-1
```

---

## ✅ Success Checklist

After deployment:
- [ ] EC2 instance is running
- [ ] Can SSH to instance
- [ ] Bot service is active
- [ ] Logs show "Polling channel C03C4QAPABU"
- [ ] Test message in Slack gets response
- [ ] Manager tagging works
- [ ] Security group restricted to your IP
- [ ] CloudWatch monitoring enabled

---

## 📞 Quick Reference

**Deployment:**
```bash
./deploy-aws-ec2.sh
```

**SSH:**
```bash
ssh -i slack-bot-key.pem ubuntu@<PUBLIC_IP>
```

**Start/Stop Bot:**
```bash
sudo systemctl start/stop/restart slack-leave-bot
```

**Logs:**
```bash
sudo tail -f /var/log/slack-leave-bot/bot.log
```

**AWS CLI:**
```bash
aws ec2 describe-instances --region ap-south-1
aws ec2 stop-instances --instance-ids <id> --region ap-south-1
```

---

Your Slack Leave Bot is now running 24/7 on AWS! 🎉
