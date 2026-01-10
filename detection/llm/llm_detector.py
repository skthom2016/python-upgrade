"""
LLM-based detectors for Python version compatibility analysis.

This module provides:
- Hybrid detection (AST + LLM validation)
- Text/semantic detection (pure LLM analysis)
"""

import ast
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from detection.llm.ollama_client import get_ollama_client, OllamaConfig
from detection.base_detector import BaseDetector
from reporting.data_models import Issue, Location, Severity


@dataclass
class LLMDetectionResult:
    """Result from LLM detection."""
    has_issue: bool
    confidence: str  # HIGH, MEDIUM, LOW
    explanation: str
    metadata: Dict[str, Any]


class LLMDetector(BaseDetector):
    """Base class for LLM-powered detectors."""

    def __init__(self, rule: Dict[str, Any], config: Optional[OllamaConfig] = None):
        """
        Initialize LLM detector.

        Args:
            rule: Rule dictionary with detection metadata
            config: Optional Ollama configuration
        """
        # Store rule before calling parent init
        self.rule = rule

        # Call parent init with version info
        super().__init__(
            target_version=rule.get('target_version', '3.7'),
            source_version=rule.get('source_version', '3.6')
        )

        self.ollama = get_ollama_client(config)
        self.detection_config = rule.get('detection', {})
        self.detection_criteria = rule.get('detection_criteria', {})
        self.semantic_description = rule.get('semantic_description', '')

    def is_llm_available(self) -> bool:
        """Check if LLM service is available."""
        return self.ollama.is_available()

    def extract_code_snippet(self, node: ast.AST, source_lines: List[str]) -> str:
        """
        Extract code snippet for a node with context.

        Args:
            node: AST node
            source_lines: Source code lines

        Returns:
            Code snippet with surrounding context
        """
        if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
            return ""

        # Get lines with context (2 lines before/after)
        start_line = max(0, node.lineno - 3)
        end_line = min(len(source_lines), node.end_lineno + 2)

        snippet_lines = source_lines[start_line:end_line]
        return '\n'.join(snippet_lines)

    def create_validation_prompt(
        self,
        code_snippet: str,
        rule_name: str,
        validation_context: str
    ) -> str:
        """
        Create validation prompt for LLM.

        Args:
            code_snippet: Code to validate
            rule_name: Rule name
            validation_context: Context from detection_criteria

        Returns:
            Formatted prompt
        """
        prompt = f"""You are analyzing Python code for version compatibility issues.

Rule: {rule_name}

Context: {validation_context}

Code snippet:
```python
{code_snippet}
```

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
"""
        return prompt


class HybridDetector(LLMDetector):
    """
    Hybrid detector: AST pattern matching + LLM validation.

    This detector:
    1. Uses AST to find potential matches
    2. Uses LLM to validate if it's a true positive
    """

    def detect(self, node: ast.AST, file_path: str) -> List[Issue]:
        """
        Detect issues using hybrid approach.

        Args:
            node: AST tree (Module node)
            file_path: Path to source file

        Returns:
            List of detected issues
        """
        issues = []

        # Set context
        self.set_context(file_path, self.source_lines)

        # First, use AST to find potential matches
        ast_matches = self._ast_scan(node)

        if not ast_matches:
            return issues

        # If LLM is not available, return AST-only results with lower confidence
        if not self.is_llm_available():
            return self._create_ast_only_issues(ast_matches, self.source_lines)

        # Validate each AST match with LLM
        for node_match in ast_matches:
            llm_result = self._llm_validate(node_match, self.source_lines)

            if llm_result.has_issue:
                issue = self._create_issue(node_match, self.source_lines, llm_result)
                issues.append(issue)

        return issues

    def _ast_scan(self, tree: ast.AST) -> List[ast.AST]:
        """
        Scan AST for potential matches.

        Args:
            tree: AST tree

        Returns:
            List of matching AST nodes
        """
        pattern = self.rule.get('pattern', {})
        if not pattern:
            return []

        matches = []
        node_type = pattern.get('node_type')

        if node_type:
            # Simple AST traversal
            for node in ast.walk(tree):
                if node.__class__.__name__ == node_type:
                    # Check attributes if specified
                    attributes = pattern.get('attributes', {})
                    if self._matches_attributes(node, attributes):
                        matches.append(node)

        return matches

    def _matches_attributes(self, node: ast.AST, attributes: Dict[str, Any]) -> bool:
        """Check if node matches attribute criteria."""
        for attr_name, attr_value in attributes.items():
            if not hasattr(node, attr_name):
                return False

            node_value = getattr(node, attr_name)

            # Handle regex patterns
            if isinstance(attr_value, str) and attr_value.startswith('regex:'):
                import re
                pattern = attr_value.replace('regex:', '')
                if not re.match(pattern, str(node_value)):
                    return False
            elif node_value != attr_value:
                return False

        return True

    def _llm_validate(
        self,
        node: ast.AST,
        source_lines: List[str]
    ) -> LLMDetectionResult:
        """
        Validate AST match using LLM.

        Args:
            node: AST node to validate
            source_lines: Source code lines

        Returns:
            LLM detection result
        """
        # Extract code snippet
        code_snippet = self.extract_code_snippet(node, source_lines)

        # Get validation context
        validation_prompt_template = self.detection_criteria.get(
            'validation_prompt',
            self.semantic_description
        )

        # Create prompt
        prompt = self.create_validation_prompt(
            code_snippet=code_snippet,
            rule_name=self.rule.get('name', 'Unknown'),
            validation_context=validation_prompt_template
        )

        # Call LLM
        result = self.ollama.generate(
            prompt=prompt,
            system_prompt="You are a Python code analysis expert. Be precise and conservative."
        )

        if not result["success"]:
            # If LLM fails, return uncertain result
            return LLMDetectionResult(
                has_issue=False,
                confidence="LOW",
                explanation=f"LLM validation failed: {result.get('error', 'Unknown')}",
                metadata=result.get("metadata", {})
            )

        # Parse response
        parsed = result.get("parsed", {})
        if not parsed:
            # Try to parse manually
            response_text = result["response"]
            parsed = self._parse_response(response_text)

        return LLMDetectionResult(
            has_issue=(parsed.get("issue") == "YES"),
            confidence=parsed.get("confidence", "LOW"),
            explanation=parsed.get("explanation", response_text),
            metadata=result.get("metadata", {})
        )

    def _parse_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response."""
        parsed = {
            "issue": "NO",
            "confidence": "LOW",
            "explanation": response
        }

        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("ISSUE:"):
                issue_val = line.replace("ISSUE:", "").strip().upper()
                if "YES" in issue_val:
                    parsed["issue"] = "YES"
                elif "NO" in issue_val:
                    parsed["issue"] = "NO"
            elif line.startswith("CONFIDENCE:"):
                conf_val = line.replace("CONFIDENCE:", "").strip().upper()
                if "HIGH" in conf_val:
                    parsed["confidence"] = "HIGH"
                elif "MEDIUM" in conf_val:
                    parsed["confidence"] = "MEDIUM"
                elif "LOW" in conf_val:
                    parsed["confidence"] = "LOW"
            elif line.startswith("EXPLANATION:"):
                parsed["explanation"] = line.replace("EXPLANATION:", "").strip()

        return parsed

    def _create_ast_only_issues(
        self,
        nodes: List[ast.AST],
        source_lines: List[str]
    ) -> List[Issue]:
        """Create issues from AST matches without LLM validation."""
        issues = []
        for node in nodes:
            llm_result = LLMDetectionResult(
                has_issue=True,
                confidence="MEDIUM",
                explanation="LLM validation unavailable - AST pattern match only",
                metadata={}
            )
            issue = self._create_issue(node, source_lines, llm_result)
            issues.append(issue)
        return issues

    def _create_issue(
        self,
        node: ast.AST,
        source_lines: List[str],
        llm_result: LLMDetectionResult
    ) -> Issue:
        """Create Issue object from detection result."""
        location = Location(
            line=getattr(node, 'lineno', 0),
            column=getattr(node, 'col_offset', 0),
            end_line=getattr(node, 'end_lineno', getattr(node, 'lineno', 0)),
            end_column=getattr(node, 'end_col_offset', getattr(node, 'col_offset', 0))
        )

        # Extract code snippet
        code_snippet = self.extract_code_snippet(node, source_lines)

        # Create message with LLM explanation
        message = self.rule.get('message', '')
        if llm_result.explanation:
            message += f"\n\nLLM Analysis ({llm_result.confidence} confidence): {llm_result.explanation}"

        # Detection method depends on the detector type
        detection_method = 'hybrid' if isinstance(self, HybridDetector) else 'llm'

        # Debug print
        print(f"[DEBUG] Creating issue {self.rule.get('id', 'UNKNOWN')} with detection_method={detection_method}")

        return Issue(
            id=self.rule.get('id', 'UNKNOWN'),
            file_path=self.file_path,  # Set from context
            location=location,
            severity=self.rule.get('severity', 'medium'),
            category=self.rule.get('category', 'unknown'),
            risk_level=self.rule.get('risk_level', 'MEDIUM'),
            message=message,
            suggestion=self.rule.get('suggestion', ''),
            code_snippet=code_snippet,
            affected_versions=[self.target_version],
            references=self.rule.get('references', []),
            detection_method=detection_method
        )


class TextDetector(LLMDetector):
    """
    Text/Semantic detector: Pure LLM-based analysis.

    This detector relies entirely on LLM to detect semantic issues
    that can't be reliably detected with AST patterns.
    """

    def detect(self, node: ast.AST, file_path: str) -> List[Issue]:
        """
        Detect issues using pure LLM analysis.

        Args:
            node: AST tree (Module node)
            file_path: Path to source file

        Returns:
            List of detected issues
        """
        # Set context
        self.set_context(file_path, self.source_lines)

        if not self.is_llm_available():
            # Cannot perform text detection without LLM
            return []

        issues = []

        # Get text keywords from detection criteria
        keywords = self.detection_criteria.get('text_keywords', [])

        # Scan source code for relevant sections
        candidate_sections = self._find_candidate_sections(
            self.source_lines,
            keywords
        )

        # Analyze each candidate section with LLM
        for start_line, end_line, code in candidate_sections:
            llm_result = self._llm_analyze(code)

            if llm_result.has_issue:
                issue = self._create_text_issue(
                    start_line,
                    end_line,
                    code,
                    llm_result
                )
                issues.append(issue)

        return issues

    def _find_candidate_sections(
        self,
        source_lines: List[str],
        keywords: List[str]
    ) -> List[tuple[int, int, str]]:
        """
        Find code sections that might match the rule.

        Args:
            source_lines: Source code lines
            keywords: Keywords to look for

        Returns:
            List of (start_line, end_line, code) tuples
        """
        if not keywords:
            # No keywords - analyze entire file in chunks
            return [(0, len(source_lines), '\n'.join(source_lines))]

        sections = []
        source_text = '\n'.join(source_lines).lower()

        # Check if any keyword appears in source
        for keyword in keywords:
            if keyword.lower() in source_text:
                # Found keyword - return entire file for analysis
                # (Can be optimized to return specific sections)
                sections.append((0, len(source_lines), '\n'.join(source_lines)))
                break

        return sections

    def _llm_analyze(self, code: str) -> LLMDetectionResult:
        """
        Analyze code using pure LLM.

        Args:
            code: Code to analyze

        Returns:
            LLM detection result
        """
        # Create semantic analysis prompt
        prompt = f"""You are analyzing Python code for semantic compatibility issues.

Rule: {self.rule.get('name', 'Unknown')}

Description: {self.semantic_description}

Validation criteria:
{self.detection_criteria.get('validation_prompt', 'Analyze for issues')}

Code to analyze:
```python
{code}
```

Task: Determine if this code has the semantic issue described above.

Respond in this exact format:
ISSUE: YES or NO
CONFIDENCE: HIGH, MEDIUM, or LOW
EXPLANATION: Detailed explanation of your analysis

Be thorough but conservative. Only flag real issues.
"""

        result = self.ollama.generate(
            prompt=prompt,
            system_prompt="You are a Python semantic analysis expert. Analyze code carefully for runtime behavior issues."
        )

        if not result["success"]:
            return LLMDetectionResult(
                has_issue=False,
                confidence="LOW",
                explanation=f"LLM analysis failed: {result.get('error', 'Unknown')}",
                metadata=result.get("metadata", {})
            )

        # Parse response
        response_text = result["response"]
        parsed = self._parse_response(response_text)

        return LLMDetectionResult(
            has_issue=(parsed.get("issue") == "YES"),
            confidence=parsed.get("confidence", "LOW"),
            explanation=parsed.get("explanation", response_text),
            metadata=result.get("metadata", {})
        )

    def _parse_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response (same as HybridDetector)."""
        parsed = {
            "issue": "NO",
            "confidence": "LOW",
            "explanation": response
        }

        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("ISSUE:"):
                issue_val = line.replace("ISSUE:", "").strip().upper()
                if "YES" in issue_val:
                    parsed["issue"] = "YES"
                elif "NO" in issue_val:
                    parsed["issue"] = "NO"
            elif line.startswith("CONFIDENCE:"):
                conf_val = line.replace("CONFIDENCE:", "").strip().upper()
                if "HIGH" in conf_val:
                    parsed["confidence"] = "HIGH"
                elif "MEDIUM" in conf_val:
                    parsed["confidence"] = "MEDIUM"
                elif "LOW" in conf_val:
                    parsed["confidence"] = "LOW"
            elif line.startswith("EXPLANATION:"):
                parsed["explanation"] = line.replace("EXPLANATION:", "").strip()

        return parsed

    def _create_text_issue(
        self,
        start_line: int,
        end_line: int,
        code: str,
        llm_result: LLMDetectionResult
    ) -> Issue:
        """Create Issue object from text detection result."""
        location = Location(
            line=start_line + 1,
            column=0,
            end_line=end_line,
            end_column=0
        )

        # Create message with LLM analysis
        message = self.rule.get('message', '')
        message += f"\n\nLLM Semantic Analysis ({llm_result.confidence} confidence): {llm_result.explanation}"

        return Issue(
            id=self.rule.get('id', 'UNKNOWN'),
            file_path=self.file_path,  # Set from context
            location=location,
            severity=self.rule.get('severity', 'medium'),
            category=self.rule.get('category', 'unknown'),
            risk_level=self.rule.get('risk_level', 'MEDIUM'),
            message=message,
            suggestion=self.rule.get('suggestion', ''),
            code_snippet=code,
            affected_versions=[self.target_version],
            references=self.rule.get('references', [])
        )


def create_llm_detector(rule: Dict[str, Any], config: Optional[OllamaConfig] = None) -> Optional[LLMDetector]:
    """
    Factory function to create appropriate LLM detector based on rule strategy.

    Args:
        rule: Rule dictionary with detection metadata
        config: Optional Ollama configuration

    Returns:
        HybridDetector, TextDetector, or None based on strategy
    """
    detection = rule.get('detection', {})
    strategy = detection.get('strategy')

    if strategy == 'hybrid':
        return HybridDetector(rule, config)
    elif strategy == 'text':
        return TextDetector(rule, config)
    else:
        return None
