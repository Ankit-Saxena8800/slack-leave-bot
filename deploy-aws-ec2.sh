#!/bin/bash
# AWS EC2 Deployment Script for Slack Leave Bot
# Region: ap-south-1 (Mumbai)
# Run this script with your AWS CLI configured

set -e

echo "🚀 Deploying Slack Leave Bot to AWS EC2 (ap-south-1)"

# Configuration
REGION="ap-south-1"
INSTANCE_TYPE="t3.micro"  # Free tier eligible
AMI_ID="ami-0f58b397bc5c1f2e8"  # Ubuntu 22.04 LTS in ap-south-1
KEY_NAME="slack-bot-key"
SECURITY_GROUP_NAME="slack-leave-bot-sg"
INSTANCE_NAME="slack-leave-bot"

# Check AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI not configured. Run: aws configure"
    exit 1
fi

echo "✅ AWS CLI configured"

# Create SSH key pair if doesn't exist
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$REGION" &> /dev/null; then
    echo "📝 Creating SSH key pair..."
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --region "$REGION" \
        --query 'KeyMaterial' \
        --output text > "$KEY_NAME.pem"
    chmod 400 "$KEY_NAME.pem"
    echo "✅ Key pair created: $KEY_NAME.pem"
else
    echo "✅ Key pair already exists"
fi

# Create security group
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
    --region "$REGION" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null)

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    echo "📝 Creating security group..."
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for Slack Leave Bot" \
        --region "$REGION" \
        --query 'GroupId' \
        --output text)

    # Allow SSH (port 22)
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --region "$REGION"

    echo "✅ Security group created: $SG_ID"
else
    echo "✅ Security group exists: $SG_ID"
fi

# Create user data script for bot installation
cat > user-data.sh << 'EOF'
#!/bin/bash
# Auto-setup script for EC2 instance

# Update system
apt-get update
apt-get upgrade -y

# Install Python and dependencies
apt-get install -y python3 python3-pip python3-venv git

# Create app directory
mkdir -p /opt/slack-leave-bot
cd /opt/slack-leave-bot

# Clone repository
git clone https://github.com/Ankit-Saxena8800/slack-leave-bot.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (placeholder - needs to be configured)
cat > .env << 'ENVEOF'
SLACK_BOT_TOKEN=your-token-here
LEAVE_CHANNEL_ID=C03C4QAPABU
ADMIN_CHANNEL_ID=CL8CN59B2
POLL_INTERVAL=60
ZOHO_CLIENT_ID=your-client-id
ZOHO_CLIENT_SECRET=your-client-secret
ZOHO_REFRESH_TOKEN=your-refresh-token
ZOHO_DOMAIN=https://people.zoho.in
CHECK_DAYS_RANGE=7
DRY_RUN=false
TEST_MODE=false
ANALYTICS_ENABLED=false
ENVEOF

# Create systemd service
cat > /etc/systemd/system/slack-leave-bot.service << 'SERVICEEOF'
[Unit]
Description=Slack Leave Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/slack-leave-bot
Environment="PATH=/opt/slack-leave-bot/venv/bin"
ExecStart=/opt/slack-leave-bot/venv/bin/python /opt/slack-leave-bot/main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/slack-leave-bot/bot.log
StandardError=append:/var/log/slack-leave-bot/error.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Create log directory
mkdir -p /var/log/slack-leave-bot
chown ubuntu:ubuntu /var/log/slack-leave-bot
chown -R ubuntu:ubuntu /opt/slack-leave-bot

# Enable service (will start after .env is configured)
systemctl daemon-reload
systemctl enable slack-leave-bot

echo "✅ Bot installed! Configure /opt/slack-leave-bot/.env and run: sudo systemctl start slack-leave-bot"
EOF

# Launch EC2 instance
echo "📝 Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --region "$REGION" \
    --user-data file://user-data.sh \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "✅ Instance launching: $INSTANCE_ID"

# Wait for instance to be running
echo "⏳ Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo ""
echo "✅ ========================================="
echo "✅ Deployment Complete!"
echo "✅ ========================================="
echo ""
echo "📊 Instance Details:"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"
echo "   Region: $REGION"
echo "   Key: $KEY_NAME.pem"
echo ""
echo "🔧 Next Steps:"
echo ""
echo "1. SSH to instance:"
echo "   ssh -i $KEY_NAME.pem ubuntu@$PUBLIC_IP"
echo ""
echo "2. Configure credentials:"
echo "   sudo nano /opt/slack-leave-bot/.env"
echo ""
echo "3. Add your actual tokens and credentials"
echo ""
echo "4. Start the bot:"
echo "   sudo systemctl start slack-leave-bot"
echo ""
echo "5. Check status:"
echo "   sudo systemctl status slack-leave-bot"
echo ""
echo "6. View logs:"
echo "   sudo tail -f /var/log/slack-leave-bot/bot.log"
echo ""
echo "✅ Bot is now running 24/7 on AWS EC2!"
echo ""

# Clean up
rm user-data.sh
