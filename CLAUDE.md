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
- **Comprehensive Rules**: 475+ rules covering all Python upgrade paths

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

### System Requirements
- **Operating System**: Windows 11 (optimized for Windows)
- **Memory**: Minimum 4GB RAM (recommended 8GB+ for large projects)
- **Storage**: Sufficient space for project files and reports
- **Network**: Not required (fully offline-capable)

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

---

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

**Rule ID Format:**
All rule IDs follow the format: `PY{VERSION}{CATEGORY}{NUMBER}`
- `{VERSION}` = Source Python version (e.g., 36, 37, 38, 39, 310, 311, 312)
- `{CATEGORY}` = Two-letter category code:
  - **BC** = Breaking Changes (breaking_changes.yaml)
  - **DF** = Deprecated Features (deprecated_features.yaml)
  - **SC** = Syntax Changes (syntax_changes.yaml)
  - **SL** = Stdlib/Library Changes (stdlib_changes.yaml)
- `{NUMBER}` = Zero-padded sequential number starting from 01

Examples:
- `PY36BC01` = Python 3.6 Breaking Changes rule #1
- `PY37DF05` = Python 3.7 Deprecated Features rule #5
- `PY310SC12` = Python 3.10 Syntax Changes rule #12
- `PY311SL20` = Python 3.11 Stdlib Changes rule #20

**Rule structure:**
  ```yaml
  - id: "PY36BC01"
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

---

## Rule Maintenance Progress

This section tracks the completion status of Python upgrade rules for each version transition.

### Version Transitions

- [x] **3.6 → 3.7** — ✅ **COMPLETE**
- [x] **3.7 → 3.8** — ✅ **COMPLETE**
- [x] **3.8 → 3.9** — ✅ **COMPLETE**
- [x] **3.9 → 3.10** — ✅ **COMPLETE**
- [x] **3.10 → 3.11** — ✅ **COMPLETE**
- [x] **3.11 → 3.12** — ✅ **COMPLETE**

---

## Python 3.6 → 3.7 — COMPLETED

**Folder:** `rules/versions/3.6/`

**Sources reviewed:**
- [What's New In Python 3.7 — Python 3.14.2 documentation](https://docs.python.org/3/whatsnew/3.7.html)
- [Porting to Python 3.7 section](https://docs.python.org/3/whatsnew/3.7.html#porting-to-python-3-7)

**Status:** COMPLETE

**Rules added/updated:**

**breaking_changes.yaml** (16 rules):
- PY36BC01: PEP 479 - StopIteration becomes RuntimeError in coroutines
- PY36BC02: Generator expressions require parentheses
- PY36BC03: async __aiter__ methods prohibited
- PY36BC04: os.stat_float_times() removed
- PY36BC05: Unknown escapes in re.sub() replacement templates now error
- PY36BC06: ntpath.splitunc() removed
- PY36BC07: collections.namedtuple() verbose parameter removed
- PY36BC08: float(), list(), tuple() keyword arguments removed
- PY36BC09: int() first argument as keyword removed
- PY36BC10: plistlib.Plist, Dict, _InternalDict removed
- PY36BC11: asyncio.windows_utils.socketpair() removed
- PY36BC12: asyncio.selectors and asyncio._overlapped no longer exported
- PY36BC13: Direct instantiation of ssl.SSLSocket and ssl.SSLObject prohibited
- PY36BC14: distutils install_misc command removed
- PY36BC15: fpectl module removed
- PY36BC16: Additional breaking changes

**deprecated_features.yaml** (21 rules):
- PY36DF01: Yield expressions in comprehensions deprecated
- PY36DF02: Returning complex subclass from __complex__() deprecated
- PY36DF03: aifc.openfp() deprecated
- PY36DF04: Direct await of asyncio.Lock deprecated
- PY36DF05: asyncio.Task.current_task() and all_tasks() deprecated
- PY36DF06: collections ABC in collections module deprecated
- PY36DF07: dbm.dumb behavior change deprecation
- PY36DF08: Non-Enum membership check deprecated
- PY36DF09: gettext non-integer plural deprecated
- PY36DF10: importlib find_module() and find_loader() deprecated
- PY36DF11: locale.format() deprecated
- PY36DF12: macpath module deprecated
- PY36DF13: dummy_threading deprecated
- PY36DF14: socket.htons() and ntohs() silent truncation deprecated
- PY36DF15: ssl.wrap_socket() deprecated
- PY36DF16: sunau.openfp() deprecated
- PY36DF17: wave.openfp() deprecated
- PY36DF18: sys.set_coroutine_wrapper() deprecated
- PY36DF19: sys.callstats() deprecated
- PY36DF20: PySlice_GetIndicesEx() deprecated (C API)
- PY36DF21: PyOS_AfterFork() deprecated (C API)

**stdlib_changes.yaml** (19 rules):
- New modules: contextvars, dataclasses, importlib.resources
- New functions: breakpoint(), asyncio.run(), asyncio.create_task(), asyncio.get_running_loop()
- Time module additions: nanosecond resolution functions, thread_time()
- API changes: asyncio loop methods return coroutines, socket type changes, subprocess changes
- Security: XML modules no longer process external entities by default
- New methods: str.isascii(), datetime.fromisoformat()

**syntax_changes.yaml** (6 rules):
- PY36SC01: async and await become reserved keywords
- PY36SC02: PEP 563 - Postponed evaluation of annotations available
- PY36SC03: await and async for allowed in f-strings

---

## Python 3.7 → 3.8 — COMPLETED

**Folder:** `rules/versions/3.7/`

**Sources reviewed:**
- [What's New In Python 3.8 — Python 3.14.2 documentation](https://docs.python.org/3/whatsnew/3.8.html)
- [Porting to Python 3.8 section](https://docs.python.org/3/whatsnew/3.8.html#porting-to-python-3-8)
- PEPs: 570 (Positional-only parameters), 572 (Assignment expressions), 574 (Pickle protocol 5), 578 (Runtime audit hooks), 586 (Literal types), 587 (Python initialization), 589 (TypedDict), 590 (Vectorcall), 591 (Final qualifier), 544 (Protocols)

**Status:** COMPLETE

**Rules added/updated:**

**breaking_changes.yaml** (18 rules total):
- PY37BC01: Yield expressions in comprehensions become SyntaxError
- PY37BC02: macpath module removed
- PY37BC03: platform.popen() removed
- PY37BC04: time.clock() removed
- PY37BC05: pyvenv script removed
- PY37BC06: cgi parse_qs, parse_qsl, escape removed
- PY37BC07: tarfile filemode function removed
- PY37BC08: XMLParser html argument removed
- PY37BC09: XMLParser doctype() method removed
- PY37BC10: unicode_internal codec removed
- PY37BC11: sqlite3 Cache and Statement objects removed
- PY37BC12: sys.set_coroutine_wrapper functions removed
- PY37BC13: asyncio.Task.current_task() requires argument (for 3.9)
- PY37BC14: asyncio.CancelledError inheritance changed
- PY37BC15: collections.namedtuple._asdict() returns dict
- PY37BC16: math.factorial() no longer accepts non-int arguments
- PY37BC17: os.path boolean methods return False for bad paths
- PY37BC18: pathlib boolean methods return False for bad paths

**deprecated_features.yaml** (17 rules total):
- PY37DF01: getchildren() and getiterator() deprecated in ElementTree
- PY37DF02: @asyncio.coroutine decorator deprecated
- PY37DF03: asyncio loop parameter deprecated
- PY37DF04: typing.NamedTuple._field_types deprecated
- PY37DF05: ast classes Num, Str, Bytes, NameConstant, Ellipsis deprecated
- PY37DF06: ast.NodeVisitor visit_Num, visit_Str, etc. deprecated
- PY37DF07: lgettext() and related functions deprecated
- PY37DF08: gettext bind_textdomain_codeset() deprecated
- PY37DF09: threading.Thread.isAlive() deprecated
- PY37DF10: int() and related functions deprecate Decimal/Fraction
- PY37DF11: Keyword arguments becoming positional-only
- PY37DF12: distutils bdist_wininst command deprecated
- PY37DF13: asyncio.wait() coroutine objects deprecated
- PY37DF14: xml.dom.pulldom.DOMEventStream.__getitem__() deprecated
- PY37DF15: wsgiref.util.FileWrapper.__getitem__() deprecated
- PY37DF16: fileinput.FileInput.__getitem__() deprecated
- PY37DF17: asyncio.loop.set_default_executor() with non-ThreadPoolExecutor deprecated

**syntax_changes.yaml** (6 rules):
- PY37SC01: Assignment expressions (walrus operator :=) available
- PY37SC02: Positional-only parameters (/) available
- PY37SC03: f-string = specifier for debugging available
- PY37SC04: continue in finally clause allowed
- PY37SC05: Generalized iterable unpacking in yield and return
- PY37SC06: \N{name} escapes supported in regular expressions

**stdlib_changes.yaml** (65 rules):
- PY37SL20: csv.DictReader returns dict instead of OrderedDict
- PY37SL21: New typing module features (TypedDict, Literal, Final, Protocol)
- PY37SL22: New statistics module features (fmean, geometric_mean, multimode, quantiles, NormalDist)
- PY37SL23: New functools features (cached_property, singledispatchmethod)
- PY37SL24: New unittest features (AsyncMock, IsolatedAsyncioTestCase)
- Plus 60 existing rules covering: importlib.metadata, math module additions, asyncio improvements, ast enhancements, datetime changes, and more

**Key changes in Python 3.8:**
- PEP 572: Assignment expressions (walrus operator)
- PEP 570: Positional-only parameters
- PEP 589: TypedDict
- PEP 586: Literal types
- PEP 591: Final qualifier
- PEP 544: Protocols
- asyncio.CancelledError now inherits from BaseException
- Many deprecated features from 3.7 were removed
- Significant stdlib additions and improvements

---

## Python 3.8 → 3.9 — COMPLETED

**Folder:** `rules/versions/3.8/`

**Sources reviewed:**
- [What's New In Python 3.9 — Python 3.14.2 documentation](https://docs.python.org/3/whatsnew/3.9.html)
- [Porting to Python 3.9 section](https://docs.python.org/3/whatsnew/3.9.html#porting-to-python-3-9)
- PEPs: 584 (Dict merge/update operators), 585 (Generic built-in collections), 593 (Annotated), 614 (Relaxed decorators), 615 (zoneinfo), 616 (removeprefix/removesuffix), 617 (PEG parser)

**Status:** COMPLETE

**Rules added/updated:**

**breaking_changes.yaml** (11 rules):
- PY38BC01: sys.getcheckinterval() and sys.setcheckinterval() removed
- PY38BC02: _dummy_thread and dummy_threading modules removed
- PY38BC03: threading.Thread.isAlive() removed
- PY38BC04: ElementTree.getchildren() and getiterator() removed
- PY38BC05: asyncio.Task.current_task() and all_tasks() removed
- PY38BC06: base64.encodestring() and decodestring() removed
- PY38BC07: fractions.gcd() removed
- PY38BC08: __import__() now raises ImportError instead of ValueError
- PY38BC09: Empty string replace behavior changed
- PY38BC10: typing.NamedTuple._field_types removed
- PY38BC11: nntplib.NNTP.xpath() and xgtitle() removed

**deprecated_features.yaml** (13 rules):
- PY38DF01: parser module deprecated
- PY38DF02: symbol module deprecated
- PY38DF03: math.factorial() accepting float deprecated
- PY38DF04: NotImplemented in boolean context deprecated
- PY38DF05: random module non-deterministic seed deprecated
- PY38DF06: Opening GzipFile without mode deprecated
- PY38DF07: _tkinter.TkappType.split() deprecated
- PY38DF08: binhex module deprecated
- PY38DF09: ast deprecated classes (slice, Index, ExtSlice, Suite, Param)
- PY38DF10: lib2to3 module deprecated
- PY38DF11: random.shuffle() random parameter deprecated
- PY38DF12: distutils.bdist_msi command deprecated
- PY38DF13: Passing coroutines to asyncio.wait() deprecated

**syntax_changes.yaml** (4 rules):
- PY38SC01: Dictionary merge operators (| and |=) available
- PY38SC02: Type hinting generics in standard collections available
- PY38SC03: Relaxed decorator grammar available
- PY38SC04: Unparenthesized lambda in comprehension if clause prohibited

**stdlib_changes.yaml** (10 rules):
- PY38SL01: xml.etree.ElementTree.getchildren() removed (duplicate from breaking)
- PY38SL02: New str.removeprefix() and removesuffix() methods
- PY38SL03: New zoneinfo module (IANA time zone database)
- PY38SL04: New graphlib module (topological sorting)
- PY38SL05: math.gcd() with multiple arguments
- PY38SL06: New math.lcm() function
- PY38SL07: New asyncio.to_thread() coroutine
- PY38SL08: New typing.Annotated type
- PY38SL09: datetime.isocalendar() returns namedtuple
- PY38SL10: inspect.BoundArguments.arguments returns dict

**Key changes in Python 3.9:**
- PEP 584: Dictionary merge and update operators (| and |=)
- PEP 585: Generic built-in collection types for type hints
- PEP 616: String methods to remove prefixes and suffixes
- PEP 617: New PEG parser (replaces LL(1) parser)
- PEP 615: IANA Time Zone Database support (zoneinfo module)
- PEP 614: Relaxed decorator grammar
- PEP 593: Annotated type hints
- Many deprecated 3.8 features removed
- asyncio improvements and API changes
- New graphlib module for graph algorithms

---

## Python 3.9 → 3.10 — COMPLETED

**Folder:** `rules/versions/3.9/`

**Sources reviewed:**
- [What's New In Python 3.10 — Python 3.14.2 documentation](https://docs.python.org/3/whatsnew/3.10.html)
- [Porting to Python 3.10 section](https://docs.python.org/3/whatsnew/3.10.html#porting-to-python-3-10)
- PEPs: 604 (Type union operator), 612 (ParamSpec), 613 (TypeAlias), 617 (Parenthesized context managers), 618 (zip strict), 626 (Precise line numbers), 634/635/636 (Pattern matching), 644 (OpenSSL 1.1.1+), 647 (TypeGuard)

**Status:** COMPLETE

**Rules added/updated:**

**breaking_changes.yaml** (13 rules):
- PY39BC01: parser module removed
- PY39BC02: formatter module removed
- PY39BC03: collections ABC aliases removed
- PY39BC04: complex special methods removed
- PY39BC05: asyncio loop parameter removed
- PY39BC06: socket.htons() overflow behavior changed
- PY39BC07: collections.abc.Callable parameter flattening
- PY39BC08: urllib.parse query separator change
- PY39BC09: shelve default protocol changed
- PY39BC10: traceback parameter renamed
- PY39BC11: Decimal/Fraction no longer accepted in builtins
- PY39BC12: __debug__ deletion now SyntaxError
- PY39BC13: NaN hash values now identity-dependent

**deprecated_features.yaml** (22 rules):
- PY39DF01: distutils module deprecated
- PY39DF02-39DF04: asynchat, asyncore, smtpd modules deprecated
- PY39DF05: Numeric literal followed by keyword
- PY39DF06-39DF08: importlib old semantics (Finder, find_loader, load_module)
- PY39DF09: random.randrange() non-integer arguments
- PY39DF10-39DF11: sqlite3.OptimizedUnicode and enable_shared_cache() deprecated
- PY39DF12: pathlib.Path.link_to() deprecated
- PY39DF13: cgi.log() deprecated
- PY39DF14-39DF17: threading old method names deprecated
- PY39DF18-39DF19: ssl old protocol constants and wrap_socket() deprecated
- PY39DF20: typing.io and typing.re deprecated
- PY39DF21: zipimport.zipimporter.load_module() deprecated
- PY39DF22: code.co_lnotab deprecated

**syntax_changes.yaml** (10 rules):
- PY39SC01: Structural pattern matching available (match/case)
- PY39SC02: Parenthesized context managers available
- PY39SC03: Type union operator available (int | str)
- PY39SC04: isinstance/issubclass with union operator
- PY39SC05: Improved error messages (informational)
- PY39SC06: PEP 626 precise line numbers
- PY39SC07: Assignment expressions in set literals
- PY39SC08: TypeAlias annotation available
- PY39SC09: ParamSpec available
- PY39SC10: TypeGuard available

**stdlib_changes.yaml** (23 rules):
- PY39SL01: int.bit_count() method
- PY39SL02: zip() strict parameter
- PY39SL03: itertools.pairwise()
- PY39SL04: statistics module new functions
- PY39SL05: base64 hex encoding functions
- PY39SL06: bisect module key parameter
- PY39SL07: codecs.unregister()
- PY39SL08: contextlib.aclosing()
- PY39SL09-39SL10: dataclasses slots and kw_only parameters
- PY39SL11: dict views mapping attribute
- PY39SL12-39SL13: pathlib.Path.hardlink_to() and parents slicing
- PY39SL14: platform.freedesktop_os_release()
- PY39SL15-39SL16: sys.orig_argv and sys.stdlib_module_names
- PY39SL17: threading trace/profile getters
- PY39SL18: typing.is_typeddict()
- PY39SL19: unittest.TestCase.assertNoLogs()
- PY39SL20-39SL21: SSL OpenSSL 1.1.1+ required and improved security defaults
- PY39SL22: os.path.realpath() strict parameter
- PY39SL23: typing.Literal behavior changes

**Key changes in Python 3.10:**
- PEP 634/635/636: Structural pattern matching (match/case statements)
- PEP 604: Type union operator using | (int | str)
- PEP 612: Parameter specification variables (ParamSpec)
- PEP 613: Explicit type aliases (TypeAlias)
- PEP 617: Parenthesized context managers
- PEP 618: Optional length checking for zip()
- PEP 626: Precise line numbers for debugging
- PEP 644: OpenSSL 1.1.1+ required
- PEP 647: User-defined type guards (TypeGuard)
- parser and formatter modules removed
- collections ABC aliases removed from collections module
- distutils module deprecated (removal in 3.12)
- Significantly improved error messages
- Many standard library enhancements

---

## Python 3.10 → 3.11 — COMPLETED

**Folder:** `rules/versions/3.10/`

**Sources reviewed:**
- [What's New In Python 3.11 — Python 3.14.2 documentation](https://docs.python.org/3/whatsnew/3.11.html)
- [Porting to Python 3.11 section](https://docs.python.org/3/whatsnew/3.11.html#porting-to-python-3-11)
- PEPs: 654 (Exception Groups), 646 (Variadic Generics), 655 (Required/NotRequired), 657 (Fine-grained error locations), 673 (Self type), 675 (LiteralString), 680 (tomllib), 681 (dataclass_transform), 688 (Buffer protocol), 594 (Mass module deprecation)

**Status:** COMPLETE

**Rules added/updated:**

**breaking_changes.yaml** (18 rules):
- PY310BC01: binhex module removed
- PY310BC02: asyncio.coroutine decorator removed
- PY310BC03: asynchat module removed
- PY310BC04: asyncore module removed
- PY310BC05: gettext l* functions removed (lgettext, ldgettext, etc.)
- PY310BC06: smtpd module removed
- PY310BC07: inspect.getargspec removed
- PY310BC08: inspect.formatargspec removed
- PY310BC09: file mode 'U' removed
- PY310BC10: random.sample set auto-conversion removed
- PY310BC11: locale.format deprecated in 3.7, removed in 3.11
- PY310BC12: regex global inline flags restricted
- PY310BC13: threading.Thread.setDaemon() removed
- PY310BC14: integer string conversion limit enforced (CVE-2020-10735)
- PY310BC15: unittest TestCase method parameter changes
- PY310BC16: __class_getitem__ behavior change
- PY310BC17: contextlib.AbstractContextManager and AbstractAsyncContextManager no longer generic
- PY310BC18: typing.io and typing.re aliases removed

**deprecated_features.yaml** (29 rules):
- PY310DF01-310DF19: PEP 594 module deprecations (19 modules):
  - aifc, audioop, chunk, cgi, cgitb, crypt, imghdr, mailcap, msilib, nis
  - nntplib, ossaudiodev, pipes, sndhdr, spwd, sunau, telnetlib, uu, xdrlib
- PY310DF20: unittest deprecated method aliases (failUnless, assertEquals, etc.)
- PY310DF21: locale.getdefaultlocale() deprecated
- PY310DF22: locale.resetlocale() deprecated
- PY310DF23: typing.Text deprecated
- PY310DF24: configparser.SafeConfigParser deprecated
- PY310DF25: sqlite3.OptimizedUnicode deprecated
- PY310DF26: threading.currentThread() deprecated
- PY310DF27: threading.activeCount() deprecated
- PY310DF28: wave.Wave_read.getparams() unpacking discouraged
- PY310DF29: webbrowser.MacOSX deprecated

**syntax_changes.yaml** (18 rules):
- PY310SC01: Exception groups (except*) available (PEP 654)
- PY310SC02: ExceptionGroup class available
- PY310SC03: TypeVarTuple for variadic generics available (PEP 646)
- PY310SC04: Unpack for variadic generics available
- PY310SC05: Self type available (PEP 673)
- PY310SC06: LiteralString type available (PEP 675)
- PY310SC07: Required and NotRequired for TypedDict available (PEP 655)
- PY310SC08: dataclass_transform decorator available (PEP 681)
- PY310SC09: Never type available
- PY310SC10: assert_never function available
- PY310SC11: reveal_type function available
- PY310SC12: assert_type function available
- PY310SC13: clear_overloads function available
- PY310SC14: get_overloads function available
- PY310SC15: Starred unpacking in for statements
- PY310SC16: Format spec 'z' option for negative zero
- PY310SC17: Async comprehensions error messages improved
- PY310SC18: Significantly improved error messages (PEP 657)

**stdlib_changes.yaml** (30 rules):
- PY310SL01: tomllib module available (PEP 680)
- PY310SL02: asyncio.TaskGroup available
- PY310SL03: asyncio.timeout() context manager available
- PY310SL04: asyncio.Runner class available
- PY310SL05: contextlib.chdir() context manager available
- PY310SL06: datetime.UTC constant available
- PY310SL07: enum.StrEnum class available
- PY310SL08: enum.ReprEnum class available
- PY310SL09: enum.verify() decorator available
- PY310SL10: enum.member() and nonmember() available
- PY310SL11: fractions.Fraction format spec support
- PY310SL12: functools.cache() decorator
- PY310SL13: inspect.BufferFlags class available (PEP 688)
- PY310SL14: math.exp2() function available
- PY310SL15: math.cbrt() function available
- PY310SL16: operator.call() function available
- PY310SL17: os.path.splitroot() function available
- PY310SL18: pathlib.Path.is_mount() method available
- PY310SL19: re.RegexFlag.NOFLAG constant available
- PY310SL20: shutil.make_archive() pathlib.Path support
- PY310SL21: socket.create_server() multi-bind support
- PY310SL22: sqlite3.Connection.blobopen() method available
- PY310SL23: sqlite3.Connection.setlimit() and getlimit() available
- PY310SL24: sys.exception() function available
- PY310SL25: sys.__interactivehook__ behavior improved
- PY310SL26: threading.setprofile_all_threads() available
- PY310SL27: traceback.StackSummary.format_frame_summary() available
- PY310SL28: unicodedata updated to Unicode 14.0
- PY310SL29: unittest.TestCase.enterContext() available
- PY310SL30: Performance improvements (average 1.25x faster)

**Key changes in Python 3.11:**
- PEP 654: Exception Groups and except* syntax
- PEP 646: Variadic generics (TypeVarTuple)
- PEP 655: Required and NotRequired for TypedDict
- PEP 657: Fine-grained error locations in tracebacks
- PEP 673: Self type for annotating methods
- PEP 675: LiteralString type for injection prevention
- PEP 680: tomllib module for TOML parsing
- PEP 681: dataclass_transform decorator
- PEP 688: Buffer protocol accessible in Python
- PEP 594: Mass deprecation of 19 modules (removal in 3.13)
- PEP 659: Specializing Adaptive Interpreter (1.25x average speedup)
- asyncio improvements: TaskGroup, timeout(), Runner
- Significantly improved error messages with precise locations
- Many typing module enhancements (Never, assert_never, reveal_type, etc.)
- New standard library features: tomllib, enum enhancements, asyncio improvements

---

## Python 3.11 → 3.12 — COMPLETED

**Folder:** `rules/versions/3.11/`

**Sources reviewed:**
- [What's New In Python 3.12 — Python 3.14.2 documentation](https://docs.python.org/3/whatsnew/3.12.html)
- [Porting to Python 3.12 section](https://docs.python.org/3/whatsnew/3.12.html#porting-to-python-3-12)
- PEPs: 695 (Type parameter syntax), 701 (F-string enhancements), 692 (TypedDict kwargs), 698 (Override decorator), 709 (Comprehension inlining), 688 (Buffer protocol), 669 (Monitoring), 684 (Per-interpreter GIL), 683 (Immortal objects), 632 (distutils removal)

**Status:** COMPLETE

**Rules added/updated:**

**breaking_changes.yaml** (20 rules):
- PY311BC01: distutils module removed (PEP 632)
- PY311BC02: imp module removed
- PY311BC03: asynchat module removed
- PY311BC04: asyncore module removed
- PY311BC05: smtpd module removed
- PY311BC06: sqlite3.enable_shared_cache() removed
- PY311BC07: sqlite3.OptimizedUnicode removed
- PY311BC08: ssl.RAND_pseudo_bytes() removed
- PY311BC09: ssl.match_hostname() removed
- PY311BC10: ssl.wrap_socket() removed
- PY311BC11: unittest TestCase deprecated aliases removed
- PY311BC12: configparser.ParsingError.filename attribute removed
- PY311BC13: ftplib.FTP_TLS.ssl_version attribute removed
- PY311BC14: gzip.GzipFile.filename attribute removed
- PY311BC15: zipimport.zipimporter.find_loader() removed
- PY311BC16: xml.etree.ElementTree.Element.copy() removed
- PY311BC17: Null bytes in source now SyntaxError
- PY311BC18: venv no longer pre-installs setuptools
- PY311BC19: Escape sequence warnings upgraded
- PY311BC20: Slices now hashable

**deprecated_features.yaml** (27 rules):
- PY311DF01: datetime.utcnow() deprecated (removal in 3.15)
- PY311DF02: datetime.utcfromtimestamp() deprecated
- PY311DF03: ast deprecated node classes (Num, Str, Bytes, etc., removal in 3.14)
- PY311DF04: asyncio.get_event_loop() deprecated (removal in 3.14)
- PY311DF05-311DF06: asyncio child watcher classes and functions deprecated
- PY311DF07: sys.last_type/value/traceback deprecated
- PY311DF08: sqlite3 named placeholders with sequences deprecated
- PY311DF09: shutil.rmtree onerror parameter deprecated
- PY311DF10: typing.Hashable deprecated (removal in 3.14)
- PY311DF11: typing.Sized deprecated (removal in 3.14)
- PY311DF12: typing.ByteString deprecated (removal in 3.14)
- PY311DF13: locale.getdefaultlocale() deprecated (removal in 3.15)
- PY311DF14: pathlib.PurePath.is_reserved() deprecated (removal in 3.15)
- PY311DF15: typing.no_type_check_decorator() deprecated (removal in 3.15)
- PY311DF16: asyncio.iscoroutinefunction() deprecated (removal in 3.16)
- PY311DF17: asyncio event loop policy deprecated (removal in 3.16)
- PY311DF18: Bitwise inversion on bool deprecated (removal in 3.16)
- PY311DF19: collections.abc.ByteString deprecated (removal in 3.17)
- PY311DF20: configparser.LegacyInterpolation deprecated (removal in 3.13)
- PY311DF21: locale.resetlocale() deprecated (removal in 3.13)
- PY311DF22: unittest find functions deprecated (removal in 3.13)
- PY311DF23: webbrowser.MacOSX deprecated (removal in 3.13)
- PY311DF24: calendar deprecated constants
- PY311DF25: codecs.open() soft-deprecated
- PY311DF26: http.server.CGIHTTPRequestHandler soft-deprecated
- PY311DF27: email.utils.localtime isdst parameter deprecated

**syntax_changes.yaml** (20 rules):
- PY311SC01: Type parameter syntax available (PEP 695)
- PY311SC02: Type alias statement available (type X = ...)
- PY311SC03: F-string quote reuse available (PEP 701)
- PY311SC04: F-string backslashes available
- PY311SC05: F-string multi-line expressions available
- PY311SC06: F-string arbitrary nesting available
- PY311SC07: TypedDict Unpack for **kwargs available (PEP 692)
- PY311SC08: Override decorator available (PEP 698)
- PY311SC09: Comprehension inlining behavioral changes (PEP 709)
- PY311SC10: Improved error messages
- PY311SC11: Buffer protocol __buffer__() available (PEP 688)
- PY311SC12: collections.abc.Buffer ABC available
- PY311SC13: Slices now hashable
- PY311SC14: Null bytes in source now SyntaxError
- PY311SC15: Invalid escape sequences now warnings
- PY311SC16: Assignment expressions in comprehensions relaxed
- PY311SC17: ExceptionGroup unwrapping behavior changed
- PY311SC18: Garbage collection timing changed
- PY311SC19: Boolean parameter acceptance relaxed
- PY311SC20: sum() improved accuracy

**stdlib_changes.yaml** (36 rules):
- PY311SL01: asyncio eager task factory available
- PY311SL02: asyncio.run() loop_factory parameter available
- PY311SL03: calendar.Month and calendar.Day enums available
- PY311SL04: csv.QUOTE_NOTNULL and csv.QUOTE_STRINGS available
- PY311SL05: inspect.markcoroutinefunction() available
- PY311SL06: inspect.getasyncgenstate() available
- PY311SL07: itertools.batched() available
- PY311SL08: math.sumprod() available
- PY311SL09: math.nextafter() steps parameter available
- PY311SL10: os.PIDFD_NONBLOCK flag available
- PY311SL11: os.listdrives/listvolumes/listmounts available
- PY311SL12: os.DirEntry.is_junction() available
- PY311SL13: os.path.isjunction() available
- PY311SL14: pathlib.Path subclassing support enhanced
- PY311SL15: pathlib.Path.walk() available
- PY311SL16: pathlib.Path.relative_to() walk_up parameter available
- PY311SL17: pathlib.Path.is_junction() available
- PY311SL18: pathlib.Path.glob() case_sensitive parameter available
- PY311SL19: random.binomialvariate() available
- PY311SL20: random.expovariate() default lambda available
- PY311SL21: shutil.rmtree() onexc parameter available
- PY311SL22: sqlite3 command-line interface available
- PY311SL23: sqlite3.Connection autocommit mode available
- PY311SL24: sqlite3.Connection.load_extension() entrypoint parameter available
- PY311SL25: sqlite3.Connection configuration methods available
- PY311SL26: statistics.correlation() ranked parameter available
- PY311SL27: sys.monitoring module available (PEP 669)
- PY311SL28: sys stack trampoline API available
- PY311SL29: sys.last_exc available
- PY311SL30: tempfile delete_on_close parameter available
- PY311SL31: types.get_original_bases() available
- PY311SL32: unittest --durations option available
- PY311SL33: uuid command-line interface available
- PY311SL34: unicodedata updated to Unicode 15.0
- PY311SL35: typing isinstance() protocols 2-20x faster
- PY311SL36: Performance improvements (comprehensions 2x faster, asyncio 75% faster)

**Key changes in Python 3.12:**
- PEP 695: Type parameter syntax (def func[T], type Alias = ...)
- PEP 701: F-string enhancements (quote reuse, backslashes, multi-line, nesting)
- PEP 692: TypedDict for **kwargs typing
- PEP 698: @override decorator for type checking
- PEP 709: Comprehension inlining (up to 2x faster)
- PEP 688: Buffer protocol accessible in Python
- PEP 669: Low-impact monitoring for profilers/debuggers
- PEP 684: Per-interpreter GIL (C API)
- PEP 683: Immortal objects for reference counting optimization
- PEP 632: distutils module removed
- Major module removals: distutils, imp, asynchat, asyncore, smtpd
- Many deprecations with scheduled removals (3.13-3.17)
- Significant performance improvements: comprehensions 2x, asyncio 75% faster
- Enhanced error messages with better suggestions
- pathlib improvements: walk(), subclassing support, junction detection
- asyncio: eager task execution, monitoring improvements
- New stdlib features: itertools.batched(), math.sumprod(), sys.monitoring

---

## Development Guide

### Adding New Rules

**Rule Structure:**
```yaml
- id: "PY{version}{category}{number}"  # e.g., PY312BC01
  name: "Human-readable name"
  category: "breaking_change|deprecation|syntax_change|stdlib_change"
  severity: "critical|high|medium|low"
  risk_level: "HIGH|MEDIUM|LOW"
  source_version: "3.X"
  target_version: "3.Y"
  detector: "DetectorClassName"  # Optional: custom detector class
  pattern:
    node_type: "Name|Call|Attribute|etc."  # AST node type
    attributes:
      id: "keyword_name"  # Attribute to match
  condition:
    not_in_context: ["context"]  # Optional: complex conditions
  message: "Description of the issue"
  suggestion: "How to fix it"
  examples:
    bad: "problematic code example"
    good: "corrected code example"
  references:
    - "https://docs.python.org/..."
    - "https://bugs.python.org/issue..."
```

**Steps to Add a Rule:**
1. Navigate to `rules/versions/{source_version}/` directory
2. Select appropriate category file:
   - `breaking_changes.yaml` - Code that will break
   - `deprecated_features.yaml` - Removed/deprecated features
   - `syntax_changes.yaml` - Syntax incompatibilities
   - `stdlib_changes.yaml` - Library API changes
3. Add rule following the structure above
4. Ensure ID follows format: `PY{VERSION}{CATEGORY}{NUMBER}`
5. Test with sample Python files
6. Verify in generated HTML reports

**AST Pattern Matching:**
- `node_type`: Any AST node type from `ast` module (Name, Call, Attribute, etc.)
- `attributes`: Key-value pairs to match in AST node
- `condition`: Advanced matching logic (optional)
  - `not_in_context`: Exclude matches in certain contexts
  - `has_parent`: Match only if parent node matches
  - `check_value`: Validate node value

### Testing Rules

**Manual Testing:**
```bash
# Create test file with problematic code
cat > test_code.py << 'EOF'
# Your test code here
EOF

# Run analyzer with verbose output
bini-analyzer analyze ./test_code.py --target 3.12 --verbose

# Check HTML report
open reports/report.html
```

**Testing Checklist:**
- [ ] Rule triggers on expected code patterns
- [ ] Rule doesn't trigger on similar but safe patterns
- [ ] Error message is clear and actionable
- [ ] Code examples are correct
- [ ] References are accurate
- [ ] Works across Python versions

### Debugging the Analyzer

**Enable Verbose Output:**
```bash
bini-analyzer analyze ./myproject --target 3.12 --verbose
```

**Common Issues:**

**Issue: Rule not triggering**
- Check AST node type using `ast.dump()` in Python
- Verify pattern attributes match exactly
- Ensure condition logic is correct
- Test with simpler patterns first

**Issue: False positives**
- Add `condition` section to refine matching
- Use `not_in_context` to exclude specific cases
- Review AST structure with `ast` module

**Issue: Syntax errors in analyzed code**
- Syntax errors are captured separately
- Check `syntax_changes.yaml` rules
- Review Python version compatibility

**Debug Tips:**
```python
# Inspect AST structure for any Python code
import ast
code = "your code here"
tree = ast.parse(code)
print(ast.dump(tree, indent=2))
```

### Common Development Workflows

**1. Adding Rules for New Python Version:**
```bash
# Create new version directory
mkdir rules/versions/3.13

# Copy template from previous version
cp rules/versions/3.12/*.yaml rules/versions/3.13/

# Review Python "What's New" documentation
# Update rules accordingly
# Test with sample code
```

**2. Fixing Bugs:**
1. Create minimal test case reproducing the bug
2. Add debug logging if needed
3. Fix the issue
4. Verify with test case
5. Check for regressions

**3. Performance Tuning:**
```bash
# Analyze large project
bini-analyzer analyze ./large-project --target 3.12 --verbose

# Monitor resource usage
bini-analyzer analyze ./project --target 3.12 --max-cpu 80 --max-memory 70

# Adjust worker count
bini-analyzer analyze ./project --target 3.12 --workers 4
```

**4. Documentation Updates:**
- Keep CLAUDE.md current with architecture changes
- Update rule counts when adding rules
- Document new features in appropriate sections
- Update README.md with usage examples

---

## Scope & Limitations

### What's In Scope

**Analysis Capabilities:**
- Static analysis only (no runtime execution)
- Python source files (.py, .pyw, .pyi)
- AST-based pattern matching
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

**Explicit Limitations:**
- **Windows-optimized**: Limited testing on Linux/macOS
- **No parallel processing**: Framework ready but not activated
- **Rule coverage**: Focuses on common Python features; edge cases may be missed
- **Memory usage**: Large projects may require significant RAM
- **False positives**: May flag code that works correctly
- **False negatives**: May miss some compatibility issues

### Known Limitations

**Technical Limitations:**
1. **Dynamic Features**: Cannot analyze code that uses `exec()`, `eval()`, or dynamic imports
2. **Type Checking**: Does not perform type checking beyond AST patterns
3. **Metaprogramming**: Limited analysis of metaclasses and decorators
4. **Conditional Imports**: May miss issues in version-specific imports
5. **Large Projects**: Performance may degrade on projects with thousands of files

**Design Limitations:**
1. **Windows Focus**: Primary development and testing on Windows
2. **No Auto-Fix**: Intentionally read-only to prevent code modification
3. **English Only**: Messages and documentation in English
4. **Python 3 Only**: Does not support Python 2 to 3 upgrades

---

## Future Roadmap

### Planned Features

**Short-Term (3-6 months):**
- [ ] Implement parallel processing for faster analysis
- [ ] Add comprehensive test suite with unit and integration tests
- [ ] Create CI/CD pipeline for automated testing
- [ ] Improve error messages with more context
- [ ] Add more rules for edge cases and less common features

**Medium-Term (6-12 months):**
- [ ] Cross-platform support (Linux, macOS)
- [ ] IDE integration (VS Code, PyCharm)
- [ ] Plugin system for custom detectors
- [ ] Performance optimizations for large projects
- [ ] Additional Python version support (3.13+)

**Long-Term (12+ months):**
- [ ] Dependency analysis integration
- [ ] Virtual environment detection
- [ ] Auto-fix suggestions with patch generation
- [ ] Web-based report viewer
- [ ] REST API for programmatic access

### Community Contributions

**Areas for Contribution:**
- Adding new rules for Python versions
- Improving existing rule accuracy
- Cross-platform testing and fixes
- Documentation improvements
- Test case development
- Performance optimizations
- Bug fixes and feature requests

**Contribution Guidelines:**
1. Follow existing code style and patterns
2. Add tests for new features
3. Update documentation
4. Submit pull requests with clear descriptions
5. Include test cases demonstrating issues

---

## Architecture Summary

Bini follows a clean, modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                     CLI Layer                            │
│              (bini_analyzer.py)                          │
│  - Argument parsing                                      │
│  - Command routing                                       │
│  - Graceful interruption                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              Configuration Layer                         │
│         (config/config_loader.py)                        │
│  - YAML config loading                                   │
│  - CLI argument merging                                  │
│  - Validation                                            │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│          Analysis Orchestrator                            │
│     (core/analysis_orchestrator.py)                      │
│  - File discovery                                        │
│  - Version detection                                     │
│  - Rule loading                                          │
│  - Analysis coordination                                 │
└───┬──────────┬──────────┬──────────┬────────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────┐ ┌─────────┐
│Parsing │ │ Rules  │ │ Det.  │ │Result   │
│ Layer  │ │System  │ │Layer │ │Process. │
└────────┘ └────────┘ └──────┘ └─────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────┐ ┌─────────┐
│ AST    │ │YAML   │ │Base  │ │Risk     │
│Parser  │ │Rules  │ │Det.  │ │Calc.    │
└────────┘ └────────┘ └──────┘ └─────────┘
                                  │
                                  ▼
                            ┌─────────┐
                            │Reporting│
                            │ Layer   │
                            └─────────┘
```

**Data Flow:**
1. **Config** → Load from file/defaults, merge with CLI, validate
2. **File Discovery** → Find all Python files in source directory
3. **Version Detection** → Auto-detect or use provided source version
4. **Rule Loading** → Load YAML rules for all intermediate versions
5. **File Analysis** (per file):
   - Parse to AST
   - Handle syntax errors
   - Execute all rules
   - Aggregate results
6. **Report Generation** → Create HTML with embedded JSON

**Key Design Principles:**
- **Modularity**: Each component has a single responsibility
- **Extensibility**: Easy to add new rules and detectors
- **Performance**: Framework ready for parallel processing
- **User Safety**: Never modifies user code
- **Offline-First**: No external dependencies during analysis

---
