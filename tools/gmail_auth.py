"""Gmail OAuth setup — run once to generate token.json.

Usage:
    python tools/gmail_auth.py

This opens a browser tab where you authorize Gmail access.
On success, writes token.json to the project root.
token.json is used by the outreach --send command to send emails.
"""

import os
import sys
from pathlib import Path

# Allow running directly from tools/ or from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()


def run_auth_flow() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_id = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("Error: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env")
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = Path("token.json")
    token_path.write_text(creds.to_json())
    print(f"token.json written to {token_path.resolve()}")
    print("Gmail send is now enabled for: python main.py outreach --job-id <id> --send")


if __name__ == "__main__":
    run_auth_flow()
