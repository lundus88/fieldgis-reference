-- One-time, explicitly human-authorized remediation for the reviewed 2026-09-30 snapshot.
-- Already executed successfully for four candidates. Rerunning aborts if the reviewed set differs.
-- Does not certify or release a candidate; all missing gate evidence remains missing.
DO $repair$
DECLARE j private.release_validation_jobs%rowtype; f public.factory_runs%rowtype; d public.deployments%rowtype; w public.workflows%rowtype; before_state jsonb; after_state jsonb; missing_count int; repaired int:=0; reason text:='Validation retry budget exhausted with missing technical gate evidence; fail-closed reconciliation, PR #434 / Issue #433';
BEGIN
 FOR j IN SELECT * FROM private.release_validation_jobs WHERE state='queued' AND attempts>=max_attempts AND updated_at<'2026-09-30T08:26:50Z'::timestamptz ORDER BY created_at FOR UPDATE LOOP
  SELECT * INTO f FROM public.factory_runs WHERE id=j.factory_run_id FOR UPDATE;
  SELECT * INTO d FROM public.deployments WHERE id=j.deployment_id FOR UPDATE;
  SELECT * INTO w FROM public.workflows WHERE id=f.workflow_id FOR UPDATE;
  IF f.target_environment<>'staging' OR f.production_locked IS DISTINCT FROM true OR f.state<>'validating' OR d.status<>'planned' OR d.factory_run_id IS DISTINCT FROM f.id OR w.state<>'running' THEN RAISE EXCEPTION 'Candidate state changed; abort reconciliation'; END IF;
  SELECT count(*) INTO missing_count FROM jsonb_array_elements(private.get_deployment_required_gates(d.id)) g WHERE g->>'key' NOT IN ('human_production_approval','production_lock') AND NOT EXISTS (SELECT 1 FROM public.release_gates rg WHERE rg.factory_run_id=f.id AND rg.gate_key=g->>'key' AND rg.status='pass');
  IF missing_count=0 THEN RAISE EXCEPTION 'No missing technical gates; candidate requires separate recovery'; END IF;
  PERFORM 1 FROM public.approvals WHERE factory_run_id=f.id FOR UPDATE;
  before_state:=jsonb_build_object('job',to_jsonb(j),'run',to_jsonb(f),'deployment',to_jsonb(d),'workflow',to_jsonb(w),'approvals',(SELECT jsonb_agg(to_jsonb(a)) FROM public.approvals a WHERE a.factory_run_id=f.id));
  UPDATE private.release_validation_jobs SET state='failed',error_text=reason,finished_at=now(),updated_at=now(),result=coalesce(result,'{}')||jsonb_build_object('retry_exhausted',true,'missing_technical_gate_count',missing_count,'reconciliation','PR434') WHERE id=j.id;
  UPDATE public.deployments SET status='failed',certificate=coalesce(certificate,'{}')||jsonb_build_object('technical_validation','FAIL','error',reason) WHERE id=d.id;
  UPDATE public.factory_runs SET state='failed',error_text=reason,finished_at=now() WHERE id=f.id;
  UPDATE public.workflows SET state='failed',finished_at=now(),output=coalesce(output,'{}')||jsonb_build_object('technical_validation','FAIL','error',reason) WHERE id=w.id;
  UPDATE public.approvals SET status='expired',decided_at=now(),rationale=concat_ws(E'\n',nullif(rationale,''),reason||'; production release not authorized') WHERE factory_run_id=f.id AND status='pending' AND approval_type='production_release';
  after_state:=jsonb_build_object('job',(SELECT to_jsonb(q) FROM private.release_validation_jobs q WHERE id=j.id),'run',(SELECT to_jsonb(q) FROM public.factory_runs q WHERE id=f.id),'deployment',(SELECT to_jsonb(q) FROM public.deployments q WHERE id=d.id),'workflow',(SELECT to_jsonb(q) FROM public.workflows q WHERE id=w.id),'approvals',(SELECT jsonb_agg(to_jsonb(a)) FROM public.approvals a WHERE a.factory_run_id=f.id));
  INSERT INTO public.audit_logs(project_id,actor_user_id,action,entity_type,entity_id,metadata) VALUES(f.project_id,null,'lom.reconcile_exhausted_validation','release_validation_job',j.id::text,jsonb_build_object('before',before_state,'after',after_state,'authorization','User: baik. sila selesaikan pembaikan teknikal, 2026-09-30','production_release_authorized',false));
  repaired:=repaired+1;
 END LOOP;
 IF repaired<>4 THEN RAISE EXCEPTION 'Expected four reviewed candidates; found %; rolling back',repaired; END IF;
END $repair$;
