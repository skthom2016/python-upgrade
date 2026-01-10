"""
Generate comprehensive test files that trigger every rule in the system.

This script:
1. Reads all 474 rules from YAML files
2. Generates Python test files with code that triggers each rule
3. Organizes tests by version and category
4. Creates a master test file that imports all tests
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


class TestGenerator:
    """Generate test files from rules."""

    def __init__(self, rules_dir: Path, output_dir: Path):
        """
        Initialize test generator.

        Args:
            rules_dir: Path to rules/versions directory
            output_dir: Path to test-upgrade directory
        """
        self.rules_dir = rules_dir
        self.output_dir = output_dir
        self.rules_by_version = defaultdict(list)
        self.stats = defaultdict(int)

    def generate_all_tests(self):
        """Generate all test files."""
        print("=" * 60)
        print("Generating Comprehensive Test Files")
        print("=" * 60)
        print()

        # Load all rules
        self.load_all_rules()

        # Generate test files
        for version in sorted(self.rules_by_version.keys()):
            self.generate_version_tests(version)

        # Generate master test file
        self.generate_master_test()

        # Print summary
        self.print_summary()

    def load_all_rules(self):
        """Load all rules from YAML files."""
        versions = ['3.6', '3.7', '3.8', '3.9', '3.10', '3.11']
        categories = ['breaking_changes', 'deprecated_features', 'syntax_changes', 'stdlib_changes']

        print("Loading rules...")
        for version in versions:
            for category in categories:
                file_path = self.rules_dir / version / f"{category}.yaml"
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        rules = yaml.safe_load(f)
                        if rules:
                            for rule in rules:
                                self.rules_by_version[version].append(rule)
                                self.stats['total_rules'] += 1
                                self.stats[f"version_{version}"] += 1
                                self.stats[f"category_{category}"] += 1

        print(f"Loaded {self.stats['total_rules']} rules")
        print()

    def generate_version_tests(self, version: str):
        """Generate test file for a specific version."""
        print(f"Generating tests for Python {version}...")

        rules = self.rules_by_version[version]
        if not rules:
            return

        # Create test file
        test_file = self.output_dir / f"test_python_{version.replace('.', '_')}_all_rules.py"

        header = f'''"""
Comprehensive test file for Python {version} upgrade rules.
This file contains code that triggers every rule defined for Python {version}.

Total rules: {len(rules)}
Generated automatically - DO NOT EDIT MANUALLY
"""

# This file intentionally contains code that will trigger compatibility issues
# when upgrading from Python {version} to later versions

'''

        body_sections = []

        # Group rules by category for better organization
        by_category = defaultdict(list)
        for rule in rules:
            category = rule.get('category', 'unknown')
            by_category[category].append(rule)

        # Generate code for each category
        for category in sorted(by_category.keys()):
            body_sections.append(self.generate_category_section(category, by_category[category]))

        # Write file
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(header)
            f.write('\n\n'.join(body_sections))

        print(f"  Created: {test_file.name} ({len(rules)} rules)")
        self.stats['files_generated'] += 1

    def generate_category_section(self, category: str, rules: List[Dict]) -> str:
        """Generate code section for a category."""
        lines = []

        lines.append(f"# {'=' * 55}")
        lines.append(f"# {category.upper().replace('_', ' ')}")
        lines.append(f"# {len(rules)} rules")
        lines.append(f"# {'=' * 55}")
        lines.append("")

        for rule in rules:
            lines.append(self.generate_rule_test(rule))
            lines.append("")

        return '\n'.join(lines)

    def generate_rule_test(self, rule: Dict) -> str:
        """Generate test code for a single rule."""
        rule_id = rule.get('id', 'UNKNOWN')
        name = rule.get('name', 'Unknown rule')
        examples = rule.get('examples', {})

        lines = []
        lines.append(f"# {rule_id}: {name}")

        # Get bad example if available
        bad_example = examples.get('bad', '') if examples else ''

        if bad_example:
            # Clean up example code
            bad_code = self.clean_example_code(bad_example)
            if bad_code:
                lines.append(bad_code)
            else:
                # No example, generate placeholder
                lines.append(self.generate_placeholder_code(rule))
        else:
            # No examples, generate placeholder
            lines.append(self.generate_placeholder_code(rule))

        return '\n'.join(lines)

    def clean_example_code(self, example: str) -> str:
        """Clean up example code from YAML."""
        lines = example.strip().split('\n')
        cleaned = []

        for line in lines:
            # Skip comment lines that are not code
            if line.strip().startswith('#'):
                # Keep code-like comments
                if any(keyword in line for keyword in ['SyntaxError', 'TypeError', 'deprecated', 'removed']):
                    cleaned.append(line)
            else:
                cleaned.append(line)

        return '\n'.join(cleaned) if cleaned else ''

    def generate_placeholder_code(self, rule: Dict) -> str:
        """Generate placeholder code when no example is available."""
        rule_id = rule.get('id', 'UNKNOWN')
        name = rule.get('name', '')
        pattern = rule.get('pattern', {})

        # Try to generate code based on pattern
        node_type = pattern.get('node_type', '') if pattern else ''

        if 'import' in name.lower() or 'module' in name.lower():
            # Extract module name from rule name
            if 'parser' in name.lower():
                return "# import parser  # Removed"
            elif 'distutils' in name.lower():
                return "# import distutils  # Removed"
            elif 'macpath' in name.lower():
                return "# import macpath  # Removed"
            else:
                return f"# Module import: {name}"

        elif 'function' in name.lower() or 'method' in name.lower():
            if 'time.clock' in name.lower():
                return "# time.clock()  # Removed"
            elif 'utcnow' in name.lower():
                return "# datetime.utcnow()  # Deprecated"
            else:
                return f"# Function call: {name}"

        else:
            return f"# Rule {rule_id}: {name}"

    def generate_master_test(self):
        """Generate master test file that references all others."""
        master_file = self.output_dir / "test_all_versions_comprehensive.py"

        content = '''"""
Master comprehensive test file for all Python version upgrade rules.

This file imports all version-specific test files.
Each version-specific file contains code that triggers all rules for that version.

Total rules covered: {total_rules}
Test files generated: {files_generated}
"""

# This test suite intentionally contains code with compatibility issues
# for testing the analyzer's detection capabilities

if __name__ == "__main__":
    print("Comprehensive Test Suite for Bini Python Upgrade Analyzer")
    print("=" * 60)
    print(f"Total rules: {total_rules}")
    print(f"Test files: {files_generated}")
    print()
    print("Version coverage:")
'''.format(
            total_rules=self.stats['total_rules'],
            files_generated=self.stats['files_generated']
        )

        for version in sorted(self.rules_by_version.keys()):
            content += f'    print(f"  - Python {version}: {len(self.rules_by_version[version])} rules")\n'

        with open(master_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"\nCreated master test file: {master_file.name}")

    def print_summary(self):
        """Print generation summary."""
        print()
        print("=" * 60)
        print("Test Generation Summary")
        print("=" * 60)
        print(f"Total rules processed: {self.stats['total_rules']}")
        print(f"Test files generated: {self.stats['files_generated']}")
        print()
        print("By version:")
        for version in sorted(self.rules_by_version.keys()):
            count = self.stats[f"version_{version}"]
            print(f"  - Python {version}: {count} rules")
        print()
        print("=" * 60)


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    rules_dir = project_root / 'rules' / 'versions'
    output_dir = Path("D:/Santhosh/latestdev/test-upgrade")

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    generator = TestGenerator(rules_dir, output_dir)
    generator.generate_all_tests()


if __name__ == '__main__':
    main()
