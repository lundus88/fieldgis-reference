# VL Capability Catalog

Status: proposal on feature branch; no production deployment.

## Positioning

VL is a **Governed AI Software Factory**. Users request outcomes or application types; VL selects certified builders, connectors and validation profiles underneath.

## Primary public categories

1. Business
2. E-Commerce
3. Mobile
4. Web/PWA
5. GIS & Mapping
6. AI & Agents
7. Automation
8. Finance & Trading
9. Data & Analytics
10. API & Integrations

The complete machine-readable catalog is `vl/public/vl-capabilities.json` and the customer-facing browser is `vl/public/capabilities.html`.

## Capability is not certification

A category appearing in the catalog means VL may accept and govern the request. It does **not** mean every specialist runtime already has a graduated production builder. If a required builder, connector, compiler, test harness or runtime certification is missing, the request must remain HOLD/fail-closed.

## High-risk profiles

High-risk categories include algorithmic trading/Forex EA, payment execution, consequential healthcare or legal workflows, cybersecurity, production infrastructure, insurance decision support and blockchain/wallet execution.

### Algorithmic Trading / Forex EA

Default controls:
- demo/paper trading first;
- dedicated MQL5/EA builder required before claiming native MetaTrader support;
- compile and static analysis;
- deterministic backtest;
- walk-forward or out-of-sample validation;
- drawdown and position-size caps;
- no martingale/grid by default;
- broker credentials isolated from generated code;
- independent evidence review;
- explicit human approval before live trading.

Direct prompt-to-live-trading is not permitted.

## Governance invariant

Catalog expansion must never widen production authority. Production approval remains human-only and existing sandbox, QA, security, certification and immutable-promotion gates remain authoritative.
