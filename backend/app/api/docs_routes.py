"""
Credence Core — OpenAPI & API Documentation Controller
Serves interactive Swagger UI documentation and the OpenAPI 3.1 specification.
"""

from flask import Blueprint, jsonify, render_template_string

docs_bp = Blueprint("docs_bp", __name__)

OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "Credence Core Banking API",
        "version": "4.0.0",
        "description": "Enterprise double-entry banking simulator API with Argon2id authentication, RBAC, and ACID ledger guarantees."
    },
    "servers": [
        {"url": "/", "description": "Current Environment"}
    ],
    "paths": {
        "/api/csrf_token": {
            "get": {
                "summary": "Obtain CSRF Token",
                "description": "Generates a cryptographically random CSRF token.",
                "responses": {
                    "200": {"description": "CSRF token generated successfully"}
                }
            }
        },
        "/api/login": {
            "post": {
                "summary": "Customer Login",
                "description": "Authenticates customer using 14-digit account number and password.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "account_number": {"type": "string"},
                                    "password": {"type": "string"}
                                },
                                "required": ["account_number", "password"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Login successful"},
                    "401": {"description": "Invalid credentials"},
                    "429": {"description": "Account locked due to excessive failed attempts"}
                }
            }
        },
        "/api/account/{acc_no}": {
            "get": {
                "summary": "Get Account Details",
                "parameters": [
                    {"name": "acc_no", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "Account details object"},
                    "403": {"description": "Access denied (BOLA protection)"},
                    "404": {"description": "Account not found"}
                }
            }
        },
        "/api/transfer": {
            "post": {
                "summary": "Funds Transfer",
                "description": "Executes double-entry atomic transfer between accounts.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "to_acc": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "method": {"type": "string", "enum": ["IMPS", "NEFT", "RTGS"]},
                                    "idempotency_key": {"type": "string"}
                                },
                                "required": ["to_acc", "amount"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Transfer completed successfully"},
                    "400": {"description": "Insufficient funds or invalid parameters"},
                    "403": {"description": "Unauthorized transfer initiation"}
                }
            }
        },
        "/api/deposit": {
            "post": {
                "summary": "Cash Deposit",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "amount": {"type": "number"},
                                    "idempotency_key": {"type": "string"}
                                },
                                "required": ["amount"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Deposit completed successfully"},
                    "400": {"description": "Invalid amount"}
                }
            }
        },
        "/api/pay_bill": {
            "post": {
                "summary": "Utility Bill Payment",
                "responses": {
                    "200": {"description": "Bill payment receipt"}
                }
            }
        },
        "/api/invest/sip": {
            "post": {
                "summary": "Create Mutual Fund SIP",
                "responses": {
                    "200": {"description": "SIP registration receipt"}
                }
            }
        },
        "/api/invest/gold_buy": {
            "post": {
                "summary": "Buy 24K Digital Gold",
                "responses": {
                    "200": {"description": "Gold purchase receipt"}
                }
            }
        },
        "/api/ledger/reconcile": {
            "get": {
                "summary": "Reconcile General Ledger (Admin)",
                "responses": {
                    "200": {"description": "Ledger reconciliation report"}
                }
            }
        },
        "/api/ledger/reverse": {
            "post": {
                "summary": "Reverse Transaction (Admin)",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "reference_id": {"type": "string"},
                                    "reason": {"type": "string"}
                                },
                                "required": ["reference_id", "reason"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Reversal completed successfully"},
                    "400": {"description": "Transaction cannot be reversed or already reversed"},
                    "403": {"description": "Admin authorization required"}
                }
            }
        },
        "/api/statement_pdf/{acc_no}": {
            "get": {
                "summary": "Download Statement PDF",
                "responses": {
                    "200": {"description": "Binary PDF stream"}
                }
            }
        },
        "/api/admin/dashboard": {
            "get": {
                "summary": "Admin Operations Dashboard KPIs",
                "responses": {
                    "200": {"description": "Bank-wide operational metrics and KPIs"},
                    "403": {"description": "Administrative role required"}
                }
            }
        },
        "/api/admin/accounts/{acc_no}/freeze": {
            "post": {
                "summary": "Freeze Account (Admin)",
                "responses": {
                    "200": {"description": "Account status set to FROZEN and debits suspended"},
                    "403": {"description": "Admin authorization required"}
                }
            }
        },
        "/api/admin/accounts/{acc_no}/unfreeze": {
            "post": {
                "summary": "Unfreeze Account (Admin)",
                "responses": {
                    "200": {"description": "Account status restored to ACTIVE"},
                    "403": {"description": "Admin authorization required"}
                }
            }
        },
        "/api/admin/fraud/alerts": {
            "get": {
                "summary": "Fraud Monitoring & Suspicious Transaction Alerts (Admin)",
                "responses": {
                    "200": {"description": "List of active rule-based fraud detection alerts"},
                    "403": {"description": "Admin authorization required"}
                }
            }
        },
        "/api/disputes": {
            "post": {
                "summary": "File Transaction Dispute",
                "responses": {
                    "200": {"description": "Dispute lodged with SUBMITTED status"},
                    "400": {"description": "Invalid dispute request"}
                }
            },
            "get": {
                "summary": "List Customer Disputes",
                "responses": {
                    "200": {"description": "List of disputes for authenticated user"}
                }
            }
        },
        "/api/admin/disputes/{dispute_id}/resolve": {
            "post": {
                "summary": "Resolve Dispute with Automatic Ledger Reversal (Admin)",
                "responses": {
                    "200": {"description": "Dispute resolved and refund posted via double-entry reversal"},
                    "403": {"description": "Admin authorization required"}
                }
            }
        },
        "/api/beneficiaries": {
            "get": {
                "summary": "List Saved Beneficiaries",
                "responses": {
                    "200": {"description": "List of registered payees"}
                }
            },
            "post": {
                "summary": "Register Beneficiary",
                "responses": {
                    "200": {"description": "Beneficiary saved successfully"},
                    "400": {"description": "Validation error"}
                }
            }
        },
        "/api/beneficiaries/quick_transfer": {
            "post": {
                "summary": "Quick Transfer to Beneficiary",
                "responses": {
                    "200": {"description": "Transfer executed successfully"}
                }
            }
        },
        "/api/notifications": {
            "get": {
                "summary": "Notification Inbox",
                "responses": {
                    "200": {"description": "User notifications with unread count"}
                }
            }
        },
        "/api/support/tickets": {
            "post": {
                "summary": "Create Support Ticket",
                "responses": {
                    "200": {"description": "Support ticket created"}
                }
            },
            "get": {
                "summary": "List Support Tickets",
                "responses": {
                    "200": {"description": "Customer support tickets"}
                }
            }
        },
        "/api/analytics/insights": {
            "get": {
                "summary": "Financial Spending Insights & Cash Flow Analysis",
                "responses": {
                    "200": {"description": "Category breakdowns, inflow/outflow, and budget insights"}
                }
            }
        },
        "/api/transactions/search": {
            "get": {
                "summary": "Advanced Transaction Search and Multi-Filter",
                "responses": {
                    "200": {"description": "Filtered list of transactions matching criteria"}
                }
            }
        },
        "/api/investments/performance": {
            "get": {
                "summary": "Investment Performance & Asset Allocation Dashboard",
                "responses": {
                    "200": {"description": "Consolidated portfolio valuation, live gold quote, and SIP returns"}
                }
            }
        }
    }
}

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Credence Core API Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
    <style>body { margin: 0; background: #fafafa; }</style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({
            url: "/api/openapi.json",
            dom_id: "#swagger-ui",
            deepLinking: true,
            presets: [SwaggerUIBundle.presets.apis]
        });
    </script>
</body>
</html>
"""


@docs_bp.route("/api/openapi.json", methods=["GET"])
def get_openapi_json():
    return jsonify(OPENAPI_SPEC)


@docs_bp.route("/api/docs", methods=["GET"])
def get_swagger_ui():
    return render_template_string(SWAGGER_UI_HTML)
