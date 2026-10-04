import io
import os
import subprocess
import threading
import time
import json
import re
import hashlib
from flask import Flask, request, jsonify, send_from_directory, make_response
from bs4 import BeautifulSoup
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import datetime
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or not os.access(BASE_DIR, os.W_OK))
DATA_DIR = "/tmp" if IS_SERVERLESS else BASE_DIR

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

PROFILES_JSON = os.path.join(DATA_DIR, "user_profiles.json")
BANK_DATA_JSON = os.path.join(DATA_DIR, "bank_data.json")
INVESTMENTS_JSON = os.path.join(DATA_DIR, "user_investments.json")

def load_profiles():
    if not os.path.exists(PROFILES_JSON):
        try:
            with open(PROFILES_JSON, "w") as f:
                json.dump({}, f)
        except Exception:
            pass
        return {}
    try:
        with open(PROFILES_JSON, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_profiles(data):
    try:
        tmp_path = PROFILES_JSON + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, PROFILES_JSON)
    except Exception:
        pass

def load_investments():
    if not os.path.exists(INVESTMENTS_JSON):
        try:
            with open(INVESTMENTS_JSON, "w") as f:
                json.dump({}, f)
        except Exception:
            pass
        return {}
    try:
        with open(INVESTMENTS_JSON, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_investments(data):
    try:
        tmp_path = INVESTMENTS_JSON + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, INVESTMENTS_JSON)
    except Exception:
        pass

def run_cpp_command(bank_instance, choice, inputs):
    with bank_instance.lock:
        if bank_instance.proc.poll() is not None:
            bank_instance.start_process()
        
        bank_instance.stdin.write(f"{choice}\n")
        bank_instance.stdin.flush()
        for val in inputs:
            bank_instance.stdin.write(f"{val}\n")
            bank_instance.stdin.flush()
            
        out = bank_instance._read_until("Enter choice: ")
        return out

def parse_output(out):
    filtered_out = re.sub(r"--- Banking Menu ---[\s\S]*?Enter choice:", "", out).strip()
    filtered_out = re.sub(r"Enter .*?:", "", filtered_out).strip()
    return filtered_out

def generate_pdf(acc_no, data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=100)
    elements = []
    
    styles = getSampleStyleSheet()
    
    history = data.get('history', [])
    opening_date = "01/01/2026"
    if history:
        try:
            opening_date = history[0].get('date', '').split(' ')[0]
        except:
            pass
    
    
    # Custom styles
    style_normal = styles['Normal']
    style_normal.fontSize = 9
    style_normal.leading = 11
    
    style_heading = styles['Heading1']
    style_heading.fontSize = 14
    style_heading.textColor = colors.HexColor("#004C8F") # Blue
    style_heading.alignment = TA_CENTER
    
    style_right = ParagraphStyle('RightAlign', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9)
    style_center = ParagraphStyle('CenterAlign', parent=styles['Heading3'], alignment=TA_CENTER)
    
    style_right_col = ParagraphStyle('RightCol', parent=styles['Normal'], fontSize=7.5, leading=9)
    style_logo = ParagraphStyle('Logo', parent=styles['Heading2'], backColor=colors.HexColor("#004C8F"), textColor=colors.white, alignment=TA_LEFT, leftIndent=5, rightIndent=5, spaceBefore=0, spaceAfter=0)
    
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
    
    # 4. Transactions Table
    table_data = [["Date", "Narration", "Ref No.", "Withdrawal (Dr)", "Deposit (Cr)", "Closing Balance"]]
    
    history = data.get('history', [])
    if history:
        for t in history:
            date_val = t.get('date', '').split(' ')[0] if ' ' in t.get('date', '') else t.get('date', '')
            narration = t.get('type', '')
            amt_str = str(t.get('amount', '0'))
            bal_str = str(t.get('balance', '0'))
            ref_no = "REF/UP/" + str(hash(date_val + narration))[-6:]
            
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
                except:
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
    
    # 5. Statement Summary
    statement_summary_title = Paragraph("<b>STATEMENT SUMMARY :-</b>", style_normal)
    elements.append(statement_summary_title)
    
    total_debits = 0.0
    total_credits = 0.0
    dr_count = 0
    cr_count = 0
    closing_bal = 0.0
    try:
        closing_bal = float(str(data.get('balance', '0')).replace(',', ''))
    except:
        pass
        
    for t in history:
        amt_val = str(t.get('amount', '0')).replace(',', '')
        amt_f = 0.0
        try:
            amt_f = float(amt_val)
        except:
            if amt_val.startswith('-'):
                try: amt_f = -float(amt_val[1:])
                except: pass
            elif amt_val.startswith('+'):
                try: amt_f = float(amt_val[1:])
                except: pass
        
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
    
    # 6. Footer Notes
    def add_footer(canvas, doc):
        canvas.saveState()
        # Right note
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc.pagesize[0] - 30, 80, "This is a computer generated statement and does not")
        canvas.drawRightString(doc.pagesize[0] - 30, 70, "require signature.")
        
        # Left notes
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(colors.HexColor('#004C8F'))
        canvas.drawString(30, 60, "FINTECH BANK LIMITED")
        
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

def get_or_create_account_history(acc_no, current_balance, name="Bank Customer"):
    history = []
    if os.path.exists(BANK_DATA_JSON):
        try:
            with open(BANK_DATA_JSON, "r") as f:
                bd = json.load(f)
                history = bd.get("accounts", {}).get(str(acc_no), {}).get("history", [])
        except Exception:
            history = []

    bal_num = float(str(current_balance).replace(',', ''))
    if not history and bal_num > 0:
        now = datetime.datetime.now()
        d_str = now.strftime("%d/%m/%Y %H:%M:%S")
        history = [
            {"date": d_str, "type": "Initial Account Deposit", "amount": f"+{bal_num:.2f}", "balance": f"{bal_num:.2f}"}
        ]

        # Save to bank_data.json
        try:
            data = {}
            if os.path.exists(BANK_DATA_JSON):
                try:
                    with open(BANK_DATA_JSON, "r") as f: data = json.load(f)
                except Exception: pass
            if "accounts" not in data: data["accounts"] = {}
            data["accounts"][str(acc_no)] = {"history": history}
            with open(BANK_DATA_JSON, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    return history

class BankBackend:
    def __init__(self):
        self.lock = threading.Lock()
        self.netbanking_db = {}
        self.user_details_db = load_profiles()
        self.use_fallback = False
        self.py_accounts = {}
        self.start_process()

    def compile_if_missing(self):
        if IS_SERVERLESS or os.environ.get("VERCEL"):
            self.use_fallback = True
            return
        exe_file = os.path.join(BASE_DIR, "bank_system.exe" if os.name == 'nt' else "bank_system")
        if not os.path.exists(exe_file):
            try:
                print("Compiling " + exe_file + "...")
                subprocess.run(["g++", "main.cpp", "account.cpp", "credit.cpp", "debit.cpp", 
                                "fd.cpp", "loan.cpp", "report.cpp", "upi.cpp", "utils.cpp", "cheque.cpp", "globals.cpp", 
                                "-o", exe_file], cwd=BASE_DIR, check=True)
            except Exception as e:
                print(f"Compilation skipped/failed ({e}). Switching to pure-Python engine.")
                self.use_fallback = True

    def start_process(self):
        # WIPE PERSISTENT FILES ON BOOT SO THE SERVER STARTS FRESH AS REQUESTED
        if os.path.exists(BANK_DATA_JSON):
            try: os.remove(BANK_DATA_JSON)
            except Exception: pass
        if os.path.exists(PROFILES_JSON):
            try: os.remove(PROFILES_JSON)
            except Exception: pass
            
        self.user_details_db = {}
        try:
            self.compile_if_missing()
        except Exception:
            self.use_fallback = True

        exe_file = os.path.join(BASE_DIR, "bank_system.exe" if os.name == 'nt' else "./bank_system")
        if not self.use_fallback and os.path.exists(exe_file):
            try:
                self.proc = subprocess.Popen(
                    [exe_file],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=BASE_DIR
                )
                if self.proc.stdout and self.proc.stdin:
                    self.stdout = self.proc.stdout
                    self.stdin = self.proc.stdin
                    self.init_output = self._read_until("Enter choice: ")
                    self.use_fallback = False
                    return
            except Exception as e:
                print(f"Failed to start binary ({e}). Using Python serverless engine.")
        
        self.use_fallback = True
        self.proc = None
        self.proc = None

    def _read_until(self, marker, timeout=5.0):
        if self.use_fallback or not self.proc:
            return ""
        buffer = ""
        start = time.time()
        while time.time() - start < timeout:
            if self.proc.poll() is not None:
                self.start_process()
                break
            char = self.stdout.read(1)
            if not char: break
            buffer += char
            if buffer.endswith(marker): break
        return buffer

    def execute(self, choice, inputs):
        if not self.use_fallback and self.proc:
            try:
                return run_cpp_command(self, choice, inputs)
            except Exception as e:
                print(f"C++ process communication error: {e}. Switching to Python engine.")
                self.use_fallback = True

        # Pure Python In-Memory Banking Ledger Fallback (Serverless / Linux / Vercel)
        choice = str(choice).strip()
        out = ""
        with self.lock:
            if choice == "1":
                # Create Account: [name, deposit, debit (y/n), pin]
                name = inputs[0] if len(inputs) > 0 else "Customer"
                deposit = float(inputs[1]) if len(inputs) > 1 and inputs[1] else 0.0
                debit_opt = inputs[2] if len(inputs) > 2 else "n"
                pin = inputs[3] if len(inputs) > 3 else "1234"
                
                # Generate unique 14-digit account number
                if not self.py_accounts and name == "Ben Tennyson":
                    acc_no = "40273146502136"
                else:
                    while True:
                        acc_no = str(random.randint(10000000000000, 99999999999999))
                        if acc_no not in self.py_accounts:
                            break
                
                card_num = f"4092 8819 2401 {acc_no[-4:]}"
                cvv = "892"
                exp = "10/30"
                self.py_accounts[acc_no] = {
                    "account_number": acc_no,
                    "name": name,
                    "balance": deposit,
                    "loanAmount": 0.0,
                    "fixedDeposit": 0.0,
                    "pin": pin,
                    "card": {"cardNumber": card_num, "nameOnCard": name, "expiry": exp, "cvv": cvv, "pin": pin} if debit_opt.lower() == 'y' else None,
                    "hasDebitCard": (debit_opt.lower() == 'y')
                }
                out = f"Your new Account Number is: {acc_no}\n"
                if debit_opt.lower() == 'y':
                    out += f"Debit Card issued successfully!\nCard Number : {card_num}\nName on Card: {name}\nExpiry Date : {exp}\nCVV         : {cvv}\n"
                out += f"Account created successfully with initial deposit of INR {deposit:.2f}.\nEnter choice: "

            elif choice == "2":
                # Check Balance: [acc]
                acc_no = str(inputs[0]) if len(inputs) > 0 else ""
                if acc_no in self.py_accounts:
                    bal = self.py_accounts[acc_no]["balance"]
                    out = f"Balance for account {acc_no} : INR {bal:.2f}\nEnter choice: "
                else:
                    out = f"Account not found.\nEnter choice: "

            elif choice == "3":
                # Transfer Money / Debit: [from_acc, to_acc, amount]
                from_acc = str(inputs[0]) if len(inputs) > 0 else ""
                to_acc = str(inputs[1]) if len(inputs) > 1 else ""
                amount = float(inputs[2]) if len(inputs) > 2 else 0.0
                if from_acc in self.py_accounts:
                    if self.py_accounts[from_acc]["balance"] >= amount:
                        self.py_accounts[from_acc]["balance"] -= amount
                        if to_acc in self.py_accounts:
                            self.py_accounts[to_acc]["balance"] += amount
                        out = f"Transfer of INR {amount:.2f} successful.\nEnter choice: "
                    else:
                        out = f"Insufficient balance.\nEnter choice: "
                else:
                    out = f"Invalid account number.\nEnter choice: "

            elif choice == "4":
                # Apply Loan: [acc, amount]
                acc_no = str(inputs[0]) if len(inputs) > 0 else ""
                amount = float(inputs[1]) if len(inputs) > 1 else 0.0
                if acc_no in self.py_accounts:
                    self.py_accounts[acc_no]["loanAmount"] += amount
                    self.py_accounts[acc_no]["balance"] += amount
                    out = f"Loan of INR {amount:.2f} approved and credited.\nEnter choice: "
                else:
                    out = f"Account not found.\nEnter choice: "

            elif choice == "5":
                # Repay Loan: [acc, amount]
                acc_no = str(inputs[0]) if len(inputs) > 0 else ""
                amount = float(inputs[1]) if len(inputs) > 1 else 0.0
                if acc_no in self.py_accounts:
                    if self.py_accounts[acc_no]["balance"] >= amount:
                        curr_loan = self.py_accounts[acc_no]["loanAmount"]
                        actual_repay = min(amount, curr_loan) if curr_loan > 0 else amount
                        self.py_accounts[acc_no]["balance"] -= actual_repay
                        self.py_accounts[acc_no]["loanAmount"] = max(0.0, curr_loan - actual_repay)
                        out = f"Loan repayment of INR {actual_repay:.2f} successful.\nEnter choice: "
                    else:
                        out = f"Insufficient balance.\nEnter choice: "
                else:
                    out = f"Account not found.\nEnter choice: "

            elif choice == "6":
                # Calculate FD Maturity: [amount, years]
                amount = float(inputs[0]) if len(inputs) > 0 else 0.0
                years = int(inputs[1]) if len(inputs) > 1 else 1
                rate = 7.2 if years == 1 else (7.5 if years == 2 else 7.8)
                maturity = amount * ((1 + rate/100.0) ** years)
                out = f"Estimated Maturity: INR {maturity:.2f}\nEnter choice: "

            elif choice == "7":
                # Create FD: [acc, amount, years]
                acc_no = str(inputs[0]) if len(inputs) > 0 else ""
                amount = float(inputs[1]) if len(inputs) > 1 else 0.0
                if acc_no in self.py_accounts:
                    if self.py_accounts[acc_no]["balance"] >= amount:
                        self.py_accounts[acc_no]["balance"] -= amount
                        self.py_accounts[acc_no]["fixedDeposit"] += amount
                        out = f"Fixed Deposit of INR {amount:.2f} created successfully.\nEnter choice: "
                    else:
                        out = f"Insufficient balance to create FD.\nEnter choice: "
                else:
                    out = f"Account not found.\nEnter choice: "

            elif choice == "8":
                # Withdraw FD: [acc]
                acc_no = str(inputs[0]) if len(inputs) > 0 else ""
                if acc_no in self.py_accounts:
                    fd_amt = self.py_accounts[acc_no]["fixedDeposit"]
                    self.py_accounts[acc_no]["balance"] += fd_amt
                    self.py_accounts[acc_no]["fixedDeposit"] = 0.0
                    out = f"Fixed Deposit withdrawn and credited to balance.\nEnter choice: "
                else:
                    out = f"Account not found.\nEnter choice: "

            elif choice == "9":
                # Report: []
                out = "\n--- Account Report ---\n"
                for a_no, a in self.py_accounts.items():
                    out += f"Account No: {a_no} | Name: {a['name']} | Balance: INR {a['balance']:.2f} | Loan: INR {a['loanAmount']:.2f} | FD: INR {a['fixedDeposit']:.2f}\n"
                out += "----------------------\nEnter choice: "

            elif choice == "10":
                # Register UPI: [acc, upi_id]
                acc_no = str(inputs[0]) if len(inputs) > 0 else ""
                upi_id = str(inputs[1]) if len(inputs) > 1 else ""
                out = f"UPI ID {upi_id} registered for account {acc_no}.\nEnter choice: "

            elif choice == "11":
                # Transfer: [from_acc, to_acc, amount, pin]
                from_acc = str(inputs[0]) if len(inputs) > 0 else ""
                to_acc = str(inputs[1]) if len(inputs) > 1 else ""
                amount = float(inputs[2]) if len(inputs) > 2 else 0.0
                if from_acc in self.py_accounts and to_acc in self.py_accounts:
                    if self.py_accounts[from_acc]["balance"] >= amount:
                        self.py_accounts[from_acc]["balance"] -= amount
                        self.py_accounts[to_acc]["balance"] += amount
                        out = f"Transfer of INR {amount:.2f} from {from_acc} to {to_acc} successful.\nEnter choice: "
                    else:
                        out = f"Insufficient balance for transfer.\nEnter choice: "
                else:
                    out = f"Invalid account number(s).\nEnter choice: "

            elif choice == "12":
                # Issue Cheque: [acc, amount]
                out = f"Cheque issued successfully.\nEnter choice: "
            else:
                out = "Invalid choice.\nEnter choice: "

        return out

    def get_report(self):
        if self.use_fallback or not self.proc:
            accounts = []
            with self.lock:
                for a_no, a in self.py_accounts.items():
                    accounts.append({
                        "account_number": str(a_no),
                        "name": str(a.get("name", "User")),
                        "balance": f"{float(a.get('balance', 0.0)):.2f}",
                        "loan_amount": f"{float(a.get('loanAmount', 0.0)):.2f}",
                        "fixed_deposit": f"{float(a.get('fixedDeposit', 0.0)):.2f}"
                    })
            return accounts

        out = self.execute("9", [])
        accounts = []
        for line in out.split('\n'):
            if line.startswith("Account No:"):
                parts = line.split(" | ")
                if len(parts) >= 3:
                    try:
                        acc_no = parts[0].split(": ")[1].strip()
                        name = parts[1].split(": ")[1].strip()
                        bal_str = parts[2].split("INR ")[-1].strip()
                        loan_str = parts[3].split("INR ")[-1].strip() if len(parts)>3 else "0"
                        fd_str = parts[4].split("INR ")[-1].strip() if len(parts)>4 else "0"
                        
                        accounts.append({
                            "account_number": acc_no,
                            "name": name,
                            "balance": bal_str,
                            "loan_amount": loan_str,
                            "fixed_deposit": fd_str
                        })
                    except Exception as e:
                        print("Parse error on line:", line, e)
                        continue
        return accounts

bank = BankBackend()
print("Connected to C++ Backend successfully.")

def init_demo_account_if_needed():
    report = bank.get_report()
    user_accs = [a for a in report if str(a["account_number"]) not in ["999999", "99999999999999"]]
    if not user_accs:
        out = bank.execute("1", ["Ben Tennyson", "25000", "y", "1234"])
        acc_no = None
        ms = re.search(r"Account Number is:\s*(\d+)", out)
        if ms:
            acc_no = ms.group(1)
        else:
            rep = bank.get_report()
            for r in rep:
                if str(r["account_number"]) not in ["999999", "99999999999999"]:
                    acc_no = str(r["account_number"])
                    break
        if not acc_no:
            acc_no = "50100982341275"

        bank.execute("10", [acc_no, f"ben_{acc_no[-4:]}@credence"])
        bank.user_details_db[str(acc_no)] = {
            "name": "Ben Tennyson",
            "email": "ben@credence.bank",
            "dob": "1998-12-27",
            "address": "Bellwood, Sector 4, Metro City",
            "nb_pass": "admin123",
            "upi_id": f"ben_{acc_no[-4:]}@credence",
            "pin": "1234",
            "card_number": f"4092 8819 2401 {acc_no[-4:]}",
            "cvv": "892",
            "expiry": "10/30",
            "company": "Visa"
        }
        save_profiles(bank.user_details_db)
        get_or_create_account_history(acc_no, "25000.00", "Ben Tennyson")

init_demo_account_if_needed()

@app.route("/")
@app.route("/index")
@app.route("/api/index")
@app.route("/api/index.py")
def index():
    return send_ui_file("code.html")

@app.route("/dashboard")
def dashboard():
    return send_ui_file("code(1).html")

@app.route("/account")
@app.route("/accounts")
def account():
    return send_ui_file("code(1).html")

@app.route("/upi")
def upi():
    return send_ui_file("code(1).html")

@app.route("/loan")
@app.route("/loans")
def loan():
    return send_ui_file("code(1).html")

@app.route("/transactions")
@app.route("/history")
def transactions():
    return send_ui_file("code(1).html")

@app.route("/analytics")
def analytics():
    return send_ui_file("code(1).html")

@app.route("/reports")
@app.route("/statement")
def reports():
    return send_ui_file("code(1).html")

@app.route("/settings")
def settings():
    return send_ui_file("code(1).html")

@app.route("/invest")
@app.route("/investments")
@app.route("/sip")
@app.route("/ipo")
@app.route("/mutualfunds")
@app.route("/fd")
@app.route("/fds")
def invest():
    return send_ui_file("code(1).html")

@app.route("/transfer")
@app.route("/pay")
@app.route("/services")
def services():
    return send_ui_file("code(1).html")

@app.route("/cards")
@app.route("/card")
def cards():
    return send_ui_file("code(1).html")

@app.route("/app.js")
def serve_app_js():
    target_dir = BASE_DIR if os.path.exists(os.path.join(BASE_DIR, "app.js")) else (
        os.path.join(BASE_DIR, "ui_code") if os.path.exists(os.path.join(BASE_DIR, "ui_code", "app.js")) else BASE_DIR
    )
    response = send_from_directory(target_dir, "app.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def send_ui_file(filename):
    filepath = os.path.join(BASE_DIR, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(BASE_DIR, "ui_code", filename)
    if not os.path.exists(filepath):
        filepath = filename

    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    existing_script = soup.find("script", src="/app.js")
    if not existing_script and soup.body:
        script_tag = soup.new_tag("script", src="/app.js")
        soup.body.append(script_tag)
    return str(soup)

@app.route("/api/login", methods=["POST"])
def login():
    req = request.json
    accNo = req.get("account")
    password = req.get("password", "")
    accounts = bank.get_report()
    
    for acc in accounts:
        if str(acc["account_number"]) == str(accNo):
            nb_pass_on_file = bank.user_details_db.get(str(accNo), {}).get("nb_pass")
            if nb_pass_on_file and password and password != nb_pass_on_file:
                return jsonify({"success": False, "message": "Invalid Netbanking Password!"})
            return jsonify({
                "success": True, 
                "message": "Logged in", 
                "account": {
                    "account_number": acc["account_number"],
                    "name": acc["name"],
                    "balance": acc["balance"],
                    "loan_amount": acc["loan_amount"],
                    "fixed_deposit": acc["fixed_deposit"]
                }
            })
            
    return jsonify({"success": False, "message": "Account not found in C++ memory. Please pass correct credentials!"})

@app.route("/api/create_account", methods=["POST"])
def create_account():
    req = request.json or {}
    name = str(req.get("name", ""))
    deposit = str(req.get("deposit", "0"))
    account_type = str(req.get("account_type", "Savings Account"))
    debit = str(req.get("debit", "y"))
    pin = str(req.get("pin", "1234"))
    want_upi = str(req.get("upi_id", ""))
    upi_pin = str(req.get("upi_pin", ""))
    want_nb = str(req.get("nb_pass", ""))
    
    if want_upi and len(upi_pin) not in [4, 6]:
        return jsonify({"success": False, "message": "UPI PIN must be 4 or 6 digits."})
    
    inputs_to_send = [name, deposit, debit]
    if debit.lower() == 'y':
        inputs_to_send.append(pin)
        
    out = bank.execute("1", inputs_to_send)
    
    acc_no = None
    ms = re.search(r"Account Number is: (\d+)", out)
    if ms:
        acc_no = ms.group(1)
        if want_upi:
            bank.execute("10", [acc_no, want_upi])
            
        # Generate unique 9-digit Customer ID
        customer_id = str(random.randint(100000000, 999999999))
        details = {
            "customer_id": customer_id,
            "account_type": account_type,
            "email": req.get("email", ""),
            "dob": req.get("dob", ""),
            "address": req.get("address", "Digital Banking Customer"),
            "nb_pass": want_nb if want_nb else ""
        }
        
        if want_upi and upi_pin:
            details["upi_pin_hash"] = hashlib.sha256(upi_pin.encode()).hexdigest()
        
        # Extract C++ generated Debit Card explicitly
        if debit.lower() == 'y':
            card_match = re.search(r"Card Number\s*:\s*([\d\s]+)", out)
            if card_match:
                details["card_number"] = card_match.group(1).strip()
            cvv_match = re.search(r"CVV\s*:\s*(\d+)", out)
            if cvv_match:
                details["cvv"] = cvv_match.group(1).strip()
            exp_match = re.search(r"Expiry Date\s*:\s*([\d/]+)", out)
            if exp_match:
                details["expiry"] = exp_match.group(1).strip()
            details["company"] = "Visa" # Inferred from C++ starting digit 4

        bank.user_details_db[str(acc_no)] = details
        save_profiles(bank.user_details_db)

        # Initialize 100% clean zero-investment portfolio for the newly created account
        all_inv = load_investments()
        all_inv[str(acc_no)] = {
            "sips": [],
            "ipos": [],
            "rds": [],
            "gold": {
                "grams": 0.0,
                "avg_buy_price": fetch_live_gold_rate()["buy_rate"],
                "total_invested": 0.0,
                "current_rate": fetch_live_gold_rate()["buy_rate"],
                "current_value": 0.0,
                "returns_pct": 0.0
            }
        }
        save_investments(all_inv)
        
        if float(deposit) > 0:
            save_transaction(acc_no, f"Initial Deposit ({account_type})", f"+{deposit}", deposit)
            
    filtered_out = parse_output(out)
    msg = f"{account_type} created! Your Account Number is {acc_no}."
    if want_upi:
        msg += f"\nUPI ID '{want_upi}' also registered."
    
    return jsonify({"success": True, "message": msg, "account_number": acc_no, "account_type": account_type, "customer_id": details.get("customer_id", "")})

@app.route("/api/account/<acc_no>")
def get_account(acc_no):
    accounts = bank.get_report()
    for acc in accounts:
        if str(acc["account_number"]) == str(acc_no):
            details = bank.user_details_db.setdefault(str(acc_no), {})
            
            # Ensure 9-digit Customer ID
            if "customer_id" not in details:
                seeded_id = str(abs(hash(str(acc_no))) % 900000000 + 100000000)
                details["customer_id"] = seeded_id
                save_profiles(bank.user_details_db)
                
            # Generate static mock debit card if missing
            if "card_number" not in details:
                import random
                random.seed(int(acc_no))
                details["card_number"] = f"4{random.randint(100,999)} {random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
                details["cvv"] = str(random.randint(100, 999))
                details["company"] = random.choice(["Visa", "MasterCard"])
                details["expiry"] = f"{random.randint(1, 12):02d}/{random.randint(26, 30)}"
                random.seed()
                save_profiles(bank.user_details_db)
                
            acc["customer_id"] = details.get("customer_id")
            acc["account_type"] = details.get("account_type", "Savings Account")
            acc["email"] = details.get("email", "")
            acc["address"] = details.get("address", "")
            acc["dob"] = details.get("dob", "")
            acc["card_number"] = details.get("card_number")
            acc["cvv"] = details.get("cvv")
            acc["company"] = details.get("company")
            acc["expiry"] = details.get("expiry")
            acc["cheque_books"] = details.get("cheque_books", [])
            acc["physical_cards"] = details.get("physical_cards", [])
            if details.get("cc_number") and not details.get("cc_cvv"):
                import random
                random.seed(int(acc_no) + 1)
                base_cc = details.get("cc_number", "").replace(" ", "")
                if len(base_cc) == 12:
                    base_cc += str(random.randint(1000, 9999))
                details["cc_number"] = base_cc
                details["cc_cvv"] = str(random.randint(100, 999))
                details["cc_expiry"] = f"{random.randint(1, 12):02d}/{random.randint(28, 32)}"
                random.seed()
                save_profiles(bank.user_details_db)

            acc["cc_number"] = details.get("cc_number", "")
            acc["cc_limit"] = details.get("cc_limit", "")
            acc["cc_cvv"] = details.get("cc_cvv", "")
            acc["cc_expiry"] = details.get("cc_expiry", "")
            
            acc["blocked_cards"] = details.get("blocked_cards", [])

            # Attach bank_data History with realistic initial entries
            acc["history"] = get_or_create_account_history(acc_no, acc.get("balance", "0"), acc.get("name", "Bank Customer"))
            return jsonify(acc)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/block_card", methods=["POST"])
def block_card():
    req = request.json
    acc_no = str(req.get("account"))
    
    if acc_no not in bank.user_details_db:
        return jsonify({"success": False, "message": "Account not found."})
        
    details = bank.user_details_db[acc_no]
    
    if "card_number" in details and details["card_number"]:
        # Move to blocked cards
        if "blocked_cards" not in details:
            details["blocked_cards"] = []
        
        details["blocked_cards"].append({
            "card_number": details["card_number"],
            "expiry": details.get("expiry", "")
        })
        
        # Clear current card
        details["card_number"] = ""
        details["cvv"] = ""
        details["expiry"] = ""
        save_profiles(bank.user_details_db)
        
        return jsonify({"success": True, "message": "Debit card securely blocked."})
        
    return jsonify({"success": False, "message": "No active debit card found."})

@app.route("/api/issue_card", methods=["POST"])
def issue_card():
    req = request.json
    acc_no = str(req.get("account"))
    
    if acc_no not in bank.user_details_db:
        bank.user_details_db[acc_no] = {}
        
    details = bank.user_details_db[acc_no]
    
    if "card_number" in details and details["card_number"]:
         return jsonify({"success": False, "message": "You already have an active debit card."})
         
    new_pin = req.get("pin")
    if not new_pin or len(str(new_pin)) != 4 or not str(new_pin).isdigit():
         return jsonify({"success": False, "message": "Valid 4-digit PIN is required."})
         
    import random
    # Use random without seed to generate new card
    random.seed()
    details["card_number"] = f"4{random.randint(100,999)} {random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
    details["cvv"] = str(random.randint(100, 999))
    details["company"] = random.choice(["Visa", "MasterCard"])
    details["expiry"] = f"{random.randint(1, 12):02d}/{random.randint(26, 30)}"
    details["pin"] = str(new_pin)
    save_profiles(bank.user_details_db)
    
    return jsonify({"success": True, "message": "New debit card issued successfully."})

@app.route("/api/services/order_chequebook", methods=["POST"])
def order_chequebook():
    req = request.json or {}
    acc_no = str(req.get("account", "")).strip()
    leaves = int(req.get("leaves", 25))
    address = str(req.get("address", "")).strip()
    cheque_type = str(req.get("type", "CTS-2010 Standard Bearer Cheque"))
    
    accs = bank.get_report()
    acc = next((a for a in accs if str(a["account_number"]) == acc_no), None)
    if not acc:
        return jsonify({"success": False, "message": "Account not found."})
        
    details = bank.user_details_db.setdefault(acc_no, {})
    if not address:
        address = details.get("address", "Registered Communication Address")
        
    if "cheque_books" not in details:
        details["cheque_books"] = []
        
    start_num = random.randint(100000, 899999)
    end_num = start_num + leaves - 1
    chq_series = f"CHQ-{start_num} to CHQ-{end_num}"
    tracking_id = f"SPEEDPOST-IN{random.randint(100000, 999999)}"
    order_date = datetime.datetime.now().strftime("%d/%m/%Y")
    
    new_order = {
        "id": f"CBK-{random.randint(1000, 9999)}",
        "leaves": leaves,
        "series": chq_series,
        "type": cheque_type,
        "address": address,
        "order_date": order_date,
        "status": "Dispatched / In Transit",
        "tracking_id": tracking_id
    }
    details["cheque_books"].insert(0, new_order)
    save_profiles(bank.user_details_db)
    
    return jsonify({
        "success": True,
        "message": f"Cheque Book ({leaves} Leaves, {chq_series}) ordered successfully! Dispatched via Speed Post (Tracking ID: {tracking_id}). It will be delivered in 2-3 working days.",
        "order": new_order
    })

@app.route("/api/services/order_physical_card", methods=["POST"])
def order_physical_card():
    req = request.json or {}
    acc_no = str(req.get("account", "")).strip()
    variant = str(req.get("variant", "Visa Platinum Obsidian"))
    name_on_card = str(req.get("name_on_card", "")).strip()
    pin = str(req.get("pin", "1234")).strip()
    address = str(req.get("address", "")).strip()
    
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({"success": False, "message": "4-Digit numeric ATM PIN is required."})
        
    accs = bank.get_report()
    acc = next((a for a in accs if str(a["account_number"]) == acc_no), None)
    if not acc:
        return jsonify({"success": False, "message": "Account not found."})
        
    details = bank.user_details_db.setdefault(acc_no, {})
    if not name_on_card:
        name_on_card = acc.get("name", "Account Holder")
    if not address:
        address = details.get("address", "Registered Communication Address")
        
    if "physical_cards" not in details:
        details["physical_cards"] = []
        
    random.seed()
    first_digit = "4" if "visa" in variant.lower() else ("6" if "rupay" in variant.lower() else "5")
    card_number = f"{first_digit}{random.randint(100,999)} {random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
    cvv = str(random.randint(100, 999))
    expiry = f"{random.randint(1, 12):02d}/{random.randint(28, 32)}"
    tracking_id = f"BLUEDART-BD{random.randint(100000, 999999)}"
    order_date = datetime.datetime.now().strftime("%d/%m/%Y")
    
    details["card_number"] = card_number
    details["cvv"] = cvv
    details["expiry"] = expiry
    details["company"] = variant
    details["pin"] = pin
    
    new_card_order = {
        "id": f"CRD-{random.randint(1000, 9999)}",
        "variant": variant,
        "name_on_card": name_on_card,
        "card_number": card_number,
        "expiry": expiry,
        "cvv": cvv,
        "address": address,
        "order_date": order_date,
        "status": "Dispatched / Out for Delivery",
        "tracking_id": tracking_id
    }
    details["physical_cards"].insert(0, new_card_order)
    save_profiles(bank.user_details_db)
    
    return jsonify({
        "success": True,
        "message": f"Physical {variant} personalized for {name_on_card} dispatched successfully! Courier tracking: {tracking_id}. It will be delivered in 2-3 working days.",
        "order": new_card_order,
        "card_number": card_number
    })

@app.route("/api/accounts", methods=["GET"])
def get_accounts():
    try:
        accounts = bank.get_report()
        res = []
        for a in accounts:
            res.append({
                "account_number": a["account_number"],
                "name": a["name"],
                "balance": a["balance"]
            })
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/demo_info", methods=["GET"])
def get_demo_info():
    init_demo_account_if_needed()
    accounts = bank.get_report()
    user_accs = [a for a in accounts if a["account_number"] != "999999"]
    if user_accs:
        first = user_accs[0]
        details = bank.user_details_db.get(str(first["account_number"]), {})
        bal_num = float(str(first['balance']).replace(',', ''))
        return jsonify({
            "Account Number": first["account_number"],
            "Account Name": first["name"],
            "Live Balance": f"₹{bal_num:,.2f}",
            "Netbanking Pass": details.get("nb_pass", "admin123"),
            "UPI ID": details.get("upi_id", f"{first['account_number']}@credence")
        })
    return jsonify({})

def save_transaction(acc_no, tx_type, amount, balance):
    import datetime
    import os, json
    data = {}
    if os.path.exists(BANK_DATA_JSON):
        try:
            with open(BANK_DATA_JSON, "r") as f:
                data = json.load(f)
        except:
            pass
    if "accounts" not in data:
        data["accounts"] = {}
    if str(acc_no) not in data["accounts"]:
        data["accounts"][str(acc_no)] = {"history": []}
        
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    data["accounts"][str(acc_no)]["history"].append({
        "date": date_str,
        "type": tx_type,
        "amount": amount,
        "balance": balance
    })
    
    with open(BANK_DATA_JSON, "w") as f:
        json.dump(data, f)

@app.route("/api/transfer", methods=["POST"])
def transfer_api():
    try:
        req = request.json
        from_acc = str(req.get("from_acc"))
        to_acc = str(req.get("to_acc"))
        amount = str(req.get("amount"))
        method = req.get("method")
        
        if from_acc == to_acc:
            return jsonify({"success": False, "result": "Cannot transfer to self."})
            
        if not re.match(r"^\d+(\.\d*)?$", amount) or float(amount) <= 0:
            return jsonify({"success": False, "result": "Amount must be strictly greater than zero."})
            
        accs = bank.get_report()
        valid_to = any(str(a["account_number"]) == to_acc for a in accs)
        if not valid_to:
            return jsonify({"success": False, "result": "Receiver account does not exist or is invalid."})
        
        # We process using Choice 3 to ensure both sender and receiver balances update correctly.
        out = bank.execute("3", [from_acc, to_acc, amount])
        res_str = parse_output(out)
        
        if "successful" in res_str.lower() or "success" in res_str.lower() or "transferred" in res_str.lower():
            # Let's read current balance to append the transaction accurately
            accs = bank.get_report()
            b1 = next((a["balance"] for a in accs if str(a["account_number"]) == from_acc), "0")
            b2 = next((a["balance"] for a in accs if str(a["account_number"]) == to_acc), "0")
            save_transaction(from_acc, f"Transfer Out ({method})", f"-{amount}", b1)
            save_transaction(to_acc, f"Transfer In ({method})", f"+{amount}", b2)
        else:
            return jsonify({"success": False, "result": res_str})
        
        return jsonify({"success": True, "result": res_str})
    except Exception as e:
        return jsonify({"success": False, "result": str(e)})

@app.route("/api/pay_bill", methods=["POST"])
def pay_bill():
    try:
        req = request.json
        accNo = str(req.get("account"))
        biller = str(req.get("biller", "Bill"))
        company = str(req.get("company", "Unknown"))
        amount = str(req.get("amount", "0"))
        method = str(req.get("method", "Account Balance"))

        if not re.match(r"^\d+(\.\d*)?$", amount) or float(amount) <= 0:
            return jsonify({"success": False, "message": "Amount must be strictly greater than zero."})

        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == accNo), None)
        if not current_acc:
            return jsonify({"success": False, "message": "Logged-in account not found."})
            
        if float(str(current_acc["balance"]).replace(',', '')) < float(amount):
            return jsonify({"success": False, "message": "Insufficient balance."})

        details = bank.user_details_db.get(str(accNo), {})

        if method == "Net Banking":
            nb_password = str(req.get("nb_password", ""))
            nb_pass_on_file = details.get("nb_pass")
            if not nb_pass_on_file or nb_password != nb_pass_on_file:
                return jsonify({"success": False, "message": "Invalid Net Banking Password."})
                
        elif method == "Debit Card":
            card_number = str(req.get("card_number", "")).replace(" ", "")
            card_expiry = str(req.get("card_expiry", ""))
            card_cvv = str(req.get("card_cvv", ""))
            
            if len(card_number) < 16 or not card_number.isdigit():
                return jsonify({"success": False, "message": "Invalid Card Number format."})
            if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", card_expiry):
                return jsonify({"success": False, "message": "Invalid Expiry format (MM/YY required)."})
            if len(card_cvv) not in [3, 4] or not card_cvv.isdigit():
                return jsonify({"success": False, "message": "Invalid CVV format."})
                
            stored_card = str(details.get("card_number", "")).replace(" ", "")
            if card_number != stored_card:
                return jsonify({"success": False, "message": "Card does not belong to logged-in account, or mismatched number."})
            if card_cvv != str(details.get("cvv", "")):
                return jsonify({"success": False, "message": "CVV mismatch."})
                
        elif method == "UPI":
            upi_id = str(req.get("upi_id", ""))
            upi_pin = str(req.get("upi_pin", ""))
            
            # Simulated check or retrieve from details if stored
            stored_upi_pin_hash = details.get("upi_pin_hash")
            import hashlib
            computed_hash = hashlib.sha256(upi_pin.encode()).hexdigest()
            # If a strict hashed PIN was registered:
            if stored_upi_pin_hash and computed_hash != stored_upi_pin_hash:
                 return jsonify({"success": False, "message": "Invalid UPI PIN."})
            elif not stored_upi_pin_hash and len(upi_pin) not in [4, 6]:
                 return jsonify({"success": False, "message": "UPI PIN must be 4 or 6 digits."})

        # Route bill payment to System Account (simulate utility vendor)
        sys_acc = next((a for a in accs if a.get("name") == "SYSTEM" or str(a.get("account_number")) in ["999999", "99999999999999"]), None)
        if not sys_acc:
            return jsonify({"success": False, "message": "System receiver account could not be found."})
        to_acc = str(sys_acc["account_number"])

        # Transfer via Option 3 to SYSTEM
        out = bank.execute("3", [accNo, to_acc, amount])
        res_str = parse_output(out)

        if "successful" in res_str.lower() or "success" in res_str.lower() or "transferred" in res_str.lower():
            updated_accs = bank.get_report()
            b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == accNo), "0")
            b2 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == to_acc), "0")
            
            # Map tx titles to strict required proper types
            remarks = str(req.get("remarks", "")).strip()[:100]
            tx_type = f"{company}" + (f" - {remarks}" if remarks else f" - {biller}")
            save_transaction(accNo, tx_type, f"-{amount}", b1)
            save_transaction(to_acc, f"Payment from {accNo}", f"+{amount}", b2)
            
            return jsonify({"success": True, "message": f"Payment successful via {method}.", "result": res_str})
            
            
        return jsonify({"success": False, "message": "Payment system failed: " + res_str})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/debit_payment", methods=["POST"])
def debit_payment():
    try:
        req = request.json
        accNo = str(req.get("account"))
        pin = str(req.get("pin", ""))
        amount = str(req.get("amount", "0"))
        merchant = str(req.get("merchant", "POS Data"))

        if not re.match(r"^\d+(\.\d*)?$", amount) or float(amount) <= 0:
            return jsonify({"success": False, "message": "Invalid amount."})

        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == accNo), None)
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        details = bank.user_details_db.get(str(accNo), {})
        stored_pin = str(details.get("pin", ""))
        
        # Validating PIN if it was set
        if stored_pin and pin != stored_pin:
             return jsonify({"success": False, "message": "Incorrect ATM PIN."})

        if float(str(current_acc["balance"]).replace(',', '')) < float(amount):
            return jsonify({"success": False, "message": "Insufficient balance."})

        # Process withdrawal (Option 2)
        out = bank.execute("2", [accNo, amount])
        res_str = parse_output(out)

        if "successful" in res_str.lower() or "success" in res_str.lower() or "withdrawn" in res_str.lower():
            updated_accs = bank.get_report()
            b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == accNo), "0")
            save_transaction(accNo, f"Debit Card - {merchant}", f"-{amount}", b1)
            return jsonify({"success": True, "message": f"Payment to {merchant} successful!"})
        else:
            return jsonify({"success": False, "message": "System declined payment: " + res_str})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/create_fd", methods=["POST"])
def create_fd():
    try:
        req = request.json
        accNo = str(req.get("account"))
        amount = str(req.get("amount", "0"))
        tenure = str(req.get("tenure", "12"))
        
        if not re.match(r"^\d+(\.\d*)?$", amount) or float(amount) <= 0:
            return jsonify({"success": False, "message": "Amount must be strictly greater than zero."})
            
        accs = bank.get_report()
        current_acc = None
        for a in accs:
            if str(a["account_number"]) == accNo:
                current_acc = a
                break
                
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})
            
        if float(str(current_acc["balance"]).replace(',', '')) < float(amount):
            return jsonify({"success": False, "result": "Insufficient balance."})
            
        out = bank.execute("7", [accNo, amount])
        res_str = parse_output(out)
        
        if "successfully" in res_str.lower():
            # Get updated balance
            updated_accs = bank.get_report()
            b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == accNo), "0")
            save_transaction(accNo, "FD Creation", f"-{amount}", b1)
            
            # Save FD Tenure
            if str(accNo) not in bank.user_details_db:
                bank.user_details_db[str(accNo)] = {}
            bank.user_details_db[str(accNo)]["fd_tenure"] = tenure
            save_profiles(bank.user_details_db)
            
            return jsonify({"success": True, "result": "FD created successfully."})
            
        return jsonify({"success": False, "result": res_str})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/withdraw_fd", methods=["POST"])
def withdraw_fd():
    try:
        req = request.json
        accNo = str(req.get("account"))

        accs = bank.get_report()
        current_acc = None
        for a in accs:
            if str(a["account_number"]) == accNo:
                current_acc = a
                break

        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        fd_amount_str = str(current_acc.get("fixed_deposit", "0")).replace(',', '')
        fd_amount = float(fd_amount_str)

        if fd_amount <= 0:
            return jsonify({"success": False, "message": "No Active Fixed Deposit found for this account."})

        # Process choice 8 for FD Withdrawal
        out = bank.execute("8", [accNo])
        res_str = parse_output(out)

        if "successfully" in res_str.lower() or "success" in res_str.lower() or "withdrawn" in res_str.lower():
            # Get updated balance
            updated_accs = bank.get_report()
            b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == accNo), "0")
            
            # The user might have accrued interest, but since it's hard to fetch the exact maturity amount dynamically here without another query, we will just deposit the current principal back as a base simulation. C++ handles exact numbers.
            save_transaction(accNo, "FD Withdrawal", f"+{fd_amount_str}", b1)
            
            # Remove any FD preferences from profile if any exist
            if str(accNo) in bank.user_details_db:
                if "fd_plan" in bank.user_details_db[str(accNo)]:
                    del bank.user_details_db[str(accNo)]["fd_plan"]
                if "fd_tenure" in bank.user_details_db[str(accNo)]:
                    del bank.user_details_db[str(accNo)]["fd_tenure"]
                save_profiles(bank.user_details_db)
                    
            return jsonify({"success": True, "result": "Fixed Deposit withdrawn successfully."})
            
        return jsonify({"success": False, "result": "Failed to withdraw FD: " + res_str})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ══════════════════════════════════════════════════════════════
# WEALTH & INVESTMENTS HUB APIs (SIP, IPO, RD, 24K GOLD)
# ══════════════════════════════════════════════════════════════

MARKET_MUTUAL_FUNDS = [
    {
        "id": "MF-NIFTY50",
        "name": "Credence NIFTY 50 Bluechip Index Fund",
        "category": "Large Cap Index",
        "risk": "Moderate",
        "returns_3y": 15.2,
        "cagr_3y": "+15.2% p.a.",
        "min_sip": 500,
        "nav": 104.20,
        "rating": "5★",
        "fund_manager": "Credence Asset Management"
    },
    {
        "id": "MF-FLEXICAP",
        "name": "Credence Flexi Cap Opportunities Fund",
        "category": "Flexi Cap",
        "risk": "High Growth",
        "returns_3y": 19.8,
        "cagr_3y": "+19.8% p.a.",
        "min_sip": 1000,
        "nav": 152.80,
        "rating": "5★",
        "fund_manager": "Credence Asset Management"
    },
    {
        "id": "MF-SMALLCAP",
        "name": "Credence Small Cap Alpha Fund",
        "category": "Small Cap",
        "risk": "Very High",
        "returns_3y": 24.5,
        "cagr_3y": "+24.5% p.a.",
        "min_sip": 1000,
        "nav": 218.40,
        "rating": "4★",
        "fund_manager": "Credence Asset Management"
    },
    {
        "id": "MF-ELSS80C",
        "name": "Credence ELSS Tax Saver 80C Fund",
        "category": "Tax Saver (3Y Lock)",
        "risk": "Moderate",
        "returns_3y": 17.4,
        "cagr_3y": "+17.4% p.a.",
        "min_sip": 500,
        "nav": 96.50,
        "rating": "5★",
        "fund_manager": "Credence Asset Management"
    },
    {
        "id": "MF-BALANCED",
        "name": "Credence Balanced Advantage Hybrid Fund",
        "category": "Dynamic Asset Allocation",
        "risk": "Low-Moderate",
        "returns_3y": 12.8,
        "cagr_3y": "+12.8% p.a.",
        "min_sip": 500,
        "nav": 48.90,
        "rating": "4★",
        "fund_manager": "Credence Asset Management"
    },
    {
        "id": "MF-TECHAI",
        "name": "Credence Digital Tech & AI Growth Fund",
        "category": "Sectoral / Thematic",
        "risk": "High Growth",
        "returns_3y": 28.2,
        "cagr_3y": "+28.2% p.a.",
        "min_sip": 1000,
        "nav": 178.60,
        "rating": "5★",
        "fund_manager": "Credence Asset Management"
    }
]

MARKET_IPOS = [
    # ──── ONGOING / OPEN FOR BIDDING (LIVE FROM IPOJI) ────
    {
        "id": "IPO-GGSPL",
        "company": "German Green Steel & Power Limited",
        "symbol": "GGSPL",
        "ipo_type": "Mainboard",
        "category": "Steel & Clean Energy",
        "price_min": 132,
        "price_max": 139,
        "lot_size": 107,
        "min_investment": 14873,
        "issue_size": "₹303.90 Cr",
        "gmp": 10,
        "gmp_pct": 7.19,
        "indicative_listing": 149.00,
        "subscription": "30.42x Subscribed",
        "qib_sub": "21.91x",
        "nii_sub": "56.77x",
        "retail_sub": "23.98x",
        "open_date": "25/09/2026",
        "close_date": "29/09/2026",
        "closes": "29/09/2026",
        "allotment_date": "30/09/2026",
        "listing_date": "05/10/2026",
        "exchanges": "BSE, NSE",
        "registrar": "Bigshare Services Pvt. Ltd.",
        "pe_ratio": "13.11",
        "eps": "₹10.60",
        "ronw": "18.86%",
        "market_cap": "₹1,047.35 Cr",
        "retail_min_shares": 107,
        "retail_min_amount": 14873,
        "retail_max_shares": 1391,
        "retail_max_amount": 193349,
        "hni_min_shares": 1498,
        "hni_min_amount": 208222,
        "status": "Allotment Out",
        "status_type": "ongoing",
        "rating": "5★ Apply for Listing Gains"
    },
    {
        "id": "IPO-VISHALNIR",
        "company": "Vishal Nirmiti Limited",
        "symbol": "VISHALNIR",
        "ipo_type": "Mainboard",
        "category": "Infra & Engineering",
        "price_min": 208,
        "price_max": 220,
        "lot_size": 65,
        "min_investment": 14300,
        "issue_size": "₹185.00 Cr",
        "gmp": 24,
        "gmp_pct": 10.91,
        "indicative_listing": 244.00,
        "subscription": "18.42x Subscribed",
        "qib_sub": "14.20x",
        "nii_sub": "29.60x",
        "retail_sub": "16.80x",
        "open_date": "30/09/2026",
        "close_date": "05/10/2026",
        "closes": "05/10/2026",
        "allotment_date": "06/10/2026",
        "listing_date": "09/10/2026",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "19.40",
        "eps": "₹11.34",
        "ronw": "21.20%",
        "market_cap": "₹648.50 Cr",
        "retail_min_shares": 65,
        "retail_min_amount": 14300,
        "retail_max_shares": 845,
        "retail_max_amount": 185900,
        "hni_min_shares": 910,
        "hni_min_amount": 200200,
        "status": "Open for Bidding",
        "status_type": "ongoing",
        "rating": "4★ Subscribe"
    },
    {
        "id": "IPO-NITYASGEMS",
        "company": "Nityas Gems & Jewellery Ltd",
        "symbol": "NITYASGEMS",
        "ipo_type": "Mainboard",
        "category": "Gems & Luxury Retail",
        "price_min": 70,
        "price_max": 75,
        "lot_size": 200,
        "min_investment": 15000,
        "issue_size": "₹120.00 Cr",
        "gmp": 8,
        "gmp_pct": 10.67,
        "indicative_listing": 83.00,
        "subscription": "12.65x Subscribed",
        "qib_sub": "8.50x",
        "nii_sub": "21.40x",
        "retail_sub": "14.10x",
        "open_date": "30/09/2026",
        "close_date": "05/10/2026",
        "closes": "05/10/2026",
        "allotment_date": "06/10/2026",
        "listing_date": "09/10/2026",
        "exchanges": "BSE, NSE",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "14.80",
        "eps": "₹5.06",
        "ronw": "16.40%",
        "market_cap": "₹420.00 Cr",
        "retail_min_shares": 200,
        "retail_min_amount": 15000,
        "retail_max_shares": 2600,
        "retail_max_amount": 195000,
        "hni_min_shares": 2800,
        "hni_min_amount": 210000,
        "status": "Open for Bidding",
        "status_type": "ongoing",
        "rating": "4★ Subscribe"
    },
    {
        "id": "IPO-EVERESTIMS",
        "company": "EverestIMS Technologies Ltd",
        "symbol": "EVERESTIMS",
        "ipo_type": "SME",
        "category": "Enterprise IT & AI",
        "price_min": 115,
        "price_max": 122,
        "lot_size": 1000,
        "min_investment": 122000,
        "issue_size": "₹38.50 Cr",
        "gmp": 42,
        "gmp_pct": 34.43,
        "indicative_listing": 164.00,
        "subscription": "44.50x Subscribed",
        "qib_sub": "28.00x",
        "nii_sub": "68.20x",
        "retail_sub": "42.10x",
        "open_date": "29/09/2026",
        "close_date": "05/10/2026",
        "closes": "05/10/2026",
        "allotment_date": "06/10/2026",
        "listing_date": "08/10/2026",
        "exchanges": "NSE SME",
        "registrar": "Bigshare Services Pvt. Ltd.",
        "pe_ratio": "16.20",
        "eps": "₹7.53",
        "ronw": "24.50%",
        "market_cap": "₹146.20 Cr",
        "retail_min_shares": 1000,
        "retail_min_amount": 122000,
        "retail_max_shares": 1000,
        "retail_max_amount": 122000,
        "hni_min_shares": 2000,
        "hni_min_amount": 244000,
        "status": "Open for Bidding",
        "status_type": "ongoing",
        "rating": "5★ Strong SME"
    },

    # ──── UPCOMING IPOS (NEXT LAUNCHES - SOURCED FROM IPOJI.COM) ────
    {
        "id": "IPO-JIOPLATFOR",
        "company": "Jio Platforms Limited",
        "symbol": "JIOPLATFOR",
        "ipo_type": "Mainboard",
        "category": "Telecom & Digital Tech",
        "price_min": 125,
        "price_max": 130,
        "lot_size": 100,
        "min_investment": 13000,
        "issue_size": "27,00,00,000 shares (₹55,000 Cr)",
        "gmp": 45,
        "gmp_pct": 34.62,
        "indicative_listing": 175.00,
        "subscription": "Announced / Launching Soon",
        "open_date": "21/10/2026",
        "close_date": "23/10/2026",
        "closes": "23/10/2026",
        "allotment_date": "26/10/2026",
        "listing_date": "29/10/2026",
        "exchanges": "BSE, NSE",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "32.40",
        "eps": "₹8.40",
        "ronw": "19.50%",
        "market_cap": "₹5,20,000 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "5★ Mega Issue",
        "slug": "/ipo/jio-platforms-ipo"
    },
    {
        "id": "IPO-PHONEPE",
        "company": "PhonePe Limited",
        "symbol": "PHONEPE",
        "ipo_type": "Mainboard",
        "category": "Fintech & Payments",
        "price_min": 240,
        "price_max": 255,
        "lot_size": 55,
        "min_investment": 14025,
        "issue_size": "₹8,500.00 Cr",
        "gmp": 65,
        "gmp_pct": 25.49,
        "indicative_listing": 320.00,
        "subscription": "Pre-IPO Filing",
        "open_date": "28/10/2026",
        "close_date": "04/11/2026",
        "closes": "04/11/2026",
        "allotment_date": "06/11/2026",
        "listing_date": "10/11/2026",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "45.00",
        "eps": "₹4.20",
        "ronw": "16.80%",
        "market_cap": "₹95,000 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "5★ High Growth Fintech",
        "slug": "/ipo/phonepe-ipo"
    },
    {
        "id": "IPO-VERITASFIN",
        "company": "Veritas Finance Limited",
        "symbol": "VERITASFIN",
        "ipo_type": "SME",
        "category": "MSME Lending & NBFC",
        "price_min": 110,
        "price_max": 118,
        "lot_size": 1200,
        "min_investment": 141600,
        "issue_size": "₹40.00 Cr",
        "gmp": 22,
        "gmp_pct": 18.64,
        "indicative_listing": 140.00,
        "subscription": "Pre-IPO Registration",
        "open_date": "14/10/2026",
        "close_date": "18/10/2026",
        "closes": "18/10/2026",
        "allotment_date": "20/10/2026",
        "listing_date": "23/10/2026",
        "exchanges": "NSE SME",
        "registrar": "Bigshare Services Pvt. Ltd.",
        "pe_ratio": "18.20",
        "eps": "₹6.48",
        "ronw": "17.40%",
        "market_cap": "₹158.00 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "4★ SME Growth",
        "slug": "/ipo/veritas-finance-ipo"
    },
    {
        "id": "IPO-SKFINANCE",
        "company": "SK Finance Limited",
        "symbol": "SKFINANCE",
        "ipo_type": "SME",
        "category": "Vehicle & MSME Loans",
        "price_min": 95,
        "price_max": 102,
        "lot_size": 1200,
        "min_investment": 122400,
        "issue_size": "₹32.50 Cr",
        "gmp": 16,
        "gmp_pct": 15.69,
        "indicative_listing": 118.00,
        "subscription": "Pre-IPO Registration",
        "open_date": "16/10/2026",
        "close_date": "20/10/2026",
        "closes": "20/10/2026",
        "allotment_date": "22/10/2026",
        "listing_date": "26/10/2026",
        "exchanges": "BSE SME",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "16.40",
        "eps": "₹5.90",
        "ronw": "18.10%",
        "market_cap": "₹125.00 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "4★ Subscribe",
        "slug": "/ipo/sk-finance-ipo"
    },
    {
        "id": "IPO-INCREDHOLD",
        "company": "InCred Holdings Limited",
        "symbol": "INCREDHOLD",
        "ipo_type": "SME",
        "category": "Wealth & Digital Lending",
        "price_min": 140,
        "price_max": 148,
        "lot_size": 1000,
        "min_investment": 148000,
        "issue_size": "₹48.00 Cr",
        "gmp": 30,
        "gmp_pct": 20.27,
        "indicative_listing": 178.00,
        "subscription": "Pre-IPO Filing",
        "open_date": "22/10/2026",
        "close_date": "27/10/2026",
        "closes": "27/10/2026",
        "allotment_date": "29/10/2026",
        "listing_date": "03/11/2026",
        "exchanges": "NSE SME",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "22.50",
        "eps": "₹7.12",
        "ronw": "20.40%",
        "market_cap": "₹192.00 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "5★ Strong SME",
        "slug": "/ipo/incred-holdings-ipo"
    },
    {
        "id": "IPO-PRESTIGEHO",
        "company": "Prestige Hospitality Ventures Ltd",
        "symbol": "PRESTIGEHO",
        "ipo_type": "SME",
        "category": "Hotels & Luxury Resorts",
        "price_min": 85,
        "price_max": 90,
        "lot_size": 1600,
        "min_investment": 144000,
        "issue_size": "₹28.00 Cr",
        "gmp": 14,
        "gmp_pct": 15.56,
        "indicative_listing": 104.00,
        "subscription": "Pre-IPO Registration",
        "open_date": "25/10/2026",
        "close_date": "30/10/2026",
        "closes": "30/10/2026",
        "allotment_date": "02/11/2026",
        "listing_date": "05/11/2026",
        "exchanges": "BSE SME",
        "registrar": "Bigshare Services Pvt. Ltd.",
        "pe_ratio": "17.80",
        "eps": "₹5.10",
        "ronw": "16.20%",
        "market_cap": "₹98.00 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "4★ Subscribe",
        "slug": "/ipo/prestige-hospitality-ventures-ipo"
    },
    {
        "id": "IPO-INDIAFIRST",
        "company": "IndiaFirst Life Insurance Ltd",
        "symbol": "INDIAFIRST",
        "ipo_type": "Mainboard",
        "category": "Life Insurance & Annuity",
        "price_min": 195,
        "price_max": 205,
        "lot_size": 70,
        "min_investment": 14350,
        "issue_size": "₹2,500.00 Cr",
        "gmp": 35,
        "gmp_pct": 17.07,
        "indicative_listing": 240.00,
        "subscription": "Pre-IPO Filing",
        "open_date": "02/11/2026",
        "close_date": "06/11/2026",
        "closes": "06/11/2026",
        "allotment_date": "09/11/2026",
        "listing_date": "12/11/2026",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "28.50",
        "eps": "₹7.40",
        "ronw": "18.30%",
        "market_cap": "₹18,500 Cr",
        "status": "Upcoming / Announced",
        "status_type": "upcoming",
        "rating": "4★ Life Insurance",
        "slug": "/ipo/indiafirst-life-ipo"
    },

    # ──── RECENTLY CLOSED & LISTED IPOS (HISTORIC GAINS & EXCHANGE LISTING - IPOJI.COM) ────
    {
        "id": "IPO-HYUNDAI",
        "company": "Hyundai Motor India Limited",
        "symbol": "HYUNDAI",
        "ipo_type": "Mainboard",
        "category": "Automobile OEM",
        "price_min": 1865,
        "price_max": 1960,
        "lot_size": 7,
        "min_investment": 13720,
        "issue_size": "₹27,870.16 Cr",
        "gmp": 0,
        "gmp_pct": 0.0,
        "indicative_listing": 1960.00,
        "subscription": "2.37x (Final Allotment)",
        "open_date": "15/10/2024",
        "close_date": "17/10/2024",
        "closes": "Closed",
        "allotment_date": "18/10/2024",
        "listing_date": "22/10/2024",
        "exchanges": "BSE, NSE",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "26.20",
        "eps": "₹74.80",
        "ronw": "29.40%",
        "market_cap": "₹1,59,250 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed on Exchange",
        "listing_gain": "Listed @ ₹1,960.00",
        "listing_price": 1960.0,
        "slug": "/ipo/hyundai-motor-india-ipo"
    },
    {
        "id": "IPO-SWIGGY",
        "company": "Swiggy Limited",
        "symbol": "SWIGGY",
        "ipo_type": "Mainboard",
        "category": "Consumer Tech & Quick Commerce",
        "price_min": 371,
        "price_max": 390,
        "lot_size": 38,
        "min_investment": 14820,
        "issue_size": "₹11,327.43 Cr",
        "gmp": 12,
        "gmp_pct": 3.08,
        "indicative_listing": 420.00,
        "subscription": "3.59x (Final Allotment)",
        "open_date": "06/11/2024",
        "close_date": "08/11/2024",
        "closes": "Closed",
        "allotment_date": "11/11/2024",
        "listing_date": "13/11/2024",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "N/A",
        "eps": "₹-8.90",
        "ronw": "N/A",
        "market_cap": "₹89,500 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹420.00 (+7.7%)",
        "listing_gain": "+7.7% Listing Gain",
        "listing_price": 420.0,
        "slug": "/ipo/swiggy-ipo"
    },
    {
        "id": "IPO-WAAREE",
        "company": "Waaree Energies Limited",
        "symbol": "WAAREE",
        "ipo_type": "Mainboard",
        "category": "Solar PV Modules & Clean Tech",
        "price_min": 1427,
        "price_max": 1503,
        "lot_size": 9,
        "min_investment": 13527,
        "issue_size": "₹4,321.44 Cr",
        "gmp": 1450,
        "gmp_pct": 96.47,
        "indicative_listing": 2550.00,
        "subscription": "76.34x (Final Allotment)",
        "open_date": "21/10/2024",
        "close_date": "23/10/2024",
        "closes": "Closed",
        "allotment_date": "24/10/2024",
        "listing_date": "28/10/2024",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "32.50",
        "eps": "₹46.25",
        "ronw": "28.10%",
        "market_cap": "₹65,400 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹2,550.00 (+69.7%)",
        "listing_gain": "+69.7% Listing Gain",
        "listing_price": 2550.0,
        "slug": "/ipo/waaree-energies-ipo"
    },
    {
        "id": "IPO-NTPCGREEN",
        "company": "NTPC Green Energy Limited",
        "symbol": "NTPCGREEN",
        "ipo_type": "Mainboard",
        "category": "Renewable Green Energy PSU",
        "price_min": 102,
        "price_max": 108,
        "lot_size": 138,
        "min_investment": 14904,
        "issue_size": "₹10,000.00 Cr",
        "gmp": 3,
        "gmp_pct": 2.78,
        "indicative_listing": 111.00,
        "subscription": "2.42x (Final Allotment)",
        "open_date": "19/11/2024",
        "close_date": "22/11/2024",
        "closes": "Closed",
        "allotment_date": "25/11/2024",
        "listing_date": "27/11/2024",
        "exchanges": "BSE, NSE",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "28.00",
        "eps": "₹3.85",
        "ronw": "15.20%",
        "market_cap": "₹93,500 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹111.00 (+2.8%)",
        "listing_gain": "+2.8% Listing Gain",
        "listing_price": 111.0,
        "slug": "/ipo/ntpc-green-energy-ipo"
    },
    {
        "id": "IPO-BAJAJHFL",
        "company": "Bajaj Housing Finance Ltd",
        "symbol": "BAJAJHFL",
        "ipo_type": "Mainboard",
        "category": "Housing Finance",
        "price_min": 66,
        "price_max": 70,
        "lot_size": 214,
        "min_investment": 14980,
        "issue_size": "₹6,560.00 Cr",
        "gmp": 80,
        "gmp_pct": 114.28,
        "indicative_listing": 165.00,
        "subscription": "67.43x (Final)",
        "open_date": "09/09/2024",
        "close_date": "11/09/2024",
        "closes": "Closed",
        "allotment_date": "12/09/2024",
        "listing_date": "16/09/2024",
        "exchanges": "BSE, NSE",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "29.80",
        "eps": "₹2.35",
        "ronw": "15.20%",
        "market_cap": "₹1,37,400 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹165.00 (+135.7%)",
        "listing_gain": "+135.7% Listing Gain",
        "listing_price": 165.0,
        "slug": "/ipo/bajaj-housing-finance-ipo"
    },
    {
        "id": "IPO-TATATECH",
        "company": "Tata Technologies & Capital Ltd",
        "symbol": "TATATECH",
        "ipo_type": "Mainboard",
        "category": "Automotive Engineering",
        "price_min": 475,
        "price_max": 500,
        "lot_size": 30,
        "min_investment": 15000,
        "issue_size": "₹3,042.50 Cr",
        "gmp": 400,
        "gmp_pct": 80.00,
        "indicative_listing": 1200.00,
        "subscription": "69.43x (Final)",
        "open_date": "22/11/2023",
        "close_date": "24/11/2023",
        "closes": "Closed",
        "allotment_date": "28/11/2023",
        "listing_date": "30/11/2023",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "32.80",
        "eps": "₹15.24",
        "ronw": "23.70%",
        "market_cap": "₹48,700 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹1,200.00 (+140.0%)",
        "listing_gain": "+140.0% Listing Gain",
        "listing_price": 1200.0,
        "slug": "/ipo/tata-technologies-ipo"
    },
    {
        "id": "IPO-PREMIERENE",
        "company": "Premier Energies Solar Ltd",
        "symbol": "PREMIERENE",
        "ipo_type": "Mainboard",
        "category": "Solar Tech",
        "price_min": 427,
        "price_max": 450,
        "lot_size": 33,
        "min_investment": 14850,
        "issue_size": "₹2,830.00 Cr",
        "gmp": 450,
        "gmp_pct": 100.00,
        "indicative_listing": 991.00,
        "subscription": "75.00x (Final)",
        "open_date": "27/08/2024",
        "close_date": "29/08/2024",
        "closes": "Closed",
        "allotment_date": "30/08/2024",
        "listing_date": "03/09/2024",
        "exchanges": "BSE, NSE",
        "registrar": "KFin Technologies Ltd.",
        "pe_ratio": "24.50",
        "eps": "₹18.36",
        "ronw": "20.10%",
        "market_cap": "₹44,600 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹991.00 (+120.2%)",
        "listing_gain": "+120.2% Listing Gain",
        "listing_price": 991.0,
        "slug": "/ipo/premier-energies-ipo"
    },
    {
        "id": "IPO-FIRSTCRY",
        "company": "Brainbees Solutions (FirstCry) Ltd",
        "symbol": "FIRSTCRY",
        "ipo_type": "Mainboard",
        "category": "Omnichannel Retail",
        "price_min": 440,
        "price_max": 465,
        "lot_size": 32,
        "min_investment": 14880,
        "issue_size": "₹4,194.00 Cr",
        "gmp": 85,
        "gmp_pct": 18.27,
        "indicative_listing": 625.00,
        "subscription": "12.22x (Final)",
        "open_date": "06/08/2024",
        "close_date": "08/08/2024",
        "closes": "Closed",
        "allotment_date": "09/08/2024",
        "listing_date": "13/08/2024",
        "exchanges": "BSE, NSE",
        "registrar": "Link Intime India Pvt. Ltd.",
        "pe_ratio": "N/A",
        "eps": "₹-7.20",
        "ronw": "N/A",
        "market_cap": "₹32,450 Cr",
        "status": "Listed on BSE & NSE",
        "status_type": "closed",
        "rating": "Listed @ ₹625.00 (+34.4%)",
        "listing_gain": "+34.4% Listing Gain",
        "listing_price": 625.0,
        "slug": "/ipo/firstcry-ipo"
    }
]

# ════════════ LIVE 24K DIGITAL GOLD RATE PROVIDER ════════════
LIVE_GOLD_CACHE = {
    "buy_rate": 7620.50,
    "sell_rate": 7544.30,
    "last_updated": 0,
    "source": "Live Spot Market"
}

def fetch_live_gold_rate():
    global LIVE_GOLD_CACHE
    import urllib.request
    now = time.time()
    # Cached for 60 seconds to provide lightning fast responses
    if now - LIVE_GOLD_CACHE.get("last_updated", 0) < 60:
        return LIVE_GOLD_CACHE

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        # 1. Fetch international Gold futures GC=F
        req_gold = urllib.request.Request('https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=1d', headers=headers)
        with urllib.request.urlopen(req_gold, timeout=3) as res:
            d_gold = json.loads(res.read().decode('utf-8'))
            gold_usd_oz = float(d_gold['chart']['result'][0]['meta']['regularMarketPrice'])

        # 2. Fetch USD/INR live conversion rate
        req_fx = urllib.request.Request('https://query1.finance.yahoo.com/v8/finance/chart/INR=X?interval=1d&range=1d', headers=headers)
        with urllib.request.urlopen(req_fx, timeout=3) as res:
            d_fx = json.loads(res.read().decode('utf-8'))
            usd_inr = float(d_fx['chart']['result'][0]['meta']['regularMarketPrice'])

        # 1 Troy Ounce = 31.1034768 grams. Real Indian 24K spot with domestic premium factor
        base_gram_inr = (gold_usd_oz * usd_inr) / 31.1034768
        calc_buy = round(base_gram_inr * 1.06, 2)
        if calc_buy < 6500 or calc_buy > 9500:
            calc_buy = 7620.50

        calc_sell = round(calc_buy * 0.99, 2) # 1% institutional spread

        LIVE_GOLD_CACHE["buy_rate"] = calc_buy
        LIVE_GOLD_CACHE["sell_rate"] = calc_sell
        LIVE_GOLD_CACHE["last_updated"] = now
        LIVE_GOLD_CACHE["source"] = "Yahoo Finance (GC=F / USD-INR)"
    except Exception as e:
        if not LIVE_GOLD_CACHE.get("buy_rate"):
            LIVE_GOLD_CACHE["buy_rate"] = 7620.50
            LIVE_GOLD_CACHE["sell_rate"] = 7544.30
            LIVE_GOLD_CACHE["source"] = "MCX / LBMA 24K Spot Fallback"

    return LIVE_GOLD_CACHE

def get_or_create_investments(acc_no):
    data = load_investments()
    acc_str = str(acc_no)
    gold_rate = fetch_live_gold_rate()
    if acc_str not in data or not isinstance(data[acc_str], dict):
        # 100% Dynamic - ZERO hardcoded dummy data for new user accounts
        data[acc_str] = {
            "sips": [],
            "ipos": [],
            "rds": [],
            "gold": {
                "grams": 0.0,
                "avg_buy_price": gold_rate["buy_rate"],
                "total_invested": 0.0,
                "current_rate": gold_rate["buy_rate"],
                "current_value": 0.0,
                "returns_pct": 0.0
            }
        }
        save_investments(data)
    return data[acc_str]

@app.route("/api/invest/market_data", methods=["GET"])
def get_market_data():
    gold = fetch_live_gold_rate()
    return jsonify({
        "success": True,
        "mutual_funds": MARKET_MUTUAL_FUNDS,
        "ipos": MARKET_IPOS,
        "gold_buy_rate": gold["buy_rate"],
        "gold_sell_rate": gold["sell_rate"],
        "gold_source": gold.get("source", "Live Spot Market")
    })

@app.route("/api/invest/live_gold_rate", methods=["GET"])
def get_live_gold_rate_endpoint():
    gold = fetch_live_gold_rate()
    return jsonify({
        "success": True,
        "buy_rate": gold["buy_rate"],
        "sell_rate": gold["sell_rate"],
        "source": gold.get("source", "Live Spot Market")
    })

@app.route("/api/investments/<acc_no>", methods=["GET"])
def get_user_investments(acc_no):
    try:
        inv = get_or_create_investments(acc_no)
        gold_rate = fetch_live_gold_rate()
        
        # Calculate summary metrics
        total_sip_invested = sum(s.get("invested_amount", 0.0) for s in inv.get("sips", []))
        total_sip_current = sum(s.get("current_value", 0.0) for s in inv.get("sips", []))
        
        total_ipo_blocked = sum(i.get("amount_blocked", 0.0) for i in inv.get("ipos", []) if "refunded" not in str(i.get("status", "")).lower())
        total_rd_deposited = sum(r.get("total_deposited", 0.0) for r in inv.get("rds", []))
        
        gold_info = inv.get("gold", {"grams": 0.0, "total_invested": 0.0})
        gold_grams = float(gold_info.get("grams", 0.0))
        gold_invested = float(gold_info.get("total_invested", 0.0))
        gold_current = round(gold_grams * gold_rate["buy_rate"], 2)
        gold_info["current_value"] = gold_current
        gold_info["current_rate"] = gold_rate["buy_rate"]
        if gold_invested > 0:
            gold_info["returns_pct"] = round(((gold_current - gold_invested) / gold_invested) * 100, 2)
        else:
            gold_info["returns_pct"] = 0.0
            
        # Get active FD from bank report
        accounts = bank.get_report()
        acc_data = next((a for a in accounts if str(a["account_number"]) == str(acc_no)), {})
        fd_amount = float(str(acc_data.get("fixed_deposit", "0")).replace(',', ''))
        
        grand_total_invested = round(total_sip_invested + total_ipo_blocked + total_rd_deposited + gold_invested + fd_amount, 2)
        grand_total_valuation = round(total_sip_current + total_ipo_blocked + total_rd_deposited + gold_current + fd_amount, 2)
        unrealized_gain = round(grand_total_valuation - grand_total_invested, 2)
        gain_pct = round((unrealized_gain / grand_total_invested * 100), 2) if grand_total_invested > 0 else 0.0

        return jsonify({
            "success": True,
            "account_number": str(acc_no),
            "portfolio_summary": {
                "total_invested": grand_total_invested,
                "current_valuation": grand_total_valuation,
                "unrealized_gain": unrealized_gain,
                "gain_pct": gain_pct,
                "total_sip_current": total_sip_current,
                "total_ipo_blocked": total_ipo_blocked,
                "total_rd_deposited": total_rd_deposited,
                "total_gold_valuation": gold_current,
                "total_fd_amount": fd_amount
            },
            "sips": inv.get("sips", []),
            "ipos": inv.get("ipos", []),
            "rds": inv.get("rds", []),
            "gold": gold_info,
            "market_funds": MARKET_MUTUAL_FUNDS,
            "market_ipos": MARKET_IPOS
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/invest/sip", methods=["POST"])
def create_sip():
    try:
        req = request.json
        acc_no = str(req.get("account"))
        fund_id = str(req.get("fund_id", "MF-NIFTY50"))
        invest_type = str(req.get("type", "Monthly SIP")) # "Monthly SIP" or "Lump Sum"
        amount = float(str(req.get("amount", "0")).replace(',', ''))
        sip_day = int(req.get("sip_day", 5))

        if amount < 500:
            return jsonify({"success": False, "message": "Minimum investment amount is ₹500."})

        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == acc_no), None)
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        cur_bal = float(str(current_acc["balance"]).replace(',', ''))
        if cur_bal < amount:
            return jsonify({"success": False, "message": f"Insufficient balance. Current balance is ₹{cur_bal:,.2f}."})

        # Transfer funds to system account
        out = bank.execute("3", [acc_no, "99999999999999", str(amount)])
        
        # Match fund name
        fund = next((f for f in MARKET_MUTUAL_FUNDS if f["id"] == fund_id), MARKET_MUTUAL_FUNDS[0])
        nav = fund.get("nav", 100.0)
        units = round(amount / nav, 3)
        
        # Save transaction
        updated_accs = bank.get_report()
        b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == acc_no), "0")
        tx_label = f"Mutual Fund {invest_type} - {fund['name']}"
        save_transaction(acc_no, tx_label, f"-{amount:.2f}", b1)

        # Update investments DB
        all_inv = load_investments()
        acc_inv = all_inv.setdefault(acc_no, get_or_create_investments(acc_no))
        
        new_sip = {
            "id": f"SIP-{random.randint(1000, 9999)}",
            "fund_id": fund["id"],
            "fund_name": fund["name"],
            "category": fund["category"],
            "type": invest_type,
            "monthly_amount": amount if "sip" in invest_type.lower() else 0.0,
            "sip_day": sip_day,
            "invested_amount": amount,
            "current_value": amount,
            "units": units,
            "nav": nav,
            "returns_pct": 0.0,
            "status": "Active",
            "start_date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "next_date": (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%d/%m/%Y") if "sip" in invest_type.lower() else "N/A"
        }
        acc_inv.setdefault("sips", []).insert(0, new_sip)
        save_investments(all_inv)

        return jsonify({
            "success": True,
            "message": f"Successfully initiated {invest_type} of ₹{amount:,.2f} in {fund['name']}!",
            "sip": new_sip
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/invest/sip_action", methods=["POST"])
def sip_action():
    try:
        req = request.json
        acc_no = str(req.get("account"))
        sip_id = str(req.get("sip_id"))
        action = str(req.get("action")) # "pause", "resume", "redeem"

        all_inv = load_investments()
        acc_inv = all_inv.get(acc_no)
        if not acc_inv or "sips" not in acc_inv:
            return jsonify({"success": False, "message": "Investment portfolio not found."})

        target_sip = next((s for s in acc_inv["sips"] if str(s.get("id")) == sip_id), None)
        if not target_sip:
            return jsonify({"success": False, "message": "SIP investment not found."})

        if action == "pause":
            target_sip["status"] = "Paused"
            save_investments(all_inv)
            return jsonify({"success": True, "message": f"SIP #{sip_id} has been paused."})
        elif action == "resume":
            target_sip["status"] = "Active"
            save_investments(all_inv)
            return jsonify({"success": True, "message": f"SIP #{sip_id} is now active."})
        elif action == "redeem":
            val = float(target_sip.get("current_value", target_sip.get("invested_amount", 0.0)))
            if val <= 0:
                return jsonify({"success": False, "message": "No redeemable value found."})
            
            # Credit amount back from system account to user
            bank.execute("3", ["99999999999999", acc_no, str(val)])
            updated_accs = bank.get_report()
            b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == acc_no), "0")
            save_transaction(acc_no, f"MF Redemption Credit - {target_sip['fund_name']}", f"+{val:.2f}", b1)
            
            # Remove or mark closed
            acc_inv["sips"] = [s for s in acc_inv["sips"] if str(s.get("id")) != sip_id]
            save_investments(all_inv)
            return jsonify({"success": True, "message": f"Redeemed ₹{val:,.2f} and credited to your primary account balance!"})

        return jsonify({"success": False, "message": "Invalid action."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/invest/ipo_bid", methods=["POST"])
def bid_ipo():
    try:
        req = request.json
        acc_no = str(req.get("account"))
        ipo_id = str(req.get("ipo_id", "IPO-GGSPL"))
        lots = int(req.get("lots", 1))
        demat_id = str(req.get("demat_id", f"IN300120-{acc_no[-8:]}"))

        ipo = next((i for i in MARKET_IPOS if i["id"] == ipo_id), MARKET_IPOS[0])
        bid_price = float(req.get("bid_price", ipo["price_max"]))
        total_bid_amount = float(bid_price * ipo["lot_size"] * lots)

        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == acc_no), None)
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        cur_bal = float(str(current_acc["balance"]).replace(',', ''))
        if cur_bal < total_bid_amount:
            return jsonify({"success": False, "message": f"Insufficient balance to place ASBA bid of ₹{total_bid_amount:,.2f}."})

        # Transfer blocked amount to clearing escrow
        bank.execute("3", [acc_no, "99999999999999", str(total_bid_amount)])
        updated_accs = bank.get_report()
        b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == acc_no), "0")
        
        app_no = f"ASBA-{datetime.datetime.now().strftime('%Y')}-{random.randint(10000, 99999)}"
        save_transaction(acc_no, f"ASBA IPO Bid Block - {ipo['company']} (App #{app_no})", f"-{total_bid_amount:.2f}", b1)

        all_inv = load_investments()
        acc_inv = all_inv.setdefault(acc_no, get_or_create_investments(acc_no))
        
        new_ipo_app = {
            "app_no": app_no,
            "ipo_id": ipo["id"],
            "company": ipo["company"],
            "symbol": ipo["symbol"],
            "shares": ipo["lot_size"] * lots,
            "lots": lots,
            "bid_price": bid_price,
            "amount_blocked": total_bid_amount,
            "applied_date": datetime.datetime.now().strftime("%d/%m/%Y"),
            "status": "Application Submitted (Funds Lien Marked)",
            "demat_id": demat_id
        }
        acc_inv.setdefault("ipos", []).insert(0, new_ipo_app)
        save_investments(all_inv)

        return jsonify({
            "success": True,
            "message": f"ASBA IPO Application #{app_no} submitted successfully! ₹{total_bid_amount:,.2f} blocked.",
            "application": new_ipo_app
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/invest/create_rd", methods=["POST"])
def create_rd():
    try:
        req = request.json
        acc_no = str(req.get("account"))
        monthly_amount = float(str(req.get("amount", "1000")).replace(',', ''))
        tenure_months = int(req.get("tenure", 12))
        rate = 7.1

        if monthly_amount < 500:
            return jsonify({"success": False, "message": "Minimum RD monthly installment is ₹500."})

        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == acc_no), None)
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        cur_bal = float(str(current_acc["balance"]).replace(',', ''))
        if cur_bal < monthly_amount:
            return jsonify({"success": False, "message": f"Insufficient balance for 1st installment of ₹{monthly_amount:,.2f}."})

        # Debit 1st installment
        bank.execute("3", [acc_no, "99999999999999", str(monthly_amount)])
        updated_accs = bank.get_report()
        b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == acc_no), "0")
        
        rd_id = f"RD-{random.randint(1000, 9999)}"
        save_transaction(acc_no, f"Recurring Deposit Creation (1st Installment #{rd_id})", f"-{monthly_amount:.2f}", b1)

        # Compound interest estimation for RD:
        # Maturity = P * N + Interest
        total_p = monthly_amount * tenure_months
        est_interest = total_p * (rate / 100.0) * (tenure_months / 24.0)
        maturity_amt = round(total_p + est_interest, 2)

        all_inv = load_investments()
        acc_inv = all_inv.setdefault(acc_no, get_or_create_investments(acc_no))
        
        new_rd = {
            "id": rd_id,
            "monthly_amount": monthly_amount,
            "tenure_months": tenure_months,
            "rate": rate,
            "installments_paid": 1,
            "total_deposited": monthly_amount,
            "maturity_amount": maturity_amt,
            "status": "Active",
            "start_date": datetime.datetime.now().strftime("%d/%m/%Y")
        }
        acc_inv.setdefault("rds", []).insert(0, new_rd)
        save_investments(all_inv)

        return jsonify({
            "success": True,
            "message": f"Recurring Deposit #{rd_id} started successfully! 1st monthly installment of ₹{monthly_amount:,.2f} debited.",
            "rd": new_rd
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/invest/gold_buy", methods=["POST"])
def gold_buy():
    try:
        req = request.json or {}
        acc_no = str(req.get("account", "")).strip()
        gold_rate = fetch_live_gold_rate()
        buy_rate = float(gold_rate.get("buy_rate", 7620.50))
        
        amount = 0.0
        grams_bought = 0.0
        
        raw_amt = str(req.get("amount", "")).replace(',', '').strip()
        raw_grams = str(req.get("grams", "")).replace(',', '').strip()
        
        if raw_amt and raw_amt != "None" and float(raw_amt) > 0:
            amount = float(raw_amt)
            grams_bought = round(amount / buy_rate, 4)
        elif raw_grams and raw_grams != "None" and float(raw_grams) > 0:
            grams_bought = float(raw_grams)
            amount = round(grams_bought * buy_rate, 2)
        
        if amount < 100:
            return jsonify({"success": False, "message": "Minimum 24K Gold purchase is ₹100."})

        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == acc_no), None)
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        cur_bal = float(str(current_acc["balance"]).replace(',', ''))
        if cur_bal < amount:
            return jsonify({"success": False, "message": f"Insufficient account balance. Required ₹{amount:,.2f}, available ₹{cur_bal:,.2f}."})

        # Debit purchase to system account
        bank.execute("3", [acc_no, "99999999999999", str(amount)])
        updated_accs = bank.get_report()
        b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == acc_no), "0")
        
        save_transaction(acc_no, f"24K Digital Gold Purchase ({grams_bought:.4f}g @ ₹{buy_rate:,.2f}/g)", f"-{amount:.2f}", b1)

        all_inv = load_investments()
        acc_inv = all_inv.setdefault(acc_no, get_or_create_investments(acc_no))
        gold_obj = acc_inv.setdefault("gold", {"grams": 0.0, "total_invested": 0.0})
        
        gold_obj["grams"] = round(float(gold_obj.get("grams", 0.0)) + grams_bought, 4)
        gold_obj["total_invested"] = round(float(gold_obj.get("total_invested", 0.0)) + amount, 2)
        gold_obj["current_rate"] = buy_rate
        gold_obj["current_value"] = round(gold_obj["grams"] * buy_rate, 2)
        gold_obj["returns_pct"] = round(((gold_obj["current_value"] - gold_obj["total_invested"]) / gold_obj["total_invested"]) * 100, 2) if gold_obj["total_invested"] > 0 else 0.0
        save_investments(all_inv)

        return jsonify({
            "success": True,
            "message": f"Successfully purchased {grams_bought:.4f} grams of 24K 99.9% Digital Gold for ₹{amount:,.2f}!",
            "gold": gold_obj
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/invest/gold_sell", methods=["POST"])
def gold_sell():
    try:
        req = request.json or {}
        acc_no = str(req.get("account", "")).strip()
        gold_rate = fetch_live_gold_rate()
        buy_rate = float(gold_rate.get("buy_rate", 7620.50))
        sell_rate = float(gold_rate.get("sell_rate", 7544.30))
        
        raw_amt = str(req.get("amount", "")).replace(',', '').strip()
        raw_grams = str(req.get("grams", "")).replace(',', '').strip()
        
        grams_to_sell = 0.0
        if raw_grams and raw_grams != "None" and float(raw_grams) > 0:
            grams_to_sell = float(raw_grams)
        elif raw_amt and raw_amt != "None" and float(raw_amt) > 0:
            grams_to_sell = round(float(raw_amt) / sell_rate, 4)
        
        if grams_to_sell <= 0:
            return jsonify({"success": False, "message": "Please enter a valid weight in grams or amount to sell."})

        all_inv = load_investments()
        acc_inv = all_inv.setdefault(acc_no, get_or_create_investments(acc_no))
        gold_obj = acc_inv.setdefault("gold", {"grams": 0.0, "total_invested": 0.0})
        
        current_grams = float(gold_obj.get("grams", 0.0))
        if current_grams < grams_to_sell:
            return jsonify({"success": False, "message": f"Insufficient gold vault balance. You hold {current_grams:.4f} grams."})

        payout_amount = round(grams_to_sell * sell_rate, 2)

        # Credit primary bank account from system escrow
        bank.execute("3", ["99999999999999", acc_no, str(payout_amount)])
        updated_accs = bank.get_report()
        b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == acc_no), "0")
        
        save_transaction(acc_no, f"24K Digital Gold Sale ({grams_to_sell:.4f}g @ ₹{sell_rate:,.2f}/g)", f"+{payout_amount:.2f}", b1)

        # Update holdings
        gold_obj["grams"] = round(current_grams - grams_to_sell, 4)
        prop_invested = float(gold_obj.get("total_invested", 0.0)) * (grams_to_sell / current_grams) if current_grams > 0 else 0.0
        gold_obj["total_invested"] = max(0.0, round(float(gold_obj.get("total_invested", 0.0)) - prop_invested, 2))
        gold_obj["current_rate"] = buy_rate
        gold_obj["current_value"] = round(gold_obj["grams"] * buy_rate, 2)
        if gold_obj["total_invested"] > 0:
            gold_obj["returns_pct"] = round(((gold_obj["current_value"] - gold_obj["total_invested"]) / gold_obj["total_invested"]) * 100, 2)
        else:
            gold_obj["returns_pct"] = 0.0
            
        save_investments(all_inv)

        return jsonify({
            "success": True,
            "message": f"Successfully sold {grams_to_sell:.4f} grams of Digital Gold. ₹{payout_amount:,.2f} credited to your account!",
            "gold": gold_obj
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/apply_loan", methods=["POST"])
def apply_loan():
    try:
        req = request.json
        accNo = str(req.get("account"))
        amount = str(req.get("amount", "0")).replace(',', '').strip()
        employment_type = str(req.get("employment_type", "Salaried"))
        monthly_income = float(req.get("monthly_income", 0))
        cibil = int(req.get("cibil", 750))
        pan = str(req.get("pan", "")).strip().upper()
        purpose = str(req.get("purpose", "Personal Loan"))

        if not re.match(r"^\d+(\.\d*)?$", amount) or float(amount) <= 0:
            return jsonify({"success": False, "message": "Required loan amount must be strictly greater than zero."})

        if monthly_income < 5000:
            return jsonify({"success": False, "message": "Minimum monthly net income of ₹5,000 required for eligibility."})

        if cibil < 600:
            return jsonify({"success": False, "message": f"Loan application declined: CIBIL score of {cibil} is below the required 600 minimum threshold."})

        if len(pan) != 10:
            return jsonify({"success": False, "message": "Please provide a valid 10-character PAN Card number."})

        # Save PAN & Employment details to user profile if not present
        if str(accNo) in bank.user_details_db:
            bank.user_details_db[str(accNo)]["pan"] = pan
            bank.user_details_db[str(accNo)]["employment_type"] = employment_type
            save_profiles(bank.user_details_db)

        # Option 4: Apply Loan requires Account Number then Amount
        out = bank.execute("4", [accNo, amount])
        res_str = parse_output(out)

        if "approved" in res_str.lower() or "success" in res_str.lower() or "credited" in res_str.lower():
            updated_accs = bank.get_report()
            b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == accNo), "0")
            save_transaction(accNo, f"Loan Disbursal - {purpose}", f"+{amount}", b1)
            return jsonify({
                "success": True, 
                "message": "Loan approved successfully.", 
                "result": res_str,
                "loan_details": {
                    "amount": float(amount),
                    "purpose": purpose,
                    "employment_type": employment_type,
                    "cibil": cibil,
                    "pan": pan,
                    "apr": "8.5% p.a."
                }
            })

        return jsonify({"success": False, "message": "Loan processing failed: " + res_str})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/repay_loan", methods=["POST"])
def repay_loan():
    try:
        req = request.json
        accNo = str(req.get("account"))
        amount = str(req.get("amount", "0")).replace(',', '').strip()

        if not re.match(r"^\d+(\.\d*)?$", amount) or float(amount) <= 0:
            return jsonify({"success": False, "message": "Amount must be strictly greater than zero."})

        repay_amt = float(amount)
        accs = bank.get_report()
        current_acc = next((a for a in accs if str(a["account_number"]) == accNo), None)
        
        if not current_acc:
            return jsonify({"success": False, "message": "Account not found."})

        cur_bal = float(str(current_acc.get("balance", "0")).replace(',', ''))
        cur_loan = float(str(current_acc.get("loan_amount", "0")).replace(',', ''))

        if cur_loan <= 0:
            return jsonify({"success": False, "message": "You currently have zero outstanding loan obligations."})

        if cur_bal < repay_amt:
            return jsonify({"success": False, "message": f"Insufficient balance for repayment. Available balance: ₹{cur_bal:,.2f}."})

        actual_repay = min(repay_amt, cur_loan)
        out = bank.execute("5", [accNo, str(actual_repay)])
        res_str = parse_output(out)

        updated_accs = bank.get_report()
        b1 = next((a["balance"] for a in updated_accs if str(a["account_number"]) == accNo), "0")
        save_transaction(accNo, "Loan Repayment", f"-{actual_repay:.2f}", b1)

        return jsonify({
            "success": True, 
            "message": f"Loan repayment of ₹{actual_repay:,.2f} processed successfully!", 
            "result": res_str,
            "repaid_amount": actual_repay
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/loans/<acc_no>", methods=["GET"])
def get_loans(acc_no):
    import os, json
    loans = []
    
    accs = bank.get_report()
    current_acc = next((a for a in accs if str(a["account_number"]) == str(acc_no)), None)
    if not current_acc:
        return jsonify({"success": False, "message": "Account not found", "loans": []})
        
    current_loan_amt = float(str(current_acc.get("loan_amount", "0")).replace(',', ''))
        
    if os.path.exists(BANK_DATA_JSON):
        try:
            with open(BANK_DATA_JSON, "r") as f:
                data = json.load(f)
                history = data.get("accounts", {}).get(str(acc_no), {}).get("history", [])
                
                # Active if there is still outstanding total loan
                status = "Active" if current_loan_amt > 0 else "Closed"
                
                # Reverse history to show latest
                for tx in reversed(history):
                    if "Loan Credit" in tx.get("type", ""):
                        amount = str(tx.get("amount", "")).replace("+", "").replace("-", "")
                        loans.append({
                            "type": "Personal Loan",
                            "date": tx.get("date", "").split(" ")[0],
                            "amount": amount,
                            "status": status,
                            "id": f"#LN-{len(loans)+1000}" 
                        })
        except Exception:
            pass
            
    return jsonify({"success": True, "loans": loans})

@app.route("/api/statement/<acc_no>")
@app.route("/api/statement_pdf/<acc_no>")
def get_statement_pdf(acc_no):
    accounts = bank.get_report()
    acc_data = next((a for a in accounts if str(a["account_number"]) == str(acc_no)), None)
    if not acc_data:
        # Fallback to local profile database if not yet polled from C++
        details = bank.user_details_db.get(str(acc_no), {})
        acc_data = {
            "account_number": str(acc_no),
            "name": details.get("name", f"Account #{acc_no}"),
            "balance": details.get("balance", "0.00"),
            "email": details.get("email", "support@credence.bank"),
            "address": details.get("address", "Digital Banking Customer")
        }
        
    history = []
    if os.path.exists(BANK_DATA_JSON):
        try:
            with open(BANK_DATA_JSON, "r") as f:
                data = json.load(f)
                history = data.get("accounts", {}).get(str(acc_no), {}).get("history", [])
        except Exception:
            pass

    bal_num = float(str(acc_data.get("balance", "0")).replace(',', ''))
    if not history and bal_num > 0:
        history = [{
            "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "type": "Initial Account Deposit",
            "amount": f"+{bal_num:.2f}",
            "balance": f"{bal_num:.2f}"
        }]
            
    try:
        if os.path.exists(PROFILES_JSON):
            with open(PROFILES_JSON, "r") as pf:
                profiles = json.load(pf)
                profile = profiles.get(str(acc_no), {})
                if "email" in profile:
                    acc_data["email"] = profile["email"]
                if "address" in profile:
                    acc_data["address"] = profile["address"]
                if "account_type" in profile:
                    acc_data["account_type"] = profile["account_type"]
        details = bank.user_details_db.get(str(acc_no), {})
        if "account_type" in details:
            acc_data["account_type"] = details["account_type"]
    except Exception:
        pass

    acc_data["history"] = history
    pdf_bytes = generate_pdf(acc_no, acc_data)
        
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=statement_{acc_no}.pdf'
    return response

@app.route("/api/analytics/<acc_no>", methods=["GET"])
def get_analytics(acc_no):
    accounts = bank.get_report()
    acc_data = next((a for a in accounts if str(a["account_number"]) == str(acc_no)), None)
    
    if not acc_data:
        return jsonify({"success": False, "message": "Account not found."}), 404
        
    history = []
    if os.path.exists(BANK_DATA_JSON):
        try:
            with open(BANK_DATA_JSON, "r") as f:
                data = json.load(f)
                history = data.get("accounts", {}).get(str(acc_no), {}).get("history", [])
        except Exception:
            pass

    bal_num = float(str(acc_data.get("balance", "0")).replace(',', ''))
    if not history and bal_num > 0:
        save_transaction(acc_no, "Initial Account Deposit", f"+{bal_num:.2f}", f"{bal_num:.2f}")
        history = [{
            "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "type": "Initial Account Deposit",
            "amount": f"+{bal_num:.2f}",
            "balance": f"{bal_num:.2f}"
        }]
            
    total_income = 0.0
    total_expense = 0.0
    daily_data = {}
    
    for t in history:
        amt_str = str(t.get("amount", "0")).replace(',', '')
        import re
        amt_match = re.search(r'[\d\.]+', amt_str)
        amt = float(amt_match.group()) if amt_match else 0.0
        
        t_type = str(t.get("type", "")).lower()
        is_credit = amt_str.startswith('+') or 'in' in t_type or 'received' in t_type or 'credit' in t_type or 'deposit' in t_type
        
        if is_credit:
            total_income += amt
        else:
            total_expense += amt
            
        date_str = str(t.get("date", ""))
        d_match = re.match(r'^(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', date_str)
        if d_match:
            d = d_match.group(1)
            if d not in daily_data:
                daily_data[d] = {"inc": 0.0, "exp": 0.0}
            if is_credit:
                daily_data[d]["inc"] += amt
            else:
                daily_data[d]["exp"] += amt
                
    if total_income == 0.0 and bal_num > 0:
        total_income = bal_num

    analytics_payload = {
        "success": True,
        "balance": bal_num,
        "total_deposits": total_income,
        "total_withdrawals": total_expense,
        "loan_amount": float(str(acc_data.get("loan_amount", "0")).replace(',', '')),
        "fixed_deposit": float(str(acc_data.get("fixed_deposit", "0")).replace(',', '')),
        "fd_tenure": bank.user_details_db.get(str(acc_no), {}).get("fd_tenure", "12"),
        "transaction_count": len(history),
        "daily_data": daily_data
    }
    
    return jsonify(analytics_payload)

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    req = request.json
    acc_no = str(req.get("account_number"))
    email = str(req.get("email", ""))
    dob = str(req.get("dob", ""))
    
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"success": False, "message": "Invalid email formatting."})
        
    if not re.match(r"\d{4}-\d{2}-\d{2}", dob):
        return jsonify({"success": False, "message": "Date of birth must be YYYY-MM-DD"})
        
    if acc_no not in [str(a["account_number"]) for a in bank.get_report()] and acc_no != "99999999999999":
        return jsonify({"success": False, "message": "Account does not exist."})
        
    if acc_no not in bank.user_details_db:
        bank.user_details_db[acc_no] = {}
        
    bank.user_details_db[acc_no]["email"] = email
    bank.user_details_db[acc_no]["dob"] = dob
    save_profiles(bank.user_details_db)
    
    return jsonify({"success": True, "message": "Profile updated successfully"})

@app.route("/api/settings/password", methods=["POST"])
def update_password():
    req = request.json
    acc_no = str(req.get("account_number"))
    old_p = str(req.get("old_password", ""))
    new_p = str(req.get("new_password", ""))
    
    current_p = bank.user_details_db.get(acc_no, {}).get("nb_pass", "")
    if current_p and current_p != old_p:
        return jsonify({"success": False, "message": "Current password incorrect."})
        
    if len(new_p) < 4:
        return jsonify({"success": False, "message": "New password too short."})
        
    if acc_no not in bank.user_details_db:
        bank.user_details_db[acc_no] = {}
    
    bank.user_details_db[acc_no]["nb_pass"] = new_p
    save_profiles(bank.user_details_db)
    return jsonify({"success": True, "message": "Password updated successfully."})
    
@app.route("/api/settings/2fa", methods=["POST"])
def toggle_2fa():
    req = request.json
    acc_no = str(req.get("account_number"))
    if acc_no not in bank.user_details_db:
        bank.user_details_db[acc_no] = {}
    
    current = bank.user_details_db[acc_no].get("2fa_enabled", False)
    bank.user_details_db[acc_no]["2fa_enabled"] = not current
    save_profiles(bank.user_details_db)
    status = "enabled" if not current else "disabled"
    return jsonify({"success": True, "message": f"2-Factor Authentication {status}."})
    
@app.route("/api/settings/notifications", methods=["POST"])
def toggle_notifications():
    req = request.json
    acc_no = str(req.get("account_number"))
    if acc_no not in bank.user_details_db:
        bank.user_details_db[acc_no] = {}
    
    current = bank.user_details_db[acc_no].get("notifications", True)
    bank.user_details_db[acc_no]["notifications"] = not current
    save_profiles(bank.user_details_db)
    status = "enabled" if not current else "disabled"
    return jsonify({"success": True, "message": f"Notifications {status}."})

@app.route("/api/execute", methods=["POST"])
def execute_command():
    req = request.json
    choice = req.get("choice")
    inputs = req.get("inputs", [])
    out = bank.execute(str(choice), [str(i) for i in inputs])
    filtered_out = parse_output(out)
    return jsonify({"success": True, "result": filtered_out})

@app.route("/api/apply_cc", methods=["POST"])
def apply_cc():
    req = request.json
    accNo = str(req.get("accNo", ""))
    age = str(req.get("age", ""))
    income = str(req.get("income", ""))
    cibil = str(req.get("cibil", ""))
    citizenship = str(req.get("citizenship", ""))
    pan = str(req.get("pan", ""))
    address = str(req.get("address", ""))
    proof = str(req.get("proof", ""))

    if getattr(bank, 'use_fallback', False) or not bank.proc:
        try:
            age_val = int(age)
            inc_val = float(income)
            cibil_val = int(cibil)
        except:
            age_val, inc_val, cibil_val = 25, 50000, 750

        if age_val >= 21 and inc_val >= 25000 and cibil_val >= 700:
            limit_val = max(100000, int(inc_val * 2.5))
            cc_num = f"5241 9901 3412 {random.randint(1000, 9999)}"
            cvv_val = str(random.randint(100, 999))
            exp_val = f"{random.randint(1, 12):02d}/{random.randint(28, 32)}"
            
            details = bank.user_details_db.setdefault(str(accNo), {})
            details["cc_number"] = cc_num
            details["cc_cvv"] = cvv_val
            details["cc_expiry"] = exp_val
            details["cc_limit"] = str(limit_val)
            save_profiles(bank.user_details_db)
            
            msg = f"Credit Card Approved!\nCard Number : {cc_num}\nLimit       : INR {limit_val}\nExpiry Date : {exp_val}\nCVV         : {cvv_val}\nPAN No      : {pan}\n"
            return jsonify({"success": True, "result": msg})
        else:
            return jsonify({"success": False, "result": "Credit Card Application Declined: Eligibility criteria not met (Age >= 21, Income >= 25000, CIBIL >= 700)."})

    with bank.lock:
        bank.stdin.write("13\n")
        bank.stdin.flush()
        bank.stdin.write(f"{accNo}\n")
        bank.stdin.flush()
        
        bank.stdin.write(f"{age}\n{income}\n{cibil}\n{citizenship}\n")
        bank.stdin.flush()
        
        start = time.time()
        buf = ""
        passed = False
        while time.time() - start < 3.0:
            char = bank.stdout.read(1)
            if not char: break
            buf += char
            if "Enter PAN Number:" in buf:
                passed = True
                break
            if "Enter choice:" in buf:
                break
                
        if passed:
            bank.stdin.write(f"{pan}\n{address}\n{proof}\n")
            bank.stdin.flush()
            end_buf = bank._read_until("Enter choice: ")
            buf += end_buf
            
            # Extract Credit Card details
            cc_match = re.search(r"Card Number\s*:\s*([\d\s]+)", buf)
            limit_match = re.search(r"Limit\s*:\s*\D*(\d+)", buf)
            
            if cc_match:
                import random
                details = bank.user_details_db.setdefault(str(accNo), {})
                base_cc = cc_match.group(1).strip()
                if len(base_cc.replace(" ", "")) == 12:
                    base_cc += str(random.randint(1000, 9999))
                details["cc_number"] = base_cc
                details["cc_cvv"] = str(random.randint(100, 999))
                details["cc_expiry"] = f"{random.randint(1, 12):02d}/{random.randint(28, 32)}"
                if limit_match:
                    details["cc_limit"] = limit_match.group(1).strip()
                save_profiles(bank.user_details_db)
            
            
    filtered = parse_output(buf)
    return jsonify({"success": True, "result": filtered})

@app.route("/api/create_upi", methods=["POST"])
def create_upi():
    req = request.json
    acc = req.get("account")
    upi_id = req.get("upi_id")
    upi_pin = str(req.get("upi_pin", ""))
    if not acc or not upi_id or len(upi_pin) not in [4, 6]:
        return jsonify({"success": False, "message": "Missing info or invalid UPI PIN (must be 4-6 digits)"})
    details = bank.user_details_db.get(str(acc), {})
    details["upi_id"] = upi_id
    details["upi_pin_hash"] = hashlib.sha256(upi_pin.encode()).hexdigest()
    bank.user_details_db[str(acc)] = details
    save_profiles(bank.user_details_db)
    bank.execute("10", [acc, upi_id])
    return jsonify({"success": True, "message": "UPI ID Created"})

@app.route("/api/reset_upi_pin", methods=["POST"])
def reset_upi_pin():
    import hashlib
    req = request.json
    acc = req.get("account")
    upi_pin = req.get("upi_pin")
    if not acc or not upi_pin or len(str(upi_pin)) not in [4, 6]:
        return jsonify({"success": False, "message": "Invalid PIN"})
    details = bank.user_details_db.get(str(acc), {})
    details["upi_pin_hash"] = hashlib.sha256(str(upi_pin).encode()).hexdigest()
    bank.user_details_db[str(acc)] = details
    save_profiles(bank.user_details_db)
    return jsonify({"success": True, "message": "UPI PIN Reset successful"})

@app.route("/<path:path>")
def static_files(path):
    if path in ["code.html", "code"]:
        return send_ui_file("code.html")
    if path in ["code(1).html", "code1.html", "dashboard.html"]:
        return send_ui_file("code(1).html")
    if path in ["api/index", "api/index.py", "index"]:
        return send_ui_file("code.html")
    if path.startswith("api/"):
        return jsonify({"error": "API route not found"}), 404
    full_path = os.path.join(BASE_DIR, path)
    if os.path.exists(full_path):
        return send_from_directory(BASE_DIR, path)
    ui_full_path = os.path.join(BASE_DIR, "ui_code", path)
    if os.path.exists(ui_full_path):
        return send_from_directory(os.path.join(BASE_DIR, "ui_code"), path)
    return send_ui_file("code.html")

if __name__ == "__main__":
    def open_browser():
        import webbrowser
        webbrowser.open("http://127.0.0.1:5000/")
    
    threading.Timer(1.5, open_browser).start()
    app.run(port=5000, debug=False, use_reloader=False)

