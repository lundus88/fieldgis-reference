# LD Observability & Cost Anomaly Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: detect service-health and cost anomalies early enough for human intervention without automatically disabling customer services or changing commercial terms.

Signals:
- request/error rate
- latency
- job/build failure rate
- AI/API spend
- hosting/storage spend
- third-party spend
- unusual tenant/project usage spikes
- incident correlation

Controls:
- compare current evidence against versioned baselines/thresholds;
- separate anomaly detection from root-cause conclusion;
- no automatic shutdown, throttling, price change or customer charge;
- tenant-specific anomalies must preserve organization isolation;
- alert suppression requires auditable policy;
- Production remediation remains separately authorized.
