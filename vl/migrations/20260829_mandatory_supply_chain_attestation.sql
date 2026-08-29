-- Mandatory cryptographic supply-chain gate for all VL builders.
-- Fail closed: only the dedicated service-role/OIDC path may set this gate PASS.

begin;

create or replace function private.guard_supply_chain_attestation_gate()
returns trigger
language plpgsql
security definer
set search_path = private, public, pg_temp
as $$
begin
  if new.gate_key = 'supply_chain_attestation'
     and new.status = 'pass'
     and old.status is distinct from 'pass'
     and coalesce(current_setting('vrs.supply_chain_authorized', true), '') <> 'true' then
    raise exception 'supply_chain_attestation PASS requires dedicated attestation authority';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_guard_supply_chain_attestation_gate on public.release_gates;
create trigger trg_guard_supply_chain_attestation_gate
before update on public.release_gates
for each row
execute function private.guard_supply_chain_attestation_gate();

create or replace function public.record_vrs_supply_chain_attestation(
  p_factory_run_id uuid,
  p_artifact_sha256 text,
  p_github_run_id text,
  p_build_workflow_run_id text,
  p_provenance_verified boolean,
  p_sbom_verified boolean,
  p_sbom_sha256 text,
  p_evidence jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = private, public, pg_temp
as $$
declare
  v_dep public.deployments%rowtype;
  v_gate public.release_gates%rowtype;
begin
  if p_factory_run_id is null then raise exception 'factory_run_id required'; end if;
  if coalesce(p_artifact_sha256,'') !~ '^[0-9a-fA-F]{64}$' then raise exception 'valid artifact SHA-256 required'; end if;
  if coalesce(p_sbom_sha256,'') !~ '^[0-9a-fA-F]{64}$' then raise exception 'valid SBOM SHA-256 required'; end if;
  if p_provenance_verified is distinct from true or p_sbom_verified is distinct from true then
    raise exception 'cryptographic provenance and SBOM verification are both required';
  end if;
  if nullif(p_github_run_id,'') is null or nullif(p_build_workflow_run_id,'') is null then
    raise exception 'GitHub attestation and build run identifiers required';
  end if;

  select * into v_dep
  from public.deployments
  where factory_run_id=p_factory_run_id
  order by created_at desc
  limit 1
  for update;
  if not found then raise exception 'deployment not found for factory run'; end if;
  if lower(coalesce(v_dep.artifact_sha256,'')) <> lower(p_artifact_sha256) then
    raise exception 'attested artifact SHA-256 does not match deployment';
  end if;

  select * into v_gate
  from public.release_gates
  where factory_run_id=p_factory_run_id and gate_key='supply_chain_attestation'
  for update;
  if not found then raise exception 'mandatory supply_chain_attestation gate not initialized'; end if;

  perform set_config('vrs.supply_chain_authorized','true',true);
  update public.release_gates
     set status='pass',
         score=1,
         checked_at=now(),
         checked_by=null,
         evidence=jsonb_build_object(
           'source','github_oidc_supply_chain_attestation',
           'artifact_sha256',lower(p_artifact_sha256),
           'sbom_sha256',lower(p_sbom_sha256),
           'provenance_verified',true,
           'sbom_verified',true,
           'attestation_workflow_run_id',p_github_run_id,
           'build_workflow_run_id',p_build_workflow_run_id,
           'verified_at',now()
         ) || coalesce(p_evidence,'{}'::jsonb)
   where factory_run_id=p_factory_run_id and gate_key='supply_chain_attestation';

  return jsonb_build_object(
    'status','pass',
    'gate_key','supply_chain_attestation',
    'factory_run_id',p_factory_run_id,
    'deployment_id',v_dep.id,
    'artifact_sha256',lower(p_artifact_sha256),
    'sbom_sha256',lower(p_sbom_sha256),
    'mandatory',true
  );
end;
$$;

revoke all on function public.record_vrs_supply_chain_attestation(uuid,text,text,text,boolean,boolean,text,jsonb) from public;
revoke all on function public.record_vrs_supply_chain_attestation(uuid,text,text,text,boolean,boolean,text,jsonb) from anon;
revoke all on function public.record_vrs_supply_chain_attestation(uuid,text,text,text,boolean,boolean,text,jsonb) from authenticated;
grant execute on function public.record_vrs_supply_chain_attestation(uuid,text,text,text,boolean,boolean,text,jsonb) to service_role;

with updated as (
  select builder_key,
         case
           when exists (
             select 1 from jsonb_array_elements(required_gates) g
             where g->>'key'='supply_chain_attestation'
           ) then required_gates
           else required_gates || jsonb_build_array(jsonb_build_object('key','supply_chain_attestation','type','supply_chain'))
         end as new_gates
  from private.builder_release_gate_profiles
)
update private.builder_release_gate_profiles p
set required_gates=u.new_gates,
    policy_version=p.policy_version+1,
    policy_sha256=encode(extensions.digest(convert_to(u.new_gates::text,'UTF8'),'sha256'),'hex'),
    updated_at=now()
from updated u
where p.builder_key=u.builder_key
  and not exists (
    select 1 from jsonb_array_elements(p.required_gates) g
    where g->>'key'='supply_chain_attestation'
  );

commit;
