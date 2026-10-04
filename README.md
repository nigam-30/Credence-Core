# Credence Core — Institutional Digital Banking & Wealth Terminal

**Credence Core** is an institutional-grade, full-stack digital banking, wealth management, and core ledger terminal. It combines a high-performance C++ core banking ledger backend with an ultra-responsive web terminal built using Python Flask, vanilla modern JavaScript, and Tailwind CSS.

---

## 🚀 Key Highlights & Feature Matrix

### 1. 🏛️ Core Banking Engine & Atomic Ledger
* **Dual Execution Architecture**: Fast C++ atomic ledger binary for local execution with 100% serverless Python fallback for cloud deployment on Vercel.
* **14-Digit Account Numbering**: Bank-grade unique account generation.
* **9-Digit Customer ID (CIF)**: Independent, unique 9-digit Customer ID generated at account opening for secure customer identification.
* **Savings vs. Current Account Classification**: Support for Personal Savings (4.0% APY) and Commercial Current Accounts (Zero-Lien, High Daily Limits).
* **PIN-Vault Privacy Architecture**: Account balance masked by default (`••••••••`) until authenticated with 4-digit security PIN.

### 2. 📈 Wealth & Capital Markets Hub
* **Fixed Deposits (FD)**: Instant booking with APY computation (up to 7.8% APY), maturity projection, and instant liquidation into primary balance.
* **Automated Mutual Fund SIP Engine**: Daily/monthly systematic investment plans with CAGR projections and instant stop/liquidation capabilities.
* **24K 99.9% Digital Gold Vault**: Live MCX spot rate synchronization, Gram-based & Rupee-based spot purchase and sell, with instantaneous liquidity.

### 3. 💳 Cards, Services & Postal Dispatches
* **Card Management**: Live Obsidian Visa Platinum, Visa Signature Metal, and RuPay Select visualizers with CVV reveal, card blocking, and ATM PIN resets.
* **Physical Debit Card Ordering**: Personalized embossed cards with custom 4-digit PIN dispatched via BlueDart Express.
* **CTS-2010 Cheque Book Ordering**: MICR-compliant physical cheque books (25, 50, or 100 leaves) with India Post SpeedPost dispatch tracking.
* **Deliveries & Dispatch Ledger**: Real-time tracking IDs and courier delivery status (**Delivered in 2-3 working days**).

### 4. 💸 Payments, Transfers & Utility Bill Desk
* **Instant Transfers**: Inter-bank and intra-bank transfers via IMPS, NEFT, and RTGS.
* **Virtual UPI ID Support**: Instant `@credence` UPI generation with PIN-secured transactions.
* **Multi-Category Bill Desk**: Instant payments for Electricity, Water, Gas, Telecom, Broadband, Credit Cards, and **Others (Custom Merchant & Utility)** with automated ledger receipts.

### 5. 📑 Statements & Official PDF Generation
* **Certified PDF Statement Generator**: Official bank statement generation with custom branding, 9-digit Customer ID, 14-digit Account Number, Opening Date, Account Classification (Savings vs Current), Debits/Credits breakdown, and opening/closing balances.

---

## 📁 Project Structure

```text
├── code.html                # Institutional Landing & Authentication Terminal
├── code(1).html             # 8-Tab Unified Banking Command Deck
├── app.js                   # Unified Modern Frontend Controller
├── flask_app.py             # Flask REST API Controller & C++ IPC Middleware
├── bank_system.exe          # Compiled C++ Core Binary (Windows)
├── vercel.json              # Vercel Serverless Deployment Configuration
├── requirements.txt         # Python Dependencies (Flask, BeautifulSoup4, ReportLab)
├── run_html_ui.bat          # 1-Click Windows Launch Script
├── bank.h                   # C++ Core Declarations
├── main.cpp                 # C++ Core Entry Point
├── account.cpp              # C++ Account Business Logic
├── credit.cpp               # C++ Deposit Logic
├── debit.cpp                # C++ Withdrawal Logic
├── fd.cpp                   # C++ Fixed Deposit Logic
├── loan.cpp                 # C++ Loan Processing
├── upi.cpp                  # C++ UPI Engine
├── cheque.cpp               # C++ Cheque Management
├── report.cpp               # C++ Account Reporting
├── utils.cpp                # C++ Utilities
├── globals.cpp              # C++ Shared Globals
├── bank_data.json           # Local Transaction Store
├── user_profiles.json       # User Profile & KYC Store
└── user_investments.json    # SIP & Gold Portfolio Store
```

---

## ⚡ Local Setup & Execution

### Option 1: 1-Click Script (Windows)
Double-click or run from command prompt:
```cmd
run_html_ui.bat
```

### Option 2: Manual Run
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the application:
   ```bash
   python flask_app.py
   ```
3. Open your browser at `http://127.0.0.1:5000/`.

---

## 🌐 Deploy to Vercel (Zero-Config)

This repository includes a production-ready `vercel.json` and serverless Python architecture:

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Deploy Credence Core Banking Platform"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. **Deploy on Vercel**:
   * Navigate to [vercel.com/new](https://vercel.com/new).
   * Import your GitHub repository.
   * Framework Preset: **Other**.
   * Click **Deploy**.

Vercel will automatically build the Python serverless function and route all API requests and UI templates seamlessly.

---

## ⚠️ Academic & Demonstration Notice
Credence Core is an educational and simulation platform developed for demonstration and engineering portfolio purposes. Do not enter real banking credentials, passwords, or sensitive financial information.
