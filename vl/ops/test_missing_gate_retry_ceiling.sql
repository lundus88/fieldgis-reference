-- Requires an exhausted queued, production-locked staging candidate.
-- Every fixture is rolled back by its subtransaction; the outer transaction is also rolled back.
BEGIN;
DO $test$
DECLARE j private.release_validation_jobs%rowtype; r jsonb; token uuid; before_gates jsonb; after_gates jsonb; k int;
BEGIN
  SELECT q.* INTO j FROM private.release_validation_jobs q JOIN public.factory_runs f ON f.id=q.factory_run_id WHERE q.state='queued' AND q.attempts>=q.max_attempts AND f.target_environment='staging' AND f.production_locked=true AND f.state='validating' ORDER BY q.created_at LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'No eligible staging regression fixture'; END IF;
  SELECT jsonb_agg(jsonb_build_object('key',gate_key,'status',status) ORDER BY gate_key) INTO before_gates FROM public.release_gates WHERE factory_run_id=j.factory_run_id;
  FOR k IN 1..3 LOOP
    BEGIN
      token:=gen_random_uuid();
      UPDATE private.release_validation_jobs SET state='leased',attempts=CASE WHEN k=1 THEN max_attempts-1 ELSE max_attempts END,lease_token=token,lease_expires_at=now()+interval '20 minutes' WHERE id=j.id;
      IF k=3 THEN
        BEGIN
          PERFORM public.complete_vrs_release_validation_job(j.id,gen_random_uuid(),true,'[]','{}',null);
          RAISE EXCEPTION 'Invalid lease was accepted';
        EXCEPTION WHEN OTHERS THEN
          IF SQLERRM <> 'invalid release validation lease' THEN RAISE; END IF;
        END;
        IF (SELECT state FROM private.release_validation_jobs WHERE id=j.id)<>'leased' THEN RAISE EXCEPTION 'Invalid lease changed state'; END IF;
      ELSE
        r:=public.complete_vrs_release_validation_job(j.id,token,true,'[]','{"regression_test":true}',null);
        IF k=1 THEN
          IF r->>'decision'<>'more_validation_required' OR (SELECT state FROM private.release_validation_jobs WHERE id=j.id)<>'queued' THEN RAISE EXCEPTION 'Below-limit retry regression'; END IF;
        ELSE
          IF r->>'decision'<>'validation_failed' OR (SELECT state FROM private.release_validation_jobs WHERE id=j.id)<>'failed' OR (SELECT state FROM public.factory_runs WHERE id=j.factory_run_id)<>'failed' OR (SELECT status FROM public.deployments WHERE id=j.deployment_id)<>'failed' THEN RAISE EXCEPTION 'Exhausted retry did not fail closed'; END IF;
        END IF;
      END IF;
      SELECT jsonb_agg(jsonb_build_object('key',gate_key,'status',status) ORDER BY gate_key) INTO after_gates FROM public.release_gates WHERE factory_run_id=j.factory_run_id;
      IF after_gates IS DISTINCT FROM before_gates OR (SELECT production_locked FROM public.factory_runs WHERE id=j.factory_run_id) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Gate or production lock changed'; END IF;
      RAISE EXCEPTION USING ERRCODE='ZX001',MESSAGE='rollback successful test fixture';
    EXCEPTION WHEN SQLSTATE 'ZX001' THEN NULL;
    END;
  END LOOP;
END
$test$;
ROLLBACK;
