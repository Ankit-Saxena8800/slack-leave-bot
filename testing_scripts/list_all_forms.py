#!/usr/bin/env python3
"""
List all available forms from Zoho People API
"""

import json
from dotenv import load_dotenv
from zoho_client import ZohoClient

load_dotenv()

def main():
    zoho_client = ZohoClient()

    print("Fetching all available forms from Zoho People...\n")

    try:
        response = zoho_client._make_request("GET", "/forms")
        forms = response.get("response", {}).get("result", [])

        print(f"Found {len(forms)} forms:\n")
        print(f"{'#':<4} {'Form Link Name':<40} {'Display Name':<40} {'Custom':<8}")
        print("=" * 100)

        for i, form in enumerate(forms, 1):
            form_link_name = form.get("formLinkName", "N/A")
            display_name = form.get("displayName", "N/A")
            is_custom = "Yes" if form.get("iscustom", False) else "No"

            print(f"{i:<4} {form_link_name:<40} {display_name:<40} {is_custom:<8}")

        # Look for On Duty / WFH related forms
        print("\n" + "=" * 100)
        print("Searching for On Duty / WFH / Attendance related forms:")
        print("=" * 100)

        keywords = ["duty", "wfh", "attendance", "work", "from", "home", "remote"]

        matches = []
        for form in forms:
            form_link_name = form.get("formLinkName", "").lower()
            display_name = form.get("displayName", "").lower()

            for keyword in keywords:
                if keyword in form_link_name or keyword in display_name:
                    matches.append(form)
                    break

        if matches:
            print(f"\nFound {len(matches)} potential matches:\n")
            for form in matches:
                print(f"  Form Link Name: {form.get('formLinkName')}")
                print(f"  Display Name: {form.get('displayName')}")
                print(f"  Custom: {'Yes' if form.get('iscustom') else 'No'}")
                print()
        else:
            print("\n✗ No forms found with keywords: duty, wfh, attendance, work, from, home, remote")
            print("\nTry searching in the full list above for the On Duty form.")

    except Exception as e:
        print(f"ERROR: Failed to fetch forms: {e}")

if __name__ == "__main__":
    main()
