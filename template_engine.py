"""
Template Engine for Slack Leave Bot
Loads and renders YAML templates with variable substitution
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from string import Formatter

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Renders message templates with variable substitution"""

    def __init__(self, template_path: str):
        """
        Initialize template engine

        Args:
            template_path: Path to templates.yaml file
        """
        self.template_path = template_path
        self.templates: Dict[str, Any] = {}
        self.date_formats: Dict[str, str] = {}
        self._load_templates()

    def _load_templates(self):
        """Load templates from YAML file"""
        try:
            template_file = Path(self.template_path)
            if not template_file.exists():
                logger.error(f"Template file not found: {self.template_path}")
                return

            with open(template_file, 'r') as f:
                data = yaml.safe_load(f)

            self.templates = data.get('templates', {})
            self.date_formats = data.get('date_formats', {})

            logger.info(f"Loaded {len(self.templates)} template categories")

        except Exception as e:
            logger.error(f"Failed to load templates: {e}", exc_info=True)

    def reload(self):
        """Reload templates from file"""
        logger.info("Reloading templates")
        self._load_templates()

    def render(
        self,
        template_key: str,
        context: Dict[str, Any],
        language: str = 'en'
    ) -> Optional[str]:
        """
        Render a template with context variables

        Args:
            template_key: Dot-separated template key (e.g., "thread_reply.leave_found")
            context: Dictionary of variables to substitute
            language: Language code (default: 'en')

        Returns:
            Rendered template string or None if template not found
        """
        try:
            # Navigate to template using dot notation
            template_parts = template_key.split('.')
            template_obj = self.templates

            for part in template_parts:
                if isinstance(template_obj, dict) and part in template_obj:
                    template_obj = template_obj[part]
                else:
                    logger.warning(f"Template not found: {template_key}")
                    return None

            # Get language-specific template
            if isinstance(template_obj, dict) and language in template_obj:
                template_str = template_obj[language]
            else:
                logger.warning(f"Language '{language}' not found for template: {template_key}")
                return None

            # Enhance context with formatted dates if needed
            enhanced_context = self._enhance_context(context)

            # Render template
            rendered = template_str.format(**enhanced_context)
            return rendered

        except KeyError as e:
            logger.error(f"Missing variable in template context: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to render template '{template_key}': {e}", exc_info=True)
            return None

    def _enhance_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance context with additional variables and formatting

        Args:
            context: Original context

        Returns:
            Enhanced context with formatted dates and other derived values
        """
        enhanced = context.copy()

        # Format leave_dates if present
        if 'leave_dates' in context:
            leave_dates = context['leave_dates']
            if isinstance(leave_dates, list) and leave_dates:
                enhanced['leave_dates_formatted'] = self._format_dates(leave_dates)

        # Add current timestamp
        enhanced['current_timestamp'] = datetime.now().isoformat()

        return enhanced

    def _format_dates(self, dates: list) -> str:
        """
        Format list of dates for display

        Args:
            dates: List of date objects or ISO strings

        Returns:
            Formatted date string
        """
        try:
            # Convert to datetime objects if needed
            date_objects = []
            for date_obj in dates:
                if isinstance(date_obj, str):
                    date_objects.append(datetime.fromisoformat(date_obj.replace('Z', '+00:00')))
                elif isinstance(date_obj, datetime):
                    date_objects.append(date_obj)

            if not date_objects:
                return ""

            # Sort dates
            date_objects.sort()

            # Get format string
            date_format = self.date_formats.get('date_format', '%b %d, %Y')

            # Format based on count
            if len(date_objects) == 1:
                return date_objects[0].strftime(date_format)
            elif len(date_objects) == 2:
                return f"{date_objects[0].strftime(date_format)} and {date_objects[1].strftime(date_format)}"
            elif self._is_continuous_range(date_objects):
                # Format as range
                return f"{date_objects[0].strftime(date_format)} to {date_objects[-1].strftime(date_format)}"
            else:
                # Format as list - show all dates
                formatted = [d.strftime(date_format) for d in date_objects]
                if len(formatted) > 1:
                    # Join with commas and "and" before the last one
                    return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"
                else:
                    return formatted[0]

        except Exception as e:
            logger.error(f"Failed to format dates: {e}")
            return str(dates)

    def _is_continuous_range(self, dates: list) -> bool:
        """
        Check if dates form a continuous range

        Args:
            dates: Sorted list of datetime objects

        Returns:
            True if dates are continuous
        """
        if len(dates) < 3:
            return False

        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i-1]).days
            if diff > 1:
                return False

        return True

    def get_template_vars(self, template_key: str, language: str = 'en') -> list:
        """
        Get list of variables used in a template

        Args:
            template_key: Dot-separated template key
            language: Language code

        Returns:
            List of variable names
        """
        try:
            # Navigate to template
            template_parts = template_key.split('.')
            template_obj = self.templates

            for part in template_parts:
                if isinstance(template_obj, dict) and part in template_obj:
                    template_obj = template_obj[part]
                else:
                    return []

            # Get language-specific template
            if isinstance(template_obj, dict) and language in template_obj:
                template_str = template_obj[language]
            else:
                return []

            # Extract variable names
            formatter = Formatter()
            field_names = [field_name for _, field_name, _, _ in formatter.parse(template_str) if field_name]

            return field_names

        except Exception as e:
            logger.error(f"Failed to get template vars: {e}")
            return []


# Global template engine instance
_template_engine: Optional[TemplateEngine] = None


def get_template_engine() -> Optional[TemplateEngine]:
    """Get global template engine instance"""
    return _template_engine


def set_template_engine(engine: TemplateEngine):
    """Set global template engine instance"""
    global _template_engine
    _template_engine = engine


def render_template(template_key: str, context: Dict[str, Any], language: str = 'en') -> Optional[str]:
    """
    Convenience function to render template using global engine

    Args:
        template_key: Template key
        context: Template context
        language: Language code

    Returns:
        Rendered template or None
    """
    engine = get_template_engine()
    if engine:
        return engine.render(template_key, context, language)
    else:
        logger.warning("Template engine not initialized")
        return None
