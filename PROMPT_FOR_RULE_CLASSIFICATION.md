# Prompt: Apply Detection Strategy Metadata to All Rules

## Context

I'm working on the Bini Python upgrade analysis tool. We've established a multi-strategy detection system to reduce false positives by classifying rules into different detection strategies (AST, Hybrid, Text/LLM, Info-Only).

**Status**: Classification patterns approved. Ready to apply metadata to all 475+ rules across Python versions 3.6-3.12.

**Project Location**: `D:\Santhosh\latestdev\bini-py-upgrade`

**Files to Modify**: All YAML files in `rules/versions/{3.6,3.7,3.8,3.9,3.10,3.11}/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`

---

## Detection Strategy Patterns (Approved)

### **Strategy 1: AST-Based (Pure Pattern Matching)**
- **Confidence**: HIGH
- **LLM Required**: NO
- **Priority**: Based on severity (critical/high/medium/low)
- **Use for**: Module imports, function removals, syntax keywords, decorators, new features
- **Estimated**: ~70% of rules

**Examples:**
- `import parser`, `import distutils` (module removal)
- `datetime.utcnow()`, `imp.load_module()` (function removal)
- `async`, `await` as variable names (syntax keywords)
- `@asyncio.coroutine` (decorator changes)
- `import contextvars`, `import dataclasses` (new features)

---

### **Strategy 2: Hybrid (AST + LLM Validation)**
- **Confidence**: MEDIUM
- **LLM Required**: YES (always validate)
- **Priority**: Based on severity
- **Use for**: Context-dependent deprecations, behavioral changes, edge cases
- **Estimated**: ~20% of rules

**Examples:**
- `yield` in comprehensions (need to check if direct child vs nested function)
- `collections.namedtuple()` parameter changes (validate if problematic)
- `ssl.wrap_socket()` calls (check if secure parameters used)
- Return type changes with subclasses

---

### **Strategy 3: Text/LLM-Based (Semantic Analysis)**
- **Confidence**: MEDIUM-LOW
- **LLM Required**: YES
- **Priority**: Based on severity
- **Use for**: Runtime behavior changes, implicit behavior changes, complex API semantics
- **Estimated**: ~5% of rules

**Examples:**
- Integer string conversion limits
- NaN hash value changes
- `__debug__` deletion behavior
- Performance-related changes

---

### **Strategy 4: Info-Only (No Detection)**
- **Confidence**: N/A
- **LLM Required**: NO
- **Priority**: info
- **Use for**: New features, performance improvements, documentation updates
- **Estimated**: ~5% of rules

**Examples:**
- `itertools.batched()` new function
- `math.sumprod()` new function
- "1.25x faster" performance notes

---

## Rule Metadata Structure to Add

Add a `detection` section to each rule:

```yaml
- id: "PY36BC01"
  name: "Rule name here"
  category: "breaking_change"
  severity: "high"
  risk_level: "HIGH"
  source_version: "3.6"
  target_version: "3.7"

  # NEW: Add this detection section
  detection:
    strategy: "ast"              # Options: ast | hybrid | text | info_only
    confidence: "high"           # Options: high | medium | low
    requires_llm: false          # Options: true | false
    priority: "high"             # Options: critical | high | medium | low | info
                                # Maps from severity: critical->critical, high->high, medium->medium, low->low, info->info

  # Optional: For hybrid/text strategies
  semantic_description: |
    Human-readable description for LLM to understand context.
    Explain what makes this rule trigger and when it's a false positive.

  detection_criteria:
    ast_pattern: "Brief description of AST pattern"
    text_keywords: ["keyword1", "keyword2", "keyword3"]
    validation_prompt: |
      Specific prompt for LLM validation.
      Explain exactly what to check.

  # Existing fields below (unchanged)
  description: |
    Original description...
  detector: "DetectorName"
  pattern:
    node_type: "..."
  condition:
    ...
  message: "..."
  suggestion: "..."
  examples:
    bad: "..."
    good: "..."
  references:
    - "..."
```

---

## Priority Mapping from Severity

```python
priority_mapping = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "info"
}
```

---

## Action Plan

### Step 1: Read All Rule Files
Read all YAML files from:
- `rules/versions/3.6/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`
- `rules/versions/3.7/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`
- `rules/versions/3.8/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`
- `rules/versions/3.9/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`
- `rules/versions/3.10/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`
- `rules/versions/3.11/{breaking_changes,deprecated_features,syntax_changes,stdlib_changes}.yaml`

### Step 2: Classify Each Rule

For each rule, determine:

1. **Strategy** based on:
   - **AST**: If it's a clear import, function call, decorator, or syntax keyword
   - **Hybrid**: If it needs context validation (yield in comprehension, behavioral changes, conditional deprecations)
   - **Text**: If it's runtime behavior, implicit changes, or complex semantics
   - **Info-Only**: If it's a new feature announcement or performance note

2. **Confidence** based on:
   - **High**: Clear AST patterns, no ambiguity
   - **Medium**: Some context needed, may have edge cases
   - **Low**: Highly context-dependent, hard to detect statically

3. **Requires LLM**:
   - `true` for hybrid and text strategies
   - `false` for ast and info_only strategies

4. **Priority**:
   - Map directly from severity field

5. **Semantic Description** (for hybrid/text only):
   - Explain the context
   - Describe what makes it trigger
   - Note when it's a false positive

6. **Detection Criteria**:
   - `ast_pattern`: Brief AST pattern description
   - `text_keywords`: 3-5 relevant keywords
   - `validation_prompt`: Specific LLM instructions

### Step 3: Update Each YAML File

For each YAML file:
1. Read all rules
2. Add `detection` section to each rule (after `target_version`, before `description`)
3. Maintain all existing fields unchanged
4. Preserve YAML formatting and structure
5. Write updated file back

### Step 4: Create Summary Report

After updating all files, generate a report showing:
```
Detection Strategy Classification Summary
===========================================

Total Rules Classified: X

By Strategy:
  AST-Based:        X (XX%) - No LLM required
  Hybrid:           X (XX%) - LLM validation required
  Text/LLM:         X (XX%) - Pure LLM analysis
  Info-Only:        X (XX%) - Documentation only

By Version:
  Python 3.6: X rules
  Python 3.7: X rules
  Python 3.8: X rules
  Python 3.9: X rules
  Python 3.10: X rules
  Python 3.11: X rules

By Category:
  breaking_changes: X rules
  deprecated_features: X rules
  syntax_changes: X rules
  stdlib_changes: X rules

By Priority:
  critical: X rules
  high: X rules
  medium: X rules
  low: X rules
  info: X rules
```

---

## Classification Guidelines by Category

### breaking_changes.yaml
- **AST**: Module removals, function removals, clear API changes
- **Hybrid**: Behavioral changes, return type changes, parameter removals with context
- **Text**: Runtime behavior changes

### deprecated_features.yaml
- **AST**: Module deprecations, clear function deprecations
- **Hybrid**: Context-dependent deprecations, conditional deprecations
- **Text**: Semantic deprecations with edge cases

### syntax_changes.yaml
- **AST**: Almost all syntax changes (keywords, operators, syntax structures)
- **Info-Only**: New feature announcements (PEPs available but optional)

### stdlib_changes.yaml
- **AST**: New module imports, new function additions, clear API additions
- **Hybrid**: API changes with behavioral differences
- **Info-Only**: New features, performance improvements

---

## Examples of Properly Classified Rules

### Example 1: AST-Based (Module Removal)
```yaml
- id: "PY39BC01"
  name: "parser module removed"
  category: "breaking_change"
  severity: "high"
  risk_level: "HIGH"
  source_version: "3.9"
  target_version: "3.10"
  detection:
    strategy: "ast"
    confidence: "high"
    requires_llm: false
    priority: "high"
  description: |
    The parser module was deprecated in Python 3.9 and removed in 3.10.
```

### Example 2: AST-Based (Function Call)
```yaml
- id: "PY311DF01"
  name: "datetime.utcnow() deprecated"
  category: "deprecation"
  severity: "medium"
  risk_level: "MEDIUM"
  source_version: "3.11"
  target_version: "3.12"
  detection:
    strategy: "ast"
    confidence: "high"
    requires_llm: false
    priority: "medium"
  description: |
    datetime.utcnow() is deprecated in Python 3.12 and will be removed in 3.15.
```

### Example 3: Hybrid (Context-Dependent)
```yaml
- id: "PY36DF01"
  name: "Yield expressions in comprehensions deprecated"
  category: "deprecation"
  severity: "medium"
  risk_level: "MEDIUM"
  source_version: "3.6"
  target_version: "3.8"
  detection:
    strategy: "hybrid"
    confidence: "medium"
    requires_llm: true
    priority: "medium"
  semantic_description: |
    Yield expressions in comprehensions are only deprecated when they appear
    directly in the comprehension body. If yield appears inside a nested
    function call within the comprehension, it's NOT deprecated.
  detection_criteria:
    ast_pattern: "Yield node inside ListComp/SetComp/DictComp/GeneratorExp"
    text_keywords: ["yield", "yield from", "comprehension", "generator"]
    validation_prompt: |
      Check if this yield statement is a DIRECT child of the comprehension
      body (deprecated) vs inside a nested function call (safe).
      Only flag if yield is directly in the comprehension, not in a
      nested function like `[foo() for x in range(10)]` where foo() does yield.
  description: |
    Yield expressions (both 'yield' and 'yield from' clauses) are now
    deprecated in comprehensions and generator expressions.
```

### Example 4: Info-Only (New Feature)
```yaml
- id: "PY36SL01"
  name: "New contextvars module"
  category: "new_feature"
  severity: "info"
  risk_level: "INFO"
  source_version: "3.6"
  target_version: "3.7"
  detection:
    strategy: "info_only"
    confidence: null
    requires_llm: false
    priority: "info"
  description: |
    Python 3.7 introduces the new contextvars module for context variables.
```

---

## Important Notes

1. **Preserve all existing fields** - Only ADD the detection section, don't modify existing content
2. **Maintain YAML structure** - Keep proper indentation and formatting
3. **Be consistent** - Use the same structure across all rules
4. **Backup first** - Create .bak files before modifying
5. **Validate YAML** - Ensure files are valid YAML after changes
6. **Work systematically** - Process files in order: 3.6 → 3.7 → 3.8 → 3.9 → 3.10 → 3.11

---

## Output Expected

1. All 24 YAML files updated with detection metadata
2. Each of the 475+ rules has a complete `detection` section
3. A summary report showing classification distribution
4. Confirmation that all YAML files are valid

---

## How to Proceed

1. Read all YAML rule files systematically
2. Analyze each rule and add appropriate detection metadata
3. Update files with proper YAML formatting
4. Generate summary report
5. Validate all changes

Start with version 3.6 and work through to 3.11, processing all 4 category files for each version.

**Ready to begin!**
