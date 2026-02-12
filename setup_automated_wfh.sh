#!/bin/bash
# Setup script for automated WFH checking

echo "=========================================="
echo "Automated WFH Verification Setup"
echo "=========================================="
echo ""

# Check which solution to use
echo "Which automated solution do you want to use?"
echo ""
echo "1. Zoho Webhooks (RECOMMENDED - requires Zoho webhook support)"
echo "2. Headless Browser Automation (Works without API)"
echo "3. Test API endpoints first"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "Setting up Zoho Webhooks..."
        echo ""

        # Install Flask if needed
        pip3 install flask requests

        # Check if ngrok is installed
        if ! command -v ngrok &> /dev/null; then
            echo "⚠️  ngrok not found. Installing..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                brew install ngrok
            else
                echo "Please install ngrok manually: https://ngrok.com/download"
                exit 1
            fi
        fi

        # Start webhook server in background
        echo "Starting webhook server on port 3002..."
        nohup python3 zoho_webhook_server.py > webhook.log 2>&1 &
        WEBHOOK_PID=$!
        echo "Webhook server started (PID: $WEBHOOK_PID)"

        sleep 2

        # Start ngrok
        echo "Starting ngrok tunnel..."
        nohup ngrok http 3002 > ngrok.log 2>&1 &
        NGROK_PID=$!

        sleep 3

        # Get ngrok URL
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*' | head -1)

        echo ""
        echo "✅ Setup complete!"
        echo ""
        echo "Webhook URL: $NGROK_URL/webhooks/zoho/onduty"
        echo ""
        echo "Next steps:"
        echo "1. Go to Zoho People → Settings → Developer Space → Webhooks"
        echo "2. Create new webhook for 'On Duty' form"
        echo "3. Use URL: $NGROK_URL/webhooks/zoho/onduty"
        echo "4. Set trigger: On Create, On Update"
        echo "5. Include all fields (Employee_Email, Type, From, To, Status)"
        echo "6. Test the webhook"
        echo ""
        echo "Test URL: $NGROK_URL/webhooks/zoho/test"
        echo "Webhook logs: tail -f webhook.log"
        echo ""
        ;;

    2)
        echo ""
        echo "Setting up Headless Browser Automation..."
        echo ""

        # Install Playwright
        echo "Installing Playwright..."
        pip3 install playwright schedule
        playwright install chromium

        # Check if credentials are set
        if ! grep -q "ZOHO_USER_EMAIL" .env; then
            echo ""
            echo "⚠️  Zoho credentials not found in .env"
            echo ""
            read -p "Enter Zoho email: " zoho_email
            read -sp "Enter Zoho password: " zoho_password
            echo ""

            echo "" >> .env
            echo "# Automated WFH Checker" >> .env
            echo "ZOHO_USER_EMAIL=$zoho_email" >> .env
            echo "ZOHO_USER_PASSWORD=$zoho_password" >> .env
            echo "WFH_CHECK_INTERVAL_MINUTES=5" >> .env
            echo "DEBUG_SCREENSHOTS=false" >> .env

            echo "✅ Credentials added to .env"
        fi

        # Test connection
        echo ""
        echo "Testing Zoho login..."
        python3 -c "
from automated_zoho_checker import AutomatedZohoChecker
checker = AutomatedZohoChecker()
print('✅ Checker initialized successfully')
" || {
            echo "❌ Failed to initialize checker. Check your credentials."
            exit 1
        }

        # Start checker in background
        echo "Starting automated checker (checks every 5 minutes)..."
        nohup python3 automated_zoho_checker.py > zoho_checker.log 2>&1 &
        CHECKER_PID=$!

        echo ""
        echo "✅ Automated checker started (PID: $CHECKER_PID)"
        echo ""
        echo "The bot will now automatically check Zoho every 5 minutes"
        echo "for pending WFH requests and auto-confirm them."
        echo ""
        echo "Logs: tail -f zoho_checker.log"
        echo "Stop: kill $CHECKER_PID"
        echo ""
        ;;

    3)
        echo ""
        echo "Testing API endpoints..."
        echo ""

        python3 << 'EOF'
import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('ZOHO_ACCESS_TOKEN')
if not token:
    print("ERROR: ZOHO_ACCESS_TOKEN not found in .env")
    exit(1)

print("Testing different API endpoints...\n")

base_urls = [
    "https://people.zoho.in/people/api",
    "https://people.zoho.in/people/api/v2",
    "https://peopleapi.zoho.in/api",
]

endpoints = [
    "/attendance/onduty",
    "/attendance/entry",
    "/onduty/records",
    "/forms/OnDuty/getRecords",
]

headers = {"Authorization": f"Zoho-oauthtoken {token}"}

found_endpoints = []

for base_url in base_urls:
    for endpoint in endpoints:
        url = base_url + endpoint
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code not in [404, 401]:
                print(f"✓ FOUND: {url}")
                print(f"  Status: {response.status_code}")
                print(f"  Response: {response.text[:200]}...")
                print()
                found_endpoints.append(url)
        except Exception as e:
            pass

if found_endpoints:
    print(f"\n✅ Found {len(found_endpoints)} working endpoint(s)!")
    print("\nUpdate zoho_client.py with the correct endpoint.")
else:
    print("\n❌ No working endpoints found.")
    print("Consider using webhooks or headless automation.")
EOF
        ;;

    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Setup complete! Check the logs for any errors."
