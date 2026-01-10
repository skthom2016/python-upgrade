"""Fix YAML indentation issues in stdlib_changes.yaml files."""

import re
from pathlib import Path


def fix_description_indentation(content: str) -> str:
    """
    Fix indentation issues in multiline description blocks.

    Find lines after 'description: |' that are not properly indented.
    """
    lines = content.split('\n')
    fixed_lines = []
    in_multiline_block = False
    block_indent = 0

    for i, line in enumerate(lines):
        # Check if this line starts a multiline block
        if re.match(r'^(\s+)(description|message|suggestion):\s*\|', line):
            in_multiline_block = True
            block_indent = len(line) - len(line.lstrip())
            fixed_lines.append(line)
            continue

        # If we're in a multiline block
        if in_multiline_block:
            # Check if line is a new key (starts with correct indentation + key:)
            if re.match(r'^(\s+)\w+:', line):
                # Calculate indentation
                current_indent = len(line) - len(line.lstrip())

                # If indentation matches or exceeds the block indent, this ends the multiline
                if current_indent <= block_indent:
                    in_multiline_block = False
                    fixed_lines.append(line)
                    continue

                # Otherwise, this is within the multiline block but improperly indented
                # Add proper indentation (block_indent + 4 spaces)
                content_start = line.lstrip()
                fixed_line = ' ' * (block_indent + 4) + content_start
                fixed_lines.append(fixed_line)
                continue

            # Regular content line in multiline block
            if line.strip():  # Non-empty line
                # Should have block_indent + 4 spaces
                current_indent = len(line) - len(line.lstrip())
                content_start = line.lstrip()

                # Fix indentation if needed
                if current_indent <= block_indent:
                    fixed_line = ' ' * (block_indent + 4) + content_start
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            else:
                # Empty line
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def main():
    """Fix indentation issues in all YAML files."""
    rules_dir = Path(__file__).parent.parent / 'rules' / 'versions'

    # Fix 3.7/stdlib_changes.yaml
    file_path = rules_dir / '3.7' / 'stdlib_changes.yaml'

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    print(f"Fixing indentation in {file_path}...")

    # Read content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix indentation
    fixed_content = fix_description_indentation(content)

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print("Done!")

    # Validate
    import yaml
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        print("[OK] YAML is valid!")
    except yaml.YAMLError as e:
        print(f"[ERROR] YAML still has errors: {e}")


if __name__ == '__main__':
    main()
