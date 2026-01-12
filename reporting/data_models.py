"""
Data models for SecurePythonUpgradeProject.
Defines all data structures used throughout the analysis pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(Enum):
    """Issue categories."""
    BREAKING_CHANGE = "breaking_change"
    DEPRECATION = "deprecation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SYNTAX_ERROR = "syntax_error"
    FILE_ERROR = "file_error"
    ANALYSIS_ERROR = "analysis_error"


class RiskLevel(Enum):
    """Risk level buckets."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Location:
    """Source code location."""
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'line': self.line,
            'column': self.column,
            'end_line': self.end_line,
            'end_column': self.end_column,
        }


@dataclass
class Issue:
    """
    Represents a single compatibility issue found in the code.

    Attributes:
        id: Unique issue identifier (e.g., "PY3601")
        file_path: Path to the file containing the issue
        location: Location of the issue in the source code
        severity: Issue severity level
        category: Issue category
        risk_level: Risk level bucket (HIGH/MEDIUM/LOW)
        message: Human-readable issue description
        suggestion: Suggested fix
        code_snippet: Code snippet showing the issue
        affected_versions: List of Python versions affected
        references: Links to documentation or PEPs
        detection_method: How the issue was detected (ast, llm, hybrid)
        llm_validated: True if LLM checked this issue (two-phase workflow)
        llm_confirmed: True if LLM confirmed issue, False if rejected as FP
        llm_explanation: LLM reasoning for validation decision
        analysis_phase: Phase when issue was detected (ast_only or llm_validated)
    """
    id: str
    file_path: str
    location: Location
    severity: str
    category: str
    risk_level: str
    message: str
    suggestion: str
    code_snippet: str = ""
    affected_versions: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    detection_method: str = "ast"
    llm_validated: bool = False
    llm_confirmed: bool = True
    llm_explanation: str = ""
    analysis_phase: str = "ast_only"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'file_path': self.file_path,
            'location': self.location.to_dict(),
            'severity': self.severity,
            'category': self.category,
            'risk_level': self.risk_level,
            'message': self.message,
            'suggestion': self.suggestion,
            'code_snippet': self.code_snippet,
            'affected_versions': self.affected_versions,
            'references': self.references,
            'detection_method': self.detection_method,
            'llm_validated': self.llm_validated,
            'llm_confirmed': self.llm_confirmed,
            'llm_explanation': self.llm_explanation,
            'analysis_phase': self.analysis_phase,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Issue':
        """Create Issue from dictionary."""
        location = Location(
            line=data['location']['line'],
            column=data['location']['column'],
            end_line=data['location'].get('end_line'),
            end_column=data['location'].get('end_column'),
        )
        return cls(
            id=data['id'],
            file_path=data['file_path'],
            location=location,
            severity=data['severity'],
            category=data['category'],
            risk_level=data['risk_level'],
            message=data['message'],
            suggestion=data['suggestion'],
            code_snippet=data.get('code_snippet', ''),
            affected_versions=data.get('affected_versions', []),
            references=data.get('references', []),
            detection_method=data.get('detection_method', 'ast'),
            llm_validated=data.get('llm_validated', False),
            llm_confirmed=data.get('llm_confirmed', True),
            llm_explanation=data.get('llm_explanation', ''),
            analysis_phase=data.get('analysis_phase', 'ast_only'),
        )


@dataclass
class FileResult:
    """
    Analysis results for a single file.

    Attributes:
        path: Absolute path to the file
        relative_path: Relative path from project root
        issues: List of issues found in the file
        total_issues: Total number of issues
        by_severity: Count of issues by severity level
        by_category: Count of issues by category
        by_risk: Count of issues by risk level
        analysis_time_ms: Time taken to analyze the file
    """
    path: str
    relative_path: str
    issues: List[Issue] = field(default_factory=list)
    total_issues: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_risk: Dict[str, int] = field(default_factory=dict)
    analysis_time_ms: float = 0.0

    def __post_init__(self):
        """Calculate statistics after initialization."""
        self.total_issues = len(self.issues)
        self.by_severity = self._count_by_field('severity')
        self.by_category = self._count_by_field('category')
        self.by_risk = self._count_by_field('risk_level')

    def _count_by_field(self, field: str) -> Dict[str, int]:
        """Count issues by a specific field."""
        counts: Dict[str, int] = {}
        for issue in self.issues:
            value = getattr(issue, field, 'unknown')
            counts[value] = counts.get(value, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'path': self.path,
            'relative_path': self.relative_path,
            'total_issues': self.total_issues,
            'by_severity': self.by_severity,
            'by_category': self.by_category,
            'by_risk': self.by_risk,
            'analysis_time_ms': self.analysis_time_ms,
            'issues': [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileResult':
        """Create FileResult from dictionary."""
        issues = [Issue.from_dict(i) for i in data.get('issues', [])]
        return cls(
            path=data['path'],
            relative_path=data['relative_path'],
            issues=issues,
            analysis_time_ms=data.get('analysis_time_ms', 0.0),
        )


@dataclass
class AnalysisSummary:
    """
    Summary statistics for the entire analysis.

    Attributes:
        total_files: Total number of files analyzed
        total_issues: Total number of issues found
        files_with_issues: Number of files that have issues
        files_without_issues: Number of files with no issues
        by_risk: Issue counts by risk level
        by_severity: Issue counts by severity level
        by_category: Issue counts by category
        top_files: List of files with the most issues
        analysis_duration_seconds: Total analysis time
        rules_executed: Number of rules executed
        cache_hits: Number of cache hits
    """
    total_files: int
    total_issues: int
    files_with_issues: int
    files_without_issues: int
    by_risk: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    top_files: List[Dict[str, Any]] = field(default_factory=list)
    analysis_duration_seconds: float = 0.0
    rules_executed: int = 0
    cache_hits: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'total_files': self.total_files,
            'total_issues': self.total_issues,
            'files_with_issues': self.files_with_issues,
            'files_without_issues': self.files_without_issues,
            'by_risk': self.by_risk,
            'by_severity': self.by_severity,
            'by_category': self.by_category,
            'top_files': self.top_files,
            'analysis_duration_seconds': self.analysis_duration_seconds,
            'rules_executed': self.rules_executed,
            'cache_hits': self.cache_hits,
        }


@dataclass
class AnalysisResult:
    """
    Complete analysis result for a project.

    Attributes:
        metadata: Analysis metadata
        summary: Analysis summary statistics
        files: Results for each file
        timeline: Timeline of analysis runs
    """
    metadata: 'AnalysisMetadata'
    summary: AnalysisSummary
    files: List[FileResult]
    timeline: List['TimelineEntry'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'metadata': self.metadata.to_dict(),
            'summary': self.summary.to_dict(),
            'files': [f.to_dict() for f in self.files],
            'timeline': [t.to_dict() for t in self.timeline],
        }


@dataclass
class AnalysisMetadata:
    """
    Metadata about the analysis run.

    Attributes:
        source_version: Source Python version
        target_version: Target Python version
        project_path: Path to analyzed project
        generated_at: Timestamp when report was generated
        analyzer_version: Version of the analyzer tool
        config_hash: Hash of configuration used
        analysis_phase: Phase of analysis (ast_only or complete)
        llm_validation_performed: True if LLM validation was performed
        llm_validation_stats: Statistics about LLM validation
    """
    source_version: str
    target_version: str
    project_path: str
    generated_at: str
    analyzer_version: str = "1.0.0"
    config_hash: str = ""
    analysis_phase: str = "complete"
    llm_validation_performed: bool = False
    llm_validation_stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'source_version': self.source_version,
            'target_version': self.target_version,
            'project_path': self.project_path,
            'generated_at': self.generated_at,
            'analyzer_version': self.analyzer_version,
            'config_hash': self.config_hash,
            'analysis_phase': self.analysis_phase,
            'llm_validation_performed': self.llm_validation_performed,
            'llm_validation_stats': self.llm_validation_stats,
        }


@dataclass
class TimelineEntry:
    """
    Entry in the analysis timeline.

    Attributes:
        timestamp: When the analysis was performed
        total_issues: Number of issues found
        total_files: Number of files analyzed
        source_version: Source Python version
        target_version: Target Python version
    """
    timestamp: str
    total_issues: int
    total_files: int
    source_version: str
    target_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'total_issues': self.total_issues,
            'total_files': self.total_files,
            'source_version': self.source_version,
            'target_version': self.target_version,
        }


@dataclass
class Baseline:
    """
    Baseline for ignoring known issues.

    Attributes:
        version: Baseline format version
        source_version: Source Python version
        target_version: Target Python version
        entries: Dictionary of file_path -> set of issue IDs to ignore
        created_at: When baseline was created
        updated_at: When baseline was last updated
    """
    version: str = "1.0"
    source_version: str = ""
    target_version: str = ""
    entries: Dict[str, List[str]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def is_ignored(self, file_path: str, issue_id: str) -> bool:
        """
        Check if an issue is ignored in the baseline.

        Args:
            file_path: Path to the file
            issue_id: ID of the issue

        Returns:
            True if the issue is ignored
        """
        if file_path not in self.entries:
            return False
        return issue_id in self.entries[file_path]

    def add_ignore(self, file_path: str, issue_id: str):
        """
        Add an issue to the baseline.

        Args:
            file_path: Path to the file
            issue_id: ID of the issue to ignore
        """
        if file_path not in self.entries:
            self.entries[file_path] = []
        if issue_id not in self.entries[file_path]:
            self.entries[file_path].append(issue_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': self.version,
            'source_version': self.source_version,
            'target_version': self.target_version,
            'entries': self.entries,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Baseline':
        """Create Baseline from dictionary."""
        return cls(
            version=data.get('version', '1.0'),
            source_version=data.get('source_version', ''),
            target_version=data.get('target_version', ''),
            entries=data.get('entries', {}),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
        )


@dataclass
class CheckpointData:
    """
    Checkpoint data for resuming analysis.

    Attributes:
        timestamp: When checkpoint was saved
        processed_files: List of already processed files
        partial_results: Results from processed files
        config_hash: Hash of configuration
        progress: Progress information
    """
    timestamp: str
    processed_files: List[str]
    partial_results: Dict[str, List[Issue]]
    config_hash: str
    progress: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'processed_files': self.processed_files,
            'partial_results': {
                path: [issue.to_dict() for issue in issues]
                for path, issues in self.partial_results.items()
            },
            'config_hash': self.config_hash,
            'progress': self.progress,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointData':
        """Create CheckpointData from dictionary."""
        partial_results = {}
        for path, issues_list in data.get('partial_results', {}).items():
            partial_results[path] = [Issue.from_dict(i) for i in issues_list]

        return cls(
            timestamp=data['timestamp'],
            processed_files=data['processed_files'],
            partial_results=partial_results,
            config_hash=data['config_hash'],
            progress=data['progress'],
        )
