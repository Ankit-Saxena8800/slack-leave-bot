"""
Zoho People API Client for Leave Management
"""
import os
import requests
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def _scrub_sensitive_data(text: str) -> str:
    """Remove sensitive tokens and credentials from text before logging"""
    if not text:
        return text

    # Remove access tokens (typically start with "1000.")
    text = re.sub(r'1000\.[a-f0-9]{32,}', '[REDACTED_TOKEN]', text, flags=re.IGNORECASE)

    # Remove any OAuth tokens
    text = re.sub(r'access_token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9._-]{20,}', 'access_token=[REDACTED]', text, flags=re.IGNORECASE)
    text = re.sub(r'refresh_token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9._-]{20,}', 'refresh_token=[REDACTED]', text, flags=re.IGNORECASE)

    # Remove client secrets
    text = re.sub(r'client_secret["\']?\s*[:=]\s*["\']?[a-zA-Z0-9]{20,}', 'client_secret=[REDACTED]', text, flags=re.IGNORECASE)

    # Remove authorization headers
    text = re.sub(r'Authorization["\']?\s*[:=]\s*["\']?Bearer\s+[a-zA-Z0-9._-]{20,}', 'Authorization=Bearer [REDACTED]', text, flags=re.IGNORECASE)

    return text


class ZohoClient:
    """Client for interacting with Zoho People API"""

    def __init__(self):
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")
        self.organization_id = os.getenv("ZOHO_ORGANIZATION_ID")
        self.domain = os.getenv("ZOHO_DOMAIN", "https://people.zoho.com")
        self.access_token = None
        self.token_expiry = None
        self._last_api_error = None

    def _get_access_token(self) -> str:
        """Get or refresh the access token"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        # Refresh the token (use .in for Indian accounts)
        token_url = "https://accounts.zoho.in/oauth/v2/token"
        payload = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }

        try:
            response = requests.post(token_url, data=payload, timeout=10)
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data["access_token"]
            # Token typically expires in 1 hour, set expiry to 50 minutes to be safe
            self.token_expiry = datetime.now() + timedelta(minutes=50)

            logger.info("Successfully refreshed Zoho access token")
            return self.access_token

        except requests.exceptions.Timeout as e:
            logger.error(f"Zoho token refresh timed out after 10s: {_scrub_sensitive_data(str(e))}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh Zoho token: {_scrub_sensitive_data(str(e))}")
            raise

    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make an authenticated request to Zoho People API"""
        token = self._get_access_token()

        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json"
        }

        url = f"{self.domain}/people/api{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=10  # 10 second timeout to prevent hanging
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            logger.error(f"Zoho API request timed out after 10s: {_scrub_sensitive_data(str(e))}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Zoho API request failed: {_scrub_sensitive_data(str(e))}")
            raise

    def get_manager_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Get manager information for an employee

        Args:
            email: Employee email address

        Returns:
            Dict with manager info: {'name': str, 'email': str, 'employee_id': str}
            None if not found or no manager assigned
        """
        try:
            employee = self.get_employee_by_email(email)
            if not employee:
                return None

            # Zoho People stores reporting manager in different possible fields
            # Check for various field name formats (with dots, underscores, etc.)
            manager_id = (employee.get('Reporting_To.ID') or
                         employee.get('Reporting_To') or
                         employee.get('ReportingTo') or
                         employee.get('ManagerId') or
                         employee.get('Manager'))

            # Get manager name and email from embedded fields
            manager_name = (employee.get('Reporting_To') or  # Contains full name
                           employee.get('ReportingTo') or
                           employee.get('Reporting_To_Name') or
                           employee.get('ReportingToName') or
                           employee.get('ManagerName'))

            manager_email = (employee.get('Reporting_To.MailID') or  # Zoho format with dot!
                            employee.get('ReportingTo.MailID') or
                            employee.get('Reporting_To_Email') or
                            employee.get('ReportingToEmail') or
                            employee.get('ManagerEmail'))

            if not manager_email:
                logger.info(f"No manager email found for {email}. Manager ID: {manager_id}, Name: {manager_name}")
                return None

            if manager_name or manager_email:
                return {
                    'name': manager_name,
                    'email': manager_email,
                    'employee_id': manager_id
                }

            # If manager details not embedded, try to fetch by ID
            try:
                endpoint = f"/forms/employee/getRecords"
                params = {'searchColumn': 'EmployeeID', 'searchValue': manager_id}
                response = self._make_request("GET", endpoint, params=params)

                if response and 'response' in response and 'result' in response['response']:
                    manager_data = response['response']['result']
                    if manager_data:
                        manager_record = manager_data[0] if isinstance(manager_data, list) else manager_data
                        return {
                            'name': manager_record.get('FullName') or manager_record.get('Name'),
                            'email': manager_record.get('EmailID') or manager_record.get('Email'),
                            'employee_id': manager_id
                        }
            except Exception as e:
                logger.warning(f"Could not fetch manager details by ID: {e}")

            return None

        except Exception as e:
            logger.error(f"Error getting manager info for {email}: {e}")
            return None

    def get_employee_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch employee details by email address

        Returns:
            Dict with employee data, None if not found
            Sets self._last_api_error if API fails
        """
        self._last_api_error = None
        endpoint = "/forms/employee/getRecords"
        import json
        search_params = json.dumps({
            "searchField": "EmailID",
            "searchOperator": "Is",
            "searchText": email
        })
        params = {"searchParams": search_params}

        try:
            response = self._make_request("GET", endpoint, params=params)

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

            return None  # Employee not found (API worked, no results)

        except Exception as e:
            error_str = str(e)
            logger.error(f"Failed to fetch employee by email {email}: {e}")
            if "403" in error_str or "forbidden" in error_str.lower():
                self._last_api_error = "ZOHO_API_ERROR: Access forbidden - check API permissions"
            else:
                self._last_api_error = f"ZOHO_API_ERROR: {e}"
            return None  # Return None but with error flag set

    def get_employee_leaves(
        self,
        employee_id: str,
        from_date: datetime = None,
        to_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get leave records for an employee within a date range

        Args:
            employee_id: Employee ID (e.g., SKS793)
            from_date: Start date for leave search (defaults to today)
            to_date: End date for leave search (defaults to 30 days from now)
        """
        if from_date is None:
            from_date = datetime.now()
        if to_date is None:
            to_date = datetime.now() + timedelta(days=30)

        try:
            import json
            endpoint = "/forms/leave/getRecords"
            search_params = json.dumps({
                "searchField": "Employee_ID",
                "searchOperator": "Contains",
                "searchText": employee_id
            })
            params = {"searchParams": search_params}

            response = self._make_request("GET", endpoint, params=params)

            leaves = []
            if response.get("response", {}).get("result"):
                result = response["response"]["result"]
                # Parse nested structure: [{"id": [{leave_data}]}]
                for record in result:
                    if isinstance(record, dict):
                        for key, value in record.items():
                            if isinstance(value, list):
                                leaves.extend(value)
                            else:
                                leaves.append(value)
                    else:
                        leaves.append(record)

            # Filter by date range - only include if date parsing succeeds
            filtered_leaves = []
            for leave in leaves:
                try:
                    leave_from = leave.get("From", "")
                    if leave_from:
                        leave_date_obj = datetime.strptime(leave_from, "%d-%b-%Y")
                        if from_date <= leave_date_obj <= to_date:
                            filtered_leaves.append(leave)
                except Exception as e:
                    logger.debug(f"Skipping leave due to date parse error: {e}")
                    # Don't include leaves with unparseable dates

            return filtered_leaves

        except Exception as e:
            logger.error(f"Failed to fetch leaves for employee {employee_id}: {e}")
            return []

    def check_leave_applied(
        self,
        email: str,
        leave_date: datetime = None,
        days_range: int = 7
    ) -> Dict[str, Any]:
        """
        Check if an employee has applied for leave around a specific date

        Args:
            email: Employee email address
            leave_date: The date mentioned in Slack (defaults to today)
            days_range: Number of days to search around the leave_date

        Returns:
            Dict with 'found' boolean, 'leaves' list, and 'employee' info
        """
        result = {
            "found": False,
            "leaves": [],
            "employee": None,
            "error": None
        }

        # Get employee by email
        employee = self.get_employee_by_email(email)

        # Check if there was an API error
        if self._last_api_error:
            result["error"] = self._last_api_error
            return result

        if not employee:
            result["error"] = f"Employee not found in Zoho People with email: {email}"
            logger.warning(result["error"])
            return result

        result["employee"] = employee
        # Use EmployeeID (like SKS793) for leave search, not Zoho_ID
        employee_id = employee.get("EmployeeID")

        if not employee_id:
            result["error"] = "Could not determine employee ID from Zoho record"
            logger.error(result["error"])
            return result

        # Set date range for search
        if leave_date is None:
            leave_date = datetime.now()

        from_date = leave_date - timedelta(days=days_range)
        to_date = leave_date + timedelta(days=days_range)

        # Get leave records
        leaves = self.get_employee_leaves(employee_id, from_date, to_date)

        # Check if any leave actually covers the requested leave_date
        if leaves:
            # DEBUG: Log all leave records to see what Zoho returns
            logger.info(f"DEBUG: Zoho returned {len(leaves)} total leave records for {employee_id}")
            for idx, leave in enumerate(leaves):
                logger.info(f"DEBUG: Leave #{idx+1}: {leave}")

            matching_leaves = []
            for leave in leaves:
                try:
                    leave_from_str = leave.get("From", "")
                    leave_to_str = leave.get("To", leave_from_str)  # Single day if no To
                    leave_type = leave.get("Leavetype", leave.get("LeaveType", leave.get("Type", "Unknown")))
                    leave_status = leave.get("ApprovalStatus", leave.get("Status", "Unknown"))

                    # DEBUG: Log each leave details
                    logger.info(f"DEBUG: Checking leave - Type: {leave_type}, Status: {leave_status}, From: {leave_from_str}, To: {leave_to_str}")

                    if leave_from_str:
                        leave_from = datetime.strptime(leave_from_str, "%d-%b-%Y")
                        leave_to = datetime.strptime(leave_to_str, "%d-%b-%Y") if leave_to_str else leave_from

                        # Check if the requested leave_date falls within this leave period
                        check_date = leave_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        if leave_from <= check_date <= leave_to:
                            matching_leaves.append(leave)
                            logger.info(f"Found matching leave: Type={leave_type}, From={leave_from_str}, To={leave_to_str}")
                except Exception as e:
                    logger.debug(f"Error parsing leave dates: {e}")

            if matching_leaves:
                result["found"] = True
                result["leaves"] = matching_leaves
            else:
                # Leaves exist but none match the specific date
                result["found"] = False
                result["leaves"] = []
                logger.info(f"Found {len(leaves)} leave(s) but none match date {leave_date.strftime('%d-%b-%Y')}")

        return result

    def get_employee_on_duty(
        self,
        employee_id: str,
        from_date: datetime = None,
        to_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get On Duty (WFH) records for an employee within a date range

        Args:
            employee_id: Employee ID (e.g., SKS793)
            from_date: Start date for search (defaults to today)
            to_date: End date for search (defaults to 30 days from now)

        Returns:
            List of On Duty records
        """
        if from_date is None:
            from_date = datetime.now()
        if to_date is None:
            to_date = datetime.now() + timedelta(days=30)

        try:
            import json
            # Try the attendance/onduty endpoint
            endpoint = "/attendance/onduty"
            search_params = json.dumps({
                "searchField": "Employee_ID",
                "searchOperator": "Contains",
                "searchText": employee_id
            })
            params = {"searchParams": search_params}

            response = self._make_request("GET", endpoint, params=params)

            on_duty_records = []
            if response.get("response", {}).get("result"):
                result = response["response"]["result"]
                # Parse nested structure similar to leave records
                for record in result:
                    if isinstance(record, dict):
                        for key, value in record.items():
                            if isinstance(value, list):
                                on_duty_records.extend(value)
                            else:
                                on_duty_records.append(value)
                    else:
                        on_duty_records.append(record)

            # Filter by date range
            filtered_records = []
            for record in on_duty_records:
                try:
                    date_str = record.get("Period", record.get("Date", ""))
                    if date_str:
                        # Parse date (format: 18-Feb-2026 or similar)
                        try:
                            record_date = datetime.strptime(date_str, "%d-%b-%Y")
                        except:
                            # Try alternative format
                            record_date = datetime.strptime(date_str, "%Y-%m-%d")

                        if from_date <= record_date <= to_date:
                            filtered_records.append(record)
                except Exception as e:
                    logger.debug(f"Skipping On Duty record due to date parse error: {e}")

            return filtered_records

        except Exception as e:
            logger.error(f"Failed to fetch On Duty records for employee {employee_id}: {e}")
            return []

    def get_pending_leaves(self, email: str) -> List[Dict[str, Any]]:
        """Get all pending leave requests for an employee"""
        employee = self.get_employee_by_email(email)
        if not employee:
            return []

        employee_id = employee.get("Zoho_ID") or employee.get("EmployeeID") or employee.get("recordId")
        if not employee_id:
            return []

        leaves = self.get_employee_leaves(
            employee_id,
            from_date=datetime.now(),
            to_date=datetime.now() + timedelta(days=90)
        )

        # Filter for pending status
        pending = [l for l in leaves if l.get("ApprovalStatus", "").lower() in ["pending", "submitted"]]
        return pending

    def check_leaves_applied_multi_date(
        self,
        email: str,
        leave_dates: List[datetime],
        is_wfh: bool = False
    ) -> Dict[str, Any]:
        """
        Check if an employee has applied for leaves for multiple specific dates.
        Uses calendar year tracking - queries entire year(s) from Zoho.

        Args:
            email: Employee email address
            leave_dates: List of datetime objects for leave dates

        Returns:
            Dict with 'found' boolean, 'leaves' list, 'employee' info, and 'missing_dates'
        """
        result = {
            "found": False,
            "leaves": [],
            "employee": None,
            "error": None,
            "missing_dates": [],
            "years_checked": []
        }

        if not leave_dates:
            result["error"] = "No leave dates provided"
            return result

        # Get employee by email
        employee = self.get_employee_by_email(email)

        # Check if there was an API error
        if self._last_api_error:
            result["error"] = self._last_api_error
            return result

        if not employee:
            result["error"] = f"Employee not found in Zoho People with email: {email}"
            logger.warning(result["error"])
            return result

        result["employee"] = employee
        employee_id = employee.get("EmployeeID")

        if not employee_id:
            result["error"] = "Could not determine employee ID from Zoho record"
            logger.error(result["error"])
            return result

        # Group dates by calendar year
        dates_by_year = {}
        for leave_date in leave_dates:
            year = leave_date.year
            if year not in dates_by_year:
                dates_by_year[year] = []
            dates_by_year[year].append(leave_date)

        logger.info(f"Checking {'WFH/On Duty' if is_wfh else 'leaves'} across {len(dates_by_year)} calendar year(s): {list(dates_by_year.keys())}")

        # Query Zoho for each calendar year (optimized to query only ±30 days around requested dates)
        all_leaves = []
        for year in sorted(dates_by_year.keys()):
            # OPTIMIZED: Query only ±30 days around min/max dates instead of entire year
            year_dates = dates_by_year[year]
            min_date = min(year_dates)
            max_date = max(year_dates)

            # Add 30-day buffer before and after
            from_date = max(min_date - timedelta(days=30), datetime(year, 1, 1))
            to_date = min(max_date + timedelta(days=30), datetime(year, 12, 31))

            logger.info(f"Querying Zoho for year {year}: {from_date.date()} to {to_date.date()} (±30 days around {min_date.date()} to {max_date.date()})")

            # Query regular leave records
            year_leaves = self.get_employee_leaves(employee_id, from_date, to_date)
            all_leaves.extend(year_leaves)

            # Also query On Duty (WFH) records if this is a WFH request
            if is_wfh:
                logger.info(f"Also querying On Duty (WFH) records for year {year}")
                on_duty_records = self.get_employee_on_duty(employee_id, from_date, to_date)
                all_leaves.extend(on_duty_records)
                logger.info(f"DEBUG: Found {len(on_duty_records)} On Duty records")

            result["years_checked"].append(year)

        logger.info(f"DEBUG: Zoho returned {len(all_leaves)} total {'leave/on-duty' if is_wfh else 'leave'} records across {len(dates_by_year)} year(s)")

        # Check each requested date against all returned leaves
        matching_leaves = []
        missing_dates = []

        for leave_date in leave_dates:
            date_found = False
            check_date = leave_date.replace(hour=0, minute=0, second=0, microsecond=0)

            for leave in all_leaves:
                try:
                    # Handle both Leave records (From/To) and On Duty records (Period/Date)
                    leave_from_str = leave.get("From", leave.get("Period", leave.get("Date", "")))
                    leave_to_str = leave.get("To", leave_from_str)
                    leave_type = leave.get("Leavetype", leave.get("LeaveType", leave.get("Type", "Unknown")))
                    leave_status = leave.get("ApprovalStatus", leave.get("Approval Status", leave.get("Status", "Unknown")))

                    # Detect WFH/On Duty requests
                    is_wfh_or_onduty = any(keyword in leave_type.lower() for keyword in ["on duty", "onduty", "wfh", "work from home"])

                    if leave_from_str:
                        # Try parsing with different date formats
                        leave_from = None
                        leave_to = None

                        for date_format in ["%d-%b-%Y", "%Y-%m-%d"]:
                            try:
                                leave_from = datetime.strptime(leave_from_str, date_format)
                                leave_to = datetime.strptime(leave_to_str, date_format) if leave_to_str else leave_from
                                break
                            except:
                                continue

                        if leave_from:
                            # Check if requested date falls within this leave/on-duty period
                            if leave_from <= check_date <= leave_to:
                                date_found = True
                                if leave not in matching_leaves:
                                    matching_leaves.append(leave)

                                # Enhanced logging to distinguish leave types
                                if is_wfh_or_onduty:
                                    logger.info(f"✓ Found WFH/On Duty for {check_date.date()}: Type={leave_type}, Status={leave_status}")
                                else:
                                    logger.info(f"✓ Found leave for {check_date.date()}: Type={leave_type}, Status={leave_status}")
                                break
                except Exception as e:
                    logger.debug(f"Error parsing leave/on-duty dates: {e}")
                    continue

            if not date_found:
                missing_dates.append(leave_date)
                logger.info(f"✗ No leave found for {check_date.date()}")

        # Update result
        if matching_leaves:
            result["found"] = True
            result["leaves"] = matching_leaves

        result["missing_dates"] = missing_dates

        # Overall found status: True only if ALL dates are covered
        if not missing_dates:
            result["found"] = True
        else:
            result["found"] = False

        return result
