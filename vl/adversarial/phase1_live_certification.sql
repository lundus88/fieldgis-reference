-- VL Phase 1 live adversarial certification.
-- Every mutation is enclosed in this transaction and rolled back.
begin;

create temp table vl_phase1_results (
  test_name text primary key,
  status text not null check (status in ('PASS','FAIL')),
  evidence text not null
) on commit drop;

do $$
declare
  j1 private.runner_jobs%rowtype;
  j2 private.runner_jobs%rowtype;
  dep public.deployments%rowtype;
  art public.factory_artifacts%rowtype;
  profile private.builder_release_gate_profiles%rowtype;
  before_snapshot jsonb;
  test_project uuid;
  test_org uuid;
  member_uid uuid;
  hidden_count int;
  other_run uuid;
begin
  select * into j1 from private.runner_jobs order by created_at desc limit 1;
  select * into j2 from private.runner_jobs where id <> j1.id order by created_at desc limit 1;
  if j1.id is null or j2.id is null then raise exception 'two runner jobs required'; end if;

  -- Concurrent/cross-run callback binding: a token from job 2 must not complete job 1.
  update private.runner_jobs set state='leased', lease_token=gen_random_uuid(),
    leased_at=now(), lease_expires_at=now()+interval '10 minutes' where id in (j1.id,j2.id);
  select * into j1 from private.runner_jobs where id=j1.id;
  select * into j2 from private.runner_jobs where id=j2.id;
  begin
    perform public.complete_vrs_runner_job(j1.id,j2.lease_token,false,'{}'::jsonb,'negative test');
    insert into vl_phase1_results values ('concurrent_run_binding','FAIL','cross-job lease token was accepted');
  exception when others then
    insert into vl_phase1_results values ('concurrent_run_binding','PASS',sqlerrm);
  end;

  -- Expired lease fencing.
  update private.runner_jobs set state='leased', lease_token=gen_random_uuid(),
    leased_at=now()-interval '20 minutes', lease_expires_at=now()-interval '10 minutes' where id=j1.id;
  select * into j1 from private.runner_jobs where id=j1.id;
  begin
    perform public.complete_vrs_runner_job(j1.id,j1.lease_token,true,'{}'::jsonb,null);
    insert into vl_phase1_results values ('expired_lease_fencing','FAIL','expired lease callback was accepted');
  exception when others then
    insert into vl_phase1_results values ('expired_lease_fencing','PASS',sqlerrm);
  end;

  -- Stale callback after terminal completion.
  update private.runner_jobs set state='succeeded', lease_token=gen_random_uuid(),
    lease_expires_at=now()+interval '10 minutes' where id=j1.id;
  select * into j1 from private.runner_jobs where id=j1.id;
  begin
    perform public.complete_vrs_runner_job(j1.id,j1.lease_token,true,'{}'::jsonb,null);
    insert into vl_phase1_results values ('stale_callback','FAIL','terminal job accepted a stale callback');
  exception when others then
    insert into vl_phase1_results values ('stale_callback','PASS',sqlerrm);
  end;

  -- Frozen policy snapshot must not drift when the live builder profile changes.
  select * into dep from public.deployments where required_gates_snapshot is not null
    and builder_key_snapshot is not null order by created_at desc limit 1;
  if dep.id is null then raise exception 'snapshotted deployment required'; end if;
  before_snapshot:=dep.required_gates_snapshot;
  select * into profile from private.builder_release_gate_profiles where builder_key=dep.builder_key_snapshot;
  update private.builder_release_gate_profiles set required_gates=required_gates||jsonb_build_array(jsonb_build_object('key','phase1_drift_probe','type','technical')),
    policy_version=policy_version+1 where builder_key=profile.builder_key;
  if (select required_gates_snapshot from public.deployments where id=dep.id) is distinct from before_snapshot then
    insert into vl_phase1_results values ('frozen_policy_snapshot','FAIL','deployment snapshot changed after live policy mutation');
  else
    insert into vl_phase1_results values ('frozen_policy_snapshot','PASS','deployment required_gates_snapshot remained byte-stable');
  end if;

  -- Artifact substitution must be rejected for a release-bound immutable artifact.
  select fa.* into art from public.factory_artifacts fa join public.deployments d
    on d.factory_run_id=fa.factory_run_id and lower(d.artifact_sha256)=lower(fa.sha256)
    where d.status in ('planned','certified','approved','deploying','deployed') limit 1;
  if art.id is null then raise exception 'release-bound artifact required'; end if;
  begin
    update public.factory_artifacts set sha256=repeat('0',64) where id=art.id;
    insert into vl_phase1_results values ('artifact_substitution','FAIL','release-bound artifact SHA was mutable');
  exception when others then
    insert into vl_phase1_results values ('artifact_substitution','PASS',sqlerrm);
  end;

  -- Approval/deployment binding: changing a deployment to another run must fail closed.
  select id into other_run from public.factory_runs where id<>dep.factory_run_id limit 1;
  begin
    update public.deployments set factory_run_id=other_run where id=dep.id;
    insert into vl_phase1_results values ('approval_artifact_binding','FAIL','deployment could be rebound to a different factory run');
  exception when others then
    insert into vl_phase1_results values ('approval_artifact_binding','PASS',sqlerrm);
  end;

  -- Tenant RLS: an authenticated member must not see an injected project without membership.
  select user_id into member_uid from public.project_members limit 1;
  insert into public.organizations(name,slug,created_by)
    values ('VL Phase1 foreign tenant','vl-phase1-foreign-'||substr(gen_random_uuid()::text,1,8),member_uid)
    returning id into test_org;
  delete from public.organization_members where organization_id=test_org and user_id=member_uid;
  insert into public.projects(organization_id,name,slug,description,status,created_by)
    values (test_org,'VL Phase1 foreign tenant probe','vl-phase1-project-'||substr(gen_random_uuid()::text,1,8),'rollback-only','active',member_uid)
    returning id into test_project;
  execute 'set local role authenticated';
  perform set_config('request.jwt.claims',jsonb_build_object('sub',member_uid::text,'role','authenticated')::text,true);
  select count(*) into hidden_count from public.projects where id=test_project;
  execute 'reset role';
  if hidden_count=0 then
    insert into vl_phase1_results values ('tenant_isolation','PASS','authenticated non-member could not read foreign project');
  else
    insert into vl_phase1_results values ('tenant_isolation','FAIL','authenticated non-member read foreign project');
  end if;
end $$;

select test_name,status,evidence from vl_phase1_results order by test_name;
rollback;

