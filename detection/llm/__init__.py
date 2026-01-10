"""
LLM-based detection module for Python version compatibility analysis.

This package provides:
- Ollama client for local LLM inference
- Hybrid detectors (AST + LLM validation)
- Text/semantic detectors (pure LLM)
"""

from detection.llm.ollama_client import (
    OllamaClient,
    OllamaConfig,
    get_ollama_client
)
from detection.llm.llm_detector import (
    LLMDetector,
    HybridDetector,
    TextDetector,
    LLMDetectionResult,
    create_llm_detector
)

__all__ = [
    'OllamaClient',
    'OllamaConfig',
    'get_ollama_client',
    'LLMDetector',
    'HybridDetector',
    'TextDetector',
    'LLMDetectionResult',
    'create_llm_detector',
]
