"""
Result aggregator for collecting and summarizing analysis results.
"""

import os
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
from datetime import datetime

from reporting.data_models import Issue, FileResult, AnalysisSummary, AnalysisResult, AnalysisMetadata, TimelineEntry
from core.risk_calculator import RiskCalculator
from core.baseline_manager import BaselineManager


class ResultAggregator:
    """
    Aggregate results from parallel workers.

    Responsibilities:
    - Collect results from multiple workers
    - Filter by baseline
    - Calculate statistics
    - Generate summary
    - Prepare data for report generation
    """

    def __init__(
        self,
        baseline_manager: Optional[BaselineManager] = None,
        source_version: str = "3.6",
        target_version: str = "3.12"
    ):
        """
        Initialize result aggregator.

        Args:
            baseline_manager: Optional baseline manager for filtering
            source_version: Source Python version
            target_version: Target Python version
        """
        self.baseline_manager = baseline_manager
        self.source_version = source_version
        self.target_version = target_version
        self.risk_calculator = RiskCalculator()

        # Storage
        self.file_results: Dict[str, FileResult] = {}
        self.all_issues: List[Issue] = []

    def add_file_result(self, file_path: str, issues: List[Issue], analysis_time_ms: float = 0.0):
        """
        Add analysis result for a file.

        Args:
            file_path: Path to the file
            issues: List of issues found
            analysis_time_ms: Time taken to analyze
        """
        # Get relative path
        relative_path = os.path.relpath(file_path)

        # Calculate risk for each issue
        for issue in issues:
            if not issue.risk_level:
                issue.risk_level = self.risk_calculator.calculate_risk(issue)

        # Filter by baseline
        if self.baseline_manager:
            issues = self.baseline_manager.filter_issues(file_path, issues)

        # Create file result
        file_result = FileResult(
            path=file_path,
            relative_path=relative_path,
            issues=issues,
            total_issues=len(issues),
            analysis_time_ms=analysis_time_ms,
        )

        self.file_results[file_path] = file_result
        self.all_issues.extend(issues)

    def get_summary(self) -> AnalysisSummary:
        """
        Get analysis summary.

        Returns:
            AnalysisSummary object
        """
        total_files = len(self.file_results)
        total_issues = len(self.all_issues)
        files_with_issues = sum(1 for r in self.file_results.values() if r.total_issues > 0)
        files_without_issues = total_files - files_with_issues

        # Count by risk
        by_risk = self._count_issues_by_field('risk_level')

        # Count by severity
        by_severity = self._count_issues_by_field('severity')

        # Count by category
        by_category = self._count_issues_by_field('category')

        # Get top problematic files
        top_files = self._get_top_files(10)

        return AnalysisSummary(
            total_files=total_files,
            total_issues=total_issues,
            files_with_issues=files_with_issues,
            files_without_issues=files_without_issues,
            by_risk=by_risk,
            by_severity=by_severity,
            by_category=by_category,
            top_files=top_files,
        )

    def _count_issues_by_field(self, field: str) -> Dict[str, int]:
        """Count issues by a specific field."""
        counter = Counter()
        for issue in self.all_issues:
            value = getattr(issue, field, 'unknown')
            counter[value] += 1
        return dict(counter)

    def _get_top_files(self, count: int) -> List[Dict[str, Any]]:
        """Get files with the most issues."""
        sorted_files = sorted(
            self.file_results.values(),
            key=lambda r: r.total_issues,
            reverse=True
        )

        return [
            {
                'path': f.relative_path,
                'total_issues': f.total_issues,
                'by_risk': f.by_risk,
            }
            for f in sorted_files[:count]
            if f.total_issues > 0
        ]

    def to_report_json(
        self,
        project_path: str,
        analysis_duration_seconds: float = 0.0,
        cache_hits: int = 0,
        rules_executed: int = 0
    ) -> Dict[str, Any]:
        """
        Generate JSON data for report generation.

        Args:
            project_path: Path to analyzed project
            analysis_duration_seconds: Total analysis time
            cache_hits: Number of cache hits
            rules_executed: Number of rules executed

        Returns:
            Dictionary for JSON serialization
        """
        # Create metadata
        metadata = AnalysisMetadata(
            source_version=self.source_version,
            target_version=self.target_version,
            project_path=project_path,
            generated_at=datetime.now().isoformat(),
            analyzer_version="1.0.0",
        )

        # Get summary
        summary = self.get_summary()
        summary.analysis_duration_seconds = analysis_duration_seconds
        summary.rules_executed = rules_executed
        summary.cache_hits = cache_hits

        # Create timeline entry
        timeline_entry = TimelineEntry(
            timestamp=metadata.generated_at,
            total_issues=summary.total_issues,
            total_files=summary.total_files,
            source_version=self.source_version,
            target_version=self.target_version,
        )

        # Create analysis result
        result = AnalysisResult(
            metadata=metadata,
            summary=summary,
            files=list(self.file_results.values()),
            timeline=[timeline_entry],
        )

        return result.to_dict()

    def get_file_result(self, file_path: str) -> Optional[FileResult]:
        """
        Get result for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            FileResult or None
        """
        return self.file_results.get(file_path)

    def get_all_file_results(self) -> List[FileResult]:
        """Get all file results."""
        return list(self.file_results.values())

    def merge_results(self, other: 'ResultAggregator'):
        """
        Merge results from another aggregator.

        Args:
            other: Another ResultAggregator
        """
        for file_path, file_result in other.file_results.items():
            if file_path not in self.file_results:
                self.file_results[file_path] = file_result
            else:
                # Merge issues
                existing = self.file_results[file_path]
                existing.issues.extend(file_result.issues)
                existing.total_issues = len(existing.issues)

        self.all_issues.extend(other.all_issues)

    def calculate_statistics(self) -> Dict[str, Any]:
        """
        Calculate detailed statistics.

        Returns:
            Dictionary with statistics
        """
        if not self.all_issues:
            return {
                'total_issues': 0,
                'average_issues_per_file': 0.0,
                'max_issues_in_file': 0,
                'most_problematic_file': None,
            }

        total_issues = len(self.all_issues)
        total_files = len(self.file_results)

        # Find file with most issues
        max_file = max(
            self.file_results.values(),
            key=lambda r: r.total_issues
        )

        return {
            'total_issues': total_issues,
            'total_files': total_files,
            'average_issues_per_file': total_issues / total_files if total_files > 0 else 0.0,
            'max_issues_in_file': max_file.total_issues,
            'most_problematic_file': {
                'path': max_file.relative_path,
                'issue_count': max_file.total_issues,
            },
        }
