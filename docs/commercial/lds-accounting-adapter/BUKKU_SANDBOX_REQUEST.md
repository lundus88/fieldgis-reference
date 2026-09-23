# Bukku Staging Account Request

Status: HUMAN ACTION REQUIRED

Bukku's official API documentation recommends requesting a staging account before live integration.

Send the request to:

**dev@bukku.my**

Include:

- Email Address (Login ID)
- requested Bukku staging URL/subdomain, for example: `yourcompany.staging.bukku.dev`
- requested duration: **3 months** or **6 months**
- company currency if different from MYR
- inventory system if different from Bukku's default

Suggested request:

Subject: Request for Bukku API Staging Account — LUNDUS DIGITAL SYSTEMS

Hello Bukku Developer Support,

We are integrating LUNDUS DIGITAL SYSTEMS with Bukku through the Bukku Open API and would like to request a staging account for controlled non-production testing.

Requested details:
- Login email: [YOUR EMAIL]
- Preferred staging subdomain: [YOUR PREFERRED SUBDOMAIN].staging.bukku.dev
- Duration: 6 months
- Company currency: MYR
- Inventory system: default is acceptable
- Purpose: API integration testing for customer, invoice, payment reconciliation and e-Invoice workflow.

We will use the staging environment only until our integration and reconciliation tests are complete.

Thank you.

## After Bukku supplies access

Do not commit credentials to GitHub.

Configure the execution environment only:

`LD_BUKKU_ENV=staging`

`LD_BUKKU_ACCESS_TOKEN=<staging token>`

`LD_BUKKU_COMPANY_SUBDOMAIN=<staging company subdomain>`

The adapter remains HOLD until exact API routes and schemas are verified and the sandbox Golden Transaction passes.
