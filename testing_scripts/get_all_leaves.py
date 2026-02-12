#!/usr/bin/env python3
"""
Get ALL leave records directly from the API to analyze structure
"""

import json
from dotenv import load_dotenv
from zoho_client import ZohoClient

load_dotenv()

def main():
    zoho_client = ZohoClient()

    print("Fetching ALL leave records (without filters)...\n")

    try:
        # Try to get leaves directly from the form
        response = zoho_client._make_request("GET", "/forms/leave/getRecords", params={})

        print(f"Response status: {response.get('response', {}).get('status')}")
        print(f"Response message: {response.get('response', {}).get('message', 'N/A')}")

        result = response.get("response", {}).get("result", [])

        if not result:
            print("\n✗ No leave records found or empty result")
            print(f"Full response: {json.dumps(response, indent=2)[:1000]}")
            return

        print(f"\n✓ Got response with {len(result)} items")

        # Parse the nested structure
        all_leaves = []
        for item in result:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, list):
                        all_leaves.extend(value)
                        print(f"  Found {len(value)} records in key '{key}'")
                    elif isinstance(value, dict):
                        all_leaves.append(value)

        print(f"\n✓ Total leaves extracted: {len(all_leaves)}")

        if not all_leaves:
            print("\n✗ Could not extract any leave records")
            print(f"Sample item structure: {json.dumps(result[0], indent=2)[:500]}")
            return

        # Analyze leave types
        leave_types = {}
        statuses = set()

        for leave in all_leaves:
            leave_type = leave.get("Leavetype") or leave.get("LeaveType") or leave.get("Type") or leave.get("LeaveTypeName") or "Unknown"
            status = leave.get("ApprovalStatus") or leave.get("Status") or "Unknown"

            leave_types[leave_type] = leave_types.get(leave_type, 0) + 1
            statuses.add(status)

        # Print analysis
        print("\n" + "="*80)
        print("LEAVE TYPES ANALYSIS")
        print("="*80)

        for leave_type, count in sorted(leave_types.items(), key=lambda x: x[1], reverse=True):
            marker = " ⚠️  COULD BE WFH/ON DUTY!" if any(keyword in leave_type.lower() for keyword in ['wfh', 'work from home', 'duty', 'remote', 'on duty']) else ""
            print(f"  {leave_type}: {count} records{marker}")

        print(f"\n" + "="*80)
        print("APPROVAL STATUSES")
        print("="*80)
        for status in sorted(statuses):
            print(f"  - {status}")

        # Print sample records
        print(f"\n" + "="*80)
        print("SAMPLE LEAVE RECORDS (first 3)")
        print("="*80)

        for i, leave in enumerate(all_leaves[:3], 1):
            print(f"\n--- Record {i} ---")
            print(json.dumps(leave, indent=2)[:400])

        # Check specifically for WFH
        if any('wfh' in lt.lower() or 'work from home' in lt.lower() or 'duty' in lt.lower() for lt in leave_types.keys()):
            print("\n" + "="*80)
            print("✓✓✓ SUCCESS! WFH/ON DUTY FOUND IN LEAVE RECORDS! ✓✓✓")
            print("="*80)
            print("\nThe solution is: WFH/On Duty is stored as a regular leave type.")
            print("The bot should check leave records and match by leave type.")
            print("\nWFH-related leave types found:")
            for lt in leave_types.keys():
                if any(keyword in lt.lower() for keyword in ['wfh', 'work from home', 'duty', 'remote', 'on duty']):
                    print(f"  - {lt}")
        else:
            print("\n✗ No WFH/On Duty leave types found")
            print("Possible reasons:")
            print("  1. WFH hasn't been applied by anyone yet")
            print("  2. WFH is in a different system/API")
            print("  3. Different naming convention")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
