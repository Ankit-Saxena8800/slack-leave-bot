#!/usr/bin/env python3
"""
Check if WFH/On Duty is stored as a leave type
"""

import json
from dotenv import load_dotenv
from zoho_client import ZohoClient
from datetime import datetime, timedelta

load_dotenv()

def main():
    zoho_client = ZohoClient()

    # Use the specific user from screenshots (ankitsaxena@turtlemint.com or ankit.s@turtlemint.com)
    # Let's try to find employees and check their leave records

    print("Fetching all employees...")
    try:
        response = zoho_client._make_request("GET", "/forms/employee/getRecords")
        employees_result = response.get("response", {}).get("result", [])

        # Extract employee list
        all_employees = []
        for item in employees_result:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, list):
                        all_employees.extend(value)
                    else:
                        all_employees.append(value)

        print(f"Found {len(all_employees)} employees\n")

        # Try to find Ankit or just use first few employees
        test_employees = []
        for emp in all_employees[:30]:  # Test first 30 employees
            emp_email = emp.get("EmailID") or emp.get("Email") or emp.get("email", "")
            emp_id = emp.get("Zoho_ID") or emp.get("EmployeeID") or emp.get("recordId") or emp.get("Employee_ID")
            emp_name = emp.get("Name") or emp.get("FirstName", "") + " " + emp.get("LastName", "")

            if emp_id:
                test_employees.append({
                    "id": emp_id,
                    "email": emp_email,
                    "name": emp_name
                })

        print(f"Testing {len(test_employees)} employees for leave records:\n")

        all_leave_types = set()
        employees_with_leaves = 0

        for emp in test_employees:
            print(f"Checking {emp['name']} ({emp['email']})...")

            try:
                # Get leaves for a wide date range
                leaves = zoho_client.get_employee_leaves(
                    emp['id'],
                    from_date=datetime.now() - timedelta(days=60),
                    to_date=datetime.now() + timedelta(days=60)
                )

                if leaves:
                    employees_with_leaves += 1
                    print(f"  ✓ Found {len(leaves)} leave records")

                    # Extract leave types
                    for leave in leaves:
                        leave_type = leave.get("Leavetype") or leave.get("LeaveType") or leave.get("Type") or leave.get("LeaveTypeName")
                        if leave_type:
                            all_leave_types.add(leave_type)

                    # Print first leave record to see structure
                    if len(leaves) > 0:
                        print(f"  Sample record:")
                        print(f"    {json.dumps(leaves[0], indent=4)[:300]}...")
                else:
                    print(f"  ✗ No leaves found")

            except Exception as e:
                print(f"  ✗ Error: {e}")

            print()

        print("\n" + "="*80)
        print("ANALYSIS")
        print("="*80)
        print(f"\nEmployees with leave records: {employees_with_leaves}/{len(test_employees)}")
        print(f"\nAll leave types found:")

        for leave_type in sorted(all_leave_types):
            marker = " ⚠️  COULD BE WFH!" if any(keyword in leave_type.lower() for keyword in ['wfh', 'work from home', 'duty', 'remote']) else ""
            print(f"  - {leave_type}{marker}")

        if any('wfh' in lt.lower() or 'work from home' in lt.lower() or 'duty' in lt.lower() for lt in all_leave_types):
            print("\n✓ FOUND IT! WFH/On Duty appears to be stored as a leave type!")
            print("   Solution: The bot should check leave records for these leave types.")
        else:
            print("\n✗ WFH/On Duty NOT found in leave types")
            print("   This means either:")
            print("   1. No one has applied WFH in the test period")
            print("   2. WFH is stored elsewhere (not accessible via API)")
            print("   3. Different Zoho People configuration")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
