#!/usr/bin/env python3
"""
Zoho OAuth Setup - Automatically captures Zoho credentials
"""
import http.server
import urllib.parse
import requests
import webbrowser
import threading
import os
import subprocess

# Zoho OAuth settings
# First we need to create a client, then use it for OAuth
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "ZohoPeople.forms.READ,ZohoPeople.leave.READ,ZohoPeople.employee.READ"
ENV_FILE = "/Users/ankitsaxena/slack-leave-bot/.env"

# We'll get these from user or create them
client_id = None
client_secret = None
done = threading.Event()
tokens = {}


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        global tokens
        if "/callback" in self.path:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)

            if "code" in params:
                code = params["code"][0]
                print(f"[+] Got authorization code")

                # Exchange code for tokens
                token_url = "https://accounts.zoho.com/oauth/v2/token"
                data = {
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code"
                }

                resp = requests.post(token_url, data=data)
                result = resp.json()

                if "refresh_token" in result:
                    tokens = result
                    print(f"[+] Got refresh token!")
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h1>Success! Zoho connected. Close this window.</h1>")
                    done.set()
                else:
                    print(f"[-] Error: {result}")
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(f"<h1>Error: {result}</h1>".encode())
            else:
                error = params.get("error", ["Unknown"])[0]
                print(f"[-] Error: {error}")
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def update_env_file(refresh_token, cid, csecret):
    """Update .env file with Zoho credentials"""
    # Read existing env
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    env_vars[key] = val

    # Update Zoho vars
    env_vars['ZOHO_CLIENT_ID'] = cid
    env_vars['ZOHO_CLIENT_SECRET'] = csecret
    env_vars['ZOHO_REFRESH_TOKEN'] = refresh_token

    # Write back
    with open(ENV_FILE, 'w') as f:
        for key, val in env_vars.items():
            f.write(f"{key}={val}\n")

    print(f"[+] Updated {ENV_FILE}")


def main():
    global client_id, client_secret

    print("=" * 50)
    print("ZOHO PEOPLE API SETUP")
    print("=" * 50)

    # Check if we already have Zoho credentials
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('ZOHO_CLIENT_ID=') and len(line.split('=')[1]) > 5:
                    client_id = line.split('=')[1]
                if line.startswith('ZOHO_CLIENT_SECRET=') and len(line.split('=')[1]) > 5:
                    client_secret = line.split('=')[1]

    if not client_id or not client_secret:
        print("\n[*] Opening Zoho API Console...")
        print("[*] Please create a 'Self Client' and enter the credentials below")
        subprocess.run(['open', 'https://api-console.zoho.com/'])

        print("\n[?] Enter your Zoho Client ID: ", end="")
        client_id = input().strip()
        print("[?] Enter your Zoho Client Secret: ", end="")
        client_secret = input().strip()

    print(f"\n[*] Using Client ID: {client_id[:10]}...")

    # Start OAuth server
    server = http.server.HTTPServer(('localhost', 8000), OAuthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # Build OAuth URL
    auth_url = (
        f"https://accounts.zoho.com/oauth/v2/auth"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&access_type=offline"
        f"&prompt=consent"
    )

    print("[*] Opening Zoho authorization page...")
    webbrowser.open(auth_url)

    print("[*] Waiting for authorization (click Accept in browser)...")

    if done.wait(120):
        refresh_token = tokens.get("refresh_token")
        print(f"\n[+] SUCCESS!")
        print(f"[+] Refresh Token: {refresh_token[:20]}...")

        update_env_file(refresh_token, client_id, client_secret)

        print("\n[+] Zoho setup complete!")
        print("[*] Restart the bot to apply changes:")
        print("    launchctl unload ~/Library/LaunchAgents/com.leavebot.plist")
        print("    launchctl load ~/Library/LaunchAgents/com.leavebot.plist")
    else:
        print("\n[-] Timeout waiting for authorization")

    server.shutdown()


if __name__ == "__main__":
    main()
