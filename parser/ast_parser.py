"""
AST Parser for Python source code.
Handles parsing, syntax error capture, and encoding validation.
"""

import ast
import os
from typing import Optional, List, Tuple
from dataclasses import dataclass

from reporting.data_models import Issue, Location, Severity, Category, RiskLevel


@dataclass
class ParseResult:
    """Result of AST parsing."""
    tree: Optional[ast.Module]
    syntax_error: Optional[SyntaxError]
    source_lines: List[str]
    encoding: str

    @property
    def has_syntax_error(self) -> bool:
        """Check if parsing resulted in a syntax error."""
        return self.syntax_error is not None


class ASTParser:
    """
    Parse Python source code into AST.

    Handles:
    - Syntax error capture
    - Encoding validation
    - File size limits
    - Source code extraction for snippets
    """

    # Maximum file size to parse (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Default encoding
    DEFAULT_ENCODING = 'utf-8'

    def __init__(self, file_path: str, encoding: str = DEFAULT_ENCODING):
        """
        Initialize AST parser.

        Args:
            file_path: Path to Python source file
            encoding: File encoding (default: utf-8)
        """
        self.file_path = file_path
        self.encoding = encoding
        self.source_lines: List[str] = []

    def parse(self) -> ParseResult:
        """
        Parse Python source file into AST.

        Returns:
            ParseResult containing AST tree or syntax error
        """
        # Check file exists
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        # Check file size
        file_size = os.path.getsize(self.file_path)
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_size} bytes "
                f"(max: {self.MAX_FILE_SIZE} bytes)"
            )

        # Read source code
        try:
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                source = f.read()
            self.source_lines = source.splitlines()
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Encoding error in {self.file_path}: {e}. "
                f"Ensure file is {self.encoding} encoded."
            )
        except Exception as e:
            raise IOError(f"Error reading {self.file_path}: {e}")

        # Parse AST
        try:
            tree = ast.parse(source, filename=self.file_path)
            return ParseResult(
                tree=tree,
                syntax_error=None,
                source_lines=self.source_lines,
                encoding=self.encoding
            )
        except SyntaxError as e:
            return ParseResult(
                tree=None,
                syntax_error=e,
                source_lines=self.source_lines,
                encoding=self.encoding
            )
        except Exception as e:
            # Other parsing errors
            return ParseResult(
                tree=None,
                syntax_error=SyntaxError(
                    f"Parse error: {str(e)}",
                    (),
                    self.file_path,
                    0,
                    0,
                    None
                ),
                source_lines=self.source_lines,
                encoding=self.encoding
            )

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

    def get_node_text(self, node: ast.AST) -> str:
        """
        Extract source text for an AST node.

        Args:
            node: AST node

        Returns:
            Source text for the node
        """
        if not hasattr(node, 'lineno') or not self.source_lines:
            return ""

        try:
            line_idx = node.lineno - 1
            col_offset = getattr(node, 'col_offset', 0)

            if node.end_lineno and node.end_col_offset:
                # Multi-line node
                end_line_idx = node.end_lineno - 1

                if line_idx == end_line_idx:
                    # Single line
                    line = self.source_lines[line_idx]
                    return line[col_offset:node.end_col_offset]
                else:
                    # Multi-line
                    lines = []
                    # First line
                    lines.append(self.source_lines[line_idx][col_offset:])
                    # Middle lines
                    for i in range(line_idx + 1, end_line_idx):
                        lines.append(self.source_lines[i])
                    # Last line
                    lines.append(self.source_lines[end_line_idx][:node.end_col_offset])
                    return "\n".join(lines)
            else:
                # Single line without end info
                line = self.source_lines[line_idx]
                return line[col_offset:]
        except (IndexError, AttributeError):
            return ""


def is_syntax_compatible_with_version(
    syntax_error: SyntaxError,
    target_version: str
) -> bool:
    """
    Check if a syntax error is compatible with target Python version.

    Some syntax errors in older versions are valid in newer versions.
    For example:
    - Walrus operator := is syntax error in 3.7, valid in 3.8+
    - Match statement is syntax error in 3.9, valid in 3.10+
    - Exception groups are syntax error in 3.10, valid in 3.11+

    Args:
        syntax_error: The syntax error to check
        target_version: Target Python version (e.g., "3.12")

    Returns:
        True if syntax is valid in target version
    """
    from packaging import version

    error_text = str(syntax_error).lower()

    # Walrus operator := (Python 3.8+)
    if ":=" in error_text or "walrus" in error_text:
        return version.parse(target_version) >= version.parse("3.8")

    # Match/Case statement (Python 3.10+)
    if "match" in error_text or "case" in error_text:
        return version.parse(target_version) >= version.parse("3.10")

    # Exception groups (Python 3.11+)
    if "exceptiongroup" in error_text or "exception*" in error_text:
        return version.parse(target_version) >= version.parse("3.11")

    # Type parameter syntax (Python 3.12+)
    if "type " in error_text and "[" in error_text:
        return version.parse(target_version) >= version.parse("3.12")

    # Default to not compatible
    return False


def syntax_error_to_issue(
    syntax_error: SyntaxError,
    file_path: str,
    target_version: str,
    parser: ASTParser
) -> Issue:
    """
    Convert syntax error to Issue object.

    Args:
        syntax_error: The syntax error
        file_path: Path to the file
        target_version: Target Python version
        parser: ASTParser instance for code snippet extraction

    Returns:
        Issue object representing the syntax error
    """
    # Check if error is version-specific
    is_future_compatible = is_syntax_compatible_with_version(syntax_error, target_version)

    if is_future_compatible:
        severity = Severity.MEDIUM.value
        category = Category.SYNTAX_ERROR.value
        risk_level = RiskLevel.MEDIUM.value
        message = (
            f"Syntax error in current version, but valid in Python {target_version}. "
            f"This code will work after upgrade."
        )
    else:
        severity = Severity.CRITICAL.value
        category = Category.SYNTAX_ERROR.value
        risk_level = RiskLevel.HIGH.value
        message = (
            f"Syntax error that will persist in Python {target_version}. "
            f"This code must be fixed manually."
        )

    # Get code snippet
    line = syntax_error.lineno or 1
    column = syntax_error.offset or 0

    snippet = parser.get_code_snippet(line, column, context_lines=2)

    # Create suggestion
    error_text = str(syntax_error)
    suggestion = f"Fix the syntax error: {error_text}"

    return Issue(
        id=f"SYNTAX_{line}_{column}",
        file_path=file_path,
        location=Location(line=line, column=column),
        severity=severity,
        category=category,
        risk_level=risk_level,
        message=message,
        suggestion=suggestion,
        code_snippet=snippet,
        affected_versions=[target_version],
        references=[]
    )
