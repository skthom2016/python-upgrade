#!/usr/bin/env python
"""
SecurePythonUpgradeProject (Bini) - Python Upgrade Compatibility Analyzer

A Windows-native, offline static analysis tool for detecting Python version
compatibility issues when upgrading between Python versions.

Usage:
    bini-analyzer analyze <project_path> --target 3.12
    bini-analyzer baseline generate <project_path> --target 3.12
    bini-analyzer cache clear <project_path>
"""

import argparse
import sys
import os
import signal
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from config.config_loader import ConfigLoader
from core.analysis_orchestrator import AnalysisOrchestrator
from reporting.report_generator import ReportGenerator
from utils.logger import setup_logger


class BiniAnalyzer:
    """Main CLI application for Bini Python upgrade analyzer."""

    def __init__(self):
        """Initialize CLI application."""
        self.logger = setup_logger()
        self.config = None
        self.orchestrator = None

    def run(self, args):
        """
        Run the analyzer with given arguments.

        Args:
            args: Parsed command-line arguments
        """
        try:
            # Load configuration
            config_loader = ConfigLoader(args.config)
            self.config = config_loader.load_config()

            # Update config from command-line arguments
            self.config = config_loader.update_from_args(self.config, args)

            # Validate configuration
            is_valid, errors = config_loader.validate_config(self.config)
            if not is_valid:
                self.logger.error("Configuration errors:")
                for error in errors:
                    self.logger.error(f"  - {error}")
                return 1

            # Setup signal handlers for graceful interrupt
            signal.signal(signal.SIGINT, self._handle_interrupt)

            # Execute command
            if args.command == 'analyze':
                return self._cmd_analyze()
            elif args.command == 'baseline':
                if args.baseline_action == 'generate':
                    return self._cmd_baseline_generate()
                elif args.baseline_action == 'update':
                    return self._cmd_baseline_update()
            elif args.command == 'cache':
                if args.cache_action == 'clear':
                    return self._cmd_cache_clear()
            else:
                self.logger.error(f"Unknown command: {args.command}")
                return 1

        except Exception as e:
            self.logger.error(f"Error: {e}")
            if self.config and self.config.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def _cmd_analyze(self) -> int:
        """Execute analyze command."""
        # Create output directory
        os.makedirs(self.config.output_path, exist_ok=True)

        # Create orchestrator
        self.orchestrator = AnalysisOrchestrator(self.config)

        # Run analysis
        report_data = self.orchestrator.analyze_project()

        # Generate report
        report_generator = ReportGenerator(
            output_dir=self.config.output_path
        )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"report_{timestamp}.html"
        report_path = os.path.join(self.config.output_path, report_filename)

        report_generator.generate_report(
            report_data=report_data,
            output_path=report_path
        )

        self.logger.info(f"Report generated: {report_path}")

        return 0

    def _cmd_baseline_generate(self) -> int:
        """Execute baseline generate command."""
        self.orchestrator = AnalysisOrchestrator(self.config)

        summary = self.orchestrator.generate_baseline()

        self.logger.info("Baseline summary:")
        self.logger.info(f"  Total files: {summary['total_files']}")
        self.logger.info(f"  Total issues: {summary['total_issues']}")

        return 0

    def _cmd_baseline_update(self) -> int:
        """Execute baseline update command."""
        # Load existing baseline
        if not os.path.exists(self.config.baseline_file):
            self.logger.error(f"Baseline file not found: {self.config.baseline_file}")
            self.logger.info("Use 'baseline generate' to create a new baseline")
            return 1

        self.orchestrator = AnalysisOrchestrator(self.config)
        # ... implement update logic

        return 0

    def _cmd_cache_clear(self) -> int:
        """Execute cache clear command."""
        cache_dir = os.path.join(self.config.output_path, 'cache')

        if os.path.exists(cache_dir):
            import shutil
            shutil.rmtree(cache_dir)
            self.logger.info(f"Cache cleared: {cache_dir}")
        else:
            self.logger.info("No cache found")

        return 0

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C interrupt gracefully."""
        self.logger.warning("\n[WARN] Analysis interrupted by user")
        self.logger.info("[INFO] Saving partial results...")

        # Generate partial report
        if self.orchestrator and self.orchestrator.aggregator:
            report_data = self.orchestrator.aggregator.to_report_json(
                project_path=self.config.source_path,
                analysis_duration_seconds=time.time() - self.orchestrator.start_time,
                cache_hits=self.orchestrator.cache_hits,
                rules_executed=0
            )

            # Save partial report
            os.makedirs(self.config.output_path, exist_ok=True)
            partial_path = os.path.join(
                self.config.output_path,
                f"partial_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            with open(partial_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)

            self.logger.info(f"[INFO] Partial report saved: {partial_path}")

        sys.exit(130)


def create_parser():
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog='bini-analyzer',
        description='Python Upgrade Compatibility Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze project for 3.6 -> 3.12 upgrade
  bini-analyzer analyze ./myproject --target 3.12

  # With explicit source version
  bini-analyzer analyze ./myproject --source 3.6 --target 3.12

  # Verbose output
  bini-analyzer analyze ./myproject --target 3.12 --verbose

  # Generate baseline
  bini-analyzer baseline generate ./myproject --target 3.12

  # Clear cache
  bini-analyzer cache clear ./myproject
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version='bini-analyzer 1.0.0'
    )

    # Global options
    parser.add_argument(
        '--config',
        help='Path to configuration file'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze a Python project for compatibility issues'
    )
    analyze_parser.add_argument(
        'project',
        help='Path to Python project to analyze'
    )
    analyze_parser.add_argument(
        '--source',
        help='Source Python version (default: auto-detect)'
    )
    analyze_parser.add_argument(
        '--target',
        required=True,
        help='Target Python version (e.g., 3.12)'
    )
    analyze_parser.add_argument(
        '--output',
        help='Output directory for reports (default: ./output)'
    )
    analyze_parser.add_argument(
        '--baseline',
        help='Path to baseline file'
    )
    analyze_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    analyze_parser.add_argument(
        '--no-parallel',
        action='store_true',
        help='Disable parallel processing'
    )
    analyze_parser.add_argument(
        '--workers',
        type=int,
        help='Number of worker processes'
    )

    # baseline command
    baseline_parser = subparsers.add_parser(
        'baseline',
        help='Manage baseline for ignoring known issues'
    )
    baseline_subparsers = baseline_parser.add_subparsers(dest='baseline_action')

    baseline_generate_parser = baseline_subparsers.add_parser(
        'generate',
        help='Generate baseline from current issues'
    )
    baseline_generate_parser.add_argument('project')
    baseline_generate_parser.add_argument('--target', required=True)

    baseline_update_parser = baseline_subparsers.add_parser(
        'update',
        help='Update existing baseline'
    )
    baseline_update_parser.add_argument('project')
    baseline_update_parser.add_argument('--target', required=True)

    # cache command
    cache_parser = subparsers.add_parser(
        'cache',
        help='Manage analysis cache'
    )
    cache_subparsers = cache_parser.add_subparsers(dest='cache_action')

    cache_clear_parser = cache_subparsers.add_parser(
        'clear',
        help='Clear analysis cache'
    )
    cache_clear_parser.add_argument('project')

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    analyzer = BiniAnalyzer()
    return analyzer.run(args)


if __name__ == '__main__':
    sys.exit(main())
