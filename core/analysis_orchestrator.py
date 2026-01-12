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

        # Two-phase workflow tracking
        self.analysis_phase = "ast_only"  # "ast_only" or "llm_validation"
        self.phase1_rules = None  # Rules loaded for Phase 1
        self.phase1_llm_config = None  # LLM config for Phase 2
        self.python_files = []  # Discovered files

    def analyze_project(self) -> Dict[str, Any]:
        """
        Analyze a Python project with two-phase workflow.

        Phase 1: AST-only analysis (fast)
        User Approval: Interactive prompt
        Phase 2: LLM validation (if approved)

        Returns:
            Dictionary with analysis results for report generation
        """
        # Phase 1: AST-only analysis
        phase1_report = self._run_phase1_ast_analysis()

        # Interactive approval (only if LLM enabled in config)
        if self.config.llm_enabled and self.phase1_llm_config is not None:
            user_approved = self._prompt_for_llm_validation(phase1_report)
            if user_approved:
                # Phase 2: LLM validation
                final_report = self._run_phase2_llm_validation(phase1_report)
                return final_report

        # Return Phase 1 report if LLM not enabled or user declined
        return phase1_report

    def _run_phase1_ast_analysis(self) -> Dict[str, Any]:
        """
        Phase 1: Run AST-only analysis without LLM.

        Returns:
            Report data from Phase 1 (AST-only)
        """
        from datetime import datetime
        from reporting.report_generator import ReportGenerator

        self.start_time = time.time()
        self.analysis_phase = "ast_only"

        print(f"[INFO] Starting Phase 1: AST Analysis...")
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
        print(f"[INFO] Loaded {len(rules)} rules (across all intermediate versions)")
        self.phase1_rules = rules

        # Check for malformed rules
        malformed = self.rule_loader.get_malformed_rules()
        if malformed:
            print(f"[WARN] {len(malformed)} malformed rules were skipped")

        # Create Ollama config if LLM is enabled (for Phase 2)
        if self.config.llm_enabled:
            try:
                from detection.llm import OllamaConfig
                self.phase1_llm_config = OllamaConfig(
                    host=self.config.llm_host,
                    model=self.config.llm_model,
                    temperature=self.config.llm_temperature,
                    timeout=self.config.llm_timeout,
                    max_tokens=self.config.llm_max_tokens
                )
                print(f"[INFO] LLM available for Phase 2 validation: {self.config.llm_model}")
            except ImportError:
                print("[WARNING] LLM detection modules not available")
                self.phase1_llm_config = None

        # Create rule executor with LLM DISABLED for Phase 1
        rule_executor = RuleExecutor(
            rules=rules,
            target_version=self.target_version,
            source_version=self.source_version,
            enable_llm=False,  # Disable LLM for Phase 1
            llm_config=None
        )

        # Discover Python files
        print(f"[INFO] Discovering Python files...")
        self.python_files = discover_python_files(self.config.source_path)
        print(f"[INFO] Found {len(self.python_files)} Python files")

        # Analyze files
        print(f"[INFO] Analyzing files (AST-only, no LLM)...")

        for i, file_path in enumerate(self.python_files):
            if self.config.verbose:
                print(f"[DEBUG] Processing ({i+1}/{len(self.python_files)}): {file_path}")

            try:
                file_issues = self._analyze_file(file_path, rule_executor)
                # Set analysis_phase for all issues
                for issue in file_issues:
                    issue.analysis_phase = "ast_only"
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
                    references=[],
                    analysis_phase="ast_only"
                )
                self.aggregator.add_file_result(file_path, [error_issue])

            # Progress update
            if (i + 1) % 100 == 0:
                print(f"[INFO] Progress: {i + 1}/{len(self.python_files)} files analyzed")

        self.end_time = time.time()
        duration = self.end_time - self.start_time

        print(f"\n[INFO] ========================================")
        print(f"[INFO]   Phase 1 (AST Analysis) Complete!")
        print(f"[INFO] ========================================")
        print(f"[INFO] Total files analyzed: {self.files_analyzed}")
        print(f"[INFO] Total issues found: {len(self.aggregator.all_issues)}")
        print(f"[INFO] Duration: {duration:.2f} seconds")

        # Generate Phase 1 report data
        report_data = self.aggregator.to_report_json(
            project_path=self.config.source_path,
            analysis_duration_seconds=duration,
            cache_hits=self.cache_hits,
            rules_executed=len(rules)
        )

        # Set phase metadata
        report_data['metadata']['analysis_phase'] = 'ast_only'
        report_data['metadata']['llm_validation_performed'] = False

        # Generate and save Phase 1 HTML report
        report_generator = ReportGenerator(output_dir=self.config.output_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        phase1_filename = f"report_phase1_ast_only_{timestamp}.html"
        phase1_path = os.path.join(self.config.output_path, phase1_filename)

        report_generator.generate_report(
            report_data=report_data,
            output_path=phase1_path
        )

        print(f"[INFO] Phase 1 report saved: {phase1_path}")

        # Generate CSV export
        csv_filename = f"report_phase1_ast_only_{timestamp}.csv"
        csv_path = os.path.join(self.config.output_path, csv_filename)
        report_generator.generate_csv_export(
            report_data=report_data,
            output_path=csv_path
        )

        report_data['report_path'] = phase1_path
        report_data['csv_path'] = csv_path

        return report_data

    def _prompt_for_llm_validation(self, phase1_report: Dict) -> bool:
        """
        Prompt user for approval to run LLM validation.

        Args:
            phase1_report: Phase 1 report data

        Returns:
            True if user approves LLM validation
        """
        summary = phase1_report.get('summary', {})
        total_issues = summary.get('total_issues', 0)
        files_with_issues = summary.get('files_with_issues', 0)

        print(f"\n[INFO] ========================================")
        print(f"[INFO]   Optional: LLM Validation")
        print(f"[INFO] ========================================")
        print(f"[INFO] Phase 1 found:")
        print(f"[INFO]   - Total issues: {total_issues}")
        print(f"[INFO]   - Files with issues: {files_with_issues}")

        # Show breakdown by severity
        by_severity = summary.get('by_severity', {})
        if by_severity:
            print(f"[INFO]   - Critical: {by_severity.get('critical', 0)}, "
                  f"High: {by_severity.get('high', 0)}, "
                  f"Medium: {by_severity.get('medium', 0)}, "
                  f"Low: {by_severity.get('low', 0)}")

        print(f"\n[INFO] LLM validation benefits:")
        print(f"[INFO]   - Reduces false positives by ~7-8%")
        print(f"[INFO]   - Provides detailed reasoning for each issue")
        estimated_time = self._estimate_llm_time(total_issues)
        print(f"[INFO]   - Estimated time: ~{estimated_time:.1f} minutes")

        print(f"\n[INFO] Would you like to run LLM validation? (y/n): ", end="", flush=True)

        try:
            response = input().strip().lower()
            return response in ['y', 'yes']
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] Validation declined.")
            return False

    def _estimate_llm_time(self, total_issues: int) -> float:
        """
        Estimate LLM validation time in minutes.

        Args:
            total_issues: Number of issues to validate

        Returns:
            Estimated time in minutes
        """
        # Rough estimate: ~30 seconds per issue
        seconds_per_issue = 30.0
        total_seconds = total_issues * seconds_per_issue
        return total_seconds / 60.0

    def _run_phase2_llm_validation(self, phase1_report: Dict) -> Dict[str, Any]:
        """
        Phase 2: Run LLM validation on Phase 1 issues.

        Args:
            phase1_report: Phase 1 report data

        Returns:
            Final report data with LLM validation
        """
        from datetime import datetime
        from reporting.report_generator import ReportGenerator

        phase2_start = time.time()
        self.analysis_phase = "llm_validation"

        print(f"\n[INFO] Starting Phase 2: LLM Validation...")
        print(f"[INFO] Processing {len(self.aggregator.all_issues)} issues across {len(self.aggregator.file_results)} files...")

        # Create rule executor with LLM enabled for validation
        rule_executor = RuleExecutor(
            rules=self.phase1_rules,
            target_version=self.target_version,
            source_version=self.source_version,
            enable_llm=True,
            llm_config=self.phase1_llm_config
        )

        # Prepare file trees and source lines for batch validation
        file_trees = {}
        file_source_lines = {}

        print(f"[INFO] Preparing file data for batch processing...")
        for file_path in self.python_files:
            try:
                parser = ASTParser(file_path, source_version=self.source_version)
                parse_result = parser.parse()
                if not parse_result.has_syntax_error:
                    file_trees[file_path] = parse_result.tree
                    file_source_lines[file_path] = parse_result.source_lines
            except Exception as e:
                print(f"[WARNING] Could not parse {file_path} for LLM validation: {e}")

        # Collect all Phase 1 issues
        all_issues = list(self.aggregator.all_issues)

        # Validate issues in batch
        print(f"[INFO] Validating issues with LLM...")
        validated_issues = rule_executor.validate_issues_batch(
            issues=all_issues,
            file_trees=file_trees,
            file_source_lines=file_source_lines
        )

        # Update aggregator with validated issues
        # Group validated issues by file
        validated_by_file = {}
        for issue in validated_issues:
            if issue.file_path not in validated_by_file:
                validated_by_file[issue.file_path] = []
            validated_by_file[issue.file_path].append(issue)

        # Clear old results and add validated ones
        self.aggregator.file_results = {}
        self.aggregator.all_issues = []

        for file_path, issues in validated_by_file.items():
            self.aggregator.add_file_result(file_path, issues)

        phase2_end = time.time()
        phase2_duration = phase2_end - phase2_start
        total_duration = phase2_end - self.start_time

        # Calculate LLM validation statistics
        llm_validated_count = sum(1 for issue in validated_issues if issue.llm_validated)
        llm_confirmed_count = sum(1 for issue in validated_issues if issue.llm_validated and issue.llm_confirmed)
        llm_rejected_count = sum(1 for issue in validated_issues if issue.llm_validated and not issue.llm_confirmed)

        print(f"\n[INFO] ========================================")
        print(f"[INFO]   Phase 2 (LLM Validation) Complete!")
        print(f"[INFO] ========================================")
        print(f"[INFO] LLM Validation Results:")
        print(f"[INFO]   - Issues validated: {llm_validated_count}")
        print(f"[INFO]   - Confirmed: {llm_confirmed_count} ({llm_confirmed_count*100/max(llm_validated_count,1):.1f}%)")
        print(f"[INFO]   - Rejected as false positives: {llm_rejected_count} ({llm_rejected_count*100/max(llm_validated_count,1):.1f}%)")
        print(f"[INFO] Phase 2 duration: {phase2_duration:.2f} seconds")
        print(f"[INFO] Total duration: {total_duration:.2f} seconds")

        # Generate final report data
        report_data = self.aggregator.to_report_json(
            project_path=self.config.source_path,
            analysis_duration_seconds=total_duration,
            cache_hits=self.cache_hits,
            rules_executed=len(self.phase1_rules)
        )

        # Set phase metadata
        report_data['metadata']['analysis_phase'] = 'complete'
        report_data['metadata']['llm_validation_performed'] = True
        report_data['metadata']['llm_validation_stats'] = {
            'total_validated': llm_validated_count,
            'confirmed': llm_confirmed_count,
            'rejected': llm_rejected_count,
            'phase2_duration_seconds': phase2_duration
        }

        # Generate and save final HTML report
        report_generator = ReportGenerator(output_dir=self.config.output_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        final_filename = f"report_final_llm_validated_{timestamp}.html"
        final_path = os.path.join(self.config.output_path, final_filename)

        report_generator.generate_report(
            report_data=report_data,
            output_path=final_path
        )

        print(f"[INFO] Final report saved: {final_path}")

        # Generate CSV export
        csv_filename = f"report_final_llm_validated_{timestamp}.csv"
        csv_path = os.path.join(self.config.output_path, csv_filename)
        report_generator.generate_csv_export(
            report_data=report_data,
            output_path=csv_path
        )

        report_data['report_path'] = final_path
        report_data['csv_path'] = csv_path

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

        # Parse file with source version syntax
        parser = ASTParser(file_path, source_version=self.source_version)
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
