#!/usr/bin/env python3
"""
Local server for Zoho OAuth setup - handles token exchange
"""
import http.server
import json
import os
import requests
import urllib.parse
import webbrowser

ENV_FILE = "/Users/ankitsaxena/slack-leave-bot/.env"
PORT = 8888

HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>Zoho Setup</title>
    <style>
        body { font-family: -apple-system, Arial; max-width: 700px; margin: 40px auto; padding: 20px; background: #f5f5f5; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 20px 0; }
        input { width: 100%; padding: 12px; margin: 8px 0; font-size: 15px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
        button { background: #0066cc; color: white; padding: 15px 30px; font-size: 16px; border: none; cursor: pointer; width: 100%; border-radius: 5px; }
        button:hover { background: #0055aa; }
        .step-num { background: #0066cc; color: white; width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; }
        h2 { display: flex; align-items: center; margin-bottom: 15px; }
        code { background: #e8e8e8; padding: 8px 12px; display: block; margin: 10px 0; border-radius: 4px; font-size: 13px; word-break: break-all; }
        .success { background: #d4edda; border: 1px solid #c3e6cb; padding: 20px; border-radius: 5px; color: #155724; }
        .error { background: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; border-radius: 5px; color: #721c24; }
        a { color: #0066cc; }
    </style>
</head>
<body>
    <h1>🔧 Zoho People API Setup</h1>

    <div class="card">
        <h2><span class="step-num">1</span> Create Self Client</h2>
        <p>Go to <a href="https://api-console.zoho.com/" target="_blank">Zoho API Console</a> and create a <b>Self Client</b></p>
        <p>Copy the <b>Client ID</b> and <b>Client Secret</b>:</p>
        <input type="text" id="clientId" placeholder="Client ID (starts with 1000.)">
        <input type="text" id="clientSecret" placeholder="Client Secret">
    </div>

    <div class="card">
        <h2><span class="step-num">2</span> Generate Authorization Code</h2>
        <p>In Zoho API Console, click <b>"Generate Code"</b> tab, enter this scope:</p>
        <code>ZohoPeople.forms.READ,ZohoPeople.leave.READ,ZohoPeople.employee.READ</code>
        <p>Set <b>Time Duration: 10 minutes</b>, click <b>CREATE</b>, then paste the code:</p>
        <input type="text" id="authCode" placeholder="Authorization Code">
    </div>

    <div class="card">
        <button onclick="setupZoho()">🚀 Complete Setup</button>
    </div>

    <div id="result"></div>

    <script>
    async function setupZoho() {
        const clientId = document.getElementById('clientId').value.trim();
        const clientSecret = document.getElementById('clientSecret').value.trim();
        const authCode = document.getElementById('authCode').value.trim();

        if (!clientId || !clientSecret || !authCode) {
            document.getElementById('result').innerHTML = '<div class="error">Please fill in all fields</div>';
            return;
        }

        document.getElementById('result').innerHTML = '<div class="card">Processing...</div>';

        const resp = await fetch('/setup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({clientId, clientSecret, authCode})
        });

        const data = await resp.json();

        if (data.success) {
            document.getElementById('result').innerHTML = `
                <div class="success">
                    <h3>✅ Zoho Setup Complete!</h3>
                    <p>Credentials saved to .env file.</p>
                    <p>The bot will restart automatically with Zoho verification enabled.</p>
                </div>`;
        } else {
            document.getElementById('result').innerHTML = `
                <div class="error">
                    <h3>❌ Error</h3>
                    <p>${data.error}</p>
                    <p>Try generating a new authorization code (they expire in 10 minutes).</p>
                </div>`;
        }
    }
    </script>
</body>
</html>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path == '/setup':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))

            client_id = data['clientId']
            client_secret = data['clientSecret']
            auth_code = data['authCode']

            # Exchange code for refresh token
            token_url = "https://accounts.zoho.com/oauth/v2/token"
            resp = requests.post(token_url, data={
                'code': auth_code,
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'authorization_code'
            })

            result = resp.json()

            if 'refresh_token' in result:
                # Update .env file
                env_vars = {}
                if os.path.exists(ENV_FILE):
                    with open(ENV_FILE, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if '=' in line and not line.startswith('#'):
                                key, val = line.split('=', 1)
                                env_vars[key] = val

                env_vars['ZOHO_CLIENT_ID'] = client_id
                env_vars['ZOHO_CLIENT_SECRET'] = client_secret
                env_vars['ZOHO_REFRESH_TOKEN'] = result['refresh_token']

                with open(ENV_FILE, 'w') as f:
                    for key, val in env_vars.items():
                        f.write(f"{key}={val}\n")

                # Restart bot
                os.system('launchctl unload ~/Library/LaunchAgents/com.leavebot.plist 2>/dev/null')
                os.system('launchctl load ~/Library/LaunchAgents/com.leavebot.plist 2>/dev/null')

                response = {'success': True}
            else:
                response = {'success': False, 'error': result.get('error', str(result))}

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())


def main():
    print(f"Starting Zoho setup server on http://localhost:{PORT}")
    server = http.server.HTTPServer(('localhost', PORT), Handler)
    webbrowser.open(f'http://localhost:{PORT}')
    print("Browser opened. Complete the setup form.")
    print("Press Ctrl+C when done.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == '__main__':
    main()
