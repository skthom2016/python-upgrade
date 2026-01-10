"""Validate all YAML files and report errors."""

import yaml
from pathlib import Path


def validate_yaml_file(file_path: Path) -> tuple[bool, str]:
    """Validate a single YAML file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        return True, "OK"
    except yaml.YAMLError as e:
        return False, str(e)


def main():
    rules_dir = Path(__file__).parent.parent / 'rules' / 'versions'
    versions = ['3.6', '3.7', '3.8', '3.9', '3.10', '3.11']
    categories = ['breaking_changes', 'deprecated_features', 'syntax_changes', 'stdlib_changes']

    print("Validating YAML files...")
    print("=" * 60)

    errors = []
    for version in versions:
        for category in categories:
            file_path = rules_dir / version / f"{category}.yaml"
            if file_path.exists():
                valid, msg = validate_yaml_file(file_path)
                if valid:
                    print(f"[OK] {version}/{category}.yaml")
                else:
                    print(f"[ERROR] {version}/{category}.yaml")
                    print(f"  Error: {msg}")
                    errors.append((version, category, msg))

    print("=" * 60)
    if errors:
        print(f"\nFound {len(errors)} files with errors:")
        for version, category, msg in errors:
            print(f"\n{version}/{category}.yaml:")
            print(f"  {msg}")
    else:
        print("\nAll files are valid!")


if __name__ == '__main__':
    main()
