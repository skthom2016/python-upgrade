"""
Ollama client wrapper for LLM-based code analysis.

This module provides a client for interacting with Ollama's local LLM API.
"""

import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Configuration for Ollama client."""
    host: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    temperature: float = 0.1  # Low temperature for deterministic analysis
    timeout: int = 30  # seconds
    max_tokens: Optional[int] = None


class OllamaClient:
    """Client for Ollama LLM API."""

    def __init__(self, config: Optional[OllamaConfig] = None):
        """
        Initialize Ollama client.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or OllamaConfig()
        self.base_url = f"{self.config.host}/api"

    def is_available(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            bool: True if Ollama is running and accessible
        """
        try:
            response = requests.get(
                f"{self.base_url}/tags",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> List[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names
        """
        try:
            response = requests.get(
                f"{self.base_url}/tags",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except requests.RequestException:
            return []

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate completion from Ollama.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            Dictionary with:
                - success: bool
                - response: str (if successful)
                - error: str (if failed)
                - metadata: dict (token counts, timing, etc.)
        """
        try:
            # Prepare request payload
            payload = {
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature or self.config.temperature,
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            if max_tokens or self.config.max_tokens:
                payload["options"]["num_predict"] = max_tokens or self.config.max_tokens

            # Make request
            response = requests.post(
                f"{self.base_url}/generate",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result.get("response", "").strip(),
                    "metadata": {
                        "model": result.get("model"),
                        "eval_count": result.get("eval_count"),
                        "eval_duration": result.get("eval_duration"),
                        "total_duration": result.get("total_duration"),
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "metadata": {}
                }

        except requests.Timeout:
            return {
                "success": False,
                "error": f"Request timed out after {self.config.timeout}s",
                "metadata": {}
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "metadata": {}
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "metadata": {}
            }

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Chat completion with message history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Optional temperature override

        Returns:
            Dictionary with success, response, and metadata
        """
        try:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature or self.config.temperature,
                }
            }

            response = requests.post(
                f"{self.base_url}/chat",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result.get("message", {}).get("content", "").strip(),
                    "metadata": {
                        "model": result.get("model"),
                        "eval_count": result.get("eval_count"),
                        "total_duration": result.get("total_duration"),
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "metadata": {}
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Chat request failed: {str(e)}",
                "metadata": {}
            }

    def analyze_code(
        self,
        code: str,
        analysis_type: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze code with specific analysis type.

        Args:
            code: Python code to analyze
            analysis_type: Type of analysis (e.g., "compatibility", "semantic")
            context: Optional context about what to look for

        Returns:
            Analysis result with success, response, and metadata
        """
        system_prompt = """You are a Python code analysis expert specializing in
version compatibility detection. Analyze code carefully and provide precise,
actionable feedback. Focus on detecting actual issues, not potential ones."""

        user_prompt = f"""Analysis Type: {analysis_type}

Code to analyze:
```python
{code}
```

{f"Context: {context}" if context else ""}

Analyze the code and respond with:
1. Whether an issue exists (YES/NO)
2. Explanation of the issue (if any)
3. Confidence level (HIGH/MEDIUM/LOW)

Format your response as:
ISSUE: YES/NO
CONFIDENCE: HIGH/MEDIUM/LOW
EXPLANATION: <your explanation>
"""

        result = self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt
        )

        if result["success"]:
            # Parse structured response
            response_text = result["response"]
            parsed = self._parse_analysis_response(response_text)
            result["parsed"] = parsed

        return result

    def _parse_analysis_response(self, response: str) -> Dict[str, str]:
        """
        Parse structured analysis response.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary with issue, confidence, explanation
        """
        parsed = {
            "issue": "UNKNOWN",
            "confidence": "LOW",
            "explanation": response
        }

        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("ISSUE:"):
                issue_val = line.replace("ISSUE:", "").strip().upper()
                if issue_val in ["YES", "NO"]:
                    parsed["issue"] = issue_val
            elif line.startswith("CONFIDENCE:"):
                conf_val = line.replace("CONFIDENCE:", "").strip().upper()
                if conf_val in ["HIGH", "MEDIUM", "LOW"]:
                    parsed["confidence"] = conf_val
            elif line.startswith("EXPLANATION:"):
                parsed["explanation"] = line.replace("EXPLANATION:", "").strip()

        return parsed


# Global client instance (lazy initialization)
_client: Optional[OllamaClient] = None


def get_ollama_client(config: Optional[OllamaConfig] = None) -> OllamaClient:
    """
    Get or create global Ollama client instance.

    Args:
        config: Optional configuration for new client

    Returns:
        OllamaClient instance
    """
    global _client
    if _client is None or config is not None:
        _client = OllamaClient(config)
    return _client
