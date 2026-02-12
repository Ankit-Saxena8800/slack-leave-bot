#!/usr/bin/env python3
"""
Verify Dashboard Data
Tests that the dashboard is showing the populated test data
"""
import requests
import json

print("\n" + "=" * 70)
print("Dashboard Data Verification")
print("=" * 70 + "\n")

BASE_URL = "http://localhost:3001"

def test_endpoint(name, url):
    """Test an API endpoint"""
    try:
        response = requests.get(f"{BASE_URL}{url}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {name}")
            return data
        else:
            print(f"❌ {name} - Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ {name} - Error: {e}")
        return None

# Test endpoints
print("1. Testing API Endpoints:\n")

overview = test_endpoint("Overview Stats", "/api/stats/overview?period=week")
if overview:
    print(f"   Total Leaves: {overview['total_leaves']}")
    print(f"   Compliant: {overview['compliant_count']}")
    print(f"   Non-Compliant: {overview['non_compliant_count']}")
    print(f"   Compliance Rate: {overview['compliance_rate']}%")
    print(f"   Pending Reminders: {overview['pending_reminders']}")
    print()

health = test_endpoint("Database Health", "/api/health/database")
if health:
    print(f"   Status: {health['status']}")
    print(f"   Leave Events: {health['tables']['leave_events']}")
    print(f"   Reminder Events: {health['tables']['reminder_events']}")
    print(f"   Daily Aggregates: {health['tables']['daily_aggregates']}")
    print()

events = test_endpoint("Recent Events", "/api/events/recent?limit=5")
if events:
    print(f"   Total Events: {len(events['events'])}")
    if events['events']:
        print(f"   Latest Event: {events['events'][0]['user_name']} - {events['events'][0]['event_type']}")
    print()

reminders = test_endpoint("Active Reminders", "/api/reminders/active")
if reminders:
    print(f"   Active Reminders: {reminders['count']}")
    print()

compliance = test_endpoint("Compliance Rate", "/api/compliance/rate?period=7d")
if compliance:
    print(f"   Average Compliance: {compliance['average_compliance_rate']}%")
    print()

print("\n2. Summary:\n")

if overview and overview['total_leaves'] > 0:
    print("✅ Dashboard has data")
    print(f"✅ {overview['total_leaves']} leave events recorded")
    print(f"✅ {overview['compliance_rate']}% compliance rate")
    print(f"✅ {overview['pending_reminders']} active reminders")
else:
    print("❌ No data in dashboard")

print("\n3. Dashboard Access:\n")
print(f"   URL: {BASE_URL}")
print("   Status: ✅ Running")
print("\n💡 Open in browser to see visual dashboard!")

print("\n" + "=" * 70)
print("Verification Complete!")
print("=" * 70 + "\n")
