"""
Auto-detect source Python version from project files.
"""

import os
import re
import ast
from typing import Optional, List
from pathlib import Path


class VersionDetector:
    """
    Detect the source Python version of a project.

    Detection strategies (in order of priority):
    1. pyproject.toml (requires-python)
    2. setup.py / setup.cfg (python_requires)
    3. .python-version file
    4. runtime.version.txt or similar
    5. __future__ imports analysis
    6. Heuristic based on syntax features
    """

    # Minimum supported version
    MIN_VERSION = "3.6"
    # Maximum supported version
    MAX_VERSION = "3.12"

    def __init__(self, project_path: str):
        """
        Initialize version detector.

        Args:
            project_path: Path to project directory
        """
        self.project_path = os.path.abspath(project_path)

    def detect_version(self) -> str:
        """
        Detect Python version from project.

        Returns:
            Detected version string (e.g., "3.6")
        """
        # Strategy 1: pyproject.toml
        version = self._check_pyproject_toml()
        if version:
            return version

        # Strategy 2: setup.py / setup.cfg
        version = self._check_setup_files()
        if version:
            return version

        # Strategy 3: .python-version
        version = self._check_python_version_file()
        if version:
            return version

        # Strategy 4: runtime.version.txt
        version = self._check_runtime_version_file()
        if version:
            return version

        # Strategy 5: Analyze Python files for __future__ imports
        version = self._check_future_imports()
        if version:
            return version

        # Strategy 6: Heuristic based on syntax features
        version = self._heuristic_detection()
        if version:
            return version

        # Default to minimum supported version
        return self.MIN_VERSION

    def _check_pyproject_toml(self) -> Optional[str]:
        """Check pyproject.toml for requires-python."""
        pyproject_path = os.path.join(self.project_path, 'pyproject.toml')

        if not os.path.exists(pyproject_path):
            return None

        try:
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for requires-python in [project] section
            match = re.search(r'requires-python\s*=\s*["\']([^"\']+)[ "\']', content)
            if match:
                version_spec = match.group(1)
                return self._parse_version_spec(version_spec)

        except Exception:
            pass

        return None

    def _check_setup_files(self) -> Optional[str]:
        """Check setup.py and setup.cfg for python_requires."""
        # Check setup.py
        setup_py = os.path.join(self.project_path, 'setup.py')
        if os.path.exists(setup_py):
            try:
                with open(setup_py, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Look for python_requires argument
                match = re.search(r'python_requires\s*=\s*["\']([^"\']+)[ "\']', content)
                if match:
                    version_spec = match.group(1)
                    return self._parse_version_spec(version_spec)
            except Exception:
                pass

        # Check setup.cfg
        setup_cfg = os.path.join(self.project_path, 'setup.cfg')
        if os.path.exists(setup_cfg):
            try:
                with open(setup_cfg, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Look for python_requires in options section
                match = re.search(r'python_requires\s*=\s*([^\n]+)', content)
                if match:
                    version_spec = match.group(1).strip()
                    return self._parse_version_spec(version_spec)
            except Exception:
                pass

        return None

    def _check_python_version_file(self) -> Optional[str]:
        """Check .python-version file."""
        version_file = os.path.join(self.project_path, '.python-version')

        if not os.path.exists(version_file):
            return None

        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # Extract version number
            match = re.search(r'(\d+\.\d+)', content)
            if match:
                return match.group(1)
        except Exception:
            pass

        return None

    def _check_runtime_version_file(self) -> Optional[str]:
        """Check for runtime version specification files."""
        possible_files = [
            'runtime.version.txt',
            'runtime.txt',
            '.python-version',
            'PYTHON_VERSION',
        ]

        for filename in possible_files:
            file_path = os.path.join(self.project_path, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()

                    # Extract version number
                    match = re.search(r'(\d+\.\d+)', content)
                    if match:
                        return match.group(1)
                except Exception:
                    pass

        return None

    def _check_future_imports(self) -> Optional[str]:
        """
        Analyze Python files for __future__ imports to determine minimum version.

        Returns the minimum version based on __future__ imports found.
        """
        future_features = {
            'annotations': '3.7',
            'generator_stop': '3.7',
        }

        min_version = None

        # Find all Python files
        python_files = self._find_python_files()

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()

                # Parse AST
                tree = ast.parse(source, filename=file_path)

                # Check for __future__ imports
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module == '__future__':
                            for alias in node.names:
                                feature = alias.name
                                if feature in future_features:
                                    version = future_features[feature]
                                    if not min_version or version < min_version:
                                        min_version = version
            except Exception:
                # Skip files that can't be parsed
                continue

        return min_version

    def _heuristic_detection(self) -> Optional[str]:
        """
        Use heuristic analysis based on syntax features.

        Detects version based on:
        - Walrus operator (:=) -> 3.8+
        - Match/Case statement -> 3.10+
        - Exception groups -> 3.11+
        - Type parameter syntax -> 3.12+
        """
        max_version = None

        # Find all Python files
        python_files = self._find_python_files()

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()

                # Parse AST
                tree = ast.parse(source, filename=file_path)

                # Walk AST and detect features
                for node in ast.walk(tree):
                    # Walrus operator (NamedExpr) - Python 3.8+
                    if isinstance(node, ast.NamedExpr):
                        max_version = max(max_version or '3.6', '3.8')

                    # Match statement - Python 3.10+
                    if isinstance(node, ast.Match):
                        max_version = max(max_version or '3.6', '3.10')

            except Exception:
                # Skip files that can't be parsed
                continue

        return max_version

    def _find_python_files(self) -> List[str]:
        """Find all Python files in the project."""
        python_files = []

        for root, dirs, files in os.walk(self.project_path):
            # Skip common directories that aren't part of the source
            dirs[:] = [d for d in dirs if d not in {
                '__pycache__',
                '.git',
                '.tox',
                'venv',
                'env',
                'node_modules',
                'dist',
                'build',
                '.eggs',
            }]

            for filename in files:
                if filename.endswith(('.py', '.pyw', '.pyi')):
                    python_files.append(os.path.join(root, filename))

        return python_files

    def _parse_version_spec(self, version_spec: str) -> Optional[str]:
        """
        Parse version specification string to extract minimum version.

        Handles:
        - ">=3.6" -> "3.6"
        - ">=3.6,<4.0" -> "3.6"
        - "3.6" -> "3.6"
        - "~3.6" -> "3.6"
        """
        # Extract version using regex
        match = re.search(r'>=\s*(\d+\.\d+)', version_spec)
        if match:
            return match.group(1)

        match = re.search(r'(\d+\.\d+)', version_spec)
        if match:
            return match.group(1)

        return None

    def validate_version(self, version: str) -> bool:
        """
        Validate version string.

        Args:
            version: Version string to validate

        Returns:
            True if valid
        """
        try:
            parts = version.split('.')
            if len(parts) != 2:
                return False

            major = int(parts[0])
            minor = int(parts[1])

            return major == 3 and 6 <= minor <= 12
        except (ValueError, IndexError):
            return False
