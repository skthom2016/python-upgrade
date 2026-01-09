"""
Baseline manager for ignoring known issues.
"""

import json
import os
from typing import Dict, List, Set, Optional
from datetime import datetime

from reporting.data_models import Baseline, Issue


class BaselineManager:
    """
    Manage baseline for ignoring known issues.

    Baseline is per-file, per-issue-ID.
    """

    def __init__(self, baseline_file: Optional[str] = None):
        """
        Initialize baseline manager.

        Args:
            baseline_file: Path to baseline JSON file (optional)
        """
        self.baseline_file = baseline_file
        self.baseline: Optional[Baseline] = None

        if baseline_file and os.path.exists(baseline_file):
            self.load_baseline()

    def load_baseline(self) -> Baseline:
        """
        Load baseline from file.

        Returns:
            Baseline object
        """
        if not self.baseline_file or not os.path.exists(self.baseline_file):
            self.baseline = Baseline()
            return self.baseline

        try:
            with open(self.baseline_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.baseline = Baseline.from_dict(data)
            return self.baseline
        except Exception as e:
            print(f"Warning: Failed to load baseline: {e}")
            self.baseline = Baseline()
            return self.baseline

    def save_baseline(self, baseline: Optional[Baseline] = None):
        """
        Save baseline to file.

        Args:
            baseline: Baseline object to save (uses self.baseline if None)
        """
        if baseline:
            self.baseline = baseline

        if not self.baseline_file:
            raise ValueError("No baseline file specified")

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.baseline_file), exist_ok=True)

        # Update timestamp
        self.baseline.updated_at = datetime.now().isoformat()
        if not self.baseline.created_at:
            self.baseline.created_at = self.baseline.updated_at

        try:
            with open(self.baseline_file, 'w', encoding='utf-8') as f:
                json.dump(self.baseline.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save baseline: {e}")

    def is_ignored(self, file_path: str, issue_id: str) -> bool:
        """
        Check if an issue is ignored in the baseline.

        Args:
            file_path: Path to the file
            issue_id: ID of the issue

        Returns:
            True if the issue is ignored
        """
        if not self.baseline:
            return False

        return self.baseline.is_ignored(file_path, issue_id)

    def filter_issues(self, file_path: str, issues: List[Issue]) -> List[Issue]:
        """
        Filter out ignored issues from a file.

        Args:
            file_path: Path to the file
            issues: List of issues

        Returns:
            List of non-ignored issues
        """
        if not self.baseline:
            return issues

        return [
            issue for issue in issues
            if not self.baseline.is_ignored(file_path, issue.id)
        ]

    def add_to_baseline(self, file_path: str, issue_id: str):
        """
        Add an issue to the baseline.

        Args:
            file_path: Path to the file
            issue_id: ID of the issue to ignore
        """
        if not self.baseline:
            self.baseline = Baseline()

        self.baseline.add_ignore(file_path, issue_id)

    def create_baseline_from_results(
        self,
        results: Dict[str, List[Issue]],
        source_version: str,
        target_version: str
    ) -> Baseline:
        """
        Create a baseline from analysis results (all current issues).

        Args:
            results: Dictionary mapping file paths to issues
            source_version: Source Python version
            target_version: Target Python version

        Returns:
            Baseline object
        """
        baseline = Baseline(
            source_version=source_version,
            target_version=target_version,
            created_at=datetime.now().isoformat(),
        )

        for file_path, issues in results.items():
            for issue in issues:
                baseline.add_ignore(file_path, issue.id)

        return baseline

    def update_baseline(
        self,
        new_results: Dict[str, List[Issue]],
        source_version: str,
        target_version: str
    ) -> Baseline:
        """
        Update baseline with new results (adds new issues only).

        Args:
            new_results: New analysis results
            source_version: Source Python version
            target_version: Target Python version

        Returns:
            Updated baseline
        """
        if not self.baseline:
            return self.create_baseline_from_results(
                new_results, source_version, target_version
            )

        # Update version info
        self.baseline.source_version = source_version
        self.baseline.target_version = target_version
        self.baseline.updated_at = datetime.now().isoformat()

        # Add new issues to baseline
        for file_path, issues in new_results.items():
            for issue in issues:
                # Only add if not already in baseline
                if not self.baseline.is_ignored(file_path, issue.id):
                    self.baseline.add_ignore(file_path, issue.id)

        return self.baseline

    def get_baseline_summary(self) -> Dict[str, int]:
        """
        Get summary statistics for the baseline.

        Returns:
            Dictionary with summary stats
        """
        if not self.baseline:
            return {
                'total_entries': 0,
                'total_files': 0,
                'total_issues': 0,
            }

        total_entries = sum(len(issues) for issues in self.baseline.entries.values())
        total_files = len(self.baseline.entries)

        return {
            'total_entries': total_entries,
            'total_files': total_files,
            'total_issues': total_entries,
        }
