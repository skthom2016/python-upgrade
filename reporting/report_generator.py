"""
Report generator for creating HTML analysis reports.
"""

import os
import json
from typing import Dict, Any
from datetime import datetime


class ReportGenerator:
    """
    Generate static HTML reports from analysis results.

    Creates:
    - Interactive HTML with embedded JSON data
    - Charts for visualization
    - Filterable issue lists
    - Code snippets with highlighting
    """

    def __init__(self, output_dir: str, template_dir: str = None):
        """
        Initialize report generator.

        Args:
            output_dir: Directory to write reports to
            template_dir: Directory containing templates (default: reporting/templates/)
        """
        self.output_dir = output_dir
        if template_dir is None:
            template_dir = os.path.join(
                os.path.dirname(__file__),
                'templates'
            )
        self.template_dir = template_dir

    def generate_report(
        self,
        report_data: Dict[str, Any],
        output_path: str
    ):
        """
        Generate HTML report.

        Args:
            report_data: Analysis results dictionary
            output_path: Path to output HTML file
        """
        # Create output directory
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Generate HTML
        html = self._render_html(report_data)

        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def _render_html(self, report_data: Dict[str, Any]) -> str:
        """
        Render HTML report.

        Args:
            report_data: Analysis results

        Returns:
            HTML string
        """
        # For now, generate a simple HTML report
        # In a full implementation, this would use a template engine

        metadata = report_data.get('metadata', {})
        summary = report_data.get('summary', {})
        files = report_data.get('files', [])

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Upgrade Analysis Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}

        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .metadata {{
            font-size: 0.9em;
            opacity: 0.9;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .card h3 {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
            text-transform: uppercase;
        }}

        .card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}

        /* Severity-based card colors */
        .card.critical .value {{
            color: #e53e3e;
        }}

        .card.high .value {{
            color: #dd6b20;
        }}

        .card.medium .value {{
            color: #ed8936;
        }}

        .card.low .value {{
            color: #48bb78;
        }}

        .files {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .file {{
            border-bottom: 1px solid #eee;
            padding: 15px 0;
        }}

        .file:last-child {{
            border-bottom: none;
        }}

        .file-path {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .issue-count {{
            font-size: 0.9em;
            color: #666;
        }}

        .issues {{
            margin-top: 10px;
        }}

        .issue {{
            background: #f9f9f9;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}

        /* Severity-based issue styling */
        .issue[data-severity="critical"] {{
            border-left-color: #e53e3e;
            background: #fff5f5;
        }}

        .issue[data-severity="high"] {{
            border-left-color: #dd6b20;
            background: #fffaf0;
        }}

        .issue[data-severity="medium"] {{
            border-left-color: #ed8936;
            background: #fffaf0;
        }}

        .issue[data-severity="low"] {{
            border-left-color: #48bb78;
            background: #f0fff4;
        }}

        .issue-id {{
            font-weight: bold;
            color: #666;
            font-size: 0.85em;
        }}

        .issue-message {{
            margin: 5px 0;
        }}

        .issue-location {{
            font-size: 0.85em;
            color: #999;
        }}

        .code-snippet {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            margin: 10px 0;
            overflow-x: auto;
        }}

        .filters {{
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
        }}

        .filters button {{
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            background: #667eea;
            color: white;
            cursor: pointer;
            transition: background 0.2s;
        }}

        .filters button:hover {{
            background: #5568d3;
        }}

        .filters button.active {{
            background: #764ba2;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐍 Python Upgrade Analysis Report</h1>
            <div class="metadata">
                <p>Source: {metadata.get('source_version', 'N/A')} -> Target: {metadata.get('target_version', 'N/A')}</p>
                <p>Generated: {metadata.get('generated_at', 'N/A')}</p>
            </div>
        </header>

        <div class="summary">
            <div class="card">
                <h3>Total Issues</h3>
                <div class="value">{summary.get('total_issues', 0)}</div>
            </div>
            <div class="card">
                <h3>Files Analyzed</h3>
                <div class="value">{summary.get('total_files', 0)}</div>
            </div>
            <div class="card">
                <h3>Files with Issues</h3>
                <div class="value">{summary.get('files_with_issues', 0)}</div>
            </div>
            <div class="card critical">
                <h3>Critical Severity</h3>
                <div class="value">{summary.get('by_severity', {}).get('critical', 0)}</div>
            </div>
            <div class="card high">
                <h3>High Severity</h3>
                <div class="value">{summary.get('by_severity', {}).get('high', 0)}</div>
            </div>
            <div class="card medium">
                <h3>Medium Severity</h3>
                <div class="value">{summary.get('by_severity', {}).get('medium', 0)}</div>
            </div>
            <div class="card low">
                <h3>Low Severity</h3>
                <div class="value">{summary.get('by_severity', {}).get('low', 0)}</div>
            </div>
        </div>

        <div class="files">
            <h2>Issues by File</h2>

            <div class="filters">
                <button onclick="filterBySeverity('all')" class="active">All Issues</button>
                <button onclick="filterBySeverity('critical')">Critical</button>
                <button onclick="filterBySeverity('high')">High</button>
                <button onclick="filterBySeverity('medium')">Medium</button>
                <button onclick="filterBySeverity('low')">Low</button>
            </div>

            {self._render_files(files)}
        </div>
    </div>

    <script>
        const reportData = {json.dumps(report_data)};

        function filterBySeverity(severity) {{
            const issues = document.querySelectorAll('.issue');
            const buttons = document.querySelectorAll('.filters button');

            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            issues.forEach(issue => {{
                const issueSeverity = issue.getAttribute('data-severity');
                if (severity === 'all' || issueSeverity === severity) {{
                    issue.style.display = 'block';
                }} else {{
                    issue.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""

        return html

    def _render_files(self, files: list) -> str:
        """
        Render HTML for file results.

        Args:
            files: List of FileResult dictionaries

        Returns:
            HTML string
        """
        html = ""

        for file_result in files:
            if file_result.get('total_issues', 0) == 0:
                continue

            html += f"""
            <div class="file">
                <div class="file-path">{file_result.get('relative_path', 'Unknown')}</div>
                <div class="issue-count">{file_result.get('total_issues', 0)} issues</div>
                <div class="issues">
                    {self._render_issues(file_result.get('issues', []))}
                </div>
            </div>
            """

        return html

    def _render_issues(self, issues: list) -> str:
        """
        Render HTML for issues.

        Args:
            issues: List of Issue dictionaries

        Returns:
            HTML string
        """
        html = ""

        for issue in issues:
            risk_class = issue.get('risk_level', 'LOW').lower()
            severity = issue.get('severity', 'low')
            location = issue.get('location', {})
            snippet = issue.get('code_snippet', '')

            issue_html = f"""
            <div class="issue {risk_class}" data-severity="{severity}">
                <div class="issue-id">{issue.get('id', 'Unknown')}</div>
                <div class="issue-message">{issue.get('message', '')}</div>
                <div class="issue-location">Line {location.get('line', '?')}, Column {location.get('column', '?')}</div>
                {f'<div class="code-snippet">{snippet}</div>' if snippet else ''}
            </div>
            """

            html += issue_html

        return html
