"""
Risk calculator for determining migration complexity.
"""

from typing import Dict, List
from reporting.data_models import Issue, RiskLevel, Severity, Category


class RiskCalculator:
    """
    Calculate risk level for compatibility issues.

    Risk is based on multiple factors:
    1. Severity (critical, high, medium, low)
    2. Category (breaking_change, syntax_error, security, deprecation, performance)
    3. Migration complexity (simple rename vs architectural change)

    Risk buckets:
    - HIGH: Score >= 70
    - MEDIUM: Score >= 40
    - LOW: Score < 40
    """

    # Severity scores
    SEVERITY_SCORES = {
        Severity.CRITICAL.value: 100,
        Severity.HIGH.value: 75,
        Severity.MEDIUM.value: 50,
        Severity.LOW.value: 25,
    }

    # Category multipliers
    CATEGORY_MULTIPLIERS = {
        Category.BREAKING_CHANGE.value: 1.5,
        Category.SYNTAX_ERROR.value: 1.3,
        Category.SECURITY.value: 1.4,
        Category.DEPRECATION.value: 1.0,
        Category.PERFORMANCE.value: 0.8,
        Category.FILE_ERROR.value: 1.2,
        Category.ANALYSIS_ERROR.value: 1.1,
    }

    # Risk thresholds
    RISK_THRESHOLDS = {
        RiskLevel.HIGH.value: 70,
        RiskLevel.MEDIUM.value: 40,
        RiskLevel.LOW.value: 0,
    }

    def calculate_risk(self, issue: Issue) -> str:
        """
        Calculate risk level for a single issue.

        Args:
            issue: Issue object

        Returns:
            Risk level string (HIGH/MEDIUM/LOW)
        """
        # Get base score from severity
        severity = issue.severity if issue.severity in self.SEVERITY_SCORES else Severity.MEDIUM.value
        score = self.SEVERITY_SCORES[severity]

        # Apply category multiplier
        category = issue.category if issue.category in self.CATEGORY_MULTIPLIERS else Category.DEPRECATION.value
        multiplier = self.CATEGORY_MULTIPLIERS[category]
        score = score * multiplier

        # Adjust for migration complexity
        complexity_bonus = self._assess_migration_complexity(issue)
        score += complexity_bonus

        # Cap at 100
        score = min(score, 100)

        # Determine risk bucket
        if score >= self.RISK_THRESHOLDS[RiskLevel.HIGH.value]:
            return RiskLevel.HIGH.value
        elif score >= self.RISK_THRESHOLDS[RiskLevel.MEDIUM.value]:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value

    def _assess_migration_complexity(self, issue: Issue) -> float:
        """
        Assess migration complexity based on suggestion text.

        Returns a bonus score to add to the risk:
        - Simple rename: +0
        - Add import: +5
        - Change function call: +10
        - Refactor logic: +20
        - Architectural change: +30

        Args:
            issue: Issue object

        Returns:
            Complexity bonus score
        """
        suggestion = issue.suggestion.lower()

        # Simple rename
        if 'rename' in suggestion:
            return 0

        # Add/import something
        if any(word in suggestion for word in ['import', 'add', 'use ']):
            return 5

        # Change/replace something
        if any(word in suggestion for word in ['change', 'replace', 'update']):
            return 10

        # Refactor/rewrite
        if any(word in suggestion for word in ['refactor', 'rewrite', 'restructure']):
            return 20

        # Architectural/design change
        if any(word in suggestion for word in ['architectural', 'design', 'rethink']):
            return 30

        # Default
        return 5

    def calculate_project_risk(self, issues: List[Issue]) -> str:
        """
        Calculate overall project risk based on all issues.

        Args:
            issues: List of all issues

        Returns:
            Overall risk level (HIGH/MEDIUM/LOW)
        """
        if not issues:
            return RiskLevel.LOW.value

        # Count issues by risk level
        high_count = sum(1 for i in issues if i.risk_level == RiskLevel.HIGH.value)
        medium_count = sum(1 for i in issues if i.risk_level == RiskLevel.MEDIUM.value)
        low_count = sum(1 for i in issues if i.risk_level == RiskLevel.LOW.value)

        # Weighted score
        total = len(issues)
        if total == 0:
            return RiskLevel.LOW.value

        # Calculate weighted risk score
        # HIGH issues count as 3, MEDIUM as 2, LOW as 1
        weighted_score = (high_count * 3 + medium_count * 2 + low_count * 1) / total

        if weighted_score >= 2.0:
            return RiskLevel.HIGH.value
        elif weighted_score >= 1.5:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value

    def get_risk_description(self, risk_level: str) -> str:
        """
        Get human-readable description of a risk level.

        Args:
            risk_level: Risk level string

        Returns:
            Description
        """
        descriptions = {
            RiskLevel.HIGH.value: (
                "High risk - Breaking changes or critical issues that require "
                "significant refactoring. Manual intervention required."
            ),
            RiskLevel.MEDIUM.value: (
                "Medium risk - Deprecated features or API changes that can be "
                "migrated with moderate effort."
            ),
            RiskLevel.LOW.value: (
                "Low risk - Minor deprecations or optimizations that can be "
                "addressed with minimal changes."
            ),
        }
        return descriptions.get(risk_level, "Unknown risk level")

    def categorize_by_risk(self, issues: List[Issue]) -> Dict[str, List[Issue]]:
        """
        Categorize issues by risk level.

        Args:
            issues: List of issues

        Returns:
            Dictionary mapping risk level to list of issues
        """
        result = {
            RiskLevel.HIGH.value: [],
            RiskLevel.MEDIUM.value: [],
            RiskLevel.LOW.value: [],
        }

        for issue in issues:
            result[issue.risk_level].append(issue)

        return result
