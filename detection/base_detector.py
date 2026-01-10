"""
Base detector class for all compatibility issue detectors.
"""

from abc import ABC, abstractmethod
import ast
from typing import List, Dict, Any, Optional

from reporting.data_models import Issue, Location, Severity, Category, RiskLevel


class BaseDetector(ABC):
    """
    Abstract base class for all compatibility issue detectors.

    All detectors must inherit from this class and implement the detect() method.
    """

    def __init__(
        self,
        target_version: str,
        source_version: str = "3.6"
    ):
        """
        Initialize detector.

        Args:
            target_version: Target Python version (e.g., "3.12")
            source_version: Source Python version (e.g., "3.6")
        """
        self.target_version = target_version
        self.source_version = source_version
        self.file_path: str = ""
        self.source_lines: List[str] = []
        self.parent_map: Dict[ast.AST, ast.AST] = {}

    @abstractmethod
    def detect(self, node: ast.AST, file_path: str) -> List[Issue]:
        """
        Detect compatibility issues in an AST node.

        Args:
            node: AST node to analyze
            file_path: Path to the source file

        Returns:
            List of Issue objects found
        """
        pass

    def get_issue_type(self) -> str:
        """
        Get the type/category of issues this detector finds.

        Returns:
            Issue category string
        """
        return Category.DEPRECATION.value

    def get_severity(self) -> str:
        """
        Get the default severity for issues this detector finds.

        Returns:
            Severity level string
        """
        return Severity.MEDIUM.value

    def get_risk_level(self) -> str:
        """
        Get the default risk level for issues this detector finds.

        Returns:
            Risk level string (HIGH/MEDIUM/LOW)
        """
        return RiskLevel.MEDIUM.value

    def set_context(self, file_path: str, source_lines: List[str]):
        """
        Set context for detection.

        Args:
            file_path: Path to the source file
            source_lines: Source code lines
        """
        self.file_path = file_path
        self.source_lines = source_lines

    def build_parent_map(self, tree: ast.Module):
        """
        Build a map of AST nodes to their parent nodes.

        Args:
            tree: AST module
        """
        self.parent_map = {}

        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parent_map[child] = parent

    def get_parent(self, node: ast.AST) -> Optional[ast.AST]:
        """
        Get parent of an AST node.

        Args:
            node: AST node

        Returns:
            Parent node or None
        """
        return self.parent_map.get(node)

    def get_code_snippet(
        self,
        line: int,
        column: int,
        context_lines: int = 1
    ) -> str:
        """
        Extract code snippet around a location.

        Args:
            line: Line number (1-indexed)
            column: Column number (0-indexed)
            context_lines: Number of lines to include before and after

        Returns:
            Code snippet with marker
        """
        if not self.source_lines:
            return ""

        # Convert to 0-indexed
        line_idx = line - 1

        # Calculate range
        start_line = max(0, line_idx - context_lines)
        end_line = min(len(self.source_lines), line_idx + context_lines + 1)

        # Extract lines
        lines = self.source_lines[start_line:end_line]

        # Add line numbers
        result = []
        for i, source_line in enumerate(lines):
            line_num = start_line + i + 1
            prefix = f"{line_num:4d}: "

            if line_num == line:
                # Add marker for the target line
                marker = " " * (column + len(prefix)) + "^"
                result.append(prefix + source_line)
                result.append(marker)
            else:
                result.append(prefix + source_line)

        return "\n".join(result)

    def create_issue(
        self,
        rule_id: str,
        node: ast.AST,
        message: str,
        suggestion: str,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        risk_level: Optional[str] = None,
        references: Optional[List[str]] = None
    ) -> Issue:
        """
        Create an Issue object from an AST node.

        Args:
            rule_id: Unique rule identifier
            node: AST node where issue was found
            message: Issue message
            suggestion: Suggested fix
            severity: Override default severity
            category: Override default category
            risk_level: Override default risk level
            references: List of reference URLs

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
        code_snippet = self.get_code_snippet(line, column)

        # Use defaults if not specified
        if severity is None:
            severity = self.get_severity()
        if category is None:
            category = self.get_issue_type()
        if risk_level is None:
            risk_level = self.get_risk_level()
        if references is None:
            references = []

        return Issue(
            id=rule_id,
            file_path=self.file_path,
            location=location,
            severity=severity,
            category=category,
            risk_level=risk_level,
            message=message,
            suggestion=suggestion,
            code_snippet=code_snippet,
            affected_versions=[self.target_version],
            references=references
        )

    def is_node_type(self, node: ast.AST, *types) -> bool:
        """
        Check if node is one of the specified types.

        Args:
            node: AST node
            *types: AST node types to check

        Returns:
            True if node is one of the types
        """
        return any(isinstance(node, t) for t in types)

    def get_node_name(self, node: ast.AST) -> Optional[str]:
        """
        Get the name of an AST node.

        Args:
            node: AST node

        Returns:
            Node name or None
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.FunctionDef):
            return node.name
        elif isinstance(node, ast.ClassDef):
            return node.name
        elif isinstance(node, ast.AsyncFunctionDef):
            return node.name
        return None
