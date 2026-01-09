# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Installation and Setup
```bash
# Install dependencies and package in development mode
pip install -r requirements.txt
pip install -e .
```

### Running the Analyzer
```bash
# Basic analysis (auto-detects source version)
bini-analyzer analyze ./myproject --target 3.12

# Explicit source and target versions
bini-analyzer analyze ./myproject --source 3.6 --target 3.12

# With custom output directory and verbose output
bini-analyzer analyze ./myproject --target 3.12 --output ./reports --verbose

# Disable parallel processing
bini-analyzer analyze ./myproject --target 3.12 --no-parallel

# Specify worker count
bini-analyzer analyze ./myproject --target 3.12 --workers 4
```

### Baseline Management
```bash
# Generate baseline from current analysis results
bini-analyzer baseline generate ./myproject --target 3.12

# Analyze with baseline filter
bini-analyzer analyze ./myproject --target 3.12 --baseline .bini-baseline.json
```

### Cache Management
```bash
# Clear analysis cache
bini-analyzer cache clear ./myproject
```

### Using Configuration Files
```bash
# Use custom config file
bini-analyzer --config custom_config.yaml analyze ./myproject --target 3.12
```

## Architecture Overview

Bini is a static analysis tool for detecting Python version compatibility issues. The architecture follows a modular pipeline design:

### Core Components

**Entry Point** (`bini_analyzer.py`)
- CLI interface using argparse with subcommands: `analyze`, `baseline`, `cache`
- Handles graceful interruption (Ctrl+C) with partial report saving
- Routes commands to appropriate handlers

**Analysis Orchestrator** (`core/analysis_orchestrator.py`)
- Central coordinator that orchestrates the entire analysis workflow
- Manages: file discovery, version detection, rule loading, file analysis, result aggregation
- Coordinates between all major components

**Parsing Layer** (`parser/`)
- `ast_parser.py`: Parses Python source into AST, captures syntax errors, extracts source lines
- `version_detector.py`: Auto-detects Python version from project files
- `syntax_error_handler.py`: Converts syntax errors to Issue objects

**Rules System** (`rules/`)
- `rule_loader.py`: Loads YAML rule files from `rules/versions/{version}/` directory
  - Rule files organized by source version: `breaking_changes.yaml`, `deprecated_features.yaml`, `syntax_changes.yaml`, `stdlib_changes.yaml`
  - Each rule contains: id, pattern (AST node type), condition, message, suggestion, severity, risk_level
- `rule_executor.py`: Executes rules against AST trees using `ASTPatternMatcher`

**Detection Layer** (`detection/`)
- `base_detector.py`: Abstract base class for all detectors (AST node visitor pattern)
- `ast_pattern_matcher.py`: Matches AST patterns defined in YAML rules
- Detectors inherit from `BaseDetector` and implement `detect()` method

**Result Processing** (`core/`)
- `result_aggregator.py`: Aggregates issues from all files, applies baseline filtering
- `risk_calculator.py`: Assigns risk levels (HIGH/MEDIUM/LOW) based on severity and category
- `baseline_manager.py`: Creates and manages baselines for ignoring known issues

**Reporting** (`reporting/`)
- `report_generator.py`: Generates static HTML reports with embedded JSON data
- `data_models.py`: Pydantic/dataclass models for Issue, Location, Severity, Category, RiskLevel
- HTML reports include: dashboard summary, filterable issue lists, code snippets

**Configuration** (`config/`)
- `config_loader.py`: Loads YAML config, validates, merges with CLI arguments
- `default_config.yaml`: Template with all configuration options
- Config dataclass with validation for version formats, upgrade paths, performance limits

### Data Flow

1. **Config Loading**: ConfigLoader loads from file or defaults, merges with CLI args, validates
2. **File Discovery**: Discover Python files in source directory
3. **Version Detection**: Auto-detect source version or use provided value
4. **Rule Loading**: RuleLoader loads rules for all intermediate versions (source → target)
5. **File Analysis** (per file):
   - Parse source to AST with ASTParser
   - Handle syntax errors if present
   - Execute all rules via RuleExecutor
   - Aggregate issues with ResultAggregator
6. **Report Generation**: ReportGenerator creates HTML with embedded JSON data

### Rule System Architecture

Rules are defined in YAML files under `rules/versions/{source_version}/`:
- Organized by category: `breaking_changes.yaml`, `deprecated_features.yaml`, `syntax_changes.yaml`, `stdlib_changes.yaml`
- Rule structure:
  ```yaml
  - id: "PY3601"
    name: "Human-readable name"
    category: "breaking_change"
    severity: "high"
    risk_level: "HIGH"
    source_version: "3.6"
    target_version: "3.7"
    detector: "DetectorClassName"
    pattern:
      node_type: "Name"
      attributes:
        id: "async"
    condition:
      not_in_context: ["async_func"]
    message: "Description of the issue"
    suggestion: "How to fix it"
    examples:
      bad: "code that breaks"
      good: "fixed code"
    references: ["https://docs.python.org/..."]
  ```

When analyzing an upgrade from 3.6 to 3.12, the loader loads rules for 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12 to catch all intermediate breaking changes.

### Adding New Rules

1. Create YAML file in `rules/versions/{source_version}/` directory
2. Follow the rule structure above
3. Define AST pattern in `pattern` section (node_type and attributes)
4. Optionally add `condition` for complex matching logic
5. If new detector logic is needed, create detector class in `detection/detectors/` inheriting from `BaseDetector`

### Supported Python Versions

- Source: 3.6, 3.7, 3.8, 3.9, 3.10, 3.11
- Target: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12

### Key Design Decisions

- **No auto-fixing**: Tool is analysis-only, never modifies user code
- **AST-based analysis**: Uses Python's built-in AST module for accurate parsing
- **Parallel processing**: Sequential processing currently implemented; parallel processing planned
- **Cache & resume**: Interrupted analysis can be resumed (partial reports saved on Ctrl+C)
- **Baseline support**: Per-file, per-issue baselining to ignore known problems
- **Offline operation**: All rules embedded, no network required
