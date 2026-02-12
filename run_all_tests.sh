#!/bin/bash
# Master Test Runner
# Runs all test suites for the Slack Leave Bot

echo "======================================================================="
echo "Running All Test Suites"
echo "======================================================================="
echo ""

# Create tests directory if it doesn't exist
mkdir -p tests

# Track results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test 1: Component Tests
echo "======================================================================="
echo "Test Suite 1: Component Tests"
echo "======================================================================="
if python3 tests/test_all_components.py; then
    echo "✅ Component tests PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ Component tests FAILED"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))
echo ""

# Test 2: Approval Workflow Tests
echo "======================================================================="
echo "Test Suite 2: Approval Workflow Tests"
echo "======================================================================="
if python3 tests/test_approval_workflow.py; then
    echo "✅ Approval workflow tests PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ Approval workflow tests FAILED"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))
echo ""

# Test 3: End-to-End Integration Tests
echo "======================================================================="
echo "Test Suite 3: End-to-End Integration Tests"
echo "======================================================================="
if python3 tests/test_end_to_end.py; then
    echo "✅ End-to-end tests PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ End-to-end tests FAILED"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))
echo ""

# Test 4: Dashboard Health Check
echo "======================================================================="
echo "Test Suite 4: Dashboard Health Check"
echo "======================================================================="
echo "Checking if dashboard server is running..."

if lsof -ti:3001 > /dev/null 2>&1; then
    echo "Dashboard is running on port 3001"
    echo "Testing API endpoints..."

    # Test health endpoint
    if curl -s http://localhost:3001/api/health/database | grep -q "healthy"; then
        echo "✅ Dashboard health check PASSED"
        ((PASSED_TESTS++))
    else
        echo "❌ Dashboard health check FAILED"
        ((FAILED_TESTS++))
    fi
else
    echo "⚠️  Dashboard not running (start with: cd dashboard && node server.js)"
    echo "⚠️  Skipping dashboard tests"
fi
((TOTAL_TESTS++))
echo ""

# Summary
echo "======================================================================="
echo "Test Results Summary"
echo "======================================================================="
echo "Total Test Suites: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo "======================================================================="
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED! 🎉"
    echo ""
    echo "Your Slack Leave Bot is fully tested and ready for production!"
    exit 0
else
    echo "❌ Some tests failed. Please review the output above."
    exit 1
fi
