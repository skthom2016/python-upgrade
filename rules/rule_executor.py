"""
Rule executor for applying rules against AST nodes.
"""

import ast
from typing import List, Dict, Any, Optional
from packaging import version

from reporting.data_models import Issue, Location, Severity, Category, RiskLevel
from rules.rule_loader import Rule
from detection.ast_pattern_matcher import ASTPatternMatcher


class RuleExecutor:
    """
    Execute rules against parsed AST trees.

    Responsibilities:
    - Execute all loaded rules against an AST tree
    - Pattern matching using ASTPatternMatcher
    - Condition evaluation
    - Issue creation with proper location and context
    """

    def __init__(
        self,
        rules: List[Rule],
        target_version: str,
        source_version: str = "3.6"
    ):
        """
        Initialize rule executor.

        Args:
            rules: List of Rule objects to execute
            target_version: Target Python version
            source_version: Source Python version
        """
        self.rules = rules
        self.target_version = target_version
        self.source_version = source_version
        self.file_path: str = ""
        self.source_lines: List[str] = []

    def execute_all(
        self,
        tree: ast.Module,
        file_path: str,
        source_lines: List[str]
    ) -> List[Issue]:
        """
        Execute all rules against an AST tree.

        Args:
            tree: Parsed AST tree
            file_path: Path to source file
            source_lines: Source code lines

        Returns:
            List of Issue objects found
        """
        self.file_path = file_path
        self.source_lines = source_lines

        issues = []

        for rule in self.rules:
            rule_issues = self.execute_rule(rule, tree)
            issues.extend(rule_issues)

        return issues

    def execute_rule(self, rule: Rule, tree: ast.Module) -> List[Issue]:
        """
        Execute a single rule against an AST tree.

        Args:
            rule: Rule to execute
            tree: AST tree

        Returns:
            List of Issue objects found
        """
        issues = []

        # Walk AST and find matches
        for node in ast.walk(tree):
            if self._matches_rule(node, rule):
                issue = self._create_issue_from_rule(rule, node)
                if issue:
                    issues.append(issue)

        return issues

    def _matches_rule(self, node: ast.AST, rule: Rule) -> bool:
        """
        Check if a node matches a rule's pattern.

        Args:
            node: AST node
            rule: Rule to check

        Returns:
            True if node matches rule
        """
        # Skip rules with null patterns (informational only)
        if not rule.pattern:
            return False

        # Use pattern matcher
        matcher = ASTPatternMatcher(rule.pattern)
        if not matcher.matches(node):
            return False

        # Check additional condition if present
        if rule.condition:
            return self._evaluate_condition(node, rule.condition)

        return True

    def _evaluate_condition(
        self,
        node: ast.AST,
        condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate additional condition on a node.

        Args:
            node: AST node
            condition: Condition dictionary

        Returns:
            True if condition is satisfied
        """
        # Check 'not_in_context' condition
        if 'not_in_context' in condition:
            contexts = condition['not_in_context']
            if self._is_in_context(node, contexts):
                return False

        # Check 'in_context' condition
        if 'in_context' in condition:
            contexts = condition['in_context']
            if not self._is_in_context(node, contexts):
                return False

        # Check 'has_decorator' condition
        if 'has_decorator' in condition:
            decorator_name = condition['has_decorator']
            if not self._has_decorator(node, decorator_name):
                return False

        # Check 'version_range' condition
        if 'version_range' in condition:
            version_range = condition['version_range']
            if not self._in_version_range(version_range):
                return False

        return True

    def _is_in_context(self, node: ast.AST, contexts: List[str]) -> bool:
        """
        Check if node is in a specific context (e.g., async function).

        Args:
            node: AST node
            contexts: List of context types

        Returns:
            True if node is in any of the contexts
        """
        # Walk up the tree to find parent contexts
        # This would require building a parent map
        # For now, implement simple checks
        for context in contexts:
            if context == 'async_func':
                if isinstance(node, (ast.AsyncFor, ast.AsyncWith)):
                    return True
            elif context == 'function':
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return True
        return False

    def _has_decorator(self, node: ast.AST, decorator_name: str) -> bool:
        """
        Check if a function has a specific decorator.

        Args:
            node: AST node
            decorator_name: Decorator name to check

        Returns:
            True if node has the decorator
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id == decorator_name:
                    return True
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr == decorator_name:
                    return True

        return False

    def _in_version_range(self, version_range: Dict[str, str]) -> bool:
        """
        Check if target version is in a specific range.

        Args:
            version_range: Dictionary with 'min' and/or 'max' versions

        Returns:
            True if target version is in range
        """
        target = version.parse(self.target_version)

        if 'min' in version_range:
            min_ver = version.parse(version_range['min'])
            if target < min_ver:
                return False

        if 'max' in version_range:
            max_ver = version.parse(version_range['max'])
            if target > max_ver:
                return False

        return True

    def _create_issue_from_rule(self, rule: Rule, node: ast.AST) -> Optional[Issue]:
        """
        Create an Issue object from a rule and matching AST node.

        Args:
            rule: Rule that matched
            node: AST node that matched

        Returns:
            Issue object
        """
        # Extract location
        line = getattr(node, 'lineno', 1)
        column = getattr(node, 'col_offset', 0)
        end_line = getattr(node, 'end_lineno', line)
        end_column = getattr(node, 'end_col_offset', column)

        location = Location(
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column
        )

        # Get code snippet
        code_snippet = self._get_code_snippet(line, column)

        # Determine affected versions
        affected_versions = self._get_affected_versions(rule)

        return Issue(
            id=rule.id,
            file_path=self.file_path,
            location=location,
            severity=rule.severity,
            category=rule.category,
            risk_level=rule.risk_level,
            message=rule.message,
            suggestion=rule.suggestion,
            code_snippet=code_snippet,
            affected_versions=affected_versions,
            references=rule.references
        )

    def _get_code_snippet(self, line: int, column: int, context_lines: int = 3) -> str:
        """
        Extract code snippet around a location.

        Args:
            line: Line number (1-indexed)
            column: Column number (0-indexed)
            context_lines: Number of lines before and after

        Returns:
            Code snippet with marker
        """
        if not self.source_lines:
            return ""

        line_idx = line - 1
        start_line = max(0, line_idx - context_lines)
        end_line = min(len(self.source_lines), line_idx + context_lines + 1)

        lines = self.source_lines[start_line:end_line]

        result = []
        for i, source_line in enumerate(lines):
            line_num = start_line + i + 1
            prefix = f"{line_num:4d}: "

            if line_num == line:
                marker = " " * (column + len(prefix)) + "^"
                result.append(prefix + source_line)
                result.append(marker)
            else:
                result.append(prefix + source_line)

        return "\n".join(result)

    def _get_affected_versions(self, rule: Rule) -> List[str]:
        """
        Get list of Python versions affected by this rule.

        Args:
            rule: Rule object

        Returns:
            List of version strings
        """
        source_minor = int(rule.source_version.split('.')[1])
        target_minor = int(rule.target_version.split('.')[1])

        # For now, return the target version
        # In a full implementation, this could return all intermediate versions
        return [f"3.{v}" for v in range(source_minor, target_minor + 1)]
