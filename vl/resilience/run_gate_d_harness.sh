#!/usr/bin/env bash
set -euo pipefail

DB_CONTAINER="vl-gate-d-postgres"
DB_NAME="gate_d"
DB_USER="postgres"
TMP_DIR="$(mktemp -d)"
cleanup() {
  docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

docker run -d --rm \
  --name "$DB_CONTAINER" \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB="$DB_NAME" \
  postgres:16 >/dev/null

for _ in $(seq 1 40); do
  if docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null

docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < vl/resilience/gate_d_harness.sql >/dev/null

psqlq() {
  docker exec "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atqc "$1"
}

# ---- Burst/concurrency: 24 jobs, 48 simultaneous claimers ----
psqlq "insert into gate_d.factory_runs(id) select 'burst-run-'||g from generate_series(1,24) g;"
psqlq "insert into gate_d.runner_jobs(factory_run_id,created_at) select 'burst-run-'||g, now()+(g*interval '1 millisecond') from generate_series(1,24) g;"

for i in $(seq 1 48); do
  (
    psqlq "select coalesce(gate_d.claim_runner('runner-$i')->>'job_id','IDLE');" > "$TMP_DIR/claim-$i.txt"
  ) &
done
wait
cat "$TMP_DIR"/claim-*.txt > "$TMP_DIR/claims.txt"

LEASED_COUNT=$(grep -vc '^IDLE$' "$TMP_DIR/claims.txt" || true)
IDLE_COUNT=$(grep -c '^IDLE$' "$TMP_DIR/claims.txt" || true)
DUPLICATE_JOB_IDS=$(grep -v '^IDLE$' "$TMP_DIR/claims.txt" | sort | uniq -d | wc -l | tr -d ' ')
DB_LEASED=$(psqlq "select count(*) from gate_d.runner_jobs where state='leased';")
ATTEMPT_SUM=$(psqlq "select coalesce(sum(attempts),0) from gate_d.runner_jobs;")

[[ "$LEASED_COUNT" == "24" ]]
[[ "$IDLE_COUNT" == "24" ]]
[[ "$DUPLICATE_JOB_IDS" == "0" ]]
[[ "$DB_LEASED" == "24" ]]
[[ "$ATTEMPT_SUM" == "24" ]]

# ---- Replay rejection on runner completion ----
IFS='|' read -r REPLAY_JOB REPLAY_TOKEN REPLAY_RUN < <(
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -AtF '|' -c \
    "select id,lease_token,factory_run_id from gate_d.runner_jobs where state='leased' order by created_at limit 1;"
)
psqlq "select gate_d.complete_runner('$REPLAY_JOB'::uuid,'$REPLAY_TOKEN'::uuid,true)->>'status';" | grep -qx recorded
if docker exec "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atqc \
  "select gate_d.complete_runner('$REPLAY_JOB'::uuid,'$REPLAY_TOKEN'::uuid,true);" \
  >"$TMP_DIR/replay.out" 2>"$TMP_DIR/replay.err"; then
  echo 'Replay unexpectedly succeeded' >&2
  exit 1
fi
grep -q 'invalid runner lease' "$TMP_DIR/replay.err"
[[ "$(psqlq "select state from gate_d.factory_runs where id='$REPLAY_RUN';")" == "validating" ]]

# ---- Externally effective action idempotency under concurrency ----
for i in $(seq 1 32); do
  (
    psqlq "select gate_d.record_external_action('idem-action-001','notification');" > "$TMP_DIR/idem-$i.txt"
  ) &
done
wait
cat "$TMP_DIR"/idem-*.txt > "$TMP_DIR/idem.txt"
IDEM_RECORDED=$(grep -c '^recorded$' "$TMP_DIR/idem.txt" || true)
IDEM_DUPLICATE=$(grep -c '^duplicate$' "$TMP_DIR/idem.txt" || true)
IDEM_EFFECT_COUNT=$(psqlq "select count(*) from gate_d.external_actions where action_key='idem-action-001';")
[[ "$IDEM_RECORDED" == "1" ]]
[[ "$IDEM_DUPLICATE" == "31" ]]
[[ "$IDEM_EFFECT_COUNT" == "1" ]]

# ---- Provider outage: payment, deployment and notification must fail closed ----
psqlq "insert into gate_d.adapters(adapter_key,available) values ('payment',false),('deployment',false),('notification',false);"
for adapter in payment deployment notification; do
  STATUS=$(psqlq "select gate_d.invoke_adapter('$adapter','outage-$adapter')->>'status';")
  FAIL_CLOSED=$(psqlq "select gate_d.invoke_adapter('$adapter','outage-$adapter-2')->>'fail_closed';")
  [[ "$STATUS" == "blocked" ]]
  [[ "$FAIL_CLOSED" == "true" ]]
done
OUTAGE_EFFECTS=$(psqlq "select count(*) from gate_d.external_actions where action_key like 'outage-%';")
[[ "$OUTAGE_EFFECTS" == "0" ]]

# ---- Expired lease recovery: old token invalid, reclaimed job cannot skip validation ----
psqlq "insert into gate_d.factory_runs(id) values ('recovery-run');"
psqlq "insert into gate_d.runner_jobs(factory_run_id,state,attempts,max_attempts,lease_token,leased_at,lease_expires_at,created_at) values ('recovery-run','leased',1,3,'00000000-0000-0000-0000-000000000001',now()-interval '30 minutes',now()-interval '10 minutes',now()-interval '2 hours');"
RECOVERY_JSON=$(psqlq "select gate_d.claim_runner('recovery-runner');")
RECOVERY_JOB=$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["job_id"])' <<<"$RECOVERY_JSON")
RECOVERY_TOKEN=$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["lease_token"])' <<<"$RECOVERY_JSON")
RECOVERY_ATTEMPTS=$(psqlq "select attempts from gate_d.runner_jobs where id='$RECOVERY_JOB'::uuid;")
[[ "$RECOVERY_ATTEMPTS" == "2" ]]
[[ "$RECOVERY_TOKEN" != "00000000-0000-0000-0000-000000000001" ]]

if docker exec "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atqc \
  "select gate_d.complete_runner('$RECOVERY_JOB'::uuid,'00000000-0000-0000-0000-000000000001'::uuid,true);" \
  >"$TMP_DIR/old-lease.out" 2>"$TMP_DIR/old-lease.err"; then
  echo 'Expired/old lease unexpectedly completed recovery job' >&2
  exit 1
fi
grep -q 'invalid runner lease' "$TMP_DIR/old-lease.err"
psqlq "select gate_d.complete_runner('$RECOVERY_JOB'::uuid,'$RECOVERY_TOKEN'::uuid,true)->>'factory_run_state';" | grep -qx validating
RECOVERY_STATE=$(psqlq "select state from gate_d.factory_runs where id='recovery-run';")
[[ "$RECOVERY_STATE" == "validating" ]]
[[ "$RECOVERY_STATE" != "awaiting_approval" ]]
[[ "$RECOVERY_STATE" != "approved" ]]
[[ "$RECOVERY_STATE" != "production" ]]

# ---- Cost/rate-limit semantics for customer and founder/internal modes ----
psqlq "insert into gate_d.usage_counters(account_id,mode,metric_key,window_start,used_count,limit_count) values ('customer-1','customer','factory_jobs',current_date,9,10),('founder-1','founder','factory_jobs',current_date,9,10);"
CUSTOMER_BLOCK=$(psqlq "select gate_d.consume_usage('customer-1','customer','factory_jobs',2,false,null)->>'status';")
CUSTOMER_OVERRIDE_BLOCK=$(psqlq "select gate_d.consume_usage('customer-1','customer','factory_jobs',2,true,'not allowed')->>'status';")
FOUNDER_BLOCK=$(psqlq "select gate_d.consume_usage('founder-1','founder','factory_jobs',2,false,null)->>'status';")
FOUNDER_OVERRIDE=$(psqlq "select gate_d.consume_usage('founder-1','founder','factory_jobs',2,true,'bounded emergency test')->>'status';")
CUSTOMER_USED=$(psqlq "select used_count from gate_d.usage_counters where account_id='customer-1';")
FOUNDER_USED=$(psqlq "select used_count from gate_d.usage_counters where account_id='founder-1';")
FOUNDER_AUDIT=$(psqlq "select count(*) from gate_d.usage_audit where account_id='founder-1' and override_used=true and reason='bounded emergency test';")
[[ "$CUSTOMER_BLOCK" == "blocked" ]]
[[ "$CUSTOMER_OVERRIDE_BLOCK" == "blocked" ]]
[[ "$FOUNDER_BLOCK" == "blocked" ]]
[[ "$FOUNDER_OVERRIDE" == "recorded" ]]
[[ "$CUSTOMER_USED" == "9" ]]
[[ "$FOUNDER_USED" == "11" ]]
[[ "$FOUNDER_AUDIT" == "1" ]]

cat > gate-d-evidence.json <<EOF
{
  "schema_version": "vl.gate-d-evidence/1",
  "environment": "ephemeral-postgres-ci",
  "production_mutation": false,
  "burst": {
    "queued_jobs": 24,
    "parallel_claimers": 48,
    "leased": $LEASED_COUNT,
    "idle": $IDLE_COUNT,
    "duplicate_job_ids": $DUPLICATE_JOB_IDS,
    "attempt_sum": $ATTEMPT_SUM,
    "pass": true
  },
  "replay": {
    "runner_completion_replay_rejected": true,
    "externally_effective_parallel_attempts": 32,
    "recorded": $IDEM_RECORDED,
    "duplicates": $IDEM_DUPLICATE,
    "effective_action_rows": $IDEM_EFFECT_COUNT,
    "pass": true
  },
  "provider_outage": {
    "adapters": ["payment", "deployment", "notification"],
    "blocked_effective_actions": $OUTAGE_EFFECTS,
    "fail_closed": true,
    "pass": true
  },
  "recovery": {
    "expired_lease_reclaimed": true,
    "old_lease_rejected": true,
    "attempt_after_reclaim": $RECOVERY_ATTEMPTS,
    "post_completion_state": "$RECOVERY_STATE",
    "skipped_human_approval": false,
    "pass": true
  },
  "cost_rate_limit_policy_harness": {
    "customer_over_limit_blocked": true,
    "customer_override_forbidden": true,
    "founder_over_limit_without_override_blocked": true,
    "founder_override_accounted": true,
    "founder_override_audit_rows": $FOUNDER_AUDIT,
    "pass": true,
    "note": "Policy harness evidence only; production founder/internal implementation remains separately gated by issue #70."
  },
  "overall": "PASS"
}
EOF

python3 -m json.tool gate-d-evidence.json >/dev/null
echo 'VL GATE D EPHEMERAL RESILIENCE HARNESS: PASS'
cat gate-d-evidence.json
