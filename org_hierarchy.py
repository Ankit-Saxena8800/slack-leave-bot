"""
Organizational Hierarchy Manager
Loads and manages organizational structure, reporting chains, and employee data
"""

import json
import logging
from typing import Optional, Dict, List, Any
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Employee:
    """Represents an employee in the organization"""
    email: str
    name: str
    slack_id: str
    department: str
    manager: Optional[str]
    position: str
    employee_id: str
    is_senior_manager: bool = False
    is_hr: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'email': self.email,
            'name': self.name,
            'slack_id': self.slack_id,
            'department': self.department,
            'manager': self.manager,
            'position': self.position,
            'employee_id': self.employee_id,
            'is_senior_manager': self.is_senior_manager,
            'is_hr': self.is_hr
        }


@dataclass
class Department:
    """Represents a department in the organization"""
    id: str
    name: str
    head: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'head': self.head
        }


class OrgHierarchy:
    """Manages organizational hierarchy and reporting structure"""

    def __init__(self, hierarchy_file: str):
        """
        Initialize organizational hierarchy

        Args:
            hierarchy_file: Path to org hierarchy JSON file
        """
        self.hierarchy_file = hierarchy_file
        self.org_data: Optional[Dict] = None
        self.employees: Dict[str, Employee] = {}  # email -> Employee
        self.employees_by_slack_id: Dict[str, Employee] = {}  # slack_id -> Employee
        self.departments: Dict[str, Department] = {}  # dept_id -> Department
        self.approval_rules: Dict[str, Any] = {}

        self._load_hierarchy()

    def _load_hierarchy(self) -> bool:
        """
        Load organizational hierarchy from JSON file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            hierarchy_path = Path(self.hierarchy_file)
            if not hierarchy_path.exists():
                logger.error(f"Hierarchy file not found: {self.hierarchy_file}")
                return False

            with open(hierarchy_path, 'r') as f:
                data = json.load(f)

            self.org_data = data.get('organization', {})

            # Load departments
            for dept_data in self.org_data.get('departments', []):
                dept = Department(
                    id=dept_data['id'],
                    name=dept_data['name'],
                    head=dept_data['head']
                )
                self.departments[dept.id] = dept

            # Load employees
            for emp_data in self.org_data.get('employees', []):
                employee = Employee(
                    email=emp_data['email'],
                    name=emp_data['name'],
                    slack_id=emp_data['slack_id'],
                    department=emp_data['department'],
                    manager=emp_data.get('manager'),
                    position=emp_data['position'],
                    employee_id=emp_data['employee_id'],
                    is_senior_manager=emp_data.get('is_senior_manager', False),
                    is_hr=emp_data.get('is_hr', False)
                )
                self.employees[employee.email] = employee
                self.employees_by_slack_id[employee.slack_id] = employee

            # Load approval rules
            self.approval_rules = self.org_data.get('approval_rules', {})

            logger.info(f"Loaded organizational hierarchy: {len(self.employees)} employees, "
                       f"{len(self.departments)} departments")
            return True

        except Exception as e:
            logger.error(f"Failed to load org hierarchy: {e}", exc_info=True)
            return False

    def reload_hierarchy(self) -> bool:
        """
        Reload hierarchy from file (for dynamic updates)

        Returns:
            True if reloaded successfully
        """
        logger.info("Reloading organizational hierarchy...")
        self.employees.clear()
        self.employees_by_slack_id.clear()
        self.departments.clear()
        self.approval_rules.clear()
        return self._load_hierarchy()

    def get_employee(self, email: str) -> Optional[Employee]:
        """
        Get employee by email

        Args:
            email: Employee email address

        Returns:
            Employee object or None if not found
        """
        return self.employees.get(email)

    def get_employee_by_slack_id(self, slack_id: str) -> Optional[Employee]:
        """
        Get employee by Slack ID

        Args:
            slack_id: Slack user ID

        Returns:
            Employee object or None if not found
        """
        return self.employees_by_slack_id.get(slack_id)

    def get_manager(self, email: str) -> Optional[Employee]:
        """
        Get employee's direct manager

        Args:
            email: Employee email address

        Returns:
            Manager Employee object or None if no manager
        """
        employee = self.get_employee(email)
        if not employee or not employee.manager:
            return None

        return self.get_employee(employee.manager)

    def get_approval_chain(self, email: str, leave_days: int) -> List[Employee]:
        """
        Get approval chain for an employee based on leave duration

        Args:
            email: Employee email address
            leave_days: Number of leave days requested

        Returns:
            List of approvers (in order)
        """
        approval_chain = []

        employee = self.get_employee(email)
        if not employee:
            logger.warning(f"Employee not found: {email}")
            return approval_chain

        # Auto-approve threshold
        auto_approve_days = self.approval_rules.get('auto_approve_days', 2)
        if leave_days <= auto_approve_days:
            logger.info(f"Leave duration ({leave_days} days) qualifies for auto-approval")
            return approval_chain  # Empty chain = auto-approve

        # Standard approval: direct manager
        manager = self.get_manager(email)
        if manager:
            approval_chain.append(manager)

        # Extended leave: requires senior manager approval
        senior_approval_threshold = self.approval_rules.get('senior_manager_approval_days', 5)
        if leave_days > senior_approval_threshold:
            # Find senior manager in the chain
            senior_manager = self._find_senior_manager(manager)
            if senior_manager and senior_manager not in approval_chain:
                approval_chain.append(senior_manager)

        logger.info(f"Approval chain for {email} ({leave_days} days): "
                   f"{[a.name for a in approval_chain]}")
        return approval_chain

    def _find_senior_manager(self, employee: Optional[Employee]) -> Optional[Employee]:
        """
        Find the nearest senior manager in the reporting chain

        Args:
            employee: Starting employee

        Returns:
            Senior manager or None
        """
        current = employee
        visited = set()  # Prevent infinite loops

        while current:
            if current.email in visited:
                logger.warning(f"Circular reference detected in org hierarchy: {current.email}")
                break
            visited.add(current.email)

            if current.is_senior_manager:
                return current

            # Move up the chain
            if current.manager:
                current = self.get_employee(current.manager)
            else:
                break

        return None

    def validate_employee(self, email: str) -> bool:
        """
        Check if employee exists in the organization

        Args:
            email: Employee email address

        Returns:
            True if employee exists
        """
        return email in self.employees

    def is_manager(self, email: str) -> bool:
        """
        Check if employee is a manager (has direct reports)

        Args:
            email: Employee email address

        Returns:
            True if employee is a manager
        """
        for emp in self.employees.values():
            if emp.manager == email:
                return True
        return False

    def is_hr_user(self, email: str) -> bool:
        """
        Check if user is part of HR team

        Args:
            email: Employee email address

        Returns:
            True if user is HR
        """
        employee = self.get_employee(email)
        return employee.is_hr if employee else False

    def get_department(self, dept_id: str) -> Optional[Department]:
        """
        Get department by ID

        Args:
            dept_id: Department ID

        Returns:
            Department object or None
        """
        return self.departments.get(dept_id)

    def get_hr_users(self) -> List[Employee]:
        """
        Get all HR team members

        Returns:
            List of HR employees
        """
        return [emp for emp in self.employees.values() if emp.is_hr]

    def get_all_employees(self) -> List[Employee]:
        """
        Get all employees

        Returns:
            List of all employees
        """
        return list(self.employees.values())

    def get_direct_reports(self, manager_email: str) -> List[Employee]:
        """
        Get all direct reports of a manager

        Args:
            manager_email: Manager's email

        Returns:
            List of direct reports
        """
        return [emp for emp in self.employees.values() if emp.manager == manager_email]

    def get_approval_rules(self) -> Dict[str, Any]:
        """
        Get approval rules configuration

        Returns:
            Approval rules dictionary
        """
        return self.approval_rules.copy()


# Global instance
_org_hierarchy: Optional[OrgHierarchy] = None


def get_org_hierarchy() -> Optional[OrgHierarchy]:
    """Get global org hierarchy instance"""
    return _org_hierarchy


def set_org_hierarchy(hierarchy: OrgHierarchy):
    """Set global org hierarchy instance"""
    global _org_hierarchy
    _org_hierarchy = hierarchy
