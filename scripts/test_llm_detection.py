"""
Test script for LLM-based detection with Ollama.

This script:
1. Checks if Ollama is running
2. Verifies qwen2.5:7b model is available
3. Tests LLM detection on sample code
"""

import sys
import ast
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from detection.llm import OllamaClient, OllamaConfig, HybridDetector, TextDetector
import yaml


def test_ollama_connection():
    """Test Ollama service connection."""
    print("=" * 60)
    print("Testing Ollama Connection")
    print("=" * 60)

    client = OllamaClient()

    print(f"Ollama host: {client.config.host}")
    print(f"Model: {client.config.model}")
    print()

    # Check availability
    print("Checking if Ollama is available...")
    if client.is_available():
        print("[OK] Ollama service is running")
    else:
        print("[ERROR] Ollama service is not available")
        print("Please start Ollama with: ollama serve")
        return False

    # List models
    print("\nListing available models...")
    models = client.list_models()
    if models:
        print(f"[OK] Found {len(models)} models:")
        for model in models:
            marker = " (ACTIVE)" if model == client.config.model else ""
            print(f"  - {model}{marker}")
    else:
        print("[WARNING] No models found")

    # Check if qwen2.5:7b is available
    if client.config.model not in models:
        print(f"\n[WARNING] {client.config.model} is not available")
        print(f"Please pull it with: ollama pull {client.config.model}")
        return False

    print(f"\n[OK] {client.config.model} is ready!")
    return True


def test_simple_generation():
    """Test basic LLM generation."""
    print("\n" + "=" * 60)
    print("Testing Basic LLM Generation")
    print("=" * 60)

    client = OllamaClient()

    prompt = "What is Python? Answer in one sentence."
    print(f"Prompt: {prompt}")
    print("\nGenerating response...")

    result = client.generate(prompt)

    if result["success"]:
        print(f"[OK] Response: {result['response']}")
        print(f"Tokens: {result['metadata'].get('eval_count', 'N/A')}")
        print(f"Duration: {result['metadata'].get('total_duration', 'N/A')} ns")
        return True
    else:
        print(f"[ERROR] {result['error']}")
        return False


def test_code_analysis():
    """Test code analysis capability."""
    print("\n" + "=" * 60)
    print("Testing Code Analysis")
    print("=" * 60)

    client = OllamaClient()

    test_code = """
async = True  # This should be flagged in Python 3.7+
result = await_for_result()
"""

    print("Test code:")
    print(test_code)
    print("\nAnalyzing...")

    result = client.analyze_code(
        code=test_code,
        analysis_type="Python 3.7 keyword compatibility",
        context="Check if 'async' or 'await' are used as variable names"
    )

    if result["success"]:
        print(f"[OK] Analysis complete")
        parsed = result.get("parsed", {})
        print(f"Issue detected: {parsed.get('issue', 'UNKNOWN')}")
        print(f"Confidence: {parsed.get('confidence', 'UNKNOWN')}")
        print(f"Explanation: {parsed.get('explanation', 'N/A')}")
        return True
    else:
        print(f"[ERROR] {result['error']}")
        return False


def test_hybrid_detection():
    """Test hybrid detection with actual rule."""
    print("\n" + "=" * 60)
    print("Testing Hybrid Detection")
    print("=" * 60)

    # Load a hybrid rule
    rules_file = project_root / 'rules' / 'versions' / '3.6' / 'deprecated_features.yaml'

    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = yaml.safe_load(f)

    # Find PY36DF01 (yield in comprehensions - should be hybrid)
    test_rule = None
    for rule in rules:
        detection = rule.get('detection', {})
        if detection.get('strategy') == 'hybrid':
            test_rule = rule
            break

    if not test_rule:
        print("[WARNING] No hybrid rules found in test file")
        return False

    print(f"Testing rule: {test_rule['id']} - {test_rule['name']}")
    print(f"Strategy: {test_rule['detection']['strategy']}")
    print()

    # Test code with yield in comprehension (should trigger)
    bad_code = """
result = [yield x for x in range(10)]
"""

    # Test code with yield in nested function (should NOT trigger)
    good_code = """
def gen():
    yield 1

result = [gen() for x in range(10)]
"""

    print("Test 1: Bad code (should detect issue)")
    print(bad_code)

    detector = HybridDetector(test_rule)
    detector.source_lines = bad_code.split('\n')
    tree = ast.parse(bad_code)
    issues = detector.detect(tree, 'test_bad.py')

    print(f"Issues found: {len(issues)}")
    if issues:
        print(f"[OK] Correctly detected issue")
        for issue in issues:
            print(f"  - {issue.message[:100]}...")
    else:
        print(f"[WARNING] Expected to detect issue but found none")

    print("\nTest 2: Good code (should NOT detect issue)")
    print(good_code)

    detector.source_lines = good_code.split('\n')
    tree = ast.parse(good_code)
    issues = detector.detect(tree, 'test_good.py')

    print(f"Issues found: {len(issues)}")
    if not issues:
        print(f"[OK] Correctly identified as safe")
    else:
        print(f"[WARNING] False positive detected")

    return True


def test_text_detection():
    """Test text/semantic detection."""
    print("\n" + "=" * 60)
    print("Testing Text/Semantic Detection")
    print("=" * 60)

    # Load a text rule
    rules_file = project_root / 'rules' / 'versions' / '3.9' / 'breaking_changes.yaml'

    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = yaml.safe_load(f)

    # Find text detection rule
    test_rule = None
    for rule in rules:
        detection = rule.get('detection', {})
        if detection.get('strategy') == 'text':
            test_rule = rule
            break

    if not test_rule:
        print("[WARNING] No text detection rules found")
        return False

    print(f"Testing rule: {test_rule['id']} - {test_rule['name']}")
    print(f"Strategy: {test_rule['detection']['strategy']}")
    print()

    # Test code
    test_code = """
# Deleting __debug__
del __debug__
"""

    print("Test code:")
    print(test_code)
    print("\nAnalyzing...")

    detector = TextDetector(test_rule)
    detector.source_lines = test_code.split('\n')
    tree = ast.parse(test_code)
    issues = detector.detect(tree, 'test_text.py')

    print(f"Issues found: {len(issues)}")
    if issues:
        print(f"[OK] Detected semantic issue")
        for issue in issues:
            print(f"  - {issue.message[:100]}...")
    else:
        print(f"[WARNING] Expected to detect issue")

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Detection Test Suite")
    print("=" * 60)
    print()

    # Test 1: Connection
    if not test_ollama_connection():
        print("\n[FAILED] Ollama connection test failed")
        print("Please ensure Ollama is running and qwen2.5:7b is installed")
        return

    # Test 2: Simple generation
    if not test_simple_generation():
        print("\n[FAILED] Simple generation test failed")
        return

    # Test 3: Code analysis
    if not test_code_analysis():
        print("\n[FAILED] Code analysis test failed")
        return

    # Test 4: Hybrid detection
    try:
        test_hybrid_detection()
    except Exception as e:
        print(f"\n[ERROR] Hybrid detection test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 5: Text detection
    try:
        test_text_detection()
    except Exception as e:
        print(f"\n[ERROR] Text detection test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test Suite Complete")
    print("=" * 60)


if __name__ == '__main__':
    main()
