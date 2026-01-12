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

        # LLM validation statistics (for AST crosscheck)
        self.llm_crosscheck_enabled = False
        self.llm_crosscheck_total = 0
        self.llm_crosscheck_confirmed = 0
        self.llm_crosscheck_rejected = 0
        self.llm_crosscheck_errors = 0

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

        # Print LLM crosscheck statistics if enabled
        if self.llm_crosscheck_enabled:
            self.print_llm_crosscheck_stats()

        return issues

    def validate_issues_batch(
        self,
        issues: List[Issue],
        file_trees: Dict[str, ast.Module],
        file_source_lines: Dict[str, List[str]]
    ) -> List[Issue]:
        """
        Validate a batch of issues using LLM (Phase 2 workflow).

        This method processes all issues from Phase 1 and validates them
        with LLM in batch mode for efficiency.

        Args:
            issues: List of issues from Phase 1
            file_trees: Map of file_path -> parsed AST tree
            file_source_lines: Map of file_path -> source code lines

        Returns:
            List of validated issues with llm_validated flags set
        """
        if not self.enable_llm or not LLM_AVAILABLE:
            print("[WARNING] LLM not available for batch validation")
            return issues

        print(f"[INFO] Starting batch LLM validation of {len(issues)} issues...")

        validated_issues = []
        validated_count = 0
        confirmed_count = 0
        rejected_count = 0
        error_count = 0

        # Group issues by file for efficient processing
        issues_by_file = {}
        for issue in issues:
            if issue.file_path not in issues_by_file:
                issues_by_file[issue.file_path] = []
            issues_by_file[issue.file_path].append(issue)

        total_processed = 0

        # Process each file's issues
        for file_path, file_issues in issues_by_file.items():
            # Get AST tree and source lines for this file
            tree = file_trees.get(file_path)
            source_lines = file_source_lines.get(file_path)

            if tree is None or source_lines is None:
                # Skip files without parsed data
                print(f"[WARNING] Skipping validation for {file_path}: No AST tree available")
                # Keep issues without validation
                validated_issues.extend(file_issues)
                total_processed += len(file_issues)
                continue

            # Set context for validation
            self.file_path = file_path
            self.source_lines = source_lines

            # Validate each issue in this file
            for issue in file_issues:
                total_processed += 1

                # Find matching rule for this issue
                matching_rule = None
                for rule in self.rules:
                    if rule.id == issue.id:
                        matching_rule = rule
                        break

                if matching_rule is None:
                    # No matching rule found, keep issue as-is
                    validated_issues.append(issue)
                    continue

                # Find matching AST node for this issue
                matching_node = self._find_matching_node(
                    tree, matching_rule, issue.location.line
                )

                if matching_node is None:
                    # Couldn't find matching node, keep issue without validation
                    validated_issues.append(issue)
                    error_count += 1
                    continue

                # Validate with LLM
                try:
                    # Extract code context
                    code_snippet = self._extract_code_context(matching_node)

                    # Create validation prompt
                    prompt = self._create_validation_prompt(
                        code_snippet, matching_rule, issue
                    )

                    # Query LLM
                    from detection.llm.ollama_client import get_ollama_client
                    ollama = get_ollama_client(self.llm_config)
                    response_dict = ollama.generate(prompt)

                    # Extract response
                    if isinstance(response_dict, dict):
                        response_text = response_dict.get('response', '')
                        if not response_dict.get('success', True):
                            print(f"[WARNING] LLM request failed: {response_dict.get('error', '')}")
                            # Keep issue without validation on error
                            validated_issues.append(issue)
                            error_count += 1
                            continue
                    else:
                        response_text = str(response_dict)

                    # Parse LLM response
                    is_confirmed = self._parse_llm_validation(response_text)

                    # Update issue with LLM validation results
                    issue.llm_validated = True
                    issue.llm_confirmed = is_confirmed
                    issue.llm_explanation = response_text[:500]  # Truncate long explanations
                    issue.analysis_phase = "llm_validated"

                    validated_issues.append(issue)
                    validated_count += 1

                    if is_confirmed:
                        confirmed_count += 1
                    else:
                        rejected_count += 1

                except Exception as e:
                    print(f"[WARNING] Error validating issue {issue.id} at line {issue.location.line}: {e}")
                    # Keep issue without validation on error
                    validated_issues.append(issue)
                    error_count += 1

                # Progress update every 10 issues
                if total_processed % 10 == 0:
                    progress_pct = (total_processed / len(issues)) * 100
                    remaining = len(issues) - total_processed
                    eta_minutes = (remaining * 30.0) / 60.0  # ~30 sec per issue
                    print(f"[INFO] Validating issues: {total_processed}/{len(issues)} "
                          f"({progress_pct:.0f}%) - ETA: {eta_minutes:.0f} min")

        # Final statistics
        print(f"\n[INFO] Batch validation complete:")
        print(f"[INFO]   - Total issues: {len(issues)}")
        print(f"[INFO]   - Validated: {validated_count}")
        print(f"[INFO]   - Confirmed: {confirmed_count}")
        print(f"[INFO]   - Rejected: {rejected_count}")
        print(f"[INFO]   - Errors/Skipped: {error_count}")

        return validated_issues

    def _find_matching_node(
        self,
        tree: ast.Module,
        rule: Rule,
        target_line: int
    ) -> Optional[ast.AST]:
        """
        Find AST node matching a rule at a specific line.

        Args:
            tree: AST tree
            rule: Rule to match
            target_line: Line number to match

        Returns:
            Matching AST node or None
        """
        for node in ast.walk(tree):
            # Check if node is at target line
            if hasattr(node, 'lineno') and node.lineno == target_line:
                # Check pattern match
                if rule.pattern:
                    matcher = ASTPatternMatcher(rule.pattern)
                    if matcher.matches(node):
                        # Check condition if present
                        if rule.condition:
                            if self._evaluate_condition(node, rule.condition):
                                return node
                        else:
                            return node

        # If not found at exact line, try nearby lines (±2)
        for node in ast.walk(tree):
            if hasattr(node, 'lineno'):
                if abs(node.lineno - target_line) <= 2:
                    if rule.pattern:
                        matcher = ASTPatternMatcher(rule.pattern)
                        if matcher.matches(node):
                            if rule.condition:
                                if self._evaluate_condition(node, rule.condition):
                                    return node
                            else:
                                return node

        return None

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
        Execute a rule using standard AST pattern matching with optional LLM validation.

        Args:
            rule: Rule to execute
            tree: AST tree

        Returns:
            List of Issue objects found
        """
        # Check if LLM crosscheck is enabled for this rule
        use_llm_crosscheck = self._should_use_llm_crosscheck(rule)

        if not use_llm_crosscheck:
            # No LLM validation, use AST-only (original behavior)
            return self._execute_ast_rule_only(rule, tree)

        # LLM crosscheck is enabled
        print(f"[DEBUG] Rule {rule.id}: Using LLM crosscheck validation")

        # Step 1: AST pattern matching (find potential issues)
        potential_issues = self._execute_ast_rule_only(rule, tree)

        if not potential_issues:
            return []

        # Step 2: LLM validation (filter false positives)
        confirmed_issues = []

        for issue in potential_issues:
            print(f"[DEBUG] Validating {issue.id} at line {issue.location.line} with LLM...")

            # Find the matching node for this issue
            matching_node = None
            for node in ast.walk(tree):
                matcher = ASTPatternMatcher(rule.pattern)
                if matcher.matches(node):
                    if not rule.condition or self._evaluate_condition(node, rule.condition):
                        matching_node = node
                        break

            if matching_node is None:
                # Couldn't find matching node (shouldn't happen), skip validation
                print(f"[DEBUG]   ⚠ Could not find matching node, skipping LLM validation")
                confirmed_issues.append(issue)
                continue

            is_confirmed = self._validate_with_llm(issue, rule, matching_node)

            if is_confirmed:
                confirmed_issues.append(issue)
                print(f"[DEBUG]   ✓ CONFIRMED as real issue")
            else:
                print(f"[DEBUG]   ✗ REJECTED as false positive")

        return confirmed_issues

    def _execute_ast_rule_only(self, rule: Rule, tree: ast.Module) -> List[Issue]:
        """
        Execute a rule using standard AST pattern matching (without LLM validation).

        This is the original AST-only implementation.

        Args:
            rule: Rule to execute
            tree: AST tree

        Returns:
            List of Issue objects found (without LLM validation)
        """
        issues = []

        # Walk AST and find matches
        for node in ast.walk(tree):
            # Check pattern match
            if not rule.pattern:
                continue

            matcher = ASTPatternMatcher(rule.pattern)
            if not matcher.matches(node):
                continue

            # Check condition if present
            if rule.condition:
                if not self._evaluate_condition(node, rule.condition):
                    continue

            # All checks passed - create issue
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

        # Check 'is_importlib_method' condition
        if 'is_importlib_method' in condition:
            if condition['is_importlib_method'] and not self._is_importlib_method_context(node):
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

        # Check 'redirects_handles' condition (for subprocess handle redirection)
        if 'redirects_handles' in condition:
            if condition['redirects_handles'] and not self._redirects_handles(node):
                return False

        # Check 'mode_is_read_or_write' condition (for dbm.dumb.open)
        if 'mode_is_read_or_write' in condition:
            if condition['mode_is_read_or_write'] and not self._mode_is_read_or_write(node):
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

        # Check 'calls_method' condition (for method calls like .removeprefix(), .getchildren())
        if 'calls_method' in condition:
            method_pattern = condition['calls_method']
            if not self._calls_method_matches(node, method_pattern):
                return False

        # Check 'imports' condition (for module imports like zoneinfo, graphlib)
        if 'imports' in condition:
            module_pattern = condition['imports']
            if not self._imports_match(node, module_pattern):
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
            decorator_name: Decorator name to check (supports dotted names like 'asyncio.coroutine')

        Returns:
            True if node has the decorator
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False

        for decorator in node.decorator_list:
            # Handle simple decorator: @decorator
            if isinstance(decorator, ast.Name):
                if decorator.id == decorator_name:
                    return True

            # Handle dotted decorator: @module.decorator or @module.submodule.decorator
            elif isinstance(decorator, ast.Attribute):
                full_name = self._get_full_decorator_name(decorator)
                if full_name == decorator_name:
                    return True

            # Handle call decorators: @decorator(args)
            elif isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Name):
                    if func.id == decorator_name:
                        return True
                elif isinstance(func, ast.Attribute):
                    full_name = self._get_full_decorator_name(func)
                    if full_name == decorator_name:
                        return True

        return False

    def _get_full_decorator_name(self, decorator: ast.Attribute) -> str:
        """
        Get the full dotted name of a decorator.

        Args:
            decorator: Attribute decorator node

        Returns:
            Full dotted name (e.g., 'asyncio.coroutine')
        """
        parts = []
        current = decorator

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)
            parts.reverse()
            return '.'.join(parts)

        return ''

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
                # Try full name match first (e.g., "finder.find_module")
                if re.match(regex_pattern, func_name):
                    return True
                # For method calls, also try just the method name
                if '.' in func_name:
                    method_name = func_name.split('.')[-1]
                    return re.match(regex_pattern, method_name) is not None
                return False
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
        Check if a function definition node has the expected name,
        or if a function call node calls a function with the expected name.

        Args:
            node: AST node (FunctionDef, AsyncFunctionDef, or Call)
            expected_name: Expected function name (supports regex: prefix)

        Returns:
            True if function name matches
        """
        func_name = None

        # Handle function definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name

        # Handle function calls
        elif isinstance(node, ast.Call):
            # Get the function name from the call
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr  # For methods like obj.method()
        else:
            return False

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

    def _calls_method_matches(self, node: ast.AST, method_pattern: str) -> bool:
        """
        Check if a Call node calls a specific method.

        Args:
            node: AST node (should be a Call node)
            method_pattern: Method name pattern (supports regex: prefix and | for multiple)

        Returns:
            True if the node calls the specified method
        """
        if not isinstance(node, ast.Call):
            return False

        # Check if it's a method call (attribute access)
        func = node.func
        if not isinstance(func, ast.Attribute):
            return False

        method_name = func.attr

        # Handle regex patterns
        if method_pattern.startswith('regex:'):
            regex_pattern = method_pattern[6:]  # Remove 'regex:' prefix
            try:
                return re.match(regex_pattern, method_name) is not None
            except re.error:
                return False

        # Handle pipe-separated multiple methods (e.g., "getchildren|getiterator")
        if '|' in method_pattern:
            methods = [m.strip() for m in method_pattern.split('|')]
            return method_name in methods

        # Direct match
        return method_name == method_pattern

    def _imports_match(self, node: ast.AST, module_pattern: str) -> bool:
        """
        Check if an Import node imports a specific module.

        Args:
            node: AST node (should be an Import or ImportFrom node)
            module_pattern: Module or name pattern (supports | for multiple, regex: prefix)

        Returns:
            True if the node imports the specified module or name
        """
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            return False

        # Extract imported module names and imported names
        imported_modules = []
        imported_names = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
                imported_names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)
            for alias in node.names:
                imported_names.append(alias.name)

        # Handle regex patterns
        if module_pattern.startswith('regex:'):
            regex_pattern = module_pattern[6:]  # Remove 'regex:' prefix
            try:
                # Check both modules and imported names
                for name in imported_modules + imported_names:
                    if re.match(regex_pattern, name):
                        return True
                return False
            except re.error:
                return False

        # Handle pipe-separated multiple modules/names (e.g., "zoneinfo|graphlib")
        if '|' in module_pattern:
            items = [m.strip() for m in module_pattern.split('|')]
            return any(item in imported_modules + imported_names for item in items)

        # Direct match (check both modules and names)
        return module_pattern in imported_modules + imported_names

    def _on_thread_object(self, node: ast.AST) -> bool:
        """
        Check if a Call node is calling a method on a threading.Thread object.

        Args:
            node: AST node (should be a Call node)

        Returns:
            True if the call is on a thread object
        """
        if not isinstance(node, ast.Call):
            return False

        func = node.func
        if not isinstance(func, ast.Attribute):
            return False

        # Get the object being called
        value = func.value

        # Check if it's a variable that might be a thread
        if isinstance(value, ast.Name):
            # Could check if the variable name suggests it's a thread
            # (e.g., thread, t, etc.) but for now we just check the type
            return True  # Assume any .isAlive() call is on a thread-like object

        # Check if it's an attribute access like threading.Thread().isAlive()
        if isinstance(value, ast.Call):
            if isinstance(value.func, ast.Attribute):
                # Check if it's threading.Thread() or similar
                if hasattr(value.func, 'attr') and value.func.attr == 'Thread':
                    return True

        return False

    def _on_element_object(self, node: ast.AST) -> bool:
        """
        Check if a Call node is calling a method on an ElementTree element.

        Args:
            node: AST node (should be a Call node)

        Returns:
            True if the call is on an element object
        """
        if not isinstance(node, ast.Call):
            return False

        func = node.func
        if not isinstance(func, ast.Attribute):
            return False

        # For methods like getchildren(), getiterator()
        # Check if the object name suggests it's an element
        value = func.value
        if isinstance(value, ast.Name):
            # Check if the variable name is commonly used for elements
            element_names = ['element', 'elem', 'el', 'root', 'node', 'xml']
            return value.id.lower() in element_names

        return True  # Assume any .getchildren() or .getiterator() call is on an element

    def _in_boolean_context(self, node: ast.AST) -> bool:
        """
        Check if a node is in a boolean context (if statement, while loop, etc.).

        Args:
            node: AST node

        Returns:
            True if the node is in a boolean context
        """
        # This would require walking up the AST tree to find parent nodes
        # For now, return True as a default to avoid blocking detections
        # A more sophisticated implementation would build a parent map
        return True

    def _imported_from_module(self, node: ast.AST, module_name: str, names: str) -> bool:
        """
        Check if a Name node was imported from a specific module.

        Args:
            node: AST node (should be a Name node)
            module_name: Module name (e.g., 'ast', 'functools', 'unittest')
            names: Pipe-separated list of names to check (e.g., 'slice|Index|ExtSlice')

        Returns:
            True if the name was imported from the specified module
        """
        if not isinstance(node, ast.Name):
            return False

        name = node.id

        # Check if the name matches one of the target names
        target_names = set(n.strip() for n in names.split('|'))
        if name not in target_names:
            return False

        # Try to determine if this name was imported from the target module
        # by searching the source code for import statements
        source_lines = self.source_lines

        for line in source_lines:
            stripped = line.strip()
            # Look for: from module import name1, name2, ...
            if stripped.startswith(f'from {module_name} import'):
                # Extract imported names
                import_part = stripped[len(f'from {module_name} import'):].strip()
                # Handle multiple imports on one line
                imported_names = [n.strip() for n in import_part.split(',')]
                # Handle 'as' aliases
                for imp in imported_names:
                    actual_name = imp.split(' as ')[0].strip()
                    if actual_name in target_names:
                        return True

        return False

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

        # Special case for __complex__: any return of a Call suggests a subclass instance
        if node.name == '__complex__' and class_name == 'complex':
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
                    return True

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
            # Check for .sockets() call or .sockets.method() call
            if func.attr == 'sockets':
                # Direct call: server.sockets()
                value = func.value
                if isinstance(value, ast.Name):
                    return value.id == 'server'
                elif isinstance(value, ast.Attribute):
                    return value.attr == 'server'
            # Check for .sockets.method() call like server.sockets.append()
            elif isinstance(func.value, ast.Attribute):
                if func.value.attr == 'sockets':
                    # Check if the .sockets is on a server object
                    value = func.value.value
                    if isinstance(value, ast.Name):
                        return value.id == 'server'
                    elif isinstance(value, ast.Attribute):
                        return value.attr == 'server'

        return False

    def _redirects_handles(self, node: ast.AST) -> bool:
        """
        Check if a subprocess.Popen call redirects standard handles (stdin, stdout, stderr).

        Args:
            node: AST node (should be a Call node)

        Returns:
            True if the call redirects any standard handles
        """
        if not isinstance(node, ast.Call):
            return False

        # Check for keyword arguments that redirect handles
        for keyword in node.keywords:
            if keyword.arg in ('stdin', 'stdout', 'stderr'):
                return True

        return False

    def _mode_is_read_or_write(self, node: ast.AST) -> bool:
        """
        Check if a dbm.dumb.open() call has mode 'r' or 'w'.

        Args:
            node: AST node (should be a Call node)

        Returns:
            True if the call has mode 'r' or 'w'
        """
        if not isinstance(node, ast.Call):
            return False

        # Check for second positional argument (mode)
        if len(node.args) >= 2:
            mode_arg = node.args[1]
            if isinstance(mode_arg, ast.Constant):
                return mode_arg.value in ('r', 'w')

        # Check for mode keyword argument
        for keyword in node.keywords:
            if keyword.arg == 'mode':
                if isinstance(keyword.value, ast.Constant):
                    return keyword.value.value in ('r', 'w')

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
        if not isinstance(node, ast.Compare):
            return False

        # Check if the left side of comparison accesses .type attribute
        # This handles cases like: sock.type & ~socket.SOCK_NONBLOCK == socket.SOCK_STREAM
        def _find_type_access(n):
            """Recursively find if node accesses .type attribute."""
            if isinstance(n, ast.Attribute) and n.attr == 'type':
                return True
            if isinstance(n, ast.BinOp):
                return _find_type_access(n.left) or _find_type_access(n.right)
            if isinstance(n, ast.UnaryOp):
                return _find_type_access(n.operand)
            return False

        # Check left side of comparison
        if _find_type_access(node.left):
            return True

        # Also check comparators for direct type comparisons
        for comparator in node.comparators:
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

    def _is_importlib_method_context(self, node: ast.AST) -> bool:
        """
        Check if a Call node is calling a method on an importlib finder object.

        Args:
            node: AST node (should be a Call node)

        Returns:
            True if the call is on an importlib finder/finder object
        """
        if not isinstance(node, ast.Call):
            return False

        # Check if this is a method call like finder.find_module()
        if isinstance(node.func, ast.Attribute):
            obj = node.func.value
            # Check if the object name is 'finder' (typical importlib variable name)
            if isinstance(obj, ast.Name) and obj.id in ['finder', 'loader', 'spec']:
                return True

        return False

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

    # ========== LLM Crosscheck Methods ==========

    def enable_llm_crosscheck(self, mode: str = 'full') -> None:
        """
        Enable LLM validation for AST-detected issues.

        Args:
            mode: 'full' (validate all rules), 'conservative' (validate only problematic rules), or 'batch' (optimized batching)
        """
        if not self.enable_llm:
            raise ValueError("LLM is not enabled. Cannot use LLM crosscheck.")

        self.llm_crosscheck_enabled = True
        self.llm_crosscheck_mode = mode
        print(f"[INFO] LLM crosscheck enabled in {mode} mode")
        if mode == 'batch':
            print(f"[INFO] Optimized batch mode: ~3x faster than match-by-match validation")

    def _should_use_llm_crosscheck(self, rule: Rule) -> bool:
        """
        Determine if rule should use LLM validation based on mode.

        Args:
            rule: Rule to check

        Returns:
            True if LLM validation should be used
        """
        if not self.llm_crosscheck_enabled:
            return False

        mode = getattr(self, 'llm_crosscheck_mode', 'full')

        if mode == 'full':
            return True  # Validate all AST rules
        elif mode == 'conservative':
            # Only validate rules with known high false positive rates
            high_fp_rules = ['PY36DF08', 'PY36BC05']
            return rule.id in high_fp_rules
        else:
            return False

    def _extract_code_context(self, node: ast.AST, context_lines: int = 3) -> str:
        """
        Extract code snippet for a node with context.

        Args:
            node: AST node
            context_lines: Number of lines before/after to include

        Returns:
            Code snippet with surrounding context
        """
        if not hasattr(node, 'lineno') or node.lineno is None:
            return ""

        start_line = max(0, node.lineno - context_lines)
        end_line = min(len(self.source_lines),
                       getattr(node, 'end_lineno', node.lineno) + context_lines)

        snippet_lines = self.source_lines[start_line:end_line]
        return '\n'.join(snippet_lines)

    def _create_validation_prompt(
        self,
        code_snippet: str,
        rule: Rule,
        issue: Issue
    ) -> str:
        """
        Create LLM validation prompt.

        Args:
            code_snippet: Code to validate
            rule: The rule that triggered detection
            issue: The detected issue

        Returns:
            Formatted prompt for LLM
        """
        return f"""You are a Python compatibility expert. Your task is to validate whether a detected issue is REAL or a FALSE POSITIVE.

## Rule: {rule.name}
**Rule ID**: {rule.id}
**Category**: {rule.category}
**Severity**: {rule.severity}

## Description:
{rule.description}

## What the rule detects:
This rule checks for: {rule.description[:200]}...

## Code to validate:
```python
{code_snippet}
```

## Question:
Does this code ACTUALLY violate the rule "{rule.name}" for upgrading from Python {rule.source_version} to {rule.target_version}?

Consider:
1. Does the code match the INTENT of the rule, not just the AST pattern?
2. Is this a real compatibility issue that would cause problems?
3. Or is this a false positive where the pattern matched but the code is actually fine?

## Your Response:
Answer with ONE word on the first line:
- REAL: if the code actually violates this rule
- FALSE_POSITIVE: if the code does NOT violate this rule (pattern matched but intent is different)

Then provide a brief explanation (1-2 sentences) for your choice.
"""

    def _parse_llm_validation(self, response: str) -> bool:
        """
        Parse LLM validation response.

        Args:
            response: LLM response text

        Returns:
            True if LLM confirms it's a real issue, False if false positive
        """
        response_upper = response.strip().upper()

        # Check first line for decision
        lines = response_upper.split('\n')
        first_line = lines[0].strip() if lines else ''

        if 'FALSE_POSITIVE' in first_line or 'FALSE POSITIVE' in first_line:
            return False  # LLM says false positive
        elif 'REAL' in first_line:
            return True  # LLM says real issue
        else:
            # Ambiguous response - conservative approach
            print(f"[WARNING] Ambiguous LLM response: {first_line}")
            print(f"[WARNING] Full response: {response[:200]}")
            return True  # Conservative: report the issue

    def _validate_with_llm(
        self,
        issue: Issue,
        rule: Rule,
        node: ast.AST
    ) -> bool:
        """
        Validate an AST-detected issue using LLM.

        Args:
            issue: The detected issue
            rule: The rule that triggered detection
            node: AST node that matched pattern

        Returns:
            True if LLM confirms this is a real issue, False if it's a false positive
        """
        self.llm_crosscheck_total += 1

        try:
            # Extract code snippet with context
            code_snippet = self._extract_code_context(node)

            # Create validation prompt
            prompt = self._create_validation_prompt(code_snippet, rule, issue)

            # Import here to avoid circular dependency
            from detection.llm.ollama_client import get_ollama_client

            # Get LLM client
            ollama = get_ollama_client(self.llm_config)

            # Query LLM
            response_dict = ollama.generate(prompt)

            # Extract response text from dict
            if isinstance(response_dict, dict):
                response_text = response_dict.get('response', '')
                if response_dict.get('success', False):
                    print(f"[WARNING] LLM request failed: {response_dict.get('error', 'Unknown error')}")
                    self.llm_crosscheck_errors += 1
                    return True  # Conservative: report the issue
            else:
                response_text = response_dict if isinstance(response_dict, str) else str(response_dict)

            # Parse LLM response text
            is_real_issue = self._parse_llm_validation(response_text)

            # Track statistics
            if is_real_issue:
                self.llm_crosscheck_confirmed += 1
            else:
                self.llm_crosscheck_rejected += 1

            return is_real_issue

        except Exception as e:
            print(f"[WARNING] LLM validation failed for {issue.id} at line {issue.location.line}: {e}")
            self.llm_crosscheck_errors += 1
            # On error, conservatively report the issue
            return True

    def print_llm_crosscheck_stats(self):
        """Print LLM crosscheck statistics."""
        if self.llm_crosscheck_total == 0:
            return

        print(f"\n{'='*70}")
        print("LLM Crosscheck Statistics")
        print(f"{'='*70}")
        print(f"Validations: {self.llm_crosscheck_total}")
        print(f"Confirmed (Real Issues): {self.llm_crosscheck_confirmed} ({self.llm_crosscheck_confirmed/max(self.llm_crosscheck_total,1)*100:.1f}%)")
        print(f"Rejected (False Positives): {self.llm_crosscheck_rejected} ({self.llm_crosscheck_rejected/max(self.llm_crosscheck_total,1)*100:.1f}%)")
        print(f"Errors: {self.llm_crosscheck_errors}")
        if self.llm_crosscheck_confirmed + self.llm_crosscheck_rejected > 0:
            fp_rate = self.llm_crosscheck_rejected / (self.llm_crosscheck_confirmed + self.llm_crosscheck_rejected) * 100
            print(f"False Positive Reduction: {fp_rate:.1f}%")
        print(f"{'='*70}\n")

