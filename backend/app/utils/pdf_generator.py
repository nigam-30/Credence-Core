"""
Credence Core — PDF Account Statement Generator
Uses ReportLab to construct formatted banking statements.
"""

import io
import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


def generate_account_statement_pdf(acc_no: str, data: dict) -> bytes:
    """Generate account statement PDF bytes using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=100)
    elements = []

    styles = getSampleStyleSheet()

    history = data.get('history', [])
    opening_date = "01/01/2026"
    if history:
        try:
            opening_date = history[0].get('date', '').split(' ')[0]
        except Exception:
            pass

    # Custom styles
    style_normal = styles['Normal']
    style_normal.fontSize = 9
    style_normal.leading = 11

    style_right_col = ParagraphStyle('RightCol', parent=styles['Normal'], fontSize=7.5, leading=9)
    style_logo = ParagraphStyle(
        'Logo',
        parent=styles['Heading2'],
        backColor=colors.HexColor("#004C8F"),
        textColor=colors.white,
        alignment=TA_LEFT,
        leftIndent=5,
        rightIndent=5,
        spaceBefore=0,
        spaceAfter=0
    )

    today_str = datetime.datetime.now().strftime("%d/%m/%Y")

    address_text = f"<font size=9>MR. {data.get('name', 'N/A').upper()}</font><br/>{data.get('address', 'As per bank records')}<br/>.<br/>.<br/><br/>JOINT HOLDERS :"
    address_box_table = Table([[Paragraph(address_text, style_normal)]], colWidths=[240])
    address_box_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    left_inner_data = [
        [Paragraph("<b> &nbsp;CREDENCE CORE BANK PVT LTD &nbsp;</b>", style_logo)],
        [Spacer(1, 15)],
        [address_box_table],
        [Spacer(1, 5)],
        [Paragraph("Nomination : Not Registered", style_normal)],
        [Spacer(1, 15)],
        [Table([[f"From : {opening_date}", f"To : {today_str}"]], colWidths=[85, 165], style=[
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ])]
    ]
    left_inner_table = Table(left_inner_data, colWidths=[250])
    left_inner_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))

    cust_id = str(data.get('customer_id') or (abs(hash(str(acc_no))) % 900000000 + 100000000))
    acc_type_val = data.get('account_type') or data.get('type') or 'Savings Account'
    right_data = [
        ["Account Branch", ": CREDENCE CORE MAIN BRANCH"],
        ["Address", ": Maker Chambers, Nariman Point, Mumbai."],
        ["City", ": Mumbai"],
        ["State", ": Maharashtra"],
        ["Phone no.", ": 011-2345678"],
        ["OD Limit", ": 0.00"],
        ["Currency", ": INR"],
        ["Email", f": {data.get('email', 'N/A')}"],
        ["Cust ID", f": {cust_id}"],
        ["Account No", f": {acc_no}"],
        ["A/C Open Date", f": {opening_date}"],
        ["Account Type", f": {acc_type_val}"],
        ["Account Status", ": Regular"],
    ]

    right_col_formatted = []
    for row in right_data:
        right_col_formatted.append([Paragraph(row[0], style_right_col), Paragraph(row[1], style_right_col)])

    right_inner_table = Table(right_col_formatted, colWidths=[80, 180])
    right_inner_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
    ]))

    master_table = Table([[left_inner_table, "", right_inner_table]], colWidths=[240, 50, 260])
    master_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))

    elements.append(Paragraph("Page No. : 1", ParagraphStyle('CenterAlign', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8)))
    elements.append(Spacer(1, 20))
    elements.append(master_table)
    elements.append(Spacer(1, 10))

    # Transactions Table
    table_data = [["Date", "Narration", "Ref No.", "Withdrawal (Dr)", "Deposit (Cr)", "Closing Balance"]]

    if history:
        for t in history:
            date_val = t.get('date', '').split(' ')[0] if ' ' in t.get('date', '') else t.get('date', '')
            narration = t.get('type', '')
            amt_str = str(t.get('amount', '0'))
            bal_str = str(t.get('balance', '0'))
            ref_no = t.get('ref_id') or ("REF/UP/" + str(abs(hash(date_val + narration)))[-6:])

            dr_amt = ""
            cr_amt = ""
            if amt_str.startswith("-"):
                dr_amt = amt_str[1:]
            elif amt_str.startswith("+"):
                cr_amt = amt_str[1:]
            else:
                try:
                    if float(amt_str) < 0:
                        dr_amt = str(abs(float(amt_str)))
                    else:
                        cr_amt = amt_str
                except Exception:
                    cr_amt = amt_str

            table_data.append([date_val, Paragraph(narration, style_normal), ref_no, dr_amt, cr_amt, bal_str])
    else:
        table_data.append(["-", "No transactions found", "-", "-", "-", "-"])

    table = Table(table_data, colWidths=[65, 200, 75, 65, 65, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#004C8F")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Statement Summary
    elements.append(Paragraph("<b>STATEMENT SUMMARY :-</b>", style_normal))

    total_debits = 0.0
    total_credits = 0.0
    dr_count = 0
    cr_count = 0
    closing_bal = 0.0
    try:
        closing_bal = float(str(data.get('balance', '0')).replace(',', ''))
    except Exception:
        pass

    for t in history:
        amt_val = str(t.get('amount', '0')).replace(',', '')
        amt_f = 0.0
        try:
            amt_f = float(amt_val)
        except Exception:
            if amt_val.startswith('-'):
                try: amt_f = -float(amt_val[1:])
                except Exception: pass
            elif amt_val.startswith('+'):
                try: amt_f = float(amt_val[1:])
                except Exception: pass

        if amt_f < 0:
            dr_count += 1
            total_debits += abs(amt_f)
        elif amt_f > 0:
            cr_count += 1
            total_credits += amt_f

    opening_bal = closing_bal + total_debits - total_credits

    summary_data = [
        ["Opening Balance", "Dr Count", "Cr Count", "Debits", "Credits", "Closing Bal"],
        [f"{opening_bal:,.2f}", str(dr_count), str(cr_count), f"{total_debits:,.2f}", f"{total_credits:,.2f}", f"{closing_bal:,.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[90, 60, 60, 80, 80, 80])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 40))

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc.pagesize[0] - 30, 80, "This is a computer generated statement and does not")
        canvas.drawRightString(doc.pagesize[0] - 30, 70, "require signature.")

        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(colors.HexColor('#004C8F'))
        canvas.drawString(30, 60, "CREDENCE CORE BANK LIMITED")

        canvas.setFont('Helvetica-Bold', 8)
        canvas.setFillColor(colors.blue)
        canvas.drawString(30, 50, "*Closing balance includes funds earmarked for hold and uncleared funds")

        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.black)
        text1 = "Contents of this statement will be considered correct if no error is reported within 30 days of receipt of statement. The address on this statement is that on record with the Bank"
        text2 = "as at the day of requesting this statement."
        text3 = "CREDENCE CORE Bank Service Tax Registration Number: M-IV/ST/BANK & OTHER SERVICES /20/2001"
        text4 = "Registered Office Address: CREDENCE CORE House, Senapati Bapat Marg, Lower Parel, Mumbai 400013"
        canvas.drawString(30, 40, text1)
        canvas.drawString(30, 31, text2)
        canvas.drawString(30, 22, text3)
        canvas.drawString(30, 13, text4)
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
