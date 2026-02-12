# Slack Leave Verification Bot

A Python bot that monitors a Slack leave intimation channel and automatically verifies if employees have applied for leave in Zoho People. If not, it sends reminders to the employee and notifies HR/Admin.

## Features

- Monitors Slack channel for leave-related messages
- Parses dates mentioned in messages (supports various formats)
- Checks Zoho People for corresponding leave applications
- Sends reminders via:
  - Thread reply in the leave channel
  - Direct message to the employee
  - Notification to HR/Admin channel

## Setup Instructions

### Step 1: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click "Create New App" > "From scratch"
3. Name it (e.g., "Leave Verification Bot") and select your workspace

#### Configure OAuth & Permissions

Navigate to "OAuth & Permissions" and add these Bot Token Scopes:
- `channels:history` - Read messages in public channels
- `channels:read` - View basic channel info
- `chat:write` - Send messages
- `im:write` - Send direct messages
- `users:read` - View user info
- `users:read.email` - View user email addresses

#### Enable Socket Mode

1. Go to "Socket Mode" in the left sidebar
2. Enable Socket Mode
3. Create an App-Level Token with `connections:write` scope
4. Save the token (starts with `xapp-`)

#### Enable Events

1. Go to "Event Subscriptions"
2. Enable Events
3. Subscribe to bot events:
   - `message.channels` - Messages in public channels
   - `app_mention` - When bot is mentioned

#### Install the App

1. Go to "Install App"
2. Install to your workspace
3. Copy the Bot User OAuth Token (starts with `xoxb-`)

### Step 2: Set Up Zoho People API

1. Go to [Zoho API Console](https://api-console.zoho.com/)
2. Create a new "Self Client"
3. Generate a refresh token with these scopes:
   ```
   ZohoPeople.forms.READ
   ZohoPeople.leave.READ
   ZohoPeople.employee.READ
   ```

#### Getting Zoho Refresh Token

1. In API Console, go to your Self Client
2. Click "Generate Code"
3. Enter the scopes above and generate
4. Use the code to get refresh token:

```bash
curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
  -d "code=YOUR_CODE" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=authorization_code"
```

5. Save the `refresh_token` from the response

### Step 3: Configure the Bot

```bash
cd ~/slack-leave-bot
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
LEAVE_CHANNEL_ID=C0123456789        # The channel to monitor
ADMIN_CHANNEL_ID=C0123456789        # HR/Admin notification channel
HR_USER_ID=U0123456789              # Optional: specific HR user to notify

# Zoho People Configuration
ZOHO_CLIENT_ID=your-zoho-client-id
ZOHO_CLIENT_SECRET=your-zoho-client-secret
ZOHO_REFRESH_TOKEN=your-zoho-refresh-token
ZOHO_ORGANIZATION_ID=your-org-id    # Optional
ZOHO_DOMAIN=https://people.zoho.com # or .in, .eu based on your region

# Bot Configuration
CHECK_DAYS_RANGE=7                  # Days to search around mentioned date
```

#### Finding Slack Channel/User IDs

- Right-click on a channel > "View channel details" > scroll down for Channel ID
- Right-click on a user > "View profile" > click "..." > "Copy member ID"

### Step 4: Install and Run

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py
```

### Step 5: Add Bot to Channels

1. Go to your leave intimation channel in Slack
2. Type `/invite @YourBotName`
3. Do the same for the admin notification channel

## Usage

Once running, the bot will:

1. Monitor messages in the configured leave channel
2. Detect leave-related messages using keyword matching
3. Extract the employee's email from their Slack profile
4. Check Zoho People for matching leave applications
5. If found: Reply with confirmation and leave details
6. If not found:
   - Reply in thread with reminder
   - Send DM to the employee
   - Notify HR/Admin channel

### Example Messages the Bot Detects

- "Taking leave tomorrow"
- "I'll be on PTO from 15th to 17th Jan"
- "Won't be available on Monday - sick leave"
- "WFH on Friday"
- "Out of office next week"

## Running as a Service (Production)

### Using systemd (Linux)

Create `/etc/systemd/system/slack-leave-bot.service`:

```ini
[Unit]
Description=Slack Leave Verification Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/slack-leave-bot
Environment=PATH=/home/your-user/slack-leave-bot/venv/bin
ExecStart=/home/your-user/slack-leave-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable slack-leave-bot
sudo systemctl start slack-leave-bot
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

Run:
```bash
docker build -t slack-leave-bot .
docker run -d --env-file .env --name leave-bot slack-leave-bot
```

## Troubleshooting

### Bot not responding to messages
- Ensure bot is invited to the channel
- Check `LEAVE_CHANNEL_ID` is correct
- Verify Socket Mode is enabled in Slack app settings

### Can't find employee in Zoho
- Ensure Slack profile email matches Zoho People email
- Check Zoho API scopes include employee read access

### Token refresh errors
- Verify Zoho credentials are correct
- Check if refresh token has expired (regenerate if needed)
- Ensure correct Zoho domain (.com, .in, .eu)

## Logs

Logs are written to both console and `bot.log` file in the project directory.
