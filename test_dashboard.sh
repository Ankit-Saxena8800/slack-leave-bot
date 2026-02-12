#!/bin/bash
# Dashboard API Testing Script

echo "========================================"
echo "Dashboard API Testing"
echo "========================================"
echo ""

echo "1. Database Health Check"
echo "----------------------------------------"
curl -s 'http://localhost:3001/api/health/database'
echo ""
echo ""

echo "2. Bot Health Check"
echo "----------------------------------------"
curl -s 'http://localhost:3001/api/health/bot'
echo ""
echo ""

echo "3. Overview Stats (Week)"
echo "----------------------------------------"
curl -s 'http://localhost:3001/api/stats/overview?period=week'
echo ""
echo ""

echo "4. Recent Events (Limit 5)"
echo "----------------------------------------"
curl -s 'http://localhost:3001/api/events/recent?limit=5'
echo ""
echo ""

echo "5. Active Reminders"
echo "----------------------------------------"
curl -s 'http://localhost:3001/api/reminders/active'
echo ""
echo ""

echo "6. Compliance Rate (7 days)"
echo "----------------------------------------"
curl -s 'http://localhost:3001/api/compliance/rate?period=7d'
echo ""
echo ""

echo "========================================"
echo "All tests complete!"
echo "Dashboard is running on: http://localhost:3001"
echo "========================================"
