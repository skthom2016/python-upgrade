#!/usr/bin/env python3
"""
Classify existing YAML rules by detection strategy.
This script analyzes rules and suggests the best detection approach.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


class RuleClassifier:
    """Classify rules by detection strategy."""

    def __init__(self, rules_base_path: str):
        self.rules_base_path = Path(rules_base_path)
        self.classifications = defaultdict(list)

    def load_all_rules(self) -> Dict[str, List[Dict]]:
        """Load all YAML rule files."""
        all_rules = {}

        for version_dir in self.rules_base_path.glob("*/"):
            if not version_dir.is_dir():
                continue

            version = version_dir.name
            all_rules[version] = {}

            for yaml_file in version_dir.glob("*.yaml"):
                category = yaml_file.stem
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    rules = yaml.safe_load(f) or []
                    all_rules[version][category] = rules

        return all_rules

    def classify_rule(self, rule: Dict, category: str) -> str:
        """
        Classify a single rule by detection strategy.

        Returns: 'ast', 'text', 'hybrid', or 'runtime'
        """
        rule_id = rule.get('id', 'UNKNOWN')
        message = rule.get('message', '').lower()
        name = rule.get('name', '').lower()
        combined_text = f"{name} {message}"

        # Syntax changes are always AST-based
        if category == 'syntax_changes':
            return 'ast'

        # Module/function removals are AST-based
        if any(keyword in combined_text for keyword in [
            'removed', 'module removed', 'function removed',
            'no longer available', 'does not exist'
        ]):
            return 'ast'

        # Behavioral changes need hybrid/text
        if any(keyword in combined_text for keyword in [
            'behavior', 'behaviour', 'now returns', 'now raises',
            'changed', 'different', 'no longer accepts'
        ]):
            # Check if it's a clear API change (AST) or subtle (hybrid)
            if any(keyword in combined_text for keyword in [
                'keyword argument', 'parameter removed', 'signature'
            ]):
                return 'ast'
            return 'hybrid'

        # Deprecations with edge cases need text/hybrid
        if any(keyword in combined_text for keyword in [
            'deprecated', 'will be removed', 'use instead'
        ]):
            # Check if deprecation is straightforward
            if 'module' in combined_text and 'deprecated' in combined_text:
                return 'ast'
            if any(keyword in combined_text for keyword in [
                'context', 'depending', 'may', 'certain cases'
            ]):
                return 'text'
            return 'hybrid'

        # Default to AST for clear patterns, text for complex
        pattern = rule.get('pattern', {})
        if pattern and pattern.get('node_type'):
            # Has AST pattern - start with AST, can upgrade to hybrid
            return 'ast'

        return 'text'

    def classify_all_rules(self):
        """Classify all rules across all versions."""
        all_rules = self.load_all_rules()

        for version, categories in all_rules.items():
            print(f"\n{'='*60}")
            print(f"Python Version: {version}")
            print(f"{'='*60}")

            for category, rules in categories.items():
                strategy_counts = defaultdict(int)

                for rule in rules:
                    strategy = self.classify_rule(rule, category)
                    strategy_counts[strategy] += 1

                    # Store classification
                    rule['detection_strategy'] = strategy

                print(f"\n{category}:")
                for strategy, count in sorted(strategy_counts.items()):
                    print(f"  {strategy:10s}: {count:3d} rules")

                # Save updated rules
                self.save_classified_rules(version, category, rules)

    def save_classified_rules(self, version: str, category: str, rules: List[Dict]):
        """Save rules with detection_strategy added."""
        output_file = self.rules_base_path / version / f"{category}.yaml"

        # Backup original
        backup_file = output_file.with_suffix('.yaml.bak')
        if not backup_file.exists():
            import shutil
            shutil.copy(output_file, backup_file)

        # Write updated rules
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(rules, f, default_flow_style=False, allow_unicode=True,
                     sort_keys=False)

        print(f"  ✓ Updated: {output_file.name}")

    def generate_summary_report(self):
        """Generate a summary report of classifications."""
        all_rules = self.load_all_rules()
        total_counts = defaultdict(int)
        category_strategy = defaultdict(lambda: defaultdict(int))

        for version, categories in all_rules.items():
            for category, rules in categories.items():
                for rule in rules:
                    strategy = rule.get('detection_strategy', 'unknown')
                    total_counts[strategy] += 1
                    category_strategy[category][strategy] += 1

        print(f"\n{'='*60}")
        print("DETECTION STRATEGY SUMMARY")
        print(f"{'='*60}\n")

        print("Overall Distribution:")
        for strategy, count in sorted(total_counts.items()):
            percentage = (count / sum(total_counts.values())) * 100
            print(f"  {strategy:10s}: {count:4d} rules ({percentage:5.1f}%)")

        print(f"\n{'='*60}")
        print("By Category:")
        print(f"{'='*60}\n")

        for category in sorted(category_strategy.keys()):
            print(f"{category}:")
            for strategy, count in sorted(category_strategy[category].items()):
                print(f"  {strategy:10s}: {count:3d} rules")


def main():
    """Main entry point."""
    rules_path = Path(__file__).parent.parent / "rules" / "versions"

    classifier = RuleClassifier(rules_path)

    print("Classifying rules by detection strategy...")
    classifier.classify_all_rules()

    print("\n" + "="*60)
    classifier.generate_summary_report()

    print("\n" + "="*60)
    print("Classification complete!")
    print("Backup files created with .bak extension")
    print("="*60)


if __name__ == "__main__":
    main()
