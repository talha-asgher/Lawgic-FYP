# Backend/app/utils/pdf_generator.py

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from io import BytesIO
import datetime

# ─── Common Styles ─────────────────────────────────────────────────────────────

def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='DocTitle',
        parent=styles['Title'],
        fontSize=16,
        leading=20,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#052379'),
    ))
    styles.add(ParagraphStyle(
        name='DocSubTitle',
        fontSize=10,
        leading=14,
        spaceAfter=2,
        alignment=TA_CENTER,
        fontName='Helvetica',
        textColor=colors.HexColor('#555555'),
    ))
    styles.add(ParagraphStyle(
        name='SectionHeading',
        fontSize=11,
        leading=15,
        spaceBefore=12,
        spaceAfter=6,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#052379'),
    ))
    styles.add(ParagraphStyle(
        name='BodyText2',
        fontSize=10,
        leading=15,
        spaceAfter=4,
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
        textColor=colors.HexColor('#222222'),
    ))
    styles.add(ParagraphStyle(
        name='SmallText',
        fontSize=9,
        leading=13,
        spaceAfter=2,
        fontName='Helvetica',
        textColor=colors.HexColor('#555555'),
    ))
    styles.add(ParagraphStyle(
        name='Bold10',
        fontSize=10,
        leading=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#111111'),
    ))
    return styles


def build_header(story, styles, title, subtitle, legal_basis):
    """Common document header"""
    story.append(Paragraph("ISLAMIC REPUBLIC OF PAKISTAN", styles['DocSubTitle']))
    story.append(Paragraph(title.upper(), styles['DocTitle']))
    story.append(Paragraph(subtitle, styles['DocSubTitle']))
    story.append(Paragraph(f"Legal Basis: {legal_basis}", styles['SmallText']))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#052379'), spaceAfter=12))


def kv_row(key, value):
    """Helper to build a key-value table row"""
    return [key, value or "____________________"]


def styled_table(data, col_widths=None):
    """Create a styled key-value table"""
    if col_widths is None:
        col_widths = [5.5 * cm, 11 * cm]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F4FF')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 13),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8F9FE')]),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EEF2FF')),
    ]))
    return table


def build_footer(story, styles, date_str=None):
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CCCCCC'), spaceBefore=8))
    story.append(Paragraph(
        f"Generated on {date_str or datetime.date.today().strftime('%d %B, %Y')} | "
        "This document is computer-generated. Please verify with a qualified lawyer before use.",
        styles['SmallText']
    ))


def signature_block(story, styles, parties):
    """Add signature lines for parties"""
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Signatures", styles['SectionHeading']))

    sig_data = []
    row = []
    for i, party in enumerate(parties):
        cell = f"<b>{party}</b><br/><br/>___________________________<br/><font size='8'>Signature &amp; Date</font>"
        row.append(Paragraph(cell, styles['SmallText']))
        if len(row) == 2 or i == len(parties) - 1:
            sig_data.append(row[:])
            row = []

    if sig_data:
        sig_table = Table(sig_data, colWidths=[8 * cm, 8 * cm])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(sig_table)


# ─── FIR ───────────────────────────────────────────────────────────────────────

def generate_fir_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)
    styles = get_styles()
    story = []

    build_header(story, styles, "First Information Report (FIR)",
                 "Police Complaint for Cognizable Offense",
                 "Under Section 154 Cr.P.C")

    # FIR Meta
    story.append(Paragraph("Complainant Information", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Full Name", data.get("complainant_name")),
        kv_row("CNIC No.", data.get("cnic")),
        kv_row("Father's Name", data.get("father_name")),
        kv_row("Mobile No.", data.get("phone")),
        kv_row("Address", data.get("address")),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Incident Details", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Police Station", data.get("police_station")),
        kv_row("District", data.get("district")),
        kv_row("Date of Incident", data.get("incident_date")),
        kv_row("Time of Incident", data.get("incident_time") or "Not specified"),
        kv_row("Location of Incident", data.get("incident_location")),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Accused & Offense Details", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Accused Name(s)", data.get("accused_name") or "Unknown"),
        kv_row("Accused Address", data.get("accused_address") or "Unknown"),
        kv_row("Offense Section", data.get("offense_section") or "To be determined"),
        kv_row("Witnesses", data.get("witnesses") or "None mentioned"),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Detailed Account of Offense:", styles['SectionHeading']))
    story.append(Paragraph(data.get("offense_details", ""), styles['BodyText2']))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "I, the complainant, hereby state that the above facts are true to the best of my knowledge "
        "and belief. I request the concerned police station to register this FIR and take necessary "
        "legal action against the accused.",
        styles['BodyText2']
    ))

    signature_block(story, styles, [
        f"Complainant\n{data.get('complainant_name', '')}",
        "Station House Officer (SHO)"
    ])
    build_footer(story, styles)
    doc.build(story)
    return buffer.getvalue()


# ─── Tenancy Agreement ─────────────────────────────────────────────────────────

def generate_tenancy_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)
    styles = get_styles()
    story = []

    build_header(story, styles, "Tenancy Agreement",
                 "Standard Rental Agreement",
                 "Rent Restriction Ordinance 2001")

    story.append(Paragraph(
        f"This Tenancy Agreement is entered into on "
        f"<b>{data.get('start_date', '___________')}</b> between:",
        styles['BodyText2']
    ))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Landlord", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Full Name", data.get("landlord_name")),
        kv_row("CNIC No.", data.get("landlord_cnic")),
        kv_row("Mobile No.", data.get("landlord_phone")),
        kv_row("Permanent Address", data.get("landlord_address")),
    ]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Tenant", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Full Name", data.get("tenant_name")),
        kv_row("CNIC No.", data.get("tenant_cnic")),
        kv_row("Mobile No.", data.get("tenant_phone")),
        kv_row("Father's Name", data.get("tenant_father_name")),
    ]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Property & Lease Details", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Property Address", data.get("property_address")),
        kv_row("Property Type", data.get("property_type")),
        kv_row("Monthly Rent", f"PKR {data.get('monthly_rent', '___')}/-"),
        kv_row("Security Deposit", f"PKR {data.get('security_deposit', '___')}/-"),
        kv_row("Advance Months", data.get("advance_months") or "N/A"),
        kv_row("Lease Duration", f"{data.get('lease_duration', '___')} months"),
        kv_row("Lease Start Date", data.get("start_date")),
        kv_row("Utilities", data.get("utilities")),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Terms & Conditions", styles['SectionHeading']))
    clauses = [
        "The Tenant shall pay rent on or before the 5th of each calendar month.",
        "The Tenant shall not sublet the premises without written consent of the Landlord.",
        "The Tenant shall maintain the premises in good condition and shall not carry out any structural changes.",
        "The Landlord shall provide 30 days' notice before terminating this agreement.",
        "The Tenant shall provide 30 days' notice before vacating the premises.",
        "The security deposit shall be refunded within 30 days of vacating, subject to deductions for damages.",
        "Disputes shall be resolved through local Union Council or competent court of Lahore/relevant city.",
    ]
    for i, clause in enumerate(clauses, 1):
        story.append(Paragraph(f"{i}. {clause}", styles['BodyText2']))

    if data.get("special_conditions"):
        story.append(Paragraph("Special Conditions:", styles['SectionHeading']))
        story.append(Paragraph(data.get("special_conditions"), styles['BodyText2']))

    signature_block(story, styles, [
        f"Landlord\n{data.get('landlord_name', '')}",
        f"Tenant\n{data.get('tenant_name', '')}",
        "Witness 1",
        "Witness 2"
    ])
    build_footer(story, styles)
    doc.build(story)
    return buffer.getvalue()


# ─── Divorce Notice ────────────────────────────────────────────────────────────

def generate_divorce_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)
    styles = get_styles()
    story = []

    build_header(story, styles, "Notice of Divorce (Talaq)",
                 "Legal Notice for Dissolution of Marriage",
                 "Muslim Family Laws Ordinance 1961 — Section 7")

    story.append(Paragraph("To,", styles['BodyText2']))
    story.append(Paragraph(f"<b>The Chairman, Union Council</b>", styles['BodyText2']))
    story.append(Paragraph(data.get("union_council", "___________"), styles['BodyText2']))
    story.append(Paragraph(data.get("city", "___________"), styles['BodyText2']))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Parties Information", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Husband's Name", data.get("husband_name")),
        kv_row("Husband's CNIC", data.get("husband_cnic")),
        kv_row("Husband's Father", data.get("husband_father")),
        kv_row("Husband's Address", data.get("husband_address")),
        kv_row("Wife's Name", data.get("wife_name")),
        kv_row("Wife's CNIC", data.get("wife_cnic")),
        kv_row("Wife's Father", data.get("wife_father")),
        kv_row("Wife's Address", data.get("wife_address")),
    ]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Marriage Details", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Date of Nikah", data.get("nikah_date")),
        kv_row("Nikah Registrar", data.get("nikah_registrar")),
        kv_row("Nikah Reg. Number", data.get("nikah_reg_number") or "N/A"),
        kv_row("Type of Talaq", data.get("talaq_type")),
        kv_row("Mehr Amount", f"PKR {data.get('mehr_amount', 'As per Nikah Nama')}"),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Notice", styles['SectionHeading']))
    story.append(Paragraph(
        f"I, <b>{data.get('husband_name', '___')}</b> son of <b>{data.get('husband_father', '___')}</b>, "
        f"CNIC No. <b>{data.get('husband_cnic', '___')}</b>, resident of <b>{data.get('husband_address', '___')}</b>, "
        f"hereby give notice under Section 7 of the Muslim Family Laws Ordinance, 1961 that I have "
        f"pronounced {data.get('talaq_type', 'Talaq')} upon my wife <b>{data.get('wife_name', '___')}</b> "
        f"daughter of <b>{data.get('wife_father', '___')}</b>.",
        styles['BodyText2']
    ))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "A copy of this notice is also being sent to the wife at the above-mentioned address. "
        "The Arbitration Council is requested to take appropriate action as per law.",
        styles['BodyText2']
    ))

    if data.get("reason"):
        story.append(Paragraph("Reason for Divorce:", styles['SectionHeading']))
        story.append(Paragraph(data.get("reason"), styles['BodyText2']))

    signature_block(story, styles, [
        f"Husband\n{data.get('husband_name', '')}",
        "Acknowledged by Union Council"
    ])
    build_footer(story, styles)
    doc.build(story)
    return buffer.getvalue()


# ─── Affidavit ─────────────────────────────────────────────────────────────────

def generate_affidavit_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)
    styles = get_styles()
    story = []

    build_header(story, styles, "Affidavit",
                 f"Re: {data.get('subject', 'Declaration')}",
                 "Qanoon-e-Shahadat Order 1984")

    if data.get("court_authority"):
        story.append(Paragraph(f"<b>Before:</b> {data.get('court_authority')}", styles['BodyText2']))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Deponent Information", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Full Name", data.get("deponent_name")),
        kv_row("CNIC No.", data.get("deponent_cnic")),
        kv_row("Father's Name", data.get("deponent_father")),
        kv_row("Age", str(data.get("deponent_age", ""))),
        kv_row("Occupation", data.get("deponent_occupation")),
        kv_row("Address", data.get("deponent_address")),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Declaration", styles['SectionHeading']))
    story.append(Paragraph(
        f"I, <b>{data.get('deponent_name', '___')}</b>, son/daughter/wife of "
        f"<b>{data.get('deponent_father', '___')}</b>, CNIC No. <b>{data.get('deponent_cnic', '___')}</b>, "
        f"aged <b>{data.get('deponent_age', '___')}</b> years, resident of "
        f"<b>{data.get('deponent_address', '___')}</b>, do hereby solemnly affirm and declare as under:",
        styles['BodyText2']
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(data.get("statement", ""), styles['BodyText2']))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "DEPONENT SOLEMNLY AFFIRMS that the contents of this Affidavit are true and correct to the "
        "best of his/her knowledge and belief. Nothing has been concealed or misrepresented.",
        styles['BodyText2']
    ))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"Sworn/Affirmed at <b>{data.get('city', '___')}</b> on this <b>{data.get('date', '___')}</b>",
        styles['BodyText2']
    ))

    signature_block(story, styles, [
        f"Deponent\n{data.get('deponent_name', '')}",
        "Oath Commissioner / Notary Public"
    ])
    build_footer(story, styles)
    doc.build(story)
    return buffer.getvalue()


# ─── Power of Attorney ─────────────────────────────────────────────────────────

def generate_poa_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)
    styles = get_styles()
    story = []

    build_header(story, styles, data.get("poa_type", "Power of Attorney"),
                 "Authorization Document",
                 "Powers of Attorney Act 1882")

    story.append(Paragraph("Principal (Grantor)", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Full Name", data.get("principal_name")),
        kv_row("CNIC No.", data.get("principal_cnic")),
        kv_row("Father's Name", data.get("principal_father")),
        kv_row("Address", data.get("principal_address")),
    ]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Attorney (Grantee)", styles['SectionHeading']))
    story.append(styled_table([
        kv_row("Full Name", data.get("attorney_name")),
        kv_row("CNIC No.", data.get("attorney_cnic")),
        kv_row("Relation to Principal", data.get("attorney_relation")),
        kv_row("Address", data.get("attorney_address")),
    ]))

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Grant of Authority", styles['SectionHeading']))
    story.append(Paragraph(
        f"KNOW ALL MEN BY THESE PRESENTS that I, <b>{data.get('principal_name', '___')}</b>, "
        f"son/daughter/wife of <b>{data.get('principal_father', '___')}</b>, CNIC No. "
        f"<b>{data.get('principal_cnic', '___')}</b>, resident of <b>{data.get('principal_address', '___')}</b>, "
        f"hereinafter called the PRINCIPAL, do hereby appoint "
        f"<b>{data.get('attorney_name', '___')}</b>, CNIC No. <b>{data.get('attorney_cnic', '___')}</b>, "
        f"my <b>{data.get('attorney_relation', '___')}</b>, as my true and lawful Attorney.",
        styles['BodyText2']
    ))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Powers Granted:", styles['SectionHeading']))
    story.append(Paragraph(data.get("powers_granted", ""), styles['BodyText2']))

    if data.get("property_description"):
        story.append(Paragraph("Property / Subject Description:", styles['SectionHeading']))
        story.append(Paragraph(data.get("property_description"), styles['BodyText2']))

    story.append(Spacer(1, 0.1 * inch))
    story.append(styled_table([
        kv_row("Validity / Duration", data.get("validity")),
        kv_row("Date of Execution", data.get("date")),
        kv_row("Place of Execution", data.get("city")),
    ]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "I hereby ratify and confirm all acts done by my said attorney in pursuance of this Power of Attorney.",
        styles['BodyText2']
    ))

    signature_block(story, styles, [
        f"Principal\n{data.get('principal_name', '')}",
        f"Attorney\n{data.get('attorney_name', '')}",
        "Witness 1",
        "Attested by Notary Public"
    ])
    build_footer(story, styles)
    doc.build(story)
    return buffer.getvalue()


# ─── Legal Notice ──────────────────────────────────────────────────────────────

def generate_legal_notice_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.2 * cm, bottomMargin=1.5 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm)
    styles = get_styles()
    story = []

    build_header(story, styles, "Legal Notice",
                 f"Subject: {data.get('notice_subject', 'Legal Matter')}",
                 "CPC Order XXI")

    story.append(Paragraph("To,", styles['BodyText2']))
    story.append(Paragraph(f"<b>{data.get('recipient_name', '___')}</b>", styles['BodyText2']))
    story.append(Paragraph(data.get("recipient_address", "___"), styles['BodyText2']))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph(f"<b>Date:</b> {data.get('date', '___')}", styles['BodyText2']))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"<b>Sub: Legal Notice — {data.get('notice_subject', '')}</b>",
        styles['BodyText2']
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CCCCCC'), spaceBefore=4, spaceAfter=8))

    story.append(Paragraph(
        f"Under instructions from and on behalf of my client <b>{data.get('sender_name', '___')}</b>, "
        f"CNIC No. <b>{data.get('sender_cnic', '___')}</b>, resident of "
        f"<b>{data.get('sender_address', '___')}</b>, I hereby serve upon you the following legal notice:",
        styles['BodyText2']
    ))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Statement of Facts:", styles['SectionHeading']))
    story.append(Paragraph(data.get("facts", ""), styles['BodyText2']))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Demand / Relief Sought:", styles['SectionHeading']))
    story.append(Paragraph(data.get("demand", ""), styles['BodyText2']))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"You are hereby called upon to comply with the above demand within "
        f"<b>{data.get('compliance_days', '___')} days</b> of receipt of this notice. "
        "Failing which, my client shall be constrained to initiate appropriate legal proceedings "
        "against you in a court of competent jurisdiction, at your risk and cost.",
        styles['BodyText2']
    ))

    story.append(Spacer(1, 0.3 * inch))
    advocate = data.get("advocate_name")
    if advocate:
        story.append(Paragraph(f"<b>Advocate:</b> {advocate}", styles['BodyText2']))
    story.append(Paragraph(f"<b>On behalf of:</b> {data.get('sender_name', '___')}", styles['BodyText2']))
    story.append(Paragraph(f"<b>Contact:</b> {data.get('sender_phone', '___')}", styles['BodyText2']))

    signature_block(story, styles, [
        f"{'Advocate / ' if advocate else ''}Sender\n{data.get('sender_name', '')}",
    ])
    build_footer(story, styles)
    doc.build(story)
    return buffer.getvalue()


# ─── Dispatcher ────────────────────────────────────────────────────────────────

PDF_GENERATORS = {
    "fir":          generate_fir_pdf,
    "tenancy":      generate_tenancy_pdf,
    "divorce":      generate_divorce_pdf,
    "affidavit":    generate_affidavit_pdf,
    "poa":          generate_poa_pdf,
    "legal_notice": generate_legal_notice_pdf,
}


def generate_document(template_type: str, form_data: dict) -> bytes:
    generator = PDF_GENERATORS.get(template_type)
    if not generator:
        raise ValueError(f"Unknown template type: {template_type}")
    return generator(form_data)