"""
Analysis orchestrator - main workflow coordinator.
"""

import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from config.config_loader import Config
from parser.ast_parser import ASTParser, ParseResult, syntax_error_to_issue
from parser.version_detector import VersionDetector
from rules.rule_loader import RuleLoader
from rules.rule_executor import RuleExecutor
from core.result_aggregator import ResultAggregator
from core.baseline_manager import BaselineManager
from core.risk_calculator import RiskCalculator
from utils.file_utils import discover_python_files
from reporting.data_models import Issue, Location


class AnalysisOrchestrator:
    """
    Main analysis workflow orchestrator.

    Coordinates:
    - File discovery
    - Version detection
    - Rule loading
    - File analysis
    - Result aggregation
    - Report generation
    """

    def __init__(self, config: Config):
        """
        Initialize analysis orchestrator.

        Args:
            config: Configuration object
        """
        self.config = config
        self.source_version = config.source_version
        self.target_version = config.target_version

        # Initialize components
        self.version_detector = VersionDetector(config.source_path)
        self.rule_loader = RuleLoader()
        self.baseline_manager = None
        if config.baseline_file:
            self.baseline_manager = BaselineManager(config.baseline_file)

        self.aggregator = ResultAggregator(
            baseline_manager=self.baseline_manager,
            source_version=self.source_version,
            target_version=self.target_version,
        )

        # Statistics
        self.files_analyzed = 0
        self.cache_hits = 0
        self.start_time = 0.0
        self.end_time = 0.0

    def analyze_project(self) -> Dict[str, Any]:
        """
        Analyze a Python project.

        Returns:
            Dictionary with analysis results for report generation
        """
        self.start_time = time.time()

        print(f"[INFO] Starting analysis...")
        print(f"[INFO] Project path: {self.config.source_path}")
        print(f"[INFO] Target version: {self.target_version}")

        # Detect source version
        if self.source_version == 'auto':
            print("[INFO] Auto-detecting source version...")
            self.source_version = self.version_detector.detect_version()
            print(f"[INFO] Detected source version: {self.source_version}")
        else:
            print(f"[INFO] Source version: {self.source_version}")

        # Update aggregator with detected version
        self.aggregator.source_version = self.source_version

        # Load rules
        print(f"[INFO] Loading rules for {self.source_version} -> {self.target_version} upgrade...")
        rules = self.rule_loader.load_rules_for_version(
            self.source_version,
            self.target_version
        )
        print(f"[INFO] Loaded {len(rules)} rules")

        # Check for malformed rules
        malformed = self.rule_loader.get_malformed_rules()
        if malformed:
            print(f"[WARN] {len(malformed)} malformed rules were skipped")

        # Create rule executor
        rule_executor = RuleExecutor(
            rules=rules,
            target_version=self.target_version,
            source_version=self.source_version,
        )

        # Discover Python files
        print(f"[INFO] Discovering Python files...")
        python_files = discover_python_files(self.config.source_path)
        print(f"[INFO] Found {len(python_files)} Python files")

        # Analyze files
        print(f"[INFO] Analyzing files...")

        # For now, process sequentially (parallel processing will be added)
        for i, file_path in enumerate(python_files):
            if self.config.verbose:
                print(f"[DEBUG] Processing: {file_path}")

            try:
                file_issues = self._analyze_file(
                    file_path,
                    rule_executor
                )
                self.aggregator.add_file_result(file_path, file_issues)
                self.files_analyzed += 1

                if self.config.verbose:
                    print(f"[DEBUG]   -> {len(file_issues)} issues found")

            except Exception as e:
                print(f"[ERROR] Error analyzing {file_path}: {e}")
                # Create error issue
                error_issue = Issue(
                    id="ANALYSIS_ERROR",
                    file_path=file_path,
                    location=Location(line=0, column=0),
                    severity="critical",
                    category="analysis_error",
                    risk_level="HIGH",
                    message=f"Analysis error: {str(e)}",
                    suggestion="Report this issue to the tool maintainers",
                    code_snippet="",
                    affected_versions=[self.target_version],
                    references=[]
                )
                self.aggregator.add_file_result(file_path, [error_issue])

            # Progress update
            if (i + 1) % 100 == 0:
                print(f"[INFO] Progress: {i + 1}/{len(python_files)} files analyzed")

        self.end_time = time.time()
        duration = self.end_time - self.start_time

        print(f"[INFO] Analysis complete!")
        print(f"[INFO] Total files analyzed: {self.files_analyzed}")
        print(f"[INFO] Total issues found: {len(self.aggregator.all_issues)}")
        print(f"[INFO] Duration: {duration:.2f} seconds")

        # Generate report data
        report_data = self.aggregator.to_report_json(
            project_path=self.config.source_path,
            analysis_duration_seconds=duration,
            cache_hits=self.cache_hits,
            rules_executed=len(rules)
        )

        return report_data

    def _analyze_file(
        self,
        file_path: str,
        rule_executor: RuleExecutor
    ) -> List[Issue]:
        """
        Analyze a single file.

        Args:
            file_path: Path to the file
            rule_executor: Rule executor instance

        Returns:
            List of issues found
        """
        issues = []

        # Parse file
        parser = ASTParser(file_path)
        parse_result = parser.parse()

        # Check for syntax errors
        if parse_result.has_syntax_error:
            syntax_issue = syntax_error_to_issue(
                parse_result.syntax_error,
                file_path,
                self.target_version,
                parser
            )
            issues.append(syntax_issue)
            return issues

        # No syntax errors, execute rules
        try:
            rule_issues = rule_executor.execute_all(
                parse_result.tree,
                file_path,
                parse_result.source_lines
            )
            issues.extend(rule_issues)
        except Exception as e:
            # Error during rule execution
            error_issue = Issue(
                id="RULE_EXECUTION_ERROR",
                file_path=file_path,
                location=Location(line=1, column=0),
                severity="critical",
                category="analysis_error",
                risk_level="HIGH",
                message=f"Error executing rules: {str(e)}",
                suggestion="Report this issue to the tool maintainers",
                code_snippet="",
                affected_versions=[self.target_version],
                references=[]
            )
            issues.append(error_issue)

        return issues

    def generate_baseline(self) -> Dict[str, Any]:
        """
        Generate a baseline from current analysis results.

        Returns:
            Baseline summary
        """
        # Run analysis first
        self.analyze_project()

        # Create baseline from results
        results = {
            file_path: file_result.issues
            for file_path, file_result in self.aggregator.file_results.items()
        }

        baseline = self.aggregator.baseline_manager.create_baseline_from_results(
            results,
            self.source_version,
            self.target_version
        )

        # Save baseline
        baseline_file = self.config.baseline_file or ".bini-baseline.json"
        self.aggregator.baseline_manager.baseline_file = baseline_file
        self.aggregator.baseline_manager.save_baseline(baseline)

        print(f"[INFO] Baseline saved to: {baseline_file}")

        return self.aggregator.baseline_manager.get_baseline_summary()
