# Legal & Trust Readiness Evidence — 2026-09-18

Status: **HOLD pending verified business particulars**

This document is a launch-control checklist, not a claim of regulatory approval.

## Current official basis

### Personal data
The Malaysian Personal Data Protection Act 2010 (Act 709) applies to persons processing or controlling personal data in connection with commercial transactions.

Official reference:
https://www.pdp.gov.my/ppdpv1/en/akta/application-and-non-application-of-the-act/

The Personal Data Protection Commissioner currently publishes DPO and Data Breach Notification guidance. Current FAQ guidance states that a DPO is required where processing involves more than 20,000 data subjects, more than 10,000 data subjects for sensitive/financial data, or regular and systematic monitoring such as online behaviour tracking. DPO requirements took effect from 1 June 2025.

Official reference:
https://www.pdp.gov.my/ppdpv1/en/faq/

Current DBN guidance states that qualifying personal data breaches must be notified to the Commissioner as soon as practicable and no later than 72 hours from occurrence/awareness as defined by the guidance.

Official reference:
https://www.pdp.gov.my/ppdpv1/en/guidelines-and-circulars-on-data-breach-notification-dbn/

### Electronic trade disclosures
Consumer Protection (Electronic Trade Transaction) Regulations 2024 [P.U. (A) 449/2024] came into operation on 25 December 2024 and revoked the 2012 Regulations.

Official KPDN source:
https://repositori.kpdn.gov.my/bitstream/123456789/5299/1/PERATURAN%20URUSNIAGA%20PERDAGANGAN%20DALAM%20ELEKTRONIK%202024.pdf

The Schedule requires disclosure of supplier/company name, website address if any, email and telephone, trade address, main service characteristics, full price including taxes/other costs, payment method, terms, estimated delivery/supply time, and applicable safety/health certification. The disclosure information is required in Bahasa Kebangsaan; other languages may be added.

## LUNDUS DIGITAL SYSTEMS launch posture

### Ready in RC
- service characteristics
- Terms RC
- Privacy RC
- Refund/Cancellation RC
- quotation-led full-price model
- server-authoritative checkout amount model
- order acknowledgement surface
- complaint/support architecture
- data-minimising lead/payment/notification design

### Must be verified before public transaction
- registered entity/legal name
- registration/licence particulars appropriate to the business
- final commercial domain
- official email
- official telephone
- official trade address
- final support/complaint channel
- effective dates for Privacy/Terms/Refund policies
- exact full price shown to the customer before payment
- payment method shown before confirmation
- estimated service supply/delivery time in accepted quotation/SOW
- Bahasa Malaysia disclosure available at the transaction surface

## Privacy-specific launch controls
1. Do not enable persistent behavioural profiling merely to obtain launch analytics.
2. Use transaction/operational metrics first.
3. Perform a DPO threshold assessment before introducing regular and systematic behaviour monitoring.
4. Maintain a data-breach response path that can support the current DBN timeframe.
5. Avoid storing plaintext recipient emails in notification evidence when a hash is sufficient.

LEGAL_TRUST_READY remains **HOLD** until the verified-business-particular fields are complete.
