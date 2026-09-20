# LD Corporate Commercial Document System v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: provide one consistent A4 document system for quotation, invoice and official receipt.

## Design

- light-premium corporate document style
- white/off-white paper
- navy structure
- restrained blue accent
- print/PDF friendly
- consistent metadata, totals, references and footer

## Numbering

- Quotation: LDS-QT-YYYY-####
- Invoice: LDS-INV-YYYY-####
- Receipt: LDS-RCP-YYYY-####

Issued references are immutable. Corrections/voids must preserve audit history.

## Data authority

The visual template is not the transaction authority.

- quotation total comes from the human-approved commercial offer;
- invoice amount must reconcile to the approved order/offer;
- receipt may show PAID only after verified provider/backend payment evidence;
- payment/reference fields should link to the authoritative ledger.

## Tax/e-Invoice boundary

These templates are normal commercial documents only.

They must not be described as Malaysian tax e-Invoices unless a separately verified MyInvois/e-Invoice compliance flow authorises that status.

## Customer issue gate

Before use with a real customer, placeholders for legal business name/registration or licence, official email, phone, address and applicable policy details must be replaced with verified current values.
