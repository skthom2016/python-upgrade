"""
Report generator for creating HTML analysis reports and CSV exports.
"""

import os
import json
import csv
from typing import Dict, Any, List
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

    def generate_csv_export(
        self,
        report_data: Dict[str, Any],
        output_path: str
    ):
        """
        Generate CSV export of all issues for Excel analysis.

        Args:
            report_data: Analysis results dictionary
            output_path: Path to output CSV file
        """
        # Create output directory
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Extract all issues from files
        all_issues = []
        for file_result in report_data.get('files', []):
            for issue in file_result.get('issues', []):
                # Flatten issue data for CSV - aggressively clean all text fields
                def clean_text(text):
                    """Remove all newlines, tabs, and extra whitespace."""
                    if not text:
                        return ''
                    # Replace all types of newlines and whitespace
                    cleaned = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                    # Remove extra spaces
                    cleaned = ' '.join(cleaned.split())
                    return cleaned.strip()

                all_issues.append({
                    'File': clean_text(file_result.get('relative_path', '')),
                    'Issue ID': clean_text(issue.get('id', '')),
                    'Severity': clean_text(issue.get('severity', '')),
                    'Category': clean_text(issue.get('category', '')),
                    'Risk Level': clean_text(issue.get('risk_level', '')),
                    'Line': issue.get('location', {}).get('line', ''),
                    'Column': issue.get('location', {}).get('column', ''),
                    'Message': clean_text(issue.get('message', '')),
                    'Suggestion': clean_text(issue.get('suggestion', '')),
                    'Detection Method': clean_text(issue.get('detection_method', 'ast')),
                    'LLM Validated': issue.get('llm_validated', False),
                    'LLM Confirmed': issue.get('llm_confirmed', True),
                    'Analysis Phase': clean_text(issue.get('analysis_phase', 'ast_only')),
                    'Code Snippet': clean_text(issue.get('code_snippet', ''))[:200]  # Truncate
                })

        # Write CSV
        if all_issues:
            fieldnames = [
                'File', 'Issue ID', 'Severity', 'Category', 'Risk Level',
                'Line', 'Column', 'Message', 'Suggestion', 'Detection Method',
                'LLM Validated', 'LLM Confirmed', 'Analysis Phase', 'Code Snippet'
            ]

            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_issues)

            print(f"[INFO] CSV export saved: {output_path}")
            print(f"[INFO] Total rows: {len(all_issues):,}")
        else:
            print("[WARNING] No issues to export to CSV")

    def _render_html(self, report_data: Dict[str, Any]) -> str:
        """
        Render HTML report with tabbed interface and lazy loading.

        Args:
            report_data: Analysis results

        Returns:
            HTML string
        """
        metadata = report_data.get('metadata', {})
        summary = report_data.get('summary', {})

        # Get phase information
        analysis_phase = metadata.get('analysis_phase', 'complete')
        llm_validated = metadata.get('llm_validation_performed', False)

        # Phase badge
        if analysis_phase == 'ast_only':
            phase_badge = '<span class="phase-badge ast-only">Phase 1: AST Analysis Only</span>'
        elif llm_validated:
            phase_badge = '<span class="phase-badge complete">Complete: LLM Validated</span>'
        else:
            phase_badge = ''

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
            margin-top: 10px;
        }}

        .phase-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            margin-top: 10px;
        }}

        .phase-badge.ast-only {{
            background: #ed8936;
            color: white;
        }}

        .phase-badge.complete {{
            background: #48bb78;
            color: white;
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

        /* Severity colors */
        .card.critical .value {{ color: #e53e3e; }}
        .card.high .value {{ color: #dd6b20; }}
        .card.medium .value {{ color: #ed8936; }}
        .card.low .value {{ color: #48bb78; }}

        /* Tab Navigation */
        .tabs {{
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
            border-bottom: 2px solid #ddd;
        }}

        .tab-button {{
            padding: 15px 30px;
            border: none;
            background: white;
            color: #667eea;
            cursor: pointer;
            font-size: 1em;
            font-weight: 500;
            border-radius: 5px 5px 0 0;
            transition: all 0.2s;
        }}

        .tab-button:hover {{
            background: #f0f0f0;
        }}

        .tab-button.active {{
            background: #667eea;
            color: white;
            border-bottom: 2px solid #667eea;
        }}

        .tab-content {{
            display: none;
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-height: 400px;
        }}

        .tab-content.active {{
            display: block;
        }}

        /* File List Styles */
        .file-list {{
            max-height: 600px;
            overflow-y: auto;
        }}

        .file-item {{
            padding: 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background 0.2s;
        }}

        .file-item:hover {{
            background: #f9f9f9;
        }}

        .file-item.selected {{
            background: #e6e6ff;
            border-left: 4px solid #667eea;
        }}

        .file-path {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .file-stats {{
            font-size: 0.9em;
            color: #666;
        }}

        /* Issue Display */
        .issue-container {{
            margin-top: 20px;
        }}

        .issue {{
            background: #f9f9f9;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}

        .issue[data-severity="critical"] {{ border-left-color: #e53e3e; background: #fff5f5; }}
        .issue[data-severity="high"] {{ border-left-color: #dd6b20; background: #fffaf0; }}
        .issue[data-severity="medium"] {{ border-left-color: #ed8936; background: #fffaf0; }}
        .issue[data-severity="low"] {{ border-left-color: #48bb78; background: #f0fff4; }}

        .issue-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}

        .issue-id {{
            font-weight: bold;
            color: #666;
            font-size: 0.9em;
        }}

        .issue-severity {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
        }}

        .issue-severity.critical {{ background: #e53e3e; color: white; }}
        .issue-severity.high {{ background: #dd6b20; color: white; }}
        .issue-severity.medium {{ background: #ed8936; color: white; }}
        .issue-severity.low {{ background: #48bb78; color: white; }}

        .issue-message {{
            margin: 10px 0;
            line-height: 1.5;
        }}

        .issue-location {{
            font-size: 0.85em;
            color: #999;
            margin: 5px 0;
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
            white-space: pre;
        }}

        /* Filters */
        .filters {{
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .filters label {{
            font-weight: 500;
            margin-right: 10px;
        }}

        .filters select, .filters input {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 0.9em;
        }}

        .filters button {{
            padding: 8px 20px;
            border: none;
            border-radius: 5px;
            background: #667eea;
            color: white;
            cursor: pointer;
            transition: background 0.2s;
            font-size: 0.9em;
        }}

        .filters button:hover {{
            background: #5568d3;
        }}

        /* Pagination */
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
            padding: 20px 0;
        }}

        .pagination button {{
            padding: 8px 16px;
            border: 1px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .pagination button:hover:not(:disabled) {{
            background: #667eea;
            color: white;
        }}

        .pagination button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        .pagination .page-info {{
            font-weight: 500;
        }}

        /* Loading Indicator */
        .loading {{
            text-align: center;
            padding: 40px;
            color: #667eea;
            font-size: 1.2em;
        }}

        .loading::after {{
            content: '...';
            animation: dots 1.5s steps(4, end) infinite;
        }}

        @keyframes dots {{
            0%, 20% {{ content: '.'; }}
            40% {{ content: '..'; }}
            60%, 100% {{ content: '...'; }}
        }}

        /* Search */
        .search-box {{
            width: 300px;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 0.9em;
        }}

        /* Statistics Table */
        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        .stats-table th, .stats-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}

        .stats-table th {{
            background: #f9f9f9;
            font-weight: 600;
            color: #667eea;
        }}

        .stats-table tr:hover {{
            background: #f9f9f9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐍 Python Upgrade Analysis Report</h1>
            {phase_badge}
            <div class="metadata">
                <p>Source: {metadata.get('source_version', 'N/A')} → Target: {metadata.get('target_version', 'N/A')}</p>
                <p>Project: {metadata.get('project_path', 'N/A')}</p>
                <p>Generated: {metadata.get('generated_at', 'N/A')}</p>
            </div>
        </header>

        <!-- Tab Navigation -->
        <div class="tabs">
            <button class="tab-button active" onclick="showTab('overview')">Overview</button>
            <button class="tab-button" onclick="showTab('by-file')">Issues by File</button>
            <button class="tab-button" onclick="showTab('by-severity')">By Severity</button>
            <button class="tab-button" onclick="showTab('by-category')">By Category</button>
        </div>

        <!-- Overview Tab -->
        <div id="overview-tab" class="tab-content active">
            <h2>Analysis Summary</h2>
            <div class="summary">
                <div class="card">
                    <h3>Total Issues</h3>
                    <div class="value">{summary.get('total_issues', 0):,}</div>
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
                    <h3>Critical</h3>
                    <div class="value">{summary.get('by_severity', {}).get('critical', 0):,}</div>
                </div>
                <div class="card high">
                    <h3>High</h3>
                    <div class="value">{summary.get('by_severity', {}).get('high', 0):,}</div>
                </div>
                <div class="card medium">
                    <h3>Medium</h3>
                    <div class="value">{summary.get('by_severity', {}).get('medium', 0):,}</div>
                </div>
                <div class="card low">
                    <h3>Low</h3>
                    <div class="value">{summary.get('by_severity', {}).get('low', 0):,}</div>
                </div>
            </div>

            <h3>Top Files with Most Issues</h3>
            <table class="stats-table">
                <thead>
                    <tr>
                        <th>File</th>
                        <th>Total Issues</th>
                        <th>Critical</th>
                        <th>High</th>
                        <th>Medium</th>
                        <th>Low</th>
                    </tr>
                </thead>
                <tbody id="top-files-tbody">
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>

        <!-- Issues by File Tab -->
        <div id="by-file-tab" class="tab-content">
            <h2>Issues by File</h2>

            <div class="filters">
                <input type="text" id="file-search" class="search-box" placeholder="Search files..." onkeyup="filterFiles()">
                <label>Severity:</label>
                <select id="severity-filter" onchange="applyFileFilters()">
                    <option value="all">All</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>
                <label>Show files with issues:</label>
                <select id="issues-filter" onchange="applyFileFilters()">
                    <option value="all">All Files</option>
                    <option value="with-issues">With Issues Only</option>
                </select>
            </div>

            <div id="file-list-container">
                <!-- Populated by JavaScript -->
            </div>

            <div class="pagination">
                <button onclick="previousFilePage()" id="prev-file-btn">Previous</button>
                <span class="page-info" id="file-page-info">Page 1 of 1</span>
                <button onclick="nextFilePage()" id="next-file-btn">Next</button>
            </div>

            <div id="selected-file-issues" style="margin-top: 30px;">
                <p style="color: #999; text-align: center; padding: 40px;">Click on a file to view its issues</p>
            </div>
        </div>

        <!-- By Severity Tab -->
        <div id="by-severity-tab" class="tab-content">
            <h2>Issues by Severity</h2>
            <div id="severity-breakdown">
                <!-- Populated by JavaScript -->
            </div>
        </div>

        <!-- By Category Tab -->
        <div id="by-category-tab" class="tab-content">
            <h2>Issues by Category</h2>
            <div id="category-breakdown">
                <!-- Populated by JavaScript -->
            </div>
        </div>
    </div>

    <script>
        // Embed full report data
        const reportData = {json.dumps(report_data)};

        // Pagination state
        let currentFilePage = 1;
        const filesPerPage = 50;
        let filteredFiles = [];
        let selectedFileIndex = -1;

        // Initialize on load
        document.addEventListener('DOMContentLoaded', function() {{
            initializeReport();
        }});

        function initializeReport() {{
            // Populate overview
            populateTopFiles();

            // Initialize file list
            filteredFiles = reportData.files.filter(f => f.total_issues > 0);
            renderFileList();
        }}

        function populateTopFiles() {{
            const topFiles = reportData.summary.top_files || [];
            const tbody = document.getElementById('top-files-tbody');

            if (topFiles.length === 0) {{
                // Generate top files from data
                const filesWithIssues = reportData.files
                    .filter(f => f.total_issues > 0)
                    .sort((a, b) => b.total_issues - a.total_issues)
                    .slice(0, 10);

                filesWithIssues.forEach(file => {{
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${{escapeHtml(file.relative_path)}}</td>
                        <td>${{file.total_issues.toLocaleString()}}</td>
                        <td>${{(file.by_severity.critical || 0).toLocaleString()}}</td>
                        <td>${{(file.by_severity.high || 0).toLocaleString()}}</td>
                        <td>${{(file.by_severity.medium || 0).toLocaleString()}}</td>
                        <td>${{(file.by_severity.low || 0).toLocaleString()}}</td>
                    `;
                }});
            }}
        }}

        function showTab(tabName) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});
            document.querySelectorAll('.tab-button').forEach(btn => {{
                btn.classList.remove('active');
            }});

            // Show selected tab
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');

            // Load content for specific tabs
            if (tabName === 'by-file' && filteredFiles.length === 0) {{
                filteredFiles = reportData.files.filter(f => f.total_issues > 0);
                renderFileList();
            }} else if (tabName === 'by-severity') {{
                renderSeverityBreakdown();
            }} else if (tabName === 'by-category') {{
                renderCategoryBreakdown();
            }}
        }}

        function renderFileList() {{
            const container = document.getElementById('file-list-container');
            const startIdx = (currentFilePage - 1) * filesPerPage;
            const endIdx = Math.min(startIdx + filesPerPage, filteredFiles.length);
            const pageFiles = filteredFiles.slice(startIdx, endIdx);

            let html = '<div class="file-list">';
            pageFiles.forEach((file, idx) => {{
                const globalIdx = startIdx + idx;
                html += `
                    <div class="file-item" onclick="showFileIssues(${{globalIdx}})">
                        <div class="file-path">${{escapeHtml(file.relative_path)}}</div>
                        <div class="file-stats">
                            ${{file.total_issues.toLocaleString()}} issues
                            (Critical: ${{file.by_severity.critical || 0}},
                             High: ${{file.by_severity.high || 0}},
                             Medium: ${{file.by_severity.medium || 0}},
                             Low: ${{file.by_severity.low || 0}})
                        </div>
                    </div>
                `;
            }});
            html += '</div>';

            container.innerHTML = html;
            updateFilePagination();
        }}

        function showFileIssues(fileIdx) {{
            const file = filteredFiles[fileIdx];
            const container = document.getElementById('selected-file-issues');

            // Highlight selected file
            document.querySelectorAll('.file-item').forEach((item, idx) => {{
                item.classList.remove('selected');
                if (idx === fileIdx % filesPerPage) {{
                    item.classList.add('selected');
                }}
            }});

            // Render issues (limit to first 100 for performance)
            const maxIssues = 100;
            const issues = file.issues.slice(0, maxIssues);
            const hasMore = file.issues.length > maxIssues;

            let html = `<h3>${{escapeHtml(file.relative_path)}}</h3>`;
            html += `<p style="margin: 10px 0; color: #666;">Showing ${{issues.length}} of ${{file.total_issues.toLocaleString()}} issues</p>`;

            if (hasMore) {{
                html += `<p style="margin: 10px 0; color: #dd6b20; font-weight: bold;">⚠ Only showing first ${{maxIssues}} issues. Full data available in JSON.</p>`;
            }}

            html += '<div class="issue-container">';
            issues.forEach(issue => {{
                html += `
                    <div class="issue" data-severity="${{issue.severity}}">
                        <div class="issue-header">
                            <span class="issue-id">${{issue.id}}</span>
                            <span class="issue-severity ${{issue.severity}}">${{issue.severity}}</span>
                        </div>
                        <div class="issue-message">${{escapeHtml(issue.message)}}</div>
                        <div class="issue-location">Line ${{issue.location.line}}, Column ${{issue.location.column}}</div>
                        ${{issue.code_snippet ? '<div class="code-snippet">' + escapeHtml(issue.code_snippet) + '</div>' : ''}}
                    </div>
                `;
            }});
            html += '</div>';

            container.innerHTML = html;
        }}

        function renderSeverityBreakdown() {{
            const container = document.getElementById('severity-breakdown');
            const bySeverity = {{'critical': [], 'high': [], 'medium': [], 'low': []}};

            // Group files by severity
            reportData.files.forEach(file => {{
                if (file.total_issues > 0) {{
                    Object.keys(bySeverity).forEach(sev => {{
                        if (file.by_severity[sev] > 0) {{
                            bySeverity[sev].push({{
                                path: file.relative_path,
                                count: file.by_severity[sev]
                            }});
                        }}
                    }});
                }}
            }});

            let html = '';
            Object.keys(bySeverity).forEach(severity => {{
                const files = bySeverity[severity].sort((a, b) => b.count - a.count).slice(0, 20);
                const total = reportData.summary.by_severity[severity] || 0;

                html += `
                    <h3 style="margin-top: 30px; color: #667eea; text-transform: capitalize;">${{severity}} (${{total.toLocaleString()}} issues)</h3>
                    <table class="stats-table">
                        <thead>
                            <tr>
                                <th>File</th>
                                <th>Issues</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                files.forEach(f => {{
                    html += `
                        <tr>
                            <td>${{escapeHtml(f.path)}}</td>
                            <td>${{f.count.toLocaleString()}}</td>
                        </tr>
                    `;
                }});

                html += `
                        </tbody>
                    </table>
                `;
            }});

            container.innerHTML = html;
        }}

        function renderCategoryBreakdown() {{
            const container = document.getElementById('category-breakdown');
            const byCategory = reportData.summary.by_category || {{}};

            let html = '<table class="stats-table"><thead><tr><th>Category</th><th>Issues</th></tr></thead><tbody>';

            Object.entries(byCategory).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {{
                html += `
                    <tr>
                        <td style="text-transform: capitalize;">${{cat.replace('_', ' ')}}</td>
                        <td>${{count.toLocaleString()}}</td>
                    </tr>
                `;
            }});

            html += '</tbody></table>';
            container.innerHTML = html;
        }}

        function filterFiles() {{
            const searchTerm = document.getElementById('file-search').value.toLowerCase();
            filteredFiles = reportData.files.filter(f =>
                f.total_issues > 0 && f.relative_path.toLowerCase().includes(searchTerm)
            );
            currentFilePage = 1;
            renderFileList();
        }}

        function applyFileFilters() {{
            const severity = document.getElementById('severity-filter').value;
            const issuesFilter = document.getElementById('issues-filter').value;
            const searchTerm = document.getElementById('file-search').value.toLowerCase();

            filteredFiles = reportData.files.filter(file => {{
                if (issuesFilter === 'with-issues' && file.total_issues === 0) return false;
                if (!file.relative_path.toLowerCase().includes(searchTerm)) return false;
                if (severity !== 'all' && (file.by_severity[severity] || 0) === 0) return false;
                return true;
            }});

            currentFilePage = 1;
            renderFileList();
        }}

        function previousFilePage() {{
            if (currentFilePage > 1) {{
                currentFilePage--;
                renderFileList();
            }}
        }}

        function nextFilePage() {{
            const totalPages = Math.ceil(filteredFiles.length / filesPerPage);
            if (currentFilePage < totalPages) {{
                currentFilePage++;
                renderFileList();
            }}
        }}

        function updateFilePagination() {{
            const totalPages = Math.ceil(filteredFiles.length / filesPerPage);
            document.getElementById('file-page-info').textContent =
                `Page ${{currentFilePage}} of ${{totalPages}} (${{filteredFiles.length.toLocaleString()}} files)`;

            document.getElementById('prev-file-btn').disabled = currentFilePage === 1;
            document.getElementById('next-file-btn').disabled = currentFilePage === totalPages;
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
    </script>
</body>
</html>"""

        return html
