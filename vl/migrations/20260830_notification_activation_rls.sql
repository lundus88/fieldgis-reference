-- Defense in depth for the private production-notification activation ledger.
-- Direct access remains limited to postgres/service_role; client roles receive
-- no table grants and no RLS policies.

revoke all on table private.notification_production_activations from anon;
revoke all on table private.notification_production_activations from authenticated;
alter table private.notification_production_activations enable row level security;

comment on table private.notification_production_activations is
  'Private fail-closed notification activation ledger. RLS enabled; direct access is service-role/postgres only.';

