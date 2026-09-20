# LD Third-Party Dependency & Vendor Risk Register v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: map third-party provider risk to actual LD customer projects.

This is different from VL provider-outage resilience testing. VL proves a runtime can fail closed; this register answers which customer projects depend on a provider, how critical that dependency is, whether a fallback exists, and whether that fallback is actually verified.

## Example providers

Supabase
Vercel
Resend
payment provider
AI/model API
map/tile provider
domain/DNS registrar
object storage

## Per-dependency metadata

- affected projects
- criticality
- dependency owner
- data sensitivity
- commercial impact
- fallback availability
- fallback verification
- last verified date

## Rules

A critical dependency with no verified fallback is visible as REVIEW/HOLD.

The register does not:
- auto-switch providers;
- mutate Production;
- contact customers;
- store secrets or API keys.

Customer communication and provider migration remain separately governed consequential actions.
