# LD Data Governance & Retention Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: define auditable customer-data classification, retention, deletion, export and legal-hold decisions without automatically destroying or exposing customer data.

Core controls:
- classify data by sensitivity and business purpose;
- apply versioned retention policy;
- distinguish deletion request from deletion authorization;
- legal hold blocks destructive deletion where applicable;
- export requires tenant/identity authorization;
- evidence of deletion must be retained without retaining deleted payload content;
- Production deletion remains separately human-authorized.
