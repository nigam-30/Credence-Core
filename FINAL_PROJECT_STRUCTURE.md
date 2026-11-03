# CREDENCE CORE — FINAL PROJECT STRUCTURE

## Overview
This document defines the final, cleaned, and organized directory structure of the Credence Core repository following Phase 6.4 cleanup.

---

```
Credence-Core/
│
├── .github/
│   └── workflows/
│       └── ci.yml                     # GitHub Actions CI/CD automated pipeline
│
├── alembic/
│   ├── versions/
│   │   └── ba89bcee5f71_create_initial_banking_schema.py # 18 module initial schema
│   ├── env.py                         # Alembic migration environment
│   ├── README                         # Alembic readme
│   └── script.py.mako                 # Migration template
│
├── api/
│   └── index.py                       # Serverless WSGI adapter (Vercel)
│
├── backend/
│   └── app/
│       ├── api/                       # Modular REST API Blueprint Controllers
│       │   ├── __init__.py            # Blueprint registry
│       │   ├── account_routes.py      # /api/accounts, /api/user_details
│       │   ├── admin_routes.py        # /api/admin/* (freeze, limits, audit, disputes)
│       │   ├── auth_routes.py         # /api/login, /api/logout, /api/register
│       │   ├── beneficiary_routes.py  # /api/beneficiaries
│       │   ├── card_routes.py         # /api/cards/* (freeze, limits, pin)
│       │   ├── dispute_routes.py      # /api/disputes
│       │   ├── docs_routes.py         # /api/docs (Swagger UI), /api/openapi.json
│       │   ├── frontend_routes.py     # /, /dashboard, /account, /app.js
│       │   ├── health_routes.py       # /health/live, /health/ready, /health/metrics
│       │   ├── investment_routes.py   # /api/investments, /api/sip, /api/gold, /api/ipo
│       │   ├── ledger_routes.py       # /api/ledger/reconcile, /api/ledger/reverse
│       │   ├── loan_routes.py         # /api/loans/* (apply, repay, schedule)
│       │   ├── notification_routes.py # /api/notifications
│       │   ├── payment_routes.py      # /api/pay_bill
│       │   ├── settings_routes.py     # /api/settings/* (mfa, password, theme)
│       │   ├── statement_routes.py    # /api/statement/download (PDF)
│       │   ├── support_routes.py      # /api/support/tickets
│       │   ├── transfer_routes.py     # /api/transfer, /api/deposit, /api/withdraw
│       │   └── upi_routes.py          # /api/upi/* (pay, verify, create)
│       │
│       ├── core/                      # Core System Configuration & Security
│       │   ├── __init__.py
│       │   ├── config.py              # Configuration profiles (Dev, Test, Prod)
│       │   ├── database.py            # Database engine & session bindings
│       │   ├── financial_policy.py    # Transaction limits, cooling periods
│       │   ├── logging.py             # Security audit logger & privacy masking
│       │   ├── mfa.py                 # TOTP enrollment, verify, AES-256-GCM encryption
│       │   ├── redis_client.py        # Distributed Redis client & memory fallback
│       │   └── security.py            # Argon2id password/PIN verification, CSRF
│       │
│       ├── middleware/                # HTTP Pipeline Interceptors
│       │   ├── __init__.py            # Security headers & CSP application
│       │   ├── auth_middleware.py     # Session verification & token extraction
│       │   ├── cors_middleware.py     # Whitelist-based CORS handler
│       │   ├── csrf_middleware.py     # Bound CSRF token validation
│       │   ├── error_handlers.py      # Uniform JSON exception handling
│       │   ├── metrics_middleware.py  # Latency & throughput telemetry
│       │   └── rate_limiter.py        # Distributed sliding-window rate limiters
│       │
│       ├── models/                    # Domain Model Re-exports
│       │   └── __init__.py            # Clean exports of all 18 SQLAlchemy models
│       │
│       ├── repositories/              # Database Access Layer (SQLAlchemy ORM)
│       │   ├── __init__.py
│       │   ├── account_repository.py
│       │   ├── base_repository.py
│       │   ├── card_repository.py
│       │   ├── investment_repository.py
│       │   ├── loan_repository.py
│       │   ├── transaction_repository.py
│       │   └── user_repository.py
│       │
│       ├── schemas/                   # Centralized Input Validation
│       │   ├── __init__.py
│       │   └── validators.py          # Account, PIN, password, PAN, UPI, Decimal
│       │
│       ├── services/                  # Decoupled Business Logic
│       │   ├── __init__.py
│       │   ├── accounts/              # AccountService
│       │   ├── admin/                 # AdminService
│       │   ├── analytics/             # AnalyticsService
│       │   ├── authentication/        # AuthService
│       │   ├── beneficiaries/         # BeneficiaryService
│       │   ├── cards/                 # CardService
│       │   ├── disputes/              # DisputeService
│       │   ├── fraud/                 # FraudService
│       │   ├── investments/           # InvestmentService
│       │   ├── ledger/                # LedgerService
│       │   ├── loans/                 # LoanService
│       │   ├── notifications/         # NotificationService
│       │   ├── payments/              # PaymentService
│       │   ├── statements/            # StatementService
│       │   ├── support/               # SupportService
│       │   └── transfers/             # TransferService
│       │
│       ├── utils/                     # Utility Modules
│       │   ├── __init__.py
│       │   ├── cpp_bench.py           # High-performance C++ benchmark harness
│       │   ├── currency.py            # Integer subunit (paise) conversions
│       │   └── pdf_generator.py       # Certified ReportLab PDF statement generator
│       │
│       └── __init__.py                # Canonical Application Factory (create_app)
│
├── docs/                              # Centralized Architectural Documentation
│   ├── architecture/
│   │   ├── API_INVENTORY.md           # Complete REST API specification
│   │   ├── ARCHITECTURE.md            # System design & component boundaries
│   │   └── DATA_FLOW.md               # End-to-end data lifecycle
│   ├── database/
│   │   ├── DATABASE_SCHEMA.md         # 18 Relational tables & ER schema
│   │   ├── FINANCIAL_INTEGRITY.md     # Double-entry general ledger principles
│   │   └── MIGRATION_GUIDE.md         # Database migration documentation
│   ├── deployment/
│   │   └── DEPLOYMENT_GUIDE.md        # Docker, Render, and production guide
│   ├── development/                   # Development guides
│   ├── security/
│   │   ├── API_SECURITY_MATRIX.md     # Endpoint permissions & roles matrix
│   │   ├── FRAUD_ENGINE.md            # Anomaly scoring and rule definitions
│   │   ├── LOGGING_PRIVACY.md         # PII masking & audit log standards
│   │   └── MFA_RELIABILITY.md         # Multi-factor authentication architecture
│   └── testing/
│       └── QA_TEST_STRATEGY.md        # Test suite architecture & QA methodology
│
├── scripts/                           # Operations & Deployment Automation
│   ├── backup.sh                      # Shell backup wrapper
│   ├── restore.sh                     # Shell restore wrapper
│   ├── db_backup.py                   # Atomic database backup script
│   ├── db_restore.py                  # Disaster recovery database restore
│   ├── migrate_ledger_to_canonical.py # Ledger entry migration
│   ├── run_local.bat                  # Local development batch runner
│   └── run_migrations.py              # Pre-deployment migration runner
│
├── tests/                             # Comprehensive Automated Test Suite (93 tests)
│   ├── fixtures/
│   │   └── synthetic_banking_fixtures.json # Sanitized test data
│   ├── qa/
│   │   ├── __init__.py
│   │   ├── test_api_regression.py     # E2E API contract regression tests
│   │   ├── test_authentication.py     # Auth, session, brute-force tests
│   │   ├── test_backup_recovery.py    # Backup & disaster recovery verification
│   │   ├── test_concurrency_stress.py # High-concurrency race condition tests
│   │   ├── test_load_performance.py   # Latency & throughput benchmarks
│   │   └── test_penetration_security.py # OWASP Top 10 penetration testing
│   ├── __init__.py
│   ├── test_advanced_banking_features.py
│   ├── test_architecture_refactoring.py
│   ├── test_database_migration.py
│   ├── test_financial_integrity.py
│   ├── test_phase6_1_remediation.py
│   ├── test_phase6_2_security.py
│   ├── test_phase6_3_hardening.py
│   └── test_security.py
│
├── account.cpp                        # C++ Account handling implementation
├── bank.h                            # C++ Banking Engine Header & Structs
├── cheque.cpp                         # C++ Chequebook issuing logic
├── credit.cpp                         # C++ Deposit / credit logic
├── debit.cpp                          # C++ Withdrawal / debit logic
├── fd.cpp                             # C++ Fixed deposit calculation logic
├── globals.cpp                        # C++ Global registry state
├── loan.cpp                           # C++ Loan disbursement & repayment logic
├── main.cpp                           # C++ Interactive CLI & harness entrypoint
├── report.cpp                         # C++ Account summary reports
├── upi.cpp                            # C++ UPI transaction logic
├── utils.cpp                          # C++ Search, validation, string utilities
├── CMakeLists.txt                     # C++ compilation configuration
│
├── app.js                             # Consolidated frontend banking client logic
├── code.html                          # Responsive landing and login view
├── code(1).html                       # Consolidated banking dashboard & wealth view
│
├── database.py                        # Authoritative database connection pool
├── ledger.py                          # Authoritative double-entry financial ledger
├── models.py                          # Authoritative 18 SQLAlchemy domain models
├── security.py                        # Authoritative security core & Argon2id hasher
├── flask_app.py                       # Thin backward-compatibility application shim
│
├── gunicorn_config.py                 # Production WSGI server configuration
├── Dockerfile                         # Production container image specification
├── docker-compose.yml                 # Production compose stack (App + Postgres + Redis)
├── docker-compose.dev.yml             # Development compose stack
├── render.yaml                        # Render.com deployment blueprint
├── vercel.json                        # Vercel serverless routing rewrite configuration
├── requirements.txt                   # Production direct runtime dependencies (14 packages)
├── requirements.lock                  # Pinned reproducible dependency lockfile
├── requirements-dev.txt               # Development & test dependencies
├── alembic.ini                        # Alembic database migration configuration
├── .gitignore                         # Comprehensive Git exclusion policy
├── .dockerignore                      # Container build exclusion policy
├── .env.example                       # Environment configuration template
│
├── README.md                          # Production GitHub release README
├── LICENSE                            # MIT License with educational disclaimer
├── SECURITY.md                        # Security policy & vulnerability reporting
├── CONTRIBUTING.md                    # Contribution guide & standards
├── ARCHITECTURE.md                    # High-level architecture documentation
│
├── CLEANUP_REPORT.md                  # Phase 6.4 cleanup summary & metrics
├── REMOVED_FILES_MANIFEST.md          # Complete manifest of removed artifacts
├── DEPENDENCY_CLEANUP_REPORT.md       # Python dependency analysis & pruning
├── GIT_HYGIENE_REPORT.md              # Git history & secret scanning report
├── FINAL_PROJECT_STRUCTURE.md         # Directory layout documentation
└── POST_CLEANUP_TEST_REPORT.md        # Post-cleanup automated test results
```
