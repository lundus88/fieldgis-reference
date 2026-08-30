create or replace function private.request_production_rollback(p_deployment_id uuid, p_reason text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'private','public','pg_temp'
as $function$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  d public.deployments%rowtype;
  prev public.deployments%rowtype;
  v_id uuid;
  v_adapter text;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for production rollback authorization'; end if;

  select * into d from public.deployments where id=p_deployment_id for update;
  if not found then raise exception 'deployment not found'; end if;
  if not private.has_project_role(d.project_id,array['owner','admin']) then raise exception 'owner/admin rollback authorization required'; end if;

  select * into prev from public.deployments x where x.project_id=d.project_id and x.id<>d.id and x.status in ('deployed','rolled_back')
    and x.certificate->>'technical_validation'='PASS' and x.artifact_sha256 is not null
    and coalesce(x.certificate->>'provider_deployment_id',x.certificate->>'provider_url') is not null
    order by x.deployed_at desc nulls last limit 1;

  if not found then
    insert into private.production_rollback_audits(deployment_id,requested_by,state,reason,evidence)
    values(d.id,v_uid,'blocked',coalesce(p_reason,'rollback requested'),jsonb_build_object('blocker','previous certified provider deployment required','authenticator_assurance_level',v_aal,'mfa_enforced',true)) returning id into v_id;
    return jsonb_build_object('status','BLOCKED','rollback_audit_id',v_id,'reason','previous certified provider deployment required','authenticator_assurance_level',v_aal,'mfa_enforced',true);
  end if;

  v_adapter:=coalesce(d.certificate->>'promotion_adapter',d.certificate#>>'{promotion,adapter}');
  insert into private.production_rollback_audits(deployment_id,previous_deployment_id,requested_by,state,target_adapter,provider_deployment_id,artifact_sha256,reason,evidence)
  values(d.id,prev.id,v_uid,'pending',v_adapter,coalesce(prev.certificate->>'provider_deployment_id',prev.certificate->>'provider_url'),prev.artifact_sha256,p_reason,
    jsonb_build_object('deterministic_target',true,'previous_release_version',prev.release_version,'history_preserved',true,'authenticator_assurance_level',v_aal,'mfa_enforced',true)) returning id into v_id;

  update public.deployments
  set certificate=certificate||jsonb_build_object('rollback_state','pending','rollback_audit_id',v_id,'rollback_target_deployment_id',prev.id,'rollback_authorization_aal',v_aal,'rollback_mfa_enforced',true)
  where id=d.id;

  return jsonb_build_object('status','PENDING','rollback_audit_id',v_id,'previous_deployment_id',prev.id,'artifact_sha256',prev.artifact_sha256,'authenticator_assurance_level',v_aal,'mfa_enforced',true);
end
$function$;
create or replace function private.approve_notification_production_activation(p_rationale text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'private','public','pg_temp'
as $function$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  v_reg private.capability_adapter_registry%rowtype;
  v_act private.notification_production_activations%rowtype;
  v_is_owner boolean:=false;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for notification production activation approval'; end if;

  select exists(select 1 from public.project_members pm where pm.user_id=v_uid and pm.role in ('owner','admin')) into v_is_owner;
  if not v_is_owner then raise exception 'owner/admin activation approval required'; end if;

  select * into v_reg from private.capability_adapter_registry where adapter_key='resend-email-v1' for update;
  if not found then raise exception 'resend-email-v1 adapter not found'; end if;
  if coalesce(v_reg.configuration->>'sandbox_e2e_verified_at','')='' then raise exception 'sandbox E2E evidence required'; end if;
  if coalesce(v_reg.configuration->>'sandbox_reconciliation_verified_at','')='' then raise exception 'sandbox reconciliation evidence required'; end if;

  select * into v_act from private.notification_production_activations where adapter_key='resend-email-v1' for update;
  if v_act.status='approved' then
    return jsonb_build_object('ok',true,'decision','already_approved','adapter_key','resend-email-v1','approved_by',v_act.approved_by,'approved_at',v_act.approved_at,'idempotent',true,'authenticator_assurance_level',v_aal,'mfa_enforced',true);
  end if;

  update private.notification_production_activations
  set status='approved',approved_at=now(),approved_by=v_uid,
      rationale=coalesce(nullif(p_rationale,''),'Explicit owner/admin approval for controlled production alert activation'),
      evidence=jsonb_build_object(
        'explicit_human_approval',true,
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'sandbox_e2e_verified_at',v_reg.configuration->>'sandbox_e2e_verified_at',
        'sandbox_reconciliation_verified_at',v_reg.configuration->>'sandbox_reconciliation_verified_at',
        'production_runtime_config_must_be_verified_by_dispatcher',true
      )
  where adapter_key='resend-email-v1';

  return jsonb_build_object('ok',true,'decision','notification_production_activation_approved','adapter_key','resend-email-v1','approved_by',v_uid,'approved_at',now(),'idempotent',false,'authenticator_assurance_level',v_aal,'mfa_enforced',true);
end
$function$;
