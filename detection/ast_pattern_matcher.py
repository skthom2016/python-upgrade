"""
AST pattern matching engine for detecting compatibility issues.
"""

import ast
from typing import Dict, Any, List, Optional, Callable


class ASTPatternMatcher:
    """
    Pattern matching engine for AST nodes.

    Supports:
    - Node type matching
    - Attribute matching
    - Children matching
    - Conditional matching
    - Wildcard matching
    """

    def __init__(self, pattern: Dict[str, Any]):
        """
        Initialize pattern matcher.

        Args:
            pattern: Pattern dictionary to match against
        """
        self.pattern = pattern

    def matches(self, node: ast.AST) -> bool:
        """
        Check if an AST node matches the pattern.

        Args:
            node: AST node to check

        Returns:
            True if node matches pattern
        """
        if not isinstance(node, ast.AST):
            return False

        # Match node type
        if 'node_type' in self.pattern:
            if not self._match_node_type(node, self.pattern['node_type']):
                return False

        # Match attributes
        if 'attributes' in self.pattern:
            if not self._match_attributes(node, self.pattern['attributes']):
                return False

        # Match children
        if 'children' in self.pattern:
            if not self._match_children(node, self.pattern['children']):
                return False

        # Match condition
        if 'condition' in self.pattern:
            if not self._match_condition(node, self.pattern['condition']):
                return False

        return True

    def _match_node_type(self, node: ast.AST, node_type: str) -> bool:
        """
        Match AST node type.

        Args:
            node: AST node
            node_type: Expected node type (string), supports multiple types separated by |

        Returns:
            True if node type matches
        """
        # Handle multiple node types (e.g., "FunctionDef|AsyncFunctionDef")
        if '|' in node_type:
            node_types = node_type.split('|')
            for nt in node_types:
                nt = nt.strip()
                try:
                    ast_class = getattr(ast, nt)
                    if isinstance(node, ast_class):
                        return True
                except AttributeError:
                    continue
            return False

        # Single node type
        try:
            ast_class = getattr(ast, node_type)
            return isinstance(node, ast_class)
        except AttributeError:
            return False

    def _match_attributes(self, node: ast.AST, attributes: Dict[str, Any]) -> bool:
        """
        Match node attributes.

        Args:
            node: AST node
            attributes: Dictionary of attribute names and expected values

        Returns:
            True if all attributes match
        """
        for attr_name, expected_value in attributes.items():
            if not hasattr(node, attr_name):
                return False

            actual_value = getattr(node, attr_name)

            # Handle wildcard values
            if expected_value == '*':
                continue

            # Handle regex patterns
            if isinstance(expected_value, str) and expected_value.startswith('regex:'):
                import re
                pattern = expected_value[6:]  # Remove 'regex:' prefix
                if not isinstance(actual_value, str):
                    return False
                if not re.match(pattern, actual_value):
                    return False
                continue

            # Handle list containment
            if isinstance(expected_value, list) and isinstance(actual_value, list):
                if set(expected_value) != set(actual_value):
                    return False
                continue

            # Handle callable (custom matcher)
            if callable(expected_value):
                if not expected_value(actual_value):
                    return False
                continue

            # Direct comparison
            if actual_value != expected_value:
                return False

        return True

    def _match_children(self, node: ast.AST, children: Dict[str, Any]) -> bool:
        """
        Match node children.

        Args:
            node: AST node
            children: Dictionary of child names and their patterns

        Returns:
            True if all children match
        """
        for child_name, child_pattern in children.items():
            if not hasattr(node, child_name):
                return False

            child = getattr(node, child_name)

            # Handle list of children (e.g., body)
            if isinstance(child, list):
                if isinstance(child_pattern, list):
                    # Match list of patterns
                    if len(child) != len(child_pattern):
                        return False
                    for child_node, pattern in zip(child, child_pattern):
                        matcher = ASTPatternMatcher(pattern)
                        if not matcher.matches(child_node):
                            return False
                elif isinstance(child_pattern, dict):
                    # Match at least one child in the list
                    found = False
                    for child_node in child:
                        matcher = ASTPatternMatcher(child_pattern)
                        if matcher.matches(child_node):
                            found = True
                            break
                    if not found:
                        return False
                else:
                    return False

            # Handle single child (AST node)
            elif isinstance(child, ast.AST):
                if isinstance(child_pattern, dict):
                    matcher = ASTPatternMatcher(child_pattern)
                    if not matcher.matches(child):
                        return False
                else:
                    return False

            # Handle scalar values (strings, numbers, booleans)
            # This is needed for matching attributes like 'attr' in Attribute nodes
            elif isinstance(child, (str, int, float, bool)) or child is None:
                if isinstance(child_pattern, dict):
                    # Pattern is a dict, but child is scalar - doesn't match
                    return False
                else:
                    # Direct comparison for scalar values
                    if child != child_pattern:
                        return False

            else:
                return False

        return True

    def _match_condition(self, node: ast.AST, condition: Any) -> bool:
        """
        Match custom condition.

        Args:
            node: AST node
            condition: Condition (callable or string)

        Returns:
            True if condition is satisfied
        """
        if callable(condition):
            return condition(node)

        # Handle predefined conditions
        if isinstance(condition, str):
            return self._check_predefined_condition(node, condition)

        return False

    def _check_predefined_condition(self, node: ast.AST, condition: str) -> bool:
        """
        Check predefined condition.

        Args:
            node: AST node
            condition: Condition string

        Returns:
            True if condition is satisfied
        """
        # Has decorator
        if condition.startswith('has_decorator:'):
            decorator_name = condition.split(':', 1)[1]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return any(
                    self._get_decorator_name(d) == decorator_name
                    for d in node.decorator_list
                )
            return False

        # In function
        if condition == 'in_function':
            return isinstance(node, ast.stmt) and hasattr(node, 'lineno')

        # Is async
        if condition == 'is_async':
            return isinstance(node, (ast.AsyncFor, ast.AsyncWith, ast.AsyncFunctionDef))

        return False

    def _get_decorator_name(self, decorator: ast.expr) -> Optional[str]:
        """
        Get decorator name.

        Args:
            decorator: Decorator node

        Returns:
            Decorator name or None
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        return None


class PatternBuilder:
    """
    Builder for creating AST patterns.
    """

    @staticmethod
    def node_type(node_type: str) -> Dict[str, Any]:
        """Create a pattern that matches node type."""
        return {'node_type': node_type}

    @staticmethod
    def import_node(module_name: str) -> Dict[str, Any]:
        """Create a pattern for import statement."""
        return {
            'node_type': 'Import',
            'attributes': {},
            'children': {
                'names': [
                    {
                        'node_type': 'alias',
                        'attributes': {'name': module_name}
                    }
                ]
            }
        }

    @staticmethod
    def import_from_node(module_name: str, name: str = '*') -> Dict[str, Any]:
        """Create a pattern for from...import statement."""
        return {
            'node_type': 'ImportFrom',
            'attributes': {'module': module_name},
            'children': {
                'names': [
                    {
                        'node_type': 'alias',
                        'attributes': {'name': name}
                    }
                ]
            }
        }

    @staticmethod
    def function_call(func_name: str) -> Dict[str, Any]:
        """Create a pattern for function call."""
        return {
            'node_type': 'Call',
            'children': {
                'func': {
                    'node_type': 'Name',
                    'attributes': {'id': func_name}
                }
            }
        }

    @staticmethod
    def name_node(name: str) -> Dict[str, Any]:
        """Create a pattern for name node."""
        return {
            'node_type': 'Name',
            'attributes': {'id': name}
        }

    @staticmethod
    def attribute_chain(*attrs: str) -> Dict[str, Any]:
        """
        Create a pattern for attribute access chain.

        Example: attribute_chain('os', 'path', 'join')
        Matches: os.path.join
        """
        if not attrs:
            return {}

        # Build nested pattern from right to left
        pattern = {
            'node_type': 'Name',
            'attributes': {'id': attrs[-1]}
        }

        for attr in reversed(attrs[:-1]):
            pattern = {
                'node_type': 'Attribute',
                'attributes': {'attr': attr},
                'children': {
                    'value': pattern
                }
            }

        return pattern
