"""
File utilities for discovering and processing Python files.
"""

import os
from typing import List


def discover_python_files(root_path: str) -> List[str]:
    """
    Discover all Python files in a directory or handle a single file.

    Args:
        root_path: Root directory to search or path to single Python file

    Returns:
        List of absolute file paths
    """
    python_files = []
    root_path = os.path.abspath(root_path)

    # Directories to skip
    skip_dirs = {
        '__pycache__',
        '.git',
        '.tox',
        'venv',
        'env',
        '.venv',
        'node_modules',
        'dist',
        'build',
        '.eggs',
        '*.egg-info',
        '.pytest_cache',
        '.mypy_cache',
        'output',
        'cache',
    }

    # Valid extensions
    valid_extensions = ('.py', '.pyw', '.pyi')

    # Handle single file case
    if os.path.isfile(root_path) and root_path.endswith(valid_extensions):
        return [root_path]

    for root, dirs, files in os.walk(root_path):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

        for filename in files:
            if filename.endswith(valid_extensions):
                file_path = os.path.join(root, filename)
                python_files.append(file_path)

    return python_files


def is_valid_python_file(file_path: str) -> bool:
    """
    Check if a file is a valid Python file.

    Args:
        file_path: Path to check

    Returns:
        True if valid Python file
    """
    valid_extensions = ('.py', '.pyw', '.pyi')
    return file_path.endswith(valid_extensions)


def normalize_path(path: str) -> str:
    """
    Normalize a file path for Windows.

    Args:
        path: Path to normalize

    Returns:
        Normalized absolute path
    """
    path = os.path.abspath(path)

    # Handle drive letter casing
    if len(path) >= 2 and path[1] == ':':
        path = path[0].upper() + path[1:]

    return path


def get_relative_path(file_path: str, base_path: str) -> str:
    """
    Get relative path from base path.

    Args:
        file_path: Absolute file path
        base_path: Base directory path

    Returns:
        Relative path
    """
    try:
        return os.path.relpath(file_path, base_path)
    except ValueError:
        # On Windows, paths on different drives raise ValueError
        return file_path
