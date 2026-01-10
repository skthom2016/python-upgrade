#!/usr/bin/env python3
"""
Fix YAML syntax errors in rule files.
Adds ': true' to condition keys that are missing values.
"""

import re
from pathlib import Path


def fix_yaml_file(file_path: Path) -> int:
    """Fix condition keys without values in a YAML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Pattern: lines that are indented and contain only lowercase_with_underscores
    # These are likely condition keys without values
    # Must be preceded by a 'condition:' key
    pattern = r'^(\s+)([a-z_][a-z0-9_]*)\s*$'

    lines = content.split('\n')
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line matches the pattern
        match = re.match(pattern, line)

        if match:
            indent = match.group(1)
            key = match.group(2)

            # Check if this is inside a condition block
            # by looking backwards for 'condition:'
            is_in_condition = False
            for j in range(i - 1, max(0, i - 10), -1):
                if re.match(r'^\s+condition:\s*$', lines[j]):
                    is_in_condition = True
                    break
                if re.match(r'^[A-Za-z_-]+:\s*$', lines[j]) and not lines[j].strip().startswith('#'):
                    # Found another top-level key, stop looking
                    break

            # Also check next line - if it starts with message/suggestion/examples, this is likely a missing value
            next_is_value_start = False
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith(('message:', 'suggestion:', 'examples:', 'references:', 'detector:')):
                    next_is_value_start = True

            # If it's in a condition block and next line is a new field, add ': true'
            if is_in_condition and next_is_value_start:
                fixed_lines.append(f"{indent}{key}: true")
                i += 1
                continue

        fixed_lines.append(line)
        i += 1

    fixed_content = '\n'.join(fixed_lines)

    if fixed_content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        return 1

    return 0


def main():
    """Main entry point."""
    rules_path = Path(__file__).parent.parent / "rules" / "versions"

    print("Fixing YAML syntax errors in rule files...")
    print("="*60)

    fixed_count = 0
    for yaml_file in rules_path.rglob("*.yaml"):
        if fix_yaml_file(yaml_file):
            print(f"[+] Fixed: {yaml_file.relative_to(rules_path.parent)}")
            fixed_count += 1

    print("="*60)
    if fixed_count > 0:
        print(f"Fixed {fixed_count} file(s)")
    else:
        print("No YAML syntax errors found")
    print("="*60)


if __name__ == "__main__":
    main()
