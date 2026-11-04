"""
AI Civic Guardian — Automatic Municipal Complaint Letter & PDF Service

Generates formal civic grievance letters and downloadable official PDF documents
from database complaint records.

Features:
- Coimbatore City Municipal Corporation (CCMC) formal letterhead and styling.
- Clear distinction between "Reported by Citizen (Verification Pending)" and "Officially Verified".
- Strict HTML/text sanitization preventing injection attacks.
- High-fidelity PDF generation via ReportLab with tables, status indicators, and audit hashes.
- Fallback text and JSON representations for API clients.
"""

import io
import html
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from app.models.complaint import Complaint
from app.complaints.constants import ISSUE_DISPLAY_NAMES, STATUS_VERIFIED, STATUS_RESOLVED


class ComplaintLetterService:
    @staticmethod
    def get_verification_label(complaint: Complaint) -> str:
        status_upper = (complaint.status or "").upper()
        if status_upper == STATUS_VERIFIED:
            return "VERIFIED (Field Inspection Confirmed by Ward Officer)"
        elif status_upper == STATUS_RESOLVED:
            return "RESOLVED (Civic Remediation Completed & Signed Off)"
        elif status_upper in ("IN_PROGRESS", "DEPARTMENT_ASSIGNED"):
            return "IN PROGRESS (Dispatched to Municipal Field Crew)"
        elif status_upper == "REJECTED":
            return "REJECTED (Outside Municipal Jurisdiction / Private Property)"
        elif status_upper == "NEEDS_HUMAN_REVIEW":
            return "PENDING REVIEW (Undergoing Supervisory Evaluation)"
        else:
            return "REPORTED (Citizen Grievance Logged — Official Field Verification Pending)"

    @classmethod
    def generate_letter_dict(cls, complaint: Complaint) -> Dict[str, Any]:
        """Returns structured metadata for the complaint letter."""
        dept_name = complaint.department.name if complaint.department else "Municipal Administration"
        issue_display = ISSUE_DISPLAY_NAMES.get(complaint.issue_type, complaint.issue_type.replace("_", " ").title())
        date_str = complaint.created_at.strftime("%d %B %Y, %I:%M %p") if complaint.created_at else "N/A"
        verification_status = cls.get_verification_label(complaint)
        citizen_name = complaint.user.name if complaint.user else "Citizen"

        return {
            "authority": "Coimbatore City Municipal Corporation (CCMC)",
            "cell": "Public Grievance Redressal & Civic Redressal Cell",
            "complaint_id": complaint.complaint_id,
            "submission_datetime": date_str,
            "citizen_name": citizen_name,
            "issue_category": issue_display,
            "raw_issue_type": complaint.issue_type,
            "description": complaint.description,
            "original_text": complaint.original_text or complaint.description,
            "assigned_department": dept_name,
            "address": complaint.address or "Coimbatore Corporation Area",
            "latitude": float(complaint.latitude) if complaint.latitude is not None else None,
            "longitude": float(complaint.longitude) if complaint.longitude is not None else None,
            "severity": complaint.severity or "MEDIUM",
            "current_status": complaint.status,
            "verification_status": verification_status,
            "is_officially_verified": (complaint.status or "").upper() in (STATUS_VERIFIED, STATUS_RESOLVED),
            "generated_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
        }

    @classmethod
    def generate_letter_text(cls, complaint: Complaint) -> str:
        """Returns plain text version of the official municipal grievance letter."""
        d = cls.generate_letter_dict(complaint)
        coords_str = f"({d['latitude']:.6f}, {d['longitude']:.6f})" if d['latitude'] and d['longitude'] else "Coordinates on File"

        return f"""================================================================================
COIMBATORE CITY MUNICIPAL CORPORATION (CCMC)
Public Grievance Redressal & Civic Redressal Cell
================================================================================

OFFICIAL GRIEVANCE INTIMATION & ACTION REQUEST

Reference Number / Grievance ID : {d['complaint_id']}
Date & Time of Registration     : {d['submission_datetime']}
Complainant                     : {d['citizen_name']}
Target Municipal Department     : {d['assigned_department']}

GRIEVANCE PARTICULARS
--------------------------------------------------------------------------------
Civic Issue Category : {d['issue_category']}
Reported Location    : {d['address']} {coords_str}
Assessed Severity    : {d['severity']}
Verification Status  : {d['verification_status']}

CITIZEN'S RECORDED STATEMENT
--------------------------------------------------------------------------------
{d['description']}

MUNICIPAL ACTION DIRECTIVE
--------------------------------------------------------------------------------
The designated zonal assistant engineer / ward health inspector of {d['assigned_department']}
is hereby formally notified to conduct an on-site inspection of the indicated location,
verify the reported issue, and initiate remediation protocols in accordance with the
CCMC Citizen Charter standards.

Notice: This document is an official record generated by the AI Civic Guardian portal.
Unless marked VERIFIED above, the issue represents a citizen report undergoing field
verification.
================================================================================
"""

    @classmethod
    def generate_letter_pdf(cls, complaint: Complaint) -> bytes:
        """
        Generates a formal, high-resolution municipal grievance intimation PDF document
        using ReportLab. Returns PDF as raw bytes.
        """
        d = cls.generate_letter_dict(complaint)
        buf = io.BytesIO()

        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=42,
            rightMargin=42,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom professional typography styles
        title_style = ParagraphStyle(
            "GovTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
        )
        subtitle_style = ParagraphStyle(
            "GovSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1e3a8a"),
        )
        header_meta_style = ParagraphStyle(
            "GovMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#64748b"),
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=8,
            spaceAfter=4,
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )
        cell_normal = ParagraphStyle(
            "CellNormal",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#334155"),
        )
        body_style = ParagraphStyle(
            "GovBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13.5,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#1e293b"),
        )
        notice_style = ParagraphStyle(
            "NoticeStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
        )

        story = []

        # 1. Header Banner
        story.append(Paragraph("COIMBATORE CITY MUNICIPAL CORPORATION", title_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("PUBLIC GRIEVANCE REDRESSAL & MONITORING SYSTEM", subtitle_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("Town Hall, Coimbatore, Tamil Nadu 641001 • civicguardian.coimbatore.gov.in", header_meta_style))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

        # 2. Document Title & Reference Box
        doc_heading_style = ParagraphStyle(
            "DocHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
        )
        story.append(Paragraph("OFFICIAL CIVIC GRIEVANCE ACTION INTIMATION", doc_heading_style))
        story.append(Spacer(1, 6))

        # Reference table (ID & Date)
        ref_data = [
            [
                Paragraph(f"<b>Grievance Ref ID:</b> <font color='#1e3a8a'>{html.escape(d['complaint_id'])}</font>", cell_normal),
                Paragraph(f"<b>Registration Date:</b> {html.escape(d['submission_datetime'])}", cell_normal),
            ],
            [
                Paragraph(f"<b>Target Department:</b> <b>{html.escape(d['assigned_department'])}</b>", cell_normal),
                Paragraph(f"<b>Complainant:</b> {html.escape(d['citizen_name'])}", cell_normal),
            ],
        ]
        ref_table = Table(ref_data, colWidths=[270, 260])
        ref_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(ref_table)
        story.append(Spacer(1, 10))

        # 3. Grievance Particulars Table
        story.append(Paragraph("1. GRIEVANCE PARTICULARS & JURISDICTION", section_heading))
        coords_display = f"({d['latitude']:.5f}, {d['longitude']:.5f})" if d['latitude'] and d['longitude'] else "Coordinates Recorded in GIS"
        
        # Color coding status
        status_color = "#166534" if d['is_officially_verified'] else "#854d0e"

        part_data = [
            [Paragraph("Civic Category", cell_bold), Paragraph(f"<b>{html.escape(d['issue_category'])}</b>", cell_normal)],
            [Paragraph("Location / Address", cell_bold), Paragraph(f"{html.escape(d['address'])}<br/><font color='#64748b' size='7'>Coordinates: {coords_display}</font>", cell_normal)],
            [Paragraph("Jurisdiction Area", cell_bold), Paragraph("Coimbatore City Municipal Corporation (CCMC Urban Limits)", cell_normal)],
            [Paragraph("Assessed Severity", cell_bold), Paragraph(f"<b>{html.escape(d['severity'])}</b>", cell_normal)],
            [Paragraph("Current Workflow Status", cell_bold), Paragraph(f"<b>{html.escape(d['current_status'])}</b>", cell_normal)],
            [Paragraph("Verification Status", cell_bold), Paragraph(f"<font color='{status_color}'><b>{html.escape(d['verification_status'])}</b></font>", cell_normal)],
        ]
        part_table = Table(part_data, colWidths=[150, 380])
        part_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(part_table)
        story.append(Spacer(1, 10))

        # 4. Citizen Statement (Strictly Escaped)
        story.append(Paragraph("2. RECORDED CITIZEN GRIEVANCE STATEMENT", section_heading))
        desc_escaped = html.escape(d['description']).replace("\n", "<br/>")
        desc_table = Table([[Paragraph(f"<i>\"{desc_escaped}\"</i>", body_style)]], colWidths=[530])
        desc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fefce8")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#fef08a")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(desc_table)
        story.append(Spacer(1, 10))

        # 5. Municipal Inspection & Redressal Request Directive
        story.append(Paragraph("3. MUNICIPAL INSPECTION & REDRESSAL DIRECTIVE", section_heading))
        directive_text = (
            f"The Competent Authority and designated Ward Engineers of <b>{html.escape(d['assigned_department'])}</b>, "
            f"Coimbatore City Municipal Corporation, are hereby officially requested to inspect the premises indicated above. "
            f"If physical site evaluation confirms the defect, necessary civil/remedial works must be scheduled in accordance "
            f"with the standard municipal citizen charter SLA guidelines."
        )
        story.append(Paragraph(directive_text, body_style))
        story.append(Spacer(1, 12))

        # 6. Verification Disclaimer Box
        notice_box_text = (
            "<b>LEGAL & PROCEDURAL NOTICE:</b> This grievance letter is an authenticated digital record from the "
            "AI Civic Guardian Municipal Grievance Redressal System. For unverified reports, this document signifies "
            "citizen submission and does not constitute a final municipal determination until field confirmation is recorded "
            "by the authorized ward engineer."
        )
        notice_table = Table([[Paragraph(notice_box_text, notice_style)]], colWidths=[530])
        notice_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(notice_table)
        story.append(Spacer(1, 14))

        # 7. Signature & Footer Audit Trail
        hash_digest = hashlib.sha256(f"{d['complaint_id']}:{d['submission_datetime']}:{d['description']}".encode()).hexdigest()
        sig_data = [
            [
                Paragraph("<b>Digitally Certified Document</b><br/><font color='#64748b' size='7'>Tamper-evident SHA-256 Audit Digest:<br/>" + hash_digest[:32] + "...</font>", cell_normal),
                Paragraph("<b>Public Grievance Redressal Officer</b><br/>Coimbatore City Municipal Corporation", cell_bold),
            ]
        ]
        sig_table = Table(sig_data, colWidths=[310, 220])
        sig_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        story.append(KeepTogether([sig_table]))

        doc.build(story)
        return buf.getvalue()
