#!/bin/bash
# Slack Leave Bot - Server Deployment Script

set -e

echo "🚀 Deploying Slack Leave Bot..."

# Update system
echo "📦 Updating system packages..."
sudo apt-get update

# Install Python 3 and pip
echo "🐍 Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# Create app directory
APP_DIR="/opt/slack-leave-bot"
echo "📁 Creating app directory: $APP_DIR"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Clone or copy repository
cd $APP_DIR
echo "📥 Setting up code..."
# If using git:
# git clone https://github.com/Ankit-Saxena8800/slack-leave-bot.git .
# OR copy files if already downloaded

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create .env file
echo "⚙️ Creating .env file..."
cat > .env << 'EOF'
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
EOF

echo "⚠️  Please edit /opt/slack-leave-bot/.env with your actual credentials"

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/slack-leave-bot.service > /dev/null << EOF
[Unit]
Description=Slack Leave Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/slack-leave-bot/bot.log
StandardError=append:/var/log/slack-leave-bot/error.log

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/slack-leave-bot
sudo chown $USER:$USER /var/log/slack-leave-bot

echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit credentials: sudo nano /opt/slack-leave-bot/.env"
echo "2. Start bot: sudo systemctl start slack-leave-bot"
echo "3. Enable auto-start: sudo systemctl enable slack-leave-bot"
echo "4. Check status: sudo systemctl status slack-leave-bot"
echo "5. View logs: sudo tail -f /var/log/slack-leave-bot/bot.log"
