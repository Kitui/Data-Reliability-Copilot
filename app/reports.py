from __future__ import annotations

from html import escape

from app.schemas import AuditResult


def build_markdown_report(audit: AuditResult) -> str:
    lines = [
        f"# Data Quality Audit: {audit.dataset_name}",
        "",
        f"- Audit ID: `{audit.audit_id}`",
        f"- Created: `{audit.created_at.isoformat()}`",
        f"- Overall score: **{audit.score.overall}/100**",
        f"- Risk level: **{audit.summary.risk_level}**",
        f"- Summary source: `{audit.summary.source}`",
        "",
        "## Executive Summary",
        "",
        audit.summary.executive_summary,
        "",
        "## Score Breakdown",
        "",
        "| Dimension | Score |",
        "| --- | ---: |",
        f"| Completeness | {audit.score.completeness} |",
        f"| Validity | {audit.score.validity} |",
        f"| Consistency | {audit.score.consistency} |",
        f"| Uniqueness | {audit.score.uniqueness} |",
        f"| Reliability | {audit.score.reliability} |",
        "",
        "## Recommended Focus",
        "",
    ]
    lines.extend(f"- {item}" for item in audit.summary.recommended_focus)
    lines.extend(["", "## Remediation Plan", ""])
    lines.extend(f"- {item}" for item in audit.summary.remediation_plan)
    lines.extend(["", "## Issues", ""])

    if not audit.issues:
        lines.append("No issues were detected by the configured rules.")
    else:
        lines.extend(
            [
                "| ID | Severity | Category | Affected Rows | Columns | Finding | Recommendation |",
                "| --- | --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for issue in audit.issues:
            lines.append(
                "| "
                + " | ".join(
                    [
                        issue.id,
                        issue.severity,
                        issue.category,
                        str(issue.affected_rows),
                        ", ".join(issue.columns),
                        _escape_table(issue.title),
                        _escape_table(issue.recommendation),
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Column Profile", ""])
    lines.extend(
        [
            "| Column | Type | Missing | Unique Values |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for column in audit.profile.columns:
        lines.append(
            f"| {column.name} | {column.inferred_type} | {column.missing_rate:.0%} | {column.unique_count} |"
        )

    return "\n".join(lines) + "\n"


def build_html_report(audit: AuditResult) -> str:
    high_priority = [issue for issue in audit.issues if issue.severity in {"critical", "high"}]
    issue_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(issue.id)}</td>
          <td><span class="badge severity-{escape(issue.severity)}">{escape(issue.severity)}</span></td>
          <td>{escape(issue.category)}</td>
          <td>{issue.affected_rows}</td>
          <td>{escape(", ".join(issue.columns))}</td>
          <td>{escape(issue.title)}</td>
          <td>{escape(issue.recommendation)}</td>
        </tr>
        """
        for issue in audit.issues
    )
    column_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(column.name)}</td>
          <td>{escape(column.inferred_type)}</td>
          <td>{column.missing_rate:.0%}</td>
          <td>{column.unique_count}</td>
        </tr>
        """
        for column in audit.profile.columns
    )
    focus_items = "\n".join(f"<li>{escape(item)}</li>" for item in audit.summary.recommended_focus)
    remediation_items = "\n".join(f"<li>{escape(item)}</li>" for item in audit.summary.remediation_plan)
    high_priority_items = "\n".join(
        f"<li><strong>{escape(issue.id)}</strong>: {escape(issue.title)} ({issue.affected_rows} affected rows)</li>"
        for issue in high_priority
    ) or "<li>No critical or high issues detected.</li>"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Data Quality Audit - {escape(audit.dataset_name)}</title>
    <style>
      body {{
        margin: 0;
        color: #172026;
        background: #f4f7f8;
        font-family: Inter, Segoe UI, Arial, sans-serif;
        line-height: 1.5;
      }}
      main {{
        max-width: 1120px;
        margin: 0 auto;
        padding: 32px 20px;
      }}
      section {{
        margin-top: 18px;
        padding: 20px;
        background: #ffffff;
        border: 1px solid #dce3e6;
        border-radius: 8px;
      }}
      h1, h2, h3, p {{
        margin-top: 0;
      }}
      h1 {{
        margin-bottom: 4px;
        font-size: 30px;
      }}
      h2 {{
        font-size: 18px;
      }}
      .muted {{
        color: #65737e;
      }}
      .score-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
      }}
      .metric {{
        padding: 16px;
        border: 1px solid #dce3e6;
        border-radius: 8px;
        background: #fbfcfc;
      }}
      .metric span {{
        display: block;
        color: #65737e;
        font-size: 13px;
      }}
      .metric strong {{
        display: block;
        margin-top: 6px;
        font-size: 28px;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
      }}
      th, td {{
        padding: 10px;
        border-bottom: 1px solid #e7ecef;
        text-align: left;
        vertical-align: top;
      }}
      th {{
        color: #65737e;
        background: #fbfcfc;
      }}
      .badge {{
        display: inline-block;
        padding: 3px 8px;
        border-radius: 999px;
        background: #edf2f3;
      }}
      .severity-critical, .severity-high {{
        color: #98251c;
        background: #fdebea;
      }}
      .severity-medium {{
        color: #8a4b00;
        background: #fff2df;
      }}
      .severity-low {{
        color: #3f6d24;
        background: #e9f3e5;
      }}
      @media print {{
        body {{ background: #ffffff; }}
        main {{ padding: 0; }}
        section {{ break-inside: avoid; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <p class="muted">Data Reliability Copilot</p>
        <h1>Data Quality Audit: {escape(audit.dataset_name)}</h1>
        <p class="muted">Audit ID: {escape(audit.audit_id)} | Created: {escape(audit.created_at.isoformat())}</p>
      </header>

      <section class="score-grid">
        <div class="metric"><span>Overall score</span><strong>{audit.score.overall}/100</strong></div>
        <div class="metric"><span>Risk level</span><strong>{escape(audit.summary.risk_level)}</strong></div>
        <div class="metric"><span>Total issues</span><strong>{len(audit.issues)}</strong></div>
        <div class="metric"><span>High priority</span><strong>{len(high_priority)}</strong></div>
      </section>

      <section>
        <h2>Executive Summary</h2>
        <p>{escape(audit.summary.executive_summary)}</p>
      </section>

      <section>
        <h2>What To Fix First</h2>
        <ul>{focus_items}</ul>
        <h3>High Priority Issues</h3>
        <ul>{high_priority_items}</ul>
      </section>

      <section>
        <h2>Score Breakdown</h2>
        <table>
          <thead><tr><th>Dimension</th><th>Score</th><th>Meaning</th></tr></thead>
          <tbody>
            <tr><td>Completeness</td><td>{audit.score.completeness}/100</td><td>How much required data is present instead of blank.</td></tr>
            <tr><td>Validity</td><td>{audit.score.validity}/100</td><td>How often values match expected formats and ranges.</td></tr>
            <tr><td>Consistency</td><td>{audit.score.consistency}/100</td><td>How uniform labels, categories, and repeated patterns are.</td></tr>
            <tr><td>Uniqueness</td><td>{audit.score.uniqueness}/100</td><td>How free the dataset is from duplicate rows or duplicate keys.</td></tr>
            <tr><td>Reliability</td><td>{audit.score.reliability}/100</td><td>A stricter operational risk score based on serious issues.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Remediation Plan</h2>
        <ul>{remediation_items}</ul>
      </section>

      <section>
        <h2>Issues</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Severity</th><th>Category</th><th>Affected Rows</th><th>Columns</th><th>Finding</th><th>Recommendation</th></tr>
          </thead>
          <tbody>{issue_rows}</tbody>
        </table>
      </section>

      <section>
        <h2>Column Profile</h2>
        <table>
          <thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique Values</th></tr></thead>
          <tbody>{column_rows}</tbody>
        </table>
      </section>
    </main>
  </body>
</html>
"""


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
