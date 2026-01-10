# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Bini** (SecurePythonUpgradeProject) is a Windows-native, offline static analysis tool that detects Python version compatibility issues when upgrading between Python versions.

### What It Does

Bini performs deep AST-based analysis to identify:
- **Breaking Changes**: Code that will break or behave differently
- **Deprecated Features**: Features removed in target version
- **Syntax Issues**: New syntax that's not backward compatible
- **Standard Library Changes**: API modifications, removals, and additions

### Key Features

- **AST-Based Analysis**: Uses Python's built-in AST module for accurate parsing
- **Offline Operation**: No internet connection required; all rules embedded
- **Multi-Version Support**: Analyzes upgrades from Python 3.6 to 3.12
- **Intelligent Version Detection**: Auto-detects source Python version from project files
- **Parallel Processing Ready**: Framework for parallel analysis (not yet activated)
- **Cache & Resume**: Interrupt and resume analysis with partial report saving
- **Interactive Reports**: HTML reports with filtering, navigation, and code snippets
- **Baseline Management**: Per-file, per-issue baselining to ignore known problems
- **No Auto-Fixing**: Analysis and reporting only - never modifies user code
- **Comprehensive Rules**: 474+ rules covering all Python upgrade paths
- **LLM-Based Detection**: Optional LLM validation using Ollama for improved accuracy

### Problems It Solves

- Identifies code that will break when upgrading Python versions
- Detects deprecated features before they cause runtime errors
- Prevents unexpected behavior after version upgrades
- Provides actionable suggestions with code examples
- Gives upgrade risk assessment with severity levels

---

## System Requirements

### Python Version Requirements
- **Minimum to run tool**: Python 3.8+
- **Maximum tested**: Python 3.12
- **Source versions supported**: 3.6, 3.7, 3.8, 3.9, 3.10, 3.11
- **Target versions supported**: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12

### Dependencies
```bash
psutil>=5.9.0      # System monitoring (CPU, memory)
pyyaml>=6.0        # YAML configuration and rule loading
packaging>=21.0    # Version parsing and comparison
```

### Optional Dependencies (for LLM Detection)
- **Ollama**: Required for LLM-based detection (qwen2.5:7b model recommended)
- **Network**: Local connection to Ollama service (http://localhost:11434)

### System Requirements
- **Operating System**: Windows 11 (optimized for Windows)
- **Memory**: Minimum 4GB RAM (recommended 8GB+ for large projects)
- **Storage**: Sufficient space for project files and reports
- **Network**: Not required for core analysis (fully offline-capable); required only for LLM detection

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

---

## Scope & Limitations

### What's In Scope

**Analysis Capabilities:**
- Static analysis only (no runtime execution)
- Python source files (.py, .pyw, .pyi)
- AST-based pattern matching
- LLM-based semantic validation (optional, 7 rules)
- HTML report generation
- Baseline management for ignoring known issues
- Multi-version upgrade path analysis (3.6 → 3.12)

**Supported Features:**
- Breaking change detection
- Deprecated feature detection
- Syntax compatibility checking
- Standard library change detection
- Version auto-detection from project files
- Interactive HTML reports with filtering
- Per-file, per-issue baselining
- LLM-powered false positive filtering

**Rule Coverage:**
- 474 total rules across all version transitions
- 320 AST-based rules (67.5%)
- 7 LLM-validated rules (1.5% - 5 hybrid + 2 text)
- 147 informational rules (31.0%)
- All Python version transitions from 3.6→3.7 through 3.11→3.12

### What's Out of Scope

**Not Supported:**
- Auto-fixing or code modification
- Runtime testing or code execution
- Dependency analysis (requirements.txt, poetry, etc.)
- Virtual environment detection
- Non-Python file analysis
- CI/CD integration (not yet implemented)
- Performance benchmarking
- IDE/editor integration (not yet implemented)
- Custom rule plugins (not yet implemented)
- Python 2 to Python 3 upgrades

**Explicit Limitations:**
- **Windows-optimized**: Limited testing on Linux/macOS
- **No parallel processing**: Framework ready but not activated
- **Rule coverage**: Focuses on common Python features; edge cases may be missed
- **Memory usage**: Large projects may require significant RAM
- **False positives**: May flag code that works correctly (mitigated by LLM validation)
- **False negatives**: May miss some compatibility issues
- **LLM performance**: 473x slower with LLM enabled (18 min vs 2.3 sec for 13 files)

### Known Limitations

**Technical Limitations:**
1. **Dynamic Features**: Cannot analyze code that uses `exec()`, `eval()`, or dynamic imports
2. **Type Checking**: Does not perform type checking beyond AST patterns
3. **Metaprogramming**: Limited analysis of metaclasses and decorators
4. **Conditional Imports**: May miss issues in version-specific imports
5. **Large Projects**: Performance may degrade on projects with thousands of files
6. **LLM Overhead**: LLM validation adds ~22-30 seconds per validation

**Design Limitations:**
1. **Windows Focus**: Primary development and testing on Windows
2. **No Auto-Fix**: Intentionally read-only to prevent code modification
3. **English Only**: Messages and documentation in English
4. **Python 3 Only**: Does not support Python 2 to 3 upgrades
5. **LLM Dependency**: LLM features require Ollama service to be running

### LLM Detection Trade-offs

**When to Use LLM:**
- Small projects (< 100 files)
- Prioritizing accuracy over speed
- Reviewing critical code paths
- Final validation pass

**When to Skip LLM:**
- Large codebases (> 1000 files)
- Quick initial scan needed
- CI/CD pipeline usage
- Running without Ollama

**Performance Impact:**
- Single file: 212s with LLM vs 1.3s without (159x slower)
- 13 files: 1079s with LLM vs 2.3s without (473x slower)
- Accuracy improvement: 7.8-8.1% fewer false positives

---

## Key Design Decisions

- **No auto-fixing**: Tool is analysis-only, never modifies user code
- **AST-based analysis**: Uses Python's built-in AST module for accurate parsing
- **LLM validation**: Optional semantic validation for complex patterns (7 rules)
- **Parallel processing**: Sequential processing currently implemented; parallel processing planned
- **Cache & resume**: Interrupted analysis can be resumed (partial reports saved on Ctrl+C)
- **Baseline support**: Per-file, per-issue baselining to ignore known problems
- **Offline operation**: All AST rules embedded, no network required (except for LLM)
- **Configurable LLM**: LLM can be enabled/disabled via configuration file

---

## Supported Python Versions

### Version Transitions (All Complete)

- [x] **3.6 → 3.7** — 62 rules (16 breaking, 21 deprecated, 6 syntax, 19 stdlib)
- [x] **3.7 → 3.8** — 106 rules (18 breaking, 17 deprecated, 6 syntax, 65 stdlib)
- [x] **3.8 → 3.9** — 38 rules (11 breaking, 13 deprecated, 4 syntax, 10 stdlib)
- [x] **3.9 → 3.10** — 68 rules (13 breaking, 22 deprecated, 10 syntax, 23 stdlib)
- [x] **3.10 → 3.11** — 95 rules (18 breaking, 29 deprecated, 18 syntax, 30 stdlib)
- [x] **3.11 → 3.12** — 103 rules (20 breaking, 27 deprecated, 20 syntax, 36 stdlib)

**Total:** 472 rules across 6 version transitions

### Rule Categories

- **Breaking Changes** (96 rules): Code that will break or behave differently
- **Deprecated Features** (129 rules): Features removed or deprecated
- **Syntax Changes** (64 rules): Syntax incompatibilities and new features
- **Standard Library Changes** (183 rules): API modifications, removals, and additions

---

## Project Structure

```
bini-py-upgrade/
├── bini_analyzer.py          # CLI entry point
├── config/                   # Configuration management
│   ├── config_loader.py
│   └── default_config.yaml   # LLM settings here
├── core/                     # Core analysis logic
│   ├── analysis_orchestrator.py
│   ├── result_aggregator.py
│   └── risk_calculator.py
├── parser/                   # Parsing layer
│   ├── ast_parser.py
│   └── version_detector.py
├── rules/                    # YAML rule definitions
│   ├── rule_loader.py
│   ├── rule_executor.py
│   └── versions/             # Rules by source version
│       ├── 3.6/
│       ├── 3.7/
│       ├── 3.8/
│       ├── 3.9/
│       ├── 3.10/
│       └── 3.11/
├── detection/                # Detection layer
│   ├── base_detector.py
│   ├── ast_pattern_matcher.py
│   └── llm/                 # LLM-based detection
│       ├── ollama_client.py
│       └── llm_detector.py
├── reporting/                # Report generation
│   ├── report_generator.py
│   └── data_models.py
└── utils/                    # Utility functions
    ├── file_utils.py
    └── logger.py
```

---

## Configuration

### LLM Detection (Optional)

Enable/disable LLM detection in `config/default_config.yaml`:

```yaml
llm:
  enabled: true              # Set to false to disable LLM
  host: "http://localhost:11434"
  model: "qwen2.5:7b"
  temperature: 0.1
```

### Running with Custom Config

```bash
# Use config with LLM disabled
bini-analyzer --config no_llm.yaml analyze ./project --target 3.12

# Use default config (LLM enabled)
bini-analyzer analyze ./project --target 3.12
```

---

## Documentation

Additional documentation available in the `docs/` directory:

- **LLM_DETECTION_IMPLEMENTATION.md**: Technical details of LLM integration
- **LLM_DETECTION_TEST_RESULTS.md**: Comprehensive test results and performance analysis
- **README.md**: User-facing documentation with usage examples
