"""
Rule loader for loading and validating YAML rules.
"""

import os
import yaml
import glob
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from reporting.data_models import Issue


@dataclass
class Rule:
    """
    Represents a single compatibility rule.

    Attributes:
        id: Unique rule identifier (e.g., "PY3601")
        name: Human-readable name
        description: Detailed description
        category: Issue category
        severity: Severity level
        risk_level: Risk level bucket
        source_version: Source Python version
        target_version: Target Python version
        detector: Detector class name
        pattern: AST pattern to match
        condition: Additional condition (optional)
        message: Error message
        suggestion: Suggested fix
        examples: Code examples (optional)
        references: Documentation links
        raw_data: Original rule data including detection metadata
    """
    id: str
    name: str
    description: str
    category: str
    severity: str
    risk_level: str
    source_version: str
    target_version: str
    detector: str
    pattern: Dict[str, Any]
    condition: Optional[Dict[str, Any]]
    message: str
    suggestion: str
    examples: Optional[Dict[str, str]]
    references: List[str]
    raw_data: Dict[str, Any] = None  # Store complete rule data for LLM detection

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'severity': self.severity,
            'risk_level': self.risk_level,
            'source_version': self.source_version,
            'target_version': self.target_version,
            'detector': self.detector,
            'pattern': self.pattern,
            'condition': self.condition,
            'message': self.message,
            'suggestion': self.suggestion,
            'examples': self.examples,
            'references': self.references,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Rule':
        """Create Rule from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            category=data['category'],
            severity=data['severity'],
            risk_level=data['risk_level'],
            source_version=data['source_version'],
            target_version=data['target_version'],
            detector=data['detector'],
            pattern=data['pattern'],
            condition=data.get('condition'),
            message=data['message'],
            suggestion=data['suggestion'],
            examples=data.get('examples'),
            references=data.get('references', []),
            raw_data=data  # Store complete data for LLM detection
        )


class RuleLoader:
    """
    Load and validate YAML rules from filesystem.

    Rules are organized by version:
    rules/versions/{source_version}/category.yaml
    """

    def __init__(self, rules_dir: Optional[str] = None):
        """
        Initialize rule loader.

        Args:
            rules_dir: Directory containing rule files (default: rules/versions/)
        """
        if rules_dir is None:
            rules_dir = os.path.join(
                os.path.dirname(__file__),
                'versions'
            )
        self.rules_dir = rules_dir
        self.rules: List[Rule] = []
        self.malformed_rules: List[Dict[str, Any]] = []

    def load_rules_for_version(
        self,
        source_version: str,
        target_version: str
    ) -> List[Rule]:
        """
        Load rules for specific version upgrade path.

        Args:
            source_version: Source Python version (e.g., "3.6")
            target_version: Target Python version (e.g., "3.12")

        Returns:
            List of Rule objects
        """
        self.rules = []
        self.malformed_rules = []

        # Determine which version directories to load
        source_minor = int(source_version.split('.')[1])
        target_minor = int(target_version.split('.')[1])

        # Load rules for each intermediate version
        for version_minor in range(source_minor, target_minor + 1):
            version_str = f"3.{version_minor}"
            version_dir = os.path.join(self.rules_dir, version_str)

            if os.path.exists(version_dir):
                self._load_rules_from_directory(version_dir, version_str)

        return self.rules

    def _load_rules_from_directory(self, directory: str, version_str: str):
        """
        Load all YAML rule files from a directory.

        Args:
            directory: Directory containing rule files
            version_str: Version string for these rules
        """
        # Find all YAML files
        pattern = os.path.join(directory, '*.yaml')
        yaml_files = glob.glob(pattern)

        # Also check for .yml extension
        pattern = os.path.join(directory, '*.yml')
        yaml_files.extend(glob.glob(pattern))

        for yaml_file in yaml_files:
            self._load_rule_file(yaml_file)

    def _load_rule_file(self, file_path: str):
        """
        Load rules from a single YAML file.

        Args:
            file_path: Path to YAML file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, list):
                self.malformed_rules.append({
                    'file': file_path,
                    'error': 'Root element must be a list',
                    'data': data
                })
                return

            for rule_data in data:
                rule = self._parse_rule(rule_data, file_path)
                if rule:
                    self.rules.append(rule)

        except yaml.YAMLError as e:
            self.malformed_rules.append({
                'file': file_path,
                'error': f'YAML parsing error: {str(e)}',
                'data': None
            })
        except Exception as e:
            self.malformed_rules.append({
                'file': file_path,
                'error': f'Unexpected error: {str(e)}',
                'data': None
            })

    def _parse_rule(self, data: Dict[str, Any], file_path: str) -> Optional[Rule]:
        """
        Parse rule data into Rule object.

        Args:
            data: Rule data dictionary
            file_path: Path to source file (for error reporting)

        Returns:
            Rule object or None if invalid
        """
        # Validate required fields
        required_fields = [
            'id', 'name', 'description', 'category', 'severity',
            'risk_level', 'source_version', 'target_version',
            'detector', 'pattern', 'message', 'suggestion'
        ]

        missing_fields = [
            field for field in required_fields
            if field not in data
        ]

        if missing_fields:
            self.malformed_rules.append({
                'file': file_path,
                'rule_id': data.get('id', 'unknown'),
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'data': data
            })
            return None

        try:
            return Rule.from_dict(data)
        except Exception as e:
            self.malformed_rules.append({
                'file': file_path,
                'rule_id': data.get('id', 'unknown'),
                'error': f'Parse error: {str(e)}',
                'data': data
            })
            return None

    def get_rules(self) -> List[Rule]:
        """Get all loaded rules."""
        return self.rules

    def get_malformed_rules(self) -> List[Dict[str, Any]]:
        """Get information about malformed rules."""
        return self.malformed_rules

    def get_rules_by_category(self, category: str) -> List[Rule]:
        """
        Get rules filtered by category.

        Args:
            category: Category to filter by

        Returns:
            List of rules in the category
        """
        return [r for r in self.rules if r.category == category]

    def get_rules_by_severity(self, severity: str) -> List[Rule]:
        """
        Get rules filtered by severity.

        Args:
            severity: Severity to filter by

        Returns:
            List of rules with the severity
        """
        return [r for r in self.rules if r.severity == severity]

    def get_rule_by_id(self, rule_id: str) -> Optional[Rule]:
        """
        Get rule by ID.

        Args:
            rule_id: Rule ID to find

        Returns:
            Rule object or None
        """
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
