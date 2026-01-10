# LLM Detection Implementation

This document describes the LLM-based detection system implementation for Bini Python upgrade analyzer using Ollama with qwen2.5:7b.

## Overview

The LLM detection system adds intelligent semantic analysis to reduce false positives and detect context-dependent compatibility issues that are difficult to identify with pure AST pattern matching.

### Key Features

- **Hybrid Detection**: AST pattern matching + LLM validation for context-dependent issues
- **Text/Semantic Detection**: Pure LLM analysis for runtime behavior changes
- **Ollama Integration**: Local LLM inference using qwen2.5:7b (no cloud dependencies)
- **Structured Prompts**: Carefully crafted prompts for consistent, reliable analysis
- **Graceful Degradation**: Falls back to AST-only detection if LLM is unavailable

## Architecture

```
┌─────────────────────────────────────────────────────┐
│             Analysis Orchestrator                    │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │         Rule Loading & Classification       │    │
│  │                                              │    │
│  │  - Load YAML rules                          │    │
│  │  - Check detection strategy                │    │
│  │  - Route to appropriate detector           │    │
│  └──────────┬──────────┬──────────┬────────────┘    │
│             │          │          │                  │
│             ▼          ▼          ▼                  │
│      ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│      │   AST    │ │  Hybrid  │ │   Text   │        │
│      │ Detector │ │ Detector │ │ Detector │        │
│      └──────────┘ └────┬─────┘ └────┬─────┘        │
│                         │            │               │
│                         │            │               │
│                         ▼            ▼               │
│                   ┌──────────────────────┐          │
│                   │   Ollama Client      │          │
│                   │   (qwen2.5:7b)       │          │
│                   └──────────────────────┘          │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Components

### 1. Ollama Client (`detection/llm/ollama_client.py`)

**Purpose**: Interface with Ollama's local LLM API

**Key Features**:
- Configurable model selection (default: qwen2.5:7b)
- Low temperature (0.1) for deterministic analysis
- Structured response parsing
- Error handling and graceful degradation
- Connection availability checking

**Example Usage**:
```python
from detection.llm import OllamaClient

client = OllamaClient()
if client.is_available():
    result = client.analyze_code(
        code="async = True",
        analysis_type="keyword compatibility",
        context="Check for reserved keyword usage"
    )
```

### 2. Hybrid Detector (`detection/llm/llm_detector.py`)

**Purpose**: Combine AST pattern matching with LLM validation

**How It Works**:
1. **AST Scan**: Use pattern matching to find potential issues
2. **LLM Validation**: For each match, ask LLM to validate if it's a true positive
3. **Confidence Assessment**: LLM provides HIGH/MEDIUM/LOW confidence level
4. **Issue Creation**: Only create issues for validated matches

**Example Rule** (PY36DF01 - Yield in comprehensions):
```yaml
detection:
  strategy: hybrid
  confidence: medium
  requires_llm: true
semantic_description: |
  Yield expressions in comprehensions are only deprecated when they appear
  directly in the comprehension body. If yield appears inside a nested
  function call within the comprehension, it's NOT deprecated.
detection_criteria:
  validation_prompt: |
    Check if this yield statement is a DIRECT child of the comprehension
    body (deprecated) vs inside a nested function call (safe).
```

**Process**:
```
Code: [yield x for x in range(10)]
  ↓
AST matches "yield in ListComp"
  ↓
Extract code snippet with context
  ↓
LLM validates: "Is this yield DIRECTLY in comprehension?"
  ↓
LLM response: ISSUE: YES, CONFIDENCE: HIGH
  ↓
Create Issue with LLM explanation
```

### 3. Text Detector (`detection/llm/llm_detector.py`)

**Purpose**: Detect semantic/runtime issues using pure LLM analysis

**How It Works**:
1. **Keyword Scan**: Find code sections with relevant keywords
2. **LLM Analysis**: Ask LLM to perform semantic analysis
3. **Contextual Understanding**: LLM considers runtime behavior, not just syntax
4. **Issue Creation**: Report semantic issues with explanation

**Example Rule** (PY39BC12 - `__debug__` deletion):
```yaml
detection:
  strategy: text
  confidence: medium
  requires_llm: true
semantic_description: |
  Deleting __debug__ involves runtime behavior changes.
  This requires LLM analysis to understand the context.
detection_criteria:
  text_keywords: ["__debug__", "del", "delete"]
  validation_prompt: |
    Analyze if this code attempts to delete __debug__.
    Consider runtime behavior and implications.
```

**Process**:
```
Code: del __debug__
  ↓
Find sections with keywords: ["__debug__", "del"]
  ↓
LLM analyzes: "Does this delete __debug__?"
  ↓
LLM response: ISSUE: YES, CONFIDENCE: HIGH
  ↓
Create Issue with semantic explanation
```

## Detection Strategies

Based on classification metadata added to 474 rules:

| Strategy | Count | % | LLM Required | Description |
|----------|-------|---|--------------|-------------|
| **AST** | 320 | 67.5% | No | Pure pattern matching |
| **Hybrid** | 5 | 1.1% | Yes | AST + LLM validation |
| **Text** | 2 | 0.4% | Yes | Pure LLM semantic analysis |
| **Info-Only** | 147 | 31.0% | No | Informational (new features) |

### Rules Requiring LLM

#### Hybrid Detection (5 rules):
1. **PY36BC16**: Direct instantiation of ssl.SSLSocket and ssl.SSLObject prohibited
2. **PY38DF04**: NotImplemented in boolean context deprecated
3. **PY39SL23**: typing.Literal behavior changes
4. **PY310BC13**: context manager TypeError instead of AttributeError
5. **PY311BC13**: ftplib.FTP_TLS.ssl_version attribute removed

#### Text Detection (2 rules):
1. **PY39BC12**: `__debug__` deletion now SyntaxError
2. **PY39BC13**: NaN hash values now identity-dependent

## Configuration

### Ollama Configuration

```python
from detection.llm import OllamaConfig

config = OllamaConfig(
    host="http://localhost:11434",  # Ollama server URL
    model="qwen2.5:7b",              # Model name
    temperature=0.1,                 # Low for deterministic analysis
    timeout=30,                      # Request timeout (seconds)
    max_tokens=None                  # No token limit
)
```

### Model Selection

**Recommended**: `qwen2.5:7b`
- Good balance of performance and accuracy
- Fast inference on consumer hardware
- Excellent code understanding
- Open source (Apache 2.0)

**Alternatives**:
- `qwen2.5:3b` - Faster but less accurate
- `qwen2.5:14b` - More accurate but slower
- Other Ollama models (codellama, mistral, etc.)

## Prompt Engineering

### System Prompt

```
You are a Python code analysis expert specializing in version
compatibility detection. Analyze code carefully and provide precise,
actionable feedback. Focus on detecting actual issues, not potential ones.
```

### User Prompt Structure

```
Analysis Type: {analysis_type}

Code to analyze:
```python
{code}
```

Context: {context}

Task: Determine if this code violates the rule described above.

Respond in this exact format:
ISSUE: YES or NO
CONFIDENCE: HIGH, MEDIUM, or LOW
EXPLANATION: Brief explanation of your analysis

Focus on:
1. Does the code match the pattern described in the rule?
2. Are there any context-specific conditions that make this safe?
3. Is this a true positive or a false alarm?

Be conservative - only flag issues you're confident about.
```

### Response Parsing

The system parses structured responses:

```python
response = """
ISSUE: YES
CONFIDENCE: HIGH
EXPLANATION: Using 'async' as a variable name violates Python 3.7+
keyword restrictions. This will cause a SyntaxError.
"""

parsed = {
    "issue": "YES",
    "confidence": "HIGH",
    "explanation": "Using 'async' as a variable name..."
}
```

## Testing

### Running Tests

```bash
# Run LLM detection test suite
python scripts/test_llm_detection.py
```

### Test Coverage

1. **Ollama Connection**: Verify service is running and model is available
2. **Basic Generation**: Test simple LLM text generation
3. **Code Analysis**: Test structured code analysis with validation
4. **Hybrid Detection**: Test AST + LLM validation workflow
5. **Text Detection**: Test pure semantic analysis

### Example Test Results

```
============================================================
LLM Detection Test Suite
============================================================

Testing Ollama Connection...
[OK] Ollama service is running
[OK] qwen2.5:7b is ready!

Testing Basic LLM Generation...
[OK] Response: Python is a high-level, interpreted programming language...
Tokens: 29
Duration: 973ms

Testing Code Analysis...
[OK] Analysis complete
Issue detected: YES
Confidence: LOW
Explanation: Using 'async' as a variable name violates Python 3.7+
             keyword restrictions...

Testing Text/Semantic Detection...
[OK] Detected semantic issue
  - Deleting __debug__ raises SyntaxError in Python 3.10.
  - LLM Semantic Analysis (HIGH confidence): The code explicitly
    attempts to delete the __debug__ constant...
```

## Performance

### Benchmarks (qwen2.5:7b on typical hardware)

| Operation | Time | Notes |
|-----------|------|-------|
| Connection check | <100ms | Fast availability check |
| Simple generation | ~1s | Basic text generation |
| Code analysis | ~2s | Structured analysis with validation |
| Hybrid detection (per match) | ~2-3s | AST + LLM validation |
| Text detection (per section) | ~3-4s | Full semantic analysis |

### Optimization Tips

1. **Batch Processing**: Group similar validations together
2. **Caching**: Cache LLM responses for identical code snippets
3. **Threshold Tuning**: Only use LLM for high-value validations
4. **Model Selection**: Use smaller models (3b) for simpler tasks

## Integration with Bini Analyzer

### Current Status

- ✅ LLM detection infrastructure implemented
- ✅ Ollama client wrapper created
- ✅ Hybrid and Text detectors implemented
- ✅ Test suite with sample rules passing
- ⏳ Integration into `analysis_orchestrator.py` (pending)
- ⏳ Configuration in `config/default_config.yaml` (pending)
- ⏳ CLI flags for LLM control (pending)

### Next Steps

1. **Orchestrator Integration**:
   - Load rules with LLM detection strategies
   - Route to appropriate detector based on strategy
   - Collect and aggregate LLM-powered issues

2. **Configuration**:
   - Add LLM settings to config file
   - CLI flags: `--enable-llm`, `--llm-model`, `--llm-host`
   - Graceful degradation if Ollama unavailable

3. **Reporting**:
   - Show LLM confidence in HTML reports
   - Distinguish AST vs LLM-validated issues
   - Performance metrics (LLM calls, timing)

4. **Documentation**:
   - User guide for Ollama setup
   - Model selection recommendations
   - Troubleshooting guide

## Troubleshooting

### Ollama Not Available

**Error**: `[ERROR] Ollama service is not available`

**Solution**:
```bash
# Start Ollama service
ollama serve

# In another terminal, pull the model
ollama pull qwen2.5:7b
```

### Model Not Found

**Error**: `[WARNING] qwen2.5:7b is not available`

**Solution**:
```bash
# Pull the model
ollama pull qwen2.5:7b

# List available models
ollama list
```

### Slow Response Times

**Solutions**:
1. Use smaller model: `qwen2.5:3b`
2. Increase timeout in config
3. Check system resources (RAM, GPU)
4. Reduce max_tokens if set

### Inconsistent Results

**Solutions**:
1. Lower temperature (already at 0.1)
2. Improve prompt specificity
3. Add more examples in prompts
4. Use larger model for better accuracy

## Future Enhancements

1. **Rule-Specific Prompts**: Custom prompts per rule for better accuracy
2. **Few-Shot Learning**: Include examples in prompts
3. **Confidence Calibration**: Tune confidence thresholds based on testing
4. **Multi-Model Support**: Support for different LLM backends (OpenAI, Anthropic, etc.)
5. **Explanation Quality**: Improve LLM explanations with better prompting
6. **Performance Monitoring**: Track LLM accuracy and adjust strategies

## References

- [Ollama Documentation](https://ollama.ai/docs)
- [Qwen2.5 Model Card](https://ollama.ai/library/qwen2.5)
- [Python AST Documentation](https://docs.python.org/3/library/ast.html)
- [Anthropic Prompt Engineering](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)

## License

This implementation follows the project's license (see LICENSE file).

## Contributors

- LLM Detection System: Implemented 2026-01-10
- Ollama Integration: qwen2.5:7b
- Classification: 474 rules across Python 3.6-3.12
