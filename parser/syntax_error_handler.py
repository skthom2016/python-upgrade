"""
Syntax error handler for Python source code.
"""

import re
from typing import Optional, Tuple
from packaging import version

from reporting.data_models import Issue, Location, Severity, Category, RiskLevel


class SyntaxErrorHandler:
    """
    Handle syntax errors in Python source code.

    Responsibilities:
    - Determine if syntax error is version-specific
    - Generate helpful error messages
    - Create Issue objects for syntax errors
    """

    def __init__(self, target_version: str):
        """
        Initialize syntax error handler.

        Args:
            target_version: Target Python version (e.g., "3.12")
        """
        self.target_version = target_version

    def is_future_compatible(self, error_text: str) -> Tuple[bool, str]:
        """
        Check if syntax error is valid in target Python version.

        Args:
            error_text: Error message text

        Returns:
            Tuple of (is_compatible, required_version)
        """
        error_lower = error_text.lower()

        # Walrus operator := (Python 3.8+)
        if ":=" in error_lower or "walrus" in error_lower:
            return version.parse(self.target_version) >= version.parse("3.8"), "3.8"

        # Match/Case statement (Python 3.10+)
        if "match" in error_lower and "case" in error_lower:
            return version.parse(self.target_version) >= version.parse("3.10"), "3.10"

        # Exception groups (Python 3.11+)
        if "exceptiongroup" in error_lower or "exception*" in error_lower:
            return version.parse(self.target_version) >= version.parse("3.11"), "3.11"

        # Type parameter syntax (Python 3.12+)
        if "type " in error_lower and "[" in error_lower:
            return version.parse(self.target_version) >= version.parse("3.12"), "3.12"

        # Default: not compatible
        return False, ""

    def explain_error(self, error: Exception) -> str:
        """
        Generate helpful explanation for syntax error.

        Args:
            error: The syntax error

        Returns:
            Helpful explanation message
        """
        error_text = str(error)
        error_lower = error_text.lower()

        # Walrus operator
        if ":=" in error_lower or "walrus" in error_lower:
            return (
                "The walrus operator (:=) was introduced in Python 3.8. "
                "In earlier versions, this syntax is not allowed. "
                "Rewrite the code to avoid using := or upgrade to Python 3.8+."
            )

        # Match/Case
        if "match" in error_lower and "case" in error_lower:
            return (
                "Pattern matching with match/case was introduced in Python 3.10. "
                "In earlier versions, 'match' and 'case' are not keywords. "
                "Use if/elif/else chains instead or upgrade to Python 3.10+."
            )

        # Exception groups
        if "exceptiongroup" in error_lower or "exception*" in error_lower:
            return (
                "Exception groups were introduced in Python 3.11. "
                "Use regular exception handling with try/except instead "
                "or upgrade to Python 3.11+."
            )

        # Generic error
        return f"Syntax error: {error_text}"

    def get_severity(self, error_text: str) -> str:
        """
        Determine severity of syntax error.

        Args:
            error_text: Error message text

        Returns:
            Severity level
        """
        is_compatible, _ = self.is_future_compatible(error_text)

        if is_compatible:
            # Will work after upgrade
            return Severity.MEDIUM.value
        else:
            # Must be fixed manually
            return Severity.CRITICAL.value

    def get_risk_level(self, error_text: str) -> str:
        """
        Determine risk level of syntax error.

        Args:
            error_text: Error message text

        Returns:
            Risk level (HIGH/MEDIUM/LOW)
        """
        is_compatible, _ = self.is_future_compatible(error_text)

        if is_compatible:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.HIGH.value

    def create_issue(
        self,
        error: Exception,
        file_path: str,
        code_snippet: str = ""
    ) -> Issue:
        """
        Create Issue object from syntax error.

        Args:
            error: The syntax error
            file_path: Path to the file
            code_snippet: Code snippet showing the error

        Returns:
            Issue object
        """
        error_text = str(error)

        # Determine compatibility
        is_compatible, required_version = self.is_future_compatible(error_text)

        # Set severity and risk
        severity = self.get_severity(error_text)
        risk_level = self.get_risk_level(error_text)

        # Generate message
        if is_compatible:
            message = (
                f"Syntax error in current version, but valid in Python {required_version}+. "
                f"This code will work after upgrading to {self.target_version}."
            )
        else:
            message = (
                f"Syntax error that will persist in Python {self.target_version}. "
                f"This code must be fixed manually before upgrading."
            )

        # Generate suggestion
        suggestion = self.explain_error(error)

        # Extract location from error
        line = 1
        column = 0

        if hasattr(error, 'lineno'):
            line = error.lineno or 1
        if hasattr(error, 'offset'):
            column = error.offset or 0

        # Create references
        references = []
        if "walrus" in error_text.lower():
            references.append("https://docs.python.org/3/whatsnew/3.8.html#pep-572-assignment-expressions")
        elif "match" in error_text.lower():
            references.append("https://docs.python.org/3/whatsnew/3.10.html#pep-634-structural-pattern-matching")
        elif "exception" in error_text.lower():
            references.append("https://docs.python.org/3/whatsnew/3.11.html#pep-654-exception-groups-and-except")

        return Issue(
            id=f"SYNTAX_{line}_{column}",
            file_path=file_path,
            location=Location(line=line, column=column),
            severity=severity,
            category=Category.SYNTAX_ERROR.value,
            risk_level=risk_level,
            message=message,
            suggestion=suggestion,
            code_snippet=code_snippet,
            affected_versions=[self.target_version],
            references=references
        )
