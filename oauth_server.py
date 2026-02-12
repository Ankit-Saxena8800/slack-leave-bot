#!/usr/bin/env python3
"""
OAuth callback server to automatically capture Slack tokens
"""
import http.server
import urllib.parse
import requests
import json
import os
import webbrowser
import threading
import time

CLIENT_ID = "475622235234.10353786012676"
CLIENT_SECRET = "0d01fc8aab614792903ee05e9d7a200c"
SIGNING_SECRET = "18e756e77d4fc2c7621b3753afe67fa3"
REDIRECT_URI = "http://localhost:3000/callback"
SCOPES = "app_mentions:read,channels:history,channels:read,chat:write,groups:history,groups:read,im:write,users:read,users:read.email"

ENV_FILE = os.path.join(os.path.dirname(__file__), '.env')


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_GET(self):
        if self.path.startswith('/callback'):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)

            if 'code' in params:
                code = params['code'][0]
                print(f"\n[+] Received authorization code")

                # Exchange code for token
                response = requests.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": REDIRECT_URI
                    }
                )

                data = response.json()

                if data.get("ok"):
                    bot_token = data.get("access_token")
                    team_name = data.get("team", {}).get("name", "Unknown")

                    print(f"[+] App installed to: {team_name}")
                    print(f"[+] Bot Token: {bot_token[:20]}...")

                    # Save to .env
                    self.save_token(bot_token)

                    # Send success response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"""
                    <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>Success!</h1>
                    <p>Leave Verification Bot has been installed.</p>
                    <p>You can close this window.</p>
                    <script>setTimeout(function(){window.close();}, 3000);</script>
                    </body></html>
                    """)

                    # Signal to stop server
                    threading.Thread(target=self.server.shutdown).start()
                else:
                    error = data.get("error", "Unknown error")
                    print(f"[-] OAuth failed: {error}")
                    self.send_error(400, f"OAuth failed: {error}")
            else:
                error = params.get('error', ['Unknown'])[0]
                print(f"[-] Authorization denied: {error}")
                self.send_error(400, f"Authorization denied: {error}")
        else:
            self.send_error(404)

    def save_token(self, bot_token):
        """Save bot token to .env file"""
        env_content = f"""# Slack Configuration (Auto-generated)
SLACK_BOT_TOKEN={bot_token}
SLACK_SIGNING_SECRET={SIGNING_SECRET}
LEAVE_CHANNEL_ID=
ADMIN_CHANNEL_ID=
HR_USER_ID=

# Zoho People Configuration
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REFRESH_TOKEN=
ZOHO_DOMAIN=https://people.zoho.com

# Bot Configuration
CHECK_DAYS_RANGE=7
POLL_INTERVAL=10
"""
        with open(ENV_FILE, 'w') as f:
            f.write(env_content)
        print(f"[+] Token saved to {ENV_FILE}")


def main():
    port = 3000
    server = http.server.HTTPServer(('localhost', port), OAuthHandler)

    print("=" * 50)
    print("Slack OAuth Setup")
    print("=" * 50)
    print(f"\n[*] Starting callback server on port {port}...")

    # Start server in background
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Open OAuth URL
    oauth_url = f"https://slack.com/oauth/v2/authorize?client_id={CLIENT_ID}&scope={SCOPES}&redirect_uri={REDIRECT_URI}"
    print(f"[*] Opening Slack authorization page...")
    webbrowser.open(oauth_url)

    print(f"\n[*] Waiting for authorization...")
    print("[*] Click 'Allow' in your browser to install the app.\n")

    # Wait for server to complete
    server_thread.join(timeout=120)  # 2 minute timeout

    if server_thread.is_alive():
        print("\n[-] Timeout waiting for authorization")
        server.shutdown()
    else:
        print("\n[+] OAuth complete!")
        print("[*] Run 'python main.py' to start the bot")


if __name__ == "__main__":
    main()
