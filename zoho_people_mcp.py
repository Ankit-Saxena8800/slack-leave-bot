#!/usr/bin/env python3
"""
Zoho People MCP Server
Model Context Protocol server for Zoho People leave management
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Any

import requests
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Zoho configuration
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
ZOHO_DOMAIN = os.getenv("ZOHO_DOMAIN", "https://people.zoho.in")

# Token cache
_access_token = None
_token_expiry = None


def get_access_token() -> str:
    """Get or refresh the Zoho access token"""
    global _access_token, _token_expiry

    if _access_token and _token_expiry and datetime.now() < _token_expiry:
        return _access_token

    token_url = "https://accounts.zoho.in/oauth/v2/token"
    payload = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }

    response = requests.post(token_url, data=payload)
    response.raise_for_status()
    token_data = response.json()

    _access_token = token_data["access_token"]
    _token_expiry = datetime.now() + timedelta(minutes=50)

    logger.info("Zoho access token refreshed")
    return _access_token


def zoho_api_request(method: str, endpoint: str, params: dict = None) -> dict:
    """Make authenticated request to Zoho People API"""
    token = get_access_token()
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json"
    }
    url = f"{ZOHO_DOMAIN}/people/api{endpoint}"

    response = requests.request(method, url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def get_employee_by_email(email: str) -> dict | None:
    """Fetch employee by email"""
    import json
    try:
        search_params = json.dumps({
            "searchField": "EmailID",
            "searchOperator": "Is",
            "searchText": email
        })
        response = zoho_api_request(
            "GET",
            "/forms/employee/getRecords",
            params={"searchParams": search_params}
        )
        if response.get("response", {}).get("result"):
            records = response["response"]["result"]
            if records and isinstance(records[0], dict):
                # Structure: [{"id": [{employee_data}]}]
                employee_list = list(records[0].values())[0]
                if isinstance(employee_list, list) and employee_list:
                    return employee_list[0]
                return employee_list
            elif records:
                return records[0]
        return None
    except Exception as e:
        logger.error(f"Failed to fetch employee: {e}")
        return None


def get_employee_leaves(employee_id: str, from_date: datetime, to_date: datetime) -> list:
    """Get leave records for an employee"""
    import json
    try:
        search_params = json.dumps({
            "searchField": "Employee_ID",
            "searchOperator": "Contains",
            "searchText": employee_id
        })
        response = zoho_api_request(
            "GET",
            "/forms/leave/getRecords",
            params={"searchParams": search_params}
        )
        leaves = []
        result = response.get("response", {}).get("result", [])
        for record in result:
            if isinstance(record, dict):
                for key, value in record.items():
                    if isinstance(value, list):
                        leaves.extend(value)
                    else:
                        leaves.append(value)
        return leaves
    except Exception as e:
        logger.error(f"Failed to fetch leaves: {e}")
        return []


# Create MCP server
server = Server("zoho-people")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="check_leave_applied",
            description="Check if an employee has applied for leave on Zoho People around a specific date",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Employee's email address"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check (YYYY-MM-DD format, defaults to today)"
                    },
                    "days_range": {
                        "type": "integer",
                        "description": "Number of days to search around the date (default: 7)"
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="get_employee_info",
            description="Get employee information from Zoho People by email",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Employee's email address"
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="get_pending_leaves",
            description="Get all pending leave requests for an employee",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Employee's email address"
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="get_leave_balance",
            description="Get leave balance for an employee (available leave days)",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Employee's email address"
                    }
                },
                "required": ["email"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls"""

    if name == "check_leave_applied":
        email = arguments["email"]
        date_str = arguments.get("date")
        days_range = arguments.get("days_range", 7)

        # Parse date
        if date_str:
            check_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            check_date = datetime.now()

        # Get employee
        employee = get_employee_by_email(email)
        if not employee:
            return [TextContent(
                type="text",
                text=f"Employee not found in Zoho People with email: {email}"
            )]

        employee_id = employee.get("Zoho_ID") or employee.get("EmployeeID") or employee.get("recordId")
        if not employee_id:
            return [TextContent(
                type="text",
                text="Could not determine employee ID from Zoho record"
            )]

        # Get leaves
        from_date = check_date - timedelta(days=days_range)
        to_date = check_date + timedelta(days=days_range)
        leaves = get_employee_leaves(employee_id, from_date, to_date)

        if leaves:
            leave_info = []
            for leave in leaves[:5]:
                from_d = leave.get("From", leave.get("from", "N/A"))
                to_d = leave.get("To", leave.get("to", "N/A"))
                status = leave.get("ApprovalStatus", leave.get("status", "N/A"))
                leave_type = leave.get("Leavetype", leave.get("leaveType", "Leave"))
                leave_info.append(f"- {leave_type}: {from_d} to {to_d} (Status: {status})")

            return [TextContent(
                type="text",
                text=f"Found {len(leaves)} leave application(s) for {email}:\n" + "\n".join(leave_info)
            )]
        else:
            return [TextContent(
                type="text",
                text=f"No leave applications found for {email} between {from_date.strftime('%d %b %Y')} and {to_date.strftime('%d %b %Y')}"
            )]

    elif name == "get_employee_info":
        email = arguments["email"]
        employee = get_employee_by_email(email)

        if not employee:
            return [TextContent(
                type="text",
                text=f"Employee not found in Zoho People with email: {email}"
            )]

        # Extract relevant info
        info = {
            "Name": employee.get("FirstName", "") + " " + employee.get("LastName", ""),
            "Email": employee.get("EmailID", email),
            "Employee ID": employee.get("EmployeeID", "N/A"),
            "Department": employee.get("Department", "N/A"),
            "Designation": employee.get("Designation", "N/A"),
            "Reporting To": employee.get("Reporting_To", "N/A")
        }

        info_text = "\n".join([f"{k}: {v}" for k, v in info.items()])
        return [TextContent(
            type="text",
            text=f"Employee Information:\n{info_text}"
        )]

    elif name == "get_pending_leaves":
        email = arguments["email"]
        employee = get_employee_by_email(email)

        if not employee:
            return [TextContent(
                type="text",
                text=f"Employee not found in Zoho People with email: {email}"
            )]

        employee_id = employee.get("Zoho_ID") or employee.get("EmployeeID") or employee.get("recordId")
        if not employee_id:
            return [TextContent(
                type="text",
                text="Could not determine employee ID"
            )]

        # Get leaves for next 90 days
        from_date = datetime.now()
        to_date = datetime.now() + timedelta(days=90)
        leaves = get_employee_leaves(employee_id, from_date, to_date)

        # Filter pending
        pending = [l for l in leaves if l.get("ApprovalStatus", "").lower() in ["pending", "submitted"]]

        if pending:
            leave_info = []
            for leave in pending:
                from_d = leave.get("From", "N/A")
                to_d = leave.get("To", "N/A")
                leave_type = leave.get("Leavetype", "Leave")
                leave_info.append(f"- {leave_type}: {from_d} to {to_d}")

            return [TextContent(
                type="text",
                text=f"Pending leave requests for {email}:\n" + "\n".join(leave_info)
            )]
        else:
            return [TextContent(
                type="text",
                text=f"No pending leave requests found for {email}"
            )]

    elif name == "get_leave_balance":
        email = arguments["email"]
        employee = get_employee_by_email(email)

        if not employee:
            return [TextContent(
                type="text",
                text=f"Employee not found in Zoho People with email: {email}"
            )]

        employee_id = employee.get("Zoho_ID") or employee.get("EmployeeID") or employee.get("recordId")
        if not employee_id:
            return [TextContent(
                type="text",
                text="Could not determine employee ID"
            )]

        try:
            response = zoho_api_request(
                "GET",
                "/leave/getLeaveTypeDetails",
                params={"userId": employee_id}
            )
            result = response.get("response", {}).get("result", [])

            if result:
                balance_info = []
                for lt in result:
                    name = lt.get("Name", lt.get("name", "Unknown"))
                    balance = lt.get("BalanceCount", lt.get("balance", "N/A"))
                    balance_info.append(f"- {name}: {balance} days")

                return [TextContent(
                    type="text",
                    text=f"Leave balance for {email}:\n" + "\n".join(balance_info)
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Could not retrieve leave balance for {email}"
                )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error fetching leave balance: {str(e)}"
            )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
