"""
Rule executor for applying rules against AST nodes.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Tuple
from packaging import version

from reporting.data_models import Issue, Location, Severity, Category, RiskLevel
from rules.rule_loader import Rule
from detection.ast_pattern_matcher import ASTPatternMatcher

# Import LLM detection components
try:
    from detection.llm import create_llm_detector, OllamaConfig
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    create_llm_detector = None
    OllamaConfig = None


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
        source_version: str = "3.6",
        enable_llm: bool = True,
        llm_config: Optional[Any] = None
    ):
        """
        Initialize rule executor.

        Args:
            rules: List of Rule objects to execute
            target_version: Target Python version
            source_version: Source Python version
            enable_llm: Whether to enable LLM detection (default: True)
            llm_config: Optional Ollama configuration
        """
        self.rules = rules
        self.target_version = target_version
        self.source_version = source_version
        self.file_path: str = ""
        self.source_lines: List[str] = []

        # LLM detection settings
        self.enable_llm = enable_llm and LLM_AVAILABLE
        self.llm_config = llm_config

        # Statistics
        self.llm_detections = 0
        self.llm_validations = 0
        self.llm_skipped = 0

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

        # Deduplicate issues by (rule_id, line, column)
        issues = self._deduplicate_issues(issues)

        return issues

    def _deduplicate_issues(self, issues: List[Issue]) -> List[Issue]:
        """
        Remove duplicate issues (same rule, line, and column).

        Args:
            issues: List of issues

        Returns:
            Deduplicated list of issues
        """
        seen: set[Tuple[str, int, int]] = set()
        unique_issues: List[Issue] = []

        for issue in issues:
            key = (issue.id, issue.location.line, issue.location.column)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues

    def execute_rule(self, rule: Rule, tree: ast.Module) -> List[Issue]:
        """
        Execute a single rule against an AST tree.

        Args:
            rule: Rule to execute
            tree: AST tree

        Returns:
            List of Issue objects found
        """
        # Check if this rule requires LLM detection
        detection_strategy = self._get_detection_strategy(rule)

        if detection_strategy in ['hybrid', 'text'] and self.enable_llm:
            # Use LLM-based detection
            return self._execute_llm_rule(rule, tree)
        else:
            # Use standard AST-based detection
            return self._execute_ast_rule(rule, tree)

    def _get_detection_strategy(self, rule: Rule) -> str:
        """Get detection strategy from rule metadata."""
        # Check if rule has detection metadata
        if hasattr(rule, 'raw_data'):
            detection = rule.raw_data.get('detection', {})
            return detection.get('strategy', 'ast')
        return 'ast'

    def _execute_llm_rule(self, rule: Rule, tree: ast.Module) -> List[Issue]:
        """
        Execute a rule using LLM detection.

        Args:
            rule: Rule to execute
            tree: AST tree

        Returns:
            List of Issue objects found
        """
        if not LLM_AVAILABLE:
            self.llm_skipped += 1
            print(f"[DEBUG] LLM not available for rule {rule.id}, falling back to AST")
            # Fall back to AST-only detection
            return self._execute_ast_rule(rule, tree)

        try:
            print(f"[DEBUG] Executing LLM rule: {rule.id} - {rule.name}")

            # Create LLM detector from rule
            detector = create_llm_detector(rule.raw_data, self.llm_config)

            if detector is None:
                # No LLM detector created, fall back to AST
                return self._execute_ast_rule(rule, tree)

            # Set context for detector
            detector.source_lines = self.source_lines
            detector.file_path = self.file_path

            # Execute LLM detection
            issues = detector.detect(tree, self.file_path)

            # Track statistics
            if issues:
                self.llm_detections += len(issues)
            self.llm_validations += 1

            return issues

        except Exception as e:
            print(f"[WARNING] LLM detection failed for rule {rule.id}: {e}")
            self.llm_skipped += 1
            # Fall back to AST-only detection
            return self._execute_ast_rule(rule, tree)

    def _execute_ast_rule(self, rule: Rule, tree: ast.Module) -> List[Issue]:
        """
        Execute a rule using standard AST pattern matching.

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

        # Check 'func_is' condition (for function/method calls)
        if 'func_is' in condition:
            func_pattern = condition['func_is']
            if not self._func_matches(node, func_pattern):
                return False

        # Check 'is_async' condition
        if 'is_async' in condition:
            is_async = condition['is_async']
            if is_async and not isinstance(node, ast.AsyncFunctionDef):
                return False
            if not is_async and isinstance(node, ast.AsyncFunctionDef):
                return False

        # Check 'function_name' or 'func_name' condition
        if 'function_name' in condition or 'func_name' in condition:
            expected_name = condition.get('function_name') or condition.get('func_name')
            if not self._function_name_matches(node, expected_name):
                return False

        # Check 'has_kwarg' condition
        if 'has_kwarg' in condition:
            kwarg_name = condition['has_kwarg']
            if not self._has_kwarg(node, kwarg_name):
                return False

        # Check 'has_keyword_args' condition
        if 'has_keyword_args' in condition:
            has_kwargs = condition['has_keyword_args']
            if has_kwargs and not self._has_any_keyword_args(node):
                return False
            if not has_kwargs and self._has_any_keyword_args(node):
                return False

        # Check 'first_arg_is_keyword' condition
        if 'first_arg_is_keyword' in condition:
            if condition['first_arg_is_keyword'] and not self._first_arg_is_keyword(node):
                return False

        # Check 'contains' condition (for string matching in code)
        if 'contains' in condition:
            if not self._contains_string(node, condition['contains']):
                return False

        # Check 'contains_yield' condition
        if 'contains_yield' in condition:
            if condition['contains_yield'] and not self._contains_yield(node):
                return False

        # Check 'contains_await_or_async_for' condition
        if 'contains_await_or_async_for' in condition:
            if condition['contains_await_or_async_for'] and not self._contains_await_or_async_for(node):
                return False

        # Check 'returns_subclass_of' condition
        if 'returns_subclass_of' in condition:
            class_name = condition['returns_subclass_of']
            if not self._returns_subclass_of(node, class_name):
                return False

        # Check 'calls_isascii' condition
        if 'calls_isascii' in condition:
            if condition['calls_isascii'] and not self._calls_isascii(node):
                return False

        # Check 'accesses_server_sockets' condition
        if 'accesses_server_sockets' in condition:
            cond_value = condition['accesses_server_sockets']
            # Handle both boolean and string format
            should_access = cond_value if isinstance(cond_value, bool) else True
            if should_access and not self._accesses_server_sockets(node):
                return False

        # Check 'is_async_function' condition
        if 'is_async_function' in condition:
            if condition['is_async_function'] and not isinstance(node, ast.AsyncFunctionDef):
                return False

        # Check 'raises_stopiteration' condition
        if 'raises_stopiteration' in condition:
            if condition['raises_stopiteration'] and not self._raises_stopiteration(node):
                return False

        # Check 'not_awaited' condition
        if 'not_awaited' in condition:
            if condition['not_awaited'] and not self._is_not_awaited(node):
                return False

        # Check 'compares_socket_type' condition
        if 'compares_socket_type' in condition:
            if condition['compares_socket_type'] and not self._compares_socket_type(node):
                return False

        # Check 'depends_on_inherited_handles' condition
        if 'depends_on_inherited_handles' in condition:
            if condition['depends_on_inherited_handles'] and not self._depends_on_inherited_handles(node):
                return False

        # Check 'used_as_identifier' condition
        if 'used_as_identifier' in condition:
            if condition['used_as_identifier'] and not self._used_as_identifier(node):
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

    def _func_matches(self, node: ast.AST, func_pattern: str) -> bool:
        """
        Check if a Call node's function matches a pattern.

        Args:
            node: AST node (should be a Call node)
            func_pattern: Function pattern (supports regex: prefix)

        Returns:
            True if function matches the pattern
        """
        # Only applicable to Call nodes
        if not isinstance(node, ast.Call):
            return False

        # Extract function name
        func_name = self._get_function_name(node)
        if not func_name:
            return False

        # Handle regex patterns
        if func_pattern.startswith('regex:'):
            regex_pattern = func_pattern[6:]  # Remove 'regex:' prefix
            try:
                return re.match(regex_pattern, func_name) is not None
            except re.error:
                return False

        # Direct string match
        return func_name == func_pattern

    def _get_function_name(self, node: ast.Call) -> Optional[str]:
        """
        Get the full name of a function call.

        Args:
            node: Call AST node

        Returns:
            Function name as string (e.g., "time.sleep", "asyncio.run")
        """
        func = node.func

        # Simple name: foo()
        if isinstance(func, ast.Name):
            return func.id

        # Attribute: foo.bar()
        if isinstance(func, ast.Attribute):
            parts = []
            current = func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                parts.reverse()
                return '.'.join(parts)

        return None

    def _function_name_matches(self, node: ast.AST, expected_name: str) -> bool:
        """
        Check if a function definition node has the expected name.

        Args:
            node: AST node
            expected_name: Expected function name (supports regex: prefix)

        Returns:
            True if function name matches
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False

        func_name = node.name

        # Handle regex patterns
        if expected_name.startswith('regex:'):
            regex_pattern = expected_name[6:]  # Remove 'regex:' prefix
            try:
                return re.match(regex_pattern, func_name) is not None
            except re.error:
                return False

        return func_name == expected_name

    def _has_kwarg(self, node: ast.AST, kwarg_name: str) -> bool:
        """
        Check if a Call node has a specific keyword argument.

        Args:
            node: AST node
            kwarg_name: Keyword argument name to check

        Returns:
            True if the call has the specified keyword argument
        """
        if not isinstance(node, ast.Call):
            return False

        for keyword in node.keywords:
            if keyword.arg == kwarg_name:
                return True

        return False

    def _has_any_keyword_args(self, node: ast.AST) -> bool:
        """
        Check if a Call node has any keyword arguments.

        Args:
            node: AST node

        Returns:
            True if the call has keyword arguments
        """
        if not isinstance(node, ast.Call):
            return False

        return len(node.keywords) > 0

    def _first_arg_is_keyword(self, node: ast.AST) -> bool:
        """
        Check if the first argument of a Call node is a keyword argument.

        Args:
            node: AST node

        Returns:
            True if the first argument is a keyword
        """
        if not isinstance(node, ast.Call):
            return False

        # Check if there's a keyword argument and it's the first one
        if node.keywords and len(node.args) == 0:
            return True

        return False

    def _contains_string(self, node: ast.AST, search_string: str) -> bool:
        """
        Check if the source code for a node contains a specific string.

        Args:
            node: AST node
            search_string: String to search for

        Returns:
            True if the source contains the string
        """
        # Get source lines for the node
        if not self.source_lines:
            return False

        start_line = getattr(node, 'lineno', 1) - 1
        end_line = getattr(node, 'end_lineno', start_line + 1)

        if start_line >= len(self.source_lines):
            return False

        end_line = min(end_line, len(self.source_lines))

        for i in range(start_line, end_line):
            if search_string in self.source_lines[i]:
                return True

        return False

    def _contains_yield(self, node: ast.AST) -> bool:
        """
        Check if a comprehension contains a yield expression.

        Args:
            node: AST node (should be a comprehension)

        Returns:
            True if the comprehension contains yield
        """
        if not isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return False

        # Walk the comprehension's generators and value
        for child in ast.walk(node):
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                return True

        return False

    def _contains_await_or_async_for(self, node: ast.AST) -> bool:
        """
        Check if an f-string contains await or async for.

        Note: Python's AST doesn't directly expose f-string content
        in a way that makes this easy to detect. This is a simplified
        check that looks for these patterns in the source.

        Args:
            node: AST node (should be JoinedStr for f-strings)

        Returns:
            True if the f-string contains await or async for
        """
        if not isinstance(node, ast.JoinedStr):
            return False

        return self._contains_string(node, 'await') or self._contains_string(node, 'async')

    def _returns_subclass_of(self, node: ast.AST, class_name: str) -> bool:
        """
        Check if a function returns a subclass of a specific class.

        Args:
            node: AST node (should be a FunctionDef)
            class_name: Name of the base class

        Returns:
            True if the function returns a subclass of the specified class
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False

        # Walk the function body to find return statements
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                # Check if the return value is a Call that instantiates a class
                if isinstance(child.value, ast.Call):
                    func = child.value.func
                    if isinstance(func, ast.Name):
                        # Simple: return MyClass()
                        if func.id == class_name:
                            return True
                    elif isinstance(func, ast.Attribute):
                        # Check for module.Class()
                        if func.attr == class_name:
                            return True

        return False

    def _calls_isascii(self, node: ast.AST) -> bool:
        """
        Check if a Call node calls the isascii() method.

        Args:
            node: AST node

        Returns:
            True if the node is a call to .isascii()
        """
        if not isinstance(node, ast.Call):
            return False

        func = node.func
        if isinstance(func, ast.Attribute):
            return func.attr == 'isascii'

        return False

    def _accesses_server_sockets(self, node: ast.AST) -> bool:
        """
        Check if a Call node accesses asyncio.Server.sockets.

        Args:
            node: AST node

        Returns:
            True if the node accesses server.sockets
        """
        if not isinstance(node, ast.Call):
            return False

        func = node.func
        if isinstance(func, ast.Attribute):
            # Check for .sockets() call
            if func.attr == 'sockets':
                # Check if it's called on something that might be a server
                value = func.value
                if isinstance(value, ast.Name):
                    return value.id == 'server'
                elif isinstance(value, ast.Attribute):
                    return value.attr == 'server'

        return False

    def _raises_stopiteration(self, node: ast.AST) -> bool:
        """
        Check if a function raises StopIteration.

        Args:
            node: AST node

        Returns:
            True if the function raises StopIteration
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False

        # Walk the function body to find raise statements
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc is not None:
                    # Check if it raises StopIteration
                    if isinstance(child.exc, ast.Name):
                        if child.exc.id == 'StopIteration':
                            return True
                    elif isinstance(child.exc, ast.Call):
                        func = child.exc.func
                        if isinstance(func, ast.Name):
                            if func.id == 'StopIteration':
                                return True

        return False

    def _is_not_awaited(self, node: ast.AST) -> bool:
        """
        Check if a Call node is not awaited.

        Args:
            node: AST node

        Returns:
            True if the call is not awaited
        """
        if not isinstance(node, ast.Call):
            return False

        # Check if this node is a child of an Await node
        # This is a simplified check - a proper implementation would
        # need to walk up the parent chain
        return True

    def _compares_socket_type(self, node: ast.AST) -> bool:
        """
        Check if a node compares socket.type.

        Args:
            node: AST node

        Returns:
            True if the node accesses socket.type
        """
        # Walk the node to find attribute access to 'type'
        for child in ast.walk(node):
            if isinstance(child, ast.Compare):
                for comparator in child.comparators:
                    if isinstance(comparator, ast.Attribute):
                        if comparator.attr == 'type':
                            return True

        return False

    def _depends_on_inherited_handles(self, node: ast.AST) -> bool:
        """
        Check if a function uses inherited handles.

        Args:
            node: AST node

        Returns:
            True if the function uses inherited handles
        """
        # This is a simplified check
        # A full implementation would need to check for specific
        # Windows API calls related to handle inheritance
        return False

    def _used_as_identifier(self, node: ast.AST) -> bool:
        """
        Check if a Name node is used as an identifier (variable/function name).

        Args:
            node: AST node

        Returns:
            True if the name is used as an identifier
        """
        if not isinstance(node, ast.Name):
            return False

        # A name is used as an identifier if it's in a position where
        # a variable/parameter/function name would appear
        # This is a simplified check - a full implementation would need
        # to check the parent context
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

    def _get_code_snippet(self, line: int, column: int, context_lines: int = 1) -> str:
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
