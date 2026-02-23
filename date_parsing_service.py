"""
Enhanced Date Parsing Service for Slack Leave Bot
Supports date ranges, relative dates, partial leaves, and fuzzy parsing
"""

import re
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import dateparser
from dateutil.parser import parse as dateutil_parse
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


class LeaveType(Enum):
    """Type of leave"""
    FULL_DAY = "full_day"
    HALF_DAY = "half_day"
    HOURLY = "hourly"


@dataclass
class DateRange:
    """Represents a date range"""
    start_date: datetime
    end_date: datetime
    days_count: int
    working_days_only: bool = True

    def get_dates(self) -> List[datetime]:
        """Get all dates in range (excluding weekends if working_days_only)"""
        dates = []
        current = self.start_date
        while current <= self.end_date:
            if not self.working_days_only or current.weekday() < 5:  # Mon-Fri
                dates.append(current)
            current += timedelta(days=1)
        return dates


@dataclass
class PartialLeaveInfo:
    """Information about partial leave"""
    leave_type: LeaveType
    date: datetime
    time_range: Optional[Tuple[str, str]] = None  # e.g., ("14:00", "17:00")
    period: Optional[str] = None  # e.g., "morning", "afternoon"


@dataclass
class ParsedDateResult:
    """Result of date parsing"""
    dates: List[datetime]
    date_range: Optional[DateRange] = None
    leave_type: LeaveType = LeaveType.FULL_DAY
    confidence: float = 1.0
    parsed_fragments: List[str] = None

    def __post_init__(self):
        if self.parsed_fragments is None:
            self.parsed_fragments = []


class DateParsingService:
    """Enhanced date parsing service with multiple strategies"""

    def __init__(self, max_range_days: int = 90, working_days_only: bool = True):
        """
        Initialize date parsing service

        Args:
            max_range_days: Maximum allowed date range
            working_days_only: Whether to only include working days in ranges
        """
        self.max_range_days = max_range_days
        self.working_days_only = working_days_only

        # Compile regex patterns
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for date parsing"""
        # Date range patterns (ordered by specificity - most specific first!)
        self.range_patterns = [
            # "23rd Feb 2026 to 25th Feb 2026" - Full date with year
            re.compile(r'(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})', re.IGNORECASE),
            # "Feb 23 2026 to Feb 25 2026" - Month first with year
            re.compile(r'(\w+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4})\s+to\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?\s+\d{4})', re.IGNORECASE),
            # "from Jan 15 to Jan 20", "from 15th Jan to 20th Jan"
            re.compile(r'from\s+(\w+\s+\d{1,2}|\d{1,2}\s+\w+)\s+to\s+(\w+\s+\d{1,2}|\d{1,2}\s+\w+)', re.IGNORECASE),
            # "Jan 15 - Jan 20", "15 Jan - 20 Jan"
            re.compile(r'(\w+\s+\d{1,2}|\d{1,2}\s+\w+)\s*-\s*(\w+\s+\d{1,2}|\d{1,2}\s+\w+)', re.IGNORECASE),
            # "15th to 20th" (no month/year) - LAST as it's most greedy
            re.compile(r'(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s*(?:to|-)\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s+(?:of\s+)?(\w+))?(?!\d)', re.IGNORECASE),
        ]

        # Partial leave patterns
        self.partial_patterns = {
            'half_day': re.compile(r'half\s*day|1/2\s*day', re.IGNORECASE),
            'morning': re.compile(r'morning|first\s*half|forenoon', re.IGNORECASE),
            'afternoon': re.compile(r'afternoon|second\s*half|post\s*lunch', re.IGNORECASE),
            'hourly': re.compile(r'(\d{1,2}):?(\d{2})?\s*(?:am|pm)?\s*(?:to|-)\s*(\d{1,2}):?(\d{2})?\s*(?:am|pm)?', re.IGNORECASE),
        }

        # Relative date patterns
        self.relative_patterns = {
            'today': re.compile(r'\btoday\b', re.IGNORECASE),
            'tomorrow': re.compile(r'\btomorrow\b', re.IGNORECASE),
            'next_week': re.compile(r'next\s+week', re.IGNORECASE),
            'this_week': re.compile(r'this\s+week', re.IGNORECASE),
            'rest_of_week': re.compile(r'rest\s+of\s+(?:the\s+)?week', re.IGNORECASE),
            'end_of_month': re.compile(r'end\s+of\s+(?:the\s+)?month', re.IGNORECASE),
        }

        # Weekday patterns
        self.weekday_pattern = re.compile(
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            re.IGNORECASE
        )

    def parse_dates(self, text: str) -> ParsedDateResult:
        """
        Parse dates from text using multiple strategies

        Args:
            text: Text containing date information

        Returns:
            ParsedDateResult with parsed dates and metadata
        """
        # Try parsing strategies in order of specificity
        result = None

        # 1. Try date range parsing
        result = self._parse_date_range(text)
        if result and result.dates:
            return result

        # 2. Try partial leave parsing
        partial_leave = self._parse_partial_leave(text)
        if partial_leave:
            # Get base date for partial leave
            base_dates = self._parse_specific_dates(text)
            if base_dates:
                return ParsedDateResult(
                    dates=base_dates,
                    leave_type=partial_leave.leave_type,
                    confidence=0.9,
                    parsed_fragments=[text]
                )

        # 3. Try relative date parsing
        result = self._parse_relative_dates(text)
        if result and result.dates:
            return result

        # 4. Try specific date parsing (existing patterns + fuzzy)
        dates = self._parse_specific_dates(text)
        if dates:
            return ParsedDateResult(
                dates=dates,
                leave_type=LeaveType.FULL_DAY,
                confidence=0.8,
                parsed_fragments=[text]
            )

        # No dates found
        return ParsedDateResult(dates=[], confidence=0.0)

    def _parse_date_range(self, text: str) -> Optional[ParsedDateResult]:
        """
        Parse date ranges from text

        Args:
            text: Text containing date range

        Returns:
            ParsedDateResult or None
        """
        for pattern in self.range_patterns:
            match = pattern.search(text)
            if match:
                try:
                    date_range = self._extract_range_from_match(match, text)
                    if date_range:
                        dates = date_range.get_dates()
                        if len(dates) <= self.max_range_days:
                            return ParsedDateResult(
                                dates=dates,
                                date_range=date_range,
                                leave_type=LeaveType.FULL_DAY,
                                confidence=0.95,
                                parsed_fragments=[match.group(0)]
                            )
                except Exception as e:
                    logger.debug(f"Failed to parse range: {e}")
                    continue

        return None

    def _extract_range_from_match(self, match: re.Match, text: str) -> Optional[DateRange]:
        """Extract DateRange from regex match"""
        groups = match.groups()

        try:
            # Handle different range formats
            if len(groups) >= 2:
                start_str = groups[0]
                end_str = groups[1]
                month_str = groups[2] if len(groups) > 2 else None

                # Parse start date
                start_date = self._parse_flexible_date(start_str, month_str)
                if not start_date:
                    return None

                # Parse end date
                # If only day number, use same month as start
                if end_str.strip().isdigit():
                    end_date = start_date.replace(day=int(end_str))
                else:
                    end_date = self._parse_flexible_date(end_str, month_str)

                if not end_date:
                    return None

                # Ensure end_date is after start_date
                if end_date < start_date:
                    # Try next month
                    end_date = end_date + relativedelta(months=1)

                days_count = (end_date - start_date).days + 1

                return DateRange(
                    start_date=start_date,
                    end_date=end_date,
                    days_count=days_count,
                    working_days_only=self.working_days_only
                )

        except Exception as e:
            logger.debug(f"Failed to extract range: {e}")
            return None

    def _parse_flexible_date(self, date_str: str, month_str: Optional[str] = None) -> Optional[datetime]:
        """
        Parse date string with flexible format

        Args:
            date_str: Date string
            month_str: Optional month string

        Returns:
            Parsed datetime or None
        """
        try:
            # If just a number, combine with month
            if date_str.strip().isdigit():
                day = int(date_str)
                if month_str:
                    date_str = f"{day} {month_str}"
                else:
                    # Use current month
                    now = datetime.now()
                    date_str = f"{day} {now.strftime('%B')}"

            # Check if year is explicitly specified
            has_explicit_year = bool(re.search(r'\b(20\d{2}|19\d{2})\b', date_str))

            # Use dateparser for flexible parsing
            # If year is explicit, don't use PREFER_DATES_FROM (causes wrong interpretation)
            if has_explicit_year:
                parsed = dateparser.parse(
                    date_str,
                    settings={
                        'RELATIVE_BASE': datetime.now()
                    }
                )
            else:
                parsed = dateparser.parse(
                    date_str,
                    settings={
                        'PREFER_DATES_FROM': 'future',
                        'RELATIVE_BASE': datetime.now()
                    }
                )

            return parsed

        except Exception as e:
            logger.debug(f"Failed to parse date '{date_str}': {e}")
            return None

    def _parse_partial_leave(self, text: str) -> Optional[PartialLeaveInfo]:
        """
        Parse partial leave information

        Args:
            text: Text containing partial leave info

        Returns:
            PartialLeaveInfo or None
        """
        # Check for half day
        if self.partial_patterns['half_day'].search(text):
            period = None
            if self.partial_patterns['morning'].search(text):
                period = 'morning'
            elif self.partial_patterns['afternoon'].search(text):
                period = 'afternoon'

            return PartialLeaveInfo(
                leave_type=LeaveType.HALF_DAY,
                date=datetime.now(),  # Will be replaced with actual date
                period=period
            )

        # Check for hourly
        match = self.partial_patterns['hourly'].search(text)
        if match:
            return PartialLeaveInfo(
                leave_type=LeaveType.HOURLY,
                date=datetime.now(),
                time_range=(match.group(0), match.group(0))  # Simplified
            )

        return None

    def _parse_relative_dates(self, text: str) -> Optional[ParsedDateResult]:
        """
        Parse relative dates (today, tomorrow, next week, etc.)

        Args:
            text: Text containing relative dates

        Returns:
            ParsedDateResult or None
        """
        now = datetime.now()
        dates = []

        # Today
        if self.relative_patterns['today'].search(text):
            dates.append(now)

        # Tomorrow
        if self.relative_patterns['tomorrow'].search(text):
            dates.append(now + timedelta(days=1))

        # Next week (Mon-Fri)
        if self.relative_patterns['next_week'].search(text):
            # Find next Monday
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = now + timedelta(days=days_until_monday)
            dates.extend([next_monday + timedelta(days=i) for i in range(5)])

        # This week
        if self.relative_patterns['this_week'].search(text):
            # Current week Mon-Fri
            days_since_monday = now.weekday()
            monday = now - timedelta(days=days_since_monday)
            dates.extend([monday + timedelta(days=i) for i in range(5)])

        # Rest of week
        if self.relative_patterns['rest_of_week'].search(text):
            # From today to Friday
            days_until_friday = 4 - now.weekday()
            if days_until_friday >= 0:
                dates.extend([now + timedelta(days=i) for i in range(days_until_friday + 1)])

        # End of month
        if self.relative_patterns['end_of_month'].search(text):
            # Last 5 working days of month
            next_month = now.replace(day=1) + relativedelta(months=1)
            last_day = next_month - timedelta(days=1)
            # Go back to find last 5 working days
            for i in range(10):
                check_date = last_day - timedelta(days=i)
                if check_date.weekday() < 5:  # Weekday
                    dates.append(check_date)
                if len(dates) >= 5:
                    break
            dates.reverse()

        if dates:
            return ParsedDateResult(
                dates=sorted(set(dates)),
                leave_type=LeaveType.FULL_DAY,
                confidence=0.9,
                parsed_fragments=[text]
            )

        return None

    def _parse_specific_dates(self, text: str) -> List[datetime]:
        """
        Parse specific dates using existing patterns and fuzzy matching

        Args:
            text: Text containing dates

        Returns:
            List of parsed dates
        """
        dates = []

        # Try parsing date lists (e.g., "2nd, 3rd, and 6th March")
        date_list = self._parse_date_list(text)
        if date_list:
            dates.extend(date_list)
            return sorted(set(dates))  # Return early if we found a list

        # Try extracting single dates like "Feb 12th", "March 5", "12th February"
        single_date_pattern = r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|March|Apr|May|June|July|Aug|Sept?|Oct|Nov|Dec|January|February|April|August|September|October|November|December)\b|\b(Jan|Feb|March|Apr|May|June|July|Aug|Sept?|Oct|Nov|Dec|January|February|April|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\b'

        for match in re.finditer(single_date_pattern, text, re.IGNORECASE):
            # Extract the date portion
            date_str = match.group(0)
            try:
                parsed = dateparser.parse(
                    date_str,
                    settings={
                        'PREFER_DATES_FROM': 'future',
                        'STRICT_PARSING': False,
                        'RELATIVE_BASE': datetime.now()
                    }
                )
                if parsed and parsed not in dates:
                    dates.append(parsed)
            except Exception as e:
                logger.debug(f"Failed to parse single date '{date_str}': {e}")

        # Try weekday patterns
        weekday_match = self.weekday_pattern.search(text)
        if weekday_match:
            weekday_name = weekday_match.group(1).lower()
            date_obj = self._get_next_weekday(weekday_name)
            if date_obj:
                dates.append(date_obj)

        # Fallback: Try fuzzy parsing with dateparser on full text
        if not dates:
            parsed = dateparser.parse(
                text,
                settings={
                    'PREFER_DATES_FROM': 'future',
                    'STRICT_PARSING': False,
                    'RELATIVE_BASE': datetime.now()
                }
            )
            if parsed and parsed not in dates:
                dates.append(parsed)

        return sorted(set(dates))

    def _parse_date_list(self, text: str) -> List[datetime]:
        """
        Parse lists of dates like "2nd, 3rd, and 6th March" or "on 5th and 9th March"
        Handles multiple occurrences of the same month name.

        Args:
            text: Text containing date list

        Returns:
            List of parsed datetime objects
        """
        dates = []

        # Pattern: multiple ordinal numbers followed by month name
        # Examples: "2nd, 3rd, and 6th March", "on 5th and 9th March"
        ordinal_pattern = r'(\d{1,2})(?:st|nd|rd|th)?'
        month_pattern = r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b'

        # Find ALL month occurrences in text
        month_matches = list(re.finditer(month_pattern, text, re.IGNORECASE))
        if not month_matches:
            return dates

        now = datetime.now()
        current_year = now.year

        # Process each month occurrence
        for month_match in month_matches:
            month_str = month_match.group(1)
            month_end_pos = month_match.start()

            # Find the start position for ordinal search
            # Look backwards from this month to the previous month (or start of text)
            month_start_pos = 0
            for prev_match in month_matches:
                if prev_match.start() < month_end_pos:
                    # This is a previous month, start after it
                    month_start_pos = prev_match.end()
                else:
                    break

            # Extract text segment before this month occurrence
            text_segment = text[month_start_pos:month_end_pos]
            ordinal_matches = re.findall(ordinal_pattern, text_segment)

            # Parse each day with this month
            for day_str in ordinal_matches:
                try:
                    # Construct date string like "2 March 2026"
                    date_str = f"{day_str} {month_str} {current_year}"
                    parsed = dateparser.parse(
                        date_str,
                        settings={
                            'PREFER_DATES_FROM': 'future',
                            'STRICT_PARSING': False
                        }
                    )

                    if parsed:
                        # If parsed date is in the past, try next year
                        if parsed < now:
                            date_str = f"{day_str} {month_str} {current_year + 1}"
                            parsed = dateparser.parse(date_str, settings={'STRICT_PARSING': False})

                        if parsed:
                            dates.append(parsed)

                except Exception as e:
                    logger.debug(f"Failed to parse date from '{day_str} {month_str}': {e}")
                    continue

        return dates

    def _get_next_weekday(self, weekday_name: str) -> Optional[datetime]:
        """Get the next occurrence of a weekday"""
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }

        target_day = weekdays.get(weekday_name.lower())
        if target_day is None:
            return None

        now = datetime.now()
        days_ahead = target_day - now.weekday()
        if days_ahead <= 0:  # Target day already passed this week
            days_ahead += 7

        return now + timedelta(days=days_ahead)

    def parse_date_range(self, text: str) -> Optional[DateRange]:
        """
        Public method to parse only date ranges

        Args:
            text: Text containing date range

        Returns:
            DateRange or None
        """
        result = self._parse_date_range(text)
        return result.date_range if result else None
