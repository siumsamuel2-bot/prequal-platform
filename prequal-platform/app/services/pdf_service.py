"""PDF Report Generation Service for Subcontractor Compliance Profiles.

Uses WeasyPrint to convert HTML templates to PDF.
"""
from __future__ import annotations

import io
import logging
from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.compliance import Subcontractor, Certification, Violation, Project, ProjectSubcontractor

logger = logging.getLogger(__name__)


SUBREPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Compliance Report - {{ company_name }}</title>
    <style>
        @page {
            size: A4;
            margin: 1cm;
            @top-center {
                content: "Prequal Compliance Report";
                font-size: 10px;
                color: #666;
            }
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10px;
                color: #666;
            }
        }
        body {
            font-family: Arial, sans-serif;
            font-size: 12px;
            line-height: 1.4;
            color: #333;
        }
        h1 {
            font-size: 24px;
            color: #1a1a1a;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }
        h2 {
            font-size: 16px;
            color: #3b82f6;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
        }
        .company-info h1 {
            margin: 0;
        }
        .company-info p {
            margin: 4px 0;
            color: #666;
        }
        .report-meta {
            text-align: right;
            font-size: 10px;
            color: #666;
        }
        .compliance-score {
            background: {{ score_bg_color }};
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            text-align: center;
            margin-bottom: 20px;
        }
        .compliance-score .score {
            font-size: 36px;
            font-weight: bold;
        }
        .compliance-score .label {
            font-size: 12px;
        }
        .section {
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f5f5f5;
            font-weight: bold;
            color: #333;
        }
        .status-valid { color: #10b981; font-weight: bold; }
        .status-expired { color: #ef4444; font-weight: bold; }
        .status-pending { color: #f59e0b; font-weight: bold; }
        .status-open { color: #ef4444; font-weight: bold; }
        .status-resolved { color: #10b981; font-weight: bold; }
        .no-data {
            color: #999;
            font-style: italic;
        }
        .footer {
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            font-size: 10px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="company-info">
            <h1>{{ company_name }}</h1>
            <p><strong>Email:</strong> {{ email }}</p>
            <p><strong>Phone:</strong> {{ phone|default('N/A') }}</p>
            <p><strong>Address:</strong> {{ address }}</p>
            <p><strong>Status:</strong> <span class="status-{{ status }}">{{ status|upper }}</span></p>
        </div>
        <div class="report-meta">
            <p><strong>Report Date:</strong> {{ report_date }}</p>
            <p><strong>Report ID:</strong> {{ report_id }}</p>
        </div>
    </div>

    <div class="compliance-score">
        <div class="score">{{ compliance_score }}%</div>
        <div class="label">Compliance Score</div>
    </div>

    <div class="section">
        <h2>Active Certifications ({{ certs|length }})</h2>
        {% if certs %}
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Number</th>
                    <th>Issued</th>
                    <th>Expires</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
            {% for cert in certs %}
                <tr>
                    <td>{{ cert.certification_type }}</td>
                    <td>{{ cert.certification_number|default('N/A') }}</td>
                    <td>{{ cert.issue_date|default('N/A') }}</td>
                    <td>{{ cert.expiration_date }}</td>
                    <td class="status-{{ cert.status }}">{{ cert.status|upper }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">No active certifications on file.</p>
        {% endif %}
    </div>

    <div class="section">
        <h2>Violations ({{ violations|length }})</h2>
        {% if violations %}
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Issued Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
            {% for v in violations %}
                <tr>
                    <td>{{ v.violation_type }}</td>
                    <td>{{ v.description|default('N/A') }}</td>
                    <td>{{ v.issued_date|default('N/A') }}</td>
                    <td class="status-{{ v.status }}">{{ v.status|upper }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">No violations on record.</p>
        {% endif %}
    </div>

    <div class="section">
        <h2>Assigned Projects ({{ projects|length }})</h2>
        {% if projects %}
        <table>
            <thead>
                <tr>
                    <th>Project Name</th>
                    <th>Project Number</th>
                    <th>Role</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
            {% for p in projects %}
                <tr>
                    <td>{{ p.project_name }}</td>
                    <td>{{ p.project_number }}</td>
                    <td>{{ p.role }}</td>
                    <td class="status-{{ p.status }}">{{ p.status|upper }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-data">Not assigned to any projects.</p>
        {% endif %}
    </div>

    <div class="footer">
        <p>This report was generated by Prequal Compliance Platform. 
           For questions, contact support@prequal.example.com</p>
        <p>Disclaimer: This report is for informational purposes only and should not be 
           considered legal or regulatory advice.</p>
    </div>
</body>
</html>
"""


def calculate_compliance_score(
    total_certs: int,
    valid_certs: int,
    open_violations: int
) -> int:
    """Calculate compliance score (0-100)."""
    if total_certs == 0:
        return 0 if open_violations > 0 else 100
    
    cert_score = (valid_certs / total_certs) * 70
    violation_score = max(0, 30 - (open_violations * 10))
    return min(100, int(cert_score + violation_score))


async def generate_subcontractor_pdf(
    db: AsyncSession,
    subcontractor_id: str
) -> bytes:
    """Generate a PDF compliance report for a subcontractor.

    Returns PDF bytes.
    """
    from weasyprint import HTML
    import uuid
    
    result = await db.execute(
        select(Subcontractor).where(Subcontractor.id == subcontractor_id)
    )
    sub = result.scalar_one_or_none()
    
    if not sub:
        raise ValueError(f"Subcontractor {subcontractor_id} not found")
    
    certs_result = await db.execute(
        select(Certification).where(Certification.subcontractor_id == subcontractor_id)
    )
    certs = certs_result.scalars().all()
    
    violations_result = await db.execute(
        select(Violation).where(Violation.subcontractor_id == subcontractor_id)
    )
    violations = violations_result.scalars().all()
    
    ps_result = await db.execute(
        select(Project, ProjectSubcontractor.role, ProjectSubcontractor.status)
        .join(ProjectSubcontractor, Project.id == ProjectSubcontractor.project_id)
        .where(ProjectSubcontractor.subcontractor_id == subcontractor_id)
    )
    project_rows = ps_result.all()
    projects = [
        {
            "project_name": row[0].project_name,
            "project_number": row[0].project_number,
            "role": row[1],
            "status": row[2]
        }
        for row in project_rows
    ]
    
    valid_certs = sum(1 for c in certs if c.status == "valid")
    open_violations = sum(1 for v in violations if v.status == "open")
    compliance_score = calculate_compliance_score(len(certs), valid_certs, open_violations)
    
    score_bg = "#10b981" if compliance_score >= 70 else "#f59e0b" if compliance_score >= 40 else "#ef4444"
    
    context = {
        "company_name": sub.company_name,
        "email": sub.email,
        "phone": sub.phone or None,
        "address": f"{sub.address_line1 or ''}, {sub.city or ''}, {sub.state or ''} {sub.zip_code or ''}".strip(", "),
        "status": sub.status,
        "report_date": date.today().strftime("%B %d, %Y"),
        "report_id": str(uuid.uuid4())[:8].upper(),
        "compliance_score": compliance_score,
        "score_bg_color": score_bg,
        "certs": [
            {
                "certification_type": c.certification_type,
                "certification_number": c.certification_number,
                "issue_date": c.issue_date.strftime("%Y-%m-%d") if c.issue_date else None,
                "expiration_date": c.expiration_date.strftime("%Y-%m-%d"),
                "status": c.status
            }
            for c in certs
        ],
        "violations": [
            {
                "violation_type": v.violation_type,
                "description": v.description,
                "issued_date": v.issued_date.strftime("%Y-%m-%d") if v.issued_date else None,
                "status": v.status
            }
            for v in violations
        ],
        "projects": projects
    }
    
    html_content = SUBREPORT_TEMPLATE
    for key, value in context.items():
        placeholder = f"{{{{ {key} }}}}"
        if value is None:
            html_content = html_content.replace(placeholder, "N/A")
        else:
            html_content = html_content.replace(placeholder, str(value))
    
    html_content = html_content.replace("{{ score_bg_color }}", score_bg)
    
    buffer = io.BytesIO()
    HTML(string=html_content).write_pdf(buffer)
    buffer.seek(0)
    return buffer.read()