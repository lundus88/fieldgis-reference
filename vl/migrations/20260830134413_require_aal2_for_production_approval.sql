create or replace function private.approve_production_release(p_deployment_id uuid, p_rationale text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'private','public','pg_temp'
as $function$
declare
  v_uid uuid:=auth.uid();
  v_aal text:=coalesce(auth.jwt()->>'aal','aal1');
  v_dep public.deployments%rowtype;
  v_run public.factory_runs%rowtype;
  v_required jsonb;
  v_missing int;
  v_approval public.approvals%rowtype;
  v_eligible_approvers int:=0;
  v_other_approvers int:=0;
  v_solo_exception boolean:=false;
begin
  if v_uid is null then raise exception 'authenticated user required'; end if;
  if v_aal <> 'aal2' then raise exception 'AAL2 MFA required for production approval'; end if;

  select * into v_dep from public.deployments where id=p_deployment_id for update;
  if not found then raise exception 'deployment not found'; end if;
  if not private.has_project_role(v_dep.project_id,array['owner','admin']) then raise exception 'owner/admin production approval required'; end if;

  if v_dep.status in ('approved','deploying','deployed') and v_dep.approved_by is not null then
    select * into v_approval from public.approvals where factory_run_id=v_dep.factory_run_id and approval_type='production_release' limit 1;
    return jsonb_build_object('decision','production_release_already_approved','deployment_id',v_dep.id,'factory_run_id',v_dep.factory_run_id,'approval_id',v_approval.id,'approved_by',v_dep.approved_by,'artifact_sha256',v_dep.artifact_sha256,'idempotent',true);
  end if;

  if v_dep.status<>'certified' then raise exception 'deployment must be technically certified before approval'; end if;
  select * into v_run from public.factory_runs where id=v_dep.factory_run_id and project_id=v_dep.project_id for update;
  if not found then raise exception 'factory run not found'; end if;
  if v_dep.workflow_id is distinct from v_run.workflow_id then raise exception 'deployment workflow mismatch'; end if;

  v_required:=private.get_deployment_required_release_gates(v_dep.id);
  select count(*) into v_missing from jsonb_array_elements(v_required) g where not exists(select 1 from public.release_gates rg where rg.factory_run_id=v_run.id and rg.gate_key=g->>'key' and rg.status='pass');
  if v_missing>0 then raise exception 'technical release gates not all PASS'; end if;

  select * into v_approval from public.approvals where factory_run_id=v_run.id and approval_type='production_release' for update;
  if not found then raise exception 'production approval record required'; end if;
  if v_approval.status='approved' then
    return jsonb_build_object('decision','production_release_already_approved','deployment_id',v_dep.id,'factory_run_id',v_run.id,'approval_id',v_approval.id,'approved_by',v_approval.decided_by,'artifact_sha256',v_dep.artifact_sha256,'idempotent',true);
  end if;
  if v_approval.status<>'pending' then raise exception 'production approval is not pending'; end if;

  select count(*) into v_eligible_approvers from public.project_members pm where pm.project_id=v_dep.project_id and pm.role in ('owner','admin');
  select count(*) into v_other_approvers from public.project_members pm where pm.project_id=v_dep.project_id and pm.role in ('owner','admin') and pm.user_id<>v_uid;

  if v_approval.requested_by=v_uid then
    if v_other_approvers>0 then
      raise exception 'production approval blocked by separation-of-duties: requester cannot approve when another owner/admin is available';
    end if;
    v_solo_exception:=true;
  end if;

  update public.approvals
  set status='approved',
      decided_by=v_uid,
      decided_at=now(),
      rationale=coalesce(nullif(p_rationale,''),rationale,case when v_solo_exception then 'Explicit solo-operator production approval; no second owner/admin available' else 'Explicit owner/admin production approval' end)
  where id=v_approval.id;

  update public.release_gates
  set status='pass',score=1,
      evidence=jsonb_build_object(
        'approval_id',v_approval.id,
        'approved_by',v_uid,
        'approved_at',now(),
        'explicit_human_approval',true,
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end,
        'eligible_approver_count',v_eligible_approvers,
        'requester_is_approver',v_approval.requested_by=v_uid
      ),
      checked_at=now(),checked_by=v_uid
  where factory_run_id=v_run.id and gate_key='human_production_approval';

  update public.release_gates
  set status='pass',score=1,
      evidence=jsonb_build_object(
        'release_unlock','approved',
        'approved_by',v_uid,
        'approved_at',now(),
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'factory_run_remains_immutable',true,
        'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end
      ),
      checked_at=now(),checked_by=v_uid
  where factory_run_id=v_run.id and gate_key='production_lock';

  update public.deployments
  set status='approved',approved_by=v_uid,
      certificate=certificate||jsonb_build_object(
        'human_approval','PASS',
        'approved_by',v_uid,
        'approved_at',now(),
        'authenticator_assurance_level',v_aal,
        'mfa_enforced',true,
        'production_release_authorized',true,
        'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end,
        'eligible_approver_count',v_eligible_approvers,
        'requester_is_approver',v_approval.requested_by=v_uid
      )
  where id=v_dep.id;

  return jsonb_build_object(
    'decision','production_release_approved',
    'deployment_id',v_dep.id,
    'factory_run_id',v_run.id,
    'approval_id',v_approval.id,
    'approved_by',v_uid,
    'artifact_sha256',v_dep.artifact_sha256,
    'next_state','approved',
    'authenticator_assurance_level',v_aal,
    'mfa_enforced',true,
    'separation_of_duties',case when v_solo_exception then 'solo_operator_exception' else 'independent_approver' end,
    'eligible_approver_count',v_eligible_approvers,
    'idempotent',false
  );
end
$function$;
