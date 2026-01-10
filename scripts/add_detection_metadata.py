"""
Script to add detection strategy metadata to all rule YAML files.

This script:
1. Reads all YAML rule files from rules/versions/{3.6-3.11}/
2. Classifies each rule into detection strategies (ast, hybrid, text, info_only)
3. Adds detection metadata to each rule
4. Writes updated YAML files back
5. Generates a summary report
"""

import yaml
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


class RuleClassifier:
    """Classifies rules into detection strategies based on patterns."""

    # AST-based patterns (HIGH confidence, no LLM)
    AST_PATTERNS = {
        # Module removals/imports
        'module_removal': r'(removed|deprecated).*module',
        'module_import': r'(import|from .* import)',

        # Function/method removals
        'function_removal': r'(function|method).*removed',
        'function_call': r'\(\).*removed',

        # Decorator changes
        'decorator': r'@\w+',

        # Syntax keywords
        'keyword': r'(async|await|match|case) (become|keyword|reserved)',

        # New features (imports/functions that are new)
        'new_module': r'new (module|function|method|class)',
        'new_syntax': r'(available|introduced|new) in',

        # Clear attribute/parameter changes
        'parameter_removed': r'parameter.*removed',
        'argument_removed': r'argument.*removed',
    }

    # Hybrid patterns (MEDIUM confidence, LLM validation needed)
    HYBRID_PATTERNS = {
        'context_dependent': r'(context|depend|only|except)',
        'behavioral_change': r'(behavior|behave|changed|now)',
        'conditional': r'(if|when|unless)',
        'inheritance': r'(inherit|subclass)',
        'return_type_change': r'return.*(type|value|changed)',
        'edge_case': r'(edge case|special case)',
    }

    # Text/LLM patterns (MEDIUM-LOW confidence, semantic analysis)
    TEXT_PATTERNS = {
        'runtime_behavior': r'runtime',
        'implicit_change': r'implicit',
        'semantic': r'semantic',
        'performance': r'(performance|faster|slower)',
        'nan_hash': r'NaN hash',
        'debug_deletion': r'__debug__.*deletion',
        'integer_limits': r'integer string conversion limit',
    }

    def __init__(self):
        self.stats = defaultdict(lambda: defaultdict(int))

    def classify_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a rule and add detection metadata.

        Returns:
            dict: Detection metadata for the rule
        """
        rule_id = rule.get('id', 'UNKNOWN')
        category = rule.get('category', '')
        severity = rule.get('severity', 'medium')
        description = rule.get('description', '').lower()
        message = rule.get('message', '').lower()
        name = rule.get('name', '').lower()

        combined_text = f"{name} {description} {message}"

        # Determine strategy
        strategy = self._determine_strategy(rule, combined_text, category)
        confidence = self._determine_confidence(strategy, combined_text)
        requires_llm = strategy in ['hybrid', 'text']
        priority = self._map_priority(severity)

        detection = {
            'strategy': strategy,
            'confidence': confidence,
            'requires_llm': requires_llm,
            'priority': priority
        }

        # Add semantic description for hybrid/text strategies
        if strategy in ['hybrid', 'text']:
            detection['semantic_description'] = self._generate_semantic_description(
                rule, strategy
            )
            detection['detection_criteria'] = self._generate_detection_criteria(
                rule, strategy
            )

        # Update stats
        version = rule.get('source_version', 'unknown')
        self.stats[version][strategy] += 1
        self.stats['total'][strategy] += 1
        self.stats['by_category'][category] += 1
        self.stats['by_priority'][priority] += 1

        return detection

    def _determine_strategy(self, rule: Dict, text: str, category: str) -> str:
        """Determine the detection strategy for a rule."""

        # Info-only: new features, performance notes
        if category in ['new_feature'] or rule.get('severity') == 'info':
            # Check if it's truly info-only (not a breaking syntax change)
            if 'not available' in text or 'requires python' in text:
                return 'info_only'
            # New imports/modules are still AST-based detection
            if any(kw in text for kw in ['import', 'module', 'function', 'method']):
                return 'ast'
            return 'info_only'

        # Check for AST patterns (high priority)
        if self._matches_ast_pattern(rule, text):
            return 'ast'

        # Check for text/semantic patterns
        if self._matches_text_pattern(text):
            return 'text'

        # Check for hybrid patterns
        if self._matches_hybrid_pattern(text):
            return 'hybrid'

        # Default: AST for most breaking changes and clear deprecations
        if category in ['breaking_change', 'deprecation']:
            # Check if it's context-dependent
            if any(kw in text for kw in ['context', 'depend', 'only if', 'except when']):
                return 'hybrid'
            return 'ast'

        # Default to AST
        return 'ast'

    def _matches_ast_pattern(self, rule: Dict, text: str) -> bool:
        """Check if rule matches AST detection patterns."""
        # Module imports/removals
        if 'import' in rule.get('name', '').lower() or 'module' in rule.get('name', '').lower():
            if 'removed' in text or 'deprecated' in text or 'new' in text:
                return True

        # Function/method calls
        if '()' in rule.get('name', '') or 'function' in text or 'method' in text:
            if 'removed' in text or 'deprecated' in text:
                return True

        # Decorators
        if '@' in rule.get('name', '') or 'decorator' in text:
            return True

        # Keywords
        if any(kw in text for kw in ['async', 'await', 'match', 'case', 'keyword', 'reserved']):
            return True

        # Parameter/argument changes (if clear)
        if 'parameter removed' in text or 'argument removed' in text:
            return True

        # Pattern-based AST detection
        pattern = rule.get('pattern', {})
        if pattern and isinstance(pattern, dict):
            node_type = pattern.get('node_type', '')
            if node_type in ['Import', 'ImportFrom', 'Call', 'FunctionDef', 'Name']:
                # Clear AST patterns
                if not any(kw in text for kw in ['context', 'depend', 'only if', 'when', 'unless']):
                    return True

        return False

    def _matches_hybrid_pattern(self, text: str) -> bool:
        """Check if rule matches hybrid detection patterns."""
        hybrid_keywords = [
            'yield in comprehension',
            'context',
            'only if',
            'except when',
            'when used',
            'inheritance changed',
            'return type changed',
            'behavior changed',
            'edge case'
        ]
        return any(kw in text for kw in hybrid_keywords)

    def _matches_text_pattern(self, text: str) -> bool:
        """Check if rule matches text/semantic detection patterns."""
        text_keywords = [
            'runtime',
            'implicit',
            'nan hash',
            '__debug__ deletion',
            'integer string conversion',
            'performance',
            'semantic'
        ]
        return any(kw in text for kw in text_keywords)

    def _determine_confidence(self, strategy: str, text: str) -> str:
        """Determine confidence level based on strategy."""
        if strategy == 'ast':
            return 'high'
        elif strategy == 'hybrid':
            return 'medium'
        elif strategy == 'text':
            # Check if it's a clear semantic issue
            if 'runtime' in text or '__debug__' in text:
                return 'medium'
            return 'low'
        else:  # info_only
            return None

    def _map_priority(self, severity: str) -> str:
        """Map severity to priority."""
        mapping = {
            'critical': 'critical',
            'high': 'high',
            'medium': 'medium',
            'low': 'low',
            'info': 'info'
        }
        return mapping.get(severity, 'medium')

    def _generate_semantic_description(self, rule: Dict, strategy: str) -> str:
        """Generate semantic description for hybrid/text rules."""
        name = rule.get('name', 'Unknown rule')
        description = rule.get('description', '').strip()

        if strategy == 'hybrid':
            return f"""
{name} requires context validation to avoid false positives.
{description[:200]}...

The rule should be validated to ensure it matches the intended context.
""".strip()
        else:  # text
            return f"""
{name} involves semantic or runtime behavior changes.
{description[:200]}...

This requires LLM analysis to understand the context and implications.
""".strip()

    def _generate_detection_criteria(self, rule: Dict, strategy: str) -> Dict[str, Any]:
        """Generate detection criteria for hybrid/text rules."""
        pattern = rule.get('pattern', {})
        name = rule.get('name', '')

        criteria = {}

        # Extract AST pattern if available
        if pattern:
            node_type = pattern.get('node_type', '')
            if node_type:
                criteria['ast_pattern'] = f"{node_type} node with specific attributes"

        # Extract text keywords
        keywords = []
        if 'yield' in name.lower():
            keywords.extend(['yield', 'yield from', 'comprehension'])
        if 'asyncio' in name.lower():
            keywords.extend(['asyncio', 'async', 'await'])
        if 'deprecated' in name.lower():
            keywords.append('deprecated')

        criteria['text_keywords'] = keywords[:5]  # Limit to 5

        # Generate validation prompt
        if strategy == 'hybrid':
            criteria['validation_prompt'] = f"""
Validate if this code matches the rule: {name}
Check for context-specific conditions and edge cases.
Ensure the pattern is not a false positive.
""".strip()
        else:  # text
            criteria['validation_prompt'] = f"""
Analyze the semantic implications of this code for: {name}
Consider runtime behavior and implicit changes.
Determine if this is truly an issue in the target version.
""".strip()

        return criteria


class YAMLProcessor:
    """Process YAML files to add detection metadata."""

    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir
        self.classifier = RuleClassifier()
        self.processed_files = []

    def process_all_files(self):
        """Process all YAML files in all version directories."""
        versions = ['3.6', '3.7', '3.8', '3.9', '3.10', '3.11']
        categories = ['breaking_changes', 'deprecated_features', 'syntax_changes', 'stdlib_changes']

        for version in versions:
            for category in categories:
                file_path = self.rules_dir / version / f"{category}.yaml"
                if file_path.exists():
                    print(f"Processing {version}/{category}.yaml...")
                    self.process_file(file_path, version, category)
                else:
                    print(f"Warning: {file_path} not found")

    def process_file(self, file_path: Path, version: str, category: str):
        """Process a single YAML file."""
        # Read YAML file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse YAML
        rules = yaml.safe_load(content)

        if not rules:
            print(f"  No rules found in {file_path}")
            return

        # Process each rule
        updated_rules = []
        for rule in rules:
            # Classify and add detection metadata
            detection = self.classifier.classify_rule(rule)

            # Create updated rule with detection section after target_version
            updated_rule = {}
            for key in ['id', 'name', 'category', 'severity', 'risk_level', 'source_version', 'target_version']:
                if key in rule:
                    updated_rule[key] = rule[key]

            # Add detection section
            updated_rule['detection'] = detection

            # Add remaining fields
            for key, value in rule.items():
                if key not in updated_rule:
                    updated_rule[key] = value

            updated_rules.append(updated_rule)

        # Write back to file with proper YAML formatting
        self.write_yaml_file(file_path, updated_rules)
        self.processed_files.append((version, category, len(updated_rules)))

        print(f"  Updated {len(updated_rules)} rules")

    def write_yaml_file(self, file_path: Path, rules: List[Dict]):
        """Write rules back to YAML file with proper formatting."""
        # Custom YAML representer for multiline strings
        def str_presenter(dumper, data):
            if len(data.splitlines()) > 1 or '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)

        yaml.add_representer(str, str_presenter)

        # Write YAML with proper formatting
        with open(file_path, 'w', encoding='utf-8') as f:
            # Write header comment
            category_name = file_path.stem.replace('_', ' ').title()
            version = file_path.parent.name
            f.write(f"# {category_name} when upgrading from Python {version}\n")
            if 'breaking' in category_name.lower():
                f.write("# These changes will cause code to break or behave differently\n")
            elif 'deprecated' in category_name.lower():
                f.write("# These features are deprecated and will be removed in future versions\n")
            elif 'syntax' in category_name.lower():
                f.write("# New syntax features and breaking syntax changes\n")
            elif 'stdlib' in category_name.lower():
                f.write("# Changes to modules, functions, and classes in the Python standard library\n")
            f.write("\n")

            # Write each rule
            yaml.dump(rules, f, default_flow_style=False, sort_keys=False,
                     allow_unicode=True, width=80, indent=2)

    def generate_summary_report(self) -> str:
        """Generate summary report of classification."""
        stats = self.classifier.stats

        report = []
        report.append("=" * 60)
        report.append("Detection Strategy Classification Summary")
        report.append("=" * 60)
        report.append("")

        # Total rules
        total = sum(stats['total'].values())
        report.append(f"Total Rules Classified: {total}")
        report.append("")

        # By strategy
        report.append("By Strategy:")
        for strategy in ['ast', 'hybrid', 'text', 'info_only']:
            count = stats['total'][strategy]
            pct = (count / total * 100) if total > 0 else 0
            llm_req = "LLM validation required" if strategy in ['hybrid', 'text'] else "No LLM required"
            report.append(f"  {strategy.upper():12s}: {count:4d} ({pct:5.1f}%) - {llm_req}")
        report.append("")

        # By version
        report.append("By Version:")
        versions = sorted([v for v in stats.keys() if v not in ['total', 'by_category', 'by_priority']])
        for version in versions:
            version_total = sum(stats[version].values())
            report.append(f"  Python {version}: {version_total:4d} rules")
            for strategy in ['ast', 'hybrid', 'text', 'info_only']:
                count = stats[version][strategy]
                if count > 0:
                    report.append(f"    - {strategy:10s}: {count:3d}")
        report.append("")

        # By category
        report.append("By Category:")
        for category, count in sorted(stats['by_category'].items()):
            report.append(f"  {category:25s}: {count:4d} rules")
        report.append("")

        # By priority
        report.append("By Priority:")
        for priority in ['critical', 'high', 'medium', 'low', 'info']:
            count = stats['by_priority'][priority]
            if count > 0:
                report.append(f"  {priority:10s}: {count:4d} rules")
        report.append("")

        # Processed files
        report.append("Processed Files:")
        for version, category, count in sorted(self.processed_files):
            report.append(f"  Python {version} - {category:25s}: {count:3d} rules")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)


def main():
    """Main entry point."""
    print("=" * 60)
    print("Adding Detection Strategy Metadata to Rules")
    print("=" * 60)
    print()

    # Get rules directory
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    rules_dir = project_dir / 'rules' / 'versions'

    if not rules_dir.exists():
        print(f"Error: Rules directory not found: {rules_dir}")
        return

    # Process all files
    processor = YAMLProcessor(rules_dir)
    processor.process_all_files()

    # Generate and print summary report
    print()
    print(processor.generate_summary_report())

    # Save report to file
    report_file = project_dir / 'detection_classification_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(processor.generate_summary_report())

    print(f"\nReport saved to: {report_file}")
    print("\nDone!")


if __name__ == '__main__':
    main()
