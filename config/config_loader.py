"""
Configuration loader and validator for SecurePythonUpgradeProject.
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Config:
    """Configuration data class."""

    # Python version settings
    source_version: str = "auto"
    target_version: Optional[str] = None

    # Scan settings
    resume: bool = True
    parallel: bool = True
    verbose: bool = False

    # Paths
    source_path: str = "./src"
    output_path: str = "./output"

    # Performance
    max_workers: Optional[int] = None
    memory_limit: int = 70
    cpu_limit: int = 90

    # Baseline
    baseline_file: Optional[str] = None

    # Cache
    cache_enabled: bool = True
    cache_expiration_days: Optional[int] = 30

    # Reporting
    include_snippets: bool = True
    snippet_lines: int = 3
    top_files_count: int = 10

    # LLM detection
    llm_enabled: bool = True
    llm_host: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b"
    llm_temperature: float = 0.1
    llm_timeout: int = 30
    llm_max_tokens: Optional[int] = None
    llm_graceful_degradation: bool = True
    llm_validation_mode: str = "none"

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Normalize paths
        self.source_path = os.path.abspath(self.source_path)
        self.output_path = os.path.abspath(self.output_path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'python': {
                'source_version': self.source_version,
                'target_version': self.target_version,
            },
            'scan': {
                'resume': self.resume,
                'parallel': self.parallel,
                'verbose': self.verbose,
            },
            'paths': {
                'source': self.source_path,
                'output': self.output_path,
            },
            'performance': {
                'max_workers': self.max_workers,
                'memory_limit': self.memory_limit,
                'cpu_limit': self.cpu_limit,
            },
            'baseline': {
                'file': self.baseline_file,
            },
            'cache': {
                'enabled': self.cache_enabled,
                'expiration_days': self.cache_expiration_days,
            },
            'reporting': {
                'include_snippets': self.include_snippets,
                'snippet_lines': self.snippet_lines,
                'top_files_count': self.top_files_count,
            },
        }


class ConfigLoader:
    """Load and validate configuration from file or command-line arguments."""

    DEFAULT_CONFIG_PATH = os.path.join(
        os.path.dirname(__file__), 'default_config.yaml'
    )

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.

        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path

    def load_config(self) -> Config:
        """
        Load configuration from file or defaults.

        Returns:
            Config object with loaded configuration
        """
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            return self._parse_config(config_dict)
        else:
            # Load default config
            with open(self.DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                default_dict = yaml.safe_load(f)
            return self._parse_config(default_dict)

    def _parse_config(self, config_dict: Dict[str, Any]) -> Config:
        """
        Parse configuration dictionary into Config object.

        Args:
            config_dict: Configuration dictionary

        Returns:
            Config object
        """
        python = config_dict.get('python', {})
        scan = config_dict.get('scan', {})
        paths = config_dict.get('paths', {})
        performance = config_dict.get('performance', {})
        baseline = config_dict.get('baseline', {})
        cache = config_dict.get('cache', {})
        reporting = config_dict.get('reporting', {})
        llm = config_dict.get('llm', {})

        return Config(
            source_version=python.get('source_version', 'auto'),
            target_version=python.get('target_version'),
            resume=scan.get('resume', True),
            parallel=scan.get('parallel', True),
            verbose=scan.get('verbose', False),
            source_path=paths.get('source', './src'),
            output_path=paths.get('output', './output'),
            max_workers=performance.get('max_workers'),
            memory_limit=performance.get('memory_limit', 70),
            cpu_limit=performance.get('cpu_limit', 90),
            baseline_file=baseline.get('file'),
            cache_enabled=cache.get('enabled', True),
            cache_expiration_days=cache.get('expiration_days'),
            include_snippets=reporting.get('include_snippets', True),
            snippet_lines=reporting.get('snippet_lines', 3),
            top_files_count=reporting.get('top_files_count', 10),
            llm_enabled=llm.get('enabled', True),
            llm_host=llm.get('host', 'http://localhost:11434'),
            llm_model=llm.get('model', 'qwen2.5-coder:7b'),
            llm_temperature=llm.get('temperature', 0.1),
            llm_timeout=llm.get('timeout', 30),
            llm_max_tokens=llm.get('max_tokens'),
            llm_graceful_degradation=llm.get('graceful_degradation', True),
            llm_validation_mode=llm.get('validation_mode', 'none'),
        )

    def update_from_args(self, config: Config, args) -> Config:
        """
        Update configuration from command-line arguments.

        Args:
            config: Current Config object
            args: Parsed command-line arguments

        Returns:
            Updated Config object
        """
        if hasattr(args, 'project') and args.project:
            config.source_path = os.path.normpath(args.project)
        if hasattr(args, 'source') and args.source:
            config.source_version = args.source
        if hasattr(args, 'target') and args.target:
            config.target_version = args.target
        if hasattr(args, 'output') and args.output:
            config.output_path = os.path.abspath(args.output)
        if hasattr(args, 'baseline') and args.baseline:
            config.baseline_file = args.baseline
        if hasattr(args, 'verbose') and args.verbose:
            config.verbose = args.verbose
        if hasattr(args, 'resume') and args.resume is not None:
            config.resume = args.resume
        if hasattr(args, 'parallel') and args.parallel is not None:
            config.parallel = args.parallel
        if hasattr(args, 'workers') and args.workers:
            config.max_workers = args.workers

        return config

    def validate_config(self, config: Config) -> tuple[bool, list[str]]:
        """
        Validate configuration.

        Args:
            config: Config object to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Target version is mandatory
        if not config.target_version:
            errors.append(
                "Target version is required. Specify it with --target or in config file."
            )

        # Validate version format
        if config.target_version:
            if not self._is_valid_version(config.target_version):
                errors.append(
                    f"Invalid target version format: {config.target_version}. "
                    "Use format: X.Y (e.g., 3.12)"
                )

        # Validate source version if not auto
        if config.source_version != 'auto':
            if not self._is_valid_version(config.source_version):
                errors.append(
                    f"Invalid source version format: {config.source_version}. "
                    "Use format: X.Y (e.g., 3.6) or 'auto' for auto-detection."
                )

        # Validate upgrade path
        if config.source_version != 'auto' and config.target_version:
            if not self._is_valid_upgrade_path(config.source_version, config.target_version):
                errors.append(
                    f"Invalid upgrade path: {config.source_version} -> {config.target_version}. "
                    "Target version must be higher than source version."
                )

        # Validate performance limits
        if not (0 < config.memory_limit <= 100):
            errors.append(f"Memory limit must be between 1 and 100, got {config.memory_limit}")

        if not (0 < config.cpu_limit <= 100):
            errors.append(f"CPU limit must be between 1 and 100, got {config.cpu_limit}")

        return len(errors) == 0, errors

    def _is_valid_version(self, version_str: str) -> bool:
        """
        Validate version string format.

        Args:
            version_str: Version string to validate

        Returns:
            True if valid format
        """
        parts = version_str.split('.')
        if len(parts) != 2:
            return False
        try:
            major = int(parts[0])
            minor = int(parts[1])
            return major == 3 and 6 <= minor <= 12
        except ValueError:
            return False

    def _is_valid_upgrade_path(self, source: str, target: str) -> bool:
        """
        Check if upgrade path is valid.

        Args:
            source: Source version
            target: Target version

        Returns:
            True if target > source
        """
        source_parts = source.split('.')
        target_parts = target.split('.')

        try:
            source_minor = int(source_parts[1])
            target_minor = int(target_parts[1])
            return target_minor > source_minor
        except (ValueError, IndexError):
            return False
