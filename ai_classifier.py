"""
AI-Powered Leave Message Classifier
Uses Anthropic Claude API for intelligent message understanding
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class LeaveClassification:
    """Result of AI classification"""
    is_leave_message: bool
    leave_type: str  # "leave", "wfh", "sick", "vacation", "emergency", "unknown"
    confidence: float  # 0.0 to 1.0
    dates_mentioned: List[str]  # Extracted date strings
    urgency: str  # "low", "medium", "high"
    reason: Optional[str] = None  # e.g., "fever", "doctor appointment"
    already_applied: bool = False  # Did they mention Zoho was applied?


class AILeaveClassifier:
    """AI-powered leave message classifier using Claude API"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.enabled = bool(self.api_key)

        if self.enabled:
            try:
                self.client = Anthropic(api_key=self.api_key)
                logger.info("✅ AI Classifier initialized with Claude API")
            except Exception as e:
                logger.error(f"Failed to initialize Claude API: {e}")
                self.enabled = False
        else:
            logger.warning("⚠️  AI Classifier disabled (ANTHROPIC_API_KEY not set)")

    def classify_message(self, text: str, user_name: str = "User") -> Optional[LeaveClassification]:
        """
        Classify a Slack message using Claude AI

        Args:
            text: Message text
            user_name: User's name for context

        Returns:
            LeaveClassification object or None if failed
        """
        if not self.enabled:
            logger.debug("AI classifier disabled, returning None")
            return None

        try:
            prompt = self._build_classification_prompt(text, user_name)

            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse Claude's response
            result_text = response.content[0].text
            return self._parse_classification(result_text)

        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return None

    def _build_classification_prompt(self, text: str, user_name: str) -> str:
        """Build prompt for Claude API"""
        return f"""Analyze this Slack message and determine if it's about taking leave, WFH, or being absent.

Message from {user_name}:
"{text}"

Respond ONLY with valid JSON in this exact format:
{{
  "is_leave_message": true/false,
  "leave_type": "leave|wfh|sick|vacation|emergency|unknown",
  "confidence": 0.0-1.0,
  "dates_mentioned": ["list of date strings found"],
  "urgency": "low|medium|high",
  "reason": "optional reason like fever, doctor, etc",
  "already_applied": true/false (if they mentioned applying on Zoho/HR system)
}}

Guidelines:
- is_leave_message: true if about absence, leave, WFH, sick, vacation
- leave_type: classify the type (wfh includes "work remotely", "working from home")
- confidence: how sure you are (0.8+ for clear messages)
- dates_mentioned: extract ALL date references (today, tomorrow, specific dates, ranges)
- urgency: high for same-day/emergency, medium for short notice, low for planned
- reason: extract WHY they're taking leave (fever, doctor, family, etc)
- already_applied: true if they mention "applied on Zoho", "HR approved", "already applied"

Examples of leave messages:
- "I'm on leave tomorrow" → leave, medium urgency
- "WFH today, doctor appointment" → wfh, high urgency, reason: doctor
- "Won't be able to join today, fever" → sick, high urgency, reason: fever
- "Taking leave from 15th to 20th, already applied on Zoho" → leave, low urgency, already_applied: true

Return ONLY the JSON, no other text."""

    def _parse_classification(self, response_text: str) -> LeaveClassification:
        """Parse Claude's JSON response into LeaveClassification"""
        import json

        try:
            # Extract JSON from response (handle markdown code blocks)
            response_text = response_text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text)

            return LeaveClassification(
                is_leave_message=data.get("is_leave_message", False),
                leave_type=data.get("leave_type", "unknown"),
                confidence=float(data.get("confidence", 0.0)),
                dates_mentioned=data.get("dates_mentioned", []),
                urgency=data.get("urgency", "medium"),
                reason=data.get("reason"),
                already_applied=data.get("already_applied", False)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response was: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse classification: {e}")
            return None

    def extract_dates_with_ai(self, text: str) -> List[str]:
        """
        Use Claude to extract dates from text

        Args:
            text: Message text

        Returns:
            List of date strings in ISO format (YYYY-MM-DD)
        """
        if not self.enabled:
            return []

        try:
            prompt = f"""Extract ALL date references from this text and convert them to ISO format (YYYY-MM-DD).
Today's date is {datetime.now().strftime("%Y-%m-%d")}.

Text: "{text}"

Return ONLY a JSON array of dates, no other text:
["YYYY-MM-DD", "YYYY-MM-DD", ...]

Examples:
- "tomorrow" → ["{(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime('%Y-%m-%d')}"]
- "15th to 20th Feb 2026" → ["2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20"]
- "next Monday and Tuesday" → calculate actual dates
- "rest of week" → all remaining working days this week

Return ONLY the JSON array."""

            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            import json
            result_text = response.content[0].text.strip()

            # Extract JSON array
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            dates = json.loads(result_text)
            logger.info(f"AI extracted {len(dates)} dates: {dates}")
            return dates

        except Exception as e:
            logger.error(f"AI date extraction failed: {e}")
            return []


# Singleton instance
_classifier_instance = None


def get_ai_classifier() -> AILeaveClassifier:
    """Get singleton instance of AI classifier"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = AILeaveClassifier()
    return _classifier_instance
